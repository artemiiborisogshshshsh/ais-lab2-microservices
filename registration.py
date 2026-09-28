import bcrypt
# user, phone, email, password
users = {}
import uuid
def userRegistrarion(user, phone, email, password):
    global users

    for existing_user in users.values():
        if existing_user["email"] == email or existing_user["username"] == user:
            return False

    user_id = str(uuid.uuid4())
    while user_id in users:
        user_id = str(uuid.uuid4())


    password = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed_password = bcrypt.hashpw(password, salt)
    users[user_id] = {user, phone, email, hashed_password}
    return True
