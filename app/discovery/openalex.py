import requests
from config.settings import OPENALEX_API_KEY
from app.discovery.discovery_interface import DiscoveryProvider
from app.discovery.models import DiscoveryResult
from models.source import Source


class OpenAlexDiscovery(DiscoveryProvider):

    def search(self, query):
        url = "https://api.openalex.org/works"

        # Authentication parameter cleanup for open academic polite pool routing
        params = {
            "search": query,
            "per_page": 5
        }

        # If you have an institutional key premium seat, append it defensively
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY

        headers = {
            "User-Agent": "mailto:akiptoo20@gmail.com"
        }

        response = requests.get(url, params=params, headers=headers)

        # Safety check status code before parsing
        if response.status_code != 200:
            raise Exception(f"OpenAlex request failed with status: {response.status_code}")

        data = response.json()

        sources = [
            self._normalize_work(work)
            for work in data.get("results", [])
        ]

        return DiscoveryResult(
            query=query,
            provider="openalex",
            sources=sources
        )

    def _reconstruct_abstract(self, inverted_index):
        """Convert OpenAlex abstract_inverted_index into normal text."""
        if not inverted_index:
            return ""

        if not isinstance(inverted_index, dict) or len(inverted_index) == 0:
            return ""

        words = []
        try:
            max_position = max(
                max(pos_list)
                for pos_list in inverted_index.values()
            )
            words = [""] * (max_position + 1)

            for word, positions in inverted_index.items():
                for position in positions:
                    words[position] = word
            return " ".join(words)
        except Exception:
            return ""

    def _normalize_work(self, work):
        return Source(
            id=work.get("id", ""),
            title=work.get("display_name", ""),
            authors=[
                author["author"]["display_name"]
                for author in work.get("authorships", [])
                if "author" in author and "display_name" in author["author"]
            ],
            year=work.get("publication_year"),
            url=work.get("id", ""),
            abstract=self._reconstruct_abstract(work.get("abstract_inverted_index")),
            source_type="academic"
        )
