import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model import (Assumptions, cdr_to_mdr, cpr_to_smm, price,  # noqa: E402
                   project_cashflows, run_scenarios, wal)

NO_STRESS = Assumptions(cpr=0.0, cdr=0.0, severity=0.0)


def test_rate_conversions():
    assert cpr_to_smm(0.0) == 0
    assert cpr_to_smm(0.06) == pytest.approx(0.005143, abs=1e-6)
    assert (1 - cdr_to_mdr(0.12)) ** 12 == pytest.approx(0.88)


def test_principal_fully_returned_without_losses():
    cf = project_cashflows(1_000_000, 0.05, 120, Assumptions(0.10, 0.0, 0.0))
    principal = cf[["scheduled_principal", "prepayment", "recovery"]].sum().sum()
    assert principal == pytest.approx(1_000_000, rel=1e-9)


def test_principal_plus_losses_equals_balance_with_defaults():
    cf = project_cashflows(1_000_000, 0.05, 120, Assumptions(0.05, 0.03, 0.4))
    returned = cf[["scheduled_principal", "prepayment", "recovery", "loss"]].sum().sum()
    assert returned == pytest.approx(1_000_000, rel=1e-9)
    assert cf["loss"].sum() > 0


def test_par_bond_prices_at_par_when_spread_matches_coupon():
    cf = project_cashflows(1_000_000, 0.06, 60, NO_STRESS)
    assert price(cf, 1_000_000, spread_bps=175, base_rate=0.0425) == pytest.approx(100, abs=1e-6)


def test_faster_prepayment_shortens_wal():
    slow = wal(project_cashflows(1e6, 0.05, 360, Assumptions(0.02, 0, 0)))
    fast = wal(project_cashflows(1e6, 0.05, 360, Assumptions(0.20, 0, 0)))
    assert fast < slow


def test_scenarios_move_in_expected_direction():
    base = Path(__file__).resolve().parents[1] / "data"
    res = run_scenarios(pd.read_csv(base / "sample_portfolio.csv"), pd.read_csv(base / "prepayment_rates.csv"))
    pnl = res.groupby("scenario")["pnl"].sum()
    assert pnl["Base"] == 0
    assert pnl["Spreads +100bp"] < 0
    assert pnl["Credit stress (3x CDR, +15% sev)"] < 0
    assert pnl["Combined stress"] < min(pnl["Spreads +100bp"], pnl["Credit stress (3x CDR, +15% sev)"])
    agency = res[(res["sector"] == "Agency MBS") & (res["scenario"].str.startswith("Credit"))]
    assert (agency["price_change"] == 0).all()  # agency paper carries no credit-loss assumption
