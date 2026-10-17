#!/bin/sh
set -eu
SCRIPT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${FORTE_PYTHON:-python3}" "$SCRIPT_ROOT/download_weights.py" "$@"
