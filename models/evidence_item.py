"""
Evidence Item

Purpose
-------
Represents a single piece of evidence
along with the source that produced it.

Why This Exists
---------------
Research conclusions are only useful
if we can trace them back to the source.

This model becomes the foundation for:

- Provenance
- Theme Detection
- Gap Analysis
- Audit Trails
- Research Memory

Design Principle
----------------
Evidence should never be separated
from its source.
"""

from pydantic import BaseModel


class EvidenceItem(BaseModel):

    source_id: str

    source_title: str

    methodology: str | None

    finding: str