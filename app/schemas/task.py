from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


TaskStatus = Literal["todo", "in-progress", "done"]
TaskPriority = Literal["low", "medium", "high"]


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    projectId: str
    assignedTo: str | None = None
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    deadline: datetime | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task title is required")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    assignedTo: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    deadline: datetime | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Task title is required")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip()


class ActivityLogOut(BaseModel):
    action: str
    by: str
    byName: str
    at: datetime


class TaskOut(BaseModel):
    id: str
    title: str
    description: str
    projectId: str
    assignedTo: str | None
    assigneeName: str | None
    status: TaskStatus
    priority: TaskPriority
    deadline: datetime | None
    createdBy: str
    createdAt: datetime


class TaskDetailOut(TaskOut):
    activityLog: list[ActivityLogOut]


class TaskListResponse(BaseModel):
    data: list[TaskOut]
    total: int
    page: int
    limit: int
    totalPages: int
    hasNext: bool
    hasPrev: bool
