# Spectrum Encrypted Specpack Implementation Plan

## Goal

Add first-class password-protected `.specpack` support without making local
agent workflows slow or awkward.

The product model is:

```text
closed briefcase: encrypted `.specpack` at rest
open briefcase: unlocked local session
agent access: fast local API, no per-query password prompts
```

The first implementation should prioritize a simple, safe container design:
encrypt the whole existing `.specpack` payload, unlock once per session, and use
the current pack/index/search/hydration code after decryption.

Token-level keyed encoding is intentionally out of scope for v1. It may be
revisited later as a Spectrum-native obfuscation layer, but it should not be the
main security primitive.

The public Spectrum dictionary and `.spec` codec must be treated as public
implementation details, not secrets. A loose plaintext `.spec` file plus the
public Spectrum repo is enough to reconstruct source text. Confidentiality comes
only from the encrypted outer `.specpack` container.

## Non-Goals For V1

- Search encrypted packs without unlocking.
- Per-file or per-section encryption.
- Cloud key custody.
- Account recovery if the user forgets the passphrase.
- Hardware-key-only workflows.
- Replacing `.spec` token compression or dictionary logic.

## Security Model

### Threats V1 Should Handle

- A copied/stolen `.specpack` file should not reveal project contents.
- A copied/stolen backup should not reveal project contents.
- A modified encrypted pack should fail authentication rather than decode
  corrupted content.
- The passphrase should never be stored in the pack, repo, logs, shell history,
  API responses, or GUI state.
- Normal encrypted workflows should not leave plaintext `.spec`, dictionary,
  manifest, index, or source-path artifacts behind in the repo, export folder,
  walkthrough workspace, demo output, or long-lived temp directories.

### Threats V1 Does Not Fully Handle

- A compromised running machine after the user unlocks the pack.
- Malware reading Spectrum process memory.
- Agents intentionally instructed by the user to reveal unlocked content.
- Weak passphrases chosen by users.
- Metadata leakage after unlock through API logs or downstream tools.
- Plain `.spec` files, unpacked packs, exported indexes, and screenshots or demo
  artifacts created after unlock.

## Crypto Design

### Recommended Primitive

Use authenticated encryption:

- Preferred: `XChaCha20-Poly1305`
- Acceptable fallback: `AES-256-GCM`

Use a memory-hard password KDF:

- Preferred: `Argon2id`
- Acceptable fallback if dependency constraints require it: `scrypt`

The pack stores KDF parameters and random salt. It does not store the passphrase
or derived key.

### Suggested KDF Profiles

Start with named profiles rather than exposing raw knobs in the common path:

| Profile | Intended Use | Target Unlock Cost |
|---|---|---:|
| `interactive` | default laptops/desktops | about 300-800 ms |
| `strong` | backups and high-value packs | about 1-3 s |
| `low-memory` | small VMs/CI/dev containers | about 300-800 ms with lower RAM |

Store the resolved numeric parameters in the pack header so future Spectrum
versions can unlock old packs exactly.

Example metadata:

```json
{
  "kdf": "argon2id",
  "kdf_profile": "interactive",
  "memory_kib": 65536,
  "iterations": 3,
  "parallelism": 1,
  "salt_b64": "...",
  "aead": "xchacha20-poly1305",
  "nonce_b64": "..."
}
```

### Passphrase Guidance

Prefer memorable passphrases over complex short passwords.

Good prompts:

```text
Use a long phrase you can remember. Six or more uncommon words is a good start.
Avoid project names, your name, dates, and quotes.
```

Support an optional cleartext hint:

```powershell
spectrum pack ./project ./project.specpack --encrypt --hint "six-word phrase about the first office"
```

The hint must be visible in `inspect` and unlock prompts, but it must never be
treated as secret.

## Format Plan

### V1 Container Strategy

Introduce an encrypted outer container around a normal `.specpack`.

```text
encrypted specpack
  magic/version/header
  encryption metadata
  ciphertext = encrypted bytes of current plain `.specpack`
  authentication tag
```

After unlock:

```text
decrypt ciphertext -> bytes of existing ZIP-based `.specpack`
parse using current spectrum_core APIs
```

This keeps the current `.spec`, manifest, `index.bin`, search, verify, and
unpack logic mostly unchanged.

The encrypted container is the confidentiality boundary. Everything inside the
normal `.specpack` is sensitive once unlocked, including `.spec` payloads,
dictionaries, manifests, source paths, indexes, checksums, and retrieval
sidecars. The public dictionary in the GitHub repo must not be relied on for
privacy.

### Magic And Detection

Add a distinct outer magic so old and new packs are easy to distinguish.

Candidate:

```text
SPENC001
```

Detection rules:

- ZIP/plain `.specpack`: existing behavior.
- `SPENC001`: encrypted pack; return locked metadata unless passphrase is
  provided.
- Unknown magic: current invalid-pack error.

### Header Contents

The unencrypted outer header may include:

- magic and encrypted container version,
- encryption algorithm,
- KDF algorithm and parameters,
- random salt,
- nonce,
- optional passphrase hint,
- created Spectrum version,
- encrypted payload length,
- optional clear display name.

Do not include:

- file list,
- source paths,
- raw sizes by file,
- manifest content,
- checksums of plaintext,
- anything derived from the passphrase except KDF metadata.

### Compatibility

- Existing unencrypted `.specpack` files continue to work.
- New Spectrum versions can read both plain and encrypted packs.
- Old Spectrum versions should fail clearly on encrypted packs with:

```text
This is an encrypted Spectrum pack. Upgrade Spectrum and unlock it with a passphrase.
```

## Core Package Work

Package: `packages/core`

Add APIs:

```python
encrypt_pack_bytes(plain_pack: bytes, passphrase: str, options: EncryptOptions) -> bytes
decrypt_pack_bytes(encrypted_pack: bytes, passphrase: str) -> bytes
is_encrypted_pack(path_or_bytes) -> bool
inspect_encrypted_header(path_or_bytes) -> EncryptedPackInfo
```

Add higher-level helpers:

```python
pack_folder(..., encrypt: bool = False, passphrase: str | None = None, ...)
open_pack(path, passphrase: str | None = None)
verify_pack(path, passphrase: str | None = None)
read_document(path, source_path, passphrase: str | None = None)
```

Implementation notes:

- Keep decrypted bytes in memory for v1.
- Use temporary files only if an existing API strictly requires a file path.
- If temp files are required, create them with restrictive permissions and
  delete them immediately.
- Never create decrypted temp packs, loose `.spec` files, dictionaries,
  manifests, or indexes inside the project repo or demo/walkthrough output
  folders during encrypted workflows.
- Prefer OS temp directories with unpredictable names for unavoidable decrypted
  intermediates, and document crash-cleanup behavior.
- Avoid printing decrypted temp paths unless in explicit debug mode.
- Zeroing Python strings is not reliable; avoid overclaiming memory wiping.

## CLI Work

Package: `packages/cli`

### New Pack Options

```powershell
spectrum pack ./project ./project.specpack --encrypt
spectrum pack ./project ./project.specpack --encrypt --kdf-profile strong
spectrum pack ./project ./project.specpack --encrypt --hint "phrase hint"
```

Behavior:

- Prompt for passphrase and confirmation.
- Refuse empty passphrases.
- Warn on very short passphrases.
- Do not support passphrase via positional argument.
- Optional environment variable for automation only:

```text
SPECTRUM_PASSPHRASE
```

If used, warn that shell/environment handling can leak secrets.

### Existing Commands Gain Unlock

```powershell
spectrum inspect ./project.specpack
spectrum verify ./project.specpack --unlock
spectrum index ./project.specpack --unlock --embed
spectrum search ./project.specpack "oracle deploy key" --unlock
spectrum unpack ./project.specpack ./restore --unlock
spectrum serve ./project.specpack --unlock
```

Behavior:

- `inspect` without unlock shows encrypted header metadata and hint.
- Commands that need contents fail with a clear locked-pack message unless
  `--unlock` is provided or a session unlock is available.
- `--unlock` prompts once for the passphrase.
- Wrong passphrase returns a clean authentication failure.
- Any CLI command, script, demo, or walkthrough that currently opens, searches,
  verifies, unpacks, serves, indexes, or benchmarks a `.specpack` must have an
  encrypted-pack path that prompts for a passphrase or accepts an approved
  automation secret source.

### Turnkey Flow

Update `spectrum load`:

```powershell
spectrum load ./project ./project.specpack --encrypt
spectrum load ./project ./project.specpack --encrypt --yes
```

Flow:

1. Show brief explanation.
2. Prompt for passphrase and confirmation.
3. Build plain pack in memory/temp workspace.
4. Encrypt final output.
5. Verify by unlocking and reading manifest.
6. Start local server with unlocked session if not `--no-serve`.

Demo and walkthrough flows should use `spectrum load --encrypt` as the default
privacy example. They must show the password prompt, the unlocked local session,
and the fact that subsequent agent/API reads are fast without repeated prompts.

### New Utility Commands

Optional v1 or v1.1:

```powershell
spectrum lock ./plain.specpack ./encrypted.specpack
spectrum unlock ./encrypted.specpack ./plain.specpack
spectrum rekey ./encrypted.specpack
spectrum key-hint ./encrypted.specpack
```

Recommendation:

- Implement `rekey` after the basic encrypted pack path is stable.
- Avoid `unlock` writing plaintext by default. Require explicit output path and
  a warning.

## Local API Work

Package: `packages/server`

### Server Unlock Modes

CLI:

```powershell
spectrum serve ./project.specpack --unlock
spectrum serve ./project.specpack --unlock --lock-after 30m
```

Runtime behavior:

- The server unlocks the pack at startup.
- Decrypted pack state is held in process memory.
- Existing endpoints remain fast and unchanged for agents.
- No per-request password prompts.
- On process exit, unlocked state disappears.

### API Additions

Expose lock status without leaking sensitive metadata:

```http
GET /packs
GET /packs/{pack_id}
```

Example:

```json
{
  "id": "repo",
  "path": "./project.specpack",
  "encrypted": true,
  "locked": false,
  "hint": "six-word phrase about the first office"
}
```

Optional local-only unlock endpoint:

```http
POST /packs/{pack_id}/unlock
POST /packs/{pack_id}/lock
```

Recommendation:

- For v1, prefer unlock at server startup and avoid HTTP passphrase submission.
- If HTTP unlock is added, bind to localhost only by default and do not log
  request bodies.

### Lock Timeout

Implement idle timeout:

```powershell
--lock-after 30m
```

Definition of activity:

- search,
- read/hydrate,
- verify,
- unpack,
- context endpoints.

On timeout:

- drop decrypted pack cache,
- return locked errors until unlocked again,
- keep the server process alive.

## GUI And HUD Work

There are two UI surfaces:

- `benchmark_hud` for benchmark visualization.
- `packages/dashboard` / local GUI for pack browsing and search.

### Dashboard / Hub GUI

Required states:

- plain pack,
- encrypted locked pack,
- encrypted unlocked pack,
- wrong passphrase,
- auto-locked after timeout.

Screens:

- Pack list shows lock badge.
- Pack detail shows encryption metadata and hint.
- Unlock modal accepts passphrase.
- Search/inspect buttons are disabled while locked.
- Lock button drops session key.
- Timeout indicator shows when auto-lock is configured.

UX rules:

- Do not show passphrases.
- Do not store passphrases in local storage.
- Do not send passphrase to non-localhost endpoints.
- Warn before writing decrypted output to disk.
- GUI onboarding, demo mode, import flows, and walkthroughs must include locked,
  unlock, wrong-password, unlocked, and re-lock states.
- GUI search, preview, export, benchmark, and agent-context actions must all
  handle encrypted locked packs explicitly instead of failing as invalid packs.

### Benchmark HUD

Benchmark HUD should recognize encrypted packs in two ways:

1. If benchmarking source folders, offer `Encrypt output pack` in run settings.
2. If loading an existing encrypted pack, show locked state and prompt unlock
   before benchmarking/searching.

HUD metrics to add:

- encrypted pack bytes,
- unlock time,
- KDF profile,
- decrypted serving memory estimate,
- search latency after unlock.

Do not include passphrases in exported run JSON.

## SDK Work

### Python SDK

Add:

```python
spectrum.pack_folder(source, output, encrypt=True, passphrase_provider=...)
spectrum.open_pack(path, passphrase=...)
spectrum.inspect_pack(path)
spectrum.is_encrypted_pack(path)
```

Prefer passphrase provider callbacks for apps:

```python
def get_passphrase(pack_info):
    return getpass.getpass(f"Unlock {pack_info.display_name}: ")
```

### JavaScript SDK

Add matching helpers where practical:

```js
await spectrum.inspectPack(path)
await spectrum.isEncryptedPack(path)
await spectrum.openPack(path, { passphrase })
```

If crypto is implemented only in Python for v1, JS SDK can call the local server
or document encrypted-pack support as server-mediated initially.

## Repository Touchpoint Audit

This repo has several direct `.specpack` readers/writers and multiple user
surfaces. Encryption cannot be implemented only in `packages/core`; every
surface below needs either first-class encrypted-pack support or an explicit
locked-pack error.

### Core Package

Files:

- `packages/core/src/spectrum_core/pack.py`
- `packages/core/src/spectrum_core/validation.py`
- `packages/core/src/spectrum_core/__init__.py`
- `packages/core/pyproject.toml`
- `packages/core/README.md`
- `packages/core/tests/test_core_api.py`

Required changes:

- Add encrypted container helpers and public exports.
- Teach `pack()`, `append_to_pack()`, `SpectrumPack.open()`, `inspect_pack()`,
  `decode_member()`, `unpack()`, and `verify_pack()` about encrypted packs.
- Decide whether append/rewrite operations preserve encryption by default. The
  expected behavior is: encrypted input produces encrypted output unless the
  user explicitly asks for plaintext output.
- Replace direct `zipfile.ZipFile(path)` assumptions with a pack-opening layer
  that can operate on decrypted bytes.
- Avoid extracting decrypted `.spec` members to repo paths; keep decode/verify
  intermediates in OS temp or memory.
- Add the selected crypto dependency and packaging notes here first, because all
  higher layers depend on core.

### Index Package

Files:

- `packages/index/src/spectrum_index/api.py`
- `packages/index/README.md`
- `packages/index/tests/test_index.py`

Required changes:

- Add passphrase/session-aware parameters to `build_index()`,
  `build_pack_index()`, `search_pack()`, and embedded-index loading.
- Replace `_replace_zip_member()` with a core helper that can rewrite plain or
  encrypted packs safely.
- Ensure embedded `index.bin` is encrypted inside encrypted packs and never
  emitted as a sidecar unless explicitly requested.
- Ensure `_extract_pack()` and temporary index reads do not leave plaintext
  `.spec`, `manifest.json`, or `index.bin` artifacts outside temp storage.

### CLI Package

Files:

- `packages/cli/src/spectrum_cli/main.py`
- `packages/cli/src/spectrum_cli/gui.py`
- `packages/cli/README.md`
- `packages/cli/tests/test_cli.py`
- `scripts/smoke-packed-cli.mjs`

Required changes:

- Add `--encrypt`, `--kdf-profile`, and `--hint` to `pack`, `project init`,
  `hub -b`, and `load`.
- Add `--unlock` and passphrase prompting to `append`, `unpack`, `inspect`,
  `verify`, `index`, `search`, `serve`, `project add`, `project serve`,
  `project restart`, `hub -a`, `hub -s`, and `load`.
- Update generated project launchers from `_write_project_launchers()` so they
  include the correct encrypted serve command and explain the password prompt.
- Decide v1 behavior for `append` against encrypted packs. Recommended:
  require unlock, rewrite encrypted output, and fail rather than silently
  writing a plaintext pack.
- Update `hub --verify-servers` and running-server detection to show
  encrypted/locked status from `/packs`.
- Extend packed smoke tests to create, inspect, unlock-search, verify, unpack,
  and serve an encrypted pack with a test passphrase supplied through the
  approved automation path.

### Server Package And Embedded Dashboard

Files:

- `packages/server/src/spectrum_server/app.py`
- `packages/server/src/spectrum_server/main.py`
- `packages/dashboard/README.md`
- `packages/server/README.md`
- `packages/server/tests/test_server.py`

Required changes:

- Make `PackRegistry` store pack state, not only path: encrypted, locked,
  unlocked session, hint, KDF metadata, last activity, and lock timeout.
- Add `--unlock`, `--lock-after`, and any approved automation secret source to
  `spectrum-server` and CLI serve entrypoints.
- Update all content endpoints to return locked-pack responses before touching
  decrypted content: `/manifest`, `/documents`, document hydration, `/context`,
  `/ops`, `/readiness`, `/verify`, `/index`, `/search`, `/unpack`, document
  upsert, and document delete.
- Ensure upsert/delete mutate encrypted packs by decrypting in memory/temp,
  rewriting the inner pack, then re-encrypting; never replace an encrypted pack
  with a plaintext ZIP.
- If HTTP unlock endpoints are added, protect them with localhost binding,
  request body log suppression, origin checks, and a per-server random token.
- Update the embedded `/project` dashboard HTML/JS in `app.py` to render locked,
  unlock, wrong-password, unlocked, timeout, and re-lock states.

### Hub Desktop GUI

Files:

- `packages/cli/src/spectrum_cli/gui.py`
- `scripts/build-hub-gui.py`
- `scripts/build-hub-gui-exe.ps1`
- `scripts/build-hub-gui-installer.ps1`
- `installer/SpectrumHub.iss`

Required changes:

- Add encrypted-pack creation options and passphrase confirmation to
  `create_specpack()`.
- Add locked-pack detection, password prompt, unlock state, and lock action to
  `open_specpack()`, `set_pack()`, append, verify/index rebuild, and server
  start.
- Ensure packaged GUI builds include any crypto dependency and keep passphrases
  out of saved metadata, logs, and launcher files.

### Python SDK

Files:

- `packages/sdk-python/spectrum/pack.py`
- `packages/sdk-python/spectrum/__init__.py`
- `packages/sdk-python/README.md`
- `packages/sdk-python/tests/test_sdk.py`

Required changes:

- Add `encrypt`, `kdf_profile`, `hint`, `passphrase`, and
  `passphrase_provider` support to create/open/from-documents workflows.
- Add `inspect_pack()`/`is_encrypted_pack()` style helpers at SDK level.
- Thread unlock support through `inspect()`, `verify()`, `build_index()`,
  `search()`, `unpack()`, `read_document()`, `extract_to()`, and `entries`.
- Ensure `from_documents()` temp plaintext documents remain in OS temp only and
  encrypted output is produced when requested.

### JavaScript SDK

Files:

- `packages/sdk-js/src/index.js`
- `packages/sdk-js/src/index.d.ts`
- `packages/sdk-js/README.md`
- `packages/sdk-js/tests/sdk.test.mjs`

Required changes:

- Add encrypted create/open/search/verify/index/unpack options and TypeScript
  types.
- Decide whether JS passes passphrases via environment/stdin to the CLI or uses
  the local server. Do not place passphrases in command arguments.
- Add tests covering encrypted pack creation and locked-pack failure behavior.

### MCP Server

Files:

- `MCP/spectrum_spec_mcp/core.py`
- `MCP/spectrum_spec_mcp/server.py`
- `MCP/README.md`

Required changes:

- Stop using direct `zipfile.ZipFile()` for `.specpack` inspection/search.
- Add locked encrypted-pack metadata responses.
- Require an explicit unlock/passphrase path before `read_specpack_member()` or
  `search_specs()` can decode encrypted pack contents.
- Update MCP docs to say `.spec` and unlocked `.specpack` contents are plaintext
  to MCP clients.

### Legacy CLI And Legacy GUI

Files:

- `CLI Tool/spectrum_cli/main.py`
- `CLI Tool/gui/server.py`
- `CLI Tool/gui/app.js`
- `CLI Tool/README.md`
- `CLI Tool/vendor/spectrum_algo/**`

Required changes:

- Either backport encrypted `.specpack` handling or clearly mark the legacy
  `spec` CLI/GUI as unable to open encrypted packs.
- Update legacy benchmark, info, verify, search, decode, GUI load, and GUI
  benchmark paths if this surface remains shipped in npm/package artifacts.
- Ensure bundled vendored runtime includes crypto support if legacy paths are
  kept functional.

### Benchmark HUD And Demo

Files:

- `benchmark_hud/server.py`
- `benchmark_hud/app.js`
- `benchmark_hud/index.html`
- `benchmark_hud/README.md`
- `demo/run_demo.py`
- `demo/README.md`
- `demo/sample-data/README.md`

Required changes:

- Add an `Encrypt output pack` option to HUD and demo runs that create packs.
- Add encrypted-pack load/unlock support for HUD and demo paths that accept
  existing packs.
- Add metrics for encrypted pack bytes, unlock time, KDF profile, and post-unlock
  search latency.
- Ensure exported HUD run JSON and demo reports never include passphrases.
- Decide whether benchmark artifacts containing loose `.spec` chunks remain
  intentionally non-private; if so, label them as plaintext-equivalent.

### Runtime And Direct `.spec` Decoders

Files:

- `Runtime/spectrum-decoder.js`
- `Runtime/spectrum-serve.mjs`
- `Runtime/spectrum-sw.js`
- `Runtime/test-decoder.mjs`
- `Runtime/*.md`
- `rag/indexer.py`
- `rag/native_decoder.py`

Required changes:

- No v1 encrypted-pack support is required for direct loose `.spec` runtime
  decoding unless encrypted web runtime becomes a product goal.
- Documentation must state that these direct `.spec` runtime paths are not
  private and are outside the encrypted `.specpack` boundary.
- Any future runtime support for encrypted packs must unlock once into memory
  and avoid writing decoded files to disk.

### Packaging, Installers, And Dependency Bundles

Files:

- `package.json`
- `bin/spectrumstore.js`
- `scripts/build-hub-gui.py`
- `scripts/build-hub-gui-exe.ps1`
- `scripts/build-hub-gui-installer.ps1`
- `scripts/install-hub-gui-build-deps.ps1`
- `installer/SpectrumHub.iss`
- package `pyproject.toml` files

Required changes:

- Add the selected crypto dependency to package metadata and GUI build scripts.
- Confirm the npm preview bundle includes runtime files needed for encrypted
  pack support.
- Add release-checklist items for encrypted pack compatibility, locked-pack
  errors, and no plaintext artifact leakage.

### Docs And Manuals

Files:

- `README.md`
- `docs/quickstart.md`
- `docs/why-spectrum.md`
- `ECOSYSTEM_MANUAL.md`
- `packages/*/README.md`
- `MCP/README.md`
- `Runtime/*.md`
- `RELEASE_CHECKLIST.md`
- `CHANGELOG.md`

Required changes:

- Update all examples that create, serve, search, verify, index, unpack, or open
  packs to include encrypted variants.
- Add a clear explanation that the public dictionary is not secret and loose
  `.spec` files are plaintext-equivalent.
- Add recovery warning, backup guidance, automation caveats, GUI walkthrough,
  CLI walkthrough, and local API unlock behavior.

### Test Matrix

Files:

- `packages/core/tests/test_core_api.py`
- `packages/index/tests/test_index.py`
- `packages/cli/tests/test_cli.py`
- `packages/server/tests/test_server.py`
- `packages/sdk-python/tests/test_sdk.py`
- `packages/sdk-js/tests/sdk.test.mjs`
- `scripts/smoke-packed-cli.mjs`
- `scripts/test.py`

Required changes:

- Add plain-pack regression tests everywhere.
- Add encrypted-pack locked/unlocked tests for core, index, CLI, server, SDKs,
  and smoke packaging.
- Add mutation tests for encrypted append/upsert/delete/index rebuild.
- Add no-leak tests that scan output/temp/demo directories for loose `.spec`,
  `manifest.json`, `index.bin`, and passphrase strings after encrypted workflows.

## Documentation Work

Update:

- `README.md`
- `docs/quickstart.md`
- `docs/why-spectrum.md`
- `ECOSYSTEM_MANUAL.md`
- demo scripts and walkthroughs,
- screenshots or recordings used by the website and README,
- `packages/server/README.md`
- `packages/sdk-python/README.md`
- `packages/sdk-js/README.md`
- website `site/`

Messaging:

```text
Spectrum packs are project briefcases: searchable, portable, and lockable.
Unlock once, work fast through the local API, then lock when done.
```

Docs should include:

- the public dictionary is not secret,
- loose `.spec` files are plaintext-equivalent once someone has the public
  decoder,
- passphrase guidance,
- what encryption protects,
- what it does not protect,
- backup guidance,
- recovery warning,
- automation caveats,
- examples for `pack`, `load`, `serve`, `search`, and `unpack`.
- updated GUI and CLI walkthroughs showing password creation, unlock, wrong
  password, local serving after unlock, and lock/timeout behavior.

## Test Plan

### Unit Tests

- encrypted header parse,
- wrong passphrase fails,
- tampered ciphertext fails,
- tampered header fails if authenticated,
- correct passphrase decrypts exactly,
- pack roundtrip plain -> encrypt -> decrypt -> verify,
- empty passphrase rejected,
- hint stored and shown,
- old plain packs still work.

### CLI Tests

- `pack --encrypt` creates encrypted pack.
- `inspect` shows locked metadata.
- `verify --unlock` prompts and succeeds.
- `search --unlock` succeeds.
- wrong passphrase exits non-zero with clean message.
- `load --encrypt --no-serve` creates encrypted output.
- `serve --unlock` exposes existing endpoints after one unlock.
- encrypted CLI walkthrough commands run end-to-end with a test passphrase.
- encrypted workflows do not leave loose `.spec`, dictionary, manifest, or index
  artifacts in the project/demo output directory.

### Server Tests

- encrypted pack registered locked.
- search fails while locked.
- startup unlock enables search.
- lock timeout drops decrypted state.
- no passphrase appears in logs.

### GUI Tests

- locked badge renders.
- unlock modal works.
- wrong passphrase state renders.
- search disabled while locked.
- lock button returns pack to locked state.
- onboarding/demo import handles encrypted packs and prompts for a passphrase.
- preview/export/search/benchmark controls transition correctly between locked
  and unlocked states.

### Performance Tests

Measure:

- pack encryption overhead,
- unlock latency by KDF profile,
- memory overhead of unlocked session,
- search latency after unlock versus plain pack.

Acceptance target:

- No meaningful search/hydration slowdown after unlock compared with plain pack.
- Unlock cost is paid once per session.

## Implementation Phases

### Phase 1: Core Encrypted Container

- Add encrypted pack format detection.
- Add encrypt/decrypt helpers.
- Add inspect locked metadata.
- Add roundtrip tests.

Deliverable:

```powershell
spectrum lock-like internal helper works through tests
```

### Phase 2: CLI Pack And Unlock

- Add `pack --encrypt`.
- Add `inspect` locked output.
- Add `verify/search/unpack --unlock`.
- Add passphrase prompts.

Deliverable:

```powershell
spectrum pack ./docs ./docs.specpack --encrypt
spectrum search ./docs.specpack "query" --unlock
```

### Phase 3: Serve/Load Workflow

- Add `load --encrypt`.
- Add `serve --unlock`.
- Add in-memory unlocked session cache.
- Add optional `--lock-after`.

Deliverable:

```powershell
spectrum load ./project ./project.specpack --encrypt
```

### Phase 4: API And GUI

- Add locked/unlocked pack state to API responses.
- Add dashboard lock states and unlock modal.
- Add benchmark HUD encrypted-pack awareness.

Deliverable:

Agents can use the existing local API after one unlock, and humans can see lock
state in the UI.

### Phase 5: Docs, Website, And Hardening

- Update public docs and website.
- Update demos, walkthroughs, screenshots, and recordings to include the
  passphrase and unlock flow.
- Add security notes.
- Add performance benchmarks.
- Add migration examples.
- Review logging and temp file behavior.

## Open Decisions

- Use `XChaCha20-Poly1305` or `AES-256-GCM` for the first implementation?
- Which Python crypto dependency is acceptable for the npm preview bundle?
- Should encrypted packs keep the `.specpack` extension or use `.specpack.enc`?
- Should `unlock` ever write plaintext by default, or only serve in memory?
- Should HTTP unlock exist in v1, or only CLI startup unlock?
- What are the default KDF parameters on low-memory machines?
- Should Cloud/hosted features ever accept encrypted packs, or should this stay
  strictly local-first?

## Recommended Initial Decisions

- Keep the `.specpack` extension and detect by magic.
- Use whole-pack encryption.
- Unlock at CLI/server startup, not per API request.
- Do not write plaintext packs unless the user gives an explicit output path.
- Use Argon2id if dependency packaging is manageable; otherwise use scrypt for
  v1 and leave Argon2id as the target.
- Make `spectrum load --encrypt` the flagship user flow.
