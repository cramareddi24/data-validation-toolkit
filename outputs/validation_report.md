# Data Validation Report

Checked **479 records** across 4 tables. Found **14 issues**: 7 Critical, 7 Warning.

**Release recommendation:** Hold. Critical issues affect numbers shown on the dashboard.

## Records checked

| Table | Records | Issues |
|---|---|---|
| clients | 41 | 4 |
| accounts | 81 | 2 |
| holdings | 237 | 5 |
| meetings | 120 | 3 |

## Issues by check

| Check | Severity | Count | Likely root cause |
|---|---|---|---|
| foreign_key | Critical | 2 | Child record points to a parent that was never created or was deleted. |
| calculated_field | Critical | 1 | Stored value was edited manually or calculated from stale inputs. |
| reconciliation | Critical | 1 | Summary total isn't refreshed when underlying records change. |
| required | Critical | 1 | Field not enforced as mandatory at entry, or dropped during import. |
| type | Critical | 1 | Free-text entry or a bad export format; value can't be parsed. |
| unique | Critical | 1 | Same record created twice, often from a re-import or double submit. |
| allowed_values | Warning | 3 | Dropdown not enforced; value typed manually (typo or old label). |
| min_value | Warning | 2 | Sign error or reversal entered as a negative amount. |
| date_order | Warning | 1 | Date entered incorrectly, or record backdated during migration. |
| pattern | Warning | 1 | Input format not validated at entry. |

## Issue log

| # | Severity | Table | Record | Check | Detail |
|---|---|---|---|---|---|
| 1 | Critical | accounts | ACC-1026 | foreign_key | client_id 'C099' not found in clients.client_id |
| 2 | Critical | accounts | ACC-1011 | reconciliation | Reported 28,971.07 vs sum of holdings 16,471.07 (variance +12,500.00) |
| 3 | Critical | clients | C022 | required | last_name is required but blank |
| 4 | Critical | clients | C017 | unique | Duplicate client_id |
| 5 | Critical | holdings | H00013 | calculated_field | market_value is 76,926.80 but quantity x price = 76,676.80 (off by 250.00) |
| 6 | Critical | holdings | H99999 | foreign_key | account_id 'ACC-9999' not found in accounts.account_id |
| 7 | Critical | meetings | M0015 | type | meeting_date is not a valid date |
| 8 | Warning | clients | C009 | allowed_values | 'Agressive' is not one of ['Conservative', 'Moderate', 'Aggressive'] |
| 9 | Warning | clients | C004 | pattern | email doesn't match the expected format |
| 10 | Warning | holdings | H00031 | allowed_values | 'Equities' is not one of ['Equity', 'Fixed Income', 'ETF', 'Mutual Fund', 'Cash'] |
| 11 | Warning | holdings | H00006 | min_value | quantity is below the minimum of 0 |
| 12 | Warning | holdings | H00006 | min_value | market_value is below the minimum of 0 |
| 13 | Warning | meetings | M0008 | allowed_values | 'Done' is not one of ['Scheduled', 'Completed', 'Canceled', 'No Show'] |
| 14 | Warning | meetings | M0041 | date_order | meeting_date 2023-10-14 is before onboard_date 2023-11-28 |
