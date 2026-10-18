"""Тестовое in-memory хранилище Order Service."""

from datetime import datetime, timezone
from uuid import uuid4

from .models import Order, OrderItem, OrderCreate


# Идентификаторы товаров соответствуют тестовым данным Catalog Service.

ORDERS: list[Order] = [
    Order(
        id="101",
        user_id="123",
        created_at=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),
        items=[
            OrderItem(
                product_id="00000000-0000-4000-8000-000000000001",
                quantity=2,
            ),
            OrderItem(
                product_id="00000000-0000-4000-8000-000000000002",
                quantity=1,
            ),
        ],
    ),
    Order(
        id="102",
        user_id="123",
        created_at=datetime(2026, 10, 12, 13, 30, tzinfo=timezone.utc),
        items=[
            OrderItem(
                product_id="00000000-0000-4000-8000-000000000001",
                quantity=1,
            ),
        ],
    ),
    Order(
        id="103",
        user_id="456",
        created_at=datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc),
        items=[
            OrderItem(
                product_id="00000000-0000-4000-8000-000000000002",
                quantity=3,
            ),
        ],
    ),
]


def get_orders_by_user_id(user_id: str) -> list[Order]:
    """Вернуть заказы пользователя или пустой список."""
    return [order for order in ORDERS if order.user_id == user_id]


def create_order(data: OrderCreate) -> Order:
    """Создать новый заказ и сохранить его в памяти."""

    new_order = Order(
        id=str(uuid4()),
        user_id=data.user_id,
        created_at=datetime.now(timezone.utc),
        items=data.items,
        status="PENDING",
        total_amount=data.total_amount
    )

    ORDERS.append(new_order)

    return new_order

def confirm_order(order_id: str) -> bool:
    """Подтвердить заказ после успешной оплаты."""

    for order in ORDERS:

        # Ищем заказ по идентификатору
        if order.id == order_id:

            # Подтверждаем только ожидающий заказ
            if order.status == "PENDING":
                order.status = "CONFIRMED"

                print(
                    f"Заказ {order_id} подтверждён",
                    flush=True
                )

                return True

            # Повторное подтверждение не меняет статус
            if order.status == "CONFIRMED":
                return True

            # Отменённый заказ подтверждать нельзя
            return False

    print(
        f"Заказ {order_id} не найден",
        flush=True
    )

    return False