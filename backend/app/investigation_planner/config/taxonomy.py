"""
Investigation Planner Taxonomy Configuration.
All category names, severity levels, priority levels, and enum constants
are defined here. Do NOT scatter these throughout the codebase.
"""
from __future__ import annotations
from typing import Dict, List, Any

# ─── Alert Classification Categories ───────────────────────────────────────────
CATEGORIES: List[str] = [
    "Transaction Fraud",
    "Money Laundering",
    "Potential Layering",
    "Structuring",
    "Mule Activity",
    "Account Takeover",
    "Identity/KYC Risk",
    "Sanctions/AML Risk",
    "Card/Payment Fraud",
    "Cross-Border Risk",
    "Other",
    "Unknown / Requires Review",
]

# ─── Category → Typology/Subcategory mapping ───────────────────────────────────
TYPOLOGIES: Dict[str, List[str]] = {
    "Money Laundering":    ["Potential Layering", "Potential Integration", "Potential Placement"],
    "Potential Layering":  ["High-Value Transfer", "Cross-Border Layering", "Rapid Asset Movement"],
    "Structuring":         ["Smurfing", "Below-Threshold Deposits", "Structured Cash"],
    "Mule Activity":       ["Mule Account", "Pass-Through Transfer", "Rapid In-Out"],
    "Account Takeover":    ["Credential Compromise", "Device Anomaly", "Session Hijack"],
    "Identity/KYC Risk":   ["Synthetic Identity", "Document Fraud", "Identity Mismatch"],
    "Sanctions/AML Risk":  ["OFAC Hit", "PEP Exposure", "Sanctioned Jurisdiction"],
    "Cross-Border Risk":   ["High-Risk Jurisdiction", "Unusual Cross-Border", "FATF Non-Compliant Country"],
    "Card/Payment Fraud":  ["CNP Fraud", "Card Skimming", "Chargeback Abuse"],
    "Transaction Fraud":   ["First-Party Fraud", "Authorised Push Payment", "Unusual Transaction"],
}

# ─── Classification Rules (priority-ordered) ──────────────────────────────────
# Each rule maps a set of signal keys → (category, typology, base_confidence)
CLASSIFICATION_RULES: List[Dict[str, Any]] = [
    # Account Takeover
    {
        "signals": ["device_change", "rapid_transfer_after_device_change"],
        "category": "Account Takeover",
        "typology": "Device Anomaly",
        "base_confidence": 0.82,
    },
    # Structuring — below-threshold repeated deposits
    {
        "signals": ["below_threshold_amount", "multiple_transactions"],
        "category": "Structuring",
        "typology": "Smurfing",
        "base_confidence": 0.80,
    },
    # Mule Activity
    {
        "signals": ["pass_through_pattern", "new_account"],
        "category": "Mule Activity",
        "typology": "Rapid In-Out",
        "base_confidence": 0.78,
    },
    # Sanctions / High-Risk Jurisdiction
    {
        "signals": ["high_risk_jurisdiction"],
        "category": "Sanctions/AML Risk",
        "typology": "Sanctioned Jurisdiction",
        "base_confidence": 0.80,
    },
    # Cross-Border Risk  
    {
        "signals": ["international_transfer", "high_risk_jurisdiction"],
        "category": "Cross-Border Risk",
        "typology": "High-Risk Jurisdiction",
        "base_confidence": 0.76,
    },
    # Cross-Border — general international
    {
        "signals": ["international_transfer"],
        "category": "Cross-Border Risk",
        "typology": "Unusual Cross-Border",
        "base_confidence": 0.68,
    },
    # Potential Layering
    {
        "signals": ["high_value", "new_beneficiary"],
        "category": "Potential Layering",
        "typology": "High-Value Transfer",
        "base_confidence": 0.75,
    },
    {
        "signals": ["high_value"],
        "category": "Potential Layering",
        "typology": "Rapid Asset Movement",
        "base_confidence": 0.65,
    },
    # KYC Risk
    {
        "signals": ["kyc_anomaly"],
        "category": "Identity/KYC Risk",
        "typology": "Synthetic Identity",
        "base_confidence": 0.77,
    },
]

# ─── High-risk jurisdictions (FATF grey/black list examples) ──────────────────
HIGH_RISK_JURISDICTIONS: List[str] = [
    "AF", "IQ", "IR", "LY", "KP", "SO", "SS", "SY", "YE",
    "PK", "MM", "ET", "PH",
    # Common string representations used in tests
    "HighRiskCountry", "HIGH_RISK", "SANCTIONED",
    "afghanistan", "iran", "north korea", "north_korea",
    "iraq", "libya", "syria", "somalia",
]

# ─── Severity Levels ───────────────────────────────────────────────────────────
class Severity:
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"

# ─── Priority Levels ──────────────────────────────────────────────────────────
class Priority:
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"

# ─── Availability Levels ──────────────────────────────────────────────────────
class Availability:
    AVAILABLE           = "AVAILABLE"
    UNAVAILABLE         = "UNAVAILABLE"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"
    UNKNOWN             = "UNKNOWN"

# ─── Expected Answer Types ────────────────────────────────────────────────────
class AnswerType:
    BOOLEAN  = "BOOLEAN"
    NUMERIC  = "NUMERIC"
    CATEGORICAL = "CATEGORICAL"
    TEXT     = "TEXT"
    DOCUMENT = "DOCUMENT"

# ─── Possible Investigation Outcomes ─────────────────────────────────────────
class Outcome:
    LEGITIMATE_ACTIVITY    = "LEGITIMATE_ACTIVITY"
    SUSPICIOUS_ACTIVITY    = "SUSPICIOUS_ACTIVITY"
    INSUFFICIENT_EVIDENCE  = "INSUFFICIENT_EVIDENCE"
    FURTHER_REVIEW_REQUIRED= "FURTHER_REVIEW_REQUIRED"
    ESCALATION_REQUIRED    = "ESCALATION_REQUIRED"

ALL_OUTCOMES: List[str] = [
    Outcome.LEGITIMATE_ACTIVITY,
    Outcome.SUSPICIOUS_ACTIVITY,
    Outcome.INSUFFICIENT_EVIDENCE,
    Outcome.FURTHER_REVIEW_REQUIRED,
    Outcome.ESCALATION_REQUIRED,
]

# ─── Classification Status ────────────────────────────────────────────────────
class ClassificationStatus:
    CONFIRMED       = "CONFIRMED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

# ─── Thresholds ───────────────────────────────────────────────────────────────
HIGH_VALUE_THRESHOLD_INR = 200_000   # ₹2,00,000
HIGH_VALUE_THRESHOLD_USD = 10_000    # $10,000
STRUCTURING_THRESHOLD_INR= 50_000    # just below 50k
