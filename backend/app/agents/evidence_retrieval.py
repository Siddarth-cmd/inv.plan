"""
Evidence Retrieval Node — Tool Calling.

Executes each plan step by calling the appropriate tool (GRAPH_QUERY,
DB_QUERY, TYPOLOGY_MATCH, SIGNAL_COMPUTE). Evidence items are created
with full traceability back to step_id.

Tool dispatch is explicit — the planner's ToolPreference enum is the
routing key. No embedded graph logic here.

Traceability: plan_id → step_id → evidence_id
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from app.agents.state import (
    AlertContext,
    AuditRecord,
    CaseContext,
    EvidenceItem,
    EvidenceType,
    Hypothesis,
    HypothesisStatus,
    InvestigationPlan,
    InvestigationState,
    PlanStep,
    PlanStepAction,
    ToolPreference,
)
from app.tools.graph_tool import GraphQueryTool
from app.tools.typology_tool import TypologyMatchTool

logger = structlog.get_logger("finspectra.agents.evidence_retrieval")


def _get_hypothesis_ids_for_step(
    step: PlanStep, hypotheses: list[Hypothesis]
) -> list[str]:
    return [h.hypothesis_id for h in hypotheses if h.step_id == step.step_id]


def _gather_transaction_history(
    step: PlanStep, case_context: CaseContext, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """GATHER_TRANSACTION_HISTORY — DB_QUERY"""
    transactions = case_context.transactions
    accounts = case_context.accounts
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)

    items = []
    txn_ids = [t.get("id", t.get("txn_ref", "")) for t in transactions]
    amounts = [t.get("amount", 0) for t in transactions]

    items.append(EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,  # will be overridden below
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.TRANSACTION_HISTORY,
        source="DB_QUERY",
        description=(
            f"Retrieved {len(transactions)} transactions for case. "
            f"Amount range: {min(amounts, default=0):,.0f}–{max(amounts, default=0):,.0f} INR. "
            f"Channels: {', '.join(set(t.get('channel', '?') for t in transactions))}."
        ),
        data={
            "transaction_count": len(transactions),
            "total_volume": sum(amounts),
            "min_amount": min(amounts, default=0),
            "max_amount": max(amounts, default=0),
            "channels": list(set(t.get("channel", "?") for t in transactions)),
            "account_count": len(accounts),
        },
        supporting_transaction_ids=txn_ids,
        confidence=1.0,
    ))

    # Account profile evidence
    for acc in accounts[:5]:  # top 5 accounts
        items.append(EvidenceItem(
            case_id=case_context.case_id,
            plan_id=step.step_id,
            step_id=step.step_id,
            hypothesis_ids=hyp_ids,
            evidence_type=EvidenceType.ACCOUNT_PROFILE,
            source="DB_QUERY",
            source_record_id=acc.get("id", ""),
            description=f"Account {acc.get('account_number', '?')} profile retrieved.",
            data=acc,
            confidence=1.0,
        ))
    return items


def _resolve_entities(
    step: PlanStep, case_context: CaseContext, graph_tool: GraphQueryTool, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """RESOLVE_ENTITIES — DB_QUERY + GRAPH shared devices"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    items = []
    entity_clusters = case_context.entity_clusters
    shared_devices = graph_tool.get_shared_devices()

    items.append(EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.ENTITY_RELATIONSHIP,
        source="DB_QUERY",
        description=(
            f"Entity resolution found {len(entity_clusters)} clusters. "
            f"Shared devices: {len(shared_devices)}."
        ),
        data={"clusters": entity_clusters, "shared_devices": shared_devices},
        confidence=1.0,
    ))

    if shared_devices:
        for dev in shared_devices:
            items.append(EvidenceItem(
                case_id=case_context.case_id,
                plan_id=step.step_id,
                step_id=step.step_id,
                hypothesis_ids=hyp_ids,
                evidence_type=EvidenceType.DEVICE_FINGERPRINT,
                source="GRAPH_QUERY",
                description=(
                    f"Device {dev['device']} used by {dev['account_count']} accounts: "
                    f"{', '.join(str(a) for a in dev.get('accounts', [])[:5])}."
                ),
                data=dev,
                confidence=0.95,
            ))
    return items


def _build_relationship_graph(
    step: PlanStep, case_context: CaseContext, graph_tool: GraphQueryTool, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """BUILD_RELATIONSHIP_GRAPH — GRAPH_QUERY"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    summary = graph_tool.build_from_context(case_context.model_dump())
    return [EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.ENTITY_RELATIONSHIP,
        source="GRAPH_QUERY",
        description=(
            f"Transaction relationship graph: {summary['nodes']} nodes, "
            f"{summary['edges']} edges, "
            f"{summary['weakly_connected_components']} components."
        ),
        data=summary,
        confidence=1.0,
    )]


def _detect_graph_cycles(
    step: PlanStep, case_context: CaseContext, graph_tool: GraphQueryTool, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """DETECT_GRAPH_CYCLES — GRAPH_QUERY"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    cycles = graph_tool.find_cycles()
    if not cycles:
        return [EvidenceItem(
            case_id=case_context.case_id,
            plan_id=step.step_id,
            step_id=step.step_id,
            hypothesis_ids=hyp_ids,
            evidence_type=EvidenceType.GRAPH_CYCLES,
            source="GRAPH_QUERY",
            description="No circular money flows detected in the transaction graph.",
            data={"cycles": []},
            confidence=1.0,
        )]
    return [EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.GRAPH_CYCLES,
        source="GRAPH_QUERY",
        description=(
            f"Detected {len(cycles)} circular money flow(s). "
            f"Largest cycle: {max(c['length'] for c in cycles)} accounts, "
            f"total amount: {max(c['total_amount'] for c in cycles):,.0f} INR."
        ),
        data={"cycles": cycles},
        supporting_transaction_ids=[tid for c in cycles for tid in c.get("txn_ids", [])],
        confidence=0.9,
    )]


def _compute_centrality(
    step: PlanStep, case_context: CaseContext, graph_tool: GraphQueryTool, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """COMPUTE_CENTRALITY — GRAPH_QUERY"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    high_central = graph_tool.get_high_centrality_nodes(threshold=0.2)
    return [EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.GRAPH_CENTRALITY,
        source="GRAPH_QUERY",
        description=(
            f"Found {len(high_central)} high-centrality nodes (threshold: 0.2). "
            + (f"Top hub: {high_central[0]['node']}." if high_central else "No hub accounts identified.")
        ),
        data={"high_centrality_nodes": high_central},
        confidence=0.9,
    )]


def _match_typologies(
    step: PlanStep,
    case_context: CaseContext,
    graph_tool: GraphQueryTool,
    typology_tool: TypologyMatchTool,
    hypotheses: list[Hypothesis],
) -> list[EvidenceItem]:
    """MATCH_TYPOLOGIES — TYPOLOGY_MATCH"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    cycles = graph_tool.find_cycles()
    passthrough = graph_tool.get_rapid_pass_through()
    shared_devices = graph_tool.get_shared_devices()
    rule_signals = case_context.alert.rule_signals

    matches = typology_tool.run(
        transactions=case_context.transactions,
        graph_cycles=cycles,
        graph_passthrough=passthrough,
        shared_devices=shared_devices,
        rule_signals=rule_signals,
    )

    items = []
    for match in matches:
        supporting_txns = [r for r in match.supporting_records if len(r) < 50]
        items.append(EvidenceItem(
            case_id=case_context.case_id,
            plan_id=step.step_id,
            step_id=step.step_id,
            hypothesis_ids=hyp_ids,
            evidence_type=EvidenceType.TYPOLOGY_MATCH,
            source="TYPOLOGY_TOOL",
            description=match.explanation,
            data=match.to_dict(),
            supporting_transaction_ids=supporting_txns,
            confidence=match.confidence,
        ))

    if not items:
        items.append(EvidenceItem(
            case_id=case_context.case_id,
            plan_id=step.step_id,
            step_id=step.step_id,
            hypothesis_ids=hyp_ids,
            evidence_type=EvidenceType.TYPOLOGY_MATCH,
            source="TYPOLOGY_TOOL",
            description="No AML typology patterns detected for this case.",
            data={"matches": []},
            confidence=1.0,
        ))
    return items


def _analyze_amount_patterns(
    step: PlanStep, case_context: CaseContext, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """ANALYZE_AMOUNT_PATTERNS — SIGNAL_COMPUTE"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    transactions = case_context.transactions
    amounts = [t.get("amount", 0) for t in transactions]
    alert = case_context.alert

    if not amounts:
        return []

    import statistics
    mean_amt = statistics.mean(amounts) if amounts else 0
    stdev_amt = statistics.stdev(amounts) if len(amounts) > 1 else 0
    below_100k = [a for a in amounts if 75000 <= a < 100000]
    round_amounts = [a for a in amounts if a % 1000 == 0]

    return [EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.AMOUNT_PATTERN,
        source="SIGNAL_COMPUTE",
        description=(
            f"Amount analysis: mean={mean_amt:,.0f} INR, stdev={stdev_amt:,.0f} INR. "
            f"Alert transaction: {alert.amount:,.0f} INR "
            f"({(alert.amount - mean_amt) / max(stdev_amt, 1):.1f} std devs from mean). "
            f"Transactions 75K–100K (structuring zone): {len(below_100k)}. "
            f"Round amounts: {len(round_amounts)}."
        ),
        data={
            "mean": mean_amt,
            "stdev": stdev_amt,
            "alert_amount": alert.amount,
            "z_score": (alert.amount - mean_amt) / max(stdev_amt, 1),
            "below_threshold_count": len(below_100k),
            "round_amount_count": len(round_amounts),
        },
        supporting_transaction_ids=[
            t.get("id", t.get("txn_ref", ""))
            for t in transactions
            if 75000 <= t.get("amount", 0) < 100000
        ],
        confidence=1.0,
    )]


def _analyze_temporal_patterns(
    step: PlanStep, case_context: CaseContext, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """ANALYZE_TEMPORAL_PATTERNS — SIGNAL_COMPUTE"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    transactions = case_context.transactions
    off_hours = [t for t in transactions if _parse_hour(t.get("timestamp", "")) in {0,1,2,3,4,5,23}]

    return [EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.TEMPORAL_PATTERN,
        source="SIGNAL_COMPUTE",
        description=(
            f"Temporal analysis: {len(transactions)} transactions. "
            f"Off-hours (11pm–5am): {len(off_hours)} ({100*len(off_hours)/max(len(transactions),1):.0f}%)."
        ),
        data={
            "total_transactions": len(transactions),
            "off_hours_count": len(off_hours),
            "off_hours_pct": 100 * len(off_hours) / max(len(transactions), 1),
        },
        supporting_transaction_ids=[t.get("id", t.get("txn_ref", "")) for t in off_hours],
        confidence=1.0,
    )]


def _assess_counterparties(
    step: PlanStep, case_context: CaseContext, graph_tool: GraphQueryTool, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """ASSESS_COUNTERPARTIES — GRAPH_QUERY"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    passthrough = graph_tool.get_rapid_pass_through()

    description = (
        f"Found {len(passthrough)} accounts with high pass-through ratios. "
        + (f"Highest: {passthrough[0]['passthrough_ratio']:.0%}" if passthrough else "")
    )
    return [EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.COUNTERPARTY_ANALYSIS,
        source="GRAPH_QUERY",
        description=description,
        data={"passthrough_accounts": passthrough},
        confidence=0.9,
    )]


def _evaluate_device_signals(
    step: PlanStep, case_context: CaseContext, graph_tool: GraphQueryTool, hypotheses: list[Hypothesis]
) -> list[EvidenceItem]:
    """EVALUATE_DEVICE_SIGNALS — GRAPH_QUERY"""
    hyp_ids = _get_hypothesis_ids_for_step(step, hypotheses)
    shared = graph_tool.get_shared_devices()
    description = (
        f"Found {len(shared)} shared device(s) across multiple accounts." if shared
        else "No shared device identifiers detected."
    )
    return [EvidenceItem(
        case_id=case_context.case_id,
        plan_id=step.step_id,
        step_id=step.step_id,
        hypothesis_ids=hyp_ids,
        evidence_type=EvidenceType.DEVICE_FINGERPRINT,
        source="GRAPH_QUERY",
        description=description,
        data={"shared_devices": shared},
        confidence=0.95 if shared else 1.0,
    )]


def _parse_hour(ts_str: str) -> int:
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.hour
    except Exception:
        return 12  # default to midday if unparseable


# ── Tool dispatch table ───────────────────────────────────────────────────────

def _dispatch_step(
    step: PlanStep,
    case_context: CaseContext,
    graph_tool: GraphQueryTool,
    typology_tool: TypologyMatchTool,
    hypotheses: list[Hypothesis],
) -> list[EvidenceItem]:
    """Route a plan step to the appropriate evidence-gathering function."""
    action = step.action
    if action == PlanStepAction.GATHER_TRANSACTION_HISTORY:
        return _gather_transaction_history(step, case_context, hypotheses)
    elif action == PlanStepAction.RESOLVE_ENTITIES:
        return _resolve_entities(step, case_context, graph_tool, hypotheses)
    elif action == PlanStepAction.BUILD_RELATIONSHIP_GRAPH:
        return _build_relationship_graph(step, case_context, graph_tool, hypotheses)
    elif action == PlanStepAction.DETECT_GRAPH_CYCLES:
        return _detect_graph_cycles(step, case_context, graph_tool, hypotheses)
    elif action == PlanStepAction.COMPUTE_CENTRALITY:
        return _compute_centrality(step, case_context, graph_tool, hypotheses)
    elif action == PlanStepAction.MATCH_TYPOLOGIES:
        return _match_typologies(step, case_context, graph_tool, typology_tool, hypotheses)
    elif action == PlanStepAction.ANALYZE_AMOUNT_PATTERNS:
        return _analyze_amount_patterns(step, case_context, hypotheses)
    elif action == PlanStepAction.ANALYZE_TEMPORAL_PATTERNS:
        return _analyze_temporal_patterns(step, case_context, hypotheses)
    elif action == PlanStepAction.ASSESS_COUNTERPARTIES:
        return _assess_counterparties(step, case_context, graph_tool, hypotheses)
    elif action == PlanStepAction.EVALUATE_DEVICE_SIGNALS:
        return _evaluate_device_signals(step, case_context, graph_tool, hypotheses)
    else:
        # SYNTHESIZE_FINDINGS, GENERATE_DECISION handled by later nodes
        return []


# ── Main node ─────────────────────────────────────────────────────────────────

def evidence_retrieval(state: InvestigationState) -> InvestigationState:
    """
    Evidence Retrieval Node — executes plan steps via tool dispatch.
    
    Each step's preferred_tool determines which tool handles it.
    All evidence items are stamped with step_id for full traceability.
    """
    start_ts = time.time()
    case_id = state["case_id"]
    plan: InvestigationPlan = state["current_plan"]
    case_context: CaseContext = state["case_context"]
    hypotheses: list[Hypothesis] = state.get("hypotheses") or []

    log = logger.bind(case_id=case_id, plan_id=plan.plan_id)
    log.info("Evidence retrieval starting", total_steps=len(plan.steps))

    # Initialize tools
    graph_tool = GraphQueryTool()
    graph_tool.build_from_context(case_context.model_dump())
    typology_tool = TypologyMatchTool()
    errors = list(state.get("errors") or [])

    existing_evidence = list(state.get("evidence") or [])
    new_evidence: list[EvidenceItem] = []

    # Execute all non-completed, non-synthesis steps
    executable_steps = [
        s for s in plan.steps
        if not s.completed
        and not s.skipped
        and s.action not in (PlanStepAction.SYNTHESIZE_FINDINGS, PlanStepAction.GENERATE_DECISION)
    ]

    for step in executable_steps:
        step_start = time.time()
        try:
            items = _dispatch_step(step, case_context, graph_tool, typology_tool, hypotheses)
            # Stamp plan_id on all items
            for item in items:
                item.plan_id = plan.plan_id
            new_evidence.extend(items)
            step.completed = True
            step_dur = int((time.time() - step_start) * 1000)
            log.debug("Step complete", action=step.action.value, items=len(items), duration_ms=step_dur)
        except Exception as exc:
            err_msg = f"Step {step.action.value} failed: {exc}"
            errors.append(err_msg)
            log.error("Step failed", action=step.action.value, error=str(exc))

    # Update hypothesis status based on evidence
    updated_hypotheses = _update_hypothesis_status(hypotheses, new_evidence)

    all_evidence = existing_evidence + new_evidence
    duration_ms = int((time.time() - start_ts) * 1000)

    log.info(
        "Evidence retrieval complete",
        new_evidence=len(new_evidence),
        total_evidence=len(all_evidence),
        duration_ms=duration_ms,
    )

    audit = AuditRecord(
        case_id=case_id,
        actor="system:evidence_retrieval",
        action="EVIDENCE_GATHERED",
        plan_id=plan.plan_id,
        summary=(
            f"Gathered {len(new_evidence)} evidence items across {len(executable_steps)} plan steps. "
            f"Total evidence: {len(all_evidence)}."
        ),
        metadata={
            "new_evidence_count": len(new_evidence),
            "total_evidence_count": len(all_evidence),
            "steps_executed": len(executable_steps),
            "errors": errors,
            "duration_ms": duration_ms,
        },
    )

    audit_trail = list(state.get("audit_trail") or [])
    audit_trail.append(audit)

    # Store graph data for later API use
    try:
        graph_data = graph_tool.to_serializable()
    except Exception:
        graph_data = {}

    return {
        **state,
        "evidence": all_evidence,
        "hypotheses": updated_hypotheses,
        "errors": errors,
        "audit_trail": audit_trail,
        "report_data": {**(state.get("report_data") or {}), "graph_data": graph_data},
    }


def _update_hypothesis_status(
    hypotheses: list[Hypothesis], new_evidence: list[EvidenceItem]
) -> list[Hypothesis]:
    """Update hypothesis status based on gathered evidence."""
    # Build evidence index by hypothesis_id
    hyp_evidence: dict[str, list[EvidenceItem]] = {}
    for ev in new_evidence:
        for hid in ev.hypothesis_ids:
            hyp_evidence.setdefault(hid, []).append(ev)

    updated = []
    for hyp in hypotheses:
        if hyp.status != HypothesisStatus.UNTESTED:
            updated.append(hyp)
            continue
        evidence_for_hyp = hyp_evidence.get(hyp.hypothesis_id, [])
        if not evidence_for_hyp:
            updated.append(hyp)
            continue

        # Check typology matches specifically
        typology_matches = [
            e for e in evidence_for_hyp
            if e.evidence_type == EvidenceType.TYPOLOGY_MATCH
            and hyp.typology
            and hyp.typology in e.data.get("typology", "")
        ]
        if typology_matches:
            avg_conf = sum(e.confidence for e in typology_matches) / len(typology_matches)
            hyp.status = HypothesisStatus.SUPPORTED if avg_conf >= 0.5 else HypothesisStatus.INCONCLUSIVE
            hyp.confidence = avg_conf
        elif evidence_for_hyp:
            hyp.status = HypothesisStatus.INCONCLUSIVE
            hyp.confidence = 0.3
        updated.append(hyp)
    return updated
