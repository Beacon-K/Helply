from django.core.management.base import BaseCommand

from apps.sla.services import find_at_risk, mark_breaches, warn_at_risk


class Command(BaseCommand):
    help = "Flag SLA breaches and list at-risk tickets. Run every few minutes (cron / scheduler)."

    def handle(self, *args, **options):
        breached = mark_breaches()
        warned = warn_at_risk()
        at_risk = find_at_risk()
        for t in breached:
            self.stdout.write(self.style.ERROR(f"BREACHED  {t.reference}  {t.priority}  {t.title}"))
        for t in at_risk:
            self.stdout.write(self.style.WARNING(f"AT RISK   {t.reference}  {t.priority}  due {t.resolution_due_at:%Y-%m-%d %H:%M}"))
        self.stdout.write(f"{len(breached)} newly breached, {len(at_risk)} at risk ({len(warned)} newly notified).")
