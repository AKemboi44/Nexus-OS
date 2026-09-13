# mcp_server.py - Production-Ready Native Messaging Controller
import sys
import json
import os
import struct
import base64
import tempfile
from dotenv import load_dotenv

project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv(os.path.join(project_root, '.env'))

from app.research.research_pipeline import ResearchPipeline
from app.reports.dossier_generator import DossierGenerator


def execute_mcp_research(topic: str, max_sources: int = 5, domain: str = "scholarly",
                         additional_sources=None):
    try:
        pipeline = ResearchPipeline()
        result_data = pipeline.run_research(
            query=topic,
            max_sources=max_sources,
            additional_sources=additional_sources or []
        )
        return result_data
    except Exception as e:
        return {"status": "error", "message": f"Pipeline failure: {str(e)}"}


def main():
    is_cli = "--cli" in sys.argv
    if sys.platform == "win32":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        if is_cli:
            raw_message = sys.stdin.readline()
            if not raw_message:
                return
            payload = json.loads(raw_message)
        else:
            raw_length = sys.stdin.buffer.read(4)
            if not raw_length or len(raw_length) < 4:
                return
            text_length = struct.unpack('=I', raw_length)[0]
            message_bytes = sys.stdin.buffer.read(text_length)
            if not message_bytes:
                return
            payload = json.loads(message_bytes.decode('utf-8'))

        if payload.get("method") == "tools/call":
            payload = payload.get("params", {}).get("arguments", {})
        action = payload.get("action")
        topic = payload.get("topic", "AI Optimization Techniques")
        included_sources = payload.get("included_sources", [])
        uploaded_sources = payload.get("uploaded_sources", [])

        parsed_uploads = []
        for upload in uploaded_sources:
            try:
                name = str(upload.get("name", "uploaded-document"))
                raw_data = base64.b64decode(upload.get("data", ""), validate=True)
                if not raw_data:
                    raise ValueError("Upload is empty.")
                text = ""
                if name.lower().endswith(".pdf") or upload.get("type") == "application/pdf":
                    import pymupdf
                    with pymupdf.open(stream=raw_data, filetype="pdf") as pdf:
                        text = "\n".join(page.get_text() for page in pdf).strip()
                else:
                    text = raw_data.decode("utf-8", errors="replace").strip()
                source = {
                    "uid": f"upload_{name}",
                    "title": name,
                    "authors": ["User Upload"],
                    "venue": "User-provided source",
                    "year": "n.d.",
                    "citation_count": 0,
                    "is_peer_reviewed": False,
                    "abstract": text[:12000] or "No extractable text.",
                    "url": f"file:///{name}",
                    "domain": payload.get("domain", "scholarly"),
                    "provider_source": "user_upload",
                    "include": bool(text.strip())
                }
                parsed_uploads.append(source)
            except Exception as upload_err:
                parsed_uploads.append({
                    "uid": f"upload_error_{upload.get('name', 'unknown')}",
                    "title": str(upload.get("name", "Uploaded source")),
                    "provider_source": "user_upload",
                    "include": False,
                    "exclusion_reason": f"Upload parsing failed: {upload_err}"
                })
        included_sources.extend([source for source in parsed_uploads if source.get("include")])

        # --- ROUTE A: DOCUMENT WORD COMPILATION WRITE-UPS ---
        if action == "trigger_docx_generation":
            domain_target = payload.get("domain", "scholarly").lower()
            if not included_sources:
                discovery = execute_mcp_research(
                    topic,
                    int(payload.get("max_sources", 5)),
                    domain_target
                )
                included_sources = discovery.get("included", [])
            generator = DossierGenerator()
            dossier = generator.generate_comprehensive_dossier(
                query=topic,
                included_sources=included_sources,
                custom_prompt=payload.get("custom_prompt"),
                domain=domain_target
            )
            from app.agents.scribe_agent import ScribeResearchAgent
            saved_path = ScribeResearchAgent().generate_apa_dossier_report(
                topic=topic,
                included_sources=included_sources,
                dossier=dossier,
                domain=domain_target
            )
            final_response = {
                "status": "success",
                "action": "docx_generation_complete",
                "document_saved_at": os.path.basename(saved_path)
            }

        # --- ROUTE B: CORE DISCOVERY SWEEPS ---
        else:
            max_sources = int(payload.get("max_sources", 5))
            domain_target = payload.get("domain", "scholarly").lower()

            raw_result = execute_mcp_research(
                topic, max_sources, domain_target,
                additional_sources=parsed_uploads
            )

            if isinstance(raw_result, dict):
                final_response = raw_result
            else:
                final_response = {
                    "status": "success",
                    "synthesis": str(raw_result)
                }

            # Guarantee explicit fallback properties to clear the front-end router gates cleanly
            final_response["status"] = final_response.get("status", "success")
            final_response["included"] = final_response.get("included", [])
            final_response["excluded"] = final_response.get("excluded", [])
            final_response["action"] = "research_scan_complete"

        if is_cli:
            cli_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(final_response, ensure_ascii=False)
                    }]
                }
            }
            print(json.dumps(cli_response, ensure_ascii=False), flush=True)
        else:
            response_bytes = json.dumps(final_response, ensure_ascii=False).encode('utf-8')
            sys.stdout.buffer.write(struct.pack('=I', len(response_bytes)))
            sys.stdout.buffer.write(response_bytes)
            sys.stdout.buffer.flush()

    except Exception as err:
        error_response = json.dumps({"status": "error", "message": str(err)}).encode('utf-8')
        if is_cli:
            print(error_response.decode("utf-8"), flush=True)
        else:
            sys.stdout.buffer.write(struct.pack('=I', len(error_response)))
            sys.stdout.buffer.write(error_response)
            sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()