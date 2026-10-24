"""MCP server exposing the ``measure_context_usage`` tool.

Run with the ``context-audit-mcp`` entry point after installing the optional
``mcp`` extra:

    pip install "context-audit-tool[mcp]"
    context-audit-mcp
"""

from __future__ import annotations

from typing import Any

from .core import audit


def measure_context_usage(
    messages: list[dict[str, Any]],
    model: str,
    context_window: int | None = None,
) -> dict[str, Any]:
    """Measure how much of *model*'s context window *messages* consume."""

    return audit(messages, model=model, context_window=context_window)


def _create_server() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        try:
            # MCP 2.x renamed the high-level server class.
            from mcp.server import MCPServer as FastMCP
        except ImportError as exc:
            raise SystemExit(
                "the MCP server requires the optional 'mcp' dependency; "
                "install it with: pip install \"context-audit-tool[mcp]\""
            ) from exc

    server = FastMCP("context-audit")
    server.add_tool(
        measure_context_usage,
        name="measure_context_usage",
        description=(
            "Measure context-window usage of a completed conversation. Returns "
            "total tokens, context window, usage ratio/percent, remaining "
            "tokens, per-role token breakdown, message count, risk level, and "
            "a warning flag."
        ),
    )
    return server


def main() -> None:
    server = _create_server()
    server.run()
