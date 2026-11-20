#!/usr/bin/env python3
"""xskill_mcp.py — Expose an XSkill knowledge base as a read-only MCP server (stdio).

Any MCP-compatible agent (Claude Code, Codex, Cursor, OpenCode, Gemini CLI, etc.)
can attach to a shared knowledge base with a single configuration entry.

Transport: stdio, newline-delimited JSON-RPC 2.0 (MCP standard).
Tools:
  xskill_search  Search skills and experiences using a full-sentence task description
  xskill_read    Read the full content of a matched entry (path-locked inside XSKILL_ROOT)

Usage:
  python3 xskill_mcp.py [--root /path/to/xskill-vault]
  XSKILL_ROOT=/path/to/xskill-vault python3 xskill_mcp.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SERVER_NAME = "xskill"
SERVER_VERSION = "1.1.0"
SUPPORTED_PROTOCOLS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
DEFAULT_PROTOCOL = "2025-06-18"
MAX_READ_CHARS = 20000

SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_root(cli_root: str | None = None) -> Path:
    if cli_root:
        return Path(cli_root).expanduser().resolve()
    env_root = os.environ.get("XSKILL_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return SCRIPT_DIR


ROOT: Path = _resolve_root()


def _load_quick_search():
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from xskill_core import quick_search  # type: ignore

    return quick_search


def _build_tools(root: Path) -> list[dict]:
    return [
        {
            "name": "xskill_search",
            "description": (
                "Search the shared XSkill knowledge base (reusable Skill workflows and "
                "Experience decision rules). Call before starting academic, technical, "
                "coding, or data tasks. Pass a full-sentence task description as `query` "
                "(short 2-3 word queries score poorly under Jaccard matching). "
                "After a hit, call `xskill_read` to load the full entry."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-sentence task description",
                    },
                    "project": {
                        "type": "string",
                        "description": "Optional project namespace; omit to search global entries",
                    },
                    "k_skills": {
                        "type": "integer",
                        "description": "Max number of skills to return (default 3)",
                        "default": 3,
                    },
                    "k_experiences": {
                        "type": "integer",
                        "description": "Max number of experiences to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "xskill_read",
            "description": (
                f"Read the full content of an XSkill entry. `path` must be returned by "
                f"`xskill_search` and reside inside {root}."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the entry markdown file",
                    }
                },
                "required": ["path"],
            },
        },
    ]


def _text(payload) -> dict:
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": payload}], "isError": False}


def _error_text(msg: str) -> dict:
    return {"content": [{"type": "text", "text": msg}], "isError": True}


def tool_search(args: dict) -> dict:
    query = (args.get("query") or "").strip()
    if not query:
        return _error_text("query must not be empty")
    project = args.get("project") or None
    try:
        quick_search = _load_quick_search()
    except Exception as e:  # noqa: BLE001
        return _error_text(f"failed to import xskill_core: {e!r}")
    try:
        r = quick_search(
            query,
            project=project,
            k_skills=int(args.get("k_skills", 3)),
            k_experiences=int(args.get("k_experiences", 5)),
            xskill_root=str(ROOT),
        )
    except Exception as e:  # noqa: BLE001
        return _error_text(f"search failed: {e!r}")

    hits = []
    for kind in ("skills", "experiences"):
        for h in r.get(kind, []):
            hits.append(
                {
                    "type": "skill" if kind == "skills" else "experience",
                    "name": h.get("name"),
                    "score": round(float(h.get("score", 0)), 4),
                    "description": h.get("description", ""),
                    "path": h.get("path"),
                    "source": h.get("source"),
                }
            )
    if not hits:
        return _text(
            {
                "hits": [],
                "note": "No matches. Retry with a fuller sentence describing the task rather than short keywords.",
            }
        )
    return _text({"hits": hits, "note": "Call xskill_read on the returned path to read the full entry."})


def tool_read(args: dict) -> dict:
    raw = (args.get("path") or "").strip()
    if not raw:
        return _error_text("path must not be empty")
    try:
        p = Path(raw).resolve()
        p.relative_to(ROOT.resolve())
    except Exception:  # noqa: BLE001
        return _error_text(f"access denied: path must reside inside {ROOT} (got {raw})")
    if not p.is_file():
        return _error_text(f"file not found: {p}")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return _error_text(f"read failed: {e!r}")
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n\n...(truncated, total {len(text)} chars)"
    return _text(text)


HANDLERS = {"xskill_search": tool_search, "xskill_read": tool_read}


def handle(req: dict) -> dict | None:
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        asked = (req.get("params") or {}).get("protocolVersion")
        proto = asked if asked in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": proto,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": _build_tools(ROOT)}}

    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if fn is None:
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32602, "message": f"unknown tool: {name}"},
            }
        try:
            payload = fn(args)
        except Exception as e:  # noqa: BLE001
            payload = _error_text(f"{name} execution error: {e!r}")
        return {"jsonrpc": "2.0", "id": rid, "result": payload}

    if rid is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main(argv: list[str] | None = None) -> int:
    global ROOT
    parser = argparse.ArgumentParser(description="XSkill read-only MCP server (stdio).")
    parser.add_argument(
        "--root",
        default=None,
        help="Path to the XSkill knowledge base root (overrides XSKILL_ROOT).",
    )
    ns = parser.parse_args(argv)
    ROOT = _resolve_root(ns.root)

    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            out.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "parse error"},
                    }
                )
                + "\n"
            )
            out.flush()
            continue
        try:
            resp = handle(req)
        except Exception as e:  # noqa: BLE001
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": {"code": -32603, "message": f"internal error: {e!r}"},
            }
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
