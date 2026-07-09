import io

import fitz
import pytest
from docx import Document

from src.ingestion.extractors import (
    PageText,
    UnsupportedFormatError,
    extract_document,
    remove_boilerplate,
)


def _build_pdf(pages_text: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _build_docx(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_extract_pdf_pages():
    data = _build_pdf(["Primeira página do processo.", "Segunda página do processo."])
    pages = extract_document("processo.pdf", data)
    assert len(pages) == 2
    assert "Primeira página" in pages[0].text
    assert pages[1].page == 2


def test_extract_docx():
    data = _build_docx(["Petição inicial.", "Dos fatos e fundamentos."])
    pages = extract_document("peticao.docx", data)
    assert len(pages) == 1
    assert "Dos fatos" in pages[0].text


def test_extract_txt():
    pages = extract_document("nota.txt", "Texto simples.".encode())
    assert pages[0].text == "Texto simples."


def test_unsupported_extension():
    with pytest.raises(UnsupportedFormatError):
        extract_document("planilha.xlsx", b"...")


def test_remove_boilerplate_strips_headers_and_page_numbers():
    header = "TRIBUNAL DE JUSTIÇA — 3ª VARA"
    pages = [
        PageText(page=i, text=f"{header}\nConteúdo relevante da página {i}.\n{i}")
        for i in range(1, 5)
    ]
    cleaned = remove_boilerplate(pages)
    for page in cleaned:
        assert header not in page.text
        assert "Conteúdo relevante" in page.text
        assert not page.text.splitlines()[-1].strip().isdigit()
