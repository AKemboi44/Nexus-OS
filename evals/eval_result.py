from pydantic import BaseModel

class EvalResult(BaseModel):
    name: str
    passed: bool
    score: float
    details: str
    rationale: str

