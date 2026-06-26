#!/usr/bin/env python3
"""mcp-readonly-skeleton: a minimal, dependency-free MCP server that exposes only
READ tools. The safe shape for discovery-style servers (e.g. a read-only feed that
surfaces what's happening). there is deliberately no tool that writes, posts, or
mutates anything. READ + DRAFT + QUEUE; never wire a write endpoint to a trigger.

It speaks MCP over stdio as newline-delimited JSON-RPC 2.0, with no third-party
deps, so it runs anywhere python3 does and is easy to read end to end. For a
production server you'd likely use the official `mcp` Python SDK (FastMCP), see
the README, but the protocol is small enough to show in full here.

Dispatch is a pure function (`handle`) so it's unit-testable without a real client.

    python3 server.py            # run as a stdio MCP server
    python3 server.py --selftest # run a scripted initialize/list/call session
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-11-25"   # current MCP spec the server speaks
SUPPORTED_PROTOCOLS = {"2025-11-25", "2025-06-18", "2025-03-26"}  # versions we accept
SERVER_INFO = {"name": "readonly-skeleton", "version": "0.1.0"}
DATA = Path(__file__).resolve().parent / "data.json"


def load_items() -> list[dict]:
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except Exception:
        return []


# ---- read-only tools: add yours here. NEVER add a tool that writes/posts. ----
TOOLS = [
    {
        "name": "search_items",
        "description": "Search discovery items by keyword in title/summary. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "keyword to match"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_item",
        "description": "Fetch one discovery item by id. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "item id"}},
            "required": ["id"],
        },
    },
]


def call_tool(name: str, args: dict) -> str:
    items = load_items()
    if name == "search_items":
        q = (args.get("query") or "").lower()
        hits = [it for it in items if q in (it.get("title", "") + it.get("summary", "")).lower()]
        if not hits:
            return f"no items match {q!r}."
        return "\n".join(f"[{it['id']}] {it['title']}" for it in hits)
    if name == "get_item":
        for it in items:
            if str(it.get("id")) == str(args.get("id")):
                return json.dumps(it, indent=2)
        return f"no item with id {args.get('id')!r}."
    raise KeyError(name)
# ------------------------------------------------------------------------------


def ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(req: dict):
    """Pure dispatch: request dict -> response dict, or None for notifications."""
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        # echo the client's version only if we actually support it, else our own.
        client_ver = params.get("protocolVersion")
        agreed = client_ver if client_ver in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return ok(rid, {
            "protocolVersion": agreed,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "notifications/initialized":
        return None  # notification: no response
    if method == "tools/list":
        return ok(rid, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            text = call_tool(name, args)
            return ok(rid, {"content": [{"type": "text", "text": text}], "isError": False})
        except KeyError:
            return ok(rid, {"content": [{"type": "text", "text": f"unknown tool: {name}"}],
                            "isError": True})
    if rid is None:
        return None  # unknown notification, ignore
    return err(rid, -32601, f"method not found: {method}")


def serve() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


def selftest() -> int:
    session = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                    "clientInfo": {"name": "selftest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "search_items", "arguments": {"query": "agent"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "get_item", "arguments": {"id": "1"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "nope", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 6, "method": "initialize",
         "params": {"protocolVersion": "1999-01-01", "capabilities": {},
                    "clientInfo": {"name": "selftest", "version": "0"}}},
    ]
    for req in session:
        resp = handle(req)
        method = req.get("method")
        # label tool calls and the version-negotiation case so the line is unambiguous
        if method == "tools/call":
            p = req.get("params") or {}
            label = f"{method} {p.get('name')}({p.get('arguments')})"
        elif method == "initialize":
            ver = (req.get("params") or {}).get("protocolVersion")
            label = f"{method} (client asked {ver})"
        else:
            label = method
        tag = " (notification, no response)" if resp is None else ""
        print(f">>> {label}{tag}")
        if resp is not None:
            print("    " + json.dumps(resp)[:200])
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
