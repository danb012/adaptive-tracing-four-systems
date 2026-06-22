from fastapi import FastAPI, HTTPException, Query
from services.common.db import init_schema
from services.common.http import get_client
from services.common.tracing import init_tracing
from services.common.faults import maybe_delay, should_error
from services.common.sampling import start_sampling_poller
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
import os

SCHEMA = "travel"

DDL = [
    """
    CREATE TABLE IF NOT EXISTS search_logs (
        id SERIAL PRIMARY KEY,
        from_station TEXT NOT NULL,
        to_station TEXT NOT NULL,
        travel_date TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
]

ROUTE_URL = os.getenv("ROUTE_URL", "http://route:8000")
SEAT_URL = os.getenv("SEAT_URL", "http://seat:8000")

app = FastAPI(title="ts-travel-service")
FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup():
    init_tracing("ts-travel-service")
    AsyncPGInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    await init_schema(SCHEMA, DDL, None)
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/travel/search")
async def search(
    from_station: str = Query(..., alias="from"),
    to_station: str = Query(..., alias="to"),
    date: str = "2026-01-28",
):
    await maybe_delay("TRAVEL")
    if should_error("TRAVEL"):
        raise HTTPException(status_code=503, detail="injected travel error")
    client = get_client()
    route_resp = await client.get(
        f"{ROUTE_URL}/routes",
        params={"from": from_station, "to": to_station},
    )
    if route_resp.status_code != 200:
        raise HTTPException(status_code=404, detail="route not found")
    route = route_resp.json()
    trip_id = f"{route['id']}:{date}"

    seat_resp = await client.get(
        f"{SEAT_URL}/seats/availability",
        params={"trip_id": trip_id, "seat_type": "second_class"},
    )
    seat = seat_resp.json()

    price = round(route["distance_km"] * 0.5, 2)

    return {
        "trips": [
            {
                "trip_id": trip_id,
                "from_station": route["from_station"],
                "to_station": route["to_station"],
                "date": date,
                "available": seat["available"],
                "price": price,
            }
        ]
    }
