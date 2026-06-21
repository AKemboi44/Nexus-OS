# Test for the source scoring model

from app import SourceScorer


def test_world_bank_report():

    scorer = SourceScorer()

    score = scorer.score(
        source_id="1",
        title="World Bank Mobile Money Report",
        year=2024
    )

    assert score.decision == "include"