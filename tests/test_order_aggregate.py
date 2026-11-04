
import unittest

from order_write_service.event_store import EventStore
from order_write_service.aggregate import rehydrate_order


class TestOrderAggregate(unittest.TestCase):

    def setUp(self):
        self.store = EventStore()

    def create_order(self):
        self.store.append_event(
            "order-123",
            "OrderCreated",
            {
                "totalAmount": 15000,
                "items": [{"productId": "product-1", "quantity": 1}]
            },
            0
        )

    def test_empty_history(self):
        state = rehydrate_order([])

        self.assertIsNone(state)

    def test_created_order(self):
        self.create_order()

        state = rehydrate_order(
            self.store.get_events("order-123")
        )

        self.assertEqual(state["status"], "CREATED")
        self.assertEqual(state["totalAmount"], 15000)
        self.assertEqual(state["version"], 1)

    def test_paid_order(self):
        self.create_order()

        self.store.append_event(
            "order-123", "OrderPaid", {}, 1
        )

        state = rehydrate_order(
            self.store.get_events("order-123")
        )

        self.assertEqual(state["status"], "PAID")
        self.assertEqual(state["version"], 2)

    def test_cancelled_after_payment(self):
        self.create_order()

        self.store.append_event(
            "order-123", "OrderPaid", {}, 1
        )

        self.store.append_event(
            "order-123", "OrderCancelled", {}, 2
        )

        state = rehydrate_order(
            self.store.get_events("order-123")
        )

        self.assertEqual(state["status"], "CANCELLED")
        self.assertEqual(state["version"], 3)

    def test_cannot_pay_twice(self):
        self.create_order()

        self.store.append_event(
            "order-123", "OrderPaid", {}, 1
        )

        self.store.append_event(
            "order-123", "OrderPaid", {}, 2
        )

        with self.assertRaises(ValueError):
            rehydrate_order(
                self.store.get_events("order-123")
            )

    def test_cannot_cancel_twice(self):
        self.create_order()

        self.store.append_event(
            "order-123", "OrderCancelled", {}, 1
        )

        self.store.append_event(
            "order-123", "OrderCancelled", {}, 2
        )

        with self.assertRaises(ValueError):
            rehydrate_order(
                self.store.get_events("order-123")
            )


if __name__ == "__main__":
    unittest.main()
