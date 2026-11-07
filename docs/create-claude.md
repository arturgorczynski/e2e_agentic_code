# Claude Code: create skills, subagents, hooks, and tools

**Use branch `agents/claude`.** This is the short authoring reference; see
[setup and working examples](agents-claude.md) for activation and native approvals.
Use [the concepts](coding-agent-guide.md) for the shared mental model.

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

Keep skills in `.claude/skills` only. This branch's `inspect-lesson` demonstrates
native delegation; the two simpler skills remain short procedures.

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
do not. A specifier in `disallowedTools` removes the whole tool. Inspect `/context all` and try a named delegation
after creating it; v2.1.311 removed the `/agents` wizard. [Agent reference and value limits](https://code.claude.com/docs/en/sub-agents).

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

## 4. Tool: the working local MCP example

The committed [server](../agent_demo/server.py) uses the official MCP Python
SDK, with dependencies pinned by [uv.lock](../agent_demo/uv.lock):

```python
from mcp.server import MCPServer

server = MCPServer("lesson_tools")

@server.tool()
def count_words(text: str) -> int:
    """Count whitespace-separated tokens in text."""
    return len(text.split())

if __name__ == "__main__":
    server.run()
```

`@server.tool()` registers the function. Its function name is the tool name,
docstring describes selection, type hints generate the JSON argument/result
schemas, and `server.run()` serves stdio. Add another typed function with this
decorator to expose another operation. The function's Python arguments are
**tool inputs**, not fields in the host's MCP configuration.

Run once from this checkout:

```powershell
uv sync --frozen --project agent_demo
uv run --frozen --project agent_demo python agent_demo/check_server.py
```

This uses `agent_demo/.venv`, separately from the course environment. The
configured PowerShell launcher resolves the Git root, starts `uv run --frozen`,
and runs `agent_demo/server.py`. It works from the root or a subdirectory, needs
no machine-specific absolute path, and targets Windows VS Code. On another OS,
replace the launcher with that OS's executable and absolute server path.
Do not write logs to stdout: it carries MCP messages.

Registration is already in `.mcp.json` under
`mcpServers.lesson_tools`: `type: stdio`, `command`, and `args` start PowerShell.
Optional `env` supplies server environment values. HTTP uses `type: http`,
`url`, and optional `headers`. Scope controls storage: `project` is `.mcp.json`,
`local` is private to this project on this machine, and `user` applies across
projects. `claude mcp add --transport stdio --scope project NAME -- COMMAND ARGS`
is the equivalent registration CLI shape. Keep secrets out of committed values.
`${CLAUDE_PROJECT_DIR}` in hook args is not a promise that the same interpolation
works in MCP launch args; this example resolves its root explicitly instead.
[MCP host fields](https://code.claude.com/docs/en/mcp).

Tool example: `count_words({"text": "small useful example"})` returns `3`.
There are no custom MCP resources, prompts, authentication, or server writes in
this example. Host-specific MCP tool display names may include a server prefix.
[Official SDK](https://py.sdk.modelcontextprotocol.io/get-started/real-host/).

## Before sharing

Run the branch tests and MCP smoke test in the [setup guide](agents-claude.md).
Then check discovery and try the skill, specialist, and harmless tool in the
actual extension. Synthetic handler tests do not establish native approval UI
behavior. These are the useful creation fields; vendor references cover the
remaining advanced options. Documentation checked 2026-11-07.
