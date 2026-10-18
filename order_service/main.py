"""REST API для Order Service."""

from fastapi import FastAPI, Query
from .events import publish_order_created
from .models import Order, OrderCreate
from .storage import get_orders_by_user_id, create_order


app = FastAPI(
    title="Order Service",
    description="REST API для создания и получения заказов",
    version="1.1.0",
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


@app.post(
    "/orders",
    response_model=Order,
    status_code=201,
    summary="Создать новый заказ"
)
def create_new_order(data: OrderCreate) -> Order:
    """Создать заказ и опубликовать событие OrderCreated."""

    # Создаём заказ со статусом PENDING
    order = create_order(data)

    print(
        f"Создан заказ {order.id}, статус: {order.status}",
        flush=True
    )

    # Отправляем событие в RabbitMQ
    publish_order_created(
        order,
        simulate_failure=data.simulate_failure
    )

    return order