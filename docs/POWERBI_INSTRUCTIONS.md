# Building the Power BI dashboard

The model writes Power BI-ready CSVs to `dashboard/exports/`. Run the pipeline first:

```bash
python scripts/run_model.py
python scripts/generate_dashboard_data.py
```

## Import

In Power BI Desktop: **Get Data → Text/CSV** and load:

| File | Grain | Use for |
|---|---|---|
| `Scenario_Results.csv` | tranche × scenario | Detail table, slicers on scenario / sector / rating |
| `Portfolio_Summary.csv` | scenario | KPI cards: market value, P&L, WAL, duration |
| `Sector_Scenario_PnL.csv` | sector × scenario | Heatmap (matrix visual with conditional formatting) |
| `Sector_Tranche_Metrics.csv` | sector × tranche (base case) | Composition and collateral profile |

## Suggested pages

1. **Portfolio summary**: KPI cards from `Portfolio_Summary` filtered to Base; notional by sector bar chart.
2. **Stress testing**: clustered bar of `pnl_vs_base` by scenario; matrix of `Sector_Scenario_PnL` with a red-to-green color scale.
3. **Tranche detail**: table from `Scenario_Results` with a scenario slicer; sort by `price_change` to surface the most exposed bonds.

Useful DAX measure:

```DAX
P&L % of Notional = DIVIDE ( SUM ( Scenario_Results[pnl] ), SUM ( Scenario_Results[notional] ) )
```

The PNGs in `dashboard/exports/` (`Risk_Heatmap.png`, `Notional_By_Sector.png`) can be dropped onto a page as static images if you prefer not to rebuild those visuals.
