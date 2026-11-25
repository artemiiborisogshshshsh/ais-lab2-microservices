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
from observability.http_logging import setup_http_logging
from .business_metrics import ORDER_REGISTRY

from observability.logging import get_service_logger
from observability.http_tracing import setup_http_tracing
from observability.messaging_tracing import (
    configure_messaging_tracing,
)
from opentelemetry.trace import NoOpTracerProvider

logger = get_service_logger(
    "order-service",
    __name__,
)


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
setup_http_logging(app, "order-service")

tracer_provider = setup_http_tracing(
    app,
    "order-service",
)

configure_messaging_tracing(tracer_provider)
tracer = (
    tracer_provider.get_tracer(__name__)
    if tracer_provider is not None
    else NoOpTracerProvider().get_tracer(__name__)
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

    with tracer.start_as_current_span("create_order") as span:

        span.set_attribute(
            "order.total_amount",
            data.total_amount,
        )

        span.set_attribute(
            "order.items_count",
            len(data.items),
        )

        order = create_order(data)

        span.set_attribute(
            "order.id",
            order.id,
        )

        logger.info(
            "Order created",
            extra={
                "event": "OrderCreated",
                "order_id": order.id,
            },
        )

        publish_order_created(
            order,
            simulate_failure=data.simulate_failure,
        )

        return order
