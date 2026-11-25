from unittest.mock import patch

import pytest

from opentelemetry.context import Context
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)

from observability.tracing import create_tracer_provider


@pytest.fixture
def tracing():
    exporter = InMemorySpanExporter()

    provider = create_tracer_provider(
        "test-service",
        exporter=exporter,
    )

    try:
        yield provider, exporter
    finally:
        provider.shutdown()


def test_service_name(tracing):
    provider, exporter = tracing

    tracer = provider.get_tracer(__name__)

    with tracer.start_as_current_span("test_operation"):
        pass

    assert provider.force_flush()

    spans = exporter.get_finished_spans()

    assert len(spans) == 1
    assert (
        spans[0].resource.attributes["service.name"]
        == "test-service"
    )


def test_span_identifiers(tracing):
    provider, exporter = tracing

    tracer = provider.get_tracer(__name__)

    with tracer.start_as_current_span("test_operation"):
        pass

    assert provider.force_flush()

    span = exporter.get_finished_spans()[0]
    context = span.context

    assert context.is_valid

    trace_id = format(context.trace_id, "032x")
    span_id = format(context.span_id, "016x")

    assert len(trace_id) == 32
    assert len(span_id) == 16
    assert context.trace_id != 0
    assert context.span_id != 0


def test_parent_child_relationship(tracing):
    provider, exporter = tracing

    tracer = provider.get_tracer(__name__)

    with tracer.start_as_current_span("parent"):
        with tracer.start_as_current_span("child"):
            pass

    assert provider.force_flush()

    spans = {
        span.name: span
        for span in exporter.get_finished_spans()
    }

    parent = spans["parent"]
    child = spans["child"]

    assert (
        parent.context.trace_id
        == child.context.trace_id
    )

    assert (
        parent.context.span_id
        != child.context.span_id
    )

    assert (
        child.parent.span_id
        == parent.context.span_id
    )


def test_context_propagation_between_services():
    gateway_exporter = InMemorySpanExporter()
    order_exporter = InMemorySpanExporter()

    gateway_provider = create_tracer_provider(
        "api-gateway",
        exporter=gateway_exporter,
    )

    order_provider = create_tracer_provider(
        "order-service",
        exporter=order_exporter,
    )

    try:
        gateway_tracer = gateway_provider.get_tracer(
            __name__
        )

        order_tracer = order_provider.get_tracer(
            __name__
        )

        propagator = TraceContextTextMapPropagator()
        headers = {}

        with gateway_tracer.start_as_current_span(
            "gateway_request"
        ):
            propagator.inject(headers)

        assert "traceparent" in headers

        extracted_context = propagator.extract(
            headers,
            context=Context(),
        )

        with order_tracer.start_as_current_span(
            "create_order",
            context=extracted_context,
        ):
            pass

        assert gateway_provider.force_flush()
        assert order_provider.force_flush()

        gateway_span = (
            gateway_exporter.get_finished_spans()[0]
        )

        order_span = (
            order_exporter.get_finished_spans()[0]
        )

        assert (
            gateway_span.context.trace_id
            == order_span.context.trace_id
        )

        assert (
            order_span.parent.span_id
            == gateway_span.context.span_id
        )

        assert order_span.parent.is_remote

    finally:
        gateway_provider.shutdown()
        order_provider.shutdown()


def test_exception_is_recorded(tracing):
    provider, exporter = tracing

    tracer = provider.get_tracer(__name__)

    with pytest.raises(RuntimeError):
        with tracer.start_as_current_span("failed_operation"):
            raise RuntimeError("Test failure")

    assert provider.force_flush()

    span = exporter.get_finished_spans()[0]

    assert span.status.status_code == StatusCode.ERROR

    assert any(
        event.name == "exception"
        for event in span.events
    )


def test_exporter_endpoint_from_environment(monkeypatch):
    endpoint = "http://localhost:4318/v1/traces"

    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        endpoint,
    )

    exporter = InMemorySpanExporter()

    with patch(
        "observability.tracing.OTLPSpanExporter",
        return_value=exporter,
    ) as mock_exporter:

        provider = create_tracer_provider(
            "test-service"
        )

        try:
            mock_exporter.assert_called_once_with(
                endpoint=endpoint,
                timeout=5,
            )

        finally:
            provider.shutdown()
