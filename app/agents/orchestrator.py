from .search_agent import PathfinderAgent
from .synthesis_agent import ScribeAgent
from .reviewer_agent import ReviewerAgent

class NexusOrchestrator:

    # The Orchestrator manages the handoff between Pathfinder, Scribe, and Reviewer.
    # It ensures the research loop flows from Discovery to Grounding.

    def __init__(self, pathfinder, scribe, reviewer):
        self.pathfinder = pathfinder
        self.scribe = scribe
        self.reviewer = reviewer

    def run_research_loop(self, topic: str):
        # Runs the complete v0.6.1 research lifecycle.
        search_results = self.pathfinder.execute(query=topic)
        sources = search_results["data"]
        synthesis_results = self.scribe.execute(topic=topic, raw_data=sources)
        insight = synthesis_results["insight"]
        review = self.reviewer.execute(insight=insight.get('insight', ''), evidence_items=sources)

        return {
            "topic": topic,
            "insight": insight,
            "review": review
        }