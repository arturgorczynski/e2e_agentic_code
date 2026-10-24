# Retrieval and future RAG design

## Current system (verified in the source)

Acme currently has a **versioned Markdown corpus**, not an embedding index. The
catalog is `data/documents/catalog.json`; bodies are under
`data/documents/content/`. `acme/company_tools.py` filters documents by the
selected application persona before reading or ranking them, checks every
file's SHA-256 against the catalog, and searches permitted document text with a
bounded lexical score. `read_document` returns a requested version and a
bounded character slice. `state/company.sqlite` contains document metadata and
record links, but the current retrieval tool reads the fixed catalog and files.

This distinction matters in a demonstration: a search result is a matched
Markdown excerpt; it is not semantic vector retrieval. A model answer should
cite a document ID **and version**, plus record IDs for business facts. The
Execution view records retrieval and document-read events, which are better
evidence than the model's prose alone.

The fixed baseline now includes three finance reports and three scientific
methods notes of varied lengths from `data/document_sources/rag/`. They have
catalog hashes, access scopes and SQLite document metadata like the other
source documents. The methods notes cite external research; they do not claim
completed Acme experiments. The finance reports distinguish fixed historical
invoice evidence from the modeled payment history.

Customer access currently covers general policies and the selected customer's
own terms. Product guides contain supplier and stock details and remain
operations-scoped. A future customer product guide must be a separately
authored, customer-safe document; changing only its UI label would leak
operational information.

## Proposed local retrieval index

Keep SQLite and the existing Markdown authoring path. Add a derived
`state/rag.sqlite` index built from **validated catalog versions**. The index
can be rebuilt without altering the source corpus or the mutable company DB.
FTS5 is the first retrieval stage; embeddings are optional after a measured
lexical baseline, and must not be required for local startup.

Each chunk should store:

| Field | Purpose |
| --- | --- |
| `document_id`, `version`, `sha256` | Stable source identity and tamper check |
| `heading_path`, `ordinal`, `body_start`, `body_end` | Reconstruct a precise passage |
| `effective_from`, `effective_until`, `status` | Answer historical questions correctly |
| `access_scope`, `category`, `record_links` | Filter before ranking |
| `text`, `content_hash` | Searchable text and idempotent rebuilds |

Chunk at Markdown heading boundaries first, then split long sections with a
small overlap. Keep tables and numbered procedures intact where possible.
Derive a chunk key from `document_id:vN:heading_path:ordinal:content_hash`.
Index only the content allowlist; never ingest `evals/`, `artifacts/`, source
maps, private threads, or local filesystem workspaces.

## Query contract

1. Resolve the actor and selected persona on the server. A customer ID in the
   prompt does not change the bound customer.
2. Filter candidate documents by category, scope, linked customer, and
   effective date **before** any text/embedding search. Keep the same rule for
   search, direct read, snippets, exports, and future citations.
3. Rank only permitted chunks. Return a bounded number of passages and bytes;
   expose a continuation cursor for longer result sets.
4. Return `document_id`, version, heading, effective interval, file hash,
   passage range, score and linked record IDs with each result.
5. Verify a cited passage still belongs to the same catalog version before
   rendering or supplying it to an agent. If it changed, fail closed and
   require an index rebuild.
6. Tell the agent when no permitted evidence matched. Do not silently broaden
   scope or fall back to a newer policy for a historical query.

## Evaluation set before adding embeddings

Use existing `evals/g02_scenarios.json` and add focused retrieval cases:

- `POL-RETURNS-001:v1` for 20 October 2011 and `v2` for the fixed 9 December
  reference date;
- a customer cannot retrieve another customer's `TERMS-*` or any operations
  product guide, even by exact title, direct ID or citation;
- finance and warehouse employees see different internal passages;
- partial shipment and credit answers link the governing policy to exact SQL
  records, with no invented explanation;
- a changed source hash invalidates a stale index result;
- document searches without matches return an honest empty result.

Measure answer correctness, citation precision, retrieval recall, median and
tail latency, and leakage separately. Add embeddings only if they improve
measured cases enough to justify their local model/index cost. Avoid mixing
the fixed 2011 business clock with today's date in prompts or metadata.

## Implementation boundaries

The index is derived state. The source documents, catalog hashes and company
records remain authoritative. UI filters are explanatory only; authorization
belongs in the backend. Use the current Python model factory and root `.env`.
The normal local setup must continue to work without Docker. Review document
visibility and current data provenance in
[`company_documents.md`](company_documents.md) and
[`source_mapping.md`](source_mapping.md) before an index migration.

References: [LangChain long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)
distinguishes thread checkpoints from cross-thread stores; it does not turn
this lexical document search into RAG by itself.
