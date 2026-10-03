"""Raise 'offline' alerts and roll raw metrics up into hourly averages.

    python manage.py monitor_check              # once (run_jobs calls this)
    python manage.py monitor_check --every 30   # keep running every 30 seconds (start-production.bat)
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from apps.monitoring import alerts, services

log = logging.getLogger(__name__)
ROLLUP_EVERY_SECONDS = 300


class Command(BaseCommand):
    help = "Check for servers that stopped reporting and keep the metric history small."

    def add_arguments(self, parser):
        parser.add_argument("--every", type=int, default=0, help="Repeat every N seconds (0 = run once).")

    def handle(self, *args, every=0, **options):
        last_rollup = 0.0
        while True:
            close_old_connections()
            try:
                raised = alerts.check_offline()
                if raised:
                    self.stdout.write(f"{timezone.localtime():%H:%M:%S} {raised} server(s) went offline - tickets raised.")
                if not every or time.monotonic() - last_rollup >= ROLLUP_EVERY_SECONDS:
                    services.rollup()
                    services.discard_abandoned()
                    last_rollup = time.monotonic()
            except Exception:  # keep watching even if one round fails
                log.exception("Monitoring check failed")
                if not every:
                    raise
            if not every:
                return
            time.sleep(max(every, 5))
