"""
Generates synthetic data for three modules of a fictional financial advisory
dashboard (Clients, Portfolio, Meetings) and plants a known set of errors so
the validator has something real to catch.

No real client or company data is used. Names, tickers, and values are made up.

Usage:
    python scripts/generate_sample_data.py
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 7
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

FIRST = ["Alex", "Jordan", "Priya", "Marcus", "Elena", "Sam", "Nina", "Omar", "Grace", "Leo",
         "Maya", "Ethan", "Sofia", "Daniel", "Aisha", "Ryan", "Hana", "Lucas", "Zoe", "Victor"]
LAST = ["Nguyen", "Lee", "Patel", "Garcia", "Kim", "Brooks", "Chen", "Rivera", "Shah", "Morgan",
        "Ali", "Foster", "Ortiz", "Reyes", "Kapoor", "Hughes", "Tran", "Bennett", "Diaz", "Cole"]
TICKERS = {
    "Equity": ["NRVA", "QTMX", "BLZE", "KRNL"],
    "ETF": ["TOTL", "GRWX", "DIVQ"],
    "Fixed Income": ["BNDQ", "MUNX", "TRSY"],
    "Mutual Fund": ["VALFX", "GRTHX"],
    "Cash": ["CASH"],
}
ACCOUNT_TYPES = ["Brokerage", "Traditional IRA", "Roth IRA", "401k Rollover", "Trust"]
MEETING_TYPES = ["Annual Review", "Portfolio Review", "Check-in"]


def rand_date(rng, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def build_clients(rng, n=40):
    rows = []
    for i in range(1, n + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        rows.append({
            "client_id": f"C{i:03d}",
            "first_name": first,
            "last_name": last,
            "email": f"{first.lower()}.{last.lower()}{i}@example.com",
            "risk_profile": rng.choice(["Conservative", "Moderate", "Aggressive"]),
            "advisor_id": f"A{rng.randint(1, 5):02d}",
            "onboard_date": rand_date(rng, date(2022, 1, 1), date(2024, 12, 31)).isoformat(),
            "status": rng.choices(["Active", "Inactive"], weights=[9, 1])[0],
        })
    return pd.DataFrame(rows)


def build_accounts(rng, clients):
    rows, n = [], 1001
    for _, c in clients.iterrows():
        for _ in range(rng.randint(1, 3)):
            onboard = date.fromisoformat(c["onboard_date"])
            rows.append({
                "account_id": f"ACC-{n}",
                "client_id": c["client_id"],
                "account_type": rng.choice(ACCOUNT_TYPES),
                "opened_date": rand_date(rng, onboard, onboard + timedelta(days=60)).isoformat(),
                "reported_total_value": 0.0,  # filled in after holdings are built
            })
            n += 1
    return pd.DataFrame(rows)


def build_holdings(rng, accounts):
    rows, n = [], 1
    for acct in accounts["account_id"]:
        for asset_class in rng.sample(list(TICKERS), rng.randint(2, 4)):
            ticker = rng.choice(TICKERS[asset_class])
            price = 1.00 if asset_class == "Cash" else round(rng.uniform(12, 480), 2)
            qty = round(rng.uniform(500, 25000), 2) if asset_class == "Cash" else rng.randint(5, 900)
            rows.append({
                "holding_id": f"H{n:05d}",
                "account_id": acct,
                "ticker": ticker,
                "asset_class": asset_class,
                "quantity": qty,
                "price": price,
                "market_value": round(qty * price, 2),
            })
            n += 1
    return pd.DataFrame(rows)


def build_meetings(rng, clients):
    rows, n = [], 1
    for _, c in clients.iterrows():
        onboard = date.fromisoformat(c["onboard_date"])
        rows.append({
            "meeting_id": f"M{n:04d}", "client_id": c["client_id"], "advisor_id": c["advisor_id"],
            "meeting_date": onboard.isoformat(), "meeting_type": "Onboarding", "status": "Completed",
        })
        n += 1
        for _ in range(rng.randint(1, 3)):
            rows.append({
                "meeting_id": f"M{n:04d}", "client_id": c["client_id"], "advisor_id": c["advisor_id"],
                "meeting_date": rand_date(rng, onboard + timedelta(days=30), date(2025, 9, 30)).isoformat(),
                "meeting_type": rng.choice(MEETING_TYPES),
                "status": rng.choices(["Completed", "Scheduled", "Canceled", "No Show"], weights=[70, 15, 10, 5])[0],
            })
            n += 1
    return pd.DataFrame(rows)


def plant_errors(clients, accounts, holdings, meetings):
    """Each line here is one discrepancy the validator should catch."""
    # Clients module
    dup = clients.iloc[[16]].copy()
    dup["email"] = "duplicate.record@example.com"
    clients = pd.concat([clients, dup], ignore_index=True)                       # duplicate client_id
    clients.loc[3, "email"] = "jordan.lee@gmail"                                  # invalid email
    clients.loc[8, "risk_profile"] = "Agressive"                                  # typo in allowed value
    clients.loc[21, "last_name"] = ""                                             # missing required field

    # Portfolio module (holding level)
    holdings.loc[5, "quantity"] = -40                                             # negative quantity
    holdings.loc[5, "market_value"] = round(-40 * holdings.loc[5, "price"], 2)
    holdings.loc[12, "market_value"] = round(holdings.loc[12, "market_value"] + 250.00, 2)  # value != qty x price
    holdings.loc[30, "asset_class"] = "Equities"                                  # wrong category label
    orphan = holdings.iloc[[0]].copy()
    orphan["holding_id"] = "H99999"
    orphan["account_id"] = "ACC-9999"
    holdings = pd.concat([holdings, orphan], ignore_index=True)                   # holding with no account

    # Account totals come from holdings, like the real dashboard would
    totals = holdings.groupby("account_id")["market_value"].sum().round(2)
    accounts["reported_total_value"] = accounts["account_id"].map(totals).fillna(0)
    accounts.loc[10, "reported_total_value"] = round(accounts.loc[10, "reported_total_value"] + 12500, 2)  # total mismatch
    accounts.loc[25, "client_id"] = "C099"                                        # account with no client

    # Meetings module
    meetings.loc[7, "status"] = "Done"                                            # invalid status
    meetings.loc[14, "meeting_date"] = "2025-13-02"                               # unparseable date
    client_id = meetings.loc[40, "client_id"]
    onboard = date.fromisoformat(clients.loc[clients["client_id"] == client_id, "onboard_date"].iloc[0])
    meetings.loc[40, "meeting_date"] = (onboard - timedelta(days=45)).isoformat() # meeting before onboarding

    return clients, accounts, holdings, meetings


def main():
    rng = random.Random(SEED)
    clients = build_clients(rng)
    accounts = build_accounts(rng, clients)
    holdings = build_holdings(rng, accounts)
    meetings = build_meetings(rng, clients)
    clients, accounts, holdings, meetings = plant_errors(clients, accounts, holdings, meetings)

    DATA_DIR.mkdir(exist_ok=True)
    for name, df in [("clients", clients), ("accounts", accounts), ("holdings", holdings), ("meetings", meetings)]:
        df.to_csv(DATA_DIR / f"{name}.csv", index=False)
        print(f"{name}: {len(df)} rows")


if __name__ == "__main__":
    main()
