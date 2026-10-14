"""
Page- and paragraph-aware chunking with exact provenance.

Each chunk records its page, the paragraph number on that page where it starts, the nearest section heading above it,
and character offsets into the normalised page text — enough for the viewer to highlight the exact span.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .text import split_pages

TARGET = 900     # characters per chunk (soft)
OVERLAP = 1      # sentences carried into the next chunk
_SENT = re.compile(r"(?<=[.!?;:])\s+(?=[\"'(\[]?[A-Z0-9])")
_HEADING = re.compile(r"^(?:[A-Z][A-Z0-9 ,.&()'/-]{3,80}|(?:section|clause|article|part|chapter|annexure|schedule)\s+[\w.()-]+.{0,80}|\d{1,2}(?:\.\d{1,2})*\.?\s+[A-Z][^.]{2,80})$", re.I)


@dataclass(frozen=True)
class RawChunk:
    ordinal: int
    page: int
    paragraph: int
    section: str | None
    text: str
    char_start: int
    char_end: int


def _paragraphs(page_text: str) -> list[tuple[int, int, str]]:
    """
    (start, end, text) per paragraph. Blank lines separate paragraphs; inside a block (PDF text has no blank lines),
    a line that ends a sentence and is clearly shorter than the block's wrapped width also ends a paragraph.
    """
    out = []
    for m in re.finditer(r"(?:[^\n]+\n?)+", page_text):
        block = m.group(0)
        if not block.strip():
            continue
        lines = block.split("\n")
        width = max(len(l.rstrip()) for l in lines)
        pos, cur_start, cur = m.start(), m.start(), []
        for i, line in enumerate(lines):
            cur.append(line)
            pos_end = pos + len(line)
            stripped = line.rstrip()
            ends = stripped.endswith((".", ":", "?", "!", ";"))
            short = width >= 60 and len(stripped) < 0.85 * width
            is_last = i == len(lines) - 1
            if is_last or (ends and short) or _is_heading(stripped):
                text = "\n".join(cur).strip()
                if text:
                    out.append((cur_start, pos_end, text))
                cur, cur_start = [], pos_end + 1
            pos = pos_end + 1
    return out


def _is_heading(text: str) -> bool:
    t = text.strip()
    return len(t) <= 90 and "\n" not in t and bool(_HEADING.match(t)) and not t.endswith((".", ";", ","))


def chunk_text(text: str) -> list[RawChunk]:
    chunks: list[RawChunk] = []
    section: str | None = None
    for page, page_text in split_pages(text):
        para_no = 0
        for start, _end, para in _paragraphs(page_text):
            lines = para.split("\n")
            # A heading line at the top of a block names the section for what follows.
            if _is_heading(lines[0]):
                section = lines[0].strip()[:160]
                lines = lines[1:]
                if not lines:
                    continue
            para_no += 1
            sentences = [s for s in _SENT.split(" ".join(l.strip() for l in lines)) if s.strip()]
            buf: list[str] = []
            for s in sentences:
                if buf and sum(len(x) + 1 for x in buf) + len(s) > TARGET:
                    chunks.append(_make(chunks, page, para_no, section, buf, page_text, start))
                    buf = buf[-OVERLAP:] if OVERLAP and len(buf) > OVERLAP else []
                buf.append(s.strip())
            if buf:
                chunks.append(_make(chunks, page, para_no, section, buf, page_text, start))
    return chunks


def _make(chunks: list[RawChunk], page: int, para: int, section: str | None, buf: list[str], page_text: str, para_start: int) -> RawChunk:
    text = " ".join(buf)
    # Offsets: locate the first sentence inside the page text (best effort; used only for highlighting).
    first = buf[0][:40]
    pos = page_text.find(first, para_start)
    start = pos if pos >= 0 else para_start
    return RawChunk(len(chunks), page, para, section, text, start, start + len(text))
