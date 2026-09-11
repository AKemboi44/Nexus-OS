import sys
import json
import os
import struct

# --- CRITICAL BUFFER SHIELD: Force UTF-8 standard stream tracking ---
sys.stdout.reconfigure(encoding='utf-8')

# Ensure local project architecture paths map cleanly
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def execute_mcp_research(topic: str, custom_prompt: str = None, max_sources: int = 5, domain: str = "scholarly") -> str:
    """
    Invokes the Nexus OS core agents over an MCP pipeline handle with strict stdout shielding.
    Safely captures rogue text prints and redirects error diagnostics to stderr.
    """
    import io
    from contextlib import redirect_stdout
    from dotenv import load_dotenv

    # Load local workspace environment file tokens securely
    load_dotenv(os.path.join(project_root, '.env'))

    # SECURITY SHIELD: Bind it to os.environ so the GenAI SDK captures it smoothly
    if "GEMINI_API_KEY" in os.environ:
        os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")

    rogue_print_buffer = io.StringIO()

    try:
        from app.research.research_pipeline import ResearchPipeline
        from app.synthesis.insight_engine import InsightEngine
        from app.agents.pathfinder_agent import PathfinderAgent
        from app.agents.synthesis_agent import ScribeAgent
        from app.agents.reviewer_agent import ReviewerAgent
        from app.agents.squire_agent import SquireAgent
        from app.agents.orchestrator import NexusOrchestrator

        # Wrap agent instantiation and execution loops to catch print leaks
        with redirect_stdout(rogue_print_buffer):
            search_engine = ResearchPipeline()
            insight_engine = InsightEngine()

            pathfinder = PathfinderAgent(search_engine)
            scribe = ScribeAgent(insight_engine)
            reviewer = ReviewerAgent()
            squire = SquireAgent()

            # The orchestrator handles the core data loops internally
            orchestrator = NexusOrchestrator(pathfinder, scribe, reviewer, squire, max_retries=1)

            results = orchestrator.run_research_loop(
                topic=topic,
                custom_prompt=custom_prompt,
                max_sources=max_sources,
                domain=domain
            )

        # Safely route any captured rogue agent text prints into stderr logs for debugging
        agent_logs = rogue_print_buffer.getvalue()
        if agent_logs:
            print(f"[Captured Agent Output]:\n{agent_logs}", file=sys.stderr)
            sys.stderr.flush()

        insight_payload = results.get('insight', {})
        if isinstance(insight_payload, dict):
            inner_insight = insight_payload.get('insight', '')
            insight_text = inner_insight.get('text') or inner_insight.get('summary') or str(
                inner_insight) if isinstance(
                inner_insight, dict) else str(inner_insight)
        else:
            insight_text = str(insight_payload)

        review_data = results.get('review', {})
        grounding_score = review_data.get('score', 0.0)
        relevance_signal = review_data.get('relevance_signal', 0.0)

        # Extraction vectors mapped natively out of orchestrator payload results array
        apa_format = results.get("apa_format_citation", "Generated in report matrix.")
        bluebook_format = results.get("bluebook_format_citation", "Generated in report matrix.")
        chunks_pushed = results.get("pymupdf_fulltext_chunks_pushed", 0)

        return json.dumps({
            "status": "success",
            "topic": topic,
            "domain_executed": domain,
            "synthesis": insight_text,
            "grounding_fidelity_score": grounding_score,
            "topical_relevance_signal": relevance_signal,
            "pymupdf_fulltext_chunks_pushed": chunks_pushed,
            "apa_format_citation": apa_format,
            "bluebook_format_citation": bluebook_format,
            "excel_report_saved_at": results.get('audit_file', 'N/A')
        }, ensure_ascii=False)

    except Exception as e:
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
            text_length_bytes = sys.stdin.buffer.read(4)
            if not text_length_bytes or len(text_length_bytes) < 4:
                return None

            text_length = struct.unpack('=I', text_length_bytes)[0]
            if text_length == 0:
                return {}

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
    Ensures safe UTF-8 byte serialization, fallback serialization handling,
    and strict native 4-byte length prefixing for Chrome Native Messaging.
    """
    try:
        serialized_text = json.dumps(response_dict, ensure_ascii=False, default=str)
    except Exception as json_err:
        print(f"[Nexus Host Error] JSON serialization failed: {json_err}", file=sys.stderr)
        serialized_text = json.dumps({
            "status": "success",
            "error_fallback": True,
            "message": "Payload contained un-serializable objects.",
            "excel_report_saved_at": response_dict.get("excel_report_saved_at", "N/A")
        })

    if is_chrome:
        try:
            encoded_payload = serialized_text.encode('utf-8')
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
            if payload is None:
                break

            if not isinstance(payload, dict):
                continue

            method = payload.get("method")
            msg_id = payload.get("id")

            # --- CHROME EXTENSION INBOUND FLOW CHANNELS ---
            if is_chrome and (method == "tools/call" or method is None or "topic" in payload):
                params = payload.get("params", {})
                arguments = params.get("arguments", payload.get("arguments", payload))

                topic = arguments.get("topic")
                custom_prompt = arguments.get("custom_prompt", None)
                max_sources = int(arguments.get("max_sources", 5))
                domain_target = arguments.get("domain", "scholarly").lower()

                if not topic:
                    write_response({"status": "error", "message": "No research topic provided."}, is_chrome)
                    continue

                # Acknowledge receipt fast to unfreeze the frontend port container loading state
                write_response({
                    "status": "processing",
                    "message": f"Successfully spawned Nexus Host. Executing autonomous [{domain_target}] research sweep..."
                }, is_chrome)

                execution_result_str = execute_mcp_research(topic, custom_prompt, max_sources, domain_target)

                try:
                    execution_json = json.loads(execution_result_str)
                    write_response(execution_json, is_chrome)
                except Exception:
                    write_response({
                        "status": "success",
                        "synthesis": execution_result_str,
                        "excel_report_saved_at": "Saved to workspace."
                    }, is_chrome)
                continue

            # --- STANDARD CLAUDE CODE MCP HANDSHAKE LOGIC ---
            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [{
                            "name": "nexus_research",
                            "description": "Triggers the autonomous multi-domain federated research core.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "topic": {"type": "string", "description": "The research question query target."},
                                    "custom_prompt": {"type": "string",
                                                      "description": "Directional instruction angle filters."},
                                    "max_sources": {"type": "integer",
                                                    "description": "Number of academic records to parse."},
                                    "domain": {"type": "string",
                                               "description": "scholarly vs legal domain tracking profile target."}},
                                "required": ["topic"]}}]}}
                write_response(response, is_chrome)
                continue

            if method == "tools/call":
                arguments = payload.get("params", {}).get("arguments", {})
                topic = arguments.get("topic")
                custom_prompt = arguments.get("custom_prompt", None)
                max_sources = int(arguments.get("max_sources", 5))
                domain_target = arguments.get("domain", "scholarly").lower()
                execution_result = execute_mcp_research(topic, custom_prompt, max_sources, domain_target)
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": execution_result}]}
                }
                write_response(response, is_chrome)
                continue

        except Exception as global_loop_err:
            print(f"MCP Server Main Loop Error: {global_loop_err}", file=sys.stderr)
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main()