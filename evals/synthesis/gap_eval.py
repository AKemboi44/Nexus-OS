"""
Gap Engine evaluation.
"""

from app.synthesis.gap_engine import (
    GapEngine
)

from models.theme import (
    Theme
)

from evals.eval_result import (
    EvalResult
)


def run():

    engine = GapEngine()

    themes = [

        Theme(
            name="Impact assessed",

            supporting_sources=[
                "Source A",
                "Source B"
            ],

            supporting_findings=[
                "Impact assessed"
            ]
        )
    ]

    gaps = (
        engine.detect_gaps(
            themes
        )
    )

    score = (
        1.0
        if len(gaps) == 1
        else 0.0
    )

    return EvalResult(
        name="gap_engine",

        passed=score == 1.0,

        score=score,

        details=(
            f"{len(gaps)} gaps detected"
        ),

        rationale=(
            "Gap detection benchmark completed"
        )
    )


if __name__ == "__main__":
    print(run())