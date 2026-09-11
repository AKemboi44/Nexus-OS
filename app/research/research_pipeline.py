import os
import sys
from typing import List, Dict

# Standardize path for local PyCharm and Colab execution
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.research_dossier import ResearchDossier
from app.synthesis.insight_engine import InsightEngine

class ResearchPipeline:
    # \"\"\"
    # Nexus OS Research Pipeline (v0.6.1)
    # Orchestrates discovery and prepares evidence for the Scribe Agent.
    # \"\"\"
    def __init__(self):
        self.insight_engine = InsightEngine()

    def _discover_sources_real(self, query: str) -> List[Dict]:
        # "Internal discovery logic with fallback data.
        return [
            {'title': 'Digital Finance Impact', 'abstract': 'Mobile money usage correlates with higher savings.', 'year': '2023'},
            {'title': 'Credit Scoring Innovation', 'abstract': 'Alternative data improves loan access.', 'year': '2022'}
        ]

    def run_research(self, query: str) -> ResearchDossier:
        # "Main research loop.
        dossier = ResearchDossier(query=query)
        raw_papers = self._discover_sources_real(query)

        dossier.included_sources = [f"{p['title']} ({p['year']})" for p in raw_papers]
        dossier.evidence_summary = [p['abstract'] for p in raw_papers]

        evidence_blocks = [{'id': f'p_{i}', 'content': p['abstract']} for i, p in enumerate(raw_papers)]
        insight_obj = self.insight_engine.generate_insight(query, evidence_blocks)
        
        dossier.themes = [insight_obj.insight]
        dossier.decision_rationales = ["Executed via stable v0.6.1 discovery logic."]

        return dossier

if __name__ == '__main__':
    pipeline = ResearchPipeline()
    res = pipeline.run_research("Local Environment Verification")
    print(f"Insight: {res.themes[0]}")
