import pathlib
import sys

from prepare import prepare
from support import Invalid, run_cli


def handle(ctx, request, action):
    if action != "run":
        raise Invalid("unsupported action")
    return prepare(ctx, request)


if __name__ == "__main__":
    sys.exit(run_cli(handle, pathlib.Path(__file__).resolve().parents[1]))
