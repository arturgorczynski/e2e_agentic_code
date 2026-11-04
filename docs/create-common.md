# Common: create a reusable coding workflow

**Branch: `agents/common`.** Start here for portable conventions and skills.
Using a host-specific feature? Open [Codex](create-codex.md) on `agents/codex`
or [Claude Code](create-claude.md) on `agents/claude`.

## Choose the smallest useful building block

| You need | Create | What it does |
| --- | --- | --- |
| A rule for every task | `AGENTS.md` | Adds repository instructions; this repo's `CLAUDE.md` imports it |
| A repeatable procedure | A skill directory with `SKILL.md` | Loads instructions when the task needs them |
| A separate specialist | A host-specific subagent definition | Gives delegated work its own instructions/context |
| Code at a lifecycle event | A host-specific hook | Inspects a real event and returns a supported decision/context |
| A callable capability | A script, or an MCP server tool | Executes code with defined inputs and outputs |

A skill describes **how to work**. A tool performs **one operation**. A hook
reacts **when an event happens**. Writing a new YAML key does not implement any
of these behaviors. Instructions also do not change the host's permissions.

## Create a portable skill

Create `.agents/skills/summarize-file/SKILL.md`, then copy it unchanged to
`.claude/skills/summarize-file/SKILL.md` for this repository's two-host layout:

```markdown
---
name: summarize-file
description: Summarize a named repository file for a beginner. Use for explanations.
---

Read the file named in the request. Ask for its path if missing.
Return its purpose, one concrete input/result, and the relevant line references.
Keep the answer under 200 words. Do not edit or execute the file.
```

Try `$summarize-file model_config.py` in Codex or
`/summarize-file model_config.py` in Claude Code. Expected result: a short,
source-grounded explanation. The path is task input; it is not a metadata field.

| Standard frontmatter field | Type / purpose |
| --- | --- |
| `name` | Required string; match the folder; 1-64 lowercase letters/digits/hyphens; no edge or doubled hyphens |
| `description` | Required nonempty string, up to 1,024 characters; say when to use it |
| `license` | Optional string naming licensing terms |
| `compatibility` | Optional string, up to 500 characters, describing prerequisites |
| `metadata` | Optional string-to-string map for your own catalog data |
| `allowed-tools` | Experimental tool pre-approval string; behavior depends on the host |

These are the [Agent Skills format fields](https://agentskills.io/specification),
not a promise that every host enforces every field. Our portable copies use only
`name` and `description`. Put inputs, steps, output format, and missing-input
handling in the Markdown body. Put optional helpers in `scripts/`, detail in
`references/`, and templates in `assets/`; reference them from the body.

## Create a real tool when instructions are insufficient

For a single local operation, an ordinary script called through the shell may
be enough. Use MCP when you want a named tool with structured arguments that
either host can discover. Save this **optional SDK v2 template** as
`tools/text_tools.py`:

```python
from mcp.server import MCPServer

mcp = MCPServer("text-tools")


@mcp.tool()
def count_words(text: str) -> int:
    """Count whitespace-separated words in supplied text."""
    return len(text.split())


if __name__ == "__main__":
    mcp.run()
```

The function name becomes `count_words`, its docstring describes the operation,
and `text: str` creates a required string argument. Input
`{"text": "small useful example"}` returns `3`. The host launches this stdio
server; it is not an HTTP service. See the [official Python SDK](https://py.sdk.modelcontextprotocol.io/)
and [host launch contract](https://py.sdk.modelcontextprotocol.io/get-started/real-host/).

| MCP tool descriptor field | Meaning |
| --- | --- |
| `name`, `description` | Operation identity and selection guidance |
| `inputSchema` | JSON Schema: `type: object`, argument `properties`, and `required` names |
| `outputSchema` | Optional schema for structured results |
| `title`, `icons` | Optional presentation metadata |
| `annotations` | Optional behavior hints; not enforced permissions |

The SDK generates the basic descriptor. Its Python v2 attributes use snake_case;
the [wire protocol](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
uses names such as `inputSchema`. Business argument names such as `text` belong
inside that schema, not in `SKILL.md` frontmatter. Connect the template using the
MCP section in your host's authoring guide. No server or SDK is installed by
these documentation examples.

## Keep the repository manageable

1. Add shared instructions/skills on `agents/common`; keep mirrored skills equal.
2. Merge common changes into both provider branches. Keep native settings there.
3. Keep credentials, personal model choice, and machine paths out of shared config.
4. Test one matching request, one unrelated request, and missing/invalid input.
5. Check the diff, then verify discovery in a fresh host session.

Run the existing portable checks with Python 3.11+:

```powershell
python -m unittest tests.test_coding_agent_patterns -v
```

More detail: [shared files and branch maintenance](agents-common.md) and
[when to choose each mechanism](coding-agent-guide.md). Field references checked
2026-11-04; runtime acceptance is separate from parsing documentation examples.
