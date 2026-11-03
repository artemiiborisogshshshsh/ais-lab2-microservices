
import json
import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from threading import Event, Thread

from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer


DB_PATH = os.getenv("READ_DB_PATH", "/data/orders_read.db")
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9093")
TOPIC = "orders-events"


@contextmanager
def database():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    with database() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders_read (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                items_json TEXT NOT NULL,
                total_amount REAL NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY
            )
        """)


def apply_event(event):
    """Обновить read-модель по событию из Kafka."""

    event_id = event["eventId"]
    order_id = event["orderId"]
    event_type = event["eventType"]
    version = int(event["version"])
    timestamp = event["timestamp"]
    payload = event["payload"]

    with database() as conn:
        # Защита от повторной доставки события
        duplicate = conn.execute(
            "SELECT 1 FROM processed_events WHERE event_id = ?",
            (event_id,)
        ).fetchone()

        if duplicate:
            return

        current = conn.execute(
            "SELECT version FROM orders_read WHERE order_id = ?",
            (order_id,)
        ).fetchone()

        if event_type == "OrderCreated":
            if current or version != 1:
                raise ValueError("Некорректное создание заказа")

            conn.execute("""
                INSERT INTO orders_read
                (order_id, user_id, items_json,
                 total_amount, status, version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                payload["userId"],
                json.dumps(payload["items"], ensure_ascii=False),
                payload["totalAmount"],
                "CREATED",
                version,
                timestamp
            ))

        elif event_type in ("OrderPaid", "OrderCancelled"):
            if not current or version != current[0] + 1:
                raise ValueError("Нарушена последовательность версий")

            status = (
                "PAID" if event_type == "OrderPaid"
                else "CANCELLED"
            )

            conn.execute("""
                UPDATE orders_read
                SET status = ?, version = ?, updated_at = ?
                WHERE order_id = ?
            """, (status, version, timestamp, order_id))

        else:
            raise ValueError(f"Неизвестный тип события: {event_type}")

        conn.execute(
            "INSERT INTO processed_events (event_id) VALUES (?)",
            (event_id,)
        )

    print(f"Read-модель обновлена: {order_id}, {event_type}", flush=True)


def consume_events(stop_event):
    """Получать события Kafka и обновлять read-модель."""

    while not stop_event.is_set():
        consumer = None

        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id="lab6-order-read-v1",
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda data: json.loads(
                    data.decode("utf-8")
                )
            )

            print("Kafka Consumer подключён", flush=True)

            while not stop_event.is_set():
                batches = consumer.poll(
                    timeout_ms=1000,
                    max_records=1
                )

                for messages in batches.values():
                    for message in messages:
                        apply_event(message.value)
                        consumer.commit()

        except Exception as error:
            print(f"Ошибка Kafka Consumer: {error}", flush=True)
            stop_event.wait(3)

        finally:
            if consumer is not None:
                consumer.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()

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
    title="Order Read Service",
    lifespan=lifespan
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    """Читать заказ только из read-модели."""

    with database() as conn:
        row = conn.execute("""
            SELECT order_id, user_id, items_json,
                   total_amount, status, version, updated_at
            FROM orders_read
            WHERE order_id = ?
        """, (order_id,)).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Заказ не найден в read-модели"
        )

    return {
        "id": row[0],
        "userId": row[1],
        "items": json.loads(row[2]),
        "totalAmount": row[3],
        "status": row[4],
        "version": row[5],
        "updatedAt": row[6]
    }
