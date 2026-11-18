#!/bin/sh
# Install HiMate Skills and Workflow templates for OpenFlow and CAC.
set -eu

python=${HIMATE_KNOWLEDGE_PYTHON:-python3}
# Remove the wrapper's interpreter option before forwarding capability options.
remaining=$#
while [ "$remaining" -gt 0 ]; do
    argument=$1
    shift
    remaining=$((remaining - 1))
    case "$argument" in
        --python)
            if [ "$remaining" -eq 0 ]; then
                printf '%s\n' 'deploy.sh: --python requires an executable path' >&2
                exit 2
            fi
            python=$1
            shift
            remaining=$((remaining - 1))
            ;;
        --python=*) python=${argument#--python=} ;;
        *) set -- "$@" "$argument" ;;
    esac
done

if [ -z "$python" ]; then
    printf '%s\n' 'deploy.sh: --python requires an executable path' >&2
    exit 2
fi

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
exec "$python" "$script_dir/scripts/deploy.py" "$@"
