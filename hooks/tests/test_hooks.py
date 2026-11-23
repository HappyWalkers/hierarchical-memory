"""Tests for memory_pre.py and memory_post.py. Run: python3 -m unittest discover -s hooks/tests"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]


def run(script, payload, env):
    proc = subprocess.run([sys.executable, "-I", str(HOOKS / script)], input=json.dumps(payload).encode(),
                          capture_output=True, env=env, timeout=30)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.decode().strip()
    return json.loads(out) if out else None


def note(path, title, summary, body=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\ncreated: 2026-01-01T00:00:00+00:00\nstatus: done\nsummary: {summary}\n---\n\n{body}\n")


def transcript(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def prompt_entry(text, ts):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}}


def tool_entry(name="Bash"):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": name, "input": {}}]}}


def result_entry():
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}}


def iso(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(seconds)) + ".000Z"


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.project = base / "project"
        self.memory = self.project / "memory"
        note(self.memory / "index.md", "Demo project", "a demo", "## Current state\nworking")
        note(self.memory / "01-database" / "index.md", "Database phase", "pick and build the database")
        note(self.memory / "01-database" / "01-engine-choice.md", "Use SQLite for the database",
             "SQLite in a single file; one server, no database service", "We compared SQLite and Postgres.")
        old = time.time() - 3600
        for f in self.memory.rglob("*.md"):
            os.utime(f, (old, old))
        self.elsewhere = base / "elsewhere"
        self.elsewhere.mkdir()
        self.env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(base), "HM_STATE_DIR": str(base / "state")}
        self.transcript = base / "t.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    # --- pre hook ---
    def test_pre_points_at_index_and_related_note(self):
        out = run("memory_pre.py", {"prompt": "Should we switch from SQLite to Postgres?", "cwd": str(self.project / "src"),
                                    "session_id": "s1"}, self.env)
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn(str(self.memory), text)
        self.assertIn("index.md", text)
        self.assertIn("01-database/01-engine-choice.md", text)
        self.assertTrue((Path(self.env["HM_STATE_DIR"]) / "turns" / "s1").is_file())

    def test_pre_silent_without_memory_tree(self):
        self.assertIsNone(run("memory_pre.py", {"prompt": "SQLite?", "cwd": str(self.elsewhere), "session_id": "s1"}, self.env))

    def test_pre_silent_for_notifications(self):
        payload = {"prompt": "<task-notification>done</task-notification>", "cwd": str(self.project), "session_id": "s1"}
        self.assertIsNone(run("memory_pre.py", payload, self.env))

    def test_pre_env_override_and_no_match(self):
        env = dict(self.env, HM_MEMORY_DIR=str(self.memory))
        out = run("memory_pre.py", {"prompt": "zebra quokka", "cwd": str(self.elsewhere), "session_id": "s2"}, env)
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("No note matched", text)
        self.assertNotIn("<memory_candidates>", text)

    def test_pre_warns_about_oversized_recent_file(self):
        big = self.memory / "01-database" / "02-big.md"
        note(big, "Big", "too long", "x" * 9000)
        out = run("memory_pre.py", {"prompt": "anything about schema", "cwd": str(self.project), "session_id": "s3"}, self.env)
        self.assertIn("02-big.md is", out["hookSpecificOutput"]["additionalContext"])

    def test_pre_bad_input_is_silent(self):
        proc = subprocess.run([sys.executable, "-I", str(HOOKS / "memory_pre.py")], input=b"not json",
                              capture_output=True, env=self.env, timeout=30)
        self.assertEqual((proc.returncode, proc.stdout), (0, b""))

    # --- post hook ---
    def post(self, entries, **extra):
        transcript(self.transcript, entries)
        payload = {"session_id": "s1", "transcript_path": str(self.transcript), "cwd": str(self.project),
                   "stop_hook_active": False}
        payload.update(extra)
        return run("memory_post.py", payload, self.env)

    def turn(self, tools, prompt_age=60):
        entries = [prompt_entry("earlier", iso(time.time() - 7200)), tool_entry(), result_entry(), tool_entry(), result_entry(),
                   prompt_entry("do the work", iso(time.time() - prompt_age))]
        for _ in range(tools):
            entries += [tool_entry(), result_entry()]
        entries.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}})
        return entries

    def test_post_blocks_when_work_left_no_memory(self):
        out = self.post(self.turn(3))
        self.assertEqual(out["decision"], "block")
        self.assertIn("3 tool calls", out["reason"])
        self.assertIn(str(self.memory), out["reason"])

    def test_post_allows_when_memory_written_this_turn(self):
        note(self.memory / "01-database" / "02-new-finding.md", "New finding", "recorded")
        self.assertIsNone(self.post(self.turn(3)))

    def test_post_counts_only_the_current_turn(self):
        self.assertIsNone(self.post(self.turn(1)))     # the earlier turn's two tool calls do not count

    def test_post_never_loops(self):
        self.assertIsNone(self.post(self.turn(5), stop_hook_active=True))

    def test_post_silent_without_memory_tree_or_transcript(self):
        self.assertIsNone(self.post(self.turn(5), cwd=str(self.elsewhere)))
        self.assertIsNone(run("memory_post.py", {"session_id": "s1", "transcript_path": str(self.transcript) + ".missing",
                                                 "cwd": str(self.project)}, self.env))

    def test_post_uses_pre_hook_marker_when_later(self):
        # The prompt timestamp is old, but memory_pre.py marked the turn start just now: a write from before the marker
        # does not count as this turn's write.
        note(self.memory / "01-database" / "02-older.md", "Older", "written before the turn")
        past = time.time() - 30
        os.utime(self.memory / "01-database" / "02-older.md", (past, past))
        run("memory_pre.py", {"prompt": "database work", "cwd": str(self.project), "session_id": "s1"}, self.env)
        self.assertEqual(self.post(self.turn(3, prompt_age=600))["decision"], "block")

    def test_post_disable_switch(self):
        transcript(self.transcript, self.turn(4))
        env = dict(self.env, HM_POST_DISABLE="1")
        self.assertIsNone(run("memory_post.py", {"session_id": "s1", "transcript_path": str(self.transcript),
                                                 "cwd": str(self.project)}, env))


if __name__ == "__main__":
    unittest.main()
