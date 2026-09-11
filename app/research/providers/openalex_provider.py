# app/research/providers/openalex_provider.py
import requests
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider

class OpenAlexProvider(DiscoveryProvider):
    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        url = f"https://openalex.org{query}&per_page={limit}"
        try:
            response = requests.get(url, headers={"User-Agent": "NexusResearch/1.0 (mailto:akiptoo20@gmail.com"}, timeout=15)
            if response.status_code == 200:
                return response.json().get("results", [])
        except Exception:
            return []
        return []

    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "uid": raw_data.get("id"),
            "title": raw_data.get("title"),
            "authors": [auth.get("author", {}).get("display_name") for auth in raw_data.get("authorships", [])],
            "venue": raw_data.get("primary_location", {}).get("source", {}).get("display_name", "Unknown Venue"),
            "year": raw_data.get("publication_year"),
            "citation_count": raw_data.get("cited_by_count", 0),
            "is_peer_reviewed": raw_data.get("primary_location", {}).get("source", {}).get("is_peer_reviewed", False),
            "abstract": raw_data.get("abstract_inverted_index"), # Process index to string if needed
            "url": raw_data.get("doi") or raw_data.get("id"),
            "domain": "scholarly"
        }
