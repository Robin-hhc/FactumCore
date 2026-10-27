# Knowledge project interface 2.0

Invoke `scripts/cli.py --input request.json --output response.json`. Request:

```json
{"operation_id":"bind-session","target_path":"<explicit existing code/workspace path>","target_id":"chip12-host"}
```

`target_id` is optional and selects a logical chip/side combination. Module labels do not prove a build or enabled macros. The CLI defaults to the actual framework lock and verifies its files; `--rules-digest SHA256` can explicitly pin it. No catalog or registry is required. An explicit `config_path` limits discovery to that config; otherwise search target ancestors. Multiple workspace matches block. Running from another current working directory does not change a resolved mapping.

Only verified domain contract bytes execute. A successful discovery returns `phase: context_loaded`, `context_ref` and `context_digest`. The immutable record contains actual AGENTS bytes/hashes, the original config hash, resolved module paths and labels, internally derived scope IDs and explicit gaps. `repos` is a dictionary of logical file scopes keyed by stable IDs; the name does not imply repository-manager integration. Chip/side relationships are derived for internal checks without user-written Target/pair tables. File-workspace discovery provides file scopes and labels; repository identity, dirty state, build and enabled macros remain unknown without separate evidence. Code capture fixes actual selected source hashes and conditions when needed.

The public module shape is `code_root: main` plus `modules: [{path: relative/directory, chips: [chip12], sides: [host], features: [], description: purpose}]`. `code_root` is relative to the config directory; module `path` is relative to `code_root`. Only path is required per module. Empty modules allow document work without implicitly authorizing all code. Specific nested modules own their files; a parent identity cannot borrow them. No expected Git URL or duplicate code-policy registration is required. A file capture checks current scope and original config bytes; an earlier discovery record is optional. Legacy explicit repository configuration remains readable for historical compatibility.

Workflow identities and transition checks belong to OpenFlow. This CLI returns its actual context and result directly; it does not validate Workflow IDs or create a per-attempt workflow manifest. Exit 2 is invalid input and 3 is a missing business prerequisite.

First-time preparation uses this Skill's `scripts/setup.py`, described in [setup and execution](setup.md). It checks the current global Python against the packaged runtime lock, installs only when packages are missing or mismatched, and reads the project's existing config.yml. It does not create a virtual environment, catalog, registry or machine binding.

When this Skill's config.env provides SSH connection hints, setup returns ssh_entry for the Agent/harness to use. The harness establishes the connection, runs setup --local or actual nodes on the project server, and checks results. No copied deployment tool directory or new runner is required. Project and source configuration remains in config.yml; generated artifacts stay in the knowledge root's existing .build/logs/artifacts locations.

The context CLI above retains its read-only discovery role. It loads the actual framework lock by default; no catalog registration is required. Existing knowledge-root tools/deploy interfaces are legacy compatibility/development tools, not the first-time workflow. Actual host triggering and independent content review require their own real execution evidence.
