import os
import sys
import arxiv
from typing import List, Dict

# Ensure project root is in sys.path for proper module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

class ArxivDiscovery:
    '''
    Handles discovery of research papers from ArXiv.
    '''
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        # self.announce(f"Searching ArXiv for: {query}") # Temporarily disabled for clean output
        try:
            search_results = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            papers = []
            for result in search_results.results():
                papers.append({
                    'title': result.title,
                    'abstract': result.summary,
                    'year': result.published.year,
                    'venue': 'arXiv',
                    'url': result.entry_id
                })
            return papers
        except Exception as e:
            # self.announce(f"ArXiv search failed: {e}") # Temporarily disabled
            return []

    # def announce(self, message: str):
    #     print(f"[ArXivDiscovery]: {message}") # Temporarily disabled
