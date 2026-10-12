
"""Модели данных Order Service."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItem(BaseModel):
    """Одна позиция в заказе."""

    model_config = ConfigDict(populate_by_name=True)

    product_id: str = Field(alias="productId", min_length=1)
    quantity: int = Field(gt=0)


class Order(BaseModel):
    """Заказ пользователя."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1)
    user_id: str = Field(alias="userId", min_length=1)
    created_at: datetime = Field(alias="createdAt")
    items: list[OrderItem]
