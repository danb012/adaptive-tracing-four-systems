import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    TraceIdRatioBased,
)
from services.common.sampling import DynamicTraceIdRatioBased, get_sampling_rate


def _build_sampler():
    sampler = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio").lower()
    arg = os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1")
    if sampler in {"always_on", "alwayson"}:
        return ALWAYS_ON
    if sampler in {"always_off", "alwaysoff"}:
        return ALWAYS_OFF
    if sampler in {"traceidratio", "traceidratiobased"}:
        try:
            ratio = float(arg)
        except ValueError:
            ratio = 0.1
        return TraceIdRatioBased(ratio)
    if sampler in {"dynamic", "parentbased_dynamic"}:
        return ParentBased(DynamicTraceIdRatioBased(get_sampling_rate))
    try:
        ratio = float(arg)
    except ValueError:
        ratio = 0.1
    return ParentBased(DynamicTraceIdRatioBased(get_sampling_rate))


def init_tracing(service_name: str) -> None:
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        return

    resource = Resource.create({"service.name": service_name})
    tracer_provider = TracerProvider(resource=resource, sampler=_build_sampler())

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)

    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)
