"""
Text extraction for validated uploads. Output uses [[PAGE n]] markers so evidence keeps page numbers.
Runs only on files that already passed security.files.validate_upload.
"""
from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from .text import with_page_markers

log = logging.getLogger("formlaw.ingestion")
MAX_PAGES = 300
MAX_TEXT = 400_000
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True)
class Extraction:
    text: str
    pages: int | None
    status: str  # extracted | needs_ocr | failed
    note: str | None = None


def extract(kind: str, data: bytes) -> Extraction:
    try:
        if kind == "text":
            text = data.decode("utf-8").replace("\x00", "")[:MAX_TEXT]
            pages = text.count("[[PAGE ") or max(1, len(text) // 1800 + 1)
            return Extraction(text, pages, "extracted")
        if kind == "pdf":
            return _pdf(data)
        if kind == "docx":
            pages = _docx_pages(data)
            return Extraction(with_page_markers(pages)[:MAX_TEXT], len(pages), "extracted")
        if kind == "image":
            return Extraction("", 1, "needs_ocr", "Image stored; OCR provider not configured")
    except (zipfile.BadZipFile, ElementTree.ParseError, ValueError) as e:
        log.warning("extraction failed kind=%s error=%s", kind, type(e).__name__)
        return Extraction("", None, "failed", "The file could not be read")
    return Extraction("", None, "failed", "Unsupported file kind")


def _pdf(data: bytes) -> Extraction:
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        return Extraction("", None, "needs_ocr", "PDF extraction requires pdfplumber on the server")
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                return Extraction("", len(pdf.pages), "failed", f"PDF exceeds {MAX_PAGES} pages")
            pages = [(p.extract_text() or "") for p in pdf.pages]
    except Exception as e:  # pdfminer raises many unrelated exception types for malformed files
        log.warning("pdf parse failed: %s", type(e).__name__)
        return Extraction("", None, "failed", "The PDF could not be read")
    if not any(p.strip() for p in pages):
        return Extraction("", len(pages), "needs_ocr", "Scanned PDF without a text layer; OCR provider not configured")
    return Extraction(with_page_markers(pages)[:MAX_TEXT], len(pages), "extracted")


def _docx_pages(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))  # size already bounded by validate_upload
    pages: list[str] = []
    lines: list[str] = []
    for para in root.iter(f"{_W}p"):
        buf: list[str] = []
        for el in para.iter():
            if el.tag == f"{_W}t" and el.text:
                buf.append(el.text)
            elif el.tag == f"{_W}tab":
                buf.append("\t")
            elif el.tag == f"{_W}br" and el.get(f"{_W}type") == "page":
                lines.append("".join(buf))
                buf = []
                pages.append("\n".join(lines))
                lines = []
        lines.append("".join(buf))
    pages.append("\n".join(lines))
    return [p for p in pages if p.strip()] or [""]
