"""
Theme Engine

Purpose
-------
Identify recurring evidence patterns.

Version 1
---------
Theme detection is intentionally simple.

A theme is defined as a finding that
appears across multiple sources.

Why This Exists
---------------
Before we generate insights, we must
first organize evidence.

This engine transforms:

Evidence
↓
Theme Candidates

Future Versions
---------------
May introduce:

- Semantic clustering
- Embeddings
- Contradictions
- Confidence scores
- Theme strength metrics
"""

from collections import defaultdict

from models.theme import Theme


class ThemeEngine:

    def detect_themes(
        self,
        evidence_items
    ) -> list[Theme]:
        """
        Detect recurring themes.

        Parameters
        ----------
        evidence_items

        Returns
        -------
        list[Theme]
        """

        findings_to_sources = (
            defaultdict(set)
        )

        findings_to_evidence = (
            defaultdict(list)
        )

        # ---------------------------------
        # Group evidence by finding
        # ---------------------------------

        for item in evidence_items:

            findings_to_sources[
                item.finding
            ].add(
                item.source_title
            )

            findings_to_evidence[
                item.finding
            ].append(
                item.finding
            )

        themes = []

        # ---------------------------------
        # Create themes
        # ---------------------------------

        for (
            finding,
            sources
        ) in findings_to_sources.items():

            # A finding must appear in
            # more than one source before
            # we consider it a theme.

            if len(sources) < 2:

                continue

            theme = Theme(
                name=finding,

                supporting_sources=
                list(sources),

                supporting_findings=
                findings_to_evidence[
                    finding
                ]
            )

            themes.append(
                theme
            )

        return themes