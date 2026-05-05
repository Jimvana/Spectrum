import {
  Presentation,
  PresentationFile,
  row,
  column,
  grid,
  panel,
  text,
  shape,
  chart,
  rule,
  fill,
  hug,
  fixed,
  wrap,
  grow,
  fr,
} from "@oai/artifact-tool";
import { writeFile } from "node:fs/promises";

const W = 1920;
const H = 1080;

const C = {
  ink: "#15171A",
  muted: "#5D6673",
  paper: "#F7F4ED",
  white: "#FFFFFF",
  blue: "#2563EB",
  cyan: "#00A7C2",
  green: "#179A68",
  amber: "#D68A00",
  red: "#C2410C",
  slate: "#27313F",
  line: "#D8D2C6",
  softBlue: "#E8F0FF",
  softGreen: "#E7F6EF",
  softAmber: "#FFF3D6",
  softRed: "#FBE7DD",
};

const methods = [
  { name: "Spectrum BM25", hit: 87.5, mrr: 0.906, recall: 90.5, ms: 2.247, compression: 0.357, color: C.blue },
  { name: "Raw BM25", hit: 87.5, mrr: 0.917, recall: 66.7, ms: 0.115, compression: 1.0, color: C.slate },
  { name: "Tree-sitter chunk BM25", hit: 100, mrr: 1.0, recall: 71.4, ms: 7.115, compression: 1.0, color: C.green },
  { name: "Dense LSA proxy", hit: 62.5, mrr: 0.792, recall: 85.7, ms: 11.871, compression: 1.0, color: C.amber },
  { name: "Hybrid BM25 + LSA", hit: 75, mrr: 0.875, recall: 85.7, ms: 11.175, compression: 1.0, color: C.red },
];

function title(slide, kicker, headline, sub = "") {
  slide.compose(
    text(kicker.toUpperCase(), {
      width: fill,
      height: hug,
      style: { fontFace: "Aptos", fontSize: 18, bold: true, color: C.blue, charSpacing: 1.6 },
    }),
    { frame: { left: 84, top: 58, width: 1600, height: 30 }, baseUnit: 8 },
  );
  slide.compose(
    text(headline, {
      width: fill,
      height: fixed(112),
      style: { fontFace: "Aptos Display", fontSize: 40, bold: true, color: C.ink, lineSpacingMultiple: 1.08 },
    }),
    { frame: { left: 84, top: 110, width: 1660, height: 112 }, baseUnit: 8 },
  );
  if (sub) {
    slide.compose(
      text(sub, {
        width: fill,
        height: fixed(62),
        style: { fontFace: "Aptos", fontSize: 23, color: C.muted, lineSpacingMultiple: 1.15 },
      }),
      { frame: { left: 84, top: 238, width: 1320, height: 62 }, baseUnit: 8 },
    );
  } else {
    slide.compose(rule({ width: fixed(170), stroke: C.blue, weight: 4 }), {
      frame: { left: 84, top: 240, width: 180, height: 8 },
      baseUnit: 8,
    });
  }
}

function footer(slide, note = "Local benchmark: 14 files, 8 labelled queries. Dense result is an LSA proxy, not neural embeddings.") {
  slide.compose(
    text(note, { width: fill, height: hug, style: { fontFace: "Aptos", fontSize: 13, color: "#847C70" } }),
    { frame: { left: 84, top: 1028, width: 1680, height: 28 }, baseUnit: 8 },
  );
}

function methodPill(label, color, body) {
  return panel(
    { fill: C.white, line: { color: C.line, width: 1 }, borderRadius: 16, padding: { x: 26, y: 22 } },
    column({ width: fill, height: fill, gap: 10 }, [
      row({ width: fill, height: hug, gap: 12, align: "center" }, [
        shape({ width: fixed(14), height: fixed(14), fill: color, borderRadius: "rounded-full" }),
        text(label, { width: fill, height: hug, style: { fontFace: "Aptos", fontSize: 24, bold: true, color: C.ink } }),
      ]),
      text(body, { width: fill, height: hug, style: { fontFace: "Aptos", fontSize: 17, color: C.muted, lineSpacingMultiple: 1.12 } }),
    ]),
  );
}

function bar(value, max, color, label) {
  const pct = Math.max(2, Math.round((value / max) * 100));
  return column({ width: fill, height: hug, gap: 6 }, [
    row({ width: fill, height: fixed(20), gap: 0 }, [
      shape({ width: fixed(pct * 3.7), height: fixed(20), fill: color, borderRadius: 6 }),
      shape({ width: fill, height: fixed(20), fill: "#EEE8DE", borderRadius: 6 }),
    ]),
    text(label, { width: fill, height: hug, style: { fontFace: "Aptos", fontSize: 14, color: C.muted } }),
  ]);
}

function metricRow(m) {
  return grid(
    {
      width: fill,
      height: fixed(70),
      columns: [fixed(300), fr(1), fr(1), fr(1)],
      columnGap: 20,
      alignItems: "center",
    },
    [
      row({ width: fill, height: hug, gap: 12, align: "center" }, [
        shape({ width: fixed(12), height: fixed(12), fill: m.color, borderRadius: "rounded-full" }),
        text(m.name, { width: fill, height: hug, style: { fontFace: "Aptos", fontSize: 19, bold: true, color: C.ink } }),
      ]),
      bar(m.hit, 100, m.color, `${m.hit.toFixed(1)}% Hit@1`),
      bar(m.recall, 100, m.color, `${m.recall.toFixed(1)}% Recall@5`),
      bar(Math.min(m.ms, 12), 12, m.color, `${m.ms.toFixed(2)} ms/query`),
    ],
  );
}

const deck = Presentation.create({ slideSize: { width: W, height: H } });

// Slide 1
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  slide.compose(
    grid({ width: fill, height: fill, columns: [fr(1.05), fr(0.95)], columnGap: 48, padding: { x: 90, y: 86 } }, [
      column({ width: fill, height: fill, justify: "center", gap: 30 }, [
        text("Spectrum retrieval", { width: fill, height: hug, style: { fontFace: "Aptos Display", fontSize: 88, bold: true, color: C.ink, lineSpacingMultiple: 0.86 } }),
        text("Where the .spec semantic-token layer sits against BM25, Tree-sitter, code search, and embedding-style retrieval.", { width: wrap(760), height: hug, style: { fontFace: "Aptos", fontSize: 28, color: C.muted, lineSpacingMultiple: 1.12 } }),
        row({ width: fill, height: hug, gap: 14 }, [
          panel({ fill: C.softBlue, borderRadius: 18, padding: { x: 20, y: 12 } }, text("fast enough", { style: { fontSize: 22, bold: true, color: C.blue } })),
          panel({ fill: C.softGreen, borderRadius: 18, padding: { x: 20, y: 12 } }, text("high recall", { style: { fontSize: 22, bold: true, color: C.green } })),
          panel({ fill: C.softAmber, borderRadius: 18, padding: { x: 20, y: 12 } }, text("compressed retrieval", { style: { fontSize: 22, bold: true, color: C.amber } })),
        ]),
      ]),
      panel(
        { fill: C.ink, borderRadius: 28, padding: { x: 46, y: 48 } },
        column({ width: fill, height: fill, justify: "center", gap: 22 }, [
          text("Positioning read", { width: fill, height: hug, style: { fontSize: 24, bold: true, color: "#A7C7FF" } }),
      text("Spectrum is closest to an offline, explainable retrieval substrate: stored compactly, structured enough to search, simple enough to run locally.", { width: fill, height: hug, style: { fontSize: 38, bold: true, color: C.white, lineSpacingMultiple: 1.03 } }),
          rule({ width: fixed(180), stroke: C.blue, weight: 5 }),
          text("The current enemy is not embeddings. It is syntax-aware BM25.", { width: fill, height: hug, style: { fontSize: 23, color: "#CED7E6" } }),
        ]),
      ),
    ]),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 2
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  title(slide, "Method map", "Five retrieval styles, one practical question", "What do they store, what do they search, and what trade-off do they buy?");
  slide.compose(
    grid({ width: fill, height: fill, columns: [fr(1), fr(1), fr(1)], rows: [fr(1), fr(1)], columnGap: 24, rowGap: 24, padding: { x: 84, y: 16 } }, [
      methodPill("Spectrum BM25", C.blue, ".spec token IDs are indexed directly. Retrieval is explainable and offline; decode happens only after ranking."),
      methodPill("Raw BM25 / Lucene", C.slate, "Text terms go into an inverted index. Very fast, mature, exact-match strong, but separate from compressed storage."),
      methodPill("Zoekt", "#111827", "Production-grade source search built around trigrams, regex, symbol-aware ranking, and large-codebase ergonomics."),
      methodPill("Tree-sitter + BM25", C.green, "Code is parsed first, chunked by syntax, then searched lexically. Strong local relevance for code questions."),
      methodPill("Dense embeddings", C.amber, "Chunks become dense vectors. Better for conceptual language, weaker for exact identifiers unless paired with lexical search."),
      methodPill("Hybrid", C.red, "Lexical and dense results are fused. Usually the production default when query intent is mixed."),
    ]),
    { frame: { left: 0, top: 330, width: W, height: 650 }, baseUnit: 8 },
  );
  footer(slide, "Zoekt and real neural embeddings were not installed locally; benchmark uses local proxies where noted.");
}

// Slide 3
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  title(slide, "Local benchmark", "Spectrum is competitive on retrieval, especially recall", "Small-corpus result: 14 files, 8 labelled queries, file-level scoring except Tree-sitter chunks aggregated to files.");
  slide.compose(
    column({ width: fill, height: fill, gap: 12, padding: { x: 94, y: 18 } }, [
      grid({ width: fill, height: fixed(34), columns: [fixed(300), fr(1), fr(1), fr(1)], columnGap: 20 }, [
        text("Method", { style: { fontSize: 15, bold: true, color: C.muted } }),
        text("Reliability: Hit@1", { style: { fontSize: 15, bold: true, color: C.muted } }),
        text("Candidate quality: Recall@5", { style: { fontSize: 15, bold: true, color: C.muted } }),
        text("Speed: lower is better", { style: { fontSize: 15, bold: true, color: C.muted } }),
      ]),
      ...methods.map(metricRow),
      panel({ fill: C.white, line: { color: C.line, width: 1 }, borderRadius: 18, padding: { x: 28, y: 18 } },
        text("Read: Tree-sitter wins top-rank accuracy here. Spectrum's strongest signal is Recall@5: it often gets the right files into the candidate set while staying quick and compressed.", { width: fill, style: { fontSize: 22, bold: true, color: C.ink } })),
    ]),
    { frame: { left: 0, top: 330, width: W, height: 650 }, baseUnit: 8 },
  );
  footer(slide);
}

// Slide 4
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  title(slide, "Positioning chart", "Speed, reliability, compression: Spectrum sits in the useful middle", "Not the fastest, not the smallest, but unusually balanced for an offline semantic-token representation.");
  const rows = [
    ["Raw BM25 / Lucene", "Excellent", "Strong exact match", "Index separate from source"],
    ["Zoekt", "Excellent", "Excellent for code search", "Search index, not codec"],
    ["Tree-sitter + BM25", "Good", "Best local code relevance", "No compression story"],
    ["Embeddings", "Moderate", "Strong conceptual recall", "Vector store + source chunks"],
    ["Hybrid", "Moderate", "Strongest broad retrieval", "Most moving parts"],
    ["Spectrum", "Good", "High recall, explainable", ".spec is compressed + indexed"],
  ];
  slide.compose(
    column({ width: fill, height: fill, gap: 0, padding: { x: 90, y: 14 } }, [
      grid({ width: fill, height: fixed(56), columns: [fixed(360), fr(1), fr(1.2), fr(1.35)], columnGap: 24, padding: { x: 24, y: 14 } }, [
        text("Method", { style: { fontSize: 17, bold: true, color: C.muted } }),
        text("Speed", { style: { fontSize: 17, bold: true, color: C.muted } }),
        text("Reliability", { style: { fontSize: 17, bold: true, color: C.muted } }),
        text("Compression / storage", { style: { fontSize: 17, bold: true, color: C.muted } }),
      ]),
      ...rows.map((r, i) =>
        grid(
          { width: fill, height: fixed(76), columns: [fixed(360), fr(1), fr(1.2), fr(1.35)], columnGap: 24, padding: { x: 24, y: 18 }, alignItems: "center" },
          r.map((v, j) =>
            text(v, {
              width: fill,
              height: hug,
              style: {
                fontFace: "Aptos",
                fontSize: j === 0 ? 21 : 19,
                bold: j === 0 || r[0] === "Spectrum",
                color: r[0] === "Spectrum" ? C.blue : C.ink,
              },
            }),
          ),
        ),
      ),
    ]),
    { frame: { left: 0, top: 322, width: W, height: 670 }, baseUnit: 8 },
  );
  footer(slide, "Qualitative cells combine local benchmark results with method properties. Real Lucene/Zoekt/neural embedding runs still needed for production-grade claims.");
}

// Slide 5
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  title(slide, "Storage reality", "The useful comparison is retrieval-ready storage", "Spectrum's claim belongs beside indexes, chunks, vectors, and source stores, not passive file compression.");
  slide.compose(
    grid({ width: fill, height: fill, columns: [fr(1), fr(1), fr(1)], columnGap: 28, padding: { x: 94, y: 26 } }, [
      panel({ fill: C.white, line: { color: C.line, width: 1 }, borderRadius: 24, padding: { x: 34, y: 32 } },
        column({ width: fill, height: fill, gap: 24 }, [
          text("Typical RAG", { width: fill, style: { fontSize: 32, bold: true, color: C.slate } }),
          text("Raw source\n+ chunks\n+ BM25 index\n+ vector index", { width: fill, style: { fontSize: 28, color: C.ink, lineSpacingMultiple: 1.25 } }),
          text("Powerful, but stores multiple representations.", { width: fill, style: { fontSize: 20, color: C.muted } }),
        ])),
      panel({ fill: C.white, line: { color: C.line, width: 1 }, borderRadius: 24, padding: { x: 34, y: 32 } },
        column({ width: fill, height: fill, gap: 24 }, [
          text("Code search", { width: fill, style: { fontSize: 32, bold: true, color: C.green } }),
          text("Source files\n+ trigram/symbol index\n+ ranking metadata", { width: fill, style: { fontSize: 28, color: C.ink, lineSpacingMultiple: 1.25 } }),
          text("Excellent search, but the index is separate from storage.", { width: fill, style: { fontSize: 20, color: C.muted } }),
        ])),
      panel({ fill: C.softBlue, line: { color: "#B9CCFF", width: 1 }, borderRadius: 24, padding: { x: 34, y: 32 } },
        column({ width: fill, height: fill, gap: 24 }, [
          text("Spectrum", { width: fill, style: { fontSize: 32, bold: true, color: C.blue } }),
          text(".spec artifact\n+ semantic token IDs\n+ BM25 over token IDs", { width: fill, style: { fontSize: 28, color: C.ink, lineSpacingMultiple: 1.25 } }),
          text("The stored form is already the retrieval signal.", { width: fill, style: { fontSize: 20, bold: true, color: C.blue } }),
        ])),
    ]),
    { frame: { left: 0, top: 330, width: W, height: 650 }, baseUnit: 8 },
  );
  footer(slide, "Focus: retrieval-ready representations. Passive compression is storage tooling, not a search baseline.");
}

// Slide 6
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  title(slide, "Strategic read", "The product lane is compressed retrieval, not universal search", "The useful claim is narrower, clearer, and easier to prove.");
  slide.compose(
    grid({ width: fill, height: fill, columns: [fr(1), fr(1)], columnGap: 44, padding: { x: 94, y: 34 } }, [
      panel({ fill: C.white, line: { color: C.line, width: 1 }, borderRadius: 24, padding: { x: 38, y: 34 } },
        column({ width: fill, height: fill, gap: 24 }, [
          text("Where Spectrum has a real angle", { width: fill, style: { fontSize: 33, bold: true, color: C.green } }),
          text("Offline code/document RAG\nExplainable candidate retrieval\nDecode-on-demand source access\nSingle artifact carries storage + retrieval signal", { width: fill, style: { fontSize: 27, color: C.ink, lineSpacingMultiple: 1.22 } }),
        ])),
      panel({ fill: C.white, line: { color: C.line, width: 1 }, borderRadius: 24, padding: { x: 38, y: 34 } },
        column({ width: fill, height: fill, gap: 24 }, [
          text("Where others remain better", { width: fill, style: { fontSize: 33, bold: true, color: C.red } }),
          text("Zoekt for exact code search\nTree-sitter for syntax-aware code chunks\nHybrid retrieval for broad mixed intent\nNeural embeddings for conceptual language", { width: fill, style: { fontSize: 27, color: C.ink, lineSpacingMultiple: 1.22 } }),
        ])),
    ]),
    { frame: { left: 0, top: 330, width: W, height: 650 }, baseUnit: 8 },
  );
  footer(slide);
}

// Slide 7
{
  const slide = deck.slides.add();
  slide.background.fill = C.ink;
  slide.compose(
    grid({ width: fill, height: fill, columns: [fr(1.1), fr(0.9)], columnGap: 70, padding: { x: 94, y: 88 } }, [
      column({ width: fill, height: fill, justify: "center", gap: 24 }, [
        text("Next benchmark", { width: fill, height: hug, style: { fontSize: 22, bold: true, color: "#9EC0FF", charSpacing: 1.2 } }),
        text("Prove the lane against the real systems.", { width: wrap(800), height: hug, style: { fontSize: 70, bold: true, color: C.white, lineSpacingMultiple: 0.92 } }),
        text("The current result is promising, but it is small. The next step is a larger benchmark with real Lucene, Zoekt, Tree-sitter chunking, and a real embedding model.", { width: wrap(780), height: hug, style: { fontSize: 27, color: "#CED7E6", lineSpacingMultiple: 1.14 } }),
      ]),
      column({ width: fill, height: fill, justify: "center", gap: 18 }, [
        methodPill("1. Build corpus", C.blue, "Use 10-50 repositories plus docs. Label query-to-file relevance instead of relying on self-retrieval."),
        methodPill("2. Run true baselines", C.green, "Lucene/OpenSearch BM25, Zoekt, Tree-sitter chunks, neural embeddings, and hybrid fusion."),
        methodPill("3. Measure end-to-end", C.amber, "Index size, source/chunk/vector storage, query latency, Recall@k, MRR, and decode time."),
      ]),
    ]),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

const pptx = await PresentationFile.exportPptx(deck);
await pptx.save("output/output.pptx");

for (let i = 0; i < deck.slides.count; i++) {
  const slide = deck.slides.getItem(i);
  const png = await slide.export({ format: "png", scale: 1 });
  await writeFile(`scratch/slide-${String(i + 1).padStart(2, "0")}.png`, Buffer.from(await png.arrayBuffer()));
}

console.log("Wrote output/output.pptx and slide PNG previews.");
