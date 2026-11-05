# Speech model copy

How `bestFor` and `description` in `catalog/speech.yaml` are written. The reader is choosing a
dictation model, not training one. `adding-a-model.md` lists the fields; this file is how to word them.

## Where each field shows

| Field | Android surface | Shape |
|---|---|---|
| `displayName` | Card title, sheet title, Speech settings | The model's own name, unchanged (`Parakeet English`, `Nemotron 3.5 Multilingual Live`) |
| `bestFor` | One line under the card title; the counterpart row in the sheet | One benefit, 48 characters or fewer, no full stop |
| `description` | Sheet, under the title | One or two sentences on what the model does. Never `bestFor` again |

The app derives the rest from facts, so copy must not repeat them:

- **When text appears**: `Live` for `CACHE_AWARE_ONLINE`, `After speaking` for `SEGMENTED`.
- **Languages**: from `languageCodes`, or `languageTiers` (shown as "Many languages", tiers in the sheet).
- **Download size** from `diskMb`, **device requirements** from `minRamMb` and `minApiLevel`.
- **Punctuation, timestamps, language detection** from the `supports*` flags and `streamLanguage`.
- **Experimental** from `experimental`. Do not write "Experimental" in a description.

## Rules

- **One benefit.** `bestFor` answers "why pick this one?". Not a stack of tags: `Live English on phones with 4 GB RAM`,
  not `Live, English, small, accurate`.
- **No unearned ranking.** No "best", "fastest", "most accurate", "highest" or "lowest". A comparison that was
  measured names what it was measured against and where: `Fewer errors than Parakeet Multilingual in tests`,
  with the languages in the description. `bench/asr/README.md` is the evidence for Parakeet Ultra.
  `scribekey-models validate` rejects the ranking words.
- **Offline is not a timing.** Every downloaded model works without internet, so "offline" never describes one
  model; the app says it once above the list. `validate` rejects it.
- **Timing words.** "Live" and "as you speak" mean words appear while the person talks. "When you finish speaking"
  means text arrives at the end of the utterance. Neither means better or worse.
- **Specific hardware.** `phones with 4 GB RAM`, not `low-end phones`. Say RAM for memory and MB for download.
- **Honest coverage.** A tiered model is not "40 languages". Coverage varies; say so.
- **Numbers and units.** `633 MB`, `6 GB RAM`, `25 languages`, a space between number and unit.
- **Sentence case**, active verbs ("Shows", "Transcribes"), "you" for a practical consequence. No em dashes, no
  exclamation marks.
- **Legacy entries** say `Existing installs only` and carry a `replacementId`.

## Before and after

| Avoid | Prefer | Why |
|---|---|---|
| `Most accurate final English` | `English text after you finish speaking` | No measured ranking backs it |
| `Lowest error rate in European languages` | `Fewer errors than Parakeet Multilingual in tests` | Names the comparison that was measured |
| `Live English on 4 GB phones` | `Live English on phones with 4 GB RAM` | Says which memory |
| `Fast speech recognition in East Asian languages` | `Chinese, Cantonese, Japanese and Korean` | Speed was not measured |
| `Offline transcription` | `After speaking` (derived by the app) | Live models are offline too |

## Checklist before a release

1. `scribekey-models validate` passes (length, full stop, distinct from description, wording).
2. Each claim matches the entry's own fields: languages, flags, RAM, API level.
3. Any comparison has a reproducible test in `bench/` and names its baseline.
4. Legacy, experimental and language-tier limits are visible through the fields above, not prose.
