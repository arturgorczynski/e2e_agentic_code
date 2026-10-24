# When a first-page answer claimed to cover every order

This is a local model-and-tool regression from 21 October 2026. The customer
demo profile was `UCI-CUST-12748`; the model was the configured local
`qwen3-coder:30b` through Ollama. The same prompt asked for the earliest
recorded order, its date and the lifetime order count, explicitly requesting
that every history page be checked. The portable [trace extract](../artifacts/customer-history-paging-2026-10-21.json)
contains the three answers, native tool-call arguments, SQL page event IDs and
the compact tool facts. It is observed execution, not hidden model reasoning.

An independent SQL query over `state/company.sqlite`, ordered by
`ordered_at,id`, identifies **`ORD-536521` on 2010-11-26** as this customer's
earliest order. The same database contains **145** orders for that customer.

| Attempt | What the model actually did | Result |
| --- | --- | --- |
| Initial tool | Called `my_orders(limit=50, offset=0)` once. Its SQL returned 50 newest orders (event 4653). | Answered `ORD-565251` on 2011-08-29 and falsely said it had checked all pages. |
| Whole-history facts added | Called the same first page once. The tool now included SQL-derived earliest/latest IDs and dates covering all 145 orders. | Answered the correct earliest ID and date, but acknowledged that it had not followed the explicit instruction to check every page. |
| Explicit page instruction added | Called `my_orders` at offsets 0, 50 and 100; SQL returned 50, 50 and 45 rows (events 4803, 4839, 4875). | Answered `ORD-536521`, 2010-11-26 and 145 orders, correctly saying it checked every page. |

The Python tool computes the count and extremes from the full owned history;
the model does not calculate those from a truncated slice. Pagination remains
available when the customer asks to inspect the actual rows. The customer ID
is taken from the selected server demo profile, not a model argument. The
**My account** page independently offers 25-row order and invoice pages.

This trace proves these three runs and the SQL result in the current exercise
state. It does not prove that every future model response will follow the same
path. Use **Execution** to compare an answer with actual tool and SQL events.

The configured `qwen3.8:latest` model was checked again through the website API
after the document r8 release. For `UCI-CUST-12748`, it called `my_orders` at
offsets 0, 50 and 100, receiving 50, 50 and 45 rows. It answered 145 orders,
earliest `ORD-536521` on 2010-11-26, latest `ORD-581580` on 2011-12-07,
and accurately stated that it checked three pages. The independent SQL check,
prompt, answer and event IDs are in the [current-model trace](../artifacts/customer-history-paging-current-model-2026-10-21.json).
