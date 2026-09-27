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
| `experimental` | Nowhere by default: the model is listed only once its Advanced Labs toggle is on | `true` for a model still being qualified, and only then give it `badge: Experimental`. Promote it by deleting the flag and the badge in a new release; the app needs no update. Never on a retired or deprecated entry. |

Retired and deprecated entries stay in the catalogue so existing installs keep working. Give them
`bestFor: Existing installs only` and a `replacementId`; the app groups them under older models.
`scribekey-models validate` enforces the unique-name, distinct-guidance, counterpart, and experimental-badge rules.
