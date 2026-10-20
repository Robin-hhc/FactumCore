# Workspace binding 2.0

Invoke `scripts/cli.py --input request.json --output response.json`. Request:

```json
{"operation_id":"bind-session","target_path":"<explicit existing code/workspace path>","target_id":"chip12-host"}
```

`target_id` is optional and selects a registered logical Target. It does not prove a build, macro set or real chip mapping. Use explicit trusted process arguments `--rules-digest SHA256`, or `--catalog CATALOG.json` / `--registry workspace-registry.json` from the isolated installer. An explicit request `config_path` limits discovery to that config; otherwise search only target ancestors, then registered code roots. Equally specific mappings or multiple workspace matches block. Running from another current working directory does not change a resolved mapping.

No pin means `phase: resolved` with `trusted_rules_digest_required`, not context loaded. A trusted pin permits only verified domain contract bytes to execute. A successful binding returns `phase: context_loaded`, `context_ref` and `context_digest`. The immutable record contains actual AGENTS bytes/hashes, actual config hash, registered repos, six logical Targets, three pairs and explicit missing facts. `repos` is a dictionary keyed by repo ID. Discovery records leave build/macro and dirty-state facts unknown; the code gate requires additional actual evidence.

For a real Workflow node pass `workflow: {run_id,node_id,attempt_id}` with three safe unique identifiers. The program writes the actual per-attempt Markdown manifest and JSON into K/logs/workflows. Reentry cannot replace a different artifact. Exit 0 means the request was handled; inspect phase/data. Exit 2 is invalid input and 3 is a missing prerequisite.

Explicit installation is `scripts/install_catalog.py --source-root REPO --destination NEW_PRIVATE_DIR --python LOCKED_PYTHON [--workspace-config CONFIG]`. It copies exactly 18 packages and two templates after verification, writes a private catalog/registry, rejects existing destinations/links/private keys, and validates installed dependency versions. It does not invoke pip or install into a host's global Skill registry. Implicit host triggering requires the actual host installation and separate acceptance.
