from datetime import datetime, timedelta, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends

from app.database import get_database
from app.middleware.auth import get_current_user
from app.schemas.dashboard import (
    DashboardOut,
    RecentActivityOut,
    UpcomingDeadlineOut,
)
from app.schemas.user import UserOut


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

TASK_STATUS_KEYS = ("todo", "in-progress", "done")
TASK_PRIORITY_KEYS = ("low", "medium", "high")

UPCOMING_TASK_PROJECTION = {
    "title": 1,
    "projectId": 1,
    "assignedTo": 1,
    "status": 1,
    "priority": 1,
    "deadline": 1,
}


async def task_scope_for(current_user: UserOut) -> tuple[dict, int]:
    db = get_database()

    if current_user.role == "admin":
        total_projects = await db.projects.count_documents({})
        return {}, total_projects

    user_id = ObjectId(current_user.id)
    projects = await db.projects.find(
        {"members": user_id},
        {"_id": 1},
    ).to_list(length=None)
    project_ids = [project["_id"] for project in projects]

    return {
        "projectId": {"$in": project_ids},
        "assignedTo": user_id,
    }, len(project_ids)


async def grouped_counts(
    *,
    match_query: dict,
    field_name: str,
    keys: tuple[str, ...],
) -> dict[str, int]:
    db = get_database()
    counts = dict.fromkeys(keys, 0)
    cursor = db.tasks.aggregate(
        [
            {"$match": match_query},
            {"$group": {"_id": f"${field_name}", "count": {"$sum": 1}}},
        ]
    )

    async for item in cursor:
        if item["_id"] in counts:
            counts[item["_id"]] = item["count"]

    return counts


async def assignee_names(tasks: list[dict]) -> dict[ObjectId, str]:
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


async def recent_activity(match_query: dict) -> list[RecentActivityOut]:
    db = get_database()
    cursor = db.tasks.aggregate(
        [
            {"$match": match_query},
            {"$unwind": "$activityLog"},
            {"$sort": {"activityLog.at": -1}},
            {"$limit": 10},
            {
                "$project": {
                    "_id": 0,
                    "taskId": "$_id",
                    "taskTitle": "$title",
                    "projectId": "$projectId",
                    "action": "$activityLog.action",
                    "by": "$activityLog.by",
                    "byName": "$activityLog.byName",
                    "at": "$activityLog.at",
                }
            },
        ]
    )

    return [
        RecentActivityOut(
            taskId=str(item["taskId"]),
            taskTitle=item["taskTitle"],
            projectId=str(item["projectId"]),
            action=item["action"],
            by=str(item["by"]),
            byName=item["byName"],
            at=item["at"],
        )
        async for item in cursor
    ]


async def upcoming_deadlines(match_query: dict) -> list[UpcomingDeadlineOut]:
    db = get_database()
    now = datetime.now(timezone.utc)
    seven_days_from_now = now + timedelta(days=7)
    query = {
        **match_query,
        "deadline": {"$gte": now, "$lte": seven_days_from_now},
        "status": {"$ne": "done"},
    }
    tasks = await db.tasks.find(
        query,
        UPCOMING_TASK_PROJECTION,
    ).sort("deadline", 1).to_list(length=None)
    names = await assignee_names(tasks)

    return [
        UpcomingDeadlineOut(
            id=str(task["_id"]),
            title=task["title"],
            projectId=str(task["projectId"]),
            assignedTo=str(task["assignedTo"]) if task.get("assignedTo") else None,
            assigneeName=names.get(task.get("assignedTo")),
            status=task["status"],
            priority=task["priority"],
            deadline=task["deadline"],
        )
        for task in tasks
    ]


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> DashboardOut:
    db = get_database()
    task_query, total_projects = await task_scope_for(current_user)
    now = datetime.now(timezone.utc)

    tasks_by_status = await grouped_counts(
        match_query=task_query,
        field_name="status",
        keys=TASK_STATUS_KEYS,
    )
    tasks_by_priority = await grouped_counts(
        match_query=task_query,
        field_name="priority",
        keys=TASK_PRIORITY_KEYS,
    )

    total_tasks = await db.tasks.count_documents(task_query)
    overdue_tasks = await db.tasks.count_documents(
        {
            **task_query,
            "deadline": {"$lt": now},
            "status": {"$ne": "done"},
        }
    )

    return DashboardOut(
        totalProjects=total_projects,
        totalTasks=total_tasks,
        completedTasks=tasks_by_status["done"],
        pendingTasks=tasks_by_status["todo"],
        overdueTasks=overdue_tasks,
        inProgressTasks=tasks_by_status["in-progress"],
        tasksByStatus=tasks_by_status,
        tasksByPriority=tasks_by_priority,
        recentActivity=await recent_activity(task_query),
        upcomingDeadlines=await upcoming_deadlines(task_query),
    )
