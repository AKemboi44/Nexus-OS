"""
Nexus OS v0.6.1 - Pathfinder
"""
from .base_agent import BaseAgent

class PathfinderAgent(BaseAgent):
    """
    The Pathfinder is responsible for the 'Discovery' phase of research.
    It interfaces with the ResearchPipeline to gather raw source data.
    """
    def __init__(self, engine):
        super().__init__(name="Pathfinder", role="Source Discovery")
        self.engine = engine

    def execute(self, query: str):
        """Executes the search via the tiered discovery engine."""
        self.announce(f"Initiating global search for: {query}")
        raw_data = self.engine._discover_sources_real(query)
        return {"data": raw_data}