"""Componentes de interface compartilhados entre as páginas do Streamlit."""

from __future__ import annotations

import streamlit as st

from src import auth
from src.config import settings
from src.rag.vector_store import get_vector_store

APP_TITLE = "Themis.IA"
APP_TAGLINE = "A sua inteligência artificial jurídica."
DISCLAIMER = (
    "⚖️ As teses e redações geradas não substituem a análise humana rigorosa "
    "de um(a) advogado(a) responsável."
)


@st.cache_resource(show_spinner="Carregando modelo de embeddings…")
def cached_vector_store():
    return get_vector_store()


def require_login() -> None:
    """Bloqueia a página até o usuário autenticar; interrompe o render se não logado."""
    if st.session_state.get("authenticated"):
        return

    st.title(f"🏛️ {APP_TITLE}")
    st.caption(APP_TAGLINE)
    st.markdown(
        "Analise processos volumosos, pesquise jurisprudência atualizada e crie "
        "teses jurídicas com a precisão da IA generativa — com respostas sempre "
        "aterradas nos seus documentos."
    )

    with st.form("login"):
        st.subheader("Entrar no Themis.IA")
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Continuar", width="stretch")

    if submitted:
        if auth.verify_credentials(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username.strip()
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

    if auth.using_default_password():
        st.info(
            "Instalação com credenciais padrão (`admin` / `themis123`). "
            "Defina `APP_USERNAME` e `APP_PASSWORD` no arquivo `.env` para alterá-las."
        )
    st.stop()


def sidebar_user_info() -> None:
    with st.sidebar:
        col_user, col_logout = st.columns([3, 1])
        col_user.markdown(f"👤 **{st.session_state.get('username', 'usuário')}**")
        if col_logout.button("Sair", width="stretch"):
            st.session_state.clear()
            st.rerun()
        if auth.using_default_password():
            st.warning("Senha padrão em uso — altere no `.env`.", icon="🔐")
        if not settings.google_api_key:
            st.error("`GOOGLE_API_KEY` não configurada — o chat não poderá responder.", icon="🔑")


def disclaimer_footer() -> None:
    st.caption(DISCLAIMER)
