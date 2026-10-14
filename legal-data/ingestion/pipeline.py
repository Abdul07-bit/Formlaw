"""
Backwards-compatible entry point. The pipeline lives in backend/app/ingestion; run it from backend/:

    python -m app.ingestion.discover_sources
    python -m app.ingestion.ingest --source local_import --manifest /path/manifest.jsonl
    python -m app.ingestion.validate
    python -m app.ingestion.index
    python -m app.ingestion.status

This wrapper forwards `import --manifest <path>` to the local_import adapter.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] != "import" or "--manifest" not in args:
        raise SystemExit(__doc__)
    from app.ingestion.ingest import run

    print(run("local_import", manifest=Path(args[args.index("--manifest") + 1])).as_dict())
