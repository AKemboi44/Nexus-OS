# Test for the source scoring model

from app.scoring.scorer import SourceScorer


def test_world_bank_report():

    scorer = SourceScorer()

    score = scorer.score(
        source_id="1",
        title="World Bank Mobile Money Report",
        query="mobile money loan repayment",
        year=2024,
        methodology=None
    )

    assert score.authority >= 8

    assert score.total_score >= 6