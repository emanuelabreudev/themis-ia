from src.rag.engine import build_messages, build_user_prompt
from src.rag.personas import GROUNDING_RULES, PERSONAS
from src.rag.retriever import RetrievedChunk
from src.tools.lexml import LexmlRecord, LexmlResult


def test_all_personas_complete():
    assert len(PERSONAS) == 6
    for persona in PERSONAS.values():
        assert persona.label and persona.description and persona.system_prompt
        assert "ATERRAMENTO" in persona.full_system_prompt()


def test_grounding_rules_forbid_hallucination():
    assert "EXCLUSIVAMENTE" in GROUNDING_RULES
    assert "Não encontrei essa informação" in GROUNDING_RULES


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(text="O valor mensal é R$ 12.000,00.", source="contrato.pdf", page=2, score=0.91)


def test_user_prompt_includes_context_and_citations():
    prompt = build_user_prompt("Qual o valor mensal?", [_chunk()], None)
    assert "contrato.pdf, p. 2" in prompt
    assert "R$ 12.000,00" in prompt
    assert "Qual o valor mensal?" in prompt
    assert "busca não acionada" in prompt


def test_user_prompt_reports_empty_base():
    prompt = build_user_prompt("Pergunta", [], None)
    assert "base de conhecimento está vazia" in prompt


def test_user_prompt_includes_lexml_records():
    result = LexmlResult(
        query="lgpd",
        records=[
            LexmlRecord(
                title="Lei nº 13.709/2018",
                urn="urn:lex:br:federal:lei:2018-08-14;13709",
                url="https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2018-08-14;13709",
                date="2018-08-14",
            )
        ],
    )
    prompt = build_user_prompt("O que diz a LGPD?", [], result)
    assert "urn:lex:br:federal:lei:2018-08-14;13709" in prompt


def test_build_messages_structure_and_history_cap():
    history = [("user", f"pergunta {i}") if i % 2 == 0 else ("assistant", f"resposta {i}") for i in range(40)]
    messages = build_messages("analista", "Pergunta final", [_chunk()], None, history)
    # system + histórico limitado + pergunta atual
    assert messages[0].type == "system"
    assert messages[-1].type == "human"
    assert "Pergunta final" in messages[-1].content
    from src.config import settings

    assert len(messages) <= 2 + settings.max_history_turns * 2
