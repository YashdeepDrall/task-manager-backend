from re import escape
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.database import get_database
from app.middleware.auth import get_current_user, require_admin
from app.models.user import create_user_document, user_out
from app.schemas.user import Token, UserCreate, UserLogin, UserOut
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt import create_access_token


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
)
async def signup(payload: UserCreate) -> Token:
    db = get_database()

    existing_user = await db.users.find_one(
        {"email": payload.email},
        {"_id": 1},
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    user_document = create_user_document(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    try:
        result = await db.users.insert_one(user_document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        ) from exc

    access_token = create_access_token(
        {"sub": str(result.inserted_id), "role": payload.role}
    )
    return Token(access_token=access_token)


@router.post("/login", response_model=Token)
async def login(payload: UserLogin) -> Token:
    db = get_database()
    user = await db.users.find_one(
        {"email": payload.email},
        {"name": 1, "email": 1, "password": 1, "role": 1},
    )

    if user is None or not verify_password(payload.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        {"sub": str(user["_id"]), "role": user["role"]}
    )
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
async def me(
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> UserOut:
    return current_user


@router.get("/users", response_model=list[UserOut])
async def search_users(
    _current_user: Annotated[UserOut, Depends(require_admin)],
    search: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[UserOut]:
    db = get_database()
    query: dict = {}

    if search:
        term = {"$regex": escape(search.strip()), "$options": "i"}
        query = {"$or": [{"name": term}, {"email": term}]}

    users = await db.users.find(
        query,
        {"password": 0},
    ).sort("name", 1).limit(limit).to_list(length=limit)

    return [UserOut(**user_out(user)) for user in users]
