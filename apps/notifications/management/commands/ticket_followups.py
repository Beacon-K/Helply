from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications import events
from apps.tickets import workflow
from apps.tickets.choices import Status
from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = ("Follow up resolved tickets the requester hasn't confirmed: remind after "
            "HELPLY_CONFIRM_REMINDER_DAYS, close after HELPLY_AUTO_CLOSE_DAYS. Run hourly or daily.")

    def handle(self, *args, **options):
        now = timezone.now()
        remind_days, close_days = settings.HELPLY_CONFIRM_REMINDER_DAYS, settings.HELPLY_AUTO_CLOSE_DAYS
        resolved = Ticket.objects.filter(status=Status.RESOLVED, resolved_at__isnull=False)

        closed = 0
        for ticket in resolved.filter(resolved_at__lte=now - timedelta(days=close_days)):
            workflow.auto_close(ticket, close_days)
            closed += 1

        reminded = 0
        for ticket in resolved.filter(resolved_at__lte=now - timedelta(days=remind_days),
                                      confirmation_reminded_at__isnull=True):
            ticket.confirmation_reminded_at = now
            ticket.save(update_fields=["confirmation_reminded_at", "updated_at"])
            events.confirmation_reminder(ticket)
            reminded += 1

        self.stdout.write(f"{reminded} reminder(s) sent, {closed} ticket(s) closed automatically.")
