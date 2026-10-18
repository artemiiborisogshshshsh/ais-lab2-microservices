"""Получение результатов оплаты через RabbitMQ."""

import json
import os

from threading import Event

import pika

from .storage import confirm_order


EXCHANGE_NAME = "lab4.events"
QUEUE_NAME = "lab4.order"


def process_payment_result(ch, method, properties, body, stop_event):
    """Обработать событие от Payment Service."""

    try:
        event = json.loads(body.decode("utf-8"))

        if not isinstance(event, dict):
            raise ValueError("Сообщение должно быть объектом JSON")

        event_name = event.get("event")
        order_id = event.get("orderId")

        if not isinstance(order_id, str) or not order_id:
            raise ValueError("Отсутствует корректный orderId")

    except (ValueError, UnicodeDecodeError) as error:
        print(f"Некорректное событие оплаты: {error}", flush=True)

        # Пока не теряем сообщение: возвращаем в очередь
        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True
        )
        stop_event.set()
        return

    print(
        f"Получено событие {event_name} для заказа {order_id}",
        flush=True
    )

    if event_name == "PaymentCompleted":

        confirmed = confirm_order(order_id)

        if confirmed:
            ch.basic_ack(
                delivery_tag=method.delivery_tag
            )

            print(
                f"PaymentCompleted обработан: {order_id}",
                flush=True
            )

        else:
            # Не удаляем результат оплаты,
            # если соответствующий заказ отсутствует
            # или его нельзя подтвердить.
            ch.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=True
            )
            stop_event.set()

    else:
        # PaymentFailed будет обрабатывать код компенсации Никиты.
        # До его подключения не подтверждаем это сообщение.
        print(
            f"Обработчик {event_name} пока не подключён",
            flush=True
        )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True
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

            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=lambda ch, method, properties, body:
                    process_payment_result(
                        ch, method, properties, body, stop_event
                    ),
                auto_ack=False
            )

            print(
                "Order Consumer запущен. Ожидание PaymentCompleted...",
                flush=True
            )

            while not stop_event.is_set():
                connection.process_data_events(time_limit=1)

        except pika.exceptions.AMQPError as error:
            print(
                f"Ошибка подключения к RabbitMQ: {error}",
                flush=True
            )
            stop_event.wait(2)

        finally:
            if connection is not None and connection.is_open:
                connection.close()