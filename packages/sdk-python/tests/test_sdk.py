from __future__ import annotations

from pathlib import Path

from spectrum import Document, SpectrumPack


def test_sdk_create_open_verify_unpack(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_bytes(b"# SDK\r\n\r\nPython SDK round trip.\r\n")
    pack_path = tmp_path / "docs.specpack"

    created = SpectrumPack.create(input_path=docs, output_path=pack_path)
    opened = SpectrumPack.open(pack_path)

    assert created.inspect()["entries"] == 1
    assert opened.verify()["valid"]
    decoded = opened.unpack(tmp_path / "decoded")
    assert decoded[0].path == "note.md"
    assert decoded[0].content_bytes == (docs / "note.md").read_bytes()


def test_sdk_from_documents(tmp_path: Path) -> None:
    pack_path = tmp_path / "memory.specpack"
    pack = SpectrumPack.from_documents(
        [
            Document(
                id="doc-1",
                path="notes/memory.md",
                content="James wants Spectrum to stay local-first.\n",
                metadata={"source": "test"},
            )
        ],
        pack_path,
    )

    assert pack.inspect()["entries"] == 1
    decoded = pack.unpack(tmp_path / "decoded")
    assert decoded[0].path == "notes/memory.md"
    assert decoded[0].content == "James wants Spectrum to stay local-first.\n"


def test_sdk_build_index_and_search(tmp_path: Path) -> None:
    pack_path = tmp_path / "search.specpack"
    pack = SpectrumPack.from_documents(
        [
            Document(id="auth", path="auth.md", content="Authentication middleware validates bearer tokens.\n"),
            Document(id="billing", path="billing.md", content="Invoices and receipts are stored here.\n"),
        ],
        pack_path,
    )

    assert pack.build_index()["embedded"]
    results = pack.search("authentication bearer middleware", top_k=1)
    assert results[0]["path"].endswith("auth.md.spec")
    assert results[0]["source_path"] == "auth.md"
