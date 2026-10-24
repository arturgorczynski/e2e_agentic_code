# When an empty tool page led to a false answer

This is a real local sequence from 20 October 2026, using `qwen3-coder:30b`
through Ollama and the superuser **demo profile**. The same prompt was submitted
in three new conversations. The [portable trace extract](../artifacts/customer-cohort-agent-trace-2026-10-20.json)
contains the actual tool arguments, SQL parameters, results and final answers.
It is observable execution evidence, not the model's hidden reasoning.

The question asked for Harbour Home Stores' customer ID, its number of orders
dated in 2026, and the total outstanding across its 2026 invoices. It also
asked the agent to keep the 2011 source history separate. Independent SQL over
`state/company.sqlite` gives customer `SCN-CUST-F909BB661742`, **8** orders,
**5** invoices and **48,750 pence = GBP 487.50** outstanding. The cancelled
and unbilled orders still count as orders.

| Attempt | Recorded tool path | Answer and failure |
| --- | --- | --- |
| Before correction | `list_records(invoices, parent_id=SCN-CUST-F909BB661742)` produced SQL `WHERE order_id=?` with a customer ID and zero rows (events `1718`–`1720`). | The model asserted that no 2026 invoices existed. The empty page only showed that no invoice had an **order ID equal to the customer ID**. |
| After adding a customer invoice filter | `list_records(invoices, customer_id=...)` returned five invoice IDs (event `2145`). A call to `list_records(orders, customer_id=...)` was rejected because that argument was not yet supported (event `2059`). | The model reported five **orders**, copying the invoice count. The source has eight orders. |
| After adding a customer order filter | `list_records(orders, customer_id=...)` returned eight order IDs (event `2533`); `list_records(invoices, customer_id=...)` returned five invoice IDs with their balances (event `2575`). | The model reported eight orders, five invoices and GBP 487.50. This one run agrees with the independent SQL check. |

The model chose the calls and wrote the answers. Python performed the fixed,
parameterized SQL and returned the records. The tool contract now accepts
`customer_id` for orders, invoices and payments. For invoices, a known customer
ID passed as `parent_id` produces an explicit error explaining that
`parent_id` means an order. The system prompt and tool description also direct
the model to `business_summary(report="receivables", customer_id=...,
start_date=..., end_date=...)` for an exact customer balance and to
`customer_orders` or a customer-filtered order page for all orders.

The deterministic regression test is
`tests/test_portal.py::PortalJourneys.test_invoice_lookup_distinguishes_customer_from_order_filter`.
The saved trace proves what happened in these three runs. It does not prove
that every future answer from this model will be correct; compare the answer
with tool results in **Execution** whenever factual accuracy matters.
