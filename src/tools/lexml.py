"""Cliente da API SRU oficial do LexML (https://www.lexml.gov.br/busca/SRU).

Evolução sobre o design original (scraping HTML com BeautifulSoup): o SRU é o
protocolo público de busca do LexML e devolve XML estruturado (Dublin Core),
mais estável que raspar a página de resultados.

Observação operacional: o portal LexML pode interpor um desafio anti-bot
(proof-of-work em JavaScript) para clientes não navegadores. Por isso o
cliente degrada graciosamente: qualquer resposta que não seja XML SRU válido
resulta em lista vazia com `blocked=True`, e a aplicação informa o usuário em
vez de falhar.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests

from src.config import settings

SRU_ENDPOINT = "https://www.lexml.gov.br/busca/SRU"
USER_AGENT = "ThemisIA/1.0 (projeto academico; cliente SRU)"

# Termos que indicam intenção de pesquisa normativa/jurisprudencial (roteador "auto").
_JURIS_HINTS = (
    "jurisprud",
    "súmula",
    "sumula",
    "acórdão",
    "acordao",
    "precedente",
    "entendimento do",
    "stf",
    "stj",
    "tst",
    "trf",
    "lei n",
    "lei nº",
    "código",
    "codigo",
    "constituição",
    "constituicao",
    "cf/88",
    "decreto",
    "medida provisória",
    "habeas corpus",
    "repercussão geral",
)

_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob", "sobre",
    "que", "qual", "quais", "quem", "quando", "onde", "como", "porque", "por que",
    "e", "ou", "mas", "se", "ao", "aos", "à", "às", "é", "são", "ser", "foi", "há",
    "me", "minha", "meu", "sua", "seu", "este", "esta", "isso", "isto", "esse", "essa",
    "existe", "existem", "pode", "podem", "deve", "devem", "fale", "diga", "explique",
    "qualquer", "algum", "alguma", "recente", "recentes", "atual", "atuais",
}


@dataclass
class LexmlRecord:
    title: str
    urn: str
    url: str
    date: str = ""
    doc_type: str = ""
    description: str = ""


@dataclass
class LexmlResult:
    query: str
    records: list[LexmlRecord] = field(default_factory=list)
    blocked: bool = False
    error: str = ""


def should_search(question: str, persona_key: str, mode: str = "auto") -> bool:
    """Roteador determinístico: decide se a busca LexML deve ser acionada.

    mode: "sempre" | "nunca" | "auto" (persona Pesquisador ou heurística de termos).
    """
    mode = (mode or "auto").lower()
    if mode == "sempre":
        return True
    if mode == "nunca":
        return False
    if persona_key == "pesquisador":
        return True
    question_lower = question.lower()
    return any(hint in question_lower for hint in _JURIS_HINTS)


def build_query(question: str, max_terms: int = 6) -> str:
    """Converte a pergunta em consulta CQL simples (termos relevantes sem stopwords)."""
    words = re.findall(r"[\wÀ-ÿ]{3,}", question.lower())
    terms = [w for w in words if w not in _STOPWORDS]
    seen: set[str] = set()
    unique_terms = [t for t in terms if not (t in seen or seen.add(t))]
    return " ".join(unique_terms[:max_terms]) or question.strip()


def search(question: str, *, max_records: int | None = None, timeout: int | None = None) -> LexmlResult:
    """Consulta o SRU do LexML; nunca levanta exceção (degradação graciosa)."""
    query = build_query(question)
    result = LexmlResult(query=query)
    params = {
        "operation": "searchRetrieve",
        "version": "1.1",
        "query": query,
        "startRecord": "1",
        "maximumRecords": str(max_records or settings.lexml_max_records),
    }
    try:
        response = requests.get(
            SRU_ENDPOINT,
            params=params,
            timeout=timeout or settings.lexml_timeout_s,
            headers={"User-Agent": USER_AGENT, "Accept": "text/xml, application/xml"},
        )
        response.raise_for_status()
        body = response.text
    except requests.RequestException as exc:
        result.error = f"falha de rede ao consultar o LexML: {exc.__class__.__name__}"
        return result

    if "<" not in body or "searchRetrieveResponse" not in body:
        # Página de desafio anti-bot ou HTML inesperado no lugar do XML SRU.
        result.blocked = True
        result.error = "o portal LexML bloqueou o acesso automatizado (desafio anti-bot)"
        return result

    try:
        result.records = parse_sru_response(body)[: max_records or settings.lexml_max_records]
    except ET.ParseError:
        result.error = "resposta XML do LexML malformada"
    return result


def parse_sru_response(xml_text: str) -> list[LexmlRecord]:
    """Extrai registros Dublin Core da resposta SRU, tolerante a namespaces."""
    root = ET.fromstring(xml_text)
    records: list[LexmlRecord] = []
    for record_el in _iter_local(root, "record"):
        fields: dict[str, list[str]] = {}
        for el in record_el.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            if el.text and el.text.strip():
                fields.setdefault(tag, []).append(el.text.strip())

        identifiers = fields.get("urn", []) + fields.get("identifier", [])
        urn = next((v for v in identifiers if v.startswith("urn:")), "")
        http_url = next((v for v in identifiers if v.startswith("http")), "")
        url = http_url or (f"https://www.lexml.gov.br/urn/{urn}" if urn else "")

        title = (fields.get("title") or [""])[0]
        if not (title or urn):
            continue
        records.append(
            LexmlRecord(
                title=title or urn,
                urn=urn,
                url=url,
                date=(fields.get("date") or [""])[0],
                doc_type=(fields.get("type") or [""])[0],
                description=(fields.get("description") or [""])[0][:500],
            )
        )
    return records


def _iter_local(root: ET.Element, local_name: str):
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == local_name:
            yield el
