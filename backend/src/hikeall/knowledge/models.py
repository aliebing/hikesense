"""Shared knowledge types (no dependency on hikeall.agent)."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class KnowledgeHit(BaseModel):
    """One passage from the knowledge index."""

    text: str
    source_id: str | None = None
    title: str | None = None
    url: str | None = None
    license: str | None = None
    score: float | None = None
    source_urls: list[str] = []  # all sources the passage rests on (own texts: frontmatter)
    status: str | None = None  # own texts: "entwurf" | "geprüft"; articles: None


class KnowledgeIndex(Protocol):
    def search(self, query: str, k: int = 5) -> list[KnowledgeHit]: ...
