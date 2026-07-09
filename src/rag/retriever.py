"""Recuperação semântica sobre o banco vetorial."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import settings


@dataclass
class RetrievedChunk:
    text: str
    source: str
    page: int
    score: float  # relevância em [0, 1] (1 = mais relevante)

    @property
    def citation(self) -> str:
        return f"{self.source}, p. {self.page}"


def retrieve(vs, query: str, *, k: int | None = None) -> list[RetrievedChunk]:
    """Busca os k chunks mais relevantes (similaridade de cosseno normalizada)."""
    results = vs.similarity_search_with_relevance_scores(query, k=k or settings.retrieval_k)
    chunks: list[RetrievedChunk] = []
    for doc, score in results:
        chunks.append(
            RetrievedChunk(
                text=doc.page_content,
                source=doc.metadata.get("source", "desconhecido"),
                page=int(doc.metadata.get("page", 0) or 0),
                score=max(0.0, min(1.0, float(score))),
            )
        )
    return chunks


def trim_to_budget(chunks: list[RetrievedChunk], max_chars: int | None = None) -> list[RetrievedChunk]:
    """Limita o contexto total em caracteres para caber no orçamento de prompt."""
    budget = max_chars or settings.max_context_chars
    selected: list[RetrievedChunk] = []
    used = 0
    for chunk in chunks:
        if used + len(chunk.text) > budget and selected:
            break
        selected.append(chunk)
        used += len(chunk.text)
    return selected
