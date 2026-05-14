# o-agent — Long-Running Autonomous Coding Harness

A minimal harness for **long-running autonomous agents**, implementing the
two-agent pattern from Anthropic's engineering blog:

- Article: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Reference implementation: https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding
- Claude Agent SDK: https://platform.claude.com/docs/en/agent-sdk/overview
- Multi-context prompting: https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices#multi-context-window-workflows

## Core idea

Each "session" runs in a fresh context window. Durable state lives on disk:

| File | Role |
|------|------|
| `feature_list.json` | 200+ test cases — **the single source of truth**. Features can only flip `passes: false` → `true`. Never removed or edited. |
| `init.sh` | Environment + dev-server startup script |
| `claude-progress.txt` | Session-by-session notes |
| `git log` | History & rollback |
| `app_spec.txt` | Immutable project specification |

The harness runs two roles:

1. **Initializer Agent** (session 1): reads `app_spec.txt`, generates `feature_list.json` (200 tests), writes `init.sh`, initialises git.
2. **Coding Agent** (sessions 2..N): orients via `pwd` / `git log` / `claude-progress.txt`, runs `init.sh`, verifies previously-passing tests (regression guard), implements **one** feature end-to-end with browser automation (Puppeteer MCP), flips its `passes` flag, commits, updates progress notes.

## Install

```bash
# Claude Code CLI (required by the SDK)
npm install -g @anthropic-ai/claude-code

# Python deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY='sk-ant-...'
```

## Run

```bash
# fresh project (places it under generations/my_project)
python autonomous_agent_demo.py --project-dir ./my_project

# limit iterations for a quick demo
python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 3

# resume — same command
python autonomous_agent_demo.py --project-dir ./my_project
```

Press `Ctrl+C` to pause; the same command resumes.

## Layout

```
o-agent/
├── autonomous_agent_demo.py   # CLI entry point
├── agent.py                   # session loop (fresh client per iteration)
├── client.py                  # ClaudeSDKClient wiring + Puppeteer MCP
├── security.py                # PreToolUse bash allowlist hook
├── progress.py                # reads feature_list.json → progress summary
├── prompts.py                 # loads prompts/*.md
├── prompts/
│   ├── app_spec.txt           # what to build (edit to target a different app)
│   ├── initializer_prompt.md  # session 1 prompt
│   └── coding_prompt.md       # session 2..N prompt
├── requirements.txt
└── generations/               # generated projects live here (gitignored)
```

## Security (defense in depth)

1. **OS sandbox** — `ClaudeCodeOptions` turns on the sandbox so bash is isolated.
2. **Filesystem permissions** — `Read/Write/Edit/Glob/Grep` limited to `./**` of `project_dir` (see `.claude_settings.json` that's auto-written per project).
3. **Bash allowlist hook** — `security.py` `bash_security_hook` is registered as `PreToolUse` for `Bash`. Anything outside `ALLOWED_COMMANDS` is blocked. `pkill`, `chmod`, `init.sh` get extra per-command validation.

Allowed commands: `ls cat head tail wc grep cp mkdir chmod pwd npm node git ps lsof sleep pkill ./init.sh`.

## Customise

- **Different app**: edit `prompts/app_spec.txt`.
- **Fewer features** (faster demos): in `prompts/initializer_prompt.md` change `200` to `20–50`.
- **Expand shell access**: add to `ALLOWED_COMMANDS` in `security.py`.
- **Different model**: `--model claude-opus-4-5-...` (the article used Opus 4.5).

## What to expect

- Session 1 (initializer) takes **10–20+ minutes** — it writes 200 test cases. This can look like a hang; watch for `[Tool: ...]` lines.
- Each coding session: **5–15 minutes**.
- A full build is **many hours**.

## Why this works

The article's thesis: give long-running agents durable, concrete, append-only artefacts instead of trying to preserve context across sessions. The feature list is the "world state"; commits and progress notes are the "journal"; `init.sh` plus a mandatory `pwd` / `git log` / regression-test opener lets every fresh agent reconstruct context in under a minute.
