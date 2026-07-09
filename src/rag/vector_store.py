"""Banco vetorial persistente (ChromaDB) com embeddings HuggingFace multilíngues."""

from __future__ import annotations

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from src.config import settings


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=settings.embedding_model)


def get_vector_store(
    persist_directory: str | None = None, collection_name: str | None = None
) -> Chroma:
    return Chroma(
        collection_name=collection_name or settings.collection_name,
        embedding_function=get_embeddings(),
        persist_directory=persist_directory or str(settings.chroma_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )


def source_exists(vs: Chroma, file_sha256: str) -> bool:
    """Verifica se um arquivo (pelo hash SHA-256) já foi indexado."""
    result = vs.get(where={"file_sha256": file_sha256}, limit=1)
    return bool(result.get("ids"))


def count_chunks(vs: Chroma) -> int:
    return len(vs.get().get("ids", []))


def list_documents(vs: Chroma) -> list[dict]:
    """Agrega os metadados por documento: nº de chunks, hash e data de indexação."""
    data = vs.get(include=["metadatas"])
    aggregated: dict[str, dict] = {}
    for md in data.get("metadatas") or []:
        source = md.get("source", "desconhecido")
        entry = aggregated.setdefault(
            source,
            {
                "source": source,
                "chunks": 0,
                "sha256": md.get("file_sha256", ""),
                "indexed_at": md.get("indexed_at", ""),
            },
        )
        entry["chunks"] += 1
    return sorted(aggregated.values(), key=lambda e: e["source"].lower())


def delete_document(vs: Chroma, source: str) -> int:
    """Remove todos os chunks de um documento; retorna quantos foram removidos."""
    ids = vs.get(where={"source": source}).get("ids", [])
    if ids:
        vs.delete(ids=ids)
    return len(ids)


def reset_collection(vs: Chroma) -> int:
    """Esvazia a coleção inteira; retorna quantos chunks foram removidos."""
    ids = vs.get().get("ids", [])
    if ids:
        vs.delete(ids=ids)
    return len(ids)
