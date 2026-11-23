#!/usr/bin/env python3
"""Stop hook: make the agent WRITE to the memory tree after it works and before it hands back to the user.

When the agent is about to stop, the hook looks at the turn that is ending (from the last real user prompt in the
transcript to now). If the turn used at least HM_POST_MIN_TOOLS tools and no file in the memory tree changed since the
turn began, it blocks the stop once with a reason that tells the agent to record the turn's decisions and results per
the hierarchical-memory skill, or to say in one line that nothing is worth recording. When the agent stops again
(stop_hook_active is true) the hook always lets it, so it cannot loop. It does nothing without a memory tree, and
any error lets the stop through; it always exits 0.

The turn starts at the later of the time memory_pre.py recorded for the session and the last user prompt's timestamp in
the transcript.

Environment (all optional; see also hm_common.py):
  HM_POST_MIN_TOOLS   tool calls a turn needs before a write is required (default 2; pure chat turns are never blocked)
  HM_POST_DISABLE     set to 1 to turn the check off
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hm_common  # noqa: E402

CHUNK = 1 << 20
MAX_SCAN = 64 << 20          # bytes of transcript to read backwards at most


def reverse_lines(path):
    """Lines of a file from the last to the first, reading at most MAX_SCAN bytes from the end."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        scanned, rest = 0, b""
        while pos > 0 and scanned < MAX_SCAN:
            step = min(CHUNK, pos)
            pos -= step
            scanned += step
            f.seek(pos)
            block = f.read(step) + rest
            lines = block.split(b"\n")
            rest = lines[0]
            for line in reversed(lines[1:]):
                if line.strip():
                    yield line
        if pos == 0 and rest.strip():
            yield rest


def is_prompt(entry):
    """True for a user turn the person typed (or a notification), False for tool results and meta entries."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        kinds = {block.get("type") for block in content if isinstance(block, dict)}
        return "tool_result" not in kinds and "text" in kinds
    return False


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def current_turn(transcript):
    """-> (tool calls in the turn, the turn's prompt time or None, True when the prompt was found)."""
    tools = 0
    for raw in reverse_lines(transcript):
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "assistant" and not entry.get("isSidechain"):
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, list):
                tools += sum(1 for block in content if isinstance(block, dict) and block.get("type") == "tool_use")
        elif is_prompt(entry):
            return tools, parse_time(entry.get("timestamp")), True
    return tools, None, False


def turn_start(session_id, prompt_time):
    times = [t for t in (prompt_time,) if t is not None]
    marker = hm_common.turn_marker(session_id)
    if marker is not None:
        try:
            times.append(marker.stat().st_mtime)
        except OSError:
            pass
    return max(times) if times else None


def reason(root, tools):
    return (f"[hierarchical-memory, Stop hook] This turn used {tools} tool calls but wrote nothing to the memory tree "
            f"{root}. Before you hand back to the user, record what is worth remembering per the hierarchical-memory skill: "
            "one small new step file per decision, finding, result, dead end or user instruction (frontmatter title, created "
            "from date -Iseconds with the UTC offset, status, one specific summary line; link files and commits instead of "
            "pasting logs), supersede old entries instead of rewriting them, and keep index.md's Current state true. Then "
            "finish your reply and name the files you wrote. If nothing from this turn is worth recording, say so in one "
            "line and finish.")


def main():
    try:
        if os.environ.get("HM_POST_DISABLE") == "1":
            return
        payload = hm_common.read_payload()
        if payload.get("stop_hook_active"):
            return                                   # the agent already continued once because of a Stop hook
        root = hm_common.find_memory_root(payload.get("cwd"))
        transcript = payload.get("transcript_path")
        if root is None or not isinstance(transcript, str) or not os.path.isfile(transcript):
            return
        tools, prompt_time, found = current_turn(transcript)
        if not found or tools < int(os.environ.get("HM_POST_MIN_TOOLS") or 2):
            return
        start = turn_start(payload.get("session_id"), prompt_time)
        if start is None:
            return
        files = hm_common.memory_files(root)
        if files and max(mtime for mtime, _, _ in files) >= start - 1.0:
            return                                   # memory was written during this turn
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason(root, tools)}) + "\n")
    except BaseException:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
