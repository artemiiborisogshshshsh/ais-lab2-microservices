import bcrypt
from registration import users

def login(username, password):
    for user_id, user_data in users.items():
        if user_data["user_name"] != username:
            continue
        
        password_bytes = password.encode("utf-8")

        password_is_correct = bcrypt.checkpw(
            password_bytes,
            user_data["hashed_password"]
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