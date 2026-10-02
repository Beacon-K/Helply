"""Load a complete demo: organisation, SLA policies, assets, knowledge base and tickets.

    python manage.py seed_demo            # safe to re-run; tickets only created if none exist
    python manage.py seed_demo --reset    # regenerate all demo tickets

Demo accounts share HELPLY_DEMO_PASSWORD from the local .env file. Never run on production.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.core.demo import simulate
from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = "Load demo users, categories, SLA policies, assets, KB articles and realistic tickets."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete and regenerate all demo tickets.")

    def handle(self, *args, reset=False, **options):
        users, _ = simulate.ensure_organisation()
        self.stdout.write(f"Organisation ready: {len(users)} users.")
        call_command("seed_kb", stdout=self.stdout)
        if Ticket.objects.exists() and not reset:
            self.stdout.write(self.style.WARNING("Tickets already exist - skipped (use --reset to regenerate)."))
            return
        call_command("seed_tickets", replace=True, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(
            "Demo data loaded. Log in as alice (supervisor), tom/tina/sam (technicians) or any employee; "
            "the shared password is HELPLY_DEMO_PASSWORD in the .env file."
        ))
