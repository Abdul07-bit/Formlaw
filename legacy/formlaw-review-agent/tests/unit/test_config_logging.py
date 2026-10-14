import json
import logging

from pydantic import SecretStr

from app.config import Settings
from app.logging import JsonFormatter, log_event


def test_secret_is_not_rendered() -> None:
    s = Settings(_env_file=None, llm_api_key=SecretStr("sk-abc"), llm_model="m")  # type: ignore[call-arg]
    assert "sk-abc" not in repr(s) and "sk-abc" not in str(s)
    assert s.llm_configured is True


def test_defaults_are_safe() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.max_document_chars > 0 and s.max_retries >= 0
    assert s.llm_configured is False


def test_json_formatter_redacts_sensitive_field_names() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "evt", None, None)
    record.fields = {"task_id": "abc", "document_text": "LEGAL TEXT", "api_key": "sk-1", "prompt": "P"}
    out = json.loads(JsonFormatter().format(record))
    assert out["task_id"] == "abc" and out["event"] == "evt"
    assert out["document_text"] == out["api_key"] == out["prompt"] == "[REDACTED]"


def test_log_event_attaches_fields(caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO)
    log_event(logging.getLogger("x"), "hello", task_id="t1")
    assert caplog.records[0].fields == {"task_id": "t1"}  # type: ignore[attr-defined]
