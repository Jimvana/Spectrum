# Spectrum Index

Index owns retrieval over Spectrum data, including BM25, metadata filters, search profiles, incremental indexing, snippet generation, and later sparse or hybrid retrieval.

The first index package wraps the existing Spectrum BM25 indexer/query engine.

```python
from spectrum_index import build_pack_index, search_pack

build_pack_index("./docs.specpack", embed=True)
results = search_pack("./docs.specpack", "authentication middleware", top_k=5)
```

Current API:

- `build_index(target, output_path=None, embed=False)`
- `build_pack_index(pack_path, output_path=None, embed=False)`
- `load_index(path)`
- `search_index(index_or_path, query, top_k=10)`
- `search_pack(pack_path, query, top_k=10)`

The index package stays separate from `packages/core`; core owns lossless storage,
while index owns retrieval sidecars and search behavior.
