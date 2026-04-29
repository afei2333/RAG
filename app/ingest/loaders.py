from __future__ import annotations

from pathlib import Path

from app.core.config import settings


class UnsupportedFileTypeError(ValueError):
    pass


def load_document(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return _load_text(path)
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")


def _load_text(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [{"text": text, "page_number": None}]


def _load_pdf(path: Path) -> list[dict]:
    parser = settings.pdf_parser.lower()
    if parser == "docling":
        try:
            return _load_pdf_with_docling(path)
        except Exception:
            if settings.pdf_fallback_parser.lower() != "pypdf":
                raise
            return _load_pdf_with_pypdf(path)
    if parser == "pypdf":
        return _load_pdf_with_pypdf(path)
    raise ValueError(f"Unsupported PDF parser: {settings.pdf_parser}")


def _load_pdf_with_docling(path: Path) -> list[dict]:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError("Advanced PDF parsing requires package: docling") from exc

    converter = DocumentConverter()
    result = converter.convert(str(path))
    markdown = result.document.export_to_markdown()
    return [{"text": markdown, "page_number": None}]


def _load_pdf_with_pypdf(path: Path) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF parsing requires package: pypdf") from exc

    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append(
            {
                "text": page.extract_text() or "",
                "page_number": index,
            }
        )
    return pages


def _load_docx(path: Path) -> list[dict]:
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise RuntimeError("DOCX parsing requires package: python-docx") from exc

    document = Document(str(path))
    blocks = []
    for block in _iter_docx_blocks(document, Paragraph, Table):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                blocks.append(text)
        elif isinstance(block, Table):
            table = _docx_table_to_markdown(block)
            if table:
                blocks.append(table)
    text = "\n\n".join(blocks)
    return [{"text": text, "page_number": None}]


def _iter_docx_blocks(document, paragraph_cls, table_cls):
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield paragraph_cls(child, document)
        elif child.tag.endswith("}tbl"):
            yield table_cls(child, document)


def _docx_table_to_markdown(table) -> str:
    rows = [
        [_normalize_table_cell(cell.text) for cell in row.cells]
        for row in table.rows
    ]
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    separator = ["---"] * width
    body = rows[1:]
    markdown_rows = [header, separator, *body]
    return "\n".join(
        "| " + " | ".join(_escape_markdown_table_cell(cell) for cell in row) + " |"
        for row in markdown_rows
    )


def _normalize_table_cell(value: str) -> str:
    return " ".join(value.split())


def _escape_markdown_table_cell(value: str) -> str:
    return value.replace("|", "\\|")
