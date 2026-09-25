#!/usr/bin/env bash
# Claude Code PreToolUse adapter for the registry-backed native-write policy.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/enforce-agent-paths.py"
