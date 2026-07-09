"""Themis.IA — interface principal de chat (Streamlit).

Fluxo: login → upload/indexação de documentos → seleção de persona →
conversa com respostas aterradas (RAG) → fontes citadas → exportação .docx.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

# Garante importações absolutas (src.*) mesmo quando o app roda fora da raiz.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import analytics, ui
from src.config import settings
from src.export import answer_to_docx_bytes
from src.ingestion.extractors import SUPPORTED_EXTENSIONS
from src.ingestion.pipeline import ingest_bytes
from src.rag import engine
from src.rag.personas import DEFAULT_PERSONA, PERSONAS
from src.rag.vector_store import count_chunks

st.set_page_config(page_title="Themis.IA", page_icon="⚖️", layout="wide")

ui.require_login()
vs = ui.cached_vector_store()

SUGGESTIONS = {
    "📄 Analisar petição inicial": (
        "Analise a petição inicial presente nos autos: identifique as partes, os pedidos, "
        "a causa de pedir e os valores envolvidos.",
        "analista",
    ),
    "⚖️ Buscar jurisprudência": (
        "Qual é a jurisprudência e a legislação aplicáveis ao tema central deste caso?",
        "pesquisador",
    ),
    "✍️ Redigir defesa": (
        "Redija uma minuta de contestação com base nos fatos e documentos dos autos.",
        "redator",
    ),
}

LEXML_MODES = {"auto": "Automático (roteador)", "sempre": "Sempre buscar", "nunca": "Nunca buscar"}


def _new_chat() -> str:
    chat_id = uuid.uuid4().hex[:8]
    st.session_state.chats[chat_id] = {"title": "Novo chat", "messages": []}
    st.session_state.active_chat = chat_id
    return chat_id


if "chats" not in st.session_state:
    st.session_state.chats = {}
    _new_chat()

chats = st.session_state.chats
active_id = st.session_state.get("active_chat")
if active_id not in chats:
    active_id = _new_chat()
chat = chats[active_id]

# ---------------------------------------------------------------- sidebar --
ui.sidebar_user_info()

with st.sidebar:
    st.divider()
    if st.button("➕ Novo chat", width="stretch"):
        _new_chat()
        st.rerun()

    st.markdown("**Histórico de chats**")
    for chat_id, data in list(chats.items()):
        label = data["title"] if data["messages"] else "Novo chat"
        button_type = "primary" if chat_id == active_id else "secondary"
        if st.button(label, key=f"chat_{chat_id}", width="stretch", type=button_type):
            st.session_state.active_chat = chat_id
            st.rerun()

    st.divider()
    persona_key = st.selectbox(
        "🎭 Persona",
        options=list(PERSONAS),
        index=list(PERSONAS).index(DEFAULT_PERSONA),
        format_func=lambda key: PERSONAS[key].display,
    )
    st.caption(PERSONAS[persona_key].description)

    lexml_mode = st.selectbox(
        "🌐 Busca LexML (web)",
        options=list(LEXML_MODES),
        format_func=LEXML_MODES.get,
        help=(
            "Automático: aciona a busca quando a pergunta menciona jurisprudência/legislação "
            "ou quando a persona Pesquisador está ativa."
        ),
    )

    st.divider()
    st.markdown("**📎 Upload de documentos**")
    uploads = st.file_uploader(
        f"PDF, DOCX, TXT ou MD (até {settings.max_upload_mb} MB cada)",
        type=[ext.lstrip(".") for ext in sorted(SUPPORTED_EXTENSIONS)],
        accept_multiple_files=True,
    )
    if uploads and st.button("Indexar documentos", width="stretch", type="primary"):
        with st.status("Indexando documentos…", expanded=True) as status:
            for file in uploads:
                size_mb = len(file.getvalue()) / (1024 * 1024)
                if size_mb > settings.max_upload_mb:
                    st.write(f"❌ **{file.name}**: {size_mb:.0f} MB excede o limite.")
                    continue
                report = ingest_bytes(vs, file.name, file.getvalue())
                if report.skipped:
                    st.write(f"⚠️ **{report.source}**: {report.reason}")
                else:
                    st.write(
                        f"✅ **{report.source}**: {report.pages} página(s) → "
                        f"{report.chunks} chunk(s)"
                    )
                    analytics.log_event(
                        "ingest", source=report.source, pages=report.pages, chunks=report.chunks
                    )
            status.update(label="Indexação concluída", state="complete")

    total_chunks = count_chunks(vs)
    st.caption(f"📚 Base de conhecimento: **{total_chunks}** chunks indexados.")

# ------------------------------------------------------------------- main --
st.title("⚖️ Themis.IA")
st.caption(ui.APP_TAGLINE)

pending_prompt: str | None = None
if not chat["messages"]:
    st.markdown("### Como posso ajudar hoje?")
    columns = st.columns(len(SUGGESTIONS))
    for column, (label, (suggestion, suggested_persona)) in zip(columns, SUGGESTIONS.items()):
        if column.button(label, width="stretch"):
            pending_prompt = suggestion
            persona_key = suggested_persona

for i, message in enumerate(chat["messages"]):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            sources = message.get("sources") or []
            lexml_records = message.get("lexml_records") or []
            lexml_note = message.get("lexml_note", "")
            if sources or lexml_records or lexml_note:
                with st.expander(
                    f"📖 Fontes ({len(sources)} trecho(s) dos autos"
                    + (f", {len(lexml_records)} resultado(s) LexML" if lexml_records else "")
                    + ")"
                ):
                    for src_item in sources:
                        st.markdown(
                            f"**[{src_item['source']}, p. {src_item['page']}]** "
                            f"(relevância {src_item['score']:.2f})\n\n> {src_item['snippet']}"
                        )
                    if lexml_records:
                        st.markdown("**Resultados LexML:**")
                        for rec in lexml_records:
                            line = f"- [{rec['title']}]({rec['url']})" if rec["url"] else f"- {rec['title']}"
                            if rec["urn"]:
                                line += f" — `{rec['urn']}`"
                            st.markdown(line)
                    if lexml_note:
                        st.info(lexml_note, icon="🌐")
            st.download_button(
                "⬇️ Exportar .docx",
                data=answer_to_docx_bytes(
                    chat["title"], message["content"], PERSONAS[message.get("persona", persona_key)].label
                ),
                file_name=f"themis_resposta_{i + 1}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"docx_{active_id}_{i}",
            )

typed_prompt = st.chat_input("Pergunte algo sobre os documentos indexados…")
prompt = typed_prompt or pending_prompt

if prompt:
    if chat["title"] == "Novo chat":
        chat["title"] = prompt[:48] + ("…" if len(prompt) > 48 else "")
    chat["messages"].append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Analisando os autos…"):
                history = [
                    (m["role"], m["content"])
                    for m in chat["messages"][:-1]
                    if m["role"] in {"user", "assistant"}
                ]
                response = engine.answer_question(
                    vs,
                    prompt,
                    persona_key=persona_key,
                    history=history,
                    lexml_mode=lexml_mode,
                )
        except engine.MissingAPIKeyError as exc:
            st.error(str(exc), icon="🔑")
            chat["messages"].pop()
            st.stop()
        except Exception as exc:  # ex.: cota da API, rede
            st.error(f"Falha ao gerar a resposta: {exc}", icon="⚠️")
            chat["messages"].pop()
            st.stop()

    lexml_note = ""
    if response.lexml_result and (response.lexml_result.blocked or response.lexml_result.error):
        lexml_note = (
            f"Busca LexML indisponível ({response.lexml_result.error}). "
            "A resposta usou apenas os documentos locais."
        )

    chat["messages"].append(
        {
            "role": "assistant",
            "content": response.answer,
            "persona": persona_key,
            "sources": [
                {
                    "source": c.source,
                    "page": c.page,
                    "score": c.score,
                    "snippet": (c.text[:300] + "…") if len(c.text) > 300 else c.text,
                }
                for c in response.sources
            ],
            "lexml_records": [
                {"title": r.title, "urn": r.urn, "url": r.url}
                for r in (response.lexml_result.records if response.lexml_result else [])
            ],
            "lexml_note": lexml_note,
            "latency_s": response.latency_total_s,
        }
    )
    st.rerun()

st.divider()
ui.disclaimer_footer()
