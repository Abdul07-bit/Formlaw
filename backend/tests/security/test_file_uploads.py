"""Malicious files through the real upload endpoint."""
from app.core.config import get_settings
from tests.helpers import DOCX, make_docx, make_pdf


def _admin_events(api):
    return api.c.get("/api/v1/admin/security-events", headers=api.demo("admin").h).json()


def test_mime_spoofed_upload_refused(api):
    s = api.register()
    case = api.case(s)
    r = api.upload(s, case["id"], "invoice.pdf", b"<html><script>alert(1)</script></html>", "application/pdf")
    assert r.status_code == 422 and r.json()["error"]["code"] == "content_mismatch"


def test_pdf_with_javascript_creates_security_event(api, seeded):
    s = api.register()
    case = api.case(s)
    evil = make_pdf(["hello"], extra_objects=b"6 0 obj << /OpenAction << /S /JavaScript /JS (x) >> >> endobj\n")
    r = api.upload(s, case["id"], "evil.pdf", evil, "application/pdf")
    assert r.json()["error"]["code"] == "active_content"
    assert any(e["kind"] == "malicious_file" for e in _admin_events(api))


def test_docx_bomb_refused(api):
    s = api.register()
    case = api.case(s)
    bomb = make_docx(["x"], {"word/media/pad.bin": b"\0" * (70 * 1024 * 1024)})
    assert api.upload(s, case["id"], "bomb.docx", bomb, DOCX).json()["error"]["code"] == "archive_bomb"


def test_oversized_upload(api, monkeypatch):
    s = api.register()
    case = api.case(s)
    big = b"a" * (get_settings().max_upload_bytes + 10)
    assert api.upload(s, case["id"], "big.txt", big, "text/plain").status_code == 413


def test_path_traversal_filename_is_neutralised(api):
    s = api.register()
    case = api.case(s)
    r = api.upload(s, case["id"], "../../../etc/passwd.txt", b"harmless text", "text/plain")
    assert r.status_code == 201 and r.json()[0]["filename"] == "passwd.txt"


def test_too_many_files(api):
    s = api.register()
    case = api.case(s)
    files = [("files", (f"f{i}.txt", b"text", "text/plain")) for i in range(11)]
    assert api.c.post(f"/api/v1/cases/{case['id']}/documents", files=files, headers=s.h).status_code in (422, 429)


def test_files_are_encrypted_at_rest_when_key_set(tmp_path):
    import base64, os
    from app.services.storage import LocalStorage
    st = LocalStorage(tmp_path, base64.b64encode(os.urandom(32)).decode(), production=False)
    key = st.put(b"SECRET FIR CONTENT")
    raw = next(p for p in tmp_path.rglob("*") if p.is_file()).read_bytes()
    assert b"SECRET FIR CONTENT" not in raw and st.get(key) == b"SECRET FIR CONTENT"
