"""
Recency Engine

Purpose
-------
Evaluate how current a source is.

Why This Exists
---------------
In fast-moving domains, newer evidence often provides more relevant insights.

However, recency should never completely override strong evidence quality.

Separating recency scoring from the main scorer keeps the architecture modular and allows future calibration.

Future Versions
---------------
May incorporate:

- Domain-specific recency windows
- Publication type
- Citation velocity
- Research freshness signals
"""

from datetime import datetime


class RecencyEngine:

    def score(
        self,
        year: int
    ) -> tuple[float, list[str]]:
        """
        Returns:

        recency_score
        rationale
        """

        rationale = []

        current_year = datetime.now().year

        age = current_year - year

        # Very recent evidence

        if age <= 2:

            rationale.append(
                "Published within 2 years"
            )

            return 10.0, rationale

        # Recent evidence

        elif age <= 5:

            rationale.append(
                "Published within 5 years"
            )

            return 8.0, rationale

        # Moderately recent evidence

        elif age <= 10:

            rationale.append(
                "Published within 10 years"
            )

            return 5.0, rationale

        # Older evidence

        rationale.append(
            "Older publication"
        )

        return 2.0, rationale