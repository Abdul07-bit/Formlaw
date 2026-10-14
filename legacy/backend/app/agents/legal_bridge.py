"""
Bridge to the original six-agent legal system in agents/legal/ (Review → Research → Drafting →
Verification + RAG chatbot). Those modules use plain sibling imports and a module-level case
registry, so they are loaded from their folder and every run is serialised.
"""
from __future__ import annotations

import re
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from .engine.chunking import DocText, markers_to_form_feeds

LEGAL_DIR = Path(__file__).resolve().parent / "legal"
if str(LEGAL_DIR) not in sys.path:
    sys.path.insert(0, str(LEGAL_DIR))

from corpus import CORPUS, is_trusted  # noqa: E402
from legal_drafting_agent import LEGAL_GROUNDS_MAP  # noqa: E402
from orchestrator import LegalOrchestrator  # noqa: E402

DRAFT_TYPES: tuple[str, ...] = tuple(LEGAL_GROUNDS_MAP)
_lock = threading.Lock()


def default_draft_type(area: str | None) -> str:
    return {"Criminal": "bail", "Property": "plaint", "Family": "plaint", "Constitutional": "affidavit"}.get(area or "", "legal_notice")


def _write_docs(docs: list[DocText], folder: Path) -> list[str]:
    paths, used = [], set()
    for d in docs:
        if not d.text.strip():
            continue
        name = re.sub(r"[^\w.\- ]+", "", d.name)[:100] or "document"
        if not name.lower().endswith((".txt", ".md")):
            name = name.rsplit(".", 1)[0] + ".txt"  # agents cite this name, e.g. "fir.txt p.2"
        while name in used:
            name = "_" + name
        used.add(name)
        (folder / name).write_text(markers_to_form_feeds(d.text), encoding="utf-8")
        paths.append(str(folder / name))
    return paths


def _jsonable(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)


def run_pipeline(docs: list[DocText], doc_type: str) -> dict[str, Any]:
    if doc_type not in LEGAL_GROUNDS_MAP:
        raise ValueError(f"Unsupported draft type: {doc_type}")
    with tempfile.TemporaryDirectory(prefix="formlaw-") as tmp, _lock:
        paths = _write_docs(docs, Path(tmp))
        if not paths:
            return {"error": "No readable document text"}
        orch = LegalOrchestrator()
        info = orch.load_documents(paths)
        out = orch.run_full(doc_type)
    out["docType"] = doc_type
    out["warnings"] = info["warnings"]
    return _jsonable(out)


def chat(docs: list[DocText], question: str, prior: dict[str, Any] | None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="formlaw-") as tmp, _lock:
        paths = _write_docs(docs, Path(tmp))
        if not paths:
            return {"status": "no_documents", "answer": "", "references": []}
        orch = LegalOrchestrator()
        orch.load_documents(paths)
        for k in ("review", "research", "draft", "verification"):
            if prior and prior.get(k):
                orch.state[k] = prior[k]
        orch._refresh_chatbot_context()
        return _jsonable(orch.do_chat(question))


def trusted_corpus() -> list[dict[str, Any]]:
    return [d for d in CORPUS if is_trusted(d)]


def corpus_citation_exists(cite: str) -> bool:
    c = cite.lower().strip()
    for d in trusted_corpus():
        if d.get("citation") and d["citation"].lower() in c:
            return True
        if d.get("type") == "statute" and d.get("section"):
            act_words = d["title"].lower().split(",")[0]
            if re.search(rf"\bsection\s+{re.escape(d['section'].lower())}\b", c) and (act_words in c or _abbr(d["title"]) in c):
                return True
    return False


def _abbr(title: str) -> str:
    return {"Indian Penal Code, 1860": "ipc", "Code of Criminal Procedure, 1973": "crpc"}.get(title, "\0")
