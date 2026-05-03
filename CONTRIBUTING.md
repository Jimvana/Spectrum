# Contributing

Thanks for taking the time to improve Spectrum CLI.

## Local Setup

```bash
npm install
npm test
node ./bin/spec.js --help
```

The CLI is distributed through npm but implemented mostly in Python. Keep the public command behaviour stable and prefer tests that execute `bin/spec.js`, because that matches the installed user path.

## Pull Requests

- Keep changes focused.
- Include tests for command behaviour changes.
- Update `README.md` when user-facing commands, flags, output files, or requirements change.
- Do not commit generated `.spec`, `.specpack`, benchmark output, or cache files.

## Release Changes

When preparing a release, update both `package.json` and `spectrum_cli/main.py`, run `npm test`, then inspect `npm pack --dry-run`.
