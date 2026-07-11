"""Application service for deterministic knowledge retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from palnavi.domain.knowledge import (
    KnowledgeQuery,
    KnowledgeRepository,
    KnowledgeSearchOutcome,
)


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalService:
    repository: KnowledgeRepository

    def search(self, query: KnowledgeQuery) -> KnowledgeSearchOutcome:
        return self.repository.search(query)
