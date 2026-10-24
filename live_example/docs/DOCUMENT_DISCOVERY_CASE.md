# Agent walkthrough: finding the right supplier review

This case shows one complete local run against the fictional Acme company.
The model chose tools; Python applied access and date rules, read fixed
Markdown, and queried SQLite. The [compact evidence record](../artifacts/document-discovery-agent-2026-10-21.json)
names the actual thread, run and trace event numbers.

## Why the tool changed

The old `search_documents` implementation split a query into words and ranked
each word independently. `procurement review` matched 87 permitted current
documents in the live catalog. Putting `SCN-PO-79511D9988BA` into the plain
query still matched 24 because pieces such as `SCN` and `PO` appeared elsewhere.
The right review happened to rank first for that ID query, but its position
was not an exact-ID guarantee.

`mentions_record_id` now requires a **complete ID mention in the Markdown
body**. The service first selects documents permitted to the current persona
and effective on the requested date. It then checks the literal ID with
identifier boundaries and ranks the remaining documents by topic words.
This is still mock text retrieval, not a foreign-key lookup or a vector index.

```text
search_documents(
    query="supplier order review",
    mentions_record_id="SCN-PO-79511D9988BA",
)
```

In a direct live call this returned only `PROCURE-79511D9988BA:v3`.
Truncating the ID by one character or appending `-X` returned no documents.
An isolated portal test also checks that a customer cannot retrieve a
support-only incident by supplying its exact customer ID.

## What the agent actually did

In fresh run `run-b661aac9b9614a58bc2542490aae03c2`, the user asked for the
current supplier review of PO `SCN-PO-79511D9988BA` and a quantity check.

| Trace sequence | Boundary | Observed action |
| --- | --- | --- |
| 8640 | Model decision | Native `search_documents` call with the complete PO ID in `mentions_record_id`; also requested the exact PO header. |
| 8658-8659 | Python retrieval and tool result | One permitted current document matched: `PROCURE-79511D9988BA:v3`. |
| 8693-8711 | Model decision and Python document read | The model requested and received the full exact version, rather than relying on the search excerpt. |
| 8722 | SQLite query | One PO line: `SCN-POITEM-79511D9988BA`, quantity 18. |
| 8775 | SQLite query | Exact `goods_receipt_id` filter found the matching stock movement, quantity +6. |
| 8827 | Application run | Completed. The answer stated 18 ordered, 6 received, 12 outstanding, with the receipt, movement and document IDs. |

The receipt row records 6 units against the PO line. The stock movement's
`goods_receipt_id`, product, warehouse and signed quantity agree with that
receipt. The document narrates the purchasing decision; the SQL rows establish
the recorded quantities. Twelve units are still outstanding on the supplier
order and are not on-hand stock.

The trace is evidence of this run, not a promise that every future model run
will choose the same calls. The deterministic service filter and permission
boundary are checked separately by the isolated test suite.
