
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from order_write_service.event_store import (
    EventStore,
    ConcurrencyError,
)

from order_write_service.commands import (
    OrderCommands,
    OrderNotFoundError,
    InvalidOrderOperationError,
)
from order_write_service.kafka_producer import KafkaEventPublisher

# Создаём FastAPI-приложение
app = FastAPI(
    title="Order Write Service",
    description="CQRS Write Side для управления заказами"
)


# Создаём единое In-Memory хранилище
event_store = EventStore()
publisher = KafkaEventPublisher()


# Передаём хранилище обработчику команд
commands = OrderCommands(
    event_store,
    event_publisher=publisher,
)

# Описываем формат запроса на создание заказа
class CreateOrderRequest(BaseModel):
    userId: str
    items: list[dict]
    totalAmount: float


# Команда создания заказа
@app.post("/orders", status_code=201)
def create_order(request: CreateOrderRequest):

    try:
        return commands.create_order(
            user_id=request.userId,
            items=request.items,
            total_amount=request.totalAmount
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error


# Команда оплаты заказа
@app.post("/orders/{order_id}/pay", status_code=201)
def pay_order(order_id: str):

    try:
        return commands.pay_order(order_id)

    except OrderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        ) from error

    except (
        InvalidOrderOperationError,
        ConcurrencyError
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        ) from error

@app.post("/orders/{order_id}/cancel", status_code=201)
def cancel_order(order_id: str):
    """Отменить заказ."""

    try:
        return commands.cancel_order(order_id)

    except OrderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        ) from error

    except (
        InvalidOrderOperationError,
        ConcurrencyError
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        ) from error

