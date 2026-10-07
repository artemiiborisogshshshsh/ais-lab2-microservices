from contextlib import asynccontextmanager

from fastapi import FastAPI

from auth_service.consul import (
    deregister_service,
    register_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await register_service()

    try:
        yield
    finally:
        await deregister_service()