# Codex in VS Code: setup and examples

Use branch **`agents/codex`**. Start with [the concepts](coding-agent-guide.md),
then use [the authoring reference](create-codex.md) when adding your own files.

## Files and their effect

| Path | Loaded purpose |
| --- | --- |
| `AGENTS.md` | Repository language, teaching, import, and validation conventions |
| `.agents/skills/explain-code/SKILL.md` | Trace actual code using a small input |
| `.agents/skills/review-lesson/SKILL.md` | Review a lesson's learning sequence |
| `.agents/skills/inspect-lesson/SKILL.md` | Explicit delegation procedure with path and audience |
| `.codex/agents/docs_reviewer.toml` | Documentation/configuration consistency reviewer |
| `.codex/agents/lesson_reviewer.toml` | Notebook learning-flow reviewer |
| `.codex/agents/joke_writer.toml` | Specialist responsible for creating five jokes |
| `.codex/config.toml` | Enable agents, limit spawned threads to two, register local MCP |
| `.codex/hooks.json` | Register the pre-call Git guard and post-edit notebook reminder |
| `.codex/hooks/*.py` | Deterministic handlers; no model calls |
| `agent_demo/` | Read-only MCP server, locked dependencies, protocol smoke test |

There is no second host's skill directory, no `CLAUDE.md`, and no third shared
assistant branch. The model, credentials, host sandbox, approval policy, and
personal preferences are inherited rather than hardcoded in this branch.

## Start in VS Code

1. Check out this branch and open its root as a VS Code folder. Install Python
   3.12+, Git, and uv on PATH. Use the Codex extension's runtime; a separately
   installed `codex` command can be older and have different configuration fields.
2. Run `uv sync --frozen --project agent_demo` once in the repository terminal.
3. Trust the repository through Codex's normal project-trust flow. Then review
   and trust the **two exact hook definitions** with the runtime's `/hooks`
   browser. Changed definitions require another review. In an untrusted project,
   `.codex/config.toml` and project hooks are not loaded.
4. Start a fresh Codex conversation after configuration changes. Inspect the
   skill picker and MCP server/tool list. Native CLI slash commands refer to the
   CLI bundled with the extension; availability in the graphical chat can differ.

Configuration is discovered by the host. Merely reading a TOML file in a chat
does not activate its agents, hooks, or MCP server. VS Code workspace trust and
Codex's project/hook trust are different controls.

## Try the features

```text
$explain-code model_config.py â€” audience: basic Python
$review-lesson notebooks/langchain/01_create_agent.ipynb
$inspect-lesson notebooks/langchain/01_create_agent.ipynb â€” audience: basic Python
Delegate a read-only check of docs/agents-codex.md to docs_reviewer.
Use joke_writer to create five fresh programming jokes in root jokes.txt.
Call lesson_tools.count_words with text "small useful example".
```

The joke writer owns the file edit and reads it back. If `jokes.txt` exists,
it stops; move your old demo output yourself before repeating the example.
There is **no extra hook-generated approval question** for writing jokes,
deleting a file, or committing. Ordinary session permissions still apply.
The writer's output restriction is instructions, not a separate tool allowlist.

The Git hook denies recognizable `reset --hard`, forced `clean`, and forced
`push` shell text. Normal commits and `git clean -nd` continue normally.
The notebook hook recognizes patch file headers and native file-path inputs
ending in `.ipynb`; it adds context after successful edits, not before them.
These text detectors are teaching examples and can miss indirect operations.

## Verify without dangerous operations

```powershell
python -m unittest tests.test_coding_agent_patterns tests.test_codex_patterns -v
uv run --frozen --project agent_demo python agent_demo/check_server.py
```

The tests submit dangerous command strings to the hook process as JSON; they
never execute those strings. The MCP check launches the exact registered
command from `notebooks/`, lists its schema, calls valid inputs, and rejects a
missing argument. It tests both modern and legacy MCP negotiation.

For an interactive denial probe, ask the agent to execute
`Write-Output 'git reset --hard HEAD'`. The quoted text intentionally matches
the heuristic. With a trusted active hook it is denied; if not, it only prints
text. Do not test with an actual destructive command.

## What this demonstrates and what it does not

Codex loads skill instructions into the agent; `inspect-lesson` asks it to
delegate. There is no Claude-style `context: fork` field. Subagents inherit
the parent's permissions and MCP connections. Read-only reviewer instructions
are behavioral guidance; this setup does not claim an isolated reviewer sandbox.

`PreToolUse` supports allow/deny; it currently does **not** implement `ask`.
`PermissionRequest` can handle an approval already triggered by the host, but
does not manufacture a new prompt for every arbitrary action. There is no
approval-file protocol, polling loop, or parent-agent question relay here.
[Hooks](https://learn.chatgpt.com/docs/hooks),
[subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Verification record

Checked 2026-11-07 with the VS Code extension 26.1021.22027 bundled runtime
`codex 0.164.0-alpha.11.1`:

- 11 automated branch/layout tests passed; all three skills passed the skill
  validator. The actual registered MCP launcher passed modern and legacy stdio
  discovery, schemas, three counting cases, and missing-input rejection.
- Native app-server discovery loaded the project agent settings, three skills,
  and both hook definitions with `trusted` status and no project hook errors.
  The project and each hook were reviewed individually in the native runtime.
- A model turn loaded `explain-code`. An interactive native session called
  `count_words` after its ordinary per-call MCP permission prompt and received
  `3`. A `docs_reviewer` subagent started and completed a separate read-only
  review; its useful structured-result documentation correction was applied.
- The native runtime denied the harmless quoted Git probe through PreToolUse.

The bundled binary needed `--no-daemon` when used as a standalone interactive
CLI; the extension supplies its own app-server integration. Non-interactive
`codex exec` uses `never` approvals and cannot answer an MCP approval prompt.
A trial with `--ephemeral` also encountered a subagent thread-context error;
the normal interactive session completed delegation. Neither issue was solved
by disabling the sandbox or globally allowing tools.

These are real tests of the extension's bundled runtime and its native terminal
interface, not a claim that the VS Code graphical panel was clicked through.
The notebook reminder has handler/launcher coverage; no teaching notebook was
modified to demonstrate it. The joke writer definition is loaded, but its write
path was not separately exercised in this branch. Model-generated review quality
can vary. Existing unrelated user-config warnings remain outside this example.
