import sys
import json
import os

# --- CRITICAL BUFFER SHIELD: Immediately force unbuffered streams ---
# This prevents Windows from chunking stdout text and corrupting JSON packets
sys.stdout.reconfigure(encoding='utf-8')

# Ensure local project architecture paths map cleanly
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Defensively route any noisy top-level module imports into a safe wrapper function
# ... (Ensuring that the top levels of mcp_server.py match previous configurations) ...

def execute_mcp_research(topic: str, custom_prompt: str = None, max_sources: int = 5) -> str:
    """Invokes the Nexus OS core agents over an MCP pipeline handle."""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(project_root, '.env'))

        from app.research.research_pipeline import ResearchPipeline
        from app.synthesis.insight_engine import InsightEngine
        from app.agents.pathfinder_agent import PathfinderAgent
        from app.agents.synthesis_agent import ScribeAgent
        from app.agents.reviewer_agent import ReviewerAgent
        from app.agents.squire_agent import SquireAgent
        from app.agents.orchestrator import NexusOrchestrator

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
        if isinstance(insight_payload, dict):
            inner_insight = insight_payload.get('insight', '')
            insight_text = inner_insight.get('text') or inner_insight.get('summary') or str(inner_insight) if isinstance(inner_insight, dict) else str(inner_insight)
        else:
            insight_text = str(insight_payload)

        # Safely capture dual metrics from final review object layout
        review_data = results.get('review', {})
        grounding_score = review_data.get('score', 0.0)
        relevance_signal = review_data.get('relevance_signal', 0.0)

        return json.dumps({
            "status": "success",
            "topic": topic,
            "synthesis": insight_text,
            "grounding_fidelity_score": grounding_score,
            "topical_relevance_signal": relevance_signal,
            "excel_report_saved_at": results.get('audit_file', 'N/A')
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def main():
    # Write initialization logs strictly to stderr
    print("Nexus OS MCP Server Initialized. Connecting stdio channels...", file=sys.stderr)
    sys.stderr.flush()

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            payload = json.loads(line)
            method = payload.get("method")
            msg_id = payload.get("id")

            # --- HANDSHAKE PHASE 1: Handle Base Protocol Initialization ---
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "nexus-research-core",
                            "version": "1.1.0"
                        }
                    }
                }
                print(json.dumps(response))
                sys.stdout.flush()
                continue

            # --- HANDSHAKE PHASE 2: Announce tool properties to Claude Code ---
            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [{
                            "name": "nexus_research",
                            "description": "Triggers the autonomous multi-agent research core. Ingests OpenAlex papers, runs factual grounding loops, caches data vectors to ChromaDB, and exports spreadsheet summaries.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "topic": {"type": "string", "description": "The target research question or field query theme."},
                                    "custom_prompt": {"type": "string", "description": "Specific focus angle filters or directional instructions."},
                                    "max_sources": {"type": "integer", "description": "Number of academic files to parse (default 5)."}
                                },
                                "required": ["topic"]
                            }
                        }],
                        "properties": {
                            "topic": {"type": "string",
                                      "description": "The target research question or field query theme."},
                            "custom_prompt": {"type": "string",
                                              "description": "Specific focus angle filters or directional instructions."},
                            "max_sources": {"type": "integer",
                                            "description": "Number of academic files to parse (default 5)."},
                            "bypass_cache": {"type": "boolean",
                                             "description": "Set to true to force a clean live live API scan, ignoring Phase 10 memory storage layer caches."}
                        },

                    }
                }

                print(json.dumps(response))
                sys.stdout.flush()
                continue

            # --- EXECUTION PHASE: Handle Actual Tool Calls ---

            if method == "tools/call":
                params = payload.get("params", {})
                arguments = params.get("arguments", {})

                topic = arguments.get("topic")
                custom_prompt = arguments.get("custom_prompt", None)
                max_sources = int(arguments.get("max_sources", 5))
                bypass_cache = arguments.get("bypass_cache", False)  # <-- Captures your override flag cleanly

                # If the user explicitly asks for a clean run, we wipe the cache folder right before executing
                if bypass_cache:
                    print("[MCP Override]: Cache bypass requested. Purging local tracking indices...", file=sys.stderr)
                    try:
                        from wipe_memory import main as run_wipe
                        run_wipe()  # Triggers our programmatic database purge
                    except Exception:
                        pass

                execution_result = execute_mcp_research(topic, custom_prompt, max_sources)

                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": execution_result}]
                    }
                }
                print(json.dumps(response))
                sys.stdout.flush()
                continue

            # Default fallback response for lifecycle notifications (like initialized)
            if msg_id is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}}))
                sys.stdout.flush()

        except Exception as e:
            print(f"MCP Core Processing Error: {e}", file=sys.stderr)
            sys.stderr.flush()


if __name__ == "__main__":
    main()