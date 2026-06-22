from models.evidence_item import (
    EvidenceItem
)


def test_evidence_item_creation():

    item = EvidenceItem(
        source_id="1",

        source_title=(
            "Mobile Money Study"
        ),

        methodology=(
            "Panel Study"
        ),

        finding=(
            "Impact assessed"
        )
    )

    assert (
        item.source_id
        ==
        "1"
    )

    assert (
        item.finding
        ==
        "Impact assessed"
    )