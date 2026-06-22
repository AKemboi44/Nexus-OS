"""
Relevance Engine evaluation.
"""

import json

from app.scoring.relevance_engine import (
    RelevanceEngine
)

from evals.eval_result import EvalResult


def run():

    with open(
        "benchmarks/relevance.json",
        "r"
    ) as f:

        benchmark = json.load(f)

    engine = RelevanceEngine()

    correct = 0

    total = len(benchmark)

    for item in benchmark:

        score, rationale = engine.score(
            query=item["query"],
            title=item["title"]
        )

        actual = (
            "high"
            if score >= 6
            else "low"
        )

        print(
            f"{item['title']}"
        )

        print(
            f"Expected: {item['expected']}"
        )

        print(
            f"Actual: {actual}"
        )

        print("-" * 50)

        if actual == item["expected"]:

            correct += 1

    accuracy = correct / total

    return EvalResult(
        name="relevance_engine",

        passed=accuracy >= 0.8,

        score=accuracy,

        details=(
            f"{correct}/{total} correct"
        ),

        rationale=(
            "Relevance benchmark "
            "comparison completed"
        )
    )


if __name__ == "__main__":
    print(run())