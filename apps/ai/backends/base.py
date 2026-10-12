from dataclasses import dataclass


@dataclass
class Classification:
    category: object | None  # tickets.Category
    confidence: float
    reason: str = ""


class AIBackend:
    """Interface every AI backend implements.

    Business code only talks to apps.ai.services, which talks to a backend
    chosen by settings.HELPLY_AI_BACKEND. That keeps the ticket workflow
    independent of any specific model or vendor.
    """

    name = "base"

    def classify(self, text, categories):
        """Return a Classification for the ticket text."""
        raise NotImplementedError

    def generate_json(self, system, user, max_tokens=900):
        """Return a parsed JSON object answering `user` under `system`, or None when no
        generative model is available. The keyword baseline has none, so the assistant
        then falls back to plain knowledge-base results."""
        return None

    def generate_text(self, system, messages, max_tokens=700, temperature=0.5):
        """Continue a conversation: `messages` is [{"role": "user"|"assistant", "content": str}].
        Returns the reply text, or None when no generative model is available."""
        return None
