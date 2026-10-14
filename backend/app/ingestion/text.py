"""Text normalisation and page markers shared by case-document and legal-corpus ingestion."""
from __future__ import annotations

import re
import unicodedata

PAGE_RE = re.compile(r"\[\[PAGE (\d+)\]\]")


def with_page_markers(pages: list[str]) -> str:
    return "\n".join(f"[[PAGE {i}]]\n{t.strip()}" for i, t in enumerate(pages, start=1))


def split_pages(text: str) -> list[tuple[int, str]]:
    """[[PAGE n]] markers → [(n, text)]. Text without markers is page 1."""
    parts = PAGE_RE.split(text)
    if len(parts) == 1:
        return [(1, text)]
    out: list[tuple[int, str]] = []
    if parts[0].strip():
        out.append((1, parts[0]))
    for i in range(1, len(parts), 2):
        out.append((int(parts[i]), parts[i + 1]))
    return out


def normalize(text: str) -> str:
    """NFKC, unify quotes/dashes, de-hyphenate line breaks, collapse runs of spaces. Keeps paragraph breaks."""
    text = unicodedata.normalize("NFKC", text).replace("\x00", "")
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def norm_for_match(text: str) -> str:
    """Whitespace-collapsed, case-folded, quote-normalised form used for verbatim-quote checks."""
    return " ".join(normalize(text).split()).casefold()
