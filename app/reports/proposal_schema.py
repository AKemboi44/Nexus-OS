"""Proposal schema v2: Pydantic models for validation and provider communication."""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class ParagraphBlock(BaseModel):
    """A paragraph with optional evidence citations."""
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    kind: str = Field(..., description="evidence, interpretation, proposal, or limitation")
    evidence_ids: List[str] = Field(default_factory=list)


class ThemeBlock(BaseModel):
    """A literature theme with title and evidence-linked content."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    blocks: List[ParagraphBlock]


class ResearchQuestion(BaseModel):
    """A research question with optional ID."""
    model_config = ConfigDict(extra="forbid")

    question_id: Optional[str] = None
    text: str = Field(..., min_length=1)
    evidence_ids: List[str] = Field(default_factory=list)


class ResearchObjective(BaseModel):
    """A research objective linked to one or more questions."""
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    question_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class MethodologySection(BaseModel):
    """Methodology with design, data collection, analysis, limitations."""
    model_config = ConfigDict(extra="forbid")

    research_design: List[ParagraphBlock] = Field(default_factory=list)
    data_collection: List[ParagraphBlock] = Field(default_factory=list)
    analysis: List[ParagraphBlock] = Field(default_factory=list)
    limitations: List[ParagraphBlock] = Field(default_factory=list)


class ProposalDraftV2(BaseModel):
    """Proposal schema v2: complete structured research proposal."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(..., description="Must be 'proposal.v2'")
    overview: List[ParagraphBlock]
    literature_insights: List[ThemeBlock] = Field(
        ..., description="Up to 5 themes; target 3-5 when supported"
    )
    contradictions_and_limitations: List[ParagraphBlock]
    research_gap: List[ParagraphBlock]
    research_problem: List[ParagraphBlock]
    research_questions: List[ResearchQuestion] = Field(
        ..., description="One primary + 0-3 supporting"
    )
    research_objectives: List[ResearchObjective] = Field(
        ..., description="One general + 0-3 specific"
    )
    methodology: MethodologySection
    conclusion: List[ParagraphBlock]
    evidence_limitations: List[ParagraphBlock]


class ProposalPrompt(BaseModel):
    """Prompt configuration for proposal generation."""
    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=2048, le=8192)
    target_min_words: int = Field(default=1200)
    target_max_words: int = Field(default=1600)
    hard_max_words: int = Field(default=1800)


def proposal_json_schema() -> dict:
    """Generate JSON schema from ProposalDraftV2 for provider instruction."""
    return ProposalDraftV2.model_json_schema()
