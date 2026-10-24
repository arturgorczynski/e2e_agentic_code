# Supplier order: from two partial receipts to completion

This fictional 2026 case teaches how a supplier order, goods receipts, stock
movements, inventory and a controlled review differ. The original public
retail transactions remain dated 2010–11. The [earlier r10 walkthrough](SPLIT_RECEIPT_WALKTHROUGH.md)
records the order before its final delivery.

## The record chain

| Record | Role in the case |
| --- | --- |
| `SCN-PO-SPLIT-75F3A546B17E` | A request for 15 units from supplier `SUP-03` for `WH-CVT`, placed 26 August 2026. The original expected date, 5 September, remains visible. Its current status is `received`. |
| `SCN-POITEM-SPLIT-75F3A546B17E` | The order line for product `SCN-SKU-75F3A546B17E` and the fixed quantity of 15. |
| `SCN-GR-SPLIT-75F3A546B17E-01`, `-02`, `-03` | Physical arrivals recorded as 5 on 8 September, 4 on 16 September, and 6 on 21 October. The receipt sum is 15. |
| `SCN-STOCK-SPLIT-75F3A546B17E-01`, `-02`, `-03` | Three positive stock entries of +5, +4 and +6, each linked to its own receipt. |
| `SCN-INV-75F3A546B17E` | Warehouse snapshot after completion: 35 on hand, four reserved and 31 available. Other opening and dispatch movements also contribute to this balance. |
| `PROCURE-SPLIT-75F3A546B17E:v1` and `:v2` | Purchasing's earlier open review and later closeout. Documents interpret the rows; they do not themselves move stock. |

The arithmetic is **15 ordered − (5 + 4 + 6 received) = 0 outstanding**.
The order was late against its expected date. Neither the original date nor
the first two receipts was rewritten. Version 1 correctly said six units were
outstanding before the third arrival. Both document versions use 21 October as
their effective calendar date because the teaching register has date precision,
not an intraday timestamp. Use the version and linked receipt IDs to determine
the sequence.

## Walk through the website

1. Choose **Superuser → Database → Browse**. Open `purchase_orders`, filter
   for the order ID, and follow its `purchase_order_items` line.
2. Filter `goods_receipts` by the line ID. Follow each receipt ID to
   `stock_movements`, checking product, warehouse, date and signed quantity.
   **Table connections** shows the foreign-key links between these tables.
3. Open `inventory` row `SCN-INV-75F3A546B17E`. Its 35 on hand is a stock
   balance, while 15 is this one supplier order's cumulative receipt total.
4. Under an Operations employee or Superuser profile, open **Knowledge** and
   search for the supplier review. Read current v2 and historical v1. The
   [authored v2](../data/document_sources/revision_r15/procurement/PROCURE-SPLIT-75F3A546B17E.md)
   explains the closeout and distinguishes supplier stock from customer
   allocation. The document scope is Operations.
5. In **Tools**, run `lookup_record` for the order, `list_records` for its
   line and receipts, and `list_records` for the stock movements. Run
   `list_document_versions` with the exact review ID to see both versions'
   metadata without reading their bodies. Then use `read_document` on each
   version. The agent uses these same bounded read tools.

Ask an Operations employee agent:

> For purchase order `SCN-PO-SPLIT-75F3A546B17E`, list all three goods
> receipts and linked stock movements. Reconcile received and outstanding
> units, current warehouse on-hand and reserved quantities, and explain how
> supplier review v1 differs from current v2. Cite the exact record IDs.

Inspect **Execution** for completed SQL and document-read events. The
[current live trace](../artifacts/split-completion-agent-r15-v5.json) shows
`lookup_record(purchase_orders)` with whole-order totals and the original
scenario provenance, the order-line and three-receipt queries,
one stock-movement lookup for each receipt, the inventory lookup,
`list_document_versions`, and reads of both review versions. Its answer gives
15 received, zero outstanding, 35 on hand and four reserved. It keeps the
same-day version order explicit and leaves the physical-count handoff
conditional.
One correct run does not guarantee every future answer. The first
[r15 trace](../artifacts/split-completion-agent-r15-v1.json) exposed an
incorrect inference that all received units still remained on hand and
placed v1 before 21 October. The general [agent prompt](../acme/agent.py)
now distinguishes a recorded arrival from a current stock balance and warns
that two reviews can share a calendar date. A later
[r15 trace](../artifacts/split-completion-agent-r15-v3.json) confirmed the
version-list tool, but its answer overstated the conditional closeout. The
current prompt keeps recommended actions distinct from completed actions. The older
[r10 trace](../artifacts/split-receipt-r10-agent-2026-10-21.json) is a saved
run against the earlier state; do not treat its six outstanding units as the
current balance.

## Release and verification

The [r15 builder](../acme/split_completion_release.py) starts from the audited
r14 corpus and checks the live r14 order, first two receipts, stock and review.
It adds one six-unit receipt, one matching movement, updates inventory and
changes the order status to `received`. It retains v1 as superseded and adds
v2 as current. The immutable candidate is
`artifacts/split-completion-release-2026-r15/documents`.

The [isolated verifier](../scripts/verify_split_completion_release.py) installs
twice on a copy of r14 state and checks idempotence, 47 business rules, 15,201
untouched source-derived orders, 174 document IDs and 461 versions. The actual
installation made a full backup at
`state/backups/document-release-20261021T185725Z-070091`.
The [post-install audit](../artifacts/modern-link-audit-2026-10-21-r15.json)
reports zero business-rule violations and a valid document corpus. From a
prepared r14 state, run:

```powershell
.\.venv\Scripts\python.exe -m scripts.split_completion_release prepare
.\.venv\Scripts\python.exe -m scripts.verify_split_completion_release
.\.venv\Scripts\python.exe -m scripts.split_completion_release install
```

These commands are for a prepared r14 state. The active state is already r15;
do not run `prepare` against it. If you edit the demo rows in Database Browse,
the walkthrough becomes a dated snapshot; rerun the audit for your changed
state.
