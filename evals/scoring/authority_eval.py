"""
Authority Engine evaluation.

Uses benchmark-style examples to validate authority scoring behaviour.
"""

from app.scoring.authority_engine import (
    AuthorityEngine
)

from evals.eval_result import EvalResult


def run():

    engine = AuthorityEngine()

    tests = [
        (
            "World Bank Mobile Money Report",
            True
        ),
        (
            "GSMA State of Mobile Money",
            True
        ),
        (
            "Personal Blog About Mobile Money",
            False
        ),
        (
            "Top 10 Reasons I Love Mobile Wallets",
            False
        )
    ]

    correct = 0

    for title, should_be_strong in tests:

        score, _ = engine.score(title)

        is_strong = score >= 7

        if is_strong == should_be_strong:

            correct += 1

    accuracy = (
        correct / len(tests)
    )

    return EvalResult(
        name="authority_engine",

        passed=accuracy >= 0.8,

        score=accuracy,

        details=(
            f"{correct}/"
            f"{len(tests)} correct"
        ),

        rationale=(
            "Authority benchmark "
            "comparison completed"
        )
    )


if __name__ == "__main__":
    print(run())