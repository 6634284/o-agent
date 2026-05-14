"""
Task lifecycle manager.

A Task has:
  - durable metadata (name, app_spec, model, max_iterations, feature_count) -> saved as JSON
  - a workspace (per-task project_dir with prompts/ + project/)
  - a subprocess (while running) streaming stdout -> structured events via event_parser

Durable state: web/data/tasks.json  +  web/data/tasks/<id>/
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from event_parser import parse_line, now_iso


REPO_ROOT = Path(__file__).resolve().parents[2]   # /Users/ltc/projects/o-agent
WEB_ROOT = REPO_ROOT / "web"
DATA_DIR = WEB_ROOT / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
TASKS_WORKSPACE = DATA_DIR / "tasks"

DEFAULT_SPEC = (REPO_ROOT / "prompts" / "app_spec.txt").read_text()
DEFAULT_INIT_PROMPT = (REPO_ROOT / "prompts" / "initializer_prompt.md").read_text()
DEFAULT_CODING_PROMPT = (REPO_ROOT / "prompts" / "coding_prompt.md").read_text()
DEFAULT_FOLLOW_UP_PROMPT = (REPO_ROOT / "prompts" / "follow_up_prompt.md").read_text()

AVAILABLE_MODELS = [
    {"id": "ppio/pa/claude-opus-4-7", "label": "Opus 4.7 (quality)"},
    {"id": "ppio/pa/claude-sonnet-4-6", "label": "Sonnet 4.6 (cheaper)"},
]

# Read API credentials from the process environment so secrets are not stored in git.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "http://model.mify.ai.srv/anthropic")

SPEC_EXPANSION_SYSTEM = """\
You expand a short product description into a detailed XML project specification that an autonomous coding agent will implement end-to-end.

Output ONLY the XML, no prose, no code fences. The XML must follow this shape:

<project_specification>
  <project_name>...</project_name>
  <overview>2-4 sentence plain description of the product</overview>
  <technology_stack>
    <frontend>
      <framework>React with Vite</framework>
      <styling>Tailwind CSS</styling>
      <state_management>React hooks</state_management>
      <port>Only launch on port {frontend_port}</port>
    </frontend>
    <backend>
      <runtime>Node.js with Express</runtime>
      <database>SQLite with better-sqlite3</database>
    </backend>
  </technology_stack>
  <core_features>
    <feature_group name="...">
      - concrete bullet
      - concrete bullet
    </feature_group>
    ... more feature_groups covering every capability the user asked for ...
  </core_features>
  <ui_requirements>
    - concrete layout / interaction rules
  </ui_requirements>
  <data_model>
    - tables and their columns
  </data_model>
  <non_goals>
    - what is explicitly out of scope for the first version
  </non_goals>
</project_specification>

Rules:
- Keep the stack block EXACTLY as shown (React+Vite frontend, Node+Express+SQLite backend, Tailwind). Include the literal string `{frontend_port}` as the port value — the agent substitutes it at runtime.
- Preserve the user's language: if the description is in Chinese, write feature bullets in Chinese.
- Be concrete, not generic. Invent reasonable details only where the user was silent; do NOT invent features they did not ask for.
- Keep to a realistic first-version scope — list ~5-10 feature_groups, not 50."""


FOLLOW_UP_EXPANSION_SYSTEM = """\
You take a short natural-language change request for an existing software project and rewrite it as a concrete, scoped change spec for a coding agent.

Rules:
- Output plain prose (no XML, no code fences).
- Be concrete: name UI elements, routes/endpoints, data fields the change implies.
- Do NOT over-specify things the user didn't ask for (colors, animations, unrelated polish).
- Include a one-line "Scope:" statement naming what is IN scope for THIS change and what is explicitly OUT.
- Preserve the user's language.
- Keep under 250 words. This is a focused follow-up, not a rewrite."""


def _expand_follow_up_request(request: str, model: str) -> str:
    """Expand a short NL follow-up request into a concrete change spec."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed — run `pip3 install anthropic`")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        system=FOLLOW_UP_EXPANSION_SYSTEM,
        messages=[{"role": "user", "content": request.strip()}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
    text = "".join(parts).strip()
    return text or request.strip()


def _expand_description_to_spec(description: str, model: str) -> str:
    """Call Claude to turn a short NL description into the detailed XML spec."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed — run `pip3 install anthropic`")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SPEC_EXPANSION_SYSTEM,
        messages=[{"role": "user", "content": description.strip()}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
    text = "".join(parts).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("xml"):
            text = text[3:]
        text = text.strip()
    if "<project_specification>" not in text:
        raise RuntimeError(f"LLM did not return a <project_specification> block:\n{text[:400]}")
    return text


@dataclass
class Task:
    id: str
    name: str
    model: str
    max_iterations: Optional[int]
    feature_count: int
    app_spec: str
    description: str = ""          # original natural-language description the user typed
    status: str = "draft"         # draft | running | completed | stopped | error
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    progress_passing: int = 0
    progress_total: int = 0
    sessions: list[dict] = field(default_factory=list)   # [{num, role, started_at, ended_at}]
    last_error: Optional[str] = None
    follow_ups: list[dict] = field(default_factory=list)  # [{text, created_at, status}]
    mode: str = "build"            # "build" (initial) | "follow_up" (iterating on existing project)

    def workspace(self) -> Path:
        return TASKS_WORKSPACE / self.id

    def project_dir(self) -> Path:
        return self.workspace() / "project"

    def prompts_dir(self) -> Path:
        return self.workspace() / "prompts"

    def log_path(self) -> Path:
        return self.workspace() / "run.log"

    def events_path(self) -> Path:
        return self.workspace() / "events.jsonl"

    def public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


class TaskManager:
    """In-memory registry + disk persistence. One process instance."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TASKS_WORKSPACE.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        self.procs: dict[str, subprocess.Popen] = {}
        # per-task asyncio.Queues so SSE endpoints get live events
        self.subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = threading.Lock()
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        if not TASKS_FILE.exists():
            return
        try:
            raw = json.loads(TASKS_FILE.read_text())
        except json.JSONDecodeError:
            return
        for d in raw:
            t = Task(**d)
            # crashed-running tasks become "error" on reload (no subprocess carried over)
            if t.status == "running":
                t.status = "error"
                t.last_error = "process not alive after server restart"
            self.tasks[t.id] = t

    def _save(self) -> None:
        TASKS_FILE.write_text(json.dumps([t.public_dict() for t in self.tasks.values()], indent=2))

    # ---------- CRUD ----------

    def list_tasks(self) -> list[dict]:
        return [t.public_dict() for t in sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)]

    def get(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        return self.tasks[task_id]

    def create(
        self,
        name: str,
        app_spec: str,
        model: str,
        max_iterations: Optional[int],
        feature_count: int,
        description: str = "",
        fork_from: Optional[str] = None,
    ) -> Task:
        task_id = uuid.uuid4().hex[:12]
        desc_stripped = description.strip()

        source_task: Optional[Task] = None
        if fork_from:
            source_task = self.get(fork_from)  # KeyError surfaces as 404 upstream
            if not source_task.project_dir().exists() or not any(source_task.project_dir().iterdir()):
                raise RuntimeError(
                    f"source task {fork_from} has no project directory to fork"
                )

        # Decide the final spec + description.
        #   fork + no desc + no spec  -> inherit everything from source
        #   desc given                -> expand via LLM (fork or not)
        #   explicit spec given       -> use as-is
        #   nothing given             -> DEFAULT_SPEC (legacy)
        if source_task and not desc_stripped and not app_spec:
            final_spec = source_task.app_spec
            desc_final = source_task.description
        elif desc_stripped and not app_spec:
            try:
                final_spec = _expand_description_to_spec(desc_stripped, model)
            except Exception as e:
                final_spec = (
                    "<project_specification>\n"
                    f"  <project_name>{name or 'untitled'}</project_name>\n"
                    f"  <overview>{desc_stripped}</overview>\n"
                    f"  <note>LLM spec expansion failed: {e}</note>\n"
                    "</project_specification>\n"
                )
            desc_final = desc_stripped
        elif app_spec:
            final_spec = app_spec
            desc_final = desc_stripped
        else:
            final_spec = DEFAULT_SPEC
            desc_final = ""

        t = Task(
            id=task_id,
            name=name or f"task-{task_id[:6]}",
            model=model,
            max_iterations=max_iterations,
            feature_count=feature_count,
            app_spec=final_spec,
            description=desc_final,
        )
        t.workspace().mkdir(parents=True, exist_ok=True)

        if source_task:
            # Deep-copy the source's project dir (code, .git, feature_list.json, init.sh, …).
            shutil.copytree(
                source_task.project_dir(),
                t.project_dir(),
                dirs_exist_ok=True,
            )
            # If the spec changed (user provided a new description), overwrite
            # the project-level app_spec.txt so the coding agent reads the new
            # requirements, and drop feature_list.json so the initializer
            # regenerates tests for the new spec. If the spec is unchanged
            # (pure copy), keep feature_list.json so coding sessions resume
            # where the source left off.
            if final_spec != source_task.app_spec:
                (t.project_dir() / "app_spec.txt").write_text(final_spec)
                feature_list = t.project_dir() / "feature_list.json"
                if feature_list.exists():
                    feature_list.unlink()
        else:
            t.project_dir().mkdir(parents=True, exist_ok=True)

        self._write_prompts(t)
        self.tasks[task_id] = t
        self._save()
        return t

    def update(self, task_id: str, **fields) -> Task:
        t = self.get(task_id)
        if t.status == "running":
            raise RuntimeError("cannot edit a running task; stop it first")
        # If the user edited the description (and didn't simultaneously hand us a
        # new app_spec), re-expand.
        if fields.get("description") is not None and fields.get("app_spec") is None:
            new_desc = fields["description"].strip()
            if new_desc and new_desc != t.description:
                try:
                    fields["app_spec"] = _expand_description_to_spec(new_desc, fields.get("model") or t.model)
                except Exception as e:
                    t.last_error = f"spec expansion failed: {e}"
        for k in ("name", "app_spec", "model", "max_iterations", "feature_count", "description"):
            if k in fields and fields[k] is not None:
                setattr(t, k, fields[k])
        t.updated_at = now_iso()
        self._write_prompts(t)
        self._save()
        return t

    def delete(self, task_id: str) -> None:
        if task_id in self.procs:
            self.stop(task_id)
        t = self.tasks.pop(task_id, None)
        if t:
            shutil.rmtree(t.workspace(), ignore_errors=True)
        self._save()

    # ---------- prompts wiring ----------

    def _write_prompts(self, t: Task) -> None:
        t.prompts_dir().mkdir(parents=True, exist_ok=True)

        # Swap 200 -> feature_count in the initializer prompt
        init_text = DEFAULT_INIT_PROMPT.replace(
            "with 200 detailed", f"with {t.feature_count} detailed"
        ).replace(
            "Minimum 200 features", f"Minimum {t.feature_count} features"
        ).replace(
            "all 200+ features", f"all {t.feature_count}+ features"
        )
        (t.prompts_dir() / "initializer_prompt.md").write_text(init_text)
        (t.prompts_dir() / "coding_prompt.md").write_text(DEFAULT_CODING_PROMPT)
        (t.prompts_dir() / "follow_up_prompt.md").write_text(DEFAULT_FOLLOW_UP_PROMPT)
        (t.prompts_dir() / "app_spec.txt").write_text(t.app_spec)

    # ---------- subprocess ----------

    def start(self, task_id: str) -> Task:
        t = self.get(task_id)
        if t.status == "running":
            return t

        cmd = [
            "python3", "-u",
            str(REPO_ROOT / "autonomous_agent_demo.py"),
            "--project-dir", str(t.project_dir().resolve()),
            "--model", t.model,
        ]
        if t.max_iterations:
            cmd += ["--max-iterations", str(t.max_iterations)]

        t.mode = "build"
        self._spawn_agent(t, cmd)
        return t

    def start_follow_up(
        self,
        task_id: str,
        follow_up_text: str,
        max_iterations: Optional[int] = 2,
        expand: bool = False,
    ) -> Task:
        """Run a follow-up coding session that applies `follow_up_text` as a delta to the
        existing project. Does NOT re-run the initializer.

        If `expand` is True, the raw request is first rewritten by Claude into a more
        concrete change spec before being handed to the coding agent. The original text
        and the expanded text are both kept in the follow_ups history.
        """
        t = self.get(task_id)
        if t.status == "running":
            raise RuntimeError("task is already running; stop it first")

        raw = (follow_up_text or "").strip()
        if not raw:
            raise ValueError("follow-up text cannot be empty")

        # Must have a project on disk (initial build done).
        if not t.project_dir().exists() or not any(t.project_dir().iterdir()):
            raise RuntimeError(
                "follow-up requires an existing built project — run the task first before iterating"
            )

        expanded_text: Optional[str] = None
        if expand:
            try:
                expanded_text = _expand_follow_up_request(raw, t.model)
            except Exception as e:
                # Don't fail the whole request — fall back to the raw text and surface the error.
                t.last_error = f"follow-up expansion failed, using raw text: {e}"
        prompt_for_agent = expanded_text or raw

        # Write the prompt to a file to avoid shell-escaping issues with long/multiline input.
        follow_up_file = t.workspace() / "follow_up.txt"
        follow_up_file.write_text(prompt_for_agent)

        cmd = [
            "python3", "-u",
            str(REPO_ROOT / "autonomous_agent_demo.py"),
            "--project-dir", str(t.project_dir().resolve()),
            "--model", t.model,
            "--follow-up-prompt-file", str(follow_up_file.resolve()),
        ]
        if max_iterations:
            cmd += ["--max-iterations", str(max_iterations)]

        t.mode = "follow_up"
        t.follow_ups.append({
            "text": raw,
            "expanded_text": expanded_text,
            "created_at": now_iso(),
            "status": "running",
        })
        self._spawn_agent(t, cmd)
        return t

    def _spawn_agent(self, t: Task, cmd: list[str]) -> None:
        """Shared subprocess-spawn + reader-thread wiring used by start() and start_follow_up()."""
        # Refresh prompt templates on disk — this backfills new templates (e.g. follow_up_prompt.md)
        # for tasks created before a template existed.
        self._write_prompts(t)

        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = env.get("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY)
        env["ANTHROPIC_BASE_URL"] = env.get("ANTHROPIC_BASE_URL", ANTHROPIC_BASE_URL)
        env["AGENT_PROMPTS_DIR"] = str(t.prompts_dir().resolve())
        # Make sure node 20 is on PATH (nvm)
        nvm_node = Path.home() / ".nvm" / "versions" / "node" / "v20.19.5" / "bin"
        if nvm_node.exists():
            env["PATH"] = f"{nvm_node}:{env.get('PATH', '')}"

        log_fp = open(t.log_path(), "ab", buffering=0)
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
        )
        self.procs[t.id] = proc
        t.status = "running"
        t.last_error = None
        t.updated_at = now_iso()
        self._save()

        threading.Thread(
            target=self._reader_thread,
            args=(t.id, proc, log_fp),
            daemon=True,
        ).start()

    def stop(self, task_id: str) -> Task:
        t = self.get(task_id)
        proc = self.procs.get(task_id)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except ProcessLookupError:
                pass
        self.procs.pop(task_id, None)
        if t.status == "running":
            t.status = "stopped"
            if t.mode == "follow_up" and t.follow_ups and t.follow_ups[-1].get("status") == "running":
                t.follow_ups[-1]["status"] = "stopped"
                t.follow_ups[-1]["ended_at"] = now_iso()
            t.updated_at = now_iso()
            self._save()
        return t

    # ---------- reader + fan-out ----------

    def _reader_thread(self, task_id: str, proc: subprocess.Popen, log_fp) -> None:
        state: dict = {}
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                try:
                    log_fp.write(raw.encode("utf-8", errors="replace"))
                except Exception:
                    pass
                ev = parse_line(raw, state)
                if ev:
                    self._emit(task_id, ev)
            rc = proc.wait()
            t = self.tasks.get(task_id)
            if t:
                if t.status == "running":
                    t.status = "completed" if rc == 0 else "error"
                    if rc != 0:
                        t.last_error = f"exit code {rc}"
                # Close the latest follow-up entry if this was a follow-up run
                if t.mode == "follow_up" and t.follow_ups and t.follow_ups[-1].get("status") == "running":
                    t.follow_ups[-1]["status"] = "completed" if rc == 0 else "error"
                    t.follow_ups[-1]["ended_at"] = now_iso()
                t.updated_at = now_iso()
                self._save()
            self._emit(task_id, {"kind": "exit", "code": rc, "ts": now_iso()})
        finally:
            try:
                log_fp.close()
            except Exception:
                pass

    def _emit(self, task_id: str, ev: dict) -> None:
        # update task state for certain events
        t = self.tasks.get(task_id)
        if t is not None:
            if ev["kind"] == "progress":
                t.progress_passing = ev["passing"]
                t.progress_total = ev["total"]
            elif ev["kind"] == "session":
                # close prior session, open this one
                if t.sessions and not t.sessions[-1].get("ended_at"):
                    t.sessions[-1]["ended_at"] = ev["ts"]
                t.sessions.append({
                    "num": ev["session"],
                    "role": ev["role"],
                    "started_at": ev["ts"],
                    "ended_at": None,
                })
            elif ev["kind"] == "done":
                if t.sessions and not t.sessions[-1].get("ended_at"):
                    t.sessions[-1]["ended_at"] = ev["ts"]
            elif ev["kind"] == "error":
                t.last_error = ev.get("text")

        # append to events.jsonl so newly-connecting clients can replay
        try:
            with open(self.tasks[task_id].events_path(), "a") as f:
                f.write(json.dumps(ev) + "\n")
        except Exception:
            pass

        # fan out to live subscribers
        for q in list(self.subscribers.get(task_id, [])):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.subscribers.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        if task_id in self.subscribers and q in self.subscribers[task_id]:
            self.subscribers[task_id].remove(q)

    def replay_events(self, task_id: str) -> list[dict]:
        p = self.tasks[task_id].events_path()
        if not p.exists():
            return []
        out = []
        for line in p.read_text().splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return out

    def feature_list(self, task_id: str) -> list[dict]:
        p = self.tasks[task_id].project_dir() / "feature_list.json"
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return []


manager = TaskManager()
