from fastapi import FastAPI
from pydantic import BaseModel
from services.common.db import get_pool, init_schema
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
import asyncio

SCHEMA = "payment"

DDL = [
    """
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        order_id INT NOT NULL,
        amount NUMERIC NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
]


class PaymentRequest(BaseModel):
    order_id: int
    amount: float


app = FastAPI(title="ts-payment-service")
FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup():
    init_tracing("ts-payment-service")
    AsyncPGInstrumentor().instrument()
    await init_schema(SCHEMA, DDL, None)
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/payments/charge")
async def charge(payload: PaymentRequest):
    await asyncio.sleep(0.05)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f'SET search_path TO "{SCHEMA}"')
        await conn.execute(
            "INSERT INTO payments (order_id, amount, status) VALUES ($1, $2, $3)",
            payload.order_id,
            payload.amount,
            "paid",
        )
    return {"status": "paid", "transaction_id": f"tx-{payload.order_id}"}
