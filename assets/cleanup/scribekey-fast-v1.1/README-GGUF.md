---
license: other
license_name: scribekey-fast-model-terms-v1.0-with-lfm-open-license-v1.0
license_link: https://huggingface.co/scribekey/scribekey-cleanup-fast-GGUF/blob/main/ADDITIONAL_TERMS.md
language:
- en
base_model: scribekey/scribekey-cleanup-fast
base_model_relation: quantized
library_name: gguf
pipeline_tag: text-generation
tags:
- gguf
- transcript-cleanup
- text-normalization
- dictation
---

# ScribeKey Fast by ScribeKey — GGUF

The evaluated Q8_0 build of [ScribeKey Fast](https://huggingface.co/scribekey/scribekey-cleanup-fast), a 350M-class English speech-to-text **cleanup** model. It receives a transcript, not audio, and returns cleaned text. It is not a general chat assistant.

**Release `v1.1`.** It replaces v1 with better handling of spoken self-corrections; architecture, size, prompt and controls are unchanged. Phone latency and memory of this exact file have not been measured yet. Two public-input BF16 CPU smoke cases ran twice with identical outputs (`bf16-smoke.json`); this is an inference check, not a BF16 quality benchmark.

| File | Bytes | SHA-256 |
|---|---:|---|
| `scribekey-cleanup-fast-350m-v1.1-Q8_0.gguf` | 379,219,904 (361.7 MiB) | `2dfd7463ae0a8ca7dd2e4abebeed9cc77a584569b9c99dc9e68ad85f1399b55a` |

Converted and quantized with llama.cpp `4c1a0af40d88c7fbb3b15c85bf2e8016d1d5b64c`, ScribeKey's runtime pin. Only the download filename changed; the evaluated bytes and internal experiment metadata are preserved. Lower-bit files have not been included because they have not been evaluated.

## Run it

Use raw completion mode and the exact task prompt. The evaluated GGUF retains an inherited LFM chat template; **do not rely on its automatic chat formatting**. `prompt-template.jinja` is a separate task-specific template for integrations that support overriding the embedded template.

```bash
llama-server -m scribekey-cleanup-fast-350m-v1.1-Q8_0.gguf \
  --host 127.0.0.1 --port 8080 -c 4096 -t 2 --temp 0 --seed 42
```

```python
import json
import urllib.request

raw = "um can you send the updated agenda before lunch"
control = "[Styling: semi-casual] [Structure: prose] [Context: general]"
prompt = f"<|startoftext|>### Input:\n{control}\n{raw}\n\n### Output:\n"
request = urllib.request.Request(
    "http://127.0.0.1:8080/completion",
    data=json.dumps({
        "prompt": prompt, "n_predict": 256, "temperature": 0,
        "top_k": 1, "top_p": 1.0, "repeat_penalty": 1.0, "seed": 42,
        "stop": ["###", "<|im_end|>"],
    }).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=60) as response:
    print(json.load(response)["content"].strip())
```

Use one BOS, no system message, no thinking mode and greedy decoding. Controls are styling (`casual`, `semi-casual`, `semi-formal`, `formal`), structure (`prose`, `lists`) and context (`general`, `email`). ScribeKey uses semi-casual/prose by default, semi-formal/email in email apps, and performs list formatting in the app after generation.

## Evidence and limitations

On ScribeKey's frozen held-out set (7,516 rows), paired against v1 under semi-casual/prose/general at the app boundary, v1.1 lowers the self-correction token edit rate by 0.036 (95% −0.046 to −0.026) and raises exact match by 3.3 points (+2.4 to +4.3). Clean-input changes (−0.9 points) and new factual values (−0.3 points, −0.7 to +0.1) are no worse than v1. Names, numbers, negations and omissions still need checking.

Phone latency and memory of this file are not measured; v1, with the same architecture and file size, measured short p50/p95 155/178 ms and long 1,702/2,718 ms on an S25 Ultra. See `evaluation.json`, `examples.json` and the full model card for scope and known limits. Keep raw transcripts and a fallback; output is not guaranteed faithful. Lists and email layout can also be wrong.

## Terms and attribution

The weights inherit **LFM Open License v1.0**, including its commercial revenue condition, not a blanket Apache or MIT licence. Retain [ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md), [LICENSE](LICENSE), [NOTICE](NOTICE) and [MODIFICATIONS.md](MODIFICATIONS.md) when redistributing and mark your changes. Organisations at or above the licence's US$10M annual-revenue threshold should obtain separate terms from Liquid AI before commercial use. Read section 5; this summary is not a legal opinion.

ScribeKey Fast continues Sotto by juanquivilla, based on LFM2.5-350M-Base by Liquid AI. `NOTICE` preserves Sotto's MIT notice and credits the training sources, including CC BY/CC BY-SA data. Those source terms remain distinct; this card does not resolve whether share-alike reaches model weights. Source text/audio and hidden benchmark rows are not distributed. The inherited Sotto data history has not been independently reconstructed. No upstream endorsement is implied. The [ScribeKey Fast Model Terms v1.0](ADDITIONAL_TERMS.md) require the ScribeKey Fast name and ScribeKey publisher credit in model selectors/information and documentation; modified derivatives must credit Derived from ScribeKey Fast by ScribeKey.

`v1.1` replaces the weights of `v1`; terms, prompt and runtime controls are unchanged. The `v1` and RC tags are preserved.
