"""Motor RAG do Themis.IA: recuperação → roteamento de ferramentas → geração.

O fluxo espelha o pipeline documentado: a pergunta do usuário passa pela
recuperação semântica (ChromaDB), o roteador determinístico decide se a busca
LexML é acionada, e o Gemini gera a resposta aterrada nas fontes, sob o system
prompt da persona ativa.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src import analytics
from src.config import settings
from src.rag.personas import DEFAULT_PERSONA, PERSONAS
from src.rag.retriever import RetrievedChunk, retrieve, trim_to_budget
from src.tools import lexml


class MissingAPIKeyError(RuntimeError):
    """GOOGLE_API_KEY ausente — a geração com Gemini não pode ser executada."""


@dataclass
class RagResponse:
    answer: str
    persona: str
    sources: list[RetrievedChunk] = field(default_factory=list)
    lexml_result: lexml.LexmlResult | None = None
    latency_total_s: float = 0.0
    latency_llm_s: float = 0.0

    @property
    def lexml_used(self) -> bool:
        return self.lexml_result is not None


def get_llm(temperature: float | None = None):
    if not settings.google_api_key:
        raise MissingAPIKeyError(
            "Defina GOOGLE_API_KEY no arquivo .env (chave do Google AI Studio) "
            "para habilitar a geração com o Gemini."
        )
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.temperature if temperature is None else temperature,
        google_api_key=settings.google_api_key,
    )


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(nenhum trecho recuperado — a base de conhecimento está vazia ou nada foi relevante)"
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        blocks.append(f"[{i}] ({chunk.citation} — relevância {chunk.score:.2f})\n{chunk.text}")
    return "\n\n".join(blocks)


def format_lexml(result: lexml.LexmlResult | None) -> str:
    if result is None:
        return "(busca não acionada para esta pergunta)"
    if result.blocked or result.error:
        return f"(busca indisponível: {result.error})"
    if not result.records:
        return f"(nenhum resultado para a consulta '{result.query}')"
    lines = []
    for rec in result.records:
        parts = [f"- {rec.title}"]
        if rec.doc_type:
            parts.append(f"  Tipo: {rec.doc_type}")
        if rec.date:
            parts.append(f"  Data: {rec.date}")
        if rec.urn:
            parts.append(f"  URN: {rec.urn}")
        if rec.url:
            parts.append(f"  URL: {rec.url}")
        if rec.description:
            parts.append(f"  Ementa: {rec.description}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def build_user_prompt(
    question: str,
    chunks: list[RetrievedChunk],
    lexml_result: lexml.LexmlResult | None,
) -> str:
    return (
        "## Contexto dos autos (trechos recuperados da base vetorial)\n"
        f"{format_context(chunks)}\n\n"
        "## Jurisprudência e legislação (LexML)\n"
        f"{format_lexml(lexml_result)}\n\n"
        "## Pergunta do usuário\n"
        f"{question.strip()}"
    )


def build_messages(
    persona_key: str,
    question: str,
    chunks: list[RetrievedChunk],
    lexml_result: lexml.LexmlResult | None,
    history: list[tuple[str, str]] | None = None,
):
    """Monta as mensagens: system (persona + aterramento), histórico e pergunta."""
    persona = PERSONAS.get(persona_key, PERSONAS[DEFAULT_PERSONA])
    messages: list = [SystemMessage(content=persona.full_system_prompt())]
    for role, content in (history or [])[-settings.max_history_turns * 2 :]:
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=build_user_prompt(question, chunks, lexml_result)))
    return messages


def answer_question(
    vs,
    question: str,
    *,
    persona_key: str = DEFAULT_PERSONA,
    history: list[tuple[str, str]] | None = None,
    lexml_mode: str = "auto",
    k: int | None = None,
    log: bool = True,
) -> RagResponse:
    """Executa o pipeline RAG completo para uma pergunta."""
    start = time.perf_counter()

    chunks = trim_to_budget(retrieve(vs, question, k=k))

    lexml_result: lexml.LexmlResult | None = None
    if lexml.should_search(question, persona_key, lexml_mode):
        lexml_result = lexml.search(question)

    llm = get_llm()
    messages = build_messages(persona_key, question, chunks, lexml_result, history)

    llm_start = time.perf_counter()
    ai_message = llm.invoke(messages)
    llm_end = time.perf_counter()

    answer = ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content)
    response = RagResponse(
        answer=answer,
        persona=persona_key,
        sources=chunks,
        lexml_result=lexml_result,
        latency_total_s=round(llm_end - start, 3),
        latency_llm_s=round(llm_end - llm_start, 3),
    )

    if log:
        analytics.log_event(
            "query",
            persona=persona_key,
            lexml_mode=lexml_mode,
            lexml_used=response.lexml_used,
            lexml_hits=len(lexml_result.records) if lexml_result else 0,
            lexml_blocked=bool(lexml_result and lexml_result.blocked),
            n_sources=len(chunks),
            latency_total_s=response.latency_total_s,
            latency_llm_s=response.latency_llm_s,
            question_chars=len(question),
            answer_chars=len(answer),
            model=settings.gemini_model,
        )
    return response


def answer_baseline(question: str, *, log: bool = False) -> tuple[str, float]:
    """Baseline sem RAG (LLM puro), usado pelo protocolo de avaliação."""
    llm = get_llm()
    start = time.perf_counter()
    ai_message = llm.invoke(
        [
            SystemMessage(
                content=(
                    "Você é um assistente jurídico brasileiro. Responda à pergunta da melhor "
                    "forma possível, em português do Brasil."
                )
            ),
            HumanMessage(content=question),
        ]
    )
    latency = round(time.perf_counter() - start, 3)
    answer = ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content)
    if log:
        analytics.log_event("baseline_query", latency_total_s=latency, question_chars=len(question))
    return answer, latency
