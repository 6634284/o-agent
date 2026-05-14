"""
FastAPI server exposing the TaskManager over HTTP + SSE.

Endpoints
    POST   /api/tasks                  create task
    GET    /api/tasks                  list
    GET    /api/tasks/{id}             detail
    PATCH  /api/tasks/{id}             edit
    DELETE /api/tasks/{id}             delete
    POST   /api/tasks/{id}/start       run
    POST   /api/tasks/{id}/stop        kill
    GET    /api/tasks/{id}/features    feature_list.json
    GET    /api/tasks/{id}/events      SSE stream (replay + live)
    GET    /api/models                 available model options
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from task_manager import manager, AVAILABLE_MODELS, DEFAULT_SPEC


app = FastAPI(title="o-agent web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskCreate(BaseModel):
    name: str = Field("", max_length=80)
    description: Optional[str] = None
    app_spec: Optional[str] = None
    model: str = "ppio/pa/claude-opus-4-7"
    max_iterations: Optional[int] = 3
    feature_count: int = 200
    fork_from_task_id: Optional[str] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    app_spec: Optional[str] = None
    model: Optional[str] = None
    max_iterations: Optional[int] = None
    feature_count: Optional[int] = None


class FollowUpRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_iterations: Optional[int] = 2
    expand: bool = False


@app.get("/api/models")
def models():
    return {"models": AVAILABLE_MODELS, "default_spec": DEFAULT_SPEC}


@app.get("/api/tasks")
def list_tasks():
    return manager.list_tasks()


@app.post("/api/tasks")
def create_task(body: TaskCreate):
    # Prefer NL description (auto-expanded via LLM). If forking with no new
    # description/spec, manager.create will inherit from the source. Only fall
    # back to DEFAULT_SPEC for the legacy case (no fork, no desc, no spec).
    desc = (body.description or "").strip()
    if body.app_spec:
        app_spec = body.app_spec
    elif desc or body.fork_from_task_id:
        app_spec = ""
    else:
        app_spec = DEFAULT_SPEC
    try:
        t = manager.create(
            name=body.name,
            app_spec=app_spec,
            model=body.model,
            max_iterations=body.max_iterations,
            feature_count=body.feature_count,
            description=desc,
            fork_from=body.fork_from_task_id,
        )
    except KeyError:
        raise HTTPException(404, f"fork source task {body.fork_from_task_id!r} not found")
    except (RuntimeError, ValueError) as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, f"create failed: {e}")
    return t.public_dict()


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    try:
        return manager.get(task_id).public_dict()
    except KeyError:
        raise HTTPException(404, "task not found")


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate):
    try:
        t = manager.update(task_id, **body.model_dump(exclude_none=True))
        return t.public_dict()
    except KeyError:
        raise HTTPException(404, "task not found")
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    try:
        manager.delete(task_id)
        return {"ok": True}
    except KeyError:
        raise HTTPException(404, "task not found")


@app.post("/api/tasks/{task_id}/start")
def start_task(task_id: str):
    try:
        return manager.start(task_id).public_dict()
    except KeyError:
        raise HTTPException(404, "task not found")


@app.post("/api/tasks/{task_id}/stop")
def stop_task(task_id: str):
    try:
        return manager.stop(task_id).public_dict()
    except KeyError:
        raise HTTPException(404, "task not found")


@app.post("/api/tasks/{task_id}/follow_up")
def follow_up_task(task_id: str, body: FollowUpRequest):
    """Run an incremental change on an already-built project — skips the initializer."""
    try:
        return manager.start_follow_up(
            task_id,
            follow_up_text=body.prompt,
            max_iterations=body.max_iterations,
            expand=body.expand,
        ).public_dict()
    except KeyError:
        raise HTTPException(404, "task not found")
    except (RuntimeError, ValueError) as e:
        raise HTTPException(409, str(e))


@app.get("/api/tasks/{task_id}/features")
def task_features(task_id: str):
    try:
        manager.get(task_id)
    except KeyError:
        raise HTTPException(404, "task not found")
    return manager.feature_list(task_id)


@app.get("/api/tasks/{task_id}/events")
async def task_events(task_id: str):
    try:
        manager.get(task_id)
    except KeyError:
        raise HTTPException(404, "task not found")

    async def gen():
        # replay first
        for ev in manager.replay_events(task_id):
            yield f"data: {json.dumps(ev)}\n\n"
        # then live
        q = manager.subscribe(task_id)
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            manager.unsubscribe(task_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=False)
