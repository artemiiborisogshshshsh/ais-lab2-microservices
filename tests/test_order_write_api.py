
import unittest

from fastapi.testclient import TestClient

from order_write_service import main as api
from order_write_service.event_store import EventStore
from order_write_service.commands import OrderCommands


class TestOrderWriteAPI(unittest.TestCase):

    def setUp(self):
        # Для каждого теста создаём чистое хранилище
        api.event_store = EventStore()
        api.commands = OrderCommands(api.event_store)

        self.client = TestClient(api.app)

        self.order_data = {
            "userId": "artemiy",
            "items": [
                {
                    "productId": "product-1",
                    "quantity": 1
                }
            ],
            "totalAmount": 15000
        }

    def test_create_order(self):
        response = self.client.post(
            "/orders",
            json=self.order_data
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["eventType"],
            "OrderCreated"
        )
        self.assertEqual(response.json()["version"], 1)

    def test_payment_and_duplicate(self):
        created = self.client.post(
            "/orders",
            json=self.order_data
        )

        order_id = created.json()["orderId"]

        paid = self.client.post(
            f"/orders/{order_id}/pay"
        )

        self.assertEqual(paid.status_code, 201)
        self.assertEqual(
            paid.json()["eventType"],
            "OrderPaid"
        )

        duplicate = self.client.post(
            f"/orders/{order_id}/pay"
        )

        self.assertEqual(duplicate.status_code, 409)

        # После отклонённой команды событий всё ещё два
        events = api.event_store.get_events(order_id)
        self.assertEqual(len(events), 2)

    def test_unknown_order(self):
        response = self.client.post(
            "/orders/nonexistent-order/pay"
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_amount(self):
        invalid_data = self.order_data.copy()
        invalid_data["totalAmount"] = -100

        response = self.client.post(
            "/orders",
            json=invalid_data
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
