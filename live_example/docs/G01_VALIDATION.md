# G01 validation

Verified on 2026-10-15 on Windows with Python 3.12.12 and uv 0.10.2.
Scope: independent package foundations, not a running company assistant.

## Results

| Requirement | Evidence | Result |
| --- | --- | --- |
| Independent package and configuration | `pyproject.toml`, `uv.lock`, `.python-version`, `acme/`, `.env.example`, `models.toml`, tests, docs, and three data directories | Present |
| Fresh dependency installation | `uv sync --locked`, then a second `uv sync --locked --offline` in an external clean copy | Passed; 53 packages installed in each environment |
| CLI entry point | `uv run --locked --offline acme --help` and `acme --version` in the clean copy | Passed; version `acme 0.1.0` |
| Independent imports | Clean-copy package-path check plus static import checks; isolated subprocess CLI tests from another working directory | Passed |
| Import has no runtime activity | Fresh-process audit hook rejects configuration reads, file writes, network operations, process creation, directory mutations, and SQLite connections; thread startup is rejected and environment changes are checked | Passed for all four application modules |
| Model factory | All four real provider classes constructed using dummy credentials with network/DNS blocked | Passed; no inference performed |
| Configuration ownership | Tests for missing local config, ancestor `.env` rejection, environment precedence, reload, explicit profile/model/role selection | Passed |
| Reuse inventory | `docs/reuse_inventory.md` records adaptations and later candidates | Present |
| Separate discovery | Parent import-layout walker excludes `LangTutorial/` and `live_example/`; pytest paths are scoped; standalone unittest discovery targets only its tests | Boundary test passed |
| Standalone tests and lint | 11 unittest checks, `ruff check .`, and formatting check | Passed |

The lock resolves LangChain 1.4.6, langchain-ollama 1.1.0,
langchain-openai 1.7.2, langchain-anthropic 1.7.6, and Ruff 0.17.1.
All resolved versions and package hashes are recorded in `uv.lock`.

## Clean-copy check

Run from `live_example/` after `uv sync --locked`:

```powershell
uv run --locked python scripts/verify_independence.py
```

The script copies only named project files/directories, excludes credentials and
environments, clears inherited Python/project path overrides, installs from the
lockfile using the warmed uv cache, runs help/version/tests/lint, checks the imported
package location, and confirms the lockfile did not change. The temporary copy is
retained for inspection; the command prints its location. It creates a new environment
without copying the original `.venv` or requiring the original checkout on `sys.path`.

The verified external copy was:

```text
C:\Users\Komputer\AppData\Local\Temp\acme-g01-w_7oqai_
```

Its package path resolved to `acme/__init__.py` inside that copy. All 11 tests and
Ruff passed there. Copying dependencies between drives caused uv to fall back from
hardlinks to ordinary file copies; installation completed successfully.

## Parent course checks

Command from the parent repository:

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

The run executed 15 test methods: 12 passed and three had failures/errors concerning
the existing `notebooks/06_middlewares/01_summarization.ipynb`:

- Its first code cell defines and registers a `tall` cell magic, violating the dedicated
  import-cell convention and requiring an IPython context during header execution.
- A later `%%tall 700` cell is not accepted by the current plain-Python syntax check.

G01 did not modify that notebook. The new discovery-boundary check and Python module
import-layout check passed. The course's full check suite must not be reported green.

## Environment notes and limits

- The sandbox initially blocked Windows temporary fixture writes. The same offline
  tests passed with normal host temp-directory permissions; no test was disabled.
- PyPI access was required to resolve and initially download dependencies. The
  external clean-copy installation then succeeded offline with those cached packages.
- No local or paid model inference, model-server startup, Docker execution, database
  seeding, company-data download, UI, or authentication journey was performed.
- macOS/Linux execution and Python 3.13 were not exercised. The verified interpreter
  is the project's selected Python 3.12.
- G02 through G13 remain pending. Data directories intentionally contain only scope
  notes, and the CLI intentionally provides only help and version.
