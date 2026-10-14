"""Missing-Information Agent: checklist of records a matter of this type normally needs."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .chunking import Chunk


@dataclass(frozen=True)
class Gap:
    title: str
    why: str
    action: str


_C = lambda t, p, w, a: (t, re.compile(p, re.I), w, a)  # noqa: E731

CHECKLISTS: dict[str, list[tuple[str, re.Pattern[str], str, str]]] = {
    "Criminal": [
        _C("Arrest memo", r"arrest memo", "Article 22 and BNSS s.36 require an arrest memo; it is the primary record of the time and place of arrest.", "Obtain a certified copy of the arrest memo."),
        _C("Previous bail proceedings", r"bail order|order copy.*available(?! in this file)", "Prior bail history may affect the assessment of procedural history and conditions.", "Retrieve the previous bail order or filing (court, case no., date)."),
        _C("CCTV footage / seizure memo", r"seizure memo|footage (was )?seized", "The suspect was named on the basis of CCTV, but no seizure memo or electronic-record certificate is on file.", "Request the seizure memo and a BSA s.63 certificate for the footage."),
        _C("Magistrate production record", r"produced before|production before", "Production within 24 hours of arrest is a constitutional safeguard under Article 22(2).", "Retrieve the first remand/production order with date and time."),
    ],
    "Family": [
        _C("Marriage certificate", r"marriage certificate", "Establishes the legal relationship and jurisdiction.", "Upload the marriage certificate or registration."),
        _C("Income proof of both parties", r"income|salary slip|itr", "Maintenance is assessed on comparative income.", "Upload salary slips or ITRs."),
    ],
    "Property": [
        _C("Title / sale deed", r"sale deed|title deed", "Ownership must be proved by registered documents.", "Upload the registered sale/title deed."),
        _C("Revenue records (jamabandi / mutation)", r"jamabandi|mutation|khata", "Revenue entries show possession and mutation history.", "Obtain certified revenue extracts."),
    ],
    "Corporate": [
        _C("Executed agreement", r"agreement|contract", "Obligations must be read from the signed contract.", "Upload the signed agreement with annexures."),
        _C("Notice of breach", r"notice", "Most contracts require written notice before termination or claims.", "Upload any notices exchanged."),
    ],
    "Consumer": [
        _C("Invoice / proof of purchase", r"invoice|receipt|order id", "Needed to establish the consumer relationship.", "Upload the invoice or order confirmation."),
        _C("Complaint correspondence", r"email|complaint|ticket", "Shows the seller was given an opportunity to remedy.", "Upload emails or ticket history."),
    ],
    "Cyber": [
        _C("Cybercrime complaint acknowledgement", r"acknowledg|cybercrime\.gov|1930", "Prompt reporting enables fund freezing.", "File on cybercrime.gov.in / call 1930 and upload the acknowledgement."),
        _C("Bank statement with transaction IDs", r"statement|utr|transaction id", "Transaction references are needed to trace funds.", "Upload the bank statement."),
    ],
    "Labour": [
        _C("Appointment letter", r"appointment letter|offer letter", "Defines employment terms and notice period.", "Upload the appointment letter."),
        _C("Termination letter", r"termination letter|relieving", "Required to examine compliance with notice and compensation.", "Upload the termination letter."),
    ],
    "Constitutional": [
        _C("Impugned order / action", r"order dated|impugned", "A writ challenges a specific order or action.", "Upload the order being challenged."),
    ],
}


def find_missing(area: str, chunks: list[Chunk]) -> list[Gap]:
    text = "\n".join(c.sentence for c in chunks)
    gaps = [Gap(t, w, a) for t, rx, w, a in CHECKLISTS.get(area, []) if not rx.search(text)]
    # Gaps the documents themselves flag ("not available") outrank checklist gaps.
    if area == "Criminal" and re.search(r"not available", text, re.I):
        idx = next((i for i, g in enumerate(gaps) if g.title == "Previous bail proceedings"), -1)
        if idx > 0:
            gaps.insert(0, gaps.pop(idx))
    return gaps
