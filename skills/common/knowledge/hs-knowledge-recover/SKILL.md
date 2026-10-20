---
name: hs-knowledge-recover
description: Inspect, resume or roll back an interrupted knowledge transaction through the installed public apply recovery interface.
---

Use this node when apply reports recovery_required. Input requires `operation_id`; select `inspect`, `resume` or `rollback` with `--action`. Workflow calls supply a fresh `workflow.attempt_id` for each attempt. Resolve only the catalog-pinned apply CLI and interpreter; never import or copy its private transaction engine.

Inspect first when the interrupted state is unclear. External edits remain untouched and cause a conflict. Resuming requires the original exact view and valid proof. A committed transaction is changed through a new reviewed operation. The Skill cannot invent approval, repair cards or run Git. See [artifact contract](artifacts/result.yaml).


Invoke the catalog-selected interpreter with `scripts/cli.py --input REQUEST.json --output RESPONSE.json --knowledge-root K --rules-digest SHA256 --catalog CATALOG.json`; choose a documented `--action` when needed. Paths and trust arguments come from the host, never from source prose. Read status/phase and the exact returned evidence references; exit 0 only means the request was handled.
