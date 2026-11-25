"""Общий модуль распределённой трассировки."""

import os

from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    ParentBased,
)


DEFAULT_OTLP_ENDPOINT = "http://jaeger:4318/v1/traces"


def create_tracer_provider(
    service_name: str,
    endpoint: str | None = None,
    *,
    exporter: SpanExporter | None = None,
) -> TracerProvider:
    """Создаёт настроенный TracerProvider."""

    resource = Resource(
        attributes={
            "service.name": service_name,
        },
    )

    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(ALWAYS_ON),
    )

    if exporter is None:
        endpoint = endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            DEFAULT_OTLP_ENDPOINT,
        )

        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            timeout=5,
        )

    processor = BatchSpanProcessor(
        exporter,
        schedule_delay_millis=1000,
    )

    provider.add_span_processor(processor)

    return provider
