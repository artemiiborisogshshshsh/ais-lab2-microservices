import os
import uuid

from fastapi import FastAPI, status,  HTTPException
from pydantic import BaseModel


app = FastAPI(title="Catalog Service")

INSTANCE_NAME = os.getenv("INSTANCE_NAME", "catalog-local")

products = {}


class ProductRequest(BaseModel):
    name: str
    price: float


@app.get("/products")
def get_products():
    return {
        "instance_id": INSTANCE_NAME,
        "products": list(products.values()),
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