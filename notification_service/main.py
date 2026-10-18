
import json
import os

import pika


EXCHANGE_NAME = "lab4.events"
QUEUE_NAME = "lab4.notification"

def process_notification(ch, method, properties, body):
    """Обработать событие и вывести уведомление клиенту."""

    try:
        event = json.loads(body.decode("utf-8"))

        if not isinstance(event, dict):
            raise ValueError("Ожидался JSON-объект")

        event_name = event.get("event")

        # Notification Service поддерживает два события
        if event_name not in ("PaymentCompleted", "OrderCancelled"):
            raise ValueError(f"Неизвестное событие: {event_name}")

        order_id = event.get("orderId")

        if not isinstance(order_id, str) or not order_id:
            raise ValueError("Не указан orderId")

    except (ValueError, UnicodeDecodeError) as error:
        print(f"Некорректное сообщение: {error}", flush=True)

        ch.basic_reject(
            delivery_tag=method.delivery_tag,
            requeue=False
        )
        return

    # Успешная оплата — часть Артемия
    if event_name == "PaymentCompleted":

        print(
            f"Уведомление клиенту: "
            f"заказ {order_id} успешно оплачен",
            flush=True
        )

    # Отмена заказа — часть Никиты
    elif event_name == "OrderCancelled":

        print(
            f"Отправлено уведомление клиенту: "
            f"заказ {order_id} отменён",
            flush=True
        )

    # Подтверждаем обработку события
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
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
    # Подписка на успешную оплату — часть Артемия
    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key="payment.completed"
)
    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key="order.cancelled"
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_notification,
        auto_ack=False
    )

    print("Notification Service запущен", flush=True)

    print(
        "Ожидание событий PaymentCompleted и OrderCancelled...",
        flush=True
    )

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Notification Service остановлен")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
