---
name: attic
description: >
  Archive vault files into attic/ cold storage, or restore them — the executable runbook for the
  CLAUDE.md §2.1 contract. Use on the owner's instruction: /attic, "archive X to the
  attic", "retire these files", "restore Y from the attic", "what's in my attic?"; an archive may
  also start on the agent's own finding of a stale file and run up to the preview, and the move then
  waits for the owner's yes. Handles one file or a batch (a closed project or campaign): inbound-reference
  census, harvest of future-useful facts into surviving pages, an owner-approved preview, manifest +
  move, a plain-text link sweep, index/log/qmd upkeep, and a control-verified final check.
  Census-scoped reads — never a full-vault pass.
user-invocable: true
---

# attic — cold-storage archive & restore (§2.1, executed)

## Contract
CLAUDE.md §2.1 stays the governing text: the attic opens only on the owner's word (an archive the agent prepares waits for their yes), its contents are
never knowledge, and outside this operation it stays unread. This skill adds **procedure only** —
it can never relax a permission. Never edit the *contents* of an archived file; a restored file is
live again, and the restore changes only its links to files still archived (Restore step 4).

## Triggers
`/attic archive <files|folder|topic>` · `/attic restore <item>` · `/attic list` · natural language
("archive the X project to the attic", "retire these files", "what's in my attic?"). Passive
context (an `@`-mention, an editor selection, IDEAS.md) never triggers it. The agent's own finding of a stale file starts an archive up to the Step-3 preview, presented for the owner's one-word yes.

## Start check (every archive and restore)
Run it once the owner's word has opened the attic: first, in an operation they asked for; after their
yes and before Step 4, in an archive the agent prepared. From the vault root,
`grep -n '^- \[pending ' attic/MANIFEST.md` prints every pending manifest line (Step 4): exit
status 1 with no output is clean, and exit status 2 (no manifest found) a failed probe, never clean.
Control, same run: `printf '%s\n' '- [pending 2000-01-01] control' | grep -c '^- \[pending '` prints 1.
A pending line is an interrupted archive: stop before anything moves or the manifest changes, and
report each line to the owner with where its file now is
(`ls -d "<origin folder>/<name>" "attic/<subfolder>/<name>"`, names only, never opening an archived
file). It is never completed, deleted or repaired automatically; the owner decides.

## Archive pipeline

### 0 — Scope
Resolve the instruction to a concrete candidate list: explicit paths, a folder, or a topic located
via `index.md` + targeted grep. Wiki pages, `output/` deliverables and `assets/` files all qualify.
`raw/` stays out of scope unless the owner names it — the source layer is already immutable cold
storage, and archived pages' `sources:` may keep pointing at it (attic→outside links are allowed).

### 1 — Census (read-only)
For every candidate, find inbound references with BOTH pattern families — missing the second family
is the known failure mode (deliverables are often cited as backticked paths, not links):
- **wikilinks**: `grep -rF "[[<basename>" --include='*.md' wiki` (catches `]]`, `|`, `#`, `![[`);
- **plain paths**: `grep -rF "<origin/path>"` plus the bare filename, across wiki/.
Also scan `MANUAL.md`, `README.md`, `output/` (report-only surfaces). Classify every hit:
**live wiki** (must sweep) · **co-candidate** (link stays — attic-internal edges are by design) ·
**`wiki/log.md`** (append-only history, never swept). Positive control (§11): the same probe against
a known-linked live page must return >0 before any "no inbound references" claim. Also check each
basename against `raw/` and `wiki/` for name collisions — this drives the manifest link form.

### 2 — Harvest gate
Before anything moves, read each candidate **wiki page** and fold facts with future value into the
surviving graph: status/outcome facts → the relevant synthesis or campaign page; durable
programme/route/organisation facts → entity pages; reusable personal material (approved bios,
standing decisions) → `wiki/user/`. New knowledge only — never duplicate what survivors already
hold. Deliverables (output/assets) are skimmed for the same purpose, not compiled. Every harvest
edit is listed in the preview.

### 3 — Preview & approval (mandatory gate)
Present the full table — file · origin · one-phrase reason · harvest destination(s) · sweep scale —
and WAIT for the owner's go. No file moves before approval, however obvious the case. The preview
also names, by path, each dated record that describes this move and so keeps its origin paths (a
register entry, a plan or run page); Step 7's path probe exempts exactly those.

### 4 — Manifest (pending, before any move)
Before the first move, add ONE line per file to `attic/MANIFEST.md`, newest-first, in its pending
form, with the file-editing tool:
`- [pending YYYY-MM-DD] <link-or-path> — from `origin/` — one-phrase reason`.
Step 8 completes each line by dropping `pending `, so a complete line begins with its date and the
start check's pattern never matches one.
`.md` files → **path-prefixed** wikilink `[[<subfolder>/<name>]]` (unambiguous under basename
collisions; gives the grey graph edge). Non-Markdown → a backticked path (an unresolvable wikilink
is worse than none). Reasons name where harvested facts now live, so a future restore knows what
already survived. The manifest is written only inside this operation. Read back:
`grep -c '^- \[pending ' attic/MANIFEST.md` prints the number of lines written. This archive's own
line for a move Step 5 did not make is deleted at once, and reported with that finding.

### 5 — Move
Batches get a thematic subfolder (`attic/<topic-year>/`, e.g. `funding-2026/`); singletons go to
the attic root (the standing convention). Move folders intact; quote every path (spaces,
apostrophes). `path:attic/` graph colouring covers subfolders automatically.
Move with a plain shell `mv -n`, never through Obsidian (its file manager, the file pane or the
link-aware `obsidian-cli` move): with automatic link updating on, Obsidian rewrites the links inside
the moved files and in every file that links to them, which edits archived contents and can edit
`raw/` (on 30 September the paper-skills kit's README links were rewritten this way). One
`mv -n "<origin folder>/<candidate name>" "<destination folder>/"` per candidate, then confirm it
moved: its origin path is gone and its destination exists. A move that did not happen (`mv -n`
skips an occupied destination silently) is a finding, reported, never forced. A shell move changes no
file's contents; Step 6 sweeps the inbound links by hand.

### 6 — Sweep
Replace every live-wiki inbound reference with plain text: first occurrence per file
`X (archived)`, later occurrences the plain title; reword where a sentence needs it. Co-candidate
links stay; `wiki/log.md` is never rewritten. §4.4 guard: every edited page keeps ≥1 wikilink — if
a sweep would orphan a page, substitute a link to the harvest destination. Remove the candidates'
`index.md` entries and refresh index descriptions that named them. Bump `updated:` only where
knowledge changed — a pure link swap is not a knowledge update.

### 7 — Guarded verify (before the log is written)
Run with §11 positive controls; write the log ONLY when all pass:
- per-candidate link probe over live wiki (excl. `log.md`) = 0, using the exact link forms
  `"[[<b>]]" "[[<b>|" "[[<b>#" "/<b>]]" "/<b>|"` · control on a kept page name > 0;
- per-candidate path probe = 0 over live wiki, excluding `wiki/log.md` and the dated records the
  preview named · control on a kept working-file path > 0;
- `index.md` clean of candidates · control on a kept entry > 0;
- no live-wiki links into attic paths: `grep -rF "[[<subfolder>/" wiki` = 0;
- orphan guard: every swept page still contains `[[`;
- moved-file count = manifest-line delta; origin folders hold no candidate remnants; `raw/`
  untouched (`find raw -type f -newermt "<op start>"` empty).
Residues are findings, not embarrassments: fix, re-run the probe, and report them honestly.

### 8 — Registries (the manifest completed last)
Append one `attic` entry to `wiki/log.md` (shell append, never Read+Edit) naming: harvest edits,
swept pages, moves, manifest delta, and read it back: `tail -n <its line count> wiki/log.md` shows
the whole entry, heading to last line. Only then complete the manifest: drop `pending ` from each
line Step 4 wrote, with the file-editing tool. Read back with
`grep -c '^- \[pending ' attic/MANIFEST.md` and, as its control, `grep -c '^- \[' attic/MANIFEST.md`,
each run before and after: the first falls to 0 and the second stays the same. Equal counts cannot
show that no line was lost (two lines completed as the first of them twice give the same counts), so
read the lines back as well:
- `sed 's/^- \[pending /- [/' attic/MANIFEST.md`, run before the completion and again after, prints
  the same text both times (before, the manifest as it must read once complete; after, as it
  reads): every other line unchanged, none lost, added or doubled.
- Each completed line is there exactly once: with the lines Step 4 wrote, `pending ` dropped,
  written one per line with no blank line with the file-writing tool to a scratch file outside the
  vault,
  `awk 'NR == FNR { n[$0] = 0; next } ($0 in n) { n[$0]++ } END { for (l in n) print n[l] ": " l }' <completed lines file> attic/MANIFEST.md`
  prints `1: ` before every one of them.

Any other result is a finding for the owner, never repaired automatically. An archive that stops
earlier leaves its lines pending, for the owner at the next start check. Archiving does not refresh
qmd: the `qmd-search` skill's gate catches the index up before its next search, so it sees the pages
archiving removed.

## Restore pipeline
1. The start check; then read `attic/MANIFEST.md` (this instruction is the sanctioned read); locate
   the item + origin.
2. Move the file back (recreate the origin folder if needed); delete its manifest line.
3. Wiki page → re-register in `index.md` (fresh one-liner from the page); then offer to re-link the
   plain-text mentions (`grep -rF "<name> (archived)" wiki`) — the owner picks which go live again.
4. Links into the attic: a restored file is live again, so its links to a file still archived (the
   other half of an archived pair) now lead into the attic. List the attic by name
   (`find attic -type f ! -path attic/MANIFEST.md -print`: only the root catalogue is set aside, by
   its path; an archived project's own `MANIFEST.md` is listed) and write each name, a Markdown file's without
   `.md`, one per line with no blank line (a blank line matches every line), with the file-writing
   tool to a scratch file outside the vault. From the vault root, search the restored Markdown files
   and the live pages naming them (`grep -rliF "<restored name>" --include='*.md' wiki`, the name
   written the same way; `wiki/log.md` set aside):
   `grep -rniFf <pattern file> --include='*.md' "<restored path>" "<page>" …`, and read every hit. A
   link of any form into the attic becomes plain text as Step 6 sweeps; a plain mention stays; a link
   that could also mean a live file of the same name is listed for the owner, never rewritten.
   Control: the same search with a pattern file holding a name a searched file is known to contain (a
   live page it links to) hits it. Known limit: a name written encoded or escaped (`%20`, `%27`,
   `&#39;`, a backslash) is not found, here or by lint (whose Step 2c states its own limits).
5. Append an `attic` log entry.
6. Boundary check, last: lint's attic-leak check (its Step 2c, its control included). Its search
   prints its own exit status after its hits, read straight after it and before the log filter, whose
   status would turn a search error into an ordinary no-match:
   `{ grep -rnoFf <pattern file> --include='*.md' wiki; echo "search exit: $?"; } | grep -v '^wiki/log\.md:'`.
   `search exit: 0` or `1` with no hit printed is a clean boundary; any other status (`2`, or no
   status line) is a failed probe, never clean. The control passes only with a hit printed and
   `search exit: 0`. A hit stops the restore and goes to the owner, never fixed here.

## /attic list
Read the manifest back to the owner. Nothing else in the attic is opened.

## Report format
Compact table: moved/restored (count + destination) · harvested (fact → surviving page) · swept
(pages / links) · verify results (each probe with its control) · any manifest line left pending.
British/UK English.

## Hard constraints
- **The move needs the owner's word** (their instruction, or their yes to a preview the agent prepared); the Step-3 preview gate is never skipped.
- **Census-scoped reads** — never a full-vault re-read; token discipline throughout.
- **A zero-findings check is a claim**: every probe carries a positive control (CLAUDE.md §11).
- **Every move is a plain shell `mv -n`**, confirmed after it runs, never a move through Obsidian.
- **The manifest line comes first, pending**, and is completed only after the log entry is read back;
  a pending line found by the start check goes to the owner, never repaired automatically.
- Never edit archived file contents; never sweep a link between two archived files, or `log.md` history.
- deep-lint SUGGESTS candidates (as ready `/attic archive …` lines); only the owner's word runs them.
