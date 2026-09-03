"""
FinSpectra FastAPI Application Entry Point.
Configures CORS, mounts all routers, and manages lifespan events.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import create_tables

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger("finspectra.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup + shutdown."""
    logger.info("FinSpectra starting up", version=settings.app_version, env=settings.environment)
    try:
        await create_tables()
        logger.info("Database tables created/verified")
        await _seed_initial_users()
    except Exception as exc:
        logger.error("Startup error", error=str(exc))
        raise
    yield
    logger.info("FinSpectra shutting down")


async def _seed_initial_users() -> None:
    """Create default dev users if they don't exist."""
    from app.database.session import AsyncSessionLocal
    from app.models import User
    from app.core.security import hash_password
    from sqlalchemy import select

    default_users = [
        {"email": "admin@finspectra.dev", "full_name": "Admin User", "role": "ADMIN", "password": "finspectra_admin"},
        {"email": "investigator@finspectra.dev", "full_name": "Jane Investigator", "role": "INVESTIGATOR", "password": "finspectra_inv"},
        {"email": "viewer@finspectra.dev", "full_name": "View Only", "role": "VIEWER", "password": "finspectra_view"},
    ]

    async with AsyncSessionLocal() as session:
        for u in default_users:
            result = await session.execute(select(User).where(User.email == u["email"]))
            if result.scalar_one_or_none() is None:
                user = User(
                    email=u["email"],
                    full_name=u["full_name"],
                    role=u["role"],
                    hashed_password=hash_password(u["password"]),
                )
                session.add(user)
        await session.commit()
    logger.info("Default users seeded")


async def _seed_initial_dataset() -> None:
    """Auto-seed synthetic, threat, and evidence datasets and run ML detection if alerts are missing."""
    import os
    from app.database.session import AsyncSessionLocal
    from app.models import Alert, Transaction, ThreatIntel, EvidenceLog
    from app.services.ingestion import ingest_csv
    from app.services.detection import run_detection
    from sqlalchemy import func, select, update

    async with AsyncSessionLocal() as session:
        # Check if transactions exist
        count_res = await session.execute(select(func.count()).select_from(Transaction))
        if count_res.scalar_one() == 0:
            raw_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "datasets", "raw"
            ))
            for fname in ["threat_dataset.csv", "evidence_dataset.csv", "synthetic_transactions.csv"]:
                fpath = os.path.join(raw_dir, fname)
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        await ingest_csv(f.read(), session, filename=fname)

        # Ensure open alerts exist
        open_res = await session.execute(select(func.count()).select_from(Alert).where(Alert.status == "OPEN"))
        if open_res.scalar_one() < 5:
            # Reset existing in_review alerts or re-run detection
            await session.execute(
                update(Alert).where(Alert.status == "IN_REVIEW").values(status="OPEN")
            )
            await run_detection(session)
            await session.commit()
            logger.info("Startup dataset ingestion & alert queue reset complete — Open alerts ready")



def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous Financial Crime Investigation Platform",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    from app.api.health import router as health_router
    from app.api.auth import router as auth_router
    from app.api.transactions import router as txn_router
    from app.api.alerts import router as alerts_router
    from app.api.investigations import router as inv_router
    from app.api.reports import router as reports_router
    from app.api.dashboard import router as dashboard_router
    from app.api.audit import router as audit_router
    from app.investigation_planner.api import router as planner_router

    app.include_router(health_router, tags=["Health"])
    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    app.include_router(txn_router, prefix="/api/transactions", tags=["Transactions"])
    app.include_router(alerts_router, prefix="/api/alerts", tags=["Alerts"])
    app.include_router(inv_router, prefix="/api/investigations", tags=["Investigations"])
    app.include_router(planner_router, prefix="/api/investigation-planner", tags=["Investigation Planner"])
    app.include_router(reports_router, prefix="/api/reports", tags=["Reports"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(audit_router, prefix="/api/audit", tags=["Audit"])

    # Mount frontend static build if dist exists
    import os
    from fastapi.staticfiles import StaticFiles
    dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
    if os.path.exists(dist_path):
        app.mount("/", StaticFiles(directory=dist_path, html=True), name="frontend")
        logger.info("Frontend static files mounted", dist_path=dist_path)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        logger.error("Unhandled exception", error=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": "See server logs for details"},
        )

    return app


app = create_app()
