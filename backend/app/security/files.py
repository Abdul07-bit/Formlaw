"""
Upload validation. Files are untrusted: the extension, the declared MIME type and the actual bytes must
all agree, archives are checked for decompression bombs, and PDFs with active content are refused.
The client-supplied filename is only ever used as a sanitised display label, never as a path.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass

from ..core.errors import TooLarge, Unprocessable

MAX_ZIP_ENTRIES = 2_000
MAX_UNCOMPRESSED = 60 * 1024 * 1024
MAX_RATIO = 120
PDF_ACTIVE = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile|OpenAction|AA|RichMedia|XFA)\b")

ALLOWED = {
    "pdf": {"mimes": {"application/pdf"}, "kind": "pdf"},
    "docx": {"mimes": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, "kind": "docx"},
    "txt": {"mimes": {"text/plain", ""}, "kind": "text"},
    "md": {"mimes": {"text/markdown", "text/plain", ""}, "kind": "text"},
    "csv": {"mimes": {"text/csv", "application/vnd.ms-excel", "text/plain", ""}, "kind": "text"},
    "png": {"mimes": {"image/png"}, "kind": "image"},
    "jpg": {"mimes": {"image/jpeg"}, "kind": "image"},
    "jpeg": {"mimes": {"image/jpeg"}, "kind": "image"},
}
CANONICAL_TYPE = {"pdf": "application/pdf", "docx": ALLOWED["docx"]["mimes"].copy().pop(), "txt": "text/plain",
                  "md": "text/markdown", "csv": "text/csv", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}


@dataclass(frozen=True)
class ValidatedFile:
    ext: str
    kind: str
    content_type: str
    display_name: str


def sanitize_filename(name: str) -> str:
    base = re.split(r"[\\/]", name or "")[-1]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^\w.\- ]+", "", base)
    base = re.sub(r"\.{2,}", ".", base).lstrip(".").strip()[:120]
    return base or "document"


def validate_upload(filename: str, declared_type: str | None, data: bytes, max_bytes: int, *, allowed: set[str] | None = None) -> ValidatedFile:
    name = sanitize_filename(filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    rule = ALLOWED.get(ext)
    if rule is None or (allowed is not None and ext not in allowed):
        raise Unprocessable(f".{ext or '?'} files are not supported", code="unsupported_type")
    if not data:
        raise Unprocessable("File is empty", code="empty_file")
    if len(data) > max_bytes:
        raise TooLarge(f"File exceeds {max_bytes // (1024 * 1024)} MB limit")
    declared = (declared_type or "").split(";")[0].strip().lower()
    if declared not in rule["mimes"] and declared != "application/octet-stream":
        raise Unprocessable("File type does not match its extension", code="mime_mismatch")

    kind = rule["kind"]
    if kind == "pdf":
        _check_pdf(data)
    elif kind == "docx":
        _check_docx(data)
    elif kind == "image":
        _check_image(ext, data)
    else:
        _check_text(data)
    return ValidatedFile(ext=ext, kind=kind, content_type=CANONICAL_TYPE[ext], display_name=name)


def _check_pdf(data: bytes) -> None:
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise Unprocessable("File content is not a PDF", code="content_mismatch")
    if PDF_ACTIVE.search(data):
        raise Unprocessable("PDF contains active content (JavaScript, launch actions or embedded files) and was refused",
                            code="active_content")


def _check_docx(data: bytes) -> None:
    if not data.startswith(b"PK\x03\x04"):
        raise Unprocessable("File content is not a DOCX document", code="content_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise Unprocessable("Document has too many parts", code="archive_bomb")
            total = sum(i.file_size for i in infos)
            if total > MAX_UNCOMPRESSED or total > max(len(data), 1) * MAX_RATIO:
                raise Unprocessable("Document expands to an unsafe size (possible decompression bomb)", code="archive_bomb")
            names = {i.filename for i in infos}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise Unprocessable("File content is not a DOCX document", code="content_mismatch")
            if any(n.startswith("/") or ".." in n.split("/") for n in names):
                raise Unprocessable("Document contains unsafe paths", code="path_traversal")
            if any(n.lower().endswith(("vbaproject.bin", ".exe", ".dll", ".js")) or "activex" in n.lower() for n in names):
                raise Unprocessable("Document contains macros or embedded executables and was refused", code="active_content")
    except zipfile.BadZipFile as e:
        raise Unprocessable("Corrupt DOCX file", code="corrupt_file") from e


def _check_image(ext: str, data: bytes) -> None:
    ok = data.startswith(b"\x89PNG\r\n\x1a\n") if ext == "png" else data.startswith(b"\xff\xd8\xff")
    if not ok:
        raise Unprocessable("File content does not match its image type", code="content_mismatch")


def _check_text(data: bytes) -> None:
    if b"\x00" in data[:8192]:
        raise Unprocessable("Binary content in a text file", code="content_mismatch")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise Unprocessable("Text files must be UTF-8", code="encoding") from e
