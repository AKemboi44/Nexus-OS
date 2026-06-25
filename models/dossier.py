from typing import List, Dict

class Dossier:
    def __init__(self, query: str):
        self.query = query
        self.included_sources: List[str] = []
        self.excluded_sources: List[str] = []
        self.evidence_summary: List[str] = []
        self.themes: List[str] = []
        self.scoring_summary: List[str] = []
        self.decision_rationales: List[str] = []
        self.identified_gaps: List[str] = []

    def __repr__(self):
        return f"Dossier(query='{self.query[:50]}...')"

    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'included_sources': self.included_sources,
            'evidence_summary': self.evidence_summary,
            'themes': self.themes,
            'identified_gaps': self.identified_gaps,
            'scoring_summary': self.scoring_summary
        }
