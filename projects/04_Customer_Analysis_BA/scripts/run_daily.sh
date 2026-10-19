#!/usr/bin/env bash
# Manual trigger for the daily pipeline (see docs/scheduling.md).
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${CONDA_ENV:-customer_analysis_ba}"
mkdir -p "$PROJECT_DIR/logs"
cd "$PROJECT_DIR"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] pipeline start" >> logs/pipeline.log
conda run -n "$ENV_NAME" python main.py "$@" >> logs/pipeline.log 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] pipeline end" >> logs/pipeline.log
