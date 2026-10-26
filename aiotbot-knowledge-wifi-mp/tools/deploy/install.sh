#!/usr/bin/env bash
# Uses the existing interpreter and pip configuration; never installs Python.
set -euo pipefail
tool_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$tool_dir/../../.." && pwd)"
python_bin=""
args=()
while (($#)); do
    case "$1" in
        --python)
            if (($# < 2)); then echo '--python needs an interpreter path' >&2; exit 2; fi
            python_bin="$2"; shift 2 ;;
        *) args+=("$1"); shift ;;
    esac
done
if [[ -z "$python_bin" ]]; then
    for candidate in python3.11 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            python_bin="$(command -v "$candidate")"
            break
        fi
    done
fi
if [[ -z "$python_bin" ]]; then
    echo 'Python 3.11 was not found. Specify --python with the existing interpreter path.' >&2
    exit 3
fi
exec "$python_bin" -X utf8 "$tool_dir/install_environment.py" \
    --source-root "$root" "${args[@]}"
