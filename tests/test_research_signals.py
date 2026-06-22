from app.scoring.authority_engine import (
    AuthorityEngine
)


def test_randomized_evaluation():

    engine = AuthorityEngine()

    score, rationale = engine.score(
        "Randomized Evaluation of Mobile Money Adoption"
    )

    assert score >= 7


def test_listicle_content():

    engine = AuthorityEngine()

    score, rationale = engine.score(
        "Top 10 Reasons I Love Mobile Wallets"
    )

    assert score <= 2