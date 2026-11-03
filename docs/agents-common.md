# Common patterns: one workflow, two coding assistants

This is the shared base for three local branches. Read the
[general guide](coding-agent-guide.md) first for vocabulary and decision rules,
then the [Codex](agents-codex.md) or [Claude Code](agents-claude.md) instructions.
Repository prose is English, following the existing project convention.

## Branches and folders

| Branch | Contains | Does not activate |
| --- | --- | --- |
| `agents/common` | Shared instructions, two skills, four guides, portable checks | Custom hooks or specialist agents |
| `agents/codex` | Common base plus Codex TOML agents and JSON-registered hooks | Claude hooks |
| `agents/claude` | Common base plus Claude agents and permission hooks | Codex hooks |

The provider branches descend from the common branch. They are alternatives,
not successive steps to merge blindly. Shared changes belong on common;
merge that branch into both variants. Review provider settings separately.

The ready-to-open local clones are `../agentic_ai-common`,
`../agentic_ai-codex`, and `../agentic_ai-claude`, beside the original
repository. The three branches also exist in the original repository.
These are independent Git checkouts with the original repository as
their local `origin`; they do not change its current branch or dirty files.

Why clones here: native discovery in Codex 0.164.0-alpha.11.1 selected
the primary checkout's hook file for linked Git worktrees, even after
moving them outside the original folder. Independent clones avoid that
observed configuration collision. This is a local verification result,
not a claim about every future Codex version.

From the original root:

```powershell
git branch --list 'agents/*'
git log --oneline agents/common
git diff agents/common..agents/codex -- .codex
git diff agents/common..agents/claude -- .claude
code -n ../agentic_ai-codex
```

Open a chosen clone as its own IDE workspace root. Changes and commits
made there stay in that clone until explicitly pushed to the original
local repository. No branch was pushed to an external remote.

For common updates: commit in the common clone, then `git push origin
agents/common`. In a provider clone, run `git fetch origin agents/common`
and `git merge FETCH_HEAD`, then run that variant's tests. Inspect the
diff before publishing; branch switching and merging can change active
assistant configuration.

## Files that carry shared behavior

`AGENTS.md` contains project conventions. `CLAUDE.md` imports it with
`@AGENTS.md`, which gives an explicit compatibility route without maintaining
two copies of the rules. Current Claude can also discover `AGENTS.md` directly
when no competing project `CLAUDE.md` is present; the import remains useful
across versions. [Anthropic instruction-file documentation](https://code.claude.com/docs/en/memory).

The two skills use only basic `name`, `description`, and Markdown instructions:

| Skill | Inputs supplied in your request | Output |
| --- | --- | --- |
| `explain-code` | Paths; audience; focus; desired detail | Small example, execution trace, evidence |
| `review-lesson` | Notebook paths; audience; prerequisites; review/edit scope | Located learning obstacles and small corrections |

They appear in both `.agents/skills/` and `.claude/skills/` so both products
discover them. Those small files are intentionally byte-identical copies.
This avoids Windows symlink requirements and an installer or generator.
Edit both copies together; the test catches drift. Provider-specific metadata
belongs in the provider branches, not in this shared skill body.

## Concrete requests

Codex:

```text
Use $explain-code on model_config.py.
Audience: basic Python. Focus: profile selection. Give one input/output example.
Read only; do not call a provider.
```

Claude Code:

```text
/explain-code model_config.py; audience=basic Python; focus=profile selection; read only
```

Both requests convey the same task. Semicolon-separated labels here are
ordinary prompt text, not a validated parser or universal CLI flags. Omitted
audience defaults to basic Python because the skill says so.

For a lesson review:

```text
Use review-lesson for notebooks/langchain/01_create_agent.ipynb.
Audience: first-time agent builder. Identify the first confusing step.
Return file and cell references. Do not edit or execute.
```

Expected result: a located question such as "Where does this model name come
from?" and a concrete correction, if the actual lesson supports that finding.
A review is not proof that the notebook runs.

## Keep application configuration separate

The course's `models.toml`, `.env`, and `model_config.py` configure examples
inside the course. They do not configure the coding assistant editing this
repository. Selecting the Anthropic provider there does not enable Claude
Code hooks. Each assistant has its own host, project configuration, and trust.

No clone inherits the original root's virtual environment automatically.
For these standard-library-only checks, Python 3.11+ on PATH is sufficient:

```powershell
python -m unittest tests.test_coding_agent_patterns -v
```

Run course-specific tests with the course dependencies installed, or use the
original repository's existing Python executable by absolute path. Avoid
installing a second environment merely to validate these configuration examples.

## Shared maintenance workflow

1. Give a task a scope, outcome, and observable acceptance condition.
2. Select the smallest useful mechanism from the general guide.
3. Inspect the actual diff, including new/untracked files.
4. Run focused checks, then required repository checks.
5. Distinguish static validation from a live host test.
6. Commit the reviewed scope; keep secrets and local session files out of Git.

All four guides are present in every branch for convenient comparison.
A provider guide names files that exist on that provider's branch; switch to
that checkout before following its commands. Documentation was researched on
2026-11-03. Each provider guide records its validation and remaining human steps.

## Verification

The shared checkout passed 23 repository tests on 2026-11-03 using
the original repository's existing Python environment. The three
portable tests also passed on system Python 3.14 without packages.
No live model or GPU workload was used. Provider results are in
their guides; approval UI acceptance is explicitly separate.
