# Spectrum Demo

The demo is a guided code-search challenge for trying Spectrum on a real
repository. It builds a conventional raw-code retrieval store and a Spectrum
`.spec` + SPB2 store from the same files, verifies lossless decode fidelity,
then prints and writes a benchmark report.

Run the guided flow:

```powershell
spectrum demo
```

Or run it without prompts:

```powershell
spectrum demo `
  --repo https://github.com/apache/commons-lang `
  --max-files 1000 `
  --query "where is string escaping implemented" `
  --clean
```

Local folders work too:

```powershell
spectrum demo --path C:\dev\my-project --query "websocket reconnect logic"
```

Generated outputs are written under `demo/runs/` by default, including
`report.md`, `report.json`, and `demo_report.html`. Cloned repositories are
written under `demo/workspaces/` by default. Both generated directories are
ignored by Git.

The benchmark's scored retrieval metrics use generated file/path queries, so
treat them as a repeatable smoke test. Free-form queries entered during the demo
are used for a search preview and are not scored unless a future labelled-query
file supplies expected paths.
