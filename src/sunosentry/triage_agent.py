"""Vertex-backed structured triage with a deterministic constrained fallback."""
from __future__ import annotations

import json
import os


class VertexTriageAgent:
    allowed = {"gas_smell", "water_leak", "no_heat", "locked_out", "other"}

    def __init__(self) -> None:
        self.enabled = os.getenv("VERTEX_TRIAGE_ENABLED", "false").lower() == "true"
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("VERTEX_LOCATION", "us-central1")
        self.model = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")

    @staticmethod
    def fallback(text: str) -> str:
        lowered = text.lower()
        if any(term in lowered for term in ("gas", "smell", "fumes", "carbon monoxide")):
            return "gas_smell"
        if any(term in lowered for term in ("leak", "flood", "water dripping", "burst pipe")):
            return "water_leak"
        if any(term in lowered for term in ("no heat", "heater", "heating", "furnace", "cold")):
            return "no_heat"
        if any(term in lowered for term in ("locked out", "lost key", "can't get in")):
            return "locked_out"
        return "other"

    def classify(self, text: str) -> tuple[str, str]:
        if not self.enabled or not self.project:
            return self.fallback(text), "rules"
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(vertexai=True, project=self.project, location=self.location)
            response = client.models.generate_content(
                model=self.model,
                contents=(
                    "Classify this field-service caller utterance. Return JSON only with one"
                    " key: issue_type. Allowed values: gas_smell, water_leak, no_heat,"
                    " locked_out, other. Do not give advice.\n\nUtterance:\n" + text
                ),
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=20,
                    response_mime_type="application/json",
                    response_schema={"type": "OBJECT", "properties": {"issue_type": {"type": "STRING", "enum": sorted(self.allowed)}}, "required": ["issue_type"]},
                ),
            )
            issue_type = json.loads(response.text or "{}").get("issue_type")
            if issue_type in self.allowed:
                return issue_type, "vertex_structured"
        except Exception:
            pass
        return self.fallback(text), "rules_fallback"
