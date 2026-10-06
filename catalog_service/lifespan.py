from contextlib import asynccontextmanager

from fastapi import FastAPI

from catalog_service.consul import register_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await register_service()

    yield