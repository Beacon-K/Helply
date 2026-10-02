from django.core.management.base import BaseCommand, CommandError

from apps.core.demo import simulate
from apps.core.demo.guard import require_demo_database
from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = "Replay the realistic demo ticket scenarios (apps/core/demo/tickets.py) through the real workflow."

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="Delete ALL existing tickets first.")
        parser.add_argument("--force", action="store_true", help="Skip the real-data safety check.")

    def handle(self, *args, replace=False, force=False, **options):
        require_demo_database("Loading demo tickets", force)
        if Ticket.objects.exists():
            if not replace:
                raise CommandError("Tickets already exist. Use --replace to delete them and regenerate the demo tickets.")
            self.stdout.write(f"Deleted {simulate.clear_tickets()} ticket-related rows.")
        try:
            tickets = simulate.run()
        except ValueError as e:
            raise CommandError(str(e)) from e
        open_count = sum(t.is_open for t in tickets)
        self.stdout.write(self.style.SUCCESS(f"Created {len(tickets)} demo tickets ({open_count} open)."))
