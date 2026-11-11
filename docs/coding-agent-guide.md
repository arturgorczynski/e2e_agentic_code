# How the assistant pieces fit together

Start with one task: explain a function, review a lesson, or create five jokes.
The assistant chooses steps; the host supplies tools and enforces permissions.
These examples use ordinary files and native host features.

| Piece | What it contributes | When to use it |
| --- | --- | --- |
| `AGENTS.md` | Repository-wide working instructions | Stable conventions: language, imports, validation |
| Skill | A reusable task procedure loaded when relevant | Repeated explanations and reviews |
| Subagent | A specialist with a separate conversation context | Delegate a bounded review or output |
| Tool | Executable operation with named input arguments | Read a file, run a command, call `count_words` |
| MCP server | Makes tools/resources/prompts available through a standard protocol | Connect your own code to an assistant |
| Hook | Deterministic code at a host event | Reject a recognized operation or add a reminder |
| Permissions | Host control over execution, access, and approval | Decide what operations can run |
| Model/runtime | The model reasons; the host discovers configuration and executes tools | Understand which component owns each decision |

## One call, end to end

```text
User request
  -> main assistant (may load a skill)
  -> optional specialist subagent
  -> proposed tool call with arguments
  -> PreToolUse hook + host permission handling
  -> tool executes, if permitted
  -> PostToolUse hook
  -> assistant reads the result and replies
```

A skill is instructions, not executable code. A subagent is another model
context, not a Python subprocess. A hook is executable code, not a second model.
The host calls the hook. The hook returns a decision; it does not perform the
pending tool operation. A native approval dialog belongs to the host UI.
The main assistant does not need to relay a hook's question.

## The examples on both branches

Two skills: `explain-code` explains actual code interactively in a pirate voice;
`review-lesson` evaluates one lesson's idea, learning sequence, code, and outputs.
A skill's path/audience are task inputs; its YAML fields
describe the skill. They are different kinds of arguments.

Two specialists: a lesson reviewer and a joke writer. The reviewer executes
notebook copies unless asked for reading-only review, then reports learning
obstacles without editing source. The Codex joke writer submits one real write
containing five numbered jokes to root `jokes.txt`. The hook denies that write,
and the agent reports the block without printing jokes or retrying. Claude's
writer requests native approval to create and then delete the file. Tool restrictions
and approval capabilities depend on the host; read the branch guide for details.

Four hooks cover Git restrictions, deletion, joke-file writing, and post-edit
notebook reminders. Git staging, commit creation, and publication are denied.
Claude asks before detected deletions and joke writes; Codex denies them under
the selected policy. The user handles staging, commits, and cleanup.

The local `lesson_tools` MCP server exposes one tool:

```json
{"name": "count_words", "arguments": {"text": "small useful example"}}
```

The function returns `3`; MCP structured content is `{"result": 3}`. The SDK derives the required string argument
from `text: str` and the result schema from `-> int`. `""` returns `0`;
punctuation stays attached; this is whitespace counting, not language analysis.
There is no API key, network service, write operation, model, or database in
this server. Dependencies download during initial setup; tool execution is local.

## What belongs where

Commit shared conventions, procedures, specialist definitions, hook code,
portable server registration, and dependency locks. Keep credentials,
machine-specific preferences, trust decisions, and local environments on the
machine. Repository config does not replace user or managed organizational
policy. A setting in the wrong directory may simply never be loaded.

One host branch contains its own native files and documentation. The conceptual
document explains both hosts; each branch records its selected policy. The MCP
implementation remains shared in purpose.
There is no third integration branch. Apply future shared improvements to both
branches with a focused cherry-pick or equivalent edit; do not merge one host's
complete assistant configuration into the other.

## Why instructions and enforcement differ

"Do not edit" in a prompt guides behavior. A tool allowlist limits which tools
the specialist receives. A hook can reject a matching call. The operating-system
sandbox and host permissions control execution. None of these should be described
as interchangeable. A skill does not grant permissions merely by requesting a tool.

The Git/deletion hooks inspect command text. They can match text inside a quoted
example and miss operations hidden in scripts, aliases, or different tools.
They are deliberately small teaching examples, not complete security controls.
The notebook hook adds context; it neither runs tests nor proves a valid notebook.
Hook activation requires host trust and a new/reloaded session when applicable.

## Create the smallest useful extension

1. Write the desired input and observable result.
2. Use `AGENTS.md` for a lasting repository convention.
3. Use a skill for a repeatable procedure; add a specialist only when delegation helps.
4. Use a Python tool and MCP for a repeatable executable operation.
5. Add a hook only when an event should trigger deterministic behavior.
6. Test success, irrelevant inputs, and refusal/error cases. Then test actual
   discovery and a harmless call in the intended host.

Passing a parser test proves syntax. Calling a hook script proves its handler.
An MCP protocol test proves the server. Seeing the feature and its outcome in
VS Code proves that the installed extension loaded and used it. Keep those
claims separate. The branch's setup guide records the actual verification.
