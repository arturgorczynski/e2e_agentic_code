---
{
  "access_scope": "analytics",
  "category": "planning_commentary",
  "document_id": "PLAN-016",
  "effective_from": "2011-12-01",
  "effective_until": null,
  "facts": {
    "id": "FC-UCI-SKU-23166-2011-12-v2",
    "input_sha256": "4d898b7c48c2a568c1dcd5b09c6c7ba17f6223494c9ca2b1bff88d79ac2afbaa",
    "lookback_months": 2,
    "method_version": 2,
    "product_id": "UCI-SKU-23166",
    "run_id": "FCRUN-2011-12-v2",
    "target_end": "2011-12-31",
    "target_start": "2011-12-01",
    "training_cutoff": "2011-11-30",
    "training_units": 747,
    "units": 374
  },
  "owner_employee_id": "EMP-004",
  "record_links": {
    "forecast_id": "FC-UCI-SKU-23166-2011-12-v2",
    "product_id": "UCI-SKU-23166"
  },
  "status": "current",
  "version": 1
}
---
# Planning note: UCI-SKU-23166 / 2011-12-01 / v2

## Frozen estimate

Forecast `FC-UCI-SKU-23166-2011-12-v2` belongs to run `FCRUN-2011-12-v2`. It estimates **374 units** for 2011-12-01 through 2011-12-31. Its training cutoff is 2011-11-30; the method averages 2 preceding complete calendar months containing 747 billed units. Missing months count as zero.

## Reproduce the estimate

Select this product's invoice lines within that lookback and strictly before the target start. Divide their total units by 2 and round half up to one unit. The recorded input fingerprint is `4d898b7c48c2a568c1dcd5b09c6c7ba17f6223494c9ca2b1bff88d79ac2afbaa`. It names the exact ordered input rows, not a hash of later actual results.

## Interpretation

This is a simple teaching forecast with reconstructed historical generation time. It does not model promotions, lead-time uncertainty or the excluded public baskets. Compare another version only for the same product and target period; shorter history can respond differently without being automatically better.

## Evaluation boundary

Use target-period billed units only after generation to calculate actual minus forecast. Percentage error divides by forecast and is undefined for a zero forecast. December is incomplete at the business reference date. Sales targets are explicitly simulated stretch goals; warehouse replenishment is retrospective and must not be cited as forecasting evidence.

Business reference: 2011-12-09. Dataset: acme-company-v8.
