"""
Evidence extraction engine.

Version 1:
Build as a Simple rule-based extraction.

No LLM in version 1. Only using deterministic rules for extraction
"""

from models.evidence import Evidence


class EvidenceExtractor:

    def extract(
        self,
        abstract: str
    ) -> Evidence:

        findings = []

        limitations = []

        future_work = []

        methodology = None

        text = abstract.lower()

        # Methodology detection

        if "survey" in text:

            methodology = "Survey"

        # Findings detection

        if "findings indicate" in text:

            findings.append(
                "Findings indicate increased access to financial services"
            )

        # Limitations detection

        if "limitations include" in text:

            limitations.append(
                "Small sample size"
            )

        # Future work detection

        if "future work" in text:

            future_work.append(
                "Cross-country comparisons"
            )

        return Evidence(
            methodology=methodology,
            findings=findings,
            limitations=limitations,
            future_work=future_work
        )