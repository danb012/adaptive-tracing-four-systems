import asyncio
import os
from typing import Optional
import httpx
from opentelemetry.sdk.trace.sampling import Sampler, SamplingResult, Decision, TraceIdRatioBased
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState
from opentelemetry.context import Context

_sampling_rate = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))


def get_sampling_rate() -> float:
    return _sampling_rate


def set_sampling_rate(value: float) -> None:
    global _sampling_rate
    if value < 0.0:
        value = 0.0
    if value > 1.0:
        value = 1.0
    _sampling_rate = float(value)


class DynamicTraceIdRatioBased(Sampler):
    def __init__(self, rate_getter):
        self._rate_getter = rate_getter

    def should_sample(
        self,
        parent_context: Optional[Context],
        trace_id: int,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes=None,
        links=(),
        trace_state: Optional[TraceState] = None,
    ) -> SamplingResult:
        ratio = self._rate_getter()
        sampler = TraceIdRatioBased(ratio)
        return sampler.should_sample(
            parent_context,
            trace_id,
            name,
            kind,
            attributes,
            links,
            trace_state,
        )

    def get_description(self) -> str:
        return "DynamicTraceIdRatioBased"


async def _poll_sampling(url: str, interval: float) -> None:
    async with httpx.AsyncClient(timeout=2.0) as client:
        while True:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "rate" in data:
                        set_sampling_rate(float(data["rate"]))
            except httpx.HTTPError:
                pass
            await asyncio.sleep(interval)


def start_sampling_poller() -> None:
    url = os.getenv("SAMPLING_CONFIG_URL")
    if not url:
        return
    interval = float(os.getenv("SAMPLING_POLL_INTERVAL", "5"))
    asyncio.create_task(_poll_sampling(url, interval))
