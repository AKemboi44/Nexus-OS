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

        elif "panel sample" in text:

            methodology = "Panel Study"

        elif "randomly assigned" in text:

            methodology = "Randomized Study"

        elif "we worked with" in text:

            methodology = "Field Experiment"

        elif "estimate" in text:

            methodology = "Empirical Analysis"

        elif "investigate" in text:

            methodology = "Research Investigation"

        # Findings detection

        if "findings indicate" in text:

            findings.append(
                "Findings indicate increased access to financial services"
            )
        if "we find" in text:
            findings.append(
                "Study reports significant findings"
            )

        if "evidence" in text:
            findings.append(
                "Evidence presented"
            )

        if "improve" in text:
            findings.append(
                "Positive impact reported"
            )

        if "impact" in text:
            findings.append(
                "Impact assessed"
            )

        # Limitations detection

        if "limitations include" in text:

            limitations.append(
                "Small sample size"
            )

        if "however" in text:
            limitations.append(
                "Potential limitations discussed"
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