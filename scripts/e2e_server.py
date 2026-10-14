"""
Backend for the browser end-to-end tests (started by playwright.config.ts).

A fresh temporary SQLite database per run — never the development database — built by the real migrations and seeded
with the SYNTHETIC demo data, served on 127.0.0.1:8010 in DEMO_MODE.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="formlaw-e2e-"))
os.environ.update({
    "FORMLAW_ENV": "development", "DEMO_MODE": "true", "DATABASE_URL": f"sqlite:///{(tmp / 'e2e.db').as_posix()}",
    "STORAGE_DIR": str(tmp / "storage"), "LLM_PROVIDER": "none", "JWT_SECRET": "e2e-only-" + "x" * 40, "FILE_ENCRYPTION_KEY": "",
    "GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "CORS_ORIGINS": "http://127.0.0.1:5180",
    # One browser signs in as several personas within seconds from one IP; the default (10/min) would block the suite.
    "AUTH_RATE_LIMIT_PER_MINUTE": "100",
})
backend = ROOT / "backend"
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend, check=True)
subprocess.run([sys.executable, str(ROOT / "database" / "seeds" / "seed.py")], cwd=backend, check=True)
sys.path.insert(0, str(backend))

import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=8010, app_dir=str(backend), log_level="warning")
