from app.research.research_pipeline import (
    ResearchPipeline
)


def test_pipeline_creation():

    pipeline = ResearchPipeline()

    assert pipeline is not None