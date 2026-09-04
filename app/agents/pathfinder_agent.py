from models.dossier import Dossier
from app.discovery.openalex import OpenAlexDiscovery

class PathfinderAgent:
    def __init__(self, search_engine=None): # Accept search_engine to match instantiation
        self.provider = OpenAlexDiscovery()
        self.search_engine = search_engine

    def execute(self, query: str, *args, **kwargs):
        print(f"[Pathfinder | Source Discovery]: Initiating live OpenAlex API query for: {query}")

        # 1. Fetch live academic data from OpenAlex
        try:
            discovery_result = self.provider.search(query)
            sources = discovery_result.sources if discovery_result else []
            print(f"[Pathfinder Success]: Found {len(sources)} matching papers from OpenAlex.")
        except Exception as e:
            print(f"[Pathfinder Error]: Live API fetch failed with message: {e}")
            sources = []

        # 2. Extract or spin up your canonical Dossier payload
        dossier = kwargs.pop('dossier', None) or (args[0] if args else None)
        if dossier is None or isinstance(dossier, dict):
            dossier = Dossier(query=query)

        # 3. Populate your live collected academic sources straight to the dossier instance
        dossier.included_sources = sources

        return dossier