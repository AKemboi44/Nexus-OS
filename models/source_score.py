
from datetime import datetime

from pydantic import BaseModel


# Model defining scores for different research sources
class SourceScore(BaseModel):
    source_id: str
    relevance: float
    authority: float
    recency: float
    methodology: str
    total_score: float
    decisions: str
    rationale: list[str]