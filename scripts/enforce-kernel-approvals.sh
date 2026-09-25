#!/usr/bin/env bash
# Claude Code PreToolUse adapter for durable, user-owned stage approvals.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/enforce-kernel-approvals.py"
