"""
Nexus OS v0.5.0 - Agent Layer
Generated for clarity and high maintainability.
"""
import os
import sys

# Path resolution to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from .base_agent import BaseAgent
from app.synthesis.insight_engine import InsightEngine

class SynthesisAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Scribe", role="Research Synthesizer")
        self.engine = InsightEngine()

    def execute(self, topic: str, evidence: list) -> dict:
        self.announce(f"Synthesizing {len(evidence)} pieces of evidence for: {topic}")
        insight = self.engine.generate_insight(topic, evidence)
        
        return {
            "status": "completed",
            "output": insight.to_dict()
        }
