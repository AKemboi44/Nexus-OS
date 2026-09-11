"""
Relevance Engine tests.

These tests verify that the engine can distinguish relevant and irrelevant research content.

The goal is not perfect semantic search. The goal is explainable, testable, and incrementally improvable relevance.
"""

from app.scoring.relevance_engine import (
    RelevanceEngine
)


def test_loan_repayment_relevance():

    engine = RelevanceEngine()

    score, rationale = engine.score(
        query="mobile money loan repayment",

        title=(
            "A Personal Touch: "
            "Text Messaging for Loan Repayment"
        )
    )

    assert score >= 7


def test_financial_inclusion_relevance():

    engine = RelevanceEngine()

    score, rationale = engine.score(
        query="mobile money loan repayment",

        title=(
            "Mobile phones for financial inclusion"
        )
    )

    assert score >= 6


def test_income_inequality_relevance():

    engine = RelevanceEngine()

    score, rationale = engine.score(
        query="mobile money loan repayment",

        title=(
            "Trends in Income Inequality"
        )
    )

    assert score <= 3