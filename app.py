"""FastAPI web app: type a company name -> tagged market-research report.

Run:  ./run.sh   (or: uvicorn app:app --reload, from the project root, venv active)
Then: http://127.0.0.1:8077

Two research paths share one pipeline:
- GET  /research/stream  -> Server-Sent Events with live progress (used by the UI)
- POST /research         -> plain blocking render (no-JS fallback)
"""
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from agent import config, pipeline

app = FastAPI(title="Market Research Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def _render_report(report: dict) -> str:
    """Render the report partial to an HTML string (for the SSE payload)."""
    return templates.env.get_template("report_partial.html").render(report=report)


def _sse(event: str, data: str) -> str:
    """Format one Server-Sent Event. Multi-line data needs a `data:` per line."""
    body = "".join(f"data: {line}\n" for line in data.split("\n"))
    return f"event: {event}\n{body}\n"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "missing_keys": config.missing_keys()},
    )


@app.get("/research/stream")
async def research_stream(company: str = ""):
    company = company.strip()

    async def gen():
        if not company:
            yield _sse("error", "Enter a company name.")
            return
        missing = config.missing_keys()
        if missing:
            yield _sse("error", f"Missing API keys: {', '.join(missing)}. Add them to .env.")
            return
        try:
            async for kind, payload in pipeline.run_events(company):
                if kind == "status":
                    yield _sse("status", payload)
                elif kind == "result":
                    yield _sse("result", _render_report(payload))
        except Exception as exc:  # readable error instead of a dropped stream
            yield _sse("error", f"Research failed — {type(exc).__name__}: {exc}")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/research", response_class=HTMLResponse)
async def research(request: Request, company: str = Form(...)):
    """No-JS fallback: blocking render of the full report page."""
    company = company.strip()
    if not company:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "missing_keys": config.missing_keys(),
             "error": "Enter a company name."},
        )
    missing = config.missing_keys()
    if missing:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "missing_keys": missing,
             "error": f"Missing API keys: {', '.join(missing)}. Add them to .env."},
        )
    try:
        report = await pipeline.run(company)
    except Exception as exc:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "missing_keys": [],
             "error": f"Research failed — {type(exc).__name__}: {exc}"},
        )
    return templates.TemplateResponse(
        "report.html",
        {"request": request, "report": report},
    )
