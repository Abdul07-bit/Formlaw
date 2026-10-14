"""legal source registry and provenance

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08 23:21:10.603470
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old pipeline used 'failed'; quarantined documents are never served.
    op.execute("UPDATE legal_documents SET quality_status = 'quarantined' WHERE quality_status = 'failed'")
    with op.batch_alter_table('legal_documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quarantine_reason', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('external_id', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('document_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('license_ref', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('neutral_citation', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('cnr', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('judges', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
        batch_op.add_column(sa.Column('disposal', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('case_type', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('page_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('data_class', sa.String(length=16), nullable=False, server_default='VERIFIED_SOURCE'))
        batch_op.create_index(batch_op.f('ix_legal_documents_data_class'), ['data_class'], unique=False)
        batch_op.create_index(batch_op.f('ix_legal_documents_external_id'), ['external_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_legal_documents_neutral_citation'), ['neutral_citation'], unique=False)
        batch_op.create_unique_constraint('uq_legal_doc_source_external', ['source_id', 'external_id'])
        batch_op.create_check_constraint('ck_legal_doc_data_class', "data_class IN ('VERIFIED_SOURCE','SYNTHETIC')")
        batch_op.create_check_constraint('ck_legal_doc_quality', "quality_status IN ('pending','passed','quarantined')")

    with op.batch_alter_table('legal_sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_type', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('jurisdiction', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('terms_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('coverage_start', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('coverage_end', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('access_method', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('allowed_usage', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('restrictions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('attribution', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('commercial_use_allowed', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('redistribution_allowed', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('api_available', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('verification_status', sa.String(length=16), nullable=False, server_default='REVIEW_REQUIRED'))
        batch_op.add_column(sa.Column('decision_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('last_checked', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    if op.get_bind().dialect.name == "sqlite":
        # Keyword index for legal retrieval (PostgreSQL uses the GIN tsvector index from 0002).
        op.execute("CREATE VIRTUAL TABLE IF NOT EXISTS legal_chunks_fts USING fts5(text, content='legal_chunks', content_rowid='rowid')")
        op.execute("INSERT INTO legal_chunks_fts(legal_chunks_fts) VALUES ('rebuild')")
        op.execute("CREATE TRIGGER IF NOT EXISTS legal_chunks_ai AFTER INSERT ON legal_chunks BEGIN "
                   "INSERT INTO legal_chunks_fts(rowid, text) VALUES (new.rowid, new.text); END")
        op.execute("CREATE TRIGGER IF NOT EXISTS legal_chunks_ad AFTER DELETE ON legal_chunks BEGIN "
                   "INSERT INTO legal_chunks_fts(legal_chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text); END")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS legal_chunks_ai")
        op.execute("DROP TRIGGER IF EXISTS legal_chunks_ad")
        op.execute("DROP TABLE IF EXISTS legal_chunks_fts")
    with op.batch_alter_table('legal_sources', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('last_checked')
        batch_op.drop_column('decision_reason')
        batch_op.drop_column('verification_status')
        batch_op.drop_column('api_available')
        batch_op.drop_column('redistribution_allowed')
        batch_op.drop_column('commercial_use_allowed')
        batch_op.drop_column('attribution')
        batch_op.drop_column('restrictions')
        batch_op.drop_column('allowed_usage')
        batch_op.drop_column('access_method')
        batch_op.drop_column('coverage_end')
        batch_op.drop_column('coverage_start')
        batch_op.drop_column('terms_url')
        batch_op.drop_column('jurisdiction')
        batch_op.drop_column('source_type')

    with op.batch_alter_table('legal_documents', schema=None) as batch_op:
        batch_op.drop_constraint('ck_legal_doc_quality', type_='check')
        batch_op.drop_constraint('ck_legal_doc_data_class', type_='check')
        batch_op.drop_constraint('uq_legal_doc_source_external', type_='unique')
        batch_op.drop_index(batch_op.f('ix_legal_documents_neutral_citation'))
        batch_op.drop_index(batch_op.f('ix_legal_documents_external_id'))
        batch_op.drop_index(batch_op.f('ix_legal_documents_data_class'))
        batch_op.drop_column('data_class')
        batch_op.drop_column('page_count')
        batch_op.drop_column('case_type')
        batch_op.drop_column('disposal')
        batch_op.drop_column('judges')
        batch_op.drop_column('cnr')
        batch_op.drop_column('neutral_citation')
        batch_op.drop_column('license_ref')
        batch_op.drop_column('retrieved_at')
        batch_op.drop_column('document_url')
        batch_op.drop_column('external_id')
        batch_op.drop_column('quarantine_reason')

