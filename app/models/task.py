from datetime import datetime, timezone
from typing import Literal, TypedDict

from bson import ObjectId


TaskStatus = Literal["todo", "in-progress", "done"]
TaskPriority = Literal["low", "medium", "high"]


class ActivityLogEntry(TypedDict):
    action: str
    by: ObjectId
    byName: str
    at: datetime


class TaskDocument(TypedDict):
    title: str
    description: str
    projectId: ObjectId
    assignedTo: ObjectId | None
    status: TaskStatus
    priority: TaskPriority
    deadline: datetime | None
    createdBy: ObjectId
    activityLog: list[ActivityLogEntry]
    createdAt: datetime


def activity_entry(
    *,
    action: str,
    by: ObjectId,
    by_name: str,
) -> ActivityLogEntry:
    return {
        "action": action,
        "by": by,
        "byName": by_name,
        "at": datetime.now(timezone.utc),
    }


def create_task_document(
    *,
    title: str,
    description: str,
    project_id: ObjectId,
    assigned_to: ObjectId | None,
    task_status: TaskStatus,
    priority: TaskPriority,
    deadline: datetime | None,
    created_by: ObjectId,
    created_by_name: str,
) -> TaskDocument:
    return {
        "title": title,
        "description": description,
        "projectId": project_id,
        "assignedTo": assigned_to,
        "status": task_status,
        "priority": priority,
        "deadline": deadline,
        "createdBy": created_by,
        "activityLog": [
            activity_entry(
                action=f"Task created by {created_by_name}",
                by=created_by,
                by_name=created_by_name,
            )
        ],
        "createdAt": datetime.now(timezone.utc),
    }


def task_base_out(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "title": document["title"],
        "description": document.get("description", ""),
        "projectId": str(document["projectId"]),
        "assignedTo": str(document["assignedTo"]) if document.get("assignedTo") else None,
        "status": document["status"],
        "priority": document["priority"],
        "deadline": document.get("deadline"),
        "createdBy": str(document["createdBy"]),
        "createdAt": document["createdAt"],
    }
