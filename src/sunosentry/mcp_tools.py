"""Narrow MCP tools and the deny-by-default client boundary.

The application never imports a tool and calls it as if it were trusted.  It
goes through :class:`MCPToolBoundary`, which validates the name and arguments,
records the risk annotation, and signs the policy evidence.  In production the
boundary uses a real MCP stdio client; the in-process transport is only for
offline tests and the deterministic benchmark.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

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


@dataclass(frozen=True)
class ToolSpec:
    name: str
    risk: str
    description: str
    arguments: frozenset[str]
    read_only: bool = True
    destructive: bool = False


# This registry is deliberately closed.  Adding a server-side function is not
# enough to make it callable by an agent; it must be explicitly reviewed here.
TOOL_SPECS: dict[str, ToolSpec] = {
    "dispatch_policy": ToolSpec(
        name="dispatch_policy",
        risk="low",
        description="Read a named safety policy; never dispatches or reserves work.",
        arguments=frozenset({"issue_type"}),
    ),
    "capacity_evidence": ToolSpec(
        name="capacity_evidence",
        risk="low",
        description="Read a simulated availability window; never reserves work.",
        arguments=frozenset({"urgency"}),
    ),
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


class MCPBoundaryError(RuntimeError):
    """Raised when the MCP boundary denies or cannot complete a tool call."""


class MCPToolBoundary:
    """A stateless, deny-by-default MCP client with signed evidence.

    ``stdio`` starts the checked-in MCP server for every call.  That makes the
    process boundary and protocol visible in traces and avoids sharing mutable
    tool state with the voice supervisor.  ``inprocess`` preserves the same
    authorization and evidence contract for offline evaluation only.
    """

    def __init__(self, transport: str | None = None, signing_key: str | None = None) -> None:
        self.transport = transport or os.getenv("MCP_CLIENT_TRANSPORT", "stdio")
        configured_key = signing_key or os.getenv("MCP_POLICY_SIGNING_KEY")
        # A deployment should inject a Secret Manager-backed key.  The local
        # fallback is per-process so the public source cannot forge evidence.
        self.signing_key = (configured_key or secrets.token_urlsafe(32)).encode()

    def _signed_evidence(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        decision: str,
        trace_id: str | None,
        task_handle: str,
        detail: str,
    ) -> dict[str, Any]:
        evidence = {
            "schema": "sunosentry.mcp.policy-evidence.v1",
            "tool": tool,
            "risk": TOOL_SPECS.get(tool, ToolSpec(tool, "unknown", "", frozenset())).risk,
            "decision": decision,
            "arguments_digest": hashlib.sha256(
                json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "trace_id": trace_id,
            "task_handle": task_handle,
            "detail": detail,
            "issued_at_unix": round(time.time(), 3),
        }
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        evidence["signature"] = hmac.new(self.signing_key, canonical, hashlib.sha256).hexdigest()
        return evidence

    def _authorize(self, tool: str, arguments: dict[str, Any]) -> ToolSpec:
        spec = TOOL_SPECS.get(tool)
        if spec is None:
            raise MCPBoundaryError(f"deny_by_default: unknown tool {tool!r}")
        if set(arguments) != set(spec.arguments):
            raise MCPBoundaryError(
                f"deny_by_default: argument shape rejected for {tool}; expected {sorted(spec.arguments)}"
            )
        return spec

    @staticmethod
    def _inprocess(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "dispatch_policy":
            return get_dispatch_policy(arguments["issue_type"])
        if tool == "capacity_evidence":
            return search_capacity(arguments["urgency"])
        raise MCPBoundaryError(f"unknown in-process tool {tool}")

    async def _stdio_call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "sunosentry.mcp_server"],
            env={**os.environ, "SUNOSENTRY_MCP_SERVER": "1"},
        )
        async with stdio_client(server) as (read_stream, write_stream), ClientSession(read_stream, write_stream) as client:
                await client.initialize()
                result = await client.call_tool(tool, arguments=arguments)
                if getattr(result, "isError", False):
                    raise MCPBoundaryError(f"MCP server returned an error for {tool}")
                for item in getattr(result, "content", []):
                    text = getattr(item, "text", None)
                    if text:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return {"text": text}
                structured = getattr(result, "structuredContent", None)
                if structured:
                    return dict(structured)
                return {}

    def call(
        self, tool: str, arguments: dict[str, Any], *, trace_id: str | None = None
    ) -> dict[str, Any]:
        task_handle = f"mcp-task-{uuid4().hex}"
        try:
            self._authorize(tool, arguments)
        except MCPBoundaryError as error:
            return {
                "ok": False,
                "task_handle": task_handle,
                "evidence": self._signed_evidence(
                    tool=tool,
                    arguments=arguments,
                    decision="deny",
                    trace_id=trace_id,
                    task_handle=task_handle,
                    detail=str(error),
                ),
                "error": str(error),
            }
        try:
            if self.transport == "failure":
                raise MCPBoundaryError("simulated MCP tool transport failure")
            if self.transport == "inprocess":
                value = self._inprocess(tool, arguments)
            else:
                value = asyncio.run(self._stdio_call(tool, arguments))
            return {
                "ok": True,
                "task_handle": task_handle,
                "value": value,
                "evidence": self._signed_evidence(
                    tool=tool,
                    arguments=arguments,
                    decision="allow",
                    trace_id=trace_id,
                    task_handle=task_handle,
                    detail=f"MCP {self.transport} client completed read-only tool call",
                ),
            }
        except Exception as error:  # noqa: BLE001 - boundary must fail closed for any transport error
            return {
                "ok": False,
                "task_handle": task_handle,
                "evidence": self._signed_evidence(
                    tool=tool,
                    arguments=arguments,
                    decision="error",
                    trace_id=trace_id,
                    task_handle=task_handle,
                    detail=f"MCP transport failure: {type(error).__name__}",
                ),
                "error": f"mcp_transport_error: {type(error).__name__}",
            }

    def verify_evidence(self, evidence: dict[str, Any]) -> bool:
        """Verify a signed evidence record without trusting its displayed fields."""
        signature = evidence.get("signature")
        if not signature:
            return False
        unsigned = {key: value for key, value in evidence.items() if key != "signature"}
        canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        expected = hmac.new(self.signing_key, canonical, hashlib.sha256).hexdigest()
        return hmac.compare_digest(str(signature), expected)
