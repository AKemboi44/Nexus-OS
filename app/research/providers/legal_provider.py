# app/research/providers/legal_provider.py
import requests
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider

class CourtListenerProvider(DiscoveryProvider):
    """Sources verified legal opinions, precedents, and federal case documents."""
    def __init__(self, api_token: str = None):
        self.token = api_token
        self.headers = {"Authorization": f"Token {self.token}"} if self.token else {}

    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        # Fallback to an open metadata endpoint or your internal legal warehouse index block
        url = f"https://courtlistener.com{query}&page_size={limit}"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                return response.json().get("results", [])
        except Exception:
            return []
        return []

    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "uid": raw_data.get("id"),
            "title": raw_data.get("caseName") or raw_data.get("document_title"),
            "authors": [raw_data.get("court", "Unknown Court")], # Courts act as creators in case law
            "venue": raw_data.get("reporter", "Federal Reporter"),
            "year": int(raw_data.get("dateFiled", "3000-01-01").split("-")[0]),
            "citation_count": raw_data.get("citation_count", 0),
            "is_peer_reviewed": True, # Precedents and judicial opinions carry binding authority
            "abstract": raw_data.get("snippet") or raw_data.get("summary"),
            "url": f"https://courtlistener.com{raw_data.get('absolute_url')}",
            "domain": "legal"
        }
