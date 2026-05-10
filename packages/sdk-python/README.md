# Spectrum Python SDK

The Python SDK owns the public Python API for packing, searching, decoding, verifying, and managing Spectrum stores.

Current package name: `spectrum-ai`.

Import name:

```python
from spectrum import Document, SpectrumPack
```

Create a pack from a folder:

```python
pack = SpectrumPack.create(
    input_path="./docs",
    output_path="./docs.specpack",
)

print(pack.inspect())
print(pack.verify())
```

Create a pack from in-memory documents:

```python
pack = SpectrumPack.from_documents(
    [
        Document(
            id="doc-1",
            path="notes/memory.md",
            content="Spectrum should stay local-first.",
            metadata={"source": "example"},
        )
    ],
    "./memory.specpack",
)
```

Decode a pack:

```python
decoded = pack.unpack("./decoded")
print(decoded[0].content)
```

Search and incremental document updates will be added after the index and memory packages are split out under `packages/`.
