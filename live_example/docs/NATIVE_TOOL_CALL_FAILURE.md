# When a model prints a tool call instead of making one

The agent offers real LangChain tools to the model. A sentence that resembles a
tool call is only text; it does not execute the tool. This distinction was
observed in an independent CLI run on 2026-10-20.

## The failed `qwen3-coder:30b` run

Run `scripts/verify_live_runtime.py` on an isolated state directory with the
question: "Remember the case label CEDAR-71. How much is still owed on
DEMO-INV-001 and how many days overdue is it? Use the invoice tool and cite its
ID." The model request offered 12 tools, including `lookup_record`. In the
first unguarded run, the model returned a plain answer containing
`<function=lookup_record>...</tool_call>` but **zero** native `tool_calls`.
Consequently, there was no invoice SQL query. A later turn claimed GBP 2,500
and 45 overdue days, both unsupported and wrong. The raw CLI outputs are under
`artifacts/live-runtime-2026-10-20-escalated/`.

The format matches an [Ollama Qwen3-Coder parser issue](https://github.com/ollama/ollama/issues/16686):
when the model omits the opening `<tool_call>` wrapper, the parser can leave
the `<function=...>` block in ordinary content. The local Ollama model declares
`PARSER qwen3-coder`; the observed response had the bare function tag. This is
evidence for this run, not a claim that every call with that model fails. A
shorter invoice request and several website runs used native tools correctly.

## What the application does now

`NativeToolCallGuardMiddleware` in `acme/middleware.py` detects markup for an
offered tool at the start of a line when the model response has no native call.
It also catches a truncated block without a closing `</tool_call>` tag. It records
`native_tool_call_retry`, makes one further model request through LangChain's
`wrap_model_call` handler, and requires a real native tool call. If the model
still returns text, it records `native_tool_call_failed` and fails the run.
It **does not parse the text and execute it**. This keeps tool validation,
authorization and tracing on the actual LangChain tool path.
If a valid final answer merely ends with an orphan `<tool_call>` marker, the
guard removes that provider formatting artifact before the answer reaches the
checkpoint. The raw `model_response` remains in the execution trace and a
`provider_markup_removed` event records the cleanup. It does not change the
answer's business facts or turn text into an executed call.

The guarded Qwen3-Coder run under
`artifacts/live-runtime-guarded-2026-10-20/` shows the first malformed
response, one retry, a second malformed response and `run_failed`. The user
does not receive a fabricated invoice answer from that run.

A separate website run recovered successfully with the same guard. In
`artifacts/native-tool-call-recovery-website-2026-10-20.json`, execution event
4060 is a model response without native calls, 4062 records the retry, 4069
contains a native `lookup_record` call, and 4086/4087 are the actual invoice SQL
and tool result. The final answer was GBP 700.00 and nine days overdue. Both
outcomes matter: retry can repair the format, but failure remains explicit when
it cannot.

## Independent passing comparison

The same three-turn CLI verifier passed with the locally installed
`qwen3.8:latest` model. Its result is
`artifacts/live-runtime-qwen38-complete-2026-10-20/validation.json`; the
matching `trace.json` records five model requests and five SQL queries. The
answers reported GBP 700.00 outstanding, nine overdue days, GBP 450.00 in
payment allocation and GBP 50.00 in credit. They also carried CEDAR-71 across
fresh CLI processes. Duplicate submission added no event, and another account
could not read the transcript. This proves this recorded run, not universal
reliability of either model.

A later [Finance website comparison](FINANCE_AGENT_MODEL_COMPARISON.md) on
21 October 2026 reproduced the malformed textual call with
`qwen3-coder:30b` on a multi-source question. The locally installed
`qwen3.8:latest` completed that question through native tool calls and read
the current `DEPT-002` v4 instruction. The local site's model selection was
updated after that comparison; the guard still rejects textual tool markup.

To repeat without changing the website's configured model, use a fresh output
directory:

```powershell
uv run python scripts/verify_live_runtime.py --model qwen3.8:latest --output artifacts/my-qwen38-check
```

This verifier makes real model calls and writes a new local state directory.
The exact Unicode answers are saved in its `turn-*.json` files; console output
escapes characters that some Windows code pages cannot print.
