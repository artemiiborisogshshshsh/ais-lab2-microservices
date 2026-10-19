"""Публикация событий Order Service."""

import json
import os

import pika

from .models import Order


EXCHANGE_NAME = "lab4.events"


def publish_order_created(
    order: Order,
    simulate_failure: bool = False
) -> None:
    """Опубликовать событие создания заказа."""

    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ["RABBITMQ_URL"])
    )

    try:
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True
        )

        channel.confirm_delivery()

        event = {
            "event": "OrderCreated",
            "orderId": order.id,
            "userId": order.user_id,
            "items": [
                item.model_dump(by_alias=True)
                for item in order.items
            ],
            "totalAmount": order.total_amount,
            "createdAt": order.created_at.isoformat(),
            "simulate_failure": simulate_failure
        }

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="order.created",
            body=json.dumps(event).encode("utf-8"),
            mandatory=True,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json"
            )
        )

        print(
            f"Опубликовано OrderCreated: {event}",
            flush=True
        )

    finally:
        if connection.is_open:
            connection.close()


def publish_order_cancelled(order_id: str, reason: str) -> None:
    """Опубликовать событие отмены заказа."""

    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ["RABBITMQ_URL"])
    )

    try:
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True
        )

        channel.confirm_delivery()

        event = {
            "event": "OrderCancelled",
            "orderId": order_id,
            "reason": reason
        }

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="order.cancelled",
            body=json.dumps(event).encode("utf-8"),
            mandatory=True,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json"
            )
        )

        print(
            f"Опубликовано OrderCancelled: {event}",
            flush=True
        )

    finally:
        if connection.is_open:
            connection.close()
