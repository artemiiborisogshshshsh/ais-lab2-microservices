
import json
import os

from confluent_kafka import Producer


class KafkaEventPublisher:

    def __init__(self):
        # Адрес Kafka для Python-клиента на Mac
        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092"
        )

        # Название топика с событиями заказов
        self.topic = "orders-events"

        self.producer = Producer({
            "bootstrap.servers": self.bootstrap_servers,
            "message.timeout.ms": 10000,
            "acks": "all",
        })

    def publish(self, event):
        """Отправить событие заказа в Kafka."""

        result = {
            "delivered": False,
            "error": None,
        }

        def delivery_callback(error, message):
            if error is not None:
                result["error"] = str(error)
            else:
                result["delivered"] = True
                print(
                    f"Событие {event['eventType']} "
                    f"доставлено в Kafka. "
                    f"Partition: {message.partition()}, "
                    f"Offset: {message.offset()}"
                )

        # Превращаем Python-словарь в JSON
        message_value = json.dumps(
            event,
            ensure_ascii=False
        ).encode("utf-8")

        # Отправляем сообщение в Kafka
        self.producer.produce(
            topic=self.topic,
            key=event["orderId"].encode("utf-8"),
            value=message_value,
            on_delivery=delivery_callback,
        )

        # Ожидаем подтверждения доставки
        remaining = self.producer.flush(10)

        if remaining != 0 or not result["delivered"]:
            raise RuntimeError(
                "Не удалось подтвердить доставку "
                f"события в Kafka: {result['error']}"
            )

        return True
