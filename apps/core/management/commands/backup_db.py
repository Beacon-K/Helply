import os
import shutil
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Back up the database to HELPLY_BACKUP_DIR and keep the newest HELPLY_BACKUP_KEEP copies."

    def handle(self, *args, **options):
        backup_dir = settings.HELPLY_BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        db = connection.settings_dict

        if connection.in_atomic_block:
            # An open transaction would make SQLite's backup wait forever for it to finish.
            raise CommandError("backup_db cannot run inside a database transaction.")

        if connection.vendor == "sqlite":
            target = backup_dir / f"helply-{stamp}.sqlite3"
            # SQLite's online backup API copies a consistent snapshot even while Helply is running.
            connection.ensure_connection()
            with closing(sqlite3.connect(target)) as dest:
                connection.connection.backup(dest)
            pattern = "helply-*.sqlite3"
        elif connection.vendor == "postgresql":
            if not shutil.which("pg_dump"):
                raise CommandError("pg_dump was not found. Install the PostgreSQL client tools or back up from the "
                                   "database server (docker compose exec db pg_dump ...).")
            target = backup_dir / f"helply-{stamp}.dump"
            subprocess.run(
                ["pg_dump", "-Fc", "-h", db["HOST"] or "localhost", "-p", str(db["PORT"] or 5432),
                 "-U", db["USER"], "-f", str(target), db["NAME"]],
                check=True, env={**os.environ, "PGPASSWORD": db["PASSWORD"]},
            )
            pattern = "helply-*.dump"
        else:
            raise CommandError(f"Backups are not supported for {connection.vendor}.")

        old = sorted(backup_dir.glob(pattern))[:-settings.HELPLY_BACKUP_KEEP]
        for path in old:
            path.unlink()
        self.stdout.write(self.style.SUCCESS(f"Backup written to {target} ({len(old)} old backup(s) removed)."))
