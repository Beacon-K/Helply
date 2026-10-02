"""Load KB articles from the Markdown files in apps/kb/articles/.

Each file starts with a front-matter block:

    ---
    title: VPN won't connect or keeps disconnecting
    category: Network
    audience: everyone          # or: internal
    keywords: vpn, remote, work from home
    summary: One or two sentences for search results.
    ---
    ## Body in KB markup ...

The file name (without .md) is the article slug. Keeping articles as files
means the content is version-controlled and reviewable like code.
"""
from dataclasses import dataclass
from pathlib import Path

ARTICLES_DIR = Path(__file__).resolve().parent / "articles"
FIELDS = {"title", "category", "audience", "keywords", "summary"}


@dataclass
class ArticleFile:
    slug: str
    title: str
    body: str
    category: str = ""
    audience: str = "everyone"
    keywords: str = ""
    summary: str = ""


def _unquote(value):
    """Allow YAML-style quoted values, e.g. title: "Windows updates: stuck"."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].replace('\\"', '"')
    return value


def parse(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing front matter")
    _, header, body = text.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in FIELDS:
            value = value.split("#", 1)[0].strip() if key == "audience" else value.strip()
            meta[key] = _unquote(value)
    if "title" not in meta:
        raise ValueError(f"{path}: 'title' is required")
    return ArticleFile(slug=Path(path).stem, body=body.strip(), **meta)


def load_all(directory=ARTICLES_DIR):
    return [parse(p) for p in sorted(Path(directory).glob("*.md"))]
