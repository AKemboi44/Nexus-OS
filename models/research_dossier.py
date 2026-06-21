
# Defines research dossier data parameters

from pydantic import BaseModel


class ResearchDossier(BaseModel):

    query: str

    included_sources: list[str]

    excluded_sources: list[str]

    evidence_summary: list[str]

    scoring_summary: list[str]

    decision_rationales: list[str]