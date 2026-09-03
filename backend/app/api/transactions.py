"""Transaction upload and retrieval API."""
from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.models import Transaction
from app.schemas import IngestionSummary, TransactionOut, TransactionPage
from app.services.ingestion import ingest_csv
from app.services.detection import run_detection

settings = get_settings()
router = APIRouter()


@router.post("/upload", response_model=IngestionSummary, status_code=status.HTTP_201_CREATED)
async def upload_transactions(
    _user: CurrentUser,
    db_session: DB,
    file: UploadFile = File(...),
):
    """Upload a CSV file of transactions. Returns ingestion summary."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.max_upload_size_mb}MB)")

    summary = await ingest_csv(content, db_session, filename=file.filename)
    return summary


@router.post("/upload-evidence", response_model=dict)
async def upload_evidence(
    _user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
):
    """Upload WAF Evidence Logs CSV and trigger detection."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    content = await file.read()
    ingest_summary = await ingest_csv(content, db, filename=file.filename)
    detection_summary = await run_detection(db)
    return {
        "dataset_type": "EVIDENCE_WAF_LOGS",
        "ingestion": ingest_summary.model_dump(),
        "detection": detection_summary,
    }


@router.post("/upload-threat", response_model=dict)
async def upload_threat(
    _user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
):
    """Upload IP Abuse Threat Intelligence CSV and trigger detection."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    content = await file.read()
    ingest_summary = await ingest_csv(content, db, filename=file.filename)
    detection_summary = await run_detection(db)
    return {
        "dataset_type": "THREAT_IP_INTELLIGENCE",
        "ingestion": ingest_summary.model_dump(),
        "detection": detection_summary,
    }


@router.post("/upload-and-detect", response_model=dict)
async def upload_and_detect(
    _user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
):
    """Upload CSV, ingest, then immediately run anomaly detection and create alerts."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.max_upload_size_mb}MB)")

    ingest_summary = await ingest_csv(content, db, filename=file.filename)
    detection_summary = await run_detection(db)

    return {
        "ingestion": ingest_summary.model_dump(),
        "detection": detection_summary,
    }



@router.post("/detect", response_model=dict)
async def trigger_detection(_user: CurrentUser, db: DB):
    """Run anomaly detection on all un-alerted transactions."""
    result = await run_detection(db)
    return result


@router.get("", response_model=TransactionPage)
async def list_transactions(
    _user: CurrentUser,
    db: DB,
    page: int = 1,
    page_size: int = 50,
    flagged_only: bool = False,
):
    """Paginated transaction list."""
    query = select(Transaction)
    if flagged_only:
        query = query.where(Transaction.is_flagged == True)
    query = query.order_by(Transaction.timestamp.desc())

    count_result = await db.execute(select(func.count()).select_from(Transaction))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    items = list(result.scalars())

    return TransactionPage(
        items=[TransactionOut.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size),
    )


@router.get("/{txn_id}", response_model=TransactionOut)
async def get_transaction(txn_id: str, _user: CurrentUser, db: DB):
    result = await db.execute(select(Transaction).where(Transaction.id == txn_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionOut.model_validate(txn)
