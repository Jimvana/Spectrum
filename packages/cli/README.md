# Spectrum Store CLI

CLI owns the developer-facing Spectrum Store preview commands: `doctor`,
`pack`, `append`, `project`, `search`, `decode`, `verify`, `inspect`, `index`,
`serve`, and `unpack`.

The first ecosystem CLI package wraps `spectrum_core` for local format workflows:

- `encode` - encode one file to `.spec`.
- `decode` - decode one `.spec` file.
- `pack` - create a `.specpack` from a file or folder.
- `append` - add files or a folder to an existing `.specpack`.
- `project` - initialize, append to, and serve portable project packs.
- `unpack` - decode a `.specpack`.
- `inspect` - inspect `.spec` or `.specpack` metadata.
- `verify` - verify `.spec`, `.spec` directory, or `.specpack` fidelity.
- `index` - build a retrieval index.
- `search` - search a `.specpack`.
- `serve` - run the local HTTP API for a `.specpack`.
- `doctor` - check the local install, Python runtime, imports, bundled runtime,
  and temporary write access.

Example:

```powershell
npm install -g spectrumstore
spectrum doctor
spectrum pack ./docs ./docs.specpack --json
spectrum append ./docs.specpack ./project-notes --json
spectrum verify ./docs.specpack --json
spectrum index ./docs.specpack --embed --json
spectrum search ./docs.specpack "authentication middleware" --json
```

Portable project workflow:

```powershell
spectrum project init ./my-project --name "My Project"
spectrum project add ./my-project/.spectrum/project.specpack ./new-notes
spectrum project serve ./my-project/.spectrum/project.specpack --port 7777
```

`project init` creates `.spectrum/project.specpack` by default, plus
cross-platform launchers: `start.cmd`, `start.ps1`, `start.command`, and
`start.sh`.

Guided hub workflow:

```powershell
spectrum hub -b
spectrum hub -a
spectrum hub -s
spectrum hub -v
spectrum hub --gui
```

The hub commands are interactive wrappers around `project init`, `project add`,
and `project serve`. `hub -v` discovers local listening ports, probes them for
the Spectrum API, and reports the dashboard and agent context URLs for running
servers. If none respond, it prints `No spectrum servers operating`. Use
`--ports 7777,7778` when you want to check an explicit list.

`spectrum hub --gui` opens the desktop Spectrum Hub. It can create or open a
`.specpack`, unlock encrypted packs, append files and folders, export/open a
restored files view, rebuild embedded indexes, start a local server without a
terminal window, open the dashboard, preview packed apps, and optionally proxy
backend API routes. Build the app for the current platform with:

```powershell
npm run deps:hub-gui
npm run build:hub-gui
```

Windows output is `dist/SpectrumHub/SpectrumHub.exe`; macOS output is
`dist/SpectrumHub.app`. Installing `tkinterdnd2` before the build enables native
drag and drop in the packaged app.

macOS has a dedicated wrapper that uses the same GUI/runtime flow as Windows
and generates a bundle icon when Pillow is available:

```bash
npm run deps:hub-gui:macos
npm run build:hub-gui:macos
```

Build the Windows installer with Inno Setup 6:

```powershell
winget install JRSoftware.InnoSetup
npm run build:hub-gui-installer
```

The installer wraps the complete PyInstaller folder, so end users do not need
Python, PyInstaller, `tkinterdnd2`, or the Spectrum source checkout installed.
It installs `SpectrumHub.exe`, bundled Python/runtime files, packaged Spectrum
modules, the drag/drop support files, and the Spectrum codec runtime.
Close any running Spectrum Hub window before rebuilding; Windows keeps bundled
DLLs locked while the app is open.
The packaged app requests administrator rights on launch, so Windows will show
a UAC prompt before opening Spectrum Hub.

If an appended source path already exists, `append` fails unless `--replace` is
passed. Appending removes embedded `index.bin` so searches do not silently use a
stale index; rebuild it with `spectrum index ./docs.specpack --embed
--incremental`. Incremental rebuilds reuse unchanged documents from the
embedded index and re-tokenize only added or changed encoded sources. The first
rebuild after upgrading from an older index falls back to a full rebuild so the
new per-source fingerprints can be stored.

### Updating The Windows GUI

This release changes the GUI index flow to use incremental embedded index
updates and progress messages. To update the Windows GUI build:

```powershell
npm run deps:hub-gui
npm run build:hub-gui:windows
```

Close any running `SpectrumHub.exe` before rebuilding because Windows locks the
bundled runtime files while the app is open. To create the distributable
installer after the executable build:

```powershell
winget install JRSoftware.InnoSetup
npm run build:hub-gui-installer
```

The installer packages the rebuilt `dist/SpectrumHub/` folder, including the
updated index layer, server batch endpoint, changed-only verification helper,
and GUI incremental index workflow.

Benchmark and dashboard commands remain in the legacy CLI until the
corresponding ecosystem packages are moved under `packages/`.
