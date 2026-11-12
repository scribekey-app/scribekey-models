# Compatibility & Android Consumer Contract

ScribeKey catalogues describe runtime contracts consumed by the Android application.

## Consumer Contract Requirements

The Android client parses published channel manifests (`qa.json`, `stable.json`) and verifies:

1. **Cryptographic Signature**: Detached P-256 / `SHA256withECDSA` signature over exact document bytes.
2. **Anti-Rollback Sequence**: `incoming.sequence > local.sequence`. Updates with non-increasing sequences are rejected.
3. **Compatibility Metadata**:
   ```yaml
   compatibility:
     minAndroidApiLevel: 28
     minAppVersionCode: 10
     catalogsSchemaVersion: 1
     supportedRuntimeFamilies: ["sherpa-onnx", "gguf", "pyannote"]
     supportedConfigFamilies: ["speech-model-catalog", "cleanup-model-catalog", "speaker-diarization-manifest", "cloud-model-tiers", "cloud-model-profiles"]
   ```
   - Android requires `sherpa-onnx` and `speech-model-catalog`, and `gguf` and `cleanup-model-catalog` only when the
     channel carries `cleanup` (`validateCompatibility` in the app's `RemoteModelCatalog.kt`). It ignores families
     it does not know, so adding one never rejects a channel for an older app.
   - Devices below `minAndroidApiLevel` or app versions below `minAppVersionCode` will decline the update.
4. **Execution Safety**: Android strictly rejects any payload referencing executable extensions (`.apk`, `.dex`, `.so`, `.jar`, `.class`, `.sh`, `.bash`, `.exe`, `.elf`, `.bat`, etc.).
5. **Relative URI Paths**: Catalogs are referenced relative to the channel document:
   `../releases/<release-id>/<filename>`
   The client resolves catalog URLs relative to the channel document location.
6. **Optional catalogues**: `catalogs.cloudTiers`, `catalogs.cloudModels`, `catalogs.notes` and `catalogs.search` are optional.
   Android looks catalogues up by key, so an app that predates one ignores it, and adding it to a release
   changes nothing it reads. `notes` needs no new `supportedConfigFamilies` entry, so an older app accepts
   a channel that carries it. A channel only gains `notes` when it is promoted to a release created with it;
   existing releases and their signed channel manifests stay byte-for-byte the same. `search` is the same,
   except that promoting a release that carries it adds `litert-lm` to the channel's
   `supportedRuntimeFamilies` (and to `catalog/channels.yaml`). `litert-lm` appears only alongside `search`.
   Android ignores runtime families it does not know, so older apps still accept the channel.
