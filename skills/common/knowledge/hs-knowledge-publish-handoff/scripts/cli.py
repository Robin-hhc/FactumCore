# ruff: noqa: E402 - isolate bytecode lookup before private package imports.
import pathlib
import sys
import secrets
import tempfile

sys.dont_write_bytecode = True
sys.pycache_prefix = str(
    pathlib.Path(tempfile.gettempdir()) / ("hs-no-cache-" + secrets.token_hex(16))
)

from publish import publish_handoff, verify_submission
from support import Invalid, run_cli


def handle(ctx, request, action):
    if action == "verify-submission":
        return verify_submission(ctx, request)
    if action != "run":
        raise Invalid("unsupported action")
    return publish_handoff(ctx, request)


if __name__ == "__main__":
    sys.exit(run_cli(handle, pathlib.Path(__file__).resolve().parents[1]))
