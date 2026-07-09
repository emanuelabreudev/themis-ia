"""Smoke test end-to-end (marcado como slow): ingestão real + recuperação semântica.

Baixa o modelo de embeddings na primeira execução. Não usa a API do Gemini.
Roda com: pytest -m slow
"""

from pathlib import Path

import pytest

from src.ingestion.pipeline import ingest_path
from src.rag.retriever import retrieve
from src.rag.vector_store import get_vector_store

EXAMPLES = Path(__file__).resolve().parent.parent / "data" / "exemplos"


@pytest.mark.slow
def test_ingest_and_retrieve_end_to_end(tmp_path):
    vs = get_vector_store(persist_directory=str(tmp_path / "chroma"), collection_name="smoke")

    report_contract = ingest_path(vs, EXAMPLES / "contrato_exemplo.txt")
    report_sentence = ingest_path(vs, EXAMPLES / "sentenca_exemplo.txt")
    assert not report_contract.skipped and report_contract.chunks > 0
    assert not report_sentence.skipped and report_sentence.chunks > 0

    # Reingestão do mesmo arquivo deve ser deduplicada por SHA-256.
    again = ingest_path(vs, EXAMPLES / "contrato_exemplo.txt")
    assert again.skipped

    chunks = retrieve(vs, "Qual a multa por atraso no pagamento do contrato?", k=3)
    assert chunks, "a recuperação deveria retornar trechos"
    top_texts = " ".join(c.text for c in chunks)
    assert "2%" in top_texts or "multa" in top_texts.lower()
    assert chunks[0].source == "contrato_exemplo.txt"

    chunks_sentence = retrieve(vs, "Qual foi o valor da condenação na sentença?", k=3)
    assert any(c.source == "sentenca_exemplo.txt" for c in chunks_sentence)
