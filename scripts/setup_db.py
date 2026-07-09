"""Popula a base vetorial com os documentos de exemplo (data/exemplos/).

Uso:
    python scripts/setup_db.py [--dir data/exemplos]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.extractors import SUPPORTED_EXTENSIONS  # noqa: E402
from src.ingestion.pipeline import ingest_path  # noqa: E402
from src.rag.vector_store import count_chunks, get_vector_store  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="data/exemplos", help="pasta com documentos a indexar")
    args = parser.parse_args()

    folder = Path(args.dir)
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    if not files:
        print(f"Nenhum arquivo suportado em {folder}/")
        return

    vs = get_vector_store()
    for path in files:
        report = ingest_path(vs, path)
        status = f"IGNORADO ({report.reason})" if report.skipped else f"{report.chunks} chunks"
        print(f"- {report.source}: {status}")

    print(f"\nTotal na base: {count_chunks(vs)} chunks.")


if __name__ == "__main__":
    main()
