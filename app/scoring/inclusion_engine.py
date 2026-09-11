"""
Nexus OS Inclusion Engine

Converts SourceScore
into InclusionDecision.
"""

from models.source_score import SourceScore
from models.inclusion_decision import InclusionDecision

class InclusionEngine:

    def decide(
            self,
            score: SourceScore
    ) -> InclusionDecision:

        decision = (
            "include"
            if score.total_score >= 6
            else "exclude"
        )

        confidence = min(
            score.total_score / 10,
            1.0
        )

        rationale = list(score.rationale)

        if decision == "include":

            rationale.append(
                "Passed inclusion threshold"
            )

        else:

            rationale.append(
                "Failed inclusion threshold"
            )

        return InclusionDecision(
            source_id=score.source_id,

            decision=decision,

            confidence=confidence,

            rationale=rationale
        )