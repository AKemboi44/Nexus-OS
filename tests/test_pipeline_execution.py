from app.research.research_pipeline import (
    ResearchPipeline
)


def test_pipeline_execution():

    pipeline = ResearchPipeline()

    dossier = pipeline.run_research(
        "mobile money repayment"
    )

    assert dossier is not None

    assert dossier.query == (
        "mobile money repayment"
    )
    assert len(dossier.included_sources) == len(dossier.report_data["included"])
    assert "excluded" in dossier.report_data
