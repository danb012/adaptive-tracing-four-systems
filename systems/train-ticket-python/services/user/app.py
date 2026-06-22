from fastapi import FastAPI, HTTPException
from services.common.db import get_pool, init_schema
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

SCHEMA = "user"

DDL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL
    );
    """,
]


async def _seed(conn):
    await conn.execute(f'SET search_path TO "{SCHEMA}"')
    count = await conn.fetchval("SELECT COUNT(*) FROM users")
    if count == 0:
        await conn.execute(
            "INSERT INTO users (name, email) VALUES ($1, $2), ($3, $4)",
            "Alice",
            "alice@example.com",
            "Bob",
            "bob@example.com",
        )


app = FastAPI(title="ts-user-service")
FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup():
    init_tracing("ts-user-service")
    AsyncPGInstrumentor().instrument()
    await init_schema(SCHEMA, DDL, _seed)
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f'SET search_path TO "{SCHEMA}"')
        row = await conn.fetchrow(
            "SELECT id, name, email FROM users WHERE id=$1",
            user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        return {"id": row["id"], "name": row["name"], "email": row["email"]}
