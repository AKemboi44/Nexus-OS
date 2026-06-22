from app.synthesis.theme_engine import (
    ThemeEngine
)

from models.evidence_item import (
    EvidenceItem
)


def test_theme_detection():

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

    assert len(themes) == 1

    assert (
        themes[0].name
        ==
        "Impact assessed"
    )