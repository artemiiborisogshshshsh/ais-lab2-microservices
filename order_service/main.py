"""REST API для Order Service."""

from fastapi import FastAPI, Query

from .models import Order
from .storage import get_orders_by_user_id


app = FastAPI(
    title="Order Service",
    description="REST API для получения заказов пользователей",
    version="1.0.0",
)


@app.get(
    "/orders",
    response_model=list[Order],
    summary="Получить заказы пользователя",
    description="Возвращает список заказов по идентификатору пользователя.",
)
def get_orders(
    user_id: str = Query(
        ...,
        alias="userId",
        min_length=1,
        description="Идентификатор пользователя",
    ),
) -> list[Order]:

    return get_orders_by_user_id(user_id)