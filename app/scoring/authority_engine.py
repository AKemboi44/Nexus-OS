"""
Authority Engine

Purpose
-------
Evaluate how trustworthy a source appears based on research-oriented signals.

This engine intentionally focuses on authority only. Recency, relevance and methodology are handled elsewhere.

Design Philosophy
-----------------
Prefer explainable heuristics first. We will replace this later with:

- Citation analysis
- Publisher databases
- Knowledge graphs
- ML models

without affecting the rest of Nexus OS.
"""
from app.scoring.research_signals import (
    RESEARCH_TERMS,
    LOW_AUTHORITY_TERMS
)

class AuthorityEngine:

    def score( self, title: str ) -> tuple[float, list[str]]:
        """
        Returns: authority_score rationale

        """

        rationale = []

        title_lower = title.lower()

        authority = 1.0

        # ---------------------------------
        # Trusted Institutions
        # ---------------------------------

        if "world bank" in title_lower:

            authority = 10.0

            rationale.append(
                "World Bank source"
            )

        elif "gsma" in title_lower:

            authority = 9.0

            rationale.append(
                "GSMA source"
            )

        # ---------------------------------
        # Strong Research Signals
        # ---------------------------------

        research_signal_score = 0

        for term, weight in (
                RESEARCH_TERMS.items()
        ):

            if term in title_lower:
                research_signal_score += weight

                rationale.append(
                    f"Research signal: {term}"
                )
        # ---------------------------------
        # Low Authority Signals
        # ---------------------------------
        for term, penalty in (
                LOW_AUTHORITY_TERMS.items()
        ):

            if term in title_lower:
                research_signal_score += penalty

                rationale.append(
                    f"Low authority signal: {term}"
                )

      # Apply Signal Score

        authority += (
            research_signal_score
        )

        # Clamp Authority
        authority = max(
            1,
            min(
                authority,
                10
            )
        )

        return authority, rationale