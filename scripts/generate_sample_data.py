"""generate_sample_data.py
Builds a synthetic securitized-products portfolio with internally consistent
relationships: spreads widen with lower ratings, Agency MBS carry agency credit
(no default assumption), prepayment speeds and default rates vary by sector.

Usage: python scripts/generate_sample_data.py [--n 40] [--seed 11]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]

# Typical behaviour by sector (annual CPR, annual CDR at BBB, loss severity, amortizing?)
SECTOR_PROFILE = {
    "Agency MBS": {"cpr": 0.08, "cdr": 0.000, "severity": 0.00, "term_yrs": (20, 30)},
    "RMBS":       {"cpr": 0.07, "cdr": 0.010, "severity": 0.35, "term_yrs": (15, 30)},
    "CMBS":       {"cpr": 0.01, "cdr": 0.015, "severity": 0.40, "term_yrs": (5, 10)},
    "ABS":        {"cpr": 0.12, "cdr": 0.020, "severity": 0.50, "term_yrs": (3, 6)},
    "CLO":        {"cpr": 0.15, "cdr": 0.025, "severity": 0.35, "term_yrs": (6, 10)},
}
RATING_SPREAD_ADD = {"AAA": 0, "AA": 40, "A": 85, "BBB": 175, "BB": 400, "B": 650}
RATING_CDR_MULT = {"AAA": 0.2, "AA": 0.4, "A": 0.7, "BBB": 1.0, "BB": 2.0, "B": 3.5}
TRANCHE_RATINGS = {"Senior": ["AAA", "AA"], "Mezzanine": ["A", "BBB"], "Junior": ["BB", "B"]}


def generate(n=40, seed=11, valuation_date="2025-10-01"):
    rng = np.random.default_rng(seed)
    base_spreads = pd.read_csv(BASE / "data" / "credit_spreads.csv").set_index("sector")["avg_spread_bps"]
    val = pd.Timestamp(valuation_date)
    rows = []
    for i in range(n):
        sector = rng.choice(list(SECTOR_PROFILE))
        prof = SECTOR_PROFILE[sector]
        if sector == "Agency MBS":
            tranche, rating = "Pass-through", "AGY"
            spread = base_spreads[sector] + rng.normal(0, 8)
            cdr = 0.0
        else:
            tranche = rng.choice(list(TRANCHE_RATINGS), p=[0.55, 0.30, 0.15])
            rating = rng.choice(TRANCHE_RATINGS[tranche])
            spread = base_spreads[sector] + RATING_SPREAD_ADD[rating] + rng.normal(0, 15)
            cdr = prof["cdr"] * RATING_CDR_MULT[rating] * rng.uniform(0.8, 1.2)
        years = rng.integers(*prof["term_yrs"], endpoint=True)
        rows.append({
            "id": f"TRN{1000 + i}",
            "sector": sector,
            "tranche": tranche,
            "rating": rating,
            "notional": int(rng.integers(100, 1200)) * 100_000,
            "coupon": round(rng.uniform(0.025, 0.065) + (spread / 10_000) * 0.5, 4),
            "maturity": (val + pd.DateOffset(years=int(years))).date(),
            "cpr": round(prof["cpr"] * rng.uniform(0.7, 1.3), 4),
            "cdr": round(cdr, 4),
            "severity": prof["severity"],
            "spread_bps": round(max(spread, 20)),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()
    df = generate(a.n, a.seed)
    df.to_csv(BASE / "data" / "sample_portfolio.csv", index=False)
    print(f"Wrote {len(df)} tranches to data/sample_portfolio.csv")
