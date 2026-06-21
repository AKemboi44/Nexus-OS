from models.research_dossier import ResearchDossier


def test_dossier_creation():

    dossier = ResearchDossier(
        query="mobile money repayment",

        included_sources=[],

        excluded_sources=[],

        evidence_summary=[],

        scoring_summary=[],

        decision_rationales=[]
    )

    assert dossier.query == "mobile money repayment"