"""
Versioned prompt registry + trust-separated message construction.

    system  = common rules (versioned) + task prompt (versioned)               ← FormLaw only
    user    = REQUEST (lawyer)  |  TRUSTED CONTEXT (FormLaw)  |  UNTRUSTED DOCUMENTS (fenced with a per-call nonce)

Untrusted text never enters the system message. The fence uses a random nonce, so a document cannot close it, and any
look-alike fence tags inside documents are defanged. Prompt ids + versions + hashes are recorded on every run.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPT_DIR = Path(__file__).resolve().parent / "prompt_texts"
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
_FENCE_LOOKALIKE = re.compile(r"<\s*/?\s*(untrusted_documents|passage|trusted_context|request)\b", re.I)


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    text: str

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()[:12]

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}#{self.sha}"


@lru_cache
def load(prompt_id: str) -> Prompt:
    raw = (PROMPT_DIR / f"{prompt_id}.md").read_text(encoding="utf-8")
    m = _FRONT.match(raw)
    if not m:
        raise RuntimeError(f"Prompt {prompt_id} has no front matter")
    meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
    return Prompt(meta["id"].strip(), meta["version"].strip(), raw[m.end():].strip())


def system_prompt(task_id: str) -> tuple[str, list[str]]:
    """Returns the system prompt and the prompt refs used (for the run record)."""
    common, task = load("common"), load(task_id)
    return f"{common.text}\n\n{task.text}", [common.ref, task.ref]


def neutralise(text: str, limit: int = 4000) -> str:
    """Defang fence look-alikes and cap length. Applied to every untrusted string before it enters a prompt."""
    return _FENCE_LOOKALIKE.sub(lambda m: m.group(0).replace("<", "‹"), text)[:limit]


@dataclass(frozen=True)
class PromptPassage:
    id: str
    source: str  # e.g. "RemandReport.pdf p.2 ¶3" — FormLaw-generated
    text: str    # untrusted


def user_message(*, request: str, passages: list[PromptPassage] = (), context: dict[str, Any] | None = None,
                 passage_limit: int = 1800) -> str:
    nonce = secrets.token_hex(6)
    parts = [f"<request>\n{neutralise(request, 2000)}\n</request>"]
    if context:
        parts.append("<trusted_context>\n" + json.dumps(context, ensure_ascii=False, default=str)[:12000] + "\n</trusted_context>")
    if passages:
        body = "\n".join(
            f'<passage id="{p.id}" source="{neutralise(p.source, 160)}">\n{neutralise(p.text, passage_limit)}\n</passage>' for p in passages
        )
        parts.append(f'<untrusted_documents nonce="{nonce}">\n{body}\n</untrusted_documents nonce="{nonce}">')
    else:
        parts.append(f'<untrusted_documents nonce="{nonce}">\n(no passages)\n</untrusted_documents nonce="{nonce}">')
    return "\n\n".join(parts)
