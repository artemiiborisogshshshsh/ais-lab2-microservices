"""Инструментация HTTP-микросервисов."""

import os

from fastapi import FastAPI

from opentelemetry.instrumentation.fastapi import (
    FastAPIInstrumentor,
)
from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
)
from opentelemetry.sdk.trace import TracerProvider

from observability.tracing import create_tracer_provider


def setup_http_tracing(
    app: FastAPI,
    service_name: str,
    *,
    instrument_httpx: bool = False,
    provider: TracerProvider | None = None,
) -> TracerProvider | None:
    """Подключает распределённую HTTP-трассировку."""

    existing_provider = getattr(
        app.state,
        "tracer_provider",
        None,
    )

    if existing_provider is not None:
        return existing_provider

    if provider is None:
        enabled = os.getenv(
            "TRACING_ENABLED",
            "false",
        ).lower()

        if enabled not in ("true", "1"):
            return None

        provider = create_tracer_provider(
            service_name
        )

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls=r"/metrics$",
        exclude_spans=["receive", "send"],
    )

    if instrument_httpx:
        HTTPXClientInstrumentor().instrument(
            tracer_provider=provider,
        )

    app.state.tracer_provider = provider

    return provider
