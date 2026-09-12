import sys
import json
import struct
import subprocess


def read_message():
    try:
        text_length_bytes = sys.stdin.buffer.read(4)
        if not text_length_bytes or len(text_length_bytes) < 4:
            return None

        # FIXED: Explicitly extract the integer scalar from index 0 of the unpacked tuple
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
    while True:
        msg = read_message()
        if msg is None:
            break

        topic = msg.get("arguments", {}).get("topic", msg.get("topic", "ai"))
        max_sources = msg.get("arguments", {}).get("max_sources", msg.get("max_sources", 5))
        domain = msg.get("arguments", {}).get("domain", msg.get("domain", "scholarly"))

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
            process = subprocess.Popen(
                ["C:\\Users\\Abraham.Kemboi\\PycharmProjects\\Nexus-os\\.venv\\Scripts\\python.exe", "mcp_server.py",
                 "--cli"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout_out, stderr_out = process.communicate(input=mcp_payload)
            send_message({"status": "success", "result": stdout_out, "logs": stderr_out})
        except Exception as e:
            send_message({"status": "error", "message": str(e)})


if __name__ == '__main__':
    main()
