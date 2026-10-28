"""
Individual validation checks.

Every check takes plain pandas DataFrames plus a rule, and returns a list of
Issue records. Keeping them small and independent makes each one easy to
unit test and easy to explain to a non-technical stakeholder.
"""

from dataclasses import dataclass, asdict

import pandas as pd

# Critical = the number on the dashboard is wrong or a record is broken.
# Warning  = the data is usable but inconsistent and should be cleaned up.
SEVERITY = {
    "required": "Critical",
    "unique": "Critical",
    "type": "Critical",
    "foreign_key": "Critical",
    "calculated_field": "Critical",
    "reconciliation": "Critical",
    "allowed_values": "Warning",
    "pattern": "Warning",
    "min_value": "Warning",
    "date_order": "Warning",
}

# Most likely root cause for each kind of failure, used in the report
ROOT_CAUSE_HINTS = {
    "required": "Field not enforced as mandatory at entry, or dropped during import.",
    "unique": "Same record created twice, often from a re-import or double submit.",
    "type": "Free-text entry or a bad export format; value can't be parsed.",
    "foreign_key": "Child record points to a parent that was never created or was deleted.",
    "calculated_field": "Stored value was edited manually or calculated from stale inputs.",
    "reconciliation": "Summary total isn't refreshed when underlying records change.",
    "allowed_values": "Dropdown not enforced; value typed manually (typo or old label).",
    "pattern": "Input format not validated at entry.",
    "min_value": "Sign error or reversal entered as a negative amount.",
    "date_order": "Date entered incorrectly, or record backdated during migration.",
}


@dataclass
class Issue:
    table: str
    check: str
    column: str
    record_id: str
    value: str
    message: str

    @property
    def severity(self) -> str:
        return SEVERITY[self.check]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity
        d["likely_root_cause"] = ROOT_CAUSE_HINTS[self.check]
        return d


def _is_blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def _ids(df: pd.DataFrame, pk: str, mask: pd.Series) -> list[str]:
    return df.loc[mask, pk].astype(str).tolist()


# ---------------------------------------------------------------------------
# Column-level checks
# ---------------------------------------------------------------------------
def check_required(df, table, pk, column) -> list[Issue]:
    mask = _is_blank(df[column])
    return [Issue(table, "required", column, rid, "", f"{column} is required but blank")
            for rid in _ids(df, pk, mask)]


def check_unique(df, table, pk, column) -> list[Issue]:
    mask = df[column].duplicated(keep="first") & ~_is_blank(df[column])
    return [Issue(table, "unique", column, rid, rid, f"Duplicate {column}")
            for rid in _ids(df, pk, mask)]


def check_type(df, table, pk, column, expected) -> list[Issue]:
    present = ~_is_blank(df[column])
    if expected == "number":
        parsed = pd.to_numeric(df[column], errors="coerce")
    elif expected == "date":
        parsed = pd.to_datetime(df[column], format="%Y-%m-%d", errors="coerce")
    else:
        return []
    mask = present & parsed.isna()
    return [Issue(table, "type", column, str(df.loc[i, pk]), str(df.loc[i, column]),
                  f"{column} is not a valid {expected}")
            for i in df.index[mask]]


def check_allowed(df, table, pk, column, allowed) -> list[Issue]:
    mask = ~_is_blank(df[column]) & ~df[column].isin(allowed)
    return [Issue(table, "allowed_values", column, str(df.loc[i, pk]), str(df.loc[i, column]),
                  f"'{df.loc[i, column]}' is not one of {allowed}")
            for i in df.index[mask]]


def check_pattern(df, table, pk, column, pattern) -> list[Issue]:
    values = df[column].astype(str)
    mask = ~_is_blank(df[column]) & ~values.str.fullmatch(pattern)
    return [Issue(table, "pattern", column, str(df.loc[i, pk]), values[i],
                  f"{column} doesn't match the expected format")
            for i in df.index[mask]]


def check_min(df, table, pk, column, minimum) -> list[Issue]:
    nums = pd.to_numeric(df[column], errors="coerce")
    mask = nums < minimum
    return [Issue(table, "min_value", column, str(df.loc[i, pk]), str(df.loc[i, column]),
                  f"{column} is below the minimum of {minimum}")
            for i in df.index[mask]]


# ---------------------------------------------------------------------------
# Cross-table and business rule checks
# ---------------------------------------------------------------------------
def check_foreign_key(child, child_name, child_pk, column, parent, parent_name, parent_col) -> list[Issue]:
    valid = set(parent[parent_col].dropna())
    mask = ~_is_blank(child[column]) & ~child[column].isin(valid)
    return [Issue(child_name, "foreign_key", column, str(child.loc[i, child_pk]), str(child.loc[i, column]),
                  f"{column} '{child.loc[i, column]}' not found in {parent_name}.{parent_col}")
            for i in child.index[mask]]


def check_calculated_field(df, table, pk, target, factors, tolerance) -> list[Issue]:
    expected = pd.Series(1.0, index=df.index)
    for f in factors:
        expected = expected * pd.to_numeric(df[f], errors="coerce")
    actual = pd.to_numeric(df[target], errors="coerce")
    diff = (actual - expected).abs()
    mask = diff > tolerance
    return [Issue(table, "calculated_field", target, str(df.loc[i, pk]), f"{actual[i]:,.2f}",
                  f"{target} is {actual[i]:,.2f} but {' x '.join(factors)} = {expected[i]:,.2f} "
                  f"(off by {diff[i]:,.2f})")
            for i in df.index[mask]]


def check_reconciliation(parent, parent_name, parent_key, parent_value,
                         child, child_key, child_value, tolerance) -> list[Issue]:
    child_totals = (child.assign(_v=pd.to_numeric(child[child_value], errors="coerce"))
                    .groupby(child_key)["_v"].sum())
    reported = pd.to_numeric(parent[parent_value], errors="coerce")
    computed = parent[parent_key].map(child_totals).fillna(0)
    diff = (reported - computed).abs()
    mask = diff > tolerance
    return [Issue(parent_name, "reconciliation", parent_value, str(parent.loc[i, parent_key]),
                  f"{reported[i]:,.2f}",
                  f"Reported {reported[i]:,.2f} vs sum of holdings {computed[i]:,.2f} "
                  f"(variance {reported[i] - computed[i]:+,.2f})")
            for i in parent.index[mask]]


def check_date_order(df, table, pk, date_col, ref, join_key, ref_date_col) -> list[Issue]:
    ref_dates = (ref.drop_duplicates(subset=join_key)
                 .set_index(join_key)[ref_date_col]
                 .pipe(pd.to_datetime, format="%Y-%m-%d", errors="coerce"))
    dates = pd.to_datetime(df[date_col], format="%Y-%m-%d", errors="coerce")
    ref_for_row = df[join_key].map(ref_dates)
    mask = dates < ref_for_row
    return [Issue(table, "date_order", date_col, str(df.loc[i, pk]), str(df.loc[i, date_col]),
                  f"{date_col} {df.loc[i, date_col]} is before {ref_date_col} {ref_for_row[i]:%Y-%m-%d}")
            for i in df.index[mask]]
