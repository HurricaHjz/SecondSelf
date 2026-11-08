---
name: output
description: >
  Produce a user-facing DELIVERABLE (report, brief, literature review, slide deck, table, email,
  outline, …) into the output/ directory — grounded in the wiki and strictly following the user's
  instruction. Use when the user runs /output, or says "write/draft/produce/generate me a <X> about
  <Y>", "make a <report/brief/deck/email/table> from my notes/wiki", or "turn [[topic]] into <format>
  in output/". Distinct from `query` (answers inline or files a cited synthesis INTO the wiki).
  The deliverable goes to output/, cites the wiki pages it
  draws on, clearly labels any general-knowledge content, and NEVER fabricates facts, figures, quotes
  or citations.
user-invocable: true
---

# output — generate a grounded deliverable into `output/`

## Goal
Turn a user instruction + the compiled wiki into a **deliverable file in `output/`** that (a) **follows
the instruction exactly** (format, scope, length, audience, style), (b) is **grounded** in the wiki and
**cited**, and (c) **never hallucinates** — abstain when unsure rather than confabulate.

## Triggers
- `/output <instruction>`
- "write / draft / produce / generate me a <deliverable> about <X>", "make a <report / brief / deck /
  table / email> from my notes", "turn [[topic]] into <format>".

## Pipeline

### Step 1 — Pin the instruction (no drift)
Extract a small **spec** from the user's words: *deliverable type · topic/scope · format · length/size ·
audience · tone · must-include / must-exclude · citation style · output filename*. If a **material**
detail is missing or genuinely ambiguous, ask **1–2 crisp questions**; otherwise proceed with sensible
defaults **and state them**. Never silently widen, narrow, or reinterpret the ask.

**Customisation gap-fill:** for spec fields the instruction leaves **unstated**, check
`CUSTOMISATION.md` → `## Deliverable defaults` (if the file and section exist): apply any
standing defaults found there (citation style, deck format, length conventions) and note them in the
grounding note. An explicit instruction always overrides; if the section is absent or empty, choose
sensible defaults yourself (and state them). Conversational output *styles* never apply to
deliverables (CLAUDE.md §1) — this gap-fill covers content-format defaults only. **Single source of
truth:** deliverable defaults live *only* in that Customisation section — re-read it on every run and
never copy its values into this skill, any config, or the deliverable itself (beyond applying them).

**Folder conventions:** before writing, choose the destination under `output/` and read the README of
that folder, then the README of each parent folder up to and including `output/README.md`, nearest
first. Read every README that exists along that path. Apply their folder-specific conventions; where
two READMEs disagree, the nearer one wins.

READMEs hold only folder-specific conventions and point to `CUSTOMISATION.md` for global deliverable
defaults without copying them. Where a README and `CUSTOMISATION.md` disagree, follow
`CUSTOMISATION.md` and name the difference in the reply for the owner to settle. A live instruction
outranks both; when it overrides either, follow it and say so in the reply, unless it asks for
something a README rule forbids with "never": then ask the owner first. Likewise ask before adding
any topic, item or question they have not already approved. Write such content only on their yes; in
an unattended run, leave it out and list each question in the report. The README shape is in
`README-template.md` beside this skill.

### Step 2 — Ground in the wiki (read first, like `query`)
Read `wiki/index.md` **whole** (`route` mode, CLAUDE.md §5), then deep-read the relevant pages (follow `## Related`
one hop, which widens a shortlist route already produced and never replaces it). Collect the
facts you will use **together with the page each comes from** (for citation). The deliverable is built
from compiled knowledge — *not guessed*. Consult `wiki/user/` for personal context when the deliverable
is about, or for, the owner. **Triage by `confidence` as `query` does**: lean on `authoritative`/`high`
pages for load-bearing claims; the field is already in frontmatter, so this is free. If the catalogue
under-covers and qmd is active (the `qmd-search` skill, dormant unless installed), use it as the semantic
fallback to locate relevant pages, then deep-read; otherwise `grep`. **Freshness duty**: apply
`query` Step 3b to the pages you read — surface stale/contradicted pages in the report line and mark
them on-page (`flagged:` frontmatter / §4.4 block); no extra reads for this.

### Step 3 — Separate grounded · general · unknown (anti-hallucination core)
Classify every claim before you write it:
- **Grounded in the wiki** → cite the page(s) inline as `[[Page]]` (or the requested citation style); weight by the page's `confidence` — state `authoritative`/`high` plainly, but attribute and hedge any claim resting only on `low`/`very-low` pages.
- **General knowledge** the instruction needs but the wiki lacks → include **only if clearly labelled**
  (e.g. *"(general knowledge — not from the wiki)"*). Never present it as wiki-sourced.
- **Unknown / unverifiable** → **do not invent it.** Omit and note the gap, or mark a factual claim
  `unverified`. **Never fabricate facts, numbers, quotes, or citations.** Prefer quoting the raw source
  over paraphrasing when precision matters.
- If the instruction needs something neither the wiki nor safe general knowledge can support, **say so**
  in the deliverable / report rather than fill the gap with invention.
- **Load-bearing wiki gap** → the Step-6 report MAY end with one propose-only gather brief (why ·
  what · how · cost) under the `query` Step-4b bar and consent ledger (CLAUDE.md §6) — the owner's
  explicit yes runs it; never proposed in non-interactive runs.

### Step 4 — Produce the deliverable, strictly to spec
Write exactly what was asked, in the requested **format and length**: a Markdown report/brief/review
(default), a **Marp** deck (`marp: true` frontmatter), a table, an email, a Canvas via the `json-canvas`
skill, etc. Use **British/UK English**; keep verbatim quotes exact; honour must-include/exclude. Default
citations are inline `[[wikilinks]]` (clickable in Obsidian); use a footnote/bibliography style instead
if the deliverable is external-facing or the user asks.

### Step 5 — Write to `output/<slug>.<ext>` (never into `wiki/`)
Save to **`output/`** (the deliverables layer — *not* the knowledge graph). Filename = a clean
kebab-case slug + correct extension. Do **not** modify `raw/`, or `wiki/` beyond the two named exceptions under Hard constraints. (If the user wants the result
compounded back into the knowledge base, that's a `query` synthesis, not an `output`.)
**Root vs subfolders (CLAUDE.md §2):** the root holds one-off / temporary deliverables; a report
(run, morning, audit, review) goes to `reports/`, the inbox the owner sorts later; standing
artefacts live in the matching subfolder (`user-notes/` owner quick-references · `fundings/` funding
applications) and are **actively maintained** — a run that updates one edits it in place. Create a
new subfolder only on the user's instruction. When filing a standing artefact derived from wiki
pages, add a "maintained derivative" line to each source page's `## Related` so future edits
propagate.

### Step 6 — Report + grounding note
State the path written, then a concise **grounding note**: which wiki pages it draws on, what (if
anything) is labelled general-knowledge, and any gaps flagged or questions still open — closing with
the freshness line (`query` Step 3b's gate, style-invariant):
`Freshness: <N> pages read · oldest [[page]] (updated YYYY-MM-DD) · <k> flagged`
**A completion gate: the report is not done without it.** A run that read no wiki pages says so instead.

## Hard constraints
- **Follow the instruction exactly** — format, length, scope, inclusions/exclusions. Use defaults only
  when unstated, and state them when used.
- **No hallucination.** Grounded → cite; general → label; unknown → omit / flag / abstain. **Never
  invent facts, figures, quotes, or citations.**
- **Weight by `confidence`.** Prefer higher-confidence wiki pages for key claims; attribute and hedge anything resting only on `low`/`very-low` pages.
- **Write only to `output/`.** Never edit `raw/`. Never edit `wiki/`, with two named exceptions: the Freshness duty's on-page marks on a stale or contradicted page (Step 2), and the "maintained derivative" line on a source page's `## Related` (Step 5). Outputs are deliverables, not knowledge.
- **British/UK English** and all other CLAUDE.md rules apply.
- **Not logged by default** — a deliverable is not a brain-update (CLAUDE.md §5). Log only if the user
  asks, or if the run also files a wiki page.

## Deliverable graphics (routing rule, moved here from CLAUDE.md §7 on 2026-09-05)
`lieflat-charts` for browser-viewed HTML and interactive charts, dashboards and full-page HTML reports (some templates need CDN network); `scientific-figure-making` (from figures4papers) for publication-grade matplotlib figures for papers, theses and slides (PDF or PNG for LaTeX). Rule of thumb: web-viewed → lieflat-charts; print or venue-bound → scientific-figure-making. Both keep a recorded `auto` ruling in `wiki/developments/capability-register.md`, as legacy rows whose proof is not re-established; under the adopt skill an existing use ruling remains authoritative.
