import sys
import requests
import certifi
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider


class SemanticScholarProvider(DiscoveryProvider):
    """
    Integrates the Allen Institute AI Academic Graph with explicit,
    isolated OS trust certificate tracking handles to prevent handshake drops.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        old_stdout = sys.stdout
        sys.stdout = sys.stderr

        url = "https://semanticscholar.org"
        query_params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,url,abstract,citationCount,isOpenAccess,venue,publicationVenue,influentialCitationCount"
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            with requests.Session() as session:
                session.trust_env = False  # Drop broken Windows system proxy environmental variables

                # FIXED: Force the connection handle to use certifi's secure authority file footprint layout
                response = session.get(url, headers=headers, params=query_params, verify=certifi.where(), timeout=12)

                if response.status_code == 200:
                    data = response.json().get("data", [])
                    sys.stdout = old_stdout
                    return data
                else:
                    print(f"[Semantic Scholar Blocked] HTTP Status {response.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"[Semantic Scholar Exception] Handshake error bypassed: {e}", file=sys.stderr)

        sys.stdout = old_stdout
        return []

    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        authors_raw = raw_data.get("authors", [])
        authors_list = [auth.get("name") for auth in authors_raw if auth.get("name")]

        pub_venue = raw_data.get("publicationVenue")
        venue_name = pub_venue.get("name") if pub_venue else raw_data.get("venue", "Unknown Venue")
        is_peer_reviewed = True if pub_venue and pub_venue.get("type") == "journal" else raw_data.get("isOpenAccess",
                                                                                                      False)

        return {
            "uid": f"semschol_{raw_data.get('paperId')}",
            "title": raw_data.get("title", "Untitled Scholarly Work"),
            "authors": authors_list if authors_list else ["Unknown Author"],
            "venue": venue_name or "Academic Preprint / Archive",
            "year": str(raw_data.get("year", "n.d.")),
            "citation_count": raw_data.get("citationCount", 0),
            "is_peer_reviewed": is_peer_reviewed,
            "abstract": raw_data.get("abstract", "No metadata abstract description block parsed."),
            "url": raw_data.get("url") or f"https://semanticscholar.org{raw_data.get('paperId')}",
            "domain": "scholarly",
            "provider_source": "semantic_scholar",
            "influential_citations": raw_data.get("influentialCitationCount", 0)
        }
