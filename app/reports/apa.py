"""APA 7 in-text citation helpers for proposal rendering."""

import re
from typing import Any, Dict, List

from app.synthesis.citation_engine import CitationEngine

_BRACKETED_SOURCE_IDS = re.compile(r"\s*\[\s*S\d+(?:\s*[,;]\s*S\d+)*\s*\]")


def _author_surnames(source: Dict[str, Any]) -> List[str]:
    return [
        CitationEngine._format_author(author).split(",", 1)[0].strip()
        for author in CitationEngine._authors(source)
    ]


def _author_label(source: Dict[str, Any]) -> str:
    surnames = _author_surnames(source)
    if len(surnames) == 1:
        return surnames[0]
    if len(surnames) == 2:
        return f"{surnames[0]} & {surnames[1]}"
    if len(surnames) > 2:
        return f"{surnames[0]} et al."
    title_words = str(source.get("title") or "Untitled").split()[:4]
    return f'"{" ".join(title_words)}"'


def in_text_citation(sources: List[Dict[str, Any]]) -> str:
    """Build one APA parenthetical, e.g. (Lee, 2022; Smith & Jones, 2023), sorted alphabetically."""
    entries = {
        (_author_label(source), str(source.get("year") or "n.d.").strip())
        for source in sources
    }
    if not entries:
        return ""
    ordered = sorted(entries, key=lambda entry: (entry[0].casefold(), entry[1]))
    return "(" + "; ".join(f"{label}, {year}" for label, year in ordered) + ")"


def append_citation(text: str, sources: List[Dict[str, Any]]) -> str:
    """Strip any bracketed source IDs and end the sentence with an APA parenthetical citation."""
    clean = _BRACKETED_SOURCE_IDS.sub("", str(text or "")).strip()
    citation = in_text_citation(sources)
    if not citation:
        return clean
    if clean.endswith((".", "!", "?")):
        return f"{clean[:-1]} {citation}{clean[-1]}"
    return f"{clean} {citation}"
