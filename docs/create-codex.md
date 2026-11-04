# Codex: create skills, subagents, hooks, and tools

**Use branch `agents/codex`.** This is the short authoring reference; see
[setup and working examples](agents-codex.md) for activation and verification.
Use [Common](create-common.md) for shared rules and the tool implementation.

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
schemas. Standard optional metadata is listed in [Common](create-common.md).
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

Read JSON from stdin; print one JSON object and exit 0. `{}` continues normal
handling. To deny, return `hookSpecificOutput` with `hookEventName: PreToolUse`,
`permissionDecision: deny`, and `permissionDecisionReason`. `allow` can carry
supported `updatedInput`; `additionalContext` adds guidance. **`ask` is currently
unsupported** and can let the call continue after a hook error. Use synchronous
handlers for decisions. Trust the project and each hook definition via `/hooks`.
[Full event/output contract](https://learn.chatgpt.com/docs/hooks).

## 4. Tool: connect callable code through MCP

First create the [Common tool template](create-common.md). For a local trial,
merge this into your user `~/.codex/config.toml`, replacing the absolute path:

```toml
[mcp_servers.text_tools]
command = "uv"
args = ["run", "--isolated", "--no-project", "--with", "mcp>=2,<3", "python", "C:/path/to/repo/tools/text_tools.py"]
enabled_tools = ["count_words"]
```

`command` starts the server; `args` is argv, not shell text. Optional fields:
`cwd`, `env`, `env_vars`, `enabled`, `startup_timeout_sec`, `tool_timeout_sec`,
`enabled_tools`, `disabled_tools`. HTTP servers use `url` instead of a stdio
launcher, with `bearer_token_env_var` when needed. Keep secrets in the host
environment. Team config can live in `.codex/config.toml` once its launcher is
portable. [MCP configuration](https://learn.chatgpt.com/docs/extend/mcp).

The trial launcher downloads an isolated SDK environment on first use.
After restarting, inspect `/mcp` and ask to call `count_words` with
`{"text": "small useful example"}`; expect `3`.

## Before sharing

Run `python -m unittest tests.test_coding_agent_patterns tests.test_codex_patterns -v`.
Then check `/skills`, agent discovery, and trusted `/hooks` in the actual host;
try the skill once and verify its output. For a new hook, test both a matching
and non-matching input before live use. This page lists the useful creation
fields; linked vendor references cover advanced settings. Checked 2026-11-04.
