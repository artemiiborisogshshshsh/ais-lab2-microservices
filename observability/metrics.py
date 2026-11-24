from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


def setup_metrics(app: FastAPI):
    registry = CollectorRegistry()

    app.state.metrics_registry = registry

    request_count = Counter(
        "http_requests_total",
        "Количество HTTP-запросов",
        ["method", "endpoint", "status"],
        registry=registry,
    )

    request_duration = Histogram(
        "http_request_duration_seconds",
        "Время обработки HTTP-запросов",
        ["method", "endpoint"],
        registry=registry,
    )

    errors_count = Counter(
        "errors_total",
        "Количество HTTP-ошибок",
        ["method", "endpoint", "status"],
        registry=registry,
    )

    @app.middleware("http")
    async def metrics_middleware(
        request: Request,
        call_next,
    ):
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code

            return response

        finally:
            duration = perf_counter() - start_time

            route = request.scope.get("route")
            endpoint = getattr(
                route,
                "path",
                "unmatched",
            )

            request_count.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(status_code),
            ).inc()

            request_duration.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)

            if status_code >= 400:
                errors_count.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=str(status_code),
                ).inc()

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )