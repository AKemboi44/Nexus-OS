import json

from evals.eval_result import EvalResult


def run():

    with open(
        "benchmarks/dossier.json",
        "r"
    ) as f:

        benchmark = json.load(f)

    passed = (
        len(
            benchmark["included_sources"]
        ) > 0
    )

    return EvalResult(
        name="dossier_benchmark",

        passed=passed,

        score=1.0 if passed else 0.0,

        details="Dossier benchmark loaded",

        rationale="Benchmark validation completed"
    )


if __name__ == "__main__":
    print(run())