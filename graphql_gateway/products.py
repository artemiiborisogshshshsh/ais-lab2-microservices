
import os
import asyncio
from strawberry.dataloader import DataLoader
import httpx
import strawberry

from graphql import GraphQLError


CATALOG_SERVICE_URL = os.getenv(
    "CATALOG_SERVICE_URL",
    "http://127.0.0.1:8001"
).rstrip("/")


@strawberry.type(description="Товар из Catalog Service")
class Product:
    id: strawberry.ID = strawberry.field(
        description="Уникальный идентификатор товара"
    )
    name: str = strawberry.field(
        description="Название товара"
    )
    price: float = strawberry.field(
        description="Цена товара"
    )


async def fetch_product_by_id(
    product_id: str,
    client: httpx.AsyncClient,
) -> Product:

    url = f"{CATALOG_SERVICE_URL}/products/{product_id}"

    try:
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()

        return Product(
            id=strawberry.ID(str(data["id"])),
            name=data["name"],
            price=float(data["price"]),
        )

    except httpx.HTTPStatusError as exc:
        raise GraphQLError(
            f"Catalog вернул HTTP "
            f"{exc.response.status_code} "
            f"для товара {product_id}"
        ) from exc

    except httpx.RequestError as exc:
        raise GraphQLError(
            "Не удалось подключиться к Catalog Service"
        ) from exc

    except (KeyError, TypeError, ValueError) as exc:
        raise GraphQLError(
            "Catalog вернул некорректные данные товара"
        ) from exc

async def load_products(
    product_ids: list[str],
) -> list[Product | Exception]:

    async with httpx.AsyncClient(timeout=5.0) as client:
        results = await asyncio.gather(
            *[
                fetch_product_by_id(product_id, client)
                for product_id in product_ids
            ],
            return_exceptions=True,
        )

    return list(results)

def create_product_loader() -> DataLoader[str, Product]:
    return DataLoader(load_fn=load_products)
