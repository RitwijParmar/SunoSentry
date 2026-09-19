from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import VoiceOpsEngine

ROOT = Path(__file__).resolve().parents[2]
engine = VoiceOpsEngine()
app = FastAPI(title="SunoSentry", version="0.1.0")
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
    return {"status": "ok", "service": "sunosentry", "mode": "verifiable-voice-demo"}


@app.post("/api/sessions")
def create_session() -> dict:
    session = engine.new_session()
    return {"reply": "Hello, this is SunoSentry. Tell me what service issue you need help with.", "session": session.public()}


@app.post("/api/turns")
def turn(request: TurnRequest) -> dict:
    try:
        return engine.handle_turn(request.session_id, request.transcript, request.confirmed)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Unknown session") from error


@app.get("/api/observability")
def observability() -> dict:
    return engine.observability()
