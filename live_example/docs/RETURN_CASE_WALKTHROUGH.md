# A return request and the policy version that applied

This fictional 2026 case shows why a document's **current** version and the
version that applied to an **earlier event** can differ. It also shows why a
request inside a return window does not create a physical return or credit.
The source-derived 2010–11 retail archive remains separate.

## Follow the records

| Record | What it says |
| --- | --- |
| Order `SCN-ORD-75F3A546B17E-02` | Lantern Trade Studio placed the order on 22 August 2026. Two one-unit lines share the Winter garland SKU. |
| Shipment `SCN-SHIP-75F3A546B17E-02` | The delivery date is recorded as 24 August 2026. A dispatch date alone would not establish this. |
| Ticket `SCN-TKT-75F3A546B17E` | The buyer's return question was recorded on 26 August; the 21 October review changed the status to `in_progress`. |
| Policy `POL-RETURNS-001:v2` | This version covered 24 August and allowed an ordinary 30-calendar-day request window. v3 began on 20 October. |
| Case file `CASE-75F3A546B17E:v2` | Support's current review records the two-day calculation and asks for the exact affected line and condition evidence. v1 remains available. |
| Invoice `SCN-BILL-75F3A546B17E-02` | GBP 124.00 posted; no payment allocation or credit note was linked when this review was recorded. |

**26 August − 24 August = two calendar days**, within the policy v2 request
window. The policy makes that eligible for review, subject to inspection and
authorization. The ticket records no acceptance of returned goods. The
invoice has no credit note. Neither fact establishes a cash refund.

## Inspect in the portal

1. Select **Superuser → Database → Browse** and open the order, shipment,
   ticket and `ticket_events` rows above. Follow the two order-item IDs
   `SCN-ITEM-75F3A546B17E-003` and `-004`. Each is one unit of the same
   product; the buyer's description does not identify which one is affected.
2. In **Knowledge**, search `CASE-75F3A546B17E` and compare v1 with current
   v2. V1 shows the request as originally reviewed; v2 includes the later
   Support check. Search `POL-RETURNS-001` with **effective date 2026-08-24**
   to obtain v2, then clear or change the date to today to see v3. Open each
   full version to compare its rule and effective interval.
3. In **Database**, inspect `SCN-BILL-75F3A546B17E-02`, its payment
   allocations and credit notes. An empty related set is evidence about the
   recorded finance rows, not evidence that physical goods came back.

The **Employee → `EMP-136`** Support profile can read tickets, ticket events,
Support documents, general policies and commercial orders. It cannot directly
read shipment rows (`operations.read`) or invoice and credit rows
(`finance.read`). Its agent must label those statements as coming from the
case file when answering under that profile. A superuser can verify the
underlying rows separately. Denied calls remain visible in **Execution**.

## Check the agent's source path

Ask the Support agent which policy version applied on 24 August and whether
the request was accepted. Inspect **Execution** for the ticket and both event
rows, the current case document, a search with `effective_on=2026-08-24`,
and a full `read_document` of `POL-RETURNS-001:v2`. A search excerpt is only
a lead; it does not show the whole rule and its exceptions.

The [first recorded run](../artifacts/return-case-employee-before-guidance-2026-10-21.json)
correctly disclosed its missing Operations and Finance access but did not
open the full v2 policy after search. The agent instruction was tightened to
require that read and to check entity permissions before querying. In the
[repeated run](../artifacts/return-case-employee-guided-2026-10-21.json),
`document_read` confirms full reads of both `CASE-75F3A546B17E:v2` and
`POL-RETURNS-001:v2`. The answer labels restricted shipment and invoice
facts as document-reported. The model still attempted two out-of-scope
record calls; the backend denied them and the answer disclosed the limit.
The [final scoped run](../artifacts/return-case-employee-scoped-2026-10-21.json)
also read both full versions. Its model request exposed only seven permitted
commercial and Support entities in each record-tool schema; it made **zero**
denied calls and still labeled shipment and invoice facts as document-reported.
The [schema walkthrough](SCOPED_TOOL_SCHEMA_WALKTHROUGH.md) explains how that
model input was built. These are individual recorded answers, not a guarantee
for future prompts.

## How the revision was installed

The [authored case source](../data/document_sources/revision_r11/support/CASE-75F3A546B17E.md)
was packaged by [the r11 builder](../acme/return_case_release.py) from the
audited r10 corpus. The candidate is in
`artifacts/return-case-release-2026-r11/documents`. The installer staged
the new ticket event and case version together, verified their links, made
a full backup, and preserved case v1. The
[isolated rehearsal](../scripts/verify_return_case_release.py) applies the
candidate to a temporary online database copy, checks a second install is
idempotent, and audits documents and contemporary business links. The
installed local state has 171 document IDs and 456 versions.
