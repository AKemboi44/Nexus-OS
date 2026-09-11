"""
Methodology Engine evaluation.
"""

from app.scoring.methodology_engine import (
    MethodologyEngine
)

from evals.eval_result import EvalResult


def run():

    engine = MethodologyEngine()

    tests = [

        ("Randomized Study", 10),

        ("Panel Study", 8),

        ("Survey", 6),

        (None, 3)
    ]

    correct = 0

    for methodology, expected in tests:

        score, rationale = (
            engine.score(
                methodology
            )
        )

        if score == expected:

            correct += 1

    accuracy = (
        correct / len(tests)
    )

    return EvalResult(
        name="methodology_engine",

        passed=accuracy >= 0.8,

        score=accuracy,

        details=(
            f"{correct}/"
            f"{len(tests)} correct"
        ),

        rationale=(
            "Methodology benchmark "
            "comparison completed"
        )
    )


if __name__ == "__main__":
    print(run())