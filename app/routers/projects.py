from math import ceil
from re import escape
from typing import Annotated, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo import ASCENDING, DESCENDING

from app.database import get_database
from app.middleware.auth import get_current_user, require_admin
from app.models.project import create_project_document, project_base_out
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailOut,
    ProjectListResponse,
    ProjectMemberAdd,
    ProjectOut,
)
from app.schemas.user import UserOut


router = APIRouter(prefix="/projects", tags=["Projects"])

PROJECT_PROJECTION = {
    "name": 1,
    "description": 1,
    "createdBy": 1,
    "members": 1,
    "createdAt": 1,
}


def parse_object_id(value: str, field_name: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}",
        )
    return ObjectId(value)


def paginated_response(
    *,
    data: list[ProjectOut],
    total: int,
    page: int,
    limit: int,
) -> ProjectListResponse:
    total_pages = ceil(total / limit) if total else 0
    return ProjectListResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


async def build_project_list_items(
    projects: list[dict],
) -> list[ProjectOut]:
    if not projects:
        return []

    db = get_database()
    project_ids = [project["_id"] for project in projects]
    creator_ids = list({project["createdBy"] for project in projects})

    creators = await db.users.find(
        {"_id": {"$in": creator_ids}},
        {"name": 1},
    ).to_list(length=None)
    creator_names = {
        creator["_id"]: creator.get("name", "Unknown user") for creator in creators
    }

    task_counts_cursor = db.tasks.aggregate(
        [
            {"$match": {"projectId": {"$in": project_ids}}},
            {"$group": {"_id": "$projectId", "count": {"$sum": 1}}},
        ]
    )
    task_counts = {
        item["_id"]: item["count"]
        async for item in task_counts_cursor
    }

    return [
        ProjectOut(
            **project_base_out(project),
            memberCount=len(project.get("members", [])),
            taskCount=task_counts.get(project["_id"], 0),
            creatorName=creator_names.get(project["createdBy"], "Unknown user"),
        )
        for project in projects
    ]


async def ensure_project_access(
    project_id: ObjectId,
    current_user: UserOut,
) -> dict:
    db = get_database()
    query = {"_id": project_id}

    if current_user.role != "admin":
        query["members"] = ObjectId(current_user.id)

    project = await db.projects.find_one(query, PROJECT_PROJECTION)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


async def build_project_detail(project: dict) -> ProjectDetailOut:
    db = get_database()
    list_items = await build_project_list_items([project])
    member_ids = project.get("members", [])
    members = await db.users.find(
        {"_id": {"$in": member_ids}},
        {"name": 1, "role": 1},
    ).to_list(length=None)
    member_order = {member_id: index for index, member_id in enumerate(member_ids)}
    members.sort(key=lambda member: member_order.get(member["_id"], 0))

    return ProjectDetailOut(
        **list_items[0].model_dump(),
        members=[
            {
                "id": str(member["_id"]),
                "name": member["name"],
                "role": member["role"],
            }
            for member in members
        ],
    )


@router.post(
    "",
    response_model=ProjectDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate,
    current_user: Annotated[UserOut, Depends(require_admin)],
) -> ProjectDetailOut:
    db = get_database()
    project_document = create_project_document(
        name=payload.name,
        description=payload.description,
        created_by=ObjectId(current_user.id),
    )
    result = await db.projects.insert_one(project_document)
    created_project = await db.projects.find_one(
        {"_id": result.inserted_id},
        PROJECT_PROJECTION,
    )

    if created_project is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project was created but could not be loaded",
        )

    return await build_project_detail(created_project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: Annotated[UserOut, Depends(get_current_user)],
    search: str | None = Query(default=None, min_length=1),
    sort: Literal["createdAt", "-createdAt", "name", "-name"] = "-createdAt",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
) -> ProjectListResponse:
    db = get_database()
    query: dict = {}

    if current_user.role != "admin":
        query["members"] = ObjectId(current_user.id)

    if search:
        term = {"$regex": escape(search.strip()), "$options": "i"}
        query["$or"] = [{"name": term}, {"description": term}]

    sort_field = sort.lstrip("-")
    sort_direction = DESCENDING if sort.startswith("-") else ASCENDING
    skip = (page - 1) * limit

    total = await db.projects.count_documents(query)
    projects = await db.projects.find(
        query,
        PROJECT_PROJECTION,
    ).sort(sort_field, sort_direction).skip(skip).limit(limit).to_list(length=limit)

    return paginated_response(
        data=await build_project_list_items(projects),
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{project_id}", response_model=ProjectDetailOut)
async def get_project(
    project_id: str,
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> ProjectDetailOut:
    project = await ensure_project_access(
        parse_object_id(project_id, "project ID"),
        current_user,
    )
    return await build_project_detail(project)


@router.post(
    "/{project_id}/members",
    response_model=ProjectDetailOut,
)
async def add_project_member(
    project_id: str,
    payload: ProjectMemberAdd,
    _current_user: Annotated[UserOut, Depends(require_admin)],
) -> ProjectDetailOut:
    db = get_database()
    project_object_id = parse_object_id(project_id, "project ID")
    user_object_id = parse_object_id(payload.userId, "user ID")

    user = await db.users.find_one(
        {"_id": user_object_id},
        {"_id": 1},
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_result = await db.projects.update_one(
        {"_id": project_object_id},
        {"$addToSet": {"members": user_object_id}},
    )
    if update_result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project = await db.projects.find_one(
        {"_id": project_object_id},
        PROJECT_PROJECTION,
    )
    return await build_project_detail(project)


@router.delete(
    "/{project_id}/members/{user_id}",
    response_model=ProjectDetailOut,
)
async def remove_project_member(
    project_id: str,
    user_id: str,
    _current_user: Annotated[UserOut, Depends(require_admin)],
) -> ProjectDetailOut:
    db = get_database()
    project_object_id = parse_object_id(project_id, "project ID")
    user_object_id = parse_object_id(user_id, "user ID")

    update_result = await db.projects.update_one(
        {"_id": project_object_id},
        {"$pull": {"members": user_object_id}},
    )
    if update_result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project = await db.projects.find_one(
        {"_id": project_object_id},
        PROJECT_PROJECTION,
    )
    return await build_project_detail(project)
