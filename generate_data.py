from __future__ import annotations

import json
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
PLATFORM_PATH = BASE_DIR / "platform_transactions.csv"
BANK_PATH = BASE_DIR / "bank_settlements.csv"
ANSWER_KEY_PATH = BASE_DIR / "answer_key.json"

CUTOFF = pd.Timestamp("2026-01-31 23:59:59+00:00")


def money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def bank_money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def iso_utc(ts: pd.Timestamp) -> str:
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def create_clean_base_data(seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    platform_rows: list[dict] = []
    bank_rows: list[dict] = []

    for day in range(1, 32):
        for hour in range(0, 24):
            for minute in range(0, 60, 15):
                if len(platform_rows) >= 400:
                    break
                created_at = pd.Timestamp("2026-01-01 00:00:00+00:00") + pd.Timedelta(days=day - 1, hours=hour, minutes=minute)
                txn_id = f"txn_{len(platform_rows) + 1:04d}"
                base_amount = Decimal(rng.randint(10, 1500)) + (Decimal(rng.randint(0, 99)) / Decimal("100"))
                amount = money(base_amount)
                if len(platform_rows) % 12 == 0:
                    txn_type = "refund"
                    original_txn_id = f"txn_{max(1, len(platform_rows) - 10):04d}"
                    amount = -amount
                else:
                    txn_type = "payment"
                    original_txn_id = None

                platform_rows.append(
                    {
                        "txn_id": txn_id,
                        "created_at": iso_utc(created_at),
                        "amount": str(amount),
                        "type": txn_type,
                        "original_txn_id": original_txn_id,
                    }
                )

                settlement_delay = pd.Timedelta(days=rng.randint(1, 2), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
                settled_at = created_at + settlement_delay
                settlement_amount = bank_money(abs(amount))
                bank_rows.append(
                    {
                        "settlement_id": f"settlement_{len(bank_rows) + 1:04d}",
                        "txn_ref": txn_id,
                        "settled_at": iso_utc(settled_at),
                        "amount": str(settlement_amount),
                    }
                )

            if len(platform_rows) >= 400:
                break

    return platform_rows, bank_rows


def apply_planted_gaps(platform_rows: list[dict], bank_rows: list[dict]) -> dict:
    answer_key: dict = {"timing": [], "rounding": [], "duplicate": {"platform": [], "bank": []}, "orphan_refund": []}

    timing_txns = [
        {"txn_id": "timing_001", "amount": "125.456", "created_at": "2026-01-30T18:30:00Z", "type": "payment", "original_txn_id": None},
        {"txn_id": "timing_002", "amount": "98.740", "created_at": "2026-01-31T12:00:00Z", "type": "payment", "original_txn_id": None},
        {"txn_id": "timing_003", "amount": "210.125", "created_at": "2026-01-31T22:55:00Z", "type": "payment", "original_txn_id": None},
    ]
    timing_settlements = [
        {"settlement_id": "timing_settlement_001", "txn_ref": "timing_001", "settled_at": "2026-02-01T08:30:00Z", "amount": "125.46"},
        {"settlement_id": "timing_settlement_002", "txn_ref": "timing_002", "settled_at": "2026-02-02T09:15:00Z", "amount": "98.74"},
        {"settlement_id": "timing_settlement_003", "txn_ref": "timing_003", "settled_at": "2026-02-02T17:45:00Z", "amount": "210.13"},
    ]
    for txn, settlement in zip(timing_txns, timing_settlements):
        platform_rows.append(txn)
        bank_rows.append(settlement)
        answer_key["timing"].append({
            "txn_id": txn["txn_id"],
            "platform_amount": txn["amount"],
            "bank_amount": settlement["amount"],
            "settled_at": settlement["settled_at"],
        })

    rounding_rows = []
    for row in platform_rows:
        if row["type"] == "payment" and row["txn_id"].startswith("txn_"):
            rounding_rows.append(row)
    selected = rounding_rows[:200]

    for row in selected:
        platform_amount = Decimal(row["amount"])
        bank_amount = bank_money(platform_amount)
        if platform_amount == bank_amount:
            platform_amount = money(platform_amount + Decimal("0.003"))
            bank_amount = bank_money(platform_amount)
        if abs(platform_amount - bank_amount) >= Decimal("0.01"):
            platform_amount = money(platform_amount + Decimal("0.003"))
            bank_amount = bank_money(platform_amount)
        matching_bank = next((record for record in bank_rows if record["txn_ref"] == row["txn_id"]), None)
        if matching_bank is not None:
            matching_bank["amount"] = str(bank_amount)
            row["amount"] = str(platform_amount)
            answer_key["rounding"].append(
                {
                    "txn_id": row["txn_id"],
                    "platform_amount": row["amount"],
                    "bank_amount": matching_bank["amount"],
                }
            )

    dup_platform_txn = {
        "txn_id": "dup_platform_001",
        "created_at": "2026-01-15T09:15:00Z",
        "amount": "42.500",
        "type": "payment",
        "original_txn_id": None,
    }
    dup_platform_txn_copy = {**dup_platform_txn}
    platform_rows.extend([dup_platform_txn, dup_platform_txn_copy])
    answer_key["duplicate"]["platform"].append({"txn_id": dup_platform_txn["txn_id"], "amount": dup_platform_txn["amount"]})

    dup_bank_txn = {
        "settlement_id": "dup_bank_settlement_001",
        "txn_ref": "dup_bank_001",
        "settled_at": "2026-01-17T10:00:00Z",
        "amount": "42.50",
    }
    dup_bank_txn_copy = {**dup_bank_txn}
    bank_rows.extend([dup_bank_txn, dup_bank_txn_copy])
    answer_key["duplicate"]["bank"].append({"txn_ref": dup_bank_txn["txn_ref"], "amount": dup_bank_txn["amount"]})

    orphan_refund = {
        "txn_id": "orphan_refund_001",
        "created_at": "2026-01-21T16:00:00Z",
        "amount": "-17.750",
        "type": "refund",
        "original_txn_id": "missing_original_001",
    }
    platform_rows.append(orphan_refund)
    answer_key["orphan_refund"].append({
        "txn_id": orphan_refund["txn_id"],
        "amount": orphan_refund["amount"],
        "original_txn_id": orphan_refund["original_txn_id"],
    })

    return answer_key


def generate_all() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    platform_rows, bank_rows = create_clean_base_data()
    answer_key = apply_planted_gaps(platform_rows, bank_rows)

    platform_df = pd.DataFrame(platform_rows)
    bank_df = pd.DataFrame(bank_rows)

    platform_df.to_csv(PLATFORM_PATH, index=False)
    bank_df.to_csv(BANK_PATH, index=False)
    with ANSWER_KEY_PATH.open("w", encoding="utf-8") as fh:
        json.dump(answer_key, fh, indent=2)

    return platform_df, bank_df, answer_key


def main() -> None:
    platform_df, bank_df, answer_key = generate_all()
    print(f"Generated {len(platform_df)} platform rows and {len(bank_df)} bank rows.")
    print(f"Answer key contains {len(answer_key['timing'])} timing gaps, {len(answer_key['rounding'])} rounding gaps, {len(answer_key['duplicate']['platform'])} platform duplicates, {len(answer_key['duplicate']['bank'])} bank duplicates, and {len(answer_key['orphan_refund'])} orphan refunds.")


if __name__ == "__main__":
    main()
