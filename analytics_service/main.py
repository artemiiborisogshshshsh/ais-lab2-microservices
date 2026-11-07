
import json
import os
from contextlib import asynccontextmanager
from threading import Event, Lock, Thread

from fastapi import FastAPI
from kafka import KafkaConsumer


KAFKA_SERVER = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka:9093"
)

TOPIC = "orders-events"

# Текущее состояние заказов для аналитики
orders = {}

# Защита от повторной обработки сообщений
processed_events = set()

# Защита при работе нескольких потоков
model_lock = Lock()


def apply_event(event):
    """Обновить аналитическую модель по событию."""

    event_id = event["eventId"]
    order_id = event["orderId"]
    event_type = event["eventType"]
    version = int(event["version"])
    payload = event["payload"]

    with model_lock:
        if event_id in processed_events:
            return

        current = orders.get(order_id)

        if event_type == "OrderCreated":
            if current is not None or version != 1:
                raise ValueError(
                    "Некорректное создание заказа"
                )

            orders[order_id] = {
                "status": "CREATED",
                "totalAmount": float(
                    payload["totalAmount"]
                ),
                "version": 1
            }

        elif event_type == "OrderPaid":
            if current is None:
                raise ValueError("Заказ не существует")

            if current["status"] != "CREATED":
                raise ValueError(
                    "Оплатить можно только созданный заказ"
                )

            if version != current["version"] + 1:
                raise ValueError(
                    "Нарушена последовательность версий"
                )

            current["status"] = "PAID"
            current["version"] = version

        elif event_type == "OrderCancelled":
            if current is None:
                raise ValueError("Заказ не существует")

            if current["status"] not in (
                "CREATED", "PAID"
            ):
                raise ValueError(
                    "Заказ уже отменён"
                )

            if version != current["version"] + 1:
                raise ValueError(
                    "Нарушена последовательность версий"
                )

            current["status"] = "CANCELLED"
            current["version"] = version

        else:
            raise ValueError(
                f"Неизвестное событие: {event_type}"
            )

        processed_events.add(event_id)

    print(
        f"Analytics: обработано {event_type}, "
        f"заказ {order_id}, версия {version}",
        flush=True
    )


def consume_events(stop_event):
    """Читать Kafka и формировать аналитику."""

    while not stop_event.is_set():
        consumer = None

        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id="lab6-analytics-replay-v1",
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda data: json.loads(
                    data.decode("utf-8")
                )
            )

            print(
                "Analytics Consumer подключён к Kafka",
                flush=True
            )

            while not stop_event.is_set():
                batches = consumer.poll(
                    timeout_ms=1000,
                    max_records=50
                )

                for messages in batches.values():
                    for message in messages:
                        try:
                            apply_event(message.value)

                        except Exception as error:
                            print(
                                "Ошибка обработки события "
                                f"offset={message.offset}: "
                                f"{error}",
                                flush=True
                            )

        except Exception as error:
            print(
                f"Ошибка Analytics Consumer: {error}",
                flush=True
            )
            stop_event.wait(3)

        finally:
            if consumer is not None:
                consumer.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = Event()

    thread = Thread(
        target=consume_events,
        args=(stop_event,),
        daemon=True
    )
    thread.start()

    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=5)


app = FastAPI(
    title="Order Analytics Service",
    description="Аналитика CQRS на основе Kafka",
    lifespan=lifespan
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "storage": "in-memory"
    }


@app.get("/analytics/summary")
def analytics_summary():
    """Получить агрегированную статистику заказов."""

    with model_lock:
        all_orders = list(orders.values())

        total_orders = len(all_orders)

        created = sum(
            1 for order in all_orders
            if order["status"] == "CREATED"
        )

        paid = sum(
            1 for order in all_orders
            if order["status"] == "PAID"
        )

        cancelled = sum(
            1 for order in all_orders
            if order["status"] == "CANCELLED"
        )

        total_amount = sum(
            order["totalAmount"]
            for order in all_orders
        )

        paid_amount = sum(
            order["totalAmount"]
            for order in all_orders
            if order["status"] == "PAID"
        )

        average_amount = (
            total_amount / total_orders
            if total_orders > 0 else 0
        )

        event_count = len(processed_events)

    return {
        "totalOrders": total_orders,
        "ordersByStatus": {
            "CREATED": created,
            "PAID": paid,
            "CANCELLED": cancelled
        },
        "totalOrderAmount": round(
            total_amount, 2
        ),
        "paidOrderAmount": round(
            paid_amount, 2
        ),
        "averageOrderAmount": round(
            average_amount, 2
        ),
        "processedEvents": event_count
    }
