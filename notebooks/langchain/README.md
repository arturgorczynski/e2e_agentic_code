# LangChain lessons

Run the numbered lessons in order. Lessons 01–08 introduce agents, memory, tools,
structured output, runtime context and streaming. [09](09_context_and_state.ipynb)
follows a support ticket across live Ollama agent turns: automated replacement,
urgency changes, resolution, safety review and attempted identity overrides.
It shows context, state and actual tool calls, then offers an editable workbench.
Run it with `gemma4:12b` available in Ollama; orders and actions are local fakes.
The model uses the shared root factory and configuration. [10](10_custom_middleware.ipynb)
builds one custom middleware from scratch.

The [advanced middleware workshop](06_middlewares/README.md) contains the longer
set of built-in middleware lessons and a broad custom middleware reference. All
notebooks use the root project environment and model factory when a real model
is needed. Generated memory, tool logs and verification artifacts are local
exercise data and are excluded from Git.
