"""Liveness/readiness endpoints for orchestration (Docker healthcheck, k8s probes)."""
from fastapi import APIRouter

from app.core.config import settings
from app.db.mongodb import get_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.env}


@router.get("/health/ready")
async def readiness():
    checks = {"mongo": False}
    try:
        await get_client().admin.command("ping")
        checks["mongo"] = True
    except Exception:  # noqa: BLE001
        pass
    ready = all(checks.values())
    return {"ready": ready, "checks": checks}
