# project-memory

A [Claude Code](https://claude.com/claude-code) skill that keeps long-running project memory as a tree of small markdown files (phases → steps) in a `memory/` directory, so an agent can recover context at the start of a session without re-reading everything.

- Layout, frontmatter format, reading and writing rules: see [`SKILL.md`](SKILL.md).
- Read `memory/index.md` first; scan summaries with `grep -r -m1 '^summary:' memory --include='*.md' | sort`.

## Install

Copy the skill folder into your Claude Code skills directory:

```bash
mkdir -p ~/.claude/skills/project-memory
cp SKILL.md ~/.claude/skills/project-memory/SKILL.md
```

Then ask the agent to use it at the start of a session ("recover context from `memory/`") and after a plan is approved ("record this as a new phase").
