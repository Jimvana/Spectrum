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
`.specpack`, show the loaded pack name and size, start a local server without a
terminal window, open the dashboard, and stage dropped documents for a confirmed
append. Build the Windows app with:

```powershell
npm run deps:hub-gui
npm run build:hub-gui
```

The build output is `dist/SpectrumHub/SpectrumHub.exe`. Installing
`tkinterdnd2` before the build enables native drag and drop in the packaged app.

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
stale index; rebuild it with `spectrum index ./docs.specpack --embed`.

Benchmark and dashboard commands remain in the legacy CLI until the
corresponding ecosystem packages are moved under `packages/`.
