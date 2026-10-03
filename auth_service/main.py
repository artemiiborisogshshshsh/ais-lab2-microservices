from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from auth_service.registration import user_registration


app = FastAPI(title="Auth Service")


class RegistrationRequest(BaseModel):
    username: str
    phone: str
    email: str
    password: str


@app.post("/register")
def register(data: RegistrationRequest):
    registration_success = user_registration(
        user=data.username,
        phone=data.phone,
        email=data.email,
        password=data.password,
    )

    if not registration_success:
        raise HTTPException(
            status_code=409,
            detail="Пользователь с таким именем или email уже существует",
        )

    return {
        "message": "Пользователь успешно зарегистрирован",
        "username": data.username,
    }