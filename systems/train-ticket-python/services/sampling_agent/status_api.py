from fastapi import FastAPI
import json
import os
from services.common.tracing import init_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

STATUS_PATH = os.getenv("AGENT_STATUS_PATH", "/tmp/agent_status.json")
SUMMARY_PATH = os.getenv("AGENT_SUMMARY_PATH", "/tmp/agent_summary.json")
DECISION_LOG_PATH = os.getenv("AGENT_DECISION_LOG", "/tmp/agent_decisions.jsonl")

app = FastAPI(title="sampling-agent-status")
FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup():
    init_tracing("sampling-agent-status")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def status():
    if not os.path.exists(STATUS_PATH):
        return {"status": "no-data"}
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError:
        return {"status": "error"}


@app.get("/summary")
async def summary():
    if not os.path.exists(SUMMARY_PATH):
        return {"status": "no-data"}
    try:
        with open(SUMMARY_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError:
        return {"status": "error"}


@app.get("/decisions")
async def decisions(limit: int = 20):
    if not os.path.exists(DECISION_LOG_PATH):
        return {"status": "no-data", "items": []}

    limit = max(1, min(limit, 200))
    try:
        with open(DECISION_LOG_PATH, "r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
    except OSError:
        return {"status": "error", "items": []}

    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return {"status": "ok", "items": items}
