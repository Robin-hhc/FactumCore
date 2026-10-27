"""Current code Claims use actual config/module/Target scope without proof chains."""
import subprocess
import sys
from pathlib import Path


def test_current_claim_loses_target_when_module_membership_is_revoked(tmp_path):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    import hashlib
    import importlib.util
    import json
    from types import SimpleNamespace

    repository = Path(__file__).resolve().parents[5]
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from node import qualify_sources

    spec = importlib.util.spec_from_file_location(
        "query_code_scope_contract", repository / "himate-knowledge-wifi-mp/governance/contracts/__init__.py",
        submodule_search_locations=[str(repository / "himate-knowledge-wifi-mp/governance/contracts")],
    )
    contract = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = contract
    spec.loader.exec_module(contract)
    from query_code_scope_contract import source_resources, validation

    workspace = Path(sys.argv[1])
    root = workspace / "himate-knowledge-wifi-mp"
    (root / "governance").mkdir(parents=True)
    source = workspace / "main/shared/file.c"
    source.parent.mkdir(parents=True)
    raw = b"int selected_fixture(void) { return 1; }\n"
    source.write_bytes(raw)
    config = {"schema_version": "2.0", "workspace_id": "query-fixture",
              "knowledge_roots": {"wifi": root.name}, "code_root": "main",
              "modules": [{"path": "shared", "chips": ["chip12"], "sides": ["host"]}]}
    config_path = workspace / "config.yml"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    normalized = validation.normalize_workspace(config, workspace)
    repo_id = normalized["repos"][0]["repo_id"]
    reference = {"evidence_ref": "e1", "source_id": "code", "snapshot_id": "code:fixture",
                 "locator": {"kind": "lines", "start": 1, "end": 1}}
    lock = {"schema_version": "2.0", "resources": [{"source_id": "code", "kind": "code", "repo_id": repo_id, "path": "file.c"}],
            "snapshots": [{"source_id": "code", "snapshot_id": "code:fixture", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}]}
    (root / "governance/sources.lock.yaml").write_text(json.dumps(lock), encoding="utf-8")
    scope = {"applicability": "constrained", "contexts": [{"context_id": "host", "target_id": "chip12-host", "chip": "chip12", "side": "host"}]}
    claim = {"id": "c1", "scope": scope, "source_records": [reference]}
    card = {"metadata": {"id": "code-card", "scope": scope, "sources": [reference]}, "claims": [claim]}
    rules = {"schemas": {"workspace": json.loads((repository / "himate-knowledge-wifi-mp/governance/schemas/workspace.schema.json").read_bytes())}}
    context = SimpleNamespace(root=root, rules=rules, operation="manual-query",
                              modules={"validation": validation, "source_resources": source_resources},
                              call=lambda *args: {"data": {"source_ref": reference, "current_source_matches": True}})
    for purpose in ("current", "implementation"):
        assert qualify_sources(context, card, {"c1"}, purpose, {}, {"code"})[0] == {"c1"}
    for membership in ({"chips": ["chip08"], "sides": ["host"]}, {"chips": ["chip12"], "sides": ["device"]}):
        config["modules"] = [{"path": "shared", **membership}]
        config_path.write_text(json.dumps(config), encoding="utf-8")
        for purpose in ("current", "implementation"):
            eligible, _, gaps = qualify_sources(context, card, {"c1"}, purpose, {}, {"code"})
            assert eligible == set()
            assert gaps[0]["code"] == "CURRENT_CODE_SCOPE_CHANGED_OR_UNKNOWN"
        assert source.read_bytes() == raw
    assert qualify_sources(context, card, {"c1"}, "historical", {}, {"code"})[0] == {"c1"}
