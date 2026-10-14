"""Deterministic grounding checks applied to every model output.

The LLM is not the source of truth. These rules run in code, after schema validation:

HARD violations (output rejected -> the agent retries with feedback, then fails safely):
  * evidence text that is not a verbatim excerpt of the supplied document
  * duplicate ids, or references to evidence/fact/claim ids that do not exist
  * contradictions that do not cite two distinct pieces of evidence
  * legal authority (citations, sections, case names, court names) asserted but absent
    from the document

CONSERVATIVE corrections (always toward less certainty; each recorded as a warning):
  * SUPPORTED/PENDING with no evidence is downgraded to UNSUPPORTED/UNVERIFIED
  * page/section/paragraph labels that cannot be found in the document are nulled
  * items named in a contradiction are marked CONTRADICTED / CONFLICTED
  * risks with no evidence are marked as inference
"""

import re
from dataclasses import dataclass

from app.agents.review.schemas import ReviewAnalysis
from app.agents.review.security import neutralize_delimiters
from app.errors import GroundingViolationError

_CITATION_RE = re.compile(r"\b(?:AIR|SCC|SCR|CrLJ)\b[^.\n]{0,12}?\d{1,4}")
_SECTION_RE = re.compile(r"\b(?:Section|Sec\.|Article)\s+\d+[A-Za-z]?(?:\(\w+\))*", re.IGNORECASE)
_CASE_NAME_RE = re.compile(r"\b([A-Z]\w*)\s+v\.?\s+([A-Z]\w*)\b")
_COURT_RE = re.compile(r"\b(?:Supreme Court|High Court)\b", re.IGNORECASE)

_ASSERTED_FACT = {"SUPPORTED", "PARTIALLY_SUPPORTED"}
_ASSERTED_CLAIM = {"PENDING", "SUPPORTED", "PARTIALLY_SUPPORTED"}
MAX_REPORTED_VIOLATIONS = 20


def normalize(text: str) -> str:
    """Whitespace-collapsed, case-folded form used for verbatim-excerpt matching."""
    return " ".join(text.split()).casefold()


def _normalize_authority(text: str) -> str:
    return re.sub(r"\bsec\.", "section", normalize(text))


@dataclass(frozen=True)
class GroundingOutcome:
    analysis: ReviewAnalysis
    warnings: list[str]


def ground_analysis(
    analysis: ReviewAnalysis, *, document_text: str, document_name: str | None
) -> GroundingOutcome:
    """Validate and conservatively correct `analysis`. Raises GroundingViolationError."""
    result = analysis.model_copy(deep=True)
    warnings: list[str] = []
    violations: list[str] = []
    doc_forms = [normalize(document_text), normalize(neutralize_delimiters(document_text))]

    evidence_ids = _check_evidence(result, document_text, document_name, doc_forms, violations, warnings)
    _check_unique_ids(result, violations)
    _check_evidence_refs(result, evidence_ids, violations)
    # Authority is checked BEFORE downgrades so a fabricated-but-"PENDING" claim cannot
    # be quietly downgraded and slip past the check.
    _check_authorities(result, doc_forms, violations)
    _apply_contradictions(result, evidence_ids, violations)
    _downgrade_unsupported(result, warnings)

    if violations:
        raise GroundingViolationError(violations[:MAX_REPORTED_VIOLATIONS])
    if not result.summary_evidence_ids and (result.facts or result.claims):
        warnings.append("Summary is not linked to any evidence.")
    return GroundingOutcome(result, list(dict.fromkeys(warnings)))


def _check_evidence(
    result: ReviewAnalysis,
    document_text: str,
    document_name: str | None,
    doc_forms: list[str],
    violations: list[str],
    warnings: list[str],
) -> set[str]:
    seen: set[str] = set()
    for ev in result.evidence:
        if ev.evidence_id in seen:
            violations.append(f"Duplicate evidence_id {ev.evidence_id}.")
        seen.add(ev.evidence_id)
        if not any(normalize(ev.text) in form for form in doc_forms):
            violations.append(
                f"Evidence {ev.evidence_id} text is not a verbatim excerpt of the document."
            )
        ev.document_name = document_name  # provenance is set by us, never by the model
        if ev.page is not None and not re.search(rf"\bpage\s*{ev.page}\b", document_text, re.I):
            warnings.append(f"Evidence {ev.evidence_id}: page number not found in document; set to null.")
            ev.page = None
        for attr in ("section", "paragraph"):
            label = getattr(ev, attr)
            if label is not None and not any(normalize(label) in form for form in doc_forms):
                warnings.append(f"Evidence {ev.evidence_id}: {attr} label not found in document; set to null.")
                setattr(ev, attr, None)
    return seen


def _check_unique_ids(result: ReviewAnalysis, violations: list[str]) -> None:
    seen: set[str] = set()
    groups = (
        result.parties, result.facts, result.timeline, result.issues,
        result.risks, result.contradictions, result.missing_information, result.claims,
    )  # fmt: skip
    for group in groups:
        for item in group:
            if item.id in seen:
                violations.append(f"Duplicate id {item.id}.")
            seen.add(item.id)


def _check_evidence_refs(
    result: ReviewAnalysis, evidence_ids: set[str], violations: list[str]
) -> None:
    owners: list[tuple[str, list[str]]] = [("summary", result.summary_evidence_ids)]
    for group in (result.parties, result.facts, result.timeline, result.issues,
                  result.risks, result.claims):  # fmt: skip
        owners += [(item.id, item.evidence_ids) for item in group]
    for owner, ids in owners:
        for eid in ids:
            if eid not in evidence_ids:
                violations.append(f"{owner} cites unknown evidence_id {eid}.")


def _apply_contradictions(
    result: ReviewAnalysis, evidence_ids: set[str], violations: list[str]
) -> None:
    facts = {f.id: f for f in result.facts}
    claims = {c.id: c for c in result.claims}
    events = {t.id: t for t in result.timeline}
    for con in result.contradictions:
        cited = set(con.conflicting_evidence_ids)
        if len(cited) < 2:
            violations.append(f"{con.id} must cite at least two distinct evidence_ids.")
        for eid in cited - evidence_ids:
            violations.append(f"{con.id} cites unknown evidence_id {eid}.")
        for aid in con.affected_ids:
            if aid in facts:
                facts[aid].status = "CONTRADICTED"
            elif aid in claims:
                claims[aid].verification_status = "CONTRADICTED"
            elif aid in events:
                events[aid].status = "CONFLICTED"
            else:
                violations.append(f"{con.id} references unknown affected id {aid}.")


def _downgrade_unsupported(result: ReviewAnalysis, warnings: list[str]) -> None:
    for fact in result.facts:
        if not fact.evidence_ids and fact.status in _ASSERTED_FACT:
            fact.status = "UNSUPPORTED"
            warnings.append(f"Fact {fact.id} had no evidence; downgraded to UNSUPPORTED.")
    for event in result.timeline:
        if not event.evidence_ids and event.status == "SUPPORTED":
            event.status = "UNKNOWN"
            warnings.append(f"Timeline event {event.id} had no evidence; set to UNKNOWN.")
    for claim in result.claims:
        if not claim.evidence_ids and claim.verification_status in _ASSERTED_CLAIM:
            grounded_type = claim.claim_type in {"FACT", "LEGAL_RULE"}
            claim.verification_status = "UNSUPPORTED" if grounded_type else "UNVERIFIED"
            warnings.append(
                f"Claim {claim.id} had no evidence; set to {claim.verification_status}."
            )
    for risk in result.risks:
        if not risk.evidence_ids and not risk.is_inference:
            risk.is_inference = True
            warnings.append(f"Risk {risk.id} had no evidence; marked as inference.")


def _authority_tokens(text: str, *, include_courts: bool) -> list[str]:
    tokens = [m.group(0) for m in _CITATION_RE.finditer(text)]
    tokens += [m.group(0) for m in _SECTION_RE.finditer(text)]
    tokens += [m.group(0) for m in _CASE_NAME_RE.finditer(text)]
    if include_courts:
        tokens += [m.group(0) for m in _COURT_RE.finditer(text)]
    return tokens


def _check_authorities(
    result: ReviewAnalysis, doc_forms: list[str], violations: list[str]
) -> None:
    """Legal authority must come from the document, never from model memory."""
    checks: list[tuple[str, str, bool]] = [("summary", result.summary, False)]
    checks += [(i.id, f"{i.title} {i.description}", False) for i in result.issues]
    checks += [(r.id, f"{r.title} {r.description}", False) for r in result.risks]
    checks += [(f.id, f.statement, True) for f in result.facts if f.status in _ASSERTED_FACT]
    checks += [(c.id, c.text, True) for c in result.claims if c.verification_status in _ASSERTED_CLAIM]
    for owner, text, include_courts in checks:
        for token in _authority_tokens(text, include_courts=include_courts):
            norm = _normalize_authority(token)
            if not any(norm in _normalize_authority(form) for form in doc_forms):
                violations.append(
                    f"{owner} asserts legal authority '{token}' that does not appear in the document."
                )
