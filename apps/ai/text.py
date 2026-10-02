import re

STOPWORDS = {
    "a", "about", "after", "all", "also", "am", "an", "and", "any", "are", "as", "at", "be", "been", "but",
    "by", "can", "cannot", "can't", "cant", "could", "did", "do", "does", "doesn", "don", "dont", "for",
    "from", "get", "got", "has", "have", "how", "i", "if", "im", "in", "into", "is", "it", "its", "just",
    "keep", "keeps", "me", "my", "no", "not", "now", "of", "on", "or", "our", "out", "please", "so", "some",
    "still", "that", "the", "then", "there", "this", "to", "up", "was", "we", "what", "when", "where", "why",
    "will", "with", "won", "working", "work", "you", "your",
}


def normalize(word):
    """Very light stemming so 'printers' matches 'printer' and 'crashes' matches 'crash'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(text):
    return {normalize(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS and len(w) > 1}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
