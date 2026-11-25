
import os
from api_gateway.rate_limit import rate_limit_middleware
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from observability.metrics import setup_metrics
from observability.http_logging import setup_http_logging
from observability.http_tracing import setup_http_tracing

app = FastAPI(
    title="API Gateway",
    description="Единая точка входа в микросервисную систему",
    version="1.0.0",
)
app.middleware("http")(rate_limit_middleware)
setup_metrics(app)
setup_http_logging(app, "api-gateway")

setup_http_tracing(
    app,
    "api-gateway",
    instrument_httpx=True,
)


AUTH_URL = os.getenv(
    "AUTH_SERVICE_URL",
    "http://auth-service:8000"
)

CATALOG_URL = os.getenv(
    "CATALOG_SERVICE_URL",
    "http://nginx/catalog"
)

ORDER_URL = os.getenv(
    "ORDER_SERVICE_URL",
    "http://order-service:8000"
)


HTTP_METHODS = [
    "GET", "POST", "PUT", "PATCH",
    "DELETE", "HEAD", "OPTIONS"
]

EXCLUDED_HEADERS = {
    "host",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}

RESPONSE_EXCLUDED_HEADERS = EXCLUDED_HEADERS | {
    "content-encoding",
    "date",
    "server",
}

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "api-gateway",
    }


async def proxy_request(request: Request, target_url: str):
    # Удаляем транспортные заголовки и пользовательские
    # заголовки роли, которым нельзя доверять.
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in EXCLUDED_HEADERS
        and key.lower() not in {"x-user-id", "x-user-role"}
    }

    # Договорённость с JWT middleware Артемия:
    # доверенные данные поступят из request.state.
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)

    if user_id is not None and user_role in ("user", "admin"):
        headers["X-User-Id"] = str(user_id)
        headers["X-User-Role"] = user_role

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            upstream_response = await client.request(
                method=request.method,
                url=target_url,
                params=list(request.query_params.multi_items()),
                content=await request.body(),
                headers=headers,
            )

        response_headers = {
            key: value
            for key, value in upstream_response.headers.items()
            if key.lower() not in RESPONSE_EXCLUDED_HEADERS
        }

        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
        )

    except httpx.RequestError:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Внутренний сервис недоступен"
            },
        )


@app.api_route("/auth/{path:path}", methods=HTTP_METHODS)
async def auth_proxy(path: str, request: Request):
    return await proxy_request(
        request,
        f"{AUTH_URL}/{path}",
    )


@app.api_route("/catalog/{path:path}", methods=HTTP_METHODS)
async def catalog_proxy(path: str, request: Request):
    return await proxy_request(
        request,
        f"{CATALOG_URL}/{path}",
    )


@app.api_route("/orders", methods=HTTP_METHODS)
@app.api_route("/orders/{path:path}", methods=HTTP_METHODS)
async def order_proxy(request: Request, path: str = ""):
    target_url = f"{ORDER_URL}/orders"

    if path:
        target_url += f"/{path}"

    return await proxy_request(request, target_url)
