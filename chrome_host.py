import sys
import json
import struct
import subprocess
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def read_message():
    try:
        text_length_bytes = sys.stdin.buffer.read(4)
        if not text_length_bytes or len(text_length_bytes) < 4:
            return None
        text_length = struct.unpack('i', text_length_bytes)[0]
        text_data = sys.stdin.buffer.read(text_length).decode('utf-8')
        return json.loads(text_data)
    except Exception:
        return None


def send_message(message):
    try:
        encoded_data = json.dumps(message).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('i', len(encoded_data)))
        sys.stdout.buffer.write(encoded_data)
        sys.stdout.buffer.flush()
    except Exception:
        pass


def main():
    working_dir = r"C:\Users\Abraham.Kemboi\PycharmProjects\Nexus-os"
    python_exe = os.path.join(working_dir, ".venv", "Scripts", "python.exe")
    server_script = os.path.join(working_dir, "mcp_server.py")

    custom_env = os.environ.copy()
    custom_env["PYTHONPATH"] = working_dir

    while True:
        msg = read_message()
        if msg is None:
            break

        topic = msg.get("topic", "ai token optimization techniques")
        max_sources = msg.get("max_sources", 5)
        domain = msg.get("domain", "scholarly")
        action_type = msg.get("action", "trigger_nexus_scan")

        # --- CRITICAL PRODUCTION ALIGNMENT: MATCH MCP SERVER STRING EXPECTATIONS ---

        if action_type == "trigger_docx_generation":
            arguments = {
                "action": "trigger_docx_generation",  # Unified exact mapping string
                "topic": str(topic),
                "included_sources": msg.get("included_sources", []),
                "uploaded_sources": msg.get("uploaded_sources", [])
            }
        else:
            arguments = {
                "topic": str(topic),
                "max_sources": int(max_sources),
                "domain": str(domain),
                "uploaded_sources": msg.get("uploaded_sources", [])
            }

        mcp_payload = json.dumps({
            "method": "tools/call",
            "id": 1,
            "params": {"arguments": arguments}
        })

        try:
            process = subprocess.Popen(
                [python_exe, server_script, "--cli"],
                cwd=working_dir,
                env=custom_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            stdout_out, stderr_out = process.communicate(input=mcp_payload)

            final_data = {}
            first_brace = stdout_out.find("{")
            last_brace = stdout_out.rfind("}")

            if first_brace != -1 and last_brace != -1:
                outer_envelope = json.loads(stdout_out[first_brace:last_brace + 1])
                content_list = outer_envelope.get("result", {}).get("content", [])

                if isinstance(content_list, list) and content_list:
                    inner_text_str = content_list[0].get("text", "")
                elif isinstance(content_list, dict):
                    inner_text_str = content_list.get("text", "")
                else:
                    inner_text_str = ""

                if inner_text_str:
                    final_data = json.loads(inner_text_str)

            is_valid_dict = isinstance(final_data, dict)
            is_scribe_success = (
                    is_valid_dict
                    and (final_data.get("action") == "docx_generation_complete" or "document_saved_at" in final_data)
            )
            is_search_success = is_valid_dict and "included" in final_data

            if is_scribe_success or is_search_success:
                if is_search_success:
                    final_data["action"] = "research_scan_complete"
                send_message(final_data)
                continue

            # --- ROUTE PRODUCTION CIRCUITS: HARD-FI FALLBACK GUARD FOR CITATION WRITES ---
            if action_type == "trigger_docx_generation":
                try:
                    # Import your exact class signature layout directly from disk workspace storage
                    from app.agents.scribe_agent import ScribeResearchAgent
                    scribe_worker = ScribeResearchAgent()

                    # Fire the exact method signature name mapping array properties
                    saved_absolute_path = scribe_worker.generate_apa_dossier_report(
                        topic=str(topic),
                        included_sources=msg.get("included_sources", [])
                    )

                    # Extract the absolute clean filename base string token dynamically
                    extracted_filename = os.path.basename(saved_absolute_path)

                    send_message({
                        "status": "success",
                        "action": "docx_generation_complete",
                        "document_saved_at": extracted_filename
                    })
                except Exception as inner_scribe_err:
                    send_message({
                        "status": "error",
                        "message": f"Direct Scribe compilation circuit failure: {str(inner_scribe_err)}"
                    })
                continue

            send_message({
                "status": "error",
                "action": "research_scan_failed",
                "message": "The research host returned no valid source-backed response.",
                "details": stderr_out.strip() or stdout_out.strip()
            })
        except Exception as e:
            send_message({"status": "error", "message": str(e)})


if __name__ == '__main__':
    main()