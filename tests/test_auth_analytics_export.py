import hashlib
import io
from types import SimpleNamespace

from docx import Document

from src import analytics, auth
from src.export import DISCLAIMER, answer_to_docx_bytes


def _fake_settings(username: str = "admin", password: str = "themis123"):
    return SimpleNamespace(
        app_username=username,
        app_password_sha256=hashlib.sha256(password.encode()).hexdigest(),
    )


def test_verify_credentials(monkeypatch):
    # Independe do .env local: injeta credenciais conhecidas.
    monkeypatch.setattr(auth, "settings", _fake_settings())
    assert auth.verify_credentials("admin", "themis123")
    assert auth.verify_credentials("  admin  ", "themis123")  # tolera espaços no usuário
    assert not auth.verify_credentials("admin", "senha-errada")
    assert not auth.verify_credentials("outro", "themis123")


def test_using_default_password_detection(monkeypatch):
    monkeypatch.setattr(auth, "settings", _fake_settings(password="themis123"))
    assert auth.using_default_password()
    monkeypatch.setattr(auth, "settings", _fake_settings(password="senha-forte"))
    assert not auth.using_default_password()


def test_analytics_roundtrip(tmp_path):
    log_path = tmp_path / "analytics.jsonl"
    analytics.log_event("query", path=log_path, persona="analista", latency_total_s=1.2)
    analytics.log_event("ingest", path=log_path, source="doc.pdf", chunks=10)
    events = analytics.load_events(log_path)
    assert len(events) == 2
    assert events[0]["type"] == "query"
    assert events[0]["persona"] == "analista"
    assert "ts" in events[0]


def test_analytics_ignores_corrupted_lines(tmp_path):
    log_path = tmp_path / "analytics.jsonl"
    analytics.log_event("query", path=log_path, persona="redator")
    log_path.open("a").write("{linha quebrada\n")
    assert len(analytics.load_events(log_path)) == 1


def test_docx_export_contains_content_and_disclaimer():
    content = "# Análise\n\n- O contrato prevê **multa de 2%**.\n- Foro de Recife/PE."
    data = answer_to_docx_bytes("Análise do contrato", content, "Analista de Documentos")
    doc = Document(io.BytesIO(data))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "multa de 2%" in full_text
    assert "Foro de Recife/PE" in full_text
    assert DISCLAIMER in full_text
    assert "Analista de Documentos" in full_text
