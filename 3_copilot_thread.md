# Copilot Thread

## User prompt
Build a payment reconciliation tool using Python and Streamlit.
Generate fake platform transaction data and bank settlement data with some mismatches.
Include cases like next-month settlements, rounding differences, duplicate entries, missing transactions, and refunds without original transactions.
Compare both datasets and automatically find all the mismatches.
Show a dashboard with matched, unmatched, and duplicate amounts, along with a summary of where the gaps are.
Also show detailed results and allow downloading the reconciliation report.
Add pytest test cases to check that all reconciliation scenarios are working correctly.

## Distilled prompt
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

# Notes & Assumptions

## Problem
A payments platform's month-end books don't match the bank's settlement records.
Goal: generate synthetic data with known gaps, build a tool that finds and
explains every gap, and show a variance bridge from platform total to bank total.

## Stack
- Python 3.11, pandas, Decimal for all money math
- Streamlit (UI + deployment on Streamlit Community Cloud)
- pytest for tests

## Assumptions
1. Currency: single currency (USD). No FX.
2. Money type: amounts handled as Decimal, never float.
3. Period: January 2026. Cutoff is 2026-01-31 23:59:59 UTC.
4. Timezone: all timestamps are UTC.
5. Settlement lag: the bank settles 1-2 days after the platform records the transaction, in daily batches.
6. Matching key: the bank's txn_ref equals the platform's txn_id.
7. Refunds: recorded as negative amounts with type refund and an original_txn_id pointing to the payment being refunded.
8. Fees: ignored. The bank settles the full gross amount.
9. Platform precision: the platform stores amounts to 3 decimal places.
   The bank rounds each settlement to 2 decimal places.
10. Reconciliation basis: compare platform transactions created in January
    to bank settlements settled in January.
11. Dataset size: about 400 transactions, plus the planted gaps.

## Schemas
platform_transactions: txn_id, created_at, amount, type, original_txn_id
bank_settlements: settlement_id, txn_ref, settled_at, amount

## Planted gaps (the answer key)
| # | Gap type | What I planted | Expected effect |
|---|----------|----------------|-----------------|
| 1 | Timing | Txn created Jan 31, settled Feb 1 or 2 | In platform January total, missing from bank January total |
| 2 | Rounding | Many rows with 3-decimal platform amounts rounded to 2 by bank | Per-row difference under 1 cent, visible only in the sum |
| 3 | Duplicate | One txn_id appears twice in [platform / bank] | Inflates that dataset's total by the duplicate amount |
| 4 | Orphan refund | Refund whose original_txn_id exists nowhere | Negative amount with no traceable original |

(Fill in exact txn IDs and amounts once your generator runs. Save them to answer_key.json too.)

## Classification rules
Every record ends up in exactly one bucket:
- Matched (IDs and amounts agree)
- Timing difference (matched ID, settlement dated after cutoff)
- Rounding difference (matched ID, amount differs by less than 0.01)
- Duplicate (same ID appears more than once in one dataset)
- Orphan refund (refund whose original cannot be found)
- Unexplained (anything else; target is zero)

## Variance bridge
Platform total - Bank total = timing + rounding + duplicate + orphan refund + unexplained

## Out of scope
Fees, FX, partial settlements, chargebacks, multiple banks, fuzzy matching
when IDs are missing, files of millions of rows.

## Known production weaknesses (draft for deliverable 5)
1. Real data rarely shares a clean ID, so matching would need fuzzy logic.
2. It ignores fees, FX, partial settlements, chargebacks and timezone drift.
3. It loads everything in memory and won't scale to millions of rows.

## Decision log
(Add a line here each time you choose between options, with the reason.)
-

## Execution summary
We created the project files and installed dependencies, then ran pytest.
The initial run showed two failures in the timing and rounding detection logic.
After adjusting timing precedence and generating rounding rows that actually keep the per-row variance below 1 cent while affecting the total, the suite passed.

Final test result:
```text
......                                                                   [100%]
6 passed in 1.45s
```

## Files created
- [requirements.txt](c:/Users/patte/Documents/TechInnovation/ONE%20lab/requirements.txt)
- [generate_data.py](c:/Users/patte/Documents/TechInnovation/ONE%20lab/generate_data.py)
- [reconcile.py](c:/Users/patte/Documents/TechInnovation/ONE%20lab/reconcile.py)
- [app.py](c:/Users/patte/Documents/TechInnovation/ONE%20lab/app.py)
- [tests/test_reconcile.py](c:/Users/patte/Documents/TechInnovation/ONE%20lab/tests/test_reconcile.py)

## Final note
The project is ready in the current directory and can be run as a Streamlit app.
