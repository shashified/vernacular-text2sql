"""
Demo server: the review-panel website plus a small JSON API around explain_pipeline.

    python scripts/demo_server.py            # then open http://localhost:8000

The built website lives in web/dist (committed, so no Node.js is needed to run the demo).
Live mode uses the model configured in .env (Groq); saved mode needs no network at all.
"""
from __future__ import annotations

import os
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.demo import explain as ex

DIST = os.path.join(ex.ROOT, "web", "dist")


class NoCacheStatic(StaticFiles):
    async def get_response(self, path, scope):
        res = await super().get_response(path, scope)
        res.headers["Cache-Control"] = "no-cache"
        return res

app = FastAPI(title="Vernacular Text-to-SQL demo")
_llm = None
_llm_lock = threading.Lock()


def get_llm():
    global _llm
    with _llm_lock:
        if _llm is None:
            from src.generation.llm import APILLM
            env = os.environ.get("DEMO_ENV", os.path.join(ex.ROOT, ".env"))
            _llm = APILLM.from_env(env)
            _llm.max_retries = 2  # a live demo should fail fast, not wait minutes
        return _llm


class Ask(BaseModel):
    question: str
    mode: str = "replay"          # "replay" (saved run) or "live"
    id: str | None = None
    lang: str | None = None


@app.get("/api/examples")
def api_examples():
    return ex.examples()


@app.get("/api/benchmark")
def api_benchmark():
    return ex.benchmark_list()


@app.get("/api/stats")
def api_stats():
    return ex.stats()


@app.get("/api/schema")
def api_schema():
    return ex.schema_info()


@app.post("/api/ask")
def api_ask(body: Ask):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Type a question first.")
    if len(q) > 400:
        raise HTTPException(400, "Please keep the question under 400 characters.")
    bench = (body.id, body.lang) if body.id and body.lang else None
    try:
        llm = get_llm() if body.mode == "live" else None
        return ex.explain_pipeline(q, mode=body.mode, llm=llm, bench=bench)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001 - surface model/network problems to the UI
        raise HTTPException(502, f"The model could not be reached ({type(e).__name__}). Try saved mode.") from e


@app.post("/api/direct")
def api_direct(body: Ask):
    try:
        return ex.direct_live(body.question.strip(), get_llm())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"The model could not be reached ({type(e).__name__}).") from e


if os.path.isdir(DIST):
    app.mount("/assets", NoCacheStatic(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def site(path: str):
        target = os.path.join(DIST, path)
        # no-cache: the browser always re-checks, so a rebuilt site shows up on a normal refresh
        headers = {"Cache-Control": "no-cache"}
        if path and os.path.isfile(target):
            return FileResponse(target, headers=headers)
        return FileResponse(os.path.join(DIST, "index.html"), headers=headers)
