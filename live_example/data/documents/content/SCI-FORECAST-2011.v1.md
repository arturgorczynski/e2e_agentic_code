---
{
  "access_scope": "analytics",
  "category": "research_notes",
  "document_id": "SCI-FORECAST-2011",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "provenance": "authored_acme_learning_document"
  },
  "owner_employee_id": "EMP-004",
  "record_links": {
    "department_id": "DEP-ANALYTICS"
  },
  "status": "current",
  "version": 1
}
---
# Research methods note: evaluating wholesale demand forecasts

## Research question and provenance

How should Acme compare forecasts for products with different sales volumes when some series contain many zero-demand periods? This is an **authored methods note**, not a claim that Acme has run a new scientific experiment. The company, its forecast runs and its operations are fictional. The note uses the fixed 2011 exercise calendar and draws methodological context from Hyndman and Koehler, *Another look at measures of forecast accuracy* (2006), https://doi.org/10.1016/j.ijforecast.2006.03.001, and Hyndman, *Another look at forecast-accuracy metrics for intermittent demand* (2006), https://robjhyndman.com/publications/another-look-at-measures-of-forecast-accuracy-for-intermittent-demand/. These references are summarized in original language; their articles are not reproduced here.

## Observation unit

The natural unit is a product and target period, with a forecast frozen before that period begins. A run must retain a product ID, run ID, target start and end, forecast units, training cutoff, input hash and method label. “Actual” should be computed from eligible billed units in the target period using the same product definition. It must not include future observations in training or evaluation features. A forecast for a product that did not exist during the training window needs an explicit cold-start policy rather than a fabricated history.

In the Acme dataset, the fixed business reference is 9 December 2011. November is complete; December is incomplete. An evaluation that treats December 1–9 as a full month would bias error and method ranking. Backtests need windows whose actual period is complete at the evaluation cutoff. The source retail transactions can support a measured billed-unit series, but the supplier, lead-time and replenishment events are fictional. Do not describe an inventory simulation as an observed retailer outcome.

## Baselines before complex models

For each eligible series, calculate a simple baseline: previous complete period, trailing mean over a documented number of complete periods, or a seasonal equivalent only when there is enough history. Keep zero-demand periods rather than dropping them merely because percentages are inconvenient. Use the same target windows and source eligibility for every candidate method. A more complex method should beat the baseline on held-out periods that were not used to tune it. One attractive single product example is insufficient evidence for deployment across a mixed catalog.

Chronological validation matters more than random shuffling. Choose a series of rolling cutoffs. At each cutoff, freeze all features, fit only on history available then, predict the next full period, and record actuals only after that period closes. If a feature such as a return or stockout is only entered later, either exclude it from the historical prediction input or reconstruct when it became known. Report the number of products and windows evaluated; a percentage without the denominator is not interpretable.

## Error measures and their failure modes

Signed error is actual minus forecast. Positive means underprediction; negative means overprediction. Absolute error measures magnitude but does not indicate direction. Mean absolute error is in units and is easy to explain for one scale. Percentage error divides by a forecast or actual value depending on the contract, and may be undefined at zero. Never silently substitute zero for an undefined percentage. Aggregating percentage errors across sparse series can allow tiny denominators to dominate the result.

Hyndman and Koehler propose mean absolute scaled error (MASE) for comparisons across different series, using a training-sample naive forecast error as the scaling denominator. The practical lesson for Acme is that the denominator and training window must be saved with the score. When a series is constant or the denominator is zero, the metric is undefined under that construction and needs an explicit fallback or exclusion rule. A scaled metric is not automatically “business cost”: a five-unit shortage on a critical product can matter more than a larger harmless surplus elsewhere.

The 2006 intermittent-demand note warns that common percentage-based measures can be infinite or undefined. This supports checking zero and near-zero cases before choosing an error measure. It does not establish that one forecasting model will perform best for Acme. That claim would require a local backtest with the company's target periods and decision costs.

## Decision-oriented evaluation

A forecast becomes useful when connected to a replenishment decision. Record lead time, review frequency, carton size, minimum order quantity and service target separately from the unit forecast. The fixed dataset's lead-time and supplier values are authored, so simulated reorder costs are scenario results. Compare candidate methods under the **same** decision policy to isolate forecast effects. Then vary the policy itself in a separate experiment. Otherwise, a better replenishment outcome might be caused by a different ordering rule rather than forecast accuracy.

Separate asymmetric errors. Underprediction may create a shortage or late delivery; overprediction may create holding cost or obsolescence. The unit error alone cannot price these outcomes. If cost data are unavailable, report physical proxies such as missed units, excess units, and service-level violations. Do not invent monetary savings to make a model appear successful.

## Reproducible study design

1. Select a complete calendar range and identify eligible product IDs from the source mapping.
2. Freeze source and forecast input hashes; retain dataset version and training cutoff per run.
3. Define baseline and candidate methods before examining the final holdout.
4. Backtest over several chronological cutoffs, logging forecast, actual, signed error, absolute error and any undefined metric state.
5. Summarize both macro results across products and volume-weighted results. Explain how zero-demand and newly introduced products were handled.
6. Review error by product family, history length and target month. Investigate outliers against source records rather than deleting them because they spoil an average.
7. If translating errors into replenishment decisions, state every simulated business assumption and run sensitivity checks.

The protocol is intentionally longer than the current Acme planning notes. A future RAG index should retrieve a narrow section such as “zero denominator” or “training cutoff”, not paste the entire note into a model prompt. The answer should cite both this internal document version and the relevant forecast run or SQL rows when claiming a company result.

## Limitations and falsification

A result based on one fixed November cannot establish general performance over a year. A product may have returns or corrections after the observation date. Grouping by category can hide poor performance for rare but important stock codes. A selected metric can change the ranking of methods; this is a reason to disclose the metric, not to select whichever looks flattering. A reproducible study should include a failure example: a naive model that appears excellent by percentage score after all zero-demand periods are dropped. Re-run it with those periods restored and examine the difference. If the claim no longer holds, report that openly.

## Questions for retrieval evaluation

“Why is percentage error missing for a zero forecast?” should retrieve the denominator discussion. “What was Acme's best model?” cannot be answered by this methods note; it needs a named completed backtest. “Can December 2011 be a full target period?” should retrieve the cutoff limitation. “Did the paper prove Acme saves money?” should be answered no: the references concern forecast measures, while Acme's replenishment economics remain simulated and untested.

Business reference: 2011-12-09. Dataset: acme-company-v8.
