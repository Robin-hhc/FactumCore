"""One in-process dispatch seam for the repository's existing stage protocols.

The CLI supplies concrete input/output paths. This module does not create a
model driver, infer reviewer identity, or chain synchronization with a second
stage in an already loaded process.
"""

from __future__ import annotations

import importlib
import sys


STAGES = (
    "explore", "source", "change-plan", "view-materialize",
    "lint", "apply", "query", "maintain",
)


def run_stage(stage: str, argv: list[str]) -> int:
    """Run one real stage without a subprocess; preserve its output and exit code.

    The development-only setup adapter calls its canonical implementation
    directly; ordinary commands never invoke environment installation.
    """
    slug = stage.replace("_", "-")
    if slug in STAGES:
        module_name = slug.replace("-", "_") + ".cli"
    else:
        raise ValueError("Unknown knowledge stage: " + stage)
    previous = sys.argv
    try:
        sys.argv = ["knowledge " + slug, *argv]
        module = importlib.import_module(".stages." + module_name, __package__)
        try:
            result = module.main()
        except SystemExit as exc:
            # argparse help/errors are part of the stage's original protocol.
            return int(exc.code or 0) if isinstance(exc.code, (int, type(None))) else 1
        return int(result or 0)
    finally:
        sys.argv = previous
