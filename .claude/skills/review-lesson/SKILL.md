---
name: review-lesson
description: Review named teaching notebooks for missing prerequisites and confusing learning steps.
---

Read the requested notebooks in the given order and the relevant project rules.
Use the audience and prerequisites from the request; otherwise assume basic Python.
Identify the first unexplained term, hidden state dependency, or conceptual jump.
For each material issue give a file, 1-based cell number, likely student question,
and the smallest improvement. Report strengths when useful; do not fill a quota.

Review only by reading unless execution was requested. Do not invoke services or
run kernels to check clarity. Return the review without edits unless editing is
part of the request. Delegation is optional, not required by this shared workflow.
