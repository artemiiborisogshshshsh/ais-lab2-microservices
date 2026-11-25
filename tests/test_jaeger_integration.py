"""Интеграционная проверка распределённой трассировки."""

import base64
import json
import os
import re
import time
import uuid

import httpx
import pytest


GATEWAY_URL = "http://localhost:8090"
JAEGER_URL = "http://localhost:16686"
LOKI_URL = "http://localhost:3100"


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_JAEGER_INTEGRATION") != "1",
    reason="Requires running Docker Compose infrastructure",
)


@pytest.fixture(scope="module")
def authenticated_client():
    """Зарегистрировать пользователя и получить JWT."""

    suffix = uuid.uuid4().hex[:12]

    username = f"trace_{suffix}"
    email = f"{username}@example.com"
    password = "TraceDemo123!"

    with httpx.Client(
        base_url=GATEWAY_URL,
        timeout=15,
    ) as client:

        response = client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "phone": "+79990000000",
                "password": password,
            },
        )

        assert response.status_code == 201, response.text

        response = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )

        assert response.status_code == 200, response.text

        token = response.json()["access_token"]

        client.headers["Authorization"] = (
            f"Bearer {token}"
        )

        response = client.get("/auth/me")

        assert response.status_code == 200, response.text

        user_id = response.json()["user_id"]

        yield client, user_id


def wait_for_order(client, user_id, order_id, expected):
    """Дождаться завершения Saga."""

    deadline = time.monotonic() + 30

    while time.monotonic() < deadline:

        response = client.get(
            "/orders",
            params={"userId": user_id},
        )

        assert response.status_code == 200, response.text

        for order in response.json():

            if (
                order["id"] == order_id
                and order["status"] == expected
            ):
                return order

        time.sleep(1)

    pytest.fail(
        f"Order {order_id} did not reach {expected}"
    )


def get_loki_logs(query, start_time):
    """Получить структурированные записи Loki."""

    response = httpx.get(
        f"{LOKI_URL}/loki/api/v1/query_range",
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

    return [
        json.loads(line)
        for stream in payload["data"]["result"]
        for _, line in stream["values"]
    ]


def wait_for_order_logs(order_id, start_time, expected):
    """Дождаться логов всех бизнес-операций."""

    query = (
        '{service=~"order-service|payment-service|'
        'notification-service"}'
        ' | json | __error__=""'
        f' | order_id="{order_id}"'
    )

    deadline = time.monotonic() + 30

    observed = set()

    while time.monotonic() < deadline:

        logs = get_loki_logs(query, start_time)

        observed = {
            (log["service_name"], log["message"])
            for log in logs
        }

        if expected.issubset(observed):
            return [
                log for log in logs
                if (
                    log["service_name"],
                    log["message"],
                ) in expected
            ]

        time.sleep(1)

    pytest.fail(
        f"Missing logs: {expected - observed}"
    )


def normalize_id(value, length):
    """Привести идентификатор к hex-строке."""

    if not value:
        return ""

    if re.fullmatch(
        rf"[0-9a-fA-F]{{{length}}}",
        value,
    ):
        return value.lower()

    decoded = base64.b64decode(
        value,
        validate=True,
    ).hex()

    assert len(decoded) == length, value

    return decoded


def get_attributes(attributes):
    """Преобразовать атрибуты OTLP в словарь."""

    return {
        item["key"]: next(
            iter(item["value"].values()),
            None,
        )
        for item in attributes
    }


def get_trace(trace_id):
    """Получить спаны из Jaeger Query API."""

    response = httpx.get(
        f"{JAEGER_URL}/api/v3/traces/{trace_id}",
        timeout=10,
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()

    # Поддерживаем обычный JSON и поток JSON-объектов.
    try:
        documents = [response.json()]

    except ValueError:
        documents = [
            json.loads(line)
            for line in response.text.splitlines()
            if line.strip()
        ]

    spans = []

    for document in documents:

        assert not document.get("error"), document

        payload = document.get("result", document)

        for resource in payload.get("resourceSpans", []):

            resource_attributes = get_attributes(
                resource.get("resource", {}).get(
                    "attributes", []
                )
            )

            service_name = resource_attributes.get(
                "service.name"
            )

            for scope in resource.get("scopeSpans", []):

                for span in scope.get("spans", []):

                    spans.append({
                        "service": service_name,
                        "name": span["name"],
                        "trace_id": normalize_id(
                            span["traceId"], 32
                        ),
                        "span_id": normalize_id(
                            span["spanId"], 16
                        ),
                        "parent_id": normalize_id(
                            span.get("parentSpanId"), 16
                        ),
                        "kind": span.get("kind"),
                        "status": span.get("status", {}),
                        "attributes": get_attributes(
                            span.get("attributes", [])
                        ),
                    })

    return spans


def wait_for_trace(trace_id, expected_spans):
    """Дождаться экспорта всех необходимых спанов."""

    deadline = time.monotonic() + 30

    observed = set()

    while time.monotonic() < deadline:

        spans = get_trace(trace_id)

        observed = {
            (span["service"], span["name"])
            for span in spans
        }

        if expected_spans.issubset(observed):
            return spans

        time.sleep(1)

    pytest.fail(
        f"Trace {trace_id}: "
        f"missing spans {expected_spans - observed}"
    )


def find_span(spans, service, name):
    """Найти единственный ожидаемый спан."""

    matching = [
        span for span in spans
        if span["service"] == service
        and span["name"] == name
    ]

    assert len(matching) == 1, (
        service, name, matching
    )

    return matching[0]


def assert_parent(child, parent):
    """Проверить родительскую связь между спанами."""

    assert child["trace_id"] == parent["trace_id"]

    assert child["parent_id"] == parent["span_id"], (
        child["name"],
        parent["name"],
    )


@pytest.mark.parametrize(
    "simulate_failure, expected_status",
    [
        (False, "CONFIRMED"),
        (True, "CANCELLED"),
    ],
)
def test_distributed_order_trace(
    authenticated_client,
    simulate_failure,
    expected_status,
):
    client, user_id = authenticated_client

    start_time = time.time_ns() - 1_000_000_000

    response = client.post(
        "/orders",
        json={
            "userId": user_id,
            "items": [
                {
                    "productId": "trace-test-product",
                    "quantity": 1,
                },
            ],
            "totalAmount": 1500,
            "simulateFailure": simulate_failure,
        },
    )

    assert response.status_code == 201, response.text

    order_id = response.json()["id"]

    order = wait_for_order(
        client,
        user_id,
        order_id,
        expected_status,
    )

    assert order["status"] == expected_status

    expected_logs = {
        ("order-service", "Order created"),
        ("order-service", "OrderCreated published"),
        ("payment-service", "OrderCreated received"),
    }

    if simulate_failure:

        payment_publish = "publish payment.failed"
        notification_event = "OrderCancelled"
        payment_result = "failed"

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

        payment_publish = "publish payment.completed"
        notification_event = "PaymentCompleted"
        payment_result = "completed"

        expected_logs.update({
            ("payment-service", "Payment completed"),
            ("order-service", "Order confirmed"),
            (
                "notification-service",
                "Payment notification sent",
            ),
        })

    logs = wait_for_order_logs(
        order_id,
        start_time,
        expected_logs,
    )

    # Получаем настоящий Trace ID из Loki.
    trace_ids = {
        log.get("trace_id")
        for log in logs
    }

    assert len(trace_ids) == 1, trace_ids

    trace_id = next(iter(trace_ids))

    assert re.fullmatch(
        r"[0-9a-f]{32}", trace_id or ""
    )

    assert int(trace_id, 16) != 0

    expected_spans = {
        ("api-gateway", "POST /orders"),
        ("api-gateway", "POST"),
        ("order-service", "POST /orders"),
        ("order-service", "create_order"),
        ("order-service", "publish order.created"),
        ("payment-service", "process_payment"),
        ("payment-service", payment_publish),
        ("order-service", "process_payment_result"),
        ("notification-service", "send_notification"),
    }

    if simulate_failure:
        expected_spans.add(
            ("order-service", "publish order.cancelled")
        )

    spans = wait_for_trace(
        trace_id,
        expected_spans,
    )

    assert {
        span["service"]
        for span in spans
    }.issuperset({
        "api-gateway",
        "order-service",
        "payment-service",
        "notification-service",
    })

    assert {
        span["trace_id"]
        for span in spans
    } == {trace_id}

    gateway_server = find_span(
        spans, "api-gateway", "POST /orders"
    )

    gateway_client = find_span(
        spans, "api-gateway", "POST"
    )

    order_server = find_span(
        spans, "order-service", "POST /orders"
    )

    create_order = find_span(
        spans, "order-service", "create_order"
    )

    order_publish = find_span(
        spans, "order-service", "publish order.created"
    )

    payment = find_span(
        spans, "payment-service", "process_payment"
    )

    payment_event = find_span(
        spans, "payment-service", payment_publish
    )

    payment_handler = find_span(
        spans, "order-service", "process_payment_result"
    )

    notification = find_span(
        spans, "notification-service", "send_notification"
    )

    # Проверяем всю цепочку родительских связей.
    assert not gateway_server["parent_id"]

    assert_parent(gateway_client, gateway_server)
    assert_parent(order_server, gateway_client)
    assert_parent(create_order, order_server)
    assert_parent(order_publish, create_order)
    assert_parent(payment, order_publish)
    assert_parent(payment_event, payment)
    assert_parent(payment_handler, payment_event)

    if simulate_failure:

        cancellation = find_span(
            spans,
            "order-service",
            "publish order.cancelled",
        )

        assert_parent(cancellation, payment_handler)
        assert_parent(notification, cancellation)

    else:

        assert_parent(notification, payment_event)

    # Проверяем бизнес-атрибуты.
    assert create_order["attributes"]["order.id"] == order_id

    assert payment["attributes"]["order.id"] == order_id

    assert (
        payment["attributes"]["payment.result"]
        == payment_result
    )

    assert (
        notification["attributes"]["order.id"]
        == order_id
    )

    assert (
        notification["attributes"]["notification.event"]
        == notification_event
    )

    # OTLP может представлять enum числом или строкой.
    payment_status = payment["status"].get("code", 0)

    if simulate_failure:

        assert payment_status in (
            2, "2", "STATUS_CODE_ERROR"
        )

    else:

        assert payment_status in (
            0, "0", "STATUS_CODE_UNSET"
        )

    # Проверяем не только Trace ID, но и реальные Span ID.
    spans_by_id = {
        span["span_id"]: span
        for span in spans
    }

    for log in logs:

        span_id = log["span_id"]

        assert span_id in spans_by_id, log

        matched_span = spans_by_id[span_id]

        assert (
            matched_span["service"]
            == log["service_name"]
        )

        assert matched_span["trace_id"] == trace_id

    print(f"\nOrder ID: {order_id}")
    print(f"Final status: {expected_status}")
    print(f"Trace ID: {trace_id}")
    print(f"Spans: {len(spans)}")
    print(f"Correlated business logs: {len(logs)}")
    print(f"Jaeger: {JAEGER_URL}/trace/{trace_id}")
