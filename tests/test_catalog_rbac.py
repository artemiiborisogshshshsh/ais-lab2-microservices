
import copy

import pytest
from fastapi.testclient import TestClient

from catalog_service import main as catalog


PRODUCT_ID = "00000000-0000-4000-8000-000000000001"
DELETE_PRODUCT_ID = "00000000-0000-4000-8000-000000000002"
MISSING_PRODUCT_ID = "99999999-9999-4999-8999-999999999999"

PRODUCT_DATA = {
    "name": "Тестовый товар",
    "price": 2999,
}

FORBIDDEN_RESPONSE = {
    "detail": "Недостаточно прав: требуется роль admin"
}


# Подготавливаем исходные товары перед каждым тестом
@pytest.fixture(autouse=True)
def reset_products(monkeypatch):
    initial_products = {
        product["id"]: product.copy()
        for product in catalog.INITIAL_PRODUCTS
    }

    monkeypatch.setattr(
        catalog,
        "products",
        initial_products,
    )


# Тестовый клиент без запуска Consul
@pytest.fixture
def client():
    return TestClient(catalog.app)


# ========================================
# POST /products — СОЗДАНИЕ
# ========================================

def test_user_cannot_create_product(client):
    before = copy.deepcopy(catalog.products)

    response = client.post(
        "/products",
        headers={"X-User-Role": "user"},
        json=PRODUCT_DATA,
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN_RESPONSE
    assert catalog.products == before


def test_admin_can_create_product(client):
    count_before = len(catalog.products)

    response = client.post(
        "/products",
        headers={"X-User-Role": "admin"},
        json=PRODUCT_DATA,
    )

    assert response.status_code == 201

    product = response.json()

    assert product["name"] == PRODUCT_DATA["name"]
    assert product["price"] == PRODUCT_DATA["price"]
    assert "id" in product

    assert len(catalog.products) == count_before + 1
    assert catalog.products[product["id"]] == product


def test_create_without_role_forbidden(client):
    before = copy.deepcopy(catalog.products)

    response = client.post(
        "/products",
        json=PRODUCT_DATA,
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN_RESPONSE
    assert catalog.products == before


def test_create_with_unknown_role_forbidden(client):
    before = copy.deepcopy(catalog.products)

    response = client.post(
        "/products",
        headers={"X-User-Role": "guest"},
        json=PRODUCT_DATA,
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN_RESPONSE
    assert catalog.products == before


# ========================================
# PUT /products/{product_id} — ИЗМЕНЕНИЕ
# ========================================

def test_user_cannot_update_product(client):
    before = copy.deepcopy(catalog.products)

    response = client.put(
        f"/products/{PRODUCT_ID}",
        headers={"X-User-Role": "user"},
        json=PRODUCT_DATA,
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN_RESPONSE
    assert catalog.products == before


def test_admin_can_update_product(client):
    response = client.put(
        f"/products/{PRODUCT_ID}",
        headers={"X-User-Role": "admin"},
        json=PRODUCT_DATA,
    )

    assert response.status_code == 200

    product = response.json()

    assert product["id"] == PRODUCT_ID
    assert product["name"] == PRODUCT_DATA["name"]
    assert product["price"] == PRODUCT_DATA["price"]
    assert catalog.products[PRODUCT_ID] == product


def test_update_without_role_forbidden(client):
    before = copy.deepcopy(catalog.products)

    response = client.put(
        f"/products/{PRODUCT_ID}",
        json=PRODUCT_DATA,
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN_RESPONSE
    assert catalog.products == before


def test_admin_update_nonexistent_product(client):
    response = client.put(
        f"/products/{MISSING_PRODUCT_ID}",
        headers={"X-User-Role": "admin"},
        json=PRODUCT_DATA,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Товар не найден"
    }


# ========================================
# DELETE /products/{product_id} — УДАЛЕНИЕ
# ========================================

def test_user_cannot_delete_product(client):
    before = copy.deepcopy(catalog.products)

    response = client.delete(
        f"/products/{DELETE_PRODUCT_ID}",
        headers={"X-User-Role": "user"},
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN_RESPONSE
    assert catalog.products == before


def test_admin_can_delete_product(client):
    product_before = catalog.products[DELETE_PRODUCT_ID].copy()

    response = client.delete(
        f"/products/{DELETE_PRODUCT_ID}",
        headers={"X-User-Role": "admin"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Товар успешно удален",
        "product": product_before,
    }
    assert DELETE_PRODUCT_ID not in catalog.products


def test_delete_without_role_forbidden(client):
    before = copy.deepcopy(catalog.products)

    response = client.delete(
        f"/products/{DELETE_PRODUCT_ID}",
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN_RESPONSE
    assert catalog.products == before


def test_admin_delete_nonexistent_product(client):
    response = client.delete(
        f"/products/{MISSING_PRODUCT_ID}",
        headers={"X-User-Role": "admin"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Товар не найден"
    }


# ========================================
# GET — ЧТЕНИЕ ТОВАРОВ
# ========================================

def test_get_products_without_role(client):
    response = client.get("/products")

    assert response.status_code == 200

    data = response.json()

    assert "instance_id" in data
    assert len(data["products"]) == 3


def test_get_product_without_role(client):
    response = client.get(f"/products/{PRODUCT_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == PRODUCT_ID


def test_get_nonexistent_product(client):
    response = client.get(
        f"/products/{MISSING_PRODUCT_ID}"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Товар не найден"
    }
