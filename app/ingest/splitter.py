from __future__ import annotations

from collections import Counter
import re
from uuid import uuid4

from app.core.config import settings


NOISE_LINE_PATTERNS = [
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*(arxiv|doi:|copyright|©|all rights reserved)\b", re.IGNORECASE),
    re.compile(r"^\s*(preprint|accepted manuscript|author manuscript)\b", re.IGNORECASE),
]

SECTION_HEADING_RE = re.compile(
    r"^(#{1,6}\s+.+|(?:\d+(?:\.\d+)*)\.?\s+[A-Z][^\n]{2,100}|"
    r"(abstract|introduction|related work|background|method|methods|"
    r"experiments?|results?|discussion|conclusion|references|bibliography|"
    r"acknowledg(e)?ments?|appendix)\b.*)$",
    re.IGNORECASE,
)

REFERENCE_HEADING_RE = re.compile(r"^(#+\s+)?(references|bibliography)\b", re.IGNORECASE)


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = _merge_wrapped_lines(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_pages(
    pages: list[dict],
    *,
    source_name: str,
    document_id: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict]:
    size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap
    if overlap >= size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    repeated_lines = _find_repeated_lines(pages)
    chunks: list[dict] = []
    for page in pages:
        text = clean_text(_remove_noise_lines(page.get("text", ""), repeated_lines))
        if not text:
            continue
        sections = _split_into_sections(text)
        skip_front_matter = _has_body_heading(sections)
        for section_number, (section_title, section_text) in enumerate(sections):
            if section_number == 0 and section_title is None and skip_front_matter:
                continue
            content_type = _content_type_for_section(section_title)
            if content_type == "references":
                continue
            for segment_type, segment_text in _split_markdown_table_segments(section_text):
                if segment_type == "table":
                    _append_chunk(
                        chunks,
                        content=segment_text,
                        document_id=document_id,
                        page_number=page.get("page_number"),
                        source_name=source_name,
                        section_title=section_title,
                        content_type="table",
                    )
                    continue

                start = 0
                while start < len(segment_text):
                    end = _choose_chunk_end(segment_text, start, size)
                    content = segment_text[start:end].strip()
                    if content and _is_useful_chunk(content):
                        _append_chunk(
                            chunks,
                            content=content,
                            document_id=document_id,
                            page_number=page.get("page_number"),
                            source_name=source_name,
                            section_title=section_title,
                            content_type=content_type,
                        )
                    if start + size >= len(segment_text):
                        break
                    start = max(end - overlap, start + 1)
    return chunks


def _append_chunk(
    chunks: list[dict],
    *,
    content: str,
    document_id: str,
    page_number: int | None,
    source_name: str,
    section_title: str | None,
    content_type: str,
) -> None:
    chunks.append(
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "content": content,
            "chunk_index": len(chunks),
            "page_number": page_number,
            "source_name": source_name,
            "metadata": {
                "section_title": section_title,
                "content_type": content_type,
            },
        }
    )


def _merge_wrapped_lines(text: str) -> str:
    lines = text.splitlines()
    merged: list[str] = []
    for line in lines:
        current = line.strip()
        if not current:
            merged.append("")
            continue
        if not merged or merged[-1] == "":
            merged.append(current)
            continue
        previous = merged[-1]
        keep_break = (
            previous.startswith("#")
            or current.startswith("#")
            or previous.startswith(("- ", "* "))
            or current.startswith(("- ", "* "))
            or previous.startswith("|")
            or current.startswith("|")
            or previous.endswith((".", "?", "!", ":", ";", "。", "？", "！", "：", "；"))
            or SECTION_HEADING_RE.match(previous)
            or SECTION_HEADING_RE.match(current)
        )
        if keep_break:
            merged.append(current)
        else:
            merged[-1] = f"{previous} {current}"
    return "\n".join(merged)


def _find_repeated_lines(pages: list[dict]) -> set[str]:
    normalized_by_page = []
    for page in pages:
        lines = {
            _normalize_noise_line(line)
            for line in page.get("text", "").splitlines()
            if _normalize_noise_line(line)
        }
        normalized_by_page.append(lines)

    counts = Counter(line for lines in normalized_by_page for line in lines)
    min_occurrences = max(2 if len(pages) < 5 else 3, int(len(pages) * 0.35))
    return {
        line
        for line, count in counts.items()
        if count >= min_occurrences and 4 <= len(line) <= 120
    }


def _remove_noise_lines(text: str, repeated_lines: set[str]) -> str:
    cleaned = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        normalized = _normalize_noise_line(line)
        if not line:
            cleaned.append("")
            continue
        if normalized in repeated_lines:
            continue
        if any(pattern.search(line) for pattern in NOISE_LINE_PATTERNS):
            continue
        if _looks_like_footnote(line):
            continue
        cleaned.append(raw_line)
    return "\n".join(cleaned)


def _normalize_noise_line(line: str) -> str:
    line = re.sub(r"\d+", "#", line.strip().lower())
    line = re.sub(r"\s+", " ", line)
    return line


def _looks_like_footnote(line: str) -> bool:
    if len(line) > 180:
        return False
    return bool(
        re.match(r"^(\*|†|‡|\d+|\[\d+\])\s+", line)
        and re.search(r"\b(email|correspond|http|www\.|university|institute)\b", line, re.I)
    )


def _split_into_sections(text: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and SECTION_HEADING_RE.match(line):
            if current_lines:
                sections.append((current_title, current_lines))
                current_lines = []
            current_title = _normalize_heading(line)
        current_lines.append(raw_line)

    if current_lines:
        sections.append((current_title, current_lines))

    return [
        (title, "\n".join(lines).strip())
        for title, lines in sections
        if "\n".join(lines).strip()
    ]


def _split_markdown_table_segments(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    segments: list[tuple[str, str]] = []
    buffer: list[str] = []
    index = 0

    while index < len(lines):
        if _is_markdown_table_start(lines, index):
            caption = _pop_table_caption(buffer)
            if buffer:
                segments.append(("text", "\n".join(buffer).strip()))
                buffer = []

            table_lines = caption
            while index < len(lines) and _looks_like_table_line(lines[index]):
                table_lines.append(lines[index])
                index += 1
            segments.append(("table", "\n".join(table_lines).strip()))
            continue

        buffer.append(lines[index])
        index += 1

    if buffer:
        segments.append(("text", "\n".join(buffer).strip()))
    return [(kind, value) for kind, value in segments if value]


def _is_markdown_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return _looks_like_table_line(lines[index]) and _is_markdown_table_separator(lines[index + 1])


def _looks_like_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.count("|") >= 2


def _is_markdown_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|")
    if not stripped:
        return False
    cells = [cell.strip() for cell in stripped.split("|")]
    return all(re.match(r"^:?-{3,}:?$", cell) for cell in cells)


def _pop_table_caption(buffer: list[str]) -> list[str]:
    if not buffer:
        return []
    caption = buffer[-1].strip()
    if re.match(r"^(table|tab\.|表)\s*\d*[:：.]?", caption, re.I):
        buffer.pop()
        return [caption]
    return []


def _normalize_heading(line: str) -> str:
    line = re.sub(r"^#{1,6}\s*", "", line.strip())
    return re.sub(r"\s+", " ", line)


def _content_type_for_section(section_title: str | None) -> str:
    if not section_title:
        return "body"
    if REFERENCE_HEADING_RE.match(section_title):
        return "references"
    if re.search(r"\b(abstract|introduction|method|experiment|result|discussion|conclusion)\b", section_title, re.I):
        return "body"
    if re.search(r"\b(acknowledg(e)?ments?|appendix)\b", section_title, re.I):
        return "supplement"
    return "body"


def _has_body_heading(sections: list[tuple[str | None, str]]) -> bool:
    return any(
        title
        and re.search(
            r"\b(abstract|introduction|background|method|experiment|result|discussion|conclusion)\b",
            title,
            re.I,
        )
        for title, _ in sections
    )


def _is_useful_chunk(content: str) -> bool:
    if len(content) < settings.min_chunk_chars:
        return False
    alpha_count = sum(1 for char in content if char.isalpha())
    if alpha_count < len(content) * 0.35:
        return False
    citation_like = len(re.findall(r"\[\d+\]|\(\w+ et al\.,? \d{4}\)", content))
    if citation_like >= 8 and len(content) < 500:
        return False
    return True


def _choose_chunk_end(text: str, start: int, chunk_size: int) -> int:
    hard_end = min(start + chunk_size, len(text))
    if hard_end == len(text):
        return hard_end

    window = text[start:hard_end]
    markdown_boundaries = [
        window.rfind("\n## "),
        window.rfind("\n### "),
        window.rfind("\n|"),
        window.rfind("\n\n"),
        window.rfind(". "),
        window.rfind("。"),
    ]
    best = max(markdown_boundaries)
    min_reasonable = int(chunk_size * 0.55)
    if best >= min_reasonable:
        return start + best + 1
    return hard_end
