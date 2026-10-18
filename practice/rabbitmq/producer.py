import json
import pika

# 1. Подключаемся к RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="localhost")
)

# 2. Создаём канал
channel = connection.channel()

# 3. Объявляем очередь
channel.queue_declare(
    queue="artemiy.lab4.demo",
    durable=True
)

# 4. Создаём сообщение
message = {
    "event": "DemoMessage",
    "text": "Привет от Артемия!"
}

# 5. Отправляем сообщение
channel.basic_publish(
    exchange="",
    routing_key="artemiy.lab4.demo",
    body=json.dumps(message, ensure_ascii=False).encode("utf-8"),
    properties=pika.BasicProperties(
        delivery_mode=2,
        content_type="application/json"
    )
)

print("Сообщение отправлено:", message)

# 6. Закрываем соединение
connection.close()