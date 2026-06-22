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

Design Notes
------------
The pipeline intentionally acts as an orchestrator.

It should coordinate work between subsystems
rather than implementing business logic itself.

Future versions may add:

- Research Memory
- Theme Detection
- Gap Analysis
- Provenance Tracking
- Project Management
"""

# ---------------------------------
# Configuration
# ---------------------------------

# Development-only diagnostics.
#
# Later versions should replace this
# with structured logging.
#
# Example:
# - logging
# - structlog
# - loguru

DEBUG_MODE = True


# ---------------------------------
# Discovery
# ---------------------------------

from app.discovery.openalex import OpenAlexDiscovery


# ---------------------------------
# Extraction
# ---------------------------------

from app.extraction.extractor import EvidenceExtractor


# ---------------------------------
# Scoring
# ---------------------------------

from app.scoring.scorer import SourceScorer


# ---------------------------------
# Inclusion
# ---------------------------------

from app.scoring.inclusion_engine import InclusionEngine


# ---------------------------------
# Reporting
# ---------------------------------

from app.reports.dossier_generator import DossierGenerator


class ResearchPipeline:
    """
    Main Nexus OS orchestration layer.
    """

    def __init__(self):
        """
        Initialize all subsystems.

        We keep initialization centralized
        so future dependency injection
        becomes easier.
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

        # ---------------------------------
        # Dossier Assembly Collections
        # ---------------------------------
        #
        # These structures accumulate outputs
        # from the workflow and are later
        # assembled into a ResearchDossier.
        #
        # Future versions may replace these
        # with a dedicated DossierBuilder.
        #

        included_sources = []

        excluded_sources = []

        evidence_findings = []

        scoring_summary = []

        decision_rationales = []

        # ---------------------------------
        # Process Sources
        # ---------------------------------

        for source in discovery_result.sources:

            # ---------------------------------
            # Development Diagnostics
            # ---------------------------------

            if DEBUG_MODE:

                print("\nABSTRACT:")

                print(
                    (source.abstract or "")[:300]
                )

            # ---------------------------------
            # Evidence Extraction
            # ---------------------------------

            evidence = (
                self.extractor.extract(
                    source.abstract or ""
                )
            )

            if DEBUG_MODE:

                print("\nEVIDENCE:")

                print(evidence)

            # ---------------------------------
            # Source Scoring
            # ---------------------------------

            score = self.scorer.score(
                source_id=source.id,

                query=query,

                title=source.title,

                year=source.year or 2000,

                methodology=evidence.methodology
            )

            # ---------------------------------
            # Inclusion Decision
            # ---------------------------------

            decision = (
                self.inclusion.decide(
                    score
                )
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

            # ---------------------------------
            # Evidence Aggregation
            # ---------------------------------
            #
            # We intentionally de-duplicate
            # findings because multiple papers
            # often support the same conclusion.
            #
            # Future versions will preserve
            # source-level provenance instead
            # of collapsing findings.
            #

            for finding in evidence.findings:

                if (
                    finding
                    not in evidence_findings
                ):

                    evidence_findings.append(
                        finding
                    )

            # ---------------------------------
            # Scoring Summary
            # ---------------------------------

            scoring_summary.append(
                f"{source.title}: "
                f"{score.total_score:.2f}"
            )

            # ---------------------------------
            # Decision Rationale
            # ---------------------------------

            decision_rationales.extend(
                decision.rationale
            )

        # ---------------------------------
        # Dossier Generation
        # ---------------------------------

        dossier = (
            self.generator.generate(
                query=query,

                included_sources=
                included_sources,

                excluded_sources=
                excluded_sources,

                evidence_summary=
                evidence_findings,

                scoring_summary=
                scoring_summary,

                decision_rationales=
                decision_rationales
            )
        )

        return dossier