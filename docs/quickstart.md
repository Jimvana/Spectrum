# Spectrum Store 5-Minute Quickstart

This quickstart creates a compact, lossless, searchable `.specpack` from a
small codebase and serves it through Spectrum's local HTTP API.

## Requirements

- Node.js 18+
- Python 3.10+

## Install

```powershell
npm install -g spectrumstore
```

## Turn The Key

Run the guided loader:

```powershell
spectrum load
```

It will:

- check the npm wrapper, Python runtime, bundled files, import paths, and temp
  write access,
- ask which repo or folder to pack,
- write a `.specpack`,
- start the local API at `http://127.0.0.1:7777`.

For a non-interactive run:

```powershell
spectrum load ./my-repo ./my-repo.specpack --yes
```

If you type an output path without `.specpack`, Spectrum appends it:

```powershell
spectrum load ./my-repo ./my-repo --yes
```

That writes `./my-repo.specpack`.

## Manual Workflow

Use this when you want each step visible.

First check the install:

```powershell
spectrum doctor
```

Then pack a codebase.

Use your own repository:

```powershell
spectrum pack ./my-repo ./my-repo.specpack --json
```

From a Spectrum checkout, you can use the tiny sample service:

```powershell
spectrum pack ./demo/sample-code/auth-service ./auth-service.specpack --json
```

## Serve It

```powershell
spectrum serve ./auth-service.specpack --port 7777
```

The positional pack is registered as `repo`. In another terminal:

```powershell
curl http://127.0.0.1:7777/health
curl http://127.0.0.1:7777/packs
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

The supported preview path is the `spectrumstore` npm CLI plus the local
Spectrum HTTP API. SDKs, dashboard, memory layer, and integrations are
developing around the same `.specpack` foundation.
