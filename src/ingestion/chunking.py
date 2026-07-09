"""Quebra semântica de texto jurídico em chunks.

Usa `RecursiveCharacterTextSplitter` com separadores adaptados ao domínio
(artigos, cláusulas e parágrafos) para evitar cortar dispositivos legais ao
meio — refinamento sobre os separadores padrão do design original.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import settings
from src.ingestion.extractors import PageText

# Ordem de preferência dos pontos de corte: parágrafos, artigos/cláusulas,
# parágrafos de lei (§), linhas, sentenças, palavras.
LEGAL_SEPARATORS = [
    "\n\n",
    "\nArt. ",
    "\nArtigo ",
    "\nCLÁUSULA",
    "\nCláusula",
    "\n§",
    "\n",
    ". ",
    " ",
    "",
]


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_pages(
    pages: list[PageText],
    *,
    source: str,
    file_sha256: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Divide as páginas em chunks preservando os metadados de origem/página."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
        separators=LEGAL_SEPARATORS,
    )
    chunks: list[Chunk] = []
    index = 0
    for page in pages:
        if not page.text.strip():
            continue
        for piece in splitter.split_text(page.text):
            piece = piece.strip()
            if not piece:
                continue
            chunks.append(
                Chunk(
                    text=piece,
                    metadata={
                        "source": source,
                        "page": page.page,
                        "chunk_index": index,
                        "file_sha256": file_sha256,
                    },
                )
            )
            index += 1
    return chunks
