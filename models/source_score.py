
from pydantic import BaseModel


class SourceScore(BaseModel):

    source_id: str

    relevance: float

    authority: float

    recency: float

    methodology_score: float

    total_score: float

    decision: str = ""

    rationale: list[str]