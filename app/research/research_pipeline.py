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
Theme Detection
    ↓
Research Dossier

Design Notes
------------
The pipeline intentionally acts as an orchestrator.

It coordinates subsystem execution
rather than implementing business logic.

Future versions may add:

- Research Memory
- Gap Analysis
- Provenance Reporting
- Project Management
- MCP Exposure Layer
"""

# ---------------------------------
# Configuration
# ---------------------------------

# Development-only diagnostics.
#
# Later versions should replace this
# with structured logging.
#
# Candidate options:
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

# ---------------------------------
# Provenance
# ---------------------------------

from models.evidence_item import (
    EvidenceItem
)

# ---------------------------------
# Synthesis
# ---------------------------------

from app.synthesis.theme_engine import (
    ThemeEngine
)

from app.synthesis.gap_engine import (
    GapEngine
)


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

        # Theme detection is the first
        # synthesis capability in Nexus OS.
        #
        # Themes are generated only from
        # trusted evidence that has passed
        # the inclusion stage.
        #
        # This prevents low-quality sources
        # from influencing synthesis results.

        self.theme_engine = (
            ThemeEngine()
        )

        # Gap detection identifies areas where
        # the evidence base appears limited.
        #
        # This is the first capability that
        # reasons about what is missing rather
        # than what is present.

        self.gap_engine = (
            GapEngine()
        )

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

        included_sources = []

        excluded_sources = []

        # Human-readable evidence findings
        # currently shown in the dossier.

        evidence_findings = []

        # ---------------------------------
        # Provenance Collections
        # ---------------------------------
        #
        # all_evidence_items
        #     Preserves the full audit trail.
        #
        # included_evidence_items
        #     Contains only trusted evidence
        #     that passed inclusion.
        #
        # Theme detection operates only on
        # included evidence.

        all_evidence_items = []

        included_evidence_items = []

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
            # provenance inside the dossier.

            for finding in evidence.findings:

                evidence_item = (
                    EvidenceItem(
                        source_id=source.id,

                        source_title=
                        source.title,

                        methodology=
                        evidence.methodology,

                        finding=finding
                    )
                )

                # Preserve complete audit trail.

                all_evidence_items.append(
                    evidence_item
                )

                # Only trusted evidence
                # contributes to synthesis.

                if (
                    decision.decision
                    ==
                    "include"
                ):

                    included_evidence_items.append(
                        evidence_item
                    )

                # Provenance debugging.

                if DEBUG_MODE:

                    print("\nPROVENANCE:")

                    print(
                        source.title
                    )

                    print(
                        finding
                    )

                # Human-readable findings.

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
            # Decision Rationales
            # ---------------------------------

            decision_rationales.extend(
                decision.rationale
            )

        # ---------------------------------
        # Theme Detection
        # ---------------------------------

        themes = (
            self.theme_engine.detect_themes(
                included_evidence_items
            )
        )

        # ---------------------------------
        # Gap Detection
        # ---------------------------------

        gaps = (
            self.gap_engine.detect_gaps(
                themes
            )
        )

        gap_summary = [
            gap.title
            for gap in gaps
        ]
        if DEBUG_MODE:

            print("\nGAPS DETECTED:")

            for gap in gaps:
                print(
                    f"- {gap.title}"
                )

                print(
                    f"  Reason: "
                    f"{gap.rationale}"
                )

        # Theme summary is currently used
        # only for diagnostics.
        #
        # Future versions will expose themes
        # directly inside the ResearchDossier.

        theme_summary = [
            theme.name
            for theme in themes
        ]

        if DEBUG_MODE:

            print("\nTHEME SUMMARY:")

            for theme in theme_summary:
                print(
                    f"- {theme}"
                )

      # To remove later: Theme detected is just for debug
        if DEBUG_MODE:

            print("\nTHEMES DETECTED:")

            for theme in themes:

                print(
                    f"- {theme.name}"
                )

                print(
                    "  Sources:"
                )

                for source in (
                    theme.supporting_sources
                ):

                    print(
                        f"    - {source}"
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

                themes=
                theme_summary,

                scoring_summary=
                scoring_summary,

                decision_rationales=
                decision_rationales
            )
        )

        return dossier