"""Synthetic test data. The Arjun Kumar case exists ONLY here, as a fixture."""

from app.agents.review.schemas import (
    Claim,
    Contradiction,
    EvidenceReference,
    Fact,
    Issue,
    MissingInformation,
    Party,
    ReviewAnalysis,
    Risk,
    TimelineEvent,
)

ARJUN_DOC = """Case: State v. Arjun Kumar

FIR:
The incident occurred on 10 March 2026 at approximately 10:30 PM. Arjun Kumar was subsequently named as a suspect.

Witness Statement:
The witness stated that visibility was poor and that they could not clearly identify the person's face.

Remand Report:
The report states that Arjun Kumar was arrested on 14 March 2026.

Earlier Case Narrative:
Another section states that Arjun Kumar was arrested on 12 March 2026.

Employment Attendance Record:
Arjun Kumar worked from 6:00 PM to 11:00 PM. The recorded clock-out time was 11:07 PM.

Previous Bail Information:
The available document does not contain complete information about the previous bail proceedings.
"""

CONTRACT_DOC = """EMPLOYMENT AGREEMENT
This Agreement is made between Acme Pvt Ltd ("Employer") and Priya Nair ("Employee").
1. Term: Employment begins on 1 April 2026.
2. Termination: Either party may terminate this Agreement by giving seven (7) days written notice.
3. Confidentiality: The Employee shall keep all Employer information confidential during and after employment.
4. Payment: The Employee shall receive a monthly salary of INR 80,000.
"""

# Verbatim excerpts of ARJUN_DOC
Q_INCIDENT = "The incident occurred on 10 March 2026 at approximately 10:30 PM."
Q_REMAND = "The report states that Arjun Kumar was arrested on 14 March 2026."
Q_NARRATIVE = "Another section states that Arjun Kumar was arrested on 12 March 2026."
Q_WITNESS = (
    "The witness stated that visibility was poor and that they could not clearly "
    "identify the person's face."
)
Q_CLOCKOUT = "The recorded clock-out time was 11:07 PM."
Q_BAIL = "The available document does not contain complete information about the previous bail proceedings."


def ev(eid: str, text: str, section: str | None = None) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=eid, document_name=None, page=None, section=section,
        paragraph=None, text=text, source_type="document_excerpt",
    )  # fmt: skip


def analysis(**overrides: object) -> ReviewAnalysis:
    """A minimal valid analysis; override any field."""
    base: dict[str, object] = dict(
        summary="The document states one thing.", summary_evidence_ids=[],
        parties=[], facts=[], timeline=[], issues=[], risks=[], contradictions=[],
        missing_information=[], claims=[], evidence=[], confidence=0.8,
    )  # fmt: skip
    base.update(overrides)
    return ReviewAnalysis(**base)  # type: ignore[arg-type]


def arrest_analysis() -> ReviewAnalysis:
    """What a well-behaved model returns for 'When was Arjun Kumar arrested?'."""
    return analysis(
        summary=(
            "The document gives conflicting arrest dates: the remand report states 14 March 2026, "
            "while an earlier case narrative states 12 March 2026. The date cannot be determined "
            "from the document alone."
        ),
        summary_evidence_ids=["E002", "E003"],
        parties=[Party(id="P001", name="Arjun Kumar", role="accused", evidence_ids=["E001"])],
        facts=[
            Fact(id="F001", statement="The incident occurred on 10 March 2026 at about 10:30 PM.",
                 category="INCIDENT", evidence_ids=["E001"], confidence=0.95, status="SUPPORTED"),
            Fact(id="F002", statement="Date of Arjun Kumar's arrest.", category="ARREST",
                 evidence_ids=["E002", "E003"], confidence=0.9, status="CONTRADICTED"),
        ],  # fmt: skip
        timeline=[
            TimelineEvent(id="T001", date="10 March 2026", description="Reported incident",
                          evidence_ids=["E001"], confidence=0.95, status="SUPPORTED"),
            TimelineEvent(id="T002", date="14 March 2026",
                          description="Arrest date stated in the remand report",
                          evidence_ids=["E002"], confidence=0.9, status="CONFLICTED"),
            TimelineEvent(id="T003", date="12 March 2026",
                          description="Arrest date stated in the earlier case narrative",
                          evidence_ids=["E003"], confidence=0.9, status="CONFLICTED"),
        ],  # fmt: skip
        issues=[Issue(id="I001", title="Conflicting arrest dates",
                      description="Two sections of the document give different arrest dates.",
                      type="FACTUAL", evidence_ids=["E002", "E003"], confidence=0.9)],
        contradictions=[Contradiction(
            id="X001",
            description="The remand report says 14 March 2026; the earlier case narrative says 12 March 2026.",
            conflicting_evidence_ids=["E002", "E003"],
            affected_ids=["F002", "T002", "T003", "C001"], confidence=0.92)],
        missing_information=[MissingInformation(
            id="M001", description="Complete previous bail documentation is unavailable.",
            why_it_matters="Prior bail history may be relevant to bail and remand.", confidence=0.9)],
        claims=[Claim(id="C001", text="Arjun Kumar was arrested on 14 March 2026.",
                      claim_type="FACT", evidence_ids=["E002", "E003"], confidence=0.9,
                      verification_status="CONTRADICTED")],
        evidence=[
            ev("E001", Q_INCIDENT, "FIR"),
            ev("E002", Q_REMAND, "Remand Report"),
            ev("E003", Q_NARRATIVE, "Earlier Case Narrative"),
            ev("E006", Q_BAIL, "Previous Bail Information"),
        ],
        confidence=0.88,
    )  # fmt: skip


def witness_analysis() -> ReviewAnalysis:
    return analysis(
        summary=(
            "No. The witness statement says visibility was poor and that the witness could not "
            "clearly identify the person's face."
        ),
        summary_evidence_ids=["E004"],
        facts=[Fact(id="F001", statement="The witness could not clearly identify the person's face.",
                    category="IDENTIFICATION", evidence_ids=["E004"], confidence=0.95,
                    status="SUPPORTED")],
        issues=[Issue(id="I001", title="Weak identification evidence",
                      description="Poor visibility limited the witness's ability to identify the person.",
                      type="EVIDENTIARY", evidence_ids=["E004"], confidence=0.85)],
        claims=[Claim(id="C001", text="The witness positively identified Arjun Kumar.",
                      claim_type="FACT", evidence_ids=["E004"], confidence=0.9,
                      verification_status="UNSUPPORTED")],
        evidence=[ev("E004", Q_WITNESS, "Witness Statement")],
        confidence=0.9,
    )  # fmt: skip


def authority_absent_analysis() -> ReviewAnalysis:
    """Honest answer to: 'Which Supreme Court judgment proves that Arjun Kumar is guilty?'"""
    return analysis(
        summary="The supplied document does not contain any judgment or other legal authority, so none can be identified.",
        claims=[Claim(id="C001", text="A judgment proving guilt is present in the document.",
                      claim_type="LEGAL_RULE", evidence_ids=[], confidence=0.95,
                      verification_status="UNSUPPORTED")],
        missing_information=[MissingInformation(
            id="M001", description="The document contains no judgment or legal authority.",
            why_it_matters="Legal propositions cannot be verified without authority.", confidence=0.95)],
        confidence=0.9,
    )  # fmt: skip


def hallucinated_authority_analysis() -> ReviewAnalysis:
    """What a hallucinating model might return. Must be rejected."""
    return analysis(
        summary="The document does not say, but a judgment exists.",
        claims=[Claim(id="C001",
                      text="The Supreme Court in Ram v. Shyam (AIR 1978 SC 597) held that possession proves guilt.",
                      claim_type="LEGAL_RULE", evidence_ids=[], confidence=0.9,
                      verification_status="PENDING")],
        confidence=0.9,
    )  # fmt: skip


def contract_analysis() -> ReviewAnalysis:
    return analysis(
        summary=(
            "Either party may terminate on seven days' written notice. The agreement contains no "
            "governing law, liability or indemnity clause."
        ),
        summary_evidence_ids=["E002"],
        parties=[
            Party(id="P001", name="Acme Pvt Ltd", role="Employer", evidence_ids=["E004"]),
            Party(id="P002", name="Priya Nair", role="Employee", evidence_ids=["E004"]),
        ],
        facts=[Fact(id="F001", statement="Employment begins on 1 April 2026.", category="TERM",
                    evidence_ids=["E001"], confidence=0.95, status="SUPPORTED")],
        risks=[Risk(id="R001", title="Short termination notice period",
                    description="Seven days' notice may be short relative to typical employment terms.",
                    risk_level="MEDIUM", evidence_ids=["E002"], is_inference=False,
                    recommended_action="Review clause against organizational policy.", confidence=0.88)],
        missing_information=[
            MissingInformation(id="M001", description="No governing law clause is present.",
                               why_it_matters="Determines which law applies to disputes.", confidence=0.9),
            MissingInformation(id="M002", description="No liability or indemnity clause is present.",
                               why_it_matters="Allocation of liability is undefined.", confidence=0.9),
        ],
        claims=[Claim(id="C001", text="Either party may terminate on seven days' written notice.",
                      claim_type="FACT", evidence_ids=["E002"], confidence=0.9,
                      verification_status="SUPPORTED")],
        evidence=[
            ev("E001", "Employment begins on 1 April 2026.", "1. Term"),
            ev("E002", "Either party may terminate this Agreement by giving seven (7) days written notice.",
               "2. Termination"),
            ev("E004", 'This Agreement is made between Acme Pvt Ltd ("Employer") and Priya Nair ("Employee").'),
        ],
        confidence=0.87,
    )  # fmt: skip
