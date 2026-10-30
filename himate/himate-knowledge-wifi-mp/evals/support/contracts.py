"""Load the same public domain functions used by the real CLI adapters.

Fixture construction trusts this development checkout. Public CLI invocations
still independently verify the copied rule lock and exact source bytes.
"""

import importlib
import importlib.util
from pathlib import Path
import shutil
import sys


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2]
ROOT = KNOWLEDGE_ROOT.parents[1]


def module(name):
    namespace = "_himate_public_contract_tests"
    if namespace not in sys.modules:
        directory = KNOWLEDGE_ROOT / "governance/contracts"
        spec = importlib.util.spec_from_file_location(
            namespace, directory / "__init__.py", submodule_search_locations=[str(directory)],
        )
        package = importlib.util.module_from_spec(spec)
        sys.modules[namespace] = package
        spec.loader.exec_module(package)
    return importlib.import_module(namespace + "." + name)


def copy_runtime(knowledge_root):
    """Explicitly install the repository executable closure into a test K.

    This is fixture construction, never a runtime fallback to development code.
    The destination may contain synthetic business data; only runtime-owned
    paths are copied, and no real originals or local configuration are read.
    """
    source = KNOWLEDGE_ROOT
    target = Path(knowledge_root)
    shutil.copytree(source / "runtime", target / "runtime", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv"))
    for name in ("knowledge.py", "knowledge.sh", "knowledge.cmd"):
        path = source / name
        if path.is_file():
            shutil.copyfile(path, target / name)


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
        directory = KNOWLEDGE_ROOT / "runtime/himate_knowledge"
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


def stage_command(stage, knowledge_root=None):
    """Invoke the shipped repository entry; target K is always explicit when supplied."""
    stage = stage.removeprefix("hs-").removeprefix("knowledge-")
    command = [sys.executable, str(KNOWLEDGE_ROOT / "knowledge.py"), stage, "--json"]
    if knowledge_root is not None:
        command += ["--knowledge-root", str(knowledge_root)]
    return command
