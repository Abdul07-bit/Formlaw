"""
EMBEDDING + INDEXING for searchable legal chunks.

    python -m app.ingestion.index                 embed chunks that have no embedding yet
    python -m app.ingestion.index --limit 2000

Keyword index: maintained automatically (SQLite FTS5 triggers / PostgreSQL GIN tsvector).
Vector index: embeddings table (+ pgvector column on PostgreSQL). Requires an embedding provider
(LLM_PROVIDER=gemini with GEMINI_API_KEY); without one, retrieval is keyword-only.
"""
from __future__ import annotations

import argparse
import json
import time

import app  # noqa: F401
from sqlalchemy import select, text

from ..llm.providers import LLMError, get_embedder
from ..db.base import new_id
from ..db.session import engine, session_factory
from ..models import Embedding, LegalChunk, LegalDocument
from ..retrieval.legal_corpus import ensure_keyword_index, pg_vector_dim


def run(limit: int = 0, batch: int = 50, pause: float = 0.0) -> dict[str, int]:
    ensure_keyword_index()
    embedder = get_embedder()
    if embedder is None:
        return {"embedded": 0, "skipped": -1}
    done = 0
    with session_factory()() as db:
        q = (select(LegalChunk).join(LegalDocument).where(LegalDocument.quality_status == "passed")
             .where(~select(Embedding.id).where(Embedding.owner_type == "legal_chunk", Embedding.owner_id == LegalChunk.id,
                                                Embedding.model == embedder.model).exists()))
        chunks = list(db.scalars(q.limit(limit) if limit else q))
        pg_dim = pg_vector_dim(db, "embeddings") if engine().dialect.name == "postgresql" else None
        for i in range(0, len(chunks), batch):
            part = chunks[i:i + batch]
            for attempt in range(32):  # up to ~30 minutes per batch
                try:
                    vecs = embedder.embed([c.text for c in part], task="document")
                    break
                except LLMError as e:
                    # Free-tier quotas / overload: wait it out (15s, 30s, then 60s steps) instead of failing.
                    print(f"  waiting: {e}", flush=True)
                    time.sleep(min(60, 15 * 2 ** attempt))
            else:
                raise SystemExit("embedding provider unavailable; re-run later (progress is kept)")
            for c, v in zip(part, vecs):
                e = Embedding(id=new_id(), owner_type="legal_chunk", owner_id=c.id, model=embedder.model, dim=len(v), vector=v)
                db.add(e)
                c.embedding_id = e.id
                # pgvector columns have a fixed dimension; other models stay in JSON and use in-process search.
                if pg_dim and len(v) == pg_dim:
                    db.flush()
                    db.execute(text("UPDATE embeddings SET vector_pg = CAST(:v AS vector) WHERE id = :id"), {"v": json.dumps(v), "id": e.id})
            db.commit()
            done += len(part)
            print(f"  embedded {done}/{len(chunks)}", flush=True)
            if pause:
                time.sleep(pause)
    return {"embedded": done, "skipped": 0}


def main() -> None:
    ap = argparse.ArgumentParser(description="Embed and index legal chunks")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--pause", type=float, default=0.0, help="Seconds between batches (stay under per-minute quotas)")
    a = ap.parse_args()
    r = run(a.limit, a.batch, a.pause)
    print("No embedding provider configured: keyword index only." if r["skipped"] == -1 else r)


if __name__ == "__main__":
    main()
