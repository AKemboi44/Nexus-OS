"""
Methodology Engine

Purpose
-------
Estimate evidence quality based on the research methodology identified during extraction.

Why This Exists
---------------
Not all research evidence is equal.

A randomized study generally provides stronger evidence than a simple survey.

Separating methodology scoring from the main scorer allows us to evolve the framework independently.

Future Versions
---------------
Later versions may incorporate:

- Peer review status
- Sample size
- Citation counts
- Research design quality
- Confidence intervals
- Statistical significance
"""


class MethodologyEngine:

    def score(
        self,
        methodology: str | None
    ) -> tuple[float, list[str]]:
        """
        Returns:

        methodology_score
        rationale
        """

        rationale = []

        # -----------------------------
        # Strongest evidence types
        # -----------------------------

        if methodology == "Randomized Study":

            rationale.append(
                "Randomized study design"
            )

            return 10.0, rationale

        if methodology == "Field Experiment":

            rationale.append(
                "Field experiment"
            )

            return 9.0, rationale

        # -----------------------------
        # Strong evidence
        # -----------------------------

        if methodology == "Panel Study":

            rationale.append(
                "Panel study methodology"
            )

            return 8.0, rationale

        if methodology == "Research Investigation":

            rationale.append(
                "Formal investigation"
            )

            return 7.0, rationale

        # -----------------------------
        # Moderate evidence
        # -----------------------------

        if methodology == "Survey":

            rationale.append(
                "Survey-based evidence"
            )

            return 6.0, rationale

        # -----------------------------
        # Unknown methodology
        # -----------------------------

        rationale.append(
            "Methodology not identified"
        )

        return 3.0, rationale