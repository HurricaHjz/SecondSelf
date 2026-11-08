---
name: qmd-search
description: >
  OPTIONAL, DORMANT semantic-search layer over the wiki, powered by qmd (local hybrid BM25 + vector +
  rerank). Use only when the wiki has outgrown index.md AND the user has installed + enabled qmd. The
  agent auto-detects qmd; if it is absent or disabled this skill does nothing and the normal
  index.md → grep search runs unchanged. Provides confidence-aware semantic retrieval as the
  query/output fallback, with a freshness gate before every qmd search. Refreshes only when needed.
  Retrieval only — never writes wiki pages or decides confidence. Trigger: /qmd-search <query>, or internally as
  the query/output semantic fallback.
user-invocable: true
---

# qmd-search — optional semantic search over the wiki (dormant until qmd is installed)

## What this is
A thin, **dormant** adapter to `qmd`. It does **not** replace `index.md` (the curated, read-first catalogue); it is the
*semantic fallback* `query`/`output` reach for when the catalogue under-covers a question, and the
**freshness gate** that catches up qmd's embeddings before a search. qmd retrieves; the wiki governs
(compile, cross-link, confidence, conflicts).

## Activation — capability detection (the opt-in *is* installation)
Use qmd **only if all three hold**; otherwise use the default search:
1. `command -v qmd` succeeds (qmd installed), AND
2. an index exists for this vault (`qmd status` lists indexed collections), AND
3. there is **no `.qmd-off` marker** in the vault root — create that file to force qmd off without uninstalling; its absence means **active** (installing qmd + building an index *is* the opt-in).

Check installation and `.qmd-off` before invoking any qmd command, including `qmd status`. If detection fails, use `index.md` → `grep`; never prompt a non-adopter to install anything. The pre-search gate also checks installation and the marker and explains a plain-route result in one line.

## When to invoke (opt-in — never on every search)
qmd search is **not** a default step. Invoke it only when:
1. **the user explicitly asks** (`/qmd-search`, "search semantically", "use qmd"), **or**
2. **the agent judges the cheap path insufficient** — `index.md` + `grep` under-cover the question (it needs
   semantic recall, or the corpus is too large to scan reliably).

Otherwise answer from `index.md` → `grep` and **do not call qmd** — a qmd *query* reads passages into the
agent's context (real tokens), so it must earn that cost. Writes leave the semantic index alone; when a qmd search is warranted, the freshness gate below catches up first.

## Search (only when active)
Before **every** `qmd search`, `qmd vsearch` or `qmd query`, run the gate in the next section and inspect its exit code. Repeat this after an earlier search in the same session. Only exit 0 permits the qmd search; any other result takes the plain route and retains the gate's explanation.
- **CLI shell-out by default** (no daemon):
  `qmd query "<question>" --json --files --min-score <t> -n <k>` over the `wiki` collection. The CLI
  inherits the shell environment, sidestepping the MCP-spawn `HOME`/db-path pitfall (qmd issue #615).
- **MCP daemon** — an *advanced* option for heavy users who want warm models (`qmd mcp --http --daemon`);
  set `QMD_CONFIG_DIR` / the db path explicitly so the server opens the real index.
- **Confidence-aware ranking:** qmd ranks by relevance; then re-order by each page's `confidence`
  (down-rank `low`/`very-low`, lift `high`/`authoritative`) and break ties by newer `updated`
  (supersession), per CLAUDE.md §4.6. Then deep-read the top pages and govern as usual.
- **Index-first, always:** `index.md` is read first; qmd is the *fallback / widener* when the catalogue is
  insufficient or the corpus is large. A qmd hit never bypasses the governing deep-read.

## Refresh before search — one-shot, never resident
**Confidence still refreshes on write.** For every created or changed page, the agent assigns or confirms `confidence` and stamps `audited:` per CLAUDE.md §4.6, independently of qmd.

**The turn-end refresh is retired.** No write operation, ingest completion or turn end starts `qmd update` or `qmd embed`. Immediately before every qmd search, run this gate from the vault root, with the same environment as the search:
```sh
/bin/sh .claude/skills/qmd-search/qmd-fresh.sh
```
- **Exit 0:** the index is fresh or a completed `qmd update && qmd embed` caught it up. The requested qmd search may now run.
- **Exit 1:** qmd is absent, `.qmd-off` is present, another session holds the refresh lock, or the refresh failed. Use `index.md` then `grep`, and say the semantic index is not current using the gate's one-line reason. Never search the stale index.
- **Exit 2:** `PROBE FAILED` names a broken premise, such as a missing source tree or failed filesystem operation. Use the same plain route and report that reason; this is never a clean freshness result.

The gate checks both files and directories under `wiki/` and `raw/` against the refresh stamp. Directory mtimes expose deletions; a missing stamp forces a refresh. It acquires the directory lock before checking freshness, waits for update and embed to finish when stale, stamps before the work and promotes the stamp only after both commands succeed. A change during refresh remains newer than that stamp and is caught at the next search. It neither waits on another session's lock nor removes that session's lock. A lock left by a killed process also takes the plain route.

The default cache is `${XDG_CACHE_HOME:-$HOME/.cache}/qmd`, with `vault-refresh-stamp` and `vault-refresh.lock`. An absolute `INDEX_PATH` uses adjacent `<INDEX_PATH>.vault-refresh-stamp` and `<INDEX_PATH>.vault-refresh.lock` instead. Keep the root, config and database environment identical for the gate and search; the gate uses the default qmd invocation, so do not add a different `--index` to the search alone. qmd updates only its configured collections; the existing exclusion of `wiki/log.md` is unchanged. No daemon, watcher or periodic write-time backstop is needed.

## Graceful degradation (mandatory)
Any qmd call that errors, times out or returns nonzero takes `index.md` → `grep`. Say why the semantic route was unavailable; a freshness failure says the semantic index is not current. The vault never depends on qmd; it only accelerates with it.

## Hard constraints
- **Retrieval only.** qmd never creates, edits, or deletes wiki pages, and never decides `confidence` or
  conflicts — those stay with `ingest`/`query`/`deep-lint`.
- **Nothing resident.** Every qmd invocation — by the agent or by the pre-search gate — is a
  **one-shot CLI call** (`qmd search`/`vsearch`/`query`/`update`/`embed`) that runs and **exits**. The
  agent MUST NOT start the MCP daemon (`qmd mcp …`) or any long-running/watching qmd process; that is a
  manual, user-only opt-in. Nothing qmd-related stays resident, and nothing runs while the vault is idle.
- **Dormant by default.** Do nothing unless detection passes; never prompt a non-adopter to install qmd.
- **Index-first.** `index.md` is read before qmd; qmd is the semantic fallback/widener, not a replacement.
- **State stays out of git.** qmd config/index/models live in `~/.config/qmd` and `~/.cache/qmd`; a
  project-local index (`.qmd/`, `*.sqlite`) is git-ignored.
- British/UK English in any user-facing output.
