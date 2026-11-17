
from auth_service.registration import users, password_context


def login(email: str, password: str):
    for user_id, user_data in users.items():

        # Ищем пользователя по электронной почте
        if user_data["email"].casefold() != email.strip().casefold():
            continue

        # Сравниваем пароль с сохранённым bcrypt-хешем
        password_is_correct = password_context.verify(
            password,
            user_data["password"]
        )

        if not password_is_correct:
            return None

        # Возвращаем информацию для создания JWT
        return {
            "user_id": user_id,
            "user_name": user_data["user_name"],
            "email": user_data["email"],
            "role": user_data.get("role", "user")
        }

    return None
