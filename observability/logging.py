import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Преобразует записи логирования в JSON."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "service_name": self.service_name,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
        }

        if hasattr(record, "order_id"):
            log_data["order_id"] = record.order_id

        return json.dumps(
            log_data,
            ensure_ascii=False,
        )


def setup_logging(
    service_name: str,
    level: str = "INFO",
) -> None:
    """Настраивает структурированное логирование сервиса."""

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))

    logging.basicConfig(
        level=level,
        handlers=[handler],
        force=True,
    )
