"""mark blank forms / templates among existing case documents

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09

Data-only. New uploads are profiled at ingestion; this re-profiles documents indexed before template detection existed,
so a blank case form is no longer treated as case evidence. Sets documents.doc_type = 'template' and records the
unfilled fields in documents.metadata.templateFields. Downgrade restores doc_type 'document' for those rows.
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.ingestion.profile import is_template, template_fields  # pyright: ignore[reportMissingImports]

    conn = op.get_bind()
    docs = conn.execute(sa.text("SELECT id, metadata FROM documents WHERE status = 'indexed' AND doc_type <> 'template'")).fetchall()
    for doc_id, meta in docs:
        text = "\n".join(r[0] for r in conn.execute(
            sa.text("SELECT text FROM document_chunks WHERE document_id = :d ORDER BY ordinal"), {"d": doc_id}))
        if not is_template(text):
            continue
        meta = (json.loads(meta) if isinstance(meta, str) else meta) or {}
        meta.update({"templateFields": template_fields(text), "references": []})
        value = "CAST(:m AS JSONB)" if conn.dialect.name == "postgresql" else ":m"
        conn.execute(sa.text(f"UPDATE documents SET doc_type = 'template', metadata = {value} WHERE id = :d"),
                     {"m": json.dumps(meta), "d": doc_id})


def downgrade() -> None:
    op.execute("UPDATE documents SET doc_type = 'document' WHERE doc_type = 'template'")
