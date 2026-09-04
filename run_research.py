import os
import sys

# Ensure project root is in path for local and containerized execution
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.research.research_pipeline import ResearchPipeline
from app.synthesis.insight_engine import InsightEngine
from app.agents.pathfinder_agent import PathfinderAgent
from app.agents.synthesis_agent import ScribeAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.squire_agent import SquireAgent
from app.agents.orchestrator import NexusOrchestrator

def main():
    # 1. Initialize Core Engines
    search_engine = ResearchPipeline()
    insight_engine = InsightEngine()

    # 2. Instantiate Specialized Agents
    pathfinder = PathfinderAgent(search_engine)
    scribe = ScribeAgent(insight_engine)
    reviewer = ReviewerAgent()
    squire = SquireAgent()

    # 3. Initialize Orchestrator with Iterative Feedback
    orchestrator = NexusOrchestrator(pathfinder, scribe, reviewer, squire, max_retries=2)

    # 4. Run Autonomous Research Cycle
    topic = "Impact of mobile money on loan repayment"
    results = orchestrator.run_research_loop(topic)

    print(f"\n{'='*60}")
    print(f"NEXUS OS v1.0.0 RESEARCH CYCLE COMPLETE")
    print(f"{'='*60}")
    # print(f"Insight Summary: {results['insight']['insight'][:150]}...")
    insight_data = results.get('insight', {})

    # Drill down if it's a nested dictionary
    if isinstance(insight_data, dict):
        inner_insight = insight_data.get('insight', '')
        if isinstance(inner_insight, dict):
            # Extract a specific text field from your insight engine dict model if it exists
            insight_text = inner_insight.get('text') or inner_insight.get('summary') or str(inner_insight)
        else:
            insight_text = str(inner_insight)
    else:
        insight_text = str(insight_data)

    # Slice cleanly now that we have a safe string representation
    print(f"Insight Summary: {insight_text[:150]}...")

    print(f"Grounding Score: {results['review'].get('score', 'N/A')}")
    print(f"Audit Trail saved to: {results['audit_file']}")

if __name__ == '__main__':
    main()