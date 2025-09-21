#!/usr/bin/env bash
set -euo pipefail
OUT_DIR="${1:-results/run}"
python -m stabcodes.cli.build --out "$OUT_DIR"
