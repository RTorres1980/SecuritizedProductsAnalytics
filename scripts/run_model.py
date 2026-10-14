"""run_model.py
Values every tranche under each scenario and writes:
  dashboard/exports/Scenario_Results.csv   tranche x scenario detail
  dashboard/exports/Portfolio_Summary.csv  portfolio-level P&L, WAL, duration by scenario
  dashboard/exports/Sector_Scenario_PnL.csv
  dashboard/exports/Risk_Heatmap.png       P&L (% of notional) by sector x scenario

Usage: python scripts/run_model.py [--valuation-date 2025-10-01]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import run_scenarios, weighted  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
EXPORTS = BASE / "dashboard" / "exports"


def portfolio_summary(results):
    rows = []
    for name, g in results.groupby("scenario", sort=False):
        rows.append({
            "scenario": name,
            "market_value": g["mv"].sum(),
            "pnl_vs_base": g["pnl"].sum(),
            "pnl_pct_of_notional": 100 * g["pnl"].sum() / g["notional"].sum(),
            "wavg_price": weighted(g, "price"),
            "wavg_wal_yrs": weighted(g, "wal_yrs"),
            "wavg_eff_duration": weighted(g, "eff_duration"),
            "wavg_cum_loss_pct": weighted(g, "cum_loss_pct"),
        })
    return pd.DataFrame(rows).round(2)


def sector_pnl(results):
    g = results.groupby(["sector", "scenario"], sort=False)
    pct = (100 * g["pnl"].sum() / g["notional"].sum()).unstack("scenario")
    return pct[results["scenario"].unique()].round(2)


def heatmap(pct, path):
    fig = Figure(figsize=(10, 4))  # backend-independent, so notebooks importing this keep inline plots
    ax = fig.subplots()
    lim = max(abs(pct.values.min()), abs(pct.values.max()), 0.01)
    im = ax.imshow(pct.values, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(pct.columns)), pct.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(pct.index)), pct.index)
    for (i, j), v in pd.DataFrame(pct.values).stack().items():
        ax.text(j, i, f"{v:+.2f}%", ha="center", va="center", fontsize=8,
                color="white" if abs(v) > 0.6 * lim else "black")
    ax.set_title("Scenario P&L by sector (% of notional vs. base)")
    fig.colorbar(im, ax=ax, label="% of notional")
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--valuation-date", default="2025-10-01")
    args = p.parse_args()

    portfolio = pd.read_csv(BASE / "data" / "sample_portfolio.csv")
    prepay = pd.read_csv(BASE / "data" / "prepayment_rates.csv")
    EXPORTS.mkdir(parents=True, exist_ok=True)

    results = run_scenarios(portfolio, prepay, args.valuation_date)
    results.to_csv(EXPORTS / "Scenario_Results.csv", index=False)
    summary = portfolio_summary(results)
    summary.to_csv(EXPORTS / "Portfolio_Summary.csv", index=False)
    pct = sector_pnl(results)
    pct.to_csv(EXPORTS / "Sector_Scenario_PnL.csv")
    heatmap(pct, EXPORTS / "Risk_Heatmap.png")

    print(summary.to_string(index=False))
    print(f"\nOutputs saved to {EXPORTS.relative_to(BASE)}")


if __name__ == "__main__":
    main()
