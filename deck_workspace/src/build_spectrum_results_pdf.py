from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
SCRATCH = ROOT / "scratch"
PREVIEWS = SCRATCH / "previews"
OUT.mkdir(parents=True, exist_ok=True)
PREVIEWS.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
BG = "#F6F1E7"
INK = "#111214"
MUTED = "#5A5F63"
RAW = "#E05A47"
SPEC = "#00A886"
SPEC_DARK = "#007A66"
LINE = "#D8D0C2"
CHARCOAL = "#202326"
CREAM = "#FFF9EE"
GOLD = "#D9A441"

FONT = Path("C:/Windows/Fonts/bahnschrift.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
FONT_REG = Path("C:/Windows/Fonts/arial.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT
    if not path.exists():
        path = FONT_REG
    return ImageFont.truetype(str(path), size)


def text(draw: ImageDraw.ImageDraw, xy, value, size=36, fill=INK, bold=False, anchor=None, spacing=8):
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, anchor=anchor, spacing=spacing)


def fit_text(draw: ImageDraw.ImageDraw, value: str, max_width: int, size: int, bold=False, min_size=24):
    while size >= min_size:
        f = font(size, bold)
        if draw.textbbox((0, 0), value, font=f)[2] <= max_width:
            return f
        size -= 2
    return font(min_size, bold)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def slide_base(title=None, kicker=None, dark=False):
    img = Image.new("RGB", (W, H), CHARCOAL if dark else BG)
    draw = ImageDraw.Draw(img)
    if title:
        if kicker:
            text(draw, (96, 72), kicker.upper(), 24, fill=GOLD if dark else SPEC_DARK, bold=True)
        text(draw, (96, 118), title, 62, fill=CREAM if dark else INK, bold=True)
    return img, draw


def footer(draw, value="Spectrum Algo benchmark snapshots | local runs, May 2026"):
    text(draw, (96, 1018), value, 20, fill="#8A8174")


def bar_pair(draw, x, y, w, h, raw_value, spec_value, raw_label, spec_label, max_value, suffix="B"):
    raw_w = int(w * raw_value / max_value)
    spec_w = int(w * spec_value / max_value)
    text(draw, (x, y - 40), raw_label, 26, fill=RAW, bold=True)
    rounded(draw, (x, y, x + raw_w, y + h), 12, RAW)
    text(draw, (x + raw_w + 18, y + h / 2 - 17), f"{raw_value:.2f}{suffix}", 30, fill=INK, bold=True)
    y2 = y + h + 72
    text(draw, (x, y2 - 40), spec_label, 26, fill=SPEC_DARK, bold=True)
    rounded(draw, (x, y2, x + spec_w, y2 + h), 12, SPEC)
    text(draw, (x + spec_w + 18, y2 + h / 2 - 17), f"{spec_value:.2f}{suffix}", 30, fill=INK, bold=True)


def metric(draw, x, y, number, label, color=SPEC, large=82):
    text(draw, (x, y), number, large, fill=color, bold=True)
    text(draw, (x, y + large + 6), label, 25, fill=MUTED)


def slide_1():
    img, draw = slide_base(dark=True)
    draw.rectangle((0, 0, W, H), fill=CHARCOAL)
    draw.polygon([(0, 760), (1920, 500), (1920, 1080), (0, 1080)], fill="#103E38")
    draw.polygon([(1120, 0), (1920, 0), (1920, 1080), (1460, 1080)], fill="#2F2A1F")
    text(draw, (104, 100), "SPECTRUM", 48, fill=GOLD, bold=True)
    text(draw, (104, 210), ".spec beats\nraw RAG storage", 104, fill=CREAM, bold=True, spacing=10)
    text(draw, (108, 485), "Lossless compressed chunks + compact token BM25\nagainst raw text + TF-IDF on code and text corpora.", 36, fill="#D8E7DF")
    metric(draw, 108, 705, "58%", "smaller total store on external codebase", color="#5EF0C5", large=88)
    metric(draw, 720, 705, "5.6x", "faster avg query on that smoke test", color="#F2C15B", large=88)
    text(draw, (108, 984), "Evidence deck | built from local benchmark outputs", 24, fill="#BFB7A8")
    return img


def slide_2():
    img, draw = slide_base("External codebase: Spectrum wins the storage story", "vladmandic/human")
    text(draw, (96, 220), "172 file-level chunks across TypeScript, JavaScript, HTML, CSS, and Markdown. Fidelity passed on every chunk.", 31, fill=MUTED)
    bar_pair(draw, 150, 360, 1120, 58, 2.913, 1.230, "RAW + TF-IDF total store", "SPECTRUM .spec + BM25 total store", 3.05, suffix="MB")
    metric(draw, 1340, 330, "0.56x", "Spectrum ratio vs raw chunks", color=SPEC_DARK, large=76)
    metric(draw, 1340, 520, "1.33x", "Raw+TF-IDF ratio vs raw chunks", color=RAW, large=76)
    text(draw, (150, 750), "Same source material.\nRaw stores text plus vector index.\nSpectrum stores lossless .spec payloads plus compact token postings.", 31, fill=INK, spacing=12)
    footer(draw, "Source: vladmandic/human @ d0c4c83 | generated path/identifier query smoke test")
    return img


def slide_3():
    img, draw = slide_base("The payload is where .spec pulls away", "storage breakdown")
    labels = ["Raw payload", "Spec payload", "Raw index", "Spec index"]
    values = [2.279, 0.898, 0.633, 0.332]
    colors = [RAW, SPEC, "#F08C78", "#4CC6AE"]
    maxv = 2.35
    x0, y0, gap = 150, 280, 115
    for i, (lab, val, col) in enumerate(zip(labels, values, colors)):
        y = y0 + i * gap
        text(draw, (x0, y - 10), lab, 28, fill=INK, bold=True)
        rounded(draw, (x0 + 250, y - 12, x0 + 250 + int(900 * val / maxv), y + 42), 10, col)
        text(draw, (x0 + 1185, y - 8), f"{val:.3f} MB", 31, fill=INK, bold=True)
    text(draw, (150, 790), "Spectrum's index is also smaller here, but the bigger proof is payload compression without giving up decode fidelity.", 34, fill=INK)
    text(draw, (150, 875), "Lossless check: 172 / 172 chunks passed.", 38, fill=SPEC_DARK, bold=True)
    footer(draw)
    return img


def slide_4():
    img, draw = slide_base("It is not just smaller. It searched faster too.", "retrieval smoke test")
    text(draw, (96, 205), "Generated queries from file paths and identifiers. This is a smoke test, not a final code-search benchmark.", 29, fill=MUTED)
    categories = [("Hit@1", 0.242, 0.317), ("MRR", 0.326, 0.390), ("Recall@5", 0.525, 0.542)]
    x = 140
    for label, raw, spec in categories:
        text(draw, (x, 330), label, 29, fill=INK, bold=True)
        rounded(draw, (x, 405, x + 74, 820), 18, "#E9DFD0")
        rounded(draw, (x, 820 - int(390 * raw / 0.60), x + 74, 820), 18, RAW)
        rounded(draw, (x + 102, 405, x + 176, 820), 18, "#E9DFD0")
        rounded(draw, (x + 102, 820 - int(390 * spec / 0.60), x + 176, 820), 18, SPEC)
        text(draw, (x - 2, 850), f"{raw:.3f}", 24, fill=RAW, bold=True)
        text(draw, (x + 94, 850), f"{spec:.3f}", 24, fill=SPEC_DARK, bold=True)
        x += 330
    metric(draw, 1240, 350, "0.079 ms", "Spectrum avg query", color=SPEC_DARK, large=72)
    metric(draw, 1240, 545, "0.440 ms", "Raw+TF-IDF avg query", color=RAW, large=72)
    text(draw, (1240, 725), "Spectrum was roughly\n5.6x faster on average\nfor this query set.", 32, fill=INK, spacing=10)
    footer(draw)
    return img


def slide_5():
    img, draw = slide_base("The pattern repeats on this repo", "self-codebase check")
    text(draw, (96, 205), "80 files from Spectrum Algo itself. Different source, same direction: smaller store, higher generated-query score, faster search.", 30, fill=MUTED)
    bar_pair(draw, 140, 340, 1000, 54, 2.773, 1.028, "RAW + TF-IDF", "SPECTRUM", 2.9, suffix="MB")
    metric(draw, 1260, 330, "0.452x", "Spectrum ratio vs raw chunks", color=SPEC_DARK, large=74)
    metric(draw, 1260, 520, "0.333", "Spectrum Hit@1 vs 0.217 raw", color=SPEC_DARK, large=74)
    metric(draw, 1260, 710, "0.052 ms", "Spectrum avg query vs 0.446 ms raw", color=SPEC_DARK, large=62)
    footer(draw, "Source: Spectrum Algo self-codebase run | 80 file-level chunks")
    return img


def slide_6():
    img, draw = slide_base("Text corpora test the storage idea", "context")
    text(draw, (96, 205), "Plain-text and mixed-document corpora test whether Spectrum stores less overall while staying lossless.", 31, fill=MUTED)
    bar_pair(draw, 140, 345, 1040, 54, 6.430, 4.173, "RAW + TF-IDF total store", "SPECTRUM .spec + BM25 total store", 6.6, suffix="MB")
    metric(draw, 1300, 350, "35%", "smaller total store", color=SPEC_DARK, large=82)
    metric(draw, 1300, 555, "0.923", "Spectrum Hit@1 vs 1.000 raw", color=GOLD, large=72)
    text(draw, (140, 770), "Takeaway: code is where Spectrum is currently most visually compelling.\nText corpora remain useful as prose stress tests.", 35, fill=INK, spacing=12)
    footer(draw, "Source: text-corpus storage benchmark, 6k-character chunks")
    return img


def slide_7():
    img, draw = slide_base("The honest headline", "what to say in the room")
    text(draw, (120, 250), "Spectrum is not claiming to beat every database or neural retriever yet.", 48, fill=INK, bold=True)
    text(draw, (120, 365), "It is showing a different storage shape:\none lossless compressed artifact that is also directly searchable.", 39, fill=MUTED, spacing=12)
    text(draw, (160, 575), "What is proven locally", 35, fill=SPEC_DARK, bold=True)
    for i, line in enumerate([
        ".spec chunks round-trip losslessly",
        "codebase stores are much smaller than raw+TF-IDF",
        "generated code queries favor Spectrum on two codebases",
        "next proof: labelled code queries + stronger baselines",
    ]):
        y = 650 + i * 66
        rounded(draw, (128, y + 6, 152, y + 30), 12, SPEC if i < 3 else GOLD)
        text(draw, (175, y), line, 33, fill=INK)
    footer(draw)
    return img


SLIDES = [slide_1, slide_2, slide_3, slide_4, slide_5, slide_6, slide_7]


def save_pdf(images: list[Path], pdf_path: Path) -> None:
    c = canvas.Canvas(str(pdf_path), pagesize=landscape((W, H)))
    for path in images:
        c.drawImage(str(path), 0, 0, width=W, height=H)
        c.showPage()
    c.save()


def make_contact_sheet(paths: list[Path]) -> Path:
    thumbs = []
    for path in paths:
        img = Image.open(path).resize((480, 270))
        thumbs.append(img)
    sheet = Image.new("RGB", (960, 1080), BG)
    for i, img in enumerate(thumbs):
        x = (i % 2) * 480
        y = (i // 2) * 270
        sheet.paste(img, (x, y))
    out = SCRATCH / "spectrum_results_contact_sheet.png"
    sheet.save(out)
    return out


def main() -> None:
    paths = []
    for idx, build in enumerate(SLIDES, start=1):
        img = build()
        path = PREVIEWS / f"slide_{idx:02d}.png"
        img.save(path)
        paths.append(path)
    pdf_path = OUT / "spectrum_spec_results.pdf"
    save_pdf(paths, pdf_path)
    contact = make_contact_sheet(paths)
    print(f"PDF: {pdf_path}")
    print(f"Previews: {PREVIEWS}")
    print(f"Contact sheet: {contact}")


if __name__ == "__main__":
    main()
