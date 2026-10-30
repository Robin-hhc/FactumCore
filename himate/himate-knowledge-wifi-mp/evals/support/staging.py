"""Real public algorithms over explicitly trusted synthetic rules, no CLI repin."""

import importlib.util
import json
from pathlib import Path



spec = importlib.util.spec_from_file_location("stage_boundary_support", Path(__file__).with_name("contracts.py"))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
runtime, records = helper.module("runtime"), helper.module("records")
operations, materials = helper.module("source_operations"), helper.module("source_materials")
resources, validation = helper.module("source_resources"), helper.module("validation")
staging = helper.module("staging")


def make_context(root, operation, **request):
    governance = Path(__file__).parents[2] / "governance"
    rules = {"knowledge_root": root, "rules_digest": "0" * 64,
             "schemas": {"record": json.loads((governance / "schemas/records.schema.json").read_bytes())}}
    modules = {name: helper.module(name) for name in ("records", "validation", "source_resources", "source_operations", "knowledge")}
    return runtime.OperationContext(root, {"operation_id": operation, **request}, modules=modules,
                                    rules=rules, rules_digest="0" * 64, tool={
                                        "skill": "hs-synthetic-stage-test", "package_digest": "0" * 64,
                                        "runtime": "synthetic", "requirements_digest": "0" * 64})


def write(root, ref, raw):
    path = root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def formal(root):
    return {p.relative_to(root).as_posix(): runtime.sha(p.read_bytes()) for p in root.rglob("*")
            if p.is_file() and not p.relative_to(root).as_posix().startswith(".build/")}
