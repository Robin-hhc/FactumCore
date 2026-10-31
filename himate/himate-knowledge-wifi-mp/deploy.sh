#!/bin/sh
# Install with the same Python that runs the shared deployment backend.
set -eu

python=${HIMATE_KNOWLEDGE_PYTHON:-python3}
expect_python=false
for argument in "$@"; do
    if [ "$expect_python" = true ]; then
        python=$argument
        expect_python=false
        continue
    fi
    case "$argument" in
        --python) expect_python=true ;;
        --python=*) python=${argument#--python=} ;;
    esac
done

if [ "$expect_python" = true ] || [ -z "$python" ]; then
    printf '%s\n' 'deploy.sh: --python requires an executable path' >&2
    exit 2
fi

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
exec "$python" "$script_dir/tools/deploy/deploy.py" "$@"
