"""
Sample Alert Scenarios for the FinSpectra Investigation Planner.

8 materially different alert scenarios for testing and UI demonstration.
All scenarios use RawAlertInput-compatible field names.
"""
from __future__ import annotations
from typing import Any, Dict

_SCENARIOS: Dict[int, Dict[str, Any]] = {
    1: {
        "alert_id": "ALT-1001",
        "customer_id": "CUST-4421",
        "transaction_id": "TXN-8801",
        "alert_type": "High-Value Unusual Transaction",
        "alert_reason": "₹485,000 international transfer to a new beneficiary",
        "transaction_amount": 485000.0,
        "currency": "INR",
        "transaction_type": "International Wire Transfer",
        "timestamp": "2024-11-15T09:22:00Z",
        "origin_country": "IN",
        "destination_country": "AE",
        "beneficiary_information": {"status": "NEW", "name": "NOT_PROVIDED", "account_number": "NOT_PROVIDED"},
        "customer_information": {"risk_rating": "MEDIUM", "account_tenure_years": 3},
        "historical_information": None,
    },
    2: {
        "alert_id": "ALT-1002",
        "customer_id": "CUST-7723",
        "transaction_id": "TXN-5512",
        "alert_type": "Structuring",
        "alert_reason": "Multiple cash deposits of ₹49,000 over 4 consecutive days — potential structuring below ₹50,000 threshold",
        "transaction_amount": 49000.0,
        "currency": "INR",
        "transaction_type": "Cash Deposit",
        "timestamp": "2024-11-10T14:00:00Z",
        "origin_country": "IN",
        "destination_country": None,
        "customer_information": {"account_type": "Savings", "occupation": "UNKNOWN"},
    },
    3: {
        "alert_id": "ALT-1003",
        "customer_id": "CUST-3301",
        "transaction_id": "TXN-2233",
        "alert_type": "Mule Pattern",
        "alert_reason": "Rapid pass-through transfer — funds received and immediately sent out within 30 minutes",
        "transaction_amount": 100000.0,
        "currency": "INR",
        "transaction_type": "Pass-Through Transfer",
        "timestamp": "2024-11-12T11:05:00Z",
        "origin_country": "IN",
        "destination_country": "IN",
        "customer_information": {"account_age_days": 15, "account_type": "Current"},
    },
    4: {
        "alert_id": "ALT-1004",
        "customer_id": "CUST-9981",
        "transaction_id": "TXN-6601",
        "alert_type": "International Risk",
        "alert_reason": "Wire transfer to high-risk jurisdiction with no prior international transfer history",
        "transaction_amount": 250000.0,
        "currency": "USD",
        "transaction_type": "Wire",
        "timestamp": "2024-11-18T08:30:00Z",
        "origin_country": "IN",
        "destination_country": "HighRiskCountry",
        "beneficiary_information": {"status": "NEW", "name": "NOT_PROVIDED"},
        "customer_information": {"international_transfers_prior": 0},
    },
    5: {
        "alert_id": "ALT-1005",
        "customer_id": "CUST-6612",
        "transaction_id": "TXN-7745",
        "alert_type": "Account Takeover",
        "alert_reason": "Device change recorded at 02:14 AM followed immediately by ₹80,000 transfer at 02:17 AM",
        "transaction_amount": 80000.0,
        "currency": "INR",
        "transaction_type": "Internal Transfer",
        "timestamp": "2024-11-20T02:17:00Z",
        "origin_country": "IN",
        "destination_country": "IN",
        "customer_information": {"account_type": "Savings", "normal_hours": "09:00–20:00"},
    },
    6: {
        "alert_id": "ALT-1006",
        "customer_id": "CUST-0012",
        "transaction_id": "TXN-9900",
        "alert_type": "Identity/KYC Risk",
        "alert_reason": "KYC validation flagged — identity document inconsistencies detected; synthetic ID indicators present",
        "transaction_amount": 150000.0,
        "currency": "INR",
        "transaction_type": "Transfer",
        "timestamp": "2024-11-14T10:00:00Z",
        "origin_country": "IN",
        "destination_country": "IN",
        "customer_information": {"kyc_status": "FLAGGED", "document_mismatch": True},
    },
    7: {
        "alert_id": "ALT-1007",
        "alert_type": "Unknown",
        "alert_reason": "System alert — insufficient transaction data to determine alert type",
    },
    8: {
        "alert_id": "ALT-1008",
        "customer_id": "CUST-5544",
        "transaction_id": "TXN-3310",
        "alert_type": "Legitimate-Looking Unusual Transaction",
        "alert_reason": "High-value transfer consistent with customer's declared business activity",
        "transaction_amount": 500000.0,
        "currency": "INR",
        "transaction_type": "Business Wire Transfer",
        "timestamp": "2024-11-19T14:00:00Z",
        "origin_country": "IN",
        "destination_country": "SG",
        "customer_information": {
            "account_type": "Business Current",
            "declared_business": "Export Trade",
            "risk_rating": "LOW",
        },
        "historical_information": {
            "avg_monthly_transfer_INR": 450000,
            "international_transfers_prior": 12,
        },
    },
}

SCENARIO_LABELS: Dict[int, str] = {
    1: "High-Value Unusual Transaction",
    2: "Potential Structuring Pattern",
    3: "Potential Mule Account",
    4: "Unusual International Transfer (High-Risk Jurisdiction)",
    5: "Account Takeover-Style Alert",
    6: "Identity / KYC Anomaly",
    7: "Insufficient Information Alert",
    8: "Legitimate-Looking Unusual Transaction",
}


def get_scenario(scenario_id: int) -> Dict[str, Any]:
    return dict(_SCENARIOS.get(scenario_id, _SCENARIOS[1]))


def get_all_scenarios() -> Dict[int, Dict[str, Any]]:
    return {sid: dict(data) for sid, data in _SCENARIOS.items()}


def get_scenario_labels() -> Dict[int, str]:
    return dict(SCENARIO_LABELS)
