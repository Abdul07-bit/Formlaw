"""Deterministic handling of untrusted document content.

Two jobs:
  1. neutralize_delimiters: stop document text from forging/closing our prompt delimiters.
  2. scan_document: flag likely injection attempts for observability. Flags never
     contain document text, and they never change what the agent is permitted to do -
     the agent has no tools, so there is nothing privileged for an injection to reach.
"""

import re

from app.agents.review.schemas import SecurityFlag

_DELIMITERS = "TRUSTED_SYSTEM_INSTRUCTIONS|UNTRUSTED_DOCUMENT|USER_REQUEST|VALIDATION_FEEDBACK"
_DELIMITER_RE = re.compile(rf"<\s*(/?)\s*({_DELIMITERS})\b", re.IGNORECASE)

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)", re.I),
    re.compile(r"reveal\s+(?:your\s+|the\s+)?(?:system\s+)?prompt", re.I),
    re.compile(r"(?:call|invoke|use)\s+(?:an?\s+|the\s+)?(?:external|admin)\s+(?:api|tool)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an|the)\b", re.I),
    re.compile(r"reveal\s+all\s+case\s+data", re.I),
]


def neutralize_delimiters(text: str) -> str:
    """Rewrite '<TAG' / '</TAG' for our delimiter names so they no longer parse as tags."""
    return _DELIMITER_RE.sub(lambda m: f"&lt;{m.group(1)}{m.group(2)}", text)


def scan_document(text: str) -> list[SecurityFlag]:
    flags: list[SecurityFlag] = []
    if any(p.search(text) for p in _INJECTION_PATTERNS):
        flags.append(
            SecurityFlag(
                type="PROMPT_INJECTION",
                severity="HIGH",
                description=(
                    "Document contains text that attempts to instruct or control the AI. "
                    "It was treated as untrusted document content."
                ),
            )
        )
    if _DELIMITER_RE.search(text):
        flags.append(
            SecurityFlag(
                type="DELIMITER_SPOOFING",
                severity="MEDIUM",
                description=(
                    "Document contains text resembling the system's prompt delimiters. "
                    "It was neutralized before being sent to the model."
                ),
            )
        )
    return flags
