"""
Theme Model

Purpose
-------
Represents a recurring pattern
observed across multiple pieces
of evidence.

Design Philosophy
-----------------
Themes should be traceable.

Every theme must be backed by:

- Evidence
- Sources

Future versions may include:

- Confidence
- Contradictions
- Evidence strength
- Consensus metrics
"""

from pydantic import BaseModel


class Theme(BaseModel):

    name: str

    supporting_sources: list[str]

    supporting_findings: list[str]