"""Tests for production safety: demo-data guards, KB source of truth, setup, backups and config checks."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, TransactionTestCase, override_settings

from apps.accounts.models import User
from apps.core.checks import production_checks
from apps.kb.models import Article
from apps.sla.models import SLAPolicy
from apps.tickets.models import Category

os.environ.setdefault("HELPLY_DEMO_PASSWORD", "test-demo-password")


def run(command, *args, **kwargs):
    call_command(command, *args, stdout=StringIO(), **kwargs)


class DemoGuardTests(TestCase):
    @override_settings(IS_PRODUCTION=True)
    def test_demo_commands_refuse_in_production(self):
        for command, args in (("seed_demo", ["--reset"]), ("seed_tickets", ["--replace"]),
                              ("demo_passwords", ["--shared"])):
            with self.assertRaisesMessage(CommandError, "production"):
                run(command, *args)

    def test_demo_data_refuses_to_touch_a_real_database(self):
        User.objects.create_user("j.smith", password="x")  # a real person, not a demo account
        with self.assertRaisesMessage(CommandError, "j.smith"):
            run("seed_demo", "--reset")
        self.assertFalse(User.objects.filter(username="alice").exists())


class KnowledgeBaseSourceOfTruthTests(TestCase):
    def test_edits_made_in_helply_are_kept(self):
        run("seed_kb")
        article = Article.objects.get(slug="reset-password")
        article.body = "Our own password procedure."
        article.save()
        run("seed_kb")
        article.refresh_from_db()
        self.assertEqual(article.body, "Our own password procedure.")

    def test_missing_articles_are_added_and_overwrite_is_explicit(self):
        run("seed_kb")
        Article.objects.filter(slug="mailbox-full").delete()
        Article.objects.filter(slug="reset-password").update(body="edited")
        run("seed_kb")
        self.assertTrue(Article.objects.filter(slug="mailbox-full").exists())
        run("seed_kb", "--overwrite")
        self.assertNotEqual(Article.objects.get(slug="reset-password").body, "edited")


class InitHelplyTests(TestCase):
    def test_sets_up_reference_data_without_demo_data(self):
        run("init_helply", "--no-input")
        self.assertEqual(SLAPolicy.objects.count(), 4)
        self.assertGreaterEqual(Category.objects.count(), 7)
        self.assertGreaterEqual(Article.objects.count(), 40)
        self.assertFalse(User.objects.exists())  # no demo people

    def test_keeps_sla_values_changed_by_the_business(self):
        run("init_helply", "--no-input")
        SLAPolicy.objects.filter(priority="P1").update(resolution_minutes=120)
        run("init_helply", "--no-input")
        self.assertEqual(SLAPolicy.objects.get(priority="P1").resolution_minutes, 120)

    def test_creates_first_administrator(self):
        answers = iter(["Jordan", "Lee"])
        with mock.patch("builtins.input", lambda prompt: next(answers)), \
                mock.patch("getpass.getpass", return_value="Correct-Horse-Battery-9"):
            run("init_helply", "--username", "jlee", "--email", "it@example.com")
        boss = User.objects.get(username="jlee")
        self.assertEqual((boss.role, boss.is_superuser, boss.email), ("administrator", True, "it@example.com"))
        self.assertTrue(boss.check_password("Correct-Horse-Battery-9"))


class BackupTests(TransactionTestCase):
    # Real commits, like production: SQLite's backup waits for open transactions to finish.
    def test_backup_and_rotation(self):
        Category.objects.create(name="Backed up")
        with tempfile.TemporaryDirectory() as tmp, override_settings(HELPLY_BACKUP_DIR=Path(tmp), HELPLY_BACKUP_KEEP=2):
            for i in range(3):
                with mock.patch("apps.core.management.commands.backup_db.datetime") as fake:
                    fake.now.return_value.strftime.return_value = f"2026010{i}-000000"
                    run("backup_db")
            files = sorted(Path(tmp).glob("helply-*.sqlite3"))
            self.assertEqual([f.name for f in files], ["helply-20260101-000000.sqlite3", "helply-20260102-000000.sqlite3"])
            with closing(sqlite3.connect(files[-1])) as copy:
                names = [r[0] for r in copy.execute("select name from tickets_category")]
            self.assertIn("Backed up", names)

    def test_run_jobs_makes_a_daily_backup(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(HELPLY_BACKUP_DIR=Path(tmp)):
            run("run_jobs")
            run("run_jobs")  # a backup from the last 24 hours exists, so no second one
            self.assertEqual(len(list(Path(tmp).glob("helply-*"))), 1)


class ProductionConfigTests(TestCase):
    def test_production_refuses_to_start_without_a_private_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != "DJANGO_SECRET_KEY"}
        env.update(HELPLY_ENVIRONMENT="production", DJANGO_SECRET_KEY="short", DJANGO_SETTINGS_MODULE="config.settings")
        result = subprocess.run([sys.executable, "-c", "import django; django.setup()"],
                                cwd=settings.BASE_DIR, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    @override_settings(IS_PRODUCTION=True, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
                       HELPLY_SITE_URL="http://127.0.0.1:8000")
    def test_production_checks_flag_unfinished_configuration(self):
        ids = {issue.id for issue in production_checks(None)}
        self.assertTrue({"helply.W001", "helply.W003"} <= ids)

    def test_no_production_warnings_outside_production(self):
        self.assertEqual(production_checks(None), [])


class BackupSafetyTests(TestCase):
    def test_refuses_inside_a_transaction_instead_of_hanging(self):
        with self.assertRaisesMessage(CommandError, "transaction"):
            run("backup_db")
