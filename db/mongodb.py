"""
Async MongoDB access via Motor. Exposes a single `db` handle plus a small
repository class (`InterviewRepository`) so route/agent code never talks to
collections directly - keeps query logic in one testable place.
"""
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logger import logger
from app.db.models import Interview

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.mongo_db_name]
    return _db


async def connect_and_ping() -> None:
    client = get_client()
    await client.admin.command("ping")
    logger.info("MongoDB connection OK ({})", settings.mongo_uri)
    await _ensure_indexes()


async def _ensure_indexes() -> None:
    db = get_db()
    await db.interviews.create_index("interview_id", unique=True)
    await db.interviews.create_index("status")
    await db.interviews.create_index("created_at")


async def close_connection() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


class InterviewRepository:
    """All persistence operations for the `interviews` collection."""

    @staticmethod
    async def create(interview: Interview) -> Interview:
        db = get_db()
        await db.interviews.insert_one(interview.to_mongo())
        return interview

    @staticmethod
    async def get(interview_id: str) -> Optional[Interview]:
        db = get_db()
        doc = await db.interviews.find_one({"interview_id": interview_id})
        return Interview.from_mongo(doc) if doc else None

    @staticmethod
    async def replace(interview: Interview) -> Interview:
        db = get_db()
        await db.interviews.replace_one(
            {"interview_id": interview.interview_id}, interview.to_mongo()
        )
        return interview

    @staticmethod
    async def list_recent(limit: int = 20) -> list[Interview]:
        db = get_db()
        cursor = db.interviews.find().sort("created_at", -1).limit(limit)
        return [Interview.from_mongo(doc) async for doc in cursor]

    @staticmethod
    async def delete(interview_id: str) -> bool:
        db = get_db()
        result = await db.interviews.delete_one({"interview_id": interview_id})
        return result.deleted_count > 0
