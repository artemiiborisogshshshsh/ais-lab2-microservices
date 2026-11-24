import unittest

from order_service.business_metrics import ORDER_REGISTRY

from order_service.models import OrderCreate

from order_service.storage import (
    ORDERS,
    create_order,
    confirm_order,
    cancel_order,
)


def metric_value(name):
    return ORDER_REGISTRY.get_sample_value(name)


class TestOrderBusinessMetrics(unittest.TestCase):

    def create_test_order(self):
        data = OrderCreate(
            userId="test-user",
            items=[
                {
                    "productId": "test-product",
                    "quantity": 1,
                }
            ],
            totalAmount=100,
        )

        order = create_order(data)

        self.addCleanup(ORDERS.remove, order)

        return order

    def test_created_counter(self):
        before = metric_value("orders_created_total")

        order = self.create_test_order()

        after = metric_value("orders_created_total")

        self.assertEqual(order.status, "PENDING")
        self.assertEqual(after - before, 1)

    def test_paid_counter(self):
        order = self.create_test_order()

        before = metric_value("orders_paid_total")

        self.assertTrue(confirm_order(order.id))

        after = metric_value("orders_paid_total")

        self.assertEqual(order.status, "CONFIRMED")
        self.assertEqual(after - before, 1)

    def test_cancelled_counter(self):
        order = self.create_test_order()

        before = metric_value("orders_cancelled_total")

        self.assertTrue(cancel_order(order.id))

        after = metric_value("orders_cancelled_total")

        self.assertEqual(order.status, "CANCELLED")
        self.assertEqual(after - before, 1)

    def test_duplicate_payment(self):
        order = self.create_test_order()

        before = metric_value("orders_paid_total")

        confirm_order(order.id)
        confirm_order(order.id)

        after = metric_value("orders_paid_total")

        self.assertEqual(after - before, 1)

    def test_duplicate_cancellation(self):
        order = self.create_test_order()

        before = metric_value("orders_cancelled_total")

        cancel_order(order.id)
        cancel_order(order.id)

        after = metric_value("orders_cancelled_total")

        self.assertEqual(after - before, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)