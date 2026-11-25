from functools import wraps
from time import perf_counter

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    start_http_server,
)


class OperationMetrics:

    def __init__(
        self,
        counter_name: str,
        duration_name: str,
    ):
        self.registry = CollectorRegistry()

        self.counter = Counter(
            counter_name,
            "Количество выполненных операций",
            ["operation", "outcome"],
            registry=self.registry,
        )

        self.duration = Histogram(
            duration_name,
            "Длительность выполнения операций",
            ["operation", "outcome"],
            registry=self.registry,
        )

    def start(self, port: int = 9100):
        return start_http_server(
            port,
            addr="0.0.0.0",
            registry=self.registry,
        )

    def instrument(self, operation: str):

        def decorator(func):

            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = perf_counter()
                outcome = "error"

                try:
                    result = func(*args, **kwargs)

                    if isinstance(result, str) and result == "rejected":
                        outcome = "rejected"
                    else:
                        outcome = "ok"

                    return result

                finally:
                    elapsed = perf_counter() - start_time

                    self.counter.labels(
                        operation=operation,
                        outcome=outcome,
                    ).inc()

                    self.duration.labels(
                        operation=operation,
                        outcome=outcome,
                    ).observe(elapsed)

            return wrapper

        return decorator