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
        self.opportunity_areas: List[str] = [] # Added for venture/monetization strategy mapping
        self.problems_to_solve: List[str] = []
        self.scoring_summary: List[str] = []
        self.decision_rationales: List[str] = []

    def __repr__(self):
        return f"ResearchDossier(query='{self.query[:40]}...', included={len(self.included_sources)}, gaps={len(self.research_gaps)})"
