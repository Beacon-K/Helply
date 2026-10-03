"""Set up Helply for a real organisation (no demo data).

    python manage.py init_helply

Creates the default support groups and categories, the four SLA tiers and the
knowledge base content pack - only where they do not exist yet, so settings and
articles already changed in Helply are never overwritten. If there is no
administrator yet, it asks for the first one (the IT manager).
"""
import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.core.reference_data import SLA, ensure_categories
from apps.sla.models import SLAPolicy


class Command(BaseCommand):
    help = "Prepare Helply for a real organisation: categories, SLA tiers, knowledge base and the first administrator."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Username for the first administrator (asked if omitted).")
        parser.add_argument("--email", help="Email for the first administrator (asked if omitted).")
        parser.add_argument("--no-input", action="store_true", help="Do not prompt; skip creating a administrator.")

    def handle(self, *args, username=None, email=None, no_input=False, **options):
        with transaction.atomic():
            groups, categories = ensure_categories()
            created_sla = 0
            for priority, name, response, resolution in SLA:
                _, created = SLAPolicy.objects.get_or_create(
                    priority=priority,
                    defaults={"name": name, "response_minutes": response, "resolution_minutes": resolution},
                )
                created_sla += created
        self.stdout.write(f"Support groups: {len(groups)} | categories: {len(categories)} | "
                          f"SLA tiers added: {created_sla} (existing tiers kept)")
        call_command("seed_kb", stdout=self.stdout)

        if User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True).exists():
            self.stdout.write(self.style.SUCCESS("A administrator already exists. Helply is ready."))
            return
        if no_input:
            self.stdout.write(self.style.WARNING("No administrator yet. Run init_helply again without --no-input to create one."))
            return
        self._create_administrator(username, email)

    def _create_administrator(self, username, email):
        self.stdout.write("\nCreate the first administrator account (the IT manager):")
        username = username or input("  Username: ").strip()
        if not username:
            raise CommandError("A username is required.")
        if User.objects.filter(username=username).exists():
            raise CommandError(f"The username '{username}' is already taken.")
        email = email if email is not None else input("  Email (for notifications): ").strip()
        first_name = input("  First name: ").strip()
        last_name = input("  Last name: ").strip()
        user = User(username=username, email=email, first_name=first_name, last_name=last_name,
                    role=User.Role.ADMINISTRATOR, is_staff=True, is_superuser=True)
        while True:
            password = getpass.getpass("  Password: ")
            if password != getpass.getpass("  Password (again): "):
                self.stderr.write("  The passwords do not match.")
                continue
            try:
                validate_password(password, user)
            except ValidationError as e:
                self.stderr.write("  " + " ".join(e.messages))
                continue
            break
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Administrator '{username}' created. Sign in and add your staff under Admin > Users."))
