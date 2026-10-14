"""Test helpers: an API wrapper with per-user sessions and builders for real PDF/DOCX files."""
from __future__ import annotations

import io
import itertools
import zipfile
from dataclasses import dataclass

from fastapi.testclient import TestClient

_n = itertools.count(1)
PASSWORD = "Correct-Horse-42"


@dataclass
class Session:
    token: str
    user: dict

    @property
    def h(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}


class Api:
    def __init__(self, client: TestClient):
        self.c = client

    def register(self, role: str = "lawyer", **extra) -> Session:
        email = extra.pop("email", f"user{next(_n)}@example.com")
        body = {"name": extra.pop("name", f"Test {role.title()}"), "email": email, "password": PASSWORD, "role": role,
                "city": extra.pop("city", "New Delhi"), **({"firmName": extra.pop("firm")} if "firm" in extra else {})}
        r = self.c.post("/api/v1/auth/register", json=body)
        assert r.status_code == 201, r.text
        return Session(r.json()["accessToken"], r.json()["user"])

    def demo(self, persona: str) -> Session:
        r = self.c.post("/api/v1/auth/demo", json={"persona": persona})
        assert r.status_code == 200, r.text
        return Session(r.json()["accessToken"], r.json()["user"])

    def case(self, s: Session, title: str = "Test matter", **extra) -> dict:
        r = self.c.post("/api/v1/cases", json={"title": title, "matterType": extra.get("matter_type", "criminal"),
                                               "description": extra.get("description", "")}, headers=s.h)
        assert r.status_code == 201, r.text
        return r.json()

    def upload(self, s: Session, case_id: str, name: str, data: bytes, ctype: str):
        return self.c.post(f"/api/v1/cases/{case_id}/documents", files=[("files", (name, data, ctype))], headers=s.h)

    def upload_text(self, s: Session, case_id: str, name: str, pages: list[str]) -> dict:
        data = "\n".join(f"[[PAGE {i}]]\n{p}" for i, p in enumerate(pages, 1)).encode()
        r = self.upload(s, case_id, name, data, "text/plain")
        assert r.status_code == 201, r.text
        return r.json()[0]

    def ask(self, s: Session, case_id: str, message: str, thread_id: str | None = None) -> dict:
        r = self.c.post(f"/api/v1/cases/{case_id}/chat", json={"message": message, **({"threadId": thread_id} if thread_id else {})}, headers=s.h)
        assert r.status_code == 202, r.text
        run = self.c.get(f"/api/v1/runs/{r.json()['runId']}", headers=s.h)
        assert run.status_code == 200, run.text
        return run.json()


def make_pdf(lines: list[str], extra_objects: bytes = b"") -> bytes:
    """Minimal valid single-page PDF with a text layer (pdfplumber-readable)."""
    content = b"BT /F1 11 Tf 50 750 Td 14 TL " + b" ".join(b"(" + l.replace("(", "").replace(")", "").encode() + b") '" for l in lines) + b" ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    out.write(extra_objects)
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def make_docx(paragraphs: list[str], extra_files: dict[str, bytes] | None = None) -> bytes:
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {ns}><w:body>{body}</w:body></w:document>')
        for name, data in (extra_files or {}).items():
            z.writestr(name, data)
    return buf.getvalue()


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
