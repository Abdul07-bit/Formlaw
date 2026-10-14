from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_TMP = Path(tempfile.mkdtemp(prefix="formlaw-test-"))
# SQLite by default. Set FORMLAW_TEST_DATABASE_URL=postgresql+psycopg://... to run the whole suite on PostgreSQL + pgvector:
# the schema is then built once by the real migrations and tables are truncated between tests.
TEST_DB_URL = os.environ.get("FORMLAW_TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}"
IS_PG = TEST_DB_URL.startswith("postgresql")
os.environ.update({
    "FORMLAW_ENV": "test", "DEMO_MODE": "true", "JWT_SECRET": "test-secret-" + "x" * 32,
    "DATABASE_URL": TEST_DB_URL, "STORAGE_DIR": str(_TMP / "storage"),
    "LLM_PROVIDER": "none", "KYC_PROVIDER": "demo", "GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "",
    "FILE_ENCRYPTION_KEY": "", "RUN_AGENTS_INLINE": "true",
})
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "database" / "seeds"))

import app  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from fastapi.testclient import TestClient  # noqa: E402

from app.llm.providers import disable_embeddings, disable_llm  # noqa: E402
from app.retrieval import case_index  # noqa: E402
from app.retrieval import legal_corpus  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.security import rate_limit  # noqa: E402
from tests.helpers import Api  # noqa: E402


@pytest.fixture(scope="session")
def _pg_schema():
    if not IS_PG:
        yield
        return
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    engine = db_session.init_engine()
    with engine.begin() as c:  # start from an empty database every session
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "database" / "migrations"))
    command.upgrade(cfg, "head")
    yield


def _truncate_all(engine) -> None:
    from sqlalchemy import text
    with engine.begin() as c:
        names = [r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"))]
        c.execute(text(f"TRUNCATE {', '.join(names)} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def fresh_db(_pg_schema):
    engine = db_session.init_engine()
    if IS_PG:
        engine.dispose()
        _truncate_all(engine)
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    legal_corpus.reset_index_cache()
    case_index._cache.clear()
    rate_limit.reset()
    disable_llm()
    disable_embeddings()
    yield
    disable_llm()
    disable_embeddings()


@pytest.fixture
def seeded(fresh_db):
    import seed

    with db_session.session_factory()() as db:
        seed.seed_demo(db)
        seed.seed_sources(db)
        db.commit()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), base_url="http://localhost")


@pytest.fixture
def api(client) -> Api:
    return Api(client)
