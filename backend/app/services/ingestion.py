"""
CSV Ingestion Service.

Validates, normalizes, and persists transaction records from uploaded CSV.
Reports an ingestion summary with rejected/duplicate/flagged counts.
Does NOT silently discard records — all rejections are logged with reasons.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Account, Customer, Transaction, EvidenceLog, ThreatIntel, Entity
from app.schemas import IngestionSummary

logger = structlog.get_logger("finspectra.services.ingestion")

# Canonical column mapping for financial transactions
COLUMN_ALIASES: dict[str, str] = {
    "txn_ref": "txn_ref",
    "transaction_id": "txn_ref",
    "from_account": "from_account_number",
    "from_account_number": "from_account_number",
    "sender_account": "from_account_number",
    "to_account": "to_account_number",
    "to_account_number": "to_account_number",
    "receiver_account": "to_account_number",
    "from_customer": "from_customer",
    "to_customer": "to_customer",
    "amount": "amount",
    "value": "amount",
    "currency": "currency",
    "channel": "channel",
    "payment_method": "channel",
    "transaction_type": "transaction_type",
    "type": "transaction_type",
    "timestamp": "timestamp",
    "date_time": "timestamp",
    "transaction_date": "timestamp",
    "description": "description",
    "narration": "description",
    "ip_address": "ip_address",
    "device_id": "device_id",
    "location": "location",
    "scenario_label": "scenario_label",
}

REQUIRED_CANONICAL = {"txn_ref", "amount", "timestamp"}
VALID_CHANNELS = {"UPI", "NEFT", "IMPS", "RTGS", "CASH", "ATM", "ONLINE", "UNKNOWN"}
VALID_TXN_TYPES = {"CREDIT", "DEBIT", "TRANSFER"}
MAX_AMOUNT = 1e12  # 1 trillion — reject anything above as likely data error


async def ingest_csv(
    file_content: bytes,
    db: AsyncSession,
    filename: str = "upload.csv",
) -> IngestionSummary:
    """
    Validate, normalize, and persist records from a CSV upload.
    Auto-detects dataset format: WAF Evidence Logs, Threat Intelligence, or Financial Transactions.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_content), dtype=str)
    except Exception as exc:
        return IngestionSummary(
            total_rows=0,
            accepted_rows=0,
            rejected_rows=0,
            duplicate_rows=0,
            flagged_rows=0,
            errors=[{"row": 0, "reason": f"CSV parse error: {exc}"}],
        )

    cols = [c.strip().lower().replace(".", "_") for c in df.columns]
    
    # Auto-detect dataset format
    if "src_ip" in cols or "bytes_in" in cols or "rule_names" in cols:
        logger.info("Auto-detected Evidence Dataset (WAF / Network Logs)")
        return await ingest_evidence_csv(file_content, db, filename)
    elif "ip_address" in cols and ("abuse_confidence_score" in cols or "risk_level" in cols or "severity" in cols):
        logger.info("Auto-detected Threat Dataset (IP Threat Intelligence)")
        return await ingest_threat_csv(file_content, db, filename)
    else:
        logger.info("Processing as Financial Transactions Dataset")
        return await ingest_transactions_csv(df, db, filename)


async def ingest_evidence_csv(
    file_content: bytes,
    db: AsyncSession,
    filename: str = "evidence.csv",
) -> IngestionSummary:
    """Ingest Evidence Dataset (Network WAF logs)."""
    df = pd.read_csv(io.BytesIO(file_content), dtype=str)
    df.columns = [c.strip().lower().replace(".", "_") for c in df.columns]
    
    accepted = 0
    rejected = 0
    duplicates = 0
    flagged = 0
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2
        src_ip = str(row.get("src_ip", "")).strip()
        if not src_ip or src_ip.lower() in ("nan", "none", ""):
            rejected += 1
            errors.append({"row": row_num, "reason": "Missing src_ip"})
            continue

        try:
            bytes_in = int(float(str(row.get("bytes_in", 0)).strip() or 0))
            bytes_out = int(float(str(row.get("bytes_out", 0)).strip() or 0))
        except ValueError:
            bytes_in, bytes_out = 0, 0

        ts_raw = str(row.get("creation_time", row.get("timestamp", ""))).strip()
        try:
            ts = pd.to_datetime(ts_raw, utc=True).to_pydatetime()
        except Exception:
            ts = datetime.now(timezone.utc)

        end_ts_raw = str(row.get("end_time", "")).strip()
        end_ts = None
        if end_ts_raw and end_ts_raw.lower() not in ("nan", "none", ""):
            try:
                end_ts = pd.to_datetime(end_ts_raw, utc=True).to_pydatetime()
            except Exception:
                end_ts = None

        rule_names = str(row.get("rule_names", "Suspicious Web Traffic")).strip()
        detection_types = str(row.get("detection_types", "waf_rule")).strip()

        # Save EvidenceLog record
        log_entry = EvidenceLog(
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            creation_time=ts,
            end_time=end_ts,
            src_ip=src_ip,
            src_ip_country_code=str(row.get("src_ip_country_code", "")).strip().upper() or None,
            protocol=str(row.get("protocol", "HTTPS")).strip().upper(),
            response_code=int(float(str(row.get("response_code", 200)).strip() or 200)),
            dst_port=int(float(str(row.get("dst_port", 443)).strip() or 443)),
            dst_ip=str(row.get("dst_ip", "")).strip() or None,
            rule_names=rule_names,
            detection_types=detection_types,
        )
        db.add(log_entry)

        # Create corresponding Transaction record so detection pipeline analyzes WAF log events
        txn_ref = f"WAF_{idx+1:06d}_{src_ip.replace('.', '_')}"
        existing = await db.execute(select(Transaction).where(Transaction.txn_ref == txn_ref))
        if existing.scalar_one_or_none():
            duplicates += 1
            continue

        cust_id = await _get_or_create_customer(db, f"CUST_IP_{src_ip}")
        from_acc_id = await _get_or_create_account(db, f"ACC_IP_{src_ip}", cust_id)
        to_acc_id = await _get_or_create_account(db, f"ACC_DST_{row.get('dst_ip', '10.138.69.97')}", None)

        total_bytes = bytes_in + bytes_out
        txn = Transaction(
            txn_ref=txn_ref,
            from_account_id=from_acc_id,
            to_account_id=to_acc_id,
            from_account_number=f"ACC_IP_{src_ip}",
            to_account_number=f"ACC_DST_{row.get('dst_ip', '10.138.69.97')}",
            amount=float(total_bytes) if total_bytes > 0 else 5000.0,
            currency="USD",
            channel="ONLINE",
            transaction_type="TRANSFER",
            timestamp=ts,
            description=f"WAF Alert: {rule_names} ({detection_types})",
            ip_address=src_ip,
            location=str(row.get("src_ip_country_code", "")).strip() or None,
            scenario_label="WAF_SUSPICIOUS_TRAFFIC",
        )
        db.add(txn)
        accepted += 1
        if total_bytes > 1_000_000:
            flagged += 1

    await db.flush()
    logger.info("Evidence WAF dataset ingestion complete", accepted=accepted, rejected=rejected)
    return IngestionSummary(
        total_rows=len(df),
        accepted_rows=accepted,
        rejected_rows=rejected,
        duplicate_rows=duplicates,
        flagged_rows=flagged,
        errors=errors[:50],
        warnings=[f"Ingested {accepted} WAF evidence logs into Threat Platform"],
    )


async def ingest_threat_csv(
    file_content: bytes,
    db: AsyncSession,
    filename: str = "threat.csv",
) -> IngestionSummary:
    """Ingest Threat Dataset (IP Abuse Threat Intelligence)."""
    df = pd.read_csv(io.BytesIO(file_content), dtype=str)
    df.columns = [c.strip().lower().replace(".", "_") for c in df.columns]

    accepted = 0
    rejected = 0
    duplicates = 0
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2
        ip = str(row.get("ip_address", "")).strip()
        if not ip or ip.lower() in ("nan", "none", ""):
            rejected += 1
            errors.append({"row": row_num, "reason": "Missing ip_address"})
            continue

        try:
            score = float(str(row.get("abuse_confidence_score", 100)).strip() or 100)
        except ValueError:
            score = 100.0

        try:
            severity = int(float(str(row.get("severity", 4)).strip() or 4))
        except ValueError:
            severity = 4

        existing = await db.execute(select(ThreatIntel).where(ThreatIntel.ip_address == ip))
        threat_rec = existing.scalar_one_or_none()
        if threat_rec:
            threat_rec.abuse_confidence_score = score
            threat_rec.risk_level = str(row.get("risk_level", "Critical")).strip()
            threat_rec.severity = severity
            duplicates += 1
        else:
            threat_rec = ThreatIntel(
                ip_address=ip,
                abuse_confidence_score=score,
                country_code=str(row.get("country_code", "")).strip().upper() or None,
                country_name=str(row.get("country_name", "")).strip() or None,
                continent=str(row.get("continent", "")).strip() or None,
                reported_date=str(row.get("reported_date", "")).strip() or None,
                risk_level=str(row.get("risk_level", "Critical")).strip(),
                severity=severity,
            )
            db.add(threat_rec)

        # Upsert Entity node for entity resolution
        norm_val = ip.lower()
        existing_ent = await db.execute(select(Entity).where(Entity.normalized_value == norm_val, Entity.entity_type == "IP"))
        if not existing_ent.scalar_one_or_none():
            ent = Entity(
                entity_type="IP",
                identifier=ip,
                normalized_value=norm_val,
                cluster_id=f"CLUSTER_THREAT_{ip.replace('.', '_')}",
            )
            db.add(ent)
        accepted += 1

    await db.flush()
    logger.info("Threat Intelligence dataset ingestion complete", accepted=accepted)
    return IngestionSummary(
        total_rows=len(df),
        accepted_rows=accepted,
        rejected_rows=rejected,
        duplicate_rows=duplicates,
        flagged_rows=accepted,
        errors=errors[:50],
        warnings=[f"Ingested {accepted} Threat IP Intelligence records into Threat Intelligence Database"],
    )


async def ingest_transactions_csv(
    df: pd.DataFrame,
    db: AsyncSession,
    filename: str = "upload.csv",
) -> IngestionSummary:
    """Ingest financial transactions dataset."""
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    accepted = 0
    rejected = 0
    duplicate_count = 0

    total_rows = len(df)
    df.columns = [c.strip().lower() for c in df.columns]
    canonical_cols = {}
    for col in df.columns:
        if col in COLUMN_ALIASES:
            canonical_cols[col] = COLUMN_ALIASES[col]
        else:
            warnings.append(f"Unknown column '{col}' — ignored")
    df = df.rename(columns=canonical_cols)

    missing_required = REQUIRED_CANONICAL - set(df.columns)
    if missing_required:
        return IngestionSummary(
            total_rows=total_rows,
            accepted_rows=0,
            rejected_rows=total_rows,
            duplicate_rows=0,
            flagged_rows=0,
            errors=[{"row": 0, "reason": f"Missing required columns: {sorted(missing_required)}"}],
        )

    for col in ["from_account_number", "to_account_number", "from_customer", "to_customer",
                "currency", "channel", "transaction_type", "description",
                "ip_address", "device_id", "location", "scenario_label"]:
        if col not in df.columns:
            df[col] = None

    flagged_rows = 0
    for idx, row in df.iterrows():
        row_num = idx + 2

        txn_ref = str(row.get("txn_ref", "")).strip()
        if not txn_ref or txn_ref.lower() in ("nan", "none", ""):
            errors.append({"row": row_num, "reason": "Missing or empty txn_ref"})
            rejected += 1
            continue

        try:
            amount = float(str(row.get("amount", "")).strip())
            if amount <= 0 or amount > MAX_AMOUNT:
                errors.append({"row": row_num, "txn_ref": txn_ref,
                                "reason": f"Invalid amount: {amount}"})
                rejected += 1
                continue
        except (ValueError, TypeError):
            errors.append({"row": row_num, "txn_ref": txn_ref, "reason": f"Non-numeric amount: {row.get('amount')}"})
            rejected += 1
            continue

        ts_raw = str(row.get("timestamp", "")).strip()
        try:
            ts = pd.to_datetime(ts_raw, utc=True).to_pydatetime()
        except Exception:
            errors.append({"row": row_num, "txn_ref": txn_ref, "reason": f"Unparseable timestamp: {ts_raw}"})
            rejected += 1
            continue

        channel = str(row.get("channel", "UNKNOWN")).strip().upper()
        if channel not in VALID_CHANNELS:
            channel = "UNKNOWN"

        txn_type = str(row.get("transaction_type", "TRANSFER")).strip().upper()
        if txn_type not in VALID_TXN_TYPES:
            txn_type = "TRANSFER"

        existing_result = await db.execute(select(Transaction).where(Transaction.txn_ref == txn_ref))
        if existing_result.scalar_one_or_none():
            duplicate_count += 1
            continue

        from_cust_ref = str(row.get("from_customer", "")).strip() or None
        to_cust_ref = str(row.get("to_customer", "")).strip() or None

        from_cust_id = await _get_or_create_customer(db, from_cust_ref)
        to_cust_id = await _get_or_create_customer(db, to_cust_ref)

        from_acc_num = str(row.get("from_account_number", "")).strip() or None
        to_acc_num = str(row.get("to_account_number", "")).strip() or None

        from_acc_id = await _get_or_create_account(db, from_acc_num, from_cust_id)
        to_acc_id = await _get_or_create_account(db, to_acc_num, to_cust_id)

        txn = Transaction(
            txn_ref=txn_ref,
            from_account_id=from_acc_id,
            to_account_id=to_acc_id,
            from_account_number=from_acc_num,
            to_account_number=to_acc_num,
            amount=amount,
            currency=str(row.get("currency", "INR")).strip().upper() or "INR",
            channel=channel,
            transaction_type=txn_type,
            timestamp=ts,
            description=str(row.get("description", "")).strip() or None,
            ip_address=str(row.get("ip_address", "")).strip() or None,
            device_id=str(row.get("device_id", "")).strip() or None,
            location=str(row.get("location", "")).strip() or None,
            scenario_label=str(row.get("scenario_label", "")).strip() or None,
        )
        db.add(txn)
        accepted += 1

        if amount >= 500_000:
            flagged_rows += 1

    await db.flush()

    return IngestionSummary(
        total_rows=total_rows,
        accepted_rows=accepted,
        rejected_rows=rejected,
        duplicate_rows=duplicate_count,
        flagged_rows=flagged_rows,
        errors=errors[:50],
        warnings=warnings[:20],
    )


async def _get_or_create_customer(db: AsyncSession, customer_ref: str | None) -> str | None:
    if not customer_ref or customer_ref.lower() in ("nan", "none", ""):
        return None
    result = await db.execute(select(Customer).where(Customer.customer_ref == customer_ref))
    cust = result.scalar_one_or_none()
    if cust:
        return cust.id
    cust = Customer(
        customer_ref=customer_ref,
        full_name=customer_ref,
        kyc_status="UNKNOWN",
        risk_profile="LOW",
    )
    db.add(cust)
    await db.flush()
    return cust.id


async def _get_or_create_account(
    db: AsyncSession, account_number: str | None, customer_id: str | None
) -> str | None:
    if not account_number or account_number.lower() in ("nan", "none", ""):
        return None
    result = await db.execute(select(Account).where(Account.account_number == account_number))
    acc = result.scalar_one_or_none()
    if acc:
        return acc.id
    if not customer_id:
        customer_id = await _get_or_create_customer(db, f"CUST_{account_number}")
    acc = Account(
        account_number=account_number,
        customer_id=customer_id,
        account_type="UNKNOWN",
    )
    db.add(acc)
    await db.flush()
    return acc.id

