from app.synthesis.gap_engine import (
    GapEngine
)

from models.theme import (
    Theme
)


def test_gap_detection():

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

    assert len(gaps) == 1

    assert (
        gaps[0].title
        ==
        "Limited diversity "
        "of evidence themes"
    )