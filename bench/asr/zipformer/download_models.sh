#!/bin/bash
set -euo pipefail
B=$(cd "$(dirname "$0")/.." && pwd)
dl(){ # name repo rev remote local
  mkdir -p "$B/models/$1"
  curl -fsSL --retry 3 -o "$B/models/$1/$5" "https://huggingface.co/$2/resolve/$3/$4"
}
R=csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26; V=672fbf1b30579d6585301139bb363f42a0ad4a24
for p in encoder decoder joiner; do dl zip0626 $R $V $p-epoch-99-avg-1-chunk-16-left-128.int8.onnx $p-epoch-99-avg-1-chunk-16-left-128.int8.onnx; done
dl zip0626 $R $V tokens.txt tokens.txt
R=csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-21; V=9a65b6ea94c311ca770c2bf895b30f456a22d703
for p in encoder decoder joiner; do dl zip0621 $R $V $p-epoch-99-avg-1.int8.onnx $p-epoch-99-avg-1.int8.onnx; done
dl zip0621 $R $V tokens.txt tokens.txt
R=csukuangfj2/sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25; V=52056fdc070914a48dcd68b31b44d6a6f5b85902
for f in encoder.int8.onnx decoder.int8.onnx joiner.int8.onnx tokens.txt; do dl nemotron $R $V $f $f; done
cd "$B/models"
printf "model\tfile\tbytes\tsha256\n" > "$B/results/files.tsv"
for m in nemotron zip0626 zip0621; do for f in $(ls $m); do
  printf "%s\t%s\t%s\t%s\n" $m $f $(stat -c%s $m/$f) $(sha256sum $m/$f | cut -d' ' -f1) >> "$B/results/files.tsv"; done; done
