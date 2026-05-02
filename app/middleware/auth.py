from typing import Annotated

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.database import get_database
from app.models.user import user_out
from app.schemas.user import UserOut
from app.utils.jwt import decode_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserOut:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            raise ValueError("Invalid token subject")
    except ValueError as exc:
        raise credentials_exception() from exc

    db = get_database()
    user = await db.users.find_one(
        {"_id": ObjectId(user_id)},
        {"password": 0},
    )

    if user is None:
        raise credentials_exception()

    return UserOut(**user_out(user))


def require_admin(
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> UserOut:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required",
        )
    return current_user


def require_member_or_admin(
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> UserOut:
    return current_user
