---
license: other
license_name: scribekey-fast-model-terms-v1.0-with-lfm-open-license-v1.0
license_link: https://huggingface.co/scribekey/scribekey-cleanup-fast/blob/main/ADDITIONAL_TERMS.md
language:
- en
base_model:
- juanquivilla/sotto-cleanup-lfm25-350m
- LiquidAI/LFM2.5-350M-Base
base_model_relation: finetune
library_name: transformers
pipeline_tag: text-generation
tags:
- transcript-cleanup
- text-normalization
- inverse-text-normalization
- punctuation
- dictation
- lfm2
datasets:
- juanquivilla/sotto-transcript-cleanup
---

# ScribeKey Fast by ScribeKey

A 350M-class English text model for cleaning speech-to-text transcripts on a device. It removes fillers and repetitions, applies spoken corrections, and adjusts punctuation, casing and layout using a control line. It takes **text**, not audio. It is a dedicated cleanup model, not a general assistant.

**Private release candidate: `v1-rc1-attribution`.** This package stages experiment `v7-replay-tgt`. The Q8_0 has offline evaluation; a direct-helper S25 recheck has completed (short p50/p95 155/178 ms; long 1,702/2,718 ms with Parakeet resident), while midrange and product end-to-end qualification remain open. Private staging does not make it ScribeKey's production default. Two public-input BF16 CPU smoke cases also ran twice with identical outputs (`bf16-smoke.json`); this is an inference check, not a BF16 quality benchmark.

## Model overview

| Property | Value |
|---|---|
| Architecture | Liquid AI LFM2.5-350M family, 354,483,968 stored parameters, 16 layers |
| Lineage | LFM2.5-350M-Base → Sotto by juanquivilla → ScribeKey's Sotto v6 → ScribeKey Fast |
| This repository | Merged BF16 weights and tokenizer; 708,984,464-byte weights file |
| On-device artifact | [Q8_0 GGUF](https://huggingface.co/scribekey/scribekey-cleanup-fast-GGUF), 379,219,904 bytes (361.7 MiB) |
| Input | One control line and one English ASR transcript, inside the exact wrapper below |
| Output | Cleaned text only; layout can contain newlines |
| Evaluated app profile | 4,000 input characters, 4,096-token runtime context, at most 256 output tokens |
| Licence | ScribeKey Fast Model Terms v1.0 + LFM Open License v1.0; inherited Sotto MIT notices retained |

The architecture's larger context limit is not a tested cleanup length. Keep dictations short, budget for output and chunk longer text at sentence boundaries. The app's 256-token ceiling can truncate longer generations.

## Quickstart

Use a Transformers version with `Lfm2ForCausalLM` support; the source checkpoint was saved with **Transformers 5.2.0**. No remote model code is required.

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "scribekey/scribekey-cleanup-fast"
REVISION = "v1-rc1-attribution"  # Pin the reviewed commit SHA for a deployment.

tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
model = AutoModelForCausalLM.from_pretrained(
    MODEL, revision=REVISION, dtype=torch.float32,
)
model.eval()

raw = "um can you send the updated agenda before lunch"
control = "[Styling: semi-casual] [Structure: prose] [Context: general]"
messages = [{"role": "user", "content": f"{control}\n{raw}"}]
inputs = tokenizer.apply_chat_template(
    messages, add_generation_prompt=True, tokenize=True,
    return_dict=True, return_tensors="pt",
).to(model.device)
with torch.inference_mode():
    generated = model.generate(**inputs, max_new_tokens=256, do_sample=False)
text = tokenizer.decode(
    generated[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True,
).split("###", 1)[0].strip()
print(text)
```

The shipped template renders exactly the task wrapper below. Send one user message, with the control line first. Do not add a system message or a conversation history. The tokenizer inherited from LFM uses chat tokens for other tasks; an ordinary LFM/ChatML conversation is not this model's training format.

## Exact input format

```text
<|startoftext|>### Input:
[Styling: semi-casual] [Structure: prose] [Context: general]
<raw transcript>

### Output:
```

The last line ends with a newline. Include **one** BOS token (`<|startoftext|>`), the blank line before `### Output:`, and the control values exactly as shown. There is no system prompt and no thinking flag. When tokenizing a hand-built prompt that already contains BOS, use `add_special_tokens=False` to avoid adding another.

Decode greedily (`do_sample=False` / temperature 0). The app uses top-k 1, top-p 1, seed 42 and no repetition penalty. Stop at EOS (`<|im_end|>`) or a new `###` delimiter. Treat partial, empty or malformed output according to your application's fallback policy; filler-only blank output is not guaranteed by this release.

## Controls

| Axis | Values | Intended behaviour |
|---|---|---|
| Styling | `casual`, `semi-casual`, `semi-formal`, `formal` | Lowercase casual through more formal written text; formal expands contractions |
| Structure | `prose`, `lists` | Prose or model-generated list layout; **prose is recommended** |
| Context | `general`, `email` | General text or layout of a greeting/body/sign-off already dictated |

The model was trained across these controls; adherence is imperfect. Its semi-casual convention generally keeps sentence casing and contractions. This differs from S1-mini's semi-casual convention. Never interchange prompts or assume identical outputs because the control-line spelling matches.

ScribeKey's integration chooses semi-casual in chat and other apps, semi-formal plus email layout in email apps, and honours a fixed style chosen by the user. It always sends **prose** to this model. If “Make lists” is enabled, the app's deterministic list formatter runs afterwards. Spelling locale is also an app pass, not another model control. These app behaviours are not part of the standalone weights.

Model lists increased unwanted formatting on ordinary dictation in the preceding `v7-replay` experiment. On the final candidate's 236 development list rows, prose plus app layout scored 35.2% exact against 35.6% for model lists. List recall remained low. Email layout is for dictated greetings and sign-offs; the model must not invent them, and can still make mistakes.

## Recorded examples

These are observed Q8_0 outputs at the pinned runtime, greedy, repeated twice with identical results. They are not invented demonstrations or BF16 measurements; `examples.json` records the controls.

| Input | Style/context | Observed output |
|---|---|---|
| `um can you send the updated agenda before lunch` | semi-casual / general | `Can you send the updated agenda before lunch?` |
| `send it on monday no sorry tuesday` | semi-casual / general | `Send it on tuesday.` |
| `i cant make the call because im on the train` | casual / general | `i cant make the call because im on the train.` |
| `i cant make the call because im on the train` | formal / general | `I cannot make the call because I am on the train.` |
| `we need three things batteries paper and usb c cables` | semi-casual / general | `We need three things: batteries, paper, and USB cables.` |

The second example leaves a day lowercase. The last is a **known meaning-preservation failure**: “USB C” became “USB”, losing a hardware detail. The model is useful but fallible; the intended preservation contract is not a guarantee.

With semi-formal / prose / email, `hi priya could you check the draft before friday thanks sam` produced:

```text
Hi Priya,

Could you check the draft before Friday?

Thanks,
Sam
```

## Evaluation and limits

The following are **Q8_0 results at the ScribeKey app boundary**, not a BF16 benchmark or a claim of error-free cleanup. CleanBench v1 contains 3,366 hidden English cases; 3,358 were scored in this comparison. Inputs use semi-casual / prose / general for this candidate. The Sotto baseline uses its bare-transcript prompt; S1-mini uses its own app-default controls. This is a comparison of deployed profiles, not identical styling for every model.

| Measure | ScribeKey Fast Q8_0 |
|---|---:|
| Inserted exact-match difference versus Sotto v6 | +1.9 percentage points (paired 95% interval −0.1 to +3.9) |
| Inserted token edit rate difference versus Sotto v6 | −0.001 (−0.010 to +0.009; lower is better) |
| Inserted exact-match difference versus S1-mini | −1.2 percentage points (−3.3 to +1.1) |
| Inserted token edit rate difference versus S1-mini | −0.008 |
| Self-corrections | 20.5% |
| Questions kept, under the benchmark's metric | 24.2% |
| New-value rate, under the benchmark's metric | 4.6% |

The intervals do not establish superiority over Sotto or equivalence to S1-mini. The candidate met the experiment's provisional non-regression criteria; the broader release bar remains unresolved. These values are specific benchmark metrics, not universal accuracy rates. The new-value rate is a real limitation: check names, dates, amounts, negations and important details before using the output. Keep a recoverable raw transcript.

Phone results often quoted for this family are for **the preceding `v7-replay` artifact**, not this package: S25 Ultra long-input warm p50/p95 1,696/2,101 ms, short-input 156/178 ms, peak combined PSS 1,567 MiB on the measured app/ASR build. They are context, not final-artifact performance claims. Midrange performance and a minimum-device guarantee are unverified. The draft catalogue retains a conservative 6 GB device-memory floor.

## Training and provenance

This is a continuation of ScribeKey's Sotto v6, rebuilt from its production Q8_0 because the original merged weights were lost. The rebuilt v6 re-export matched all 148 production tensors at Q8_0 precision. This run starts from that dequantized point, not the lost original BF16 checkpoint.

Continued training used 4,350 rows: 2,000 pilot training rows, 2,000 Sotto public replay rows and 350 targeted correction/question rows. LoRA rank 16, alpha 32, three epochs, learning rate 0.0004, effective batch 8, unpacked 1,024-token sequences; merged into BF16. The final mix SHA-256 is `9a978c3f3a8cc140852fd19acea8280beeb75ac206abeae2a14f69822d60df73`.

`NOTICE` records the actual source/component attributions, including Common Voice, People's Speech, Handy, dictation-speech, the teacher models and TTS/ASR tooling. The Sotto replay revision is pinned in `provenance.json`. Training text, source recordings and hidden benchmark cases are not distributed in this repository. Third-party declarations in the inherited Sotto lineage have not been independently reconstructed. Fine-tuning does not remove inherited terms or guarantee that a model never reproduces source text.

## Using ScribeKey Fast in your app

Place it after ASR: **audio → your recogniser → raw transcript → ScribeKey Fast → reviewed text**. On-device inference can keep transcripts on the device; a hosted deployment has the privacy properties of its host. Choose the controls explicitly, retain the raw text, test important cases and provide a fallback. Do not treat dictated questions or commands as instructions for a tool to execute.

Ship `ADDITIONAL_TERMS.md`, `LICENSE`, `NOTICE` and `MODIFICATIONS.md` with redistributions. The [ScribeKey Fast Model Terms v1.0](ADDITIONAL_TERMS.md) require the name **ScribeKey Fast** and publisher credit **ScribeKey** in model selectors/information and documentation; modified derivatives must credit **Derived from ScribeKey Fast by ScribeKey**. Retain upstream attribution and identify your changes. Attribution does not imply endorsement.

## Licence and commercial use

The [ScribeKey Fast Model Terms v1.0](ADDITIONAL_TERMS.md) add model naming and attribution requirements. The weights also inherit **LFM Open License v1.0**. This is not an Apache-2.0-only or MIT-only model. Read the full [LICENSE](LICENSE), especially sections 4 (redistribution), 5 (commercial use) and 7 (trademarks), and retain the Sotto MIT text in [NOTICE](NOTICE).

The licence defines a US$10 million annual-revenue threshold and conditions commercial use on section 5. Organisations at or above that threshold should obtain separate terms from Liquid AI before commercial deployment. This summary is guidance, not a replacement for the licence or a legal opinion. The metadata/tooling repository's Apache-2.0 licence does not override the weights' terms.

Some training sources carry CC BY or CC BY-SA licences. They are credited separately; their text/audio is not relicensed here. The reach of share-alike obligations to trained weights is not settled by this model card. Review your distribution and source-reproduction risks before public or commercial use. The licence includes warranty and liability disclaimers; the model can alter or omit meaning despite its intended behaviour.

## Citation

```bibtex
@misc{scribekeyfast2026,
  title = {ScribeKey Fast: on-device English transcript cleanup},
  author = {ScribeKey},
  year = {2026},
  url = {https://huggingface.co/scribekey/scribekey-cleanup-fast}
}
```

The `v1-rc1-attribution` update changes documentation and terms only; weight bytes and prompt/runtime controls are unchanged from `v1-rc1`. The original tag is preserved.
