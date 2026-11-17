from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from generate_data import ANSWER_KEY_PATH, BANK_PATH, PLATFORM_PATH, generate_all
from reconcile import CUTOFF, format_money, reconcile_frames

st.set_page_config(page_title="Payments Reconciliation", layout="wide")

ASSUMPTIONS = [
    "Single currency: USD. No FX or fees.",
    "Period: January 2026. Cutoff: 2026-01-31 23:59:59 UTC.",
    "Bank settles 1-2 days after platform records the transaction.",
    "Bank txn_ref equals platform txn_id.",
    "Refunds are negative amounts with type 'refund' and an original_txn_id.",
    "Platform amounts are recorded to 3 decimal places, while bank amounts are rounded to 2.",
    "Reconciliation compares platform transactions created in January with bank settlements settled in January.",
]


def load_data(platform_file=None, bank_file=None):
    if platform_file is not None and bank_file is not None:
        platform_df = pd.read_csv(platform_file)
        bank_df = pd.read_csv(bank_file)
        return platform_df, bank_df

    if not PLATFORM_PATH.exists() or not BANK_PATH.exists():
        generate_all()
    platform_df = pd.read_csv(PLATFORM_PATH)
    bank_df = pd.read_csv(BANK_PATH)
    return platform_df, bank_df


st.title("Payments Reconciliation Dashboard")

with st.sidebar:
    st.header("Data source")
    platform_file = st.file_uploader("Upload platform transactions CSV", type=["csv"], key="platform_upload")
    bank_file = st.file_uploader("Upload bank settlements CSV", type=["csv"], key="bank_upload")
    st.caption("Leave uploads blank to use the generated January 2026 dataset.")

platform_df, bank_df = load_data(platform_file, bank_file)
result = reconcile_frames(platform_df, bank_df)

summary = result["summary"]

col1, col2, col3 = st.columns(3)
col1.metric("Platform total", format_money(summary["platform_total"]))
col2.metric("Bank total", format_money(summary["bank_total"]))
col3.metric("Variance", format_money(summary["variance"]))

bridge_df = pd.DataFrame(
    [
        {"Gap type": "Timing", "Contribution": result["bridge"]["timing"]},
        {"Gap type": "Rounding", "Contribution": result["bridge"]["rounding"]},
        {"Gap type": "Duplicate", "Contribution": result["bridge"]["duplicate"]},
        {"Gap type": "Orphan refund", "Contribution": result["bridge"]["orphan_refund"]},
        {"Gap type": "Unexplained", "Contribution": result["bridge"]["unexplained"]},
    ]
)

st.subheader("Variance bridge")
st.dataframe(bridge_df, use_container_width=True, hide_index=True)

metrics_df = pd.DataFrame(
    [
        {"Bucket": "Matched", "Rows": summary["matched_rows"]},
        {"Bucket": "Timing gaps", "Rows": summary["timing_rows"]},
        {"Bucket": "Rounding gaps", "Rows": summary["rounding_rows"]},
        {"Bucket": "Duplicate rows", "Rows": summary["duplicate_rows"]},
        {"Bucket": "Orphan refunds", "Rows": summary["orphan_refund_rows"]},
        {"Bucket": "Unexplained", "Rows": summary["unexplained_rows"]},
    ]
)
st.dataframe(metrics_df, use_container_width=True, hide_index=True)

for category, label in [
    ("matched", "Matched records"),
    ("timing_difference", "Timing differences"),
    ("rounding_difference", "Rounding differences"),
    ("duplicate", "Duplicate rows"),
    ("orphan_refund", "Orphan refunds"),
    ("unexplained", "Unexplained records"),
]:
    rows = result["categories"][category]
    st.subheader(label)
    if not rows:
        st.write("No rows found.")
        continue
    if category == "duplicate":
        display = pd.DataFrame(rows)
        display["amount"] = display["amount"].apply(lambda x: format_money(x))
        if "source" in display.columns:
            display["source"] = display["source"].str.title()
    else:
        display = pd.DataFrame(rows)
        if "platform_amount" in display.columns:
            display["platform_amount"] = display["platform_amount"].apply(lambda x: format_money(x))
        if "bank_amount" in display.columns:
            display["bank_amount"] = display["bank_amount"].apply(lambda x: format_money(x))
        if "amount" in display.columns:
            display["amount"] = display["amount"].apply(lambda x: format_money(x))
    st.dataframe(display, use_container_width=True, hide_index=True)

st.subheader("Assumptions")
for assumption in ASSUMPTIONS:
    st.markdown(f"- {assumption}")

if ANSWER_KEY_PATH.exists():
    st.caption(f"Loaded answer key from {ANSWER_KEY_PATH.name}.")
