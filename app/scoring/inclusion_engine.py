"""
Nexus OS Inclusion Engine

Converts SourceScore
into InclusionDecision.
"""

from models.source_score import SourceScore
from models.inclusion_decision import InclusionDecision

from Nexus_os.models.inclusion_decision import InclusionDecision


class InclusionEngine:
    def __init__(self, threshold: float = 6.0):
        self.threshold = threshold

    def process(self, source_score) -> InclusionDecision:
        # Determine explicit inclusion choice
        decision = "include" if source_score.total_score >= self.threshold else "exclude"

        # Calculate confidence metric from threshold distance
        if decision == "include":
            margin = source_score.total_score - self.threshold
            confidence = min(0.5 + (margin / 8.0), 1.0)
        else:
            margin = self.threshold - source_score.total_score
            confidence = min(0.5 + (margin / 6.0), 1.0)

        # Compile a robust audit trail of rationale attributes
        rationale = []
        if source_score.authority >= 7:
            rationale.append(f"High authority organization source (Score: {source_score.authority})")
        else:
            rationale.append(f"Informal or blog source context (Score: {source_score.authority})")

        rationale.append(
            f"Total quality score {source_score.total_score} evaluated against a system threshold of {self.threshold}.")

        return InclusionDecision(
            source_id=source_score.source_id,
            decision=decision,
            confidence=round(confidence, 2),
            rationale=rationale
        )
