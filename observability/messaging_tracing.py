"""Распределённая трассировка сообщений RabbitMQ."""

import os
from functools import wraps
from collections.abc import Mapping

import pika

from opentelemetry.context import Context
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)

from observability.tracing import create_tracer_provider


propagator = TraceContextTextMapPropagator()

_tracer = None


def configure_messaging_tracing(provider):
    """Использовать провайдер текущего микросервиса."""

    global _tracer

    if provider is None:
        _tracer = None
    else:
        _tracer = provider.get_tracer(
            "observability.messaging"
        )


def setup_worker_tracing(service_name: str):
    """Настроить трассировку фонового микросервиса."""

    enabled = os.getenv(
        "TRACING_ENABLED",
        "false",
    ).lower()

    if enabled not in ("true", "1"):
        configure_messaging_tracing(None)
        return None

    provider = create_tracer_provider(service_name)

    configure_messaging_tracing(provider)

    return provider


def inject_headers() -> dict:
    """Записать текущий контекст в заголовки сообщения."""

    headers = {}

    propagator.inject(headers)

    return headers


def extract_context(properties):
    """Восстановить контекст полученного сообщения."""

    raw_headers = getattr(
        properties,
        "headers",
        None,
    )

    headers = {}

    if isinstance(raw_headers, Mapping):
        for key, value in raw_headers.items():

            if key not in ("traceparent", "tracestate"):
                continue

            if isinstance(value, bytes):
                try:
                    value = value.decode("ascii")
                except UnicodeDecodeError:
                    continue

            if isinstance(value, str):
                headers[key] = value

    return propagator.extract(
        headers,
        context=Context(),
    )


def publish_event(
    channel,
    *,
    exchange: str,
    routing_key: str,
    body: bytes,
    mandatory: bool = True,
):
    """Опубликовать сообщение с контекстом трассировки."""

    def send(headers=None):
        return channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            mandatory=mandatory,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                headers=headers,
            ),
        )

    if _tracer is None:
        return send()

    with _tracer.start_as_current_span(
        f"publish {routing_key}",
        kind=SpanKind.PRODUCER,
        attributes={
            "messaging.system": "rabbitmq",
            "messaging.destination.name": exchange,
            "messaging.rabbitmq.destination.routing_key": routing_key,
            "messaging.operation.name": "publish",
        },
    ):
        return send(inject_headers())


def traced_consumer(span_name: str, queue: str):
    """Декоратор трассировки обработчика RabbitMQ."""

    def decorator(callback):

        @wraps(callback)
        def wrapper(
            ch,
            method,
            properties,
            body,
            *args,
            **kwargs,
        ):
            if _tracer is None:
                return callback(
                    ch,
                    method,
                    properties,
                    body,
                    *args,
                    **kwargs,
                )

            context = extract_context(properties)

            with _tracer.start_as_current_span(
                span_name,
                context=context,
                kind=SpanKind.CONSUMER,
                attributes={
                    "messaging.system": "rabbitmq",
                    "messaging.destination.name": queue,
                    "messaging.operation.name": "process",
                },
            ):
                return callback(
                    ch,
                    method,
                    properties,
                    body,
                    *args,
                    **kwargs,
                )

        return wrapper

    return decorator
