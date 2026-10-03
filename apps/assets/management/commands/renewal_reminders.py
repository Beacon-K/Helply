from django.core.management.base import BaseCommand

from apps.assets.renewals import send_renewal_reminders


class Command(BaseCommand):
    help = "Send reminders for subscriptions and cloud servers that renew soon. Safe to run often."

    def handle(self, *args, **options):
        reminded = send_renewal_reminders()
        for asset in reminded:
            self.stdout.write(f"REMINDED  {asset.asset_tag}  {asset.name}  renews {asset.warranty_expiry}")
        self.stdout.write(f"{len(reminded)} renewal reminder(s) sent.")
