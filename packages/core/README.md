# Spectrum Core

Core owns the open Spectrum format, encode/decode primitives, `.spec` and `.specpack` readers/writers, dictionary handling, metadata handling, version compatibility, and validation.

Planned layout:

- `src/` - implementation.
- `tests/` - format, encode/decode, pack IO, and validation tests.

## Python API

The first core package is Python-based and wraps the existing production Spectrum algorithm modules from the repository root.

```python
from spectrum_core import pack, unpack, verify_pack

pack("./docs", "./docs.specpack")
report = verify_pack("./docs.specpack")
unpack("./docs.specpack", "./decoded")
```

Useful entry points:

- `encode_file(source, output)` - write a `.spec` file.
- `decode_file(spec, output)` - reconstruct source from a `.spec` file.
- `inspect_spec(path)` - read `.spec` header metadata.
- `pack(input_path, output_path)` - create a `.specpack`.
- `unpack(pack_path, output_dir)` - decode a `.specpack`.
- `inspect_pack(pack_path)` - read `.specpack` manifest and size metadata.
- `verify_spec(path)`, `verify_pack(path)`, `verify_path(path)` - validate decode fidelity.

When this package is used outside the repository checkout, set `SPECTRUM_REPO_ROOT` to the Spectrum repo that contains `dictionary.py` and `spec_format/`.

## Portability

Core `.spec` and `.specpack` operations are intended to run on Windows, Linux, and macOS. The encode/decode path preserves source bytes for UTF-8 text, including CRLF line endings, and uses byte writes on decode to avoid platform newline translation.

The legacy PNG encoder imports Pillow only when image output is requested; normal `.spec` core usage does not require Pillow.
