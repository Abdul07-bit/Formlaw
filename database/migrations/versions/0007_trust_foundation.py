"""trust foundation: connection policy gate, consents, verification history, SUSPENDED, no biometric checks

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-13

* connection_policies — versioned compliance decisions that gate advocate discovery / matching / client requests.
  No row = every connection feature off.
* consents — what a client agreed to share, with whom, under which exact disclosures.
* verification_events — append-only history of advocate verification status changes.
* lawyers.verification_status gains SUSPENDED.
* face_match verification checks are removed: biometrics are not collected without a lawful basis and specialist legal
  review. Existing face_match rows held only a provider outcome (never an image) and are deleted.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_STATUSES_OLD = "'NOT_STARTED','PENDING','UNDER_REVIEW','VERIFIED','REJECTED','EXPIRED'"
_STATUSES_NEW = _STATUSES_OLD + ",'SUSPENDED'"
_TYPES_OLD = "'government_id','bar_registration','qualification','face_match','judicial_status'"
_TYPES_NEW = "'government_id','bar_registration','qualification','judicial_status'"
_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "connection_policies",
        sa.Column("jurisdiction", sa.String(length=8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("public_discovery_enabled", sa.Boolean(), nullable=False),
        sa.Column("matching_enabled", sa.Boolean(), nullable=False),
        sa.Column("client_requests_enabled", sa.Boolean(), nullable=False),
        sa.Column("show_fees", sa.Boolean(), nullable=False),
        sa.Column("visible_profile_fields", _JSON, nullable=False),
        sa.Column("required_disclosures", _JSON, nullable=False),
        sa.Column("professional_rules", _JSON, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=12), nullable=False),
        sa.Column("review_reference", sa.String(length=200), nullable=True),
        sa.Column("review_note", sa.String(length=1000), nullable=True),
        sa.Column("drafted_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("review_status IN ('DRAFT','APPROVED','REJECTED','SUPERSEDED','REVOKED','DEMO_ONLY')",
                           name="ck_connection_policy_status"),
        sa.ForeignKeyConstraint(["drafted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jurisdiction", "version", name="uq_connection_policy_version"),
    )
    op.create_table(
        "consents",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=60), nullable=False),
        sa.Column("subject_type", sa.String(length=30), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("recipient_type", sa.String(length=30), nullable=False),
        sa.Column("recipient_id", sa.String(length=36), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=True),
        sa.Column("disclosures", _JSON, nullable=False),
        sa.Column("disclosure_hash", sa.String(length=64), nullable=False),
        sa.Column("approval_id", sa.String(length=36), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["connection_policies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consents_user_id", "consents", ["user_id"])
    op.create_index("ix_consents_subject_id", "consents", ["subject_id"])
    op.create_table(
        "verification_events",
        sa.Column("lawyer_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=14), nullable=False),
        sa.Column("to_status", sa.String(length=14), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("actor_role", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["lawyer_id"], ["lawyers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verification_events_lawyer_id", "verification_events", ["lawyer_id"])

    op.execute("DELETE FROM lawyer_verifications WHERE verification_type = 'face_match'")
    with op.batch_alter_table("lawyer_verifications", recreate="auto") as b:
        b.drop_constraint("ck_lv_type", type_="check")
        b.create_check_constraint("ck_lv_type", f"verification_type IN ({_TYPES_NEW})")
    with op.batch_alter_table("lawyers", recreate="auto") as b:
        b.drop_constraint("ck_lawyer_verification", type_="check")
        b.create_check_constraint("ck_lawyer_verification", f"verification_status IN ({_STATUSES_NEW})")


def downgrade() -> None:
    # SUSPENDED has no equivalent in 0006; EXPIRED is the closest state that keeps the profile unpublished.
    op.execute("UPDATE lawyers SET verification_status = 'EXPIRED', profile_status = 'draft' WHERE verification_status = 'SUSPENDED'")
    with op.batch_alter_table("lawyers", recreate="auto") as b:
        b.drop_constraint("ck_lawyer_verification", type_="check")
        b.create_check_constraint("ck_lawyer_verification", f"verification_status IN ({_STATUSES_OLD})")
    with op.batch_alter_table("lawyer_verifications", recreate="auto") as b:
        b.drop_constraint("ck_lv_type", type_="check")
        b.create_check_constraint("ck_lv_type", f"verification_type IN ({_TYPES_OLD})")
    op.drop_index("ix_verification_events_lawyer_id", table_name="verification_events")
    op.drop_table("verification_events")
    op.drop_index("ix_consents_subject_id", table_name="consents")
    op.drop_index("ix_consents_user_id", table_name="consents")
    op.drop_table("consents")
    op.drop_table("connection_policies")
