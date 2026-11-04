
import unittest
from unittest.mock import Mock, call

from order_write_service.event_store import EventStore
from order_write_service.commands import (
    OrderCommands,
    InvalidOrderOperationError,
)


class TestOrderKafkaPublishing(unittest.TestCase):

    def setUp(self):
        self.event_store = EventStore()
        self.publisher = Mock()

        self.commands = OrderCommands(
            self.event_store,
            event_publisher=self.publisher,
        )

    def create_order(self):
        return self.commands.create_order(
            user_id="artemiy",
            items=[
                {
                    "productId": "product-1",
                    "quantity": 2,
                    "price": 5000,
                }
            ],
            total_amount=10000,
        )

    def test_create_order_publishes_event(self):
        event = self.create_order()

        self.publisher.publish.assert_called_once_with(event)
        self.assertEqual(event["eventType"], "OrderCreated")
        self.assertEqual(event["version"], 1)

    def test_pay_order_publishes_event(self):
        created = self.create_order()
        paid = self.commands.pay_order(created["orderId"])

        self.assertEqual(paid["eventType"], "OrderPaid")
        self.assertEqual(paid["version"], 2)

        self.publisher.publish.assert_has_calls([
            call(created),
            call(paid),
        ])

        self.assertEqual(self.publisher.publish.call_count, 2)

    def test_duplicate_payment_does_not_publish_event(self):
        created = self.create_order()
        self.commands.pay_order(created["orderId"])

        with self.assertRaises(InvalidOrderOperationError):
            self.commands.pay_order(created["orderId"])

        self.assertEqual(self.publisher.publish.call_count, 2)
        self.assertEqual(
            len(self.event_store.get_events(created["orderId"])),
            2,
        )


    def test_publication_failure_preserves_saved_event(self):
        # Имитируем недоступность Kafka
        self.publisher.publish.side_effect = RuntimeError(
            "Kafka недоступна"
        )

        # Команда должна сообщить об ошибке публикации
        with self.assertRaises(RuntimeError):
            self.create_order()

        # Проверяем, что попытка публикации была
        self.publisher.publish.assert_called_once()

        # Получаем событие, которое пытались отправить
        event = self.publisher.publish.call_args.args[0]

        # Проверяем, что событие осталось в Event Store
        events = self.event_store.get_events(event["orderId"])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["eventType"], "OrderCreated")
        self.assertEqual(events[0]["version"], 1)
        self.assertEqual(events[0], event)



if __name__ == "__main__":
    unittest.main()
