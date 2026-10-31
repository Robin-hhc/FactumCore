"""P4 reads an explicitly encoded header with conventional C++ linkage guards."""

import importlib.util
from pathlib import Path

import yaml


_spec = importlib.util.spec_from_file_location(
    "guarded_header_support", Path(__file__).resolve().parents[1] / "support/contracts.py")
_support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_support)
module = _support.module
write_plan = _support.write_plan


def test_public_check_resolves_a_new_gb18030_header_without_dropping_its_symbol(tmp_path):
    project = tmp_path / "project"
    root = project / "himate/library"
    for directory in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / directory).mkdir(parents=True)
    (root / "docs-raw/design.md").write_text("# Reply\n\nReturn the input value.\n", encoding="utf-8")
    code = project / "main/wifi/sample.h"
    code.parent.mkdir(parents=True)
    code_bytes = ('#ifndef SAMPLE_H\n#define SAMPLE_H\n#ifdef __cplusplus\n#if __cplusplus\nextern "C" {\n#endif\n#endif\n'
                  'static int ready(int value) { /* 原值 */ return value; }\n'
                  '#ifdef __cplusplus\n#if __cplusplus\n}\n#endif\n#endif\n#endif\n').encode("gb18030")
    code.write_bytes(code_bytes)
    (project / "config.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "guarded-header",
        "knowledge_roots": {"wifi": "himate/library"}, "code_root": "main", "modules": [{"path": "wifi"}],
    }), encoding="utf-8")
    for request in ({"kind": "doc", "path": "docs-raw/design.md", "source_id": "doc-design"},
                    {"kind": "code", "path": "main/wifi/sample.h", "source_id": "code-ready", "encoding": "gb18030"}):
        _, status = module("library").sources(root, "register", request)
        assert status == "registered"
    _, status = module("ingest").scan(root, {"source": "doc-design"})
    assert status == "prepared"
    header = {"id": "ready", "doc_ref": [{"doc_id": "doc-design", "line_start": 1, "line_end": 3}],
              "code_ref": [{"code_id": "code-ready", "line_start": 8, "line_end": 8, "symbol": "ready"}]}
    candidate = root / ".build/cards/ready.md"
    candidate.write_text("---\n" + yaml.safe_dump(header, sort_keys=False)
                         + "---\n# Ready\n\nReturn the input value.\n", encoding="utf-8")
    original_draft = candidate.read_bytes()
    write_plan(root, [("ready", "knowledge/ready.md")])

    checked, status = module("ingest").check(root, {})

    assert status == "passed", checked
    assert candidate.read_bytes() == original_draft
    assert code.read_bytes() == code_bytes
