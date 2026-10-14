"""constitution: allow the Preamble as a provision kind

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("constitution_provisions", schema=None) as batch_op:
        batch_op.drop_constraint("ck_constitution_kind", type_="check")
        batch_op.create_check_constraint("ck_constitution_kind", "kind IN ('preamble','part','chapter','article','clause','schedule','amendment')")


def downgrade() -> None:
    op.execute("DELETE FROM constitution_provisions WHERE kind = 'preamble'")
    with op.batch_alter_table("constitution_provisions", schema=None) as batch_op:
        batch_op.drop_constraint("ck_constitution_kind", type_="check")
        batch_op.create_check_constraint("ck_constitution_kind", "kind IN ('part','chapter','article','clause','schedule','amendment')")
