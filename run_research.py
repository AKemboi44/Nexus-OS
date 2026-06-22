"""
Manual Nexus OS execution script.

Runs a complete research workflow
and prints the resulting dossier.
"""

from app.research.research_pipeline import (
    ResearchPipeline
)


def main():

    pipeline = ResearchPipeline()

    dossier = pipeline.run_research(
        "Impact of mobile money on loan repayment"
    )

    print("\n" + "=" * 60)
    print("NEXUS OS RESEARCH DOSSIER")
    print("=" * 60)

    print("\nQuery:")
    print(dossier.query)

    print("\nIncluded Sources:")
    for source in dossier.included_sources:
        print(f"- {source}")

    print("\nExcluded Sources:")
    for source in dossier.excluded_sources:
        print(f"- {source}")

    print("\nEvidence Summary:")
    for item in dossier.evidence_summary:
        print(f"- {item}")

    print("\nThemes:")
    for theme in dossier.themes:
        print(
            f"- {theme}"
        )

    print("\nScoring Summary:")
    for item in dossier.scoring_summary:
        print(f"- {item}")

    print("\nDecision Rationales:")
    for item in dossier.decision_rationales:
        print(f"- {item}")


if __name__ == "__main__":
    main()