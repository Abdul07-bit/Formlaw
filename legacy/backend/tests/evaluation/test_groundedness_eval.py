"""
Small labelled evaluation set for the Verification Agent. Fails the build if accuracy drops, and
never tolerates a false SUPPORTED on a contradicted or fabricated claim (the costly error).
"""
from app.agents.legal_bridge import corpus_citation_exists
from app.verification.groundedness import verify_claim

E = {
    "fir": "FIR No. 0412/2026 registered at Sector 21, Dwarka. Offence: Theft from shop premises under Section 303 BNS.",
    "arrest": "The accused Arjun Kumar was arrested on 14 March 2026 at about 10:00 hrs.",
    "witness": "At about 21:15 I saw a man in a blue jacket near the shop. I could not see his face clearly.",
    "cash": "The complainant states that cash of Rs. 1,85,000 was taken from the locked counter drawer.",
}

CASES = [
    ("The FIR registers theft under Section 303 BNS.", ["fir"], [], "SUPPORTED"),
    ("Arjun Kumar was arrested on 14 March 2026.", ["arrest"], [], "SUPPORTED"),
    ("Cash of Rs. 1,85,000 was taken from the counter drawer.", ["cash"], [], "SUPPORTED"),
    ("The witness saw a man in a blue jacket near the shop.", ["witness"], [], "SUPPORTED"),
    ("Arjun Kumar was arrested on 14 March 2026 by the crime branch after a chase.", ["arrest"], [], "PARTIALLY_SUPPORTED"),
    ("The witness saw a man near the shop and later picked him out at a parade.", ["witness"], [], "PARTIALLY_SUPPORTED"),
    ("Arjun Kumar was arrested on 12 March 2026.", ["arrest"], [], "CONTRADICTED"),
    ("The FIR registers the offence under Section 305 BNS.", ["fir"], [], "CONTRADICTED"),
    ("The accused confessed to the crime before the magistrate.", ["arrest", "fir"], [], "UNSUPPORTED"),
    ("A sum of Rs. 5,00,000 was recovered from the accused's house.", ["witness"], [], "UNSUPPORTED"),
    ("Arjun Kumar was arrested on 14 March 2026.", [], [], "UNVERIFIED"),
    ("Theft is punishable.", ["fir"], ["(2030) 4 SCC 1"], "UNVERIFIED"),
]


def test_verification_accuracy():
    correct, dangerous = 0, []
    for claim, ev, cites, want in CASES:
        got = verify_claim(claim, [E[k] for k in ev], citations=cites, citation_exists=corpus_citation_exists).status
        correct += got == want
        if got == "SUPPORTED" and want in ("CONTRADICTED", "UNSUPPORTED", "UNVERIFIED"):
            dangerous.append((claim, got))
    assert not dangerous, f"false SUPPORTED verdicts: {dangerous}"
    assert correct / len(CASES) >= 0.9, f"accuracy {correct}/{len(CASES)}"
