"""Shared helpers for the hierarchical-memory hooks (memory_pre.py, memory_post.py). Standard library only."""
import json
import os
import re
import sys
import time
from pathlib import Path

# Environment variables (all optional):
#   HM_MEMORY_DIR    memory tree to use; default: the nearest memory/ with an index.md at or above the session's cwd
#   HM_STATE_DIR     where the pre hook records each turn's start; default ${XDG_STATE_HOME:-~/.local/state}/hierarchical-memory
#   HM_FILE_LIMIT    per-file size budget in bytes the pre hook warns about (default 8192, about 2k tokens)


def read_payload(limit=5_000_000):
    """The hook's stdin JSON as a dict ({} when it is missing or malformed)."""
    try:
        data = json.loads(sys.stdin.buffer.read(limit).decode("utf-8", "replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def find_memory_root(cwd=None):
    """The memory tree for this session, or None.

    HM_MEMORY_DIR wins when it names a directory. Otherwise walk up from cwd (the hook payload's cwd, else the
    process cwd) and return the first <dir>/memory that has an index.md, as the skill lays the tree out."""
    explicit = os.environ.get("HM_MEMORY_DIR")
    if explicit:
        path = Path(explicit).expanduser()
        return path.resolve() if path.is_dir() else None
    try:
        start = Path(cwd or os.getcwd()).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    for directory in (start, *start.parents):
        candidate = directory / "memory"
        if (candidate / "index.md").is_file():
            return candidate
    return None


def state_dir():
    base = os.environ.get("HM_STATE_DIR")
    if base:
        return Path(base).expanduser()
    xdg = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(xdg) / "hierarchical-memory"


def turn_marker(session_id):
    """Path of the file whose mtime is the start of the session's current turn (None without a usable id)."""
    if not isinstance(session_id, str):
        return None
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", session_id)[:128]
    if not safe.strip("._"):
        return None
    return state_dir() / "turns" / safe


def mark_turn_start(session_id):
    marker = turn_marker(session_id)
    if marker is None:
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{time.time():.3f}\n")
    except OSError:
        pass


def memory_files(root):
    """(mtime, size, relative path) of every .md file in the tree, skipping hidden directories."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            out.append((st.st_mtime, st.st_size, os.path.relpath(full, root)))
    return out


def is_automated_prompt(prompt):
    """Background events delivered as prompts (task notifications, system notices) carry no request."""
    head = prompt.lstrip()[:200]
    return head.startswith(("<task-notification>", "[SYSTEM NOTIFICATION", "<system-reminder>"))
