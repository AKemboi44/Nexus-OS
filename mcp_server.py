import sys
import json
import os
from dotenv import load_dotenv

# Ensure local project architecture paths map cleanly
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv(os.path.join(project_root, '.env'))

from app.research.research_pipeline import ResearchPipeline
from app.synthesis.insight_engine import InsightEngine
from app.agents.pathfinder_agent import PathfinderAgent
from app.agents.synthesis_agent import ScribeAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.squire_agent import SquireAgent
from app.agents.orchestrator import NexusOrchestrator


def execute_mcp_research(topic: str, custom_prompt: str = None, max_sources: int = 5) -> str:
    """Invokes the Nexus OS core agents over an MCP pipeline handle."""
    try:
        search_engine = ResearchPipeline()
        insight_engine = InsightEngine()

        pathfinder = PathfinderAgent(search_engine)
        scribe = ScribeAgent(insight_engine)
        reviewer = ReviewerAgent()
        squire = SquireAgent()

        orchestrator = NexusOrchestrator(pathfinder, scribe, reviewer, squire, max_retries=1)

        results = orchestrator.run_research_loop(
            topic=topic,
            custom_prompt=custom_prompt,
            max_sources=max_sources
        )

        insight_payload = results.get('insight', {})
        insight_text = insight_payload.get('insight', str(insight_payload)) if isinstance(insight_payload,
                                                                                          dict) else str(
            insight_payload)

        return json.dumps({
            "status": "success",
            "topic": topic,
            "synthesis": insight_text,
            "grounding_score": results.get('review', {}).get('score', 0.0),
            "excel_report_saved_at": results.get('audit_file', 'N/A')
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def main():
    """Main stdio loop reading JSON-RPC 2.0 frames expected by Claude Code and Cursor."""
    print("Nexus OS MCP Server Initialized. Awaiting JSON-RPC payloads over stdin...", file=sys.stderr)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            payload = json.loads(line)
            # Match standard Model Context Protocol schema parameters
            if payload.get("method") == "tools/call":
                params = payload.get("params", {})
                arguments = params.get("arguments", {})

                topic = arguments.get("topic", "Token optimization for production agents")
                custom_prompt = arguments.get("custom_prompt", None)
                max_sources = int(arguments.get("max_sources", 5))

                # Execute the live multi-agent core
                execution_result = execute_mcp_research(topic, custom_prompt, max_sources)

                # Return standard JSON-RPC response frame block back to host IDE terminal console
                response = {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "result": {
                        "content": [{"type": "text", "text": execution_result}]
                    }
                }
                print(json.dumps(response))
                sys.stdout.flush()
        except Exception as e:
            print(f"MCP Core Processing Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
