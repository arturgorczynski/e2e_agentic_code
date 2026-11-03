# Managing coding agents without unnecessary machinery

A coding agent is a model working inside a program that supplies tools, context,
permissions, and a loop: understand the task, call tools, inspect results, and
continue. The model and the host are different components. Model instructions
can guide behavior; the host decides which tools and permissions exist.

In this guide, "hooks" means lifecycle callbacks, not browser cookies.
"Subagents" means delegated model workers, not independent operating-system users.

## Choose the mechanism by the job

| Mechanism | Role | Use when | Avoid when |
| --- | --- | --- | --- |
| Task prompt | Defines today's outcome and scope | A one-off request is clear | Repeating a long procedure in every request |
| Project instructions | Short durable project conventions | Rules apply to most work here | Writing a copied product manual or task history |
| Skill | A reusable task procedure | The same workflow recurs | A single trivial edit needs no procedure |
| Subagent | Separate reasoning context for a bounded task | Independent review or research would help | The task is tiny or every step depends on the parent's last step |
| Hook | Program reacting to a lifecycle event | A deterministic check or reminder has a clear trigger | Asking a regex to understand arbitrary program intent |
| Permission rule | Host policy about tool access | Repeated tool operations need approval or denial | The restriction is merely a writing preference |
| Sandbox | Limits what execution can access | Filesystem/network separation matters | Treating prose like operating-system isolation |
| MCP server | Supplies tools/data to an assistant | An external service needs a supported interface | Existing local tools already do the job |
| Git worktree | Isolates files and an index for a branch | Parallel work changes different variants | Several agents still edit the same files in one checkout |

## A good request is an acceptance contract

Give the agent these inputs in ordinary language:

```text
Outcome: explain why profile selection falls back to a default.
Scope: model_config.py and its direct callers.
Constraints: reading only; no model API calls.
Evidence: trace one concrete input to its output and cite the relevant lines.
Completion: explain both the normal path and the missing-profile case.
```

For implementation, add allowed files and the checks that prove success.
For a review, specify whether edits are wanted. "Review only" and "fix the
findings" authorize different actions. File paths and audience labels are
task inputs; they do not automatically become permissions.

## Instructions: keep the durable facts close to the code

Root instructions describe shared conventions. Nested instructions narrow
the context for notebooks or a component. Put the execution command beside
the code that owns it; avoid copying it into five global prompts.

A useful rule here is "imports belong in the first notebook code cell."
It is short, observable, and supported by a layout test. "Make everything
excellent" has no comparable acceptance condition.

Keep model names, credentials, personal MCP connections, and workstation paths
out of shared instructions unless the project actually requires them.

## Skills: organize a repeated task

Use a precise description so the agent knows when to load the skill.
The procedure should change decisions, not repeat generic advice to be helpful.

Our explanation skill takes paths, audience, and focus; it returns an actual
execution trace. Our lesson review takes notebook paths and prerequisites;
it returns located obstacles. Neither needs a special runtime or hidden state.

A skill can refer to a script when repeatable execution matters. Keep the
script's CLI arguments separate from the skill's free-form task inputs.
For example, `python -m unittest tests.test_coding_agent_patterns -v` has real
Python arguments; `audience=beginner` in a prompt is just a label for the model.

## Subagents: divide responsibility, not accountability

A useful delegation includes a narrow question, relevant files, allowed effects,
and a result format:

```text
Review only docs/agents-codex.md against .codex/.
Do not edit. Return each confirmed mismatch with both source locations.
Distinguish untested behavior from a demonstrated error.
```

The parent still integrates the report and owns the final result. Two workers
should not unknowingly edit the same file. Give each ownership of distinct
paths or separate worktrees. Separate model context reduces distraction;
it does not by itself isolate filesystem access.

Read-only reviewers are a useful first example. A writer agent is appropriate
when its output and permitted target are narrow. The Claude joke writer owns
only root `jokes.txt`; it uses a restricted tool set and its own hook.

## Hooks: keep execution small and observable

A hook has an event, a matcher, a handler, input, and output.
The event says when; the matcher says which tool; the handler is a program.
Input JSON describes the proposed or completed call. Output JSON can carry a
decision or context, depending on the product and event.

A before-tool check can prevent a supported call. An after-tool reminder
cannot undo the side effect. A script failure is not the same as a deliberate
denial; configure and test the runtime's error behavior.

Avoid hooks that ask a model to inspect every command, automatically install
packages, launch kernels on every save, or write transcript approval receipts.
They add cost, latency, and hidden state. For approval, prefer a host-native
prompt where the product supports one.

## Use cases and the smallest useful setup

| Use case | Inputs | Setup | Evidence of success |
| --- | --- | --- | --- |
| Explain one function | Path, symbol, audience | Prompt or explanation skill | Correct trace with source locations |
| Review five lessons | Ordered paths, prerequisites | Skill; optional independent reviewer | Located learning obstacles |
| Keep tests aligned with edits | Changed paths, test command | Agent workflow plus post-edit reminder | Actual passing test output |
| Ask before a Claude commit | Pending shell command | Claude PreToolUse hook returning ask | Host prompt, then approved/denied effect |
| Ask before writing jokes | Five fresh jokes, exact target | Foreground Claude agent plus scoped hook | Native prompt; target created only after approval |
| Protect a Codex operation | Explicit condition | Supported deny hook and host permissions | Actual tool interception |
| Implement two independent features | Per-worker file ownership | Worktrees and bounded workers | Reviewed diffs and relevant checks |

Codex and Claude do not have identical hook contracts. See the
[Codex guide](agents-codex.md) and [Claude guide](agents-claude.md) before copying
configuration. A provider name in a model API request does not select the
coding-agent host.

## Validate in layers

1. Parse configuration and check links.
2. Feed synthetic JSON to hooks; inspect decisions without executing the commands.
3. Run the configured launcher from the expected working directory.
4. Confirm the host discovers skills/agents and trusts the hooks.
5. Exercise both approval and denial in a disposable target.
6. Inspect the actual effect: a file, commit, diff, or absence of one.

Only steps 4-6 establish live integration. A model saying "I was blocked" is
weaker than the hook event and actual state. Never silently answer a permission
dialog for the user during a permission demonstration.

When something cannot be completed, report the exact operation, actual error,
and smallest next step. Do not repeat an endless permission loop or call
partial work complete.

## Branch upkeep

Use common for shared skill bodies and conventions. Merge shared changes into
both provider branches, then run their specific tests. Avoid an installer that
writes global configuration or overwrites unrelated project settings.

Before switching tools, open the intended worktree, inspect its branch and
status, and start a fresh assistant session. Keep a small verification record
in the provider guide; do not create a new report for every test run.
