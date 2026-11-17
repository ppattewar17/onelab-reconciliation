Build a payments reconciliation tool in Python. Work in the current directory.

## Context

A payments platform records each transaction instantly. The bank settles funds
in batches 1-2 days later. At month end, every platform transaction should
have a matching bank settlement, but the totals don't match. The tool must
find the gaps, classify them, and show a variance bridge.

## Stack

Python 3.11, pandas, Decimal for ALL money math (never float), Streamlit for
the UI, pytest for tests. It must run on Streamlit Community Cloud
(requirements.txt, app entry point app.py).

## Assumptions (display these in the app UI too)

- Single currency (USD). No FX, no fees.
- Period: January 2026. Cutoff 2026-01-31 23:59:59 UTC. All timestamps UTC.
- Bank settles 1-2 days after the platform records the transaction.
- Bank txn_ref equals platform txn_id (matching key).
- Refunds are negative amounts, type "refund", with original_txn_id.
- Platform stores amounts to 3 decimals; the bank rounds each to 2.
- Reconciliation compares platform transactions created in January to bank
  settlements settled in January.

## Schemas

platform_transactions: txn_id, created_at, amount, type (payment|refund),
original_txn_id (nullable)
bank_settlements: settlement_id, txn_ref, settled_at, amount

## Data generator (generate_data.py)

Deterministic (fixed random seed). About 400 clean transactions, with matching
settlements 1-2 days later, then plant these gaps:

1. TIMING: 3 transactions created Jan 30-31 whose settlements land Feb 1-2.
2. ROUNDING: ~200 rows where the platform amount has 3 decimals and the bank
   amount is rounded to 2. No single row differs by 0.01 or more, but the
   sum differs visibly.
3. DUPLICATE: 1 transaction duplicated in the platform data and 1 settlement
   duplicated in the bank data (two separate duplicates, one per dataset).
4. ORPHAN REFUND: 1 refund whose original_txn_id exists in neither dataset.
   Output platform_transactions.csv, bank_settlements.csv, and answer_key.json
   listing every planted gap with IDs and amounts.

## Reconciliation engine (reconcile.py)

Pure functions, no UI code. Match on txn_id/txn_ref. Classify every record
into exactly one bucket: matched, timing_difference, rounding_difference,
duplicate, orphan_refund, unexplained. Produce a variance bridge:
Platform total - Bank total = timing + rounding + duplicate + orphan_refund

- unexplained. The bridge must sum exactly. Unexplained should be 0 on the
  generated data.

## UI (app.py)

1. Headline: platform total, bank total, variance.
2. Variance bridge (waterfall chart or clear table) showing each gap type's
   contribution.
3. One drill-down table per gap type with the affected rows and a plain-English
   explanation of why it happened.
4. A section listing the assumptions.
5. A file upload option for custom CSVs, falling back to the generated data.

## Tests (tests/)

pytest tests covering: each planted gap detected and correctly classified
(checked against answer_key.json); clean data gives zero variance; the bridge
sums exactly; edge cases: transaction at exactly the cutoff, refund with a
valid original, duplicate in bank vs. platform; empty input.

## Process

Build in this order: generator, engine, tests, UI. Run the tests and fix
failures before moving on. Show me test output at the end.
