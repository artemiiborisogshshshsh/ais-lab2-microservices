import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from observability.http_logging import setup_http_logging


def create_test_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/forbidden")
    def forbidden():
        raise HTTPException(status_code=403)

    @app.get("/error")
    def error():
        raise RuntimeError("Test error")

    @app.get("/products/{product_id}")
    def product(product_id: str):
        return {"id": product_id}

    @app.get("/metrics")
    def metrics():
        return {"metrics": "test"}

    setup_http_logging(app, "test-service")

    return app


@pytest.mark.parametrize(
    "path, expected_status, expected_level",
    [
        ("/health", 200, "INFO"),
        ("/forbidden", 403, "WARNING"),
        ("/error", 500, "ERROR"),
    ],
)
def test_http_request_logging(
    path,
    expected_status,
    expected_level,
    capsys,
):
    app = create_test_app()

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client.get(path)

    assert response.status_code == expected_status

    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["service_name"] == "test-service"
    assert result["method"] == "GET"
    assert result["endpoint"] == path
    assert result["status_code"] == expected_status
    assert result["level"] == expected_level
    assert result["duration_ms"] >= 0


def test_sensitive_request_data_is_not_logged(capsys):
    app = create_test_app()
    client = TestClient(app)

    response = client.get(
        "/products/private-id",
        params={"password": "secret-password"},
        headers={
            "Authorization": "Bearer secret-token",
        },
    )

    assert response.status_code == 200

    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["endpoint"] == "/products/{product_id}"

    assert "private-id" not in output
    assert "secret-password" not in output
    assert "secret-token" not in output


def test_metrics_requests_are_not_logged(capsys):
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert capsys.readouterr().out == ""
