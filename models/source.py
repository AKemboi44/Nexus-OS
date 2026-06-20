# models/source.py
from datetime import datetime

from pydantic import BaseModel

# Model defining research source parameters
class Source(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int | None
    url: str
    abstract: str| None
    source_type: str

# Model defining researcg evidences
class Evidence(BaseModel):
    methodology: str | None
    findings: list[str]
    limitations: list[str]
    future_work: list[str]

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

# Model defining project paramaters.
class ResearchProject(BaseModel):
    id: str
    query: str
    created_at: datetime
