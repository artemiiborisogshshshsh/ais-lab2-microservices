import os

import httpx
import strawberry

from graphql import GraphQLError


# Адрес микросервиса заказов
ORDER_SERVICE_URL = os.getenv(
    "ORDER_SERVICE_URL",
    "http://127.0.0.1:8003"
)


# GraphQL-тип позиции заказа
@strawberry.type
class OrderItem:
    product_id: str
    quantity: int


# GraphQL-тип заказа
@strawberry.type
class Order:
    id: strawberry.ID
    user_id: str
    created_at: str
    items: list[OrderItem]


# Получение заказов из REST API
async def fetch_orders_by_user_id(user_id: str) -> list[Order]:

    url = f"{ORDER_SERVICE_URL}/orders"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                url,
                params={"userId": user_id}
            )

            response.raise_for_status()

    except httpx.HTTPStatusError as exc:
        raise GraphQLError(
            f"Order Service вернул ошибку HTTP {exc.response.status_code}"
        ) from exc

    except httpx.RequestError as exc:
        raise GraphQLError(
            "Не удалось подключиться к Order Service"
        ) from exc

    orders_data = response.json()

    result = []

    for order_data in orders_data:

        items = [
            OrderItem(
                product_id=item["productId"],
                quantity=item["quantity"]
            )
            for item in order_data["items"]
        ]

        order = Order(
            id=strawberry.ID(str(order_data["id"])),
            user_id=order_data["userId"],
            created_at=order_data["createdAt"],
            items=items
        )

        result.append(order)

    return result