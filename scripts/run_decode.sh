#!/usr/bin/env bash
set -euo pipefail
META_PATH="${1:-results/run/build_meta.json}"
OUT_DIR="${2:-$(dirname "$META_PATH")}"
python -m stabcodes.decode.run --meta "$META_PATH" --out "$OUT_DIR"
