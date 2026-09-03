"""
Pydantic schemas for all API boundaries.
These are separate from SQLAlchemy models to maintain clean separation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ============================================================
# Base
# ============================================================

class BaseResponse(BaseModel):
    model_config = {"from_attributes": True}


# ============================================================
# Auth
# ============================================================

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str
    full_name: str


class UserOut(BaseResponse):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


# ============================================================
# Transactions
# ============================================================

class TransactionOut(BaseResponse):
    id: str
    txn_ref: str
    from_account_number: Optional[str]
    to_account_number: Optional[str]
    amount: float
    currency: str
    channel: str
    transaction_type: str
    timestamp: datetime
    description: Optional[str]
    is_flagged: bool
    scenario_label: Optional[str]
    ingested_at: datetime


class IngestionSummary(BaseModel):
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    duplicate_rows: int
    flagged_rows: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int
    pages: int


# ============================================================
# Alerts
# ============================================================

class AlertOut(BaseResponse):
    id: str
    transaction_id: str
    customer_id: Optional[str]
    anomaly_score: float
    rule_signals: Optional[Any]
    graph_signals: Optional[Any]
    initial_priority: str
    status: str
    reasons: Optional[list]
    created_at: datetime
    updated_at: datetime


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int
    page: int
    page_size: int
    pages: int


# ============================================================
# Investigations
# ============================================================

class InvestigationCreate(BaseModel):
    alert_id: str


class InvestigationOut(BaseResponse):
    id: str
    alert_id: str
    status: str
    created_by: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


class InvestigationDetail(InvestigationOut):
    steps: list[StepOut] = Field(default_factory=list)
    evidence_items: list[EvidenceOut] = Field(default_factory=list)
    risk_assessment: Optional[RiskAssessmentOut] = None
    decision: Optional[DecisionOut] = None
    report: Optional[ReportOut] = None


class StepOut(BaseResponse):
    id: str
    step_name: str
    status: str
    output: Optional[dict]
    error_message: Optional[str]
    duration_ms: Optional[int]
    created_at: datetime


class EvidenceOut(BaseResponse):
    id: str
    evidence_type: str
    source: str
    source_record_id: Optional[str]
    description: str
    supporting_transaction_ids: Optional[list]
    confidence: float
    is_external: bool
    created_at: datetime


class RiskAssessmentOut(BaseResponse):
    id: str
    risk_level: str
    composite_score: float
    transaction_risk_score: float
    customer_risk_score: float
    network_risk_score: float
    typology_risk_score: float
    risk_factors: Optional[list]
    positive_evidence: Optional[list]
    negative_evidence: Optional[list]
    uncertainties: Optional[list]
    narrative: Optional[str]
    created_at: datetime


class DecisionOut(BaseResponse):
    id: str
    decision: str
    risk_level: str
    reasons: Optional[list]
    required_human_action: Optional[str]
    policy_version: str
    created_at: datetime


class ReportOut(BaseResponse):
    id: str
    investigation_id: str
    generated_by: str
    llm_used: bool
    created_at: datetime


# ============================================================
# Audit
# ============================================================

class AuditEventOut(BaseResponse):
    id: str
    investigation_id: Optional[str]
    timestamp: datetime
    actor: str
    action: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    summary: str
    extra_metadata: Optional[dict] = Field(None, alias="metadata")


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    total: int
    page: int
    page_size: int
    pages: int


# ============================================================
# Dashboard
# ============================================================

class DashboardSummary(BaseModel):
    total_transactions: int
    flagged_transactions: int
    open_alerts: int
    high_priority_alerts: int
    active_investigations: int
    completed_investigations: int
    sar_recommended: int
    risk_distribution: dict[str, int]
    alert_trend: list[dict[str, Any]]
    recent_alerts: list[AlertOut]


# ============================================================
# Graph
# ============================================================

class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    label: str
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metrics: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Error responses
# ============================================================

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# Forward refs
InvestigationDetail.model_rebuild()
