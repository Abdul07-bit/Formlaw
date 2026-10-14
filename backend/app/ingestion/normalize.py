"""Text normalisation, metadata sanitising and page-aware chunking for legal documents."""
from __future__ import annotations

import html
import re
import unicodedata

HEADING = re.compile(r"^\s*((?:PART|CHAPTER|SCHEDULE)\s+[IVXLC\d]+.*|\d{1,3}[A-Z]?\.\s+[A-Z][^.]{2,80}\.?|[A-Z][A-Z ,\-]{6,80})\s*$")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")  # incl. bidi overrides
PAGE = re.compile(r"\[\[PAGE (\d+)\]\]")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("­", "")
    text = _CTRL.sub("", text.replace("\f", "\n"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"-\n(?=[a-z])", "", text)  # de-hyphenate line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_meta(value: str | None, limit: int = 300) -> str | None:
    """Metadata from external sources is untrusted: strip markup/control chars, collapse whitespace, cap length."""
    if value is None:
        return None
    v = html.unescape(re.sub(r"<[^>]+>", " ", str(value)))
    v = _CTRL.sub("", unicodedata.normalize("NFKC", v))
    v = re.sub(r"\s+", " ", v).strip()
    return v[:limit] or None


def chunk_text(text: str, target: int = 1200, overlap: int = 150) -> list[tuple[str | None, str]]:
    """Paragraph-aware chunks (~target chars) that remember the most recent heading."""
    chunks: list[tuple[str | None, str]] = []
    heading: str | None = None
    buf = ""
    for para in re.split(r"\n\s*\n|\n(?=\s*\d{1,3}\.\s)", text):
        p = para.strip()
        if not p:
            continue
        if HEADING.match(p) and len(p) < 120:
            heading = p[:200]
        if len(buf) + len(p) > target and buf:
            chunks.append((heading, buf.strip()))
            tail = buf[-overlap:]
            m = re.search(r"[.?!]\s+", tail)  # overlap starts at a sentence boundary, never mid-word
            buf = tail[m.end():] if m else ""
        buf += ("\n" if buf else "") + p
    if buf.strip():
        chunks.append((heading, buf.strip()))
    return chunks


def chunk_pages(text_with_markers: str, target: int = 1200) -> list[tuple[int, str | None, str]]:
    """Chunks that keep the page they came from, so evidence can cite 'p.14'."""
    out: list[tuple[int, str | None, str]] = []
    parts = PAGE.split(text_with_markers)
    pages = [(1, parts[0])] if parts[0].strip() else []
    pages += [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    for page, body in pages:
        for heading, chunk in chunk_text(normalize(body), target):
            out.append((page, heading, chunk))
    return out
