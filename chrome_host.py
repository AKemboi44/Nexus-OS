import sys
import json
import struct
import subprocess
import os


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
    # Force absolute working context variables down the execution track
    working_dir = r"C:\Users\Abraham.Kemboi\PycharmProjects\Nexus-os"
    python_exe = os.path.join(working_dir, ".venv", "Scripts", "python.exe")
    server_script = os.path.join(working_dir, "mcp_server.py")

    # Inherit and patch system environment variables cleanly
    custom_env = os.environ.copy()
    custom_env["PYTHONPATH"] = working_dir

    while True:
        msg = read_message()
        if msg is None:
            break

        # Extract inputs from popup channel triggers safely
        topic = msg.get("params", {}).get("arguments", {}).get("topic") or msg.get("topic", "AI optimization")
        max_sources = msg.get("params", {}).get("arguments", {}).get("max_sources") or msg.get("max_sources", 5)
        domain = msg.get("params", {}).get("arguments", {}).get("domain") or msg.get("domain", "scholarly")

        # Build pristine canonical MCP input payloads
        mcp_payload = json.dumps({
            "method": "tools/call",
            "id": 1,
            "params": {
                "arguments": {
                    "topic": str(topic),
                    "max_sources": int(max_sources),
                    "domain": str(domain)
                }
            }
        })

        try:
            # Spawn the underlying engine with explicit directory and path context locks
            process = subprocess.Popen(
                [python_exe, server_script, "--cli"],
                cwd=working_dir,
                env=custom_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout_out, stderr_out = process.communicate(input=mcp_payload)

            # Drill down and parse the data frame right here inside Python safely
            final_data = {}
            first_brace = stdout_out.find('{')
            last_brace = stdout_out.rfind('}')

            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                clean_json_str = stdout_out[first_brace:last_brace + 1]
                base_mcp = json.loads(clean_json_str)

                # Extract inner content text vectors safely
                content_block = base_mcp.get("result", {}).get("content", [])
                if isinstance(content_block, list) and len(content_block) > 0:
                    text_data = content_block[0].get("text", "{}")
                    final_data = json.loads(text_data)
                elif isinstance(content_block, dict) and "text" in content_block:
                    final_data = json.loads(content_block["text"])

            # Defensive fallback check: if inner extraction failed, pass raw stdout
            if not final_data:
                final_data = {"status": "success", "message": stdout_out, "error_log": stderr_out}

            # Force standard keys to ensure they match popup.js perfectly
            if "status" not in final_data:
                final_data["status"] = "success"

            send_message(final_data)

        except Exception as e:
            send_message({"status": "error", "message": str(e)})


if __name__ == '__main__':
    main()
