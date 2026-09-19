"""Optional Vertex AI wording layer with a deterministic safety fallback."""
from __future__ import annotations

import os


class VertexNarrator:
    """Makes voice copy more natural without granting the model action authority."""

    def __init__(self) -> None:
        self.enabled = os.getenv("VERTEX_NARRATION_ENABLED", "false").lower() == "true"
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("VERTEX_LOCATION", "us-central1")
        self.model = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")

    def polish(self, approved_copy: str) -> tuple[str, bool]:
        if not self.enabled or not self.project:
            return approved_copy, False
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(vertexai=True, project=self.project, location=self.location)
            response = client.models.generate_content(
                model=self.model,
                contents=(
                    "Rewrite the approved voice acknowledgement below in a concise, warm,"
                    " professional voice. Preserve every safety instruction exactly. Do not"
                    " invent facts, promises, times, policies, actions, or questions."
                    f"\n\nApproved acknowledgement:\n{approved_copy}"
                ),
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=90),
            )
            candidate = (response.text or "").strip()
            return (candidate, True) if 1 <= len(candidate) <= 420 else (approved_copy, False)
        except Exception:
            return approved_copy, False
