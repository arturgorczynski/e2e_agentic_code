---
{
  "access_scope": "analytics",
  "category": "planning_commentary",
  "document_id": "PLAN-010",
  "effective_from": "2011-12-01",
  "effective_until": null,
  "facts": {
    "id": "FC-UCI-SKU-22197-2011-12-v2",
    "input_sha256": "549e0acfafa3eaea4f17151063bc10449c668cc9c342ae0216aa15e62803b05e",
    "lookback_months": 2,
    "method_version": 2,
    "product_id": "UCI-SKU-22197",
    "run_id": "FCRUN-2011-12-v2",
    "target_end": "2011-12-31",
    "target_start": "2011-12-01",
    "training_cutoff": "2011-11-30",
    "training_units": 12118,
    "units": 6059
  },
  "owner_employee_id": "EMP-004",
  "record_links": {
    "forecast_id": "FC-UCI-SKU-22197-2011-12-v2",
    "product_id": "UCI-SKU-22197"
  },
  "status": "current",
  "version": 1
}
---
# Planning note: UCI-SKU-22197 / 2011-12-01 / v2

## Frozen estimate

Forecast `FC-UCI-SKU-22197-2011-12-v2` belongs to run `FCRUN-2011-12-v2`. It estimates **6059 units** for 2011-12-01 through 2011-12-31. Its training cutoff is 2011-11-30; the method averages 2 preceding complete calendar months containing 12118 billed units. Missing months count as zero.

## Reproduce the estimate

Select this product's invoice lines within that lookback and strictly before the target start. Divide their total units by 2 and round half up to one unit. The recorded input fingerprint is `549e0acfafa3eaea4f17151063bc10449c668cc9c342ae0216aa15e62803b05e`. It names the exact ordered input rows, not a hash of later actual results.

## Interpretation

This is a simple teaching forecast with reconstructed historical generation time. It does not model promotions, lead-time uncertainty or the excluded public baskets. Compare another version only for the same product and target period; shorter history can respond differently without being automatically better.

## Evaluation boundary

Use target-period billed units only after generation to calculate actual minus forecast. Percentage error divides by forecast and is undefined for a zero forecast. December is incomplete at the business reference date. Sales targets are explicitly simulated stretch goals; warehouse replenishment is retrospective and must not be cited as forecasting evidence.

Business reference: 2011-12-09. Dataset: acme-company-v8.
