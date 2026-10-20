import pathlib
import sys

from support import run_cli
from transaction import execute


if __name__ == "__main__":
    sys.exit(run_cli(execute, pathlib.Path(__file__).resolve().parents[1]))
