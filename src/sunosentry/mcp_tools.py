"""Narrow, deterministic MCP-compatible tools. No tool executes a real dispatch."""
from __future__ import annotations

from dataclasses import asdict

from .models import DispatchProposal


POLICIES = {
    "gas_smell": {
        "urgency": "emergency",
        "rule": "Tell the caller to leave the area and contact emergency services. Do not diagnose remotely.",
    },
    "water_leak": {
        "urgency": "priority",
        "rule": "Ask whether water can be isolated; offer the earliest qualified technician window.",
    },
    "no_heat": {
        "urgency": "priority",
        "rule": "Prioritize vulnerable occupants and sub-freezing conditions; otherwise offer same-day service.",
    },
    "locked_out": {
        "urgency": "priority",
        "rule": "Verify approved contact details before proposing locksmith dispatch.",
    },
    "other": {
        "urgency": "standard",
        "rule": "Collect the issue summary and propose the next available service window.",
    },
}


def get_dispatch_policy(issue_type: str) -> dict:
    return {"issue_type": issue_type, **POLICIES.get(issue_type, POLICIES["other"])}


def search_capacity(urgency: str) -> dict:
    windows = {
        "emergency": "Immediate safety escalation; human dispatcher paged now",
        "priority": "Today, 2:00–4:00 PM",
        "standard": "Tomorrow, 9:00–11:00 AM",
    }
    return {"availability": windows[urgency], "source": "simulated_capacity_service"}


def create_proposed_dispatch(issue_type: str, urgency: str, window: str) -> DispatchProposal:
    return DispatchProposal(issue_type=issue_type, urgency=urgency, proposed_window=window)


def proposal_for_audit(proposal: DispatchProposal) -> dict:
    return asdict(proposal)
