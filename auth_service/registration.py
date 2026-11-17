from passlib.context import CryptContext
import uuid  # Для уникальных ID
import os

users = {}

# Настройка хеширования паролей через passlib
password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# 'user': user, 'phone': phone, 'email': email, 'password': hashed_password

def user_registration(
    user, phone, email, password, role="user"
):
    if role not in ("user", "admin"):
        raise ValueError("Недопустимая роль пользователя")

    # Проверяем уникальность пользователя и email
    for existing_user in users.values():
        if (
            existing_user["email"] == email
            or existing_user["user_name"] == user
        ):
            return False

    # Создаем уникальный ID пользователя
    user_id = str(uuid.uuid4())

    while user_id in users:
        user_id = str(uuid.uuid4())

    # Хешируем пароль через passlib
    hashed_password = password_context.hash(password)

    # Сохраняем пользователя в in-memory хранилище
    users[user_id] = {
        "user_name": user,
        "phone": phone,
        "email": email,
        "password": hashed_password,
        "role": role,
    }

    return True

def bootstrap_admin_from_env():
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME")
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")

    if not any((username, email, password)):
        return False

    if not all((username, email, password)):
        raise RuntimeError(
            "Для создания admin необходимо задать "
            "все три BOOTSTRAP_ADMIN_* переменные"
        )

    return user_registration(
        user=username,
        phone="not-provided",
        email=email,
        password=password,
        role="admin"
    )
