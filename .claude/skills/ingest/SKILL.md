---
name: ingest
description: >
  Compile inbox files in raw/ into the wiki (source + entity/concept/model/benchmark pages), update
  index + log, then sort the raw file into its category subfolder. Use on /ingest, when files are
  dropped into raw/, or "add this to my wiki / ingest this / file this source / process my inbox".
  Non-.md sources (PDF, PPTX, DOCX, XLSX, image, audio, HTML, CSV, EPUB, YouTube/web URL) are
  converted to Markdown first; runs a cheap de-dup check; picks each source's depth
  (concise/standard/research) after reading it, within the run's authorised range, and records the
  choice with its evidence in the report and log. Scans the raw/ ROOT only (or one given path);
  never edits raw file contents — only relocates them.
user-invocable: true
---

# ingest — compile raw sources into the wiki

You maintain a **persistent, compounding wiki** (see `CLAUDE.md`). `raw/` root is the **inbox**;
`wiki/` is the **compiled layer**. Work in **British/UK English**.

## Trigger logic
1. **`/ingest`** (no arg) → list every file in the **`raw/` root only** (exclude all subfolders;
   they are already processed), then process them at the pacing chosen in **Pacing** below.
2. **`/ingest <path>`** → process just that file (or a YouTube/web URL the user gives you).
3. **Implicit** → user says "add this to my wiki" / "ingest this" / "file this source".

## Pacing: auto (default), one-by-one, batch, one-lane, or parallel
Read the **pacing** from the user's words; **if they don't specify, default to `auto` and decide yourself.**
Do not ask which *pacing* to use unless the choice is genuinely risky. (This is pacing only — **depth**
is a separate axis with its own rules; see Depth. `auto` names a default on both, so never read a
pacing sentence as licence on depth, or a depth rule as licence on pacing.)

**Execution precedence:** a batch compiles in a lane by default; the owner’s word, else the head’s pre-flight judgement, chooses the one-lane or parallel shape. The head may compile a small batch itself where the instrument rule favours it, as for a few short sources that fit its context with room to spare; the pre-flight records that reason, and the owner’s word on a batch’s shape holds over either default. The **Verify step** runs on a batch the head compiles as it does on a lane’s, unless that batch’s pre-flight records why it need not.

For a batch compiled in a lane, the pre-flight records the standing instrument-rule reason that satisfies the `single` regime: (d) a batch longer than the head can afford, or (b) breadth one context cannot hold. The Routing note at Step 3 applies its head-compile rule under `single` to the single-source path; a batch the head compiles takes the precedence above. For a batch in a lane, the owner’s word, else the head’s pre-flight judgement, selects `one-lane` for the whole batch serially where converted bytes fit the source-size bound, or `parallel` for several lanes above that bound or under time pressure.

A two-source batch compiled in a lane under `single` uses `one-lane` where its converted bytes fit the source budget, with its standing instrument-rule reason recorded in the pre-flight; the owner’s word or the head’s pre-flight judgement can select `parallel`. The same batch under `multi` follows the same shape rule.

The batch shape takes precedence over the Routing note’s older per-source `auto` sequence. The head’s retained duties remain as assigned by Routing and the chosen shape: the brief, the verify leg, any merge, sorting and Step 7 work retained by the head, and registries where the ingest exception is not granted.

Compile routing follows the standing instrument-rule reason above. Source size selects the lane
shape; source count does not. The source budget is the size rule's effective packing budget,
min(`PACK`, `CEILING`), stated once in **Parallel mode**, step 1 (Partition). Both shapes keep the
**Verify step**.

- **`auto` (DEFAULT)** — a batch follows **Execution precedence** above; in a lane, choose `one-lane` or `parallel` by the owner’s word, else the head’s pre-flight judgement and the source-size bound above. Use batch review when sources overlap the existing wiki or conflict risk is low; use one-by-one review for diverse or unfamiliar sources, high conflict risk, or a long, dense source. Pause immediately if a genuine knowledge conflict surfaces.
- **`one-by-one`** — user says "one at a time" / "let me review each", or names a single file. It sets the review pace, never the compile shape: a single named file takes the Routing note at Step 3, and two or more sources stay a batch under the rule above, with the run pausing for the owner's review between sources. "One at a time" in a plan the head wrote does not decide the compile shape; a plan that keeps a batch in the head records its reason in the pre-flight, as the rule above sets.

- **`batch`** — user says "all at once" / "batch them" / "do them all"; the batch follows **Execution precedence** above. In a lane, with its standing instrument-rule reason recorded in the pre-flight, choose `one-lane` or `parallel` by the owner’s word, else the source-size bound and the head’s pre-flight judgement.

- **`one-lane`** — one `wiki-compile` lane under `brief-compile` compiles the whole batch serially, writes its source pages and warranted shared pages itself (no claims, no merge, no conflict lane; the head stays thin), and writes its own index lines and log entry under the §2.2 ingest exception. It sorts each raw pair after its own Step 7 self-check, as the routed single-source shape does. One verify lane covers all its pages before the head accepts the run; follow the **Verify step** and the Routing note at Step 3 for the head's retained duties.
- **`parallel [N]`** — user says `--parallel` (optionally a lane count), or the head's pre-flight judgement selects it when converted bytes exceed one lane's source budget or time pressure warrants it. **Owner-go gate, knob-invariant:** parallel compile lanes are never spawned without the owner's explicit go on the echoed spawn record — the `pre-report` knob switches reporting only, never this consent (delegate skill §3 slot 0); a routed single-source lane's go is the `/ingest` invocation itself (Routing note, Step 3; 2026-09-03); under the `light` breadth tier a fan-out needs an explicit owner ask. Parallel mode is available under **both** delegation modes: a batch the head cannot hold in one context is the instrument rule's reason (b), and the verify legs of the lanes it spawns are reason (a) (delegate skill §1). Mechanics: **Parallel mode** below.

### Token-efficiency rules (especially in batch — avoid redundant repetition)
- Read each source **once**; never re-read the whole wiki per file.
- Collect entities/concepts across **all** batched sources first, **dedupe**, then create/update each
  shared page **once** — not once per source.
- Update `index.md` and `log.md` **once** at the end of the batch (a single batch `log` entry is fine).
- Skip irrelevant/off-topic source material instead of compiling noise. Don't re-read pages you just wrote.

## Depth (chosen per source AFTER the read, recorded always)
Depth sets how deep/academic the output is (orthogonal to Pacing). **Decide each source's depth once you
have read it — never from its filename, folder, length or markers**, none of which separate a
research-worthy source from an ordinary one in practice.

### The authorised range (consent)
Every run has a range of depths you may use. **Default: all three.** The user narrows it
(`--depth concise,standard`, "no research this time") or pins one (`--research` / `--standard` /
`--concise` — unchanged, each forces that depth for the whole run). **Never choose outside the range.**
If a source genuinely needs a depth the range excludes, **stop and ask** — that is the one surviving
pause, and it should fire rarely. Echo the resolved range in words before compiling when the user gave
anything other than the default, and resolve an ambiguous phrase to the **narrower** reading.

### The decision (three triggers, judged on the source you just read)
- **T1 · Reuse** — does it carry original figures, a reimplementable method, or wording where a
  paraphrase would falsify the claim?
- **T2 · Proximity** — does it bear on a topic named in `wiki/user/`, or on an open question already in
  the wiki (a `## Conflicts / Open Questions` block, a `flagged:` page)? *Fallback*: if
  `wiki/user/` is absent, empty, **or outside the reader's scoped reading list** (a delegated compile
  lane; №103), read T2 as "a topic with ≥3 source pages in `index.md`"; if the wiki
  is too small for even that, say so once and work in concise/standard only.
- **T3 · Novelty** — does it add anything not already on an existing page?

**`research` = T1 ∧ T2 · `concise` = ¬T3 · `standard` = everything else.**

**Overrides (fire regardless of the triggers):**
- A source in `raw/9-originals/` (the owner's own work) is **never below standard**.
- A source that **corrects an existing wiki page is always research** — a correction has to be exact.
- A source whose Step 0 check found **collapsed word boundaries can never be research** (verbatim
  quoting is impossible on it): compile at standard and say so in the report. The same holds for a
  conversion the Step 0 scorer reads `suspect` in scope `pdf` (3c): the `flagged:` line it puts on the source
  page is the record, and the depth line names that verdict as the reason. 3b and 3c never contradict —
  either one raising the flag is enough, and a 3c `clean` never clears a 3b `COLLAPSED`.

**Name the evidence, or drop a rung.** Every depth you record carries a locator — `research — T1 (Table 3
ablation) · T2 (calibration, About Me)`, `concise — ¬T3 (link post, all three tools already have pages)`.
A trigger letter with empty parentheses is a defect, not a record. **If you cannot name the evidence,
take the lower rung** (the §4.6 tie-goes-lower principle, applied to depth).

- **standard (the usual outcome)** — articles, blogs, posts, docs. Run Steps 2–4 as written.
- **concise** — thin or fully-redundant sources (brief tweet, link dump, thin page): concise
  summary, create pages only for genuinely new entities/concepts, minimal bullets.
- **research** — primary material the owner will need to reuse exactly. At research depth:
  - Preserve exact figures (no rounding); quote critical claims verbatim with §/page refs; mark
    anything not directly stated as `unverified`; never infer numbers.
  - **Quote discipline, all depths:** short critical quotes as above stay mandatory; *long-form
    block quotes* stay in the raw file — link, never transplant — so compiled pages stay quotable
    from their source (a refusal while reading follows CLAUDE.md §11).
  - **Computed numbers and quotation starts, all depths (2026-09-10):** a number you computed over a set
    (files, hits, list lengths) is copied from the command's printed output in this pass, never recalled,
    and re-run once before the report, the sentence corrected if it moved; a quotation checked back against
    the raw is checked from its opening quote mark, so a splice at the start cannot pass.
  - Replace the Step 3 source page with the **literature-note template** below.
  - Add academic frontmatter (`authors`, `year`, `venue`, `doi`, `depth: research`).
  - Cross-check findings against existing pages and flag confirmations/contradictions explicitly.

**Table quotations, all depths:** A cell from a column-collapsed table is quoted only with its row and column labels verified in the raw, never with a superlative or a row label the table does not print. If the raw does not let you verify the labels, report the cell as unverifiable and omit the attributed figure. A word or unit absent from a collapsed cell is never supplied: the cell is quoted as printed and the gap marked `unverified`.

**Record it, always.** Every source page carries `depth: concise|standard|research` (Step 3); every run
reports each source's depth + locator (Step 8) and logs the tally (Step 5). *Never silent* is now
**never unrecorded**: consent lives in the range, notice lives in the record. Do **not** backfill `depth:`
onto pages compiled before this contract — an absent value means "unknown", and inventing one would be
fabrication.

### Research-depth source page (replaces the Step 3 template)
Schema (CLAUDE.md §4.3, the research-depth clause of 2026-09-14): these sections stand in place of
`## Summary` and `## Key Takeaways`; `## Related` stays mandatory, and the lint required-sections check
reads `depth:` before judging the page.
```markdown
---
title: "Paper: <Title>"
type: source
depth: research
confidence: high   # authoritative if peer-reviewed/published; see CLAUDE.md §4.6
audited: <YYYY-MM-DD>   # today — assignment with the source in context is the check (§4.6)
tags: [paper, <field>]
authors: [<First Author>, <…>]
year: <YYYY>
venue: "<journal / conference>"
doi: "<DOI or stable URL>"
sources: [raw/2-papers/<file>.pdf, raw/2-papers/<file>.md]   # original + converted
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

## Citation
<full reference string>

## Research Question
## Methodology
## Key Findings
- <finding with exact figures, e.g. "+12.3 BLEU, p<0.01">
## Data / Setup
## Contributions
## Limitations & Threats to Validity
## Relation to Wiki
- Confirms [[…]]; contradicts [[…]] → flag a `## Conflicts / Open Questions` block on that page
## Key Quotes
> "<verbatim>" (§/p.)
## Open Questions / Follow-ups
## Related
- [[…]]
```

**Genre note — research depth is not paper-only.** T1 ∧ T2 fire on any primary source whose exact
wording matters (regulations, institutional handbooks, contracts, policy documents). For those, keep
the frontmatter fields that exist (no DOI → omit it; `venue:` takes the issuing body + version) and
replace the paper-shaped middle sections (Research Question … Limitations) with genre-fitting
equivalents (e.g. Scope & Applicability · Requirements & Thresholds · Deadlines & Milestones ·
Governance). The obligations never flex — exact figures, verbatim quotes with §/page refs,
`## Relation to Wiki`, `## Related` — and the substitution is declared on the page and in the run
report. A regulation or an institutional handbook is the typical case: its exact thresholds and
term-relative deadlines are precisely what a paraphrase would falsify.

## Run ledger (persistence — every run, serial or parallel)

Every ingest run appends an event log under the agent home `~/.llm-wiki/`:
`~/.llm-wiki/ingest-runs/run-<YYYYMMDD-HHMM-id>.jsonl` — one JSON
event per line via shell append (`printf '%s\n' '<json>' >> <ledger>`), the same primitive that makes
`log.md` race-safe. **Never read-modify-write it**; resume state is a fold over events.
Appends stay a shell primitive, with no helper script (§12). The mechanical check is `ledger_check.py` (`python3 .claude/skills/ingest/ledger_check.py <ledger or run id> [--brief LANE=PATH ...]`): the head runs it at the merge and close step, before `run_close`, and an offence or exit 2 is settled before the run closes.

**Fold with a parser; a key-pattern grep is a locator, never a verdict.** Writers disagree on key
spacing (`json.dumps` writes `"lane": "LB"`, a `printf` event `"lane":"LB"`), so every count, census
or resume fold reads the lines through `python3 -c` or `jq`. A grep locates a line to look at; it
never settles a question. Parse records before counting fields or using absence as evidence.

**Every event's `ts` is the shell clock at write time** — `$(date +%FT%R%z)`, one offset format,
head-written events included — never typed, remembered or derived from context. A lane that types
its own clock can stamp hours fast, and the resume pre-flight below reads a future-dated stamp as
perpetually live, so a fabricated clock disables the liveness check it feeds.

**Events** (extra fields are free): `run_open` (run id · pacing · authorised depth range · inbox
listing as `inbox: [{file, sha256 prefix}]`) · `lane_open` / `lane_close` (lane id · definition ·
model · effort · `role: compile|verify|conflict` on `lane_open`) · per-source `checkpoint` (`source` + `stage` + stage fields; `claims_emitted` carries every claim object, its `diff`, `base` and `diff_hash` in the `claims` list, never a count; an optional count goes under `claims_count`) · `conflict` (page ·
both statements' locators · disposition) · `merge_open` (plan artefact named, parallel mode) · `merged` (per merge target, parallel
mode) · `verify` (Verify step: compile lane id · verifier id · definition · model · effort · all eight names on the `scores:` line in parallel mode · verdict · fixes · distinct source-qualified `quarantined` claim objects) ·
`preflight` (parallel mode: the head's append before the owner go, at the ledger path copied from a
brief — briefs · failures · controls; Parallel mode step 1) · `run_close` (tallies mirroring the Step 5 log entry). **Serial runs use lane id `head`** — one schema serves both.

**Checkpoint stages, mapped to the pipeline** (append as each source passes the step):
`deduped` (pre-flight) → `converted` (Step 0; skipped for native `.md`) → `read` (Step 1) →
`compiled` (Steps 2–4: pages created/updated · depth + locator · confidence tiers) →
`claims_emitted` (parallel lanes only) → `registered` (Step 5) → `sort_planned` (Step 6, before any move) → `sorted` (Step 6).

**The ledger is evidence, never authority — disk is truth.** Resume re-verifies every ledger claim
against disk before acting — content, not existence (torn-write check: frontmatter closes,
`## Related` present). A 0-hit disk probe shortly after a crash gets one retry before it is believed
(phantom-zero rule). Ledger-vs-disk mismatch → reconcile from disk and append a correction event;
ledger missing mid-run → fall back to the raw-root convention (root = unprocessed) and say so. A
malformed line never blocks a fold: skip it and report it.

**Resume pre-flight (start of every run, before the inbox scan):** one cheap check —
`grep -L run_close ~/.llm-wiki/ingest-runs/run-*.jsonl 2>&1` (dir absent / no files → proceed fresh,
silently). Any open run → report it (each source's last checkpoint, plus the **age of the last
event**) and offer resume before scanning the inbox fresh. Last event under **~60 minutes** old →
flag "possibly live in another session" and let the owner decide (concurrent sessions are routine
against this vault; resuming a live run would create a dual-writer race). The 60-minute line is
set by judgement, unmeasured for a new installation.
**A `ts` later than the shell clock is invalid — never "live".** A typed clock can run hours fast,
and a future stamp sits under the 60-minute line for ever, disabling the check it feeds. So
age the latest event against the wall clock, comparing stamps as parsed instants (a string `max` ranks
`+0100` above `+0000` for the same clock reading), and where the latest `ts` is later than now, or any
stamp is unparseable or carries no UTC offset, fall back to the ledger file's mtime and name the source of
the age in the report:
```bash
python3 -c "
import datetime as dt, json, os, sys
p=sys.argv[1]; now=dt.datetime.now(dt.timezone.utc); t=None; ts=''; bad_ts=''; skipped=0
for line in open(p):
    try: s=json.loads(line).get('ts','') or ''
    except Exception: skipped += line.strip() != ''; continue
    try: c=dt.datetime.fromisoformat(s)
    except ValueError: c=None
    if c is None or c.tzinfo is None: bad_ts = bad_ts or (s or 'absent'); continue
    if t is None or c > t: t, ts = c, s
bad = t is None or t > now or bad_ts != ''
age=now.timestamp() - (os.path.getmtime(p) if bad else t.timestamp())
print(('mtime (ts invalid: ' + (bad_ts or ts or 'absent') + ')') if bad else ('ts ' + ts),
      round(age/60), 'min old ·', skipped, 'malformed line(s) skipped')" ~/.llm-wiki/ingest-runs/<run>.jsonl
```
The mtime is a fallback, not a clock: a ledger synced in from another machine can carry a preserved
older stamp, so the age it yields may overstate how long the run has been quiet. Report a rejected
stamp as "ledger clock rejected, mtime age <n> min" and let the owner decide, exactly as with a run
inside the 60-minute window.

**Completion gating (ungated mid-pipeline duties are easily skipped — so gate, don't
trust habit):** the Step 8 report carries one mandatory line — `Run: <id> · <n> ledger events ·
closed` — and the Step 5 log entry names the run id. A silent zero surfaces in the reply the
completion gate already requires; where the `ingest-check` kit is on (`bash setup.sh --enable
ingest-check`), the warn-only Stop hook (`.claude/hooks/ingest-ledger-check.sh`) additionally
flags stale open runs at turn end.

## Parallel mode (compile lanes + entity merge)

A batch compiled in a lane follows the precedence in **Pacing**, which holds its pre-flight reason and its choice of `one-lane` or `parallel`. The chosen batch shape takes precedence over the older per-source `auto` sequence. The head’s retained brief, verification, merge, sorting, Step 7 and registry duties remain as assigned by Routing and the chosen shape, including registries where the ingest exception is not granted. Parallel adds a merge stage; both shapes keep the **Verify step**. Run parallel through the delegate skill (routing, spawn slots, `brief-compile` template).

1. **Partition (script; planner lane where a source read is needed, on the head's recorded judgement — its output is a proposal, §2.2).** Run `python3 .claude/skills/ingest/partition.py --inbox <raw root>` or `--ledger <run ledger>`, optionally with `--lanes <N>` or `--max-bytes <B>`. Every direct Markdown file counts, native Markdown included; a same-stem original is not counted twice. Related sources can be co-assigned with `--group <file>` (one stem per line, blank lines between groups); a group is indivisible. **The size rule** (stated here once; every other mention points here). A unit is one source or one group, sized in converted Markdown bytes. The packing budget `PACK` is `--max-bytes` (default 250000 bytes, set by judgement, unmeasured: small sources share one helper's fixed cost, the lane core, its slices and the brief). The ceiling `CEILING`, the most one helper may hold, is share × window × bytes per token, rounded down to whole bytes: `--ceiling-share` (default 0.2, set by judgement, unmeasured: a helper also holds the lane core, its slices, every page it writes and its checks, so it keeps a reserve as the context belt does) × `--window-tokens` (the compile model's context window; default 1000000, the figure the harness reports for opus 5.5; name the window of any other compile model) × 4 bytes per token (set by judgement, unmeasured), which is 800000 bytes by default; the plan header prints both with the derivation. No helper holds more than `CEILING`, so the effective budget is min(`PACK`, `CEILING`): units at or below it share helpers, largest first, each into the first helper it fits; a unit above it and at or below `CEILING` gets a helper of its own, never refused and never split. `--lanes <N>` keeps an exact count: units above the effective budget take a helper each and the rest go largest first to the least-loaded remaining helper; the call exits 2 only when a helper would exceed the effective budget, its message giving a lower bound and first fit's count as an upper bound, never as the needed count. **Verified, never assumed:** the script asserts that every inbox source appears exactly once, in one lane or one reported line; a broken premise exits 2 with `PROBE FAILED`. Exit 0 is a full plan; exit 3 is a plan with one or more reported lines, every other unit still planned. **A `split:` line** names one source above `CEILING`; this run does not compile it. The head leaves it in the inbox and names it in the run's report and log entry with the reason (the source, its bytes and the ceiling). It is compiled only once a parts procedure exists: chapter parts kept outside `raw/`, which takes no new file beyond a conversion (CLAUDE.md §2), each part with a verification path of its own and the parent's coverage checked; that procedure is a follow-up design (known-issues, the entry on a source above the compile ceiling). **A `group-over-ceiling:` line** names every member of a group above `CEILING` and the group's total; partition.py never splits a group. The head resolves it per run: give the group a larger-window model (re-run partition.py on the group's members alone, an inbox or ledger holding only them, with that model's `--window-tokens`, then check that the combined plan holds every source exactly once) or release the grouping for that run; either way the reason goes in the run's log entry. Before any spawn the head reviews every brief, including pairwise-empty source/page file whitelists. **Then the brief check, before the owner-go echo** (design extension
   2026-09-13, part 4; a head-side rewrite can mangle the ledger path in every compile brief, and a
   lane given a mangled path appends nothing): create each lane's scratch directories, persist each headless
   lane's `lane.py spawn … --expect-usd <usd> --dry-run` stdout, and run `python3 .claude/skills/ingest/brief_preflight.py
   --ledger <run ledger> --dry-run <lane>=<that file> … --in-session <lane> … <every filled compile and
   verify brief>`. It fails a brief on (a) a path token whose parent directory is missing or that holds
   an unfilled `{{…}}` or `<…>` slot, (b) a ledger path that differs between briefs or from the run's,
   (c) no `preflight` event after `run_open` at the brief's literal ledger path, (d) a fence answer
   other than allow for a headless lane's own append there (a verify brief is exempt: the head appends
   the verifier's `lane_open` and `lane_close`, Verify step item 5), (e) a reading list that names an index
   `## ` section or carries one whole; exit 2 is a broken probe, never a pass. The head proves (c) with
   its own append, made only once a run shows (a), (b), (d) and (e) passing (the check's `NEXT:` line;
   `>>` creates a file wherever its parent exists, so an earlier append could land in another run's
   ledger): copy the path from a brief's text, append
   `printf '{"ts":"%s","event":"preflight","run":"<run>","lane":"head","briefs":<n>,"failures":<n>,"controls":"ok"}\n' "$(date +%FT%R%z)" >> <that path>`
   (`briefs` and `failures` copied from that run's `summary:` line), then run the check again: exit 0
   is the only pass, and the owner-go echo carries its `summary:` line.
2. **Owner go on the echoed spawn record** — this skill's own approval gate, whatever `pre-report`
   says (a reporting knob, never a consent switch).
3. **Lane shape.** `wiki-compile` under `brief-compile` + **ledger appends and anchored claim diffs**
   (`lane_open` · per-source checkpoints · `lane_close`) and **claims instead of shared-page writes**.
   Per-lane whitelist: its raw pairs (conversion writes — disjoint files), its source pages (sole
   writer), the run ledger (append-only), and, under the §2.2 ingest exception, its own
   `index.md` source-heading lines by **anchored per-heading `Edit`** and its own `log.md`
   entry by **shell append** (`vault-writes.py log-append`) — never an `Edit` on the log, which the harness
   would make the lane read whole. Grep-verify both back and show the grep.
   Also grant the lane's own `<run>-diffs/<lane>/` directory beside the ledger for its proposed unified diffs. A `lane_open` records `role: compile`; verify and conflict lanes record their corresponding role. The ledger lane id must equal the spawn record's lane id: the meter joins its per-agent rows on that id before grouping by role. This is the baseline attribution change; no historical re-meter is built here. Everything else is propose-don't-write.
4. **Lanes never write shared-type pages** (entity/concept/model/benchmark — the true race surface).
   Each lane emits **claims** in its report AND **in full under `claims` inside the `claims_emitted` checkpoint** —
   `claims` is the list of claim objects, never a count; an optional count goes under `claims_count`. The event carries complete objects, never just their names: lane reports die with
   their sessions, so a name-only mirror leaves the run unresumable if the head dies before merge. Claim schema:
   `{name · type · kind: create|update · target · facts[] with per-fact source locators · links[] · appears_in[] · confidence · from: source-page · source: raw identity · diff: absolute path · base: sha256 prefix · diff_hash: sha256 prefix}`. Canonicalise against index names and page aliases; mark shaky facts `unverified`. Each update diff is against the exact bytes read, with `base` the first 16 sha256 hex digits, the `source_hash` length used by de-dup. The planner keeps that validated hash as the expected base; a later disk read cannot replace it, and drift during planning is manual or a probe failure. A create diff uses `/dev/null` as its old header and carries the schema's frontmatter and sections, including `aliases:` with acronym and expansion wherever the source gives both. The checkpoint's `claims` list mirrors the complete objects and the diff's own hash. Reports remain readable prose; the planner consumes the parsed `claims` objects. Before `registered` or `lane_close`, the lane runs compile-core §5's mandatory post-checkpoint assertion and records its `claims-shape:` and `controls:` lines in its final report under `## Controls`; the verifier checks that evidence. The lane also runs §5's claims-locator check (`raw_slices.py --check-claims`) on each checkpoint before appending it and over the ledger after, so every fact's `locator` resolves through the verify leg's slicer and every claim is attributed to its own source page and raw, and records beside them, for each raw, the check's `locators:` line, which names the lane, the raw and its source page.
5. **Lanes do NOT sort — they end at `registered`.** Sorting before merge would mark sources processed
   while their entity claims were still unapplied, silently breaking root-state truth (the §2
   fallback invariant). The head sorts at merge-close.
6. **Plan and anchored apply (head, after each lane's latest close and verify).** Run `python3 .claude/skills/ingest/merge_plan.py --vault <vault> --ledger <run ledger> --lanes <comma-separated compile lane ids>`; repeat `--ledger` for separate claims JSONL files. The first ledger binds the run, and runless events inherit only their own file's `run_open`. Separate-file claims require timestamps proving they preceded the close and verify. Persist the plan and append `merge_open` naming it BEFORE a page write. An empty or unparseable ledger, a latest opening or latest close without subsequent verification, malformed claim containers, foreign or premature evidence, missing score names, or a quarantine count without distinct objects exits 2. An unsettled malformed line also exits 2; only an explicit `--allow-malformed <exact file>:<line>` settles that real file and line. A zero-target plan carries its same-run control.

   The planner joins normalised targets and aliases from existing pages and create diffs. Quarantine removes individual objects first. The page guard is an exception applied before ordinary classification: a guarded target is `manual`; otherwise `conflict` outranks `manual`, which outranks `tier-raised`, which outranks `apply-union`, which outranks `apply`. More than one claiming lane is a conflict except when every member adds only list items (lines beginning `- `) under `## Appears in`, `## Related`, `## Key Points` or `## Conflicts / Open Questions`, touching the frontmatter at most by re-dating `updated:`/`audited:` or by appending to a single-line `sources:`/`aliases:` list (widened 2026-09-21: run-20260921-rlcd sent 35 additive targets to conflict under the earlier link-only rule, `known-issues` 16:0x). Those additions form one `apply-union` diff against the current page: each new item appended after the last item of the list its member put it in (or where its member put it, when it starts a list of its own) in member order, complete list items de-duplicated after whitespace collapse and trailing-space trimming only when all continuation lines and their section, parser blocks and neighbouring base/addition context agree, the stamps folded to one line each at the latest date, each list merged as the page's items plus the appends. Punctuation, case and target/gloss boundaries are preserved, so different glosses for one target both survive; bullets from different lanes sit side by side, so a near duplicate is the head's call at the composed-diff read, never the planner's. The composed-page check covers every member addition, including each de-duplicated occurrence; removal requires a verified complete item in the same context. A removed or edited body line, prose outside a list item, a heading, or any other frontmatter change stays conflict. Missing or unusable member diffs stay conflict; an otherwise eligible union whose base/context, heading or list re-base fails is manual. Missing diffs, moved bases and existing creates from one lane are manual. A confidence lift always requires a full-page head read even when its disposition is conflict or manual. A union-eligible overlap whose claim objects declare a lift is tier-raised first: the planner still composes its union diff, marked `after the full-page read`, and the head applies it only after that read, since the union never lifts a tier; a lift written into a member diff's `confidence:` line keeps the target in conflict after the read. A single-lane tier-raised target follows its next class after the read (otherwise apply or manual). Every block the rule names is markdown-it-py's CommonMark reading of the page body (IDEAS №172; the frontmatter stays the planner's own parse, and a missing parser exits 2 with `PROBE FAILED: markdown-it-py not importable`, never falling back to line scanning): an addition counts only when the parser reads it as a one-line top-level list item holding a block of its own, in a section (from its ATX or Setext heading to the next heading of the same or higher level, the innermost deciding) headed by one of those four headings, and, like the page guard and before ordinary classification, a multi-lane target is `manual`, with the construct and a member or page line, when an addition lands inside a fence, an indented code block or an HTML block, takes an existing line into its item (a nested child, a continuation or a lazy line), or changes an existing line's blocks (a Setext underline, a swallowing fence), or when the parsed composed page moves an addition or an existing line out of the list, blocks or section its member's proposal gave it. The page guard remains only for what CommonMark cannot place: an Obsidian comment marker (%% anywhere) or a maths block marker ($$ anywhere) in the current body or a member's added body lines makes a multi-lane target `manual`, with the frontmatter excluded.

   The planner reads existing and proposed aliases with the same frontmatter list parser; an `aliases:` line inside a page's body (a fenced example) adds none. Both metadata and body readers close frontmatter only at the first column-zero `---` or `...` line, with trailing spaces or tabs allowed; an unclosed block exits 2. Block sequences continue across blank and comment lines to the next lower-indentation key or frontmatter close. Single-line quoted items and folded or literal scalars retain their YAML values, including indentation, folding and chomping. An unimplemented form records the page's alias identity as `UNCERTAIN`, naming the form and line; every multi-lane target touching that page is `manual`, with a `reason:` and no union artefact or commands. Alias appends also become manual where an uncertain catalogue page prevents the collision check; body-only unions on unrelated known pages retain their outcome. The same reader and local uncertainty refusal serve `sources:`. A held union, and a lift a resolved diff introduces, print no apply command for that target: the named second step is `merge_plan.py --vault <vault> --resolved <artefact> --after-read <base>:<diff_hash>` after the full-page read, and that acknowledgement binds the read to the page bytes and the exact held artefact, so a substituted member diff, a changed artefact or a moved base is refused. Every resolution in a batch is validated and re-checked before any apply command prints (the builder's fixes of 2026-09-21, critic rounds 1 and 2).

   Name `--union-dir <existing run scratch directory>` when planning unions. This is the planner's sole write exception: it creates union diff artefacts outside the vault, reuses identical bytes and refuses to overwrite different bytes. Missing scratch is a broken premise (exit 2), never an apply. Read the composed diff, then use the same dry-run, immediate base re-check, patch flags and per-target event as for apply. No union is emitted while the ledger evidence is incomplete.

   Read the create list's names and aliases and move any semantic duplicate into conflict. Spawn one `wiki-compile` conflict lane only if conflicts remain, with `brief-merge-conflict.md`, `role: conflict`, all competing claims/diffs and each target. Manual targets join it when it exists; otherwise resolve each by an anchor read. It returns resolved diffs, the canonical-name map and link diffs for losing source-page variants. Read every resolved diff and run `merge_plan.py --vault <vault> --resolved <diff>`: an introduced confidence lift, quoted or unquoted, requires a whole-page read. Resolved diffs are head-reviewed; they receive no new verify score.

   For each apply target use the printed command with `patch -F0 -N --no-backup-if-mismatch -r <scratch reject file> --dry-run <explicit target> <diff>`, then re-check the base hash immediately before the same command without `--dry-run`. A create re-check proves absence. Zero fuzz derives from exact-context anchoring; `-N` on an already-applied patch is a failed replay probe. Rejects stay in run scratch, with no backup or reject beside a page. Append `merged` per target only after its added lines are verified on disk. On resume both disk content and that event are required. The head reconciles source links, indexes each accepted page, sorts fully merged raw pairs by Step 6's checked procedure, appending each `sorted` checkpoint only after its `post` check exits 0, and appends its batch log entry. Run log composition remains the lane entries plus one head batch entry.
7. **Confidence at merge (§4.6):** the lane that read the source assigns the tier; merge *combines* —
   corroboration across claims may lift a compiled page toward its `high` cap, never above — and never
   re-grades a reading lane's tier without reading the source. The head's §4.6 spot-check rides the
   merge pass; `audited:` stamps at merge write.
8. **Step 7 splits.** A claims-mode lane checks: every link resolves to a real page **or to a target
   in my emitted claims**. The head runs the Verify step (below) over each lane's pages and claims
   BEFORE merge, including every claim diff's added lines as page text under fabrication, then the full Step 7 over the batch post-merge and `ledger_check.py` over the run ledger (Run ledger) — the final gates before `run_close`.
   **Quarantine is per claim, not per lane.** A claim's facts carry their own locators, so the verify
   leg's `claims` dimension counts the claim objects whose facts the flagged sentence, paragraph or
   table feeds and names them; the head quarantines exactly those and merges the lane's remaining
   claims. Name each quarantined object by `claim_id` from the plan or by `name` plus `lane` and `source` or `from`; an ambiguous name or the same object named twice exits 2, including in a `--quarantine` JSON list. A numeric `claims` score must equal the number of distinct objects named. A refuted fact whose object still applies (its diff carries no refuted text) is not a quarantine: the verify event lists it under `flagged_facts` (name · lane · fact · fix), counts the refuted sentence under `fab`, and leaves `claims` at the objects dropped; a lane-report evidence failure (a claims-shape line the exact-line grep rejects) goes into the verifier's findings and the event's `shape: fail` field, never into `claims`, since the planner validates every object itself (both shapes exited the planner on 2026-09-21). One case still takes the whole set: a leg that could not run the dimension (`claims -`) — fail closed. Derivation:
   a per-lane quarantine discards every usable claim object a lane made over one fabricated
   sentence, and the merge then pays to re-derive them.
9. **Conflicts under parallelism.** A lane never pauses the batch: it keeps both statements in its
   claim (§4.4) and appends a `conflict` event; the head surfaces every conflict in the batch report,
   and high-stakes ones pause the **merge** — the single point where a pause still has leverage.

## Verify step (every compile a lane did — the routed single-source path and each parallel lane's pages — and a batch the head compiled, unless that batch's pre-flight records why it need not)

Runs head-side after the lane closes, or after the head's own compile of a batch, and before the head accepts the run (Step 7 and the close-out).
Design: the routing design page (see **Vault records** at the end of this skill), protocol items
3, 4, 5, 6 and 9 (item 4's single-source form and item 3's mechanism delta are dated status facts
there). **Routing (shipped
2026-09-03, critic C15 folded; mode-gated 2026-09-04):** the scripts run in the head's shell (M0), the
scoring runs in a `verifier` lane at the class's per-call pick (delegate skill §2; tier verdicts are
judgement claims), the verdict stays with the head (M2). The lane
is the default under the `multi` regime; under `single` the head scores in-session **unless** an
instrument-rule reason holds — and one always does when the compile itself was routed, since a verify
leg on a routed step is reason (a) (delegate skill §1). So a lane-compiled source never loses its
independent leg, in either mode; a head-compiled single source gets one only where the head proposes it, and a head-compiled batch gets one under **Execution precedence**, its pages taken as the lane's would be.

1. **Output set by manifest, never by report.** Before the run's first spawn, `touch` a marker file
   beside the run ledger (`~/.llm-wiki/ingest-runs/<run>.marker`) — once per run, never re-touched on a
   resume; after the lane closes, `find <vault>/wiki -name '*.md' -newer <marker>` (absolute path) is the
   candidate set, **intersected with the lane's file whitelist from its brief**: a candidate off the
   whitelist is reported as an "unexpected writer" (a concurrent session, a sync, a lane off its
   contract) and is never scored or rewritten. Controls: the source page the lane reports must be in
   the set — an empty set against a reported page is a broken probe, not a clean one; where the lane's
   durable transcript exists, its Write/Edit/redirect paths (the parity store's scope parser lists
   them) must equal the set. Parallel mode takes the set per lane, before merge.
2. **M0 pre-checks, head shell, stdout only — persisted, then named in the brief.** Run `python3
   .claude/skills/lint/tier-cap-check.py --format json` (vault-wide — a clean vault implies a clean
   set); `python3 .claude/skills/lint/anomaly-lister.py --pages <set>` (the page-visible list the
   lane's `## Anomalies` is checked against); `python3 .claude/skills/lint/check-links.py` (dead
   links). Write all three, each under a heading naming its script, to
   `~/.llm-wiki/ingest-runs/<run>-m0-<lane>.txt` beside the run ledger, and let the brief name that
   path instead of pasting the lines: a lane cannot treat brief text as evidence, so it scores a pasted
   line UNVERIFIABLE (`known-issues`, 2026-09-04). The path joins the lane's read grants. A breach here is a miss before the verifier runs.
   **Raw slices (parallel mode).** Run `python3 .claude/skills/ingest/raw_slices.py --raw <converted raw> --page <source page> --lane <compile lane> --ledger <run ledger>` for each source; persist the complete outputs beside the M0 file as `<run>-slices-<lane>.txt` and grant that file for read. The skeleton is structural, independent of the claims. Missing claims, conversion suspicion or hash drift take the whole-read fallback. Conversion pairs count as one source identity before ambiguity is checked; distinct source directories still compete. An empty claim object exits 2; a partial claim with missing source or locator evidence counts unresolved and takes the whole-read fallback. An incomplete output (a missing numbered line, footer or closing `controls:` line) also takes the whole raw. Exit 2 is a broken probe and cannot establish coverage.
3. **Verifier lane** from `.claude/skills/delegate/templates/brief-ingest-verify.md`, which also
   receives the compile brief's CONTEXT NOTES verbatim, the M0 file's path and the raw slices file, and (parallel mode) the lane's emitted claims: claim list and warranted set from each raw's skeleton before opening outputs, then the counts —
   fabrication · coverage · tier · structure · integration · language · anomalies, plus
   `claims` in parallel mode (the claim objects whose facts a flagged sentence feeds, the quarantine
   unit of step 8 above) — evidence per non-zero, both controls, and the last line `scores: …`
   (`claims` is appended to that line in parallel mode only). Group compile lanes per verifier so that the raw bytes one verifier may need to read whole (the plan's bytes for every compile lane it serves) stay at or below that verifier model's `CEILING` (the size rule in **Parallel mode**, step 1, at the verifier model's window), every compile still checked; a disputed call re-runs that lane alone. Run the full protocol per compile lane in order, with its own pages, claim objects, slices file, M0 file and `## Controls`; the head prepares raw slices once per compile lane's set and names every file. Parallel score lines are prefixed by the compile lane id, keeping the exact seven names plus `claims`: `<lane> scores: fab <n> cov <n> tier <n> struct <n> integ <n> lang <n> anom <n> claims <n|->`. The lane's evidence decides. Each unsupported fabrication candidate is confirmed on its source's whole raw before it counts; that source's remaining checks then use the whole raw. Both controls use the whole raw. Controls carry `raw read: <source> · slices <bytes> of <bytes> · full no|yes (<reason>)` per source.

   **Shadow coverage measurement.** The designated measurement run gets one independent whole-raw shadow over the compile lane with the most sources, whether or not any call is disputed (one leg and the selection are set by judgement, unmeasured). Trace every item the shadow finds that the slice leg lacks with `raw_slices.py --trace <persisted slices> --item <absolute raw path>:<first>-<last>`. Full source identities remain distinct; an ambiguous source or incomplete output exits 2. An item outside or crossing the slices is `LOSS` (exit 1); an item wholly inside them, or in a whole-read source, is `VARIANCE` (exit 0). Any slicing loss fails coverage and returns every verify leg to whole-raw reads until the prefill changes; lane variance is recorded. Meter the shadow separately from cost per source. Coverage reading (i), (ii), (iv) and (v) is checked: one verify event per compile lane, all eight score names with a numeric claims, whole-raw confirmation for every counted fabrication, and this shadow.
4. **Verdict (head, M2).** Fabrication 0 is required. A fabrication reverts that compile to the head for the run: the head corrects
   or rewrites the pages itself, appends a `known-issues` entry (`vault-writes.py register add`, its
   `--why-not-fixed-now` naming what blocks the fix), and the step's next use needs a brief
   or rubric change first (protocol item 1's retry rule); in parallel mode the `claims` count says
   which of that lane's claim objects the merge must drop (step 8) rather than the whole set. Every
   other non-zero item the head settles from the cited evidence: a coverage, structure or language miss is fixed on the page; an integration
   miss on both pages; a tier dispute — and every tier the lane raised above an existing page's badge —
   is read in full by the head (§4.6: delegation never raises a tier unread); an anomaly the lane
   omitted is judged and, where real, written as a §4.4 block. **Head slice (protocol item 4):**
   whatever the scores, the head reads the source page and up to two more set pages in full against
   the raw (the larger of three items or ten per cent); the per-run empirical re-compile is withdrawn
   for single-source compiles (routing design page, dated status) — every fifth routed run the head also
   compiles the source in a fixture and diffs. The head never edits a lane's page on a verdict alone —
   it reads the cited line first.
5. **Record.** One `verify` ledger event per compile lane scored (compile lane id · verifier id · definition · model · effort · that lane's complete `scores:` line · verdict · fixes applied · distinct quarantined claim objects), appended with a shell clock. Never replace these with one aggregate event for the verifier. The head also appends the verifier's `lane_open` (`role: verify`) and `lane_close`, each with the verifier's spawn-record lane id and `"written_by": "head"`, with a shell clock like every event: the verifier definition forbids the lane's own ledger append, so a verify brief grants none and `brief_preflight.py` exempts verify briefs from its check (d). The spawn record carries the
   full meter; **a routed-run register row on the routing design page every run** (misses, reverts, fable
   share). Then Step 7 runs head-side over the set (its controls are the head's, not the lane's); the
   lane's `audited:` stamps stand, with the mechanism (lane check · verify leg · head slice) named in
   the head's close-out log entry (protocol item 9) — always written for a routed run beside the lane's
   own entry, carrying the verdict line, the `fable share:` meter line (protocol item 8;
   `fable-share.py`) and wikilinks to the network pages the head accepted (the lane's entry names them
   in code font); the Step 8 report carries the `scores:` line and the verdict beside the depth and
   confidence lines.

## Pipeline (per source)

### Pre-flight — De-dup: have I ingested this already? (one cheap shell call)
Step 6 (move-to-subfolder) is the **primary** guard: a root file is unprocessed by construction and
archived files are never re-scanned. The pre-flight only catches a doc that was **re-added**
(re-clipped, copied, or renamed). **Keep it minimal-token**: run it as ONE combined command that prints
*only* a match — so it costs ~nothing when there's no duplicate, and **its output does not grow with
wiki size** (grep for *this* file's hash, never dump all hashes; never read page contents):

```bash
f="<filename>"; u="<source: URL, or empty>"
{ find raw -mindepth 2 -name "$f"
  h=$(shasum -a 256 "raw/$f" | cut -c1-16); [ -n "$h" ] && grep -rlF "$h" wiki/sources/
  [ -n "$u" ] && grep -rlF -- "$u" wiki/sources/ raw/*/
} | sort -u      # any path printed = possible duplicate
grep -rlF "source_hash" wiki/sources/ | head -1   # §11 control: MUST print a page — silence = the probe searched nothing, so "NEW" is unproven
```
An empty candidate list means NEW **only when the control line printed**; stderr stays visible by
design (a missing file or unreadable dir must surface, never read as "no duplicate").
**Paper keys:** run `python3 .claude/skills/ingest/dedup_probe.py "raw/$f" --url "$u"` (add `--title`/`--doi` for a PDF), which covers the block's name, hash and URL keys and adds arXiv id, DOI and normalised title, also without a trailing site suffix such as ` | arXiv`, over `wiki/sources/` and `raw/` frontmatter — the key code `capture_write.py dedup` loads — and prints `CANDIDATE <path> [keys]` lines or `NEW` beside its controls, exiting 2 with `PROBE FAILED: <what>`, never NEW, when its premise fails.

**On a match, decide (don't blindly skip):**
- **Process it as an UPDATE** when there's something new to extract — the user gave extra instructions,
  a deeper **depth** is requested (e.g. `--research`), it's a newer/extended version, or it plausibly
  carries **new content** (e.g. an **OpenReview / peer-review page** with reviews, rebuttals, scores,
  decisions). Read it and **merge new findings into the EXISTING wiki pages** (don't create a redundant
  second source page). A genuinely different artifact gets its own page, and a **review** always does:
  it is filed to `raw/7-reviews/` (Step 6).
  - **Depth upgrade (merge vs replace).** When the update is a *deeper depth* for an already-compiled
    source, **replace that one source page** with the deeper template (research → the literature-note
    template) and update its `depth:`; **merge** everywhere else — entity/concept/model/benchmark pages
    take the new detail incrementally, never a rewrite. Never downgrade: a re-ingest at a shallower
    depth leaves an existing deeper source page alone unless the user explicitly pins the shallower one.
- **Quarantine** to `raw/duplicates/` when it's **not useful** (truly redundant) OR the user says
  **"ignore duplicates"**; a review is never a duplicate (CLAUDE.md section 3), however redundant it
  looks. Move the file there — never leave dups in the inbox or delete them.
  A raw already filed under `raw/` (the capture of a source page a merge retires) moves there by
  the Step 6 sort procedure with `--re-sort`.
- No match (genuinely new) → proceed to Step 0. Record `source_url`/`source_hash` (Step 3) for next time.

> The probe catches *exact/near-exact* dups (name · byte-hash · URL) and the same paper in another file
> when an arXiv id, DOI or normalised title is shared. A **content duplicate carrying none of those keys**
> (a retitled version; an OpenReview page) won't match — spot it while reading, then apply the same
> decision (update vs `duplicates`).

- **Opt-out**: `--no-dedup` (or "skip dedup") skips this pre-flight for bulk all-new loads. On by default (cheap).

### Step 0 — Normalize to Markdown (MarkItDown) — conversion for non-`.md` sources; the score (3c) for every file carrying `converted_by:`
**If the source is already `.md`, SKIP the conversion (1–3b) — do NOT invoke MarkItDown — but still run 3c on it when its frontmatter carries `converted_by:`.** A gather, Jina or defuddle capture is a conversion whatever its extension, and the score keys on that observable, never on the extension; a Markdown extension alone does not establish that a conversion is undamaged. A `.md` with no `converted_by:` takes no Step 0 at all. A capture whose `converted_from:` names a TED talk page (`ted.com/talks/`), a gather capture included, also takes the TED check of the URL routing below, against the TED page fetched now if no copy was kept, recorded and reported the same way.

Otherwise (`.pdf`, `.pptx`, `.docx`, `.xlsx`, `.png`/`.jpg`, `.mp3`/`.wav`, `.html`, `.csv`, `.epub`,
… or a YouTube/web URL):

1. **Preflight the engine** (install once if missing — the console script is NOT on PATH here, so
   check *importability*, not `command -v`):
   `python3 -c "import markitdown" 2>/dev/null || pip3 install 'markitdown[all]'`
   `pdftotext` is **optional** and serves 3c's recovery measure only: `command -v pdftotext || brew install poppler`
   (macOS; the `poppler-utils` package elsewhere). Absent, or failing on a PDF, the scorer prints
   `recovery n/a (pdftotext absent)` or `recovery n/a (pdftotext failed: <reason>)` and decides on its other
   four text measures — it never stalls a conversion on the binary. A scanned PDF whose own text layer is
   unreadable reads `recovery n/a (reference unreadable (readable-words <share>, letter density <density>))` the same way (3c).
2. **Convert** (always use the module form — `python3 -m markitdown` — since the bare `markitdown`
   script isn't on PATH):
   - **Local file** → `python3 -m markitdown "<absolute path>" -o "raw/<stem>.md"`
   - **URL — capture the *original*, never a summary.** Route by type:
     - **Raw `.md` / text / code URL** (`raw.githubusercontent.com`, gist raw, `.txt`) → `curl -sL "<url>"` and save the bytes **verbatim**. **Do NOT use WebFetch** — it returns a model *summary*, not the source.
     - **Web page (article / repo / docs)** → the gather skill's structural routing, never a bare `defuddle` of the URL: `python3 .claude/skills/gather/capture_probe.py capture "<url>" --work <a new directory outside the vault>` fetches the page once, sends a page whose HTML carries a collapsed or tabbed block (details, hidden or aria-hidden panels, accordions, tab sets) through markitdown with each tab label set before its own panel (`curl+markitdown (structural route)`) and any other page through defuddle on the same fetched copy (`curl+defuddle`), compares the capture with the fetched page, and leaves `capture.md` and `result.json` in that directory. The comparison warns and never blocks: whatever it finds, the capture is saved, carrying its stamp (step 3). Exit 2 is `PROBE FAILED`: no capture was made (an HTTP error, a failed curl, a non-HTML response, ambiguous tabs, a failed conversion), so take the next route below and keep that `result.json` for step 3. The gather skill's capture chain states when the routing retires. Use WebFetch *only* for a throwaway lookup where exact text is irrelevant — never for ingest.
     - **TED talk page** (`ted.com/talks/…`) → TED loads a talk's transcript in the browser, so the structural route keeps only the page's description, and the Jina fallback has dropped a transcript's closing lines. Capture the talk's YouTube upload by the YouTube route below, which carries the human-made transcript; find the upload from the TED page or a search, and confirm its title with `curl -s "https://www.youtube.com/oembed?url=<video url>&format=json"`. Then check the capture against the transcript the TED page embeds, with `python3 .claude/skills/ingest/ted_cue_check.py <page.html> <capture>`, where `<page.html>` is the copy the structural route's probe saved or `curl -sL --compressed "<ted url>" -o <work>/page.html`. Exit 0 passes. Exit 3 prints the cues the capture lacks: re-take the capture, or declare it degraded (`capture_quality: "declared — <why>"`, step 3). Exit 2 is a broken premise (no transcript data, a cue with no text, an unreadable or empty file) and decides nothing. Record the outcome as `ted_check` on the source's `converted` checkpoint (`pass`, the missing count, or `undecidable` with its reason); anything but a pass is named in the Step 8 report under `Suspect conversions:`, whatever the structural probe's own stamp says, since that stamp cannot see transcript lines. A TED talk with no YouTube upload takes the Jina fallback below, with the same check. Suite: `bash .claude/skills/ingest/test_ted_cue_check.sh`.
     - **arXiv HTML / LaTeXML page** (`arxiv.org/html/…`, ar5iv) → do **not** defuddle it (defuddle's Markdown converter crashes on LaTeXML and silently emits raw HTML): `curl -sL` the page to a temp file, then convert with `python3 -m markitdown`.
     - **GitHub repo** → `curl -sL` the raw README/files (`raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md`), or `gh api` / `gh repo view` if authenticated.
     - **YouTube / binary URL** → MarkItDown's Python API (its CLI only accepts file paths):
       `python3 -c "from markitdown import MarkItDown; open('raw/<stem>.md','w').write(MarkItDown().convert('<url>').text_content)"`
     - **Blocked paper or page** (a paywall, a bot wall, an abstract-only page; an official web page behind a bot wall included) → resolve it first through the gather skill's open-access resolver, `python3 .claude/skills/gather/oa_resolve.py <doi|arXiv id|url|title> [--json] [--hand-fetch]`, which prints `RESOLVED <url> via <source>` (capture that URL by the rules above) or `UNRESOLVED` with a hand-fetch block for the owner; the gather skill defines the abstract-page refusal and any separately configured browser fallback. The resolver requires `OA_CONTACT_EMAIL`.
     - **Fallback — a web page none of the above can capture** (JS-heavy / anti-bot / empty or garbled result) → `curl -sL "https://r.jina.ai/<url>"` (Jina Reader renders server-side → clean Markdown). **Last resort only**; it routes the URL through a third party, so skip it for sensitive or login-walled pages. A page this fallback cannot capture either goes to the owner through the resolver's hand-fetch block (`oa_resolve.py <url> --hand-fetch`), and the owner saves it; never improvise a capture route, and never send page content from a browser to a local listener.
     - **Public X/Twitter post URL** → capture via the tier-1 Jina channel: `curl -sL "https://r.jina.ai/<post-url>"` (declare the routing in the ingest report, as with any Jina capture). Single public posts only — X search, timelines and protected content take the platform-gap path below.
     - **Platform URL the whole chain cannot capture** (a Reddit thread, XiaoHongShu note, X search/timeline/protected content, Bilibili search page, or other login-walled/bot-blocked platform page) → do NOT improvise a scraper and never WebFetch it: report the gap and point at the ready, owner-gated platform-reach option (nothing installs or routes without the owner's word). YouTube stays on the markitdown route above.
     - **Opt-in `--verbatim` (byte-exact original).** When the user wants the *unaltered* source (research-grade provenance / exact quoting), `curl -sL "<url>" > raw/<stem>.md` (or `gh`) and keep the bytes **unmodified** — skip the step-3 defang/clean (raw/ is graph-excluded anyway). For an HTML page, `curl` it then `python3 -m markitdown` to convert deterministically (full content, no summary). Heavier on tokens → opt-in, not the default.
3. **Save** the Markdown into `raw/` as `<original-stem>.md` (use `<original-stem>.converted.md` if
   that name is taken). **This is the only time you may add a file to `raw/`.** For a web page, first run
   `python3 .claude/skills/gather/capture_probe.py stamp "<work>/result.json" --body "<the Markdown file to save>" --url "<url>" --engine "<the engine that produced it>"`
   (the probe's own `capture.md` takes the engine `capture` printed; the Jina fallback's body takes
   `jina-reader`, with the probe's `result.json` wherever the probe left one). It compares that body with
   the page the probe fetched and prints the provenance lines to use: `converted_from:`, `converted_by:`
   (the engine you named, never the probe's) and `capture_check:`, a stamp that warns and never blocks
   the save: `suspected loss — <findings>`, `no loss found by the unit check (<counts>); not compared:
   <what the check does not compare>`, or `not run — <why>` (no result, an unreadable, malformed or failed
   one, a page the probe never fetched). The stamp never says the capture is complete. Record it on the
   source's `converted` checkpoint as `capture_check`, and name every `suspected loss` in the Step 8 report
   beside `Suspect conversions:`. A body you know is damaged takes `--allow-degraded '<why>'` on the same
   command, which adds `capture_quality: "declared — <why>"` and the checkpoint's `degraded` value; declare
   it in the run report. The command exits 0 whatever the check found; exit 2 means it printed nothing (an
   unreadable or empty body, a URL that is not one http(s) URL, or an engine or reason on more than one
   line). Prepend provenance:
   ```yaml
   ---
   converted_from: <original filename or source URL>
   converted_by: markitdown
   converted_on: <YYYY-MM-DD>
   conversion_score: <from 3c, e.g. clean · short-lines 4.0 % · run-together 1.7 % · long-run 0.3 /1k · recovery 0.96 · scope pdf · readable-words 0.950>
   ---
   ```
   Then **sanitise the saved body** so it can never pollute the Obsidian graph (MarkItDown emits stray
   `[text](bareword)` links from math/citations, and sometimes control/binary bytes):
   ```bash
   python3 -B .claude/skills/ingest/sanitise.py "raw/<stem>.md"
   ```
   (Strips control bytes; defangs `[a,b](z)`→`a,b (z)` and `[[x]]`→`[ [x] ]`, repeating until nothing changes; keeps real `://`, `#` and `mailto` links. `raw/` is also graph-excluded — see CLAUDE.md §12.)
   **The script checks its own invariants before it writes** (the passes converged, control bytes gone, no `[[`/`]]` or bareword link left, no real link's tail lost, the byte delta accounted for) and prints one `PASS <file>` line with the before/after counts; the independent check is its suite's perl oracle (`bash .claude/skills/ingest/test_sanitise.sh`). `FAIL` (exit 3) is a sanitiser defect with the file untouched: STOP and inspect. Exit 2 is a missing or unwritable file; exit 5 is a file outside the lane's write grants (`LLM_WIKI_LANE_WRITES`: the fence cannot see a write made inside an interpreter's script, so the script honours the variable itself). It runs under the lane fence, which denies in-place editors and redirection. `--verbatim` captures skip sanitising. (A capture-group clobber can ship `[]()` mangles that only a size check catches — `wiki/developments/known-issues.md` §Closed.)
3b. **Conversion-quality check (converted files only).** *3b and 3c never contradict: a `COLLAPSED` here is
   authoritative on its own, a `suspect` from 3c (scope `pdf`) is authoritative on its own, and either one
   raises the `flagged:` line on the source page — 3c's line records the five measures and names `3b COLLAPSED`
   beside them when 3b fired, so the line says which check spoke; a 3c `clean` never clears a 3b `COLLAPSED`.
   Probe (b) locates the damage.* Some PDFs convert with the inter-word spaces
   stripped, so the body reads `ProximalPolicyOptimizationAlgorithms…`. The text is still readable but
   has **no word boundaries to quote**, which silently defeats research depth's verbatim-quote contract
   and makes every word-count metric wrong. One arithmetic check, no LLM read:
   ```bash
   python3 -c "
   t=open('raw/<stem>.md',encoding='utf-8',errors='replace').read()
   w=len(t.split()) or 1; c=len(t); cjk=sum(1 for ch in t if '一'<=ch<='鿿')
   print(('COLLAPSED' if c/w>50 and cjk/max(c,1)<0.10 else 'ok'), round(c/w), 'chars/word')"
   ```
   **The whole-file mean clears a partially collapsed file.** MarkItDown's table padding, reference lists
   and prompt blocks restore enough whitespace to pull the ratio back under 50 while the running prose
   stays space-stripped.
   So every converted file also takes probe (a) below, which decides; where the mean or (a) fires, run probe (b)
   for the locators:
   ```bash
   # (a) run-word probe: letter runs of 25+ with no space in them, per 1,000 words.
   python3 -c "
   import re,sys
   t=open(sys.argv[1],encoding='utf-8',errors='replace').read()
   r=len(re.findall(r'[A-Za-z]{25,}',t)); w=len(t.split()) or 1
   print(('COLLAPSED' if r>=10 and r*1000.0/w>5 else 'ok'), r, 'runs', round(r*1000.0/w,1), 'per 1k words')" "raw/<stem>.md"
   # Positive control on the same run: compare with a known-clean capture.
   # `-c` counts matching lines, not runs; confirm that the control is below the suspect input.
   grep -coE '[A-Za-z]{25,}' "raw/<a clean capture>.md"
   # (b) per-line ratio over PROSE lines only — fences, |-rows, quotes, embeds and numbered
   #     reference entries dropped, since their markup is what dilutes the whole-file mean.
   #     (Both counts sit in their own variables: a `/` straight after `)` reads as a path to the lane
   #     shell fence, which denies the whole command.)
   python3 -c "
   import re,sys
   fence=False; bt=chr(96)*3
   for n,l in enumerate(open(sys.argv[1],encoding='utf-8',errors='replace'),1):
       s=l.strip()
       if s.startswith(bt) or s.startswith('~~~'): fence = not fence; continue
       if fence or len(s)<60 or s[:1] in '|>' or s.startswith('![') or re.match(r'^\[\d+\]',s): continue
       c=len(s); w=len(s.split()) or 1
       if c/w>50: print(n, round(c/w), s[:60])" "raw/<stem>.md"
   ```
   `COLLAPSED` from **either** the mean or probe (a) → the source **cannot be research** (Depth override):
   compile at standard, say so in the Step 8 report, and offer `--agent-convert` or a different capture
   route if the owner wants it quotable.
   A high ratio with ≥10% CJK is **not** a collapse — Chinese and Japanese have no inter-word spaces, so
   word counts are meaningless there while quoting works fine. The compatibility thresholds are
   set by judgement, unmeasured for a new corpus. Review them with known clean and damaged captures.
   Probe (b) is read, never counted: glyph padding and data-URI blobs can create false positives.
3c. **Conversion score — the scripted check (every file carrying `converted_by:`; register entry 2026-09-08).**
   Its compatibility thresholds require review against the local labelled corpus. Run it on every
   conversion after the sanitiser and its post-check, and on every `.md` capture whose frontmatter carries
   `converted_by:` — a gather or Jina capture included; the conversion steps are what a `.md` source skips,
   never this score:
   ```bash
   python3 -B .claude/skills/ingest/conversion_score.py "raw/<stem>.md"
   ```
   One verdict line per file — `clean` or `suspect` — with five measures, the threshold each was judged
   **The five measures.** Short-line share, joined-word share and long-run rate detect damaged
   spacing. Their compatibility cuts are 57.57%, 4.41% and 6.56 per 1,000 words; the long-run
   arm needs at least ten runs. Sentence recovery compares sentences of six or more words
   against an available `pdftotext` reference, with a cut below 0.15. Readable-word share counts
   ASCII letters in runs of four or more divided by all ASCII letters, with a cut below 0.367.
   The selection of these compatibility cuts is set by judgement, unmeasured for a new corpus;
   use `--derive DIR --positives FILE` and `--derive-readable DIR --positives FILE` with labelled
   local examples before relying on their calibration. Code, tags, links and non-Latin text
   follow the scorer's documented scope exclusions. Zero readable share means `destroyed`;
   low non-zero share means `damaged`. These are proxy flags, not an independent damage audit.
   Recovery is `n/a` when its PDF or tool is absent or its reference is unreadable. A reference
   is unreadable only when both readable-word share and letter density fall below their cuts;
   the density cut 0.306 is set by judgement, unmeasured for a new corpus. Equality remains readable.
   Same-run controls check glyph soup, readable prose, excluded frontmatter and inert padding.
   **`readable-words` (fourth text arm):** word-letter share — letters inside ASCII runs of four or more divided by all ASCII letters in the body, excluding YAML frontmatter. Digits, punctuation and markup padding do not enter the denominator; body letters in code and tags do. The compatibility cut is set by judgement from the author's own conversions; re-derive it against labelled local examples before relying on it. Keep corpus counts, boundary-file identities and measured scores in local records. `--derive-readable DIR --positives FILE` re-derives only this arm and names both boundary files. Zero share is `damage: destroyed`; a low non-zero share is `damage: damaged`; both retain `suspect` and exit 3. These are proxy flags, not an independent damage audit. The arm is `n/a` on non-Latin-majority bodies. Same-run controls check glyph soup, readable prose, excluded frontmatter and inert non-letter padding.
   Exit 0 = clean, 3 = suspect, 2 = a premise failure (an empty or unreadable file, a body with no alphabetic token, including digits only, or a directory with no `.md`): a premise failure is not a verdict — fix the premise and re-run.
   - **Scope — where the thresholds hold.** They were derived on PDF conversions of papers, and every verdict
     line says whether the file is inside that population: `scope: pdf` when `converted_from:` names a `.pdf`,
     a `.pdf` sibling exists, or `converted_by:` is one of this skill's document-conversion routes
     (`markitdown`, `agent`); `scope: other` for a defuddle, Jina, curl or gh capture of a web page. A
     `suspect` in scope `other` goes into the Step 8 `Suspect conversions:` block with its scope and measures
     and raises **no `flagged:` line by itself**: read the verdict line — API-docs captures fire the long-run
     rate on `BetaMessageParam`-shaped identifiers, READMEs the share on product names — and flag it only
     where the damage is real (a non-paper capture can read `suspect` with nothing damaged).
   - Copy the verdict, the five measures and the scope, in the verdict line's order, into the provenance block's `conversion_score:` line
     (the template in step 3), a measure the scorer reads `n/a` with its reason as printed (e.g.
     `recovery n/a (reference unreadable (readable-words 0.000, letter density 0.003))`), e.g.
     `conversion_score: clean · short-lines 4.0 % · run-together 1.7 % · long-run 0.3 /1k · recovery 0.96 · scope pdf · readable-words 0.950`. A source that arrived as `.md` (a gather capture) has no step-3 template of its own: its score stays in the run report and on the source page's `flagged:` line when suspect, and the raw file is never written back (raw immutability).
   - **`suspect` in scope `pdf`, and 3b's `COLLAPSED`, are recorded in the flag channel, and only there.** The
     source page (Step 3) carries one line,
     `flagged: <YYYY-MM-DD> source conversion suspect — raw/<path>.md · short-lines N % · run-together N % · long-run N /1k · recovery N · readable-words N[ · 3b COLLAPSED]; verify quotations against the original`
     — the 3c measures always, `3b COLLAPSED` appended when 3b fired, so the line says which check spoke;
     never a prose note in the summary and never a `depth:` comment: deep-lint reads `flagged:` and nothing
     else, and lint's `check_flag_admissions.py` reports a source page that admits damage in prose without a
     conversion flag. The source **cannot be research** (the Depth override); a quotation from it is
     paraphrase, or is checked against the original; and the Step 8 report lists it under `Suspect
     conversions:` with its measures. Offer `--agent-convert` or another capture route if the owner wants it
     quotable.
   - **Terminal state — how a conversion flag ends.** The flag is removed when a repaired conversion — a
     `raw/<path>-repair.md` beside the original, or a re-fetched conversion — scores `clean` here and joins the
     page's `sources:`, and the page's `## Summary` ends with one dated Provenance sentence naming the repair
     file and the quotation check:
     `Provenance (YYYY-MM-DD): compiled from a damaged conversion (<what the scorer read>); repaired conversion raw/<path>-repair.md (<its verdict>); quotation check: n confirmed, m corrected, u unverifiable.`
     That sentence admits the old damage by design, and `check_flag_admissions.py` counts an admission that
     also names a `repaired conversion` under its `RESOLVED:` line, never as a finding. Removing the flag
     without the repair, or rewriting the admission away, is not a resolution.
   - `--thresholds SHORT,RUN,RECOVERY,LONGRUN[,READABLE]` overrides the five measures for a scratch run (`-` keeps one, `off` disables one); four values retain the derived readable-word cut. The override is printed on the summary line; it is never the way to make a conversion pass.
4. **Keep the original untouched.** The original and the converted `.md` are now a **pair**. For a
   URL source there is no local original — the converted `.md` is the only file; keep the URL in
   `converted_from`.
5. **Agent conversion — opt-in `--agent-convert`, and the offered fallback.** On `--agent-convert` (or
   "transcribe it yourself"), skip the engine: read the original directly (PDF pages / images via the
   Read tool) and transcribe it to `raw/<stem>.md` yourself — a faithful transcription, never a summary;
   mark illegible spots `unverified`; set provenance `converted_by: agent`. Reserve it for sources where
   layout or precision defeats MarkItDown — it costs real tokens, so it is never the default. **Fallback:**
   when a conversion returns empty/garbled text (e.g. a scanned, image-only PDF), FIRST rule out a
   truncated download — an empty converter error on a binary source may mean a partial file, so compare
   byte size against the source and re-fetch once. Only then OFFER this route with a
   page/token estimate and proceed only on explicit confirmation; otherwise ask the user to OCR
   externally. Never fabricate content.

> From here on, "the source" means the **converted `.md`** (for converted sources) or the original
> `.md` (for native-Markdown sources).

### Step 1 — Read the source
- Read the source Markdown in full.
- If it references images worth keeping, download them into `assets/` and read them separately
  (LLMs can't read inline-image Markdown in one pass).
- If the clip is mainly a **pointer to a richer primary source** (a docs page, repo, or article URL),
  **follow that link** and fetch the real source by Step 0's URL routes, never WebFetch — compile
  from the source, not the stub.

### Step 2 — Extract & (if needed) translate
Pull out: **core thesis** (concise and complete), **entities** (people/companies), **tools** (software/apps/plugins/skills/services),
**concepts** (frameworks/methods/theories). Translate non-English content into British/UK English.

### Step 3 — Create the source summary → `wiki/sources/<slug>.md` (kebab-case)
```markdown
---
title: "Source: <Human Title>"
type: source
depth: concise | standard | research   # the depth you chose (Depth) — required on every source page
confidence: <tier>   # per CLAUDE.md §4.6: who wrote the source and how they know, never where it was posted; replace this comment with the ground of a tier off its default or a fidelity step's capture, or delete it
audited: <YYYY-MM-DD>   # today — assignment with the source in context is the check (§4.6); on updating an existing page, re-check its badge and re-stamp
tags: [topic]
sources: [raw/2-papers/report.md, raw/2-papers/report.pdf]   # converted .md AND original; one entry if native .md or URL
source_url: "<original web URL if a clip — else omit>"        # de-dup
source_hash: "<first 16 hex chars of the raw file's sha256>"   # de-dup — the length the pre-flight greps
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

## Summary
[The core summary, with the detail its claims need.]

## Key Takeaways
- ...

## Related
- [[EntityName]] — why related
- [[Concept Name]] — why related
```
**Dual provenance:** for a converted source, `sources:` must list **both** the converted `.md` and
the original (file path, or the URL for web/YouTube). Predict the post-sort paths (Step 6) so the
links don't break after the move. A review that starts before the sort meets planned paths that do
not exist yet: its brief maps each planned path to the file's current inbox path and names the
pending move.

**Compile routing — G3 and G4.** The routed workflow uses these carriers: (a) `.claude/skills/delegate/templates/brief-compile.md` carries the two gate-added clauses (the source page states the source's own provenance — publisher, date, URL; any sentence about a linked page uses only that page's or the raw's words), the CONTEXT NOTES slot and the `## Anomalies` report section; (b) the Verify step above scores every lane compile against the raw — fabrication · coverage · tier · structure · integration · language · anomalies, plus `claims` in parallel mode — before the head accepts it. **Mode gate (2026-09-04):** this routed default applies under the `multi` regime (owner-set, or head-resolved for the run under delegation `auto`, 2026-09-04). Under `single` the head compiles in-session unless an instrument-rule reason holds for that source — a batch it cannot hold (reason (b), which is Parallel mode below), or context isolation its watermark bands demand (reasons (c)/(d)) — and it may propose ONE verify lane for a high-stakes in-head compile, once (delegate skill §1). Default executor for a single-source compile in `multi`: a `wiki-compile` lane, at the class's per-call pick (delegate skill §2), at the run's authorised depth range — standard and research are gated (G3, G4); concise is ungated (a lane that chooses it is covered by the verify leg; the routing design page records the residual); estimate the current installation's index and source load for the cost rule; a 2–5 source `auto` batch routes one lane at a time (two routed lanes writing network pages concurrently is Parallel mode's race surface, and that shape takes Parallel mode's claims); the head keeps the resume pre-flight, the spawn record (echoed per `pre-report`; under `auto` the owner's `/ingest` invocation is the go for this single lane, whose whitelist is the ingest's own output — delegate skill §3 slot 0, dated clause), the Verify step and the close-out. When routed: the lane runs with the shape the gates tested — it writes the source page and the warranted network pages, its own index line and log entry under the §2.2 ingest exception, and sorts the raw; the head's post-lane check is the verify step plus Step 7's controls plus a full read of every page whose tier the lane raised (§4.6: delegation never raises a tier unread); §4.4 conflict settlement and the research-depth key-claim spot-check stay head-side; the head's close-out log entry, always written for a routed run beside the lane's, carries the verify verdict, the stamp mechanism and the `fable share` meter line; the spawn record keeps the full meter. **Re-gate runbook (rule 7; delegate skill §2):** a re-gate runs the paired fixture form — the parity store's `g34v2` fixture builder, scope parser, verify-dir stager and verdict script — with a fresh-session head arm (`claude -p --model <the head's model id> --effort max` in a snapshot-equal fixture, its transcript effort confirmed; the head's model is opus 5.5 unless the owner names fable, owner ruling 2026-09-29) against two routed lanes on the current carriers. A depth's second routed use no longer owes one: the standard-depth re-gate has run, the research-depth one is retired, and both routed defaults stand, every lane compile keeping its verify leg (see **Vault records** below). The runbook stays the procedure for a re-gate another rule triggers, such as a change to `wiki-compile`'s default model (delegate skill §2).

### Step 4 — Network the knowledge (entities · tools · concepts · models · benchmarks)

**Index read modes for a whole ingest run (CLAUDE.md §5).** Read `section` for the six sections this step
matches against, and `name` for the five it only checks membership in. Never `route`: an ingest knows
its types, so the whole file is waste — but a section list that is *wrong* loses recall silently, so
these eleven sections are the whole list; a step that needs a section outside them says so in its report and takes `route` for that step alone.

| `## ` section | Mode | Why | Write |
|---|---|---|---|
| Entities · Tools · Concepts · Models · Benchmarks | `section` | the only types a source shares with existing pages, so the only place duplication is the risk (§4.5) | free |
| Sources | `name` | sibling-source links in `## Related` and name canonicalisation; de-dup uses the pre-flight frontmatter probe, and sources never merge into another source | free |
| Syntheses | `section` | a new source can contradict an answer already filed; surface it as a §4.4 conflict | **ask** |
| Maps | `name` | a source in a mapped cluster usually belongs on that map | **ask** |
| Developments · User | `name` | framework records and the owner's profile may be relevant to source links and proposals; descriptions are not required | **ask** |
| Experience | `name` | a page here is read at its feature's deciding step, never matched against a source, so its name is all a link or a proposal needs | **ask** |

**A lane whose brief names an index slice reads that file instead of the five network sections' `section` read** (design
extension 2026-09-13, part 3): `python3 .claude/skills/ingest/index_slice.py <the lane's raws>`, persisted
by the head beside the run ledger as `<run>-index-<lane>.txt`, prints the complete name list of the five
sections (so membership recall equals the section read's), in `anchor` form the index line of every entry
whose name or `aliases:` value the raws name, and the index's sha256 prefix, which dates the slice; any
other entry is fetched by exact name, so a slice is a small fraction of the index it stands in for.

**"Ask" means propose, never write.** Those five are the owner's or a past decision's, so this step
reports the proposed line and waits; `wiki/user/` already carries that rule in CLAUDE.md §1. A lane
writes only what its brief whitelists, whatever this table says.

For each entity → `wiki/entities/`, **tool** (software/app/plugin/skill/library/service) →
`wiki/tools/`, concept → `wiki/concepts/`, **model** (any LLM named — e.g. Qwen,
GPT, Llama) → `wiki/models/`, **benchmark** (any eval dataset named — e.g. AIME, GSM8K, GPQA) →
`wiki/benchmarks/` (Title Case filenames; a tool keeps its canonical lowercase where applicable):
1. **Page missing** → create it per the `CLAUDE.md` frontmatter + required sections (`## Definition /
   ## Key Points / ## Related`; model & benchmark pages also carry `## Appears in`); set its
   `confidence` per §4.6 (compiled pages **cap at `high`**). Judge by **grounding strength, not source count** (the rubric's settled reading, 2026-09-02): one strong source that is *primary for the page's own claims* grounds `high` on its own; a strong source primary only for something adjacent, or reputable-secondary grounding, is `medium`; a page is graded by what it says, never lowered for being short, and where a stronger source it names is not captured the Step 8 report proposes capturing it; corroboration that conflicts is weighed as §4.6 says. The cap is a ceiling, never a demotion; assess the strength of the evidence rather than counting sources.
2. **Page exists** → read it, then **incrementally merge** new info (don't clobber).
3. **Conflict found** → **pause**, report the conflict to the user, ask how to handle it
   (keep both under `## Conflicts / Open Questions`, overwrite, or skip), then continue.
   **Time-sensitive conflict → suspect the page first.** When the contradicted fact is
   time-sensitive (releases, versions, prices, dates, roles) and the wiki page predates the
   source, never default to grading the incoming claim down — an earlier compile date is
   evidence of age, not of correctness. Either run ONE bounded verification probe (a single
   search or authoritative lookup) to settle which side is current, or set
   `flagged: YYYY-MM-DD <one-phrase reason>` on the page and keep both statements per §4.4.
   In batch pacing this needs no pause — report the outcome in Step 8.

**Models & benchmarks link bidirectionally** (CLAUDE.md §4.5): add this paper under the model/benchmark
page's `## Appears in`, and list the models/benchmarks the paper uses in the source page's `## Related`
(Obsidian backlinks then close the loop automatically). **Reuse** an existing model/benchmark page —
never duplicate one (fold `GPT-4`/`GPT-4o` into `GPT`, `MATH500` into `MATH`, `Qwen2.5` into `Qwen`).

A single source typically touches **10–15 wiki pages** via cross-links. No orphans — every page
gets a `## Related` section.

### Step 5 — Update the registries
- **First-run bootstrap**: if `wiki/index.md` or `wiki/log.md` is missing (a fresh clone), create it first
  — an empty `index.md` with the standard `## Sources / Entities / Tools / Models / Benchmarks / Concepts
  / Syntheses / Experience / Developments / Maps / User` headers, and a `log.md` seeded with one `setup` entry. On this
  same fresh-vault branch, **once**, ensure the graph colour palette: run
  `python3 .claude/skills/lint/apply-palette.py --apply` (idempotent — a no-op if the shipped palette is
  intact; restores it if a fresh clone had `colorGroups` wiped by Obsidian). If it prints `APPLIED…`, tell
  the user to reload Obsidian with the graph view closed. This runs **only** here (registries missing),
  never on a normal ingest. Then proceed.
- **`wiki/index.md`** → add each new page under its type heading (Sources / Entities / Tools / Models /
  Benchmarks / Concepts / Syntheses / …) with a one-line desc; sections are **thematically clustered,
  not alphabetical** — place the new line beside its nearest relations, not at the section tail.
  **Mechanism: anchored `Edit` (or append)
  per heading — NEVER a whole-file read-modify-write** (a rewrite writes back a stale snapshot and
  silently drops entries a concurrent session added; CLAUDE.md §5).
- **`wiki/log.md`** → append **via shell** (`vault-writes.py log-append`; never Read the whole file — it grows unbounded):
  ```markdown
  ## [YYYY-MM-DD] ingest | <short title>
  - **Changed**: created [[..]], [[..]]; updated [[index.md]]
  - **Converted**: <original> → <stem>.md via markitdown   (omit if source was native .md)
  - **Depth**: <tally, e.g. research 2 · standard 9 · concise 1>   (note the range if it was narrowed or pinned)
  - **Confidence**: <level(s) assigned, e.g. high>   (note any override of the §4.6 default)
  - **Conflicts**: none (or: conflict [[Page]], flagged/paused)
  - **Run**: <ledger run id>   (parallel runs also name lanes + models — §5 attribution)
  ```

### Step 6 — Sort the raw source (this vault's archive design)
Only after Steps 3–5 are confirmed done, **move** the source out of the `raw/` root into the
matching category subfolder with a plain shell `mv -n`, never the link-aware `obsidian-cli` move, by the
sort procedure below (**never edit file contents**, though you MAY
rename an unwieldy auto-generated clip filename to a clean kebab-case slug as part of the move):

| Signal | → destination |
|--------|---------------|
| arxiv / PDF / formal paper / report | `raw/2-papers/` |
| tweet / X status / LinkedIn / Reddit / thread | `raw/6-social/` |
| Substack / personal blog / newsletter | `raw/5-blogs/` |
| docs / reference / GitHub repo / gist / tool manual | `raw/4-webinfo/` |
| news / magazine / long-form web article | `raw/1-articles/` |
| meeting / personal notes | `raw/3-notes/` |
| video / podcast / audio / lecture transcript | `raw/8-transcripts/` |
| peer review / OpenReview page / rebuttal / meta-review | `raw/7-reviews/` |
| owner-authored original work (research outline / draft / paper / thesis) | `raw/9-originals/` |
| a repo pack (`repo-pack` engine) of the owner's OWN repository — a project-store snapshot; authorship outranks form, so never `4-webinfo/` (tie rule, 2026-09-07) | `raw/9-originals/` |
| none of the above / deprecated | `raw/archives/` |
| confirmed duplicate (ignored / not useful) | `raw/duplicates/` |

**If the source was converted in Step 0, move the original AND its converted `.md` together** into
the same subfolder, so they stay paired and the `sources:` links remain valid. After moving, the
`raw/` root should contain only still-unprocessed files.

**The sort procedure (every sort: the head's at merge-close, and a lane's where its brief grants sorting).** No wiki page links a raw file by name, since `sources:` holds the path, so a link-aware move has nothing to update and can only do harm: where a raw stem equals a source slug, Obsidian resolves a bare link to the raw file and its updater rewrites that link into a path link. A plain move changes no page. Four steps, each a command:
1. **Check, and move nothing on a refusal.** `python3 .claude/skills/ingest/sort_check.py pre --vault <root> <source>=<destination> …` names every file of the sort at once, both members of every original/conversion pair. `pre` checks only the files it is given and never looks for a pair member left out, so the sorter checks the paired-move rule above before running it: list the `converted_from:` of each conversion the sort names and name the original it records in the same plan (a URL names no file to move). Exit 0 prints one `MOVE` line per file, with its sha256 prefix, the `plan:` list (every member with its prefix) and the `post` command to run after the moves. Exit 1 refuses the whole sort, naming each occupied destination, missing source or missing category folder, and prints no `MOVE` line: move nothing, resolve each refusal (an existing destination is never overwritten) and run `pre` again. Exit 2 is a broken probe, never a pass.
2. **Record the plan, then move.** Before any move, append the plan to the run ledger as one `sort_planned` checkpoint for the source, the `plan:` list as its `post` value: `printf '{"ts":"%s","event":"checkpoint","run":"<run>","lane":"<lane>","stage":"sort_planned","source":"<source>","post":%s}\n' "$(date +%FT%R%z)" '<the plan: list>' >> <ledger>`. The record outlives the context that ran `pre`; a lane that sorts without the ledger reports the list under `## Controls` instead. Then move each file a `MOVE` line names with `mv -n <source> <destination>` (no-clobber).
3. **Verify, then record.** Run the `post` command `pre` printed. Its exit 0 shows that every move the plan names completed (each source gone, each destination present with the recorded sha256 prefix) and that no wiki page carries a path link (it scans every wiki page, outside code, for a wikilink or embed whose target starts `raw/` or `wiki/`); it does not check that the plan names both members of every converted pair. That duty sits with the paired-move rule above, checked by the sorter before `pre` (step 1). Only its exit 0 lets the `sorted` checkpoints be appended. Exit 1 lists each `NOT MOVED`, `MISMATCH` and `PATHLINK` line and records nothing as sorted: finish an interrupted pair by step 4, restore a path link on the run's own pages to its bare link, and report a path link on any other page rather than fix it silently.
4. **Recover an interrupted sort from its plan.** A sort that stopped part-way (a `NOT MOVED` line, or a resumed run whose last checkpoint for the source is `sort_planned`) is finished over its complete recorded plan, never re-planned from the members still in the inbox: run `pre` over every member with its recorded prefix, `<source>=<destination>@<prefix>`, exactly the `post` command's arguments. Where the context that ran `pre` is gone, they are the `post` list of the last `sort_planned` checkpoint for the source, read with a parser, or, for a lane's sort, the list in its report (in its transcript if it stopped before reporting). `pre` reads a member already at its destination with its recorded prefix as `IN PLACE`, refuses one that changed or is missing from both places, and prints a `post` over the whole recorded plan again: move what it prints, run that `post`, and append `sorted` only on its exit 0. A refused recovery, or a partly moved pair with no recorded plan, cannot be verified: report it and record nothing as sorted. Never move a file back.

**A raw already filed** (into `raw/duplicates/` above all) moves by the same four steps with `--re-sort` on `pre`, whose `post` carries it: the source is then a file in a folder under `raw/`, never in the inbox, and the destination a file in another folder under `raw/`. `pre` lists each wiki page that names the source's path as a `NAMES` line; the sorter updates those `sources:` in the same pass, or retires the page, and Step 7's link check confirms none dangles.


### Step 7 — Self-check (leave the wiki lint-clean)
Before reporting done, verify your own output so a later `/lint` would find nothing to fix:
1. Every page you created/updated is registered in `index.md`.
2. Every `[[wikilink]]` you wrote resolves to a real page — or you created that page.
3. Every page you created has a `## Related` section and ≥1 inbound link from another page (no orphans).
4. Each `sources:` path points to the file's **post-sort** location.
5. Every page you created carries a valid `confidence` (except `map`), assigned per §4.6, and every page you created **or updated** carries today's `audited:` stamp (§4.6 write-time self-audit — an update re-checks the badge, not just the content).
6. No page of the run's output set carries tool-call markup of the model harness (register entry 2026-09-17: a lane's pages each ended with a leaked closing tag that its own checks passed). Run `python3 .claude/skills/lint/check-tool-markup.py --vault . --files` followed by every page path in the set, each quoted. The set is every page you created or updated; for the head of a routed run it is the run's whole output: every lane's pages, each shared-page change applied at merge, and `wiki/index.md` and `wiki/log.md` where the run wrote them. The Verify step's manifest, `find <vault>/wiki -name '*.md' -newer <marker>`, taken again after the merge, lists them; keep the pages a lane's whitelist or the merge covers, as Verify step 1 does. Exit 0 passes. Exit 1 prints each hit as `path:line: <tag>`: remove a real leak from the page; a false alarm (a tag quoted in a way the check's strict rule does not count as code) is rewritten as plain code, a plain fence or a one-line code span in a paragraph free of raw HTML and link syntax, or the tag is named in words; then run the check again. Exit 2 (`cannot check <path>`, `0 pages checked`, `PROBE FAILED`) decides nothing: the self-check has not passed until a run over the whole set exits 0. A non-zero exit therefore fails this step and, for the head, the gate before `run_close`. Give the paths as arguments, never through `xargs` or `find -exec … +`, which run nothing on an empty list and so read as a pass. A normal ingest runs no lint, so this is the run's only look for the markup.

Fix any gap immediately. Scope this to the pages you touched — don't re-scan the whole wiki (efficiency).

### Step 8 — Report the new pages + depth + confidence (for the user to check)
After the self-check, surface a short summary so the human can review the agent's two judgement calls —
**how deep** each source was compiled and **how far** each page is to be trusted. List each page **created
or updated** with its `confidence` (add a word of basis for any grade off its default, the ground on its
`confidence:` line, and for any `authoritative`), and give every **source** its depth with the locator
that justified it (Depth). Invite the user to re-grade either; both are one-line changes. Example:

```
Ingested 3 sources → 11 pages (range: all three)
Depth:
- [[some-paper-slug]]    — research  T1 (Table 3 ablations) · T2 (calibration, About Me)
- [[some-docs-slug]]     — standard  T1 no (no original results)
- [[some-tweet-slug]]    — concise   ¬T3 (both tools already have pages)
Confidence:
- [[some-paper-slug]] — authoritative  (peer-reviewed)
- [[Some Concept]] — medium
- [[Some Entity]] — low  (rests on its maker's own praise)
- [[Some Benchmark Post]] — medium  (off its default: run by a staff member of one of the systems it ranks)
Suspect conversions:
- raw/2-papers/some-paper.md — short-lines 1.0 % · run-together 12.3 % · long-run 31.8 /1k · recovery n/a · scope pdf · readable-words 0.950 → flagged: on its source page; standard depth
- raw/4-webinfo/some-api-docs.md — scope other · long-run 8.7 /1k (identifiers in the prose) → read, not flagged
Run: run-<id> · 14 ledger events · closed
Re-grade a depth or a confidence and I'll fix it.
```

`Suspect conversions:` lists every conversion the Step 0 scorer (3c) read `suspect`, with its scope and the
measures from its verdict line, and says whether it was flagged (scope `pdf`, or a 3b `COLLAPSED`) or read and
left unflagged (scope `other`); a run with none writes `Suspect conversions: none`, so the absence is a
statement rather than a silence. A depth cell with an empty locator is a defect — go back and name the evidence, or drop a rung. To
**re-grade a depth upward** later, re-run `/ingest --research <sorted path>`: the de-dup pre-flight
recognises it as a deeper-depth request and takes the UPDATE path.

Where a page sits lower, or says little, only because a stronger source it names is not captured (a
repository, a paper, an official page), add a `Capture proposals:` line naming it with its `/gather`
command written out — at most three, for pages this run's work rests on; the owner's yes runs it.

**Completion gate:** an ingest is not done until this report — the depth lines, the confidence lines
**and the `Run:` ledger line** — has appeared in the reply. Deliver it in
the same reply that declares the run complete — never deferred to a later turn, and never displaced by
the self-check or other verification running long. A batch run reports every page of the batch in one
table; an interrupted run reports the pages compiled so far at the point it stops. If zero pages were
created, one line saying so satisfies the gate.

## Hard constraints
- **Pace via the Pacing section** (default = `auto`). Keep the human in the loop for conflicts and
  large/uncertain batches; don't ask permission for small, low-risk, on-topic batches.
- **Every run keeps a ledger** (Run ledger): `run_open` → checkpoints → `run_close`, evidence-only,
  disk is truth. The Step 8 `Run:` line is part of the completion gate.
- **Parallel mode never spawns without the owner's go** on the echoed spawn record; lanes emit claims
  for shared-type pages and never sort — the head merges, sorts and closes the run.
- **Never** modify or delete the text inside an existing raw file. The only permitted `raw/` writes
  are *relocating* a file (Step 6) and *adding* a MarkItDown-converted `.md` beside its original (Step 0).
- Convert every non-`.md` source with `markitdown` before reading it; never guess a binary file's contents.
- Every wiki page must have a `## Related` section (no orphans).
- Every wiki page (except `map`) carries a `confidence` — assign it per CLAUDE.md §4.6 (free, since you've already read the source).
- **Every source page carries a `depth`** — decided *after* the read, inside the run's authorised range, never from filename/folder/length/markers (Depth). Never backfill it onto older pages.
- After ingesting, **report the created/updated pages with their depth + locator and their `confidence`** so the user can review and re-grade — a completion gate: no done-declaration without it (Step 8).
- **Confidence on write; qmd before search:** confirm each created/updated page's `confidence` and stamp `audited:` per CLAUDE.md §4.6. Ingest completion starts no qmd refresh. Before every qmd search, run `.claude/skills/qmd-search/qmd-fresh.sh` per `qmd-search`; only exit 0 permits qmd, otherwise use `index.md` → `grep` and report why the semantic index is not current.
- Entities/Concepts = Title Case filenames; Sources/Syntheses = kebab-case.
- Write everything in **British/UK English** (US spelling only inside verbatim quotes, proper nouns, or code).
- Don't fabricate. Mark uncertain claims `unverified` and cite the source.

> **Standing derivative**: `output/user-notes/gather-ingest-quick-reference.md` — a change to this skill's user-facing workflow (commands, flags, gates, report shape) updates that note in the same pass (§2 output contract).

**Vault records.** Some steps above lean on records a vault keeps for itself rather than on anything this skill ships. The **routing design page** holds the routing's protocol items, the parity gates' evidence, the dated status facts and the **routed-run register**: one row per routed run (run id · step · lanes and models · verify-leg result · head slice result · empirical item result · misses · reverts · head output delta and fable share), appended at the close-out (Verify step, item 5). The **parity store** holds the paired fixture form's fixture builder, scope parser, verify-dir stager and verdict script, under the agent home. A vault names both in its local pointers here; where a vault has neither, the re-gate runbook cannot run as written, and the head reports that gap rather than guess a fixture.

