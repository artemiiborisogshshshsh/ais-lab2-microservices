import strawberry

from graphql_gateway.orders import (
    Order,
    fetch_orders_by_user_id
)


@strawberry.type
class Query:

    @strawberry.field(
        description="Проверка работоспособности GraphQL Gateway"
    )
    def health(self) -> str:
        return "GraphQL Gateway работает"

    @strawberry.field(
        description="Получение заказов пользователя из Order Service"
    )
    async def orders_by_user_id(
        self,
        user_id: str
    ) -> list[Order]:

        return await fetch_orders_by_user_id(user_id)


schema = strawberry.Schema(query=Query)