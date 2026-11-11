# Codex: setup and examples

Use branch **`agents/codex`**. This setup reproduces `agents/claude` at
`1775bf5`, with the permission differences explicitly chosen for Codex.
Start with [the concepts](coding-agent-guide.md), then use
[the authoring reference](create-codex.md) to create your own examples.

## What is installed

| Path | Behavior |
| --- | --- |
| `AGENTS.md` | Shared teaching conventions and Codex specialist routing |
| `.agents/skills/explain-code/SKILL.md` | Pirate explanation: idea, Mermaid map, then one part per turn |
| `.agents/skills/review-lesson/SKILL.md` | Review one lesson in the current conversation as a student, using Cap'n Groggy's pirate voice |
| `.agents/skills/review-lesson/scripts/run_copy.py` | Execute into an ignored copy without rewriting the source |
| `.codex/agents/lesson_reviewer.toml` | Review named lessons, or all teaching notebooks when none are named, using Cap'n Groggy's pirate voice |
| `.codex/agents/joke_writer.toml` | Attempt one actual write of five numbered jokes to root `jokes.txt`; stop on hook denial |
| `.codex/hooks/git_safety.py` | Deny recognizable destructive Git and staging/commit/push commands |
| `.codex/hooks/block_delete.py` | Deny detected file deletions and patch moves |
| `.codex/hooks/block_jokes_write.py` | Deny recognized writes to root `jokes.txt` |
| `.codex/hooks/notebook_context.py` | Remind the agent about import-layout checks after notebook edits |
| `.codex/hooks.json` | Register the four synchronous command hooks |
| `.codex/config.toml` | Enable subagents, cap spawned threads at two, retain the local MCP example |

The superseded `inspect-lesson` skill, `docs_reviewer` agent, and local `.claude`
configuration are removed. Models, credentials, trust decisions, and session
permissions remain on the host. The root model factory and `.env` are unchanged.

## Differences from Claude

| Claude reference | Selected Codex behavior |
| --- | --- |
| Ask for native approval before deletion | Deny detected deletion; the user removes files manually |
| Validate and ask before creating `jokes.txt`, then request deletion | Attempt the actual write; the hook denies it, so verification and deletion are skipped |
| Agent-specific tool allowlists | Keep responsibilities in instructions; inherit parent tools and permissions |
| Bash heredoc for notebook execution | A portable Python runner invoked from PowerShell or Bash |
| Pirate voice specified only in `explain-code` | Also use that persona in `review-lesson` and `lesson_reviewer`, as requested on November 11 |

`PreToolUse` does not support `permissionDecision: "ask"`. Returning it reports
an error and can let the operation continue. `PermissionRequest` handles approval
the host already requires; it does not create a prompt for an arbitrary action.
This setup uses `deny`, with no approval files or chat-based workaround.
[Official hooks documentation](https://learn.chatgpt.com/docs/hooks).

Subagents inherit parent tools and permissions. Instructions to avoid source
edits do not create a separate sandbox or Claude-equivalent tool restrictions.
[Official subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Activate in the intended Codex client

1. Open this checkout. Python 3.12+, Git, and uv must be on PATH.
2. Trust the project through Codex's project-trust flow. Review and trust the
   four exact hook definitions in the native `/hooks` browser. Changed hooks
   may need review again; untrusted hooks do not enforce this policy.
3. Start a fresh conversation. Confirm the two skills, two custom agents, and
   four hooks are discovered. Desktop, CLI, and VS Code can bundle different
   runtime versions; inspect the client you actually use.
4. For the optional existing MCP demo, prepare its environment once with
   `uv sync --frozen --project agent_demo` if it is not already installed.

Reading configuration in chat does not activate it. Preserve native trust review.

## Try the features

```text
$explain-code model_config.py - audience: basic Python
$review-lesson notebooks/langchain/01_create_agent.ipynb
Delegate a reading-only review of notebooks/langchain/09_context_and_state.ipynb to lesson_reviewer.
Tell me five programming jokes using joke_writer.
Call lesson_tools.count_words with text "small useful example".
```

The lesson reviewer reads before running, compares predicted and actual outputs,
then reports 1-based cell findings and the smallest useful fixes. A reading-only
request skips execution. Normal execution may invoke services or models used
by that lesson. It does not install packages, start Docker, or change `.env`.
Missing services or credentials are environment blockers, not lesson defects.

Copies retain the source's relative path under `.tmp/lesson-review/`. The kernel
runs in the source folder. Existing copies are preserved; the user removes them
manually before rerunning that lesson. A copy does not sandbox the notebook's
own code, which can still have side effects.

## Verify safely

```powershell
python -m unittest tests.test_coding_agent_patterns tests.test_codex_patterns tests.test_rag_lessons -v
uv run --no-sync --frozen --project agent_demo python agent_demo/check_server.py
```

Hook tests pass dangerous command strings as JSON to handlers; they never execute
those strings. Launcher tests use the configured Windows commands from `notebooks/`.
For a harmless native probe, ask Codex to run `Write-Output 'git reset --hard HEAD'`
or `Write-Output 'Remove-Item demo.txt'`. An active trusted hook should deny the
text; without the hook the command only prints it. Never use real destructive
operations as probes.

These detectors remain teaching examples. They can match quoted text and miss
indirect scripts, aliases, or unsupported tool paths. The deletion guard also
matches `git clean -nd`, despite its dry-run intent. Shell mutations mentioning
`jokes.txt` are detected conservatively; patch/native paths resolve against the
repository root. Hook process failures and untrusted definitions can leave calls
unguarded. The notebook reminder neither executes tests nor proves correctness.

## Verification record

On 2026-11-11, the corrected `joke_writer` was tested in fresh native session
`01a1c9a1-2f16-7611-be9e-0609c2e7c835`. The configured subagent submitted one
actual `apply_patch` Add File call containing five numbered jokes for root
`jokes.txt`. The active PreToolUse hook denied the call. The agent reported
the block without a retry or chat fallback. All 16 focused tests passed again.

The rebuild was checked against official documentation on 2026-11-10. Handler,
launcher, discovery, and runtime evidence are distinguished below. Old results
from the superseded configuration are not proof of this configuration.

- All 16 focused hook, launcher, documentation, and import-layout checks passed.
  Both skills passed the skill validator.
- A tiny synthetic notebook ran successfully through the portable runner. It
  proved source preservation, source-folder execution, error-cell reporting,
  continued execution after a cell error, and refusal to overwrite a review
  copy. The initial restricted-shell attempt hit a Windows Jupyter ACL error;
  the same smoke test passed with reviewed host permissions. No course notebook
  or course model service was executed for this check.
- The existing MCP smoke test passed modern and legacy stdio discovery, schema,
  counting, and invalid-argument checks after a Windows named-pipe permission
  retry. No package installation was needed.
- The VS Code bundled runtime `0.164.0-alpha.11.1` discovered both skills and
  all four hooks without project errors. The three changed definitions were
  reviewed and trusted individually in its native hook browser. A fresh
  discovery check reported all four definitions enabled and trusted.
- In native session `01a1c699-18b1-79c0-bbe4-23bd55462688`, all three harmless
  shell probes were denied by their respective Git, deletion, and joke-write
  guards. No denied operation was retried.
- Before the November 11 correction, the same session spawned the actual
  `joke_writer` and `lesson_reviewer` roles. The old writer returned five
  chat-only jokes; this does not validate the corrected write-attempt flow.
  The reviewer returned a reading-only notebook review
  with cell findings. No `jokes.txt` was created. The explanation skill produced
  the pirate introduction, a Mermaid map, a four-part route, and a question
  before continuing.

These are native runtime and terminal-interface checks, not a graphical VS Code
panel walkthrough. The notebook post-edit hook has handler and launcher
coverage; no teaching notebook was modified to trigger it. Existing unrelated
user-configuration warnings were outside this rebuild. Reload older sessions
to pick up the new agent definitions and project instructions.

### Manual cleanup

The deletion policy leaves generated verification artifacts for the user.
Only the following task-specific paths under the ignored `.tmp/` directory
belong to this rebuild:

- `codex-rebuild/` and `codex-schema/`
- `native_discovery.py`, `native-discovery-result.json`, and `runner_smoke.py`
- `runner-smoke-1d0d361d9f58420a8fa0ad5906ac07fc/`
- `runner-smoke-fd294c78ba7740be823dd1fd3326d5e9/`
- The two corresponding `runner-smoke-*` folders under `lesson-review/.tmp/`

Other existing `.tmp/` content is unrelated and should be preserved.
