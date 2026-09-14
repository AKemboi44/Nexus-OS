"""
Nexus Research AI v0.6.1 - Scribe
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

    def execute(self, *args, **kwargs):
        """Processes raw sources into a ResearchDossier-compatible insight."""
        # Safely extract matching parameters across orchestrator contract naming conventions
        topic = kwargs.get("topic") or kwargs.get("query") or (args[0] if len(args) > 0 else "")
        raw_data = kwargs.get("raw_data") or kwargs.get("sources") or (args[1] if len(args) > 1 else [])

        # Ensure raw_data is always iterable to prevent TypeError on len()
        if raw_data is None:
            raw_data = []

        self.announce(f"Synthesizing {len(raw_data)} evidence blocks for: {topic}")
        insight = self.engine.generate_insight(topic, raw_data)
        return {"insight": insight.to_dict()}