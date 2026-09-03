"""Alerts API."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, CurrentUser
from app.models import Alert
from app.schemas import AlertOut, AlertPage

router = APIRouter()


@router.get("", response_model=AlertPage)
async def list_alerts(
    _user: CurrentUser,
    db: DB,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    priority: str | None = None,
):
    query = select(Alert)
    if status:
        query = query.where(Alert.status == status.upper())
    if priority:
        query = query.where(Alert.initial_priority == priority.upper())
    query = query.order_by(Alert.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(Alert))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    items = list(result.scalars())

    return AlertPage(
        items=[AlertOut.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / max(page_size, 1)),
    )


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: str, _user: CurrentUser, db: DB):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertOut.model_validate(alert)
