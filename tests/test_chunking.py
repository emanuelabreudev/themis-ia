from src.ingestion.chunking import chunk_pages
from src.ingestion.extractors import PageText


def _make_pages() -> list[PageText]:
    clause = (
        "CLÁUSULA PRIMEIRA — DO OBJETO\n"
        "1.1. O presente contrato tem por objeto a prestação de serviços de consultoria. "
        + "Detalhes adicionais da prestação de serviços. " * 30
    )
    return [PageText(page=1, text=clause), PageText(page=2, text="Texto curto da página dois.")]


def test_chunks_respect_size_limit():
    chunks = chunk_pages(_make_pages(), source="doc.pdf", file_sha256="abc", chunk_size=500, chunk_overlap=100)
    assert chunks, "deveria gerar chunks"
    assert all(len(c.text) <= 500 for c in chunks)


def test_metadata_preserved_and_indexed():
    chunks = chunk_pages(_make_pages(), source="doc.pdf", file_sha256="abc", chunk_size=500, chunk_overlap=100)
    assert {c.metadata["source"] for c in chunks} == {"doc.pdf"}
    assert {c.metadata["file_sha256"] for c in chunks} == {"abc"}
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))
    assert chunks[-1].metadata["page"] == 2


def test_empty_pages_are_skipped():
    chunks = chunk_pages([PageText(page=1, text="   ")], source="x.pdf", file_sha256="h")
    assert chunks == []
