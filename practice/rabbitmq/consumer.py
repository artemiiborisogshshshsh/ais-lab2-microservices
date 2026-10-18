import pika

# 1. Подключаемся к RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="localhost")
)

# 2. Создаём канал
channel = connection.channel()

# 3. Подключаемся к очереди
channel.queue_declare(
    queue="artemiy.lab4.demo",
    durable=True
)

# 4. Функция обработки сообщения
def callback(ch, method, properties, body):

    message = body.decode("utf-8")

    print("Получено сообщение:", message)

    # Подтверждаем успешную обработку
    ch.basic_ack(delivery_tag=method.delivery_tag)


# 5. Подписываемся на очередь
channel.basic_consume(
    queue="artemiy.lab4.demo",
    on_message_callback=callback,
    auto_ack=False
)

print("Ожидаем сообщения...")

# 6. Запускаем получение сообщений
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print("\nConsumer остановлен")
finally:
    if connection.is_open:
        connection.close()