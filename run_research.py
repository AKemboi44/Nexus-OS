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

import os
import sys
from dotenv import load_dotenv

# Ensure project root is in path for local and containerized execution
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Explicitly read environment configuration variables beforehand
load_dotenv(os.path.join(project_root, '.env'))

from app.research.research_pipeline import ResearchPipeline
from app.synthesis.insight_engine import InsightEngine
from app.agents.pathfinder_agent import PathfinderAgent
from app.agents.synthesis_agent import ScribeAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.squire_agent import SquireAgent
from app.agents.orchestrator import NexusOrchestrator


def main():
    # 1. Initialize Core Engines and Storage Providers
    search_engine = ResearchPipeline()
    insight_engine = InsightEngine()

    # 2. Instantiate Specialized Agents (Correctly maps PathfinderAgent import)
    pathfinder = PathfinderAgent(search_engine)
    scribe = ScribeAgent(insight_engine)
    reviewer = ReviewerAgent()
    squire = SquireAgent()

    # 3. Initialize Orchestrator with safe parameters (Defines 'orchestrator' cleanly)
    orchestrator = NexusOrchestrator(pathfinder, scribe, reviewer, squire, max_retries=2)

    print("\n" + "=" * 60)
    print("NEXUS OPERATING SYSTEM v1.0.0 INTERACTIVE INTERFACE")
    print("=" * 60)

    # 4. Accept user strings directly out of standard system prompts
    topic = input("Enter core research topic/query (or press Enter for default): ").strip()
    if not topic:
        topic = "Impact of mobile money on loan repayment"

    custom_prompt = input("Enter any specific angle or custom directive filters (or press Enter): ").strip()
    if not custom_prompt:
        custom_prompt = None

    sources_input = input("Enter number of sources to parse (default 5, scale higher for deep sweeps): ").strip()
    try:
        max_sources = int(sources_input) if sources_input else 5
    except ValueError:
        max_sources = 5

    # 5. Execute Autonomous Research Pipeline using dynamic arguments
    results = orchestrator.run_research_loop(
        topic=topic,
        custom_prompt=custom_prompt,
        max_sources=max_sources
    )

    print(f"\n{'=' * 60}")
    print(f"NEXUS OS v1.0.0 DYNAMIC CYCLE RUN COMPLETED")
    print(f"{'=' * 60}")

    # Drill down through nested dictionary data wrappers to print a clean summary trace
    insight_data = results.get('insight', {})
    if isinstance(insight_data, dict):
        inner_insight = insight_data.get('insight', '')
        if isinstance(inner_insight, dict):
            insight_text = inner_insight.get('text') or inner_insight.get('summary') or str(inner_insight)
        else:
            insight_text = str(inner_insight)
    else:
        insight_text = str(insight_data)

    print(f"Final Insight Summary (First 150 chars): {insight_text[:150]}...")
    print(f"Factual Grounding Score: {results.get('review', {}).get('score', 'N/A')}")
    print(f"Comprehensive Tabular Report Output saved to: {results['audit_file']}")


if __name__ == '__main__':
    main()