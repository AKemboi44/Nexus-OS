from app.reports.dossier_generator import DossierGenerator
from app.synthesis.providers import SynthesisProvider, SynthesisProviderRegistry


class MockProvider(SynthesisProvider):
    name = "mock"

    def is_configured(self) -> bool:
        return True

    def generate_text(self, prompt: str, **kwargs) -> str:
        return (
            "ABSTRACT: Mobile money improves access to credit and formal savings.\n"
            "KEY THEMES: Theme 1\n"
            "CONTRADICTIONS: Contradiction 1\n"
            "RESEARCH GAPS: Gap 1\n"
            "RESEARCH AREAS: Area 1\n"
            "OPPORTUNITY AREAS: Opportunity 1\n"
            "PROBLEMS TO SOLVE: Problem 1\n"
        )


def test_generate_dossier():
    generator = DossierGenerator(provider_registry=SynthesisProviderRegistry(providers=[MockProvider()]))

    dossier = generator.generate(
        query="mobile money repayment",

        included_sources=[
            "World Bank Report"
        ],

        excluded_sources=[
            "Personal Blog"
        ],

        evidence_summary=[
            "Mobile money improves access"
        ],

        themes=[],

        scoring_summary=[
            "World Bank score: 7.75"
        ],

        decision_rationales=[
            "Trusted institution"
        ]
    )

    assert dossier.query == "mobile money repayment"
    assert "Mobile money" in dossier.abstract