# app/research/providers/openalex_provider.py
import re
import requests
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider

NO_DESCRIPTION = "No description."
_ABSTRACT_LABEL = re.compile(r"^Abstract(?:\s*[:.\-–—]\s*|\s+(?=[A-Z]))")


def reconstruct_abstract(index: Any) -> str:
    """Rebuild an abstract from OpenAlex's inverted index, {word: [every position it occurs at]}.

    Each word goes at each of its own positions; the text is the words in position order. (Repeating
    a word once per occurrence at its first position scrambles the text: "of of of of artificial".)
    """
    if not isinstance(index, dict):
        return NO_DESCRIPTION
    slots: Dict[int, str] = {}
    for word, positions in index.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int) and not isinstance(position, bool):
                slots[position] = str(word)
    if not slots:
        return NO_DESCRIPTION
    text = " ".join(slots[position] for position in sorted(slots))
    # Some records start with the heading word. Only strip it when it is clearly a label ("Abstract: ..." or
    # "Abstract As ..."), never a sentence about abstract algebra.
    return _ABSTRACT_LABEL.sub("", text, count=1) or text


# Work types as OpenAlex names them, for search-time filters.
_OPENALEX_TYPES = {
    "review": "review", "journal-article": "article", "conference-paper": "conference-paper",
    "preprint": "preprint", "book": "book", "book-chapter": "book-chapter",
}


def build_filter(hints: Any) -> str:
    """The OpenAlex `filter` for a targeted search; empty when the hints give it nothing to filter on."""
    if not isinstance(hints, dict):
        return ""
    parts = []
    if hints.get("year_from"):
        parts.append(f"from_publication_date:{int(hints['year_from'])}-01-01")
    if hints.get("open_access"):
        parts.append("is_oa:true")
    if hints.get("min_citations"):
        parts.append(f"cited_by_count:>{int(hints['min_citations']) - 1}")
    work_types = hints.get("work_types") or []
    if hints.get("review"):
        parts.append("type:review")
    elif work_types:
        types = [_OPENALEX_TYPES[t] for t in work_types if t in _OPENALEX_TYPES]
        if types:
            parts.append("type:" + "|".join(dict.fromkeys(types)))
        if "journal-article" in work_types:
            parts.append("primary_location.source.type:journal")
    return ",".join(parts)


def work_type_of(raw_type: Any, source_type: Any) -> str:
    """OpenAlex's work type, normalized to the names the criteria use."""
    raw_type = str(raw_type or "").lower()
    if raw_type == "review":
        return "review"
    if raw_type in ("preprint", "posted-content"):
        return "preprint"
    if raw_type in ("conference-paper", "proceedings-article", "proceedings"):
        return "conference-paper"
    if raw_type in ("book", "monograph"):
        return "book"
    if raw_type in ("book-chapter", "book-section"):
        return "book-chapter"
    if raw_type == "dataset":
        return "dataset"
    if raw_type == "article":
        return "journal-article" if source_type == "journal" else "other"
    return "other"


class OpenAlexProvider(DiscoveryProvider):
    def supports_hints(self, hints: Dict[str, Any]) -> bool:
        return bool(build_filter(hints))

    def fetch_raw_sources(self, query: str, limit: int = 5, hints: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        url = "https://api.openalex.org/works"
        params = {"search": str(query).strip(), "per-page": int(limit)}
        if build_filter(hints):
            params["filter"] = build_filter(hints)
        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": "NexusResearch/1.0 (mailto:akiptoo20@gmail.com)"},
                timeout=15
            )
            if response.status_code == 200:
                return response.json().get("results", [])
        except Exception:
            return []
        return []

    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        primary_location = raw_data.get("primary_location") or {}
        venue_source = primary_location.get("source") or {}
        abstract = reconstruct_abstract(raw_data.get("abstract_inverted_index"))
        # OpenAlex has no peer-review field. As with Semantic Scholar, "published in a journal" is the
        # signal we have: it is not a verified peer review, and preprints or repository copies are excluded.
        published_in_journal = (
            venue_source.get("type") == "journal" and primary_location.get("is_published") is not False
        )
        return {
            "uid": raw_data.get("id"),
            "title": raw_data.get("title"),
            "authors": [auth.get("author", {}).get("display_name") for auth in raw_data.get("authorships", [])],
            "venue": venue_source.get("display_name", "Unknown Venue"),
            "year": raw_data.get("publication_year"),
            "citation_count": raw_data.get("cited_by_count", 0),
            "is_peer_reviewed": published_in_journal,
            "abstract": abstract,
            "work_type": work_type_of(raw_data.get("type"), venue_source.get("type")),
            "is_open_access": (raw_data.get("open_access") or {}).get("is_oa", primary_location.get("is_oa")),
            "language": raw_data.get("language"),
            "url": raw_data.get("doi") or raw_data.get("id"),
            "domain": "scholarly"
        }
