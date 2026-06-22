"""
Authority Engine tests.

These tests verify that authority scoring behaves correctly before integration into the scoring engine.

The goal is to catch authority regressions without needing to run the full pipeline.
"""

from app.scoring.authority_engine import (
    AuthorityEngine
)


def test_world_bank_authority():

    engine = AuthorityEngine()

    score, rationale = engine.score(
        "World Bank Mobile Money Report"
    )

    assert score == 10.0

    assert (
        "World Bank source"
        in rationale
    )


def test_gsma_authority():

    engine = AuthorityEngine()

    score, rationale = engine.score(
        "GSMA State of Mobile Money"
    )

    assert score == 9.0


def test_randomized_study_authority():

    engine = AuthorityEngine()

    score, rationale = engine.score(
        "Randomized Evaluation of Mobile Money Adoption"
    )

    assert score >= 7.0


def test_blog_authority():

    engine = AuthorityEngine()

    score, rationale = engine.score(
        "Personal Blog About Mobile Money"
    )

    assert score == 1.0


def test_listicle_authority():

    engine = AuthorityEngine()

    score, rationale = engine.score(
        "Top 10 Reasons I Love Mobile Wallets"
    )

    assert score == 1.0