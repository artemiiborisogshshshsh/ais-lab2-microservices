import httpx
import pytest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import (
    FastAPIInstrumentor,
)
from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode

from observability.tracing import create_tracer_provider
from observability.http_tracing import setup_http_tracing


@pytest.fixture
def traced_app():
    exporter = InMemorySpanExporter()

    provider = create_tracer_provider(
        "http-test-service",
        exporter=exporter,
    )

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/products/{product_id}")
    def product(product_id: str):
        return {"id": product_id}

    @app.get("/metrics")
    def metrics():
        return {"metrics": True}

    @app.get("/error")
    def error():
        raise HTTPException(
            status_code=500,
            detail="Test error",
        )

    setup_http_tracing(
        app,
        "http-test-service",
        provider=provider,
    )

    try:
        with TestClient(app) as client:
            yield client, provider, exporter

    finally:
        FastAPIInstrumentor.uninstrument_app(app)
        provider.shutdown()


def get_server_spans(provider, exporter):
    assert provider.force_flush()

    return [
        span
        for span in exporter.get_finished_spans()
        if span.kind == SpanKind.SERVER
    ]


def test_http_server_span(traced_app):
    client, provider, exporter = traced_app

    response = client.get("/health")

    assert response.status_code == 200

    spans = get_server_spans(provider, exporter)

    assert len(spans) == 1
    assert spans[0].name == "GET /health"

    assert (
        spans[0].resource.attributes["service.name"]
        == "http-test-service"
    )


def test_route_template(traced_app):
    client, provider, exporter = traced_app

    response = client.get("/products/product-123")

    assert response.status_code == 200

    spans = get_server_spans(provider, exporter)

    assert len(spans) == 1

    assert (
        spans[0].name
        == "GET /products/{product_id}"
    )


def test_metrics_are_excluded(traced_app):
    client, provider, exporter = traced_app

    response = client.get("/metrics")

    assert response.status_code == 200

    assert provider.force_flush()

    assert len(exporter.get_finished_spans()) == 0


def test_incoming_trace_context(traced_app):
    client, provider, exporter = traced_app

    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_id = "00f067aa0ba902b7"

    response = client.get(
        "/health",
        headers={
            "traceparent": (
                f"00-{trace_id}-{parent_id}-01"
            ),
        },
    )

    assert response.status_code == 200

    span = get_server_spans(
        provider,
        exporter,
    )[0]

    assert format(span.context.trace_id, "032x") == trace_id
    assert format(span.parent.span_id, "016x") == parent_id

    assert span.parent.is_remote


def test_http_error_span(traced_app):
    client, provider, exporter = traced_app

    response = client.get("/error")

    assert response.status_code == 500

    span = get_server_spans(
        provider,
        exporter,
    )[0]

    assert span.status.status_code == StatusCode.ERROR


def test_tracing_disabled(monkeypatch):
    monkeypatch.setenv(
        "TRACING_ENABLED",
        "false",
    )

    app = FastAPI()

    result = setup_http_tracing(
        app,
        "disabled-service",
    )

    assert result is None

    assert getattr(
        app.state,
        "tracer_provider",
        None,
    ) is None


def test_httpx_context_propagation():
    exporter = InMemorySpanExporter()

    provider = create_tracer_provider(
        "test-gateway",
        exporter=exporter,
    )

    tracer = provider.get_tracer(__name__)

    received_headers = {}

    def upstream(request):
        received_headers.update(request.headers)

        return httpx.Response(
            200,
            json={"status": "ok"},
        )

    instrumentor = HTTPXClientInstrumentor()

    try:
        transport = httpx.MockTransport(upstream)

        with httpx.Client(
            transport=transport,
        ) as client:

            instrumentor.instrument_client(
                client,
                tracer_provider=provider,
            )

            try:
                with tracer.start_as_current_span(
                    "gateway_request"
                ) as parent:

                    parent_context = (
                        parent.get_span_context()
                    )

                    response = client.get(
                        "http://order-service/orders"
                    )

                assert response.status_code == 200

            finally:
                instrumentor.uninstrument_client(client)

        assert provider.force_flush()

        spans = exporter.get_finished_spans()

        client_spans = [
            span for span in spans
            if span.kind == SpanKind.CLIENT
        ]

        assert len(client_spans) == 1

        client_span = client_spans[0]

        assert (
            client_span.context.trace_id
            == parent_context.trace_id
        )

        assert (
            client_span.parent.span_id
            == parent_context.span_id
        )

        assert "traceparent" in received_headers

        _, trace_id, span_id, flags = (
            received_headers["traceparent"].split("-")
        )

        assert trace_id == format(
            client_span.context.trace_id,
            "032x",
        )

        assert span_id == format(
            client_span.context.span_id,
            "016x",
        )

        assert (int(flags, 16) & 0x01) == 0x01

    finally:
        provider.shutdown()


def test_api_gateway_application_import(monkeypatch):
    monkeypatch.setenv("TRACING_ENABLED", "false")

    from api_gateway.main import app

    assert isinstance(app, FastAPI)

    assert any(
        route.path == "/health"
        for route in app.routes
    )