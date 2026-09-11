"""
Relevance Engine

Purpose
-------
Estimate how closely a source matches a research question.

Design Philosophy
-----------------
Simple and explainable first.

Later versions may use:

- embeddings
- rerankers
- semantic search
- LLM scoring

without changing the rest of Nexus OS.
"""


class RelevanceEngine:

    def score(
        self,
        query: str,
        title: str
    ) -> tuple[float, list[str]]:

        rationale = []

        score = 0

        query_lower = query.lower()

        title_lower = title.lower()

        # ---------------------------------
        # Strong signals
        # ---------------------------------

        if "loan repayment" in title_lower:

            score += 7

            rationale.append(
                "Direct loan repayment match"
            )

        if "financial inclusion" in title_lower:

            score += 6

            rationale.append(
                "Financial inclusion match"
            )

        if "mobile money" in title_lower:

            score += 6

            rationale.append(
                "Mobile money match"
            )

        # ---------------------------------
        # Supporting signals
        # ---------------------------------

        if "mobile" in title_lower:

            score += 2

        if "loan" in title_lower:

            score += 2

        if "repayment" in title_lower:

            score += 2

        # ---------------------------------
        # Clamp
        # ---------------------------------

        score = min(
            score,
            10
        )

        return score, rationale