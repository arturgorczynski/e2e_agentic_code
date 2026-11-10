# Claude Code in VS Code: setup and examples

Use branch **`agents/claude`**. Start with [the concepts](coding-agent-guide.md),
then use [the authoring reference](create-claude.md) to add your own examples.

## Files and their effect

| Path | Loaded purpose |
| --- | --- |
| `AGENTS.md` | Native repository instructions; no `CLAUDE.md` shim |
| `.claude/skills/explain-code/SKILL.md` | Trace code with a concrete example |
| `.claude/skills/review-lesson/SKILL.md` | Review the learning sequence |
| `.claude/skills/inspect-lesson/SKILL.md` | Fork a review into `lesson-reviewer` and wait |
| `.claude/agents/docs-reviewer.md` | Read-only documentation/configuration review |
| `.claude/agents/lesson-reviewer.md` | Student-view review that executes notebook copies |
| `.claude/agents/joke-writer.md` | Creates root `jokes.txt`, then deletes it; both steps ask |
| `.claude/settings.json` | Normal permissions, Git guard, deletion and joke approval, notebook reminder |
| `.claude/hooks/*.py` | Deterministic event handlers |
| `.mcp.json` | Project-local registration of `lesson_tools` |
| `agent_demo/` | Read-only MCP server, locked dependencies, protocol smoke test |

No `.agents/skills` mirror is present. User credentials, model preference, and
workspace trust are local. `.claude/settings.local.json` and root `jokes.txt`
are ignored by Git; committed settings do not bypass user or managed policies.

## Start in VS Code

1. Open this branch's root in VS Code with Claude Code. Use version 2.1.295+
   for the shipped `args`/`onFailure` hook configuration. The verified installed
   extension/runtime version is recorded below. Python 3.12+, Git, and uv must
   be on PATH.
2. Run `uv sync --frozen --project agent_demo` once in the repository terminal.
3. Review and trust this workspace in a normal interactive session; enable the
   project `lesson_tools` MCP server when prompted. Keep normal/default
   permissions so the approval example remains observable.
4. Open a fresh conversation. Check Customize > Hooks in VS Code; in the native
   terminal interface use `/hooks`, `/skills`, `/mcp`, and `/context all`.
   Confirm the three specialists, three skills, and `count_words` are available.
   In v2.1.311 `/agents` reports that its wizard was removed; inspect custom
   agents through `/context all`, edit their files, or request a real delegation.

Modern Claude Code reads `AGENTS.md` natively (v2.1.277+). Its default
`claude-md-or-agents-md` mode uses AGENTS when there is no competing `CLAUDE.md`,
`.claude/CLAUDE.md`, or `CLAUDE.local.md` in this directory or ancestors. A user
or managed setting can change that behavior. If instructions are missing,
inspect Project instructions in `/config` and the loaded context. Do not add a
CLAUDE import shim to this example. Native AGENTS loading does not emit the
`InstructionsLoaded` hook event.
[Instruction discovery](https://code.claude.com/docs/en/memory).

## Try the features

```text
/explain-code model_config.py
/review-lesson notebooks/langchain/01_create_agent.ipynb
/inspect-lesson notebooks/langchain/01_create_agent.ipynb "basic Python"
Use docs-reviewer to check docs/agents-claude.md against the actual files.
Use joke-writer to create five fresh programming jokes in root jokes.txt, then delete it.
Call lesson_tools.count_words with text "small useful example".
```

`inspect-lesson` is explicit-only, substitutes `$0` and `$1`, uses `context:
fork` and `agent: lesson-reviewer`, and waits because `background: false`.
The other skills can also be selected by the model. The fork needs explicit
inputs; it does not inherit the full main conversation.

`lesson-reviewer` has `tools: Read, Grep, Glob, Bash`. It uses `Bash` only to
execute notebook copies into the ignored `.tmp/lesson-review/` and never edits
the source notebooks. The writer has `Read, Write,
PowerShell, Bash` and demonstrates two approvals in one task: it creates the
file, reads it back, then deletes it with one `Remove-Item`/`rm` call. The
shell is there only for that deletion, which `ask_before_change.py` turns into
a native `ask`; the prompt, not a hook, limits the shell to that one command.
The project Write hook `approve_jokes.py` validates the exact repository-root
path, absence of an existing file, and five numbered nonempty lines. Valid input
returns native `ask`; invalid input returns `deny`. The writer submits the call,
the host asks you, and after approval the host executes the writer's pending
Write. The hook itself never writes. Refusal stops this task; the parent does
not retry the write for it. The validation is preflight, not an atomic
filesystem guarantee or a humor check.

The hook is registered in `.claude/settings.json`, not in the agent's
frontmatter. Agent-scoped frontmatter hooks can be omitted when the agent runs
as a background, non-interactive subagent; then the session's permission mode
(for example accept-edits) silently allows the Write. A project hook runs for
subagents too. Its `ask` applies to **every Write of root `jokes.txt`**,
whichever agent sends it. When the event's `agent_type` is `joke-writer`, writes
to any other path are denied; other writers' normal edits return `{}` and keep
ordinary host permissions.

Run joke-writer in the foreground to see the prompt. A background subagent
cannot display the dialog, so the `ask` ends as a refusal and no file appears.

## Hook behavior selected for this branch

| Proposed operation | Extra repository hook result |
| --- | --- |
| Git add/commit/push or other staging and commit-making command | `deny`; the user commits |
| Recognizable file deletion | Native `ask` |
| Valid Write of root `jokes.txt` (any agent) | Native `ask` |
| joke-writer Write elsewhere, existing file, malformed joke content | `deny` |
| Recognizable destructive Git reset/clean/force-push | `deny` |
| Notebook Edit/Write/NotebookEdit | Post-call validation reminder |

Multiple hooks can match; `deny` takes precedence over `ask`. Thus forced Git
clean remains denied even though the deletion handler also asks. Shell matching
is heuristic: quoted examples can match; hidden scripts can evade it. This is
not a full deletion security policy.
[Hook decisions](https://code.claude.com/docs/en/hooks).

## Verify the example

```powershell
python -m unittest tests.test_coding_agent_patterns tests.test_claude_patterns -v
uv run --frozen --project agent_demo python agent_demo/check_server.py
```

The tests exercise JSON decisions, path/content validation, launchers, notebook
inputs, and MCP protocol calls. Dangerous strings are input data, not executed
operations. For a harmless interactive Git denial probe ask the agent to execute
`echo "git reset --hard HEAD"`; the expected denial proves the text hook fired.
For deletion approval, create a clearly disposable file, request its removal,
and try refusal first. Verify it still exists. Approve a later explicitly
requested deletion only when you intend it. For jokes, use an unused root output
and verify that no file appears on refusal, then approve a new requested attempt.

Trust and permission dialogs require an interactive host. A `claude -p` handler
or discovery test does not prove the user saw or accepted the native dialog;
untrusted agent-scoped hooks can be omitted in that mode.

## Verification record

Checked 2026-11-07 with the VS Code extension/native runtime `2.1.311`:

- 14 automated branch/layout tests passed. The actual registered MCP launcher
  passed modern and legacy stdio discovery, schemas, three counting cases, and
  missing-input rejection.
- Native initialization discovered all three project skills and all three
  project specialists. A real model turn invoked `explain-code`, called
  `count_words` and received `3`, and delegated a completed review to
  `docs-reviewer`. That trial explicitly selected the committed `.mcp.json`
  with `--strict-mcp-config --mcp-config .mcp.json` to exclude unrelated servers.
- The Git hook denied a harmless quoted command through native PreToolUse.
- In a non-interactive trial, joke-writer's own Write reached its scoped hook;
  the returned `ask` stopped the write and no file appeared. In a later native
  interactive session the host displayed `Create file - from the joke-writer
  agent`. After explicit user approval, that subagent wrote five numbered lines
  and read the result back. The parent did not perform the write. The ignored
  local `jokes.txt` is demonstration output, not part of the branch.
- 2026-11-10: a background joke-writer launched from the VS Code chat wrote
  `jokes.txt` with no prompt. Its transcript showed no frontmatter-hook run and
  the Write accepted by permission mode. The guard then moved to the project
  `PreToolUse` Write hook; the native prompt has not yet been re-verified.

Workspace trust was accepted through the native interactive flow. New users
still review their own checkout and enable the project MCP server. These tests
used the extension's bundled runtime and native terminal UI; the graphical
VS Code approval panel was not separately inspected. Deletion decisions and
notebook reminders have handler/launcher coverage; no real deletion or teaching
notebook edit was needed. A refusal caused by non-interactive mode is not the
same test as a person selecting No in the graphical panel.
