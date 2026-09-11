"""
Defines the parameters of the inclusion decision.
Represents the final inclusion or exclusion
decision for a source.
"""

from pydantic import BaseModel


class InclusionDecision:
    def __init__(self, source_id: str, decision: str, confidence: float, rationale: list[str]):
        self.source_id = source_id
        self.decision = decision        # "include" or "exclude"
        self.confidence = confidence    # Quantitative confidence mapping
        self.rationale = rationale      # Auditable criteria list
