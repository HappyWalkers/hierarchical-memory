# Hooks for hierarchical memory

Two [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) that make the agent use the memory tree on every turn instead of only when it remembers to:

| Hook | Event | What it does |
|---|---|---|
| `memory_pre.py` | `UserPromptSubmit` | **Check memory before acting.** Adds context that tells the agent to read `memory/index.md` and the notes related to the prompt, with a ranked list of those notes: a keyword match over titles, summaries, paths and bodies. Also reports the last memory write and any recent file over the size budget. |
| `memory_post.py` | `Stop` | **Write memory before handing back.** If the turn that is ending used tools but changed nothing in the memory tree, it blocks the stop once and tells the agent to record the turn's decisions and results, or to say in one line that nothing is worth recording. |

Both find the tree the way the skill lays it out: the nearest `memory/` that has an `index.md`, walking up from the session's working directory. Set `HM_MEMORY_DIR` to use a fixed tree instead.

Without a tree they do nothing. They never fail a prompt: every error is swallowed and they always exit 0. The Stop hook lets the agent stop the second time (`stop_hook_active`), so it cannot loop.

## Install

```bash
git clone https://github.com/HappyWalkers/hierarchical-memory.git
cd hierarchical-memory
mkdir -p ~/.claude/skills/hierarchical-memory ~/.claude/hooks/hierarchical-memory
cp SKILL.md ~/.claude/skills/hierarchical-memory/
cp hooks/hm_common.py hooks/memory_pre.py hooks/memory_post.py ~/.claude/hooks/hierarchical-memory/
```

Then add the hooks to `~/.claude/settings.json`, or to a project's `.claude/settings.json`. Merge them into any `hooks` you already have; don't replace those.

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "python3 -I \"$HOME/.claude/hooks/hierarchical-memory/memory_pre.py\"", "timeout": 10 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "python3 -I \"$HOME/.claude/hooks/hierarchical-memory/memory_post.py\"", "timeout": 10 } ] }
    ]
  }
}
```

Requirements: Python 3.8 or newer, standard library only. Open `/hooks` in Claude Code once after editing settings (or restart) so it reloads them.

## Settings

All optional environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `HM_MEMORY_DIR` | nearest `memory/` with an `index.md` | use this tree |
| `HM_EXTRA_ROOTS` | none | more note trees for the pre hook to search, `label=/dir;label2=/dir2` |
| `HM_RECALL_MAX` | 6 | most related notes listed |
| `HM_RECALL_MIN` | 17 | score the best match needs before any note is listed |
| `HM_FILE_LIMIT` | 8192 | per-file size budget in bytes (about 2k tokens) the pre hook warns about |
| `HM_POST_MIN_TOOLS` | 2 | tool calls a turn needs before the Stop hook asks for a memory write; chat-only turns are never blocked |
| `HM_POST_DISABLE` | unset | `1` turns the Stop check off |
| `HM_STATE_DIR` | `${XDG_STATE_HOME:-~/.local/state}/hierarchical-memory` | where the pre hook records when each turn started |

## How the Stop check decides

The turn starts at the later of two times: when `memory_pre.py` saw the prompt, and the last user prompt's timestamp in the transcript. The transcript is read backwards from the end, so long sessions stay fast.

The hook counts the turn's tool calls, ignoring subagent entries. It blocks when two things are true: there are at least `HM_POST_MIN_TOOLS` of them, and no `.md` file under the memory tree changed since the turn started.

When it blocks, the agent gets one more round to write the notes or decline in a line. That round costs one extra model call per blocked turn.

## Tests

```bash
python3 -m unittest discover -s hooks/tests -v
```
