"""
Nexus OS v0.5.0 - Agent Layer
Generated for clarity and high maintainability.
"""
import os
import sys

# Path resolution to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from .base_agent import BaseAgent
from app.research.research_pipeline import ResearchPipeline

class SearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Pathfinder", role="Source Discovery")
        self.pipeline = ResearchPipeline()

    def execute(self, query: str) -> dict:
        self.announce(f"Initiating global search for: {query}")
        # Use the established discovery logic from v0.4.1
        papers = self.pipeline._discover_sources_real(query)
        
        return {
            "status": "success",
            "output": papers
        }
