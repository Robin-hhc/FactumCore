"""Load the same public domain functions used by the real CLI adapters.

Fixture construction trusts this development checkout. Public CLI invocations
still independently verify the copied rule lock and exact source bytes.
"""

import importlib
import importlib.util
from pathlib import Path
import shutil
import sys


def module(name):
    namespace = "_himate_public_contract_tests"
    if namespace not in sys.modules:
        directory = Path(__file__).resolve().parents[1] / "governance/contracts"
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
    source = Path(__file__).resolve().parents[1]
    target = Path(knowledge_root)
    shutil.copytree(source / "runtime", target / "runtime", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("knowledge.py", "knowledge.sh", "knowledge.cmd"):
        path = source / name
        if path.is_file():
            shutil.copyfile(path, target / name)


def runtime_module(name):
    """Import canonical implementation for deliberately low-level test seams."""
    namespace = "_himate_runtime_contract_tests"
    if namespace not in sys.modules:
        directory = Path(__file__).resolve().parents[1] / "runtime/himate_knowledge"
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
