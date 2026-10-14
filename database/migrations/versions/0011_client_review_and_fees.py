"""client document review, client budget, advocate fee range

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-13

* intakes.budget_max, intakes.review, intakes.reviewed_at — the client's stated budget and the automated review of
  their own uploaded files (organised facts, not legal advice).
* lawyers.fee_range_min / fee_range_max — self-declared typical fees; displayed only when the ConnectionPolicy shows fees.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("intakes", recreate="auto") as b:
        b.add_column(sa.Column("budget_max", sa.Integer(), nullable=True))
        b.add_column(sa.Column("review", _JSON, nullable=True))
        b.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("lawyers", recreate="auto") as b:
        b.add_column(sa.Column("fee_range_min", sa.Integer(), nullable=True))
        b.add_column(sa.Column("fee_range_max", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lawyers", recreate="auto") as b:
        b.drop_column("fee_range_max")
        b.drop_column("fee_range_min")
    with op.batch_alter_table("intakes", recreate="auto") as b:
        b.drop_column("reviewed_at")
        b.drop_column("review")
        b.drop_column("budget_max")
