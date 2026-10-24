# Conversation and tools redesign

Scope: the ten requested usability changes following the initial release.
Status: **all ten requested changes implemented and verified on Windows/Chrome with local Ollama**, 2026-10-16.
Earlier milestone reports describe the previous interface. This is the current UI acceptance record.

| Request | Implementation | Verified evidence |
| --- | --- | --- |
| Own user at setup; choose or create a user in browser | Custom username, display name and selected role; profile picker and creation form | CLI created `ux.reviewer`; Chrome created Browser Learner with a selected role, then logged out and back in through the picker. Six UX tests cover duplicates, invalid inputs, role and ownership. |
| Assistant left, user right, clear labels | Bubble layout and role labels | Measured at 1280px: user x=425, assistant x=310. At 390px: user x=54, assistant x=12. Both roles have visible labels. |
| Repetitive streaming | Chat renders final answers separately from tool narration; execution view preserves intermediate output; customer-order aggregate covers the reported failed task | Cumulative previews replace content; tool narration stays in saved evidence. Real ranking: 2 model calls / 1 aggregate / correct 145-order result. |
| Mode switching and separate history | Navigate to an existing conversation of that mode or start one; popup guidance; scoped history and Trash | Chrome restored separate Free and Company chats; keyboard mode switch showed guidance popup. Tests preserve used history and scope Trash. |
| Less wasted chat space | Wider conversation/composer; reduced margins | Conversation/composer fill available width; all three main tabs measured document scroll width=390 at 390px viewport. |
| Better mode selector | Segmented selector in the persistent sidebar | Segmented selector fits the sidebar; pointer and Space-key switching worked. |
| Fixed history, tools and settings | Bounded history scroll, company tool descriptions, account/config information and response refresh control | History has a fixed scroll area; company catalog hides in Free mode. Refresh slider changed 0.75 to 0.5 seconds and reset correctly. |
| Rebuild execution panel | Chat selector, saved conversation, message/run selector, timeline, step input/output and model-input comparison | Chrome inspected Company while Chat stayed Free; selecting a SQL timeline row populated its Input; model-input comparison returned differences. Direct tool actions also appear in the execution list. |
| Separate direct tools | Documents, calculator, files/CSV, proposals and approval | Chrome rendered a document, -25% calculation and completed CSV job. API acceptance edited/approved/replayed a report. Direct tool events remain separate from the 2 model calls in the ranking run. |
| Database access and exploration | Role-scoped browser, prepared aggregates, exact file path and read-only Python connection | Exact UI Python sample executed read-only and listed 35 tables. Browser displayed 10 of 3832 customers, then another page. Analyst finance projection denied with no SQL execution. |

Architecture: retain one agent, the existing authenticated services and official
checkpointer. Custom profiles map to a sample employee for the selected business
role, while each profile receives its own immutable user ID and private conversations.
Creating a profile does not modify the 200-employee baseline.

Switching mode navigates between conversations. Once accepted messages exist,
their mode and checkpoints remain associated with their original conversation.
The tool workspace and execution viewer each have an explicit chat selector.

The original "most orders" run made nine model calls without a complete order-count
aggregate. Pagination exposed only a sample, then the model guessed a ranking.
`business_summary(report="customer_orders")` now returns a top-ten ranking over all
matching orders using a prepared aggregate after reading the earliest order date.
Dates default to that earliest date through the business date 2011-12-09.
It counts every order status and resolves ties by customer
ID. The result describes this basis; listing a sampled page is not ranking evidence.


## Reproduce and inspect the evidence

- [Final clean installation and 93-test log](ux_independence.txt): **93 tests passed in 139.595 seconds**, source/company verification, initialization and Ruff. Four tests exercised optional Docker; the other 89 do not require it.
- [Working-copy suite](ux_working_tests.txt): 93 tests passed in 143.863 seconds.
- [Final external-copy UX regressions](ux_copy_final_checks.txt): six tests passed after the last execution-refresh change. Presentation-only alignment CSS was then synchronized and linted.
- [Source parity](ux_copy_parity.json): all 63 application/test/script/schema/configuration files match the independently installed copy.
- [Course import checks](ux_parent_imports.txt): all four pass using the course environment and its documented `middleware` dependency group.
- [Actual Gradio acceptance](ux_api_validation.json): real model execution, disconnect/reconnect, independent pages, edited approval/replay, context differences, CSV work and cross-account denial.
- [Real ranking and full-table count](ux_ranking_live.json), [direct tools and read-only connection](ux_direct_tools.json), and [completed browser CSV worker](ux_browser_csv.json).
- [Browser observations and measurements](ux_browser_acceptance.json).

Screenshots: [user picker](examples/ux_user_picker.jpg), [desktop chat](examples/ux_chat_desktop.jpg),
[desktop execution viewer](examples/ux_executions_desktop.jpg), [mode guidance](examples/ux_mode_popup.jpg),
[mobile chat](examples/ux_chat_mobile.jpg), [mobile execution viewer](examples/ux_executions_mobile.jpg),
and [mobile database tools](examples/ux_tools_mobile.jpg).

```powershell
cd live_example
uv sync --locked
uv run acme setup
uv run acme serve
```

For an existing server, stop it with Ctrl+C and restart it from this directory.
Accounts, conversations, checkpoints and files are retained. The new account-profile
metadata table is created without overwriting existing credentials. On a narrow screen,
close the sidebar to use Chat and open **More tabs** to reach additional tool sections.

The [updated application guide](learning_app.md) covers the three main views and database
connection. The [middleware lesson](middleware.md) uses the new execution selectors.

Scope limits: local learning identity and fictional company data; mock text retrieval;
no arbitrary model-generated SQL. Historical model answers remain historical evidence.
Ask again to recompute an old answer with the new aggregate. Other operating systems,
physical mobile devices, browser engines and cloud inference remain unverified.

Official component references: [Gradio Chatbot](https://www.gradio.app/docs/gradio/chatbot)
and [Gradio Info messages](https://www.gradio.app/docs/gradio/info).
