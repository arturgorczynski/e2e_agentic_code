# A current Finance instruction in a live agent run

On 21 October 2026, the local employee `EMP-001` asked the company agent to
reconcile invoice `SCN-BILL-A12C4F10C352-02` and use the **current** Finance
operating instruction before discussing collection. The portable
[comparison extract](../artifacts/finance-agent-model-comparison-2026-10-21.json)
contains the exact questions, final answers, native tool arguments, SQL event
labels, document reads and run times. It summarizes observable events from
`state/events.sqlite`; it does not expose model reasoning.

Independent SQL in the active exercise state gives an original invoice total
of **18,000 pence**, a **1,000-pence credit note**, **no payment allocation**
and **17,000 pence outstanding**. The current instruction is `DEPT-002` v4,
effective 2026-10-21. Its collection guidance calls for a balance review,
payment/credit reconciliation, a business reference date and escalation of
unmatched receipts, duplicate allocations or negative balances. A credit note
does not establish a cash refund.

| Run | Actual path | Outcome |
| --- | --- | --- |
| `qwen3-coder:30b`, full Finance question | Two ordinary-text `<function=lookup_record>` blocks, no native tool call or SQL. The guard failed the run (events 4932, 4943, 4949). | No unsupported invoice answer was returned. |
| `qwen3-coder:30b`, short invoice question | First response was textual markup; retry produced a native `lookup_record`, followed by invoice SQL. | Correct GBP 180.00 total and GBP 170.00 outstanding, but this did not exercise the Finance document. |
| `qwen3.8:latest`, full Finance question with explicit model override | Native invoice lookup, payment-allocation list, credit-note list and document search; then `read_document(DEPT-002, v4)`. | Correct reconciliation and document-specific collection guidance. |
| `qwen3.8:latest`, customer terms question with explicit override | Native `my_profile` and `my_account_terms`; complete `TERMS-2026-A12C4F10C352` v3 read. | Correct payment term and distinct customer contact versus Acme account manager. |
| `qwen3.8:latest`, full Finance question through the website default | Native tool calls at event 5323 and exact document read at 5416. | Correct answer through the same `/api/chat` path a visitor uses. |

The current local `.env` selects `qwen3.8:latest` for the existing `local`
profile. The shared model factory and `models.toml` remain the source of model
construction and provider settings. New runs read the selected model; existing
conversations and saved traces retain their own model history. The comparison
does not establish a universal ranking between models. In these recorded runs,
the first full Qwen3.8 Finance run took 54.2 seconds, while the later website
run took 12.0 seconds; cold loading and prompt state can affect latency.

The application never executes `<function=...>` text. Only LangChain native
tool calls can reach the validated company tools. The model still decides what
to call and how to answer, so a passing run is evidence for this scenario,
not a guarantee for every future question. Check **Execution** when presenting
an answer as grounded in a tool or document.
