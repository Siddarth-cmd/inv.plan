"""Reports download API."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models import Report

router = APIRouter()


@router.get("/{report_id}/download")
async def download_report(report_id: str, _user: CurrentUser, db: DB):
    """Download the PDF report for a given report_id."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.pdf_path or not os.path.exists(report.pdf_path):
        raise HTTPException(status_code=404, detail="PDF not yet generated for this report")
    return FileResponse(
        path=report.pdf_path,
        media_type="application/pdf",
        filename=os.path.basename(report.pdf_path),
    )
