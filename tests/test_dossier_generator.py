from app import (
    DossierGenerator
)


def test_generate_dossier():

    generator = DossierGenerator()

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

        scoring_summary=[
            "World Bank score: 7.75"
        ],

        decision_rationales=[
            "Trusted institution"
        ]
    )

    assert (
        dossier.query
        ==
        "mobile money repayment"
    )