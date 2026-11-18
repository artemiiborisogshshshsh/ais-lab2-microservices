
import asyncio
import time

from fastapi import Request
from fastapi.responses import JSONResponse


WINDOW_SECONDS = 15 * 60
GENERAL_LIMIT = 100
LOGIN_LIMIT = 5

# Счётчики запросов:
# (IP, тип лимита) -> (номер окна, количество запросов)
counters = {}
counter_lock = asyncio.Lock()


def register_request(ip: str, limit_type: str, now: float):
    window_number = int(now // WINDOW_SECONDS)
    key = (ip, limit_type)

    previous_window, count = counters.get(
        key, (window_number, 0)
    )

    if previous_window != window_number:
        count = 0

    count += 1
    counters[key] = (window_number, count)

    return count


async def rate_limit_middleware(
    request: Request,
    call_next,
):
    ip = request.client.host if request.client else "unknown"
    now = time.time()

    is_login = (
        request.method == "POST"
        and request.url.path.rstrip("/") == "/auth/login"
    )

    async with counter_lock:
        general_count = register_request(
            ip, "general", now
        )

        login_count = 0

        if is_login:
            login_count = register_request(
                ip, "login", now
            )

    limit = LOGIN_LIMIT if is_login else GENERAL_LIMIT
    count = login_count if is_login else general_count

    if general_count > GENERAL_LIMIT:
        limit = GENERAL_LIMIT
        count = general_count

    reset_at = (
        int(now // WINDOW_SECONDS) + 1
    ) * WINDOW_SECONDS

    remaining = max(0, limit - count)

    if general_count > GENERAL_LIMIT or (
        is_login and login_count > LOGIN_LIMIT
    ):
        response = JSONResponse(
            status_code=429,
            content={
                "detail": "Превышен лимит запросов"
            },
        )

        response.headers["Retry-After"] = str(
            max(1, reset_at - int(now))
        )
    else:
        response = await call_next(request)

    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(
        remaining
    )
    response.headers["X-RateLimit-Reset"] = str(
        reset_at
    )

    return response
