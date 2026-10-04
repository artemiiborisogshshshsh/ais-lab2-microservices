from auth_service.registration import users, password_context


def login(username, password):
    for user_id, user_data in users.items():
        if user_data["user_name"] != username:
            continue

        password_is_correct = password_context.verify(
            password,
            user_data["password"]
        )

        if password_is_correct:
            return {
                "user_id": user_id,
                "user_name": user_data["user_name"],
                "phone": user_data["phone"],
                "email": user_data["email"]
            }

        return None

    return None