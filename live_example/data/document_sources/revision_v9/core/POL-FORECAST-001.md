# Forecast runs and information cutoffs

## Purpose and records

Analytics retains each forecast as a dated run linked to a product, target
period, method version, training cutoff and input fingerprint. A forecast is a
planning estimate, not an order, stock receipt or commitment to a customer.
Historical run timestamps in the 2011 reconstruction describe the simulated
company record; they do not claim an operational forecasting service existed.

## Method and input control

For the historical baseline, version 1 averages billed units in the three
complete calendar months before the target month; version 2 uses two months.
Missing months contribute zero and final unit estimates are rounded half up.
The input fingerprint identifies the invoice lines used. Every included line
must have been posted before the target begins and no later than the run's
training cutoff. A later credit, invoice or actual target-month sale cannot be
inserted into an older run. A contemporary fictional run must use its own
contemporary cutoff and visibly simulated provenance.

## Comparison and evaluation

Compare runs only for the same product and target period, and show the method,
lookback window, cutoff and units beside each result. When the target period is
complete, error is actual billed units minus forecast units. Percentage error
divides by forecast units; with a zero-unit forecast it is undefined. State
whether actuals are complete as of the relevant business reference date.
December 2011 historical results are provisional after 9 December.

## Planning handoff

Sales targets are separately labelled simulated stretch targets. They are not
additional training evidence or proof of demand. Replenishment reconstruction
explains historical stock flow and is not a forward forecast. Retain previous
runs; a later rerun gets a new identifier, cutoff and fingerprint. Cite the run
ID and source records whenever a forecast supports an operating decision.
