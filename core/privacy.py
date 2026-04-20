"""Redact secrets, drop blocked projects, optionally abstract tech names."""
from __future__ import annotations

import re
from typing import Any

from core.schema import Activity

# Coarse map from concrete tech → abstract description.
# Only applied when config.privacy.abstract_tech is True.
TECH_ABSTRACT: dict[str, str] = {
    r"\bpostgres(?:ql)?\b": "relational DB",
    r"\bpgvector\b": "vector index extension",
    r"\bmysql\b": "relational DB",
    r"\bredis\b": "in-memory key/value store",
    r"\bchroma(?:db)?\b": "vector DB",
    r"\bpinecone\b": "vector DB",
    r"\bqdrant\b": "vector DB",
    r"\bmilvus\b": "vector DB",
    r"\bweaviate\b": "vector DB",
    r"\bllamaindex\b": "RAG framework",
    r"\blangchain\b": "LLM orchestration framework",
    r"\bfastapi\b": "Python async web framework",
    r"\bdjango\b": "Python web framework",
    r"\bflask\b": "Python micro web framework",
    r"\bnext(?:\.js)?\b": "React meta-framework",
    r"\bnuxt\b": "Vue meta-framework",
    r"\bremix\b": "React meta-framework",
    r"\bnestjs\b": "Node backend framework",
    r"\bcelery\b": "distributed task queue",
    r"\brabbitmq\b": "message broker",
    r"\bkafka\b": "event streaming platform",
    r"\bclaude(?:\s+code|\s+3\.\d+|\s+opus|\s+sonnet|\s+haiku)?\b": "large language model",
    r"\bgpt[-\s]?\d\w*\b": "large language model",
    r"\bgemini\b": "large language model",
}


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


class PrivacyFilter:
    def __init__(self, cfg: dict[str, Any]) -> None:
        priv = cfg.get("privacy", {})
        self.redactors = _compile(priv.get("redact_patterns") or [])
        self.blocklist = set(priv.get("blocklist") or [])
        self.abstract = bool(priv.get("abstract_tech"))
        self.tech_patterns = [(re.compile(p, re.IGNORECASE), v) for p, v in TECH_ABSTRACT.items()]

    def redact(self, text: str) -> str:
        if not text:
            return text
        for rx in self.redactors:
            text = rx.sub("[REDACTED]", text)
        if self.abstract:
            for rx, repl in self.tech_patterns:
                text = rx.sub(repl, text)
        return text

    def is_blocked(self, project: str | None) -> bool:
        if not project:
            return False
        return any(b in project for b in self.blocklist)

    def apply(self, act: Activity) -> Activity | None:
        if self.is_blocked(act.project):
            return None
        act.summary = self.redact(act.summary)
        act.keywords = [self.redact(k) for k in act.keywords]
        act.files_touched = [self.redact(f) for f in act.files_touched]
        if act.extra:
            act.extra = {
                k: (self.redact(v) if isinstance(v, str) else v) for k, v in act.extra.items()
            }
        return act
