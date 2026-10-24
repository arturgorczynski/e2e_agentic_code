---
{
  "access_scope": "analytics",
  "category": "planning_commentary",
  "document_id": "PLAN-007",
  "effective_from": "2011-12-01",
  "effective_until": null,
  "facts": {
    "id": "FC-UCI-SKU-21977-2011-12-v1",
    "input_sha256": "18635e631be8e0c8da074f4b09aef6c46c0155080d8aa5520bea5e443a2f2688",
    "lookback_months": 3,
    "method_version": 1,
    "product_id": "UCI-SKU-21977",
    "run_id": "FCRUN-2011-12-v1",
    "target_end": "2011-12-31",
    "target_start": "2011-12-01",
    "training_cutoff": "2011-11-30",
    "training_units": 4358,
    "units": 1453
  },
  "owner_employee_id": "EMP-004",
  "record_links": {
    "forecast_id": "FC-UCI-SKU-21977-2011-12-v1",
    "product_id": "UCI-SKU-21977"
  },
  "status": "current",
  "version": 1
}
---
# Planning note: UCI-SKU-21977 / 2011-12-01 / v1

## Frozen estimate

Forecast `FC-UCI-SKU-21977-2011-12-v1` belongs to run `FCRUN-2011-12-v1`. It estimates **1453 units** for 2011-12-01 through 2011-12-31. Its training cutoff is 2011-11-30; the method averages 3 preceding complete calendar months containing 4358 billed units. Missing months count as zero.

## Reproduce the estimate

Select this product's invoice lines within that lookback and strictly before the target start. Divide their total units by 3 and round half up to one unit. The recorded input fingerprint is `18635e631be8e0c8da074f4b09aef6c46c0155080d8aa5520bea5e443a2f2688`. It names the exact ordered input rows, not a hash of later actual results.

## Interpretation

This is a simple teaching forecast with reconstructed historical generation time. It does not model promotions, lead-time uncertainty or the excluded public baskets. Compare another version only for the same product and target period; shorter history can respond differently without being automatically better.

## Evaluation boundary

Use target-period billed units only after generation to calculate actual minus forecast. Percentage error divides by forecast and is undefined for a zero forecast. December is incomplete at the business reference date. Sales targets are explicitly simulated stretch goals; warehouse replenishment is retrospective and must not be cited as forecasting evidence.

Business reference: 2011-12-09. Dataset: acme-company-v8.
