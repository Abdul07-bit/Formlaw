"""Logging with PII/secret redaction applied to every record."""
from __future__ import annotations

import logging
import re

_RULES = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b"), "[phone]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[aadhaar]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[pan]"),
    (re.compile(r"(?i)(bearer\s+)[\w.-]+"), r"\1[token]"),
    (re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[=:]\s*)\S+"), r"\1[redacted]"),
]


def redact(text: str) -> str:
    for rx, repl in _RULES:
        text = rx.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in (record.args if isinstance(record.args, tuple) else (record.args,)))
        return True


def configure() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger("formlaw")
    if not root.handlers:
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
