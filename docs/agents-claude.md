# Claude Code branch: native approval and a scoped writer

Creating your own? Start with the [short authoring reference](create-claude.md).

Use `agents/claude`. It includes the [common base](agents-common.md) plus
Claude-specific settings and agents. "Claude Code" is the coding host;
an Anthropic model used by the course is a separate thing.

## Files and responsibilities

| File | Role |
| --- | --- |
| `CLAUDE.md` | Import shared `AGENTS.md` |
| `.claude/skills/explain-code/SKILL.md` | Shared explanation workflow |
| `.claude/skills/review-lesson/SKILL.md` | Shared review workflow |
| `.claude/skills/inspect-lesson/SKILL.md` | Claude argument substitution and delegated review |
| `.claude/agents/lesson-reviewer.md` | Reviewer with read/search tools |
| `.claude/agents/joke-writer.md` | Writer with its own PreToolUse hook |
| `.claude/settings.json` | Global commit/deletion approval hook |
| `.claude/hooks/ask_before_change.py` | Recognize commit/deletion proposals and return ask |
| `.claude/hooks/approve_jokes.py` | Constrain joke writes and request consent |
| `tests/test_claude_patterns.py` | Hook and configuration checks |

## Global approvals

The project registers a before-tool handler for shell tools and recognizable
commit/delete tool names. It returns native `ask` for commit commands and
recognized deletion operations. Reads and ordinary edits return `{}` and
follow normal permission handling. The settings keep Manual/default permissions.

The detector covers direct `git commit`/`commit-tree`, `git rm`,
`git clean`, `rm`, `rmdir`, `del`, `Remove-Item`, common Python/.NET
deletion calls, and Delete File patch markers. This is deliberately conservative
text inspection, with false positives possible in quoted examples. It cannot
prove that an arbitrary script, alias, or external connector never deletes
anything. Native permissions and review remain necessary.

The handler returns this decision shape with an operation-specific reason:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "Review the proposed commit or deletion."
  }
}
```

The runtime displays the prompt, waits for the user's decision, and executes
or rejects the pending call. The parent model does not record consent or retry
a simulated approval. Claude supports `ask`; Codex currently does not.
[Claude hook reference](https://code.claude.com/docs/en/hooks),
[Codex hook reference](https://learn.chatgpt.com/docs/hooks).

## The joke writer owns its hook

Ask in a trusted interactive session:

```text
Use joke-writer to generate five fresh English programming jokes.
Let its own hook request permission to create root jokes.txt.
Wait for the result. Do not write the file yourself.
```

The agent can use `Read` and `Write`, not a shell or the Edit tool.
Its frontmatter registers `approve_jokes.py` only for its `Write` calls.
The script checks the actual `file_path` against this checkout's root
`jokes.txt`, denies other paths and an existing target, checks that content
contains five numbered nonempty lines, and returns `ask` for a valid proposal.
The script does not write the file. Claude's Write tool does so after approval.

```text
joke-writer proposes Write(file_path, content)
  -> its own hook validates the target/content
  -> ask -> native permission prompt
  -> Yes: the pending Write executes
  -> No: Write is rejected; agent reports refusal and stops
```

No transcript scan, receipt file, or parent-agent permission relay exists.
The existing-file check is a preflight check, not an atomic filesystem lock;
keep one writer for this demonstration.

Project-agent hooks require workspace trust. An untrusted agent may still run
while its hooks are skipped, so trust and inspect this folder before testing.
Current interactive Claude can surface subagent prompts in the main session.
Unattended print/SDK runs need a permission host; they cannot assume a human
can answer. [Claude subagent behavior](https://code.claude.com/docs/en/sub-agents).

## Configuration arguments used here

| Argument | Example's purpose |
| --- | --- |
| `permissions.defaultMode: default` | Keep manual permission handling |
| `matcher` | Select a tool name with a regex |
| `type: command` | Run a local hook program |
| `command: python` | Resolve the interpreter on PATH |
| `args` | Direct argv, including the project script path |
| `timeout: 10` | Bound hook execution |
| `onFailure: block` | Hook crash/timeout blocks the pending operation |
| `name`, `description` | Agent identity and selection guidance |
| `tools: Read, Grep, Glob` | Reviewer's available built-in tools |
| `model: inherit` | Reuse the session model |
| `permissionMode: default` | Joke agent uses normal manual permissions |
| `hooks` inside agent frontmatter | Callback scoped to that agent |

Direct `args` form avoids shell quoting differences. The first argument
is `-I`, isolating Python from inherited Python environment variables. The path placeholder
`${CLAUDE_PROJECT_DIR}` is expanded by Claude. Use a real Python executable,
not a batch wrapper on Windows. `onFailure` requires a recent Claude version;
the installed `2.1.311` is newer than its documented `2.1.295` introduction.
No global configuration is installed.
[Hook command fields](https://code.claude.com/docs/en/hooks#command-hook-fields),
[Settings scope](https://code.claude.com/docs/en/settings).

## Skill arguments and name mapping

The portable skills accept ordinary task text:

```text
/explain-code model_config.py; focus=profile selection; audience=basic Python
/review-lesson notebooks/langchain/01_create_agent.ipynb; read only
```

The additional `inspect-lesson` example uses `argument-hint`,
`disable-model-invocation: true`, `context: fork`, and
`agent: lesson-reviewer`. Its body refers to `$0` (path) and `$1` (audience):

```text
/inspect-lesson notebooks/langchain/01_create_agent.ipynb "basic Python"
```

`argument-hint` is UI guidance, not a schema validator. `$ARGUMENTS` would
insert the full argument string; indexed placeholders select positional
values. The explicit-only setting prevents automatic invocation, while
`context: fork` runs this workflow with the named agent.
[Claude skills](https://code.claude.com/docs/en/skills).

| Codex example | Claude counterpart | Transfer rule |
| --- | --- | --- |
| `$review-lesson` | `/review-lesson` | Shared body, different invocation |
| `lesson_reviewer.toml` | `lesson-reviewer.md` | Re-author metadata; do not just rename |
| `developer_instructions` | Markdown agent body | Same responsibility can be expressed |
| `commandWindows` launcher | `command` plus `args` here | Different launcher schema |
| Codex `deny` | Claude `deny` or `ask` | Test the target runtime's decision contract |
| Parent permission inheritance | Claude agent tool allowlist | Similar intent, different control surface |

## Run and accept the examples

```powershell
cd ../agentic_ai-claude
python -m unittest tests.test_coding_agent_patterns tests.test_claude_patterns -v
claude --permission-mode manual
```

Inside Claude, accept workspace trust, inspect `/hooks`, and inspect
`/agents`. Check the joke writer has only the intended tools and its own hook.
Review the displayed command before answering any prompt.

Use a disposable file for deletion and a dry-run commit proposal to test the
global prompts. A dry-run still asks because it contains `git commit`.
For the writer, start with no root `jokes.txt`, reject once and verify absence,
then invoke again and approve once. Check exactly five jokes were created.
If the file already exists, the expected behavior is denial, not overwrite.

In `claude -p`, a prompt may be denied without an interactive permission host.
Do not add permission-bypass flags to make a demonstration appear successful.

## Verification

Documentation researched on 2026-11-03; installed Claude Code: `2.1.311`.
The branch passed 30 repository tests on Python 3.12; its ten
portable/hook tests also passed on Python 3.14. The tests cover commit
and deletion requests in both shells, connector names, malformed input,
scope/content validation, existing-file preservation, and the actual
direct-argv launcher. Markdown frontmatter was parsed with PyYAML and
the joke agent's restricted tools and hook path were checked.

`claude doctor` in the final clone found no installation issues, loaded
organization policy from Anthropic, and reported no managed settings for
this organization. An earlier sandboxed diagnostic could not reach that
endpoint; the normal diagnostic resolved it. No live model was called.

Remaining user acceptance: launch the command above, trust the folder,
inspect `/hooks` and `/agents`, then reject and approve the disposable
operations described above. Those native Yes/No interactions have not
been claimed as tested. This setup never asks Codex to relay consent.
