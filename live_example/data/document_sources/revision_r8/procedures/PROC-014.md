# Historical-price explanation

## Use and owner

Sales (`DEP-SALES`) owns an explanation of a recorded product price. Price row `PRICE-DEMO-ORD-001:L001` is an authored fixture: its `price_kind` is `fixture` and its `source_row_id` is empty. It demonstrates the register format but is not an observed UCI price. First identify the product and the specific basket or price observation the question concerns.

## Review steps

1. Read `price_history.product_id`, `observed_at`, the exact `raw_unit_price_gbp` string and `price_kind`. Do not replace the stored decimal text with a rounded display value when reviewing provenance.
2. For `price_kind=observed`, retain the linked `source_row_id` and confirm that it belongs to the requested source observation. For a fixture, say that the source-row link is absent; do not invent one.
3. If the question concerns what a customer was billed, follow the order item and posted invoice line. The order item's quantity, raw unit price and `line_pence` support that answer; a different price-history observation does not change the posted line.
4. Compare observations only within their dates and product IDs. Multiple prices on one date may come from different baskets. State the reference period before describing a change.

## Decision and exception

Price history is evidence of observations and fixtures, not a current price list or a promise to honor an earlier amount. If a posted line disagrees with its supporting order record, give both IDs and amounts to Finance or Sales for review. Do not treat a draft correction or a credit note as a cash refund.

## Handoff record

Record reviewer, product, observation date, price-history ID, `price_kind`, source-row ID when present, and any order and invoice lines used for a billed-price explanation. Keep source-derived 2011 observations and authored scenario fixtures visibly separate.
