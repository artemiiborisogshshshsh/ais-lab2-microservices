
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4


class ConcurrencyError(Exception):
    """Версия истории заказа не совпадает с ожидаемой."""


class EventStore:
    def __init__(self):
        # orderId -> список событий заказа
        self.events = {}

        # Защита от одновременной записи в рамках процесса
        self.lock = RLock()

    def append_event(
        self,
        order_id,
        event_type,
        payload,
        expected_version
    ):
        """Добавить новое событие в историю заказа."""

        if not order_id or not event_type:
            raise ValueError(
                "order_id и event_type обязательны"
            )

        if not isinstance(payload, dict):
            raise ValueError(
                "payload должен быть словарём"
            )

        if (
            type(expected_version) is not int
            or expected_version < 0
        ):
            raise ValueError(
                "expected_version должен быть целым "
                "неотрицательным числом"
            )

        with self.lock:
            order_events = self.events.get(order_id, [])

            current_version = len(order_events)

            if current_version != expected_version:
                raise ConcurrencyError(
                    f"Ожидалась версия {expected_version}, "
                    f"текущая версия {current_version}"
                )

            event = {
                "eventId": str(uuid4()),
                "orderId": order_id,
                "eventType": event_type,
                "payload": deepcopy(payload),
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
                "version": current_version + 1
            }

            self.events.setdefault(order_id, []).append(event)

            return deepcopy(event)

    def get_events(self, order_id):
        """Вернуть всю историю событий заказа."""

        with self.lock:
            return deepcopy(self.events.get(order_id, []))
