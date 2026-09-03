"""Audit Trail API for end-to-end investigation transparency."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models import AuditEvent
from app.schemas import AuditEventOut, AuditPage

router = APIRouter()


@router.get("", response_model=AuditPage)
async def list_audit_events(
    _user: CurrentUser,
    db: DB,
    page: int = 1,
    page_size: int = 50,
    investigation_id: str | None = None,
    action: str | None = None,
    actor: str | None = None,
):
    query = select(AuditEvent)
    if investigation_id:
        query = query.where(AuditEvent.investigation_id == investigation_id)
    if action:
        query = query.where(AuditEvent.action == action)
    if actor:
        query = query.where(AuditEvent.actor == actor)
    query = query.order_by(AuditEvent.timestamp.desc())

    count_result = await db.execute(select(func.count()).select_from(AuditEvent))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    items = list(result.scalars())

    return AuditPage(
        items=[AuditEventOut.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / max(page_size, 1)),
    )
