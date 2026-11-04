
import unittest

from order_write_service.event_store import EventStore
from order_write_service.aggregate import rehydrate_order
from order_write_service.commands import (
    OrderCommands,
    OrderNotFoundError,
    InvalidOrderOperationError,
)


class TestOrderCommands(unittest.TestCase):

    def setUp(self):
        self.store = EventStore()
        self.commands = OrderCommands(self.store)

    def create_order(self):
        return self.commands.create_order(
            user_id="artemiy",
            items=[
                {"productId": "product-1", "quantity": 1}
            ],
            total_amount=15000
        )

    def test_create_order(self):
        event = self.create_order()

        self.assertEqual(event["eventType"], "OrderCreated")
        self.assertEqual(event["version"], 1)

        state = rehydrate_order(
            self.store.get_events(event["orderId"])
        )

        self.assertEqual(state["status"], "CREATED")

    def test_pay_order(self):
        created = self.create_order()
        order_id = created["orderId"]

        paid = self.commands.pay_order(order_id)

        self.assertEqual(paid["eventType"], "OrderPaid")
        self.assertEqual(paid["version"], 2)

        state = rehydrate_order(
            self.store.get_events(order_id)
        )

        self.assertEqual(state["status"], "PAID")

    def test_cannot_pay_twice(self):
        created = self.create_order()
        order_id = created["orderId"]

        self.commands.pay_order(order_id)

        with self.assertRaises(InvalidOrderOperationError):
            self.commands.pay_order(order_id)

        self.assertEqual(
            len(self.store.get_events(order_id)),
            2
        )

    def test_cannot_pay_cancelled_order(self):
        created = self.create_order()
        order_id = created["orderId"]

        # Имитируем уже записанное событие отмены
        self.store.append_event(
            order_id,
            "OrderCancelled",
            {},
            1
        )

        with self.assertRaises(InvalidOrderOperationError):
            self.commands.pay_order(order_id)

        self.assertEqual(
            len(self.store.get_events(order_id)),
            2
        )

    def test_unknown_order(self):
        with self.assertRaises(OrderNotFoundError):
            self.commands.pay_order("missing-order")

    def test_invalid_amount(self):
        with self.assertRaises(ValueError):
            self.commands.create_order(
                user_id="artemiy",
                items=[
                    {"productId": "product-1", "quantity": 1}
                ],
                total_amount=-100
            )


if __name__ == "__main__":
    unittest.main()
