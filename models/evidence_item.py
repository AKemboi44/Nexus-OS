"""
Evidence item with source provenance.

We intentionally keep provenance attached to evidence because future synthesis,
theme detection and reporting all depend on traceability.
"""

from pydantic import BaseModel


class EvidenceItem(BaseModel):

    source_id: str

    source_title: str

    finding: str