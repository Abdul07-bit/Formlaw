"""
Detection of instructions hidden in untrusted content (documents, chat requests, retrieved text, model output).

Detection is defence in depth, not the boundary: even an undetected instruction cannot act, because agents reach
tools only through the ToolGateway (allow-lists, no network/e-mail/delete tools) and model output is verified.
What detection buys: flagged spans are kept out of model prompts, the lawyer is warned, and an audit event is recorded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(ignore|disregard|forget)\b.{0,20}\b(all |any )?(the )?(previous|prior|above|earlier|preceding|system)\b.{0,15}\b(instructions?|rules|prompts?|directions)", re.I), "prompt_injection"),
    (re.compile(r"(reveal|print|show|repeat|output|leak|display)\b.{0,20}\b(system|hidden|developer|initial|secret)\s+(prompt|instructions|message)", re.I), "prompt_injection"),
    (re.compile(r"\byou are now\b|\bact as (an? )?(unrestricted|jailbroken|dan|different)\b|\bpretend (to be|you are)\b", re.I), "prompt_injection"),
    (re.compile(r"\b(disregard|override|bypass|disable)\b.{0,20}\b(rules|policy|policies|guidelines|safety|guardrails|verification|security)\b", re.I), "prompt_injection"),
    (re.compile(r"\bnew (system )?instructions?\s*:|\bsystem\s*:\s*you\b|\[\s*system\s*\]|<\s*/?\s*system\s*>", re.I), "prompt_injection"),
    (re.compile(r"\b(mark|declare|treat|record)\b.{0,30}\b(accused|defendant|respondent|petitioner|claim|evidence)\b.{0,20}\b(as )?(guilty|innocent|verified|supported|true|false)\b", re.I), "prompt_injection"),
    (re.compile(r"\b(AI|assistant|model|language model|chatbot|LLM)\b.{0,40}\b(must|should|shall)\b.{0,40}\b(say|state|conclude|answer|report|respond)\b", re.I), "prompt_injection"),
    (re.compile(r"\b(call|invoke|use|access)\b.{0,15}\b(external|outside|remote|admin|internal)\s+(services?|apis?|tools?|endpoints?|database)", re.I), "tool_request"),
    (re.compile(r"\b(run|execute|eval)\b.{0,15}\b(shell|command|code|script|sql|query)\b", re.I), "tool_request"),
    (re.compile(r"\b(send|upload|post|forward|exfiltrate|email|transmit)\b.{0,40}\b(documents|files|data|records|evidence|case|everything|all)\b.{0,40}\b(to|at)\b", re.I), "exfiltration"),
    (re.compile(r"\b(upload|post|forward|exfiltrate|email|send)\b.{0,60}(https?://|\S+@\S+\.\w+)", re.I), "exfiltration"),
    (re.compile(r"!\[[^\]]*\]\(\s*https?://", re.I), "exfiltration"),  # markdown image beacons
    (re.compile(r"(api[_ -]?key|password|secret|token|credentials)\b.{0,30}\b(reveal|print|send|show|share)|\b(reveal|print|send|show|share)\b.{0,30}\b(api[_ -]?key|password|secrets?|tokens?|credentials)\b", re.I), "exfiltration"),
    (re.compile(r"\b(delete|drop|erase|wipe)\b.{0,20}\b(all|every|the)\b.{0,20}\b(cases?|documents?|records?|data|tables?)\b", re.I), "tool_request"),
]
DELIMITER_SPOOF = re.compile(r"<\s*/?\s*(untrusted_documents|passage|trusted_context|request)\b", re.I)
URL = re.compile(r"https?://[^\s)>\]]+", re.I)


@dataclass
class Finding:
    kinds: set[str] = field(default_factory=set)
    spans: list[str] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return bool(self.kinds)

    @property
    def kind(self) -> str:
        for k in ("exfiltration", "tool_request", "prompt_injection", "delimiter_spoofing"):
            if k in self.kinds:
                return k
        return "prompt_injection"

    @property
    def snippet(self) -> str:
        return " … ".join(self.spans)[:220]


def kinds_in(text: str) -> set[str]:
    out = {kind for rx, kind in PATTERNS if rx.search(text)}
    if DELIMITER_SPOOF.search(text):
        out.add("delimiter_spoofing")
    return out


def scan(text: str) -> Finding:
    """Scan text sentence by sentence; return kinds and the offending spans (for the lawyer and the audit log)."""
    f = Finding()
    for sentence in re.split(r"(?<=[.!?\n])\s+", text):
        k = kinds_in(sentence)
        if k:
            f.kinds |= k
            f.spans.append(sentence.strip()[:200])
    return f


def scan_output(text: str, allowed_urls: set[str] | None = None) -> set[str]:
    """Model output must not carry instructions, beacons or links that did not come from the evidence."""
    out = {k for k in kinds_in(text) if k != "delimiter_spoofing"}
    for u in URL.findall(text):
        if not allowed_urls or u not in allowed_urls:
            out.add("output_url")
    return out


def neutralise(text: str, limit: int = 4000) -> str:
    """Defang delimiter look-alikes and cap length before untrusted text enters any prompt."""
    return DELIMITER_SPOOF.sub(lambda m: m.group(0).replace("<", "‹"), text)[:limit]
