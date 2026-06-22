"""
Recency Engine evaluation.
"""

from datetime import datetime

from app.scoring.recency_engine import (
    RecencyEngine
)

from evals.eval_result import EvalResult


def run():

    engine = RecencyEngine()

    current_year = datetime.now().year

    tests = [

        (current_year, 10),

        (current_year - 4, 8),

        (current_year - 8, 5),

        (current_year - 15, 2)
    ]

    correct = 0

    for year, expected in tests:

        score, rationale = engine.score(
            year
        )

        if score == expected:

            correct += 1

    accuracy = (
        correct / len(tests)
    )

    return EvalResult(
        name="recency_engine",

        passed=accuracy >= 0.8,

        score=accuracy,

        details=(
            f"{correct}/"
            f"{len(tests)} correct"
        ),

        rationale=(
            "Recency benchmark "
            "comparison completed"
        )
    )


if __name__ == "__main__":
    print(run())