# Portable Project Packs

Portable Project Packs are a product direction for Spectrum: make an ongoing
software project easy for humans and AI agents to resume from any session,
without depending on one chat history, one machine setup note, or one person's
memory.

## Idea

A Spectrum `.specpack` can become a local project continuity vault.

It can store:

- source files
- project notes
- current status
- deployment runbooks
- server layout
- SSH aliases and connection notes
- references to secrets
- architecture decisions
- known risks
- agent instructions

The pack can then be served locally:

```powershell
spectrum project serve ./project.specpack --port 7777
```

An agent can query `localhost`, search the pack, hydrate exact documents, and
continue work with the right context.

## Why This Matters

AI-assisted development often loses continuity. A new session may know the repo,
but not the server, deployment process, decisions, current state, or operational
constraints.

Portable Project Packs solve that by creating a durable local bundle of project
knowledge. The pack grows as the project grows:

```powershell
spectrum project add ./project.specpack ./new-notes --json
```

This turns Spectrum from just compact searchable storage into a practical agent
memory layer.

## Product Goal

The end user experience should be simple:

```text
Choose a project.
Create or update its Spectrum pack.
Serve it locally.
Let tools and agents use it.
Keep adding notes as the project develops.
```

For technical users, the CLI is enough. For GUI-first users, terminal commands
will be a barrier. The finished product should have both:

- a reliable CLI for automation and power users
- a simple local GUI for everyday project owners

## Proposed Pack Structure

Each portable project should use predictable document names so agents and GUI
tools can find the right context quickly.

```text
project.md
status.md
agent-rules.md
architecture.md
deploy.md
server.md
ssh.md
secrets.refs.md
runbook.md
decisions.md
```

Optional folders:

```text
notes/
deploy/
servers/
incidents/
decisions/
prompts/
```

This structure should stay simple. The value is that a non-expert can understand
what belongs where.

## Secret Model

Spectrum should support operational continuity without becoming an unsafe secret
dump.

Recommended default:

```text
Store secret references, not raw secrets.
```

Examples:

```text
SSH alias: bytespectrum-prod
Private key: available through ssh-agent
Production env: on server at /var/www/site/.env
Password vault: 1Password item "ByteSpectrum production"
```

Future versions could add encrypted secret storage, but that needs explicit
cryptographic design, key management, access prompts, and a clear threat model.
Until then, the product should steer users toward secret references.

## Current Building Blocks

Already available:

- `spectrum pack` creates `.specpack` files.
- `spectrum append` adds new information to existing packs.
- `spectrum project init` creates `.spectrum-project` templates, packs the project, verifies it, and embeds search.
- `spectrum project add` appends new project notes and rebuilds embedded search.
- `spectrum project serve` serves a project pack locally as `repo`.
- `spectrum verify` checks lossless reconstruction.
- `spectrum index --embed` builds embedded search.
- `spectrum search` queries the pack.
- `spectrum serve` exposes the local HTTP API.
- `GET /packs/repo/documents/{path}` hydrates exact document content.
- `GET /projects/repo/context` assembles the standard project context bundle.

This is enough for a first working Portable Project Pack workflow.

## What Needs To Be Done

1. Refine the official project-pack template with real user feedback.
2. Build a local GUI for non-terminal users.
3. Add clear secret-reference handling and later passkey-based protection.
4. Add examples using a real website or server project.
5. Add a project status editor so users can update context without touching Markdown.
6. Add a one-click "append and rebuild search" flow in the GUI.
7. Add project pack import/export affordances.
8. Document the workflow for agents and humans.

## Agent Context Endpoint

The current server exposes pack primitives. A project-friendly endpoint could
assemble the useful pieces for agents:

Implemented:

```text
GET /projects/repo/context
GET /packs/repo/context
```

Possible response:

```json
{
  "project": "bytespectrum.cc",
  "status": "...",
  "rules": "...",
  "deploy": "...",
  "server": "...",
  "secret_references": "...",
  "documents": [
    {
      "path": "project.md",
      "content": "..."
    }
  ]
}
```

This should not replace search and hydration. It should give agents a fast
starting context, then let them search deeper when needed.

## GUI Direction

The GUI should be local-first and practical. It should avoid assuming users are
comfortable with terminals.

Core screens:

- project picker
- create pack
- append notes/files
- view pack contents
- search pack
- edit project context files
- serve/stop local API
- copy local endpoint
- verify pack
- rebuild index

Useful GUI actions:

- "Create Project Pack"
- "Add Notes"
- "Add Folder"
- "Update Existing File"
- "Start Local Agent Server"
- "Verify Pack"
- "Rebuild Search"

The GUI should show plain-language status:

```text
Pack ready
Local server running at http://127.0.0.1:7777
Search index needs rebuild
No raw secrets found
```

## Ease Of Use Requirements

The product should be easy enough that a user can succeed without reading the
manual.

Requirements:

- sensible defaults
- no required `PYTHONPATH` setup
- no need to know what an index is
- clear warnings before replacing documents
- clear warnings before storing secrets
- one-click local server start in GUI
- copyable local URL
- visible checklist of recommended context files
- automatic verify after pack creation or append
- prompt to rebuild search after append

## Suggested First Version

Minimum useful product:

```text
spectrum project init ./my-project
spectrum project add ./my-project.specpack ./notes
spectrum project serve ./my-project.specpack
```

GUI equivalent:

```text
Open Spectrum
Choose project folder
Click Create Pack
Click Add Notes
Click Start Local Server
```

Current built-in dashboard:

```text
http://127.0.0.1:7777/project
```

The first release does not need encrypted secret storage. It needs a smooth
continuity workflow, strong warnings, and reliable pack growth.

## Long-Term Shape

Portable Project Packs can become the bridge between humans, local tools, and AI
agents.

The pack is the durable artifact. The local server is the access layer. The GUI
is the human-friendly control surface. Agents use the API to retrieve exact,
verified context.

That combination is the product.
