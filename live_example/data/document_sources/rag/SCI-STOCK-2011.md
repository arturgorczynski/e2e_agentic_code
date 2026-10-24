# Research methods note: inventory availability and replenishment evidence

## Aim

This authored study protocol asks how a warehouse analyst can tell whether a shortage signal is real, how to compare reorder rules, and how to avoid turning modeled supplier data into observed history. It does not assert that Acme has completed a prospective experiment. Acme Wholesale is fictional. The warehouse locations, suppliers, purchase orders, receipts and dispatch timing in the exercise are modeled extensions around eligible historical retail baskets.

## Measurement before optimization

At a specified timestamp, on-hand quantity describes physical or recorded stock; reservations are commitments against it; available quantity is on-hand minus reservations under the current policy. A negative available quantity requires investigation. It may indicate an oversubscription, delayed posting or an error in the synthetic event sequence. Do not hide it with `max(0, ...)` before explaining. A purchase order is a planned inbound movement, not on-hand stock. A supplier ETA is not proof of arrival. A goods receipt and linked stock movement are stronger evidence for warehouse arrival.

A customer order is also distinct from a shipment. The ordered quantity, shipped quantity and outstanding quantity should be reported per line. Split fulfillment can produce more than one consignment and more than one date. An order marked complete in a current state cannot be used as evidence that every line was already shipped at an earlier historical cutoff. Reconstruct state as of the chosen date when asking a historical question.

## Candidate policy experiment

Define a simple reorder point using expected demand during supplier lead time plus a safety allowance. For a fixed demonstration, compare three policies: a constant minimum stock, a trailing-mean demand rule and a forecast-informed rule. Keep the simulated supplier lead time, review cadence, pack sizes and service target fixed across policies. Record every trigger and order quantity. A method that orders more may reduce shortages while increasing inventory, so one score is insufficient.

Useful measures include units short at dispatch, customer orders affected, number of late consignments, average on-hand units, days of supply and excess units at the end of the test window. If monetary costs are introduced, distinguish documented prices from invented holding or shortage penalties. Treat the latter as scenario parameters and show a sensitivity range. Do not claim profit improvement from a scenario with no verified cost ledger.

## Backtest design

Start each historical test at a date with reconstructable stock, reservations and outstanding purchase orders. Expose only records known at that date. Advance by event time, not by row insertion order. At each decision point, let the candidate policy inspect only its allowed features, then record its proposed action. Apply a deterministic simulated supplier response under the same assumptions for every policy. Compare resulting customer fulfillment. If stock records are retrospectively reconstructed from observed later sales, they are not independent evidence of what the warehouse really held; label the test a simulation.

The dataset's December 2011 period is incomplete at the fixed 9 December cutoff. Do not score a full December service rate. Run a complete-period sensitivity test and a short-window sensitivity test separately. A later exercise state can contain synthetic contemporary orders; these belong to a different scenario clock and must not be mixed into the fixed historical backtest.

## Data quality checks

Verify unit consistency: pieces, cartons and monetary amounts are different types. Validate product ID and supplier ID links. Reconcile purchase-order item quantities with receipts and remaining outstanding quantities. Match each goods receipt to a stock movement when asserting arrival. Check that reservations and shipments cannot precede their source order under the modeled timeline. Identify returns and credit notes separately; returning an item does not automatically make it saleable stock. Any data repair should preserve an audit trail and rerun the experiment with a new input hash.

## Retrieval and access

This note is operations-scoped because it discusses internal suppliers, stock and fulfillment. A general customer user may receive a customer-safe delivery policy, but should not see supplier terms or internal stock positions through a high-scoring snippet. A future RAG index must filter by scope before ranking. Questions like “Has purchase order X arrived?” require a linked goods receipt and movement, not this methods note alone. “What is available stock?” requires current database values and a timestamp; the definition here is only the calculation rule.

## Scientific limits

The method compares decisions under explicit assumptions. It cannot establish a causal effect in the real world without a prospective rollout or independent historical observations. Demand can depend on stock availability: recorded sales may understate demand when products were out of stock. A policy trained only on sales can perpetuate this bias. The simulation should at minimum include a sensitivity run with plausible lost demand and report how the result changes. Excluding inconvenient product families after seeing the result would invalidate a claimed catalog-wide finding.

The main deliverable of a completed study would be a table of policy outputs with source IDs, scenario parameters and uncertainty ranges. Until that exists, this document is a protocol, not a result. A retrieval answer should not transform its “candidate policy” into an Acme decision already taken.
