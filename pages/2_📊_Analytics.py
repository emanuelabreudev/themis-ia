"""Dashboard de analytics: consumo do log JSONL de consultas e ingestões.

Cores: paleta de referência validada para daltonismo (slot 1 azul #2a78d6,
slot 2 aqua #1baf7a); magnitude usa tom único; identidade nunca depende só de
cor (rótulos diretos + vista em tabela).
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import analytics, ui
from src.rag.personas import PERSONAS

st.set_page_config(page_title="Analytics — Themis.IA", page_icon="📊", layout="wide")

ui.require_login()
ui.sidebar_user_info()

SERIES_1 = "#2a78d6"  # azul — slot categórico 1
SERIES_2 = "#1baf7a"  # aqua — slot categórico 2
GRID = "#e1e0d9"

st.title("📊 Analytics de uso")
st.caption("Métricas registradas em `data/analytics/search_analytics.jsonl`.")

events = analytics.load_events()
queries = pd.DataFrame([e for e in events if e.get("type") == "query"])
ingests = [e for e in events if e.get("type") == "ingest"]

if queries.empty:
    st.info("Ainda não há consultas registradas. Use o chat para gerar dados de uso.")
    st.stop()

queries["ts"] = pd.to_datetime(queries["ts"], errors="coerce")
queries["persona_label"] = queries["persona"].map(
    lambda key: PERSONAS[key].label if key in PERSONAS else str(key)
)

# ------------------------------------------------------------------- KPIs --
total = len(queries)
avg_latency = queries["latency_total_s"].mean()
lexml_pct = 100 * queries["lexml_used"].fillna(False).astype(bool).mean()
top_persona = queries["persona_label"].mode().iat[0]

kpi_cols = st.columns(4)
kpi_cols[0].metric("Consultas", f"{total}")
kpi_cols[1].metric("Latência média", f"{avg_latency:.1f} s")
kpi_cols[2].metric("Consultas com LexML", f"{lexml_pct:.0f}%")
kpi_cols[3].metric("Persona mais usada", top_persona)
st.caption(f"Documentos indexados no período: {len(ingests)}")

st.divider()
left, right = st.columns(2)

# --------------------------------------------- consultas por persona (bar) --
with left:
    st.subheader("Consultas por persona")
    by_persona = queries.groupby("persona_label", as_index=False).size()
    base = alt.Chart(by_persona).encode(
        y=alt.Y("persona_label:N", sort="-x", title=None),
        x=alt.X("size:Q", title="Consultas", axis=alt.Axis(gridColor=GRID, tickMinStep=1)),
        tooltip=[
            alt.Tooltip("persona_label:N", title="Persona"),
            alt.Tooltip("size:Q", title="Consultas"),
        ],
    )
    bars = base.mark_bar(color=SERIES_1, cornerRadiusEnd=4, height=18)
    labels = base.mark_text(align="left", dx=6).encode(text="size:Q")
    st.altair_chart(bars + labels, width="stretch")

# ------------------------------------------------ latência ao longo do tempo --
with right:
    st.subheader("Latência das respostas")
    latency_chart = (
        alt.Chart(queries)
        .mark_line(color=SERIES_1, strokeWidth=2, point=alt.OverlayMarkDef(color=SERIES_1, size=60))
        .encode(
            x=alt.X("ts:T", title=None, axis=alt.Axis(gridColor=GRID)),
            y=alt.Y("latency_total_s:Q", title="Latência total (s)", axis=alt.Axis(gridColor=GRID)),
            tooltip=[
                alt.Tooltip("ts:T", title="Quando", format="%d/%m %H:%M"),
                alt.Tooltip("latency_total_s:Q", title="Total (s)", format=".2f"),
                alt.Tooltip("latency_llm_s:Q", title="LLM (s)", format=".2f"),
                alt.Tooltip("persona_label:N", title="Persona"),
            ],
        )
    )
    st.altair_chart(latency_chart, width="stretch")

# ----------------------------------------------------------- uso do LexML --
st.subheader("Uso da busca LexML")
lexml_counts = (
    queries["lexml_used"]
    .fillna(False)
    .astype(bool)
    .map({True: "Com busca LexML", False: "Somente base local"})
    .value_counts()
    .rename_axis("categoria")
    .reset_index(name="consultas")
)
lexml_base = alt.Chart(lexml_counts).encode(
    y=alt.Y("categoria:N", title=None),
    x=alt.X("consultas:Q", title="Consultas", axis=alt.Axis(gridColor=GRID, tickMinStep=1)),
    color=alt.Color(
        "categoria:N",
        scale=alt.Scale(
            domain=["Com busca LexML", "Somente base local"],
            range=[SERIES_1, SERIES_2],
        ),
        legend=None,  # identidade já está no rótulo do eixo y
    ),
    tooltip=[
        alt.Tooltip("categoria:N", title="Categoria"),
        alt.Tooltip("consultas:Q", title="Consultas"),
    ],
)
lexml_bars = lexml_base.mark_bar(cornerRadiusEnd=4, height=18)
lexml_labels = lexml_base.mark_text(align="left", dx=6).encode(text="consultas:Q")
st.altair_chart(lexml_bars + lexml_labels, width="stretch")

# ------------------------------------------------- vista em tabela (a11y) --
with st.expander("📋 Dados brutos (tabela)"):
    display = queries[
        ["ts", "persona_label", "latency_total_s", "latency_llm_s", "n_sources", "lexml_used"]
    ].rename(
        columns={
            "ts": "Quando (UTC)",
            "persona_label": "Persona",
            "latency_total_s": "Latência total (s)",
            "latency_llm_s": "Latência LLM (s)",
            "n_sources": "Trechos usados",
            "lexml_used": "LexML",
        }
    )
    st.dataframe(display.sort_values("Quando (UTC)", ascending=False), hide_index=True, width="stretch")

st.divider()
ui.disclaimer_footer()
