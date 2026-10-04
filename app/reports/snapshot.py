"""The free preview of a Word proposal: its outline and opening paragraph, never the document.

Built from the rendered DOCX so a freshly generated report and one read back from the cache produce
the same snapshot.
"""

import io
import re
from typing import Any, Dict, List

from docx import Document

OPENING_MIN_WORDS = 20
OPENING_MAX_CHARS = 700
IN_TEXT_CITATION = re.compile(r"\([^()]*\b(?:19|20)\d{2}[a-z]?[^()]*\)")


def _trim_to_sentence(text: str) -> str:
    if len(text) <= OPENING_MAX_CHARS:
        return text
    cut = text[:OPENING_MAX_CHARS]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > OPENING_MAX_CHARS // 2 else cut.rstrip() + "…"


def snapshot_from_docx(document_bytes: bytes) -> Dict[str, Any]:
    document = Document(io.BytesIO(document_bytes))
    title = ""
    opening = ""
    sections: List[Dict[str, Any]] = []
    current = None
    in_references = False
    reference_count = 0
    citation_count = 0

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        style = paragraph.style.name or ""
        if style.startswith("Heading"):
            level = int(style.split()[-1]) if style.split()[-1].isdigit() else 1
            current = {"title": text, "level": level, "words": 0}
            sections.append(current)
            in_references = text.lower() == "references"
            continue
        if not text:
            continue
        if current is None:
            title = title or text
            continue
        if in_references:
            reference_count += 1
            continue
        words = len(text.split())
        current["words"] += words
        citation_count += len(IN_TEXT_CITATION.findall(text))
        if not opening and words >= OPENING_MIN_WORDS:
            opening = _trim_to_sentence(text)

    return {
        "title": title,
        "opening_paragraph": opening,
        "sections": sections,
        "total_words": sum(section["words"] for section in sections),
        "citation_count": citation_count,
        "reference_count": reference_count,
        "locked_sections": max(0, len(sections) - 1),
    }
