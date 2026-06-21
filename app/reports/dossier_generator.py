"""
Nexus OS Research Dossier Generator.
"""

from models.research_dossier import ResearchDossier

class DossierGenerator:

    def generate(
        self,
        query: str,
        included_sources: list[str],
        excluded_sources: list[str],
        evidence_summary: list[str],
        scoring_summary: list[str],
        decision_rationales: list[str]
    ) -> ResearchDossier:
        return ResearchDossier(
            query=query,

            included_sources=included_sources,

            excluded_sources=excluded_sources,

            evidence_summary=evidence_summary,

            scoring_summary=scoring_summary,

            decision_rationales=decision_rationales
        )

if __name__ == "__main__":
    print(run())