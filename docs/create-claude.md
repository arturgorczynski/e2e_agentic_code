# Claude Code: create skills, subagents, hooks, and tools

**Use branch `agents/claude`.** This is the short authoring reference; see
[setup and working examples](agents-claude.md) for activation and native approvals.
Use [Common](create-common.md) for portable instructions and the tool implementation.

## 1. Skill: a reusable procedure with optional arguments

Create `.claude/skills/summarize-file/SKILL.md`:

```markdown
---
name: summarize-file
description: Explain a named repository file for a specified audience.
argument-hint: "[path] [audience]"
arguments: [path, audience]
disable-model-invocation: true
---

Read $path for audience $audience. Ask if either value is empty.
Return its purpose, one input/result, and source line references.
Do not edit or execute the file.
```

Invoke: `/summarize-file model_config.py "basic Python"`. The following fields
are recognized in local Claude Code skills; most are optional:

| Frontmatter field | Value / function |
| --- | --- |
| `name`, `description`, `when_to_use` | Strings: command name, purpose, extra selection hints |
| `argument-hint` | Autocomplete hint; no validation |
| `arguments` | Ordered names, e.g. `[path, audience]` |
| `disable-model-invocation` | `true`: explicit invocation only |
| `user-invocable` | `false`: hide and disable user slash invocation |
| `allowed-tools` | List/string: temporary permission grants, not an exclusive tool list |
| `disallowed-tools` | List/string: temporarily remove tools |
| `model`, `effort` | Model/effort override; levels depend on model |
| `context`, `agent` | `fork`: delegated context; `agent`: specialist name |
| `background` | With `fork`, `false` waits for completion |
| `hooks` | Registered on invocation; persist for the session |
| `paths` | Glob list/string: automatic activation scope |
| `shell` | `bash` or `powershell` for injected commands |
| `metadata`, `license`, `compatibility` | Catalog map, licensing, prerequisites; informational |

Body substitutions: `$ARGUMENTS` is full input, `$0`/`$ARGUMENTS[0]` is the first
position, and `$path` uses `arguments`. `${CLAUDE_SKILL_DIR}` locates bundled files.
Use exact field spelling; unknown keys are ignored. **Skill fields differ from
agent fields** (`disallowed-tools` versus `disallowedTools`).
[Skill reference](https://code.claude.com/docs/en/skills).

Keep the two mirrored portable skills minimal. Give Claude-specific workflows
their own names, as this branch does with `inspect-lesson`.

## 2. Subagent: an independent specialist with a tool list

Create `.claude/agents/file-reviewer.md`:

```markdown
---
name: file-reviewer
description: Review a named file for concrete correctness problems.
tools: Read, Grep, Glob
model: inherit
---

Read the file and relevant callers. Return confirmed problems with line
references and a minimal correction. Do not edit or run the program.
```

Ask: `Use file-reviewer to review model_config.py.`

| Agent frontmatter field | Value / function |
| --- | --- |
| `name`, `description` | Required strings: identity and selection |
| `tools`, `disallowedTools` | Tool list/string: allowed pool and removals |
| `model`, `effort` | Available model or `inherit`; supported reasoning level |
| `permissionMode` | E.g. `default` for normal prompts or `plan` for planning |
| `maxTurns`, `autoCompactWindow` | Turn cap; optional compaction token threshold |
| `skills` | Skill names to preload |
| `mcpServers` | Existing server names or inline server definitions |
| `hooks` | Callbacks scoped to this agent |
| `memory` | `user`, `project`, or `local` persistence |
| `background`, `isolation` | `true` forces background; `worktree` creates separate checkout |
| `omitClaudeMd` | `true` omits ordinary CLAUDE.md context |
| `color`, `initialPrompt` | UI color; first prompt when used as main session agent |
| `experimental.cacheTtl` | Optional cache lifetime: `5m` or `1h` |

The Markdown body is the agent prompt. Start with the four fields in the example;
add others only for a concrete need. `tools` limits access; instructions alone
do not. A specifier in `disallowedTools` removes the whole tool. Check `/agents`
after creating it. [Agent reference and value limits](https://code.claude.com/docs/en/sub-agents).

## 3. Hook: a native event handler

Register a script under `hooks` in `.claude/settings.json`. Merge entries into
the existing map. This example uses this branch's shipped approval handler:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "^(Bash|PowerShell)$",
      "hooks": [{
        "type": "command",
        "command": "python",
        "args": ["-I", "${CLAUDE_PROJECT_DIR}/.claude/hooks/ask_before_change.py"],
        "timeout": 10,
        "onFailure": "block"
      }]
    }]
  }
}
```

| Field | Value / function |
| --- | --- |
| Event key, `matcher` | E.g. `PreToolUse` before execution; tool-name regex |
| `type` | `command` here; other types have separate schemas |
| `command`, `args` | Executable and direct argv; `args` disables shell interpretation |
| `shell` | For shell form without `args`: `bash` or `powershell` |
| `timeout`, `statusMessage` | Seconds; progress label |
| `onFailure` | `block` or `continue` when execution fails |
| `if` | Optional filter using permission-rule syntax |
| `async`, `once` | Background command; one successful run (`once` only in skill hooks) |

Script stdin: event JSON, including `tool_name` and `tool_input`. Return JSON
on stdout and exit 0. `{}` follows normal permissions. For `PreToolUse`, return:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Review this proposed change."}}
```

`ask` requests the native prompt; `deny` rejects; `allow` grants permission at
this hook stage. The hook does not execute the pending operation. Keep approval
handlers synchronous. Agent-scoped hooks require workspace trust; see the
existing `joke-writer` example. `onFailure` needs v2.1.295+.
[Hook protocol and advanced types](https://code.claude.com/docs/en/hooks).

## 4. Tool: connect an MCP server

Create the [Common tool template](create-common.md), then register it locally
from the repository root (replace the absolute path):

```powershell
claude mcp add --transport stdio --scope local text_tools -- uv run --isolated --no-project --with "mcp>=2,<3" python "C:/path/to/repo/tools/text_tools.py"
```

The trial launcher downloads an isolated SDK environment on first use.
`--transport` selects stdio; `--scope local` keeps this machine's path local;
the name identifies the server; everything after `--` is its executable/argv.
Use `--scope project` for portable team configuration stored in `.mcp.json`.
Its `mcpServers.<name>` entries use `command`, `args`, optional `env` for stdio;
HTTP entries use `type: http`, `url`, and optional `headers`. Keep credentials
out of committed values. [MCP configuration](https://code.claude.com/docs/en/mcp).

Restart, inspect `/mcp`, and call `count_words` with
`{"text": "small useful example"}`; expect `3`. Adding an MCP server is separate
from naming its tools in a skill or agent.

## Before sharing

Run `python -m unittest tests.test_coding_agent_patterns tests.test_claude_patterns -v`.
Check `/skills`, `/agents`, and `/hooks` in a trusted interactive session.
Try missing skill arguments and both approval choices for a disposable operation.
These checks distinguish valid files from actual host behavior. Checked
2026-11-04; newer fields may require a newer Claude Code release.
