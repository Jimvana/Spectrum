# Spectrum Store Release Checklist

Use this checklist for `spectrumstore@0.1.0-preview.1` and later preview
releases.

## Before Publishing

- Confirm `package.json` has the intended package name, version, license, files,
  and `bin` entries.
- Run the full workspace tests:

```powershell
python scripts/test.py
```

- Run the packed install smoke test:

```powershell
npm run smoke:packed
```

- Inspect the package contents:

```powershell
npm pack --dry-run
```

- Confirm the public npm name is still available or under the expected account:

```powershell
npm view spectrumstore name version dist-tags
```

- Confirm the changelog entry is accurate and dated if this is the final release
  commit.
- Tag the release commit:

```powershell
git tag v0.1.0-preview.1
```

## Publish

Publishing requires an npm account with permission for the package:

```powershell
npm login
npm publish --tag preview
```

After publishing, verify a clean global install:

```powershell
npm uninstall -g spectrumstore
npm install -g spectrumstore@preview
spectrum doctor
spectrum --help
```

## Post-Publish

- Create the GitHub release for the tag.
- Include the quickstart command block in the release notes.
- Link to `docs/quickstart.md` and `docs/why-spectrum.md`.
- Open or update follow-up issues for SDK publishing, server packaging,
  dashboard packaging, and stable format policy.
