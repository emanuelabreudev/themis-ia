"""Orquestração da ingestão: hash → extração → chunking → indexação no ChromaDB.

Deduplicação por SHA-256: um arquivo já indexado (mesmo conteúdo) é ignorado,
o que torna a ingestão idempotente e rastreável (o hash fica registrado nos
metadados de cada chunk e aparece no data card da base).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.ingestion.chunking import chunk_pages
from src.ingestion.extractors import extract_document
from src.rag import vector_store


@dataclass
class IngestReport:
    source: str
    sha256: str
    pages: int = 0
    chunks: int = 0
    skipped: bool = False
    reason: str = ""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ingest_bytes(vs, filename: str, data: bytes, *, ocr_enabled: bool | None = None) -> IngestReport:
    """Indexa um documento (bytes) no banco vetorial e retorna um relatório."""
    file_hash = sha256_bytes(data)

    if vector_store.source_exists(vs, file_hash):
        return IngestReport(
            source=filename,
            sha256=file_hash,
            skipped=True,
            reason="documento com conteúdo idêntico já indexado (SHA-256 repetido)",
        )

    use_ocr = settings.ocr_enabled if ocr_enabled is None else ocr_enabled
    pages = extract_document(filename, data, ocr_enabled=use_ocr)
    chunks = chunk_pages(pages, source=filename, file_sha256=file_hash)

    if not chunks:
        return IngestReport(
            source=filename,
            sha256=file_hash,
            pages=len(pages),
            skipped=True,
            reason="nenhum texto extraível (PDF escaneado sem OCR habilitado?)",
        )

    indexed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for chunk in chunks:
        chunk.metadata["indexed_at"] = indexed_at

    vs.add_texts(
        texts=[c.text for c in chunks],
        metadatas=[c.metadata for c in chunks],
    )
    return IngestReport(source=filename, sha256=file_hash, pages=len(pages), chunks=len(chunks))


def ingest_path(vs, path: str | Path, *, ocr_enabled: bool | None = None) -> IngestReport:
    """Indexa um arquivo do disco."""
    path = Path(path)
    return ingest_bytes(vs, path.name, path.read_bytes(), ocr_enabled=ocr_enabled)
