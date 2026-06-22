"""
Nexus OS Source Scoring Engine

Version 1:
Rule-based Source scoring orchestration.

This module coordinates scoring engines.It should not contain large amounts of scoring logic itself.

The long-term goal is to delegate each scoring dimension to its own specialized engine.
"""

from datetime import datetime

from models.source_score import SourceScore

from app.scoring.authority_engine import (
    AuthorityEngine
)

from app.scoring.relevance_engine import (
    RelevanceEngine
)

from app.scoring.methodology_engine import (
    MethodologyEngine
)

from app.scoring.recency_engine import (
    RecencyEngine
)

# Current scoring weights.
# We keep them centralized because scoring calibration will evolve significantly as Nexus OS matures.

AUTHORITY_WEIGHT = 0.25

METHODOLOGY_WEIGHT = 0.25

RELEVANCE_WEIGHT = 0.20

RECENCY_WEIGHT = 0.30

class SourceScorer:
    def __init__(self):
        """
        Initialize scoring engines.

        We keep engines separate so they can evolve independently.
        """

        self.authority_engine = (
            AuthorityEngine()
        )
        # Relevance scoring depends on the research question being asked.
        # Keeping it separate allows us to evolve from keyword matching to embeddings or rerankers later.
        self.relevance_engine = (
            RelevanceEngine()
        )

        # Methodology scoring allows Nexus OS to distinguish between stronger and weaker forms of evidence.
        # This becomes increasingly important as we move toward evidence-based inclusion decisions.

        self.methodology_engine = (
            MethodologyEngine()
        )

        # Recency scoring is isolated so we can
        # later introduce domain-specific freshness rules without modifying the scorer.

        self.recency_engine = (
            RecencyEngine()
        )

    def score(
        self,
        source_id: str,
        query: str,
        title: str,
        year: int,
        methodology: str | None
    ) -> SourceScore:

# ---------------------------------
# Source Authority Scoring
# ---------------------------------
# Authority scoring is delegated to the AuthorityEngine. This keeps scorer.py focused on orchestration rather than scoring implementation details.

        authority, authority_rationale = (
            self.authority_engine.score(
                title
            )
        )

        # Recency scoring evaluates how current the evidence is.
        # This is intentionally separated from authority because an older source may still be highly trustworthy.

        recency, recency_rationale = (
            self.recency_engine.score(
                year
            )
        )


        # Relevance scoring evaluates how well
        # a source answers the research question.
        #
        # This is intentionally separate from
        # authority because a trustworthy source
        # is not necessarily relevant.

        relevance, relevance_rationale = (
            self.relevance_engine.score(
                query=query,
                title=title
            )
        )


        # Methodology scoring is delegated to a dedicated engine.
        # This allows research quality assessment to evolve separately from authority and relevance.

        methodology_score, methodology_rationale = (
            self.methodology_engine.score(
                methodology
            )
        )

      # Total source score calculation


        total_score = (
                authority * AUTHORITY_WEIGHT
                +
                methodology_score * METHODOLOGY_WEIGHT
                +
                relevance * RELEVANCE_WEIGHT
                +
                recency * RECENCY_WEIGHT
        )

      # Rationale handling
      # This preserves authority explanations, Making Nexus OS explainable
        rationale = []

        rationale.extend(
            authority_rationale
        )

        rationale.extend(
            methodology_rationale
        )

        rationale.extend(
            recency_rationale
        )


        rationale.extend(
            relevance_rationale
        )

        return SourceScore(
            source_id=source_id,

            relevance=relevance,

            authority=authority,

            recency=recency,

            methodology_score=methodology_score,

            total_score=total_score,

            rationale=rationale
        )