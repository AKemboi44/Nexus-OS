"""
Scoring evaluation.

Evaluates whether Nexus OS
correctly classifies benchmark sources.
"""

import json

from app.scoring.scorer import SourceScorer
from app.scoring.inclusion_engine import (
    InclusionEngine
)

from evals.eval_result import EvalResult


def run():

    with open(
        "benchmarks/scoring.json",
        "r"
    ) as f:

        benchmark = json.load(f)

    scorer = SourceScorer()
    inclusion_engine = (
        InclusionEngine()
    )

    correct = 0

    total = len(benchmark)

    for item in benchmark:

        score = scorer.score(
            source_id=item["title"],
            query="mobile money loan repayment",
            title=item["title"],
            year=item["year"],
            methodology=None
        )

        decision = (
            inclusion_engine.decide(
                score
            )
        )

        actual = decision.decision

        print(
            f"{item['title']}"
        )

        print(
            f"Expected: {item['expected']}"
        )

        print(
            f"Actual: {actual}"
        )

        print(
            f"Score: {score.total_score:.2f}"
        )

        print("-" * 50)

        if actual == item["expected"]:

            correct += 1

    accuracy = correct / total

    passed = accuracy >= 0.8

    return EvalResult(
        name="scoring_accuracy",
        passed=passed,
        score=accuracy,
        details=(
            f"{correct}/{total} "
            f"classifications correct"
        ),
        rationale=(
            "Scoring benchmark "
            "comparison completed"
        )
    )


if __name__ == "__main__":
    print(run())