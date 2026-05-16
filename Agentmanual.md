# Agent Manual

This manual explains how an AI agent should use Spectrum `.specpack` files as
local project context.

## Purpose

A `.specpack` is a portable, lossless, searchable project archive. It can hold
source files, notes, deployment instructions, architecture decisions, and
project continuity documents. The agent should treat it as a local source of
truth for project context.

The usual workflow is:

```text
inspect pack -> search pack -> hydrate selected documents -> act with context
```

## Basic Commands

Create a pack from a project or notes folder:

```powershell
spectrum pack ./my-project ./my-project.specpack --json
```

Append new project information later:

```powershell
spectrum append ./my-project.specpack ./project-notes --json
```

Replace an existing packed document intentionally:

```powershell
spectrum append ./my-project.specpack ./project-notes --replace --json
```

Verify exact decode fidelity:

```powershell
spectrum verify ./my-project.specpack --json
```

Inspect pack summary:

```powershell
spectrum inspect ./my-project.specpack --json
```

Build or rebuild the embedded search index:

```powershell
spectrum index ./my-project.specpack --embed --json
```

Search the pack:

```powershell
spectrum search ./my-project.specpack "deploy process" --top 5 --json
```

Serve the pack through the local HTTP API:

```powershell
spectrum serve ./my-project.specpack --port 7777
```

Create a portable project pack with standard context files:

```powershell
spectrum project init ./my-project ./my-project.specpack --name "My Project"
```

Append project notes and rebuild the embedded index:

```powershell
spectrum project add ./my-project.specpack ./new-notes
```

Serve it as a project pack:

```powershell
spectrum project serve ./my-project.specpack --port 7777
```

Human dashboard:

```text
http://127.0.0.1:7777/project
```

## Local API

When served, a positional pack is registered as `repo`.

Base URL:

```text
http://127.0.0.1:7777
```

Useful endpoints:

```text
GET  /health
GET  /packs
GET  /packs/repo
GET  /project
POST /packs/repo/search
GET  /packs/repo/documents/{source_path}
GET  /projects/repo/context
POST /packs/repo/verify
POST /packs/repo/index
```

Search request:

```json
{
  "query": "ssh deploy host",
  "top_k": 5
}
```

The search response includes `source_path`. Use that path to hydrate exact
content:

```text
GET /packs/repo/documents/project.md
GET /packs/repo/documents/deploy/production.md
```

For nested paths, URL-encode when your HTTP client requires it:

```text
GET /packs/repo/documents/deploy%2Fproduction.md
```

For portable project packs, fetch the starter bundle first:

```text
GET /projects/repo/context
```

That response includes the standard context documents that exist in the pack,
a `missing` list for recommended files that are not present yet, and convenience
fields such as `project`, `status`, `rules`, `deploy`, `server`, `ssh`, and
`secret_references`.

## Recommended Project Context Files

A project continuity pack should include a small set of predictable documents.
Agents should look for these first:

```text
project.md
agent-rules.md
status.md
architecture.md
deploy.md
server.md
ssh.md
secrets.refs.md
runbook.md
decisions.md
```

The CLI creates these under:

```text
.spectrum-project/
```

Suggested meanings:

- `project.md` describes what the project is and where the source lives.
- `agent-rules.md` lists instructions, safety rules, and forbidden actions.
- `status.md` records current work, blockers, and last known state.
- `architecture.md` explains the important technical shape of the system.
- `deploy.md` contains deployment commands and verification steps.
- `server.md` describes hosts, paths, services, logs, and restart behavior.
- `ssh.md` stores SSH aliases and connection notes, not raw private keys.
- `secrets.refs.md` lists where secrets live, such as `ssh-agent`, 1Password,
  Bitwarden, Windows Credential Manager, or `.env` paths.
- `runbook.md` lists common operations and recovery steps.
- `decisions.md` records important prior decisions and tradeoffs.

## Secret Handling

Agents should not assume that raw secrets are safe to store in a `.specpack`.

Preferred pattern:

```text
Store references, aliases, and instructions in Spectrum.
Keep private keys and credentials in the operating system, ssh-agent, or a
password manager.
Ask before executing commands that use secrets or connect to production.
```

Good examples:

```text
SSH host alias: bytespectrum-prod
Production path: /var/www/bytespectrum
Key access: available through local ssh-agent
Env file: stored on server at /var/www/bytespectrum/.env
```

Avoid storing raw private keys, API keys, database passwords, or recovery codes
unless the user has explicitly chosen that risk and the storage model is
properly encrypted and access-controlled.

## Agent Behavior

Before making project changes, an agent should:

1. Check whether a relevant `.specpack` is available.
2. Inspect the pack.
3. Search for task-specific context.
4. Hydrate exact documents before relying on search snippets.
5. Verify deployment and secret-handling rules before using SSH or production.
6. Append new durable knowledge after important work is completed.

Useful post-work append examples:

```powershell
spectrum append ./my-project.specpack ./new-runbook-notes --json
spectrum index ./my-project.specpack --embed --json
```

If a served pack is already running and the pack changes on disk, restart the
server to make sure the registry and index state are fresh.

## Safety Defaults

Agents should ask for confirmation before:

- using SSH
- deploying
- modifying production data
- reading or exposing secrets
- replacing existing packed documents with `--replace`
- unpacking over an existing working directory

The pack is a continuity tool. It should make the agent better informed, not
less careful.
