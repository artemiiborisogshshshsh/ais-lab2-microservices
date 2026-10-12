
"""Тестовое in-memory хранилище Order Service."""

from datetime import datetime, timezone

from .models import Order, OrderItem


# ВАЖНО: product_id ниже — примеры.
# Проверьте, что товары с такими ID существуют в Catalog.

ORDERS: list[Order] = [
    Order(
        id="101",
        user_id="123",
        created_at=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),
        items=[
            OrderItem(product_id="1", quantity=2),
            OrderItem(product_id="5", quantity=1),
        ],
    ),
    Order(
        id="102",
        user_id="123",
        created_at=datetime(2026, 10, 12, 13, 30, tzinfo=timezone.utc),
        items=[
            OrderItem(product_id="1", quantity=1),
        ],
    ),
    Order(
        id="103",
        user_id="456",
        created_at=datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc),
        items=[
            OrderItem(product_id="2", quantity=3),
        ],
    ),
]


def get_orders_by_user_id(user_id: str) -> list[Order]:
    """Вернуть заказы пользователя или пустой список."""
    return [order for order in ORDERS if order.user_id == user_id]
