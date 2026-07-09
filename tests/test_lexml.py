from src.tools import lexml

SRU_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">
  <srw:version>1.1</srw:version>
  <srw:numberOfRecords>2</srw:numberOfRecords>
  <srw:records>
    <srw:record>
      <srw:recordData>
        <srw_dc:dc xmlns:srw_dc="info:srw/schema/1/dc-schema"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
          <urn>urn:lex:br:federal:lei:2018-08-14;13709</urn>
          <dc:title>Lei nº 13.709, de 14 de Agosto de 2018</dc:title>
          <dc:date>2018-08-14</dc:date>
          <dc:type>Lei</dc:type>
          <dc:description>Lei Geral de Proteção de Dados Pessoais (LGPD).</dc:description>
        </srw_dc:dc>
      </srw:recordData>
    </srw:record>
    <srw:record>
      <srw:recordData>
        <srw_dc:dc xmlns:srw_dc="info:srw/schema/1/dc-schema"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:identifier>https://www.lexml.gov.br/urn/urn:lex:br:federal:constituicao:1988-10-05;1988</dc:identifier>
          <dc:title>Constituição da República Federativa do Brasil de 1988</dc:title>
        </srw_dc:dc>
      </srw:recordData>
    </srw:record>
  </srw:records>
</srw:searchRetrieveResponse>
"""


def test_parse_sru_response():
    records = lexml.parse_sru_response(SRU_FIXTURE)
    assert len(records) == 2
    first = records[0]
    assert first.urn == "urn:lex:br:federal:lei:2018-08-14;13709"
    assert first.url.endswith(first.urn)
    assert "13.709" in first.title
    assert first.doc_type == "Lei"
    second = records[1]
    assert second.url.startswith("https://www.lexml.gov.br/urn/")


def test_build_query_removes_stopwords():
    query = lexml.build_query("Qual é a jurisprudência recente do STJ sobre prisão preventiva?")
    assert "qual" not in query.split()
    assert "jurisprudência" in query
    assert "preventiva" in query


def test_should_search_router():
    assert lexml.should_search("qualquer coisa", "analista", "sempre")
    assert not lexml.should_search("qualquer coisa", "pesquisador", "nunca")
    assert lexml.should_search("qualquer coisa", "pesquisador", "auto")
    assert lexml.should_search("Existe súmula sobre o tema?", "analista", "auto")
    assert not lexml.should_search("Resuma os fatos do documento.", "analista", "auto")


def test_search_degrades_gracefully_on_challenge(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "<!DOCTYPE html><title>I Challenge Thee</title>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(lexml.requests, "get", lambda *a, **kw: FakeResponse())
    result = lexml.search("jurisprudência sobre prisão preventiva")
    assert result.blocked
    assert result.records == []
    assert "anti-bot" in result.error
