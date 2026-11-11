# Codex: create skills, subagents, hooks, and tools

**Use branch `agents/codex`.** This is the short authoring reference; see
[setup and working examples](agents-codex.md) for activation and verification.
Use [the concepts](coding-agent-guide.md) for the shared mental model.

## 1. Skill: a reusable procedure

Create `.agents/skills/summarize-file/SKILL.md`:

```markdown
---
name: summarize-file
description: Explain a named repository file with one concrete input and result.
---

Read the requested file. If no path was given, ask for it.
Return its purpose, the main execution steps, and source line references.
Do not edit or execute the file.
```

Invoke: `$summarize-file model_config.py`. The YAML header supplies **required
strings** `name` (identity) and `description` (selection); the body supplies the
procedure. Describe your own inputs in the body. Codex's documented format does
not provide Claude's `$ARGUMENTS` substitution or `context: fork` switch.

Optional host metadata goes in **`agents/openai.yaml` inside the skill folder**:

```yaml
interface:
  display_name: "Summarize a file"
  short_description: "Explain a file with a concrete example"
  default_prompt: "Use $summarize-file to explain model_config.py."
policy:
  allow_implicit_invocation: false
```

| Recognized path in `agents/openai.yaml` | Value / function |
| --- | --- |
| `interface.display_name`, `interface.short_description` | Strings for the skill picker |
| `interface.default_prompt` | Suggested invocation text |
| `interface.icon_small`, `interface.icon_large` | Asset paths relative to the skill |
| `interface.brand_color` | Hex color string |
| `policy.allow_implicit_invocation` | Boolean; `false` makes invocation explicit; default `true` |
| `dependencies.tools[]` | Tool dependency objects: `type: mcp`, `value`, `description`, `transport`, `url` |

Dependencies describe needed connections; they do not define tool argument
schemas. Optional `metadata` is descriptive; keep the required `name` and `description`.
Use host permissions for access control; do not assume a skill header creates
a sandbox. [Official skills reference](https://learn.chatgpt.com/docs/build-skills).

## 2. Subagent: a separate specialist

Create `.codex/agents/file_reviewer.toml`:

```toml
name = "file_reviewer"
description = "Review one file for concrete correctness problems."
developer_instructions = """
Read the named file and relevant callers. Do not edit.
Return confirmed problems with line references and a minimal correction.
"""
```

| Agent TOML field | Type / function |
| --- | --- |
| `name`, `description`, `developer_instructions` | Required strings: identity, selection, instructions |
| `model` | Optional available model ID; omission preserves resolved inheritance |
| `model_reasoning_effort` | Optional model-supported effort, e.g. `low`, `medium`, `high` |
| `model_reasoning_summary`, `model_verbosity` | Optional model output preferences |
| `features.shell_tool`, `features.apps`, `features.plugins`, `features.memories`, `features.request_permissions_tool` | Boolean; `false` disables that capability |
| `skills.config`, `skills.bundled.enabled`, `skills.include_instructions` | Selectively disable skills or their automatic instruction block |

Request: `Delegate a read-only review of model_config.py to file_reviewer.`
The agent inherits parent permissions and MCP servers. `sandbox_mode`,
`approval_policy`, and `mcp_servers` in this file do not override the parent.
In `.codex/config.toml`, `[agents]` supports `enabled` (boolean),
`max_concurrent_threads_per_session` (spawned-thread limit),
`default_subagent_model`, `default_subagent_reasoning_effort`, and
`interrupt_message`. Our branch uses a limit of two.
[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents);
[accepted config values](https://learn.chatgpt.com/docs/config-file/config-reference).

## 3. Hook: code at an event

Add a handler under `.codex/hooks/` and register it in `.codex/hooks.json`.
This complete example registers the Git handler already shipped on this branch:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "^(Bash|exec_command)$",
      "hooks": [{
        "type": "command",
        "command": "python -I \"$(git rev-parse --show-toplevel)/.codex/hooks/git_safety.py\"",
        "commandWindows": "python -I \"$(git rev-parse --show-toplevel)/.codex/hooks/git_safety.py\"",
        "timeout": 10,
        "statusMessage": "Checking Git command"
      }]
    }]
  }
}
```

Merge new event entries into the existing file; preserve the notebook handler.

| Field / input | Function |
| --- | --- |
| Event key | `PreToolUse`: before a call; `PostToolUse`: after its result |
| `matcher` | Regex over tool names for these events |
| `type`, `command` | `command` handler and shell launcher |
| `commandWindows` | Windows launcher override |
| `timeout`, `statusMessage` | Seconds; progress label |
| `async`, `additionalContextLimit` | Optional background execution; context preview limit |
| stdin `tool_name`, `tool_input` | Pending tool identity and actual arguments |

This branch additionally registers `block_delete.py` and `block_jokes_write.py`.
They deny their recognized operations; they never ask for permission. The joke
agent attempts one real write to root `jokes.txt`; the hook denies it. The agent
reports the block and stops without printing jokes or retrying. The notebook
reminder is the fourth handler.

Read JSON from stdin; print one JSON object and exit 0. `{}` continues normal
handling. To deny, return `hookSpecificOutput` with `hookEventName: PreToolUse`,
`permissionDecision: deny`, and `permissionDecisionReason`. `allow` can carry
supported `updatedInput`; `additionalContext` adds guidance. **`ask` is currently
unsupported** and can let the call continue after a hook error. Use synchronous
handlers for decisions. Trust the project and each hook definition via `/hooks`.
[Full event/output contract](https://learn.chatgpt.com/docs/hooks).

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

Registration is already in `.codex/config.toml` under
`[mcp_servers.lesson_tools]`: `command` and `args` start PowerShell; the server
has `enabled_tools = ["count_words"]`, `startup_timeout_sec = 30`, and
`tool_timeout_sec = 10`. Other recognized options include `cwd`, `env`,
`env_vars`, `enabled`, and `disabled_tools`. Approval options are
`default_tools_approval_mode` and `tools.<name>.approval_mode`, with values
`auto`, `prompt`, `writes`, `approve`; `writes` prompts for tools not marked
read-only. This example leaves that decision at the host default. HTTP uses `url` and, if needed,
`bearer_token_env_var` rather than a stdio command. Keep secrets out of Git.
[MCP host fields](https://learn.chatgpt.com/docs/extend/mcp).

Tool example: `count_words({"text": "small useful example"})` returns `3`.
There are no custom MCP resources, prompts, authentication, or server writes in
this example. Host-specific MCP tool display names may include a server prefix.
[Official SDK](https://py.sdk.modelcontextprotocol.io/get-started/real-host/).

## Before sharing

Run the branch tests and MCP smoke test in the [setup guide](agents-codex.md).
Then check discovery and try the skill, specialist, and harmless tool in the
actual extension. Synthetic handler tests do not establish native approval UI
behavior. These are the useful creation fields; vendor references cover the
remaining advanced options. Skills, agent schema, and hook contracts were
rechecked against official documentation on 2026-11-10.
