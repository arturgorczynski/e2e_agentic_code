# Fulfillment and split consignments

## Purpose and scope

Operations records fulfillment for each order line. The order header provides
the customer and commercial status; a shipment header confirms a dispatch
event. Neither alone proves that every unit was shipped or delivered. This
procedure applies to domestic and export orders and to each separate
consignment on a split order.

## Establish the line position

1. Confirm the order ID and retrieve every order line. Keep its product code,
   ordered quantity and line ID visible during the review.
2. Retrieve all shipments and shipment lines for that order, including further
   result pages. Sum dispatched units by order-line ID and compare them with
   ordered units. Record any missing or excess quantity by product.
3. Match the dispatch movement to its shipment line and warehouse. A stock
   movement without the corresponding shipment evidence must be investigated.

An order is **confirmed** before dispatch, **partial** when at least one unit
has shipped and another remains, and **fulfilled** when all its lines are fully
dispatched. Keep the status-event history alongside the current status so the
sequence remains auditable.

## Delivery and exceptions

Dispatched-on and delivered-on dates describe different events. A dispatch
reference does not confirm carrier delivery. If delivery confirmation is
missing, describe the dispatch and the missing evidence separately. A supplier
purchase-order date is an inbound expectation and must not be quoted as a
customer delivery commitment. Escalate shortages, conflicting line quantities
or carrier exceptions to the responsible team before giving a revised date.

## Handoff record

Record the order, product, line, shipment, movement and carrier references,
the quantities compared, the current evidence date and the owner of the next
action. Operations may propose a split-dispatch response; buying, reservation,
stock adjustment and financial change follow their own authorization paths.
Historical Acme source invoices and fictional fulfillment events must remain
distinguishable in any customer-facing explanation.
