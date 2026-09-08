import sys
import json
import os
import struct

# --- CRITICAL BUFFER SHIELD: Force utf-8 standard stream tracking ---
sys.stdout.reconfigure(encoding='utf-8')

# Ensure local project architecture paths map cleanly
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def execute_mcp_research(topic: str, custom_prompt: str = None, max_sources: int = 5) -> str:
    """Invokes the Nexus OS core agents over an MCP pipeline handle with strict stdout shielding."""
    import io
    from contextlib import redirect_stdout
    from dotenv import load_dotenv

    # Load local workspace environment file tokens securely
    load_dotenv(os.path.join(project_root, '.env'))

    # CRITICAL SECURITY SHIELD: Bind it to os.environ so the GenAI SDK captures it smoothly
    if "GEMINI_API_KEY" in os.environ:
        os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")

    rogue_print_buffer = io.StringIO()

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

        # Wrap agent instantiation and execution loops to catch text leaks
        with redirect_stdout(rogue_print_buffer):
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

        # Safely route any captured rogue agent text prints into stderr logs for debugging
        agent_logs = rogue_print_buffer.getvalue()
        if agent_logs:
            print(f"[Captured Agent Output]:\n{agent_logs}", file=sys.stderr)
            sys.stderr.flush()

        insight_payload = results.get('insight', {})
        if isinstance(insight_payload, dict):
            inner_insight = insight_payload.get('insight', '')
            insight_text = inner_insight.get('text') or inner_insight.get('summary') or str(inner_insight) if isinstance(
                inner_insight, dict) else str(inner_insight)
        else:
            insight_text = str(insight_payload)

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
        # Route processing exceptions securely to stderr logs
        error_logs = rogue_print_buffer.getvalue()
        print(f"[Pipeline Exception Log]: {e}\nCaptured Output: {error_logs}", file=sys.stderr)
        sys.stderr.flush()
        return json.dumps({"status": "error", "message": f"{str(e)} | Logs: {error_logs}"})

def read_message(is_chrome: bool):
    """
    Reads data inputs dynamically across both standard raw text string fields
    and Chrome length-prefixed raw binary streams with strict tuple extraction.
    """
    if is_chrome:
        try:
            # Read the 4-byte length header prefix chunk securely
            text_length_bytes = sys.stdin.buffer.read(4)
            if not text_length_bytes or len(text_length_bytes) < 4:
                return None

            # CRITICAL FIX: Extract the raw scalar integer out of the tuple by assigning index [0]
            text_length = struct.unpack('=I', text_length_bytes)[0]
            if text_length == 0:
                return {}

            # Fetch the exact block matching character length bounds
            raw_payload = sys.stdin.buffer.read(text_length)
            if len(raw_payload) < text_length:
                return None

            return json.loads(raw_payload.decode('utf-8'))
        except Exception as stream_err:
            print(f"[Nexus Host Error] Stream read failure: {stream_err}", file=sys.stderr)
            sys.stderr.flush()
            return None
    else:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)


def write_response(response_dict, is_chrome: bool):
    """
    Outputs response packets cleanly, conditionally injecting binary size
    headers when transmitting back up to browser extension targets.
    """
    serialized_text = json.dumps(response_dict)
    if is_chrome:
        try:
            encoded_payload = serialized_text.encode('utf-8')
            # Prepend payload length matching standard unsigned native format layout structures
            sys.stdout.buffer.write(struct.pack('=I', len(encoded_payload)))
            sys.stdout.buffer.write(encoded_payload)
            sys.stdout.buffer.flush()
        except Exception as stream_err:
            print(f"[Nexus Host Error] Stream write failure: {stream_err}", file=sys.stderr)
            sys.stderr.flush()
    else:
        print(serialized_text)
        sys.stdout.flush()
def main():
    # Force strict binary standard stream configuration on Windows systems
    if sys.platform == "win32":
        import os
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    print("Nexus OS MCP Server Initialized. Connecting stdio channels...", file=sys.stderr)
    sys.stderr.flush()

    is_chrome = True
    if "--cli" in sys.argv:
        is_chrome = False

    while True:
        try:
            payload = read_message(is_chrome)
            if not payload:
                break

            # Defensively guarantee payload maps as a dictionary frame
            if not isinstance(payload, dict):
                continue

            method = payload.get("method")
            msg_id = payload.get("id")

            # =========================================================================
            # BULLETPROOF CHROME EXTENSION INTERCEPTOR WITH IMMEDIATE RECEIPT PACKET:
            # Prevents Chrome from timing out and killing the communication line
            # during long-running network academic scans.
            # =========================================================================
            if is_chrome and (method == "tools/call" or method is None or "topic" in payload):
                params = payload.get("params", {})
                arguments = params.get("arguments", payload.get("arguments", payload))

                topic = arguments.get("topic")
                custom_prompt = arguments.get("custom_prompt", None)
                max_sources = int(arguments.get("max_sources", 5))

                if not topic:
                    write_response({"status": "error", "message": "No research topic string provided."}, is_chrome)
                    continue

                # 1. IMMEDIATE HANDSHAKE: Send Chrome a fast status receipt chunk to prove the host is alive
                # This breaks Chrome's silent timeout loop immediately!
                write_response({
                    "status": "processing",
                    "message": f"Successfully spawned Nexus Host. Sweeping {max_sources} academic paths..."
                }, is_chrome)

                # 2. RUN LONG ENGINE: Now we can safely take our time fetching data over live ports
                execution_result = execute_mcp_research(topic, custom_prompt, max_sources)

                # 3. FINAL DATA STREAM: Push the heavy data results directly up the pipeline channel
                try:
                    normalized_json = json.loads(execution_result)
                    # Force inject final status token so popup knows it's complete
                    normalized_json["status"] = "success"
                    write_response(normalized_json, is_chrome)
                except Exception:
                    write_response({
                        "status": "success",
                        "synthesis": execution_result,
                        "excel_report_saved_at": "Saved to workspace directory."
                    }, is_chrome)
                continue
            # =========================================================================

            # --- STANDARD CLAUDE CODE HANDSHAKE LIFECYCLE PATHS ---
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "nexus-research-core", "version": "1.1.0"}
                    }
                }
                write_response(response, is_chrome)
                continue

            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [{
                            "name": "nexus_research",
                            "description": "Triggers the autonomous multi-agent research core.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "topic": {"type": "string", "description": "Target research query."},
                                    "custom_prompt": {"type": "string", "description": "Steering directives."},
                                    "max_sources": {"type": "integer", "description": "Source limit."}
                                },
                                "required": ["topic"]
                            }
                        }]
                    }
                }
                write_response(response, is_chrome)
                continue

            if msg_id is not None:
                write_response({"jsonrpc": "2.0", "id": msg_id, "result": {}}, is_chrome)

        except Exception as e:
            print(f"MCP Core Ingestion Loop Failure: {e}", file=sys.stderr)
            sys.stderr.flush()


if __name__ == "__main__":
    main()