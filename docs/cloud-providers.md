# Cloud providers

The cloud model list is generated, not written by hand. `scribekey-models generate` builds each provider's models and their profiles (price, output limit, temperature support and the reasoning floor) from a pinned models.dev snapshot, and folds in probe evidence from `qualifications/cloud/<provider>/`. The only hand-written part is the per-provider protocol table in `src/scribekey_models/catalog.py` (`CLOUD_PROVIDER_PROTOCOLS`), which says how to send a request and turn reasoning off. Do not add rules that name a model. If a model needs different handling, the probe record should show it, and the profile follows.

The reasoning column is the provider's wire form. Each model's own floor comes from its profile: `openai/gpt-oss-120b` on Groq gets `low`, and a model with no reasoning options gets nothing.

| Provider | Endpoint | Auth header | Token field | How reasoning is turned off | Speech preset | Known quirks | Last verified | Record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| openai | `https://api.openai.com/v1` | `Authorization: Bearer` | `max_completion_tokens` | `reasoning_effort: "none"` (floor per model) | OpenAI (`gpt-transcribe`) | Sends `max_completion_tokens` only for gpt-5, gpt-6 and o* models (fix pending). Speech: no Dictionary keywords sent (UNCONFIRMED field name). Diarize model retires 2027-02-26. | not yet | |
| anthropic | `https://api.anthropic.com/v1` | `x-api-key` plus `anthropic-version: 2023-06-01` | `max_tokens` | `thinking: {type: "disabled"}` where the model has a toggle, otherwise the lowest `output_config.effort` (Sonnet 5.5: `low`) | none | Adaptive thinking is on when `thinking` is unset, and its tokens count toward `max_tokens`. | not yet | |
| gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `Authorization: Bearer` | `max_tokens` | `reasoning_effort: "none"` (Gemini 3.8 Flash floor `low` or `minimal`: UNCONFIRMED) | none | OpenAI-compatible endpoint, not `generateContent`. | not yet | |
| groq | `https://api.groq.com/openai/v1` | `Authorization: Bearer` | `max_tokens` | `reasoning_effort: "none"` | Groq (`whisper-large-v3-turbo`) | The 8 s `Retry-After` cap is too short for the audio-hour limit. Speech `prompt` is capped at 500 bytes. | not yet | |
| cerebras | `https://api.cerebras.ai/v1` | `Authorization: Bearer` | `max_tokens` | `reasoning_effort: "none"` | none | qwen-3.8 reasons at high by default. | not yet | |
| openrouter | `https://openrouter.ai/api/v1` | `Authorization: Bearer` | `max_tokens` | `reasoning: {enabled: false}` | none | `max_tokens` with openai/gpt-5.x is UNCONFIRMED. | not yet | |
| mistral | `https://api.mistral.ai/v1` | `Authorization: Bearer` | `max_tokens` | `reasoning_effort` where the profile lists effort values (Large has none, so nothing is sent) | Mistral (`voxtral-mini-latest`) | Whether small reasons by default is UNCONFIRMED. `voxtral-mini-latest` aliases a model deprecated 2026-10-31. A 400 from `context_bias` fails the segment. | not yet | |
| alibabacloud | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | `Authorization: Bearer` | `max_tokens` | `enable_thinking: false` | none | qwen3.8-max thinks by default and is slow; measure first. | not yet | |
| nvidia | `https://integrate.api.nvidia.com/v1` | `Authorization: Bearer` | `max_tokens` | `chat_template_kwargs: {enable_thinking: false}` | none | Nemotron 3.5 thinks by default and can truncate. models.dev prices every model at $0. | not yet | |
| foundry | Per account (`endpointPerAccount`) | `Authorization: Bearer` and `api-key` | `max_completion_tokens` | `reasoning_effort: "none"` (gpt-5-mini floor `minimal`) | Microsoft Foundry (`MAI-Transcribe-2`) | Sends `max_tokens` today, which reasoning models reject (fix pending). Requests name a deployment, which can differ from its model (UNCONFIRMED). Batch requests have no retry. Word timings probably empty (UNCONFIRMED). Dictionary ignored. | not yet | |

## Not offered as a built-in

- **OpenCode Zen.** Chat and the model list live at different URLs, so one `baseUrl` cannot serve both. Some ids are Responses-only or Messages-only, and filtering on chat completions is UNCONFIRMED. It resells models ScribeKey already reaches directly and adds a party to the data path, with a 4.6% + $0.31 fee per purchase. Its free models log or train on prompts. Use the Custom preset. (#1655)
- **Responses-only models**, such as OpenAI's pro and codex models. They need a Responses adapter, which is deferred for lack of eval evidence. Route them through OpenRouter, which serves them over Chat Completions. (#1664)
- **Gemini native `generateContent` models.** The OpenAI-compatible endpoint already serves all of them, so a native adapter adds no models. (#1664)

## How a provider becomes verified

1. In `scribekey-model-research`, run `skmodels cloud probe` for the provider.
2. Commit the record under `qualifications/cloud/<provider>/`. The generator uses the latest record per provider.
3. Run `scribekey-models generate`, then `scribekey-models validate`, and commit the regenerated `generated/cloud_models.json`.
4. Set the provider's "Last verified" and "Record" cells in the table above to the date and the record file.
