# Fulfillment and split consignments

Operations tracks fulfillment at order-line level. A shipment header is evidence that
a dispatch occurred, not that every product on an order was shipped. Retrieve every
shipment line for the order, including all pages of a result, before answering whether
the order is complete. Compare each line's ordered quantity with the sum of its shipped
quantity. Report outstanding quantities by product and cite the dispatch references.

## Timing and exceptions

An order is confirmed before any dispatch. It becomes partial when at least one unit
has shipped and at least one remains. It becomes fulfilled only when every line is
fully dispatched. Delivered-on dates are separate from dispatched-on dates. A missing
delivery confirmation must not be turned into a successful delivery claim.

The learning baseline models an initial domestic dispatch one day after posting and
an export dispatch three days after posting. Lines with 48 or more units use a first
consignment of three quarters, rounded down, with the remainder three days later.
Events after the business reference date have not happened yet. These rules reconstruct
an operational story; the original retailer did not supply shipment records.

## What the assistant may promise

A supplier purchase-order ETA is an inbound expectation, not a customer delivery date.
Describe it as an expectation and separate it from carrier evidence. Do not create
reservations, buy replacement stock or change financial records. If quantities disagree,
provide the conflicting line IDs and ask operations to investigate before making a promise.
