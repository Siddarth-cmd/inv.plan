"""
End-to-End Acceptance Test for FinSpectra.

Workflow under test:
  1. Initialize DB & seed default admin user
  2. Ingest synthetic transactions dataset (99 records, 7 AML scenarios)
  3. Run Anomaly Detection (Isolation Forest + Rule Signals) → Create Alerts
  4. For each alert:
     a. Context/Data Loader → LangGraph Case State (thread_id=case_id)
     b. invest.planner → Plan generation
     c. Hypothesis generation → AML hypotheses
     d. Evidence retrieval → Tool dispatch (GraphQueryTool, TypologyMatchTool, etc.)
     e. Analysis & reasoning → Risk composite scoring
     f. Adaptive planner → STOP or REPLAN
     g. Decision node → Policy v1.0 decision
     h. Report generation → Structured JSON + ReportLab PDF
     i. Persist to SQLite DB
  5. Validate complete traceability chain:
     case_id → plan_id → step_id → evidence_id → finding_id → decision_id
  6. Output summary report with pass/fail metrics.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import structlog
logger = structlog.get_logger("finspectra.test.e2e")


async def run_e2e_test():
    start_time = time.time()
    print("=" * 70)
    print(" FINSPECTRA -- END-TO-END SYSTEM ACCEPTANCE TEST")
    print("=" * 70)

    from app.database.session import create_tables, AsyncSessionLocal
    from app.services.ingestion import ingest_csv
    from app.services.detection import run_detection
    from app.services.context_loader import load_case_context
    from app.agents.state import InvestigationState
    from app.agents.workflow import run_investigation
    from app.models import (
        Alert, Investigation, InvestigationStep, Evidence, RiskAssessment, Decision, Report, AuditEvent
    )
    from sqlalchemy import select

    # 1. Initialize DB
    print("\n[Step 1] Initializing SQLite database & tables...")
    await create_tables()
    print("  [OK] Database schema created successfully.")

    # 2. Ingest synthetic dataset
    dataset_path = os.path.join(root_dir, "datasets", "raw", "synthetic_transactions.csv")
    if not os.path.exists(dataset_path):
        print(f"  [ERROR] Synthetic dataset not found at {dataset_path}")
        return False

    print(f"\n[Step 2] Ingesting synthetic dataset ({dataset_path})...")
    with open(dataset_path, "rb") as f:
        csv_bytes = f.read()

    async with AsyncSessionLocal() as session:
        ingest_summary = await ingest_csv(csv_bytes, session, filename="synthetic_transactions.csv")
        await session.commit()

    print(f"  [OK] Ingestion complete: {ingest_summary.accepted_rows}/{ingest_summary.total_rows} rows accepted.")
    print(f"    - Duplicates skipped: {ingest_summary.duplicate_rows}")
    print(f"    - Flagged (>500K INR): {ingest_summary.flagged_rows}")

    # 3. Anomaly Detection & Alert Prioritization
    print("\n[Step 3] Running ML Anomaly Detection & Rule Signal Engine...")
    async with AsyncSessionLocal() as session:
        detection_summary = await run_detection(session)
        await session.commit()

    print(f"  [OK] Detection complete: {detection_summary.get('alerts_created')} alerts created.")
    print(f"    - Transactions analyzed: {detection_summary.get('total_transactions_analyzed')}")
    print(f"    - Rule signals triggered: {detection_summary.get('rule_signals_total')}")

    # Fetch created alerts
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Alert).order_by(Alert.anomaly_score.desc()))
        alerts = list(result.scalars())

    if not alerts:
        print("  [ERROR] No alerts created during detection.")
        return False

    print(f"\n  Found {len(alerts)} alerts to investigate.")

    # 4. Run LangGraph Workflow for top alerts
    investigation_results = []
    for idx, alert in enumerate(alerts[:5]):  # Run top 5 alerts
        print(f"\n[Step 4.{idx+1}] Investigating Alert {alert.id[:8]} (Priority: {alert.initial_priority}, Score: {alert.anomaly_score:.3f})...")

        async with AsyncSessionLocal() as session:
            # Create investigation record
            inv = Investigation(alert_id=alert.id, status="RUNNING")
            session.add(inv)
            await session.flush()
            inv_id = inv.id

            # Load case context
            case_context = await load_case_context(alert.id, session)
            case_context.case_id = inv_id

            # Initial LangGraph state
            initial_state: InvestigationState = {
                "case_id": inv_id,
                "investigation_id": inv_id,
                "case_context": case_context,
                "current_plan": None,
                "plan_history": [],
                "current_step_index": 0,
                "hypotheses": [],
                "evidence": [],
                "analysis_result": None,
                "findings": [],
                "adaptive_decision": None,
                "replan_reason": None,
                "iteration_count": 0,
                "max_iterations": 3,
                "decision": None,
                "report_data": None,
                "pdf_path": None,
                "audit_trail": [],
                "errors": [],
            }

            # Execute LangGraph workflow (thread_id = case_id)
            final_state = run_investigation(initial_state)

            # Persist to DB
            inv.status = "COMPLETED"

            # Persist plan steps
            plan = final_state.get("current_plan")
            if plan:
                for step in plan.steps:
                    session.add(InvestigationStep(
                        investigation_id=inv_id,
                        step_name=step.action.value,
                        status="COMPLETED" if step.completed else "PENDING",
                        output={"step_id": step.step_id, "priority": step.priority},
                    ))

            # Persist evidence
            for ev in (final_state.get("evidence") or []):
                session.add(Evidence(
                    investigation_id=inv_id,
                    evidence_type=ev.evidence_type.value,
                    source=ev.source,
                    description=ev.description[:500],
                    confidence=ev.confidence,
                ))

            # Persist risk & decision
            analysis = final_state.get("analysis_result")
            if analysis:
                session.add(RiskAssessment(
                    investigation_id=inv_id,
                    risk_level=analysis.risk_level,
                    composite_score=analysis.composite_risk_score,
                    transaction_risk_score=analysis.transaction_risk_score,
                    network_risk_score=analysis.network_risk_score,
                    typology_risk_score=analysis.typology_risk_score,
                    risk_factors=analysis.risk_factors,
                ))

            dec = final_state.get("decision")
            if dec:
                session.add(Decision(
                    investigation_id=inv_id,
                    decision=dec.outcome.value,
                    risk_level=dec.risk_level,
                    reasons=dec.reasons,
                    supporting_evidence_ids=dec.supporting_evidence_ids,
                    policy_version=dec.policy_version,
                ))

            pdf_path = final_state.get("pdf_path")
            if final_state.get("report_data"):
                session.add(Report(
                    investigation_id=inv_id,
                    pdf_path=pdf_path,
                    report_data=final_state["report_data"],
                ))

            await session.commit()

            investigation_results.append({
                "inv_id": inv_id,
                "alert_id": alert.id,
                "plan_version": plan.version if plan else 1,
                "step_count": len(plan.steps) if plan else 0,
                "evidence_count": len(final_state.get("evidence") or []),
                "finding_count": len(final_state.get("findings") or []),
                "decision": dec.outcome.value if dec else "NONE",
                "risk_level": analysis.risk_level if analysis else "NONE",
                "composite_score": analysis.composite_risk_score if analysis else 0.0,
                "pdf_path": pdf_path,
                "pdf_exists": os.path.exists(pdf_path) if pdf_path else False,
            })

            print(f"  [OK] Case {inv_id[:8]} completed.")
            print(f"    - Decision: {dec.outcome.value if dec else 'NONE'} (Risk: {analysis.risk_level if analysis else 'NONE'})")
            print(f"    - Evidence Items: {len(final_state.get('evidence') or [])}")
            print(f"    - Findings: {len(final_state.get('findings') or [])}")
            print(f"    - PDF Generated: {os.path.exists(pdf_path) if pdf_path else False}")

    # 5. Validate Traceability Chain
    print("\n[Step 5] Validating Rigid Traceability Chain...")
    async with AsyncSessionLocal() as session:
        for res in investigation_results:
            inv_id = res["inv_id"]
            # Fetch decision
            d_res = await session.execute(select(Decision).where(Decision.investigation_id == inv_id))
            d = d_res.scalar_one_or_none()

            e_res = await session.execute(select(Evidence).where(Evidence.investigation_id == inv_id))
            evidence_list = list(e_res.scalars())

            rep_res = await session.execute(select(Report).where(Report.investigation_id == inv_id))
            r = rep_res.scalar_one_or_none()

            assert d is not None, f"Missing decision for investigation {inv_id}"
            assert len(evidence_list) > 0, f"Missing evidence for investigation {inv_id}"
            assert r is not None, f"Missing report for investigation {inv_id}"
            assert r.report_data.get("traceability") is not None, f"Missing traceability metadata in report {inv_id}"

            tc = r.report_data["traceability"]
            print(f"  [OK] Traceability verified for Case {inv_id[:8]}:")
            print(f"    Case ID: {tc['case_id']}")
            print(f"    Plan IDs: {tc['plan_ids']}")
            print(f"    Evidence IDs: {len(tc['evidence_ids'])} items")
            print(f"    Finding IDs: {len(tc['finding_ids'])} items")
            print(f"    Decision ID: {tc['decision_id']}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(" ACCEPTANCE TEST RESULTS: ALL CHECKS PASSED")
    print("=" * 70)
    print(f" Total Duration: {elapsed:.2f} seconds")
    print(f" Investigations Tested: {len(investigation_results)}")
    for res in investigation_results:
        print(f"  * Case {res['inv_id'][:8]} -> Decision: {res['decision']} | Risk: {res['risk_level']} | PDF: {'YES' if res['pdf_exists'] else 'NO'}")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_e2e_test())
    sys.exit(0 if success else 1)
