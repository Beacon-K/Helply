"""Deterministic keyword baseline.

Good enough to demo the end-to-end flow and to serve as the comparison
baseline when an LLM / embedding backend is added.
"""
import re

from apps.ai.text import normalize, tokenize

from .base import AIBackend, Classification

PHRASE = re.compile(r"[^a-z0-9]")


class KeywordBackend(AIBackend):
    name = "keyword-baseline"

    def classify(self, text, categories):
        tokens = tokenize(text)
        lowered = text.lower()
        scores = {}
        for category in categories:
            hits = [
                k for k in category.keyword_list()
                # multi-word / hyphenated keywords match as phrases, single words as tokens
                if (k in lowered if PHRASE.search(k) else normalize(k) in tokens)
            ]
            if hits:
                scores[category] = hits
        if not scores:
            return Classification(None, 0.0, "no keyword matched")

        best, best_hits = max(scores.items(), key=lambda item: len(item[1]))
        total_hits = sum(len(h) for h in scores.values())
        # Share of all matches that went to the winner, damped when evidence is thin.
        confidence = (len(best_hits) / total_hits) * min(1.0, len(best_hits) / 2)
        return Classification(best, round(confidence, 2), "matched: " + ", ".join(best_hits))
