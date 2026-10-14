"""Functional + reliability tests. The LLM is scripted, so these verify the agent's pipeline
(prompting, validation, grounding, retries, failure handling) - not a real model's reasoning."""

from app.agents.base import AgentStatus, WorkflowType
from app.agents.review.agent import ReviewAgent
from app.agents.review.schemas import ReviewAnalysis
from app.config import Settings
from app.errors import LLMFailureError, StructuredOutputError
from tests.conftest import make_context
from tests.fakes import HangingLLMProvider, ScriptedLLMProvider
from tests.fixtures import (
    CONTRACT_DOC,
    arrest_analysis,
    authority_absent_analysis,
    contract_analysis,
    hallucinated_authority_analysis,
    witness_analysis,
)

# ----------------------------------------------------------------- functional


async def test_basic_case_review(settings: Settings) -> None:
    provider = ScriptedLLMProvider(arrest_analysis())
    result = await ReviewAgent(provider=provider, settings=settings).run(make_context())

    assert result.status is AgentStatus.COMPLETED
    assert result.error is None and result.output is not None
    out = result.output
    assert out.workflow_type is WorkflowType.CASE_REVIEW
    assert out.status.value == "COMPLETED"
    assert result.prompt_version == "common_v1+case_v1"
    assert result.attempts == 1 and len(provider.calls) == 1
    assert provider.calls[0]["schema"] is ReviewAnalysis
    assert provider.calls[0]["model"] == "test-model"
    assert {e.evidence_id for e in out.evidence} >= {"E001", "E002", "E003"}
    assert all(e.document_name == "case_001.pdf" for e in out.evidence)
    # every fact/claim/timeline item is tied to evidence that exists
    known = {e.evidence_id for e in out.evidence}
    for item in [*out.facts, *out.claims, *out.timeline]:
        assert item.evidence_ids and set(item.evidence_ids) <= known


async def test_arrest_date_contradiction_is_reported_not_resolved(settings: Settings) -> None:
    provider = ScriptedLLMProvider(arrest_analysis())
    result = await ReviewAgent(provider=provider, settings=settings).run(make_context())
    out = result.output
    assert out is not None

    assert len(out.contradictions) == 1
    con = out.contradictions[0]
    assert set(con.conflicting_evidence_ids) == {"E002", "E003"}
    assert con.resolution_status == "UNRESOLVED"

    texts = {e.evidence_id: e.text for e in out.evidence}
    assert "14 March 2026" in texts["E002"] and "12 March 2026" in texts["E003"]
    assert "14 March 2026" in out.summary and "12 March 2026" in out.summary
    # neither date is asserted as the (supported) arrest date
    assert not any(
        c.verification_status == "SUPPORTED" and "arrest" in c.text.lower() for c in out.claims
    )
    assert {t.status for t in out.timeline if t.id in {"T002", "T003"}} == {"CONFLICTED"}
    assert "When was Arjun Kumar arrested?" in provider.calls[0]["user_prompt"]


async def test_contradiction_forces_affected_items_to_contradicted(settings: Settings) -> None:
    """If the model forgets to mark items it listed as contradicted, code does it."""
    sloppy = arrest_analysis()
    sloppy.facts[1].status = "SUPPORTED"
    sloppy.timeline[1].status = "SUPPORTED"
    sloppy.claims[0].verification_status = "SUPPORTED"

    result = await ReviewAgent(provider=ScriptedLLMProvider(sloppy), settings=settings).run(
        make_context()
    )
    out = result.output
    assert out is not None
    assert out.facts[1].status == "CONTRADICTED"
    assert out.timeline[1].status == "CONFLICTED"
    assert out.claims[0].verification_status == "CONTRADICTED"


async def test_witness_identification_is_not_supported(settings: Settings) -> None:
    result = await ReviewAgent(
        provider=ScriptedLLMProvider(witness_analysis()), settings=settings
    ).run(make_context(request="Did the witness positively identify Arjun Kumar?"))
    out = result.output
    assert out is not None
    claim = next(c for c in out.claims if "positively identified" in c.text)
    assert claim.verification_status in {"UNSUPPORTED", "CONTRADICTED"}
    assert claim.evidence_ids == ["E004"]
    evidence = next(e for e in out.evidence if e.evidence_id == "E004")
    assert "could not clearly identify" in evidence.text
    assert out.summary.startswith("No.")


async def test_missing_information_is_reported(settings: Settings) -> None:
    result = await ReviewAgent(
        provider=ScriptedLLMProvider(arrest_analysis()), settings=settings
    ).run(make_context(request="Was Arjun previously granted bail?"))
    out = result.output
    assert out is not None
    assert any("bail" in m.description.lower() for m in out.missing_information)


async def test_contract_review_extracts_clauses_and_gaps(settings: Settings) -> None:
    provider = ScriptedLLMProvider(contract_analysis())
    result = await ReviewAgent(provider=provider, settings=settings).run(
        make_context(
            request="Review this employment agreement and identify termination risks.",
            document_text=CONTRACT_DOC,
            workflow=WorkflowType.CONTRACT_REVIEW,
            document_name="employment.docx",
        )
    )
    out = result.output
    assert out is not None
    assert out.workflow_type is WorkflowType.CONTRACT_REVIEW
    assert result.prompt_version == "common_v1+contract_v1"
    assert "CONTRACT_REVIEW" in provider.calls[0]["system_prompt"]
    risk = out.risks[0]
    assert risk.risk_level == "MEDIUM" and risk.evidence_ids == ["E002"]
    cited = next(e for e in out.evidence if e.evidence_id == "E002")
    assert cited.text in CONTRACT_DOC and cited.section == "2. Termination"
    assert any("governing law" in m.description.lower() for m in out.missing_information)


async def test_unsupported_legal_authority_is_reported_as_missing(settings: Settings) -> None:
    result = await ReviewAgent(
        provider=ScriptedLLMProvider(authority_absent_analysis()), settings=settings
    ).run(make_context(request="Which Supreme Court judgment proves that Arjun Kumar is guilty?"))
    out = result.output
    assert out is not None
    assert "does not contain" in out.summary
    assert out.claims[0].verification_status == "UNSUPPORTED"
    assert any("no judgment" in m.description.lower() for m in out.missing_information)


async def test_hallucinated_authority_is_rejected_then_corrected(settings: Settings) -> None:
    provider = ScriptedLLMProvider(hallucinated_authority_analysis(), authority_absent_analysis())
    result = await ReviewAgent(provider=provider, settings=settings).run(
        make_context(request="Which Supreme Court judgment proves that Arjun Kumar is guilty?")
    )
    assert result.status is AgentStatus.COMPLETED and result.attempts == 2
    assert "<VALIDATION_FEEDBACK>" in provider.calls[1]["user_prompt"]
    assert "does not appear in the document" in provider.calls[1]["user_prompt"]
    assert result.output is not None
    assert "Ram v. Shyam" not in result.output.model_dump_json()


async def test_persistent_hallucinated_authority_fails_safely(settings: Settings) -> None:
    result = await ReviewAgent(
        provider=ScriptedLLMProvider(hallucinated_authority_analysis()), settings=settings
    ).run(make_context())
    assert result.status is AgentStatus.FAILED and result.output is None
    assert result.error is not None and result.error.code == "RETRY_EXHAUSTED"
    assert "GROUNDING_VIOLATION" in result.error.message


# ---------------------------------------------------------------- reliability


async def test_transient_llm_failure_is_retried(settings: Settings) -> None:
    provider = ScriptedLLMProvider(LLMFailureError("temporarily down", retryable=True), arrest_analysis())
    result = await ReviewAgent(provider=provider, settings=settings).run(make_context())
    assert result.status is AgentStatus.COMPLETED
    assert result.attempts == 2 and len(provider.calls) == 2


async def test_invalid_output_is_retried_with_feedback(settings: Settings) -> None:
    provider = ScriptedLLMProvider(
        StructuredOutputError("bad", details=["summary: Field required"]), arrest_analysis()
    )
    result = await ReviewAgent(provider=provider, settings=settings).run(make_context())
    assert result.status is AgentStatus.COMPLETED and result.attempts == 2
    assert "summary: Field required" in provider.calls[1]["user_prompt"]
    assert "<VALIDATION_FEEDBACK>" not in provider.calls[0]["user_prompt"]


async def test_retry_exhaustion_returns_structured_failure(settings: Settings) -> None:
    provider = ScriptedLLMProvider(LLMFailureError("down", retryable=True))
    result = await ReviewAgent(provider=provider, settings=settings).run(make_context())
    assert result.status is AgentStatus.FAILED and result.output is None
    assert result.error is not None and result.error.code == "RETRY_EXHAUSTED"
    assert result.attempts == settings.max_retries + 1 == len(provider.calls)


async def test_non_retryable_llm_failure_is_not_retried(settings: Settings) -> None:
    provider = ScriptedLLMProvider(LLMFailureError("rejected", retryable=False))
    result = await ReviewAgent(provider=provider, settings=settings).run(make_context())
    assert result.status is AgentStatus.FAILED
    assert result.error is not None and result.error.code == "LLM_FAILURE"
    assert len(provider.calls) == 1


async def test_out_of_range_output_is_never_accepted(settings: Settings) -> None:
    """A provider handing back an unvalidated instance (confidence=5) is re-validated and rejected."""
    bad = arrest_analysis().model_copy(update={"confidence": 5.0})
    provider = ScriptedLLMProvider(bad)
    result = await ReviewAgent(provider=provider, settings=settings).run(make_context())
    assert result.status is AgentStatus.FAILED and result.output is None
    assert result.error is not None and result.error.code == "RETRY_EXHAUSTED"
    assert "STRUCTURED_OUTPUT_INVALID" in result.error.message
    assert "confidence" in provider.calls[1]["user_prompt"]


async def test_wrong_output_type_is_rejected(settings: Settings) -> None:
    from app.agents.review.schemas import ReviewRequest

    wrong = ReviewRequest(request="x", workflow_type=WorkflowType.CASE_REVIEW, document_text="y")
    result = await ReviewAgent(provider=ScriptedLLMProvider(wrong), settings=settings).run(make_context())
    assert result.status is AgentStatus.FAILED and result.output is None


async def test_llm_timeout_is_classified_and_fails(settings: Settings) -> None:
    fast = settings.model_copy(update={"llm_timeout_seconds": 0.05, "max_retries": 1})
    provider = HangingLLMProvider()
    result = await ReviewAgent(provider=provider, settings=fast).run(make_context())
    assert result.status is AgentStatus.FAILED
    assert result.error is not None and result.error.code == "RETRY_EXHAUSTED"
    assert "LLM_FAILURE" in result.error.message
    assert provider.calls == 2
