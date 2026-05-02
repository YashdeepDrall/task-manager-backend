from datetime import datetime, timezone
from typing import TypedDict

from bson import ObjectId


class ProjectDocument(TypedDict):
    name: str
    description: str
    createdBy: ObjectId
    members: list[ObjectId]
    createdAt: datetime


def create_project_document(
    *,
    name: str,
    description: str,
    created_by: ObjectId,
) -> ProjectDocument:
    return {
        "name": name,
        "description": description,
        "createdBy": created_by,
        "members": [created_by],
        "createdAt": datetime.now(timezone.utc),
    }


def project_base_out(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "name": document["name"],
        "description": document.get("description", ""),
        "createdBy": str(document["createdBy"]),
        "createdAt": document["createdAt"],
    }
