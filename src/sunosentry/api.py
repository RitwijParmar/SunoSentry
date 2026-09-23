from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .benchmarks import CONTROLLED_BENCHMARK
from .cloud_runtime import FirestoreSessionStore, HandoffEventPublisher
from .engine import VoiceOpsEngine

# In a local checkout the working directory is the repository; in the container
# it is /app. Keep the UI outside the installed wheel and resolve it explicitly.
ROOT = Path(os.getenv("APP_ROOT", Path.cwd()))
engine = VoiceOpsEngine()
session_store = FirestoreSessionStore()
handoff_events = HandoffEventPublisher()
app = FastAPI(title="SunoSentry", version="0.2.0")
app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")


class TurnRequest(BaseModel):
    session_id: str
    transcript: str = Field(min_length=1, max_length=2000)
    confirmed: bool = False


@app.get("/")
def home() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sunosentry", "mode": "verifiable-voice-demo", "mcp_client": "stdio", "triage": "rules-first-abstain"}


@app.post("/api/sessions")
def create_session() -> dict:
    session = engine.new_session()
    session_store.save(session)
    return {"reply": "Hello, this is SunoSentry. Tell me what service issue you need help with.", "session": session.public()}


@app.post("/api/turns")
def turn(request: TurnRequest) -> dict:
    try:
        if request.session_id not in engine.sessions:
            restored = session_store.load(request.session_id)
            if restored is None:
                raise KeyError(request.session_id)
            engine.sessions[request.session_id] = restored
        result = engine.handle_turn(request.session_id, request.transcript, request.confirmed)
        session = engine.get(request.session_id)
        result["persistence"] = "firestore" if session_store.save(session) else "memory_fallback"
        if result["handoff"]:
            result["handoff_event_id"] = handoff_events.publish(session)
        return result
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Unknown session") from error


@app.get("/api/observability")
def observability() -> dict:
    return engine.observability()


@app.get("/api/benchmark")
def benchmark() -> dict:
    return CONTROLLED_BENCHMARK
