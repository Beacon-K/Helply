"""Give every placeholder account the address <username>@helply.work.

    python manage.py demo_emails

For people whose email is blank or a reserved test address (example.com, *.test, ...), e.g. demo accounts created
before the demo company moved to helply.work. Anyone with a real address is left alone. These addresses have no
mailbox, so email notifications are switched off for the accounts that are changed (in-app notifications still
work); see apps/core/demo/people.py. Explicit and one-off: nothing runs this automatically.
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.core.demo import people
from apps.core.demo.guard import require_demo_allowed
from apps.notifications.services import email_is_blocked


class Command(BaseCommand):
    help = "Set <username>@helply.work as the email of every account whose address is blank or a reserved test address."

    def handle(self, *args, **options):
        require_demo_allowed("Rewriting email addresses")
        changed = []
        for user in User.objects.order_by("username"):
            if user.email and not email_is_blocked(user.email):
                continue  # a real address: never touched
            user.email = people.email_for(user.username)
            user.email_notifications = False
            user.save(update_fields=["email", "email_notifications"])
            changed.append(user.username)
        kept = User.objects.count() - len(changed)
        self.stdout.write(self.style.SUCCESS(f"{len(changed)} accounts now use <username>@{people.EMAIL_DOMAIN} "
                                             f"(email notifications off for them); {kept} with real addresses left alone."))