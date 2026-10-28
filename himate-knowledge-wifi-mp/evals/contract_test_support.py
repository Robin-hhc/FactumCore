"""Load the same public domain functions used by the real CLI adapters.

Fixture construction trusts this development checkout. Public CLI invocations
still independently verify the copied rule lock and exact source bytes.
"""

import importlib
import importlib.util
from pathlib import Path
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
