"""
KYC provider interface. A real provider (government ID / DigiLocker, Bar Council roll, judicial status) implements
`KycProvider`; the platform depends only on this interface. There is deliberately no biometric (face-match) method:
collecting biometrics needs an established lawful basis, necessity and proportionality, and specialist legal review.

`DemoVerificationProvider` is the prototype stand-in. It performs NO real identity verification: it only
checks that files are structurally valid and labels every result `DEMO VERIFICATION PROVIDER`, with
status `manual_review`. A human admin still decides, and the UI shows that no real check ran.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from typing import Literal, Protocol

from ..core.config import get_settings

Status = Literal["passed", "failed", "manual_review"]


@dataclass(frozen=True)
class CheckResult:
    status: Status
    reference: str
    result: dict = field(default_factory=dict)


class KycProvider(Protocol):
    name: str

    def verify_government_id(self, *, id_type: str, document: bytes) -> CheckResult: ...
    def verify_qualification(self, *, document: bytes) -> CheckResult: ...
    def verify_professional_registration(self, *, bar_council: str, enrolment_no: str, name: str) -> CheckResult: ...
    def verify_judicial_status(self, *, name: str, court: str) -> CheckResult: ...


class DemoVerificationProvider:
    name = "DEMO VERIFICATION PROVIDER"
    _NOTE = "DEMO VERIFICATION PROVIDER — no real identity, qualification or Bar roll check was performed."

    def _ref(self) -> str:
        return f"DEMO-{secrets.token_hex(4).upper()}"

    def _result(self, **extra) -> dict:
        return {"demo": True, "message": self._NOTE, **extra}

    def verify_government_id(self, *, id_type, document):
        return CheckResult("manual_review", self._ref(), self._result(id_type=id_type, document_sha256=hashlib.sha256(document).hexdigest()))

    def verify_qualification(self, *, document):
        return CheckResult("manual_review", self._ref(), self._result(document_sha256=hashlib.sha256(document).hexdigest()))

    def verify_professional_registration(self, *, bar_council, enrolment_no, name):
        if not bar_council.strip() or not re.fullmatch(r"[A-Za-z0-9/\- ]{3,60}", enrolment_no or ""):
            return CheckResult("failed", self._ref(), self._result(reason="Bar Council and enrolment number are required"))
        return CheckResult("manual_review", self._ref(), self._result(bar_council=bar_council))

    def verify_judicial_status(self, *, name, court):
        return CheckResult("manual_review", self._ref(), self._result(court=court))


def get_kyc_provider() -> KycProvider:
    s = get_settings()
    if s.kyc_provider == "demo":
        return DemoVerificationProvider()
    raise RuntimeError(f"KYC provider '{s.kyc_provider}' is not installed. Implement KycProvider and register it here.")
