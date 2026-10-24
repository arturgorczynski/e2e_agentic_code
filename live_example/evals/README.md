# Private scenario specifications

`g02_scenarios.json` defines 12 learning/evaluation cases, their actor, required
records/documents, expected facts, permissions, tool sequence candidates, and checks.
It contains authored numeric fixtures and answer keys, not observed UCI records.

These files are never company knowledge. Do not place them under `data/documents/`,
index them, inject them into prompts, or make them available to agent filesystem tools.
G04 materializes operational scenario records in a separate synthetic namespace.
`source_answer_map.json` resolves the records, computed-view aliases and policy versions.
`runtime_seed.json` defines later private application fixtures and proposed outputs;
they are not company database rows and are not initialized by G04/G05. G13 will evaluate
actual agent behavior against these expectations.

G02 tests check arithmetic, references, ownership expectations, policy dates, tool
inventory, and the design boundary. They do not claim a live agent, login system,
approval workflow. G04/G05 tests additionally derive facts from the built database and
documents; later runtime action gates remain explicit in the source map.
