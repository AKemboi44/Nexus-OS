"""
Gap Engine

Purpose
-------
Identify potential research gaps
from the currently detected themes.

Version 1
---------
Uses simple coverage-based rules.

Future Versions
---------------
May incorporate:

- Semantic theme clustering
- Contradictory evidence
- Research recommendations
- Literature coverage analysis
"""

from models.research_gap import (
    ResearchGap
)


class GapEngine:

    def detect_gaps(
        self,
        themes
    ) -> list[ResearchGap]:
        """
        Detect potential gaps.

        Parameters
        ----------
        themes

        Returns
        -------
        list[ResearchGap]
        """

        gaps = []

        # ---------------------------------
        # Theme Diversity Gap
        # ---------------------------------
        #
        # If very few themes are detected,
        # the evidence base may be narrow.
        #

        if len(themes) <= 1:

            gaps.append(
                ResearchGap(
                    title=(
                        "Limited diversity "
                        "of evidence themes"
                    ),

                    rationale=(
                        "Only a small number "
                        "of recurring themes "
                        "were detected."
                    ),

                    supporting_themes=[
                        theme.name
                        for theme in themes
                    ]
                )
            )

        return gaps