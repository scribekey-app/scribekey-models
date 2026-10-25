# Changes made by ScribeKey

25 October 2026, ScribeKey Fast v1 release candidate (`v7-replay-tgt`).

- **Weights:** continued LoRA training of ScribeKey's Sotto v6 on 4,350 rows, then merged into BF16. The v6 starting point was reconstructed from its production Q8_0, not recovered original BF16 weights. The reconstruction re-exported bit-identically at Q8_0 tensor precision.
- **GGUF:** converted the merged checkpoint to F16 and quantized to Q8_0 with llama.cpp `4c1a0af40d88c7fbb3b15c85bf2e8016d1d5b64c`. The distribution filename is `scribekey-cleanup-fast-350m-v1-Q8_0.gguf`. Its bytes and embedded experiment metadata are unchanged from the evaluated artifact. Its embedded LFM chat template is inherited; use the documented raw prompt or the separate task-specific template.
- **Tokenizer template:** replaced the inherited LFM conversation template in the BF16 package with the exact single-turn Input/Output control-line task wrapper. The tokenizer vocabulary/tokens are unchanged. The same replacement is supplied separately as `prompt-template.jinja` with the GGUF.
- **Generation config:** made greedy decoding and a 256-token output limit explicit; no change to learned weights. Removed the stale local source-revision file from distribution; immutable ancestry and hashes are recorded in `provenance.json` instead.
- **Documentation and manifests:** added ScribeKey Fast naming, observed examples, evaluation limits, immutable provenance, required upstream notices and licence guidance. The original LFM licence and prior Sotto notice are retained verbatim.

The `model.safetensors` and GGUF files carry their modification notices through this accompanying document, `NOTICE` and `provenance.json`; their binary contents have not been rewritten merely to change branding. Distribute these notices with them.
