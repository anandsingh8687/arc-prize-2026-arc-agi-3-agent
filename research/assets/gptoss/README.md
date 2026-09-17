# Offline Harmony vocabulary

`o200k_base.tiktoken.gz` is the gzip-compressed, unchanged official vocabulary:

- Source: https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken
- Uncompressed bytes: `3613922`
- Uncompressed SHA256: `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`
- Rust cache key: `fb374d419588a4632f3f557e76b4b70aebbca790`
- Rust cache directory variable: `TIKTOKEN_RS_CACHE_DIR`
- Source loader: https://github.com/openai/harmony/blob/main/src/tiktoken_ext/public_encodings.rs

The source uses this one file for both O200kBase and O200kHarmony; the cache key is SHA1 of the full source URL. The Hugging Face model's `tokenizer.json` does not replace this asset. An inherited `TIKTOKEN_ENCODINGS_BASE` would change the lookup, so the runtime removes that override when selecting the pinned cache.

Downloaded by `openai-harmony==0.0.8` on 2026-09-17 into a fresh temporary cache. The same library failed with an empty cache under macOS `sandbox-exec` `(deny network*)`, then loaded and rendered a conversation with networking still denied after this file was supplied. No model weights or game data are in this asset.

The notebook loads compressed bytes from the private Kaggle input `anandsingh8687/arc3-harmony-vocab-20260917`, verifies the uncompressed hash, and places them at the cache key before startup. Inlining them was rejected by Kaggle: "The kernel source must be less than 1 megabytes in size." The content checksum pins the bytes even if the dataset pointer changes. The runtime independently validates the file and renders with its own installed Harmony package before starting vLLM. The local package version is not asserted to equal the remote package until that preflight reports it.
