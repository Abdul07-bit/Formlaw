"""conflict checks + client-declared parties

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-13

* conflict_checks — one per client request; run before the advocate sees the matter summary.
* intakes.declared_parties — people/organisations the client named as involved (used only for conflict checks).
Existing requests get their check created on first access (services/conflicts.ensure), so none can skip it.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("intakes", recreate="auto") as b:
        b.add_column(sa.Column("declared_parties", _JSON, nullable=False, server_default=sa.text("'[]'")))
    op.create_table(
        "conflict_checks",
        sa.Column("connection_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("names_checked", _JSON, nullable=False),
        sa.Column("automated_hits", _JSON, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=1000), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('PENDING_REVIEW','CLEARED','CONFLICT')", name="ck_conflict_status"),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
    )
    op.create_index("ix_conflict_checks_organization_id", "conflict_checks", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_conflict_checks_organization_id", table_name="conflict_checks")
    op.drop_table("conflict_checks")
    with op.batch_alter_table("intakes", recreate="auto") as b:
        b.drop_column("declared_parties")
