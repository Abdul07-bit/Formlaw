from app.retrieval.hybrid import Passage, search

P = [
    Passage("1", "Article 21 protects life and personal liberty.", "c1", "Constitution", section="Article 21", source="constitution",
            metadata={"kind": "constitution_article", "jurisdiction": "India"}),
    Passage("2", "Section 437 deals with bail in non-bailable offences.", "s1", "CrPC", section="Section 437", source="statute",
            metadata={"kind": "statute_section", "jurisdiction": "India"}),
    Passage("3", "The court granted bail considering the period of custody.", "j1", "State v. X", source="judgment",
            metadata={"kind": "judgment", "court": "Delhi High Court", "date": "2022-05-01", "jurisdiction": "Delhi"}),
    Passage("4", "Bail was refused because of the gravity of the offence.", "j2", "State v. Y", source="judgment",
            metadata={"kind": "judgment", "court": "Bombay High Court", "date": "2014-01-01", "jurisdiction": "Maharashtra"}),
]


def test_keyword_ranking_and_provenance():
    hits = search(P, "bail custody", k=2)
    assert hits[0][0].id == "3"
    ev = hits[0][0].as_evidence()
    assert {"evidence_id", "document_id", "document_name", "page", "section", "text", "source", "content_hash"} <= set(ev)
    assert len(ev["content_hash"]) == 64


def test_metadata_filters():
    assert [p.id for p, _ in search(P, "bail", filters={"kind": ["judgment"], "date_from": "2016-01-01"})] == ["3"]
    assert [p.id for p, _ in search(P, "bail", filters={"court": "Bombay High Court"})] == ["4"]
    assert search(P, "bail", filters={"jurisdiction": "Kerala"}) == []


def test_article_query_prefers_article():
    assert search(P, "Article 21 personal liberty", k=1)[0][0].id == "1"


def test_semantic_fusion_used_when_available():
    vectors = {"1": [1.0, 0.0], "2": [0.0, 1.0], "3": [0.0, 1.0], "4": [0.0, 1.0]}
    hits = search(P, "freedom", embed=lambda texts: [[1.0, 0.0]], passage_vectors=vectors)
    assert hits and hits[0][0].id == "1"  # no keyword overlap; found semantically


def test_empty_query():
    assert search(P, "   ") == []
