# app/research/providers/openalex_provider.py
import requests
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider

NO_DESCRIPTION = "No description."


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
    return " ".join(slots[position] for position in sorted(slots)) if slots else NO_DESCRIPTION


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
    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        url = "https://api.openalex.org/works"
        try:
            response = requests.get(
                url,
                params={"search": str(query).strip(), "per-page": int(limit)},
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
