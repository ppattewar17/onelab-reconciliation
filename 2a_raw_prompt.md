Build a payment reconciliation tool using Python and Streamlit.
Generate fake platform transaction data and bank settlement data with some mismatches.
Include cases like next-month settlements, rounding differences, duplicate entries, missing transactions, and refunds without original transactions.
Compare both datasets and automatically find all the mismatches.
Show a dashboard with matched, unmatched, and duplicate amounts, along with a summary of where the gaps are.
Also show detailed results and allow downloading the reconciliation report.
Add pytest test cases to check that all reconciliation scenarios are working correctly.
