"""The demo web app: a dashboard of one run, and the decisions that move it.

Server-rendered on purpose. Statuses and the readiness verdict are derived
on every read, so every page load shows what the engine says right now —
there is no client-side copy that could show a stale verdict after a
decision.

Handlers are plain ``def`` (FastAPI runs them in a threadpool) and share
one lock: DuckDB and the file store are not built for two writers.
"""

import threading
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from before_we_ai.core.objects import Scope
from before_we_ai.readiness import (
    confirm_classification,
    require_again,
    waive_item,
)
from before_we_ai.statements import (
    answer_question,
    confirm_claim,
    defer_question,
    pick_up_question,
)
from readiness_report.render import write_project_view

from ui import pipeline, views

HERE = Path(__file__).resolve().parent
LOCK = threading.Lock()

app = FastAPI(title="before-we-ai demo", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


def _store():
    return pipeline.store() if pipeline.exists() else None


def _page(request: Request, name: str, **context) -> HTMLResponse:
    with LOCK:
        s = _store()
        base = views.overview(s)
        extra = {key: build(s) if callable(build) else build
                 for key, build in context.items()}
    return templates.TemplateResponse(request, f"{name}.html", {
        "page": name,
        "o": base,
        "notice": request.query_params.get("notice", ""),
        "refused": request.query_params.get("refused", ""),
        **extra,
    })


def _back(request: Request, fallback: str, *, notice: str = "",
          refused: str = "") -> RedirectResponse:
    # back to the page the act came from, keeping only which tab was open
    referer = urlsplit(request.headers.get("referer") or fallback)
    params = {key: value for key, value in parse_qsl(referer.query)
              if key in ("tab", "status")}
    if notice:
        params["notice"] = notice
    elif refused:
        params["refused"] = refused
    target = referer.path + (f"?{urlencode(params)}" if params else "")
    return RedirectResponse(target, status_code=303)


def _act(request: Request, fallback: str, notice: str, action) -> RedirectResponse:
    """Run one human act. A refusal from the engine is shown word for word:
    the reasons it refuses are the product."""
    try:
        with LOCK:
            action()
    except Exception as exc:  # noqa: BLE001 — every refusal is shown, none hidden
        return _back(request, fallback, refused=str(exc))
    return _back(request, fallback, notice=notice)


# ---------------------------------------------------------------- pages


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    return _page(request, "overview")


@app.get("/run", response_class=HTMLResponse)
def run(request: Request):
    return _page(request, "run")


@app.get("/sources", response_class=HTMLResponse)
def sources(request: Request):
    return _page(request, "sources",
                 sources=lambda s: views.sources(s) if s else [])


@app.get("/knowledge", response_class=HTMLResponse)
def knowledge(request: Request):
    return _page(request, "knowledge",
                 claims=lambda s: views.claims(s) if s else [],
                 only=request.query_params.get("status", ""))


@app.get("/decisions", response_class=HTMLResponse)
def decisions(request: Request):
    def findings(s):
        if s is None:
            return []
        ready = views.readiness(s) if s.requests else None
        return views.findings(s, ready)
    return _page(request, "decisions", findings=findings,
                 tab=request.query_params.get("tab", "blocking"))


@app.get("/readiness", response_class=HTMLResponse)
def readiness(request: Request):
    return _page(request, "readiness")


@app.get("/foundation", response_class=HTMLResponse)
def foundation(request: Request):
    def result(s):
        f = pipeline.foundation_result() if s else None
        if f:
            counts = {}
            for rule in f["rules"]:
                counts[rule["state"]] = counts.get(rule["state"], 0) + 1
            f["counts"] = counts
            f["settled"] = sorted({r for rule in f["rules"]
                                   for r in rule["settled"]})
        return f
    return _page(request, "foundation", f=result,
                 available=lambda s: bool(s) and pipeline.foundation_available())


@app.post("/apply-foundation")
def apply_foundation(request: Request):
    return _act(request, "/foundation",
                "The document was read and its rules measured. Statuses "
                "and the verdict were re-derived.",
                pipeline.apply_foundation)


@app.get("/report", response_class=HTMLResponse)
def report():
    """The full audit report — the existing readiness report, unchanged."""
    if not pipeline.exists():
        return RedirectResponse("/run", status_code=303)
    with LOCK:
        path = write_project_view(pipeline.project_dir(),
                                  pipeline.workdir() / "report.html")
    return HTMLResponse(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the run


@app.post("/api/run/{key}")
def run_step(key: str):
    try:
        with LOCK:
            summary = pipeline.run_step(key)
            upcoming = pipeline.next_step()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return {"ok": True, "summary": summary,
            "next": upcoming.key if upcoming else ""}


@app.post("/api/load")
def load_recorded():
    """Load the store a live run left behind, re-judged by today's engine."""
    try:
        with LOCK:
            pipeline.load_recorded()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return {"ok": True}


@app.post("/landscape")
def choose_landscape(name: str = Form(...)):
    with LOCK:
        pipeline.set_active(name)
    return RedirectResponse("/", status_code=303)


@app.post("/reset")
def reset():
    with LOCK:
        pipeline.reset()
    return RedirectResponse("/run", status_code=303)


# ---------------------------------------------------------------- human acts


def _scope(entity: str, period: str) -> Scope | None:
    entity, period = entity.strip(), period.strip()
    if not entity and not period:
        return None
    return Scope(entity=entity or None, period=period or None)


@app.post("/decide")
def decide(request: Request, claim_id: str = Form(...), card_id: str = Form(""),
           entity: str = Form(""), period: str = Form("")):
    """A person says which candidate is right, or that a rule holds."""
    def action():
        s = pipeline.store()
        scope = _scope(entity, period)
        if card_id:
            answer_question(s, card_id, pick=claim_id, scope=scope,
                            note="decided in the demo UI")
        else:
            confirm_claim(s, claim_id, scope=scope,
                          note="decided in the demo UI")
    return _act(request, "/decisions", "Recorded. The verdict was re-derived.",
                action)


@app.post("/waive")
def waive(request: Request, ref: str = Form(...), reason: str = Form("")):
    def action():
        if not reason.strip():
            raise ValueError(
                "A waiver needs a reason: it is the only trace of why this "
                "dependency was set aside.")
        s = pipeline.store()
        waive_item(s, pipeline.guide(), views._request(s).id, ref,
                   reason.strip())
    return _act(request, "/decisions",
                f"'{ref}' was waived. It stays visible on the readiness page.",
                action)


@app.post("/require")
def require(request: Request, ref: str = Form(...)):
    def action():
        s = pipeline.store()
        require_again(s, pipeline.guide(), views._request(s).id, ref)
    return _act(request, "/readiness", f"'{ref}' is required again.", action)


@app.post("/confirm-list")
def confirm_list(request: Request):
    def action():
        s = pipeline.store()
        confirm_classification(s, pipeline.guide(), views._request(s).id)
    return _act(request, "/readiness",
                "You vouched for the dependency list.", action)


@app.post("/defer")
def defer(request: Request, card_id: str = Form(...)):
    def action():
        defer_question(pipeline.store(), card_id,
                       note="deferred in the demo UI")
    return _act(request, "/decisions?tab=findings",
                "Deferred. It moves down the list and unblocks nothing.",
                action)


@app.post("/pickup")
def pickup(request: Request, card_id: str = Form(...)):
    def action():
        pick_up_question(pipeline.store(), card_id)
    return _act(request, "/decisions?tab=findings", "Picked up again.", action)
