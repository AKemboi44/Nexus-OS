import os
import sys
import requests
import certifi
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider


class SemanticScholarProvider(DiscoveryProvider):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")

    _TYPES = {
        "review": "Review", "journal-article": "JournalArticle", "conference-paper": "Conference",
        "book": "Book", "book-chapter": "BookSection",
    }

    def _filter_params(self, hints: Any) -> Dict[str, str]:
        """Search-time filters. Without an API key Semantic Scholar rate-limits shared traffic, so none are sent."""
        if not self.api_key or not isinstance(hints, dict):
            return {}
        params: Dict[str, str] = {}
        if hints.get("year_from"):
            params["year"] = f"{int(hints['year_from'])}-"
        if hints.get("min_citations"):
            params["minCitationCount"] = str(int(hints["min_citations"]))
        if hints.get("open_access"):
            params["openAccessPdf"] = ""
        types = ["Review"] if hints.get("review") else [
            self._TYPES[t] for t in dict.fromkeys(hints.get("work_types") or []) if t in self._TYPES]
        if types:
            params["publicationTypes"] = ",".join(types)
        return params

    def supports_hints(self, hints: Dict[str, Any]) -> bool:
        return bool(self._filter_params(hints))

    def fetch_raw_sources(self, query: str, limit: int = 5, hints: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        fields = "title,authors,year,url,abstract,citationCount,isOpenAccess,venue,publicationVenue,publicationTypes,influentialCitationCount"
        params = {"query": str(query).strip(), "limit": int(limit), "fields": fields, **self._filter_params(hints)}

        # FIXED: Canonical absolute API routing endpoint path
        absolute_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        print(f"[Semantic Scholar Outbound URL]: {absolute_url}", file=sys.stderr)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            response = requests.get(absolute_url, params=params, headers=headers, verify=certifi.where(), timeout=15)
            if response.status_code == 200:
                data = response.json().get("data", [])
                return data if isinstance(data, list) else []
            else:
                print(f"[Semantic Scholar HTTP Error]: Code {response.status_code}. Content: {response.text[:150]}",
                      file=sys.stderr)
        except Exception as e:
            print(f"[Semantic Scholar Exception Handler] {e}", file=sys.stderr)

        return []

    @staticmethod
    def _work_type(publication_types: Any, pub_venue: Any) -> str:
        types = {str(item) for item in publication_types or [] if item}
        if types & {"Review", "MetaAnalysis"}:
            return "review"
        if pub_venue and pub_venue.get("type") == "repository":
            return "preprint"
        if "Conference" in types:
            return "conference-paper"
        if "Book" in types:
            return "book"
        if "BookSection" in types:
            return "book-chapter"
        if "Dataset" in types:
            return "dataset"
        if "JournalArticle" in types or (pub_venue and pub_venue.get("type") == "journal"):
            return "journal-article"
        return "other"

    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        authors_raw = raw_data.get("authors", [])
        authors_list = [auth.get("name") for auth in authors_raw if auth.get("name")]
        pub_venue = raw_data.get("publicationVenue")
        venue_name = pub_venue.get("name") if pub_venue else raw_data.get("venue", "Unknown Venue")
        return {
            "uid": f"semschol_{raw_data.get('paperId')}",
            "title": raw_data.get("title", "Untitled Scholarly Work"),
            "authors": authors_list if authors_list else ["Unknown Author"],
            "venue": venue_name or "Academic Preprint / Archive",
            "year": str(raw_data.get("year", "n.d.")),
            "citation_count": raw_data.get("citationCount", 0),
            # Published in a journal. (Being open access says nothing about peer review.)
            "is_peer_reviewed": bool(pub_venue and pub_venue.get("type") == "journal"),
            "abstract": raw_data.get("abstract", "No description."),
            "work_type": self._work_type(raw_data.get("publicationTypes"), pub_venue),
            "is_open_access": raw_data.get("isOpenAccess"),
            "language": None,
            # FIXED: Correct base URL mapping frame for web link strings
            "url": raw_data.get("url") or f"https://api.semanticscholar.org/{raw_data.get('paperId')}",
            "domain": "scholarly",
            "provider_source": "semantic_scholar",
            "influential_citations": raw_data.get("influentialCitationCount", 0)
        }
