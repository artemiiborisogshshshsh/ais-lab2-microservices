import json
import os
import subprocess
import time
import re

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LOKI_INTEGRATION") != "1",
    reason="Requires running Docker Compose infrastructure",
)


ORDER_SCENARIO = """
import httpx
import json
import sys
import time
import uuid

simulate_failure = sys.argv[1] == "true"
user_id = str(uuid.uuid4())

base_url = "http://order-service:8000"

response = httpx.post(
    base_url + "/orders",
    headers={
        "X-User-Id": user_id,
        "X-User-Role": "user",
    },
    json={
        "userId": user_id,
        "items": [
            {
                "productId":
                    "00000000-0000-4000-8000-000000000001",
                "quantity": 1,
            }
        ],
        "totalAmount": 75000,
        "simulateFailure": simulate_failure,
    },
    timeout=10,
)

response.raise_for_status()
order_id = response.json()["id"]

expected_status = (
    "CANCELLED" if simulate_failure else "CONFIRMED"
)

deadline = time.monotonic() + 30

while time.monotonic() < deadline:
    response = httpx.get(
        base_url + "/orders",
        params={"userId": user_id},
        timeout=5,
    )

    response.raise_for_status()

    for order in response.json():
        if (
            order["id"] == order_id
            and order["status"] == expected_status
        ):
            print(json.dumps({
                "order_id": order_id,
                "status": order["status"],
            }))
            sys.exit(0)

    time.sleep(0.5)

raise RuntimeError(
    f"Order {order_id} did not reach {expected_status}"
)
"""


def create_order(simulate_failure):
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api-gateway",
            "python",
            "-c",
            ORDER_SCENARIO,
            str(simulate_failure).lower(),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr

    return json.loads(result.stdout.strip())


def get_order_logs(order_id, start_time):
    query = (
        '{service=~"order-service|payment-service|'
        'notification-service"}'
        ' | json | __error__=""'
        f' | order_id="{order_id}"'
    )

    response = httpx.get(
        "http://localhost:3100/loki/api/v1/query_range",
        params={
            "query": query,
            "start": str(start_time),
            "limit": 100,
        },
        timeout=10,
    )

    response.raise_for_status()

    payload = response.json()

    assert payload["status"] == "success"

    logs = []

    for stream in payload["data"]["result"]:
        for timestamp, line in stream["values"]:
            logs.append(json.loads(line))

    return logs


@pytest.mark.parametrize(
    "simulate_failure, expected_status",
    [
        (False, "CONFIRMED"),
        (True, "CANCELLED"),
    ],
)
def test_order_logs_in_loki(
    simulate_failure,
    expected_status,
):
    start_time = time.time_ns() - 1_000_000_000

    order = create_order(simulate_failure)

    assert order["status"] == expected_status

    order_id = order["order_id"]

    expected_logs = {
        ("order-service", "Order created"),
        ("order-service", "OrderCreated published"),
        ("payment-service", "OrderCreated received"),
    }

    if simulate_failure:
        expected_logs.update({
            ("payment-service", "Payment failed"),
            ("order-service", "Order cancelled"),
            ("order-service", "OrderCancelled published"),
            (
                "notification-service",
                "Cancellation notification sent",
            ),
        })
    else:
        expected_logs.update({
            ("payment-service", "Payment completed"),
            ("order-service", "Order confirmed"),
            (
                "notification-service",
                "Payment notification sent",
            ),
        })

    deadline = time.monotonic() + 30
    observed_logs = set()

    while time.monotonic() < deadline:
        logs = get_order_logs(order_id, start_time)

        observed_logs = {
            (log["service_name"], log["message"])
            for log in logs
        }

        if expected_logs.issubset(observed_logs):

            matched_logs = [
                log
                for log in logs
                if (
                    log["service_name"],
                    log["message"],
                ) in expected_logs
            ]

            for log in matched_logs:

                assert re.fullmatch(
                    r"[0-9a-f]{32}",
                    log.get("trace_id") or "",
                ), log

                assert re.fullmatch(
                    r"[0-9a-f]{16}",
                    log.get("span_id") or "",
                ), log

                assert int(log["trace_id"], 16) != 0
                assert int(log["span_id"], 16) != 0

            trace_ids = {
                log["trace_id"]
                for log in matched_logs
            }

            assert len(trace_ids) == 1, trace_ids

            print(
                f"\nOrder: {order_id}"
            )

            print(
                f"Trace ID: {next(iter(trace_ids))}"
            )

            print(
                f"Correlated logs: {len(matched_logs)}"
            )

            return

        time.sleep(1)

    missing = expected_logs - observed_logs

    pytest.fail(
        f"Missing Loki logs for order {order_id}: {missing}"
    )
