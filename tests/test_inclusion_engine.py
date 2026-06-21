from app import InclusionEngine

from models.source_score import SourceScore

def test_include_decision():

    engine = InclusionEngine()

    score = SourceScore(
        source_id="1",

        relevance=5,

        authority=10,

        recency=10,

        methodology_score=5,

        total_score=7.75,

        decision="include",

        rationale=[
            "Trusted institution"
        ]
    )

    result = engine.decide(score)

    assert result.decision == "include"