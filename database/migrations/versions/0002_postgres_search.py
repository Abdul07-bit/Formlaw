"""PostgreSQL-only: pgvector embeddings + full-text search indexes for legal retrieval.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08

No-op on SQLite (development/tests), where retrieval falls back to in-process BM25.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768  # must match the configured embedding model


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS vector_pg vector({EMBEDDING_DIM})")
    op.execute("CREATE INDEX IF NOT EXISTS ix_embeddings_vector_pg ON embeddings USING hnsw (vector_pg vector_cosine_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_legal_chunks_fts ON legal_chunks USING gin (to_tsvector('english', text))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_constitution_fts ON constitution_provisions USING gin (to_tsvector('english', coalesce(text, '')))")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_constitution_fts")
    op.execute("DROP INDEX IF EXISTS ix_legal_chunks_fts")
    op.execute("DROP INDEX IF EXISTS ix_embeddings_vector_pg")
    op.execute("ALTER TABLE embeddings DROP COLUMN IF EXISTS vector_pg")
