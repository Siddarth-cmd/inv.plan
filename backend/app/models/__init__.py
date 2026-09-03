"""
SQLAlchemy ORM models for FinSpectra.
All models use UUIDs, have timestamps, and enforce foreign key relationships.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ============================================================
# Users / Auth
# ============================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("ADMIN", "INVESTIGATOR", "VIEWER", name="user_role"),
        default="VIEWER",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ============================================================
# Customers
# ============================================================

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    customer_ref: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    kyc_status: Mapped[str] = mapped_column(
        Enum("VERIFIED", "PENDING", "REJECTED", "UNKNOWN", name="kyc_status"),
        default="UNKNOWN",
    )
    risk_profile: Mapped[str] = mapped_column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_profile"),
        default="LOW",
    )
    occupation: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="customer")

    __table_args__ = (Index("ix_customers_phone", "phone"),)


# ============================================================
# Accounts
# ============================================================

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    account_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(
        Enum("SAVINGS", "CURRENT", "WALLET", "UPI", "UNKNOWN", name="account_type"),
        default="SAVINGS",
    )
    bank_name: Mapped[Optional[str]] = mapped_column(String(100))
    upi_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="accounts")
    outgoing_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", foreign_keys="Transaction.from_account_id", back_populates="from_account"
    )
    incoming_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", foreign_keys="Transaction.to_account_id", back_populates="to_account"
    )


# ============================================================
# Transactions
# ============================================================

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    txn_ref: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    from_account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("accounts.id"), index=True)
    to_account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("accounts.id"), index=True)
    from_account_number: Mapped[Optional[str]] = mapped_column(String(50))
    to_account_number: Mapped[Optional[str]] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    channel: Mapped[str] = mapped_column(
        Enum("UPI", "NEFT", "IMPS", "RTGS", "CASH", "ATM", "ONLINE", "UNKNOWN", name="txn_channel"),
        default="UNKNOWN",
    )
    transaction_type: Mapped[str] = mapped_column(
        Enum("CREDIT", "DEBIT", "TRANSFER", name="txn_type"),
        default="TRANSFER",
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    device_id: Mapped[Optional[str]] = mapped_column(String(100))
    location: Mapped[Optional[str]] = mapped_column(String(100))
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    scenario_label: Mapped[Optional[str]] = mapped_column(String(50))  # For synthetic data only

    from_account: Mapped[Optional["Account"]] = relationship(
        "Account", foreign_keys=[from_account_id], back_populates="outgoing_transactions"
    )
    to_account: Mapped[Optional["Account"]] = relationship(
        "Account", foreign_keys=[to_account_id], back_populates="incoming_transactions"
    )


# ============================================================
# Entities (for entity resolution)
# ============================================================

class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    entity_type: Mapped[str] = mapped_column(
        Enum("ACCOUNT", "CUSTOMER", "PHONE", "EMAIL", "UPI_ID", "DEVICE", "IP", name="entity_type"),
        nullable=False,
    )
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_value", name="uq_entity_type_value"),
    )


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    entity_a_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    entity_b_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ============================================================
# Alerts
# ============================================================

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"), index=True)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    rule_signals: Mapped[Optional[dict]] = mapped_column(JSON)
    graph_signals: Mapped[Optional[dict]] = mapped_column(JSON)
    initial_priority: Mapped[str] = mapped_column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="alert_priority"),
        default="MEDIUM",
    )
    status: Mapped[str] = mapped_column(
        Enum("OPEN", "IN_REVIEW", "CLOSED", "ESCALATED", name="alert_status"),
        default="OPEN",
        index=True,
    )
    reasons: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    investigation: Mapped[Optional["Investigation"]] = relationship(
        "Investigation", back_populates="alert", uselist=False
    )


# ============================================================
# Investigations
# ============================================================

class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="investigation_status"),
        default="PENDING",
        index=True,
    )
    created_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    alert: Mapped["Alert"] = relationship("Alert", back_populates="investigation")
    steps: Mapped[list["InvestigationStep"]] = relationship(
        "InvestigationStep", back_populates="investigation", order_by="InvestigationStep.created_at"
    )
    evidence_items: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="investigation")
    risk_assessment: Mapped[Optional["RiskAssessment"]] = relationship(
        "RiskAssessment", back_populates="investigation", uselist=False
    )
    decision: Mapped[Optional["Decision"]] = relationship(
        "Decision", back_populates="investigation", uselist=False
    )
    report: Mapped[Optional["Report"]] = relationship(
        "Report", back_populates="investigation", uselist=False
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="investigation", order_by="AuditEvent.timestamp"
    )


class InvestigationStep(Base):
    __tablename__ = "investigation_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED", name="step_status"),
        default="PENDING",
    )
    output: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="steps")


# ============================================================
# Evidence
# ============================================================

class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_transaction_ids: Mapped[Optional[list]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="evidence_items")


# ============================================================
# Risk Assessment
# ============================================================

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, unique=True, index=True)
    risk_level: Mapped[str] = mapped_column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level"),
        nullable=False,
    )
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    customer_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    network_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    typology_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_factors: Mapped[Optional[list]] = mapped_column(JSON)
    positive_evidence: Mapped[Optional[list]] = mapped_column(JSON)
    negative_evidence: Mapped[Optional[list]] = mapped_column(JSON)
    uncertainties: Mapped[Optional[list]] = mapped_column(JSON)
    narrative: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="risk_assessment")


# ============================================================
# Decision
# ============================================================

class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, unique=True, index=True)
    decision: Mapped[str] = mapped_column(
        Enum("CLEAR", "MONITOR", "ESCALATE", "SAR_RECOMMENDED", "HUMAN_REVIEW", name="decision_outcome"),
        nullable=False,
    )
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    reasons: Mapped[Optional[list]] = mapped_column(JSON)
    supporting_evidence_ids: Mapped[Optional[list]] = mapped_column(JSON)
    required_human_action: Mapped[Optional[str]] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(20), default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="decision")


# ============================================================
# Reports
# ============================================================

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, unique=True, index=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    report_data: Mapped[Optional[dict]] = mapped_column(JSON)
    generated_by: Mapped[str] = mapped_column(String(50), default="system")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="report")


# ============================================================
# Audit Events
# ============================================================

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    investigation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("investigations.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)  # "system" or user_id
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSON)

    investigation: Mapped[Optional["Investigation"]] = relationship("Investigation", back_populates="audit_events")


# ============================================================
# Evidence Dataset (WAF Logs) & Threat Dataset (IP Threat Intel)
# ============================================================

class EvidenceLog(Base):
    __tablename__ = "evidence_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    bytes_in: Mapped[int] = mapped_column(Integer, default=0)
    bytes_out: Mapped[int] = mapped_column(Integer, default=0)
    creation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    src_ip_country_code: Mapped[Optional[str]] = mapped_column(String(10))
    protocol: Mapped[str] = mapped_column(String(20), default="HTTPS")
    response_code: Mapped[int] = mapped_column(Integer, default=200)
    dst_port: Mapped[int] = mapped_column(Integer, default=443)
    dst_ip: Mapped[Optional[str]] = mapped_column(String(45))
    rule_names: Mapped[Optional[str]] = mapped_column(String(255))
    detection_types: Mapped[Optional[str]] = mapped_column(String(100))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ThreatIntel(Base):
    __tablename__ = "threat_intel"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, nullable=False, index=True)
    abuse_confidence_score: Mapped[float] = mapped_column(Float, default=100.0)
    country_code: Mapped[Optional[str]] = mapped_column(String(10))
    country_name: Mapped[Optional[str]] = mapped_column(String(100))
    continent: Mapped[Optional[str]] = mapped_column(String(50))
    reported_date: Mapped[Optional[str]] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(20), default="Critical", index=True)
    severity: Mapped[int] = mapped_column(Integer, default=4)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

