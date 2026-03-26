"""MCP tool server for PII-Safe.

Exposes PII detection and sanitization as MCP tools that AI agents
can discover and call via the Model Context Protocol.

Tools:
    pii_safe_scan    — Detect and sanitize PII in text
    pii_safe_detect  — Detect PII only (no sanitization)
    pii_safe_score   — Get privacy risk score for text

Run:
    python -m src.mcp_server
"""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .engine import PIISafeEngine
from .policies import BUILTIN_POLICIES

app = Server("pii-safe")
engine = PIISafeEngine()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="pii_safe_scan",
            description=(
                "Detect and sanitize PII in text. Returns the sanitized text "
                "with PII redacted or pseudonymized according to the policy."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to scan for PII",
                    },
                    "policy": {
                        "type": "string",
                        "description": "Sanitization policy: default, strict, or permissive",
                        "enum": list(BUILTIN_POLICIES.keys()),
                        "default": "default",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="pii_safe_detect",
            description=(
                "Detect PII entities in text without sanitizing. "
                "Returns entity types, positions, and confidence scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to analyze for PII",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="pii_safe_score",
            description=(
                "Compute a privacy risk score for text. "
                "Returns a score from 0.0 (no risk) to 1.0 (critical) "
                "with a risk level: NONE, LOW, MEDIUM, HIGH, CRITICAL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to assess for privacy risk",
                    },
                },
                "required": ["text"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    text = arguments.get("text", "")

    if name == "pii_safe_scan":
        policy_name = arguments.get("policy", "default")
        if policy_name in BUILTIN_POLICIES:
            engine.set_policy(policy_name)
        result = engine.scan(text)
        output = {
            "sanitized_text": result.sanitization.sanitized_text,
            "entities_found": result.detection.entity_count,
            "privacy_score": result.privacy_score.to_dict(),
            "details": result.sanitization.to_dict()["entities"],
        }
        return [TextContent(type="text", text=json.dumps(output, indent=2))]

    if name == "pii_safe_detect":
        detection = engine.detect(text)
        output = detection.to_dict()
        return [TextContent(type="text", text=json.dumps(output, indent=2))]

    if name == "pii_safe_score":
        result = engine.scan(text)
        output = result.privacy_score.to_dict()
        return [TextContent(type="text", text=json.dumps(output, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    import asyncio

    asyncio.run(run())


if __name__ == "__main__":
    main()
