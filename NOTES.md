# Onelab Assessment: Notes & Assumptions

## Problem
A payments platform's month-end books don't match the bank's settlement records.
Goal: generate synthetic data with known gaps, build a tool that finds and
explains every gap, and show a variance bridge from platform total to bank total.

## Stack
- Python 3.11, pandas, Decimal for all money math
- Streamlit (UI + deployment on Streamlit Community Cloud)
- pytest for tests

## Assumptions
1. **Currency:** single currency (USD). No FX.
2. **Money type:** amounts handled as `Decimal`, never float.
3. **Period:** January 2026. Cutoff is 2026-01-31 23:59:59 UTC.
4. **Timezone:** all timestamps are UTC.
5. **Settlement lag:** the bank settles 1-2 days after the platform records
   the transaction, in daily batches.
6. **Matching key:** the bank's `txn_ref` equals the platform's `txn_id`.
7. **Refunds:** recorded as negative amounts with type `refund` and an
   `original_txn_id` pointing to the payment being refunded.
8. **Fees:** ignored. The bank settles the full gross amount.
9. **Platform precision:** the platform stores amounts to 3 decimal places.
   The bank rounds each settlement to 2 decimal places.
10. **Reconciliation basis:** compare platform transactions created in January
    to bank settlements settled in January.
11. **Dataset size:** about 400 transactions, plus the planted gaps.

## Schemas
**platform_transactions:** txn_id, created_at, amount, type, original_txn_id
**bank_settlements:** settlement_id, txn_ref, settled_at, amount

## Planted gaps (the answer key)
| # | Gap type | What I planted | Expected effect |
|---|----------|----------------|-----------------|
| 1 | Timing | Txn created Jan 31, settled Feb 1 or 2 | In platform January total, missing from bank January total |
| 2 | Rounding | Many rows with 3-decimal platform amounts rounded to 2 by bank | Per-row difference under 1 cent, visible only in the sum |
| 3 | Duplicate | One txn_id appears twice in [platform / bank] | Inflates that dataset's total by the duplicate amount |
| 4 | Orphan refund | Refund whose original_txn_id exists nowhere | Negative amount with no traceable original |

(Fill in exact txn IDs and amounts once your generator runs. Save them to
`answer_key.json` too.)

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