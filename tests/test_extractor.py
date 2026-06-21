from app import EvidenceExtractor


def test_extract_evidence():

    abstract = """
    This study uses survey data
    to investigate mobile money.

    Findings indicate increased
    access to financial services.

    Limitations include a small
    sample size.

    Future work should examine
    cross-country comparisons.
    """

    extractor = EvidenceExtractor()

    evidence = extractor.extract(
        abstract
    )

    assert evidence.methodology == "Survey"

    assert len(
        evidence.findings
    ) > 0

    assert len(
        evidence.limitations
    ) > 0

    assert len(
        evidence.future_work
    ) > 0