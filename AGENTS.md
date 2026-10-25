# Repository conventions

This repository teaches agentic coding to readers with limited prior exposure.
Start each lesson with the idea, then explain the code in a clear sequence.
Keep examples focused and avoid unnecessary helpers, output and abstraction.
- Write all repository Markdown, teaching notebook content, code comments,
  prompts, example text, and user-facing strings in English. Keep proper names,
  external source titles, and required protocol values as written.

- In every teaching notebook, put all imports in one dedicated first code cell.
  Only the minimal project-path bootstrap may share that cell. Model creation,
  configuration display, function/class definitions and examples belong in later cells.
- Never add imports to example cells or inside functions/classes/conditionals.
  Python modules also keep imports in their top-level import block, after a
  module docstring and minimal path bootstrap if required.
- Preserve the shared root model factory and the single root `.env` configuration.
- Check the import-layout tests after changing notebooks or Python modules.
- Do not rewrite historical executed notebooks/logs under `artifacts` or
  third-party environments/caches when refactoring teaching source.
- Keep Live Example's root README as an overview and maintain focused READMEs
  for its main components. Remove temporary files produced during development.
- Prefer local execution. Ask before adding Docker to the normal workflow.
