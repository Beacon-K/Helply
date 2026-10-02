from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.tickets import services
from apps.tickets.models import Ticket

from . import services as sla
from .models import SLAPolicy


class SLATests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="x")
        SLAPolicy.objects.create(priority="P1", name="Critical", response_minutes=15, resolution_minutes=240)

    def ticket(self):
        return services.create_ticket(requester=self.user, title="Server down", description="Everything down",
                                      impact=1, urgency=1)

    def test_due_dates_from_policy(self):
        t = self.ticket()
        self.assertEqual(t.priority, "P1")
        self.assertEqual(t.resolution_due_at - t.created_at, timedelta(minutes=240))
        self.assertEqual(t.response_due_at - t.created_at, timedelta(minutes=15))

    def test_pause_extends_due_date(self):
        t = self.ticket()
        due = t.resolution_due_at
        start = timezone.now()
        sla.pause(t, start)
        sla.resume(t, start + timedelta(minutes=30))
        self.assertEqual(t.resolution_due_at, due + timedelta(minutes=30))

    def test_states(self):
        t = self.ticket()
        self.assertEqual(sla.sla_state(t, t.created_at + timedelta(minutes=10)), sla.SLAState.OK)
        self.assertEqual(sla.sla_state(t, t.created_at + timedelta(minutes=200)), sla.SLAState.AT_RISK)
        self.assertEqual(sla.sla_state(t, t.created_at + timedelta(minutes=300)), sla.SLAState.BREACHED)

    def test_mark_breaches(self):
        t = self.ticket()
        breached = sla.mark_breaches(now=t.created_at + timedelta(hours=5))
        self.assertEqual([b.pk for b in breached], [t.pk])
        self.assertTrue(Ticket.objects.get(pk=t.pk).sla_breached)
        self.assertEqual(sla.mark_breaches(now=t.created_at + timedelta(hours=6)), [])  # not flagged twice
