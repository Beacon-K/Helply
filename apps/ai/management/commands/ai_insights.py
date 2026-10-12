"""Refresh the administrator ticket analysis. run_jobs calls this; it only does work when the last one is stale.

    python manage.py ai_insights          # refresh if older than HELPLY_AI_INSIGHTS_HOURS
    python manage.py ai_insights --force  # refresh now
"""
from django.core.management.base import BaseCommand

from apps.ai import insights


class Command(BaseCommand):
    help = "Analyse recent tickets for recurring problems (administrator dashboard)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Refresh even if the last analysis is recent.")

    def handle(self, *args, force=False, **options):
        if not force and not insights.due():
            self.stdout.write("Ticket analysis is up to date.")
            return
        report = insights.generate(force=force)
        self.stdout.write(f"Ticket analysis refreshed: {len(report.stats.get('clusters', []))} recurring issue(s), "
                          f"{'explained by AI' if report.analysis else 'counted only'}.")