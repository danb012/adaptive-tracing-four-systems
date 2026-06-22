from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.common.http import get_client
from services.common.tracing import init_tracing
from services.common.sampling import start_sampling_poller
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import os

AUTH_URL = os.getenv("AUTH_URL", "http://auth:8000")
USER_URL = os.getenv("USER_URL", "http://user:8000")
TRAVEL_URL = os.getenv("TRAVEL_URL", "http://travel:8000")
ORDER_URL = os.getenv("ORDER_URL", "http://order:8000")

app = FastAPI(title="ts-gateway-service")
FastAPIInstrumentor.instrument_app(app)


class LoginRequest(BaseModel):
    username: str
    password: str


class OrderRequest(BaseModel):
    user_id: int
    trip_id: str
    amount: float
    seat_type: str = "second_class"


@app.on_event("startup")
async def startup():
    init_tracing("ts-gateway-service")
    HTTPXClientInstrumentor().instrument()
    start_sampling_poller()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/login")
async def login(payload: LoginRequest):
    client = get_client()
    resp = await client.post(f"{AUTH_URL}/login", json=payload.dict())
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    client = get_client()
    resp = await client.get(f"{USER_URL}/users/{user_id}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.get("/travel/search")
async def search(from_station: str, to_station: str, date: str):
    client = get_client()
    resp = await client.get(
        f"{TRAVEL_URL}/travel/search",
        params={"from": from_station, "to": to_station, "date": date},
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.post("/orders")
async def create_order(payload: OrderRequest):
    client = get_client()
    resp = await client.post(f"{ORDER_URL}/orders", json=payload.dict())
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
