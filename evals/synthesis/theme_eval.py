"""
Theme Engine evaluation.
"""

from app.synthesis.theme_engine import (
    ThemeEngine
)

from models.evidence_item import (
    EvidenceItem
)

from evals.eval_result import (
    EvalResult
)


def run():

    engine = ThemeEngine()

    evidence = [

        EvidenceItem(
            source_id="1",

            source_title=
            "Paper A",

            methodology=
            "Panel Study",

            finding=
            "Impact assessed"
        ),

        EvidenceItem(
            source_id="2",

            source_title=
            "Paper B",

            methodology=
            "Survey",

            finding=
            "Impact assessed"
        )
    ]

    themes = (
        engine.detect_themes(
            evidence
        )
    )

    score = (
        1.0
        if len(themes) == 1
        else 0.0
    )

    return EvalResult(
        name="theme_engine",

        passed=score == 1.0,

        score=score,

        details=(
            f"{len(themes)} themes detected"
        ),

        rationale=(
            "Theme detection benchmark completed"
        )
    )


if __name__ == "__main__":
    print(run())