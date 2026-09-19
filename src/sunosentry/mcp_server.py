"""MCP server exposing only named, read-only dispatch evidence tools."""
from mcp.server.fastmcp import FastMCP

from .mcp_tools import get_dispatch_policy, search_capacity

mcp = FastMCP("sunosentry-evidence")


@mcp.tool()
def dispatch_policy(issue_type: str) -> dict:
    """Read the approved safety and dispatch policy for a classified service issue."""
    return get_dispatch_policy(issue_type)


@mcp.tool()
def capacity_evidence(urgency: str) -> dict:
    """Read a proposed service window. This never reserves or dispatches work."""
    return search_capacity(urgency)


if __name__ == "__main__":
    mcp.run()
