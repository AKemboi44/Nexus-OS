import sys
import requests
import certifi
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider


class CrossrefProvider(DiscoveryProvider):
    """
    Direct client wrapper to query the global Crossref metadata registry ecosystem
    with isolated trust certificate configurations.
    """

    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        old_stdout = sys.stdout
        sys.stdout = sys.stderr

        url = "https://crossref.org"
        query_params = {"query": query, "rows": limit}

        headers = {
            "User-Agent": "NexusResearchEngine/1.1 (mailto:abraham.kemboi@nexusos.org) PythonRequests/2.31",
            "Accept": "application/json"
        }

        try:
            with requests.Session() as session:
                session.trust_env = False

                # FIXED: Direct certifi verification binding structure bypasses local WinSSL truncation drops
                response = session.get(url, headers=headers, params=query_params, verify=certifi.where(), timeout=12)

                if response.status_code == 200:
                    items = response.json().get("message", {}).get("items", [])
                    sys.stdout = old_stdout
                    return items
                else:
                    print(f"[Crossref Blocked] HTTP Status {response.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"[Crossref Exception] Handshake error bypassed: {e}", file=sys.stderr)

        sys.stdout = old_stdout
        return []

    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        authors_raw = raw_data.get("author", [])
        authors_list = []
        for auth in authors_raw:
            given = auth.get("given", "")
            family = auth.get("family", "")
            if family:
                authors_list.append(f"{given} {family}".strip())

        date_parts = raw_data.get("published-print", raw_data.get("published-online", {})).get("date-parts", [["n.d."]])
        year = date_parts if date_parts and date_parts else "n.d."

        container_title = raw_data.get("container-title", [])
        venue_name = container_title if isinstance(container_title,
                                                   list) and container_title else "Unknown Publisher Registry"

        return {
            "uid": f"crossref_{raw_data.get('DOI')}",
            "title": raw_data.get("title", ["Untitled Metadata Entry"]) if isinstance(raw_data.get("title"),
                                                                                      list) else raw_data.get("title",
                                                                                                              "Untitled Metadata Entry"),
            "authors": authors_list if authors_list else ["Unknown Contributor"],
            "venue": venue_name,
            "year": str(year),
            "citation_count": raw_data.get("is-referenced-by-count", 0),
            "is_peer_reviewed": True if raw_data.get("type") == "journal-article" else False,
            "abstract": raw_data.get("abstract",
                                     "Abstract index layer truncated or requires full publisher text handshake."),
            "url": raw_data.get("URL") or f"https://doi.org{raw_data.get('DOI')}",
            "domain": "scholarly",
            "provider_source": "crossref",
            "influential_citations": 0
        }
