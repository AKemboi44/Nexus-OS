"""
Nexus OS Source Scoring Engine

Version 1:
Rule-based scoring.
"""

from datetime import datetime

from models.source_score import SourceScore

class SourceScorer:

    def score(
        self,
        source_id: str,
        title: str,
        year: int
    ) -> SourceScore:

 # Source authority scoring
        authority = 1.0

        title_lower = title.lower()

        if "world bank" in title_lower:

            authority = 10.0

        elif "gsma" in title_lower:

            authority = 9.0

        elif "financial inclusion" in title_lower:

            authority = 7.0

        elif "research" in title_lower:

            authority = 7.0

        elif "study" in title_lower:

            authority = 7.0

        elif "blog" in title_lower:

            authority = 1.0

        elif "brochure" in title_lower:

            authority = 1.0

        elif "marketing" in title_lower:

            authority = 1.0
        elif "evidence" in title_lower:

            authority = 7

        elif "financial inclusion" in title_lower:

            authority = 7

        elif "loan repayment" in title_lower:

            authority = 7

        elif "mobile phone" in title_lower:

            authority = 7

        elif "mobile money" in title_lower:

            authority = 7

# Source recency scoring
        current_year = datetime.now().year
        age = current_year - year
        if age <= 2:

            recency = 10.0

        elif age <= 5:

            recency = 8.0

        elif age <= 10:

            recency = 5.0

        else:

            recency = 2.0

        relevance = 5.0

        methodology_score = 5.0

# Total source score calculation
        total_score = (
                authority * 0.25
                +
                methodology_score * 0.25
                +
                relevance * 0.20
                +
                recency * 0.30
        )

        rationale = []

        if authority >= 8:

            rationale.append(
                "Trusted institution"
            )

        elif authority >= 6:

            rationale.append(
                "Research-oriented source"
            )

        else:

            rationale.append(
                "Low authority source"
            )

        if authority >= 8:
            rationale.append(
                "High authority source"
            )

        if recency >= 8:
            rationale.append(
                "Recent publication"
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