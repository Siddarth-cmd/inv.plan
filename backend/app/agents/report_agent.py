"""
Report Generation Agent.

Generates a structured investigation report and a ReportLab PDF.
All report content derived from actual case state — no fabrication.
LLM used only for narrative text if configured; deterministic fallback always available.

Structure:
  1. Case Summary
  2. Subject/Customer Information
  3. Transaction Summary
  4. Transaction Timeline
  5. Entity Relationships
  6. Network Findings
  7. Detected Signals
  8. AML Typology Matches
  9. Risk Assessment
  10. Decision
  11. Evidence
  12. Uncertainties/Limitations
  13. Audit Metadata

Traceability chain stamped into the report metadata.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from app.agents.state import (
    AuditRecord,
    CaseContext,
    EvidenceItem,
    Finding,
    InvestigationDecision,
    InvestigationState,
)
from app.core.config import get_settings

logger = structlog.get_logger("finspectra.agents.report")
settings = get_settings()


def _build_report_data(state: InvestigationState) -> dict[str, Any]:
    """Assemble all report sections from state. Pure data — no formatting."""
    case_id = state["case_id"]
    case_context: CaseContext = state["case_context"]
    plan = state.get("current_plan")
    plan_history = state.get("plan_history") or []
    evidence: list[EvidenceItem] = state.get("evidence") or []
    findings: list[Finding] = state.get("findings") or []
    analysis = state.get("analysis_result")
    decision: InvestigationDecision = state.get("decision")
    hypotheses = state.get("hypotheses") or []
    audit_trail = state.get("audit_trail") or []
    errors = state.get("errors") or []

    alert = case_context.alert
    transactions = case_context.transactions
    customers = case_context.customers
    accounts = case_context.accounts

    return {
        "report_id": str(uuid.uuid4()),
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_version": "1.0",

        # Traceability chain
        "traceability": {
            "case_id": case_id,
            "plan_ids": [p.plan_id for p in plan_history],
            "step_ids": [s.step_id for p in plan_history for s in p.steps],
            "evidence_ids": [e.evidence_id for e in evidence],
            "finding_ids": [f.finding_id for f in findings],
            "decision_id": decision.decision_id if decision else None,
        },

        # 1. Case Summary
        "case_summary": {
            "alert_id": alert.alert_id,
            "transaction_id": alert.transaction_id,
            "alert_priority": alert.initial_priority,
            "anomaly_score": alert.anomaly_score,
            "investigation_plans": len(plan_history),
            "total_evidence": len(evidence),
            "total_findings": len(findings),
            "decision": decision.outcome.value if decision else "PENDING",
            "risk_level": analysis.risk_level if analysis else "UNKNOWN",
        },

        # 2. Subject/Customer
        "subjects": customers[:10],
        "accounts": accounts[:10],

        # 3. Transaction Summary
        "transaction_summary": {
            "total_transactions": len(transactions),
            "alert_amount": alert.amount,
            "alert_currency": "INR",
            "total_volume": sum(t.get("amount", 0) for t in transactions),
            "channels": list({t.get("channel", "?") for t in transactions}),
            "date_range": {
                "from": min((t.get("timestamp", "") for t in transactions), default=""),
                "to": max((t.get("timestamp", "") for t in transactions), default=""),
            },
        },

        # 4. Transaction Timeline
        "transaction_timeline": sorted(
            [
                {
                    "txn_ref": t.get("txn_ref", t.get("id", "")),
                    "timestamp": t.get("timestamp", ""),
                    "from_account": t.get("from_account_number", t.get("from_account", "")),
                    "to_account": t.get("to_account_number", t.get("to_account", "")),
                    "amount": t.get("amount", 0),
                    "channel": t.get("channel", ""),
                    "scenario_label": t.get("scenario_label", ""),
                }
                for t in transactions
            ],
            key=lambda x: x["timestamp"],
        )[:50],

        # 5. Entity Relationships
        "entity_clusters": case_context.entity_clusters,

        # 6. Network Findings
        "network_findings": (state.get("report_data") or {}).get("graph_data", {}),

        # 7. Detected Signals
        "detected_signals": alert.rule_signals,
        "hypotheses": [
            {
                "id": h.hypothesis_id,
                "statement": h.statement,
                "typology": h.typology,
                "status": h.status.value,
                "confidence": h.confidence,
            }
            for h in hypotheses
        ],

        # 8. AML Typology Matches
        "typology_matches": analysis.typology_matches if analysis else [],

        # 9. Risk Assessment
        "risk_assessment": {
            "risk_level": analysis.risk_level if analysis else "UNKNOWN",
            "composite_score": analysis.composite_risk_score if analysis else 0,
            "transaction_risk": analysis.transaction_risk_score if analysis else 0,
            "network_risk": analysis.network_risk_score if analysis else 0,
            "typology_risk": analysis.typology_risk_score if analysis else 0,
            "risk_factors": analysis.risk_factors if analysis else [],
            "positive_evidence": analysis.positive_evidence if analysis else [],
            "negative_evidence": analysis.negative_evidence if analysis else [],
            "narrative": analysis.narrative if analysis else "",
        },

        # 10. Decision
        "decision": {
            "outcome": decision.outcome.value if decision else "PENDING",
            "risk_level": decision.risk_level if decision else "UNKNOWN",
            "reasons": decision.reasons if decision else [],
            "required_human_action": decision.required_human_action if decision else None,
            "policy_version": decision.policy_version if decision else "1.0",
            "decision_id": decision.decision_id if decision else None,
        },

        # 11. Evidence Summary
        "evidence_summary": [
            {
                "evidence_id": e.evidence_id,
                "step_id": e.step_id,
                "type": e.evidence_type.value,
                "source": e.source,
                "description": e.description[:300],
                "confidence": e.confidence,
                "is_external": e.is_external,
            }
            for e in evidence
        ],

        # 12. Findings
        "findings": [
            {
                "finding_id": f.finding_id,
                "title": f.title,
                "severity": f.severity.value,
                "typology": f.typology,
                "confidence": f.confidence,
                "description": f.description[:500],
                "evidence_ids": f.evidence_ids,
            }
            for f in findings
        ],

        # 13. Uncertainties / Limitations
        "uncertainties": analysis.uncertainties if analysis else [],
        "errors_during_investigation": errors,
        "data_source": "SYNTHETIC_DEMONSTRATION_DATA — Not real financial records",

        # 14. Audit Metadata
        "audit_events": [
            {
                "audit_id": a.audit_id,
                "timestamp": a.timestamp.isoformat(),
                "actor": a.actor,
                "action": a.action,
                "summary": a.summary,
                "plan_id": a.plan_id,
                "step_id": a.step_id,
            }
            for a in audit_trail
        ],
    }


def _generate_pdf(report_data: dict[str, Any], output_path: str) -> bool:
    """
    Generate a ReportLab PDF from the report data.
    Returns True on success, False on failure (fallback: JSON report still exists).
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, HRFlowable, PageBreak
        )

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, spaceAfter=6, textColor=colors.HexColor("#1a237e"))
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceAfter=4, textColor=colors.HexColor("#283593"))
        body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, spaceAfter=3)
        label = ParagraphStyle("Label", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
        warning_style = ParagraphStyle("Warning", parent=styles["Normal"], fontSize=8,
                                       textColor=colors.HexColor("#b71c1c"),
                                       backColor=colors.HexColor("#ffebee"))

        story = []

        # Header
        story.append(Paragraph("FinSpectra — Investigation Report", h1))
        story.append(Paragraph("SYNTHETIC DEMONSTRATION DATA ONLY — Not a real financial record", warning_style))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a237e")))
        story.append(Spacer(1, 4))

        # Case Summary
        summary = report_data["case_summary"]
        story.append(Paragraph("1. Case Summary", h2))
        summary_data = [
            ["Case ID", report_data["case_id"]],
            ["Alert ID", summary["alert_id"]],
            ["Alert Priority", summary["alert_priority"]],
            ["Anomaly Score (ML)", f"{summary['anomaly_score']:.4f}"],
            ["Decision", summary["decision"]],
            ["Risk Level", summary["risk_level"]],
            ["Total Evidence Items", str(summary["total_evidence"])],
            ["Investigation Plans", str(summary["investigation_plans"])],
            ["Generated At", report_data["generated_at"]],
        ]
        t = Table(summary_data, colWidths=[60*mm, 110*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8eaf6")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

        # Traceability Chain
        story.append(Paragraph("Traceability Chain", h2))
        tc = report_data["traceability"]
        story.append(Paragraph(f"Case ID → Plan IDs → Step IDs → Evidence IDs → Finding IDs → Decision ID", label))
        story.append(Paragraph(f"Decision ID: {tc.get('decision_id', 'N/A')}", body))
        story.append(Paragraph(f"Evidence items: {len(tc.get('evidence_ids', []))}", body))
        story.append(Paragraph(f"Findings: {len(tc.get('finding_ids', []))}", body))
        story.append(Spacer(1, 8))

        # Risk Assessment
        risk = report_data["risk_assessment"]
        story.append(Paragraph("2. Risk Assessment", h2))
        risk_color = {"CRITICAL": "#b71c1c", "HIGH": "#e65100", "MEDIUM": "#f57f17", "LOW": "#1b5e20"}.get(
            risk["risk_level"], "#000000"
        )
        risk_style = ParagraphStyle("Risk", parent=styles["Normal"], fontSize=14,
                                    textColor=colors.HexColor(risk_color), spaceAfter=4)
        story.append(Paragraph(f"Risk Level: {risk['risk_level']}", risk_style))
        story.append(Paragraph(
            f"Composite Score: {risk['composite_score']:.4f} | "
            f"Transaction: {risk['transaction_risk']:.4f} | "
            f"Network: {risk['network_risk']:.4f} | "
            f"Typology: {risk['typology_risk']:.4f}", body
        ))
        if risk.get("risk_factors"):
            story.append(Paragraph("Risk Factors:", label))
            for rf in risk["risk_factors"][:8]:
                story.append(Paragraph(f"• {rf}", body))
        story.append(Spacer(1, 8))

        # Decision
        dec = report_data["decision"]
        story.append(Paragraph("3. Decision", h2))
        dec_color = {"SAR_RECOMMENDED": "#b71c1c", "ESCALATE": "#e65100", "MONITOR": "#f57f17",
                     "CLEAR": "#1b5e20", "HUMAN_REVIEW": "#1565c0"}.get(dec["outcome"], "#000000")
        dec_style = ParagraphStyle("Dec", parent=styles["Normal"], fontSize=14,
                                   textColor=colors.HexColor(dec_color), spaceAfter=4)
        story.append(Paragraph(f"Outcome: {dec['outcome']}", dec_style))
        story.append(Paragraph(f"Policy Version: {dec['policy_version']}", label))
        if dec.get("required_human_action"):
            story.append(Paragraph(f"Required Action: {dec['required_human_action']}", body))
        if dec.get("reasons"):
            story.append(Paragraph("Decision Basis:", label))
            for r in dec["reasons"][:6]:
                story.append(Paragraph(f"• {r}", body))
        story.append(Spacer(1, 8))

        # AML Typology Matches
        story.append(Paragraph("4. AML Typology Matches", h2))
        typologies = report_data.get("typology_matches", [])
        if typologies:
            for tm in typologies:
                story.append(Paragraph(f"Typology: {tm.get('typology', '?')} (confidence: {tm.get('confidence', 0):.0%})", body))
                for cond in tm.get("matched_conditions", []):
                    story.append(Paragraph(f"  • {cond}", label))
        else:
            story.append(Paragraph("No AML typology patterns matched.", body))
        story.append(Spacer(1, 8))

        # Findings
        story.append(Paragraph("5. Findings", h2))
        findings = report_data.get("findings", [])
        if findings:
            for f in findings[:10]:
                story.append(Paragraph(f"[{f['severity']}] {f['title']}", body))
                story.append(Paragraph(f"Confidence: {f['confidence']:.0%} | Type: {f.get('typology', 'N/A')}", label))
                story.append(Paragraph(f.get("description", "")[:200], label))
                story.append(Spacer(1, 3))
        else:
            story.append(Paragraph("No findings recorded.", body))
        story.append(Spacer(1, 8))

        # Transaction Timeline (abbreviated)
        story.append(Paragraph("6. Transaction Timeline (Top 20)", h2))
        timeline = report_data.get("transaction_timeline", [])[:20]
        if timeline:
            tdata = [["Timestamp", "From", "To", "Amount (INR)", "Channel"]]
            for txn in timeline:
                tdata.append([
                    txn["timestamp"][:16] if txn["timestamp"] else "?",
                    str(txn["from_account"])[:15] or "?",
                    str(txn["to_account"])[:15] or "?",
                    f"{txn['amount']:,.0f}",
                    txn["channel"] or "?",
                ])
            tt = Table(tdata, colWidths=[40*mm, 35*mm, 35*mm, 30*mm, 25*mm])
            tt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#283593")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]))
            story.append(tt)
        story.append(Spacer(1, 8))

        # Audit Trail (abbreviated)
        story.append(Paragraph("7. Audit Trail", h2))
        for ae in report_data.get("audit_events", []):
            story.append(Paragraph(
                f"[{ae['timestamp'][:19]}] {ae['actor']}: {ae['action']} — {ae['summary'][:120]}",
                label,
            ))
        story.append(Spacer(1, 8))

        # Disclaimer
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        story.append(Paragraph(
            "DISCLAIMER: This report was generated by FinSpectra, an automated financial crime investigation system. "
            "All findings are algorithmic recommendations and require human review before any regulatory action. "
            "This is SYNTHETIC DEMONSTRATION DATA — not a real financial record. "
            f"Policy version: {dec.get('policy_version', '1.0')}.",
            label,
        ))

        doc.build(story)
        return True
    except Exception as exc:
        logger.error("PDF generation failed", error=str(exc))
        return False


def report_generation(state: InvestigationState) -> InvestigationState:
    """
    Report Generation Node.
    
    Assembles structured report data from actual case state.
    Generates PDF via ReportLab.
    Deterministic — no LLM required for core report.
    """
    start_ts = time.time()
    case_id = state["case_id"]
    log = logger.bind(case_id=case_id)
    log.info("Report generation starting")

    report_data = _build_report_data(state)

    # Merge any existing graph_data
    existing_report_data = state.get("report_data") or {}
    if "graph_data" in existing_report_data:
        report_data["network_findings"] = existing_report_data["graph_data"]

    # Generate PDF
    os.makedirs(settings.reports_dir, exist_ok=True)
    pdf_filename = f"finspectra_report_{case_id[:8]}.pdf"
    pdf_path = os.path.join(settings.reports_dir, pdf_filename)
    pdf_ok = _generate_pdf(report_data, pdf_path)

    duration_ms = int((time.time() - start_ts) * 1000)
    log.info(
        "Report generation complete",
        pdf_generated=pdf_ok,
        pdf_path=pdf_path if pdf_ok else None,
        duration_ms=duration_ms,
    )

    audit = AuditRecord(
        case_id=case_id,
        actor="system:report_generation",
        action="REPORT_GENERATED",
        summary=(
            f"Investigation report generated. "
            f"PDF: {'Yes' if pdf_ok else 'Failed (JSON available)'}. "
            f"Sections: 14. Evidence items: {len(state.get('evidence') or [])}."
        ),
        metadata={
            "pdf_generated": pdf_ok,
            "pdf_path": pdf_path if pdf_ok else None,
            "duration_ms": duration_ms,
            "llm_used": False,
        },
    )

    audit_trail = list(state.get("audit_trail") or [])
    audit_trail.append(audit)

    return {
        **state,
        "report_data": report_data,
        "pdf_path": pdf_path if pdf_ok else None,
        "audit_trail": audit_trail,
    }
