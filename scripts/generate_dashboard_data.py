"""generate_dashboard_data.py
Produces Power BI-ready CSVs and a notional-by-sector chart from the base-case results.
Run scripts/run_model.py first.
"""
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
EXPORTS = BASE / "dashboard" / "exports"

results = pd.read_csv(EXPORTS / "Scenario_Results.csv")
base = results[results["scenario"] == "Base"]

metrics = base.groupby(["sector", "tranche"]).apply(
    lambda g: pd.Series({
        "tranches": len(g),
        "total_notional": g["notional"].sum(),
        "market_value": g["mv"].sum(),
        "wavg_price": (g["price"] * g["notional"]).sum() / g["notional"].sum(),
        "wavg_wal_yrs": (g["wal_yrs"] * g["notional"]).sum() / g["notional"].sum(),
        "wavg_duration": (g["eff_duration"] * g["notional"]).sum() / g["notional"].sum(),
    }), include_groups=False).round(2).reset_index()
metrics.to_csv(EXPORTS / "Sector_Tranche_Metrics.csv", index=False)

sector = base.groupby("sector")["notional"].sum().sort_values() / 1e6
fig, ax = plt.subplots(figsize=(7, 3.5))
ax.barh(sector.index, sector.values, color="#3b6ea5")
ax.set_xlabel("Notional ($MM)")
ax.set_title("Portfolio notional by sector")
for i, v in enumerate(sector.values):
    ax.text(v, i, f" {v:,.0f}", va="center", fontsize=8)
fig.tight_layout()
fig.savefig(EXPORTS / "Notional_By_Sector.png", dpi=150)
print("Wrote Sector_Tranche_Metrics.csv and Notional_By_Sector.png")
