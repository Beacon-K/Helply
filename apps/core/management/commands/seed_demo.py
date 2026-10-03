"""Load a complete demo: organisation, SLA policies, assets, knowledge base and tickets.

Cloud servers are never invented: the monitoring page only shows servers you add and connect yourself.

    python manage.py seed_demo            # safe to re-run; tickets only created if none exist
    python manage.py seed_demo --reset    # regenerate all demo tickets

Demo accounts share HELPLY_DEMO_PASSWORD from the local .env file. Refuses to run in production,
or on any database that contains non-demo accounts. For a real company use init_helply instead.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.core.demo import simulate
from apps.core.demo.legacy import remove_sample_servers
from apps.core.demo.guard import require_demo_database
from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = "Load demo users, categories, SLA policies, assets, KB articles and realistic tickets."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete and regenerate all demo tickets.")
        parser.add_argument("--force", action="store_true", help="Skip the real-data safety check.")

    def handle(self, *args, reset=False, force=False, **options):
        require_demo_database("Loading demo data", force)
        users, _ = simulate.ensure_organisation()
        self.stdout.write(f"Organisation ready: {len(users)} users.")
        call_command("seed_kb", stdout=self.stdout)
        removed = remove_sample_servers()
        if removed:
            self.stdout.write(f"Removed {removed} sample cloud server(s) from an earlier demo version.")
        if Ticket.objects.exists() and not reset:
            self.stdout.write(self.style.WARNING("Tickets already exist - skipped (use --reset to regenerate)."))
            return
        call_command("seed_tickets", replace=True, force=force, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(
            "Demo data loaded. Log in as alice (administrator), tom/tina/sam (technicians) or any employee; "
            "the shared password is HELPLY_DEMO_PASSWORD in the .env file."
        ))
