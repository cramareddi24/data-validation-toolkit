"""
Runs every rule in config/schemas.json against the CSVs in data/ and writes:
    outputs/validation_issues.csv   one row per issue, with a likely root cause
    outputs/validation_report.md    summary for stakeholders

Usage:
    python -m validator.runner
    python -m validator.runner --fail-on-critical   # exit code 1 if anything Critical is found (for CI)
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from validator import checks

ROOT = Path(__file__).resolve().parents[1]


def load_tables(config: dict, data_dir: Path) -> dict[str, pd.DataFrame]:
    # Read everything as text so the validator decides what's valid, not pandas
    return {
        name: pd.read_csv(data_dir / spec["file"], dtype=str, keep_default_na=False)
        for name, spec in config["tables"].items()
    }


def run_checks(config: dict, tables: dict[str, pd.DataFrame]) -> list[checks.Issue]:
    issues: list[checks.Issue] = []

    # Column-level rules
    for name, spec in config["tables"].items():
        df, pk = tables[name], spec["primary_key"]
        missing = [c for c in spec["columns"] if c not in df.columns]
        if missing:
            raise ValueError(f"{name} is missing expected columns: {missing}")

        for col, rule in spec["columns"].items():
            if rule.get("required"):
                issues += checks.check_required(df, name, pk, col)
            if rule.get("unique"):
                issues += checks.check_unique(df, name, pk, col)
            if rule.get("type") in ("number", "date"):
                issues += checks.check_type(df, name, pk, col, rule["type"])
            if "allowed" in rule:
                issues += checks.check_allowed(df, name, pk, col, rule["allowed"])
            if "pattern" in rule:
                issues += checks.check_pattern(df, name, pk, col, rule["pattern"])
            if "min" in rule:
                issues += checks.check_min(df, name, pk, col, rule["min"])

    # Referential integrity across modules
    for fk in config.get("foreign_keys", []):
        child_pk = config["tables"][fk["table"]]["primary_key"]
        issues += checks.check_foreign_key(
            tables[fk["table"]], fk["table"], child_pk, fk["column"],
            tables[fk["ref_table"]], fk["ref_table"], fk["ref_column"],
        )

    # Business rules
    rules = config.get("business_rules", {})
    for r in rules.get("calculated_fields", []):
        pk = config["tables"][r["table"]]["primary_key"]
        issues += checks.check_calculated_field(tables[r["table"]], r["table"], pk, r["target"], r["factors"], r["tolerance"])

    for r in rules.get("reconciliations", []):
        issues += checks.check_reconciliation(
            tables[r["parent_table"]], r["parent_table"], r["parent_key"], r["parent_value"],
            tables[r["child_table"]], r["child_key"], r["child_value"], r["tolerance"],
        )

    for r in rules.get("date_order", []):
        pk = config["tables"][r["table"]]["primary_key"]
        issues += checks.check_date_order(
            tables[r["table"]], r["table"], pk, r["date_column"],
            tables[r["ref_table"]], r["join_key"], r["ref_date_column"],
        )

    return issues


def write_outputs(issues: list[checks.Issue], tables: dict, out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["severity", "table", "check", "column", "record_id", "value", "message", "likely_root_cause"]
    df = pd.DataFrame([i.to_dict() for i in issues], columns=cols)
    df["severity"] = pd.Categorical(df["severity"], ["Critical", "Warning"], ordered=True)
    df = df.sort_values(["severity", "table", "check", "record_id"]).reset_index(drop=True)
    df.to_csv(out_dir / "validation_issues.csv", index=False)

    total_rows = sum(len(t) for t in tables.values())
    n_crit = int((df["severity"] == "Critical").sum())
    n_warn = int((df["severity"] == "Warning").sum())

    lines = [
        "# Data Validation Report",
        "",
        f"Checked **{total_rows} records** across {len(tables)} tables. "
        f"Found **{len(df)} issues**: {n_crit} Critical, {n_warn} Warning.",
        "",
        "**Release recommendation:** "
        + ("Hold. Critical issues affect numbers shown on the dashboard." if n_crit else "Clear to release."),
        "",
        "## Records checked",
        "",
        "| Table | Records | Issues |",
        "|---|---|---|",
    ]
    for name, t in tables.items():
        lines.append(f"| {name} | {len(t)} | {int((df['table'] == name).sum())} |")

    lines += ["", "## Issues by check", "", "| Check | Severity | Count | Likely root cause |", "|---|---|---|---|"]
    by_check = df.groupby("check", observed=True).agg(count=("record_id", "size"), severity=("severity", "first"))
    for check, row in by_check.sort_values(["severity", "count"], ascending=[True, False]).iterrows():
        lines.append(f"| {check} | {row['severity']} | {row['count']} | {checks.ROOT_CAUSE_HINTS[check]} |")

    lines += ["", "## Issue log", "", "| # | Severity | Table | Record | Check | Detail |", "|---|---|---|---|---|---|"]
    for n, row in enumerate(df.itertuples(), start=1):
        lines.append(f"| {n} | {row.severity} | {row.table} | {row.record_id} | {row.check} | {row.message} |")

    (out_dir / "validation_report.md").write_text("\n".join(lines) + "\n")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dashboard data against schema and business rules.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "schemas.json")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    tables = load_tables(config, args.data)
    issues = run_checks(config, tables)
    df = write_outputs(issues, tables, args.output)

    print(f"{len(df)} issues found ({(df['severity'] == 'Critical').sum()} Critical, "
          f"{(df['severity'] == 'Warning').sum()} Warning)")
    print(f"Report: {args.output / 'validation_report.md'}")

    if args.fail_on_critical and (df["severity"] == "Critical").any():
        sys.exit(1)


if __name__ == "__main__":
    main()
