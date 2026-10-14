"""
Drafting Agent (quick brief). Uses only verified facts with their evidence references; never invents
facts, case numbers or citations. Blank court/case fields stay as blanks for the advocate to fill.
"""
from __future__ import annotations

from .case_review import ContradictionItem, EvidenceItem, Fact
from .missing import Gap

FOOTER = "[DRAFT generated from verified evidence only. Must be reviewed and signed by an enrolled advocate before filing.]"


def draft_for(area: str, title: str, facts: list[Fact], contradictions: list[ContradictionItem], missing: list[Gap],
              evidence: list[EvidenceItem]) -> tuple[str, str]:
    by_label = {e.label: e for e in evidence}

    def ref(f: Fact) -> str:
        return " ".join(f"[{l}: {by_label[l].doc_name}, p.{by_label[l].page}]" for l in f.evidence if l in by_label)

    usable = [f for f in facts if f.status != "UNSUPPORTED"]
    fact_lines = "\n".join(f"{i}. {f.statement} {ref(f)}{' — CONFLICTING' if f.status == 'CONTRADICTED' else ''}" for i, f in enumerate(usable, 1))
    conflict_lines = "\n".join(f'• {c.topic}: "{c.a_value}" [{c.a_evidence}] vs "{c.b_value}" [{c.b_evidence}]' for c in contradictions)
    missing_lines = "\n".join(f"• {g.title} — {g.action}" for g in missing) or "• None identified."

    if area == "Criminal":
        return ("Draft — Application for Regular Bail (BNSS s.480 / s.483)", f"""IN THE COURT OF ____________________
{title.upper()}

APPLICATION FOR REGULAR BAIL ON BEHALF OF THE ACCUSED

MOST RESPECTFULLY SHOWETH:

GROUNDS (each ground is linked to evidence on record)
{fact_lines or '• No verifiable facts could be extracted.'}

INCONSISTENCIES IN THE PROSECUTION RECORD
{conflict_lines or '• None detected in the supplied documents.'}

The applicant submits that the right to personal liberty under Article 21 of the Constitution of India, and the safeguards under Article 22, require that the above inconsistencies be examined before continued custody is ordered.

DOCUMENTS TO BE PLACED ON RECORD BEFORE FILING
{missing_lines}

PRAYER
It is therefore prayed that the applicant be released on bail on such terms as this Hon'ble Court deems fit.

{FOOTER}""")
    return ("Draft — Case Summary & Legal Notice Outline", f"""CASE SUMMARY — {title}

FACTS ESTABLISHED FROM DOCUMENTS
{fact_lines or '• No verifiable facts could be extracted from text documents.'}

{f'CONFLICTS{chr(10)}{conflict_lines}{chr(10)}{chr(10)}' if conflict_lines else ''}INFORMATION REQUIRED BEFORE ISSUING NOTICE
{missing_lines}

{FOOTER}""")
