"""Load the same public domain functions used by the real CLI adapters.

Fixture construction trusts this development checkout. Public CLI invocations
still independently verify the copied rule lock and exact source bytes.
"""

import importlib
import importlib.util
import json
from pathlib import Path
import sys

import yaml


TOOL_ROOT = Path(__file__).resolve().parents[2]
ROOT = TOOL_ROOT.parents[1]
KNOWLEDGE_ROOT = ROOT / "himate/himate-knowledge-wifi-mp"


def write_plan(root, cards, body="Keep the documented knowledge and its chosen location."):
    """Write explicit author intent; callers supply expected IDs and final paths."""
    path = Path(root) / ".build/plan.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"cards": [
        {"id": identity, "path": relative} for identity, relative in cards
    ]}
    task_path = Path(root) / ".build/task.json"
    if task_path.is_file():
        task = json.loads(task_path.read_bytes())
        if "pdf_review" in task:
            batch = task["pdf_review"]
            metadata["source_pages"] = [[batch["start_page"], batch["end_page"]]]
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False)
                    + "---\n" + body + "\n", encoding="utf-8")
    return path


def module(name):
    namespace = "_himate_public_contract_tests"
    if namespace not in sys.modules:
        directory = TOOL_ROOT / "governance/contracts"
        spec = importlib.util.spec_from_file_location(
            namespace, directory / "__init__.py", submodule_search_locations=[str(directory)],
        )
        package = importlib.util.module_from_spec(spec)
        sys.modules[namespace] = package
        spec.loader.exec_module(package)
    return importlib.import_module(namespace + "." + name)


def copy_workspace_metadata(workspace, knowledge_root, *, source_root=ROOT, source_knowledge_root=KNOWLEDGE_ROOT):
    """Copy public Git metadata, adapting the source placement to a fixture K.

    Flat and custom configured roots remain intentional consumer test cases;
    the development default must not leak into their private ignore rules.
    """
    workspace, knowledge_root = Path(workspace), Path(knowledge_root)
    old = ("/" + Path(source_knowledge_root).relative_to(source_root).as_posix() + "/").encode()
    new = ("/" + knowledge_root.relative_to(workspace).as_posix() + "/").encode()
    for name in (".gitignore", ".gitattributes"):
        path = Path(source_root) / name
        if path.is_file():
            (workspace / name).write_bytes(path.read_bytes().replace(old, new))


def runtime_module(name):
    """Import canonical implementation for deliberately low-level test seams."""
    namespace = "_himate_runtime_contract_tests"
    if namespace not in sys.modules:
        directory = TOOL_ROOT / "runtime/himate_knowledge"
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        entry = directory / "__init__.py"
        spec = (importlib.util.spec_from_file_location(
            namespace, entry, submodule_search_locations=[str(directory)],
        ) if entry.is_file() else importlib.util.spec_from_loader(namespace, loader=None, is_package=True))
        package = importlib.util.module_from_spec(spec)
        package.__path__ = [str(directory)]
        sys.modules[namespace] = package
        if spec.loader is not None:
            spec.loader.exec_module(package)
    return importlib.import_module(namespace + "." + name)
