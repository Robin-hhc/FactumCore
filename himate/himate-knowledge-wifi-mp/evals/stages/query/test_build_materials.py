"""Direct business evidence survives indexing and is rechecked during queries."""
import base64
import importlib.util
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location(
    "direct_material_fixture", ROOT / "himate/himate-knowledge-wifi-mp/evals/support/stages/lint_code.py"
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_actual_build_runtime_materials_need_no_passed_receipts_and_detect_changed_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("HIMATE_TEST_TMP", str(tmp_path))
    environment = fixture.PublicCodeGateTests(methodName="runTest")
    environment.setUp()
    try:
        context = json.loads((environment.root / environment.context_ref).read_bytes())
        original = base64.b64decode(environment.view["writes"][0]["bytes_b64"]).decode()
        _, front, body = original.split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["claims"][0]["verification_requirements"] = ["build-support", "runtime-support"]
        metadata["claims"].append({**metadata["claims"][0], "id": "static", "text_ref": "#static",
                                   "verification_requirements": ["semantic-support"]})
        body += "\n<a id=\"static\"></a>\nStatic fixture function source location.\n"
        official = environment.root / environment.view["writes"][0]["path"]
        official.parent.mkdir(parents=True, exist_ok=True)
        official.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body, encoding="utf-8")
        for row in environment.view["writes"][1:]:
            path = environment.root / row["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(row["bytes_b64"]))
        # No successful Skill report or apply transaction is available to consult.
        for relative in (environment.report_ref, environment.context_ref, environment.view_ref):
            (environment.root / relative).unlink()
        materials = {"logs/evidence/build.bin": b"synthetic fixture build only\n",
                     "logs/evidence/runtime.log": b"synthetic runtime observation\n",
                     "logs/evidence/macros.json": b'["WIFI_ON"]'}
        for relative, raw in materials.items():
            (environment.root / relative).write_bytes(raw)
        code_context = {
            "config_digest": fixture.digest((environment.workspace / "config.yml").read_bytes()),
            "code_identity": {"repos": {"wifi-code": {"root": str(environment.code), "head": environment.head,
                              "files": {"src/wifi.c": fixture.digest(environment.source)}, "checked_files_dirty": False}},
                              "target": context["target"], "macro_digest": context["build_evidence"]["macro_digest"],
                              "build_files": {path: fixture.digest(raw) for path, raw in materials.items()}},
            "claim_evidence": {"c1": [
                {"requirement": requirement, "path": path, "sha256": fixture.digest(materials[path])}
                for requirement, path in (("build-support", "logs/evidence/build.bin"),
                                           ("runtime-support", "logs/evidence/runtime.log"))]},
        }
        assert "passed" not in json.dumps(code_context) and "status" not in code_context

        def build(operation, data):
            result = environment.invoke("hs-knowledge-index-build", "build", {"operation_id": operation, **data}, use_catalog=False)["data"]
            environment.invoke("hs-knowledge-index-build", "activate", {"operation_id": operation + "-activate",
                               "generation_ref": result["generation_ref"], "expected_active": result["expected_active"]}, use_catalog=False)
            return result

        def claims(purpose):
            result = environment.invoke("hs-knowledge-query", "search", {"operation_id": "material-query", "query": "function",
                                       "purpose": purpose, "context": context["target"]}, use_catalog=False)["data"]
            return {claim for row in result["matches"] for claim in row["claim_ids"]}

        build("source-only-index", {})
        assert claims("implementation") == {"static"}
        built = build("material-index", {"code_contexts": {metadata["id"]: code_context}})
        manifest = json.loads((environment.root / built["generation_ref"]).read_bytes())
        assert manifest["code_contexts"][metadata["id"]] == code_context
        assert manifest["qualifications"] == {}
        for purpose in ("current", "implementation"):
            assert claims(purpose) == {"c1", "static"}
        for relative, raw in materials.items():
            (environment.root / relative).write_bytes(raw + b"changed\n")
            for purpose in ("current", "implementation"):
                assert claims(purpose) == {"static"}
            rejected = environment.invoke("hs-knowledge-index-build", "build", {"operation_id": "changed-material",
                                          "code_contexts": {metadata["id"]: code_context}}, expected=2, use_catalog=False)
            assert rejected["diagnostics"][0]["code"] == "CODE_BUILD_CHANGED"
            (environment.root / relative).write_bytes(raw)
        assert claims("implementation") == {"c1", "static"}
        assert not list((environment.root / "logs/operations").glob("*/apply-result.json"))
    finally:
        environment.doCleanups()
