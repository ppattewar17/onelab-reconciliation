from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

CUTOFF = pd.Timestamp("2026-01-31 23:59:59+00:00")
ZERO = Decimal("0")


def to_decimal(value) -> Decimal:
    if pd.isna(value):
        return ZERO
    return Decimal(str(value))


def format_money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01')):,.2f}"


def normalize_platform(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["created_at"] = pd.to_datetime(out["created_at"], utc=True)
    out["amount"] = out["amount"].map(to_decimal)
    out["txn_id"] = out["txn_id"].astype(str)
    out["type"] = out["type"].fillna("payment").astype(str)
    out["original_txn_id"] = out["original_txn_id"].replace({pd.NA: None})
    return out


def normalize_bank(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["settled_at"] = pd.to_datetime(out["settled_at"], utc=True)
    out["amount"] = out["amount"].map(to_decimal)
    out["txn_ref"] = out["txn_ref"].astype(str)
    return out


def sum_column(rows: list[dict], key: str) -> Decimal:
    return sum((to_decimal(row.get(key, 0)) for row in rows), ZERO)


def reconcile_frames(platform_df: pd.DataFrame, bank_df: pd.DataFrame) -> dict:
    platform = normalize_platform(platform_df)
    bank = normalize_bank(bank_df)

    result = {
        "matched": [],
        "timing_difference": [],
        "rounding_difference": [],
        "duplicate": [],
        "orphan_refund": [],
        "unexplained": [],
    }

    duplicate_platform_ids = platform["txn_id"][platform["txn_id"].duplicated(keep=False)].unique().tolist()
    duplicate_bank_ids = bank["txn_ref"][bank["txn_ref"].duplicated(keep=False)].unique().tolist()

    classified_platform_ids = set()
    classified_bank_ids = set()

    for row in platform[platform["txn_id"].isin(duplicate_platform_ids)].to_dict("records"):
        result["duplicate"].append({
            "source": "platform",
            "txn_id": row["txn_id"],
            "amount": row["amount"],
            "created_at": row["created_at"],
            "type": row.get("type"),
        })
        classified_platform_ids.add(row["txn_id"])

    for row in bank[bank["txn_ref"].isin(duplicate_bank_ids)].to_dict("records"):
        result["duplicate"].append({
            "source": "bank",
            "txn_ref": row["txn_ref"],
            "amount": row["amount"],
            "settled_at": row["settled_at"],
        })
        classified_bank_ids.add(row["txn_ref"])

    for txn_id in sorted(set(platform["txn_id"]) & set(bank["txn_ref"])):
        if txn_id in duplicate_platform_ids or txn_id in duplicate_bank_ids:
            continue

        platform_match = platform[platform["txn_id"] == txn_id].iloc[0]
        bank_match = bank[bank["txn_ref"] == txn_id].iloc[0]

        if (bank_match["settled_at"] > CUTOFF) and (platform_match["created_at"] <= CUTOFF):
            result["timing_difference"].append({
                "txn_id": txn_id,
                "platform_amount": platform_match["amount"],
                "bank_amount": bank_match["amount"],
                "created_at": platform_match["created_at"],
                "settled_at": bank_match["settled_at"],
            })
        elif platform_match["amount"] == bank_match["amount"]:
            result["matched"].append({
                "txn_id": txn_id,
                "platform_amount": platform_match["amount"],
                "bank_amount": bank_match["amount"],
            })
        elif abs(platform_match["amount"] - bank_match["amount"]) < Decimal("0.01"):
            result["rounding_difference"].append({
                "txn_id": txn_id,
                "platform_amount": platform_match["amount"],
                "bank_amount": bank_match["amount"],
            })
        else:
            result["unexplained"].append({
                "txn_id": txn_id,
                "platform_amount": platform_match["amount"],
                "bank_amount": bank_match["amount"],
            })

        classified_platform_ids.add(txn_id)
        classified_bank_ids.add(txn_id)

    for _, row in platform.iterrows():
        txn_id = str(row["txn_id"])
        if txn_id in classified_platform_ids:
            continue
        if row["type"] == "refund" and row["original_txn_id"] not in set(platform["txn_id"]) | set(bank["txn_ref"]):
            result["orphan_refund"].append({
                "txn_id": txn_id,
                "amount": row["amount"],
                "original_txn_id": row["original_txn_id"],
                "created_at": row["created_at"],
            })
        else:
            result["unexplained"].append({
                "txn_id": txn_id,
                "platform_amount": row["amount"],
                "bank_amount": Decimal("0"),
            })
        classified_platform_ids.add(txn_id)

    for _, row in bank.iterrows():
        txn_ref = str(row["txn_ref"])
        if txn_ref in classified_bank_ids:
            continue
        result["unexplained"].append({
            "txn_id": txn_ref,
            "platform_amount": Decimal("0"),
            "bank_amount": row["amount"],
        })
        classified_bank_ids.add(txn_ref)

    platform_total = sum((row["amount"] for _, row in platform.iterrows()), ZERO)
    bank_total = sum((row["amount"] for _, row in bank.iterrows()), ZERO)
    variance = platform_total - bank_total

    bridge = {
        "timing": sum_column(result["timing_difference"], "platform_amount") - sum_column(result["timing_difference"], "bank_amount"),
        "rounding": sum_column(result["rounding_difference"], "platform_amount") - sum_column(result["rounding_difference"], "bank_amount"),
        "duplicate": sum_column([row for row in result["duplicate"] if row.get("source") == "platform"], "amount") - sum_column([row for row in result["duplicate"] if row.get("source") == "bank"], "amount"),
        "orphan_refund": sum_column(result["orphan_refund"], "amount"),
        "unexplained": sum_column([row for row in result["unexplained"] if row.get("platform_amount") is not None], "platform_amount") - sum_column([row for row in result["unexplained"] if row.get("bank_amount") is not None], "bank_amount"),
    }

    total_bridge = sum(bridge.values(), ZERO)
    if variance != total_bridge:
        raise ValueError(f"Variance bridge mismatch: {variance} != {total_bridge}")

    summary = {
        "matched_rows": len(result["matched"]),
        "timing_rows": len(result["timing_difference"]),
        "rounding_rows": len(result["rounding_difference"]),
        "duplicate_rows": len(result["duplicate"]),
        "orphan_refund_rows": len(result["orphan_refund"]),
        "unexplained_rows": len(result["unexplained"]),
        "platform_total": platform_total,
        "bank_total": bank_total,
        "variance": variance,
    }

    return {
        "summary": summary,
        "categories": result,
        "bridge": bridge,
        "platform_total": platform_total,
        "bank_total": bank_total,
        "variance": variance,
    }


def reconcile_file_paths(platform_path: str | Path, bank_path: str | Path) -> dict:
    platform_df = pd.read_csv(platform_path)
    bank_df = pd.read_csv(bank_path)
    return reconcile_frames(platform_df, bank_df)
