from datetime import datetime, timezone
from typing import Literal, TypedDict


UserRole = Literal["admin", "member"]


class UserDocument(TypedDict):
    name: str
    email: str
    password: str
    role: UserRole
    createdAt: datetime


def create_user_document(
    *,
    name: str,
    email: str,
    password_hash: str,
    role: UserRole,
) -> UserDocument:
    return {
        "name": name,
        "email": email,
        "password": password_hash,
        "role": role,
        "createdAt": datetime.now(timezone.utc),
    }


def user_out(document: dict) -> dict[str, str]:
    return {
        "id": str(document["_id"]),
        "name": document["name"],
        "email": document["email"],
        "role": document["role"],
    }
