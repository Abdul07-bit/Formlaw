"""Intent understanding: rules first (always available, auditable), a fast model when configured."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...domain.enums import Intent

RULES: list[tuple[Intent, str]] = [
    (Intent.DRAFT, r"\b(draft|write|prepare|compose|generate)\b.{0,60}\b(notice|memo|summary|outline|letter|update|reply|response|clause|note|chronology|questions|report|brief)\b|\bcross[- ]exam"),
    (Intent.CONTRADICTIONS, r"\b(contradict\w*|inconsisten\w*|conflict\w*|discrepan\w*|mismatch\w*)\b"),
    (Intent.MISSING_INFO, r"\b(missing|gaps?|lacking|absent)\b|\bwhat else\b.{0,30}\bneed|\bnot (been )?(provided|produced|filed)\b"),
    (Intent.TIMELINE, r"\b(timeline|chronolog\w*|sequence of events)\b"),
    (Intent.CONTRACT_REVIEW, r"\b(contract|clause|agreement|nda|lease)\b.{0,40}\b(risk|review|analy\w+|obligation|terminat\w*)\b|\b(review|analy\w+)\b.{0,30}\b(contract|agreement)\b"),
    (Intent.LEGAL_RESEARCH, r"\b(authorit\w+|precedents?|case law|judgments?|research|rulings?|supreme court|high court)\b"),
    (Intent.COMPARE_DOCUMENTS, r"\b(compare|comparison|difference between|differences)\b"),
    (Intent.CASE_REVIEW, r"\b(review|analy[sz]e|analysis|weakness\w*|strength\w*|assess\w*|evaluate)\b"),
    (Intent.SUMMARY, r"\b(summar\w+|overview|brief me|senior counsel)\b"),
]
DRAFT_KINDS = [
    ("cross_examination_questions", r"cross[- ]exam|questions"), ("legal_notice", r"\bnotice\b"), ("research_memo", r"\bmemo\b"),
    ("argument_outline", r"\boutline|arguments?\b"), ("client_update", r"\bclient\b.{0,20}\bupdate|\bupdate\b"),
    ("chronology", r"\bchronolog"), ("response_draft", r"\breply|response\b"), ("contract_clause", r"\bclause\b"),
    ("briefing_note", r"\bbriefing|senior counsel|brief\b"), ("case_summary", r"\bsummary|summar"),
]
_VERBS = re.compile(r"\b(please|can you|could you|find|identify|show me|tell me|list|give me|what|which|who|when|where|how|is|are|does|do|"
                    r"the|a|an|in|of|and|for|this|that|case|documents?|records?|review|analy[sz]e|build|draft|write|prepare|about|"
                    r"regarding|me|any|all|there|from|to|on|with|my|our|more|most|less|reliable|reliability|establish\w*|prove\w*|"
                    r"show\w*|strongest|biggest|main|key|important|relevant|evidence|support\w*|weakness\w*|strength\w*|"
                    r"opposing|party|party's|whether|be|been|was|were|it|its|do|not|assume|anything|between|each|other|"
                    r"say|says|said|mention\w*|tell|happened)\b", re.I)


@dataclass
class IntentResult:
    intent: Intent
    secondary: list[Intent] = field(default_factory=list)
    topic: str = ""
    draft_kind: str = ""
    wants_research: bool = False
    engine: str = "rules"


def topic_of(text: str) -> str:
    t = re.sub(r"[^\w\s'-]", " ", text)
    for _, pat in RULES:
        t = re.sub(pat, " ", t, flags=re.I)
    words = [w for w in _VERBS.sub(" ", t).split() if len(w) > 2]
    return " ".join(words[:6])


def classify_rules(text: str) -> IntentResult:
    low = text.lower()
    matched = [i for i, pat in RULES if re.search(pat, low)]
    primary = matched[0] if matched else Intent.EVIDENCE_QA
    # "Which document establishes the arrest date?" is a question about evidence, even if it mentions a judgment.
    if primary == Intent.LEGAL_RESEARCH and re.search(r"\b(which|what) (document|record|evidence)\b", low):
        primary = Intent.EVIDENCE_QA
    draft_kind = next((k for k, p in DRAFT_KINDS if re.search(p, low)), "case_summary") if primary == Intent.DRAFT else ""
    return IntentResult(primary, [i for i in matched if i != primary][:3], topic_of(text), draft_kind,
                        Intent.LEGAL_RESEARCH in matched and primary != Intent.LEGAL_RESEARCH)
