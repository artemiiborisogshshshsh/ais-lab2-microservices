from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from auth_service.registration import user_registration
from auth_service.login import login


app = FastAPI(title="Auth Service")


class RegistrationRequest(BaseModel):
    username: str
    phone: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegistrationRequest):
    registration_success = user_registration(
        user=data.username,
        phone=data.phone,
        email=data.email,
        password=data.password,
    )

    if not registration_success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким именем или email уже существует",
        )

    return {
        "message": "Пользователь успешно зарегистрирован",
        "username": data.username,
    }


@app.post("/login")
def login_user(data: LoginRequest):
    user = login(
        username=data.username,
        password=data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )

    return {
        "message": "Вход выполнен успешно",
        "user": user,
    }