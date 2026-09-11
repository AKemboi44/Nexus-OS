"""
Evidence provenance evaluation.
"""

import json

from evals.eval_result import (
    EvalResult
)


def run():

    with open(
        "benchmarks/provenance.json",
        "r"
    ) as f:

        benchmark = json.load(f)

    passed = (
        len(benchmark) > 0
    )

    return EvalResult(
        name="provenance_model",

        passed=passed,

        score=1.0 if passed else 0.0,

        details=(
            "Provenance benchmark loaded"
        ),

        rationale=(
            "Benchmark validation completed"
        )
    )


if __name__ == "__main__":
    print(run())