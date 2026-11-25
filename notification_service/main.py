import json
import os

import pika

from observability.logging import get_service_logger
from observability.messaging_tracing import (
    traced_consumer,
    setup_worker_tracing,
)
from opentelemetry import trace

logger = get_service_logger(
    "notification-service",
    __name__,
)

EXCHANGE_NAME = "lab4.events"
QUEUE_NAME = "lab4.notification"


@traced_consumer(
    "send_notification",
    QUEUE_NAME,
)
def process_notification(
    ch, method, properties, body
):
    """Обработать событие и вывести уведомление."""

    try:
        event = json.loads(body.decode("utf-8"))

        if not isinstance(event, dict):
            raise ValueError("Ожидался JSON-объект")

        event_name = event.get("event")

        if event_name not in (
            "PaymentCompleted",
            "OrderCancelled",
        ):
            raise ValueError("Неизвестное событие")

        order_id = event.get("orderId")

        if not isinstance(order_id, str) or not order_id:
            raise ValueError("Не указан orderId")

    except (ValueError, UnicodeDecodeError):
        logger.warning(
            "Invalid notification event",
            extra={"event": "InvalidEvent"},
        )

        ch.basic_reject(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )
        return
    span = trace.get_current_span()

    span.set_attribute(
        "order.id",
        order_id,
    )

    span.set_attribute(
        "notification.event",
        event_name,
    )
    if event_name == "PaymentCompleted":
        logger.info(
            "Payment notification sent",
            extra={
                "event": event_name,
                "order_id": order_id,
            },
        )

    elif event_name == "OrderCancelled":
        logger.info(
            "Cancellation notification sent",
            extra={
                "event": event_name,
                "order_id": order_id,
            },
        )

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    setup_worker_tracing("notification-service")
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(os.environ["RABBITMQ_URL"])
        )

    except (pika.exceptions.AMQPError, OSError):
        logger.error("RabbitMQ connection failed")
        raise

    channel = connection.channel()

    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="topic",
        durable=True,
    )

    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
    )

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key="payment.completed",
    )

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key="order.cancelled",
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_notification,
        auto_ack=False,
    )

    logger.info("Notification Service started")
    logger.info("Waiting for notification events")

    try:
        channel.start_consuming()

    except KeyboardInterrupt:
        logger.info("Notification Service stopped")

    except (pika.exceptions.AMQPError, OSError):
        logger.error("RabbitMQ processing failed")
        raise

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
