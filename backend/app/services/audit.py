"""Audit trail + security events. Details are redacted and truncated; document content is never logged."""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy.orm import Session

from ..core.logging import redact
from ..models import AuditLog, SecurityEvent

log = logging.getLogger("formlaw.audit")


def ip_hash(ip: str | None) -> str | None:
    return hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None


def record(db: Session, *, action: str, result: str, actor=None, resource_type: str | None = None,
           resource_id: str | None = None, risk: str = "LOW", organization_id: str | None = None, case_id: str | None = None,
           task_id: str | None = None, agent: str | None = None, tool: str | None = None, latency_ms: int | None = None,
           verification_status: str | None = None, security_event_id: str | None = None, detail: str | None = None,
           ip: str | None = None) -> AuditLog:
    user = getattr(actor, "user", actor)  # accepts a Principal or a User
    entry = AuditLog(
        organization_id=organization_id, case_id=case_id, task_id=task_id, actor_id=getattr(user, "id", None),
        actor_role=getattr(user, "role", None), action=action, resource_type=resource_type, resource_id=resource_id,
        risk_level=risk, result=result, agent=agent, tool=tool, latency_ms=latency_ms,
        verification_status=verification_status, security_event_id=security_event_id,
        detail=redact(detail)[:300] if detail else None, ip_hash=ip_hash(ip),
    )
    db.add(entry)
    log.info("audit action=%s result=%s risk=%s resource=%s:%s", action, result, risk, resource_type, resource_id)
    return entry


def security_event(db: Session, *, kind: str, source: str, snippet: str, actions: list[str], risk: str = "HIGH",
                   organization_id: str | None = None, case_id: str | None = None, document_id: str | None = None,
                   run_id: str | None = None, actor_id: str | None = None) -> SecurityEvent:
    ev = SecurityEvent(kind=kind, source=source[:200], snippet=redact(snippet)[:240], actions=actions, risk=risk,
                       organization_id=organization_id, case_id=case_id, document_id=document_id, run_id=run_id, actor_id=actor_id)
    db.add(ev)
    db.flush()
    log.warning("security_event kind=%s risk=%s case=%s", kind, risk, case_id)
    return ev
