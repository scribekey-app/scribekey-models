#!/usr/bin/env bash
# Measure, one pair at a time, everything plan.py says is missing (all models, or the ids given).
# One model's files and one FLEURS language are on disk at once. For the whole catalogue, use the
# Measure speech accuracy workflow instead: it runs the pairs in parallel on GitHub's runners.
set -euo pipefail
cd "$(dirname "$0")/../../.."
CACHE="${BENCH_CACHE:-/tmp/scribekey-fleurs}"
PY="${BENCH_PYTHON:-uv run --python 3.12 --with-requirements bench/asr/fleurs/requirements.txt python}"

previous=""
python3 bench/asr/fleurs/plan.py "$@" | while read -r id lang; do
  [ -n "$previous" ] && [ "$previous" != "$id" ] && command rm -rf "$CACHE/models/$previous"
  previous="$id"
  $PY bench/asr/fleurs/measure.py "$id" "$lang" 2>&1 | grep -v -i warning | tail -1
done
