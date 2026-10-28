"""Unit tests for each validation check, using tiny hand-built tables."""

import pandas as pd

from validator import checks


def make_clients():
    return pd.DataFrame({
        "client_id": ["C001", "C002", "C002", "C003"],
        "email": ["a@example.com", "bad-email", "b@example.com", ""],
        "risk_profile": ["Moderate", "Agressive", "Conservative", "Aggressive"],
        "onboard_date": ["2024-01-10", "2024-02-01", "2024-02-01", "2024-03-15"],
    })


def test_required_flags_blank_values():
    issues = checks.check_required(make_clients(), "clients", "client_id", "email")
    assert [i.record_id for i in issues] == ["C003"]


def test_unique_flags_second_occurrence_only():
    issues = checks.check_unique(make_clients(), "clients", "client_id", "client_id")
    assert len(issues) == 1 and issues[0].record_id == "C002"


def test_allowed_values_catches_typo():
    allowed = ["Conservative", "Moderate", "Aggressive"]
    issues = checks.check_allowed(make_clients(), "clients", "client_id", "risk_profile", allowed)
    assert [i.value for i in issues] == ["Agressive"]


def test_pattern_skips_blanks_and_flags_bad_format():
    pattern = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"
    issues = checks.check_pattern(make_clients(), "clients", "client_id", "email", pattern)
    assert [i.value for i in issues] == ["bad-email"]


def test_type_check_rejects_impossible_date():
    df = pd.DataFrame({"meeting_id": ["M1", "M2"], "meeting_date": ["2025-01-05", "2025-13-02"]})
    issues = checks.check_type(df, "meetings", "meeting_id", "meeting_date", "date")
    assert [i.record_id for i in issues] == ["M2"]


def test_foreign_key_finds_orphans():
    accounts = pd.DataFrame({"account_id": ["ACC-1", "ACC-2"], "client_id": ["C001", "C999"]})
    issues = checks.check_foreign_key(accounts, "accounts", "account_id", "client_id",
                                      make_clients(), "clients", "client_id")
    assert [i.record_id for i in issues] == ["ACC-2"]


def test_calculated_field_respects_tolerance():
    holdings = pd.DataFrame({
        "holding_id": ["H1", "H2"],
        "quantity": ["10", "10"],
        "price": ["5.00", "5.00"],
        "market_value": ["50.004", "75.00"],
    })
    issues = checks.check_calculated_field(holdings, "holdings", "holding_id", "market_value",
                                           ["quantity", "price"], tolerance=0.01)
    assert [i.record_id for i in issues] == ["H2"]


def test_reconciliation_flags_variance():
    accounts = pd.DataFrame({"account_id": ["ACC-1", "ACC-2"], "reported_total_value": ["150", "999"]})
    holdings = pd.DataFrame({"account_id": ["ACC-1", "ACC-1", "ACC-2"], "market_value": ["100", "50", "100"]})
    issues = checks.check_reconciliation(accounts, "accounts", "account_id", "reported_total_value",
                                         holdings, "account_id", "market_value", tolerance=1.0)
    assert [i.record_id for i in issues] == ["ACC-2"]


def test_date_order_flags_meeting_before_onboarding():
    meetings = pd.DataFrame({"meeting_id": ["M1", "M2"], "client_id": ["C001", "C003"],
                             "meeting_date": ["2024-02-01", "2024-01-01"]})
    issues = checks.check_date_order(meetings, "meetings", "meeting_id", "meeting_date",
                                     make_clients(), "client_id", "onboard_date")
    assert [i.record_id for i in issues] == ["M2"]


def test_every_check_has_a_severity_and_root_cause():
    assert set(checks.SEVERITY) == set(checks.ROOT_CAUSE_HINTS)
