from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserRole


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()


class ProjectMemberAdd(BaseModel):
    userId: str


class ProjectMemberOut(BaseModel):
    id: str
    name: str
    role: UserRole


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    createdBy: str
    createdAt: datetime
    memberCount: int
    taskCount: int
    creatorName: str


class ProjectDetailOut(ProjectOut):
    members: list[ProjectMemberOut]


class ProjectListResponse(BaseModel):
    data: list[ProjectOut]
    total: int
    page: int
    limit: int
    totalPages: int
    hasNext: bool
    hasPrev: bool
