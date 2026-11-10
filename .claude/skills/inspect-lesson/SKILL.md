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
If the notebook is missing or a placeholder remains unresolved, request the
missing value before reviewing. If only the audience is missing, use your
default student. Execute a copy, never edit the source, and return material
learning obstacles with cell references and small corrections.
