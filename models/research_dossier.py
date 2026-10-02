from typing import List, Dict, Any


class ResearchDossier:
    def __init__(
        self,
        query: str,
        abstract: str = "",
        included_sources: List[Any] = None,
        excluded_sources: List[Any] = None,
        evidence_summary: List[str] = None,
        themes: List[str] = None,
        contradictions: List[str] = None,
        research_gaps: List[str] = None,
        research_areas: List[str] = None,
        opportunity_areas: List[str] = None,
        problems_to_solve: List[str] = None,
        scoring_summary: List[str] = None,
        decision_rationales: List[str] = None,
        quality_report: Dict[str, Any] = None,
        provenance: List[Dict[str, Any]] = None,
        **kwargs
    ):
        self.query = query
        self.abstract = abstract or ""
        self.included_sources = included_sources if included_sources is not None else []
        self.excluded_sources = excluded_sources if excluded_sources is not None else []
        self.evidence_summary = evidence_summary if evidence_summary is not None else []
        self.themes = themes if themes is not None else []
        self.contradictions = contradictions if contradictions is not None else []
        self.research_gaps = research_gaps if research_gaps is not None else []
        self.research_areas = research_areas if research_areas is not None else []
        self.opportunity_areas = opportunity_areas if opportunity_areas is not None else []
        self.problems_to_solve = problems_to_solve if problems_to_solve is not None else []
        self.scoring_summary = scoring_summary if scoring_summary is not None else []
        self.decision_rationales = decision_rationales if decision_rationales is not None else []
        self.quality_report = quality_report if quality_report is not None else {}
        self.provenance = provenance if provenance is not None else []
        self.report_data: Dict[str, Any] = kwargs

    def to_dict(self):
        return {
            "query": self.query,
            "abstract": self.abstract,
            "included_sources": self.included_sources,
            "excluded_sources": self.excluded_sources,
            "evidence_summary": self.evidence_summary,
            "themes": self.themes,
            "contradictions": self.contradictions,
            "research_gaps": self.research_gaps,
            "research_areas": self.research_areas,
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
