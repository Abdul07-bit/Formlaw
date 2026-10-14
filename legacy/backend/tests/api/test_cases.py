from tests.helpers import DOCX, make_docx, make_pdf

FIR = ["FIRST INFORMATION REPORT. Police Station: Sector 9. FIR No. 77/2026.",
       "Offence: Theft from shop premises under Section 303 BNS.",
       "The accused Ravi Verma was arrested on 14 March 2026 at his residence.",
       "On the night of 10 March 2026 the shop was burgled."]
REMAND = ["REMAND REPORT. The accused Ravi Verma was arrested on 12 March 2026 by the police."]


def _reviewed_case(api, s):
    case = api.case(s, "State v. Ravi Verma", description="My brother was arrested for theft.")
    assert api.upload(s, case["id"], "fir.pdf", make_pdf(FIR), "application/pdf").status_code == 201
    assert api.upload(s, case["id"], "remand.docx", make_docx(REMAND), DOCX).status_code == 201
    r = api.c.post(f"/api/v1/cases/{case['id']}/review", headers=s.h)
    assert r.status_code == 200, r.text
    return case, r.json()


def test_case_create_and_list(api):
    s = api.register()
    case = api.case(s, "My matter")
    assert case["access"] == "owner" and case["documents"] == []
    assert [c["id"] for c in api.c.get("/api/v1/cases", headers=s.h).json()] == [case["id"]]


def test_upload_pdf_docx_and_review(api, seeded):
    s = api.register()
    case, a = _reviewed_case(api, s)
    assert a["area"] == "Criminal"
    assert a["contradictions"][0]["topic"] == "Arrest date"
    assert {a["contradictions"][0]["a"]["value"], a["contradictions"][0]["b"]["value"]} == {"12 March 2026", "14 March 2026"}
    ev_ids = {e["id"] for e in a["evidence"]}
    assert all(set(f["evidenceIds"]) <= ev_ids and f["evidenceIds"] for f in a["facts"])
    assert {e["docName"] for e in a["evidence"]} == {"fir.pdf", "remand.docx"}
    assert a["matches"], "seeded verified criminal lawyers should match"
    assert all(m["reasons"] for m in a["matches"])
    assert "guarantee" in a["feeDisclaimer"]
    assert a["legalPipeline"]["release_status"]
    assert any(t["agent"] == "Legal Agents" for t in a["trace"])
    # GET returns the persisted analysis.
    got = api.c.get(f"/api/v1/cases/{case['id']}", headers=s.h).json()
    assert got["analysis"]["taskId"] == a["taskId"] and got["status"] == "reviewed"


def test_review_needs_documents(api):
    s = api.register()
    case = api.case(s)
    assert api.c.post(f"/api/v1/cases/{case['id']}/review", headers=s.h).json()["error"]["code"] == "no_documents"


def test_chat_grounded_and_conflict_aware(api, seeded):
    s = api.register()
    case, _ = _reviewed_case(api, s)
    conflict = api.c.post(f"/api/v1/cases/{case['id']}/chat", json={"question": "When was the accused arrested?"}, headers=s.h).json()
    assert conflict["status"] == "conflicted" and len(conflict["evidenceIds"]) == 2
    ans = api.c.post(f"/api/v1/cases/{case['id']}/chat", json={"question": "Which section is the offence under?"}, headers=s.h).json()
    assert ans["status"] == "supported" and "Section 303 BNS" in ans["text"] and ans["evidence"]
    none = api.c.post(f"/api/v1/cases/{case['id']}/chat", json={"question": "What is the weather in Paris?"}, headers=s.h).json()
    assert none["status"] == "insufficient"


def test_statutory_draft_types(api, seeded):
    s = api.register()
    case, _ = _reviewed_case(api, s)
    r = api.c.post(f"/api/v1/cases/{case['id']}/draft", json={"docType": "anticipatory_bail"}, headers=s.h)
    assert r.status_code == 200 and r.json()["legalPipeline"]["docType"] == "anticipatory_bail"
    assert api.c.post(f"/api/v1/cases/{case['id']}/draft", json={"docType": "fake_type"}, headers=s.h).status_code == 422


def test_evidence_and_matches_endpoints(api, seeded):
    s = api.register()
    case, a = _reviewed_case(api, s)
    ev = api.c.get(f"/api/v1/cases/{case['id']}/evidence", headers=s.h).json()
    assert ev == a["evidence"] and all(len(e["contentHash"]) == 64 for e in ev)
    m = api.c.get(f"/api/v1/cases/{case['id']}/lawyer-matches", headers=s.h).json()
    assert m["matches"] == a["matches"]


def test_research_distinguishes_kinds_and_never_fabricates(api):
    s = api.register()
    r = api.c.post("/api/v1/research", json={"query": "bail in murder case Section 439"}, headers=s.h).json()
    kinds = {x["kind"] for x in r["results"]}
    assert "statute_section" in kinds and all(x["sourceUrl"] for x in r["results"])
    art = api.c.post("/api/v1/research", json={"query": "Article 21 personal liberty", "kinds": ["constitution_article"]}, headers=s.h).json()
    assert art["results"] == [] and "not been imported" in art["note"]


def test_demo_case(api, seeded):
    s = api.demo("client")
    r = api.c.post("/api/v1/cases/demo", json={"malicious": True}, headers=s.h)
    assert r.status_code == 201 and r.json()["isDemo"] and len(r.json()["documents"]) == 7
