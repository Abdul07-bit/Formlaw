"""missing_information.basis: widen to 30 and constrain

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-13

The agents write 'referenced_in_documents' (23 chars) into a VARCHAR(20). SQLite ignores declared lengths, so this was
invisible in development; PostgreSQL rejected the insert and every case review that found a missing record crashed.
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_BASES = "'referenced_in_documents','checklist','conflict_resolution','template_field','timeline_gap'"


def upgrade() -> None:
    with op.batch_alter_table("missing_information", recreate="auto") as b:
        b.alter_column("basis", existing_type=sa.String(length=20), type_=sa.String(length=30), existing_nullable=False)
        b.create_check_constraint("ck_missing_basis", f"basis IN ({_BASES})")


def downgrade() -> None:
    with op.batch_alter_table("missing_information", recreate="auto") as b:
        b.drop_constraint("ck_missing_basis", type_="check")
        b.alter_column("basis", existing_type=sa.String(length=30), type_=sa.String(length=20), existing_nullable=False)
