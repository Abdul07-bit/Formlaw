"""Deterministic grounding rules: the model is never trusted to police itself."""

import pytest
from pydantic import ValidationError

from app.agents.review.schemas import Claim, Contradiction, Fact, Risk, TimelineEvent
from app.agents.review.validators import ground_analysis
from app.errors import GroundingViolationError
from tests.fixtures import ARJUN_DOC, Q_REMAND, analysis, arrest_analysis, ev


def _ground(a, doc=ARJUN_DOC, name="case_001.pdf"):
    return ground_analysis(a, document_text=doc, document_name=name)


def test_valid_analysis_passes_without_warnings() -> None:
    outcome = _ground(arrest_analysis())
    assert outcome.warnings == []


def test_fabricated_evidence_text_is_rejected() -> None:
    a = arrest_analysis()
    a.evidence[1].text = "The report states that Arjun Kumar was arrested on 13 March 2026."
    with pytest.raises(GroundingViolationError) as exc:
        _ground(a)
    assert any("verbatim" in v for v in exc.value.violations)


def test_verbatim_match_ignores_whitespace_and_case() -> None:
    a = arrest_analysis()
    a.evidence[1].text = Q_REMAND.replace(" ", "\n ").upper()
    _ground(a)  # must not raise


def test_unknown_evidence_reference_is_rejected() -> None:
    a = arrest_analysis()
    a.facts[0].evidence_ids = ["E999"]
    with pytest.raises(GroundingViolationError) as exc:
        _ground(a)
    assert any("E999" in v for v in exc.value.violations)


def test_duplicate_ids_are_rejected() -> None:
    a = arrest_analysis()
    a.facts[1].id = "F001"
    with pytest.raises(GroundingViolationError):
        _ground(a)


def test_fact_without_evidence_cannot_be_supported() -> None:
    a = analysis(facts=[Fact(id="F001", statement="Something.", category=None,
                             evidence_ids=[], confidence=0.9, status="SUPPORTED")])  # fmt: skip
    outcome = _ground(a)
    assert outcome.analysis.facts[0].status == "UNSUPPORTED"
    assert any("F001" in w for w in outcome.warnings)


def test_claims_without_evidence_are_downgraded() -> None:
    a = analysis(claims=[
        Claim(id="C001", text="A thing happened.", claim_type="FACT", evidence_ids=[],
              confidence=0.9, verification_status="SUPPORTED"),
        Claim(id="C002", text="Probably a thing.", claim_type="INFERENCE", evidence_ids=[],
              confidence=0.4, verification_status="PENDING"),
    ])  # fmt: skip
    claims = _ground(a).analysis.claims
    assert claims[0].verification_status == "UNSUPPORTED"
    assert claims[1].verification_status == "UNVERIFIED"


def test_risk_without_evidence_is_marked_inference() -> None:
    a = analysis(risks=[Risk(id="R001", title="Big", description="d", risk_level="CRITICAL",
                             evidence_ids=[], is_inference=False, recommended_action=None,
                             confidence=0.7)])  # fmt: skip
    assert _ground(a).analysis.risks[0].is_inference is True


def test_timeline_event_without_evidence_is_unknown() -> None:
    a = analysis(timeline=[TimelineEvent(id="T001", date="1 Jan 2026", description="x",
                                         evidence_ids=[], confidence=0.5, status="SUPPORTED")])  # fmt: skip
    assert _ground(a).analysis.timeline[0].status == "UNKNOWN"


def test_contradiction_needs_two_distinct_evidence_ids() -> None:
    with pytest.raises(ValidationError):  # schema-level: min_length=2
        Contradiction(id="X1", description="d", conflicting_evidence_ids=["E002"],
                      affected_ids=[], confidence=0.5)  # fmt: skip
    a = arrest_analysis()
    a.contradictions[0].conflicting_evidence_ids = ["E002", "E002"]  # same evidence twice
    with pytest.raises(GroundingViolationError):
        _ground(a)


def test_contradiction_with_unknown_affected_id_is_rejected() -> None:
    a = arrest_analysis()
    a.contradictions[0].affected_ids = ["F404"]
    with pytest.raises(GroundingViolationError):
        _ground(a)


def test_guessed_page_number_is_nulled_but_real_marker_is_kept() -> None:
    a = arrest_analysis()
    a.evidence[1].page = 7
    outcome = _ground(a)
    assert outcome.analysis.evidence[1].page is None
    assert any("page" in w for w in outcome.warnings)

    marked = f"[Page 2]\n{ARJUN_DOC}"
    a2 = arrest_analysis()
    a2.evidence[1].page = 2
    assert _ground(a2, doc=marked).analysis.evidence[1].page == 2


def test_unknown_section_label_is_nulled() -> None:
    a = arrest_analysis()
    a.evidence[1].section = "Annexure Q"
    out = _ground(a).analysis
    assert out.evidence[1].section is None


def test_document_name_comes_from_caller_not_model() -> None:
    a = arrest_analysis()
    a.evidence[0].document_name = "model_invented.pdf"
    assert _ground(a, name="real.pdf").analysis.evidence[0].document_name == "real.pdf"
    assert _ground(a, name=None).analysis.evidence[0].document_name is None


def test_authority_present_in_document_is_allowed() -> None:
    doc = "Charges are framed under Section 302 of the Penal Code. The High Court granted bail."
    a = analysis(
        summary="The document refers to Section 302.",
        claims=[Claim(id="C001", text="The High Court granted bail.", claim_type="FACT",
                      evidence_ids=["E001"], confidence=0.9, verification_status="SUPPORTED")],
        evidence=[ev("E001", "The High Court granted bail.")],
    )  # fmt: skip
    _ground(a, doc=doc)


def test_invented_section_in_summary_is_rejected() -> None:
    a = analysis(summary="The accused is liable under Section 420.")
    with pytest.raises(GroundingViolationError) as exc:
        _ground(a)
    assert any("Section 420" in v for v in exc.value.violations)


def test_unsupported_claim_mentioning_absent_authority_is_allowed() -> None:
    a = analysis(claims=[Claim(id="C001", text="A Supreme Court judgment proves guilt.",
                               claim_type="LEGAL_RULE", evidence_ids=[], confidence=0.9,
                               verification_status="UNSUPPORTED")])  # fmt: skip
    _ground(a)  # recording that the claim is unsupported is not asserting it
