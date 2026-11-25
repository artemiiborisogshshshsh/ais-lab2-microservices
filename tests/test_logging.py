import json
import logging
from datetime import datetime
from unittest.mock import patch

import pytest

from observability.logging import (
    JsonFormatter,
    setup_logging,
)


def create_record(
    level: int = logging.INFO,
    message: str = "Тестовое сообщение",
) -> logging.LogRecord:
    return logging.LogRecord(
        name="test_logger",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_log_is_valid_json():
    formatter = JsonFormatter("order-service")
    record = create_record()

    result = json.loads(formatter.format(record))

    assert isinstance(result, dict)
    assert result["message"] == "Тестовое сообщение"


def test_log_contains_required_fields():
    formatter = JsonFormatter("auth-service")
    record = create_record()

    result = json.loads(formatter.format(record))

    assert result["service_name"] == "auth-service"
    assert result["logger"] == "test_logger"
    assert result["trace_id"] is None
    assert result["span_id"] is None

    timestamp = datetime.fromisoformat(result["timestamp"])
    assert timestamp.tzinfo is not None


@pytest.mark.parametrize(
    "level, expected",
    [
        (logging.DEBUG, "DEBUG"),
        (logging.INFO, "INFO"),
        (logging.WARNING, "WARNING"),
        (logging.ERROR, "ERROR"),
        (logging.CRITICAL, "CRITICAL"),
    ],
)
def test_logging_levels(level, expected):
    formatter = JsonFormatter("payment-service")
    record = create_record(level=level)

    result = json.loads(formatter.format(record))

    assert result["level"] == expected


def test_log_contains_order_id():
    formatter = JsonFormatter("order-service")
    record = create_record()
    record.order_id = "order-123"

    result = json.loads(formatter.format(record))

    assert result["order_id"] == "order-123"


def test_log_contains_trace_context():
    formatter = JsonFormatter("payment-service")
    record = create_record()

    record.trace_id = "a" * 32
    record.span_id = "b" * 16

    result = json.loads(formatter.format(record))

    assert result["trace_id"] == "a" * 32
    assert result["span_id"] == "b" * 16


def test_unknown_extra_fields_are_not_exported():
    formatter = JsonFormatter("auth-service")
    record = create_record()

    record.password = "test-password"
    record.authorization = "test-token"

    result = json.loads(formatter.format(record))

    assert "password" not in result
    assert "authorization" not in result


def test_setup_logging(capsys):
    with patch("logging.basicConfig") as mock_config:
        setup_logging("notification-service")

        config = mock_config.call_args.kwargs

        assert config["level"] == "INFO"
        assert config["force"] is True
        assert len(config["handlers"]) == 1

        handler = config["handlers"][0]

        assert isinstance(handler, logging.StreamHandler)
        assert isinstance(handler.formatter, JsonFormatter)

        handler.handle(create_record())

        output = capsys.readouterr().out
        result = json.loads(output)

        assert result["service_name"] == "notification-service"
        assert result["level"] == "INFO"
