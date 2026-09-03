"""
InvestigationState — The fully-typed LangGraph state for a FinSpectra investigation.

Architecture:
  invest.planner → Investigation Plan → Hypothesis → Evidence Retrieval
  → Analysis → Adaptive Planner → (REPLAN | STOP) → Decision → Report

Traceability chain:
  case_id → plan_id → step_id → evidence_id → finding_id → decision_id

One LangGraph thread per case (thread_id = case_id).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# Sub-models for Plan (validated Pydantic)
# ============================================================

class EvidenceType(str, Enum):
    TRANSACTION_HISTORY = "TRANSACTION_HISTORY"
    ACCOUNT_PROFILE = "ACCOUNT_PROFILE"
    ENTITY_RELATIONSHIP = "ENTITY_RELATIONSHIP"
    GRAPH_CENTRALITY = "GRAPH_CENTRALITY"
    GRAPH_CYCLES = "GRAPH_CYCLES"
    TYPOLOGY_MATCH = "TYPOLOGY_MATCH"
    ANOMALY_SCORE = "ANOMALY_SCORE"
    RULE_SIGNAL = "RULE_SIGNAL"
    COUNTERPARTY_ANALYSIS = "COUNTERPARTY_ANALYSIS"
    TEMPORAL_PATTERN = "TEMPORAL_PATTERN"
    AMOUNT_PATTERN = "AMOUNT_PATTERN"
    DEVICE_FINGERPRINT = "DEVICE_FINGERPRINT"


class ToolPreference(str, Enum):
    GRAPH_QUERY = "GRAPH_QUERY"           # GraphQueryTool (NetworkX / Neo4j)
    DB_QUERY = "DB_QUERY"                  # DatabaseQueryTool
    TYPOLOGY_MATCH = "TYPOLOGY_MATCH"     # TypologyMatchTool
    SIGNAL_COMPUTE = "SIGNAL_COMPUTE"     # Re-compute ML signals
    NONE = "NONE"                          # No specific tool


class PlanStepAction(str, Enum):
    GATHER_TRANSACTION_HISTORY = "GATHER_TRANSACTION_HISTORY"
    RESOLVE_ENTITIES = "RESOLVE_ENTITIES"
    BUILD_RELATIONSHIP_GRAPH = "BUILD_RELATIONSHIP_GRAPH"
    DETECT_GRAPH_CYCLES = "DETECT_GRAPH_CYCLES"
    COMPUTE_CENTRALITY = "COMPUTE_CENTRALITY"
    MATCH_TYPOLOGIES = "MATCH_TYPOLOGIES"
    ANALYZE_AMOUNT_PATTERNS = "ANALYZE_AMOUNT_PATTERNS"
    ANALYZE_TEMPORAL_PATTERNS = "ANALYZE_TEMPORAL_PATTERNS"
    ASSESS_COUNTERPARTIES = "ASSESS_COUNTERPARTIES"
    EVALUATE_DEVICE_SIGNALS = "EVALUATE_DEVICE_SIGNALS"
    SYNTHESIZE_FINDINGS = "SYNTHESIZE_FINDINGS"
    GENERATE_DECISION = "GENERATE_DECISION"


class PlanStep(BaseModel):
    """A single step in the investigation plan.
    
    Traceability: plan_id.step_id → evidence gathered per this step.
    """
    step_id: str = Field(default_factory=new_id)
    action: PlanStepAction
    priority: int = Field(ge=1, le=5, description="1=highest, 5=lowest")
    description: str
    required_evidence: list[EvidenceType] = Field(default_factory=list)
    preferred_tool: ToolPreference = ToolPreference.NONE
    dependencies: list[str] = Field(
        default_factory=list,
        description="step_id values that must complete before this step",
    )
    stop_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions under which this step concludes the investigation",
    )
    escalation_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that trigger immediate escalation",
    )
    completed: bool = False
    skipped: bool = False
    skip_reason: Optional[str] = None


class InvestigationPlan(BaseModel):
    """Validated structured plan produced by invest.planner.
    
    Traceability root: case_id → plan_id → step_id
    """
    plan_id: str = Field(default_factory=new_id)
    case_id: str
    alert_id: str
    objective: str
    rationale: str = Field(description="Why this plan was chosen based on alert signals")
    steps: list[PlanStep] = Field(default_factory=list)
    max_evidence_items: int = 20
    confidence_threshold: float = Field(
        default=0.6,
        description="Minimum confidence for stopping evidence collection",
    )
    created_at: datetime = Field(default_factory=utcnow)
    version: int = 1  # Increments on replan


# ============================================================
# Hypothesis
# ============================================================

class HypothesisStatus(str, Enum):
    UNTESTED = "UNTESTED"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class Hypothesis(BaseModel):
    """A testable hypothesis about suspicious behavior."""
    hypothesis_id: str = Field(default_factory=new_id)
    plan_id: str                  # Links back to plan
    step_id: str                  # Which plan step generated this
    statement: str
    typology: Optional[str] = None  # e.g. "STRUCTURING", "CIRCULAR_TRANSFER"
    supporting_signals: list[str] = Field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.UNTESTED
    confidence: float = 0.0


# ============================================================
# Evidence (with full traceability)
# ============================================================

class EvidenceItem(BaseModel):
    """A piece of evidence gathered during the investigation.
    
    Traceability: step_id → evidence_id
    """
    evidence_id: str = Field(default_factory=new_id)
    case_id: str
    plan_id: str
    step_id: str                   # Which plan step produced this evidence
    hypothesis_ids: list[str] = Field(default_factory=list)  # Evidence tests these hypotheses
    evidence_type: EvidenceType
    source: str                    # e.g. "DB_QUERY", "GRAPH_QUERY", "TYPOLOGY_TOOL"
    source_record_id: Optional[str] = None
    description: str
    data: dict[str, Any] = Field(default_factory=dict)
    supporting_transaction_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    is_external: bool = False
    collected_at: datetime = Field(default_factory=utcnow)


# ============================================================
# Findings (derived from Evidence)
# ============================================================

class FindingSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Finding(BaseModel):
    """An analytical conclusion derived from one or more evidence items.
    
    Traceability: evidence_id → finding_id
    """
    finding_id: str = Field(default_factory=new_id)
    case_id: str
    plan_id: str
    evidence_ids: list[str]        # Which evidence supports this finding
    hypothesis_id: Optional[str] = None
    title: str
    description: str
    severity: FindingSeverity
    typology: Optional[str] = None
    confidence: float
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# ============================================================
# Analysis Result
# ============================================================

class AnalysisResult(BaseModel):
    """Synthesized analysis over all evidence and findings."""
    case_id: str
    plan_id: str
    composite_risk_score: float = Field(ge=0.0, le=1.0)
    transaction_risk_score: float = Field(ge=0.0, le=1.0)
    network_risk_score: float = Field(ge=0.0, le=1.0)
    typology_risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_factors: list[str] = Field(default_factory=list)
    positive_evidence: list[str] = Field(default_factory=list)
    negative_evidence: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    typology_matches: list[dict[str, Any]] = Field(default_factory=list)
    narrative: str = ""
    evidence_sufficient: bool = False
    created_at: datetime = Field(default_factory=utcnow)


# ============================================================
# Decision (deterministic, policy-driven)
# ============================================================

class DecisionOutcome(str, Enum):
    CLEAR = "CLEAR"
    MONITOR = "MONITOR"
    ESCALATE = "ESCALATE"
    SAR_RECOMMENDED = "SAR_RECOMMENDED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class InvestigationDecision(BaseModel):
    """Policy-driven decision. Final element in traceability chain.
    
    Traceability: finding_id → decision_id
    """
    decision_id: str = Field(default_factory=new_id)
    case_id: str
    plan_id: str
    finding_ids: list[str]         # Which findings drove the decision
    outcome: DecisionOutcome
    risk_level: str
    reasons: list[str] = Field(default_factory=list)
    required_human_action: Optional[str] = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    policy_version: str = "1.0"
    created_at: datetime = Field(default_factory=utcnow)


# ============================================================
# Audit Event
# ============================================================

class AuditRecord(BaseModel):
    """Immutable audit record for every investigation action."""
    audit_id: str = Field(default_factory=new_id)
    case_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    actor: str                     # "system:invest.planner", "system:evidence_retrieval", etc.
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    plan_id: Optional[str] = None
    step_id: Optional[str] = None
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Alert Context (loaded by Context/Data Loader)
# ============================================================

class AlertContext(BaseModel):
    """Alert data passed into the LangGraph workflow."""
    alert_id: str
    transaction_id: str
    customer_id: Optional[str] = None
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    amount: float
    anomaly_score: float
    rule_signals: list[dict[str, Any]] = Field(default_factory=list)
    initial_priority: str
    reasons: list[str] = Field(default_factory=list)


class CaseContext(BaseModel):
    """Full case context loaded before LangGraph execution."""
    case_id: str                   # = investigation_id
    alert: AlertContext
    transactions: list[dict[str, Any]] = Field(default_factory=list)   # Related transactions
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    customers: list[dict[str, Any]] = Field(default_factory=list)
    entity_clusters: list[dict[str, Any]] = Field(default_factory=list)
    graph_nodes: int = 0
    graph_edges: int = 0
    ml_features: dict[str, Any] = Field(default_factory=dict)
    loaded_at: datetime = Field(default_factory=utcnow)


# ============================================================
# LangGraph State (per case thread: thread_id = case_id)
# ============================================================

class AdaptivePlannerDecision(str, Enum):
    STOP = "STOP"
    REPLAN = "REPLAN"


class InvestigationState(TypedDict):
    """
    The complete LangGraph state for one investigation case.
    
    thread_id = case_id (LangGraph config parameter)
    
    Traceability chain embedded:
      case_id → plan.plan_id → step.step_id → evidence.evidence_id
                → finding.finding_id → decision.decision_id
    """
    # Identifiers
    case_id: str
    investigation_id: str

    # Case data (loaded by Context/Data Loader, before LangGraph)
    case_context: Optional[CaseContext]

    # invest.planner output (current active plan)
    current_plan: Optional[InvestigationPlan]
    plan_history: list[InvestigationPlan]       # All plans including replans
    current_step_index: int

    # Hypothesis Generation output
    hypotheses: list[Hypothesis]

    # Evidence Retrieval output (keyed by step_id for traceability)
    evidence: list[EvidenceItem]

    # Analysis & Reasoning output
    analysis_result: Optional[AnalysisResult]
    findings: list[Finding]

    # Adaptive Planner output
    adaptive_decision: Optional[AdaptivePlannerDecision]
    replan_reason: Optional[str]
    iteration_count: int
    max_iterations: int

    # Decision output
    decision: Optional[InvestigationDecision]

    # Report
    report_data: Optional[dict]
    pdf_path: Optional[str]

    # Audit trail
    audit_trail: list[AuditRecord]

    # Errors (non-fatal — investigation continues with reduced evidence)
    errors: list[str]
