from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.common.db import get_pool, init_schema
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

SCHEMA = "auth"

DDL = [
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """,
]


async def _seed(conn):
    await conn.execute(f'SET search_path TO "{SCHEMA}"')
    count = await conn.fetchval("SELECT COUNT(*) FROM accounts")
    if count == 0:
        await conn.execute(
            "INSERT INTO accounts (username, password) VALUES ($1, $2), ($3, $4)",
            "alice",
            "password",
            "bob",
            "password",
        )


app = FastAPI(title="ts-auth-service")
FastAPIInstrumentor.instrument_app(app)


class LoginRequest(BaseModel):
    username: str
    password: str


@app.on_event("startup")
async def startup():
    init_tracing("ts-auth-service")
    AsyncPGInstrumentor().instrument()
    await init_schema(SCHEMA, DDL, _seed)
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/login")
async def login(payload: LoginRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f'SET search_path TO "{SCHEMA}"')
        row = await conn.fetchrow(
            "SELECT id, username FROM accounts WHERE username=$1 AND password=$2",
            payload.username,
            payload.password,
        )
        if not row:
            raise HTTPException(status_code=401, detail="invalid credentials")
        return {"token": f"token-{row['username']}", "user_id": row["id"]}
