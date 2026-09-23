"""Durable state and event delivery adapters for the Cloud Run deployment."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from .models import DispatchProposal, Session, TraceEvent


class FirestoreSessionStore:
    """Stores only redacted session state; raw audio is never persisted."""

    def __init__(self) -> None:
        self.enabled = os.getenv("FIRESTORE_SESSIONS_ENABLED", "false").lower() == "true"
        self._client = None

    def _collection(self):
        if not self.enabled:
            return None
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client()
        return self._client.collection("sunosentry_sessions")

    def save(self, session: Session) -> bool:
        try:
            collection = self._collection()
            if collection is None:
                return False
            collection.document(session.session_id).set(
                {
                    **session.public(),
                    "transcript": session.transcript,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "data_boundary": "redacted_text_only_no_audio",
                }
            )
            return True
        except Exception:
            return False

    def load(self, session_id: str) -> Session | None:
        try:
            collection = self._collection()
            if collection is None:
                return None
            document = collection.document(session_id).get()
            if not document.exists:
                return None
            data = document.to_dict()
            proposal = DispatchProposal(**data["proposal"]) if data.get("proposal") else None
            trace = [TraceEvent(**event) for event in data.get("trace", [])]
            return Session(
                session_id=data["session_id"],
                trace_id=data["trace_id"],
                turn_count=data.get("turn_count", 0),
                transcript=data.get("transcript", []),
                proposal=proposal,
                trace=trace,
                pii_redactions=data.get("pii_redactions", 0),
            )
        except Exception:
            return None


class HandoffEventPublisher:
    """Publishes redacted handoff metadata; this is not a dispatch command."""

    def __init__(self) -> None:
        self.enabled = os.getenv("PUBSUB_HANDOFF_ENABLED", "false").lower() == "true"
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.topic = os.getenv("HANDOFF_TOPIC", "sunosentry-handoff-events")
        self._publisher = None

    def publish(self, session: Session) -> str | None:
        if not self.enabled or not self.project:
            return None
        try:
            if self._publisher is None:
                from google.cloud import pubsub_v1

                self._publisher = pubsub_v1.PublisherClient()
            topic_path = self._publisher.topic_path(self.project, self.topic)
            payload = {
                "event_type": "human_review_handoff",
                "session_id": session.session_id,
                "trace_id": session.trace_id,
                "proposal": session.proposal.to_dict() if session.proposal else None,
                "pii_redactions": session.pii_redactions,
                "data_boundary": "no_raw_audio_or_transcript",
            }
            return self._publisher.publish(topic_path, json.dumps(payload).encode("utf-8")).result(timeout=5)
        except Exception:
            return None
