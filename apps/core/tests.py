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

    def test_supervisor_sees_attention_list_and_workload(self):
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

    def _tmp_dir(self):
        import tempfile
        from pathlib import Path

        return Path(tempfile.mkdtemp())
