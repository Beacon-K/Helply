"""Show which AI model each feature uses and (with --test) check that the providers really answer.

    python manage.py ai_status          # configuration only, makes no network call
    python manage.py ai_status --test   # sends one tiny test message to each configured provider

The output never contains a key: it only says whether one is set.
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string

from apps.ai import metering
from apps.ai.backends import external
from apps.ai.services import get_backend

FEATURES = ("classify", "ask", "copilot", "chat", "insights")
PING = "Reply with the single word OK."


class Command(BaseCommand):
    help = "Show the AI backend used by each feature; --test sends one small request to each provider."

    def add_arguments(self, parser):
        parser.add_argument("--test", action="store_true", help="Make a real, tiny request to every configured provider.")

    def handle(self, *args, test=False, **options):
        out = self.stdout.write
        default = import_string(settings.HELPLY_AI_BACKEND)()
        out(f"Default backend : {settings.HELPLY_AI_BACKEND.rsplit('.', 1)[-1]} ({default.name})")
        out(f"Cloudflare AI   : account {'set' if settings.HELPLY_CF_ACCOUNT_ID else 'NOT set'}, "
            f"token {'set' if settings.HELPLY_CF_API_TOKEN else 'NOT set'}, chat model {settings.HELPLY_CF_CHAT_MODEL or default.name}")
        ext = external.configured()
        if ext:
            backend = external.ExternalBackend()
            out(f"External model  : {backend.name}  (key set, base url {settings.HELPLY_EXT_BASE_URL or 'provider default'})")
            if not backend.model:
                out("                  WARNING: HELPLY_EXT_MODEL is empty; set the model name for this provider.")
        else:
            out("External model  : not configured (set HELPLY_EXT_PROVIDER and HELPLY_EXT_API_KEY in .env to enable)")
        snap = metering.snapshot()
        if snap["configured"]:
            cap = f" of {snap['limit']:,}" if snap["limit"] else ""
            out(f"Usage today     : {snap['used']:,.0f}{cap} Neurons ({snap['calls']} calls; "
                f"{'Cloudflare account analytics' if snap['source'] == 'account' else 'Helply calls as reported by Cloudflare'})")
        out("")
        out("Feature   -> backend")
        for feature in FEATURES:
            used = get_backend(feature)
            via = "external, falling back to default" if type(used).__name__ == "WithFallback" else "default"
            name = used.name
            if feature == "chat" and via == "default" and settings.HELPLY_CF_CHAT_MODEL and name.startswith("cloudflare"):
                name = f"cloudflare:{settings.HELPLY_CF_CHAT_MODEL}"  # the conversational model differs from the classifier
            out(f"  {feature:<9} {name}  [{via}]")
        if not test:
            return
        out("")
        for label, backend in (("default", default), ("external", external.ExternalBackend() if ext else None)):
            if backend is None:
                continue
            started = time.time()
            reply = backend.generate_text(PING, [{"role": "user", "content": PING}], max_tokens=10, temperature=0)
            took = f"{time.time() - started:.1f}s"
            if reply:
                out(self.style.SUCCESS(f"Test {label:<8}: answered in {took}"))
            else:
                out(self.style.ERROR(f"Test {label:<8}: no answer after {took} (see the log line above for the HTTP status)"))