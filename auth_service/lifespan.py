from contextlib import asynccontextmanager

from fastapi import FastAPI

from auth_service.registration import bootstrap_admin_from_env
from auth_service.consul import (
    deregister_service,
    register_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём администратора из настроек окружения
    bootstrap_admin_from_env()

    # Регистрируем микросервис в Consul
    await register_service()

    try:
        yield
    finally:
        await deregister_service()