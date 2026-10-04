from django.core.management.base import BaseCommand

from apps.core.demo import passwords
from apps.core.demo.guard import require_demo_allowed


class Command(BaseCommand):
    help = ("Change the passwords of the demo accounts. Nothing runs this automatically: accounts get a password "
            "once when they are created and keep it until a person changes it. --shared gives every demo account "
            "HELPLY_DEMO_PASSWORD from .env (local demos). --rotate gives every demo account its own new random "
            "password, listed here and in demo-passwords.txt.")

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--shared", action="store_true")
        mode.add_argument("--rotate", "--public", action="store_true", dest="rotate")

    def handle(self, *args, shared=False, rotate=False, **options):
        require_demo_allowed("Changing demo passwords")
        if shared:
            passwords.reset_to_shared()
            self.stdout.write("Demo accounts use the shared password HELPLY_DEMO_PASSWORD from the .env file.")
            return

        rows = passwords.randomize()
        lines = [f"{u.username:<12} {u.get_role_display():<14} {pw}" for u, pw in rows]
        out_file = passwords.password_list()
        out_file.write_text(passwords.LIST_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(self.style.WARNING("Every demo account now has its own new random password."))
        shown = [line for (u, _), line in zip(rows, lines) if u.role != "employee"]  # the IT team; 100 lines would bury them
        for line in shown:
            self.stdout.write("  " + line)
        hidden = len(lines) - len(shown)
        if hidden:
            self.stdout.write(f"  ... and {hidden} employee accounts (username = first name, e.g. ava, noah).")
        self.stdout.write(f"All {len(lines)} passwords are saved to {out_file.name} on this drive.")