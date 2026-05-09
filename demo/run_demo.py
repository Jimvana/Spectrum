#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_EXCLUDES = [
    "dist",
    "build",
    "coverage",
    "node_modules",
    "vendor",
    ".next",
    ".cache",
    "typedoc",
    "docs/generated",
    "models",
]


@dataclass
class DemoConfig:
    source_root: Path
    out_dir: Path
    max_files: int | None
    max_file_bytes: int
    chunk_chars: int
    top_k: int
    rerank_profile: str
    search_queries: list[str]


def slugify(value: str) -> str:
    value = value.rstrip("/\\")
    if value.endswith(".git"):
        value = value[:-4]
    tail = re.split(r"[/\\:]+", value)[-1] or "repo"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", tail).strip("-._")
    return slug.lower() or "repo"


def prompt_text(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def prompt_int(label: str, default: int, allow_zero: bool = False) -> int:
    while True:
        raw = prompt_text(label, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if value < 0 or (value == 0 and not allow_zero):
            print("Please enter a positive number.")
            continue
        return value


def prompt_yes_no(label: str, default: bool = True) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label} [{default_text}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def prompt_choice(label: str, choices: list[str], default: str) -> str:
    choice_text = "/".join(choices)
    while True:
        raw = prompt_text(f"{label} ({choice_text})", default).lower()
        if raw in choices:
            return raw
        print(f"Please enter one of: {', '.join(choices)}.")


def collect_interactive_queries() -> list[str]:
    print()
    print("Step 6 - Enter search queries to try after the benchmark.")
    print("Add one query per line. Press Enter on a blank line when done.")
    queries: list[str] = []
    while True:
        query = input(f"Query {len(queries) + 1}: ").strip()
        if not query:
            break
        queries.append(query)
    return queries


def clone_or_use_repo(repo_url: str, target: Path, interactive: bool) -> Path:
    target = target.expanduser().resolve()
    if target.exists():
        is_empty = not any(target.iterdir())
        if is_empty:
            if interactive and not prompt_yes_no(f"{target} already exists and is empty. Clone into it"):
                raise SystemExit("Demo cancelled.")
            print(f"[demo] cloning {repo_url} -> {target}")
            subprocess.run(
                ["git", "clone", "--depth=1", repo_url, str(target)],
                check=True,
            )
            return target
        if not (target / ".git").exists():
            message = (
                f"{target} already exists, but it is not a Git checkout. "
                "Using it will benchmark that folder as-is instead of cloning the repo."
            )
            print(message)
        if interactive and not prompt_yes_no(f"{target} already exists. Use it"):
            raise SystemExit("Demo cancelled.")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[demo] cloning {repo_url} -> {target}")
    subprocess.run(
        ["git", "clone", "--depth=1", repo_url, str(target)],
        check=True,
    )
    return target


def resolve_config(args: argparse.Namespace, repo_root: Path, interactive: bool) -> DemoConfig:
    demo_root = repo_root / "demo"
    workspace_root = Path(args.workspace_dir).expanduser() if args.workspace_dir else demo_root / "workspaces"
    runs_root = demo_root / "runs"

    repo_url = args.repo or ""
    local_path = args.path or ""

    if interactive and not repo_url and not local_path:
        print("Spectrum Code Search Demo")
        print()
        print("Step 1 - Choose a repository.")
        repo_url = prompt_text("Enter a Git repo URL, or leave blank to use a local folder")
        if not repo_url:
            local_path = prompt_text("Enter local repo/folder path", str(repo_root))

    if repo_url:
        slug = slugify(repo_url)
        clone_default = workspace_root / slug
        clone_path = Path(args.clone_path).expanduser() if args.clone_path else clone_default
        if interactive:
            print()
            print("Step 2 - Choose where Spectrum should clone or reuse the repo.")
            clone_path = Path(prompt_text("Local path", str(clone_path)))
        source_root = clone_or_use_repo(repo_url, clone_path, interactive)
    else:
        if not local_path:
            raise SystemExit("Provide --repo, --path, or run interactively.")
        source_root = Path(local_path).expanduser().resolve()
        slug = slugify(str(source_root))

    if not source_root.exists():
        raise SystemExit(f"Source path not found: {source_root}")

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else runs_root / slug
    if interactive:
        print()
        print("Step 3 - Choose where the demo report should be written.")
        out_dir = Path(prompt_text("Output directory", str(out_dir)))

    max_files = args.max_files
    if interactive and max_files is None:
        print()
        print("Step 4 - Choose scan size. Use 0 for all supported files.")
        max_files = prompt_int("Maximum source files", 1000, allow_zero=True)
    if max_files == 0:
        max_files = None
    if max_files is None and not interactive:
        max_files = 1000

    rerank_profile = args.rerank_profile
    if interactive:
        print()
        print("Step 5 - Choose the search profile for Spectrum result preview.")
        rerank_profile = prompt_choice(
            "Rerank profile",
            ["off", "fast", "balanced", "accurate", "quality"],
            rerank_profile,
        )

    queries = list(args.query or [])
    if interactive and not queries:
        queries = collect_interactive_queries()

    return DemoConfig(
        source_root=source_root,
        out_dir=out_dir.expanduser().resolve(),
        max_files=max_files,
        max_file_bytes=args.max_file_bytes,
        chunk_chars=args.chunk_chars,
        top_k=args.top_k,
        rerank_profile=rerank_profile,
        search_queries=queries,
    )


def run_codebase_benchmark(config: DemoConfig, clean: bool) -> dict:
    from rag import codebase_benchmark

    if clean and config.out_dir.exists():
        shutil.rmtree(config.out_dir)

    bench_args = argparse.Namespace(
        source_root=str(config.source_root),
        out_dir=str(config.out_dir),
        max_files=config.max_files,
        max_file_bytes=config.max_file_bytes,
        chunk_chars=config.chunk_chars,
        overlap_chars=600,
        queries=80,
        top_k=config.top_k,
        skip_verify=False,
        spectrum_k1=1.5,
        spectrum_b=0.75,
        spectrum_max_df_ratio=0.9,
        spectrum_title_boost=0.5,
        postings_format="v2",
        exclude_dir=DEFAULT_EXCLUDES,
    )
    return codebase_benchmark.run(bench_args)


def run_search_preview(config: DemoConfig) -> list[dict]:
    if not config.search_queries:
        return []

    from rag.spectrum_serving import SpectrumServingRetriever, code_rerank_profile

    retriever = SpectrumServingRetriever.from_codebase_benchmark(
        config.out_dir,
        rerank_profile=code_rerank_profile(config.rerank_profile),
    )
    rows = []
    md_lines = [
        "# Spectrum Demo Search Preview",
        "",
        f"- Benchmark dir: `{config.out_dir}`",
        f"- Top-k: {config.top_k}",
        f"- Rerank profile: `{config.rerank_profile}`",
        "",
    ]
    print()
    print("[demo] Search preview")
    for query in config.search_queries:
        print()
        print(f"Query: {query}")
        results = retriever.search(query, top_k=config.top_k)
        query_rows = []
        md_lines.extend([f"## {query}", ""])
        if not results:
            print("  No Spectrum results.")
            md_lines.extend(["No Spectrum results.", ""])
            rows.append({"query": query, "results": []})
            continue
        for result in results:
            decoded = retriever.decode(result.id) if result.score_rank == 1 else None
            preview = {
                "rank": result.score_rank,
                "source_path": result.source_path,
                "title": result.title,
                "snippet": result.snippet,
                "top_result_decode_ms": round(decoded.decode_ms, 4) if decoded else None,
            }
            query_rows.append(preview)
            decode_note = (
                f", decoded top result in {decoded.decode_ms:.3f} ms"
                if decoded is not None
                else ""
            )
            print(f"  {result.score_rank}. {result.source_path}{decode_note}")
            md_lines.extend(
                [
                    f"### {result.score_rank}. `{result.source_path}`",
                    "",
                    result.snippet.strip() or "_No snippet available._",
                    "",
                ]
            )
        rows.append({"query": query, "results": query_rows})

    (config.out_dir / "demo_search_results.json").write_text(
        json.dumps(rows, indent=2),
        encoding="utf-8",
    )
    (config.out_dir / "demo_search_results.md").write_text(
        "\n".join(md_lines) + "\n",
        encoding="utf-8",
    )
    return rows


def write_html_report(config: DemoConfig, report: dict, search_rows: list[dict]) -> None:
    top_k = report["settings"]["top_k"]
    raw = report["stores"]["conventional"]
    spectrum = report["stores"]["spectrum"]
    raw_ret = report["retrieval"]["conventional"]
    spectrum_ret = report["retrieval"]["spectrum"]

    def e(value: object) -> str:
        return html.escape(str(value), quote=True)

    search_html = ""
    if search_rows:
        blocks = []
        for row in search_rows:
            result_items = []
            for result in row["results"]:
                decode = result.get("top_result_decode_ms")
                decode_text = f" <span>decoded in {decode} ms</span>" if decode is not None else ""
                result_items.append(
                    "<li>"
                    f"<strong>{e(result['rank'])}. {e(result['source_path'])}</strong>{decode_text}"
                    f"<pre>{e(result.get('snippet', '').strip())}</pre>"
                    "</li>"
                )
            if not result_items:
                result_items.append("<li>No Spectrum results.</li>")
            blocks.append(
                f"<section><h3>{e(row['query'])}</h3><ol>{''.join(result_items)}</ol></section>"
            )
        search_html = f"<h2>Search Preview</h2>{''.join(blocks)}"

    markup = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spectrum Demo Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.45; margin: 32px; color: #1f2933; }}
    main {{ max-width: 1040px; margin: 0 auto; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; }}
    th, td {{ border-bottom: 1px solid #d9e2ec; padding: 10px 12px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f0f4f8; }}
    code, pre {{ background: #f5f7fa; border-radius: 6px; }}
    code {{ padding: 2px 4px; }}
    pre {{ padding: 12px; overflow: auto; white-space: pre-wrap; }}
    .meta {{ color: #52606d; }}
    .ok {{ color: #0f7b45; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>Spectrum Demo Report</h1>
  <p class="meta">Source: <code>{e(config.source_root)}</code></p>
  <p class="meta">Search profile: <code>{e(config.rerank_profile)}</code></p>
  <p class="meta">Files: {report['corpus']['files']:,} | Chunks: {report['corpus']['chunks']:,} | Raw bytes: {report['corpus']['raw_bytes']:,}</p>

  <h2>Storage</h2>
  <table>
    <thead><tr><th>Store</th><th>Bytes</th><th>Ratio vs raw</th><th>Payload bytes</th><th>Index bytes</th><th>Build sec</th></tr></thead>
    <tbody>
      <tr><td>Conventional raw+TF-IDF</td><td>{raw['bytes']:,}</td><td>{raw['ratio_vs_raw']:.3f}x</td><td>{raw['components']['payload_bytes']:,}</td><td>{raw['components']['index_bytes']:,}</td><td>{raw['build_seconds']:.3f}</td></tr>
      <tr><td>Spectrum .specpack + BM25</td><td>{spectrum['bytes']:,}</td><td>{spectrum['ratio_vs_raw']:.3f}x</td><td>{spectrum['components']['payload_bytes']:,}</td><td>{spectrum['components']['index_bytes']:,}</td><td>{spectrum['build_seconds']:.3f}</td></tr>
    </tbody>
  </table>

  <h2>Retrieval</h2>
  <table>
    <thead><tr><th>Store</th><th>Hit@1</th><th>MRR</th><th>Recall@{top_k}</th><th>Avg ms</th><th>P95 ms</th></tr></thead>
    <tbody>
      <tr><td>Conventional raw+TF-IDF</td><td>{raw_ret['hit_at_1']:.3f}</td><td>{raw_ret['mrr']:.3f}</td><td>{raw_ret[f'recall_at_{top_k}']:.3f}</td><td>{raw_ret['avg_query_ms']:.3f}</td><td>{raw_ret['p95_query_ms']:.3f}</td></tr>
      <tr><td>Spectrum .specpack + BM25</td><td>{spectrum_ret['hit_at_1']:.3f}</td><td>{spectrum_ret['mrr']:.3f}</td><td>{spectrum_ret[f'recall_at_{top_k}']:.3f}</td><td>{spectrum_ret['avg_query_ms']:.3f}</td><td>{spectrum_ret['p95_query_ms']:.3f}</td></tr>
    </tbody>
  </table>

  <h2>Fidelity</h2>
  <p>Spectrum lossless: <span class="ok">{e(spectrum['lossless_ok'])}</span>; failures: {e(spectrum['fidelity_failures'])}</p>
  {search_html}
</main>
</body>
</html>
"""
    (config.out_dir / "demo_report.html").write_text(markup, encoding="utf-8")


def print_summary(config: DemoConfig, report: dict) -> None:
    top_k = report["settings"]["top_k"]
    raw = report["stores"]["conventional"]
    spectrum = report["stores"]["spectrum"]
    raw_ret = report["retrieval"]["conventional"]
    spectrum_ret = report["retrieval"]["spectrum"]
    print()
    print("Spectrum demo complete")
    print(f"Source: {config.source_root}")
    print(f"Report: {config.out_dir / 'report.md'}")
    print(f"Search profile: {config.rerank_profile}")
    print()
    print("Store                         Size        Hit@1   MRR     Recall@{}   Avg ms".format(top_k))
    print(
        "Conventional raw+TF-IDF      "
        f"{raw['bytes']:>10,}  {raw_ret['hit_at_1']:.3f}   {raw_ret['mrr']:.3f}   "
        f"{raw_ret[f'recall_at_{top_k}']:.3f}      {raw_ret['avg_query_ms']:.3f}"
    )
    print(
        "Spectrum .specpack + BM25    "
        f"{spectrum['bytes']:>10,}  {spectrum_ret['hit_at_1']:.3f}   {spectrum_ret['mrr']:.3f}   "
        f"{spectrum_ret[f'recall_at_{top_k}']:.3f}      {spectrum_ret['avg_query_ms']:.3f}"
    )
    print(f"Fidelity: {spectrum['lossless_ok']} ({spectrum['fidelity_failures']} failures)")
    if config.search_queries:
        print(f"Search preview: {config.out_dir / 'demo_search_results.md'}")


def run_demo(args: argparse.Namespace, repo_root: Path | None = None) -> int:
    repo_root = (repo_root or ROOT).resolve()
    interactive = not args.non_interactive and sys.stdin.isatty()
    config = resolve_config(args, repo_root, interactive=interactive)
    report = run_codebase_benchmark(config, clean=args.clean)
    search_rows = run_search_preview(config)
    write_html_report(config, report, search_rows)
    print_summary(config, report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the guided Spectrum code search demo.")
    parser.add_argument("--repo", help="Git repository URL to clone and benchmark.")
    parser.add_argument("--path", help="Local repository/folder path to benchmark.")
    parser.add_argument("--clone-path", help="Local clone destination for --repo.")
    parser.add_argument("--workspace-dir", help="Directory for cloned demo repositories.")
    parser.add_argument("--out-dir", help="Output directory for benchmark reports.")
    parser.add_argument("--max-files", type=int, help="Maximum source files to scan; 0 means all.")
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=512_000_000,
        help="Skip individual source files larger than this.",
    )
    parser.add_argument(
        "--chunk-chars",
        type=int,
        default=12_000,
        help="Characters per benchmark chunk; 0 keeps one chunk per file.",
    )
    parser.add_argument("--query", action="append", help="Free-form Spectrum search query to preview after the build.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of search results and Recall@k.")
    parser.add_argument(
        "--rerank-profile",
        choices=["off", "fast", "balanced", "accurate", "quality"],
        default="accurate",
        help="Spectrum search preview rerank profile.",
    )
    parser.add_argument("--clean", action="store_true", help="Delete the output directory before running.")
    parser.add_argument("--non-interactive", action="store_true", help="Do not prompt for missing values.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_demo(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
