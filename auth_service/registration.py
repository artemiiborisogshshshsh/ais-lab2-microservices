from passlib.context import CryptContext
import uuid  # Для уникальных ID


users = {}

# Настройка хеширования паролей через passlib
password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# 'user': user, 'phone': phone, 'email': email, 'password': hashed_password

def user_registration(user, phone, email, password):
    global users

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
    }

    return True