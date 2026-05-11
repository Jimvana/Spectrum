from __future__ import annotations

from pathlib import Path

from spectrum_core import pack
from spectrum_index import PACK_INDEX_NAME, build_pack_index, search_pack


def test_build_embedded_pack_index_and_search(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text("Authentication middleware validates bearer tokens.\n", encoding="utf-8")
    (docs / "billing.md").write_text("Invoices and payment receipts live here.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)

    summary = build_pack_index(pack_path, embed=True)
    results = search_pack(pack_path, "authentication bearer middleware", top_k=1)

    assert summary["embedded"]
    assert summary["documents"] == 2
    assert f"#{PACK_INDEX_NAME}" in summary["index_path"]
    assert results
    assert results[0]["path"].endswith("auth.md.spec")
    assert results[0]["source_path"] == "auth.md"
