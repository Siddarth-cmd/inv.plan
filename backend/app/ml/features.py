"""
Feature engineering for transaction anomaly detection.
Builds meaningful features from raw transaction data.
Features are documented — not arbitrary IDs fed into the model.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "amount",
    "log_amount",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "account_tx_count_7d",
    "account_tx_count_30d",
    "account_total_volume_7d",
    "account_total_volume_30d",
    "account_unique_counterparties_7d",
    "amount_vs_account_mean",
    "amount_vs_account_std",
    "time_since_last_tx_hours",
    "is_round_amount",
    "channel_encoded",
]


def build_features(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build feature matrix from transactions DataFrame.

    Args:
        transactions_df: DataFrame with columns:
            id, from_account_number, to_account_number, amount,
            timestamp, channel, transaction_type

    Returns:
        DataFrame with feature columns and 'id' index.
    """
    df = transactions_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Basic amount features
    df["log_amount"] = df["amount"].apply(lambda x: math.log1p(max(x, 0)))
    df["is_round_amount"] = (df["amount"] % 1000 == 0).astype(int)

    # Temporal features
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Channel encoding
    channel_map = {"UPI": 0, "NEFT": 1, "IMPS": 2, "RTGS": 3, "CASH": 4, "ATM": 5, "ONLINE": 6, "UNKNOWN": 7}
    df["channel_encoded"] = df["channel"].map(channel_map).fillna(7).astype(int)

    # Account-level rolling features
    account_7d_count = {}
    account_30d_count = {}
    account_7d_vol = {}
    account_30d_vol = {}
    account_7d_counterparties = {}
    time_since_last = {}
    last_tx_time = {}
    account_amounts = {}

    tx_counts_7d = []
    tx_counts_30d = []
    tx_vols_7d = []
    tx_vols_30d = []
    tx_cp_7d = []
    time_since = []
    amount_vs_mean = []
    amount_vs_std = []

    for _, row in df.iterrows():
        acc = row["from_account_number"] or "UNKNOWN"
        ts = row["timestamp"]
        amt = row["amount"]
        to_acc = row["to_account_number"] or "UNKNOWN"

        # Rolling windows
        hist_7d = [
            (t, a, cp)
            for t, a, cp in account_7d_count.get(acc, [])
            if ts - t <= timedelta(days=7)
        ]
        hist_30d = [
            (t, a, cp)
            for t, a, cp in account_30d_count.get(acc, [])
            if ts - t <= timedelta(days=30)
        ]

        tx_counts_7d.append(len(hist_7d))
        tx_counts_30d.append(len(hist_30d))
        tx_vols_7d.append(sum(a for _, a, _ in hist_7d))
        tx_vols_30d.append(sum(a for _, a, _ in hist_30d))
        tx_cp_7d.append(len(set(cp for _, _, cp in hist_7d)))

        # Time since last transaction
        if acc in last_tx_time:
            delta_hours = (ts - last_tx_time[acc]).total_seconds() / 3600
        else:
            delta_hours = 24 * 30  # assume 30 days for first transaction
        time_since.append(min(delta_hours, 24 * 30))

        # Amount vs historical mean/std
        historical_amounts = account_amounts.get(acc, [])
        if len(historical_amounts) >= 2:
            hist_mean = np.mean(historical_amounts)
            hist_std = max(np.std(historical_amounts), 1.0)
            amount_vs_mean.append((amt - hist_mean) / hist_std)
            amount_vs_std.append(hist_std)
        else:
            amount_vs_mean.append(0.0)
            amount_vs_std.append(0.0)

        # Update rolling state
        account_7d_count[acc] = hist_7d + [(ts, amt, to_acc)]
        account_30d_count[acc] = hist_30d + [(ts, amt, to_acc)]
        last_tx_time[acc] = ts
        if acc not in account_amounts:
            account_amounts[acc] = []
        account_amounts[acc].append(amt)

    df["account_tx_count_7d"] = tx_counts_7d
    df["account_tx_count_30d"] = tx_counts_30d
    df["account_total_volume_7d"] = tx_vols_7d
    df["account_total_volume_30d"] = tx_vols_30d
    df["account_unique_counterparties_7d"] = tx_cp_7d
    df["time_since_last_tx_hours"] = time_since
    df["amount_vs_account_mean"] = amount_vs_mean
    df["amount_vs_account_std"] = amount_vs_std

    return df[["id"] + FEATURE_COLUMNS]


def get_feature_columns() -> list[str]:
    return FEATURE_COLUMNS
