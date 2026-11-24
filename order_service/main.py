"""REST API для Order Service."""

from fastapi import (
    FastAPI,
    Query,
    Header,
    Depends,
    HTTPException,
    status,
)
from .events import publish_order_created
from .models import Order, OrderCreate
from .storage import get_orders_by_user_id, create_order

from contextlib import asynccontextmanager
from threading import Event, Thread

from .consumer import consume_payment_results
from observability.metrics import setup_metrics
from .business_metrics import ORDER_REGISTRY
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запустить Consumer вместе с Order Service."""

    stop_event = Event()

    consumer_thread = Thread(
        target=consume_payment_results,
        args=(stop_event,),
        daemon=True
    )

    consumer_thread.start()

    try:
        yield
    finally:
        stop_event.set()
        consumer_thread.join(timeout=3)
app = FastAPI(
    title="Order Service",
    description="REST API для создания и получения заказов",
    version="1.2.0",
    lifespan=lifespan,
)
setup_metrics(app, registry=ORDER_REGISTRY)

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


def require_authenticated_role(
    x_user_id: str | None = Header(
        default=None,
        alias="X-User-Id",
    ),
    x_user_role: str | None = Header(
        default=None,
        alias="X-User-Role",
    ),
):
    if not x_user_id or x_user_role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для создания заказа",
        )

    return {
        "user_id": x_user_id,
        "role": x_user_role,
    }

@app.post(
    "/orders",
    response_model=Order,
    status_code=201,
    summary="Создать новый заказ"
)
def create_new_order(
    data: OrderCreate,
    user_info: dict = Depends(require_authenticated_role),
) -> Order:
    """Создать заказ и опубликовать событие OrderCreated."""
    if (
        user_info["role"] == "user"
        and data.user_id != user_info["user_id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя создать заказ от имени другого пользователя",
        )

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