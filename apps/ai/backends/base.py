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
