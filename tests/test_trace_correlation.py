import io
import json
import logging

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pika
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opentelemetry.trace import SpanKind, StatusCode
from opentelemetry.instrumentation.fastapi import (
    FastAPIInstrumentor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from observability.logging import JsonFormatter
from observability.tracing import create_tracer_provider
from observability.http_logging import setup_http_logging
from observability.http_tracing import setup_http_tracing

from observability import messaging_tracing as messaging

from order_service import main as order_api
from order_service.models import OrderCreate

from payment_service import main as payment
from notification_service import main as notification


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


def create_record():
    return logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )


def test_log_uses_active_span(tracing):
    provider, exporter = tracing

    tracer = provider.get_tracer(__name__)

    formatter = JsonFormatter("test-service")

    with tracer.start_as_current_span("test") as span:

        context = span.get_span_context()

        record = create_record()

        # Проверяем приоритет активного контекста.
        record.trace_id = "a" * 32
        record.span_id = "b" * 16

        result = json.loads(
            formatter.format(record)
        )

        assert result["trace_id"] == format(
            context.trace_id,
            "032x",
        )

        assert result["span_id"] == format(
            context.span_id,
            "016x",
        )


def test_log_context_not_leaked(tracing):
    provider, exporter = tracing

    tracer = provider.get_tracer(__name__)

    formatter = JsonFormatter("test-service")

    with tracer.start_as_current_span("test"):

        active_log = json.loads(
            formatter.format(create_record())
        )

        assert active_log["trace_id"] is not None
        assert active_log["span_id"] is not None

    outside_log = json.loads(
        formatter.format(create_record())
    )

    assert outside_log["trace_id"] is None
    assert outside_log["span_id"] is None


def test_http_log_matches_server_span(
    tracing,
    capsys,
):
    provider, exporter = tracing

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    setup_http_logging(
        app,
        "test-service",
    )

    setup_http_tracing(
        app,
        "test-service",
        provider=provider,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200

        assert provider.force_flush()

        span = next(
            span
            for span in exporter.get_finished_spans()
            if span.kind == SpanKind.SERVER
        )

        logs = [
            json.loads(line)
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("{")
        ]

        log = next(
            log
            for log in logs
            if log["message"] == "HTTP request completed"
        )

        assert log["trace_id"] == format(
            span.context.trace_id,
            "032x",
        )

        assert log["span_id"] == format(
            span.context.span_id,
            "016x",
        )

    finally:
        FastAPIInstrumentor.uninstrument_app(app)


@pytest.mark.parametrize(
    "simulate_failure, expected_result, expected_status",
    [
        (False, "completed", StatusCode.UNSET),
        (True, "failed", StatusCode.ERROR),
    ],
)
def test_payment_business_span(
    tracing,
    monkeypatch,
    simulate_failure,
    expected_result,
    expected_status,
):
    provider, exporter = tracing

    monkeypatch.setattr(
        messaging,
        "_tracer",
        provider.get_tracer(__name__),
    )

    channel = Mock()
    method = Mock(delivery_tag=1)

    body = json.dumps({
        "event": "OrderCreated",
        "orderId": "test-order-1",
        "simulate_failure": simulate_failure,
    }).encode()

    stream = io.StringIO()

    with patch.object(
        payment.logger.handlers[0],
        "stream",
        stream,
    ):
        payment.process_order(
            channel,
            method,
            None,
            body,
        )

    assert provider.force_flush()

    span = next(
        span
        for span in exporter.get_finished_spans()
        if span.name == "process_payment"
    )

    assert span.status.status_code == expected_status

    assert (
        span.attributes["order.id"]
        == "test-order-1"
    )

    assert (
        span.attributes["payment.result"]
        == expected_result
    )

    logs = [
        json.loads(line)
        for line in stream.getvalue().splitlines()
    ]

    assert len(logs) == 2

    for log in logs:

        assert log["trace_id"] == format(
            span.context.trace_id,
            "032x",
        )

        assert log["span_id"] == format(
            span.context.span_id,
            "016x",
        )

    channel.basic_ack.assert_called_once_with(
        delivery_tag=1,
    )


@pytest.mark.parametrize(
    "event_name",
    ["PaymentCompleted", "OrderCancelled"],
)
def test_notification_business_span(
    tracing,
    monkeypatch,
    event_name,
):
    provider, exporter = tracing

    monkeypatch.setattr(
        messaging,
        "_tracer",
        provider.get_tracer(__name__),
    )

    channel = Mock()
    method = Mock(delivery_tag=2)

    body = json.dumps({
        "event": event_name,
        "orderId": "test-order-2",
    }).encode()

    stream = io.StringIO()

    with patch.object(
        notification.logger.handlers[0],
        "stream",
        stream,
    ):
        notification.process_notification(
            channel,
            method,
            None,
            body,
        )

    assert provider.force_flush()

    span = exporter.get_finished_spans()[0]

    assert span.name == "send_notification"

    assert span.status.status_code == StatusCode.UNSET

    assert (
        span.attributes["order.id"]
        == "test-order-2"
    )

    assert (
        span.attributes["notification.event"]
        == event_name
    )

    log = json.loads(
        stream.getvalue().strip()
    )

    assert log["trace_id"] == format(
        span.context.trace_id,
        "032x",
    )

    assert log["span_id"] == format(
        span.context.span_id,
        "016x",
    )

    channel.basic_ack.assert_called_once_with(
        delivery_tag=2,
    )


def test_create_order_business_span(
    tracing,
    monkeypatch,
):
    provider, exporter = tracing

    tracer = provider.get_tracer(__name__)

    monkeypatch.setattr(
        order_api,
        "tracer",
        tracer,
    )

    monkeypatch.setattr(
        messaging,
        "_tracer",
        tracer,
    )

    order = SimpleNamespace(
        id="test-order-3",
    )

    monkeypatch.setattr(
        order_api,
        "create_order",
        Mock(return_value=order),
    )

    channel = Mock()

    def publish(order, simulate_failure=False):
        messaging.publish_event(
            channel,
            exchange="lab4.events",
            routing_key="order.created",
            body=b"test-message",
        )

    monkeypatch.setattr(
        order_api,
        "publish_order_created",
        publish,
    )

    data = OrderCreate(
        userId="test-user",
        items=[
            {
                "productId": "test-product",
                "quantity": 1,
            }
        ],
        totalAmount=1500,
    )

    stream = io.StringIO()

    with patch.object(
        order_api.logger.handlers[0],
        "stream",
        stream,
    ):
        with tracer.start_as_current_span(
            "http_request"
        ) as parent:

            parent_context = parent.get_span_context()

            result = order_api.create_new_order(
                data,
                {
                    "user_id": "test-user",
                    "role": "user",
                },
            )

    assert result is order

    assert provider.force_flush()

    spans = exporter.get_finished_spans()

    business_span = next(
        span
        for span in spans
        if span.name == "create_order"
    )

    producer_span = next(
        span
        for span in spans
        if span.kind == SpanKind.PRODUCER
    )

    assert (
        business_span.parent.span_id
        == parent_context.span_id
    )

    assert (
        producer_span.parent.span_id
        == business_span.context.span_id
    )

    assert (
        business_span.attributes["order.id"]
        == "test-order-3"
    )

    assert (
        business_span.attributes["order.total_amount"]
        == 1500
    )

    assert (
        business_span.attributes["order.items_count"]
        == 1
    )

    log = json.loads(
        stream.getvalue().strip()
    )

    assert log["trace_id"] == format(
        business_span.context.trace_id,
        "032x",
    )

    assert log["span_id"] == format(
        business_span.context.span_id,
        "016x",
    )
