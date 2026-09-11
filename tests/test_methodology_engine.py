"""
Methodology Engine tests.

These tests verify that stronger research methods receive higher scores.
"""

from app.scoring.methodology_engine import (
    MethodologyEngine
)


def test_randomized_study():

    engine = MethodologyEngine()

    score, rationale = engine.score(
        "Randomized Study"
    )

    assert score == 10.0


def test_panel_study():

    engine = MethodologyEngine()

    score, rationale = engine.score(
        "Panel Study"
    )

    assert score == 8.0


def test_survey():

    engine = MethodologyEngine()

    score, rationale = engine.score(
        "Survey"
    )

    assert score == 6.0


def test_unknown_methodology():

    engine = MethodologyEngine()

    score, rationale = engine.score(
        None
    )

    assert score == 3.0