"""Importing this package registers every table on Base.metadata (used by Alembic and tests)."""
from .case import Case, CaseMember, ChunkEmbedding, Document, DocumentChunk
from .client import ClientUpdate, Connection, Intake, IntakeDocument, LawyerMatch, Message
from .compliance import CONFLICT_STATUSES, POLICY_STATUSES, ConflictCheck, Consent, ConnectionPolicy
from .governance import Approval, AuditLog, MemoryItem, Notification, SecurityEvent
from .knowledge import (Citation, Claim, Contradiction, Draft, Evidence, LegalAuthority, MissingInformation, SavedFinding,
                        Task, TimelineEvent)
from .lawyer import VERIFICATION_TYPES, Lawyer, LawyerPracticeArea, LawyerVerificationCheck, VerificationEvent
from .legal import (AUTHORITY_KINDS, ConstitutionProvision, Embedding, IngestionRun, LegalChunk, LegalDocument,
                    LegalSource)
from .runtime import AgentRun, AgentStep, ChatMessage, ChatThread, ToolCall
from .user import Membership, Organization, RefreshToken, User

__all__ = [
    "Case", "CaseMember", "ChunkEmbedding", "Document", "DocumentChunk",
    "ClientUpdate", "Connection", "Intake", "IntakeDocument", "LawyerMatch", "Message",
    "CONFLICT_STATUSES", "POLICY_STATUSES", "ConflictCheck", "Consent", "ConnectionPolicy",
    "Approval", "AuditLog", "MemoryItem", "Notification", "SecurityEvent",
    "Citation", "Claim", "Contradiction", "Draft", "Evidence", "LegalAuthority", "MissingInformation", "SavedFinding",
    "Task", "TimelineEvent",
    "VERIFICATION_TYPES", "Lawyer", "LawyerPracticeArea", "LawyerVerificationCheck", "VerificationEvent",
    "AUTHORITY_KINDS", "ConstitutionProvision", "Embedding", "IngestionRun", "LegalChunk", "LegalDocument", "LegalSource",
    "AgentRun", "AgentStep", "ChatMessage", "ChatThread", "ToolCall",
    "Membership", "Organization", "RefreshToken", "User",
]
