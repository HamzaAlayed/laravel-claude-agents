#!/usr/bin/env bash
# Stdlib-Python entrypoint for the kernel runtime-budget policy.
set -u

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/enforce-kernel-budgets.py"
