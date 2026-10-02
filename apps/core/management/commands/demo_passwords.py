from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.demo import passwords
from apps.core.demo.guard import require_demo_allowed


class Command(BaseCommand):
    help = ("Set demo account passwords. --shared: everyone gets HELPLY_DEMO_PASSWORD from .env (local demos). "
            "--public: everyone gets their own random password, shown here and saved to demo-passwords.txt.")

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--shared", action="store_true")
        mode.add_argument("--public", action="store_true")

    def handle(self, *args, shared=False, public=False, **options):
        require_demo_allowed("Changing demo passwords")
        if shared:
            passwords.reset_to_shared()
            self.stdout.write("Demo accounts use the shared password HELPLY_DEMO_PASSWORD from the .env file.")
            return

        rows = passwords.randomize()
        lines = [f"{u.username:<8} {u.get_role_display():<11} {pw}" for u, pw in rows]
        out_file = settings.BASE_DIR / "demo-passwords.txt"
        out_file.write_text(
            "Helply public demo - one-time passwords (regenerated every time start-online.bat runs).\n"
            "Keep this private. Not committed to git.\n\n" + "\n".join(lines) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.WARNING("Public mode: every demo account now has its own random password."))
        for line in lines:
            self.stdout.write("  " + line)
        self.stdout.write(f"Also saved to {out_file.name} on this drive.")
