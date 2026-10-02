from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import SupportGroup, User
from apps.sla.models import SLAPolicy
from apps.sla.services import mark_breaches, warn_at_risk
from apps.tickets import services, workflow
from apps.tickets.choices import Status
from apps.tickets.models import Category, Ticket

from .models import Notification
from .services import email_muted


class NotificationTestBase(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="x", email="emp@example.com")
        self.tech = User.objects.create_user("tech", password="x", email="tech@example.com", role=User.Role.TECHNICIAN)
        self.sup = User.objects.create_user("sup", password="x", email="sup@example.com", role=User.Role.SUPERVISOR)
        group = SupportGroup.objects.create(name="Desk")
        group.members.add(self.tech)
        self.cat = Category.objects.create(name="Hardware", default_group=group, keywords="laptop,printer")
        SLAPolicy.objects.create(priority="P3", name="Medium", response_minutes=60, resolution_minutes=480)

    def ticket(self, **kw):
        data = dict(requester=self.emp, title="Printer jam", description="Paper stuck", impact=2, urgency=2,
                    category=self.cat)
        data.update(kw)
        return services.create_ticket(**data)

    def kinds(self, user):
        return list(Notification.objects.filter(recipient=user).order_by("pk").values_list("kind", flat=True))


class EventRuleTests(NotificationTestBase):
    def test_new_unassigned_ticket(self):
        # Emails go out only after the database transaction commits.
        with self.captureOnCommitCallbacks(execute=True):
            self.ticket()
        self.assertEqual(self.kinds(self.emp), ["received"])
        self.assertEqual(self.kinds(self.sup), ["needs_triage"])
        self.assertEqual([m.to for m in mail.outbox], [["emp@example.com"]])  # triage alert is in-app only

    def test_assignment_and_conversation(self):
        t = self.ticket()
        workflow.assign(t, self.tech, actor=self.sup)
        self.assertIn("assigned", self.kinds(self.tech))
        services.add_comment(t, self.tech, "Is it the tray 2 printer?")
        self.assertEqual(self.kinds(self.emp)[-1], "reply")
        services.add_comment(t, self.emp, "Yes, tray 2.")
        self.assertEqual(self.kinds(self.tech)[-1], "reply")

    def test_actor_is_never_notified_and_internal_notes_stay_internal(self):
        t = self.ticket()
        workflow.assign(t, self.tech, actor=self.sup)
        services.add_comment(t, self.tech, "my own note", is_internal=True)
        self.assertNotIn("note", self.kinds(self.tech))
        self.assertNotIn("note", self.kinds(self.emp))
        services.add_comment(t, self.sup, "check the fuser", is_internal=True)
        self.assertEqual(self.kinds(self.tech)[-1], "note")

    def test_resolve_asks_requester_to_confirm(self):
        t = self.ticket()
        workflow.assign(t, self.tech, actor=self.sup)
        workflow.perform(t, "start", self.tech)
        workflow.perform(t, "resolve", self.tech, note="Cleared the jam")
        note = Notification.objects.filter(recipient=self.emp, kind="resolved").get()
        self.assertIn("Cleared the jam", note.body)
        workflow.perform(t, "reopen", self.emp, note="Jammed again")
        self.assertEqual(self.kinds(self.tech)[-1], "reopened")

    def test_requester_reply_goes_to_supervisors_when_unassigned(self):
        t = self.ticket()
        services.add_comment(t, self.emp, "Any update?")
        self.assertEqual(self.kinds(self.sup)[-1], "reply")


class EmailTests(NotificationTestBase):
    def test_reply_right_after_submission_is_still_emailed(self):
        with self.captureOnCommitCallbacks(execute=True):
            t = self.ticket()
            workflow.assign(t, self.tech, actor=self.sup)
            services.add_comment(t, self.tech, "On my way")
        self.assertEqual([m.subject.split("] ")[1] for m in mail.outbox if m.to == ["emp@example.com"]],
                         ["We received your ticket", "tech replied to your ticket"])

    def test_burst_of_updates_sends_one_email(self):
        t = self.ticket()
        workflow.assign(t, self.tech, actor=self.sup)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.add_comment(t, self.tech, "first")
            services.add_comment(t, self.tech, "second")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.emp, kind="reply").count(), 2)
        self.assertIn(t.reference, mail.outbox[0].subject)
        self.assertIn(t.get_absolute_url(), mail.outbox[0].body)

    def test_email_preference_off(self):
        self.emp.email_notifications = False
        self.emp.save()
        self.ticket()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.kinds(self.emp), ["received"])

    def test_muted(self):
        with email_muted():
            self.ticket()
        self.assertEqual(mail.outbox, [])

    def test_mail_failure_does_not_break_workflow(self):
        with mock.patch("apps.notifications.services.send_mail", side_effect=OSError("smtp down")),                 self.captureOnCommitCallbacks(execute=True):
            t = self.ticket()
        self.assertTrue(Ticket.objects.filter(pk=t.pk).exists())


class ScheduledJobTests(NotificationTestBase):
    def resolved(self, days_ago):
        t = self.ticket()
        workflow.assign(t, self.tech, actor=self.sup)
        workflow.perform(t, "start", self.tech)
        workflow.perform(t, "resolve", self.tech, note="done")
        Ticket.objects.filter(pk=t.pk).update(resolved_at=timezone.now() - timedelta(days=days_ago))
        return t

    @override_settings(HELPLY_CONFIRM_REMINDER_DAYS=2, HELPLY_AUTO_CLOSE_DAYS=5)
    def test_reminder_then_auto_close(self):
        recent, stale, old = self.resolved(1), self.resolved(3), self.resolved(6)
        call_command("ticket_followups", stdout=StringIO())
        call_command("ticket_followups", stdout=StringIO())  # second run must not remind twice
        for t in (recent, stale, old):
            t.refresh_from_db()
        self.assertEqual(recent.status, Status.RESOLVED)
        self.assertEqual(stale.status, Status.RESOLVED)
        self.assertEqual(old.status, Status.CLOSED)
        self.assertEqual(Notification.objects.filter(ticket=stale, kind="reminder").count(), 1)
        self.assertTrue(Notification.objects.filter(ticket=old, recipient=self.emp, title__contains="automatically").exists())

    def test_sla_risk_warned_once_and_breach_notified(self):
        t = self.ticket()
        workflow.assign(t, self.tech, actor=self.sup)
        at_risk_time = t.created_at + timedelta(minutes=400)
        self.assertEqual(warn_at_risk(at_risk_time), [t])
        self.assertEqual(warn_at_risk(at_risk_time), [])
        self.assertIn("sla_risk", self.kinds(self.tech))
        mark_breaches(now=t.created_at + timedelta(hours=9))
        self.assertIn("sla_breach", self.kinds(self.tech))
        self.assertIn("sla_breach", self.kinds(self.sup))


class ViewTests(NotificationTestBase):
    def test_bell_list_open_and_read_all(self):
        t = self.ticket()
        self.client.force_login(self.emp)
        page = self.client.get(reverse("notifications:list"))
        self.assertContains(page, "We received your ticket")
        self.assertEqual(page.context["unread_notifications"], 1)
        self.assertEqual(self.client.get(reverse("notifications:unread")).json(), {"unread": 1})
        note = Notification.objects.get(recipient=self.emp)
        self.assertRedirects(self.client.get(reverse("notifications:open", args=[note.pk])), t.get_absolute_url())
        self.assertEqual(self.client.get(reverse("notifications:unread")).json(), {"unread": 0})

    def test_viewing_ticket_marks_its_notifications_read(self):
        t = self.ticket()
        self.client.force_login(self.emp)
        self.client.get(t.get_absolute_url())
        self.assertFalse(Notification.objects.filter(recipient=self.emp, is_read=False).exists())

    def test_cannot_open_someone_elses_notification(self):
        self.ticket()
        note = Notification.objects.get(recipient=self.sup)
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("notifications:open", args=[note.pk])).status_code, 404)

    def test_email_preference_toggle(self):
        self.client.force_login(self.emp)
        self.client.post(reverse("notifications:email_preference"), {})
        self.emp.refresh_from_db()
        self.assertFalse(self.emp.email_notifications)
