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

from config.settings import OPENALEX_API_KEY

from app.discovery.discovery_interface import (
    DiscoveryProvider
)

from app.discovery.models import (
    DiscoveryResult)

from models.source import Source



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

        print(
            data["results"][0].keys()
        )

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

    "# OpenALex returns inverted Abstract, therefore our summary output will always be empty"
    "We are adding a helper function to convert openAlex abstract inverted index to normal text"

    def _reconstruct_abstract(
            self,
            inverted_index
    ):
        """
        Convert OpenAlex abstract_inverted_index
        into normal text.
        """

        if not inverted_index:
            return ""

        words = []

        max_position = max(
            max(pos_list)
            for pos_list in inverted_index.values()
        )

        words = [""] * (
                max_position + 1
        )

        for word, positions in (
                inverted_index.items()
        ):

            for position in positions:
                words[position] = word

        return " ".join(words)

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
            abstract=self._reconstruct_abstract(
                work.get(
                    "abstract_inverted_index"
                )
            ),
            source_type="academic"
        )
