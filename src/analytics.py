"""Registro de analytics em JSONL (data/analytics/search_analytics.jsonl).

Cada evento é uma linha JSON com timestamp UTC. O dashboard (página Analytics
do Streamlit) e o protocolo de avaliação consomem este arquivo.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings


def log_event(event_type: str, *, path: Path | None = None, **fields) -> dict:
    """Anexa um evento ao log JSONL e o retorna."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": event_type,
        **fields,
    }
    target = path or settings.analytics_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def load_events(path: Path | None = None) -> list[dict]:
    """Lê todos os eventos do log; linhas corrompidas são ignoradas."""
    target = path or settings.analytics_path
    if not target.exists():
        return []
    events: list[dict] = []
    with target.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events
