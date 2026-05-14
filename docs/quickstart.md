# Spectrum Store 5-Minute Quickstart

This quickstart creates a compact, lossless, searchable `.specpack` from a
small codebase and verifies that Spectrum can restore the original files.

## Requirements

- Node.js 18+
- Python 3.10+

## Install

```powershell
npm install -g spectrumstore
spectrum doctor
```

`spectrum doctor` checks the npm wrapper, Python runtime, bundled Spectrum
runtime files, import paths, and temporary write access.

## Pack A Codebase

Use your own repository:

```powershell
spectrum pack ./my-repo ./my-repo.specpack --json
```

From a Spectrum checkout, you can use the tiny sample service:

```powershell
spectrum pack ./demo/sample-code/auth-service ./auth-service.specpack --json
```

## Search It

```powershell
spectrum search ./auth-service.specpack "authentication middleware bearer token" --top 5 --json
```

If the pack has no embedded index yet, `search` builds one automatically. To
embed the index explicitly:

```powershell
spectrum index ./auth-service.specpack --embed --json
```

## Verify Lossless Restore

```powershell
spectrum verify ./auth-service.specpack --json
spectrum unpack ./auth-service.specpack ./auth-service-restored --json
```

`verify` decodes entries and checks that reconstructed bytes match the original
checksums stored in the pack manifest.

## Useful Commands

```powershell
spectrum inspect ./auth-service.specpack --json
spectrum search ./auth-service.specpack "rate limit login requests" --top 3 --json
spectrum unpack ./auth-service.specpack ./restored-auth-service --json
```

## Current Preview Scope

The preview is intentionally CLI-first. The SDKs, server, dashboard, memory
layer, and connectors are developing around the same `.specpack` foundation, but
the supported installation path for new users is the `spectrumstore` npm CLI.
