# Spectrum Benchmark HUD

The Spectrum Benchmark HUD is a local visual benchmark surface that streams real
measured retrieval events from the current checkout. It compares Spectrum SPB
against TF-IDF, raw BM25, dense vectors, and FAISS Flat where the optional
dependencies are available.

The HUD can benchmark the built-in Small, Medium, and Large corpora, or clone a
public GitHub repository and benchmark that repo as a custom corpus.

Run it from the repository root:

```powershell
python benchmark_hud/server.py --port 8765
```

Windows launcher:

```powershell
powershell -ExecutionPolicy Bypass -File .\benchmark_hud\launch-windows.ps1
```

macOS launcher:

```bash
chmod +x benchmark_hud/launch-mac.command
./benchmark_hud/launch-mac.command
```

Then open:

```text
http://127.0.0.1:8765
```

In the browser:

1. Choose `Small`, `Medium`, `Large`, or `My own repo`.
2. For `My own repo`, enter `owner/name` or `https://github.com/owner/name`.
3. Set the number of generated source/path queries.
4. Click `Start run`.

Run artifacts are written under `benchmark_hud/runs/` and are intentionally
ignored by Git.

Smoke-test the benchmark runner without the browser:

```powershell
python benchmark_hud/server.py --once small --queries 4
```

Run a one-off benchmark against a public GitHub repo:

```powershell
python benchmark_hud/server.py --once custom --repo pallets/click --queries 4
```

Large repositories can take several minutes to clone and scan. The HUD keeps the
event stream alive with clone progress messages and stores generated data under
`benchmark_hud/runs/`.
