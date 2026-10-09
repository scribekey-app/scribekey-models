#!/bin/bash
# Supplementary: FLEURS en_us with every clip (after babble mixing) peak-normalised to 0.9.
set -euo pipefail
B=$(cd "$(dirname "$0")/.." && pwd); cd /; mkdir -p $B/results/peaknorm
for m in nemotron zip0626 zip0621; do PEAK_NORM=0.9 ONLY_SET=fl_en_us python3 -I $B/scripts/bench_model.py $m $B/models $B/data $B/results/peaknorm/raw_$m.json; done
python3 -I $B/scripts/score.py $B/data $B/results/peaknorm
