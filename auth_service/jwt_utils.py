
import os
from datetime import datetime, timedelta, timezone

import jwt


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def get_secret_key():
    secret_key = os.getenv("JWT_SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "Не задан JWT_SECRET_KEY в переменных окружения"
        )

    return secret_key


def create_access_token(user_id, username, role):
    if role not in ("user", "admin"):
        raise ValueError("Недопустимая роль пользователя")

    expiration_time = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expiration_time,
    }

    token = jwt.encode(
        payload,
        get_secret_key(),
        algorithm=ALGORITHM,
    )

    return token


def decode_access_token(token):
    payload = jwt.decode(
        token,
        get_secret_key(),
        algorithms=[ALGORITHM],
        options={
            "require": ["sub", "role", "exp"]
        },
    )

    return payload
