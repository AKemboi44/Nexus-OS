"""
Recency Engine tests.
"""

from datetime import datetime

from app.scoring.recency_engine import (
    RecencyEngine
)


def test_recent_publication():

    engine = RecencyEngine()

    current_year = datetime.now().year

    score, rationale = engine.score(
        current_year
    )

    assert score == 10.0


def test_five_year_publication():

    engine = RecencyEngine()

    current_year = datetime.now().year

    score, rationale = engine.score(
        current_year - 4
    )

    assert score == 8.0


def test_old_publication():

    engine = RecencyEngine()

    current_year = datetime.now().year

    score, rationale = engine.score(
        current_year - 15
    )

    assert score == 2.0