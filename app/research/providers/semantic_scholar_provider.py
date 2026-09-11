import sys
import requests
import certifi
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider


class SemanticScholarProvider(DiscoveryProvider):
    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        old_stdout = sys.stdout
        sys.stdout = sys.stderr

        clean_query = requests.utils.quote(str(query).strip())
        fields = "title,authors,year,url,abstract,citationCount,isOpenAccess,venue,publicationVenue,influentialCitationCount"

        # FIXED: Canonical absolute API routing endpoint path
        absolute_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={clean_query}&limit={int(limit)}&fields={fields}"

        print(f"[Semantic Scholar Outbound URL]: {absolute_url}", file=sys.stderr)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            response = requests.get(absolute_url, headers=headers, verify=certifi.where(), timeout=15)
            if response.status_code == 200:
                data = response.json().get("data", [])
                sys.stdout = old_stdout
                return data if isinstance(data, list) else []
            else:
                print(f"[Semantic Scholar HTTP Error]: Code {response.status_code}. Content: {response.text[:150]}",
                      file=sys.stderr)
        except Exception as e:
            print(f"[Semantic Scholar Exception Handler] {e}", file=sys.stderr)

        sys.stdout = old_stdout
        return []

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
            "is_peer_reviewed": True if pub_venue and pub_venue.get("type") == "journal" else raw_data.get(
                "isOpenAccess", False),
            "abstract": raw_data.get("abstract", "No description."),
            # FIXED: Correct base URL mapping frame for web link strings
            "url": raw_data.get("url") or f"https://api.semanticscholar.org/{raw_data.get('paperId')}",
            "domain": "scholarly",
            "provider_source": "semantic_scholar",
            "influential_citations": raw_data.get("influentialCitationCount", 0)
        }
