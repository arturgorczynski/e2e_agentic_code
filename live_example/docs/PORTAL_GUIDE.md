# Acme Wholesale portal guide

## What this application is

Acme Wholesale is a fictional local company. The website combines the existing
`state/company.sqlite` database, the installed versioned Markdown corpus in
`state/documents`, the Acme Python tools, and the LangChain agent runtime. It is a
learning and presentation environment. The visible persona switcher is designed
for scenario testing; it is not a production login or security system. Keep the
default server on `127.0.0.1`.

The immutable v8 data bundle contains 3,832 customers, 3,585 products, 15,213
orders, 200 employees, 35 company tables, 3 SQLite views and 148 document
versions across 147 document IDs. Source transactions came from the prepared
public data; the named company, staff, policies, workflows and scenario records
are authored fiction. `data/company/baseline/` is the fixed generated bundle.
`data/documents/` is its original document corpus. The current local exercise
has an additional, fictional 2026 customer history and an installed 2026 document
revision with 174 IDs and 461 versions. The active register and Markdown files
are in `state/company.sqlite` and `state/documents/`. `state/app.sqlite` holds
personas, conversations, proposals, reports and the `portal_edits` audit.
`state/events.sqlite` holds the execution trace. Do not delete `state/` if you
want to keep your exercises.
`state/checkpoints.sqlite` holds conversation state; `state/memory.sqlite`
holds explicitly saved persona preferences across conversations. See
[agent architecture](AGENT_ARCHITECTURE.md) for their different lifetimes.

## Start

In PowerShell, from `live_example`:

```powershell
uv sync --locked
npm --prefix frontend install
npm --prefix frontend run build
uv run acme setup
uv run acme doctor
uv run acme serve
```

Open <http://127.0.0.1:7860>. The backend serves the built React app and its
`/api` routes from one local process. There is no Docker dependency on this
path. A configured model provider is needed for chat, not for browsing the
company data. Use `uv run acme doctor --inference` to test actual model/tool
capability. First model responses can take longer than database pages.

For frontend development, run `uv run acme serve` in one terminal and
`npm --prefix frontend run dev` in another. Open <http://127.0.0.1:5173>.
Vite proxies `/api` to port 7860. After editing the frontend, run
`npm --prefix frontend run build` again to update the single-server website.

## Walkthrough: customer

1. Open **Home**. The catalog searches real local product rows and shows the
   latest recorded price. Use its search field and pagination. Click a product
   card to inspect its exact code, category, latest observed price and
   observation date. Fifty-five featured historical items and eight contemporary
   scenario SKUs have explicitly labeled [AI concept images](IMAGE_ASSETS.md);
   the remaining images illustrate their
   category. None is verified stock photography.
2. Click the persona control in the top right, choose **Customer**, search
   `DEMO-CUST-001`, and select Brookside Home & Gift.
   Use the order-count range, order-status filter and sort control to find
   high-volume, low-volume, cancelled or high-value customer histories. The
   History filter selects the 2010–11 historical archive or contemporary fictional accounts.
   Eight contemporary sample customers cover January to October 2026. **Create
   scenario customer** adds a customer, address and your chosen number of
   orders, line items and total value. It also creates a fictional account
   contact and a readable address. Specify cancelled and fulfilled counts;
   fulfilled orders create linked invoices, shipments and stock movements.
   Choose a fully paid, partly paid or unpaid invoice history. New scenario
   orders are dated relative to today and marked as fictional contemporary
   records; the 2010–11 source transactions stay unchanged. The optional description box parses simple phrases such as
   `5 orders, 2 items per order, £250 total, 1 cancelled, 3 fulfilled` into
   the visible fields for review before creation.
3. Open **My account**. Check the customer ID, address, Acme account manager,
   separately listed customer contacts, orders and invoices. Use the separate
   order and invoice page controls to browse the full account history. Click
   `DEMO-ORD-001` to see its product lines. Click an invoice to see its original
   amount, current outstanding balance and linked payment allocations or credit
   notes. The invoice ledger has its own page control. A credit note reduces the
   balance but does not by itself prove a cash refund. Changing
   persona changes the backend account and automatically reloads the open page,
   including this customer's profile and order list.
4. Ask the assistant, for example, “What is my current address? Use your account
   tool and cite the record.” The customer tools obtain the selected customer ID
   from the server session. The prompt cannot supply another ID to those tools.
5. Open **Knowledge**. Customers see general policies and only
   customer terms linked to their own customer ID. Each of the eight contemporary
   seed customers has an individual account-terms record covering its fictional
   order history, named contact, payment term and service route. Choose a document to read Markdown
   and its version/effective dates. The page starts with versions effective today;
   change **Effective on** to inspect another date, or click **All versions** to
   inspect every version, including earlier reviews from the same day.
   The separate status filter distinguishes the latest register version from superseded
   versions; a latest version may have a future effective date. **Markdown** downloads the source;
   **Print / PDF** uses the browser's print dialog and print stylesheet.
   Search titles and IDs, or search words in the full document text. Filter by
   category, topic tag, visibility scope, status, owner and linked record type.
   Tags are derived from the document title, category and explicit record links,
   so a passing mention in standard body instructions does not tag the document;
   they are portal search metadata rather than fields in the fixed source catalog.

## Walkthrough: employee

1. In the persona control choose **Employee** and search an employee ID, for
   example `EMP-001` (finance), `EMP-002` (logistics), or `EMP-005` (support).
   Narrow the list by current department, location, role and minimum number of
   managed customers; sort by customer count, name or hire date. The selector
   displays each employee's assignment and actual customer count.
2. Open **Workspace** for recent orders, company counts and the internal agent.
   These are company metrics and customer orders, not the employee's purchases.
   **My account** is the selected customer's private account view. Workspace's
   company order feed is a fixed, recent sample; employee permissions still
   govern database, documents, tools and agent actions.
   Employee permissions follow the selected employee's current department.
   The finance example can inspect invoices; logistics can inspect shipment
   and stock records. The agent's tool calls still enforce those scopes.
3. Open **Knowledge** to inspect documents allowed by the employee's scopes.
   The library shows category, owner, linked records, effective date and
   version. An exact version is selected when opened.
4. Open **Tools**. Select a tool, inspect its model-facing JSON schema and
   example, fill in the generated form or switch to JSON, and click **Run tool**.
   The purpose stays visible and the raw request and response appear below. The page displays
   the actual returned record envelope, facts, errors and source references.
   Some tools create pending proposals that require a separate approval in
   **Execution**. A proposal is not a completed business change.
   `remember_note` saves an explicitly requested preference for this persona;
   `recall_notes` can retrieve it in a different conversation.

## Walkthrough: superuser and database editing

1. Select **Superuser** in the persona control. Search and sort company or
   department focuses, or show only departments with managed customers.
   Selecting a department narrows the Workspace order feed to customers whose
   current account manager works there. Counts and superuser permissions remain
   company-wide. The database explorer now
   lists all 35 tables and 3 views. Select a table, search text fields, page
   through rows and click a row for details. Related ID fields offer links.
   Open an `orders` row to see its **Order journey**: linked customer, order
   lines, invoice balance, status changes, dispatch, delivery, payment
   allocations, credits, and service events. Each event links back to its
   database record. The labels distinguish observed source invoice dates and
   prices from reconstructed orders, modeled logistics and settlement, and
   authored service scenarios. This view is available to Superuser because it
   combines records from several employee scopes.
   For contemporary purchasing, browse `purchase_orders`, open a row, and follow
   its item to the product and supplier. Four fictional supplier orders show a
   complete receipt, a short receipt, an overdue order without a receipt, and
   a split delivery completed by a third receipt on 21 October 2026. Its
   earlier two-receipt review remains available as a superseded version.
   The receipt and stock movement records reconcile with the product inventory;
   the original 2010–11 source transactions remain dated and identified separately.
   For October 2026 planning, browse `forecast_runs`, `forecasts` and
   `sales_targets`. Two fictional products each have a three-month and a
   two-month forecast made from invoice lines billed before 1 October. The
   Cedar & Stone two-month input is empty: its forecast is zero and the
   two-unit target is labelled as a planner override.
   Open **Knowledge** as a purchasing employee to read the four supplier
   order reviews; an analytics employee can read four forecast decision records.
   These documents cite the corresponding table IDs and retain their own
   issue date and document version.
2. Open **Table connections**. Choose `customers` to see a directed graph of incoming links from
   orders, payments and contacts, and outgoing links to addresses and account
   managers. Click a linked table to focus it, or **Browse records** to inspect
   its rows. The map is generated from the SQLite foreign-key definitions and
   respects the active employee scope.
3. In **Browse**, choose an editable table and click **Add row**. The form shows
   its columns and required fields; ID and provenance can be filled
   automatically. Date fields use date pickers, and common status/currency
   values appear as suggestions. Monetary `*_pence` fields are labeled in GBP
   pence. For foreign keys, use **Find** to search existing records.
   A successful save writes the new row to `state/company.sqlite` and records
   before/after data in `state/app.sqlite` in the same transaction. The new ID
   appears in the search box so you can inspect it immediately.
   For `company_expenses`, select a suggested category and leave ID, currency
   and provenance blank for their demo defaults. Selecting a purchase order
   fills its supplier; a mismatch is rejected by SQLite.
4. Double-click a cell, a row, or click once and choose **Edit row**. Change its fields
   and save. IDs stay fixed; database constraints are checked and a stale form
   cannot overwrite another edit. Editing a shared address row changes every
   customer or supplier linked to it, so use the dedicated customer address
   form when the change belongs to only one customer. You can delete an
   unreferenced row after a second confirmation. The editor shows incoming
   foreign-key links and their counts first; click a linked table to browse the
   referencing rows. Deletion stays disabled while links exist. Calculated SQL views and
   document metadata tables are read-only; documents live in the Markdown
   corpus and need their own versioned workflow.
5. Search the `customers` table for `DEMO-CUST-001`, open its row, and edit the
   address. The form requires a meaningful address and country. Saving creates
   a new address record, relinks this customer, and stores before/after values
   in the `portal_edits` audit table in one transaction. This avoids silently
   changing any other customer or supplier that shared the old address.
6. Open **Edit history** to see the recorded change. Switch back to that
   customer and verify the new address in **My account**. Ask the customer
   assistant for its current address; its `my_profile` tool reads the changed
   SQLite record.
7. Use **SQL query** for bounded read-only `SELECT`, `WITH`, or `EXPLAIN`
   exploration. Results are capped at 200 rows. The SQL console is available
   to the superuser; employee table browsing follows department scopes.
8. Open **Check links** as a superuser and run the read-only audit after editing
   linked 2026 records. It reports the contemporary cohort size and all 50
   business-history checks. Failed rules appear first; **Show all checks**
   reveals the passing rules too. A passing result confirms internal
   consistency for this snapshot, not that the fictional events happened.
9. Use **Reset data** to preview exercise differences between the mutable company
   database and the installed, verified baseline. Installed document revisions
   and the contemporary ticket histories they document are retained together
   and shown separately from resettable changes. Tick other changes to preserve,
   then reset the rest. Preserving a generated scenario customer retains its
   linked business history. A complete database backup is written under
   `state/backups/` before replacement. Conversations remain in Execution;
   reverted row-edit audit entries are removed from the active audit. Preview
   again if the company database changed since your preview.

The superuser can also edit a customer contact's name and responsibility with
the same audit trail. The generic row editor is a local demo data tool; it does
not run the agent approval workflow or enforce business rules beyond SQLite
constraints. The agent's `update_ticket` and
`save_report` tools create proposals
that remain subject to the existing approval workflow.
`simulate_delete` is a superuser-only training proposal for a record or exact
document version. Even after approval it records `deleted=false` and leaves
the database row and Markdown file intact. Inspect its decision in **Execution**.

## Trace a real agent answer

Open **Execution** after chatting. Internal personas see every saved conversation;
customers see their own. Filter by user, topic, message count or tool used, and
use **Clear filters** to show the complete count. Pick a conversation and compare the
**AGENT CLAIM** with recorded **model request**, **tool attempt**, **SQL**,
**tool result** and **approval** events. Expand an event to read its stored
payload. All loaded event kinds are visible by default; **Load more events**
continues through long runs. A sentence written
by the model is not proof of execution; the matching tool/SQL event is.
Conversation and event history persist in SQLite across browser refreshes and
server restarts. The direct tool workbench uses a separate tools workspace, so
its calls are inspectable without mixing them into a customer chat.

## Code map

- `frontend/src/`: React views, typed API client and responsive styles.
- `acme/portal.py`: FastAPI routes and static frontend serving.
- `acme/portal_data.py`: SQLite browsing, customer views, bounded SQL and
  transactional address edits.
- `acme/database_editor.py`: schema metadata, visible foreign-key graph,
  audited row insertion and updates with conflict detection.
- `acme/portal_identity.py`: local demo personas and employee scope mapping.
- `acme/customer_tools.py`: server-bound customer agent records.
  `my_invoices` gives the customer agent a bounded page of its own invoices,
  plus exact lifetime invoice count, billed total and outstanding balance.
  It joins invoices to orders using the selected server-side customer identity;
  an invoice balance includes payment allocations and credits but does not
  identify individual payments.
  `my_invoice` reads one selected customer's invoice and pages through its
  linked settlement entries. It reports whether the customer-visible entries
  reconcile to the stored outstanding balance. The website has a separate
  read-only invoice detail route; it does not execute the agent tool. Follow
  one real run in the [customer invoice walkthrough](CUSTOMER_INVOICE_AGENT_WALKTHROUGH.md).
- `acme/agent.py`, `acme/runtime.py`, `acme/ui_service.py`: existing agent,
  durable queue, history and traces, extended with a customer tool set.
- `acme/company_tools.py`: shared document access and direct company tools.
- `acme/memory_tools.py`: persistent, persona-scoped preference notes.

The Gradio code remains as historical teaching source. The normal `serve.py`
entry point uses the React/FastAPI portal.
