from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.ingest.splitter import clean_text


FIGURE_CAPTION_RE = re.compile(
    r"(?im)^\s*(fig(?:ure)?\.?\s*\d+[a-z]?[.:)\-]?\s+.+)$"
)
MAX_CONTEXT_CHARS = 1200


def extract_pdf_figures(
    pdf_path: Path,
    *,
    pages: list[dict],
    source_name: str,
    document_id: str,
    start_index: int,
) -> list[dict]:
    if pdf_path.suffix.lower() != ".pdf":
        return []

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Figure extraction requires package: pypdf") from exc

    figures_dir = settings.storage_dir / document_id / "figures"
    reader = PdfReader(str(pdf_path))
    figure_chunks: list[dict] = []

    for page_index, page in enumerate(reader.pages, start=1):
        images = list(getattr(page, "images", []) or [])
        if not images:
            continue

        page_info = _page_info_for_number(pages, page_index)
        page_text = clean_text(page.extract_text() or "")
        if not page_text and page_info:
            page_text = clean_text(page_info.get("text", ""))
        captions = _extract_captions(page_text)
        context = _compact_context(page_text)

        for image_index, image in enumerate(images, start=1):
            image_data = getattr(image, "data", None)
            if not image_data:
                continue

            figures_dir.mkdir(parents=True, exist_ok=True)
            image_ext = _image_extension(getattr(image, "name", ""))
            image_name = f"figure_{page_index}_{image_index}{image_ext}"
            image_path = figures_dir / image_name
            image_path.write_bytes(image_data)

            caption = _caption_for_image(captions, image_index)
            content = _figure_content(
                page_number=page_index,
                figure_index=image_index,
                caption=caption,
                context=context,
            )
            figure_chunks.append(
                {
                    "id": str(uuid4()),
                    "document_id": document_id,
                    "content": content,
                    "chunk_index": start_index + len(figure_chunks),
                    "page_number": page_index,
                    "source_name": source_name,
                    "metadata": {
                        "content_type": "figure",
                        "figure_index": image_index,
                        "caption": caption,
                        "image_path": str(image_path),
                        "image_url": f"/uploads/{document_id}/figures/{image_name}",
                    },
                }
            )

    return figure_chunks


def _page_info_for_number(pages: list[dict], page_number: int) -> dict | None:
    for page in pages:
        if page.get("page_number") == page_number:
            return page
    if len(pages) == 1 and pages[0].get("page_number") is None:
        return pages[0]
    return None


def _extract_captions(text: str) -> list[str]:
    captions = []
    for match in FIGURE_CAPTION_RE.finditer(text):
        caption = re.sub(r"\s+", " ", match.group(1)).strip()
        if caption:
            captions.append(caption)
    return captions


def _caption_for_image(captions: list[str], image_index: int) -> str:
    if not captions:
        return ""
    return captions[min(image_index - 1, len(captions) - 1)]


def _compact_context(text: str) -> str:
    if len(text) <= MAX_CONTEXT_CHARS:
        return text
    return text[:MAX_CONTEXT_CHARS].rsplit(" ", 1)[0].strip()


def _figure_content(
    *,
    page_number: int,
    figure_index: int,
    caption: str,
    context: str,
) -> str:
    parts = [f"Figure image on page {page_number}, image {figure_index}."]
    if caption:
        parts.append(f"Caption: {caption}")
    if context:
        parts.append(f"Page context: {context}")
    return "\n".join(parts)


def _image_extension(name: str) -> str:
    suffix = Path(name).suffix.lower()
    supported_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".tiff",
        ".tif",
    }
    if suffix in supported_extensions:
        return suffix
    return ".png"
