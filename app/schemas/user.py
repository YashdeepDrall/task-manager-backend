from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


UserRole = Literal["admin", "member"]


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)
    role: UserRole = "member"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
