import json
import os

import pika

from observability.logging import get_service_logger
from observability.messaging_tracing import (
    publish_event,
    traced_consumer,
    setup_worker_tracing,
)

logger = get_service_logger(
    "payment-service",
    __name__,
)

EXCHANGE_NAME = "lab4.events"
QUEUE_NAME = "lab4.payment"


@traced_consumer(
    "process_payment",
    QUEUE_NAME,
)
def process_order(ch, method, properties, body):    
    try:
        event = json.loads(body.decode("utf-8"))

        if not isinstance(event, dict):
            raise ValueError("Сообщение должно быть объектом JSON")

        if event.get("event") != "OrderCreated":
            raise ValueError("Ожидалось событие OrderCreated")

        order_id = event.get("orderId")

        if not isinstance(order_id, str) or not order_id:
            raise ValueError("Отсутствует корректный orderId")

    except (ValueError, UnicodeDecodeError):
        logger.warning(
            "Invalid order event",
            extra={"event": "InvalidEvent"},
        )

        ch.basic_reject(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )
        return

    logger.info(
        "OrderCreated received",
        extra={
            "event": "OrderCreated",
            "order_id": order_id,
        },
    )

    if event.get("simulate_failure") is True:
        failed_event = {
            "event": "PaymentFailed",
            "orderId": order_id,
            "reason": "Ошибка проведения платежа",
        }

        publish_event(
            ch,
            exchange=EXCHANGE_NAME,
            routing_key="payment.failed",
            body=json.dumps(failed_event).encode("utf-8"),
            mandatory=True,
        )

        logger.warning(
            "Payment failed",
            extra={
                "event": "PaymentFailed",
                "order_id": order_id,
            },
        )

    else:
        completed_event = {
            "event": "PaymentCompleted",
            "orderId": order_id,
        }

        publish_event(
            ch,
            exchange=EXCHANGE_NAME,
            routing_key="payment.completed",
            body=json.dumps(completed_event).encode("utf-8"),
            mandatory=True,
        )

        logger.info(
            "Payment completed",
            extra={
                "event": "PaymentCompleted",
                "order_id": order_id,
            },
        )

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    setup_worker_tracing("payment-service")

    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(
                os.environ["RABBITMQ_URL"]
            )
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
        routing_key="order.created",
    )

    channel.queue_declare(
        queue="lab4.order",
        durable=True,
    )

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue="lab4.order",
        routing_key="payment.failed",
    )

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue="lab4.order",
        routing_key="payment.completed",
    )

    channel.confirm_delivery()

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_order,
        auto_ack=False,
    )

    logger.info("Payment Service started")
    logger.info("Waiting for OrderCreated events")

    try:
        channel.start_consuming()

    except KeyboardInterrupt:
        logger.info("Payment Service stopped")

    except (pika.exceptions.AMQPError, OSError):
        logger.error("RabbitMQ processing failed")
        raise

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
