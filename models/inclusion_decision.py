"""
Defines the parameters of the inclusion decision.
Represents the final inclusion or exclusion
decision for a source.
"""

from pydantic import BaseModel


class InclusionDecision(BaseModel):

    source_id: str

    decision: str

    confidence: float

    rationale: list[str]