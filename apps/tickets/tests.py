from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import SupportGroup, User
from apps.sla.models import SLAPolicy

from . import services, workflow
from .choices import Priority, Status, compute_priority
from .models import Category, TicketEvent


class PriorityMatrixTests(TestCase):
    def test_matrix(self):
        self.assertEqual(compute_priority(1, 1), Priority.P1)
        self.assertEqual(compute_priority(2, 1), Priority.P2)
        self.assertEqual(compute_priority(2, 2), Priority.P3)
        self.assertEqual(compute_priority(3, 3), Priority.P4)


class WorkflowTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="x", role=User.Role.EMPLOYEE)
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        self.other_tech = User.objects.create_user("tech2", password="x", role=User.Role.TECHNICIAN)
        self.sup = User.objects.create_user("sup", password="x", role=User.Role.ADMINISTRATOR)
        group = SupportGroup.objects.create(name="Desk")
        group.members.add(self.tech)
        self.cat = Category.objects.create(name="Hardware", default_group=group, keywords="laptop,printer")
        SLAPolicy.objects.create(priority="P3", name="Medium", response_minutes=60, resolution_minutes=480)

    def make(self, **kw):
        data = dict(requester=self.emp, title="Printer jam", description="Paper stuck", impact=2, urgency=2)
        data.update(kw)
        return services.create_ticket(**data)

    def test_happy_path(self):
        t = self.make(category=self.cat)
        self.assertEqual(t.status, Status.NEW)
        self.assertIsNotNone(t.resolution_due_at)
        workflow.assign(t, self.tech, actor=self.sup)
        self.assertEqual(t.status, Status.ASSIGNED)
        workflow.perform(t, "start", self.tech)
        self.assertIsNotNone(t.first_response_at)
        workflow.perform(t, "resolve", self.tech, note="Cleared jam")
        workflow.perform(t, "close", self.emp)
        self.assertEqual(t.status, Status.CLOSED)
        self.assertEqual(t.events.filter(kind=TicketEvent.Kind.TRANSITION).count(), 3)

    def test_technician_cannot_work_someone_elses_ticket(self):
        t = self.make(category=self.cat)
        workflow.assign(t, self.tech, actor=self.sup)
        with self.assertRaises(workflow.TransitionError):
            workflow.perform(t, "start", self.other_tech)

    def test_employee_cannot_resolve(self):
        t = self.make(category=self.cat)
        workflow.assign(t, self.tech, actor=self.sup)
        workflow.perform(t, "start", self.tech)
        with self.assertRaises(workflow.TransitionError):
            workflow.perform(t, "resolve", self.emp, note="done")

    def test_resolve_requires_note(self):
        t = self.make(category=self.cat)
        workflow.assign(t, self.tech, actor=self.sup)
        workflow.perform(t, "start", self.tech)
        with self.assertRaises(workflow.TransitionError):
            workflow.perform(t, "resolve", self.tech)

    def test_illegal_transition(self):
        t = self.make(category=self.cat)
        with self.assertRaises(workflow.TransitionError):
            workflow.perform(t, "resolve", self.sup, note="skip ahead")

    def test_only_administrator_assigns(self):
        t = self.make(category=self.cat)
        with self.assertRaises(workflow.TransitionError):
            workflow.assign(t, self.tech, actor=self.tech)

    def test_ai_auto_triage_and_assign(self):
        t = self.make(title="Laptop and printer broken", description="My laptop cannot reach the printer")
        self.assertEqual(t.category, self.cat)
        self.assertTrue(t.ai_classified)
        self.assertEqual(t.status, Status.ASSIGNED)
        self.assertEqual(t.assignee, self.tech)

    def test_unclear_ticket_stays_new(self):
        t = self.make(title="Help", description="Something is wrong")
        self.assertEqual(t.status, Status.NEW)
        self.assertIsNone(t.category)


class TicketVisibilityTests(TestCase):
    def test_employee_cannot_see_others_ticket(self):
        a = User.objects.create_user("a", password="x")
        b = User.objects.create_user("b", password="x")
        t = services.create_ticket(requester=a, title="x", description="y", impact=3, urgency=3)
        self.client.force_login(b)
        self.assertEqual(self.client.get(reverse("tickets:detail", args=[t.pk])).status_code, 404)
        self.client.force_login(a)
        self.assertEqual(self.client.get(reverse("tickets:detail", args=[t.pk])).status_code, 200)


class RecategorizeTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="x")
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        self.sup = User.objects.create_user("sup", password="x", role=User.Role.ADMINISTRATOR)
        self.group = SupportGroup.objects.create(name="Desk")
        self.group.members.add(self.tech)
        self.hw = Category.objects.create(name="Hardware", default_group=self.group, keywords="laptop,printer")
        self.net = Category.objects.create(name="Network", keywords="vpn,wifi")

    def test_correcting_ai_marks_suggestion_wrong(self):
        t = services.create_ticket(requester=self.emp, title="Laptop printer", description="laptop printer vpn",
                                   impact=3, urgency=3)
        self.assertEqual(t.category, self.hw)
        workflow.recategorize(t, self.net, self.sup)
        self.assertEqual(t.category, self.net)
        self.assertFalse(t.ai_classified)
        self.assertIs(t.ai_suggestions.get(kind="classify").accepted, False)
        self.assertTrue(t.events.filter(kind=TicketEvent.Kind.UPDATED).exists())

    def test_closing_confirms_ai_category(self):
        t = services.create_ticket(requester=self.emp, title="Laptop printer", description="laptop printer",
                                   impact=3, urgency=3)
        workflow.perform(t, "start", t.assignee)
        workflow.perform(t, "resolve", t.assignee, note="fixed")
        workflow.perform(t, "close", self.emp)
        self.assertIs(t.ai_suggestions.get(kind="classify").accepted, True)

    def test_employee_cannot_recategorize(self):
        t = services.create_ticket(requester=self.emp, title="x", description="y", impact=3, urgency=3)
        with self.assertRaises(workflow.TransitionError):
            workflow.recategorize(t, self.net, self.emp)


class TicketListFilterTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="x")
        self.sup = User.objects.create_user("sup", password="x", role=User.Role.ADMINISTRATOR)
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        make = lambda title: services.create_ticket(requester=self.emp, title=title, description="d", impact=3, urgency=3)
        self.new = make("new one")
        self.assigned = workflow.assign(make("assigned one"), self.tech, actor=self.sup)
        self.cancelled = workflow.perform(make("cancelled one"), "cancel", self.emp, note="dup")
        self.client.force_login(self.sup)

    def titles(self, **params):
        return {t.title for t, _ in self.client.get(reverse("tickets:list"), params).context["rows"]}

    def test_default_is_open(self):
        self.assertEqual(self.titles(), {"new one", "assigned one"})

    def test_not_started_groups_new_and_assigned(self):
        self.assertEqual(self.titles(status="not_started"), {"new one", "assigned one"})

    def test_closed_includes_cancelled(self):
        self.assertEqual(self.titles(status="closed"), {"cancelled one"})

    def test_counts(self):
        counts = {key: n for key, _, n in self.client.get(reverse("tickets:list")).context["filters"]}
        self.assertEqual((counts["open"], counts["not_started"], counts["closed"], counts["all"]), (2, 2, 1, 3))

    def test_exact_status_still_works(self):
        self.assertEqual(self.titles(status="assigned"), {"assigned one"})
