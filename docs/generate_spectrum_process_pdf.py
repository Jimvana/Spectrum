from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
)


OUT = Path(__file__).with_name("spectrum_process_explainer.pdf")

PALETTE = {
    "blue": colors.HexColor("#2D9CDB"),
    "green": colors.HexColor("#27AE60"),
    "yellow": colors.HexColor("#F2C94C"),
    "orange": colors.HexColor("#F2994A"),
    "red": colors.HexColor("#EB5757"),
    "purple": colors.HexColor("#9B51E0"),
    "ink": colors.HexColor("#1F2937"),
    "muted": colors.HexColor("#5B677A"),
    "paper": colors.HexColor("#FFFDF7"),
    "pale_blue": colors.HexColor("#EAF6FF"),
    "pale_green": colors.HexColor("#EAF9F0"),
    "pale_yellow": colors.HexColor("#FFF7D6"),
    "pale_orange": colors.HexColor("#FFF0E1"),
}


def styles():
    base = getSampleStyleSheet()
    base.add(
        ParagraphStyle(
            name="TitleBig",
            parent=base["Title"],
            fontSize=34,
            leading=38,
            textColor=PALETTE["ink"],
            alignment=TA_CENTER,
            spaceAfter=12,
        )
    )
    base.add(
        ParagraphStyle(
            name="Subtitle",
            parent=base["BodyText"],
            fontSize=14,
            leading=20,
            textColor=PALETTE["muted"],
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    base.add(
        ParagraphStyle(
            name="Section",
            parent=base["Heading1"],
            fontSize=22,
            leading=26,
            textColor=PALETTE["ink"],
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    base.add(
        ParagraphStyle(
            name="SmallHeading",
            parent=base["Heading2"],
            fontSize=14,
            leading=17,
            textColor=PALETTE["ink"],
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    base.add(
        ParagraphStyle(
            name="BodyLarge",
            parent=base["BodyText"],
            fontSize=11.5,
            leading=16,
            textColor=PALETTE["ink"],
            spaceAfter=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="Tiny",
            parent=base["BodyText"],
            fontSize=8.2,
            leading=10,
            textColor=PALETTE["muted"],
        )
    )
    base.add(
        ParagraphStyle(
            name="White",
            parent=base["BodyText"],
            fontSize=10,
            leading=12,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
    )
    return base


class BubbleFlow(Flowable):
    def __init__(self, labels: list[tuple[str, str]], width=9.4 * inch, height=1.45 * inch):
        super().__init__()
        self.labels = labels
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        colors_list = [PALETTE["blue"], PALETTE["green"], PALETTE["yellow"], PALETTE["orange"], PALETTE["purple"]]
        step = self.width / len(self.labels)
        y = self.height * 0.5
        for i, (title, note) in enumerate(self.labels):
            x = step * i + step * 0.5
            fill = colors_list[i % len(colors_list)]
            c.setFillColor(fill)
            c.setStrokeColor(colors.white)
            c.setLineWidth(2)
            c.roundRect(x - 0.58 * inch, y - 0.33 * inch, 1.16 * inch, 0.66 * inch, 12, fill=1, stroke=1)
            c.setFillColor(colors.white if fill != PALETTE["yellow"] else PALETTE["ink"])
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(x, y + 5, title)
            c.setFont("Helvetica", 7.7)
            c.drawCentredString(x, y - 9, note)
            if i < len(self.labels) - 1:
                c.setStrokeColor(PALETTE["ink"])
                c.setLineWidth(1.5)
                c.line(x + 0.65 * inch, y, x + step - 0.65 * inch, y)
                c.setFillColor(PALETTE["ink"])
                c.circle(x + step - 0.65 * inch, y, 2.5, fill=1, stroke=0)


class LibraryFlow(Flowable):
    def __init__(self, width=9.4 * inch, height=3.6 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(PALETTE["pale_blue"])
        c.roundRect(0, 0, w, h, 16, fill=1, stroke=0)
        c.setStrokeColor(PALETTE["blue"])
        c.setLineWidth(2)
        c.roundRect(0, 0, w, h, 16, fill=0, stroke=1)

        shelf_x = 0.45 * inch
        shelf_y = 0.55 * inch
        shelf_w = 3.2 * inch
        shelf_h = 2.35 * inch
        c.setFillColor(colors.white)
        c.roundRect(shelf_x, shelf_y, shelf_w, shelf_h, 10, fill=1, stroke=0)
        c.setStrokeColor(PALETTE["ink"])
        for row in range(3):
            y = shelf_y + 0.45 * inch + row * 0.6 * inch
            c.line(shelf_x + 0.18 * inch, y, shelf_x + shelf_w - 0.18 * inch, y)
        book_cols = [PALETTE["red"], PALETTE["orange"], PALETTE["green"], PALETTE["purple"], PALETTE["blue"]]
        for row in range(3):
            for i in range(7):
                x = shelf_x + 0.28 * inch + i * 0.38 * inch
                y = shelf_y + 0.5 * inch + row * 0.6 * inch
                c.setFillColor(book_cols[(i + row) % len(book_cols)])
                c.roundRect(x, y, 0.22 * inch, 0.45 * inch, 3, fill=1, stroke=0)
        c.setFillColor(PALETTE["ink"])
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(shelf_x + shelf_w / 2, shelf_y + shelf_h + 0.18 * inch, ".spec payloads")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(shelf_x + shelf_w / 2, shelf_y + 0.14 * inch, "The books: exact chapters stored compactly")

        card_x = 4.05 * inch
        card_y = 0.75 * inch
        for i, label in enumerate(["index.bin", "docs.json", "snippet sidecar"]):
            y = card_y + i * 0.75 * inch
            c.setFillColor([PALETTE["pale_yellow"], PALETTE["pale_green"], PALETTE["pale_orange"]][i])
            c.roundRect(card_x, y, 1.75 * inch, 0.52 * inch, 8, fill=1, stroke=0)
            c.setFillColor(PALETTE["ink"])
            c.setFont("Helvetica-Bold", 9.5)
            c.drawCentredString(card_x + 0.875 * inch, y + 0.31 * inch, label)
            c.setFont("Helvetica", 7.5)
            sub = ["card catalog", "shelf map", "preview cards"][i]
            c.drawCentredString(card_x + 0.875 * inch, y + 0.14 * inch, sub)
        c.setStrokeColor(PALETTE["ink"])
        c.line(3.75 * inch, 1.7 * inch, 4.0 * inch, 1.7 * inch)

        c.setFillColor(PALETTE["green"])
        c.circle(6.8 * inch, 2.3 * inch, 0.32 * inch, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(6.8 * inch, 2.2 * inch, "?")
        c.setFillColor(PALETTE["ink"])
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(7.65 * inch, 2.55 * inch, "Question")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(7.65 * inch, 2.35 * inch, "Query text becomes token IDs")

        c.setFillColor(PALETTE["purple"])
        c.roundRect(6.35 * inch, 0.85 * inch, 2.35 * inch, 0.78 * inch, 10, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawCentredString(7.525 * inch, 1.25 * inch, "Decoder librarian")
        c.setFont("Helvetica", 8)
        c.drawCentredString(7.525 * inch, 1.06 * inch, "opens only the chosen book")
        c.setStrokeColor(PALETTE["ink"])
        c.line(5.85 * inch, 1.7 * inch, 6.35 * inch, 2.2 * inch)
        c.line(5.85 * inch, 1.45 * inch, 6.35 * inch, 1.2 * inch)


class SpecFileFlow(Flowable):
    def __init__(self, width=9.4 * inch, height=2.35 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        x, y = 0.25 * inch, 0.35 * inch
        c.setFillColor(PALETTE["pale_yellow"])
        c.roundRect(x, y, 8.9 * inch, 1.6 * inch, 14, fill=1, stroke=0)
        parts = [
            ("SPEC", 0.75, PALETTE["red"]),
            ("dict v12", 1.05, PALETTE["orange"]),
            ("flags", 0.8, PALETTE["green"]),
            ("orig length", 1.2, PALETTE["blue"]),
            ("language", 1.05, PALETTE["purple"]),
            ("checksum", 1.05, PALETTE["red"]),
            ("zlib token ID body", 2.05, PALETTE["ink"]),
        ]
        px = x + 0.25 * inch
        for label, width_in, fill in parts:
            pw = width_in * inch
            c.setFillColor(fill)
            c.roundRect(px, y + 0.7 * inch, pw, 0.46 * inch, 6, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawCentredString(px + pw / 2, y + 0.86 * inch, label)
            px += pw + 0.08 * inch
        c.setFillColor(PALETTE["ink"])
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x + 4.45 * inch, y + 1.32 * inch, "A .spec file is a labeled lunchbox")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(
            x + 4.45 * inch,
            y + 0.38 * inch,
            "The first 16 bytes say how to read it. The body is compressed uint32 token IDs.",
        )


def pill(text: str, fill):
    return Table(
        [[Paragraph(text, ST["White"])]],
        style=[
            ("BACKGROUND", (0, 0), (-1, -1), fill),
            ("BOX", (0, 0), (-1, -1), 0, fill),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ],
    )


def para(text: str, style="BodyLarge"):
    return Paragraph(text, ST[style])


def bullets(items: list[str]):
    return ListFlowable(
        [ListItem(para(item), bulletColor=PALETTE["blue"]) for item in items],
        bulletType="bullet",
        start="circle",
        leftIndent=16,
    )


def colored_table(data, widths, header=True):
    style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), PALETTE["blue"]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E2EC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for r in range(1 if header else 0, len(data)):
        style.append(("BACKGROUND", (0, r), (-1, r), PALETTE["paper"] if r % 2 else colors.white))
    return Table(data, colWidths=widths, repeatRows=1 if header else 0, style=style)


def section(title: str):
    return [Paragraph(title, ST["Section"])]


def build_story():
    story = []
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("How Spectrum Stores, Serves, and Reads Files", ST["TitleBig"]))
    story.append(
        Paragraph(
            "A bright guide to the Spectrum process: from a corpus, to .spec storage, to fast search, to exact decoding.",
            ST["Subtitle"],
        )
    )
    story.append(BubbleFlow([
        ("Corpus", "books arrive"),
        ("Encode", "make compact IDs"),
        ("Index", "build catalog"),
        ("Serve", "answer questions"),
        ("Decode", "open exact text"),
    ]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        colored_table(
            [
                [para("<b>Kid version</b>"), para("<b>Engineer version</b>")],
                [
                    para("Spectrum is like a library that squeezes books onto tiny shelves, keeps a smart card catalog, and asks the librarian to open only the book you need."),
                    para("Spectrum stores source text losslessly as .spec token streams, builds compact retrieval postings, serves snippets and metadata first, then hydrates selected payloads by decoding .spec bytes back to exact text."),
                ],
            ],
            [4.5 * inch, 4.5 * inch],
        )
    )
    story.append(PageBreak())

    story.extend(section("The Library Picture"))
    story.append(LibraryFlow())
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        colored_table(
            [
                [para("<b>Library thing</b>"), para("<b>Spectrum thing</b>"), para("<b>What it does</b>")],
                [para("Book"), para(".spec payload"), para("Stores the original chapter exactly, but in compact token-ID form.")],
                [para("Shelf label"), para("docs.json"), para("Maps document IDs to titles, paths, chunk numbers, language IDs, and sizes.")],
                [para("Card catalog"), para("index.bin / postings"), para("Says which documents contain which meaningful tokens, so search can skip most books.")],
                [para("Bookmark card"), para("snippet sidecar"), para("Shows a small preview without opening and decoding the whole .spec file.")],
                [para("Librarian"), para("decoder"), para("Rebuilds the exact original text when a result is selected.")],
            ],
            [1.65 * inch, 2.1 * inch, 5.25 * inch],
        )
    )
    story.append(PageBreak())

    story.extend(section("1. Encoding From a Corpus"))
    story.append(
        para(
            "A corpus is the pile of source material: code files, text documents, notes, or mixed project folders. Spectrum first chooses how to read that material, then turns the text into a stream of stable token IDs."
        )
    )
    story.append(BubbleFlow([
        ("Read", "files/pages"),
        ("Chunk", "useful pieces"),
        ("Tokenize", "words/code bits"),
        ("ID map", "dictionary nums"),
        ("Compress", "RLE + zlib"),
    ]))
    story.append(SpecFileFlow())
    story.append(
        colored_table(
            [
                [para("<b>Step</b>"), para("<b>What Spectrum uses</b>"), para("<b>Where to look</b>")],
                [para("Read corpus"), para("Filesystem scanning, repo/demo inputs, JSONL records, or UTF-8 text directories."), para("CLI Tool/spectrum_cli/main.py, rag/storage_benchmark.py")],
                [para("Choose tokenizer"), para("Extension/language mapping selects Python, JS, CSS, text, XML-compatible, Java, C/C++, Go, C#, shell, JSON/YAML/TOML, and more."), para("spec_format/spec_encoder.py, tokenizers/")],
                [para("Map tokens to IDs"), para("Known tokens become dictionary IDs. Unknown ASCII or Unicode characters use fallback IDs so the file stays lossless."), para("dictionary.py, english_tokens.py, spec_format/extension_tokens.py")],
                [para("Shrink runs"), para("Repeated IDs can be encoded with an RLE marker. Then the ID stream is zlib-compressed."), para("spec_format/spec_encoder.py")],
                [para("Write .spec"), para("Header stores magic bytes, dictionary version, flags, original length, language ID, and checksum. Body stores compressed uint32 IDs."), para("spec_format/spec_encoder.py")],
            ],
            [1.45 * inch, 4.35 * inch, 3.2 * inch],
        )
    )
    story.append(Spacer(1, 0.08 * inch))
    story.append(para("<b>Important rule:</b> the .spec payload must not throw away bytes. Retrieval tricks live beside it, not inside it.", "BodyLarge"))
    story.append(PageBreak())

    story.extend(section("2. Building the Search Catalog"))
    story.append(
        para(
            "After the books are stored, Spectrum builds the library catalog. It reads token IDs from the .spec files and keeps the useful retrieval tokens. It does not need to decode every file back to raw source text just to build the catalog."
        )
    )
    story.append(
        colored_table(
            [
                [para("<b>Catalog part</b>"), para("<b>Job</b>"), para("<b>Format</b>")],
                [para("Document rows"), para("One row per chunk/document: ID, path, title, language, original length, token count."), para("docs.json")],
                [para("Frequency vectors"), para("For each document, count how often meaningful token IDs appear."), para("in-memory during build")],
                [para("Inverted postings"), para("For each token ID, list the documents containing it, plus term frequency."), para("SPB1 or SPB2 binary index")],
                [para("Snippet sidecar"), para("Small preview strings used for result lists so full decode can wait."), para("snippet_sidecar.json or built from chunks.jsonl")],
            ],
            [2.0 * inch, 4.4 * inch, 2.6 * inch],
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        para(
            "The newest compact postings path uses SPB2: document IDs are stored as gaps and numbers are encoded as variable-length integers. That makes the catalog smaller, like writing shelf numbers as short directions instead of full addresses every time."
        )
    )
    story.append(
        bullets(
            [
                "Search scoring uses BM25: rare useful words usually count more than words found everywhere.",
                "Candidate selection can drop very common tokens and focus on rare, path-like, or identifier-like tokens.",
                "Code reranking can add signals from paths, filenames, identifiers, function/class names, imports, and proximity.",
            ]
        )
    )
    story.append(PageBreak())

    story.extend(section("3. Serving the Spectrum Store"))
    story.append(
        para(
            "Serving is the part that answers questions quickly. The server loads metadata and the postings catalog, turns the user's question into Spectrum token IDs, finds likely documents, returns snippets, and only decodes the full payload when needed."
        )
    )
    story.append(BubbleFlow([
        ("Question", "query text"),
        ("Tokens", "query IDs"),
        ("Postings", "candidate docs"),
        ("Rank", "BM25 + boosts"),
        ("Snippet", "fast preview"),
    ]))
    story.append(
        colored_table(
            [
                [para("<b>Serving action</b>"), para("<b>What happens</b>"), para("<b>Code path</b>")],
                [para("Load store"), para("If a .specpack exists, open it as a zip and read docs.json plus index.bin. Otherwise read a spectrum_spec directory."), para("rag/spectrum_serving.py")],
                [para("Preload or lazy-load .spec bytes"), para("Payload bytes may be kept in RAM or read from the pack/file only when needed."), para("SpectrumServingRetriever.__init__")],
                [para("Search"), para("Normalize query to token IDs, ask the binary BM25 postings index for candidates, then optionally rerank."), para("search_ids_with_trace")],
                [para("Return result list"), para("Return title, source path, rank, and a windowed snippet. No full decode required for the list view."), para("search, windowed_snippet")],
                [para("Hydrate selected result"), para("Decode selected .spec bytes and cache the decoded text for repeated access."), para("decode")],
            ],
            [1.85 * inch, 4.5 * inch, 2.65 * inch],
        )
    )
    story.append(PageBreak())

    story.extend(section("4. Decoding Back to the Exact Text"))
    story.append(
        para(
            "Decoding is the librarian opening the chosen book and putting every word, space, and symbol back in the right place. It uses the header to know which dictionary version and language rules apply."
        )
    )
    story.append(BubbleFlow([
        ("Header", "read labels"),
        ("zlib", "inflate body"),
        ("uint32", "unpack IDs"),
        ("Tokens", "expand IDs"),
        ("Text", "rebuild bytes"),
    ]))
    story.append(
        colored_table(
            [
                [para("<b>Decode step</b>"), para("<b>Why it matters</b>")],
                [para("Parse 16-byte header"), para("Checks magic bytes, dictionary version, flags, original byte length, language ID, and checksum.")],
                [para("Choose token table"), para("Current dictionary is used for current files; frozen old dictionaries allow older files to decode.")],
                [para("Decompress body"), para("zlib turns compressed bytes back into a raw uint32 ID stream.")],
                [para("Expand special IDs"), para("RLE markers repeat prior tokens; ASCII and Unicode fallback IDs become characters; dictionary IDs become stored token strings.")],
                [para("Reconstruct text"), para("Plain text and XML-compatible payloads can use text reconstruction controls; code-like languages mostly join token strings.")],
                [para("Verify length/checksum"), para("Confirms the decoded result matches the original byte length and checksum.")],
            ],
            [2.35 * inch, 6.65 * inch],
        )
    )
    story.append(PageBreak())

    story.extend(section("Outside Resources and Dependencies"))
    story.append(
        para(
            "Spectrum's core .spec encode/decode path is mostly local Python plus its own dictionary and tokenizer files. Some benchmark, corpus, runtime, and optional acceleration paths use outside libraries or outside data."
        )
    )
    story.append(
        colored_table(
            [
                [para("<b>Area</b>"), para("<b>Dependency/resource</b>"), para("<b>Used for</b>")],
                [para("Core encode/decode"), para("Python standard library: struct, zlib, pathlib, sys, warnings"), para("Binary headers, compressed token body, paths, version handling.")],
                [para("Dictionary"), para("dictionary.py and generated english_tokens.py"), para("Stable token IDs and large English word coverage.")],
                [para("Tokenizers"), para("Local tokenizers/ package"), para("Language-aware splitting for code, text, XML-compatible input, and config formats.")],
                [para("Extension compatibility"), para("spec_format/extension_tokens.py"), para("Preserves decoding compatibility for older extension-token payloads.")],
                [para("Corpus input"), para("Local files, JSONL records, or cloned repositories"), para("Builds benchmark/demo corpora without relying on a specific external corpus.")],
                [para("RAG benchmarks"), para("numpy, scipy, scikit-learn"), para("Conventional TF-IDF baseline and benchmark comparison store; not required for basic .spec decode.")],
                [para("Serving store"), para("json, zipfile, re, dataclasses; local binary postings"), para("Read .specpack zip bundles, docs metadata, snippets, and query features.")],
                [para("Optional native decode"), para("Rust crate under native/spectrum_native"), para("Faster byte-prism decoding path when available, with Python fallback.")],
                [para("CLI/runtime"), para("Node/npm for CLI packaging and browser runtime files"), para("spectrum command, JS decoder/service-worker experiments, and web serving shim.")],
                [para("External demo inputs"), para("User-provided repos or cloned GitHub repositories"), para("Building demo corpora and .specpack benchmark outputs.")],
            ],
            [1.8 * inch, 3.0 * inch, 4.2 * inch],
        )
    )
    story.append(PageBreak())

    story.extend(section("One Walk Through"))
    story.append(para("<b>Imagine a tiny library with three books:</b> app.py, style.css, and notes.md.", "BodyLarge"))
    story.append(
        bullets(
            [
                "The encoder reads each book and picks the right reading glasses: Python tokenizer, CSS tokenizer, or text tokenizer.",
                "Words and code pieces become numbered library stickers from the Spectrum dictionary.",
                "Repeated stickers are shortened with RLE, then the sticker list is zipped with zlib and placed in .spec books.",
                "The catalog maker records which stickers appear in which books and writes index.bin plus docs.json.",
                "When a child asks, 'Where is the button color?', the librarian turns that question into stickers too.",
                "The catalog points to likely books quickly. The result list shows a bookmark snippet.",
                "Only when the child opens a result does the decoder rebuild the full original file exactly.",
            ]
        )
    )
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        colored_table(
            [
                [para("<b>What stays true</b>"), para("<b>What can change by profile</b>")],
                [
                    para(".spec payloads are meant to be lossless and portable. Dictionary IDs are append-only across versions, and older snapshots help decode older files."),
                    para("Chunk sizes, overlap, BM25 settings, title/path boosts, sidecars, rerank depth, and corpus preprocessing can change per corpus profile."),
                ],
            ],
            [4.5 * inch, 4.5 * inch],
        )
    )
    story.append(PageBreak())

    story.extend(section("Repo Map"))
    repo_rows = [
        [para("<b>File or folder</b>"), para("<b>Why it matters</b>")],
        [para("spec_format/spec_encoder.py"), para("Writes .spec headers and compressed token ID bodies.")],
        [para("spec_format/spec_decoder.py"), para("Reads .spec files and reconstructs exact text.")],
        [para("dictionary.py, english_tokens.py"), para("Stable core dictionary and generated English token list.")],
        [para("tokenizers/"), para("Language-aware tokenizers used before ID mapping.")],
        [para("rag/indexer.py"), para("Builds retrieval indexes from .spec files without full source decode.")],
        [para("rag/storage_benchmark.py"), para("Builds Spectrum stores, docs.json, binary postings, and benchmark baselines.")],
        [para("rag/spectrum_serving.py"), para("Production-shaped serving retriever: load pack, search, snippets, decode selected payloads.")],
        [para("rag/query.py"), para("Encodes queries and BM25 search over Spectrum indexes.")],
        [para("tools/build_hf_retrieval_corpus.py"), para("Builds local retrieval corpora for storage and serving experiments.")],
        [para("CLI Tool/spectrum_cli/main.py"), para("Public CLI encode/archive/index/search/demo commands.")],
        [para("Runtime/"), para("Browser/service-worker and JS runtime experiments for serving .spec-backed web projects.")],
        [para("native/spectrum_native/"), para("Optional Rust decoder acceleration path.")],
    ]
    story.append(colored_table(repo_rows, [2.8 * inch, 6.2 * inch]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(para("Generated from local repository context on 2026-05-09.", "Tiny"))
    return story


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PALETTE["paper"])
    canvas.rect(0, 0, landscape(letter)[0], landscape(letter)[1], fill=1, stroke=0)
    canvas.setFillColor(PALETTE["blue"])
    canvas.rect(0, landscape(letter)[1] - 0.18 * inch, landscape(letter)[0], 0.18 * inch, fill=1, stroke=0)
    canvas.setFillColor(PALETTE["green"])
    canvas.rect(0, 0, landscape(letter)[0], 0.12 * inch, fill=1, stroke=0)
    canvas.setFillColor(PALETTE["muted"])
    canvas.setFont("Helvetica", 8)
    footer = f"Spectrum process explainer - page {doc.page}"
    canvas.drawRightString(landscape(letter)[0] - 0.45 * inch, 0.22 * inch, footer)
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=landscape(letter),
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title="How Spectrum Stores, Serves, and Reads Files",
        author="Spectrum project",
    )
    doc.build(build_story(), onFirstPage=on_page, onLaterPages=on_page)
    print(OUT)


ST = styles()


if __name__ == "__main__":
    main()
