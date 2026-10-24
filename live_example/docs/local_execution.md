# Local analysis and optional generated Python

The default tool, `analyze_workspace`, runs **predefined** CSV operations. It is a
project-local tool, alongside the original eight company tools. Actions are
`prepare_sales`, `list`, `analyze`, `status`, `read` and `cancel`. Identity is supplied
by `ToolRuntime`, never as a model argument. Arithmetic remains available through
the original `run_analysis` tool.

CSV operations are `numeric_summary` and `group_sum`. They compute counts, exact decimal
totals, minimum, maximum and mean; grouped analysis adds totals per label. The worker
writes `result.json` and `report.md`. No `eval`, model-generated SQL, host shell or
arbitrary Python is available through this tool.

| Boundary | Limit / behavior |
| --- | --- |
| Input | UTF-8 CSV, 5 MiB, 50,000 data rows, 1–32 unique named columns |
| Fields | 10,000 characters; numeric strings up to 40 characters, finite magnitude ≤ 1e12, at most 12 decimal places |
| Grouping | At most 200 groups; labels at most 200 characters |
| Output | Combined local result/report ≤ 1 MiB; model preview ≤ 6,000 characters |
| Workspace | Owned user/thread directories, fixed filenames, recorded sizes and hashes; reject path escapes and links |
| Storage | 50 MiB per account, including conservative retained scratch reservations |
| Concurrency | Two analysis jobs per account, four in total |
| Execution | Local worker deadline 0.01–30 seconds; UI minimum 0.1 seconds |
| Cancellation | Queued/running → cancel requested → process killed and reaped → cancelled |
| Publishing | Cancellation is too late once results enter publishing; incomplete job artifacts are not downloadable |

The worker has its own deadline/parent-liveness watchdog. The supervisor also enforces
deadlines and verifies process exit before finishing a cancellation. Tests check that
the owned worker handle is dead and no artifacts continue changing afterward.
Closing a UI stream is not cancellation. Use **Cancel owned analysis worker** and
observe the terminal job status.

A workspace is an organizational boundary. A local process runs as the host user;
its working directory alone does not isolate arbitrary code. This project only runs
its fixed, reviewed analysis worker on the host.

## Optional Docker path

Start a local Linux-container Docker engine and explicitly prepare its image:

```powershell
docker pull python:3.12-slim
```

Open the optional Python panel, review the code, optionally supply a permitted input CSV
ID, and run it. Input is `/input/data.csv`; print results to stdout for `python.txt`.
The runner never silently downloads an image or falls back to host execution.

The container has no network, a read-only root, no capabilities, no-new-privileges,
a non-root user, 128 MiB memory with no additional swap allowance, one CPU, 32 processes
and a 16 MiB temporary filesystem. It receives only individual read-only code/CSV mounts.
No repository, home directory, model credentials or Docker socket is mounted. The host
CLI uses an explicit local engine endpoint (Docker Desktop Linux engine on Windows;
`/var/run/docker.sock` on Linux). Alternate/rootless engines are not currently configured.

Code has an in-container deadline; the supervisor additionally bounds startup/execution,
captures at most 1 MiB, and removes only its named container. Cancellation removes the
container as well as stopping the CLI. A failed cleanup is reported as unverified with
the exact owned-container removal command. Container isolation depends on the engine
and OS; it does not make this a production untrusted-code hosting service.

On server restart, `acme/job_recovery.py` compares the recorded controller/worker PID
and process creation time with actual OS process state. It leaves a live controller
alone and never signals a reused PID. Confirmed abandoned workers are stopped and
reaped; owned containers are removed before the job is marked interrupted. Cleanup
that cannot be verified is labeled `recovery_required`, not successful. Graceful
server shutdown requests cancellation of its active analysis jobs.

Docker became available during validation. Four actual container tests now pass:
CSV/Python execution with read-only input, no network and no provider secrets;
timeout cleanup; explicit cancellation and CLI termination; and oversized stdout cleanup.
The initial cancellation test exposed a creation race, fixed by separate create/start phases.
These checks complement the command-construction and bounded-output unit tests.
See [Docker resource limits](https://docs.docker.com/engine/containers/resource_constraints/)
for the underlying runtime flags.
