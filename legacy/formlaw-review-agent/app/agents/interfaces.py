"""Placeholders for future agents/services. Intentionally not implemented in this milestone.

The Orchestrator will depend on these protocols, so implementations can be swapped in
without changing the Review Agent.
"""

from typing import Protocol
from uuid import UUID

from app.agents.review.schemas import Claim, EvidenceReference


class RetrievalService(Protocol):
    async def retrieve(
        self, query: str, *, organization_id: UUID, case_id: UUID, limit: int = 10
    ) -> list[EvidenceReference]: ...


class VerificationAgent(Protocol):
    async def verify(
        self, claims: list[Claim], evidence: list[EvidenceReference]
    ) -> list[Claim]:
        """Return claims with verification_status updated from PENDING."""
        ...
