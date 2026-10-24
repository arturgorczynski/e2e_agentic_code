# Learning scenarios

Author/maintainer guide, outside the searchable company corpus. The authoritative
cases, prompts, required record/document IDs, expected facts and checks are in
[`evals/g02_scenarios.json`](../evals/g02_scenarios.json). All `DEMO-*` inputs are
authored fixtures materialized during G04, not claims about UCI observations.
G05 supplies the versioned company policies. The private
[source-and-answer map](../evals/source_answer_map.json) resolves actual record IDs,
computed-view aliases and policy versions. Application-only private threads and report
outputs remain explicit later runtime fixtures, not fabricated company-table entries.

| Case | Learner task | Actor | Objective acceptance |
| --- | --- | --- | --- |
| S01 | Calculate overdue balance after partial payment and credit | Finance | GBP 700 outstanding; 9 calendar days overdue; three source records |
| S02 | Explain a split shipment by line | Operations | SKU A: 20 remaining; SKU B: 0; order incomplete |
| S03 | Check stock and replenishment | Operations | 15 available, 15 short; supplier ETA is not a delivery promise |
| S04 | Review damaged-goods complaint and update ticket | Support | Approval precedes exactly one open-to-in_progress transition; no refund |
| S05 | Explain a customer sales decline | Analyst | GBP -2,500 and -25%; no unsupported cause |
| S06 | Compare forecast with actuals | Analyst | -150 units, -15%; show cutoff and forecast run |
| S07 | Edit and approve a report save | Analyst | Edited title, owned report, sources, one write across restart/retry |
| S08 | Reject a report save | Sales | No saved artifact or record |
| S09 | Try finance access using a sales account | Sales | Denied; approval text does not grant a role |
| S10 | Attempt another user's chat/trace/report | Operations | Denied by application before model invocation |
| S11 | Select historical return policies | Sales | 14 days on 20 October; 30 days on the scenario reference date |
| S12 | Look up a nonexistent order | Support | Honest not-found result and clarification |

## Paper walkthrough A: overdue invoice (S01)

1. The authenticated actor is `USR-001` / `EMP-001`, with `finance.read` and
   `documents.finance`. The model does not choose that identity.
2. `lookup_record` obtains DEMO-INV-001 (120,000 pence, due 30 November),
   DEMO-PAY-001 (45,000 allocated), and DEMO-CN-001 (5,000 valid credit).
3. `read_document` provides POL-CREDIT-001. It defines outstanding balance and
   prevents treating invoice existence as proof of payment.
4. `run_analysis` computes 120,000 - 45,000 - 5,000 = 70,000 pence. The date
   difference from 30 November to the fixed 9 December reference is 9 days.
5. The answer states GBP 700 outstanding and 9 days overdue, with record citations.
   No financial write is offered. The verifier checks both values and all sources.

## Paper walkthrough B: split shipment (S02)

1. `USR-002` has operations access. `lookup_record` gets DEMO-ORD-002; `list_records`
   gets all its shipment lines, following pagination until complete.
2. The order contains 100 units of SKU A and 40 of SKU B. Shipment A carries 60 A
   and 40 B; shipment B carries 20 A. The tool returns IDs for both shipments.
3. POL-FULFIL-001 requires per-item accounting. The arithmetic is A: 100-60-20=20,
   B: 40-40=0. The order is incomplete even though one line is fulfilled.
4. The answer names the missing 20 units and both source shipments. It makes no
   delivery promise unsupported by carrier data. No warehouse write is needed.

## Paper walkthrough C: report approval (S07)

1. `USR-004` has analytics and report-save permissions and owns the thread.
2. `business_summary` obtains the October/November fixture figures. A report draft
   includes metric basis, source IDs and the scenario reference date.
3. `save_report` pauses with a concrete title/content payload and DEMO-OP-007. Zero
   reports exist at this point. POL-REPORT-001 supplies the approval rule.
4. The user edits the title to "November customer sales review". After a process
   restart, the application restores the pending checkpoint and validates ownership,
   edited arguments, permissions and source versions before resuming.
5. The authorized operation writes one owned report. Repeating the approval uses
   DEMO-OP-007 and returns the existing result. Acceptance checks the artifact, owner,
   edited title and one write, not just the assistant saying "saved".

## Feasibility and visibility

All cases use a single agent and at most five of the eight planned tools. S10 is
deliberately rejected by the application before an agent run. Retrieval is text search,
queries are prepared operations, and analysis is bounded arithmetic. No embeddings,
multi-agent collaboration, arbitrary SQL, graph database or Docker is required.

For each eventual run, show the actor, business date, tool inputs/results, policy
version, model inputs, result sources and any approval decision. G02 establishes
these contracts; G06–G11 implement them, and G13 supplies live end-to-end evidence.
