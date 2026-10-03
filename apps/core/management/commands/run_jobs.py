"""Scheduled jobs: SLA checks, ticket follow-ups, server monitoring checks and a daily database backup.

    python manage.py run_jobs              # run once (e.g. from Task Scheduler or cron)
    python manage.py run_jobs --every 5    # keep running, every 5 minutes (start-production.bat does this)
"""
import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run Helply's scheduled jobs once, or repeatedly with --every MINUTES."

    def add_arguments(self, parser):
        parser.add_argument("--every", type=int, default=0, help="Repeat every N minutes (0 = run once).")

    def handle(self, *args, every=0, **options):
        while True:
            self.run_once()
            if not every:
                return
            time.sleep(every * 60)

    def run_once(self):
        for name in ("check_sla", "ticket_followups", "monitor_check", "renewal_reminders"):
            try:
                call_command(name, stdout=self.stdout)
            except Exception:  # one failing job must not stop the others or the loop
                log.exception("Scheduled job %s failed", name)
        if self._backup_due():
            try:
                call_command("backup_db", stdout=self.stdout)
            except Exception:
                log.exception("Scheduled backup failed")

    @staticmethod
    def _backup_due():
        backups = sorted(settings.HELPLY_BACKUP_DIR.glob("helply-*"))
        if not backups:
            return True
        return datetime.fromtimestamp(backups[-1].stat().st_mtime) < datetime.now() - timedelta(hours=24)
