"""Prompt loading (versioned files under prompts/review/) and prompt assembly."""

from dataclasses import dataclass
from pathlib import Path

from app.agents.base import WorkflowType
from app.agents.review.security import neutralize_delimiters
from app.errors import PromptNotFoundError

_COMMON_STEM = "common_v1"
_WORKFLOW_STEMS = {
    WorkflowType.CASE_REVIEW: "case_v1",
    WorkflowType.CONTRACT_REVIEW: "contract_v1",
}


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    version: str


class PromptLibrary:
    """Loads all review prompts at construction so a missing file fails fast."""

    def __init__(self, prompts_dir: Path) -> None:
        review_dir = prompts_dir / "review"
        common = self._read(review_dir / f"{_COMMON_STEM}.md")
        self._bundles: dict[WorkflowType, PromptBundle] = {}
        for workflow, stem in _WORKFLOW_STEMS.items():
            specific = self._read(review_dir / f"{stem}.md")
            body = f"{common}\n\n{specific}"
            wrapped = f"<TRUSTED_SYSTEM_INSTRUCTIONS>\n{body}\n</TRUSTED_SYSTEM_INSTRUCTIONS>"
            self._bundles[workflow] = PromptBundle(wrapped, f"{_COMMON_STEM}+{stem}")

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise PromptNotFoundError(f"Prompt file not found: {path.name}") from exc

    def get(self, workflow: WorkflowType) -> PromptBundle:
        return self._bundles[workflow]


def _safe_attr(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch not in '"<>\r\n')
    return cleaned[:255]


def build_user_prompt(
    *,
    request: str,
    document_text: str,
    document_name: str | None,
    feedback: list[str] | None = None,
) -> str:
    """Trusted request and untrusted document are separated by explicit delimiters.

    The document (and the user's request) are passed through `neutralize_delimiters`
    so they cannot close a block and smuggle in "trusted" text.
    """
    name = _safe_attr(document_name) if document_name else "unnamed"
    parts = [
        "<USER_REQUEST>",
        neutralize_delimiters(request),
        "</USER_REQUEST>",
        "",
        f'<UNTRUSTED_DOCUMENT name="{name}">',
        neutralize_delimiters(document_text),
        "</UNTRUSTED_DOCUMENT>",
    ]
    if feedback:
        bullet_lines = "\n".join(f"- {line}" for line in feedback[:20])
        parts += [
            "",
            "<VALIDATION_FEEDBACK>",
            "Your previous output was rejected by deterministic validation:",
            bullet_lines,
            "Return a complete corrected output that fixes every item above.",
            "</VALIDATION_FEEDBACK>",
        ]
    return "\n".join(parts)
