# cloud_app.py - Block 1 of 2
import os
import sys
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.research.research_pipeline import ResearchPipeline

app = FastAPI(title="Nexus Research AI Gateway", version="1.0.0")
pipeline = ResearchPipeline()

class ScanRequest(BaseModel):
    topic: str
    max_sources: Optional[int] = 5
    domain: Optional[str] = "scholarly"

class AnalyticsEvent(BaseModel):
    user_id: str
    event: str
    timestamp: str
    context: dict
# cloud_app.py - Block 2 of 2
@app.post("/v1/scan")
async def execute_cloud_scan(payload: ScanRequest, authorization: Optional[str] = Header(None)):
    if not payload.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be blank.")
    try:
        result_data = pipeline.run_research(
            query=payload.topic,
            max_sources=payload.max_sources
        )
        return result_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/analytics")
async def log_telemetry_event(event: AnalyticsEvent):
    print(f"[Telemetry]: {event.event} | User: {event.user_id}", file=sys.stderr)
    return {"status": "logged"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("cloud_app.py", host="0.0.0.0", port=8000, reload=True)
