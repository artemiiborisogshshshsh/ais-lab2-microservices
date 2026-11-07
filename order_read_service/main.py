
import json
import os
from copy import deepcopy
from contextlib import asynccontextmanager
from threading import Event, Lock, Thread

from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer


# Настройки Kafka
KAFKA_SERVER = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka:9093"
)
TOPIC = "orders-events"


# In-Memory Read Model
# Ключ — orderId, значение — текущее состояние заказа
orders_read = {}

# Идентификаторы уже обработанных событий
processed_events = set()

# Защита данных от одновременного изменения из разных потоков
model_lock = Lock()


def apply_event(event):
    """Применить событие к In-Memory read-модели."""

    event_id = event["eventId"]
    order_id = event["orderId"]
    event_type = event["eventType"]
    payload = event["payload"]
    timestamp = event["timestamp"]
    version = event["version"]

    with model_lock:

        # Не обрабатываем повторно одно и то же событие
        if event_id in processed_events:
            print(
                f"Пропущен дубликат события: {event_id}",
                flush=True
            )
            return

        current = orders_read.get(order_id)

        # Создание заказа
        if event_type == "OrderCreated":

            if current is not None:
                raise ValueError("Заказ уже существует")

            if version != 1:
                raise ValueError("Первая версия должна быть 1")

            orders_read[order_id] = {
                "id": order_id,
                "userId": payload["userId"],
                "items": deepcopy(payload["items"]),
                "totalAmount": payload["totalAmount"],
                "status": "CREATED",
                "version": version,
                "updatedAt": timestamp
            }

        # Оплата или отмена заказа
        elif event_type in ("OrderPaid", "OrderCancelled"):

            if current is None:
                raise ValueError("Заказ не найден")

            if version != current["version"] + 1:
                raise ValueError(
                    "Нарушена последовательность версий"
                )

            if event_type == "OrderPaid":
                status = "PAID"
            else:
                status = "CANCELLED"

            current["status"] = status
            current["version"] = version
            current["updatedAt"] = timestamp

        else:
            raise ValueError(
                f"Неизвестный тип события: {event_type}"
            )

        # Запоминаем успешно обработанное событие
        processed_events.add(event_id)

    print(
        f"Read-модель обновлена: {order_id}, "
        f"{event_type}, версия {version}",
        flush=True
    )


def consume_events(stop_event):
    """Читать Kafka и восстанавливать In-Memory read-модель."""

    while not stop_event.is_set():
        consumer = None

        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id=None,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda data: json.loads(
                    data.decode("utf-8")
                )
            )

            print(
                "Kafka Consumer подключён. "
                "Восстанавливаем read-модель из событий...",
                flush=True
            )

            while not stop_event.is_set():
                batches = consumer.poll(
                    timeout_ms=1000,
                    max_records=100
                )

                for messages in batches.values():
                    for message in messages:
                        try:
                            apply_event(message.value)

                        except (KeyError, TypeError, ValueError) as error:
                            print(
                                f"Ошибка обработки события "
                                f"offset={message.offset}: {error}",
                                flush=True
                            )

        except Exception as error:
            print(
                f"Ошибка Kafka Consumer: {error}",
                flush=True
            )
            stop_event.wait(3)

        finally:
            if consumer is not None:
                consumer.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск Consumer вместе с FastAPI."""

    stop_event = Event()

    consumer_thread = Thread(
        target=consume_events,
        args=(stop_event,),
        daemon=True
    )

    consumer_thread.start()

    try:
        yield

    finally:
        stop_event.set()
        consumer_thread.join(timeout=5)


app = FastAPI(
    title="Order Read Service - In Memory",
    description="CQRS Read Side для лабораторной №6",
    lifespan=lifespan
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "storage": "in-memory"
    }


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    """Получить заказ только из In-Memory read-модели."""

    with model_lock:
        order = orders_read.get(order_id)

        if order is not None:
            order = deepcopy(order)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Заказ не найден в read-модели"
        )

    return order
