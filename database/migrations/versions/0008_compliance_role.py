"""compliance reviewer account type

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13

Adds 'compliance' to users.role. Compliance reviewers approve connection policies; they are created only with
`python -m app.manage create-staff` (never self-registered).
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", recreate="auto") as b:
        b.drop_constraint("ck_user_role", type_="check")
        b.create_check_constraint("ck_user_role", "role IN ('lawyer','client','admin','compliance')")


def downgrade() -> None:
    # Converting reviewers to another role could silently grant privileges; make the operator decide instead.
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM users WHERE role = 'compliance'")).scalar():
        raise RuntimeError("Compliance accounts exist: remove or re-role them explicitly before downgrading past 0008")
    with op.batch_alter_table("users", recreate="auto") as b:
        b.drop_constraint("ck_user_role", type_="check")
        b.create_check_constraint("ck_user_role", "role IN ('lawyer','client','admin')")
