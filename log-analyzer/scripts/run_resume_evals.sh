#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:-}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -z "$PROJECT" ]]; then
  "$PYTHON_BIN" "$ROOT/scripts/metrics_report.py" triage-eval
else
  "$PYTHON_BIN" "$ROOT/scripts/metrics_report.py" triage-eval --project "$PROJECT"
fi
