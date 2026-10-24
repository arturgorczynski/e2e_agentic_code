# Company document collection

This page describes the **immutable v8 baseline**. The current local exercise
uses the installed `acme-documents-2026-r15` corpus in `state/documents`:
174 document IDs and 461 versions, including later hand-authored case reviews.
See the [realism audit](REALISM_AUDIT.md) and
[settlement walkthrough](SETTLEMENT_WALKTHROUGH.md) and
[supplier completion](SPLIT_COMPLETION_WALKTHROUGH.md) for those additive
fictional 2026 revisions.

The full dataset contains **147 distinct documents and 148 Markdown versions**, all
in English and generated without model calls. The source of nine core policies is
hand-authored Markdown. Other documents combine reviewed category-specific instructions
with real facts queried from the same company database.

| Category | Documents | Concrete use |
| --- | ---: | --- |
| Policies | 9 | Receivables, fulfillment, stock, complaints, metrics, forecasts, reports, returns and access |
| Procedures | 18 | Distinct operational workflows, each with a starting record, decision and handoff |
| Product guides | 40 | Frequently ordered products, their purchasing history, modeled availability, handling and source-price interpretation |
| Customer terms | 25 | Active accounts, assigned terms, country assumptions, purchasing coverage and service boundaries |
| Department instructions | 10 | Each actual department's headcount, remit, handoffs and information boundaries |
| Incident notes | 25 | Linked service cases, event timelines, present state and evidence still required |
| Planning commentary | 20 | Product-specific frozen forecasts, cutoffs, methods, input fingerprints and evaluation limits |

Documents are not made substantial by repeating a minimum word count. Each template
category has a different business purpose, and each generated entity document supplies
record-specific evidence. Validation checks those facts against SQL and checks that the
prose actually includes its asserted quantities and states. The readable core policies
define the operative rules rather than hiding all useful content in metadata.

## Metadata and locations

The baseline retrieval allowlist is **`data/documents/content/`**. When an
audited revision is installed, the portal and agent read
**`state/documents/content/`** instead. Each Markdown file begins
with JSON-formatted YAML-compatible front matter between `---` lines:

- stable document ID and version;
- owner employee, category and access scope;
- effective start/end dates and current/superseded state;
- real company-record links and structured factual values.

The catalog and database contain matching hashes and version metadata. Database links
use actual foreign keys to products, customers, departments, tickets, forecasts and
other supported records. They cannot silently point at nonexistent entities.

The portal's **Knowledge** list first limits the catalog to documents allowed for
the selected demo persona. Title/ID, category, tag, visibility, status, owner,
linked-record type and effective-date filters then use catalog metadata. A
keyword-in-text search reads and verifies only the remaining candidate Markdown
bodies. Opening or downloading one version verifies its SHA-256 hash before
returning its content. Topic tags are derived from the document title, category
and record links; they are search facets, not claims that every occurrence of a
word in the body has been manually classified.

The authoring inputs are `data/document_sources/core/` and
`acme/company_documents.py`. Rebuilding with the same data/rules produces fixed Markdown
artifacts. Learners never need a document-generation model at startup. Source-and-answer
maps, expected values, application fixtures and validation reports remain outside the
retrieval allowlist. PDF/DOCX ingestion is a later exercise.

## Scope and historical context

Policies have their business scope. Product guides include stock figures and supplier
assignments, so they are **operations-only**. General customer terms deliberately omit
payment allocations and outstanding balances. Service notes are support-scoped and
planning notes analytics-scoped. The active local portal filters scope before
ranking or returning excerpts using the selected demo persona. That selector
is a scenario control, not production authentication.

Return policy `POL-RETURNS-001:v1` grants a fictional 14-day window through 2011-10-31.
It remains marked superseded. Version 2 grants 30 days from 2011-11-01. An October
question resolves to v1; a question about the reference date resolves to v2. This is
an authored commercial teaching rule, not advice about real consumer law.

Generated account, product and department snapshots become effective at the business
reference date, so they do not pretend their final snapshot was known earlier. Incident
notes become effective at their latest included event. Planning notes use their target
start and discuss only frozen inputs plus evaluation rules, without later actual values.

## Review and extension

Representative review should include one document from every category, both historical
return versions, a partial/open service case, an export account and both forecast methods.
Check readability, arithmetic, references, permissions and the distinction between public
observations and simulated extensions. [Validation evidence](G04_G05_VALIDATION.md)
records this release's actual review.

When extending the corpus, add a business question that the new document answers and
link it to the relevant records. Repeated prose with substituted IDs is insufficient
unless the record-specific evidence makes each entry independently useful. Keep stable
IDs and create another version for changed operative policy, retaining its prior interval.
