#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:-}"
PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" "$ROOT/scripts/metrics_report.py" clustering

if [[ -z "$PROJECT" ]]; then
  echo
  echo "No project provided, so live metrics, LLM evals, and benchmarks were skipped."
  echo "Usage: $ROOT/scripts/run_resume_evals.sh <project-name>"
  exit 0
fi

echo
"$PYTHON_BIN" "$ROOT/scripts/metrics_report.py" live --project "$PROJECT"

echo
"$PYTHON_BIN" "$ROOT/scripts/metrics_report.py" analysis-eval --project "$PROJECT" || true

echo
"$PYTHON_BIN" "$ROOT/scripts/metrics_report.py" suppression-eval --project "$PROJECT"

echo
"$PYTHON_BIN" "$ROOT/scripts/benchmark_ingest.py" --project "$PROJECT" --mode cluster-only --lines 1000 --batch-size 100

echo
"$PYTHON_BIN" "$ROOT/scripts/benchmark_ingest.py" --project "$PROJECT" --mode full-pipeline --lines 200 --batch-size 50
