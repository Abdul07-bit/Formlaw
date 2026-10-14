"""Structured (JSON) logging with redaction of sensitive field names.

Callers pass safe metadata (ids, counts, hashes). As a second line of defence,
fields whose names suggest sensitive content are redacted by the formatter.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

REDACTED_KEYS = frozenset(
    {
        "document_text",
        "document",
        "prompt",
        "system_prompt",
        "user_prompt",
        "request_text",
        "raw_output",
        "api_key",
        "authorization",
        "password",
        "token",
        "secret",
    }
)
_HANDLER_MARK = "_formlaw_json_handler"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields: dict[str, Any] = getattr(record, "fields", {})
        for key, value in fields.items():
            payload[key] = "[REDACTED]" if key.lower() in REDACTED_KEYS else value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__  # type only, no message
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if any(getattr(h, _HANDLER_MARK, False) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_MARK, True)
    root.addHandler(handler)


def log_event(
    logger: logging.Logger, event: str, *, level: int = logging.INFO, **fields: Any
) -> None:
    logger.log(level, event, extra={"fields": fields})
