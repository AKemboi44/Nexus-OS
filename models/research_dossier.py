from typing import List, Dict, Any


class ResearchDossier:
    def __init__(self, query: str):
        self.query = query
        self.included_sources: List[Any] = []
        self.excluded_sources: List[Any] = []
        self.evidence_summary: List[str] = []
        self.themes: List[str] = []
        self.contradictions: List[str] = []  # Added for comprehensive Phase 5 analysis
        self.research_gaps: List[str] = []   # Added for explicit structural tracking
        self.opportunity_areas: List[str] = []  # Added for venture/monetization strategy mapping
        self.problems_to_solve: List[str] = []
        self.scoring_summary: List[str] = []
        self.decision_rationales: List[str] = []
        self.quality_report: Dict[str, Any] = {}
        self.provenance: List[Dict[str, Any]] = []
        self.report_data: Dict[str, Any] = {}

    def to_dict(self):
        return {
            "query": self.query,
            "included_sources": self.included_sources,
            "excluded_sources": self.excluded_sources,
            "evidence_summary": self.evidence_summary,
            "themes": self.themes,
            "contradictions": self.contradictions,
            "research_gaps": self.research_gaps,
            "opportunity_areas": self.opportunity_areas,
            "problems_to_solve": self.problems_to_solve,
            "quality_report": self.quality_report,
            "provenance": self.provenance,
            **self.report_data,
        }

    def model_dump(self):
        return self.to_dict()

    def get(self, key: str, default=None):
        return self.to_dict().get(key, default)

    def __getitem__(self, key):
        return self.to_dict()[key]

    def __contains__(self, key):
        return key in self.to_dict()

    def __repr__(self):
        return f"ResearchDossier(query='{self.query[:40]}...', included={len(self.included_sources)}, gaps={len(self.research_gaps)})"
