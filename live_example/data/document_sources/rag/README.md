# Authored long-form Acme documents

These six Markdown sources become versioned `data/documents/content/*.v1.md`
files and catalog entries when `acme company build` creates a new baseline.
They are original learning documents for **fictional** Acme Wholesale, not
copied annual reports or scientific papers. Finance reports use numbers
reconciled against the fixed `acme-company-v8` baseline through 2011-12-09;
scientific notes describe methods and cite their primary sources. A methods
note is a proposed study, not an observed Acme result.

| Documents | Access scope | Size in this source set |
|---|---|---|
| `FIN-YTD-2011`, `FIN-RECEIVABLES-2011`, `FIN-CASH-2011` | finance | long, medium, short |
| `SCI-FORECAST-2011` | analytics | long |
| `SCI-STOCK-2011`, `SCI-QUALITY-2011` | operations | medium, short |

The baseline catalog stores file SHA-256, document ID, version, effective date
and scope. Current document search is lexical; the planned RAG index should
chunk these source versions and filter scope before retrieval. Questions about
specific company records still require database evidence.
