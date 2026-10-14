"""Groundedness: SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED / CONTRADICTED / UNVERIFIED."""
import pytest

from app.agents.legal_bridge import corpus_citation_exists
from app.verification.groundedness import verify_claim

EV = ["The accused was arrested on 14 March 2026 at his residence in Dwarka, New Delhi.",
      "Offence: Theft from shop premises under Section 303 BNS."]


def test_supported_claim():
    assert verify_claim("The accused was arrested on 14 March 2026.", EV).status == "SUPPORTED"


def test_partially_supported_claim():
    v = verify_claim("The accused was arrested on 14 March 2026 after a dawn raid by a special task force.", EV)
    assert v.status == "PARTIALLY_SUPPORTED"


def test_unsupported_claim():
    assert verify_claim("The complainant paid Rs. 50,000 to a broker for the flat.", EV).status == "UNSUPPORTED"


@pytest.mark.parametrize("claim", ["The accused was arrested on 12 March 2026.", "The FIR registers theft under Section 305 BNS."])
def test_contradicted_claim(claim):
    assert verify_claim(claim, EV).status == "CONTRADICTED"


def test_missing_evidence_is_unverified():
    assert verify_claim("The accused was arrested on 14 March 2026.", []).status == "UNVERIFIED"


def test_fabricated_citation_is_unverified():
    v = verify_claim("Bail is the rule.", EV, citations=["(2031) 9 SCC 999"], citation_exists=corpus_citation_exists)
    assert v.status == "UNVERIFIED" and "not found" in v.reason


def test_wrong_citation_is_unverified():
    # Real-looking section number that is not in the trusted corpus.
    v = verify_claim("Punishment for theft.", EV, citations=["Section 999 IPC"], citation_exists=corpus_citation_exists)
    assert v.status == "UNVERIFIED"


def test_real_citation_passes_citation_check():
    assert corpus_citation_exists("Section 302 IPC")
    assert corpus_citation_exists("Lalita Kumari v. Government of U.P. (2014) 2 SCC 1")
