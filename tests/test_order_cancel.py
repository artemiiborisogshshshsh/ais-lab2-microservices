
import unittest

from order_write_service.event_store import EventStore
from order_write_service.commands import (
    OrderCommands,
    OrderNotFoundError,
    InvalidOrderOperationError,
)
from order_write_service.aggregate import rehydrate_order


class TestOrderCancellation(unittest.TestCase):

    def setUp(self):
        self.store = EventStore()
        self.commands = OrderCommands(self.store)

    def create_order(self):
        return self.commands.create_order(
            user_id="nikita",
            items=[
                {"productId": "product-1", "quantity": 1}
            ],
            total_amount=15000
        )

    def test_cancel_created_order(self):
        created = self.create_order()
        order_id = created["orderId"]

        cancelled = self.commands.cancel_order(order_id)

        self.assertEqual(
            cancelled["eventType"], "OrderCancelled"
        )
        self.assertEqual(cancelled["version"], 2)

        state = rehydrate_order(
            self.store.get_events(order_id)
        )

        self.assertEqual(state["status"], "CANCELLED")

    def test_cancel_paid_order(self):
        created = self.create_order()
        order_id = created["orderId"]

        self.commands.pay_order(order_id)
        cancelled = self.commands.cancel_order(order_id)

        self.assertEqual(cancelled["version"], 3)

        state = rehydrate_order(
            self.store.get_events(order_id)
        )

        self.assertEqual(state["status"], "CANCELLED")

    def test_cannot_cancel_twice(self):
        created = self.create_order()
        order_id = created["orderId"]

        self.commands.cancel_order(order_id)

        with self.assertRaises(InvalidOrderOperationError):
            self.commands.cancel_order(order_id)

        self.assertEqual(
            len(self.store.get_events(order_id)), 2
        )

    def test_cannot_pay_cancelled_order(self):
        created = self.create_order()
        order_id = created["orderId"]

        self.commands.cancel_order(order_id)

        with self.assertRaises(InvalidOrderOperationError):
            self.commands.pay_order(order_id)

    def test_cancel_unknown_order(self):
        with self.assertRaises(OrderNotFoundError):
            self.commands.cancel_order("unknown-order")


if __name__ == "__main__":
    unittest.main()
