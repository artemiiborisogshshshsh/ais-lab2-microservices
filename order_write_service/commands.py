
from uuid import uuid4

from order_write_service.aggregate import rehydrate_order


class OrderNotFoundError(Exception):
    """Заказ не найден."""


class InvalidOrderOperationError(Exception):
    """Операция запрещена бизнес-правилами."""


class OrderCommands:
    def __init__(self, event_store, event_publisher=None):
        self.event_store = event_store
        self.event_publisher = event_publisher

    def create_order(self, user_id, items, total_amount):
        """Создать заказ."""

        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Необходимо указать пользователя")

        if not isinstance(items, list) or not items:
            raise ValueError("Список товаров не должен быть пустым")

        if (
            isinstance(total_amount, bool)
            or not isinstance(total_amount, (int, float))
            or total_amount <= 0
        ):
            raise ValueError("Сумма заказа должна быть положительной")

        order_id = str(uuid4())

        # Проверяем, что у нового заказа нет истории
        events = self.event_store.get_events(order_id)
        state = rehydrate_order(events)

        if state is not None:
            raise InvalidOrderOperationError(
                "Заказ уже существует"
            )

        event = self.event_store.append_event(
            order_id=order_id,
            event_type="OrderCreated",
            payload={
                "userId": user_id,
                "items": items,
                "totalAmount": total_amount
            },
            expected_version=0
        )

        if self.event_publisher is not None:
            self.event_publisher.publish(event)

        return event

    def pay_order(self, order_id):
        """Оплатить заказ."""

        # 1. Загружаем историю
        events = self.event_store.get_events(order_id)

        # 2. Восстанавливаем состояние
        state = rehydrate_order(events)

        # 3. Проверяем существование заказа
        if state is None:
            raise OrderNotFoundError(
                f"Заказ {order_id} не найден"
            )

        # 4. Проверяем бизнес-правила
        if state["status"] != "CREATED":
            raise InvalidOrderOperationError(
                "Оплатить можно только созданный заказ"
            )

        # 5. Создаём новое событие
        event = self.event_store.append_event(
            order_id=order_id,
            event_type="OrderPaid",
            payload={
                "transactionId": str(uuid4())
            },
            expected_version=state["version"]
        )

        if self.event_publisher is not None:
            self.event_publisher.publish(event)

        return event
    
    def cancel_order(self, order_id):
        """Отменить созданный или оплаченный заказ."""

        # Загружаем события заказа
        events = self.event_store.get_events(order_id)

        # Восстанавливаем текущее состояние
        state = rehydrate_order(events)

        if state is None:
            raise OrderNotFoundError(
                f"Заказ {order_id} не найден"
            )

        # Проверяем бизнес-правила
        if state["status"] not in ("CREATED", "PAID"):
            raise InvalidOrderOperationError(
                "Заказ уже отменён"
            )

        # Записываем новое событие
        event = self.event_store.append_event(
            order_id=order_id,
            event_type="OrderCancelled",
            payload={},
            expected_version=state["version"]
        )

        # Публикуем событие в Kafka
        if self.event_publisher is not None:
            self.event_publisher.publish(event)

        return event

