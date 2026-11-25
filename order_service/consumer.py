"""Получение результатов оплаты через RabbitMQ."""

import json
import os

from threading import Event

import pika

from .storage import confirm_order, cancel_order, ORDERS
from .events import publish_order_cancelled

from observability.logging import get_service_logger


logger = get_service_logger(
    "order-service",
    __name__,
)

EXCHANGE_NAME = "lab4.events"
QUEUE_NAME = "lab4.order"

def process_payment_result(
    ch, method, properties, body, stop_event
):
    """Обработать событие от Payment Service."""

    try:
        event = json.loads(body.decode("utf-8"))

        if not isinstance(event, dict):
            raise ValueError("Сообщение должно быть объектом JSON")

        event_name = event.get("event")
        order_id = event.get("orderId")

        if not isinstance(order_id, str) or not order_id:
            raise ValueError("Отсутствует корректный orderId")

    except (ValueError, UnicodeDecodeError):
        logger.warning(
            "Invalid payment event",
            extra={"event": "InvalidEvent"},
        )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )
        stop_event.set()
        return

    if event_name == "PaymentCompleted":

        confirmed = confirm_order(order_id)

        if confirmed:
            ch.basic_ack(
                delivery_tag=method.delivery_tag,
            )

            logger.info(
                "Order confirmed",
                extra={
                    "event": "PaymentCompleted",
                    "order_id": order_id,
                },
            )

        else:
            logger.error(
                "Order confirmation failed",
                extra={
                    "event": "PaymentCompleted",
                    "order_id": order_id,
                },
            )

            ch.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=True,
            )
            stop_event.set()

    elif event_name == "PaymentFailed":

        order = next(
            (order for order in ORDERS if order.id == order_id),
            None,
        )

        if order is not None and order.status == "CANCELLED":
            logger.info(
                "Order already cancelled",
                extra={
                    "event": "PaymentFailed",
                    "order_id": order_id,
                },
            )

            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        cancelled = cancel_order(order_id)

        if cancelled:
            reason = event.get("reason") or "Ошибка оплаты"

            try:
                publish_order_cancelled(order_id, reason)

            except (pika.exceptions.AMQPError, OSError):
                logger.error(
                    "OrderCancelled publication failed",
                    extra={
                        "event": "OrderCancelled",
                        "order_id": order_id,
                    },
                )

                ch.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True,
                )
                stop_event.set()
                return

            ch.basic_ack(delivery_tag=method.delivery_tag)

            logger.info(
                "Order cancelled",
                extra={
                    "event": "OrderCancelled",
                    "order_id": order_id,
                },
            )

        else:
            logger.error(
                "Order cancellation failed",
                extra={
                    "event": "PaymentFailed",
                    "order_id": order_id,
                },
            )

            ch.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=True,
            )
            stop_event.set()

    else:
        logger.warning(
            "Unknown payment event",
            extra={
                "event": "UnknownEvent",
                "order_id": order_id,
            },
        )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )
        stop_event.set()


def consume_payment_results(stop_event: Event):
    """Слушать очередь результатов оплаты."""

    while not stop_event.is_set():
        connection = None

        try:
            connection = pika.BlockingConnection(
                pika.URLParameters(os.environ["RABBITMQ_URL"])
            )

            channel = connection.channel()

            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="topic",
                durable=True
            )

            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True
            )

            channel.queue_bind(
                exchange=EXCHANGE_NAME,
                queue=QUEUE_NAME,
                routing_key="payment.completed"
            )
            
            # Подписка на ошибки оплаты
            channel.queue_bind(
                exchange=EXCHANGE_NAME,
                queue=QUEUE_NAME,
                routing_key="payment.failed"
            )


            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=lambda ch, method, properties, body:
                    process_payment_result(
                        ch, method, properties, body, stop_event
                    ),
                auto_ack=False
            )

           
            logger.info(
                "Order Consumer started"
            )


            while not stop_event.is_set():
                connection.process_data_events(time_limit=1)

        except pika.exceptions.AMQPError as error:
            logger.error(
                "RabbitMQ connection failed"
            )

        finally:
            if connection is not None and connection.is_open:
                connection.close()