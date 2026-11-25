import io
import json

from threading import Event
from unittest.mock import Mock, patch

import pytest

from payment_service import main as payment
from notification_service import main as notification
from order_service import consumer


def read_logs(stream):
    return [
        json.loads(line)
        for line in stream.getvalue().splitlines()
    ]


@pytest.mark.parametrize(
    "simulate_failure, event_name, routing_key, level",
    [
        (
            False,
            "PaymentCompleted",
            "payment.completed",
            "INFO",
        ),
        (
            True,
            "PaymentFailed",
            "payment.failed",
            "WARNING",
        ),
    ],
)
def test_payment_logging(
    simulate_failure,
    event_name,
    routing_key,
    level,
):
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

    logs = read_logs(stream)
    result = logs[-1]

    assert result["service_name"] == "payment-service"
    assert result["event"] == event_name
    assert result["level"] == level
    assert result["order_id"] == "test-order-1"

    channel.basic_ack.assert_called_once_with(
        delivery_tag=1,
    )

    channel.basic_publish.assert_called_once()

    published = channel.basic_publish.call_args.kwargs

    assert published["routing_key"] == routing_key
    assert json.loads(published["body"])["event"] == event_name


@pytest.mark.parametrize(
    "event_name",
    ["PaymentCompleted", "OrderCancelled"],
)
def test_notification_logging(event_name):
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

    result = read_logs(stream)[-1]

    assert result["service_name"] == "notification-service"
    assert result["event"] == event_name
    assert result["level"] == "INFO"
    assert result["order_id"] == "test-order-2"

    channel.basic_ack.assert_called_once_with(
        delivery_tag=2,
    )


@pytest.mark.parametrize(
    "module, callback",
    [
        (payment, payment.process_order),
        (notification, notification.process_notification),
    ],
)
def test_invalid_event_logging(module, callback):
    channel = Mock()
    method = Mock(delivery_tag=3)
    stream = io.StringIO()

    with patch.object(
        module.logger.handlers[0],
        "stream",
        stream,
    ):
        callback(
            channel,
            method,
            None,
            b"invalid-json",
        )

    result = read_logs(stream)[-1]

    assert result["level"] == "WARNING"
    assert result["event"] == "InvalidEvent"

    channel.basic_reject.assert_called_once_with(
        delivery_tag=3,
        requeue=False,
    )

    channel.basic_ack.assert_not_called()


def test_order_confirmation_logging():
    channel = Mock()
    method = Mock(delivery_tag=4)
    stop_event = Event()

    body = json.dumps({
        "event": "PaymentCompleted",
        "orderId": "test-order-4",
    }).encode()

    stream = io.StringIO()

    with (
        patch.object(
            consumer,
            "confirm_order",
            return_value=True,
        ) as confirm,
        patch.object(
            consumer.logger.handlers[0],
            "stream",
            stream,
        ),
    ):
        consumer.process_payment_result(
            channel,
            method,
            None,
            body,
            stop_event,
        )

    result = read_logs(stream)[-1]

    assert result["service_name"] == "order-service"
    assert result["message"] == "Order confirmed"
    assert result["event"] == "PaymentCompleted"
    assert result["order_id"] == "test-order-4"

    confirm.assert_called_once_with("test-order-4")

    channel.basic_ack.assert_called_once_with(
        delivery_tag=4,
    )

    assert not stop_event.is_set()


def test_order_cancellation_logging():
    channel = Mock()
    method = Mock(delivery_tag=5)
    stop_event = Event()

    body = json.dumps({
        "event": "PaymentFailed",
        "orderId": "test-order-5",
        "reason": "Test failure",
    }).encode()

    stream = io.StringIO()

    with (
        patch.object(consumer, "ORDERS", []),
        patch.object(
            consumer,
            "cancel_order",
            return_value=True,
        ) as cancel,
        patch.object(
            consumer,
            "publish_order_cancelled",
        ) as publish,
        patch.object(
            consumer.logger.handlers[0],
            "stream",
            stream,
        ),
    ):
        consumer.process_payment_result(
            channel,
            method,
            None,
            body,
            stop_event,
        )

    result = read_logs(stream)[-1]

    assert result["service_name"] == "order-service"
    assert result["message"] == "Order cancelled"
    assert result["event"] == "OrderCancelled"
    assert result["order_id"] == "test-order-5"

    cancel.assert_called_once_with("test-order-5")

    publish.assert_called_once_with(
        "test-order-5",
        "Test failure",
    )

    channel.basic_ack.assert_called_once_with(
        delivery_tag=5,
    )

    assert not stop_event.is_set()
