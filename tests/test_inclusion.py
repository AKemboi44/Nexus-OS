
# to test inclusion engine if it produces relevant outcome
from models.inclusion_decision import InclusionDecision


def test_inclusion_decision_creation():

    decision = InclusionDecision(
        source_id="1",
        decision="include",
        confidence=0.91,
        rationale=[
            "Trusted institution"
        ]
    )

    assert decision.decision == "include"