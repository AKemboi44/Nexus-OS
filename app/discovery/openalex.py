# OpenAlex.py is responsible only for one thing as below
# Query OpenAlex
# ↓
# Normalize to Source
# ↓
# Return DiscoveryResult
"""
Convert OpenAlex response
into Nexus OS Source objects.
"""

import requests

from app.discovery.models import DiscoveryResult
from models.source import Source
from app.discovery.discovery_interface import DiscoveryProvider
from config.settings import OPENALEX_API_KEY


#first version - proof connectivity;
#later: Add normalization, ranking, Source conversion.

class OpenAlexDiscovery(DiscoveryProvider):

    def search(self, query):
        #1. Defining the enpoint url
        url = "https://api.openalex.org/works"


        #2. Authentication and search parameter setup
        params = {
             "search":query,
             "api_key": OPENALEX_API_KEY,
             "per-page": 5
         }

        #3 adding a user-agent containing my email to get into the polite pool
        headers = {
             "User-Agent": "mailto:akiptoo20@gmail.com"
         }

        #4. Fire the authentication request
        response = requests.get(url, params=params, headers=headers)

         #5., Safety check status code before parsing'
        if "text/html" in response.headers.get ("content-type", ""):
            raise Exception (
                f"Target URL is incorrect. Received a webpage instead of data. "
                f"Status: {response.status_code}. Content Snippet: {response.text[:200]}"
            )
        data = response.json()

        sources = [
            self._normalize_work(work)
            for work in data.get(
                "results",
                []
            )
        ]

        return DiscoveryResult(
            query=query,
            provider="openalex",
            sources=sources
        )

    def _normalize_work(self, work):
        return Source(
            id=work.get("id", ""),
            title=work.get("display_name", ""),
            authors=[
                author["author"]["display_name"]
                for author in work.get(
                    "authorships",
                    []
                )
            ],
            year=work.get("publication_year"),
            url=work.get("id", ""),
            abstract=None,
            source_type="academic"
        )
