"""Configurações centrais do Themis.IA.

Todas as opções podem ser sobrescritas por variáveis de ambiente (arquivo `.env`
na raiz do projeto). Os padrões refletem o protocolo documentado no README:
chunks de 1000 caracteres com 200 de sobreposição, top-k 5 e semente global 42.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# Desliga telemetria do ChromaDB e paralelismo ruidoso de tokenizers.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

DEFAULT_PASSWORD = "themis123"
DEFAULT_PASSWORD_SHA256 = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "sim"}


@dataclass(frozen=True)
class Settings:
    # LLM (Google Gemini)
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    temperature: float = _float("GEMINI_TEMPERATURE", 0.2)

    # Embeddings — modelo multilíngue (o texto-alvo é jurídico em pt-BR)
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )

    # Banco vetorial (ChromaDB persistente)
    chroma_dir: Path = Path(os.getenv("CHROMA_DIR", str(BASE_DIR / "chroma_db")))
    collection_name: str = os.getenv("CHROMA_COLLECTION", "themis_docs")

    # Ingestão / chunking
    chunk_size: int = _int("CHUNK_SIZE", 1000)
    chunk_overlap: int = _int("CHUNK_OVERLAP", 200)
    max_upload_mb: int = _int("MAX_UPLOAD_MB", 150)
    ocr_enabled: bool = _bool("OCR_ENABLED", False)

    # Recuperação semântica
    retrieval_k: int = _int("RETRIEVAL_K", 5)
    max_context_chars: int = _int("MAX_CONTEXT_CHARS", 12000)
    max_history_turns: int = _int("MAX_HISTORY_TURNS", 8)

    # LexML
    lexml_max_records: int = _int("LEXML_MAX_RECORDS", 5)
    lexml_timeout_s: int = _int("LEXML_TIMEOUT_S", 15)

    # Analytics
    analytics_path: Path = Path(
        os.getenv(
            "ANALYTICS_PATH",
            str(BASE_DIR / "data" / "analytics" / "search_analytics.jsonl"),
        )
    )

    # Autenticação da interface
    app_username: str = os.getenv("APP_USERNAME", "admin")
    app_password_sha256: str = os.getenv(
        "APP_PASSWORD_SHA256",
        hashlib.sha256(os.getenv("APP_PASSWORD", DEFAULT_PASSWORD).encode()).hexdigest(),
    )

    # Reprodutibilidade
    seed: int = _int("SEED", 42)


settings = Settings()
