import logging
import sys
from time import perf_counter

from fastapi import FastAPI, Request

from observability.logging import JsonFormatter


def setup_http_logging(
    app: FastAPI,
    service_name: str,
) -> None:
    """Подключает логирование HTTP-запросов."""

    logger = logging.Logger(
        f"{service_name}.http",
        level=logging.INFO,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))

    logger.addHandler(handler)
    logger.propagate = False

    @app.middleware("http")
    async def logging_middleware(
        request: Request,
        call_next,
    ):
        # Не засоряем логи запросами Prometheus.
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code

            return response

        finally:
            duration_ms = round(
                (perf_counter() - start_time) * 1000,
                2,
            )

            route = request.scope.get("route")
            endpoint = getattr(
                route,
                "path",
                "unmatched",
            )

            if status_code >= 500:
                level = logging.ERROR
            elif status_code >= 400:
                level = logging.WARNING
            else:
                level = logging.INFO

            logger.log(
                level,
                "HTTP request completed",
                extra={
                    "method": request.method,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
