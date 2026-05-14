"""
Parse the autonomous agent's stdout into structured events the UI can render.

Input (examples):
    ======================================================================
      SESSION 3: CODING AGENT
    ======================================================================
    [Tool: Bash]
       Input: {'command': 'ls -la', ...}
       [Done]
       [BLOCKED] ...
       [Error] ...
    Progress: 12/200 tests passing (6.0%)

Output events:
    {"kind": "session", "session": 3, "role": "coding"}
    {"kind": "tool_use", "name": "Bash", "input": "..."}
    {"kind": "tool_result", "status": "done"|"blocked"|"error", "detail": "..."}
    {"kind": "progress", "passing": 12, "total": 200, "pct": 6.0}
    {"kind": "text", "text": "..."}
    {"kind": "info", "text": "..."}
    {"kind": "error", "text": "..."}
    {"kind": "done"}
"""

import re
import time
from typing import Iterable, Iterator, Optional


SESSION_RE = re.compile(r"^\s*SESSION\s+(\d+):\s+(INITIALIZER|CODING AGENT)\s*$")
PROGRESS_RE = re.compile(r"Progress:\s*(\d+)/(\d+)\s+tests passing\s*\(([\d.]+)%\)")
TOOL_USE_RE = re.compile(r"^\s*\[Tool:\s*([^\]]+)\]\s*$")
TOOL_INPUT_RE = re.compile(r"^\s*Input:\s*(.+?)\s*$")
DONE_RE = re.compile(r"^\s*\[Done\]\s*$")
BLOCKED_RE = re.compile(r"^\s*\[BLOCKED\]\s*(.*)$")
ERROR_LINE_RE = re.compile(r"^\s*\[Error\]\s*(.*)$")
ERROR_DURING_RE = re.compile(r"^Error during agent session:\s*(.*)$")
FATAL_RE = re.compile(r"^Fatal error:\s*(.*)$")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def parse_line(line: str, state: dict) -> Optional[dict]:
    """Parse one raw line and return a structured event, or None to skip."""
    stripped = line.rstrip("\n")

    m = SESSION_RE.match(stripped)
    if m:
        return {
            "kind": "session",
            "session": int(m.group(1)),
            "role": "initializer" if m.group(2) == "INITIALIZER" else "coding",
            "ts": now_iso(),
        }

    m = PROGRESS_RE.search(stripped)
    if m:
        return {
            "kind": "progress",
            "passing": int(m.group(1)),
            "total": int(m.group(2)),
            "pct": float(m.group(3)),
            "ts": now_iso(),
        }

    m = TOOL_USE_RE.match(stripped)
    if m:
        state["pending_tool"] = {"name": m.group(1).strip(), "input": None}
        return None  # wait for the input line

    m = TOOL_INPUT_RE.match(stripped)
    if m and state.get("pending_tool"):
        pending = state.pop("pending_tool")
        pending["input"] = m.group(1)
        pending["kind"] = "tool_use"
        pending["ts"] = now_iso()
        return pending

    m = BLOCKED_RE.match(stripped)
    if m:
        return {"kind": "tool_result", "status": "blocked", "detail": m.group(1), "ts": now_iso()}

    m = ERROR_LINE_RE.match(stripped)
    if m:
        return {"kind": "tool_result", "status": "error", "detail": m.group(1), "ts": now_iso()}

    m = DONE_RE.match(stripped)
    if m:
        return {"kind": "tool_result", "status": "done", "ts": now_iso()}

    m = ERROR_DURING_RE.match(stripped) or FATAL_RE.match(stripped)
    if m:
        return {"kind": "error", "text": m.group(1), "ts": now_iso()}

    if "SESSION COMPLETE" in stripped:
        return {"kind": "done", "ts": now_iso()}

    if stripped.strip() in {"", "-" * 70, "=" * 70}:
        return None

    # Informational banner lines vs. agent-produced text.
    # Heuristic: lines that look like banners start with spaces or keywords.
    if any(stripped.startswith(pfx) for pfx in (
        "Project directory:", "Model:", "Max iterations:",
        "Fresh start", "Continuing", "Copied app_spec",
        "Created security", "   -", "Sending prompt",
        "Preparing next", "Agent will auto-continue",
        "  ", "NOTE:", "TO RUN THE", "cd ", "./init.sh",
        "# Or manually", "  npm install", "Then open",
    )):
        return {"kind": "info", "text": stripped, "ts": now_iso()}

    return {"kind": "text", "text": stripped, "ts": now_iso()}


def parse_lines(lines: Iterable[str]) -> Iterator[dict]:
    state: dict = {}
    for line in lines:
        ev = parse_line(line, state)
        if ev:
            yield ev
