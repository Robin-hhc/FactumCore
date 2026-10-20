import pathlib
import sys

from recover import recover
from support import run_cli


if __name__ == "__main__":
    sys.exit(run_cli(recover, pathlib.Path(__file__).resolve().parents[1]))
