"""Thin async client for the workspace's Soda Straw MCP gateway.

Every Postgres query and Discord call the supervisor bot makes goes through
here, using a scoped agent API key, so credentials and audit stay governed by
Soda Straw. We speak MCP (streamable HTTP) and adapt to whatever tool surface
the agent key exposes — flattened straw tools, or a `straws.call` meta-tool.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import DB_NAME, DISCORD_STRAW, POSTGRES_STRAW, STRAW_API_KEY, STRAW_MCP_URL


@asynccontextmanager
async def _session():
    headers = {"Authorization": f"Bearer {STRAW_API_KEY}"}
    async with streamablehttp_client(STRAW_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _text(result):
    return "".join(
        b.text for b in (getattr(result, "content", None) or [])
        if getattr(b, "type", None) == "text"
    )


def _unwrap(data):
    """Soda Straw wraps adapter output as {straw_id, tool, result} — unwrap it."""
    if isinstance(data, dict) and "result" in data and ("straw_id" in data or "tool" in data):
        return data["result"]
    return data


def _payload(result):
    """Pull the JSON body out of an MCP CallToolResult."""
    if getattr(result, "isError", False):
        raise RuntimeError(f"Soda Straw tool error: {_text(result)}")
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, dict) and "result" in structured and "straw_id" not in structured:
            structured = structured["result"]
        return _unwrap(structured)
    text = _text(result)
    return _unwrap(json.loads(text)) if text else None


async def _call(session, straw, tool_name, arguments):
    tools = {t.name for t in (await session.list_tools()).tools}
    for direct in (tool_name, f"{straw}_{tool_name}", f"{straw}.{tool_name}"):
        if direct in tools:
            return _payload(await session.call_tool(direct, dict(arguments)))
    meta = next((n for n in tools if n in ("straws_call", "straws.call") or n.endswith("_call")), None)
    if meta:
        return _payload(await session.call_tool(
            meta, {"straw": straw, "tool_name": tool_name, "arguments": dict(arguments)}))
    raise RuntimeError(f"No tool to call {straw}.{tool_name}; available: {sorted(tools)}")


async def straw_call(straw, tool_name, arguments):
    async with _session() as session:
        return await _call(session, straw, tool_name, arguments)


# --- Postgres ---------------------------------------------------------------

def _rows(res):
    """Normalize an execute_query result into a list of dict rows."""
    if isinstance(res, dict) and res.get("columns") is not None and res.get("rows") is not None:
        return [dict(zip(res["columns"], r)) for r in res["rows"]]
    return res  # write statements return a status dict, not rows


async def sql(query, intent, params=None, row_limit=1000):
    args = {"sql": query, "_intent": intent, "database": DB_NAME, "row_limit": row_limit}
    if params:
        args["params"] = params
    return _rows(await straw_call(POSTGRES_STRAW, "execute_query", args))


# --- Discord ----------------------------------------------------------------

async def discord(method, path, intent, body=None, query=None):
    args = {"method": method, "path": path, "_intent": intent}
    if body is not None:
        args["body"] = body
    if query is not None:
        args["query_params"] = query
    return await straw_call(DISCORD_STRAW, "http_request", args)
