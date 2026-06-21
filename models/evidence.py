# This extracts the evidence from a research source
from pydantic import BaseModel, Field

class Evidence (BaseModel):
    methodology : str|None  = None
    findings : list[str] = Field(default_factory=list)
    limitations : list[str] = Field(default_factory=list)
    future_work : list[str] = Field(default_factory=list)


