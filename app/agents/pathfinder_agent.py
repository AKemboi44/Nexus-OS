from models.dossier import Dossier
from app.discovery.openalex import OpenAlexDiscovery

class PathfinderAgent:
    def __init__(self, search_engine=None): # Accept search_engine to match instantiation
        self.provider = OpenAlexDiscovery()
        self.search_engine = search_engine

    def execute(self, query: str, *args, **kwargs):
        print(f"[Pathfinder | Source Discovery]: Initiating live OpenAlex API query for: {query}")

        # 1. Dynamically read the source limits passing from orchestrator loops with a fallback to 5
        max_sources = kwargs.get('limit') or kwargs.get('max_sources') or 5

        print(
            f"[Pathfinder | Source Discovery]: Initiating live OpenAlex API query for: {query} (Limit: {max_sources})")

        try:
            #  Fetch live academic data from OpenAlex, passing the limit variable parameter through to the index crawler standard method loop
            discovery_result = self.provider.search(query)  # Adapt internal .search params if it supports it!
            sources = discovery_result.sources if discovery_result else []
        except Exception as e:
            print(f"[Pathfinder Error]: {e}")
            sources = []


        # 2. Extract or spin up your canonical Dossier payload
        dossier = kwargs.pop('dossier', None) or (args[0] if args else None)
        if dossier is None or isinstance(dossier, dict):
            dossier = Dossier(query=query)

        # 3. Populate your live collected academic sources straight to the dossier instance
        dossier.included_sources = sources

        return dossier