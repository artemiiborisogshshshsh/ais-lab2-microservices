import os
import uuid

from fastapi import FastAPI, status
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