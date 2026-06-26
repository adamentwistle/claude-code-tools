# mcp-readonly-skeleton

**status: working**

a minimal, dependency-free mcp server that exposes **only read tools**. the safe
shape for a discovery-style server (the kind a read-only feed would be). it speaks
mcp over stdio as newline-delimited json-rpc 2.0 with zero third-party deps, so it
runs anywhere `python3` does and you can read the whole protocol in one file.

there is deliberately **no tool that writes, posts, or mutates anything**. that's
the point: read + draft + queue, never wire a write endpoint to a trigger. copy it
as the starting shape for any "surface information to the agent" server.

## why read-only by construction

a discovery feed should only ever read. if the server has no write tool at all,
"never automate interaction" stops being a promise you have to keep and becomes a
property of the code. this is the clean public template for that idea: a server
whose entire surface is read-only because there is nothing else in it.

## the tools (both read-only)

- `search_items(query)`: keyword search over discovery items in `data.json`.
- `get_item(id)`: fetch one item.

swap `data.json` and `call_tool()` for your real read source (an official,
read-only api). the marked block is the only place you add tools, and the comment
says, in caps, not to add a writer.

## requirements

python3 only, no install, no third-party deps. needs python >= 3.9 (it uses
`from __future__ import annotations` plus pep 604 `list[dict]` type hints).

## run + register

```bash
python3 server.py              # runs as a stdio mcp server
python3 server.py --selftest   # scripted initialize/list/call session
```

register in claude code. copy `.mcp.json.example` to `.mcp.json` and use an
**absolute** path to `server.py` (a relative path won't resolve once claude code
launches the server from its own cwd):

```json
{ "mcpServers": { "readonly-skeleton": {
    "type": "stdio", "command": "python3", "args": ["/abs/path/server.py"] } } }
```

or let the cli write it for you:

```bash
claude mcp add --scope project --transport stdio readonly-skeleton -- python3 /abs/path/server.py
```

## protocol (verified against the mcp spec)

- transport: **newline-delimited json-rpc 2.0** over stdio (one compact object per
  line; no content-length headers).
- `initialize`: returns `{protocolVersion, capabilities:{tools:{}}, serverInfo}`.
  the server agrees on the client's `protocolVersion` only if it is one it
  supports, otherwise it answers with its own (`2025-11-25`).
- `notifications/initialized`: notification, no response.
- `tools/list`: returns `{tools:[{name, description, inputSchema}]}` (inputSchema is
  a json schema object).
- `tools/call`: returns `{content:[{type:"text", text}], isError}`.

all shapes and method names confirmed against the official mcp spec (2025-11-25).

## verified

stdlib-only, no network. dispatch is a pure `handle()` function. this is the
**literal** `python3 server.py --selftest` output (each response line is truncated
to 200 chars by the selftest, so a couple end mid-json; run it yourself and it
matches exactly):

```
>>> initialize (client asked 2025-11-25)
    {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "readonly-skeleton", "version": "0.1.0"}}}
>>> notifications/initialized (notification, no response)
>>> tools/list
    {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "search_items", "description": "Search discovery items by keyword in title/summary. Read-only.", "inputSchema": {"type": "object", "properties
>>> tools/call search_items({'query': 'agent'})
    {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "[1] subagents can spawn subagents, capped 5 deep\n[3] the verification paradox in agent loops"}], "isError": false}}
>>> tools/call get_item({'id': '1'})
    {"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text", "text": "{\n  \"id\": \"1\",\n  \"title\": \"subagents can spawn subagents, capped 5 deep\",\n  \"summary\": \"recursive agents fail
>>> tools/call nope({})
    {"jsonrpc": "2.0", "id": 5, "result": {"content": [{"type": "text", "text": "unknown tool: nope"}], "isError": true}}
>>> initialize (client asked 1999-01-01)
    {"jsonrpc": "2.0", "id": 6, "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "readonly-skeleton", "version": "0.1.0"}}}
```

the last line is the version check: a client asking for the unsupported
`1999-01-01` gets the server's own `2025-11-25` back rather than a blind echo.

also exercised as a real piped stdio session (the server consumed
newline-delimited requests and emitted one response line per request, none for the
notification). `.mcp.json.example` and `data.json` validated as json.

## next

- the same surface using the official `mcp` python sdk (fastmcp) for production:
  `@mcp.tool()`-decorated read functions; this stdlib version is the teaching one.
- pagination (`nextCursor`) once a real source returns many items.
- a `resources/list` read surface alongside tools.
