from fastapi import FastAPI, HTTPException, Query
from services.common.db import get_pool, init_schema
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

SCHEMA = "route"

DDL = [
    """
    CREATE TABLE IF NOT EXISTS routes (
        id SERIAL PRIMARY KEY,
        from_station TEXT NOT NULL,
        to_station TEXT NOT NULL,
        distance_km INT NOT NULL
    );
    """,
]


async def _seed(conn):
    await conn.execute(f'SET search_path TO "{SCHEMA}"')
    count = await conn.fetchval("SELECT COUNT(*) FROM routes")
    if count == 0:
        await conn.executemany(
            "INSERT INTO routes (from_station, to_station, distance_km) VALUES ($1, $2, $3)",
            [
                ("Shanghai", "Beijing", 1218),
                ("Beijing", "Tianjin", 120),
                ("Guangzhou", "Shenzhen", 140),
                ("Nanjing", "Shanghai", 300),
            ],
        )


app = FastAPI(title="ts-route-service")
FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup():
    init_tracing("ts-route-service")
    AsyncPGInstrumentor().instrument()
    await init_schema(SCHEMA, DDL, _seed)
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/routes")
async def get_route(
    from_station: str = Query(..., alias="from"),
    to_station: str = Query(..., alias="to"),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f'SET search_path TO "{SCHEMA}"')
        row = await conn.fetchrow(
            """
            SELECT id, from_station, to_station, distance_km
            FROM routes
            WHERE from_station=$1 AND to_station=$2
            """,
            from_station,
            to_station,
        )
        if not row:
            raise HTTPException(status_code=404, detail="route not found")
        return {
            "id": row["id"],
            "from_station": row["from_station"],
            "to_station": row["to_station"],
            "distance_km": row["distance_km"],
        }
