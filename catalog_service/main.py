import os
import uuid

from fastapi import FastAPI, status, HTTPException, Query
from pydantic import BaseModel
from catalog_service.lifespan import lifespan


app = FastAPI(
    title="Catalog Service",
    lifespan=lifespan,
)

INSTANCE_NAME = os.getenv("INSTANCE_NAME", "catalog-local")


INITIAL_PRODUCTS = [
    {
        "id": "00000000-0000-4000-8000-000000000001",
        "name": "Ноутбук",
        "price": 75000.0,
    },
    {
        "id": "00000000-0000-4000-8000-000000000002",
        "name": "Мышь",
        "price": 1500.0,
    },
    {
        "id": "00000000-0000-4000-8000-000000000003",
        "name": "Клавиатура",
        "price": 3500.0,
    },
]

products = {
    product["id"]: product.copy()
    for product in INITIAL_PRODUCTS
}



class ProductRequest(BaseModel):
    name: str
    price: float



@app.get(
    "/products",
    summary="Получить список товаров",
    description="Возвращает список товаров с поддержкой пагинации.",
)
def get_products(
    skip: int = Query(
        default=0,
        ge=0,
        description="Количество пропускаемых товаров",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Максимальное количество товаров",
    ),
):
    all_products = list(products.values())

    paginated_products = all_products[skip:skip + limit]

    return {
        "instance_id": INSTANCE_NAME,
        "products": paginated_products,
    }



@app.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(data: ProductRequest):
    product_id = str(uuid.uuid4())

    product = {
        "id": product_id,
        "name": data.name,
        "price": data.price,
    }

    products[product_id] = product

    return product

@app.put("/products/{product_id}")
def update_product(product_id: str, data: ProductRequest):
    if product_id not in products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        )

    products[product_id] = {
        "id": product_id,
        "name": data.name,
        "price": data.price,
    }

    return products[product_id]

@app.delete("/products/{product_id}")
def delete_product(product_id: str):
    if product_id not in products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        )

    deleted_product = products.pop(product_id)

    return {
        "message": "Товар успешно удален",
        "product": deleted_product,
    }

@app.get(
    "/products/{product_id}",
    summary="Получить товар по ID",
    description="Возвращает информацию об одном товаре из каталога.",
    responses={
        404: {"description": "Товар не найден"}
    },
)
def get_product(product_id: str):
    product = products.get(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        )

    return product
