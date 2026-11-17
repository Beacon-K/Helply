"""Optional external large language model (OpenAI or Anthropic Claude) behind the same backend interface.

Why it exists: the Workers AI models are free and keep data with our existing provider, but a flagship model
reasons better. Which features use it is a setting, so the expensive model is spent where it pays off
(the daily admin analysis, the technician copilot) and everything else stays on the free tier.

Safety rules, the same as for every backend:
- The API key lives only in the environment (.env). It is never logged, never stored in the database and
  never put in an error message: failures are logged by exception type or HTTP status only, because a
  provider's error body can echo request details.
- Any failure (no key, offline, timeout, quota, bad answer) returns None / degrades, and WithFallback then
  asks the next backend, so nothing in Helply depends on this provider being up.
- Only https is accepted (plain http only for localhost, e.g. a local model server).
"""
import json
import logging
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.conf import settings

from .base import AIBackend
from .cloudflare import MAX_PROMPT_CHARS, MAX_TEXT_CHARS, SYSTEM_PROMPT, _json_object, parse_classification
from .keyword import KeywordBackend

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1"
DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5"}  # OpenAI has no default: its model names change, so you choose
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ExternalConfigError(RuntimeError):
    """The provider settings are missing or unsafe."""


def provider():
    return (settings.HELPLY_EXT_PROVIDER or "").strip().lower()


def configured():
    return bool(settings.HELPLY_EXT_API_KEY and provider() in ("openai", "anthropic"))


def _safe_url(url):
    parts = urlparse(url)
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        return url
    raise ExternalConfigError("HELPLY_EXT_BASE_URL must use https (http only for localhost)")


class ExternalBackend(AIBackend):
    name = "external"

    def __init__(self):
        self.provider = provider()
        self.model = settings.HELPLY_EXT_MODEL or DEFAULT_MODELS.get(self.provider, "")
        self.name = f"{self.provider}:{self.model}"
        self._fallback = KeywordBackend()

    # ----- transport -----
    def _request(self, system, messages, max_tokens, temperature):
        """One provider call; returns the reply text. Raises on any failure."""
        if not configured():
            raise ExternalConfigError("HELPLY_EXT_PROVIDER / HELPLY_EXT_API_KEY not set")
        if not self.model:
            raise ExternalConfigError("HELPLY_EXT_MODEL not set")
        key, timeout = settings.HELPLY_EXT_API_KEY, settings.HELPLY_EXT_TIMEOUT
        if self.provider == "anthropic":
            url = _safe_url(settings.HELPLY_EXT_BASE_URL or ANTHROPIC_URL)
            body = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "system": system,
                    "messages": messages}
            headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
        else:
            base = _safe_url((settings.HELPLY_EXT_BASE_URL or OPENAI_URL).rstrip("/"))
            url = f"{base}/chat/completions"
            body = {"model": self.model, "messages": [{"role": "system", "content": system}] + messages}
            if base == OPENAI_URL:
                body["max_completion_tokens"] = max_tokens  # current OpenAI models; temperature is model-fixed on some
            else:
                body["max_tokens"] = max_tokens  # OpenAI-compatible servers
                body["temperature"] = temperature
            headers = {"Authorization": f"Bearer {key}"}
        request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                         headers={**headers, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - scheme checked above
            payload = json.load(response)
        if self.provider == "anthropic":
            return "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
        return ((payload.get("choices") or [{}])[0].get("message") or {}).get("content")

    @staticmethod
    def _log_failure(what, exc):
        # Status or exception type only: never the message, URL or body, which could carry the key.
        detail = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
        logger.warning("External AI %s unavailable (%s)", what, detail)

    # ----- interface -----
    def generate_text(self, system, messages, max_tokens=700, temperature=0.5):
        try:
            text = self._request(system[:MAX_PROMPT_CHARS], messages, max_tokens, temperature)
        except Exception as exc:  # noqa: BLE001 - must degrade, never raise into a page
            self._log_failure("chat", exc)
            return None
        return re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL).strip() or None

    def generate_json(self, system, user, max_tokens=900):
        try:
            return _json_object(self._request(system, [{"role": "user", "content": user[:MAX_PROMPT_CHARS]}],
                                              max_tokens, 0))
        except Exception as exc:  # noqa: BLE001
            self._log_failure("analysis", exc)
            return None

    def classify_strict(self, text, categories):
        """Raises on failure so WithFallback can hand the ticket to the next backend."""
        categories = list(categories)
        if not categories:
            from .base import Classification
            return Classification(None, 0.0, "no categories")
        options = "\n".join(f"{c.pk}: {c.name}" + (f" ({c.keywords})" if c.keywords else "") for c in categories)
        answer = self._request(SYSTEM_PROMPT, [{"role": "user", "content": f"Categories:\n{options}\n\nTicket:\n{text[:MAX_TEXT_CHARS]}"}], 120, 0)
        return parse_classification(answer, categories)

    def classify(self, text, categories):
        """Used when this backend is the main one (HELPLY_AI_BACKEND): degrade to the keyword baseline."""
        categories = list(categories)
        try:
            return self.classify_strict(text, categories)
        except Exception as exc:  # noqa: BLE001
            self._log_failure("classification", exc)
            result = self._fallback.classify(text, categories)
            self.name = self._fallback.name
            result.reason = f"{result.reason} (external AI unavailable)"
            return result


class WithFallback(AIBackend):
    """Ask `primary`; if it cannot answer, ask `fallback`. `name` always says who really answered."""

    def __init__(self, primary, fallback):
        self.primary, self.fallback = primary, fallback
        self.name = primary.name

    def _ask(self, method, *args, **kwargs):
        result = getattr(self.primary, method)(*args, **kwargs)
        if result is not None:
            self.name = self.primary.name
            return result
        result = getattr(self.fallback, method)(*args, **kwargs)
        self.name = self.fallback.name
        return result

    def generate_text(self, system, messages, max_tokens=700, temperature=0.5):
        return self._ask("generate_text", system, messages, max_tokens, temperature)

    def generate_json(self, system, user, max_tokens=900):
        return self._ask("generate_json", system, user, max_tokens)

    def classify(self, text, categories):
        categories = list(categories)
        try:
            result = self.primary.classify_strict(text, categories)
            self.name = self.primary.name
        except Exception as exc:  # noqa: BLE001
            ExternalBackend._log_failure("classification", exc)
            result = self.fallback.classify(text, categories)
            self.name = self.fallback.name
        return result