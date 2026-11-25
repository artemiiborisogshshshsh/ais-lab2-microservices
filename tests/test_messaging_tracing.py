import json
from unittest.mock import Mock

import pika
import pytest

from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from observability.tracing import create_tracer_provider
from observability import messaging_tracing as messaging

from payment_service.main import process_order
from notification_service.main import process_notification


@pytest.fixture
def make_provider(monkeypatch):
    providers = []

    monkeypatch.setattr(
        messaging,
        "_tracer",
        None,
    )

    def factory(service_name):
        exporter = InMemorySpanExporter()

        provider = create_tracer_provider(
            service_name,
            exporter=exporter,
        )

        providers.append(provider)

        return provider, exporter

    try:
        yield factory

    finally:
        messaging.configure_messaging_tracing(None)

        for provider in providers:
            provider.shutdown()


def test_publish_propagates_context(make_provider):
    provider, exporter = make_provider("order-service")

    messaging.configure_messaging_tracing(provider)

    tracer = provider.get_tracer(__name__)

    channel = Mock()

    with tracer.start_as_current_span("parent") as parent:

        parent_context = parent.get_span_context()

        messaging.publish_event(
            channel,
            exchange="lab4.events",
            routing_key="order.created",
            body=b'{"event":"OrderCreated"}',
        )

    assert provider.force_flush()

    spans = exporter.get_finished_spans()

    producer = next(
        span for span in spans
        if span.kind == SpanKind.PRODUCER
    )

    assert (
        producer.context.trace_id
        == parent_context.trace_id
    )

    assert (
        producer.parent.span_id
        == parent_context.span_id
    )

    published = channel.basic_publish.call_args.kwargs

    properties = published["properties"]

    assert properties.delivery_mode == 2
    assert properties.content_type == "application/json"

    assert published["mandatory"] is True

    assert "traceparent" in properties.headers

    extracted = messaging.extract_context(properties)

    remote_span = trace.get_current_span(extracted)

    remote_context = remote_span.get_span_context()

    assert (
        remote_context.trace_id
        == producer.context.trace_id
    )

    assert (
        remote_context.span_id
        == producer.context.span_id
    )

    assert remote_context.is_remote


def test_consumer_extracts_context(make_provider):
    provider, exporter = make_provider("consumer-service")

    messaging.configure_messaging_tracing(provider)

    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_id = "00f067aa0ba902b7"

    properties = pika.BasicProperties(
        headers={
            "traceparent": (
                f"00-{trace_id}-{parent_id}-01"
            ).encode("ascii")
        },
    )

    callback = Mock(return_value="processed")

    decorated = messaging.traced_consumer(
        "process_event",
        "test.queue",
    )(callback)

    channel = Mock()
    method = Mock()

    result = decorated(
        channel,
        method,
        properties,
        b"message",
    )

    assert result == "processed"

    callback.assert_called_once_with(
        channel,
        method,
        properties,
        b"message",
    )

    assert provider.force_flush()

    span = exporter.get_finished_spans()[0]

    assert span.kind == SpanKind.CONSUMER

    assert format(
        span.context.trace_id,
        "032x",
    ) == trace_id

    assert format(
        span.parent.span_id,
        "016x",
    ) == parent_id

    assert span.parent.is_remote


@pytest.mark.parametrize(
    "properties",
    [
        None,
        pika.BasicProperties(
            headers={"traceparent": "invalid"}
        ),
    ],
)
def test_consumer_without_valid_context(
    make_provider,
    properties,
):
    provider, exporter = make_provider("test-service")

    messaging.configure_messaging_tracing(provider)

    tracer = provider.get_tracer(__name__)

    callback = Mock()

    decorated = messaging.traced_consumer(
        "process_event",
        "test.queue",
    )(callback)

    with tracer.start_as_current_span("unrelated") as span:

        unrelated_trace_id = (
            span.get_span_context().trace_id
        )

        decorated(
            Mock(),
            Mock(),
            properties,
            b"message",
        )

    assert provider.force_flush()

    consumer_span = next(
        span
        for span in exporter.get_finished_spans()
        if span.kind == SpanKind.CONSUMER
    )

    assert consumer_span.context.is_valid

    assert consumer_span.parent is None

    assert (
        consumer_span.context.trace_id
        != unrelated_trace_id
    )


def test_disabled_messaging_tracing(make_provider):
    messaging.configure_messaging_tracing(None)

    channel = Mock()

    messaging.publish_event(
        channel,
        exchange="lab4.events",
        routing_key="order.created",
        body=b"message",
    )

    published = channel.basic_publish.call_args.kwargs

    assert published["properties"].headers is None

    callback = Mock(return_value="ok")

    decorated = messaging.traced_consumer(
        "process_event",
        "test.queue",
    )(callback)

    method = Mock()

    assert decorated(
        channel,
        method,
        None,
        b"message",
    ) == "ok"

    callback.assert_called_once_with(
        channel,
        method,
        None,
        b"message",
    )


def test_consumer_exception_is_recorded(make_provider):
    provider, exporter = make_provider("test-service")

    messaging.configure_messaging_tracing(provider)

    @messaging.traced_consumer(
        "failed_operation",
        "test.queue",
    )
    def failing_callback(
        ch,
        method,
        properties,
        body,
    ):
        raise RuntimeError("Test failure")

    with pytest.raises(RuntimeError):
        failing_callback(
            Mock(),
            Mock(),
            None,
            b"message",
        )

    assert provider.force_flush()

    span = exporter.get_finished_spans()[0]

    assert span.status.status_code == StatusCode.ERROR

    assert any(
        event.name == "exception"
        for event in span.events
    )


def test_payment_to_notification_trace(make_provider):
    order_provider, order_exporter = make_provider(
        "order-service"
    )

    payment_provider, payment_exporter = make_provider(
        "payment-service"
    )

    notification_provider, notification_exporter = make_provider(
        "notification-service"
    )

    messaging.configure_messaging_tracing(order_provider)

    order_channel = Mock()

    tracer = order_provider.get_tracer(__name__)

    with tracer.start_as_current_span("create_order") as root:

        trace_id = root.get_span_context().trace_id

        messaging.publish_event(
            order_channel,
            exchange="lab4.events",
            routing_key="order.created",
            body=json.dumps({
                "event": "OrderCreated",
                "orderId": "test-order-1",
                "simulate_failure": False,
            }).encode(),
        )

    order_message = (
        order_channel.basic_publish.call_args.kwargs
    )

    # Имитируем доставку RabbitMQ в Payment Service.

    messaging.configure_messaging_tracing(payment_provider)

    payment_channel = Mock()

    process_order(
        payment_channel,
        Mock(delivery_tag=1),
        order_message["properties"],
        order_message["body"],
    )

    payment_channel.basic_ack.assert_called_once_with(
        delivery_tag=1
    )

    payment_message = (
        payment_channel.basic_publish.call_args.kwargs
    )

    assert (
        payment_message["routing_key"]
        == "payment.completed"
    )

    # Имитируем доставку результата в Notification Service.

    messaging.configure_messaging_tracing(
        notification_provider
    )

    notification_channel = Mock()

    process_notification(
        notification_channel,
        Mock(delivery_tag=2),
        payment_message["properties"],
        payment_message["body"],
    )

    notification_channel.basic_ack.assert_called_once_with(
        delivery_tag=2
    )

    assert order_provider.force_flush()
    assert payment_provider.force_flush()
    assert notification_provider.force_flush()

    order_spans = order_exporter.get_finished_spans()

    payment_spans = payment_exporter.get_finished_spans()

    notification_spans = (
        notification_exporter.get_finished_spans()
    )

    all_spans = (
        order_spans
        + payment_spans
        + notification_spans
    )

    assert len(all_spans) == 5

    assert {
        span.context.trace_id
        for span in all_spans
    } == {trace_id}

    order_publish = next(
        span for span in order_spans
        if span.kind == SpanKind.PRODUCER
    )

    payment_process = next(
        span for span in payment_spans
        if span.kind == SpanKind.CONSUMER
    )

    payment_publish = next(
        span for span in payment_spans
        if span.kind == SpanKind.PRODUCER
    )

    notification_process = notification_spans[0]

    assert payment_process.name == "process_payment"

    assert (
        notification_process.name
        == "send_notification"
    )

    assert (
        payment_process.parent.span_id
        == order_publish.context.span_id
    )

    assert (
        payment_publish.parent.span_id
        == payment_process.context.span_id
    )

    assert (
        notification_process.parent.span_id
        == payment_publish.context.span_id
    )
