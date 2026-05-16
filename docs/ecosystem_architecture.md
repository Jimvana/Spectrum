# Spectrum Ecosystem Architecture

## Purpose

Spectrum should not be positioned only as a file format. A file format is useful, but an ecosystem is what makes developers adopt it.

The goal is to build Spectrum as a compact, deterministic, lossless retrieval substrate for AI memory, RAG, code search, archive search, and local-first agent systems.

Spectrum should provide:

- A reliable open format for storing text/code/memory in `.spec` and `.specpack` form.
- Fast retrieval over Spectrum stores.
- Lossless reconstruction of original content.
- Developer tools for packing, searching, benchmarking, and inspecting data.
- SDKs and APIs so other applications can use Spectrum directly.
- Agent-memory tooling that allows LLM agents to store and recall long-term memories.
- Optional integrations with existing RAG frameworks and vector/hybrid retrieval stacks.
- A path to optional hosted/cloud services without locking out regular users.

The core principle should be:

> The format stays open. The ecosystem makes it useful.

---

# 1. Spectrum Core

## Summary

Spectrum Core is the foundation of the ecosystem. It contains the open-source format specification, encoder, decoder, `.spec` reader/writer, `.specpack` reader/writer, and validation tools.

This is the part that must be stable, well-documented, and trustworthy.

## What it does

Spectrum Core should handle:

- Encoding source content into Spectrum token/color/dictionary representation.
- Decoding `.spec` or `.specpack` back into original source text.
- Creating and reading `.specpack` bundles.
- Validating pack integrity.
- Verifying lossless reconstruction.
- Managing dictionaries.
- Handling metadata.
- Supporting versioned format compatibility.

## Key responsibilities

### 1. Format specification

The format spec should document:

- `.spec` structure.
- `.specpack` structure.
- Dictionary layout.
- Token encoding rules.
- Chunk metadata schema.
- Compression strategy, if used.
- Checksums/hashes.
- Versioning rules.
- Backwards compatibility guarantees.
- Error handling expectations.

This matters because developers will not trust a retrieval/storage format unless they understand how it works and how stable it is.

### 2. Encoder

The encoder takes raw input such as text, Markdown, code, JSON, logs, HTML, or exported chat data and converts it into Spectrum representation.

Expected behaviour:

```text
raw document -> chunking -> token mapping -> dictionary references -> .spec/.specpack output
```

The encoder should support:

- Single file input.
- Folder input.
- Streamed input.
- Batch input.
- Metadata attachment.
- Configurable chunking.
- Configurable dictionary strategy.
- Optional deduplication.

### 3. Decoder

The decoder takes Spectrum data and reconstructs original content.

Expected behaviour:

```text
.spec/.specpack + dictionary -> original raw text/content
```

Decoder guarantees should be strict:

- Byte-for-byte reconstruction where possible.
- Clear reporting where byte-for-byte mode is not applicable.
- Hash verification.
- Error reporting for missing dictionaries or corrupted packs.

Lossless decode is one of Spectrum's biggest differentiators. It must be treated as a headline feature, not a side effect.

### 4. Pack reader/writer

The `.specpack` format should act as a portable bundle containing:

- Encoded chunks/documents.
- Dictionaries.
- Metadata.
- Checksums.
- Optional search index data.
- Optional benchmark/query reports.
- Version manifest.

A pack should be self-describing enough that a different machine can open it later and understand what it contains.

### 5. Validation

Spectrum Core should include validation functions such as:

- `validate_pack()`
- `verify_decode()`
- `check_dictionary()`
- `check_chunk_integrity()`
- `compare_to_source()`

Validation output should be machine-readable and human-readable.

Example:

```json
{
  "valid": true,
  "chunks_checked": 172,
  "decode_passed": 172,
  "decode_failed": 0,
  "format_version": "1.0.0"
}
```

## Public API examples

### TypeScript

```ts
import { pack, unpack, searchPack, verifyPack } from "@spectrum/core";

const result = await pack({
  input: "./docs",
  output: "./memory.specpack",
  chunking: "semantic",
  includeIndex: true
});

const verification = await verifyPack("./memory.specpack");
```

### Python

```python
from spectrum import pack, unpack, verify_pack

pack(
    input_path="./docs",
    output_path="./memory.specpack",
    chunking="semantic",
    include_index=True,
)

report = verify_pack("./memory.specpack")
```

## Design requirements

Spectrum Core should be:

- Open-source.
- Stable.
- Well-tested.
- Dependency-light.
- Fast enough for local use.
- Designed for use by CLI, SDK, server, and external apps.
- Versioned carefully.

---

# 2. Spectrum CLI

## Summary

The Spectrum CLI is the main developer-facing tool for local use. It should allow someone to install Spectrum, pack data, search it, decode it, benchmark it, and generate reports without writing code.

The CLI is critical because it gives people a quick way to test Spectrum on their own data.

## Core commands

### `spectrum pack`

Creates a `.specpack` from files, folders, repositories, exports, or other supported sources.

Example:

```bash
spectrum pack ./docs --out docs.specpack
```

Possible options:

```bash
spectrum pack ./docs \
  --out docs.specpack \
  --chunking semantic \
  --include-index \
  --profile accurate \
  --metadata project=demo
```

Responsibilities:

- Read input files.
- Apply chunking.
- Encode into Spectrum format.
- Build dictionary.
- Optionally build index.
- Verify decode.
- Write `.specpack`.
- Produce summary.

### `spectrum search`

Searches a `.specpack`.

Example:

```bash
spectrum search docs.specpack "authentication middleware"
```

Expected output:

```text
1. src/auth/middleware.ts:42
   Score: 12.93
   Snippet: validates JWT token and refreshes session...

2. docs/security.md:18
   Score: 10.44
   Snippet: authentication flow uses...
```

Options:

```bash
spectrum search docs.specpack "query" \
  --top-k 5 \
  --profile accurate \
  --json
```

### `spectrum decode`

Decodes a `.spec` or `.specpack` back to source.

Example:

```bash
spectrum decode docs.specpack --out ./decoded
```

Responsibilities:

- Decode all chunks/documents.
- Reconstruct original folder/file structure where possible.
- Verify hashes.
- Report any mismatch.

### `spectrum bench`

Runs retrieval and performance benchmarks.

Example:

```bash
spectrum bench docs.specpack \
  --queries queries.json \
  --baseline raw-tfidf \
  --report report.md
```

Should measure:

- Store size.
- Payload size.
- Index size.
- Average query latency.
- P50/P95/P99 latency.
- Hit@1.
- MRR.
- Recall@5.
- Decode fidelity.
- CPU time.
- Memory usage where possible.

### `spectrum demo`

Runs an end-to-end demonstration.

Example:

```bash
spectrum demo --repo https://github.com/example/project --query "database connection"
```

Responsibilities:

- Clone or scan input.
- Build raw baseline.
- Build Spectrum pack.
- Run search comparisons.
- Verify decode.
- Generate Markdown/JSON/HTML reports.

### `spectrum inspect`

Allows a user to inspect a pack.

Example:

```bash
spectrum inspect docs.specpack
```

Output:

```text
Pack: docs.specpack
Format version: 1.0.0
Documents: 172
Chunks: 571
Payload size: 897,993 B
Index size: 331,782 B
Decode verified: yes
Created: 2026-05-10
```

### `spectrum verify`

Checks integrity and decode fidelity.

Example:

```bash
spectrum verify docs.specpack --source ./docs
```

## CLI design principles

The CLI should be:

- Easy to install.
- Useful without writing code.
- Good at generating reports.
- Friendly to benchmarks and demos.
- Scriptable in CI.
- Able to output JSON for automation.

## CLI role in adoption

The CLI is the first thing most developers will try. It should make Spectrum feel real quickly.

A good first experience:

```bash
npm install -g spectrum
spectrum demo --repo https://github.com/some/project
```

Then the user sees:

- Size reduction.
- Search speed.
- Retrieval quality.
- Lossless decode proof.
- Report files.

That is much more persuasive than a theoretical README.

---

# 3. Spectrum SDK

## Summary

The Spectrum SDK lets developers use Spectrum inside their own applications. There should eventually be at least two official SDKs:

- TypeScript/JavaScript SDK.
- Python SDK.

These are the two most important ecosystems for AI tooling, RAG, agents, and developer apps.

## Why the SDK matters

A CLI is good for demos. An SDK is what makes Spectrum usable in products.

Developers need to be able to:

- Pack documents programmatically.
- Search packs programmatically.
- Decode selected results.
- Build indexes.
- Update memory stores.
- Attach metadata.
- Integrate with agents and RAG systems.

## TypeScript SDK

Package name example:

```text
@spectrum/core
```

Possible API:

```ts
import { SpectrumPack } from "@spectrum/core";

const pack = await SpectrumPack.open("./memory.specpack");

const results = await pack.search("toes in the water", {
  topK: 5,
  profile: "accurate"
});

const content = await pack.decode(results[0].chunkId);
```

Useful classes/functions:

- `SpectrumPack.open(path)`
- `SpectrumPack.create(options)`
- `pack.addDocument(document)`
- `pack.search(query, options)`
- `pack.decode(chunkId)`
- `pack.verify()`
- `pack.exportReport()`

## Python SDK

Package name example:

```text
spectrum-ai
```

Possible API:

```python
from spectrum import SpectrumPack

pack = SpectrumPack.open("memory.specpack")
results = pack.search("otter buddy", top_k=5, profile="accurate")
content = pack.decode(results[0].chunk_id)
```

Useful functions:

- `SpectrumPack.open()`
- `SpectrumPack.create()`
- `pack.add_document()`
- `pack.search()`
- `pack.decode()`
- `pack.verify()`
- `pack.export_report()`

## Shared SDK concepts

### Document object

```json
{
  "id": "doc_001",
  "path": "notes/memory.md",
  "content": "raw content here",
  "metadata": {
    "source": "openai_export",
    "created_at": "2026-05-10",
    "user_id": "james"
  }
}
```

### Search result object

```json
{
  "chunk_id": "chunk_123",
  "document_id": "doc_001",
  "score": 14.22,
  "rank": 1,
  "snippet": "...toes in the water...",
  "metadata": {
    "source": "openai_export"
  }
}
```

### Decode result object

```json
{
  "chunk_id": "chunk_123",
  "content": "decoded original text",
  "hash_verified": true
}
```

## SDK design principles

The SDK should be:

- Simple for basic use.
- Powerful for advanced users.
- Async-friendly.
- Metadata-aware.
- Compatible with local files and server APIs.
- Designed to be embedded in agents.
- Clear about whether results are snippets or full decoded content.

---

# 4. Spectrum Server

## Summary

Spectrum Server is a local or hosted HTTP API that exposes Spectrum functionality over endpoints.

This allows tools, agents, apps, browser extensions, and dashboards to use Spectrum without linking directly to the SDK.

## Why it matters

Many AI tools expect a running service they can talk to over HTTP.

A server allows Spectrum to become:

- A local memory server.
- A RAG backend.
- A code/document search API.
- A drop-in retrieval service for agents.
- The backend for a dashboard.

## Core endpoints

### Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### Create/open pack

```http
POST /packs
```

Request:

```json
{
  "name": "openai-memory",
  "path": "./memory.specpack"
}
```

### Ingest document

```http
POST /packs/{pack_id}/documents
```

Request:

```json
{
  "id": "doc_001",
  "content": "raw text here",
  "metadata": {
    "source": "chat_export"
  }
}
```

### Search

```http
POST /packs/{pack_id}/search
```

Request:

```json
{
  "query": "toes in the water",
  "top_k": 5,
  "profile": "accurate"
}
```

Response:

```json
{
  "results": [
    {
      "rank": 1,
      "chunk_id": "chunk_123",
      "document_id": "doc_001",
      "score": 18.44,
      "snippet": "...toes in the water...",
      "metadata": {}
    }
  ]
}
```

### Decode chunk

```http
GET /packs/{pack_id}/chunks/{chunk_id}/decode
```

Response:

```json
{
  "chunk_id": "chunk_123",
  "content": "decoded text",
  "hash_verified": true
}
```

### Verify pack

```http
POST /packs/{pack_id}/verify
```

Response:

```json
{
  "valid": true,
  "decode_passed": 571,
  "decode_failed": 0
}
```

### Benchmark

```http
POST /packs/{pack_id}/bench
```

Request:

```json
{
  "queries": [
    {
      "query": "otter buddy",
      "expected_id": "chunk_123"
    }
  ],
  "baseline": "raw_tfidf"
}
```

## Local-first server mode

A local server could run like this:

```bash
spectrum serve ./memory.specpack --port 7777
```

Then an agent could call:

```http
POST http://localhost:7777/search
```

This is especially useful for:

- Local AI agents.
- Ollama-based workflows.
- OpenClaw-style agent systems.
- Desktop assistants.
- Private memory stores.

## Server design principles

Spectrum Server should be:

- Local-first.
- Simple to run.
- API-compatible with common AI workflows.
- Secure by default when exposed beyond localhost.
- Able to manage multiple packs.
- Able to serve snippets fast and decode full content on demand.

---

# 5. Spectrum Memory

## Summary

Spectrum Memory is the agent-memory layer built on top of Spectrum.

This is where Spectrum becomes more than search. It becomes a system for storing, recalling, updating, and managing long-term memories for AI agents.

## What it does

Spectrum Memory should manage:

- Conversation memories.
- User preferences.
- Project facts.
- Emotional/contextual memories.
- Long-term agent identity notes.
- Event memories.
- Search and recall.
- Memory update/delete/merge.
- Memory provenance.

## Why it matters

Most agents do not just need document search. They need memory.

A memory system should answer questions like:

- What should be remembered?
- What should be forgotten?
- What memory is relevant right now?
- Is this memory stale?
- Does this new memory contradict an old one?
- Where did this memory come from?
- Can the original conversation be reconstructed?

Spectrum's lossless format gives it an advantage here because memories can be traced back to original source context rather than only stored as summaries or embeddings.

## Memory object

A memory entry could look like:

```json
{
  "memory_id": "mem_001",
  "type": "preference",
  "content": "James prefers local-first tools and does not want regular users charged for Spectrum.",
  "source_chunk_id": "chunk_123",
  "source_pack_id": "pack_openai_export",
  "created_at": "2026-05-10T12:00:00Z",
  "updated_at": "2026-05-10T12:00:00Z",
  "confidence": 0.92,
  "importance": 0.8,
  "metadata": {
    "user_id": "james",
    "project": "Spectrum"
  }
}
```

## Memory operations

### Add memory

```http
POST /memory
```

Request:

```json
{
  "content": "James wants Spectrum Core to be open source.",
  "type": "project_preference",
  "metadata": {
    "project": "Spectrum"
  }
}
```

### Recall memory

```http
POST /memory/search
```

Request:

```json
{
  "query": "what does James want to be open source?",
  "top_k": 5
}
```

### Update memory

```http
PATCH /memory/{memory_id}
```

### Forget memory

```http
DELETE /memory/{memory_id}
```

### Explain memory source

```http
GET /memory/{memory_id}/source
```

This should return the original decoded source chunk or conversation context.

## Memory retrieval flow

A typical agent recall flow:

```text
user message -> memory query generation -> Spectrum search -> candidate memories -> rerank/filter -> inject relevant memories into prompt
```

Example:

```text
User: Should Spectrum be open source?

Memory system searches:
- "Spectrum open source James regular users charge"
- "business model Spectrum core free"

Top memory returned:
- James wants the core to be open source and does not want to charge regular users.
```

## Memory write flow

```text
conversation -> memory extraction -> importance scoring -> deduplication -> Spectrum encode -> index update
```

Important: Spectrum Memory should not blindly store everything.

It should support:

- Manual save.
- Auto-save with rules.
- Importance scoring.
- Deduplication.
- Conflict detection.
- User-controlled deletion.
- Export.

## Memory design principles

Spectrum Memory should be:

- Transparent.
- Source-linked.
- User-controllable.
- Local-first.
- Compatible with agent frameworks.
- Able to retrieve exact memories and surrounding context.
- Careful about privacy.

---

# 6. Spectrum Index

## Summary

Spectrum Index is the retrieval layer over `.specpack` data.

It should support fast lexical search first, then optional sparse, hybrid, and semantic layers later.

## Why it matters

The format stores data. The index makes it searchable.

A strong Spectrum Index lets Spectrum compete with raw text + BM25 stores and become useful for RAG and memory retrieval.

## Retrieval modes

### 1. BM25 over Spectrum chunks

This is the first serious retrieval mode.

It should support:

- Token indexing.
- BM25 scoring.
- Field weighting.
- Metadata filters.
- Top-k search.
- Snippet generation.

### 2. Sparse vector mode

A sparse retrieval mode could represent chunks using term/token weights.

This helps with:

- BM25-like ranking.
- Hybrid compatibility.
- Efficient lexical retrieval.

### 3. Spectrum-native similarity

This is a research area.

Potential approaches:

- Binary cosine over unique Spectrum token IDs.
- Token overlap scoring.
- Weighted token similarity.
- Dictionary-aware similarity.
- Chunk structure similarity.

This matters because early tests suggested that the `.spec` representation may carry retrieval signal even without conventional ranking.

### 4. Hybrid mode

Hybrid search combines Spectrum lexical retrieval with embeddings.

Possible flow:

```text
query -> Spectrum BM25 candidates
query -> vector candidates
merge/rerank -> final results
```

This allows Spectrum to work with existing vector databases rather than trying to replace them immediately.

## Metadata filters

Index search should support filters:

```json
{
  "query": "otter buddy",
  "filters": {
    "source": "openai_export",
    "date_after": "2024-01-01",
    "project": "Lexi"
  }
}
```

## Index update strategy

Spectrum should support:

- Static indexes for archive/search use cases.
- Incremental indexes for active memory systems.
- Rebuild indexes for major dictionary/format changes.
- Optional index stored inside `.specpack`.
- Optional external index sidecar file.

Possible files:

```text
memory.specpack
memory.specindex
```

or internal:

```text
memory.specpack
  /chunks
  /dictionary
  /metadata
  /index
```

## Search profiles

Search profiles could include:

| Profile | Purpose |
|---|---|
| `fast` | Lowest latency, approximate/snippet-first search |
| `balanced` | Good default for local search |
| `accurate` | More scoring/reranking, better precision |
| `memory` | Tuned for agent memory recall |
| `code` | Tuned for code/documentation search |

## Index design principles

Spectrum Index should be:

- Fast.
- Compact.
- Rebuildable.
- Queryable without fully decoding every chunk.
- Able to serve snippets quickly.
- Able to decode full source only when needed.
- Designed for both static archives and active memory.

---

# 7. Connectors

## Summary

Connectors let Spectrum ingest useful real-world data sources.

This is one of the most important adoption pieces. People use tools that connect to what they already have.

## Initial connector targets

### 1. OpenAI exports

This is an excellent early connector because it matches the agent-memory use case.

Should support:

- `conversations.json`
- Chat HTML exports.
- Uploaded files where available.
- Message metadata.
- Conversation titles.
- Dates.
- Participants/roles.
- Conversation chunking.

Possible command:

```bash
spectrum import openai ./export --out openai-memory.specpack
```

Use cases:

- Personal memory search.
- AI continuity experiments.
- Archive analysis.
- Local private memory.

### 2. Markdown folders

Markdown is common for:

- Notes.
- Obsidian vaults.
- Documentation.
- READMEs.
- Project plans.

Command:

```bash
spectrum import markdown ./vault --out vault.specpack
```

### 3. GitHub repositories

Useful for code/RAG demos.

Should support:

- Clone repo.
- Respect `.gitignore`.
- Include/exclude file types.
- Code-aware chunking.
- Preserve paths and line ranges.

Command:

```bash
spectrum import github https://github.com/user/repo --out repo.specpack
```

### 4. Obsidian vaults

Obsidian is a strong local-first knowledge base target.

Should support:

- Markdown notes.
- Internal links.
- Tags.
- Frontmatter.
- Folder structure.
- Attachments metadata.

### 5. Discord exports

Useful for communities, project chat, AI logs, and roleplay/memory archives.

Should support:

- Channels.
- Users.
- Timestamps.
- Message threading where possible.
- Attachments metadata.

### 6. Logs

Useful for engineering and observability.

Should support:

- Plain logs.
- JSONL logs.
- Timestamp parsing.
- Severity fields.
- Service/app metadata.

### 7. Generic files

Should support:

- `.txt`
- `.md`
- `.json`
- `.csv`
- `.html`
- source code files

Later:

- PDFs.
- Word documents.
- Email exports.
- Slack exports.
- Notion exports.

## Connector architecture

Each connector should produce a common internal document format:

```json
{
  "id": "doc_001",
  "content": "raw content",
  "source_type": "openai_export",
  "path": "conversations.json",
  "metadata": {
    "title": "Conversation title",
    "created_at": "2026-05-10",
    "author": "user"
  }
}
```

Then Spectrum Core handles encoding and packing.

This keeps connectors separate from the format itself.

## Connector design principles

Connectors should be:

- Modular.
- Easy to add.
- Metadata-rich.
- Careful with privacy.
- Good at preserving source context.
- Able to run locally.

---

# 8. UI / Dashboard

## Summary

A dashboard makes Spectrum understandable. It lets users browse packs, inspect data, run searches, compare benchmarks, and verify decode integrity visually.

This is not required for the core to work, but it is extremely useful for trust and adoption.

## Main dashboard features

### 1. Pack browser

Shows available packs:

- Pack name.
- Source type.
- Size.
- Number of documents/chunks.
- Created date.
- Decode status.
- Index status.

### 2. Search interface

A simple query UI:

```text
Search: [ toes in the water ]
```

Results should show:

- Rank.
- Score.
- Snippet.
- Source file/conversation.
- Metadata.
- Decode/open button.

### 3. Chunk inspector

Shows:

- Encoded chunk metadata.
- Decoded original text.
- Token/dictionary information.
- Hash verification.
- Related chunks.
- Source path/date.

### 4. Benchmark viewer

Shows benchmark comparisons:

- Spectrum vs raw TF-IDF.
- Spectrum vs BM25.
- Spectrum vs vector store, if available.
- Size comparison.
- Latency comparison.
- Hit@1/MRR/Recall@5.
- Charts.
- Query-by-query results.

### 5. Decode verification page

Shows:

- Number of chunks verified.
- Number passed.
- Number failed.
- Mismatch details.
- Source comparison.

### 6. Memory browser

For Spectrum Memory:

- View saved memories.
- Search memories.
- Edit memories.
- Delete memories.
- View source conversation/chunk.
- Show importance/confidence.
- Show last accessed date.

## Dashboard modes

### Local dashboard

Runs locally:

```bash
spectrum dashboard --pack memory.specpack
```

Could open:

```text
http://localhost:7777
```

### Hosted dashboard

Later, for teams/cloud users:

- Authentication.
- Team workspaces.
- Shared packs.
- Usage metrics.
- Access controls.

## UI design principles

The dashboard should be:

- Clear.
- Technical but not intimidating.
- Focused on trust.
- Good for demos.
- Good for debugging.
- Able to export reports.

A good dashboard helps users understand why Spectrum retrieved something, not just that it did.

---

# 9. LangChain and LlamaIndex Integrations

## Summary

Integrations with LangChain and LlamaIndex make Spectrum usable in existing RAG/agent workflows.

Developers already build with these frameworks, so Spectrum should meet them where they are.

## LangChain integration

Possible components:

- `SpectrumDocumentLoader`
- `SpectrumVectorStore` or `SpectrumRetriever`
- `SpectrumMemory`
- `SpectrumBM25Retriever`

Example:

```python
from spectrum_langchain import SpectrumRetriever

retriever = SpectrumRetriever.from_pack("memory.specpack", top_k=5)

results = retriever.invoke("what did James say about open source?")
```

Potential LangChain roles:

| Component | Role |
|---|---|
| Document Loader | Load `.specpack` content into LangChain docs |
| Retriever | Retrieve relevant chunks directly from Spectrum |
| Memory | Use Spectrum as long-term memory store |
| Tool | Expose Spectrum search to an agent |

## LlamaIndex integration

Possible components:

- `SpectrumReader`
- `SpectrumIndex`
- `SpectrumRetriever`
- `SpectrumMemoryStore`

Example:

```python
from spectrum_llamaindex import SpectrumRetriever

retriever = SpectrumRetriever("memory.specpack")
results = retriever.retrieve("toes in the water")
```

## Integration design principle

Do not force developers to abandon their existing stack.

Spectrum should be able to work as:

- A document source.
- A retriever.
- A memory backend.
- A compact source store under a vector index.
- A local recall tool for agents.

## Hybrid integration possibility

Spectrum could retrieve candidate chunks first, then an embedding model could rerank them.

Flow:

```text
User query -> Spectrum BM25 top 50 -> embedding reranker top 5 -> LLM context
```

This can reduce vector search cost and keep source data compact.

---

# 10. Optional Cloud

## Summary

The cloud should be optional, not required.

Spectrum should remain local-first and open for regular users. A cloud product can exist later for teams and businesses that need hosting, sync, access control, and support.

## Why optional cloud makes sense

Regular users and hobbyists may want:

- Free local use.
- Privacy.
- Control.
- No subscription.

Businesses may want:

- Hosted API.
- Team access.
- Backups.
- Security controls.
- Compliance tools.
- Monitoring.
- Support.

This allows an open-core model without punishing regular users.

## Possible cloud features

### 1. Hosted packs

Users can upload or sync `.specpack` stores.

Features:

- Secure storage.
- API access.
- Search endpoint.
- Decode endpoint.
- Versioning.

### 2. Team workspaces

Features:

- Multiple users.
- Shared projects.
- Permissions.
- Audit logs.
- Usage tracking.

### 3. Managed indexes

Features:

- Hosted BM25/sparse/hybrid indexes.
- Automatic rebuilds.
- Query analytics.
- Performance monitoring.

### 4. Connectors

Hosted connectors for:

- GitHub.
- Google Drive.
- Slack.
- Notion.
- S3.
- OpenAI exports.

### 5. Compliance and governance

Useful for business customers:

- Data retention settings.
- Deletion controls.
- Access logs.
- Export tools.
- Encryption.
- Private deployment options.

## Open-core split

### Free/open-source

- Format spec.
- Core encoder/decoder.
- CLI.
- Local server.
- Basic SDKs.
- Basic connectors.
- Local dashboard.
- LangChain/LlamaIndex integrations.

### Paid/commercial later

- Hosted cloud.
- Team workspaces.
- Enterprise connectors.
- Managed indexes.
- Advanced dashboards.
- Compliance tools.
- Support.
- Private deployments.

## Cloud design principles

The cloud should:

- Never be required for local use.
- Avoid vendor lock-in.
- Let users export their data.
- Keep the format open.
- Charge businesses for convenience, scale, and support, not regular users for basic memory.

---

# 11. Suggested Build Order

## Phase 1: Stabilise Core and CLI

Goal: make Spectrum reliable and easy to test locally.

Build:

- Format spec draft.
- Core encode/decode library.
- `.specpack` reader/writer.
- `spectrum pack`.
- `spectrum search`.
- `spectrum decode`.
- `spectrum verify`.
- `spectrum demo`.
- Markdown/JSON/HTML reports.

Success criteria:

- Users can run Spectrum on their own folder/repo/export.
- Decode fidelity is proven.
- Benchmarks are reproducible.
- Reports are clear.

## Phase 2: SDKs and Index Improvements

Goal: make Spectrum usable inside apps.

Build:

- TypeScript SDK.
- Python SDK.
- Stable search API.
- BM25 index improvements.
- Metadata filters.
- Incremental indexing.
- Search profiles.

Success criteria:

- Developers can integrate Spectrum without shelling out to CLI.
- Search results are consistent between CLI and SDK.
- Local agent systems can call Spectrum directly.

## Phase 3: Connectors

Goal: make Spectrum easy to apply to real data.

Build:

- OpenAI export connector.
- Markdown folder connector.
- GitHub repo connector.
- Obsidian connector.
- Logs connector.

Success criteria:

- Users can import meaningful datasets with one command.
- Metadata is preserved.
- Search results remain source-linked.

## Phase 4: Spectrum Server and Dashboard

Goal: make Spectrum usable as a local service and visually inspectable.

Build:

- Local HTTP server.
- Search/decode/verify endpoints.
- Basic dashboard.
- Pack browser.
- Search UI.
- Benchmark viewer.
- Memory browser prototype.

Success criteria:

- Agents can use Spectrum over HTTP.
- Users can inspect packs visually.
- Demos are easy to understand.

## Phase 5: Spectrum Memory

Goal: turn Spectrum into an agent-memory layer.

Build:

- Memory schema.
- Memory add/search/update/delete.
- Source-linked memories.
- Importance/confidence metadata.
- Deduplication.
- Agent recall API.
- LangChain/LlamaIndex memory integrations.

Success criteria:

- Agents can store and recall long-term memories.
- Memories can be traced back to source context.
- Users can control and delete memories.

## Phase 6: Hybrid and Cloud Options

Goal: expand compatibility and commercial viability.

Build:

- Optional vector reranking.
- Hybrid search support.
- Hosted prototype.
- Team workspaces.
- Auth/access controls.
- Managed indexes.
- Enterprise connectors.

Success criteria:

- Spectrum can fit into modern RAG stacks.
- Businesses have a reason to pay.
- Local users are not locked out.

---

# 12. Positioning

Spectrum should avoid sounding like just another database, compression tool, or vector store.

A strong positioning statement:

> Spectrum is a compact, deterministic, lossless retrieval substrate for AI memory and RAG. It stores source content in a retrievable format, supports fast lexical recall, and can reconstruct the original data exactly when needed.

## What Spectrum is

- A format.
- A pack system.
- A retrieval substrate.
- A local-first memory store.
- A benchmarkable alternative to raw text stores.
- A possible foundation for agent memory.

## What Spectrum is not, at least initially

- Not a full Elasticsearch replacement.
- Not a vector database killer.
- Not a cloud-only SaaS.
- Not just compression.
- Not just another RAG demo.

## Best early markets

1. Local-first AI agents.
2. Personal AI memory.
3. OpenAI/LLM conversation archive search.
4. Codebase/documentation retrieval.
5. Compressed RAG stores.
6. Offline/private knowledge bases.
7. Audit-friendly memory systems.

## Strongest differentiators

- Compact representation.
- Lossless reconstruction.
- Fast search.
- Source-linked recall.
- Local-first design.
- Works with lexical/BM25-style retrieval.
- Can complement vector search rather than fight it.

---

# 13. Recommended Repository Structure

A possible monorepo layout:

```text
spectrum/
  README.md
  SPECIFICATION.md
  ROADMAP.md
  LICENSE

  packages/
    core/
      src/
      tests/
      package.json

    cli/
      src/
      tests/
      package.json

    sdk-js/
      src/
      tests/
      package.json

    sdk-python/
      spectrum/
      tests/
      pyproject.toml

    server/
      src/
      tests/
      package.json

    dashboard/
      src/
      package.json

    connectors/
      openai/
      markdown/
      github/
      obsidian/
      logs/

    integrations/
      langchain/
      llamaindex/

  demo/
    runs/
    sample-data/

  docs/
    architecture.md
    cli.md
    sdk.md
    server.md
    memory.md
    connectors.md
    benchmarks.md
```

This structure keeps the format and tools together while allowing different packages to mature separately.

---

# 14. Minimum Viable Ecosystem

If the goal is to make Spectrum useful quickly, the minimum viable ecosystem should be:

1. Stable `.specpack` format.
2. Core encode/decode.
3. CLI with pack/search/decode/demo/bench/verify.
4. OpenAI export connector.
5. Markdown/GitHub connector.
6. TypeScript SDK.
7. Python SDK.
8. Local HTTP server.
9. Basic dashboard.
10. LangChain retriever integration.

That would be enough for developers to:

- Try Spectrum.
- Benchmark Spectrum.
- Use it in local agents.
- Search their own archives.
- Build apps on top of it.

---

# 15. Final Strategic Recommendation

Spectrum should be developed as an open-core local-first ecosystem.

The format and core tools should be open source because trust is essential for memory/storage infrastructure. Developers need to know they can inspect it, use it locally, and recover their data without permission from a company.

The business opportunity should come later from hosted convenience, team features, enterprise connectors, managed indexes, dashboards, compliance tooling, and support.

The most important immediate goal is not to beat every vector database or search engine. The immediate goal is to prove this statement repeatedly:

> Spectrum can store real-world memory, code, and document corpora more compactly than raw text stores, retrieve from them quickly, and reconstruct the source data losslessly.

Once that is clearly proven, the ecosystem around Spectrum can grow naturally.
