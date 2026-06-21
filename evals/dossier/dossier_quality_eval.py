from app.reports.dossier_generator import (
    DossierGenerator
)

from evals.eval_result import EvalResult

def run():

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

    score = 0

    if dossier.included_sources:
        score += 0.2

    if dossier.excluded_sources:
        score += 0.2

    if dossier.evidence_summary:
        score += 0.2

    if dossier.scoring_summary:
        score += 0.2

    if dossier.decision_rationales:
        score += 0.2

    return EvalResult(
    name="dossier_quality",

    passed=score >= 0.8,

    score=score,

    details="Dossier quality evaluation",

    rationale="All required sections present"
)

if __name__ == "__main__":
    print(run())