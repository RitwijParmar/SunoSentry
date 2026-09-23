from __future__ import annotations

import re
import time
from collections import Counter

from .mcp_tools import MCPToolBoundary, create_proposed_dispatch
from .models import Session, TraceEvent
from .triage_agent import TriageDecision, VertexTriageAgent
from .vertex_narrator import VertexNarrator


class VoiceOpsEngine:
    """Bounded supervisor for a field-service voice interaction.

    Specialists are deterministic so a model cannot create a dispatch, bypass a
    safety check, or call an arbitrary integration. Gemini only improves the
    natural-language acknowledgement when explicitly enabled.
    """

    def __init__(self, mode: str = "multi_agent", mcp_transport: str | None = None) -> None:
        if mode not in {"multi_agent", "single_agent", "rules_only"}:
            raise ValueError("mode must be multi_agent, single_agent, or rules_only")
        self.mode = mode
        self.sessions: dict[str, Session] = {}
        self.metrics: Counter[str] = Counter()
        self.narrator = VertexNarrator()
        self.triage = VertexTriageAgent(enabled=False if mode == "rules_only" else None)
        self.mcp = MCPToolBoundary(transport=mcp_transport)

    def new_session(self) -> Session:
        session = Session()
        self.sessions[session.session_id] = session
        self.metrics["sessions_started"] += 1
        return session

    def get(self, session_id: str) -> Session:
        return self.sessions[session_id]

    def _trace(
        self,
        session: Session,
        agent: str,
        decision: str,
        outcome: str,
        detail: str,
        started: float,
        evidence: dict | None = None,
    ) -> None:
        session.trace.append(
            TraceEvent(
                agent=agent if self.mode == "multi_agent" else self.mode.replace("_", "-"),
                decision=decision,
                outcome=outcome,  # type: ignore[arg-type]
                detail=detail,
                latency_ms=max(1, round((time.perf_counter() - started) * 1000)),
                evidence=evidence,
            )
        )

    @staticmethod
    def _redact(text: str) -> tuple[str, int]:
        patterns = (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", r"\b\d{3}-\d{2}-\d{4}\b")
        total = 0
        for pattern in patterns:
            text, substitutions = re.subn(pattern, "[redacted]", text)
            total += substitutions
        return text, total

    def _approved_acknowledgement(self, issue_type: str) -> str:
        if issue_type == "gas_smell":
            return "This may be unsafe. Please leave the area now and contact emergency services. I am paging a human dispatcher; I will not attempt a remote diagnosis."
        if issue_type == "water_leak":
            return "I understand this is a water leak. If it is safe, please isolate the water source. I can propose the earliest qualified technician window."
        if issue_type == "no_heat":
            return "I understand you have a heating issue. I will prioritize the request and propose the earliest qualified service window."
        if issue_type == "locked_out":
            return "I can help with a lockout request. Before any dispatch, a human will verify approved contact details."
        return "I can capture the service issue and propose the next available service window."

    def _natural_acknowledgement(self, session: Session, issue_type: str) -> str:
        approved = self._approved_acknowledgement(issue_type)
        started = time.perf_counter()
        wording, used_vertex = self.narrator.polish(approved)
        if used_vertex:
            self.metrics["vertex_narrations"] += 1
            self._trace(session, "voice-agent", "polish_approved_acknowledgement", "pass", "Vertex AI wording layer; deterministic action plan retained.", started)
        return wording

    def handle_turn(self, session_id: str, transcript: str, confirmed: bool = False) -> dict:
        session = self.get(session_id)
        safe_text, redactions = self._redact(transcript.strip())
        session.pii_redactions += redactions
        session.turn_count += 1
        session.transcript.append({"role": "caller", "text": safe_text})

        triage_started = time.perf_counter()
        triage = self.triage.classify(safe_text)
        if self.mode == "single_agent" and triage.abstained and not triage.prompt_injection:
            # Deliberately weak ablation baseline: a single decision-maker turns
            # uncertainty into an "other" request instead of escalating.
            triage = TriageDecision("other", "single_agent_baseline", "none", 0.50, False, reason="naive uncertainty handling")
        self.metrics["classifier_calls"] += triage.model_calls
        triage_outcome = "review" if triage.abstained else "pass"
        self._trace(
            session,
            "triage-agent",
            "classify_service_intent",
            triage_outcome,
            f"{triage.issue_type}; provider={triage.provider}; confidence={triage.confidence:.2f}; reason={triage.reason or 'structured decision'}",
            triage_started,
        )

        if triage.abstained:
            safety_started = time.perf_counter()
            self.metrics["abstentions"] += 1
            self.metrics["human_escalations"] += 1
            reply = "I cannot safely classify that request automatically. I am sending it to a human dispatcher for review; no service action was created."
            self._trace(
                session,
                "safety-agent",
                "abstain_and_escalate",
                "blocked",
                "Classifier abstained; no policy or dispatch tool was invoked.",
                safety_started,
            )
            session.transcript.append({"role": "agent", "text": reply})
            return {"reply": reply, "session": session.public(), "handoff": True}
        issue_type = triage.issue_type

        policy_started = time.perf_counter()
        policy_result = self.mcp.call("dispatch_policy", {"issue_type": issue_type}, trace_id=session.trace_id)
        self.metrics["mcp_calls"] += 1
        if not policy_result["ok"]:
            self.metrics["tool_failures"] += 1
            self._trace(session, "grounding-agent", "read_named_policy", "review", policy_result.get("error", "MCP policy unavailable"), policy_started, policy_result.get("evidence"))
            self.metrics["human_escalations"] += 1
            reply = "The policy evidence service is unavailable, so I will not propose a service action. A human dispatcher will review this request."
            session.transcript.append({"role": "agent", "text": reply})
            return {"reply": reply, "session": session.public(), "handoff": True}
        policy = policy_result["value"]
        self._trace(session, "grounding-agent", "read_named_policy", "pass", policy["rule"], policy_started, policy_result.get("evidence"))

        if issue_type == "gas_smell":
            safety_started = time.perf_counter()
            session.proposal = None
            self._trace(session, "safety-agent", "block_automated_dispatch", "blocked", "Emergency safety protocol requires immediate human escalation.", safety_started)
            self.metrics["human_escalations"] += 1
            reply = self._approved_acknowledgement(issue_type)
            session.transcript.append({"role": "agent", "text": reply})
            return {"reply": reply, "session": session.public(), "handoff": True}

        plan_started = time.perf_counter()
        capacity_result = self.mcp.call("capacity_evidence", {"urgency": policy["urgency"]}, trace_id=session.trace_id)
        self.metrics["mcp_calls"] += 1
        if not capacity_result["ok"]:
            self.metrics["tool_failures"] += 1
            self._trace(session, "planning-agent", "propose_dispatch_window", "review", capacity_result.get("error", "MCP capacity unavailable"), plan_started, capacity_result.get("evidence"))
            self.metrics["human_escalations"] += 1
            reply = "I could not verify a service window, so no action was proposed. A human dispatcher will review this request."
            session.transcript.append({"role": "agent", "text": reply})
            return {"reply": reply, "session": session.public(), "handoff": True}
        capacity = capacity_result["value"]
        session.proposal = create_proposed_dispatch(issue_type, policy["urgency"], capacity["availability"])
        self._trace(session, "planning-agent", "propose_dispatch_window", "pass", capacity["availability"], plan_started, capacity_result.get("evidence"))

        safety_started = time.perf_counter()
        if confirmed:
            session.proposal.confirmation_received = True
            session.proposal.status = "ready_for_handoff"
            self._trace(session, "consent-agent", "verify_spoken_confirmation", "pass", "Explicit confirmation recorded; proposal sent to human queue.", safety_started)
            self.metrics["verified_handoffs"] += 1
            reply = f"Thank you. I recorded your confirmation for {session.proposal.proposed_window}. A human dispatcher will verify and finalize the service request."
            handoff = True
        else:
            self._trace(session, "consent-agent", "verify_spoken_confirmation", "review", "No confirmation; proposal remains a draft.", safety_started)
            reply = f"{self._natural_acknowledgement(session, issue_type)} I can offer {session.proposal.proposed_window}. Would you like me to send this proposal to a human dispatcher for verification?"
            handoff = False
        session.transcript.append({"role": "agent", "text": reply})
        return {"reply": reply, "session": session.public(), "handoff": handoff}

    def observability(self) -> dict:
        sessions = list(self.sessions.values())
        events = [event for session in sessions for event in session.trace]
        latencies = [event.latency_ms for event in events]
        safety_blocks = sum(1 for event in events if event.outcome == "blocked")
        return {
            "active_sessions": len(sessions),
            "agent_steps": len(events),
            "p95_agent_latency_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0,
            "safety_blocks": safety_blocks,
            "verified_handoffs": self.metrics["verified_handoffs"],
            "pii_redactions": sum(session.pii_redactions for session in sessions),
            "vertex_narrations": self.metrics["vertex_narrations"],
            "classifier_model_calls": self.metrics["classifier_calls"],
            "mcp_calls": self.metrics["mcp_calls"],
            "mcp_tool_failures": self.metrics["tool_failures"],
            "classifier_abstentions": self.metrics["abstentions"],
            "mode": self.mode,
            "slo": {"handoff_trace_complete": "100%", "unconfirmed_dispatches": 0},
        }
