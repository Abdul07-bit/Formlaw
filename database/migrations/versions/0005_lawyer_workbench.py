"""lawyer-first workbench schema (v2)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09

Replaces the v1 client-first application tables (cases owned by clients, per-run review tables, lawyer ratings)
with the lawyer-first workbench schema: organizations + memberships, case members, a persisted per-case chunk
index, agent runs / steps / tool calls, lawyer-reviewable case knowledge, intake and matching.

The legal corpus (legal_sources, legal_documents, legal_chunks, constitution_provisions, embeddings,
ingestion_runs) is NOT touched. v1 application rows were demo/test data and are dropped; back up first if needed.
Irreversible: downgrade raises.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# v1 application tables, children before parents.
V1_TABLES = [
    "related_cases", "lawyer_matches", "citations", "contradictions", "missing_information", "claims", "evidence",
    "analysis_runs", "messages", "connections", "approval_requests", "security_events", "audit_logs", "documents",
    "kyc_verifications", "lawyer_cases", "lawyer_expertise", "cases", "lawyers", "refresh_tokens", "users", "organizations",
]
EMBEDDING_DIM = 768  # must match the configured embedding model (see migration 0002)


def _drop_v1() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
    for t in V1_TABLES:
        if t in existing:
            op.drop_table(t)
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON")


def _postgres_search() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE chunk_embeddings ADD COLUMN IF NOT EXISTS vector_pg vector({EMBEDDING_DIM})")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chunk_embeddings_vector_pg ON chunk_embeddings USING hnsw (vector_pg vector_cosine_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_chunks_fts ON document_chunks USING gin (to_tsvector('english', text))")


def upgrade() -> None:
    _drop_v1()
    op.create_table('audit_logs',
    sa.Column('organization_id', sa.String(length=36), nullable=True),
    sa.Column('case_id', sa.String(length=36), nullable=True),
    sa.Column('task_id', sa.String(length=24), nullable=True),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('actor_role', sa.String(length=10), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('resource_type', sa.String(length=30), nullable=True),
    sa.Column('resource_id', sa.String(length=36), nullable=True),
    sa.Column('risk_level', sa.String(length=6), nullable=False),
    sa.Column('result', sa.String(length=12), nullable=False),
    sa.Column('agent', sa.String(length=40), nullable=True),
    sa.Column('tool', sa.String(length=40), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('verification_status', sa.String(length=40), nullable=True),
    sa.Column('security_event_id', sa.String(length=36), nullable=True),
    sa.Column('ip_hash', sa.String(length=16), nullable=True),
    sa.Column('detail', sa.String(length=300), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("risk_level IN ('LOW','MEDIUM','HIGH')", name='ck_audit_risk'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_task_id'), ['task_id'], unique=False)

    op.create_table('organizations',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('plan', sa.String(length=20), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("type IN ('individual','law_firm','legal_department','platform')", name='ck_org_type'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.Column('failed_logins', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('lawyer','client','admin')", name='ck_user_role'),
    sa.CheckConstraint("status IN ('active','locked','disabled')", name='ck_user_status'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_organization_id'), ['organization_id'], unique=False)

    op.create_table('approvals',
    sa.Column('organization_id', sa.String(length=36), nullable=True),
    sa.Column('case_id', sa.String(length=36), nullable=True),
    sa.Column('requester_id', sa.String(length=36), nullable=False),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('risk_level', sa.String(length=6), nullable=False),
    sa.Column('resource_type', sa.String(length=30), nullable=False),
    sa.Column('resource_id', sa.String(length=36), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('summary', sa.String(length=400), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('decided_by', sa.String(length=36), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('result', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('pending','approved','rejected','executed','expired','failed')", name='ck_approval_status'),
    sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('approvals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_approvals_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_approvals_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_approvals_requester_id'), ['requester_id'], unique=False)

    op.create_table('cases',
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('reference', sa.String(length=40), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('matter_type', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('jurisdiction', sa.String(length=120), nullable=False),
    sa.Column('court', sa.String(length=160), nullable=False),
    sa.Column('client_name', sa.String(length=120), nullable=False),
    sa.Column('intake_id', sa.String(length=36), nullable=True),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("matter_type IN ('criminal','civil','contract','property','family','employment','corporate','consumer','cyber','constitutional','other')", name='ck_case_matter_type'),
    sa.CheckConstraint("status IN ('intake','active','on_hold','closed','archived')", name='ck_case_status'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cases_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cases_reference'), ['reference'], unique=False)

    op.create_table('intakes',
    sa.Column('client_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('answers', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('structured', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('matter_type', sa.String(length=20), nullable=True),
    sa.Column('jurisdiction', sa.String(length=120), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=False),
    sa.Column('urgency', sa.String(length=10), nullable=False),
    sa.Column('language', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('security_flags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('draft','submitted','matched','connected','closed')", name='ck_intake_status'),
    sa.ForeignKeyConstraint(['client_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('intakes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_intakes_client_id'), ['client_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_intakes_organization_id'), ['organization_id'], unique=False)

    op.create_table('lawyers',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('headline', sa.String(length=160), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=False),
    sa.Column('state', sa.String(length=80), nullable=False),
    sa.Column('jurisdictions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('bar_council', sa.String(length=120), nullable=False),
    sa.Column('enrolment_number', sa.String(length=60), nullable=False),
    sa.Column('experience_years', sa.Integer(), nullable=False),
    sa.Column('languages', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('education', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('qualifications', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('bio', sa.Text(), nullable=False),
    sa.Column('accepting_clients', sa.Boolean(), nullable=False),
    sa.Column('consultation_fee', sa.Integer(), nullable=True),
    sa.Column('verification_status', sa.String(length=14), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verification_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('judicial_status_verified', sa.Boolean(), nullable=False),
    sa.Column('profile_status', sa.String(length=10), nullable=False),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("profile_status IN ('draft','published','suspended')", name='ck_lawyer_profile'),
    sa.CheckConstraint("verification_status IN ('NOT_STARTED','PENDING','UNDER_REVIEW','VERIFIED','REJECTED','EXPIRED')", name='ck_lawyer_verification'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('memberships',
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('owner','admin','member')", name='ck_membership_role'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'user_id', name='uq_membership')
    )
    with op.batch_alter_table('memberships', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_memberships_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_memberships_user_id'), ['user_id'], unique=False)

    op.create_table('notifications',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('link', sa.String(length=200), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)

    op.create_table('refresh_tokens',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('family_id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('replaced_by', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_refresh_tokens_family_id'), ['family_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_refresh_tokens_user_id'), ['user_id'], unique=False)

    op.create_table('agent_runs',
    sa.Column('task_id', sa.String(length=24), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('thread_id', sa.String(length=36), nullable=True),
    sa.Column('goal', sa.Text(), nullable=False),
    sa.Column('intent', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('plan', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('result', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('engine', sa.String(length=60), nullable=False),
    sa.Column('steps', sa.Integer(), nullable=False),
    sa.Column('tool_calls', sa.Integer(), nullable=False),
    sa.Column('replans', sa.Integer(), nullable=False),
    sa.Column('tokens', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('error', sa.String(length=300), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('queued','running','completed','partial','refused','failed')", name='ck_run_status'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('agent_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agent_runs_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_agent_runs_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_agent_runs_task_id'), ['task_id'], unique=False)

    op.create_table('case_members',
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('added_by', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('lead','member','viewer','client')", name='ck_case_member_role'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'user_id', name='uq_case_member')
    )
    with op.batch_alter_table('case_members', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_case_members_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_case_members_user_id'), ['user_id'], unique=False)

    op.create_table('chat_threads',
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('chat_threads', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chat_threads_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_chat_threads_organization_id'), ['organization_id'], unique=False)

    op.create_table('claims',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('agent', sa.String(length=40), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('confidence', sa.String(length=6), nullable=False),
    sa.Column('reason', sa.String(length=400), nullable=False),
    sa.Column('review_status', sa.String(length=10), nullable=False),
    sa.Column('reviewed_by', sa.String(length=36), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_note', sa.String(length=500), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.CheckConstraint("confidence IN ('high','medium','low')", name='ck_claim_confidence'),
    sa.CheckConstraint("review_status IN ('unreviewed','accepted','rejected')", name='ck_claim_review'),
    sa.CheckConstraint("status IN ('SUPPORTED','PARTIALLY_SUPPORTED','UNSUPPORTED','CONTRADICTED','UNVERIFIED')", name='ck_claim_status'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'key', name='uq_claim_key')
    )
    with op.batch_alter_table('claims', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_claims_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_claims_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_claims_run_id'), ['run_id'], unique=False)

    op.create_table('client_updates',
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('author_id', sa.String(length=36), nullable=False),
    sa.Column('approval_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('client_updates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_client_updates_case_id'), ['case_id'], unique=False)

    op.create_table('connections',
    sa.Column('intake_id', sa.String(length=36), nullable=False),
    sa.Column('client_id', sa.String(length=36), nullable=False),
    sa.Column('lawyer_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('client_note', sa.String(length=1000), nullable=False),
    sa.Column('lawyer_note', sa.String(length=1000), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=True),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('requested','accepted','declined','withdrawn')", name='ck_connection_status'),
    sa.ForeignKeyConstraint(['client_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['intake_id'], ['intakes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lawyer_id'], ['lawyers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('intake_id', 'lawyer_id', name='uq_connection')
    )
    with op.batch_alter_table('connections', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_connections_client_id'), ['client_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_connections_intake_id'), ['intake_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_connections_lawyer_id'), ['lawyer_id'], unique=False)

    op.create_table('documents',
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('uploaded_by', sa.String(length=36), nullable=False),
    sa.Column('filename', sa.String(length=160), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.String(length=64), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('status_note', sa.String(length=300), nullable=True),
    sa.Column('doc_type', sa.String(length=40), nullable=False),
    sa.Column('pages', sa.Integer(), nullable=True),
    sa.Column('metadata', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('security_flags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('received','indexed','needs_ocr','failed')", name='ck_doc_status'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'content_hash', name='uq_doc_case_hash')
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_content_hash'), ['content_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_organization_id'), ['organization_id'], unique=False)

    op.create_table('drafts',
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('sections', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('approved_by', sa.String(length=36), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.CheckConstraint("status IN ('draft','approved','shared')", name='ck_draft_status'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('drafts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_drafts_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_drafts_organization_id'), ['organization_id'], unique=False)

    op.create_table('intake_documents',
    sa.Column('intake_id', sa.String(length=36), nullable=False),
    sa.Column('filename', sa.String(length=160), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['intake_id'], ['intakes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('intake_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_intake_documents_intake_id'), ['intake_id'], unique=False)

    op.create_table('lawyer_matches',
    sa.Column('intake_id', sa.String(length=36), nullable=False),
    sa.Column('lawyer_id', sa.String(length=36), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('reasons', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('considerations', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['intake_id'], ['intakes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lawyer_id'], ['lawyers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lawyer_matches', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lawyer_matches_intake_id'), ['intake_id'], unique=False)

    op.create_table('lawyer_practice_areas',
    sa.Column('lawyer_id', sa.String(length=36), nullable=False),
    sa.Column('area', sa.String(length=20), nullable=False),
    sa.Column('verified', sa.Boolean(), nullable=False),
    sa.CheckConstraint("area IN ('criminal','civil','contract','property','family','employment','corporate','consumer','cyber','constitutional','other')", name='ck_practice_area'),
    sa.ForeignKeyConstraint(['lawyer_id'], ['lawyers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('lawyer_id', 'area')
    )
    op.create_table('lawyer_verifications',
    sa.Column('lawyer_id', sa.String(length=36), nullable=False),
    sa.Column('submission_id', sa.String(length=36), nullable=False),
    sa.Column('verification_type', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=14), nullable=False),
    sa.Column('provider', sa.String(length=60), nullable=False),
    sa.Column('provider_reference', sa.String(length=120), nullable=True),
    sa.Column('result', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('document_key', sa.String(length=64), nullable=True),
    sa.Column('document_name', sa.String(length=160), nullable=True),
    sa.Column('reviewer_id', sa.String(length=36), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('note', sa.String(length=500), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('pending','passed','failed','manual_review')", name='ck_lv_status'),
    sa.CheckConstraint("verification_type IN ('government_id','bar_registration','qualification','face_match','judicial_status')", name='ck_lv_type'),
    sa.ForeignKeyConstraint(['lawyer_id'], ['lawyers.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lawyer_verifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lawyer_verifications_lawyer_id'), ['lawyer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lawyer_verifications_submission_id'), ['submission_id'], unique=False)

    op.create_table('legal_authorities',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('legal_document_id', sa.String(length=36), nullable=False),
    sa.Column('legal_chunk_id', sa.String(length=36), nullable=False),
    sa.Column('authority_type', sa.String(length=24), nullable=False),
    sa.Column('title', sa.String(length=400), nullable=False),
    sa.Column('citation', sa.String(length=200), nullable=True),
    sa.Column('court', sa.String(length=200), nullable=True),
    sa.Column('decision_date', sa.Date(), nullable=True),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('quote', sa.Text(), nullable=False),
    sa.Column('issue', sa.String(length=300), nullable=False),
    sa.Column('source_name', sa.String(length=200), nullable=False),
    sa.Column('source_url', sa.String(length=500), nullable=True),
    sa.Column('license', sa.String(length=200), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('review_status', sa.String(length=10), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['legal_chunk_id'], ['legal_chunks.id'], ),
    sa.ForeignKeyConstraint(['legal_document_id'], ['legal_documents.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'key', name='uq_authority_key')
    )
    with op.batch_alter_table('legal_authorities', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_legal_authorities_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_legal_authorities_organization_id'), ['organization_id'], unique=False)

    op.create_table('memory_items',
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=True),
    sa.Column('scope', sa.String(length=10), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('content', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('provenance', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('validated', sa.Boolean(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("scope IN ('case','episodic','semantic','security')", name='ck_memory_scope'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('memory_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_memory_items_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_memory_items_key'), ['key'], unique=False)
        batch_op.create_index(batch_op.f('ix_memory_items_organization_id'), ['organization_id'], unique=False)

    op.create_table('messages',
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('sender_id', sa.String(length=36), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_messages_case_id'), ['case_id'], unique=False)

    op.create_table('saved_findings',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=240), nullable=False),
    sa.Column('content', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('message_id', sa.String(length=36), nullable=True),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('saved_findings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_saved_findings_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_saved_findings_organization_id'), ['organization_id'], unique=False)

    op.create_table('tasks',
    sa.Column('title', sa.String(length=240), nullable=False),
    sa.Column('status', sa.String(length=6), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('assignee_id', sa.String(length=36), nullable=True),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.CheckConstraint("status IN ('open','done')", name='ck_task_status'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tasks_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_organization_id'), ['organization_id'], unique=False)

    op.create_table('agent_steps',
    sa.Column('run_id', sa.String(length=36), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('t_ms', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=24), nullable=False),
    sa.Column('agent', sa.String(length=40), nullable=True),
    sa.Column('step_id', sa.String(length=12), nullable=True),
    sa.Column('summary', sa.String(length=400), nullable=False),
    sa.Column('data', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('agent_steps', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agent_steps_run_id'), ['run_id'], unique=False)

    op.create_table('chat_messages',
    sa.Column('thread_id', sa.String(length=36), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('author_id', sa.String(length=36), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('result', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('user','assistant')", name='ck_message_role'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chat_messages_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_chat_messages_run_id'), ['run_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_chat_messages_thread_id'), ['thread_id'], unique=False)

    op.create_table('document_chunks',
    sa.Column('document_id', sa.String(length=36), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=160), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('char_start', sa.Integer(), nullable=False),
    sa.Column('char_end', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('security_flags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'ordinal', name='uq_chunk_ordinal')
    )
    with op.batch_alter_table('document_chunks', schema=None) as batch_op:
        batch_op.create_index('ix_chunks_org_case', ['organization_id', 'case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_chunks_document_id'), ['document_id'], unique=False)

    op.create_table('security_events',
    sa.Column('organization_id', sa.String(length=36), nullable=True),
    sa.Column('case_id', sa.String(length=36), nullable=True),
    sa.Column('document_id', sa.String(length=36), nullable=True),
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('source', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('risk', sa.String(length=6), nullable=False),
    sa.Column('snippet', sa.String(length=240), nullable=False),
    sa.Column('actions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("risk IN ('LOW','MEDIUM','HIGH')", name='ck_security_risk'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('security_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_security_events_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_security_events_organization_id'), ['organization_id'], unique=False)

    op.create_table('tool_calls',
    sa.Column('run_id', sa.String(length=36), nullable=False),
    sa.Column('step_id', sa.String(length=12), nullable=True),
    sa.Column('agent', sa.String(length=40), nullable=False),
    sa.Column('tool', sa.String(length=40), nullable=False),
    sa.Column('risk', sa.String(length=6), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('tokens', sa.Integer(), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=True),
    sa.Column('error', sa.String(length=200), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("risk IN ('LOW','MEDIUM','HIGH')", name='ck_tool_risk'),
    sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tool_calls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tool_calls_run_id'), ['run_id'], unique=False)

    op.create_table('chunk_embeddings',
    sa.Column('chunk_id', sa.String(length=36), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('dim', sa.Integer(), nullable=False),
    sa.Column('vector', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('chunk_id', 'model')
    )
    with op.batch_alter_table('chunk_embeddings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chunk_embeddings_case_id'), ['case_id'], unique=False)

    op.create_table('evidence',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('document_id', sa.String(length=36), nullable=False),
    sa.Column('chunk_id', sa.String(length=36), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=160), nullable=True),
    sa.Column('quote', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('source_type', sa.String(length=20), nullable=False),
    sa.Column('first_run_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'key', name='uq_evidence_key')
    )
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evidence_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_evidence_organization_id'), ['organization_id'], unique=False)

    op.create_table('citations',
    sa.Column('claim_id', sa.String(length=36), nullable=False),
    sa.Column('evidence_id', sa.String(length=36), nullable=True),
    sa.Column('authority_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.CheckConstraint('(evidence_id IS NOT NULL) OR (authority_id IS NOT NULL)', name='ck_citation_target'),
    sa.ForeignKeyConstraint(['authority_id'], ['legal_authorities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('citations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_citations_claim_id'), ['claim_id'], unique=False)

    op.create_table('contradictions',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('topic', sa.String(length=160), nullable=False),
    sa.Column('statement_a', sa.Text(), nullable=False),
    sa.Column('statement_b', sa.Text(), nullable=False),
    sa.Column('evidence_a_id', sa.String(length=36), nullable=False),
    sa.Column('evidence_b_id', sa.String(length=36), nullable=False),
    sa.Column('nature', sa.String(length=30), nullable=False),
    sa.Column('confidence', sa.String(length=6), nullable=False),
    sa.Column('provenance', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('resolution_note', sa.String(length=500), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.CheckConstraint("status IN ('open','resolved','dismissed')", name='ck_contradiction_status'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evidence_a_id'], ['evidence.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evidence_b_id'], ['evidence.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'key', name='uq_contradiction_key')
    )
    with op.batch_alter_table('contradictions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contradictions_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_contradictions_organization_id'), ['organization_id'], unique=False)

    op.create_table('missing_information',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('why_needed', sa.Text(), nullable=False),
    sa.Column('basis', sa.String(length=20), nullable=False),
    sa.Column('evidence_id', sa.String(length=36), nullable=True),
    sa.Column('importance', sa.String(length=6), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.CheckConstraint("status IN ('open','requested','resolved','dismissed')", name='ck_missing_status'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'key', name='uq_missing_key')
    )
    with op.batch_alter_table('missing_information', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_missing_information_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_missing_information_organization_id'), ['organization_id'], unique=False)

    op.create_table('timeline_events',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=36), nullable=True),
    sa.Column('event_date', sa.Date(), nullable=True),
    sa.Column('date_text', sa.String(length=60), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('event_type', sa.String(length=40), nullable=False),
    sa.Column('evidence_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('case_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'key', name='uq_timeline_key')
    )
    with op.batch_alter_table('timeline_events', schema=None) as batch_op:
        batch_op.create_index('ix_timeline_case_date', ['case_id', 'event_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_timeline_events_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_timeline_events_organization_id'), ['organization_id'], unique=False)
    _postgres_search()


def downgrade() -> None:
    raise RuntimeError("0005 replaces the v1 application schema and cannot be downgraded. Restore a backup instead.")
