from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.common.db import get_pool, init_schema
from services.common.http import get_client
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller
from services.common.faults import maybe_delay, should_error
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
import os
import asyncio
import time

SCHEMA = "order"
SEAT_URL = os.getenv("SEAT_URL", "http://seat:8000")
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment:8000")

DDL = [
    """
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL,
        trip_id TEXT NOT NULL,
        amount NUMERIC NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
]


class OrderRequest(BaseModel):
    user_id: int
    trip_id: str
    amount: float
    seat_type: str = "second_class"


app = FastAPI(title="ts-order-service")
FastAPIInstrumentor.instrument_app(app)

_stats_lock = asyncio.Lock()
_stats = {
    "total": 0,
    "errors": 0,
    "latency_ms_total": 0.0,
    "latency_ms_count": 0,
    "window_total": 0,
    "window_start": time.monotonic(),
}


@app.on_event("startup")
async def startup():
    init_tracing("ts-order-service")
    AsyncPGInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    await init_schema(SCHEMA, DDL, None)
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _record(success: bool, latency_ms: float) -> None:
    async with _stats_lock:
        _stats["total"] += 1
        if not success:
            _stats["errors"] += 1
        _stats["latency_ms_total"] += latency_ms
        _stats["latency_ms_count"] += 1
        _stats["window_total"] += 1


@app.get("/stats")
async def stats():
    async with _stats_lock:
        total = _stats["total"]
        errors = _stats["errors"]
        latency_total = _stats["latency_ms_total"]
        latency_count = _stats["latency_ms_count"]
        window_total = _stats["window_total"]
        window_start = _stats["window_start"]

        now = time.monotonic()
        window_seconds = max(now - window_start, 0.001)
        qps = window_total / window_seconds

        _stats["window_total"] = 0
        _stats["window_start"] = now

    error_rate = (errors / total) if total else 0.0
    avg_latency_ms = (latency_total / latency_count) if latency_count else 0.0
    return {
        "total": total,
        "errors": errors,
        "error_rate": error_rate,
        "avg_latency_ms": avg_latency_ms,
        "qps": qps,
    }


@app.post("/orders")
async def create_order(payload: OrderRequest):
    await maybe_delay("ORDER")
    if should_error("ORDER"):
        raise HTTPException(status_code=503, detail="injected order error")
    start = time.monotonic()
    client = get_client()

    reserve_resp = await client.post(
        f"{SEAT_URL}/seats/reserve",
        json={
            "trip_id": payload.trip_id,
            "seat_type": payload.seat_type,
            "count": 1,
        },
    )
    if reserve_resp.status_code != 200:
        latency_ms = (time.monotonic() - start) * 1000
        await _record(False, latency_ms)
        raise HTTPException(status_code=409, detail="seat reservation failed")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f'SET search_path TO "{SCHEMA}"')
        order_id = await conn.fetchval(
            """
            INSERT INTO orders (user_id, trip_id, amount, status)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            payload.user_id,
            payload.trip_id,
            payload.amount,
            "pending",
        )

    payment_resp = await client.post(
        f"{PAYMENT_URL}/payments/charge",
        json={"order_id": order_id, "amount": payload.amount},
    )
    if payment_resp.status_code != 200:
        status = "failed"
    else:
        status = payment_resp.json().get("status", "paid")

    async with pool.acquire() as conn:
        await conn.execute(f'SET search_path TO "{SCHEMA}"')
        await conn.execute(
            "UPDATE orders SET status=$1 WHERE id=$2",
            status,
            order_id,
        )

    latency_ms = (time.monotonic() - start) * 1000
    await _record(status == "paid", latency_ms)
    return {"order_id": order_id, "status": status}
