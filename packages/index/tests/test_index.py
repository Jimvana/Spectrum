from __future__ import annotations

from pathlib import Path

from spectrum_core import append_to_pack, pack
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
    assert "embedded index in pack" in summary["progress"]
    assert results
    assert results[0]["path"].endswith("auth.md.spec")
    assert results[0]["source_path"] == "auth.md"


def test_incremental_pack_index_reuses_unchanged_documents(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text("Authentication middleware validates bearer tokens.\n", encoding="utf-8")
    (docs / "billing.md").write_text("Invoices and payment receipts live here.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path)
    build_pack_index(pack_path, embed=True)

    update = tmp_path / "update"
    update.mkdir()
    (update / "billing.md").write_text("Invoices include incremental indexing marker.\n", encoding="utf-8")
    append_to_pack(pack_path, update, replace=True, preserve_index=True)

    summary = build_pack_index(pack_path, embed=True, incremental=True)
    results = search_pack(pack_path, "incremental indexing marker", top_k=1)

    assert summary["incremental"]
    assert summary["incremental_stats"] == {
        "kept": 1,
        "added": 0,
        "changed": 1,
        "deleted": 0,
        "reindexed": 1,
    }
    assert results[0]["source_path"] == "billing.md"


def test_search_pack_filters_generated_results_by_default(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    (docs / "src").mkdir(parents=True)
    (docs / "dist").mkdir()
    (docs / "src" / "app.md").write_text("portable specpack runtime source marker.\n", encoding="utf-8")
    (docs / "dist" / "bundle.md").write_text("portable specpack runtime generated marker.\n", encoding="utf-8")
    pack_path = tmp_path / "docs.specpack"
    pack(docs, pack_path, include_all=True)
    build_pack_index(pack_path, embed=True)

    default_results = search_pack(pack_path, "portable specpack runtime marker", top_k=10)
    archive_results = search_pack(pack_path, "portable specpack runtime marker", top_k=10, include_generated=True)

    assert {result["source_path"] for result in default_results} == {"src/app.md"}
    assert {result["source_path"] for result in archive_results} == {"src/app.md", "dist/bundle.md"}
