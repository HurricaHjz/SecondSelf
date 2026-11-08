---
name: lint
description: >
  Health-check the Obsidian wiki — the "static analysis" pass for a knowledge base. Use when the
  user runs /lint, /health, /scan, or asks to "check the wiki", "find broken links", "clean up the
  wiki", or "find gaps/orphans/conflicts". A scan, read-only until its report, of dead links, dead media
  embeds, orphan pages, pages missing from index.md, unresolved knowledge conflicts, live links
  leaking into the attic, wikilinks from shipped skill or agent files into wiki pages that never ship, experience-page pointers by file and step, and the
  count of pending `flagged:` freshness flags (≥5 suggests a deep-lint). Also restores the graph colour
  palette on request (on-demand only, never on a routine scan). After the report it applies the fixes
  that are certain and easy to reverse and lists them; it asks first only for an attic-leak repair or
  a choice held for the owner under CLAUDE.md §12 or hard to reverse.
user-invocable: true
---

# lint — knowledge-graph health check

## Goal
Find the rot that accumulates as a knowledge base grows: **dead links, orphans, unindexed pages,
unresolved conflicts, and lost or misplaced experience-page pointers.**

## When to run (and when not)
**Don't lint routinely after a normal ingest** — ingest/query leave the graph integrity-clean by
construction (CLAUDE.md §6). Run lint for *drift* (manual edits/renames/deletes in Obsidian, external or
OneDrive/git sync changes) and periodic *discovery* (emerging gap pages, cross-corpus contradictions,
stale claims).

**Scope boundary:** confidence coverage, staleness scoring, and online-source freshness are **not**
lint's job — they live in the heavier, ~monthly **`deep-lint`**. Routine `/lint` stays cheap and never
reads pages for confidence or fetches anything.

## Triggers
`/lint` · `/health` · `/scan` · "check my wiki" · "find broken links / orphans / gaps".

## Pipeline (read-only until the report; then fix, asking first only where Hard constraints say)

### 1 — Index consistency (one scripted check)
Run `python3 .claude/skills/lint/check-index.py --vault .` (exit 0 = the probe ran, findings or none;
2 = broken premise). It compares `wiki/index.md` with the pages on disk and prints three lists with their
counts: **unindexed pages** (on disk, registered by no `- [[…]]` entry), **dangling index entries**
(registered, no page on disk) and **duplicate entries** (the same target registered twice). The rules are
deep-lint `audit-pools.py`'s, copied so a reader can check them against it: resolution on the basename with or without
`.md`, `index.md` and `log.md` excluded as pages, and a page's frontmatter `aliases:` counting as a
resolution on both sides (one deliberate departure from audit-pools, which aliases the dangling side only). It
prints `SCANNED: <pages> pages · <entries> index entries` as its own positive control (§11): a root it cannot
scan ends in `PROBE FAILED` and exit 2 before any list prints, so a clean result always carries non-zero counts.
Copy the three figures into the report — never re-derive them by hand. Shared stems are printed as information, not a finding.

### 2 — Link health (one shared script — the single source of truth for link rules)
Run `python3 .claude/skills/lint/check-links.py` (exit 0 = clean, 1 = findings; deep-lint's
structural pass uses the same script). It applies the codified rules so scans never re-derive them:
code spans / fenced blocks / HTML comments are not links; frontmatter `aliases` resolve (the list is
read as YAML reads it, a one-line flow list or a block list of one-line items, so a quoted alias may
carry a comma; a list YAML cannot parse, such as an unclosed quote, text after the closing bracket or an
escape naming no character, or a value spread over more than one line, such as a block scalar, a wrapped
list or an item continued below, prints under `MALFORMED ALIASES:`, a finding, and gives no alias);
vault-path and root-doc targets resolve;
`wiki/log.md` is exempt as a source (append-only history); and **media embeds `![[name.png|pdf|…]]`
resolve the way Obsidian resolves a file name** — a bare name by file name anywhere in the vault outside
dot paths and the attic, a path-qualified one by its path; a missing target is a **dead embed**, reported
separately (they are checked, not skipped), and a bare name that more than one visible file carries
prints under `AMBIGUOUS EMBEDS:` (it renders, so it is listed, not a finding: qualify it with a path).
The script prints its scan totals as its own positive control (§11): zero findings with zero links
scanned is a broken probe, not a clean vault.
- The same script resolves each page's frontmatter `sources:` entries against disk and reports **dangling
  sources** separately from dead links: one line per page · path, with `SOURCES SCANNED:` as that arm's
  control. A URL, prose provenance (`email: …`, `session: …`) and an entry that declares its own deletion
  (`path (deleted YYYY-MM-DD)`) are counted, never flagged — provenance written as prose is legitimate. An entry the
  parser could not read prints as `(empty or unparsed sources)` inside the same block: read it, since it is the
  parser's own gap detector, not a dangler. On a source or synthesis page an empty `sources:` is a finding of
  `check-required-sections.py` (Structure, below). A `~`- or `/`-led entry is provenance **outside the vault** (a run
  store, a home directory): resolved with `expanduser`, it prints under `OUT-OF-VAULT SOURCES: n present | m missing`
  — a missing one is a finding in that bucket, never a dangling vault path (register entry 2026-09-08).
- The same script reads the frontmatter `converted_from:` of every `raw/**/*.md` conversion and lists, under `MISSING ORIGINALS:`, a local original found neither beside the conversion, nor at its vault path, nor anywhere under `raw/` by file name, with `CONVERSIONS SCANNED:` as that arm's control; a URL or prose value is counted and never resolved, and a stale value whose original survives elsewhere under `raw/` is listed apart, never as a finding (register entry 2026-09-09).
- Beside it, `python3 .claude/skills/lint/check_flag_admissions.py --vault .` (exit 0 = clean, 1 = findings, 2 =
  premise: not a vault root, or no `wiki/sources/`) lists every page under `wiki/sources/` whose prose or frontmatter
  comment **admits conversion damage** — the vocabulary `collapsed`, `lost inter-word spaces`, `inter-word`,
  `space-restored`, `run-together`, `run together`, `verbatim quotation is unavailable`, `lost every chart`, `lost
  every figure`, `lost every table`, `charts lost`, `figures lost` — while the page carries no **conversion** flag: a
  `flagged:` line counts only when its own text carries `conversion` (`source conversion suspect …`), so a flag about
  something else never masks an admission. A damage admission belongs in the flag channel (ingest Step 0 scores every
  file carrying `converted_by:` and records a `suspect` one in scope `pdf` as `flagged:`), which is the only channel deep-lint reads;
  the fix for a hit is a `flagged:` line on the page, never a rewrite of the prose — and the flag's end is ingest 3c's
  terminal state: a repaired conversion scored `clean` in `sources:` plus the dated Provenance sentence, which the
  probe counts under its `RESOLVED:` line (an admission that also names a `repaired conversion`), never as a finding.
  It prints its own in-memory controls (a page that must fire; its conversion-flagged twin that must not; a twin
  flagged for something else that must; a resolved twin; a marked twin and a negated twin that must not) and the
  count scanned (register entry 2026-09-08, ingest Step 0 conversions, and the folds of the same day).
  A line carrying `<!-- lint: not a conversion admission -->`, or whose term directly follows a negation (`must not be collapsed`), is listed under `SUPPRESSED:` and never counted as a finding (register entry 2026-09-09).
- Every script in this directory refuses, in vault mode, a root that is not a vault (no `raw/` + `wiki/`): one `PROBE
  FAILED: <root> is not a vault root (no raw/ or wiki/)` line on stderr and exit 2, so a wrong root can
  never read as a clean vault scan (the 2026-08-26 standard; the register entry of 2026-09-06 that closed it
  here; the file-mode forms `anomaly-lister --pages` and `tier-cap-check --verdicts` keep their own checks). Every
  Python script and `check-qmd-registry.sh` take `--vault ROOT`; an unknown flag is refused with exit 2, never
  read as the root.
- Orphans are scripted too: `python3 .claude/skills/lint/check-orphans.py --vault .` reports a page with **no inbound links** from any other page as an **orphan**, exempting `index`, `log`, and `maps/` pages (Maps of Content are navigational entry points, not orphans). It applies this directory's link rules, prints its own inbound-link control (zero orphans with a zero control is a broken probe, §11), and additionally lists the pages `index.md` alone reaches — information, not a finding.
- Two further helpers in this directory serve deep-lint and the routing design's verify leg, not routine lint: `tier-cap-check.py` (§4.6 type cap; an owner override, a `confidence:` comment opening `override:`, is reported separately, never as a violation) and `anomaly-lister.py` (page-visible anomalies: open conflict blocks, `flagged:` lines, thin-page notes, `unverified` markers; a conflict block counts as settled only when every claim in it, nested items included, opens its own line with the CLAUDE.md §4.4 form `Settled YYYY-MM-DD:` (the word as written, one space, a real calendar date in that shape, the colon straight after it, and the outcome on the same line), and no open signal (`still disagrees`, `remains open`, `unresolved`, `not yet`, `pending`, a negated marker such as `never been resolved`) sits anywhere in it, so another marker word (`Resolved 2026-10-01:`), a bare colon (`**Settled**:`), a date without its colon, a date the calendar lacks (`Settled 2026-02-30:`), a declaration with no outcome after its colon, or `resolved`, `settled` or `a single resolution` anywhere else never settles one, and a block in an older form is listed, never rewritten; `--settled-markers` accepts only `Settled` and refuses any other value (exit 2), so no value of it settles another form; a list inside a block quote is read as claims like any other, a declaration whose value opens with `once`, `when`, `if`, `after`, `until` or `pending` settles nothing, `closed` is no marker word (it names an issue's closure), and a block that settles one claim and leaves another open stays listed: the script's docstring states the rule). Suite for all three: `bash .claude/skills/lint/test_lint_phase2.sh`.
- Structure: `python3 .claude/skills/lint/check-required-sections.py --vault .` lists every page missing a level-2 section its table requires, with each page's `depth:` beside it; the table covers `## Related` for concept, entity and tool, `## Appears in` for model and benchmark, `## Summary`, `## Key Takeaways` and `## Related` for source, and `## Sources Used` for synthesis and development, exempts maps, and checks no other part of CLAUDE.md §4.3 (register entry 2026-09-03). A research-depth source page carrying the ingest template's `## Citation` is judged on `## Related` alone (CLAUDE.md §4.3, the research-depth clause of 2026-09-14): the check reads `depth:` before judging a page's sections, and such a page is a finding only without `## Related`. It also lists under `EMPTY SOURCES:`, with the same exit code, every source or synthesis page whose frontmatter `sources:` parses to no non-empty entry (absent, `[]` on the key's line or below it, `null`, `~`, empty strings, blank or comment-only items, a mapping such as `{}`, a value YAML cannot read, an invalid escape included, or a value spread over more than one line, a block scalar included: the value is read with its YAML type, one line per value or per list item; CLAUDE.md §4.1, register entry 2026-09-15); a development page is outside that rule. Every page's whole frontmatter block is also read by PyYAML (BaseLoader, as the ingest lookup reads it): one it refuses, or one that opens with a `---` line and never closes, is listed under `MALFORMED FRONTMATTER:`, with the same exit code. Without PyYAML the check stops with `PROBE FAILED` and exit 2, since it has no other reader for the block.
- Restated rules: `python3 .claude/skills/lint/check-tier-vocabulary.py --vault .` extracts every `caps at` / `defaults to` plus a tier word from CLAUDE.md §4.6 and from each skill's `SKILL.md`, and lists under `MISMATCHES:` a skill statement to which §4.6 gives another tier for the same page type (register entry 2026-09-03).
- Register: `python3 .claude/skills/lint/check_register.py --vault .` lists an entry under `## Open` in `wiki/developments/known-issues.md` whose `**Status**:` begins `closed`, `fixed` or `resolved`, and two Open entries citing one `file:line` locator, and prints `register-check: n/a` when the vault has no register yet (register entry 2026-09-07).
- Each of those three prints its own in-memory control and its scan totals and exits 0 clean, 1 findings, 2 broken premise; they share the suite above.
- Tool-call markup: `python3 .claude/skills/lint/check-tool-markup.py --vault . --all` lists every wiki page carrying tool-call markup of the model harness outside code, one `path:line: <tag as found>` line per hit (register entry 2026-09-17: a compile lane's pages carried a leaked closing tag past the lane's own output gate). A hit is an opening, closing or self-closing tag named `invoke`, `parameter`, `function_calls`, `function_results` or `content`, or carrying the `antml` namespace prefix, anywhere but in code. Code is strict (owner decision of 9 October 2026): only the lines inside a plain fence (three or more backticks or tildes, opened at most three spaces in and closed by a run of the same character at least as long) and a one-line code span in a plain paragraph count, so a tag in an HTML comment, an indented block, a block-quoted fence, a span spread over two lines or anything after a fence never closed is a hit, and an unusual quotation shows up as a false hit rather than a missed leak. The script's docstring states the rule in full. It prints its in-memory control, a `CANDIDATES:` line and the `tool-markup:` summary with the pages checked. Exit 0 clean; 1 hits, which are findings and report-only for the script: after the report the agent removes a real leak from the page, and rewrites a false alarm's quotation as plain code (a plain fence, or a one-line code span in a paragraph free of raw HTML and link syntax) or names the tag in words, listing each; 2 cannot decide (`cannot check <path>`, `incomplete scan: <dir>`, `0 pages checked`, `PROBE FAILED`), reported as a finding, never as clean. The same script is the compile lane's output gate and ingest Step 7's check over a run's own pages. Suite: `bash .claude/skills/lint/test_check_tool_markup.sh`.
- **Routing (M0, 2026-09-02; residue closed 2026-09-07):** every lint check is a script; the agent reads reports and never re-derives a scripted count (orphans became `check-orphans.py`, Phase 2 of the routing design; Step 1's index-consistency comparison became `check-index.py`, the last hand comparison in this pipeline).

### 2b — Pending freshness flags (count only — reconciling them is deep-lint's job)
`grep -rl "^flagged:" wiki --include='*.md' | wc -l` — with the engine control
`grep -rl "^confidence:" wiki --include='*.md' | wc -l` (must be >0, proving the probe ran).
Report the count; at **≥5 flagged pages**, suggest running `/deep-lint` (set by judgement, unmeasured).
Never read or resolve the flagged pages here — lint counts, deep-lint reconciles.

### 2c — Attic-leak check (filenames only — attic contents are never opened)
Live pages must never link into the attic (CLAUDE.md §2.1): Obsidian resolves wikilinks and embeds
vault-wide, so a surviving `[[link]]` or `![[embed]]` to an archived file silently reconnects retired
material and can pull a query in. List every attic file by name only, the root catalogue `attic/MANIFEST.md`
aside by its path (an archived project's own `MANIFEST.md` is listed like any other file; the check
reads names, never contents; attic absent or empty → report "attic-leak: n/a"), and grep live wiki with
fixed strings for the **delimiter-complete** link forms of each name: every form ends in the character
that closes a link target, so a longer name never matches.
- A Markdown file `b.md`: `[[b]]` `[[b|` `[[b#` `[[b.md]]` `[[b.md|` `[[b.md#` `/b]]` `/b|` `/b#` `/b.md]]` `/b.md|` `/b.md#`, and the Markdown-link forms `(b.md)` `(b.md#` `/b.md)`.
- Any other file `b.ext` (an image, a PDF, a script; a name without an extension is kept whole): `[[b.ext]]` `[[b.ext|` `[[b.ext#` `/b.ext]]` `/b.ext|` `/b.ext#`, and the Markdown-link forms `(b.ext)` `(b.ext#` `/b.ext)`. An embed is covered by the `[[` forms.
- The forms go in a **pattern file**, never on a command line. List the names, write every form of every name, one per line with no blank line (a blank line is an empty pattern, which matches every line), with the file-writing tool (not a shell command) to a scratch file outside the vault, then search with fixed strings; from the vault root, `wiki/log.md` (append-only history) excluded, each hit printing as `path:line:form`:
  ```sh
  find attic -type f ! -path attic/MANIFEST.md -print
  { grep -rnoFf <pattern file> --include='*.md' wiki; echo "search exit: $?"; } | grep -v '^wiki/log\.md:'
  ```
  The search's own exit status prints after its hits, read straight after it and before the log filter, whose status would turn a search error into an ordinary no-match: `search exit: 0` with hits, or with log hits only, `1` with none, and any other status (`2`, or no status line) is a failed probe, never "no leaks", whatever else printed.
  Most forms begin with `/`, and a fenced headless lane refuses a command word that begins with `/` and lies outside its grants. With the forms in the file no form is ever a command word, so no command word begins with `/` but the pattern file's own path, which lies inside the scratch area the session or lane may use.
- Not findings, and not matched: a plain-text mention (`attic/b.pdf (archived)`, the §2.1 sweep style) and a longer name (`[[b.pdf.old]]`). Stated limits: a Markdown-link target written URL-encoded (`my%20note.md`) or in angle brackets is not matched; a parenthetical plain mention ending exactly at the name ("see attic/b.pdf)") and a live file sharing an attic file's name do match, so read each hit before calling it a leak.

Any confirmed hit is a **leak finding**: report it; the fix (owner-confirmed) is re-sweeping to plain
text per §2.1, or `/attic restore` if the page should live again. Control (§11): a pattern file holding
the forms of one known linked live page's name, searched with the same command, must print a hit
(`path:line:form`) and `search exit: 0` before reporting "no leaks"; a diagnostic or the status line
alone is no hit.

### 2d — qmd registry guard (one scripted check; skipped silently when qmd is dormant)
`wiki/log.md` must stay out of the semantic index (CLAUDE.md §10) — embeddings key on a file's
whole-content hash, so every append re-embeds the whole timeline, and a hit invites an unbounded whole-file read via
`qmd get`. The exclusion lives in `~/.config/qmd/index.yml`, **outside the vault and outside both
git repos**, so it can disappear silently. Run
`sh .claude/skills/lint/check-qmd-registry.sh .` and copy its one line into the report verbatim.
The script carries its own §11 control (`index.md`, deliberately kept, must be listed) and reports
`PROBE FAILED` rather than "clean" when its own premise breaks. Exit 1 = finding; the fix is to
restore `ignore: ["**/log.md"]` on the `wiki` collection and re-run `qmd update`.

### 2e — Injection guard (names only — no skill or definition contents are read)
Third-party installers write into the roots the harness auto-loads, and anything landing there reaches
**every** session (Agent Reach's documented SKILL.md auto-install; two register incidents prove the
class: `wiki/developments/known-issues.md` 2026-08-21/22). **Two roots, four arms, and a plugin arm (below).** Skills are
**directories** under `.claude/skills/`; agent definitions are **files** under `.claude/agents/`, and
each is auto-loaded — a definition names a lane's model, tools and write scope, so an unsanctioned one
is the same exposure as an unsanctioned skill. The asymmetry is real: `ls` yields names in one case and
filenames in the other, so the `comm` inputs differ. Both diff against the same baseline,
`.claude/skills/lint/sanctioned-skills.txt` (its `-skills` filename is kept for compatibility; it is the
registry for both), plus the user's own `.claude/sanctioned.local.txt` where that file exists: the same
line format, in the user's layer, never shipped. A user's own skills and helpers (the `my-` names) are
listed there, since the shipped registry is core in a user's copy; the prefix alone sanctions nothing.
```bash
b=".claude/skills/lint/sanctioned-skills.txt"    # ships: vault skill names + agent definition filenames
bl=".claude/sanctioned.local.txt"                # the user's own lines, same format; absent = none, never ships
hs="$HOME/.claude/skills/.sanctioned.txt"        # machine-local baselines, never shipped
ha="$HOME/.claude/agents/.sanctioned.txt"
[ -s "$b" ] || echo "PROBE FAILED: vault baseline missing/empty"            # premise guard, never "clean"
reg="$(cat "$b"; [ ! -f "$bl" ] || cat "$bl")"   # the shipped registry, then the user's own lines
# vault skills (directories)
comm -13 <(grep '^vault:' <<<"$reg" | cut -d: -f2 | sort) <(ls .claude/skills | sort)
# vault agent definitions (FILES — list everything, do not filter to *.md: a stray file here is the finding)
[ -d .claude/agents ] && comm -13 <(grep '^agent:' <<<"$reg" | cut -d: -f2 | sort) <(ls .claude/agents | sort) \
                      || echo "agents-guard: n/a (no .claude/agents in this vault)"
# user-level roots
[ -d ~/.claude/skills ] || echo "PROBE FAILED: ~/.claude/skills missing"    # premise guard, never "clean"
[ -s "$hs" ] && [ -d ~/.claude/skills ] && comm -13 <(sort "$hs") <(ls ~/.claude/skills | sort)
[ -s "$ha" ] && [ -d ~/.claude/agents ] && comm -13 <(sort "$ha") <(ls ~/.claude/agents | sort)
```
Any name printed = an **unsanctioned entry** (finding: report it; the fix — owner-confirmed — is removal,
or a conscious baseline addition in the same pass that sanctions it; in a user's copy, for the user's own
skill, that addition is a line in `.claude/sanctioned.local.txt`). **Premise failures never read as
clean, each in its own way:** a missing/empty vault baseline reports `PROBE FAILED`; an absent
`.claude/agents/` reports `n/a` (a vault may legitimately have none, so absence is not a finding and not
a pass either); an absent user-level root reports `PROBE FAILED`; no machine-local baseline yet (fresh
machine) → report that root's current listing as info and propose seeding it after the owner reviews,
never a finding, never auto-seeded. Baseline entries missing on disk are info (drift), not findings.
§11 control before trusting any empty result: re-run **each** arm's `comm` with a known-absent name
injected into the disk side (`printf 'zzz-ctrl\n'`) and confirm it prints — one arm's control does not
vouch for another's. The local list has its own control where it holds a line: re-run the vault-skills
arm on `$b` alone and confirm it prints each listed `my-` skill that is on disk, then confirm the arm
above prints none of them. A skill or helper that is on disk and in neither file is a finding, whatever its
name.
(Deep-lint inherits this via its structural pass.)
**Plugin arm (the fifth).** `python3 .claude/skills/lint/check-plugins.py --vault .` lists every plugin that `enabledPlugins` turns on in `~/.claude/settings.json` (under `$CLAUDE_CONFIG_DIR` when it is set) and in this vault's `.claude/settings.json` and `.claude/settings.local.json`, and prints each key that has no `plugin:<name>@<marketplace>` line in the machine-local `~/.claude/skills/.sanctioned.txt` as an unsanctioned plugin (exit 1).
A plugin can ship `hooks/hooks.json`, and its hooks reach every session just as its skills do, so the arm names each enabled plugin's hooks state beside its key.
Its premises follow the rules above: a baseline with no `plugin:` line yet is a fresh machine (the enabled list is information and a seeding proposal, exit 0), an unparseable settings file is `PROBE FAILED` (exit 2), and a known-absent key injected into the enabled side prints on every run as the arm's own control.
- **Throttle check (delegate skill §2, 2026-09-02):** `python3 .claude/skills/delegate/throttle.py check` — each `DRIFT` / `MISSING` / `UNROUTED` / `DESCRIPTION-TIER` line is a finding (the fix is `throttle.py set <active>` for drift, a definition or routing entry for the other two, the range wording for a description); `PROBE FAILED` (unreadable `routing.json`, unknown throttle name, absent `.claude/agents/`) never reads as clean. The script prints its own §11 control (a planted-drift comparator) on every run.

**Register arm (2026-09-05; names only, both directions).** `wiki/developments/capability-register.md` lists every
user-level skill as one row (`| \`name\` |`) under `## User-level skills`; the directory and the register must agree:
```bash
reg="wiki/developments/capability-register.md"
[ -s "$reg" ] || echo "register-arm: n/a (no register page yet — a fresh vault; /adopt seeds it)"
[ -s "$reg" ] && rows=$(awk '/^## User-level skills/{f=1} /^## Plugins/{f=0} f' "$reg" | grep -oE '^\| `[a-z0-9-]+`' | tr -d '|` ' | sort -u) \
  && { echo "installed, no row:"; comm -13 <(printf '%s\n' "$rows") <(ls ~/.claude/skills | sort); echo "row, not installed:"; comm -23 <(printf '%s\n' "$rows") <(ls ~/.claude/skills | sort); }
```
Either list non-empty = a finding (the fix, owner-confirmed, is a row or an install, never a silent delete). Control before
trusting two empty lists: re-run with one real row name filtered out of `rows` and see it appear under "installed, no row".


### 2f — Customisation pairing (cheap greps — no preference content is judged)
The preference layer is two files: always-on `CUSTOMISATION.md` (core: contracts + default style/role
blocks + `customised`) and on-demand `CUSTOMISATION-definitions.md` (the other definitions; read on
switch). Core absent (fresh vault) → report `customisation-pairing: n/a` and skip. Checks:
- The `style` and `role` values in core's `## Settings` each have a matching `^### <value>` heading
  **in core** (the block-move rule keeps the defaults there). §11 control: the same probe must find
  `### customised` in core (it never moves) before any missing-heading finding — or an all-present
  result — is trusted.
- No `### ` heading appears in both files:
  `comm -12 <(grep '^### ' CUSTOMISATION.md | sort) <(grep '^### ' CUSTOMISATION-definitions.md | sort)`
  must print nothing. A hit = a duplicated definition (finding: propose removing one copy; the owner
  says which — never auto-edit their preferences). Note `### ` lines inside HTML comments (e.g. the
  generalist example) can surface here; a hit inside a comment is reported as info, not a finding.
- Definitions file missing while core exists → **warning** (switches beyond the defaults will run
  without their definitions): propose recreating it from the private backup or the template seed
  (the `mk_custom_defs` function in the shipped `setup.sh`). Never fatal, never auto-created.

### 2g — Shipped-surface wikilinks (one scripted check — the publish gate's test suite calls the same script)
Every `.md` under `.claude/skills/` and `.claude/agents/` ships with the public framework; a `[[wikilink]]`
in one of them that resolves in this vault but not in the published copy is dead for every installer — the
class the 2026-08-30 delegate-skill finding proved. Run `python3 .claude/skills/lint/check-shipped-links.py --skip-skill <name> .`
(one `--skip-skill` per skill the exporter's skip lines keep out of every public build, the names the publish gate's leg 14 passes) and copy its first line into the report verbatim. Scope is keyed on the export's auto-discovery contract
(`list_skills`/`list_agents`), minus vault-shaped content bundled inside a skill (any `wiki/` or `raw/`
segment, i.e. the shipped seed demo); names that ship are never findings (`index`, `log`, and the seed's own
pages); links inside code spans, fenced blocks and HTML comments are not links; targets resolve as Obsidian
does, frontmatter aliases included; root docs are out of scope (their `[[…]]` are naming examples by design —
CLAUDE.md §12's ship-safe-citation rule governs citations there). A link dead in both copies is counted on
the control line, never flagged: shipped skills use placeholders such as `[[topic]]`. The script carries its
own §11 control (a synthetic surface linking a synthetic page must be caught) and tells legitimate absence
from a broken premise: an empty `wiki/` (a fresh install, the published copy itself) reports `n/a`; a missing
`wiki/`, no surfaces, an unreadable surface or a silent self-control reports `PROBE FAILED`, never "clean".
Exit 1 = findings: the fix, applied after the report and listed, is rewriting the citation in ship-safe
wording — the page name in code font, no link — never deleting the reference. The publish gate's test suite runs the same script
(its leg 14), so an edit-time miss here is caught there; regression fixtures live beside the script
(`bash .claude/skills/lint/test_check_shipped_links.sh`).

### 2h — Experience reach (one scripted check)

`python3 .claude/skills/lint/check-experience-reach.py --vault .` pairs each page in `wiki/experience/` with the readers its header declares, by file and step, and each pointer with a page. Report its totals and every `WARN` line (0: no warning; 1: warnings; 2: a failed premise). A vault with no pages and no pointers prints that state, which is no evidence that a pair works. A reach warning is reported and by default not repaired here, since moving or restoring a pointer edits a skill or an owner rule; an authorised repair writes `reach changed` as the page's preamble says.

### 3 — Conflict audit
Find pages containing `## Conflicts / Open Questions`. List each unresolved conflict (the two sides)
as cognitive tech-debt to resolve.

### 4 — Gap scan (optional, suggestive)
Note entities/concepts mentioned often but lacking their own page, and stale claims newer sources
supersede. Suggest sources or web searches to fill gaps.

## Graph colour restore (on-demand — NOT part of a routine lint)
The graph's per-type colours live in `.obsidian/graph.json` → `colorGroups`. That file is **volatile**:
Obsidian rewrites it from memory whenever a graph setting changes (or a sync clobbers it), and can wipe
the palette so the graph turns all-grey. A wiped palette is **immediately visible**, so handle it
**only on a real signal** — never scan for it on a routine lint.

**Trigger — do this only when:**
1. the user reports a grey/colourless graph or asks to check/fix/restore graph colours, **or**
2. it is a **fresh vault** at first-run — `ingest`'s bootstrap calls this once (see that skill).

Otherwise do nothing: a routine `/lint` never reads `graph.json` or the palette.

**Procedure (one shared script — the single source of truth for the palette):**
- **Detect:** `python3 .claude/skills/lint/apply-palette.py --check` → exit 0 = palette complete (stop);
  exit 1 = it prints the missing framework groups.
- **Restore:** `python3 .claude/skills/lint/apply-palette.py --apply`, then say it ran —
  it **merges** the canonical palette (`.claude/skills/lint/palette.json`) into `colorGroups`, adding
  only the missing framework groups and **preserving any custom groups**. Idempotent.
- **Reload:** tell the user to **close the graph view and reload Obsidian** (`Cmd/Ctrl+R`), so Obsidian
  does not overwrite the edit with stale in-memory state.

The palette data (`palette.json`) and logic (`apply-palette.py`) ship with this skill, so `setup.sh`,
`ingest`'s first-run, and this restore all use the **same** definition — read **only** on this path,
never on a routine lint.

## Report format
```markdown
## 🩺 Wiki Health Report — YYYY-MM-DD

### ✅ Healthy
- ...

### ⚠️ Warnings
- **N orphan pages**: [[..]] — suggest linking or categorizing
- **N unindexed pages**: [[..]] — on disk but missing from index.md

### ❌ Errors
- **N dead links**: [[Source]] → [[Missing Target]] · **N dead embeds**: [[Source]] → ![[missing.png]]
- **N unresolved conflicts**: [[Page]]

### ⏳ Flags
- **N pages carry `flagged:`** (engine control OK) — ≥5 → consider `/deep-lint`
- experience reach: the script's totals line, with each warning (or PROBE FAILED with its reason)
- `<the qmd-registry line, verbatim from the script>` · `attic-leak: none / n/a / N leaks` · `skill-guard: clean / N unsanctioned (control OK)` · `customisation-pairing: ok / n/a / N findings` · `throttle-check: clean (N of M diffed, control OK) / N findings / PROBE FAILED` · `shipped-links: clean / n/a / N dead / PROBE FAILED` · `plugins-guard: clean / not seeded (N enabled) / N unsanctioned / PROBE FAILED` · `missing-originals: 0 / N` · `required-sections: clean / N pages · E empty sources · T research-depth template pages (judged on ## Related alone)` · `tier-vocabulary: clean / N mismatches` · `register-check: clean / n/a / N findings` · `tool-markup: clean / N hits on M pages / cannot decide`

### 🛠️ Fixes
- Applied after the report, each listed (e.g. N unindexed pages registered): …
- Waiting for the owner, each with its reason (an attic-leak repair, held under CLAUDE.md §12, hard to reverse, or an ambiguous match): …
- Re-derive / resolve the listed conflicts? (a source re-read, beyond this cheap pass)
```

## Hard constraints
- **Read-only scan.** Do not modify, rename, or delete anything before the report.
- **No unverified "clean".** A check that returns zero findings must be validated with a positive
  control (the same probe matching something known to exist) before the report may say "clean"
  (CLAUDE.md §11).
- **Fix after the report and list every fix**; ask first only for an attic-leak repair (Step 2c keeps
  it owner-confirmed) or a choice held for the owner under CLAUDE.md §12 (the owner's rule text, a design direction, the owner's
  preferences) or hard to reverse (CLAUDE.md §12). A fix applied without asking must be certain: its
  target resolved, its effect checked; one that rests on a guess stays a finding and is reported.
  Lint checks a fix's effect by re-running the check that found it.

  The generated capability register at `wiki/developments/capability-register.md` is never edited by hand in any step of this run: report each finding on it and route any repair through an adopt proposal, including findings about formatting, narrative, links, sections, staleness or metadata. This rule still applies if its digest is missing or invalid; retain every check and its controls, and follow the existing authorisation and review rules for the proposal.
- **Graph colour restore is on-demand only** (see its section) — never scanned or read on a routine lint.
- After fixes, append to `wiki/log.md`:
  `## [YYYY-MM-DD] lint | fixed N issues (M dead links, K unindexed)`.
- **qmd after fixes:** writes do not refresh qmd; the `qmd-search` skill's gate catches the index up
  before its next search (that skill owns the rule).
- Report in **British/UK English**.
