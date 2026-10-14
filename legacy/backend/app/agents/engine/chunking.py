"""Split extracted document text into page-aware sentence chunks ([[PAGE n]] markers carry page numbers)."""
from __future__ import annotations

import re
from dataclasses import dataclass

PAGE_RE = re.compile(r"\[\[PAGE (\d+)\]\]")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    doc_name: str
    page: int
    sentence: str


@dataclass(frozen=True)
class DocText:
    id: str
    name: str
    text: str


def chunk_documents(docs: list[DocText]) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        if not d.text:
            continue
        page = 1
        for line in d.text.splitlines():
            m = PAGE_RE.search(line)
            if m:
                page = int(m.group(1))
                continue
            for part in SENT_SPLIT.split(line):
                s = part.strip()
                if len(s) > 3:
                    out.append(Chunk(d.id, d.name, page, s))
    return out


def with_page_markers(pages: list[str]) -> str:
    return "\n".join(f"[[PAGE {i}]]\n{t.strip()}" for i, t in enumerate(pages, start=1))


def markers_to_form_feeds(text: str) -> str:
    """For the legacy agents, which split pages on form feeds. Keeps original page numbers (gaps → empty pages)."""
    pages: dict[int, list[str]] = {}
    current = 1
    for part in re.split(r"(\[\[PAGE \d+\]\])", text):
        m = re.fullmatch(r"\[\[PAGE (\d+)\]\]", part)
        if m:
            current = max(1, int(m.group(1)))
        elif part.strip():
            pages.setdefault(current, []).append(part.strip())
    if not pages:
        return text
    return "\f".join("\n".join(pages.get(i, [])) for i in range(1, max(pages) + 1))
