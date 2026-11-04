
import unittest

from order_write_service.event_store import (
    EventStore,
    ConcurrencyError,
)


class TestEventStore(unittest.TestCase):

    def setUp(self):
        self.store = EventStore()

    def test_events_saved_in_order(self):
        self.store.append_event(
            "order-123",
            "OrderCreated",
            {"totalAmount": 15000},
            0
        )

        self.store.append_event(
            "order-123",
            "OrderPaid",
            {},
            1
        )

        events = self.store.get_events("order-123")

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["version"], 1)
        self.assertEqual(events[1]["version"], 2)
        self.assertEqual(
            events[1]["eventType"],
            "OrderPaid"
        )

    def test_old_version_rejected(self):
        self.store.append_event(
            "order-123",
            "OrderCreated",
            {},
            0
        )

        with self.assertRaises(ConcurrencyError):
            self.store.append_event(
                "order-123",
                "OrderPaid",
                {},
                0
            )

        self.assertEqual(
            len(self.store.get_events("order-123")),
            1
        )

    def test_orders_are_independent(self):
        self.store.append_event(
            "order-1", "OrderCreated", {}, 0
        )

        self.store.append_event(
            "order-2", "OrderCreated", {}, 0
        )

        self.assertEqual(
            len(self.store.get_events("order-1")),
            1
        )

        self.assertEqual(
            len(self.store.get_events("order-2")),
            1
        )

    def test_new_store_is_empty(self):
        self.store.append_event(
            "order-123", "OrderCreated", {}, 0
        )

        new_store = EventStore()

        self.assertEqual(
            new_store.get_events("order-123"),
            []
        )

    def test_returned_events_cannot_change_history(self):
        payload = {"items": [{"quantity": 1}]}

        self.store.append_event(
            "order-123",
            "OrderCreated",
            payload,
            0
        )

        payload["items"][0]["quantity"] = 99

        events = self.store.get_events("order-123")
        events[0]["payload"]["items"][0]["quantity"] = 50

        saved = self.store.get_events("order-123")

        self.assertEqual(
            saved[0]["payload"]["items"][0]["quantity"],
            1
        )


if __name__ == "__main__":
    unittest.main()
