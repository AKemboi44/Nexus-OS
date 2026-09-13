# app/research/providers/openalex_provider.py
import requests
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider

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
        abstract_index = raw_data.get("abstract_inverted_index") or {}
        abstract = " ".join(
            word
            for word, positions in sorted(
                abstract_index.items(),
                key=lambda item: min(item[1]) if item[1] else 0
            )
            for _ in positions
        ) if isinstance(abstract_index, dict) else "No description."
        return {
            "uid": raw_data.get("id"),
            "title": raw_data.get("title"),
            "authors": [auth.get("author", {}).get("display_name") for auth in raw_data.get("authorships", [])],
            "venue": venue_source.get("display_name", "Unknown Venue"),
            "year": raw_data.get("publication_year"),
            "citation_count": raw_data.get("cited_by_count", 0),
            "is_peer_reviewed": venue_source.get("is_peer_reviewed", False),
            "abstract": abstract,
            "url": raw_data.get("doi") or raw_data.get("id"),
            "domain": "scholarly"
        }
