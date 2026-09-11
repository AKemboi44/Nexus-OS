"""
Nexus OS v0.6.1 - Scribe
"""
from .base_agent import BaseAgent

class ScribeAgent(BaseAgent):
    """
    The Scribe acts as the 'Synthesizer'. 
    It transforms raw evidence blocks into structured research insights.
    """
    def __init__(self, engine):
        super().__init__(name="Scribe", role="Research Synthesizer")
        self.engine = engine

    def execute(self, topic: str, raw_data: list):
        """Processes raw sources into a ResearchDossier-compatible insight."""
        self.announce(f"Synthesizing {len(raw_data)} evidence blocks for: {topic}")
        insight = self.engine.generate_insight(topic, raw_data)
        return {"insight": insight.to_dict()}