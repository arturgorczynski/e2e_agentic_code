---
name: inspect-lesson
description: Explicitly delegate a notebook learning-flow review to lesson-reviewer.
argument-hint: "<notebook-path> <audience>"
disable-model-invocation: true
context: fork
background: false
agent: lesson-reviewer
---

Review notebook $0 for audience $1.
If either argument is missing or a placeholder remains unresolved, request the
missing value before reviewing. Read the notebook without executing or editing.
Return material learning obstacles with cell references and small corrections.
