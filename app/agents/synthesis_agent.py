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

    def execute(self, *args, **kwargs):
        """Processes raw sources into a ResearchDossier-compatible insight."""
        topic = kwargs.get("topic") or kwargs.get("query") or (args[0] if args else "")
        raw_data = kwargs.get("raw_data") or kwargs.get("sources") or (args[1] if len(args) > 1 else [])

        if raw_data is None:
            raw_data = []

        self.announce(f"Synthesizing {len(raw_data)} evidence blocks for: {topic}")

        # Generates a ResearchInsight object
        insight_obj = self.engine.generate_insight(topic, raw_data)

        # Pack it cleanly into a plain dictionary to prevent NameErrors/KeyErrors in Orchestrator loops
        return {
            "insight": {
                "theme": insight_obj.theme,
                "insight": insight_obj.insight
            }
        }