"""
Research Gap

Purpose
-------
Represents a potential gap identified
from the current body of trusted evidence.

Design Philosophy
-----------------
A gap is not a fact.

A gap is a hypothesis that indicates
where evidence appears limited.

Future versions may include:

- Confidence scores
- Supporting themes
- Contradictory evidence
- Suggested research questions
"""

from pydantic import BaseModel


class ResearchGap(BaseModel):

    title: str

    rationale: str

    supporting_themes: list[str]