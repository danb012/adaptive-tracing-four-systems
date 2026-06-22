from fastapi import FastAPI
from pydantic import BaseModel, Field
from services.common.tracing import init_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI(title="sampling-config-service")
FastAPIInstrumentor.instrument_app(app)

_sampling_rate = 0.1


class SamplingConfig(BaseModel):
    rate: float = Field(..., ge=0.0, le=1.0)


@app.on_event("startup")
async def startup():
    init_tracing("sampling-config-service")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/sampling")
async def get_sampling():
    return {"rate": _sampling_rate}


@app.put("/sampling")
async def set_sampling(cfg: SamplingConfig):
    global _sampling_rate
    _sampling_rate = float(cfg.rate)
    return {"rate": _sampling_rate}
