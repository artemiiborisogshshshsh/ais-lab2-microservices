import unittest

from observability.operation_metrics import OperationMetrics


class TestOperationMetrics(unittest.TestCase):

    def setUp(self):
        self.metrics = OperationMetrics(
            counter_name="test_operations_total",
            duration_name="test_duration_seconds",
        )

    def count(self, outcome):
        return self.metrics.registry.get_sample_value(
            "test_operations_total",
            {
                "operation": "test_operation",
                "outcome": outcome,
            },
        )

    def test_successful_operation(self):

        @self.metrics.instrument("test_operation")
        def operation():
            return 42

        self.assertEqual(operation(), 42)
        self.assertEqual(self.count("ok"), 1)

    def test_rejected_operation(self):

        @self.metrics.instrument("test_operation")
        def operation():
            return "rejected"

        self.assertEqual(operation(), "rejected")
        self.assertEqual(self.count("rejected"), 1)

    def test_failed_operation(self):

        @self.metrics.instrument("test_operation")
        def operation():
            raise RuntimeError("Test error")

        with self.assertRaises(RuntimeError):
            operation()

        self.assertEqual(self.count("error"), 1)

    def test_multiple_operations(self):

        @self.metrics.instrument("test_operation")
        def operation():
            return True

        for _ in range(5):
            operation()

        self.assertEqual(self.count("ok"), 5)

    def test_duration_histogram(self):

        @self.metrics.instrument("test_operation")
        def operation():
            return True

        operation()

        count = self.metrics.registry.get_sample_value(
            "test_duration_seconds_count",
            {
                "operation": "test_operation",
                "outcome": "ok",
            },
        )

        duration = self.metrics.registry.get_sample_value(
            "test_duration_seconds_sum",
            {
                "operation": "test_operation",
                "outcome": "ok",
            },
        )

        self.assertEqual(count, 1)
        self.assertGreater(duration, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)