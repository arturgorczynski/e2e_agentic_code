# Acme Wholesale: live presentation script

This is a 15–20 minute route through the current local website. Acme is a
fictional wholesaler. The prepared retail transactions are historical source
data ending on **2011-12-09**; a separate authored scenario history covers
2026. Company identities, staff, policies and training cases are fictional.
The persona selector is an
intentional scenario control, not a production authentication system. Keep the
server bound to `127.0.0.1`.

## Prepare once

From `live_example/` in PowerShell:

```powershell
uv sync --locked
npm --prefix frontend install
npm --prefix frontend run build
uv run acme setup
uv run acme doctor --inference
uv run acme serve
```

Open <http://127.0.0.1:7860>. The inference probe matters: browsing the catalog
does not prove the model can call tools. If port 7860 already serves the portal,
leave that server running and use `uv run acme doctor --port 7861 --inference`
for a separate diagnostic. Docker is unnecessary. The first model response may
take longer than a database page.

Keep **Execution** available throughout. Compare each answer with its recorded
tool result, SQL or document event. Assistant wording alone is not proof of a
read. Use fictional values for edits.

## Route through the website

| Step | Show and do | Explain |
| --- | --- | --- |
| Home | Search the catalog, page through products and open a product card. | Rows, codes, prices and observation dates come from local SQLite. Fifty-five historical stock codes have individual labeled AI concepts; eight contemporary SKUs share six more. Other cards use category illustrations. |
| Customer identity | In the header choose **Customer** → `DEMO-CUST-001` (Brookside Home & Gift). Open **My account**. | The server binds this ID to the account. The page shows address, lifetime counts and recent records. |
| Customer chat | Ask “What is my current address? Use my profile record.” Inspect **Execution**. | Find the `my_profile` tool result. This exercise copy may contain an audited address edit, so read the current value first. |
| High activity | Switch to `UCI-CUST-12748` (Orchard & Finch Living). Ask for total orders and latest order. | The current bundle has 145 orders. **My account** pages orders and invoices separately, 25 rows at a time, with a lifetime count. |
| Lapsed account | Switch to `UCI-CUST-17850` (Elm & Cole Boutique). Ask when it last ordered and why it stopped. | It has 34 orders and last ordered on 2010-12-01. Records establish the gap, not its cause. |
| Employee | Choose **Employee** → `EMP-002` (logistics). In **Workspace** ask what remains unshipped for `DEMO-ORD-002`. | The authored split-shipment case has 20 units of SKU A outstanding and none of SKU B. Department scopes restrict tools and records. |
| Planning | Switch to analytics employee `EMP-004`. Ask for the October linen-cover desk notebook v2 forecast and Sales target, with exact record and document references. | Inspect the separate 6-unit forecast, 7-unit target and versioned decision document. Follow the [recorded planning walkthrough](PLANNING_AGENT_WALKTHROUGH.md) in **Execution**. |
| Purchasing | Give `EMP-002` Operations access and ask for every receipt of `SCN-PO-SPLIT-75F3A546B17E`, linked stock movements, current outstanding units and both supplier-review versions. | The authored 2026 order moved from 5 + 4 received and six outstanding to a final +6 receipt, 15 received and zero outstanding. Inspect the [completion walkthrough](SPLIT_COMPLETION_WALKTHROUGH.md), then compare the archived [two-receipt run](SPLIT_RECEIPT_WALKTHROUGH.md). |
| Supplier journey | As `EMP-002` or superuser, open **Database → Browse → purchase_orders**, select `SCN-PO-SPLIT-75F3A546B17E`, and scroll below its record fields. Follow a goods receipt, its stock movement, and the order line. | The supplier journey calculates 15 ordered, 15 received, zero outstanding from linked rows and shows all three receipts. It labels this history as an authored contemporary scenario. The displayed warehouse inventory is a current balance, not stock allocated to this purchase order. The seed provenance text describes the earlier two-receipt state; the calculated linked totals are current. |
| Insights | As superuser open **Insights**, filter contemporary orders, open one history, then compare monthly billing, customer cash and the fictional expense ledger. Switch to the 2010–11 cohort. | Order detail follows saved statuses and linked records. The 2026 expense ledger is authored and incomplete; its cash difference is not profit. Historical outflows are unavailable. Follow the [metric definitions](BUSINESS_INSIGHTS.md). |
| Support | Select `EMP-136` and ask which `POL-RETURNS-001` version applied to delivery on 24 August 2026 for `SCN-TKT-75F3A546B17E`. | The effective version was v2. The 26 August request met its review window; no return or credit was authorized. The agent can read the case and policy but must label restricted shipment and invoice facts as document-reported. Follow the [case walkthrough](RETURN_CASE_WALKTHROUGH.md). |
| Finance settlement | Select customer Fable Home Merchants and open invoice `SCN-BILL-83DAA020DE34-01`, then switch to Finance employee `EMP-120` and ask why the October Support case showed GBP 120.00 outstanding while this invoice now shows GBP 0.00. | Two GBP 120.00 receipts were assigned by two allocation records; the second receipt and allocation have different dates. Finance sees the scoped review, while the customer sees its own ledger. Follow the [settlement walkthrough](SETTLEMENT_WALKTHROUGH.md). |
| Knowledge | As employee, search `POL-RETURNS-001`, open v1 and v2, inspect effective dates, download Markdown or use **Print / PDF**. | The corpus is versioned Markdown with visibility and linked records. Search is currently lexical retrieval, not embedding RAG. |
| Scope | Switch to a customer and reopen **Knowledge**. | Only general policies and that customer's linked terms appear. A prompt naming another customer does not grant invoice access. |
| Direct tools | Choose **Superuser** → **Tools**. Inspect a JSON schema and run `lookup_record` or `read_document`. | The Workbench calls the same backend service without the model. Some tools create proposals. |
| Human decision | Run `simulate_delete` for customer `DEMO-CUST-001` with a training reason. Inspect and decide in **Execution**. | Approval records `deleted=false`. The customer still exists in **Database**. This is an application-level decision, not a suspended LangGraph interrupt. |
| Database | As superuser open **Table connections** and follow `customers → addresses`. In **Browse**, add a fictional address, double-click its row to edit it, then inspect **Edit history**. | The graph reflects SQLite foreign keys. Row writes are audited and database constraints apply. Views and document metadata remain read-only; SQL query is bounded and read-only. |
| Memory | In customer chat ask to remember a preference. Start another chat and ask it to check saved notes. | **Execution** should show `memory saved` and `memory recalled`. Checkpoints hold one thread; the persona store spans threads. |

## What lives where

| Location | Purpose |
| --- | --- |
| `data/company/baseline/` | Reproducible generated company bundle. |
| `state/company.sqlite` | Mutable business data. |
| `data/documents/` | Versioned Markdown corpus used by the site and tools. |
| `state/app.sqlite` | Personas, sessions, conversations, proposals and portal edit audit. |
| `state/events.sqlite` | Model, tool, SQL, document and decision events. |
| `state/checkpoints.sqlite` | LangGraph state for each conversation. |
| `state/memory.sqlite` | Explicit preferences keyed to a stable persona. |
| `frontend/src/` and `acme/portal.py` | React/TypeScript frontend and FastAPI backend. |

The installed `acme-company-v8` bundle has **3,832 customers, 3,585 products,
15,213 orders, 200 employees, 35 tables, 3 views, and 148 versions of 147
documents**. These counts may change after a future rebuild. `acme company
verify` checks the baseline against its catalog.

## Presenter boundaries

- Some original product descriptions remain terse uppercase retail labels.
  Featured product images are labeled AI concepts; the rest are category
  illustrations. None is verified stock photography.
- The persona switcher deliberately enables role changes in this local demo.
  It is not production security. Keep the server on localhost and use fake data.
- `save_report` and `update_ticket` create real pending proposals;
  `simulate_delete` never deletes a row or file.
- This application's approval workflow differs from LangChain's native
  `HumanInTheLoopMiddleware` and `interrupt()` pattern.
- Markdown is the document source. The browser print stylesheet produces a
  PDF through **Print / PDF**; there is no static PDF archive.

Continue with the [portal guide](PORTAL_GUIDE.md),
[agent architecture](AGENT_ARCHITECTURE.md),
[data quality and provenance](DATA_QUALITY.md), [bot scenarios](BOT_SCENARIOS.md)
and [RAG roadmap](RAG_ROADMAP.md).
