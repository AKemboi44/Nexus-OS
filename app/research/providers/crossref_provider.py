import sys
import html
import re
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
        for auth in authors_raw if isinstance(authors_raw, list) else []:
            if not isinstance(auth, dict):
                continue
            given = auth.get("given", "")
            family = auth.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors_list.append(name)

        doi = self._clean_doi(raw_data.get("DOI"))
        title = self._first_text(raw_data.get("title")) or "Untitled"
        venue = (
            self._first_text(raw_data.get("container-title"))
            or self._clean_text(raw_data.get("publisher"))
            or ""
        )
        year = self._publication_year(raw_data)
        abstract = self._clean_abstract(raw_data.get("abstract"))
        url = raw_data.get("URL")
        if doi:
            url = f"https://doi.org/{doi}"
        elif url:
            url = str(url).strip()

        return {
            "uid": f"crossref_{doi or raw_data.get('URL') or title}",
            "title": title,
            "authors": authors_list,
            "venue": venue,
            "year": str(year) if year else "",
            "citation_count": raw_data.get("is-referenced-by-count", 0) or 0,
            # Crossref's work type alone does not establish peer review.
            "is_peer_reviewed": False,
            "abstract": abstract,
            "doi": doi,
            "url": url or "",
            "keywords": raw_data.get("subject") if isinstance(raw_data.get("subject"), list) else [],
            "domain": "scholarly",
            "provider_source": "crossref",
            "influential_citations": 0,
        }

    @staticmethod
    def _first_text(value: Any) -> str:
        if isinstance(value, list):
            value = next((item for item in value if str(item or "").strip()), "")
        return CrossrefProvider._clean_text(value)

    @staticmethod
    def _clean_text(value: Any) -> str:
        return re.sub(r"\s+", " ", html.unescape(str(value or "")).strip())

    @staticmethod
    def _clean_doi(value: Any) -> str:
        doi = str(value or "").strip()
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
        return doi.strip()

    @classmethod
    def _publication_year(cls, raw_data: Dict[str, Any]):
        for field in ("published-print", "published-online", "published", "issued", "created"):
            date_parts = raw_data.get(field, {}).get("date-parts") if isinstance(raw_data.get(field), dict) else None
            if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
                year = date_parts[0][0]
                if isinstance(year, int) or (isinstance(year, str) and year.isdigit() and len(year) == 4):
                    return int(year)
        return None

    @classmethod
    def _clean_abstract(cls, value: Any) -> str:
        if not value:
            return ""
        text = html.unescape(str(value))
        # Crossref returns JATS fragments such as <jats:p>...</jats:p>.
        text = re.sub(r"<[^>]+>", " ", text)
        return cls._clean_text(text)
