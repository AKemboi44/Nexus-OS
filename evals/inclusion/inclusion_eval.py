"""
Evaluate Inclusion Engine.
"""

import json

from evals.eval_result import EvalResult
from app.scoring.inclusion_engine import InclusionEngine

from models.source_score import SourceScore


def run():

    with open(
        "benchmarks/inclusion.json",
        "r"
    ) as f:

        benchmark = json.load(f)

    correct = 0

    total = len(benchmark)

    for item in benchmark:


        engine = InclusionEngine()

        source_score = SourceScore(
            source_id=item["source_id"],

            relevance=0,

            authority=0,

            recency=0,

            methodology_score=0,

            total_score=item["score"],

            rationale=[]
        )

        decision = engine.decide(
            source_score
        )

        actual = decision.decision

        expected = item["expected"]

        print(
            f"Source: {item['source_id']}"
        )

        print(
            f"Expected: {expected}"
        )

        print(
            f"Actual: {actual}"
        )

        print("-" * 50)

        if actual == expected:

            correct += 1

    accuracy = correct / total

    passed = accuracy >= 0.8

    return EvalResult(
        name="inclusion_accuracy",

        passed=passed,

        score=accuracy,

        details=(
            f"{correct}/{total} "
            f"decisions correct"
        ),

        rationale=(
            "Inclusion benchmark "
            "comparison completed"
        ),

        decision= ""
    )


if __name__ == "__main__":
    print(run())