"""
Evidence Requirements Mapping Stage.

For every investigation question, determine what evidence is required to answer it.
Evidence availability is stated honestly — UNKNOWN when not assessable from the alert.
"""
from __future__ import annotations

from typing import List, Tuple

from ..config.taxonomy import Availability
from ..schemas.evidence import EvidenceRequirement
from ..schemas.question import InvestigationQuestion

# ─── Evidence templates: (trigger_keyword, evidence_type, description, why, source_cat) ───
_TEMPLATES: List[Tuple[str, str, str, str, str]] = [
    ("historical behav", "Transaction History",
     "Customer's full historical transaction records",
     "Required to establish a behavioural baseline and detect statistical anomaly",
     "Internal — Core Banking System"),

    ("source of funds", "Financial Documentation",
     "Source-of-funds documentation (payslips, bank statements, business records)",
     "Required to verify the origin of the transacted funds",
     "Customer-Provided / External"),

    ("beneficiary relationship", "Beneficiary Records",
     "Beneficiary identity documents and relationship history",
     "Required to assess the legitimacy of the customer-beneficiary relationship",
     "Internal — CRM / Beneficiary Register"),

    ("beneficiary previously", "Transaction History",
     "Prior transactions between the customer and this beneficiary",
     "Required to determine whether the beneficiary is a recurring or novel counterparty",
     "Internal — Core Banking System"),

    ("purpose", "Customer Communication",
     "Customer-stated transaction purpose (written declaration or interview notes)",
     "Required to assess the plausibility of the transaction's stated purpose",
     "Customer-Provided"),

    ("jurisdiction", "Jurisdictional Risk Data",
     "Regulatory risk classification for the destination jurisdiction",
     "Required to confirm the destination's risk level and applicable AML requirements",
     "External — FATF / Sanctions Lists"),

    ("counterparty", "Counterparty KYC Records",
     "KYC and identity records for the beneficiary in the destination jurisdiction",
     "Required to verify the legitimacy of the receiving entity",
     "External — Correspondent Bank / Registry"),

    ("international", "Cross-Border Transfer History",
     "Historical international transfers by this customer",
     "Required to determine whether international transfers are part of the customer's normal profile",
     "Internal — Core Banking System"),

    ("structuring pattern", "Full Transaction Ledger",
     "Complete transaction ledger for the assessment period",
     "Required to aggregate transactions and identify structuring patterns",
     "Internal — Core Banking System"),

    ("reporting threshold", "Regulatory Reporting Records",
     "Previous cash transaction reports (CTRs) filed for this customer",
     "Required to identify a pattern of deliberate threshold avoidance",
     "Internal — Compliance System"),

    ("dwell time", "Account Activity Timeline",
     "Timestamp-level account debit/credit sequence",
     "Required to calculate the duration funds were held before onward transfer",
     "Internal — Core Banking System"),

    ("account's primary function", "Account Opening Records",
     "Account purpose declaration and KYC from account opening",
     "Required to compare declared purpose with actual behaviour",
     "Internal — Account Management System"),

    ("device", "Device & Session Logs",
     "Device fingerprint, IP address, geolocation, and session metadata at time of transaction",
     "Required to assess account access authenticity and detect session anomalies",
     "Internal — Digital Banking Platform"),

    ("session", "Session Audit Logs",
     "Complete session audit log for the transaction event",
     "Required to reconstruct the access sequence and verify account holder presence",
     "Internal — Digital Banking Platform"),

    ("identity document", "KYC Documentation",
     "Government-issued ID, proof of address, and KYC verification records",
     "Required to verify the authenticity and consistency of the customer's identity",
     "Customer-Provided / Internal KYC System"),

    ("kyc profile", "KYC Profile & Transaction Comparison",
     "KYC-declared attributes alongside full transaction behaviour profile",
     "Required to identify discrepancies between stated and actual customer activity",
     "Internal — KYC System + Core Banking System"),

    ("system alert", "Alert Engine Logs",
     "Detection engine rule/model output and signal detail",
     "Required to understand the precise trigger that generated this alert",
     "Internal — Alert Engine"),
]

_DEFAULT_TEMPLATE = (
    "",  # trigger keyword (empty — used as fallback)
    "Supporting Documentation",
    "Documentation or data relevant to the investigation question",
    "Required to answer the investigation question",
    "Internal / External — to be determined",
)


def map_evidence_requirements(questions: List[InvestigationQuestion]) -> List[EvidenceRequirement]:
    """Stage 8 – Map required evidence to each investigation question."""
    evidence_reqs: List[EvidenceRequirement] = []
    ev_counter = 1
    # evidence_text → EvidenceRequirement (to deduplicate and share across questions)
    dedup_map: dict = {}

    for q in questions:
        q_lower = q.question.lower()
        matched_templates = [t for t in _TEMPLATES if t[0] in q_lower]

        if not matched_templates:
            matched_templates = [_DEFAULT_TEMPLATE]

        for template in matched_templates:
            ev_type, desc, why, source_cat = template[1], template[2], template[3], template[4]
            key = (ev_type, desc)

            if key in dedup_map:
                # Existing evidence — just link the question
                existing_req = dedup_map[key]
                if q.question_id not in existing_req.related_question_ids:
                    existing_req.related_question_ids.append(q.question_id)
                if existing_req.evidence_id not in q.required_evidence:
                    q.required_evidence.append(existing_req.evidence_id)
            else:
                ev_id = f"EV{ev_counter:03d}"
                req = EvidenceRequirement(
                    evidence_id=ev_id,
                    evidence_type=ev_type,
                    description=desc,
                    why_required=why,
                    source_category=source_cat,
                    availability=Availability.UNKNOWN,
                    related_question_ids=[q.question_id],
                )
                evidence_reqs.append(req)
                dedup_map[key] = req
                q.required_evidence.append(ev_id)
                ev_counter += 1

    return evidence_reqs
