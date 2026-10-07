import os

import httpx


CONSUL_URL = os.getenv(
    "CONSUL_URL",
    "http://consul:8500"
)

SERVICE_NAME = os.getenv(
    "SERVICE_NAME",
    "auth"
)

SERVICE_ID = os.getenv(
    "SERVICE_ID",
    "auth-service"
)

SERVICE_HOST = os.getenv(
    "SERVICE_HOST",
    "auth-service"
)

SERVICE_PORT = int(
    os.getenv("PORT", "8000")
)


async def register_service():
    payload = {
        "Name": SERVICE_NAME,
        "ID": SERVICE_ID,
        "Address": SERVICE_HOST,
        "Port": SERVICE_PORT,
    }

    url = f"{CONSUL_URL}/v1/agent/service/register"

    async with httpx.AsyncClient() as client:
        response = await client.put(
            url,
            json=payload,
        )

        response.raise_for_status()

    print(
        f"Auth Service зарегистрирован в Consul: "
        f"{SERVICE_ID}"
    )


async def deregister_service():
    url = (
        f"{CONSUL_URL}/v1/agent/service/deregister/"
        f"{SERVICE_ID}"
    )

    async with httpx.AsyncClient() as client:
        response = await client.put(url)

        response.raise_for_status()

    print(
        f"Auth Service удален из Consul: "
        f"{SERVICE_ID}"
    )