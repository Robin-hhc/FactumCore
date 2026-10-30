"""A complete legacy content closure remains readable through producer context."""

import os
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("dbox_legacy_cases", Path(__file__).resolve().parents[2] / "support/stages/apply_publication_cli.py")
existing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(existing)


def test_legacy_content_completion_and_status_remain_readable(tmp_path):
    trial = existing.P6.PublicP7(tmp_path)
    request = existing.publication_content(trial)
    probe = tmp_path / "legacy-writer"
    probe.mkdir()
    # Emit the historical metadata before the caller constructs its dependent
    # retrieval records. All byte/index/query checks still run through the CLI.
    (probe / "sitecustomize.py").write_text('''import sys
def profile(frame, event, manifest):
    if (event == "return" and frame.f_code.co_name == "publish_manifest"
            and frame.f_code.co_filename.replace("\\\\", "/").endswith("/contracts/publication.py")):
        ctx = frame.f_locals["ctx"]
        value = dict(manifest)
        value.pop("digest", None)
        value.pop("dbox_execution_scope", None)
        value["protocol_version"] = "1.0"
        value = ctx.modules["records"].seal(value)
        manifest.clear()
        manifest.update(value)
        from pathlib import Path
        import json
        path = ctx.root / ("logs/publications/" + ctx.operation + "/manifest.json")
        path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
sys.setprofile(profile)
''', encoding="utf-8")
    result = trial.call("batch", request, environment={**os.environ, "PYTHONPATH": str(probe)})
    assert result["data"]["batch_complete"] is True
    manifest = trial.record(result["data"]["publication_ref"])
    completion = trial.record(result["data"]["completion_ref"])
    assert manifest["protocol_version"] == completion["protocol_version"] == "1.0"
    assert "dbox_execution_scope" not in manifest
    replay = trial.call("batch", {"operation_id": request["operation_id"]})
    assert replay["data"]["batch_complete"] is True
    status = trial.call("status", {"operation_id": "legacy-status", "target_operation_id": request["operation_id"]},
                        skill="hs-knowledge-source")
    assert status["status"] == "ok"
