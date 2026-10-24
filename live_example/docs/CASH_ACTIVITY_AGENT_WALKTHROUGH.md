# One agent run over fictional cash activity

On 22 October 2026 the local website used the configured Ollama
`qwen3.8:latest` model for a fresh superuser chat. The question asked for
customer cash received, recorded expense cash outflow, their difference and
the expense-category breakdown for the fictional 2026 cohort. The
[current portable run extract](../artifacts/cash-activity-agent-2026-10-22-r4.json)
contains the prompt, final answer, `cash_activity` result and six SQL event
IDs. It is an observed run, not hidden model reasoning. An
[earlier extract](../artifacts/cash-activity-agent-2026-10-22-r2.json)
predates the category query and correctly retains its original five-event trace.

| 2026-01-01 through 2026-10-22 | Integer pence | Display |
| --- | ---: | ---: |
| Customer receipts | 294,754 | GBP 2,947.54 |
| Authored expense payments | 44,350 | GBP 443.50 |
| Recorded cash difference | 250,404 | GBP 2,504.04 |

| Authored expense category | Payments | Recorded GBP outflow |
| --- | ---: | ---: |
| Supplier payment | 3 | 177.00 |
| Marketing | 2 | 97.00 |
| Logistics | 2 | 81.00 |
| Packaging | 2 | 50.50 |
| Software | 2 | 38.00 |
| **Total** | **11** | **443.50** |

The agent made a native `cash_activity` call. Python validated the inclusive
dates and finance scope, then ran fixed, parameterized queries for invoice
postings, credit notes, customer payments, expense-ledger availability, total
expenses and expenses by category. Each query has a `sql` event in
`state/events.sqlite`; the result contains the corresponding query source IDs.
The verifier compared both the money facts and all category records with an
independent read of the Insights service over the current SQLite state.

The final answer stated all three GBP amounts, called the 2026 entries
**authored fictional scenario events**, described the expense ledger as
incomplete, and explicitly said the difference is **not profit**. It listed
all five category amounts and counts, and cited one query event ID that appears
in the saved six-event trace. The script's answer checks are string-based
signals; the quoted answer remains available for human review. One correct
run does not guarantee future model wording. The stable boundary is the
finance-scoped Python tool with fixed SQL and traceable outputs; verify a
particular answer in **Execution**.

To repeat the exercise while the local website and Ollama are running:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_cash_activity_agent `
  --output artifacts/cash-activity-agent-new-run.json
```

Choose a fresh output path each time. The verifier compares the tool result
with the active company database and records the answer separately. For the
definitions behind the figures and the source/fictional timeline boundary,
see [business insights](BUSINESS_INSIGHTS.md).
