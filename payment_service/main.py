
import json
import os

import pika


RABBITMQ_URL = os.environ["RABBITMQ_URL"]

EXCHANGE_NAME = "lab4.events"
QUEUE_NAME = "lab4.payment"




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

    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        print(f"Некорректное сообщение: {error}", flush=True)

        ch.basic_reject(
            delivery_tag=method.delivery_tag,
            requeue=False
        )
        return

    print(f"Получено событие OrderCreated: {order_id}", flush=True)

    # Имитируем неуспешную оплату
    if event.get("simulate_failure") is True:

        failed_event = {
            "event": "PaymentFailed",
            "orderId": order_id,
            "reason": "Ошибка проведения платежа"
        }

        # Отправляем результат обратно в RabbitMQ
        ch.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key="payment.failed",
            body=json.dumps(failed_event).encode("utf-8"),
            mandatory=True,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json"
            )
        )

        print(f"Оплата заказа {order_id} не прошла", flush=True)
        print(f"Опубликовано PaymentFailed: {failed_event}", flush=True)

    else:
        # Временное поведение до интеграции успешной ветки Артемия.
        # Пока не отправляем сюда настоящие успешные заказы.
        print("Успешная ветка будет добавлена Артемием", flush=True)

    # Подтверждаем обработку сообщения
    ch.basic_ack(delivery_tag=method.delivery_tag)




def main():
    connection = pika.BlockingConnection(
        pika.URLParameters(RABBITMQ_URL)
    )

    channel = connection.channel()

    # Общий Exchange для событий
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="topic",
        durable=True
    )

    # Очередь Payment Service
    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True
    )

    # Подписка на событие создания заказа
    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key="order.created"
    )

    
    # Очередь, в которую Order Service получит PaymentFailed
    channel.queue_declare(
        queue="lab4.order",
        durable=True
    )

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue="lab4.order",
        routing_key="payment.failed"
    )

    # Ожидаем подтверждения публикации от RabbitMQ
    channel.confirm_delivery()

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_order,
        auto_ack=False
    )

    print("Payment Service запущен")
    print("Ожидание событий OrderCreated...")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Payment Service остановлен")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
