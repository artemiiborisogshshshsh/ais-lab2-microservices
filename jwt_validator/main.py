import os

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI(title="JWT Validator")

security = HTTPBearer(auto_error=False)


@app.get("/internal/validate")
def validate_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
        )

    secret_key = os.getenv("JWT_SECRET_KEY")

    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret_key,
            algorithms=["HS256"],
            options={"require": ["sub", "role", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired JWT",
        )

    user_id = payload.get("sub")
    role = payload.get("role")

    if (
        not isinstance(user_id, str)
        or not user_id
        or role not in ("user", "admin")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid JWT claims",
        )

    return Response(
        status_code=204,
        headers={
            "X-User-Id": user_id,
            "X-User-Role": role,
        },
    )