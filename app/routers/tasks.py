from datetime import datetime, timezone
from math import ceil
from re import escape
from typing import Annotated, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pymongo import ASCENDING, DESCENDING

from app.database import get_database
from app.middleware.auth import get_current_user, require_admin
from app.models.task import activity_entry, create_task_document, task_base_out
from app.schemas.task import (
    ActivityLogOut,
    TaskCreate,
    TaskDetailOut,
    TaskListResponse,
    TaskOut,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)
from app.schemas.user import UserOut


router = APIRouter(prefix="/tasks", tags=["Tasks"])

TASK_LIST_PROJECTION = {
    "title": 1,
    "description": 1,
    "projectId": 1,
    "assignedTo": 1,
    "status": 1,
    "priority": 1,
    "deadline": 1,
    "createdBy": 1,
    "createdAt": 1,
}

TASK_DETAIL_PROJECTION = {
    **TASK_LIST_PROJECTION,
    "activityLog": 1,
}

PROJECT_ACCESS_PROJECTION = {
    "members": 1,
}


def parse_object_id(value: str, field_name: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}",
        )
    return ObjectId(value)


def paginated_response(
    *,
    data: list[TaskOut],
    total: int,
    page: int,
    limit: int,
) -> TaskListResponse:
    total_pages = ceil(total / limit) if total else 0
    return TaskListResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


async def ensure_project_access(
    project_id: ObjectId,
    current_user: UserOut,
    *,
    detail: str = "Project not found",
) -> dict:
    db = get_database()
    query: dict = {"_id": project_id}

    if current_user.role != "admin":
        query["members"] = ObjectId(current_user.id)

    project = await db.projects.find_one(query, PROJECT_ACCESS_PROJECTION)
    if project is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=detail,
        )

    return project


async def validate_assignee(assigned_to: str | None) -> ObjectId | None:
    if assigned_to is None:
        return None

    db = get_database()
    assignee_id = parse_object_id(assigned_to, "assignee ID")
    user = await db.users.find_one(
        {"_id": assignee_id},
        {"_id": 1},
    )
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Assigned user not found",
        )

    return assignee_id


async def assignee_names_for(tasks: list[dict]) -> dict[ObjectId, str]:
    assignee_ids = list(
        {
            task["assignedTo"]
            for task in tasks
            if task.get("assignedTo") is not None
        }
    )
    if not assignee_ids:
        return {}

    db = get_database()
    users = await db.users.find(
        {"_id": {"$in": assignee_ids}},
        {"name": 1},
    ).to_list(length=None)
    return {user["_id"]: user["name"] for user in users}


def serialize_activity_log(entries: list[dict]) -> list[ActivityLogOut]:
    return [
        ActivityLogOut(
            action=entry["action"],
            by=str(entry["by"]),
            byName=entry["byName"],
            at=entry["at"],
        )
        for entry in entries
    ]


async def build_task_items(tasks: list[dict]) -> list[TaskOut]:
    names = await assignee_names_for(tasks)
    return [
        TaskOut(
            **task_base_out(task),
            assigneeName=names.get(task.get("assignedTo")),
        )
        for task in tasks
    ]


async def build_task_detail(task: dict) -> TaskDetailOut:
    list_item = (await build_task_items([task]))[0]
    return TaskDetailOut(
        **list_item.model_dump(),
        activityLog=serialize_activity_log(task.get("activityLog", [])),
    )


def sort_options(sort: str) -> tuple[str, int]:
    direction = DESCENDING if sort.startswith("-") else ASCENDING
    return sort.lstrip("-"), direction


async def get_task_or_404(task_id: ObjectId) -> dict:
    db = get_database()
    task = await db.tasks.find_one({"_id": task_id}, TASK_DETAIL_PROJECTION)
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


async def assignee_label(assignee_id: ObjectId | None) -> str:
    if assignee_id is None:
        return "Unassigned"

    db = get_database()
    user = await db.users.find_one(
        {"_id": assignee_id},
        {"name": 1},
    )
    return user["name"] if user else "Unknown user"


async def change_message(
    *,
    field: str,
    old_value,
    new_value,
    actor_name: str,
) -> str:
    labels = {
        "title": "Title",
        "description": "Description",
        "assignedTo": "Assignee",
        "status": "Status",
        "priority": "Priority",
        "deadline": "Deadline",
    }

    if field == "description":
        return f"Description updated by {actor_name}"

    if field == "assignedTo":
        old_label = await assignee_label(old_value)
        new_label = await assignee_label(new_value)
    elif field == "deadline":
        old_label = old_value.isoformat() if old_value else "none"
        new_label = new_value.isoformat() if new_value else "none"
    else:
        old_label = str(old_value)
        new_label = str(new_value)

    return f"{labels[field]} changed from {old_label} to {new_label} by {actor_name}"


@router.post(
    "",
    response_model=TaskDetailOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_task(
    payload: TaskCreate,
    current_user: Annotated[UserOut, Depends(require_admin)],
) -> TaskDetailOut:
    db = get_database()
    project_id = parse_object_id(payload.projectId, "project ID")
    project = await db.projects.find_one(
        {"_id": project_id},
        {"_id": 1},
    )
    if project is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    assigned_to = await validate_assignee(payload.assignedTo)
    task_document = create_task_document(
        title=payload.title,
        description=payload.description,
        project_id=project_id,
        assigned_to=assigned_to,
        task_status=payload.status,
        priority=payload.priority,
        deadline=payload.deadline,
        created_by=ObjectId(current_user.id),
        created_by_name=current_user.name,
    )
    result = await db.tasks.insert_one(task_document)
    task = await db.tasks.find_one(
        {"_id": result.inserted_id},
        TASK_DETAIL_PROJECTION,
    )
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task was created but could not be loaded",
        )

    return await build_task_detail(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    current_user: Annotated[UserOut, Depends(get_current_user)],
    project_id: str = Query(..., alias="projectId"),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    assigned_to: str | None = Query(default=None, alias="assignedTo"),
    priority: TaskPriority | None = None,
    search: str | None = Query(default=None, min_length=1),
    overdue: bool = False,
    sort: Literal["deadline", "-deadline", "createdAt", "-createdAt"] = "-createdAt",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    my_tasks: bool = Query(default=False, alias="myTasks"),
) -> TaskListResponse:
    db = get_database()
    project_object_id = parse_object_id(project_id, "project ID")
    await ensure_project_access(project_object_id, current_user)

    query: dict = {"projectId": project_object_id}

    if status_filter:
        query["status"] = status_filter

    if assigned_to:
        query["assignedTo"] = parse_object_id(assigned_to, "assignee ID")

    if current_user.role != "admin" and my_tasks:
        query["assignedTo"] = ObjectId(current_user.id)

    if priority:
        query["priority"] = priority

    if search:
        query["title"] = {"$regex": escape(search.strip()), "$options": "i"}

    if overdue:
        query["deadline"] = {"$lt": datetime.now(timezone.utc)}
        if status_filter == "done":
            query["status"] = {"$eq": "done", "$ne": "done"}
        elif not status_filter:
            query["status"] = {"$ne": "done"}

    sort_field, sort_direction = sort_options(sort)
    skip = (page - 1) * limit
    total = await db.tasks.count_documents(query)
    tasks = await db.tasks.find(
        query,
        TASK_LIST_PROJECTION,
    ).sort(sort_field, sort_direction).skip(skip).limit(limit).to_list(length=limit)

    return paginated_response(
        data=await build_task_items(tasks),
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{task_id}", response_model=TaskDetailOut)
async def get_task(
    task_id: str,
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> TaskDetailOut:
    task = await get_task_or_404(parse_object_id(task_id, "task ID"))
    await ensure_project_access(
        task["projectId"],
        current_user,
        detail="Task not found",
    )
    return await build_task_detail(task)


@router.patch("/{task_id}", response_model=TaskDetailOut)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> TaskDetailOut:
    db = get_database()
    task_object_id = parse_object_id(task_id, "task ID")
    task = await get_task_or_404(task_object_id)
    await ensure_project_access(
        task["projectId"],
        current_user,
        detail="Task not found",
    )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    if current_user.role != "admin":
        if task.get("assignedTo") != ObjectId(current_user.id):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Members can update only tasks assigned to them",
            )
        if set(updates) != {"status"}:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Members can update only the status field",
            )

    if "assignedTo" in updates:
        updates["assignedTo"] = await validate_assignee(updates["assignedTo"])

    changed_fields = {
        field: value
        for field, value in updates.items()
        if task.get(field) != value
    }
    if not changed_fields:
        return await build_task_detail(task)

    activity_log = [
        activity_entry(
            action=await change_message(
                field=field,
                old_value=task.get(field),
                new_value=value,
                actor_name=current_user.name,
            ),
            by=ObjectId(current_user.id),
            by_name=current_user.name,
        )
        for field, value in changed_fields.items()
    ]

    await db.tasks.update_one(
        {"_id": task_object_id},
        {
            "$set": changed_fields,
            "$push": {"activityLog": {"$each": activity_log}},
        },
    )
    updated_task = await get_task_or_404(task_object_id)
    return await build_task_detail(updated_task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    _current_user: Annotated[UserOut, Depends(require_admin)],
) -> dict[str, str]:
    db = get_database()
    task_object_id = parse_object_id(task_id, "task ID")
    result = await db.tasks.delete_one({"_id": task_object_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return {"detail": "Task deleted"}
