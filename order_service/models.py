"""Модели данных Order Service."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderItem(BaseModel):
    """Одна позиция в заказе."""

    model_config = ConfigDict(populate_by_name=True)

    product_id: str = Field(alias="productId", min_length=1)
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    """Данные для создания нового заказа."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId", min_length=1)
    items: list[OrderItem] = Field(min_length=1)
    total_amount: float = Field(alias="totalAmount", gt=0)

    simulate_failure: bool = Field(
        default=False,
        alias="simulateFailure"
    )


class Order(BaseModel):
    """Заказ пользователя."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1)
    user_id: str = Field(alias="userId", min_length=1)
    created_at: datetime = Field(alias="createdAt")
    items: list[OrderItem]

    status: Literal[
        "PENDING",
        "CONFIRMED",
        "CANCELLED"
    ] = "PENDING"

    total_amount: float | None = Field(
        default=None,
        alias="totalAmount",
        ge=0
    )