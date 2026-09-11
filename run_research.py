import sys
from app.research.research_pipeline import ResearchPipeline
from app.synthesis.insight_engine import InsightEngine
from app.agents.search_agent import PathfinderAgent
from app.agents.synthesis_agent import ScribeAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.orchestrator import NexusOrchestrator

def main():
    # Setup engines
    search_engine = ResearchPipeline()
    insight_engine = InsightEngine()

    # Setup agents
    nexus = NexusOrchestrator(
        PathfinderAgent(search_engine), 
        ScribeAgent(insight_engine), 
        ReviewerAgent()
    )

    topic = "Impact of mobile money on loan repayment"
    result = nexus.run_research_loop(topic)
    
    print(f"\n[Final Result] Topic: {result['topic']}")
    print(f"[Grounding Score]: {result['review']['grounding_score']}")

if __name__ == '__main__':
    main()