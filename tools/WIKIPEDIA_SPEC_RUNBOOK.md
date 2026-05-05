# Wikipedia to Spectrum .spec Runbook

This workflow converts Wikimedia `pages-articles` dumps into portable Spectrum
`.spec` shards. It is text-only: article namespace pages are read from the XML
dump, redirects are skipped by default, file/image/media links are stripped in
`clean-text` mode, and each shard is encoded as Spectrum text.

## Full English Wikipedia

As of the April 2026 dump, the English Wikipedia article dump is roughly
24.4 GiB compressed as bzip2 before extraction/encoding:

```powershell
python tools\wiki_dump_to_spec.py `
  --project enwiki `
  --output-dir wiki_spec_enwiki `
  --mode clean-text `
  --chunk-bytes 67108864
```

The script downloads:

```text
https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles-multistream.xml.bz2
```

Outputs:

```text
wiki_spec_enwiki/
  downloads/enwiki-latest-pages-articles-multistream.xml.bz2
  chunks/wiki_000000.spec
  chunks/wiki_000001.spec
  ...
  manifest.json
```

The manifest declares the Spectrum libraries required to interpret the shard
set:

```text
spectrum-core@9
english-text@1
wikimedia-clean-text@1
```

This is the first version of the extension-library model. The dependencies are
stored in the shard manifest, not inside each 16-byte `.spec` header.

## Safer Trial Run

Use Simple English Wikipedia first. Its April 2026 article dump is about
375 MB compressed, so it is much quicker for validating ratios and speed.

```powershell
python tools\wiki_dump_to_spec.py `
  --project simplewiki `
  --output-dir wiki_spec_simplewiki `
  --mode clean-text `
  --chunk-bytes 67108864
```

For a tiny smoke test against any dump:

```powershell
python tools\wiki_dump_to_spec.py `
  --input path\to\pages-articles.xml.bz2 `
  --output-dir wiki_spec_sample `
  --max-pages 1000
```

## Raw Wikitext Variant

If the goal is perfect preservation of article source rather than readable
plain text, use raw wikitext mode:

```powershell
python tools\wiki_dump_to_spec.py `
  --project enwiki `
  --output-dir wiki_spec_enwiki_raw `
  --mode raw-wikitext
```

Raw mode keeps templates, tables, refs, and MediaWiki markup. It is more
complete, but it will compress and search differently because the token stream
contains markup noise.

Raw mode uses dictionary v10 XML/MediaWiki tokens for repeated article-source
syntax while preserving the extracted article wikitext records exactly.

## Full XML Variant

Use full XML mode when the goal is lossless preservation of the decompressed
Wikimedia XML stream rather than extracted article records:

```powershell
python tools\wiki_dump_to_spec.py `
  --input wiki_enwiki_dump\downloads\enwiki-latest-pages-articles-multistream.xml.bz2 `
  --output-dir wiki_spec_enwiki_fullxml `
  --mode full-xml `
  --chunk-bytes 67108864
```

For a bounded test:

```powershell
python tools\wiki_dump_to_spec.py `
  --input wiki_enwiki_dump\downloads\enwiki-latest-pages-articles-multistream.xml.bz2 `
  --output-dir wiki_spec_enwiki_fullxml_sample `
  --mode full-xml `
  --max-input-bytes 16777216 `
  --chunk-bytes 4194304
```

Full XML mode declares:

```text
spectrum-core@10
english-text@1
wikimedia-xml@1
```

It preserves XML structure, revision metadata, templates, links, refs, tables,
categories, and redirects because it tokenizes the decompressed XML stream
directly instead of parsing article records out of it.

## Notes

- Each `.spec` chunk must stay below 4 GiB of original text because the current
  `.spec` header stores `original_length` as uint32.
- `manifest.json` records dump path, dictionary version, article count, text
  bytes, `.spec` bytes, ratio, and per-chunk stats.
- `manifest.json` also records required extension libraries. Decoders should
  verify library name, version, and hash before treating a shard set as
  canonical.
- Dictionary v10 includes core XML/MediaWiki source tokens. Full XML shards use
  language id `9` (`XML/Wiki`) in the `.spec` header.
- Full English Wikipedia will take a long time and needs substantial temporary
  disk space: keep room for the 24+ GiB bzip2 dump plus extracted text volume as
  `.spec` chunks.
- Decoding on Windows PowerShell may need UTF-8 console output:

```powershell
$env:PYTHONIOENCODING='utf-8'
python spec_format\spec_decoder.py wiki_spec_enwiki\chunks\wiki_000000.spec --out decoded.txt
```
