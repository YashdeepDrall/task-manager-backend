from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.config import settings


client: Optional[AsyncIOMotorClient] = None
database: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongo() -> AsyncIOMotorDatabase:
    global client, database

    if database is not None:
        return database

    client = AsyncIOMotorClient(settings.mongo_uri)
    database = client[settings.db_name]
    await client.admin.command("ping")
    await create_indexes(database)
    return database


async def close_mongo_connection() -> None:
    global client, database

    if client is not None:
        client.close()

    client = None
    database = None


def get_database() -> AsyncIOMotorDatabase:
    if database is None:
        raise RuntimeError("Database connection has not been initialized")
    return database


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index([("email", ASCENDING)], unique=True)

    await db.tasks.create_index([("projectId", ASCENDING)])
    await db.tasks.create_index([("assignedTo", ASCENDING)])
    await db.tasks.create_index([("status", ASCENDING)])
    await db.tasks.create_index([("deadline", ASCENDING)])

    await db.projects.create_index([("createdBy", ASCENDING)])
    await db.projects.create_index([("members", ASCENDING)])
