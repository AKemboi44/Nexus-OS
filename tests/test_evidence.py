from models.evidence import Evidence

def test_evidence_creation():
    evidence = Evidence(
        methodology = "Survey"
    )

    assert evidence.methodology == "Survey"

    assert evidence.findings == []

    assert evidence.limitations == []

    assert evidence.future_work == []