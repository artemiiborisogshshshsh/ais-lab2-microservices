from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from auth_service.registration import user_registration
from auth_service.login import login
from auth_service.jwt_utils import create_access_token, decode_access_token
from auth_service.lifespan import lifespan


# Настройка приложения и документации OpenAPI

app = FastAPI(
    title="Auth Service",
    description=(
        "Микросервис регистрации и аутентификации пользователей. "
        "Поддерживает регистрацию, вход с получением JWT "
        "и получение информации о текущем пользователе."
    ),
    version="1.0.0",
    lifespan=lifespan,
    root_path="/auth",
)

security = HTTPBearer()


# Модели входящих данных

class RegistrationRequest(BaseModel):
    username: str = Field(
        ...,
        description="Уникальное имя пользователя",
        examples=["student_demo"],
    )
    phone: str = Field(
        ...,
        description="Номер телефона пользователя",
        examples=["+79990000000"],
    )
    email: str = Field(
        ...,
        description="Электронная почта пользователя",
        examples=["student@example.com"],
    )
    password: str = Field(
        ...,
        description="Пароль пользователя",
        examples=["ExamplePassword123!"],
    )


class LoginRequest(BaseModel):
    username: str = Field(
        ...,
        description="Имя зарегистрированного пользователя",
        examples=["student_demo"],
    )
    password: str = Field(
        ...,
        description="Пароль пользователя",
        examples=["ExamplePassword123!"],
    )


# Модели ответов

class RegistrationResponse(BaseModel):
    message: str
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    user_id: str
    username: str


class ErrorResponse(BaseModel):
    detail: str


# Регистрация пользователя

@app.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Регистрация пользователя",
    description=(
        "Создаёт нового пользователя. "
        "Пароль сохраняется в виде хеша bcrypt. "
        "Если имя пользователя или email уже заняты, "
        "возвращается HTTP 409."
    ),
    responses={
        409: {
            "model": ErrorResponse,
            "description": "Пользователь уже существует",
        },
    },
)
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


# Авторизация пользователя

@app.post(
    "/login",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="Авторизация пользователя",
    description=(
        "Проверяет имя пользователя и пароль. "
        "При успешной авторизации возвращает JWT-токен. "
        "Срок действия токена — 30 минут."
    ),
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Неверное имя пользователя или пароль",
        },
    },
)
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

    access_token = create_access_token(
        user_id=user["user_id"],
        username=user["user_name"],
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# Получение информации о пользователе

@app.get(
    "/me",
    response_model=UserResponse,
    tags=["Authentication"],
    summary="Получение текущего пользователя",
    description=(
        "Возвращает информацию о пользователе "
        "на основе действительного JWT-токена. "
        "Токен передаётся через Authorization: Bearer."
    ),
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Недействительный или просроченный JWT",
        },
        403: {
            "model": ErrorResponse,
            "description": "Отсутствует Bearer-токен",
        },
    },
)
def get_me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    try:
        payload = decode_access_token(credentials.credentials)

        return {
            "user_id": payload["sub"],
            "username": payload["username"],
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или просроченный токен",
        )