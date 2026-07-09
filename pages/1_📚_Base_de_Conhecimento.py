"""Página de gestão da base de conhecimento (documentos indexados no ChromaDB)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ui
from src.rag.vector_store import delete_document, list_documents, reset_collection

st.set_page_config(page_title="Base de Conhecimento — Themis.IA", page_icon="📚", layout="wide")

ui.require_login()
vs = ui.cached_vector_store()
ui.sidebar_user_info()

st.title("📚 Base de Conhecimento")
st.caption("Documentos indexados no banco vetorial (ChromaDB) com rastreabilidade por SHA-256.")

documents = list_documents(vs)

if not documents:
    st.info("Nenhum documento indexado ainda. Faça upload na página principal do chat.")
    st.stop()

table = pd.DataFrame(documents)
table["sha256"] = table["sha256"].str.slice(0, 16) + "…"
table = table.rename(
    columns={
        "source": "Documento",
        "chunks": "Chunks",
        "sha256": "SHA-256 (prefixo)",
        "indexed_at": "Indexado em (UTC)",
    }
)
st.dataframe(table, width="stretch", hide_index=True)

st.divider()
st.subheader("Remover documento")
col_select, col_button = st.columns([3, 1])
target = col_select.selectbox(
    "Documento a remover",
    options=[d["source"] for d in documents],
    label_visibility="collapsed",
)
if col_button.button("Remover", type="primary", width="stretch"):
    removed = delete_document(vs, target)
    st.success(f"Removidos {removed} chunks de '{target}'.")
    st.rerun()

st.divider()
st.subheader("Zerar base")
confirm = st.checkbox("Confirmo que desejo apagar todos os documentos indexados.")
if st.button("🗑️ Apagar tudo", disabled=not confirm):
    removed = reset_collection(vs)
    st.success(f"Base zerada ({removed} chunks removidos).")
    st.rerun()

st.divider()
ui.disclaimer_footer()
