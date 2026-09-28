import bcrypt  # Для паролей
import uuid  # Для уникальных ID

users = {}
# 'user':user, 'phone':phone, 'email':email, 'password':hashed_password


def user_registration(user, phone, email, password):
    global users

    # Проверяем уникальность по правильному ключу "user_name"
    for existing_user in users.values():
        if existing_user["email"] == email or existing_user["user_name"] == user:
            return False

    user_id = str(uuid.uuid4())
    while user_id in users:
        user_id = str(uuid.uuid4())

    password = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed_password = bcrypt.hashpw(password, salt)

    users[user_id] = {
        "user_name": user,
        "phone": phone,
        "email": email,
        "password": hashed_password,
    }
    return True
