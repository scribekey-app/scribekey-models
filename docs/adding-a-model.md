# Adding a model

The canonical model definitions live in `catalog/`. Generated JSON in `generated/` should not be edited by hand.

For a new model:

1. Add or update the relevant YAML file in `catalog/`.
2. Pin the upstream artifact to an immutable revision where the provider supports it.
3. Record the expected file size and SHA-256 digest.
4. Include upstream licence and attribution information.
5. Run `scribekey-models generate`.
6. Run `scribekey-models validate` and `pytest`.

Model weights are not added to Git history. Mirroring is handled separately and only for artifacts whose licence permits redistribution.

Compatibility metadata should describe what ScribeKey actually supports rather than what an upstream runtime might support in theory.


## How the app presents a speech model

Android shows these fields directly, so write them as screen copy (sentence case, no internal names):

| Field | Where it appears | Rule |
| --- | --- | --- |
| `displayName` | Card title, Settings summary | Unique across the catalogue. A legacy entry never shares its replacement's name — suffix it (`Moonshine Base v1`). |
| `bestFor` | The one line under the card title | A phrase of 48 characters or fewer, no full stop. Why someone picks this model. |
| `description` | The info sheet, under the title | One or two sentences saying what the model does. Never a copy of `bestFor`. |
| `languageCodes` | Language names on the card and in the sheet; search | ISO 639 codes, when the languages can be listed. Leave it out for models whose coverage is a count (`1600+ languages`). |
| `counterpartId` | "Live version" / "Final text version" link in the sheet | The same job in the other transcription mode. Must be mutual, cross modes, and point at a selectable model. |
| `provenance` | Model card and licence links in the sheet | Every entry, legacy ones included. |

Retired and deprecated entries stay in the catalogue so existing installs keep working. Give them
`bestFor: Existing installs only` and a `replacementId`; the app groups them under older models.
`scribekey-models validate` enforces the unique-name, distinct-guidance, and counterpart rules.


## How the app presents a cleanup model

Cleanup entries in `catalog/cleanup.yaml` carry the same presentation fields as speech, under the
same rules: `displayName`, `bestFor` (48 characters or fewer, no full stop), `description` (one or
two sentences, never a copy of `bestFor`), `info` (`paramsBadge`, `architecture`, `languages`) and
`provenance` (source model, the exact Hugging Face repository and revision the GGUF comes from, the
quantisation as `exportVariant`, and the SPDX licence). A replaced model stays in the catalogue with
`deprecated: true` and a `replacementId`, so existing installs keep working.

Before a cleanup model is added, screen it with `scribekey-models cleanbench` (see
`bench/README.md`). Only small, cleanup-only models qualify.
