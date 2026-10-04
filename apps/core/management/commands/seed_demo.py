"""Load a demo company: organisation, SLA policies, assets, knowledge base and tickets.

Cloud servers are never invented: the monitoring page only shows servers you add and connect yourself.

    python manage.py seed_demo               # adds whatever is missing; changes and deletes nothing
    python manage.py seed_demo --if-empty    # does nothing unless the database has no users yet (used by launchers)
    python manage.py seed_demo --overwrite   # also put existing demo people, SLA targets and assets back to the demo values
    python manage.py seed_demo --reset       # delete ALL tickets and regenerate the demo tickets (explicit, destructive)

The database is the source of truth, so by default nothing that already exists is touched. Demo accounts get a
password once, when they are created (see apps/core/demo/passwords.py). Refuses to run in production, or on a
database that contains non-demo accounts. For a real company use init_helply instead.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.core.demo import simulate
from apps.core.demo.guard import require_demo_database
from apps.core.demo.legacy import remove_sample_servers
from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = "Add demo users, categories, SLA policies, assets, KB articles and tickets that are missing."

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true", help="Do nothing if the database already has users.")
        parser.add_argument("--overwrite", action="store_true",
                            help="Put existing demo people, SLA targets and assets back to the demo values.")
        parser.add_argument("--reset", action="store_true", help="Delete ALL tickets and regenerate the demo tickets.")
        parser.add_argument("--force", action="store_true", help="Skip the real-data safety check.")

    def handle(self, *args, if_empty=False, overwrite=False, reset=False, force=False, **options):
        if if_empty and User.objects.exists():
            self.stdout.write("The database already has data - nothing was changed.")
            return
        require_demo_database("Loading demo data", force)
        before = User.objects.count()
        users, _ = simulate.ensure_organisation(overwrite=overwrite)
        added = User.objects.count() - before
        self.stdout.write(f"Organisation ready: {len(users)} people ({added} added).")
        call_command("seed_kb", stdout=self.stdout)
        removed = remove_sample_servers()
        if removed:
            self.stdout.write(f"Removed {removed} sample cloud server(s) from an earlier demo version.")
        if Ticket.objects.exists() and not reset:
            self.stdout.write("Tickets already exist - left as they are (use --reset to delete and regenerate them).")
            return
        call_command("seed_tickets", replace=True, force=force, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(
            "Demo data loaded. Log in as alice (administrator), tom/tina/sam (technicians) or any employee. "
            "Accounts created just now use the password in .env (HELPLY_DEMO_PASSWORD) or, on the public site, "
            "the one-time passwords in demo-passwords.txt."
        ))
