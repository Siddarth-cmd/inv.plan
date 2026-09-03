"""
FinSpectra Synthetic Transaction Dataset Generator.
Produces a deterministic, reproducible CSV with 7 AML scenarios.
SYNTHETIC DATA ONLY — NOT real financial records.
"""
from __future__ import annotations

import csv
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

SEED = 42
random.seed(SEED)

BASE_DATE = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

CHANNELS = ["UPI", "NEFT", "IMPS", "RTGS", "CASH", "ONLINE"]


def _dt(days_offset: float, hour: int = 9) -> str:
    d = BASE_DATE + timedelta(days=days_offset, hours=hour)
    return d.isoformat()


def _ref() -> str:
    return f"TXN{uuid.uuid4().hex[:12].upper()}"


rows = []

# ── Scenario A: Normal Customer (C001 / ACC001)
# Regular small UPI transactions, no suspicious patterns
for i in range(20):
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC001",
        "to_account": f"SHOP{random.randint(100,199):03d}",
        "from_customer": "C001",
        "to_customer": "",
        "amount": round(random.uniform(200, 2000), 2),
        "currency": "INR",
        "channel": "UPI",
        "transaction_type": "DEBIT",
        "timestamp": _dt(random.uniform(0, 59), hour=random.randint(8, 20)),
        "description": "Regular purchase",
        "ip_address": "103.21.45.1",
        "device_id": "DEV_A001",
        "location": "Mumbai",
        "scenario_label": "A_NORMAL",
    })

# ── Scenario B: Large Unusual Transfer (C002 / ACC002)
# One extremely large transfer against low historical baseline
for i in range(3):
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC002",
        "to_account": "ACC_FOREIGN_001",
        "from_customer": "C002",
        "to_customer": "C_FOREIGN_001",
        "amount": round(random.uniform(1_500_000, 4_000_000), 2),
        "currency": "INR",
        "channel": "RTGS",
        "transaction_type": "DEBIT",
        "timestamp": _dt(random.uniform(30, 45), hour=random.randint(1, 5)),
        "description": "Wire transfer",
        "ip_address": "45.33.0.1",
        "device_id": "DEV_B002",
        "location": "Delhi",
        "scenario_label": "B_LARGE_TRANSFER",
    })
# Normal baseline for C002
for i in range(5):
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC002",
        "to_account": f"VENDOR{random.randint(1,50):03d}",
        "from_customer": "C002",
        "to_customer": "",
        "amount": round(random.uniform(5000, 25000), 2),
        "currency": "INR",
        "channel": "NEFT",
        "transaction_type": "DEBIT",
        "timestamp": _dt(random.uniform(0, 29), hour=random.randint(10, 16)),
        "description": "Vendor payment",
        "ip_address": "45.33.0.1",
        "device_id": "DEV_B002",
        "location": "Delhi",
        "scenario_label": "A_NORMAL",
    })

# ── Scenario C: Structuring / Smurfing (C003 / ACC003)
# Multiple transfers just below 10L threshold
for i in range(12):
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC003",
        "to_account": f"ACC_STRUCT_{i % 4:02d}",
        "from_customer": "C003",
        "to_customer": f"C_S{i % 4:02d}",
        "amount": round(random.uniform(89000, 99500), 2),
        "currency": "INR",
        "channel": random.choice(["CASH", "IMPS"]),
        "transaction_type": "DEBIT",
        "timestamp": _dt(random.uniform(60, 90), hour=random.randint(9, 17)),
        "description": "Cash deposit",
        "ip_address": "192.168.1.10",
        "device_id": "DEV_C003",
        "location": "Bengaluru",
        "scenario_label": "C_STRUCTURING",
    })

# ── Scenario D: Rapid Pass-Through / Layering (C004 / ACC004 chain)
# Money in → immediately out to multiple accounts
chain_in_times = [_dt(95 + i * 0.04, hour=10) for i in range(5)]
chain_out_times = [_dt(95 + i * 0.04 + 0.02, hour=10) for i in range(5)]
for i in range(5):
    # Credit into ACC004
    rows.append({
        "txn_ref": _ref(),
        "from_account": f"ACC_SOURCE_{i}",
        "to_account": "ACC004",
        "from_customer": f"C_SRC_{i}",
        "to_customer": "C004",
        "amount": round(random.uniform(200000, 500000), 2),
        "currency": "INR",
        "channel": "IMPS",
        "transaction_type": "CREDIT",
        "timestamp": chain_in_times[i],
        "description": "Fund transfer",
        "ip_address": "10.0.0.1",
        "device_id": "DEV_D004",
        "location": "Chennai",
        "scenario_label": "D_LAYERING",
    })
    # Immediate debit out
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC004",
        "to_account": f"ACC_DEST_{i}",
        "from_customer": "C004",
        "to_customer": f"C_DST_{i}",
        "amount": round(random.uniform(180000, 490000), 2),
        "currency": "INR",
        "channel": "IMPS",
        "transaction_type": "DEBIT",
        "timestamp": chain_out_times[i],
        "description": "Fund transfer out",
        "ip_address": "10.0.0.1",
        "device_id": "DEV_D004",
        "location": "Chennai",
        "scenario_label": "D_LAYERING",
    })

# ── Scenario E: Circular Money Movement (C005/ACC005 → ACC006 → ACC007 → ACC005)
circle_base = 100
for cycle in range(3):
    t = _dt(105 + cycle * 2)
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC005",
        "to_account": "ACC006",
        "from_customer": "C005",
        "to_customer": "C006",
        "amount": round(random.uniform(300000, 500000), 2),
        "currency": "INR",
        "channel": "NEFT",
        "transaction_type": "TRANSFER",
        "timestamp": t,
        "description": "Business payment",
        "ip_address": "172.16.0.5",
        "device_id": "DEV_E005",
        "location": "Hyderabad",
        "scenario_label": "E_CIRCULAR",
    })
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC006",
        "to_account": "ACC007",
        "from_customer": "C006",
        "to_customer": "C007",
        "amount": round(random.uniform(280000, 480000), 2),
        "currency": "INR",
        "channel": "NEFT",
        "transaction_type": "TRANSFER",
        "timestamp": _dt(105 + cycle * 2, hour=11),
        "description": "Settlement",
        "ip_address": "172.16.0.6",
        "device_id": "DEV_E006",
        "location": "Hyderabad",
        "scenario_label": "E_CIRCULAR",
    })
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC007",
        "to_account": "ACC005",
        "from_customer": "C007",
        "to_customer": "C005",
        "amount": round(random.uniform(260000, 460000), 2),
        "currency": "INR",
        "channel": "NEFT",
        "transaction_type": "TRANSFER",
        "timestamp": _dt(105 + cycle * 2, hour=13),
        "description": "Return payment",
        "ip_address": "172.16.0.7",
        "device_id": "DEV_E007",
        "location": "Hyderabad",
        "scenario_label": "E_CIRCULAR",
    })

# ── Scenario F: Multiple Accounts, Shared Device (C008, C009, C010 / same DEV_F001)
for cust_idx, acc in enumerate(["ACC008", "ACC009", "ACC010"]):
    cust = f"C00{8 + cust_idx}"
    for i in range(8):
        rows.append({
            "txn_ref": _ref(),
            "from_account": acc,
            "to_account": "ACC_AGGREGATOR",
            "from_customer": cust,
            "to_customer": "C_AGGREGATOR",
            "amount": round(random.uniform(10000, 80000), 2),
            "currency": "INR",
            "channel": "UPI",
            "transaction_type": "DEBIT",
            "timestamp": _dt(random.uniform(110, 140), hour=random.randint(8, 22)),
            "description": "Transfer",
            "ip_address": "203.0.113.5",
            "device_id": "DEV_F001",  # shared device — entity resolution signal
            "location": "Pune",
            "scenario_label": "F_SHARED_DEVICE",
        })

# ── Scenario G: Mixed Normal + Suspicious (C011 / ACC011)
for i in range(15):
    rows.append({
        "txn_ref": _ref(),
        "from_account": "ACC011",
        "to_account": f"RETAIL{random.randint(1, 30):03d}",
        "from_customer": "C011",
        "to_customer": "",
        "amount": round(random.uniform(500, 5000), 2),
        "currency": "INR",
        "channel": "UPI",
        "transaction_type": "DEBIT",
        "timestamp": _dt(random.uniform(0, 59), hour=random.randint(9, 18)),
        "description": "Retail",
        "ip_address": "106.51.10.2",
        "device_id": "DEV_G011",
        "location": "Kolkata",
        "scenario_label": "A_NORMAL",
    })
# Sudden suspicious transfer
rows.append({
    "txn_ref": _ref(),
    "from_account": "ACC011",
    "to_account": "ACC_SUSPICIOUS_01",
    "from_customer": "C011",
    "to_customer": "C_SUSPICIOUS_01",
    "amount": 950000.00,
    "currency": "INR",
    "channel": "IMPS",
    "transaction_type": "DEBIT",
    "timestamp": _dt(62, hour=2),
    "description": "Urgent transfer",
    "ip_address": "192.0.2.99",
    "device_id": "DEV_UNKNOWN",
    "location": "Unknown",
    "scenario_label": "G_MIXED_SUSPICIOUS",
})

# Sort by timestamp for realism
rows.sort(key=lambda r: r["timestamp"])

# Write CSV
out_dir = os.path.join(os.path.dirname(__file__), "..", "datasets", "raw")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "synthetic_transactions.csv")

fieldnames = [
    "txn_ref", "from_account", "to_account", "from_customer", "to_customer",
    "amount", "currency", "channel", "transaction_type", "timestamp",
    "description", "ip_address", "device_id", "location", "scenario_label",
]

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} synthetic transactions -> {out_path}")
