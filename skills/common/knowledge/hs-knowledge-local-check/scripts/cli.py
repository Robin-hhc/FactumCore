import pathlib
import sys

from check import local_check
from support import run_cli


if __name__ == "__main__":
    sys.exit(run_cli(local_check, pathlib.Path(__file__).resolve().parents[1]))
