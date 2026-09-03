"""Health check router."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check — always returns 200 if the app is running."""
    return {
        "status": "healthy",
        "service": "finspectra",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/health")
async def api_health_check():
    return await health_check()
