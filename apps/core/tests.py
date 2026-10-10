import os
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.ai.models import AISuggestion
from apps.core.demo.tickets import SCENARIOS
from apps.sla.services import SLAState, sla_state
from apps.tickets.choices import Status
from apps.tickets.models import Ticket, TicketEvent

os.environ.setdefault("HELPLY_DEMO_PASSWORD", "test-demo-password")


class DemoSeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def test_every_scenario_becomes_a_ticket(self):
        self.assertEqual(Ticket.objects.count(), len(SCENARIOS))

    def test_company_has_100_people_with_a_small_it_team(self):
        from collections import Counter

        from apps.accounts.models import Department, User

        self.assertEqual(User.objects.count(), 100)
        self.assertEqual(Counter(User.objects.values_list("role", flat=True)),
                         {"administrator": 1, "technician": 3, "employee": 96})
        self.assertEqual(User.objects.filter(department__name="IT").count(), 4)
        self.assertEqual(Department.objects.count(), 10)
        self.assertFalse(User.objects.filter(email="").exists())
        self.assertEqual(len(set(User.objects.values_list("email", flat=True))), 100)  # the People page needs unique emails

    def test_seeding_again_does_not_duplicate_people(self):
        from apps.accounts.models import User

        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(User.objects.count(), 100)
    def test_realistic_mix_of_states(self):
        statuses = set(Ticket.objects.values_list("status", flat=True))
        for status in (Status.NEW, Status.IN_PROGRESS, Status.ON_HOLD, Status.RESOLVED, Status.CLOSED, Status.CANCELLED):
            self.assertIn(status, statuses)
        states = {sla_state(t) for t in Ticket.objects.all()}
        self.assertTrue({SLAState.MET, SLAState.BREACHED, SLAState.PAUSED, SLAState.OK} <= states)

    def test_history_is_backdated_and_ordered(self):
        ticket = Ticket.objects.get(title="Excel crashes opening the inventory workbook")
        events = list(ticket.events.all())
        self.assertLess(events[0].created_at, events[-1].created_at)
        self.assertEqual(events[0].created_at, ticket.created_at)
        self.assertTrue(ticket.events.filter(to_status=Status.IN_PROGRESS, from_status=Status.RESOLVED).exists())  # reopened

    def test_ai_feedback_recorded(self):
        reviewed = AISuggestion.objects.filter(kind=AISuggestion.Kind.CLASSIFY, accepted__isnull=False)
        self.assertTrue(reviewed.filter(accepted=True).exists())
        self.assertTrue(reviewed.filter(accepted=False).exists())  # e.g. sales@ mailbox: AI said Email, really Access

    def test_reset_regenerates(self):
        call_command("seed_demo", reset=True, stdout=StringIO())
        self.assertEqual(Ticket.objects.count(), len(SCENARIOS))
        self.assertTrue(TicketEvent.objects.filter(kind=TicketEvent.Kind.UPDATED).exists())


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def login(self, username):
        from apps.accounts.models import User

        self.client.force_login(User.objects.get(username=username))
        return self.client.get("/")

    def test_administrator_sees_attention_list_and_workload(self):
        response = self.login("alice")
        self.assertContains(response, "Needs attention")
        self.assertContains(response, "Team workload")
        reasons = [reason for _, reason in response.context["attention"]]
        self.assertEqual(reasons, sorted(reasons, key=["breached", "at_risk", "unassigned"].index))

    def test_technician_queue_is_most_urgent_first(self):
        from apps.core.views import URGENCY

        response = self.login("tom")
        order = [URGENCY[state] for _, state in response.context["queue"]]
        self.assertEqual(order, sorted(order))

    def test_employee_sees_progress_and_confirmations(self):
        response = self.login("ava")
        self.assertContains(response, "Please confirm these are fixed")
        steps = response.context["my_open"][0][1]
        self.assertEqual([s for _, s in steps], ["current", "todo", "todo", "todo"])


class DemoPasswordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def test_shared_password_comes_from_environment_not_code(self):
        from django.contrib.auth import authenticate

        self.assertTrue(authenticate(username="alice", password=os.environ["HELPLY_DEMO_PASSWORD"]))
        self.assertIsNone(authenticate(username="alice", password="helply-demo-2026"))

    def test_public_mode_gives_each_account_its_own_password(self):
        from django.contrib.auth import authenticate

        from apps.core.demo import passwords

        with self.settings(BASE_DIR=self._tmp_dir()):
            rows = passwords.randomize()
        self.assertEqual(len({pw for _, pw in rows}), len(rows))
        user, pw = rows[0]
        self.assertTrue(authenticate(username=user.username, password=pw))
        self.assertIsNone(authenticate(username=user.username, password=os.environ["HELPLY_DEMO_PASSWORD"]))
        passwords.reset_to_shared()
        self.assertTrue(authenticate(username=user.username, password=os.environ["HELPLY_DEMO_PASSWORD"]))

    def test_public_mode_lists_the_it_team_and_saves_everyone(self):
        from pathlib import Path

        out = StringIO()
        with self.settings(BASE_DIR=self._tmp_dir()):
            call_command("demo_passwords", rotate=True, stdout=out)
            saved = (Path(self.settings_base()) / "demo-passwords.txt").read_text(encoding="utf-8")
        shown = out.getvalue()
        for username in ("alice", "tom", "tina", "sam"):
            self.assertIn(username, shown)
        self.assertEqual(shown.count("helply-"), 4)  # four passwords printed (the IT team); employees are summarised
        self.assertIn("96 employee accounts", shown)
        self.assertEqual(len([l for l in saved.splitlines() if "helply-" in l]), 100)

    def settings_base(self):
        from django.conf import settings

        return settings.BASE_DIR
    def _tmp_dir(self):
        import tempfile
        from pathlib import Path

        return Path(tempfile.mkdtemp())


class DemoDataIsLeftAloneTests(TestCase):
    """The database is the source of truth: seeding adds what is missing and never rewrites what exists."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def reseed(self, *flags, **options):
        call_command("seed_demo", *flags, stdout=StringIO(), **options)

    def test_edits_made_in_the_app_survive_seeding(self):
        from apps.accounts.models import Department, SupportGroup, User
        from apps.assets.models import Asset
        from apps.sla.models import SLAPolicy

        ava = User.objects.get(username="ava")
        ava.role, ava.first_name, ava.department = "technician", "Avery", Department.objects.get(name="Sales")
        ava.save()
        SLAPolicy.objects.filter(priority="P1").update(response_minutes=7, name="Edited")
        asset = Asset.objects.first()
        Asset.objects.filter(pk=asset.pk).update(name="Corrected name", location="Moved")
        SupportGroup.objects.get(name="Service Desk").members.remove(User.objects.get(username="sam"))
        self.reseed()
        ava.refresh_from_db()
        self.assertEqual((ava.role, ava.first_name, ava.department.name), ("technician", "Avery", "Sales"))
        self.assertEqual(SLAPolicy.objects.get(priority="P1").response_minutes, 7)
        self.assertEqual(Asset.objects.get(pk=asset.pk).name, "Corrected name")
        self.assertFalse(SupportGroup.objects.get(name="Service Desk").members.filter(username="sam").exists())

    def test_overwrite_puts_demo_values_back(self):
        from apps.accounts.models import User

        User.objects.filter(username="ava").update(role="technician", first_name="Avery")
        self.reseed("--overwrite")
        ava = User.objects.get(username="ava")
        self.assertEqual((ava.role, ava.first_name), ("employee", "Ava"))

    def test_seeding_never_changes_existing_passwords_or_tickets(self):
        from apps.accounts.models import User

        before = dict(User.objects.values_list("username", "password"))
        tickets = sorted(Ticket.objects.values_list("pk", flat=True))
        self.reseed()
        self.assertEqual(dict(User.objects.values_list("username", "password")), before)
        self.assertEqual(sorted(Ticket.objects.values_list("pk", flat=True)), tickets)  # not regenerated either

    def test_a_person_who_chose_their_own_password_keeps_it(self):
        from django.contrib.auth import authenticate

        from apps.accounts.models import User

        noah = User.objects.get(username="noah")
        noah.set_password("My-own-pass-123")
        noah.save()
        self.reseed()
        self.assertTrue(authenticate(username="noah", password="My-own-pass-123"))

    def test_if_empty_does_nothing_when_there_are_users_and_seeds_when_there_are_none(self):
        from apps.accounts.models import User

        out = StringIO()
        call_command("seed_demo", if_empty=True, stdout=out)
        self.assertIn("nothing was changed", out.getvalue())
        Ticket.objects.all().delete()
        User.objects.all().delete()
        call_command("seed_demo", if_empty=True, stdout=StringIO())
        self.assertEqual(User.objects.count(), 100)

    def test_missing_people_are_added_without_touching_the_rest(self):
        from apps.accounts.models import User

        User.objects.filter(username__in=["hannah", "ethan"]).delete()  # people without tickets can be removed
        before = dict(User.objects.values_list("username", "password"))
        self.reseed()
        self.assertEqual(User.objects.count(), 100)
        for username, password in before.items():
            self.assertEqual(User.objects.get(username=username).password, password)

    def test_demo_command_refuses_a_database_with_real_accounts(self):
        from django.core.management.base import CommandError

        from apps.accounts.models import User

        User.objects.create_user("real.person", password="x", email="real@company.com")
        with self.assertRaises(CommandError):
            self.reseed()


class NewAccountPasswordTests(TestCase):
    def test_public_site_accounts_get_their_own_password_once(self):
        import tempfile
        from pathlib import Path

        from django.contrib.auth import authenticate

        from apps.accounts.models import User

        folder = Path(tempfile.mkdtemp())
        with self.settings(BASE_DIR=folder, HELPLY_PUBLIC_HOST="helply.example"):
            call_command("seed_demo", stdout=StringIO())
            lines = [l for l in (folder / "demo-passwords.txt").read_text(encoding="utf-8").splitlines() if "helply-" in l]
            self.assertEqual(len(lines), 100)
            passwords = {l.split()[0]: l.split()[-1] for l in lines}
            self.assertEqual(len(set(passwords.values())), 100)  # nobody shares a password
            self.assertTrue(authenticate(username="alice", password=passwords["alice"]))
            self.assertIsNone(authenticate(username="alice", password=os.environ["HELPLY_DEMO_PASSWORD"]))
            hashes = dict(User.objects.values_list("username", "password"))
            call_command("seed_demo", stdout=StringIO())  # a second run adds nothing and changes nothing
            self.assertEqual(dict(User.objects.values_list("username", "password")), hashes)
            self.assertEqual(len((folder / "demo-passwords.txt").read_text(encoding="utf-8").splitlines()),
                             len(lines) + 3)  # header lines are unchanged: no new entries were written

    def test_rotate_is_the_only_thing_that_changes_existing_passwords(self):
        from apps.accounts.models import User

        call_command("seed_demo", stdout=StringIO())
        before = User.objects.get(username="alice").password
        import tempfile
        from pathlib import Path

        with self.settings(BASE_DIR=Path(tempfile.mkdtemp())):
            call_command("demo_passwords", rotate=True, stdout=StringIO())
        self.assertNotEqual(User.objects.get(username="alice").password, before)


class DemoEmailAddressTests(TestCase):
    """Demo accounts use <username>@helply.work, and nothing is ever emailed to those mailbox-less addresses."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def test_every_demo_account_uses_its_username_at_helply_work(self):
        from apps.accounts.models import User

        wrong = [u.username for u in User.objects.all() if u.email != f"{u.username}@helply.work"]
        self.assertEqual(wrong, [])
        self.assertEqual(User.objects.filter(email__iendswith="example.com").count(), 0)

    def test_demo_accounts_start_with_email_notifications_off_so_nothing_bounces(self):
        from django.core import mail

        from apps.accounts.models import User
        from apps.notifications.models import Notification
        from apps.notifications.services import notify

        self.assertEqual(User.objects.filter(email_notifications=True).count(), 0)
        ava = User.objects.get(username="ava")
        with self.captureOnCommitCallbacks(execute=True):
            notify([ava], Notification.Kind.REMINDER, "Check this", email=True)
        self.assertEqual(mail.outbox, [])  # no mailbox exists behind the address
        self.assertTrue(Notification.objects.filter(recipient=ava, title="Check this").exists())  # still shown in the app

    def test_command_rewrites_placeholders_only(self):
        from apps.accounts.models import User

        User.objects.filter(username="ava").update(email="ava@example.com", email_notifications=True)
        User.objects.filter(username="noah").update(email="", email_notifications=True)
        User.objects.filter(username="mia").update(email="mia.patel@acme-corp.com", email_notifications=True)
        out = StringIO()
        call_command("demo_emails", stdout=out)
        ava, noah, mia = (User.objects.get(username=n) for n in ("ava", "noah", "mia"))
        self.assertEqual((ava.email, ava.email_notifications), ("ava@helply.work", False))
        self.assertEqual((noah.email, noah.email_notifications), ("noah@helply.work", False))
        self.assertEqual((mia.email, mia.email_notifications), ("mia.patel@acme-corp.com", True))  # real address untouched
        self.assertIn("2 accounts now use", out.getvalue())
        again = StringIO()
        call_command("demo_emails", stdout=again)
        self.assertIn("0 accounts now use", again.getvalue())  # idempotent

    def test_command_refuses_in_production(self):
        from django.core.management.base import CommandError

        with self.settings(IS_PRODUCTION=True):
            with self.assertRaises(CommandError):
                call_command("demo_emails", stdout=StringIO())


class LoginLandingTests(TestCase):
    """The sign-in page doubles as the product introduction; the form must keep working inside it."""

    def test_page_has_the_form_the_intro_and_working_images(self):
        import re

        from django.contrib.staticfiles import finders

        page = self.client.get("/accounts/login/")
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        for needle in ('name="username"', 'name="password"', "csrfmiddlewaretoken", 'id="signin"', "IT help,", "Forgot your password?"):
            self.assertIn(needle, html)
        for src in re.findall(r'src="/static/(img/landing/[^"?]+)', html):
            self.assertIsNotNone(finders.find(src), src)
        self.assertEqual(html.count("<form"), 1)  # one form: the "Sign in" links scroll to it, they do not duplicate it

    def test_next_parameter_survives_for_the_hidden_field(self):
        html = self.client.get("/accounts/login/?next=/tickets/").content.decode()
        self.assertIn('name="next" value="/tickets/"', html)

    def test_wrong_password_shows_the_error_inside_the_card(self):
        page = self.client.post("/accounts/login/", {"username": "nobody", "password": "x"})
        self.assertContains(page, 'class="lp-alert"')
        self.assertContains(page, "Please enter a correct")
