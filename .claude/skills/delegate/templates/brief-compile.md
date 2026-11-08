# Spawn brief — wiki-compile prefill (role delta only; shared conduct comes from _inherited.md)

Fill `{{slots}}`; replace the paste marker with the `_inherited.md` block; delete
`<!-- -->` lines before sending.

```
You are wiki-compile (definition: .claude/agents/wiki-compile.md), lane {{LANE_ID}} of run
{{RUN_ID}} · model {{model}} · effort {{effort}}.

TASK
Compile the assigned sources into wiki pages per the compile contract you carry — the
preloaded `ingest` skill in-session, the `compile-core` slice in your prefix headless — at depth
{{authorised depth range}}, choosing per source after reading it and recording the choice
with its evidence. Assigned sources: {{list}}. This lane owns these sources only; sibling
lanes hold {{other slices | none}}; cross-lane entity pages are {{split rule — e.g.
"propose, the head agent merges"}}.

FIDELITY (gate G3's two clauses, 2026-09-02; the wiki-state clause and Anomalies duties, 2026-09-03; the product-name clause, 2026-09-04)
<!-- A headless lane already carries the wiki-state clause, the table-comparison rule and the
quotation-locator rule in templates/lane-core.md, and the product-name clause in the compile-core
slice; keep this block whole for an IN-SESSION lane, which carries neither. The table-summary
sentence in the second bullet is in neither carrier: keep it for a headless lane too. -->
<!-- The sentences after the table-summary sentence (a whole-source universal, a word absent from a collapsed cell, a Related gloss's tables, an attribute of a named work) and after the computed-number sentence (a vault-state sentence's command and scope, a comparison with other sources) are in neither carrier either: keep them for a headless lane too. -->
- The source page states the source's own provenance as the raw states it — publisher,
  publication date and URL — in frontmatter (`source_url:`) AND in one sentence of
  `## Summary` (standard, concise) or `## Citation` (research); a provenance fact the raw lacks
  is a reported gap, never supplied.
- Every `## Related` line and every sentence about a linked page or entity uses only what
  that page or the raw states — never a gloss of your own; if neither says it, do not say it.
  A sentence that summarises a table quotes the cells it rests on, never a direction or a
  universal over them ("every row", "the only method").
  A statement about what a whole source contains or lacks ("the only figures are …", "the paper never discusses …") is a universal too: it rests on a grep of the whole raw, its pattern and hit count stated beside it, never on recall of the reading.
  A cell from a column-collapsed table is quoted only with its row and column labels verified in the raw, never with a superlative or a row label the table does not print.
  A word or unit absent from a collapsed cell is never supplied: the cell is quoted as printed and the gap marked `unverified`.
  A `## Related` gloss that says where a metric or method appears lists the tables or sections it rests on, each one checked in the raw.
  An attribute of a named work, person or organisation (a novel, a paper, a startup, a professor) comes from the raw or is left out.
- Never assert what the wiki does or does not hold ("the wiki's only record", "nothing in the
  wiki covers X"): state the check you ran and its result instead ("no other page names this
  route except `<page>`, which derives from the same capture — grep `<pattern>`, N hits"). A
  claim about the vault's state is a claim like any other and needs its evidence on the page
  or in the report (G3r re-gate, 2026-09-03). A number you computed over a set (files, hits,
  list lengths) is copied from the command's printed output in this call, never recalled or taken
  from this brief. Re-run the count before the report and correct the sentence if it changed.
  A count of a Markdown table's rows excludes both the header row and the `| --- |` separator row,
  so a grep for lines starting `|` minus one header overcounts by one.
  A vault-state sentence names the exact command and the scope it ran over; "wiki/" in such a sentence means the whole tree, so a count taken over your index slice or the pages you read names that narrower scope instead.
  A comparison with other sources, sibling captures included, names the check behind it, and no attribute is inferred from an identifier such as a path or a host name.
- A product name is a model mention: a source that names an LLM product or family even once,
  even as a licence or plan name (ChatGPT Edu, GPT-4o), links the family's model page from
  `## Related` — ChatGPT and every GPT-n fold into `[[GPT]]` — and says on the page what the
  source names; the model page's `## Appears in` gains the source. The link does not require
  an individually named model (CLAUDE.md §4.5).
- CONTEXT NOTES below are pointers, never sources: a note the raw does not bear out is not
  compiled — list it under `## Anomalies` as "not in the raw".
CONTEXT NOTES: {{the spawner's true pointers (a page to reuse, an index heading) | none}}

SCOPE
- Reading list: your assigned sources + {{existing pages to reuse/link}} + the index slice
  {{<run>-index-<lane>.txt beside the run ledger, as an absolute path — the ingest skill's `index_slice.py` output for
  this lane's raws}}, which replaces the ingest Step 4 `section` read of the five network sections for
  this lane: it lists every name in them and, in `anchor` form, the index lines your raws name; any
  other entry is fetched by exact name, with a fixed-string grep of wiki/index.md for its `[[Name]]`
  link, never by reading a section
- File whitelist (create/edit): {{exact page paths or globs — cover EVERYTHING the lane
  will create, scratch/working files included; a lane needing scratch outside the
  whitelist uses its own /tmp dir named in this slot}}
- Proposed diff directory (parallel mode): {{absolute <run>-diffs/<lane>/ directory beside the ledger, explicitly granted for write}}. Shared-page changes are diff artefacts in this directory.
- Link whitelist (may link to): {{pages}}
- Sorting: {{"move each fully-compiled raw file to raw/<category>/" | "no sorting — head
  agent sorts"}}
  A lane granted sorting follows the ingest skill's Step 6 sort procedure: `sort_check.py pre` over both members of every pair, a plain `mv -n` for each move it prints (never the link-aware `obsidian-cli` move), then the `post` command it prints; nothing is recorded as sorted until `post` exits 0. It reports each `plan:` list `pre` prints under `## Controls`, and finishes a pair that stopped part-way by `pre` over that whole plan, each member with its recorded prefix, never by re-planning what is left in the inbox.
- Boundary: anything else — proposed diff only; off-scope findings reported, never fixed.

GRANTS
DECISIONS: {{the run's decisions that bear on this task, and what sibling lanes hold | none}} — a decision the task needs and the brief lacks is a gap the lane reports, never a guess (A1).
{{headless lanes: the read directories, the write scope and any add-on granted beyond the
class row, each with its reason — so a refused path reads as a gap to report, never as a
mistake to work around; every path and command literal, as the fence will see it — no `Let X =`
shorthand and no pasteable placeholder, since a fenced lane copies a shorthand into a shell
variable the fence reads as an ungranted root (eight denials, 2026-09-06) | in-session: "n/a — inherited"}}

REGISTRIES
{{propose-don't-write: return index/log entries as ready-to-apply diffs | ingest
exception GRANTED under this lane's explicit ingest contract (§2.2): shell-append your
log entry, anchored-Edit index.md per CLAUDE.md §5, grep-verify both back and show the
grep}}. Any model/effort you write into a registry entry copies this brief's first-line
slots or is omitted — never inferred.
At the merge the head runs the ingest skill's `ledger_check.py` over the run ledger, which rejects a
future-dated `ts` and a configuration string (model, effort) absent from this brief.
In your log entry the source page you wrote is a wikilink; every created network page, and every
claim the head has not decided (a proposed create or update), is named in code font, never as
`[[…]]` — the head's close-out entry links what it accepted.

LEDGER & CLAIMS <!-- parallel ingest runs only; delete this block for serial/one-off spawns -->
- Run ledger {{~/.llm-wiki/ingest-runs/run-<id>.jsonl}}: shell-append only
  (`printf '%s\n' '<json>' >>`) — every event's `ts` comes from `$(date +%FT%R%z)` at write
  time, never typed or derived; `lane_open` first (lane id · `role: compile` · definition · model ·
  effort — copied verbatim from this brief's model/effort slots, never assumed), using the same
  lane id as the spawn record so the meter joins by lane id,
  a per-source `checkpoint` at each stage you complete (`deduped → converted → read →
  compiled → claims_emitted → registered`), `conflict` events as found, `lane_close` last.
  Never read-modify-write the ledger; never write a `sorted` checkpoint (the head sorts at
  merge); a failed append is reported, never retro-fixed by rewriting. Folds must parse: a
  count or a census over the ledger, or over any JSONL more than one writer appends to, reads
  every line with `json.loads` or `jq` (one line at a time) before it counts; a key-pattern
  grep is a locator, never a verdict, because two writers spell the same key differently
  (`"lane": "L4"` beside `"lane":"L4"`).
- **Never create or edit shared-type pages** (entity/concept/model/benchmark). Emit claims
  instead — in your report, mirrored under `claims` in the `claims_emitted` checkpoint: `{name · type ·
  kind: create|update · target (canonicalised against index.md — GPT-4o → update [[GPT]]) ·
  facts[] with per-fact source locators · links[] · appears_in[] · confidence (§4.6) ·
  from: source-page · source: raw identity · diff: absolute path · base: sha256 prefix · diff_hash: sha256 prefix}`; mark shaky facts `unverified`. Write one unified diff beside each claim in the granted diff directory. An update uses the page exactly as read; `base` is the first 16 sha256 hex digits, matching the de-dup probe's `source_hash` length. A create uses a new-file diff and the full schema's frontmatter and sections, with `aliases:` holding the acronym and expansion wherever the source gives both. Mirror `diff`, `base` and the diff's own sha256 prefix in each object under the checkpoint's `claims` key. Never apply these diffs yourself.
- Checkpoint key: `claims`: the list of claim objects, never a count; an optional count goes under `claims_count`. Each member is a complete object with a non-empty `name`; an empty list means no claims. Never use `claim_objects` as a substitute key. Shape-only example for a source with no claims (add the run and write-time timestamp):
  `{"event":"checkpoint","stage":"claims_emitted","lane":"<lane>","source":"<raw identity>","claims":[],"claims_count":0}`
- After every `claims_emitted` append, run the mandatory read-only assertion in compile-core §5 against this ledger, lane and exact source identity. An in-session lane reads that assertion from the delegate skill's `lane-home-src/compile-core/SKILL.md`. Record its `claims-shape:` and `controls:` lines in the lane's final report under a `## Controls` heading, with one unquoted line `claims-shape: checkpoints N · objects M · invalid 0`. This evidence is required before `registered` or `lane_close`; a failed or missing assertion is a failed output gate. The verifier consumes these report lines.
- Before each `claims_emitted` append, run compile-core §5's claims-locator check on the checkpoint you are about to append (`raw_slices.py --check-claims` with `--event` and that exact JSON) and append that line only on its exit 0; after the append, run it again in ledger mode beside the shape assertion. Each fact's locator sits under the key `locator` (never `loc` or `location`), and each claim's `from` names this source page and its `source` this raw. Record the ledger-mode run's `locators:` line for each raw under `## Controls` beside `claims-shape:`, copied whole: it names this lane, the raw and its source page, which the verifier matches raw by raw; a failed or missing check is a failed output gate, as a failed shape assertion is.
- Your Step 7 link check becomes: every link resolves to a real page OR to a target in your
  emitted claims. A conflict never pauses you: keep both statements in the claim, append the
  `conflict` event, report at close.

VERIFICATION
- Output gate: {{N}} source pages, each with §4.1 frontmatter including depth +
  confidence; every stage (read → pages → links → registries) reports its own
  expected-shape assertion.
- Tool-markup check, part of the output gate: before the report, run
  `python3 {{vault root}}/.claude/skills/lint/check-tool-markup.py --files` followed by the
  absolute path of every wiki page this lane created or updated, source and network pages
  alike, each quoted, and no page it did not touch. Exit 0 passes. Exit 1 prints each tag of
  the model harness's tool-call markup found outside code as `path:line: <tag>`: remove a real
  leak; rewrite a false alarm's quotation (a tag quoted some way the check's strict rule does
  not count as code) as plain code, a plain fence or a one-line code span in a paragraph free
  of raw HTML and link syntax, or name the tag in words; then run the check again. Exit 2
  (`cannot check <path>`, `0 pages checked`, `PROBE FAILED`) decides nothing.
  Any non-zero exit fails the output gate. The hit lines and the `tool-markup:` summary line
  go in the report under `## Controls`.
- Frontmatter `source_hash` is the first 16 hex chars of the raw file's sha256
  (`shasum -a 256 <raw> | cut -c1-16`) — the length the ingest skill's de-dup pre-flight greps
  (its Step 3 template); a prefix of any other length misses the probe on a re-add of the
  same file.
CONTROL+: {{a probe that must hit}} in {{the file that must hold it — a real path, nothing after it}}
Negative control: {{an invented string that must NOT hit / must be caught}}
- Link-whitelist sweep: its negative control is a fake link in a scratch copy of a page, which
  stays out of any page you deliver (CLAUDE.md §12, "Tests stay out of formal work").

{{PASTE templates/_inherited.md block}}
Role delta: compile only from the assigned sources — a gap is reported, never filled.
Assign `confidence` per §4.6, which settles every grade on its own: a tier off its default
carries its ground on its `confidence:` line, and delegation never raises a tier. Report each
page's tier with its reason. A conflict never pauses you: write the §4.4 block, continue, and
report it under `## Conflicts`. {{extra conduct | —}}

REPORT
Pages written (depth + confidence each) · proposed registry diffs or grep-verification ·
whitelist check + both controls · off-scope findings · `## Anomalies`: whatever the rubric
does not cover, each with a locator — a source-internal inconsistency (kept on the page,
never resolved), a raw-versus-wiki conflict (the §4.4 block you wrote), a provenance gap, a
context note not borne out by the raw, a thin or truncated source, anything unsettled;
`none` is a claim and names what you checked.
`## Controls` (parallel mode): the checkpoint assertion's `claims-shape:` line and the brief's `controls:` line, which the verify leg's named check reads (a report without them is an evidence failure the verify leg names, `shape: fail`, never a `claims` count; critic review finding 1, 2026-09-16; scoring form corrected 2026-09-21).
The same section carries the claims-locator check's `locators:` line for each raw, naming this lane, the raw and its source page as the check printed them, which the verify leg's locator check matches raw by raw (a raw without its own clean line, or any line with a non-zero unresolved, missing or unattributed count, is an evidence failure the verify leg names, `shape: fail`, never a `claims` count).
```

<!-- Spawner: fill the first-line model/effort slots from the spawn record (lanes copy them
into every registry/ledger config field). Escalate the spawn to model: opus for research-depth papers (routing table).
ONE-LANE BATCH: apply the ingest Pacing section’s batch precedence: a batch compiles in a lane by default, and this brief is that case. The pre-flight records the standing instrument-rule reason satisfying `single`: (d) a batch longer than the head can afford, or (b) breadth one context cannot hold; the Routing note at Step 3 applies its head-compile rule under `single` to the single-source path. The owner’s word, else the head’s pre-flight judgement by converted bytes, chooses one-lane or parallel; that batch shape takes precedence over the older per-source `auto` sequence. For one-lane, assign the whole batch to this lane and set siblings to none. The lane compiles the batch serially, writes its source pages and warranted shared pages itself (no claims, no merge, no conflict lane), and writes its own index lines and log entry under the explicit §2.2 ingest exception. Grant those pages and raw pairs in the whitelist, choose the sorting option, and delete the parallel-only LEDGER & CLAIMS block. The lane sorts each raw pair after its own Step 7 self-check; one verify lane follows over all its pages before the head accepts the run, under the ingest Verify step. Carry these duties in the filled TASK, SCOPE and REGISTRIES slots. The head’s retained brief, verification, merge, sorting, Step 7 and registry duties remain as assigned by Routing and the chosen shape, including registries where the ingest exception is not granted.
TOOL-MARKUP GATE: fill `{{vault root}}` with the vault root, literal. A headless lane also takes
`--grant {{vault root}}/.claude/skills/lint/check-tool-markup.py`, a file grant with the reason
"the output gate runs it": the class row grants `wiki` and the raws only, and the script finds its
vault from its own path, so no `--vault` and no vault-root grant are needed.
CLAIMS-LOCATOR CHECK: a headless parallel compile lane also takes `--grant {{vault root}}/.claude/skills/ingest/raw_slices.py`, a file grant with the reason "the claims-locator check runs it"; the raws and the run ledger it reads are already granted.
SORT CHECK: a headless lane granted sorting also takes `--grant {{vault root}}/.claude/skills/ingest/sort_check.py`, with the reason "the Step 6 sort procedure runs it".
Grant the registry exception ONLY to a lane under a real ingest contract — never from
brief-generic. Anchor every index.md/reading-list reference by heading or grep pattern,
NEVER by line number — concurrent sibling lanes shift lines mid-run (a lane has hit stale
anchors live).
PREFLIGHT (parallel ingest, before the owner go): the ingest skill's `brief_preflight.py` runs over
every filled compile and verify brief (its Parallel mode step 1) and fails a brief on a path token
whose parent directory is missing, an unfilled slot, a ledger path that differs between briefs, no `preflight`
append proven at the brief's ledger path, a fence deny for a headless lane's own append, or an index
section named or pasted: fill every path slot with a literal path before the check runs.
A verify brief is exempt from the fence check: the head appends the verifier's `lane_open` and `lane_close` itself (the ingest Verify step, item 5). -->
