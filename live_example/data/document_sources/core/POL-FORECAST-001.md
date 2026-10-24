# Forecast versions and information cutoff

Every forecast names a run, product, generation timestamp, training cutoff, target period,
method and version. Historical generation timestamps are reconstructed for this learning
company. They are not claims that a real forecasting service ran on those dates.

## Baseline methods

Version 1 uses the mean billed units in the three complete calendar months before the
target month. Version 2 uses two months. Missing months contribute zero. Unit forecasts
are rounded half up. Input rows must have a posting date strictly before the target
start and no later than the recorded training cutoff. The input fingerprint records
the exact invoice lines used. Forecast generation must not read target-period actuals.

Sales targets are separately labeled simulated stretch targets, normally ten percent
above the forecast. They are neither actual outcomes nor additional training evidence.
Monthly replenishment reconstruction is also a separate process; it is not a valid
forward-looking forecast.

## Evaluation

Once a target period is complete, error equals actual units minus forecast units.
Percentage error divides by forecast units; a zero forecast has no defined percentage
error. Cite the run and cutoff with the result. A valid cutoff demonstrates an information
boundary, not forecast quality. Compare versions on the same product and period, and
keep December evaluation provisional while its actual history is incomplete. Never
overwrite an earlier forecast with later observations to make its error smaller.
