---
name: review-lesson
description: Review one teaching notebook as a student would. Use it on the notebook the user names, or the one being written or edited in this conversation. Runs a copy of it, checks whether the idea, markdown, code and outputs make the lesson clear, and returns per-cell findings with the smallest fix.
---

# Review one lesson as a student

This is the single-lesson, in-conversation version of the `lesson-reviewer`
agent. Use it while a lesson is being written or changed, so feedback arrives
before moving on.

## 1. Pick the lesson

- Use the notebook the user named.
- Otherwise use the notebook being created or edited in this conversation, or
  the notebook open in the IDE. Say which one you picked.
- If more than one could be meant, ask which one. Review only one notebook. For
  a whole series, suggest the `lesson-reviewer` agent.

## 2. Become the student

Use the audience the user gives. Otherwise you are a student with basic Python
(functions, classes, dicts, loops, imports) and basic AI ideas (LLM, prompt,
token, API call). You know only what earlier lessons in the same folder teach.
Read `AGENTS.md` for the repository's teaching rules.

## 3. Read before running

- From the title and first markdown cell, write down the idea the lesson
  promises.
- For each cell, note what you expect it to do or print, and any term or object
  used before it is explained.

## 4. Run a copy

Execute the lesson into `.tmp/lesson-review/` with the command in
`.claude/agents/lesson-reviewer.md`. The source notebook is never edited by the
run. Compare each output with what you expected. A missing API key, a stopped
model server or Docker is an environment blocker, not a lesson finding. Skip
the run if the user asked for a reading-only review.

## 5. Judge

1. **Idea:** Can the student state the main idea in two sentences at the end?
   Does the markdown say why it matters before the code?
2. **Sequence:** Does each cell build on the one before, with no jump or hidden
   prerequisite?
3. **Code:** Is each cell easy to follow, without needless helpers, dense
   one-liners or too much in one cell?
4. **Evidence:** Do the outputs show the effect, and does the markdown say what
   to look for in them?
5. **Conventions:** Are the imports in the first code cell and is everything in
   English, as `AGENTS.md` requires?

Report only obstacles that would really slow or mislead this student. If the
lesson is clear, say so.

## 6. Report

- **Lesson**, run status (`ran clean`, `cell N failed`, `blocked: <reason>`) and
  the idea in one sentence, as the student understood it.
- **Verdict:** `clear`, `minor gaps` or `needs work`.
- **Findings**, most serious first: 1-based cell number, the student's
  question, why it matters, and the smallest fix.
- What works well, in one or two lines, so it survives later edits.

Do not edit the notebook unless the user asks. Afterwards, offer to apply the
fixes and to delete the executed copy.
