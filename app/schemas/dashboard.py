from datetime import datetime

from pydantic import BaseModel

from app.schemas.task import TaskPriority, TaskStatus


class RecentActivityOut(BaseModel):
    taskId: str
    taskTitle: str
    projectId: str
    action: str
    by: str
    byName: str
    at: datetime


class UpcomingDeadlineOut(BaseModel):
    id: str
    title: str
    projectId: str
    assignedTo: str | None
    assigneeName: str | None
    status: TaskStatus
    priority: TaskPriority
    deadline: datetime


class DashboardOut(BaseModel):
    totalProjects: int
    totalTasks: int
    completedTasks: int
    pendingTasks: int
    overdueTasks: int
    inProgressTasks: int
    tasksByStatus: dict[str, int]
    tasksByPriority: dict[str, int]
    recentActivity: list[RecentActivityOut]
    upcomingDeadlines: list[UpcomingDeadlineOut]
