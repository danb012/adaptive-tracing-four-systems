from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.common.db import get_pool, init_schema
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

SCHEMA = "seat"
DEFAULT_SEATS = 5000

DDL = [
    """
    CREATE TABLE IF NOT EXISTS seats (
        id SERIAL PRIMARY KEY,
        trip_id TEXT NOT NULL,
        seat_type TEXT NOT NULL,
        available INT NOT NULL,
        UNIQUE (trip_id, seat_type)
    );
    """,
]


app = FastAPI(title="ts-seat-service")
FastAPIInstrumentor.instrument_app(app)


class ReserveRequest(BaseModel):
    trip_id: str
    seat_type: str = "second_class"
    count: int = 1


@app.on_event("startup")
async def startup():
    init_tracing("ts-seat-service")
    AsyncPGInstrumentor().instrument()
    await init_schema(SCHEMA, DDL, None)
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _ensure_trip(conn, trip_id: str, seat_type: str):
    await conn.execute(f'SET search_path TO "{SCHEMA}"')
    row = await conn.fetchrow(
        "SELECT id, available FROM seats WHERE trip_id=$1 AND seat_type=$2",
        trip_id,
        seat_type,
    )
    if row:
        return row
    await conn.execute(
        "INSERT INTO seats (trip_id, seat_type, available) VALUES ($1, $2, $3)",
        trip_id,
        seat_type,
        DEFAULT_SEATS,
    )
    return await conn.fetchrow(
        "SELECT id, available FROM seats WHERE trip_id=$1 AND seat_type=$2",
        trip_id,
        seat_type,
    )


@app.get("/seats/availability")
async def availability(trip_id: str, seat_type: str = "second_class"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await _ensure_trip(conn, trip_id, seat_type)
        return {"trip_id": trip_id, "seat_type": seat_type, "available": row["available"]}


@app.post("/seats/reserve")
async def reserve(payload: ReserveRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _ensure_trip(conn, payload.trip_id, payload.seat_type)
            await conn.execute(f'SET search_path TO "{SCHEMA}"')
            available = await conn.fetchval(
                "SELECT available FROM seats WHERE trip_id=$1 AND seat_type=$2 FOR UPDATE",
                payload.trip_id,
                payload.seat_type,
            )
            if available < payload.count:
                raise HTTPException(status_code=409, detail="not enough seats")
            new_available = available - payload.count
            await conn.execute(
                "UPDATE seats SET available=$1 WHERE trip_id=$2 AND seat_type=$3",
                new_available,
                payload.trip_id,
                payload.seat_type,
            )
            return {
                "trip_id": payload.trip_id,
                "seat_type": payload.seat_type,
                "reserved": payload.count,
                "available": new_available,
            }
