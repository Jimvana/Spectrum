# Portable Specpack Runtime Plan

## Current Status

Spectrum can now hold and serve a whole repo directly from a `.specpack` with sidecar media/model files. The Hub can append large projects with visible progress, skip generated/build folders by default, defer expensive indexing for large appends, and rebuild the embedded search index on demand.

The server now has a lightweight `/packs/{id}/files` endpoint and a decoded-file cache, so agents and app previews can browse and hydrate files without repeatedly unpacking the same content or pulling the full manifest.

## Completed

- Hub append flow now shows staged progress, verification/indexing stages, and a progress bar.
- Hub has a `Rebuild Index` action and defers indexing automatically for large appends.
- Hub append defaults to project-context behavior by skipping generated/build folders unless explicitly included.
- Core packing supports `include_generated=False` for project-friendly capture.
- Media, model, binary, and failed-encoding files continue to externalize into the `.media` sidecar.
- Search filters generated/build paths by default, with `include_generated=true` available for archive-style searches.
- Server raw/document hydration uses an in-memory decoded-file cache with mutation invalidation.
- Server exposes `/packs/{id}/files` with pagination, prefix filtering, raw URLs, hydrate URLs, and generated-path filtering.
- Test coverage now covers generated-folder skipping, search filtering, files endpoint behavior, and raw decode caching.

## Next Work

- Improve search ranking noise:
  - Down-rank or exclude `test_sources`, benchmark outputs, large fixtures, and vendored examples by default.
  - Keep a clear `include_generated` or archive-mode path for full-pack searching.

- Improve Hub append UX:
  - Add finer file-count progress from the core append loop instead of path-level progress only.
  - Show explicit “index stale” state when indexing is deferred.
  - Add a cancel-safe append/index workflow if long operations become common.

- Improve Files view:
  - Use the server `/files` endpoint for quick browsing before exporting.
  - Add optional export/open selected file or folder behavior.
  - Keep true mounted-folder editing as a later phase.

- Improve app serving:
  - Add clearer route diagnostics when a packed project expects a backend dev server.
  - Support per-pack app defaults for entry point and backend proxy.
  - Consider mapping packed app ports to their expected local development ports where safe.

## Acceptance Checks

- Full Spectrum repo pack serves on `7777` without pulling a multi-megabyte manifest for normal browsing.
- Repeated raw hydration of the same file returns from cache and feels sub-second.
- Default search results prefer source/project files over generated artifacts.
- Large Hub appends remain visibly active through scan, append, verify, and index stages.
- Rebuilding the Hub exe and installer includes the portable-runtime changes.

