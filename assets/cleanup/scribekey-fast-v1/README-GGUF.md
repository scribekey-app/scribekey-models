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

**Release `v1`**, experiment `v7-replay-tgt`. This Q8_0 is ScribeKey's on-device cleanup model, replacing Sotto. Direct-helper S25 Ultra timing of this exact file is complete; midrange and product end-to-end performance have not been measured. Two public-input BF16 CPU smoke cases also ran twice with identical outputs (`bf16-smoke.json`); this is an inference check, not a BF16 quality benchmark.

| File | Bytes | SHA-256 |
|---|---:|---|
| `scribekey-cleanup-fast-350m-v1-Q8_0.gguf` | 379,219,904 (361.7 MiB) | `bbce6fe5dc52080366ea65768f96e8d6265c45c1925d9a2e3d03de32856295cc` |

Converted and quantized with llama.cpp `4c1a0af40d88c7fbb3b15c85bf2e8016d1d5b64c`, ScribeKey's runtime pin. Only the download filename changed; the evaluated bytes and internal experiment metadata are preserved. Lower-bit files have not been included because they have not received this candidate's quality evaluation.

## Run it

Use raw completion mode and the exact task prompt. The evaluated GGUF retains an inherited LFM chat template; **do not rely on its automatic chat formatting**. `prompt-template.jinja` is a separate task-specific template for integrations that support overriding the embedded template.

```bash
llama-server -m scribekey-cleanup-fast-350m-v1-Q8_0.gguf \
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

Use one BOS, no system message, no thinking mode and greedy decoding. Controls are styling (`casual`, `semi-casual`, `semi-formal`, `formal`), structure (`prose`, `lists`) and context (`general`, `email`). ScribeKey uses semi-casual/prose by default, semi-formal/email in email apps, and performs list formatting in the app after generation. This model's casing conventions differ from S1-mini's despite the shared control-line shape.

## Evidence and limitations

On hidden CleanBench v1 (3,366 cases, 3,358 scored), under semi-casual/prose/general at the app boundary, this Q8_0 differs from Sotto v6 by +1.9 percentage points inserted exact (95% −0.1 to +3.9) and −0.001 token edit rate (−0.010 to +0.009). It differs from S1-mini by −1.2 points exact (−3.3 to +1.1). These intervals do not establish superiority or equivalence. The benchmark new-value metric is 4.6%; names, numbers, negations and omissions need checking.

The frequently quoted S25 Ultra long-input p95 of 2,101 ms belongs to **v7-replay**, not this final candidate. The final-artifact S25 direct-helper recheck measured short p50/p95 155/178 ms and long 1,702/2,718 ms with Parakeet resident; midrange and product end-to-end qualification remain pending. See `evaluation.json`, `examples.json` and the full model card for scope and known limits. Keep raw transcripts and a fallback; output is not guaranteed faithful. Lists and email layout can also be wrong.

## Terms and attribution

The weights inherit **LFM Open License v1.0**, including its commercial revenue condition, not a blanket Apache or MIT licence. Retain [ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md), [LICENSE](LICENSE), [NOTICE](NOTICE) and [MODIFICATIONS.md](MODIFICATIONS.md) when redistributing and mark your changes. Organisations at or above the licence's US$10M annual-revenue threshold should obtain separate terms from Liquid AI before commercial use. Read section 5; this summary is not a legal opinion.

ScribeKey Fast continues Sotto by juanquivilla, based on LFM2.5-350M-Base by Liquid AI. `NOTICE` preserves Sotto's MIT notice and credits the training sources, including CC BY/CC BY-SA data. Those source terms remain distinct; this card does not resolve whether share-alike reaches model weights. Source text/audio and hidden benchmark rows are not distributed. The inherited Sotto data history has not been independently reconstructed. No upstream endorsement is implied. The [ScribeKey Fast Model Terms v1.0](ADDITIONAL_TERMS.md) require the ScribeKey Fast name and ScribeKey publisher credit in model selectors/information and documentation; modified derivatives must credit Derived from ScribeKey Fast by ScribeKey.

The `v1` release is the public `v1-rc1-attribution` package with updated card wording; weight bytes, terms and prompt/runtime controls are unchanged from `v1-rc1`. The original RC tags are preserved.
