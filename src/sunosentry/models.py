from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TraceEvent:
    agent: str
    decision: str
    outcome: Literal["pass", "review", "blocked"]
    detail: str
    latency_ms: int
    timestamp: str = field(default_factory=now)


@dataclass
class DispatchProposal:
    issue_type: str
    urgency: Literal["emergency", "priority", "standard"]
    proposed_window: str
    consent_required: bool = True
    confirmation_received: bool = False
    status: Literal["draft", "ready_for_handoff", "blocked"] = "draft"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    turn_count: int = 0
    transcript: list[dict] = field(default_factory=list)
    proposal: DispatchProposal | None = None
    trace: list[TraceEvent] = field(default_factory=list)
    pii_redactions: int = 0

    def public(self) -> dict:
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "turn_count": self.turn_count,
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "trace": [asdict(event) for event in self.trace],
            "pii_redactions": self.pii_redactions,
        }
