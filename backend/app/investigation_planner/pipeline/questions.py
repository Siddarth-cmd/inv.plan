"""
Investigation Questions Generation Stage.

Converts red flags and information gaps into actionable investigation questions.
Questions are specific and measurable — not vague like "Is this suspicious?".
"""
from __future__ import annotations

from typing import List, Optional

from ..config.taxonomy import AnswerType, Priority
from ..schemas.information_gap import InformationGap
from ..schemas.question import InvestigationQuestion
from ..schemas.red_flag import RedFlag


def _q(
    question_id: str,
    question: str,
    objective: str,
    related_red_flags: List[str],
    information_gap: Optional[str],
    priority: str,
    expected_answer_type: str,
) -> InvestigationQuestion:
    return InvestigationQuestion(
        question_id=question_id,
        question=question,
        objective=objective,
        related_red_flags=related_red_flags,
        information_gap=information_gap,
        priority=priority,
        required_evidence=[],  # Populated by evidence stage
        expected_answer_type=expected_answer_type,
    )


def generate_investigation_questions(
    gaps: List[InformationGap],
    red_flags: List[RedFlag],
) -> List[InvestigationQuestion]:
    """Stage 7 – Generate actionable investigation questions from red flags and gaps."""
    questions: List[InvestigationQuestion] = []
    counter = 1
    seen: set = set()

    def add(q: InvestigationQuestion) -> None:
        nonlocal counter
        if q.question not in seen:
            q.question_id = f"Q{counter:03d}"
            questions.append(q)
            seen.add(q.question)
            counter += 1

    # ── Questions derived from red flags ──────────────────────────────────────
    for rf in red_flags:
        desc_lower = rf.description.lower()
        priority = rf.severity  # HIGH → HIGH, etc.

        if "high" in desc_lower and "amount" in desc_lower:
            add(_q("", "Is this transaction amount significantly outside the customer's historical behaviour?",
                   "Determine whether the transaction amount constitutes a statistical anomaly relative to the customer's known profile.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.BOOLEAN))
            add(_q("", "Can the source of funds for this transaction be established and documented?",
                   "Verify that the origin of the funds is legitimate and consistent with the customer's known income sources.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.DOCUMENT))

        if "beneficiary" in desc_lower:
            add(_q("", "Can the beneficiary relationship to the customer be established?",
                   "Determine whether a documented, plausible relationship exists between the customer and the beneficiary.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.BOOLEAN))
            add(_q("", "Has the customer transacted with this beneficiary previously?",
                   "Retrieve historical beneficiary transaction data to assess the novelty of the relationship.",
                   [rf.red_flag_id], None, Priority.MEDIUM, AnswerType.BOOLEAN))

        if "jurisdiction" in desc_lower or "high-risk" in desc_lower:
            add(_q("", "What is the stated business or personal purpose for the transaction to this jurisdiction?",
                   "Establish whether a plausible, documented reason exists for the cross-border destination.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.TEXT))
            add(_q("", "Is the beneficiary in the destination jurisdiction a known, verified counterparty?",
                   "Determine the identity and legitimacy of the receiving party in the high-risk jurisdiction.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.DOCUMENT))

        if "international" in desc_lower and "high-risk" not in desc_lower:
            add(_q("", "Is international transfer activity consistent with the customer's known profile?",
                   "Assess whether this is the customer's first or unusual international transfer.",
                   [rf.red_flag_id], None, Priority.MEDIUM, AnswerType.BOOLEAN))

        if "structuring" in desc_lower or "threshold" in desc_lower:
            add(_q("", "Are there other transactions by this customer in the same period that form a structuring pattern?",
                   "Retrieve full transaction history to assess whether transactions aggregate above the reporting threshold.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.NUMERIC))
            add(_q("", "Is the transaction amount consistently positioned just below the reporting threshold?",
                   "Determine whether there is a deliberate pattern of amount placement near the threshold.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.BOOLEAN))

        if "pass-through" in desc_lower or "mule" in desc_lower:
            add(_q("", "How long were the funds held in the account before the outbound transfer?",
                   "Determine the dwell time of funds to assess pass-through behaviour.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.NUMERIC))
            add(_q("", "Is the account's primary function consistent with this type of rapid transfer?",
                   "Compare the account's declared purpose with its actual transaction behaviour.",
                   [rf.red_flag_id], None, Priority.MEDIUM, AnswerType.BOOLEAN))

        if "device" in desc_lower or "account takeover" in desc_lower:
            add(_q("", "Was the device change immediately before the transfer authorised by the account holder?",
                   "Verify account holder consent for the device change and subsequent transfer.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.BOOLEAN))
            add(_q("", "Does the IP address and session data match the account holder's normal access pattern?",
                   "Assess whether session-level data indicates unauthorised access.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.BOOLEAN))

        if "kyc" in desc_lower or "identity" in desc_lower:
            add(_q("", "Are the customer's identity documents consistent, valid, and verifiable?",
                   "Verify the authenticity and consistency of the customer's identity documentation.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.DOCUMENT))
            add(_q("", "Are there any mismatches between the customer's KYC profile and their transaction behaviour?",
                   "Compare KYC-declared attributes with observed transaction patterns.",
                   [rf.red_flag_id], None, Priority.HIGH, AnswerType.BOOLEAN))

        if "system" in desc_lower or "anomalous" in desc_lower:
            add(_q("", "What specific pattern triggered the system alert?",
                   "Identify the underlying rule or model signal that produced this alert.",
                   [rf.red_flag_id], None, Priority.MEDIUM, AnswerType.TEXT))

    # ── Questions derived from information gaps ────────────────────────────────
    for gap in gaps:
        desc_lower = gap.description.lower()

        if "source of funds" in desc_lower:
            add(_q("", "Can the source of funds for this transaction be independently verified?",
                   "Obtain documentation of the funds' origin (salary, business revenue, savings, etc.).",
                   [], gap.gap_id, Priority.HIGH, AnswerType.DOCUMENT))

        if "transaction purpose" in desc_lower or "intent" in desc_lower:
            add(_q("", "What is the stated purpose of this transaction according to the customer?",
                   "Obtain customer-stated reason for the transaction for plausibility assessment.",
                   [], gap.gap_id, Priority.MEDIUM, AnswerType.TEXT))

        if "historical" in desc_lower:
            add(_q("", "Is this transaction consistent with the customer's historical transaction behaviour?",
                   "Retrieve and compare transaction history to identify statistical deviation.",
                   [], gap.gap_id, Priority.HIGH, AnswerType.BOOLEAN))

        if "beneficiary relationship" in desc_lower:
            add(_q("", "What is the nature of the relationship between the customer and the beneficiary?",
                   "Document the customer-beneficiary relationship type (family, business, personal, etc.).",
                   [], gap.gap_id, Priority.MEDIUM, AnswerType.TEXT))

        if "device" in desc_lower or "session" in desc_lower:
            add(_q("", "What device and session information is available for this transaction?",
                   "Retrieve device fingerprint, IP address, and session metadata.",
                   [], gap.gap_id, Priority.MEDIUM, AnswerType.DOCUMENT))

    # ── Fallback question if none generated ───────────────────────────────────
    if not questions:
        add(_q("", "What further information is required to assess the nature of this alert?",
               "Conduct a preliminary manual review to determine next investigative steps.",
               [rf.red_flag_id for rf in red_flags[:1]],
               gaps[0].gap_id if gaps else None,
               Priority.HIGH, AnswerType.TEXT))

    return questions
