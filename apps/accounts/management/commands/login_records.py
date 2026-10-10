"""Read the local sign-in record. It is not shown anywhere in the web app on purpose.

    python manage.py login_records                     last 30 days, newest first
    python manage.py login_records --days 7 --user alice
    python manage.py login_records --csv               also write logs/login-records-<date>.csv
    python manage.py login_records --csv D:\\audit\\logins.csv
    python manage.py login_records --failures          wrong-password attempts instead (kept one day)
    python manage.py login_records --prune 365         delete records older than 365 days

Online time is the span from sign-in to sign-out; for a session that was never signed out it runs to the last
page that person loaded.
"""
import csv
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import LoginFailure, LoginRecord


def human(delta):
    seconds = int(delta.total_seconds())
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s" if hours else f"{minutes}m {seconds:02d}s"


def status(record, now):
    if record.logged_out_at:
        return "signed out"
    return "active" if now - record.last_seen_at < timedelta(minutes=5) else "session ended"


class Command(BaseCommand):
    help = "Show or export the local sign-in record (time, address, online time). Not available in the web app."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="how far back to look (default 30)")
        parser.add_argument("--user", help="only this username")
        parser.add_argument("--limit", type=int, default=200, help="rows to print (default 200; the CSV has them all)")
        parser.add_argument("--csv", nargs="?", const="", metavar="PATH", help="write a CSV (default logs/login-records-<date>.csv)")
        parser.add_argument("--failures", action="store_true", help="list wrong-password attempts instead")
        parser.add_argument("--prune", type=int, metavar="DAYS", help="delete records older than DAYS days and exit")

    def handle(self, *args, **options):
        now = timezone.now()
        if options["prune"] is not None:
            if options["prune"] < 30:
                raise CommandError("Keep at least 30 days of records.")
            deleted, _ = LoginRecord.objects.filter(logged_in_at__lt=now - timedelta(days=options["prune"])).delete()
            self.stdout.write(f"Deleted {deleted} record(s) older than {options['prune']} days.")
            return
        since = now - timedelta(days=options["days"])
        if options["failures"]:
            return self.failures(options, since)

        records = LoginRecord.objects.filter(logged_in_at__gte=since)
        if options["user"]:
            records = records.filter(username__iexact=options["user"])
        rows = [(timezone.localtime(r.logged_in_at).strftime("%Y-%m-%d %H:%M:%S"), r.username, r.role, r.ip or "-", r.country or "-",
                 human(r.duration), status(r, now),
                 timezone.localtime(r.logged_out_at).strftime("%Y-%m-%d %H:%M:%S") if r.logged_out_at else "",
                 timezone.localtime(r.last_seen_at).strftime("%Y-%m-%d %H:%M:%S"), r.user_agent) for r in records]
        head = ("Signed in", "User", "Role", "IP address", "Country", "Online for", "Status", "Signed out", "Last activity", "Browser")
        if options["csv"] is not None:
            self.write_csv(options["csv"], head, rows, now)
        if not rows:
            self.stdout.write("No sign-ins in this period.")
            return
        widths = [max(len(str(x)) for x in col) for col in zip(head[:7], *[r[:7] for r in rows[:options["limit"]]])]
        line = "  ".join("{:<%d}" % w for w in widths)
        self.stdout.write(line.format(*head[:7]))
        self.stdout.write(line.format(*["-" * w for w in widths]))
        for row in rows[:options["limit"]]:
            self.stdout.write(line.format(*row[:7]))
        shown = min(len(rows), options["limit"])
        self.stdout.write(f"\n{len(rows)} sign-in(s) in the last {options['days']} days" + (f" (showing {shown})" if shown < len(rows) else ""))

    def failures(self, options, since):
        rows = LoginFailure.objects.filter(at__gte=since)
        if options["user"]:
            rows = rows.filter(username=options["user"].strip().lower())
        for f in rows[:options["limit"]]:
            self.stdout.write(f"{timezone.localtime(f.at):%Y-%m-%d %H:%M:%S}  {f.username:<20} {f.ip or '-'}")
        self.stdout.write(f"\n{rows.count()} failed attempt(s) (failures are only kept for one day).")

    def write_csv(self, path, head, rows, now):
        if not path:
            folder = settings.BASE_DIR / "logs"
            folder.mkdir(exist_ok=True)
            path = str(folder / f"login-records-{timezone.localtime(now):%Y%m%d-%H%M%S}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:  # BOM so Excel reads the text correctly
            writer = csv.writer(handle)
            writer.writerow(head)
            writer.writerows(rows)
        self.stdout.write(f"Wrote {len(rows)} row(s) to {path}")