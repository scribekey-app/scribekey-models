#!/bin/bash
set -euo pipefail
B=$(cd "$(dirname "$0")/.." && pwd); cd /
for m in nemotron zip0626 zip0621; do python3 -I $B/scripts/bench_model.py $m $B/models $B/data $B/results/raw_$m.json; done
python3 -I $B/scripts/score.py $B/data $B/results
for m in nemotron zip0626 zip0621; do python3 -I $B/scripts/rss.py $m $B/models $B/data/clips/libri_other/000.wav; done > $B/results/rss.jsonl
