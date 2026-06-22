"""
Nexus OS Research Pipeline

Purpose
-------
Coordinates all Nexus OS subsystems.

Current Flow
------------
Query
    ↓
Discovery
    ↓
Source
    ↓
Extraction
    ↓
Evidence
    ↓
Scoring
    ↓
Inclusion
    ↓
Research Dossier

This is the first orchestration layer.
"""


# Discovery
from app.discovery.openalex import OpenAlexDiscovery


# Extraction
from app.extraction.extractor import EvidenceExtractor


# Scoring
from app.scoring.scorer import SourceScorer


# Inclusion
from app.scoring.inclusion_engine import InclusionEngine


# Reporting
from app.reports.dossier_generator import DossierGenerator
class ResearchPipeline:
    """
    Main Nexus OS orchestration layer.
    """

    def __init__(self):
        """
        Initialize all subsystems.

        Later versions may use:
        - Dependency injection
        - Configuration
        - Plugin loading
        """

        self.discovery = OpenAlexDiscovery()

        self.extractor = EvidenceExtractor()

        self.scorer = SourceScorer()

        self.inclusion = InclusionEngine()

        self.generator = DossierGenerator()

    def run_research(
        self,
        query: str
    ):
        """
        Execute a complete research workflow.

        Parameters
        ----------
        query : str

        Returns
        -------
        ResearchDossier
        """

        print(
            f"\nStarting research: {query}\n"
        )

        # ---------------------------------
        # Discovery Stage
        # ---------------------------------

        discovery_result = (
            self.discovery.search(query)
        )

        print(
            f"Discovered "
            f"{len(discovery_result.sources)} "
            f"sources"
        )

        included_sources = []

        excluded_sources = []

        evidence_summary = []

        scoring_summary = []

        decision_rationales = []

        for source in discovery_result.sources:
            print(
                "\nABSTRACT:"
            )

            print(
                source.abstract[:300]
            )
            evidence = (
                self.extractor.extract(
                    source.abstract
                    or ""
                )
            )
            print("\nEVIDENCE:")

            print(evidence)

            score = self.scorer.score(
                source_id=source.id,
                query=query,
                title=source.title,
                year=source.year or 2000,
                methodology=evidence.methodology
            )

            decision = (
                self.inclusion.decide(score)
            )

            if (
                decision.decision
                ==
                "include"
            ):

                included_sources.append(
                    source.title
                )

            else:

                excluded_sources.append(
                    source.title
                )
            # We intentionally de-duplicate findings
            # because multiple papers often support the same observation.
            # Later versions will track source-level provenance instead of collapsing findings.
            for finding in evidence.findings:

                if finding not in evidence_summary:
                    evidence_summary.append(
                        finding
                    )

            scoring_summary.append(
                f"{source.title}: "
                f"{score.total_score:.2f}"
            )

            decision_rationales.extend(
                decision.rationale
            )

        dossier = (
            self.generator.generate(
                query=query,

                included_sources=
                included_sources,

                excluded_sources=
                excluded_sources,

                evidence_summary=
                evidence_summary,

                scoring_summary=
                scoring_summary,

                decision_rationales=
                decision_rationales
            )
        )

        return dossier

    # TODO:
    # Replace print statements with a structured
    # logging framework once Nexus OS moves
    # beyond local development.
    #
    # Candidate options:
    # - logging (stdlib)
    # - structlog
    # - loguru