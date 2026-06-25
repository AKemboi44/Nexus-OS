"""
Nexus OS v0.5.0 - Agent Layer
Generated for clarity and high maintainability.
"""
import os
import sys

# Path resolution to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from typing import List, Dict
from .search_agent import SearchAgent
from .synthesis_agent import SynthesisAgent

class ResearchOrchestrator:
    def __init__(self):
        self.searcher = SearchAgent()
        self.synthesizer = SynthesisAgent()

    def run_research_loop(self, query: str) -> Dict:
        print(f"\n[Orchestrator] Starting multi-agent loop for: {query}")
        
        # Step 1: Search Phase (Pathfinder)
        search_results = self.searcher.execute(query=query)
        raw_data = search_results.get('output', [])
        
        # Step 2: Synthesis Phase (Scribe)
        # Convert raw paper data into evidence blocks for the synthesizer
        evidence_blocks = [
            {'content': p.get('abstract', ''), 'citation': p.get('title', 'Unknown')} 
            for p in raw_data if p.get('abstract')
        ]
        
        synthesis_result = self.synthesizer.execute(topic=query, evidence=evidence_blocks)
        
        return {
            "query": query,
            "sources_count": len(raw_data),
            "final_insight": synthesis_result.get('output', {})
        }
