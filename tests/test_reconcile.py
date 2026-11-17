from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from generate_data import generate_all
from reconcile import reconcile_frames

ROOT = Path(__file__).resolve().parents[1]


def load_generated_data():
    generate_all()
    platform_df = pd.read_csv(ROOT / "platform_transactions.csv")
    bank_df = pd.read_csv(ROOT / "bank_settlements.csv")
    with (ROOT / "answer_key.json").open("r", encoding="utf-8") as fh:
        answer_key = json.load(fh)
    return platform_df, bank_df, answer_key


def test_generated_data_detects_each_gap():
    platform_df, bank_df, answer_key = load_generated_data()
    result = reconcile_frames(platform_df, bank_df)
    categories = result["categories"]

    timing_ids = {item["txn_id"] for item in categories["timing_difference"]}
    assert {item["txn_id"] for item in answer_key["timing"]} <= timing_ids

    rounding_ids = {item["txn_id"] for item in categories["rounding_difference"]}
    assert len(rounding_ids) >= len(answer_key["rounding"])

    bank_dup_ids = {item["txn_ref"] for item in categories["duplicate"] if item["source"] == "bank"}
    platform_dup_ids = {item["txn_id"] for item in categories["duplicate"] if item["source"] == "platform"}
    assert "dup_platform_001" in platform_dup_ids
    assert "dup_bank_001" in bank_dup_ids

    orphan_ids = {item["txn_id"] for item in categories["orphan_refund"]}
    assert "orphan_refund_001" in orphan_ids


def test_bridge_sums_exactly():
    platform_df, bank_df, _ = load_generated_data()
    result = reconcile_frames(platform_df, bank_df)

    bridge_total = sum(result["bridge"].values(), Decimal("0"))
    assert result["variance"] == bridge_total
    assert result["variance"] == result["summary"]["platform_total"] - result["summary"]["bank_total"]


def test_clean_data_has_zero_variance():
    platform_df = pd.DataFrame(
        [
            {"txn_id": "txn_001", "created_at": "2026-01-02T10:00:00Z", "amount": "10.500", "type": "payment", "original_txn_id": None},
            {"txn_id": "txn_002", "created_at": "2026-01-06T12:00:00Z", "amount": "15.250", "type": "payment", "original_txn_id": None},
        ]
    )
    bank_df = pd.DataFrame(
        [
            {"settlement_id": "s_01", "txn_ref": "txn_001", "settled_at": "2026-01-03T08:00:00Z", "amount": "10.50"},
            {"settlement_id": "s_02", "txn_ref": "txn_002", "settled_at": "2026-01-07T08:00:00Z", "amount": "15.25"},
        ]
    )

    result = reconcile_frames(platform_df, bank_df)
    assert result["summary"]["variance"] == Decimal("0")
    assert result["summary"]["platform_total"] == result["summary"]["bank_total"]
    assert result["categories"]["unexplained"] == []


def test_empty_input_handles_cleanly():
    empty_platform = pd.DataFrame(columns=["txn_id", "created_at", "amount", "type", "original_txn_id"])
    empty_bank = pd.DataFrame(columns=["settlement_id", "txn_ref", "settled_at", "amount"])
    result = reconcile_frames(empty_platform, empty_bank)
    assert result["summary"]["platform_total"] == Decimal("0")
    assert result["summary"]["bank_total"] == Decimal("0")
    assert result["summary"]["variance"] == Decimal("0")
    assert result["categories"]["unexplained"] == []


def test_duplicate_and_refund_edge_case():
    platform_df = pd.DataFrame(
        [
            {"txn_id": "dup_txn", "created_at": "2026-01-02T00:00:00Z", "amount": "25.000", "type": "payment", "original_txn_id": None},
            {"txn_id": "dup_txn", "created_at": "2026-01-02T01:00:00Z", "amount": "25.000", "type": "payment", "original_txn_id": None},
            {"txn_id": "refund_001", "created_at": "2026-01-03T00:00:00Z", "amount": "-10.500", "type": "refund", "original_txn_id": "missing_ref"},
        ]
    )
    bank_df = pd.DataFrame(
        [
            {"settlement_id": "s_1", "txn_ref": "dup_txn", "settled_at": "2026-01-03T10:00:00Z", "amount": "25.00"},
        ]
    )

    result = reconcile_frames(platform_df, bank_df)
    dup_ids = {item["txn_id"] for item in result["categories"]["duplicate"] if item.get("source") == "platform"}
    assert "dup_txn" in dup_ids
    assert {item["txn_id"] for item in result["categories"]["orphan_refund"]} == {"refund_001"}


def test_cutoff_timing_is_detected():
    platform_df = pd.DataFrame(
        [
            {"txn_id": "cutoff_txn", "created_at": "2026-01-31T23:59:59Z", "amount": "200.000", "type": "payment", "original_txn_id": None},
        ]
    )
    bank_df = pd.DataFrame(
        [
            {"settlement_id": "cutoff_settlement", "txn_ref": "cutoff_txn", "settled_at": "2026-02-01T08:00:00Z", "amount": "200.00"},
        ]
    )

    result = reconcile_frames(platform_df, bank_df)
    assert len(result["categories"]["timing_difference"]) == 1
    assert result["categories"]["timing_difference"][0]["txn_id"] == "cutoff_txn"
