#!/bin/sh
# Fail closed: a missing Python runtime must never turn the secret boundary off.
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
  echo "BLOCKED: security policy runtime is unavailable; sensitive input was omitted." >&2
  exit 2
fi
exec python3 "$SCRIPT_DIR/enforce-sensitive-access.py"
