"""model.py
Monthly cash-flow engine for securitized tranches with prepayment (CPR/SMM),
defaults (CDR/MDR) and loss severity, plus pricing, WAL and effective duration.

Simplification: each tranche is modeled on its own collateral cash flows
(no deal waterfall / subordination). That is enough to show how prepayment,
credit and spread assumptions move value, which is the point of the scenarios.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

BASE_RATE = 0.0425  # flat benchmark rate; spread is added on top for discounting


def cpr_to_smm(cpr):
    """Annual conditional prepayment rate -> single monthly mortality."""
    return 1 - (1 - cpr) ** (1 / 12)


def cdr_to_mdr(cdr):
    """Annual constant default rate -> monthly default rate."""
    return 1 - (1 - cdr) ** (1 / 12)


@dataclass
class Assumptions:
    cpr: float
    cdr: float
    severity: float


def project_cashflows(balance, coupon, months, a: Assumptions):
    """Return a DataFrame of monthly cash flows for a level-pay amortizing pool."""
    r = coupon / 12
    smm, mdr = cpr_to_smm(a.cpr), cdr_to_mdr(a.cdr)
    rows = []
    for t in range(1, months + 1):
        if balance <= 0.01:
            break
        remaining = months - t + 1
        defaults = balance * mdr
        perf = balance - defaults
        interest = perf * r
        payment = perf * r / (1 - (1 + r) ** -remaining) if r > 0 else perf / remaining
        sched = min(payment - interest, perf)
        prepay = (perf - sched) * smm
        if t == months:  # balloon: retire whatever is left
            sched = perf - prepay
        recovery = defaults * (1 - a.severity)
        loss = defaults * a.severity
        principal = sched + prepay + recovery
        rows.append((t, balance, interest, sched, prepay, recovery, loss, interest + principal))
        balance = perf - sched - prepay
    return pd.DataFrame(rows, columns=["month", "begin_balance", "interest", "scheduled_principal",
                                       "prepayment", "recovery", "loss", "total_cash"])


def price(cf, notional, spread_bps, base_rate=BASE_RATE):
    """Price per 100 of face: cash flows discounted at benchmark + spread (monthly)."""
    y = (base_rate + spread_bps / 10_000) / 12
    pv = (cf["total_cash"] / (1 + y) ** cf["month"]).sum()
    return 100 * pv / notional


def wal(cf):
    """Weighted-average life in years (principal-weighted, includes recoveries)."""
    prin = cf["scheduled_principal"] + cf["prepayment"] + cf["recovery"]
    return float((cf["month"] * prin).sum() / prin.sum() / 12) if prin.sum() else 0.0


def effective_duration(cf, notional, spread_bps, shift_bps=25):
    up = price(cf, notional, spread_bps + shift_bps)
    down = price(cf, notional, spread_bps - shift_bps)
    mid = price(cf, notional, spread_bps)
    return (down - up) / (2 * mid * shift_bps / 10_000)


def months_to(maturity, valuation_date):
    m = (pd.Timestamp(maturity).year - valuation_date.year) * 12 + pd.Timestamp(maturity).month - valuation_date.month
    return max(int(m), 1)


def value_tranche(row, valuation_date, cpr_mult=1.0, cdr_mult=1.0, severity_add=0.0, spread_add=0.0):
    a = Assumptions(cpr=min(row.cpr * cpr_mult, 0.99),
                    cdr=min(row.cdr * cdr_mult, 0.99),
                    severity=min(row.severity + (severity_add if row.cdr > 0 else 0), 1.0))
    cf = project_cashflows(row.notional, row.coupon, months_to(row.maturity, valuation_date), a)
    spread = row.spread_bps + spread_add
    return {
        "price": price(cf, row.notional, spread),
        "wal_yrs": wal(cf),
        "eff_duration": effective_duration(cf, row.notional, spread),
        "cum_loss_pct": 100 * cf["loss"].sum() / row.notional,
    }


def scenarios(prepay_table):
    """Base case plus prepay, spread and credit stresses. Prepay multipliers come
    from data/prepayment_rates.csv (PSA-style speed labels)."""
    mult = prepay_table.set_index("speed_label")["multiplier"]
    return {
        "Base": {},
        "Slow prepay (PSA_50)": {"cpr_mult": mult["PSA_50"]},
        "Fast prepay (PSA_200)": {"cpr_mult": mult["PSA_200"]},
        "Spreads +100bp": {"spread_add": 100},
        "Credit stress (3x CDR, +15% sev)": {"cdr_mult": 3.0, "severity_add": 0.15},
        "Combined stress": {"cpr_mult": mult["PSA_50"], "cdr_mult": 3.0, "severity_add": 0.15, "spread_add": 100},
    }


def run_scenarios(portfolio, prepay_table, valuation_date="2025-10-01"):
    val = pd.Timestamp(valuation_date)
    out = []
    for name, shocks in scenarios(prepay_table).items():
        for row in portfolio.itertuples(index=False):
            res = value_tranche(row, val, **shocks)
            out.append({"scenario": name, "id": row.id, "sector": row.sector, "tranche": row.tranche,
                        "rating": row.rating, "notional": row.notional, **res})
    df = pd.DataFrame(out)
    base = df[df["scenario"] == "Base"].set_index("id")["price"]
    df["price_change"] = df["price"] - df["id"].map(base)
    df["mv"] = df["price"] / 100 * df["notional"]
    df["pnl"] = df["price_change"] / 100 * df["notional"]
    return df.round({"price": 3, "wal_yrs": 2, "eff_duration": 2, "cum_loss_pct": 2, "price_change": 3,
                     "mv": 0, "pnl": 0})


def weighted(df, col):
    return np.average(df[col], weights=df["notional"])
