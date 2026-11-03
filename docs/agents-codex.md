# Codex branch: reusable tasks and deterministic hooks

Use this guide from `agents/codex`. Its parent is `agents/common`; the shared
skills and conventions are described in [common patterns](agents-common.md).
The [general guide](coding-agent-guide.md) explains when each mechanism helps.

## Installed example

| Path | Job |
| --- | --- |
| `.agents/skills/explain-code/SKILL.md` | Explain a real execution flow |
| `.agents/skills/review-lesson/SKILL.md` | Review teaching clarity |
| `.codex/agents/lesson_reviewer.toml` | Independent beginner-perspective reviewer |
| `.codex/agents/docs_reviewer.toml` | Check documentation against files |
| `.codex/config.toml` | Agent enablement and concurrency |
| `.codex/hooks.json` | Register two lifecycle callbacks |
| `.codex/hooks/git_safety.py` | Deny recognized destructive Git commands |
| `.codex/hooks/notebook_context.py` | Add validation context after notebook patches |
| `tests/test_codex_patterns.py` | Protocol and launcher checks |

The hook scripts use only the Python standard library. Launchers use `python -I`
on PATH, so they do not require a virtual environment in every checkout. The `-I` flag isolates Python from inherited
Python environment variables; this avoids mixed 3.12/3.14 standard libraries.
Use Python 3.11+ for the TOML-based validation tests.

## Skills and their inputs

```text
Use $explain-code on model_config.py.
Audience: basic Python. Focus: how a profile becomes a model.
Read only; show one concrete input and result.

Use $review-lesson on notebooks/langchain/01_create_agent.ipynb.
Audience: new to agents. Return the first confusing step with its cell number.
```

The paths and labels are prompt inputs, not a shell grammar.
Skills contain `name`, `description`, and the procedure. Codex discovers
repository skills under `.agents/skills/`. The shared copies under
`.claude/skills/` are for Claude discovery; they do not activate Claude hooks.
[Codex skills](https://learn.chatgpt.com/docs/build-skills).

## Specialist agents

Request delegation explicitly:

```text
Use docs_reviewer to compare docs/agents-codex.md with .codex/.
Read only. Return confirmed mismatches and their source locations.

Use lesson_reviewer on notebooks/langchain/01_create_agent.ipynb.
Assume basic Python. Review only; do not run a model.
```

A custom TOML file defines these fields:

| Field used here | Value/meaning in this example |
| --- | --- |
| `name` | Stable identifier such as `docs_reviewer` |
| `description` | Short selection guidance |
| `developer_instructions` | Scope, procedure, and expected evidence |

The project `[agents]` table sets `enabled = true` and
`max_concurrent_threads_per_session = 2` (spawned threads, excluding the primary).
We leave model choice inherited. Optional `model` and
`model_reasoning_effort` are model-dependent; do not invent an available model
from an example. Custom agents inherit parent permissions and MCP servers.
Prose saying "read only" is not a separate sandbox.
[Codex subagent fields](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Use a reviewer when independent context helps. For a two-line correction,
direct editing is usually simpler. The parent must inspect and integrate
the review rather than treating another model's confidence as evidence.

## Hook configuration

`hooks.json` maps events to matcher groups. Each group contains command handlers.

| Example argument | Meaning |
| --- | --- |
| `PreToolUse` | Inspect a pending tool call |
| `PostToolUse` | Inspect a tool result after execution |
| `matcher` | Regex selecting tool names |
| `type: command` | Execute a program |
| `command` | Bash-compatible launcher |
| `commandWindows` | PowerShell launcher override |
| `timeout: 10` | Ten-second handler limit |
| `statusMessage` | User-visible progress label |

Both launchers resolve the Git root so calls from a subdirectory still find
the script. Python reads a JSON event from stdin and prints one JSON result.
The event's `tool_input.command` contains shell text or patch text;
the examples also accept the observed `cmd` shell alias.

The Git example returns `deny` for recognized hard resets, forced cleans,
and force pushes. Ordinary commits are permitted by this example.
It is conservative text matching: quoted examples may trigger, wrappers and
arbitrary script bodies may not. It is not a full shell parser or universal
Git protection.

The notebook example looks only at patch operation headers ending in
`.ipynb`. It returns `additionalContext` reminding the agent about import
layout. It never runs a kernel or test suite, and cannot undo an edit.
Different editor tools need their own input adapters.

### Test a decision without performing the operation

```powershell
'{"tool_input":{"command":"git reset --hard HEAD"}}' |
    python .codex/hooks/git_safety.py
```

This runs Python with a string as input. It does not run Git.
Expected output contains `permissionDecision: deny`. Sending
`git status --short` instead produces `{}`.

Codex currently supports denial and supported input/context outputs, but not
`PreToolUse.permissionDecision: ask`. `PermissionRequest` handles a request
already raised by the host; it does not manufacture a prompt for an otherwise
permitted call. An empty output does not override sandbox policy.
[Codex hook protocol](https://learn.chatgpt.com/docs/hooks).

Therefore this branch does not pretend to implement Claude's approval flow.
Use host permissions where an operation needs consent; use the Claude branch
to study a hook that directly requests a native prompt.

## Launch and verify

From the original checkout:

```powershell
code -n ../agentic_ai-codex
```

Open a fresh Codex session in that folder. Review the two definitions in
Settings > Hooks (CLI: `/hooks`) and trust them. Verify the host lists both
custom agents and both skills. Do not change user-global model or credentials
just to activate project examples.

Local commands:

```powershell
python -m unittest tests.test_coding_agent_patterns tests.test_codex_patterns -v
```

For a harmless live interception check, ask for a shell call
`Write-Output 'git reset --hard'`. The text heuristic intentionally denies
that quoted example. Printed text means the new hook did not intercept it.
For context injection, edit a disposable notebook copy under `.tmp/` and
inspect the post-tool hook event.

## Versions and verification

On 2026-11-03, terminal PATH resolved Codex `0.147.0`; the installed VS Code
extension bundled `0.164.0-alpha.11.1`. This branch follows the current
documented standalone-agent and hook formats. Check the actual executable
used by your surface: an old terminal binary is not proof of IDE behavior.

The branch passed 29 repository tests, including six Codex-specific tests,
on the existing Python 3.12 environment. Nine configuration/portable tests
also passed on Python 3.14. Both configured Windows launchers were
executed from `notebooks/` with synthetic tool data. No model was called.

A native discovery probe exposed the linked-worktree hook-source issue
documented in the common guide; separate clones are the supported local
launch layout for these examples. Review the hook source paths in the
fresh clone and trust those definitions. Native discovery in the final clone
found both shared skills without errors and identified the clone's own
project configuration layer. That layer is currently disabled because the
new project has not yet been trusted; no hooks were loaded. This is the
expected trust gate, not evidence that the hooks executed.

To activate it, open `F:/Gildia_AI/agentic_ai-codex` as a new Codex project
and accept its project trust prompt. If your surface does not expose that
prompt, merge this entry into your user `~/.codex/config.toml` yourself:

```toml
[projects.'F:\Gildia_AI\agentic_ai-codex']
trust_level = "trusted"
```

Then restart the session and review/trust the two hooks in `/hooks` or
Settings > Hooks. Confirm their source is the new checkout, not
`F:/Gildia_AI/agentic_ai`. Project trust and individual hook trust are
separate checks. Neither was silently granted by this setup. A model-driven
live interception test remains a user activation check, not a claimed result.
