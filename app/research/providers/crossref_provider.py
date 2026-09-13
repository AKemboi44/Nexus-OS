import sys
import requests
import certifi
from typing import List, Dict, Any
from .base_provider import DiscoveryProvider

class CrossrefProvider(DiscoveryProvider):
    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        old_stdout = sys.stdout
        sys.stdout = sys.stderr

        absolute_url = "https://api.crossref.org/works"
        print(f"[Crossref Outbound URL]: {absolute_url}", file=sys.stderr)

        headers = {
            "User-Agent": "NexusResearchEngine/1.1 (mailto:akiptoo20@gmail.com) PythonRequests/2.31",
            "Accept": "application/json"
        }

        try:
            response = requests.get(
                absolute_url,
                params={"query": str(query).strip(), "rows": int(limit)},
                headers=headers,
                verify=certifi.where(),
                timeout=15
            )
            if response.status_code == 200:
                items = response.json().get("message", {}).get("items", [])
                sys.stdout = old_stdout
                return items if isinstance(items, list) else []
            else:
                print(f"[Crossref HTTP Error]: Code {response.status_code}. Content: {response.text[:150]}", file=sys.stderr)
        except Exception as e:
            print(f"[Crossref Exception Handler] {e}", file=sys.stderr)

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
        return {
            "uid": f"crossref_{raw_data.get('DOI')}",
            "title": raw_data.get("title", ["Untitled"]) if isinstance(raw_data.get("title"), list) else raw_data.get("title", "Untitled"),
            "authors": authors_list if authors_list else ["Unknown Contributor"],
            "venue": "Crossref Repository",
            "year": "2026",
            "citation_count": raw_data.get("is-referenced-by-count", 0),
            "is_peer_reviewed": True if raw_data.get("type") == "journal-article" else False,
            "abstract": "Metadata entry.",
            "url": raw_data.get("URL") or f"https://doi.org{raw_data.get('DOI')}",
            "domain": "scholarly",
            "provider_source": "crossref",
            "influential_citations": 0
        }
