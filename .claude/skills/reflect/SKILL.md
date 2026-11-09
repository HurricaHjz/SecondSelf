---
name: reflect
description: >
  Sweep the current conversation for things worth keeping — knowledge and insight, working context
  (decisions, directions, preferences), method lessons, framework defects — and propose where each
  should be recorded, then write what the owner approves, and lessons an independent checker failed
  to refute on a feature's existing experience page. The test is future performance across
  ALL the owner's work (research, writing, funding, life), never framework development alone; an
  intuition the owner states counts. It reports the unrecorded essentials, ranked, and no number cuts a survivor. Use ONLY on an explicit instruction: /reflect, "capture what we learned", "reflect on
  this session", "store the lessons from this". NEVER runs automatically and never fires from
  passive context. It is a SECOND lane beside the agent's ordinary in-flight filing, which is
  unchanged: this is the owner's own trigger for what that lane missed. Preview every run and
  approve what needs it; opt-in `--yes` writes inside wiki/ within the bounds its section sets, and may correct
  aiMyth's own working records outside it. `--cross
  <transcript>` runs the same bar over ANOTHER session's transcript via a read-only reflector
  lane (cross-reflection; see its section below).
user-invocable: true
---

# reflect — capture what a session learned, on the owner's word

The agent files findings as it works. **That lane is unchanged and ungated.** This skill is the *second* lane: an explicit trigger the owner owns, for the
times the first one did not fire. It removes model-dependence from the **trigger**, not from the quality
of the harvest — a weaker model still finds less; it just no longer has to think of looking.

**The test is always future performance, across everything the owner does** — research, writing, funding,
work and life as much as framework development. A hunch about a research direction, a preference learned
from how a draft was received, a decision and the reason behind it: each can be worth more to a future
session than any number of process notes. Do not read "essential" as "technical".

## Trigger — explicit only
`/reflect`, or an imperative addressed to the agent: "capture what we learned", "reflect on this
session", "store the lessons from this". **Passive context never fires it** — not an `<editor_selection>`,
not an `@`-mention, not a line in `IDEAS.md`. If a phrase like "we should remember that" appears in
passing, surface it and ask; do not start a run.

**Non-interactive runs** (headless, scheduled) need an explicit trigger. A read-only reflector lane
proposes and never writes. An authorised head follows Step 6's modes, and `--yes` never widens a file
grant, since a flag cannot authorise a write its grants do not hold.

## Pipeline

### Step 1 — Read the register's open entries
`wiki/developments/known-issues.md`, `## Open` only. Two reasons, both intrinsic: a candidate defect must
not duplicate an entry already there, and a lesson from this session sometimes **closes** one. Surface an
entry to the owner **only when a candidate touches it** — do not print the list every run.

### Step 2 — Sweep the visible conversation, and say how far it reaches
Collect candidates of four kinds. The first two matter most often; the last is the narrowest.
- **Knowledge & insight** — something established, corrected or discovered here that the wiki does not
  hold: a correction the owner made, a finding from a probe run in the conversation, a conclusion drawn
  across pages that sits on none of them, or **a stated intuition worth testing later**.
- **Working context** — how the owner works and where they are going: a decision and its reason, a
  direction taken or abandoned, a priority, a standing preference, a constraint that will recur. Usually
  `wiki/user/`, and usually invisible to any source-driven route.
- **Method / process lesson** — something about how to work that would change a future session.
- **Defect** — a fault in a framework surface (the schema, a skill, a script).

**Horizon, measured every run.** Earlier turns may have been compacted out of context, so measure the
boundary against the on-disk session transcript instead of asserting it: `echo` a fresh nonce in shell,
then grep for it **in a later call** under the harness transcript directory (the transcript records a
call's result only after that call returns, so the same call cannot find its own nonce) (Claude Code: `~/.claude/projects/<vault path,
separators as dashes>/*.jsonl`). The single file containing the nonce IS this session's record — the
transcript logs the probe itself, which is the positive control (CLAUDE.md §11). A **negative** control here needs a needle the transcript has not already recorded: assemble it at runtime rather than typing the literal (a typed literal matches because the command logging it is part of the medium), or state the baseline count of self-hits. A control that fires against its own stated expectation is repaired, never narrated past. Count its human turns
with a filter **verified against the visible span** (every visible human turn must be matched; beware:
tool results, harness task-notifications AND Skill-tool injections (`isMeta: true`, opening "Base directory for
this skill") all carry `"type":"user"` and must all be excluded: №103 cross-reflection P1, 2026-08-28; cross-reflection R1,
2026-09-05), and report
`visible k of N recorded turns`. **Fallback** — no transcript, no unique nonce match, or a filter that fails its own check →
the unmeasured form: name the earliest visible turn and state that the boundary carries no control
this run. **Never report "nothing to capture this session"** — only "nothing in the visible span".
On `--full` (explicit request only), read the compacted-out remainder from the transcript file itself,
declaring the token cost before reading.

### Step 2b — Usage and waste (development runs only; owner-added 2026-09-05)
Runs when the session ran a development item: the visible conversation shows the owner invoking an
IDEAS todo or naming a `wiki/developments/` page as the plan of record, or a spawn record names this
session (`grep -l <sid> ~/.llm-wiki/spawn-records/run-*.jsonl`, printed with the store's file count and
a grep for another record's known session id as its §11 controls; no store or no session id → say so and
use the conversation test alone). Otherwise print `usage: n/a (not a development run — <the test that
failed>)` and skip.
- **The billed line at each boundary.** From the run's boundary records — the spawn record's
  `phase-boundary` and `decision` events and the hand-off document's trace rows (delegate skill §4) —
  list the billed line at every item or phase boundary, per session as the meter printed it
  (`fable-share.py --session <sid> --lanes auto`, §2a), then the heads' total as a shown sum of those
  session figures, and beside it the run total: the run spend the last boundary or close recorded
  (`run_spend_usd`, every head metered alone plus every lane on the record), never the heads' total
  plus the lanes, since a session figure may already hold some of them (register entry 2026-09-20
  01:09). Records with no boundary figure → meter the session once now and say the boundaries
  carried none; an `unmetered` or `unbilled` exit is quoted as printed, never read as zero or estimated.
- **One waste table, three classes:**
  `| Item | ≈ $ or idle min | Kind | Fix and
  where it lands |`, keyed on what the spend produced — **real** = its output was lost or unused (a lost
  lane, a wrong probe, a stall); **arguable** = its output was used, but a better brief, order or spec
  would have bought it cheaper; **structural** = a cost of the chosen shape (the contract prefix, a
  rewrite after a long hold). Each row names its event (Step 3 clause 1) and carries its figure with its
  derivation — a meter total or per-agent row, a lane's `lane-closed` cost, or `≈` with the arithmetic
  beside it — else `unmeasured`, never a bare number. Its fix lands in exactly one of: a phase of a named
  plan of record, a `known-issues` entry (the register's format, written with `vault-writes.py register add`
  and its required `--why-not-fixed-now`), an IDEAS todo (a proposal — nothing enters
  IDEAS.md unless the owner says "queue it", Step 8), or `accepted` (a cost of the shape, or a fix
  already shipped, named). No waste found → one row saying so and naming what was searched (the billed
  line's `rewrites` and reason tally, the trace's idle minutes and denials), since a zero-findings claim
  needs its control (§11).
- **The waste fields are read, not recalled (2026-09-05).** Each `phase-boundary` event carries
  `idle_min`, `over_cap_reports`, `denials`, `respawn_cost_usd` and `rewrites`; list each as its own
  row with the figure the field holds and the event it came from — the field is the source, never a
  memory of the run — and where an event omits one, write `field absent` rather than `0`, since a
  missing field and a measured zero are different claims. The run's `gate` events carry the head's
  context at each item, so context per item is read off them as the delta between consecutive gates
  rather than estimated; a run with no `gate` events says so and drops that column.
- **A candidate like any other.** The table takes Step 3's bar, the 5b critique and the Step 6 preview,
  and its destination is the run's record page in `wiki/developments/` (Step 4). The `--yes` rules below
  apply unchanged: that page is never written under `--yes`, so an auto-approved run reports the table
  and says it waits for the owner.

### Step 3 — Apply the bar, then keep only what matters
**The bar is deliberately narrow: the unrecorded essentials, not everything noticed.** A long session
generates dozens of small observations. The three clauses below keep the lessons, the Handback keeps
the owner's part to what needs him, and no number cuts a survivor.

A candidate survives only if all three hold:
1. **Evidenced** — it points at something that actually happened here: a command and its output, a
   correction, a file read, a review, **or the owner stating a judgement, hunch or preference**. The
   owner voicing an intuition *is* the event, and it is recordable — marked as a hypothesis and graded
   honestly by §4.6, not discarded for lacking proof. What fails this clause is *the agent's* own
   generality with no event behind it.
2. **Not already recorded** — check *everywhere* it could already live before proposing it: the
   destination page, `known-issues.md`, the relevant `developments/` doc, and a `grep` of `wiki/` for
   the claim. **Open every hit.** A `grep -l` answers "does this string occur", never "is this idea
   recorded", and the filename it returns often looks unrelated to the candidate — an unopened hit
   can be the one page already carrying the candidate's entire argument, and the candidate is then
   proposed as novel. A hit that is not opened leaves the candidate *unresolved*, not clear. A content-mode search prints `[Omitted long matching line]` for a line over about 500 characters: that is a hit, so read the line by number. **Stamp each dedup probe with the time it ran (2026-09-06):** a reflect run over a session that
   edited the vault is checking a moving surface, and a candidate can be fixed by the same run that
   raised it, and a critic can spend its budget refuting defects that no longer exist. The stamp is what lets a later reader tell a stale candidate from a
   wrong one. This is also what stops repeat runs re-proposing the same thing; there is no session
   cursor for proposals, and none can be built (the log carries no clock). Check against the files on disk, never the copy of
   `CLAUDE.md` or `CUSTOMISATION.md` injected into your context: a helper agent's injected copy is the
   head's session-start snapshot, so it can lack edits made since.
3. **Load-bearing** — one decidable question: *would a future session do the work worse without it?*
   That covers both halves — repeating a mistake, redoing work or answering wrongly, **and** missing a
   better approach, a known preference, or a direction already decided. If the honest answer is no, it
   is an observation, not a lesson. "Interesting" is not the bar; "would change what a future session
   does" is.

**Stored is not recorded.** A lesson about doing something, stored only where no reader reads it at its
moment (a notes page, a run page, a report), counts as not yet recorded and goes on to Step 4 as new.

**Missed moments.** Print the `## Experience` section of `wiki/index.md`, one line per feature with a
page, and open a page only when a candidate routes to it or a suspected case below concerns it. A
moment of a listed feature with no use note after it is a suspected miss; a use note with no such
moment is a suspected false trigger. Each is a candidate for the independent check, never a conclusion
from a keyword.

**Then rank and merge.** Order the survivors by the third test and report every one.
Where several candidates are variations of one underlying point, merge them and propose the general
form once — three symptoms of one fault are one lesson. End every survivor in the same pass: applied
where the mode admits it, registered with the reason that blocks it, or dropped with the reason it is
not worth doing, so that none rests only in a reply.

**Scope.** `--all` and instructions like "capture everything" or "don't filter" change no test: the
evidence, deduplication and load-bearing clauses stay the candidate bar whatever the flag.

**Self-conduct.** A lesson about the agent's own behaviour is a candidate only if it **names the external
mechanism that caught it** — a printed control, a failing test, an owner correction, a reviewer. An
unwitnessed self-assessment has no witness and does not survive step 3.

**Probe discipline (2026-08-27).** A dedup grep never carries an exclusion filter — one can filter out
 the very record that makes a candidate redundant, manufacturing false novelty. And a probe's control is never
the claim under test: pair every 0-hit with a positive control that hits on the same surface (§11),
phrased in the subject's own vocabulary — a path or name as the checked text spells it, never as the
checker would spell it; a spelling mismatch must not turn a present record into a false absence.

### Step 4 — Route it
In priority order. Say which rule sent it there.

| Destination | When | Note |
|---|---|---|
| A **rule** — `CLAUDE.md`, `CUSTOMISATION.md` or a skill | The lesson generalises, **and** it can tighten or replace an existing line | Contracts and skills are the surfaces actually read. But a rule that only *adds* a line feeds the always-on ratchet: report the byte delta and prefer a tightening. In a user's copy the core is read-only (CLAUDE.md §12): a rule for it goes to a skill of the user's own (a `my-` name) or to `CUSTOMISATION.md`, and a lesson for the core becomes a suggestion (the `suggest` skill) |
| An **experience page** — `wiki/experience/<feature>.md` | A lesson about how one feature should decide next time, applied case by case | A checked `lesson` entry on an existing page, within the bound (`--yes` section). No page yet: one Approve line carrying the page and its pointer together, never a page alone (Step 7). An `owner` entry changes under CLAUDE.md §12, never here. In a user's copy the pointer goes in a skill of the user's own or `CUSTOMISATION.md`, since the core is read-only |
| A **wiki page** (`concepts/`, `entities/`, `tools/`, `models/`, `benchmarks/`, `user/`) | Domain or research knowledge | New page or an addition to an existing one. `user/` is the owner's to curate — propose, never auto-write |
| A **`notes-*` synthesis** | A reusable procedure or a cross-page conclusion | `type: synthesis`, kebab-case, `notes-` prefix, `## Sources Used`, and `sources:` in frontmatter |
| `known-issues.md` | A framework defect that a named reason blocks from being fixed now (CLAUDE.md §12: fix it now if you can) | The register's own entry format |
| The run's record page in `developments/` | The Step 2b usage-and-waste table of a development run | An append to the page holding the run's trace or design; owner-approved, never under `--yes` |
| **Discard** | Fails the bar, or is already recorded | Report it as discarded and why — a silent drop reads as "nothing found" |

**Reaches.** Each lesson about doing something names the reader and step that read its destination at
its moment. If none reads it then, route it again. Knowledge and working-context candidates keep their
own routing tests and show `not a doing lesson`.

**Contradictions.** A candidate that conflicts with something a page already claims never silently
overwrites it. Add a `## Conflicts / Open Questions` block keeping both statements and contrasting them
(CLAUDE.md §4.4), and say so at the preview. This is the common shape for an owner correction that
disagrees with a sourced claim.

**Sources.** A conversation here almost always rests on wiki pages, so cite them: `## Sources Used` plus
`sources:` in frontmatter. Where a finding is genuinely original with nothing prior to cite, that is a
legitimate page — say so plainly and let §4.6 grade it.

### Step 5 — Grade and attribute
**No confidence rule of its own.** Apply CLAUDE.md §4.6 (the slice: the schema slice's section 4.6,
explained in `contract/confidence-rubric.md` where present) to the evidence and to how the speaker knows
it, never to the speaker's standing in the session: the owner's own work is `high` by default and drops
if they state uncertainty; an inference that follows directly from an `authoritative` page carries that
page's support within its own page's cap (compiled and agent-derived pages never above `high`); an
extrapolation beyond the evidence is `very-low`. Record **provenance** in the page — what the claim rests
on — so a later reader can tell.

### Step 5b — Independent critique (default-on)
Before the preview, brief a subagent to **refute** the candidate table: per candidate — is the evidence
a real event in the recorded span, is it genuinely unrecorded (re-run the Step 3 destination checks),
is it load-bearing, and does a self-conduct item name a true external witness? For each lesson about
doing something, test Reaches and that a proposed pointer precedes its decision. For a repeat, say
whether the page was not read, read and not followed, or the evidence is insufficient. For a suspected
miss or false trigger, return not read, read with its note missing, no moment, or unresolved with the
missing evidence. Quote the deciding evidence. A refuted candidate
moves to "seen, not proposed" with the refutation as its reason; an arguable refutation stays proposed
with the objection attached. **A refuted candidate's defensible residue is a NEW candidate**: it
re-enters at Step 3 and waits for the Step 6 preview like any other — never a direct write, however
broad the standing go (№103 session,
recorded 2026-08-28). This is the bounded per-run witness self-reflection lacks (the
cross-session form is `## Cross-reflection` below). `--no-critic` skips it and the preview says "critic: skipped"; where the
harness offers no subagent mechanism, say "critic: unavailable". **The critic filters proposals; it
never approves writes.** The head judges a checked lesson within the bound; everything else still
terminates at the owner. A skipped or unavailable critic, an unanswered experience question or an
arguable refutation holds the lesson for the owner's yes, so that no unchecked entry steers a later
decision, and the text written is the text the checker read.

### Step 6 — Preview, and get approval for what needs it
One table, always, before any write:

```
Reflect — visible from turn N ("<first few words>"); earlier turns may have been compacted.
| # | Candidate | Evidence | Reaches | → Destination | Tier | Edit |
Seen, not proposed (3): <one line each, with its reason>
Discarded: 2 (already recorded ×1, no event behind it ×1)
Proposed rules: 1 · always-on cost +180 bytes
```

`Reaches` names a lesson's reader and step, or says `not a doing lesson`. An experience lesson the bound
admits reads `N approve — <reason>; applied under the experience bound`.

**The preview leads with the head's recommendation** (owner instruction 2026-09-06): one line per
item — approve · strike · defer, each with its concise reason — printed before the approval
question, so the owner can accept in a word; the recommendation is the head's, never the critic's,
and it changes nothing about who approves. **The line is style-invariant** (owner ruling 2026-09-07:
a style chooses the form of an obligation, never its presence): under `brief` and `shortest` it
gives a concise reason per item (`1 approve — repeat`, `2 strike — already recorded`), never to a
bare verdict in a column and never absent; a style's `Test:` bounds content, never an obligation's
presence (CUSTOMISATION `## Output styles`). The Stop-hook check that logs its absence, warn-only,
is recorded on the per-reply contract enforcement page (`reflect-preview`).
The owner approves per item ("1 and 3", "all but 2"). **Nothing is written without approval**, except
under `--yes` below and the experience bound. One exception is a duty, not a licence: a defect the run itself finds is registered
under CLAUDE.md §12 with the pass whatever else is approved, listed in the preview as `register (§12)` so
the owner can strike it (owner-approved, cross-reflection XR-2, written 2026-09-05 20:27 BST).

**Experience pages.** A lesson changes by aiMyth's judgement once a reflection found it and its
independent checker failed to refute it, so the head applies it within the experience bound (`--yes`
section) and lists it under Undo if you disagree, with its evidence and exact reverse edit. A lesson the
head is unsure of goes under Decide instead. What each mode admits:

| Mode | Automatic experience writes | The rest |
|---|---|---|
| Attended `/reflect`, with its critic | Checked lessons, within the bound | Preview and approval as above |
| An attended session's own cross-reflection with `--yes`, or its eligible successor | Checked lessons, within the bound | The reflector proposes; the head re-verifies and writes |
| A hands-off close with `--yes` | Checked lessons, within the bound | Its `wiki/syntheses/` append bound stands beside it; checked lessons are listed in the morning report under Undo if you disagree, what the bound excludes waits there under Approve with its exact edit, and a hands-off close records a waiting lesson there, not in the register |
| A hands-off close without `--yes` | None | The whole table goes to the morning report, each lesson under Approve with its exact edit, and a waiting lesson is recorded there, not in the register |
| Any other run, such as another session's cross run, a read-only reflector lane, a headless head without `--yes`, or a run with `--no-critic` | None | Findings and exact proposals, which prevents applying a lesson without its required authority or check |

The register duty above also takes a lesson that must wait (a new page's yes, his decision, a missing
grant or input): one entry per feature, in the same pass, listed as `register (§12)`, so nothing rests
only in a reply (widened to waiting lessons on 7 November 2026, provisional).

### Step 7 — Write, log, report
- Write the approved items and what Step 6's modes admit, reading each write back. Every new page gets `## Related` and an `index.md` entry (§4.4, §5).
- **Log by what changed, never by which command ran**: `synthesis` for knowledge written into the wiki,
  `framework` for a contract or `developments/` change, nothing for a register append (§12 exempts it).
  A run that changes nothing logs nothing.
- **A new experience page, approved with its pointer.** Create both in one pass, from
  `.claude/skills/reflect/experience-page-template.md`, filling its placeholders and keeping its fixed
  words. The pointer is one sentence at the deciding step, under its Markdown heading, inside a
  vault-local block in a shipped file: `**Experience:** before <the decision>, and before changing how
  it is made, read `wiki/experience/<feature>.md` whole.` Where no step reliably runs at the moment,
  it is one always-on line in `CUSTOMISATION.md`, under CLAUDE.md §12's central rule. Judge `confidence:` and stamp `audited:`; keep
  `sources:` and `## Sources Used` to the first entry's evidence; start `Measures` with `reach changed`,
  `entry added`, `uses 0 and repeats 0 since` the creation date and `last label E1`, the probe reading
  `not yet run` until it runs; add the page's line under `## Experience` in `index.md`, naming its
  moment, since a reflection routes by that line; log the pair as `framework`. A reflection's automatic
  bound creates neither a page nor a pointer.
- **Experience writes.** One anchored edit inside `## Rules`, by the bound. Re-judge `confidence:`, stamp
  `audited:`, and keep `sources:` and `## Sources Used` to the evidence the remaining entries cite. An
  addition moves `entry added` and `last label`, and a label is never reused. A retirement removes the
  entry and keeps its complete text, date and reason in the log entry. Log a lesson change as
  `synthesis`. An `owner` change is outside this step: its exact text goes to him (CLAUDE.md §12).
- **Repeats and uses.** A repeat the checker confirms adds one to `repeats` on the `Measures` line in the
  same pass, as a records-only edit, which changes no claim and stamps neither `confidence:` nor
  `audited:`. Uses are counted monthly by deep-lint (Step 4a), never here.
- Report what was written, where, at what tier, and what was discarded.
- **Every write carries its clock time** (owner instruction 2026-09-05): beside the date, the local time of the
  write and the run or lane id — on a register entry's `Where observed` line, in a rule addition's dated note,
  in an appended block's heading — so a parallel session's earlier fix or later edit can be ordered against it;
  an agent that finds the item already fixed reads the two stamps and keeps the later state.
- **A fix handed to another session** is recorded on its register entry with the taking run and that
  run's gate state, clock-stamped; if that gate later refuses, the entry reverts to open with the refusal
  dated, so a claimed-but-gated fix never reads as done (cross-reflection XR-2, written 2026-09-05 20:27 BST).

### Step 8 — Recommend, don't queue (owner-added 2026-08-27)
Close the report with next-action recommendations derived ONLY from what this run shipped, corrected or
left undecided — an open decision surfaced, a stale premise fixed, a watch worth setting. A short ranked
list: action · whose decision it is · when it becomes urgent. Where a written page ships, mirror it as a
`## Next` section **worded as recommendations with their reasons** — findings, never instructions to
future agents (§2.2 discipline applies to pages as to reports). Nothing self-executes; nothing enters
IDEAS.md unless the owner says "queue it" (normal IDEAS rules then apply). A run with nothing genuinely
open recommends nothing — no forced next.

## Cross-reflection (`--cross`) — one agent reflects on another's session

**Trigger, explicit only:** `/reflect --cross <transcript-path | session-id>`, or the owner accepting
a workflow-end proposal (the delegate skill §5 owns that policy: the head may propose once, cost
declared first, never auto-run; the run's log entry records whether one was proposed — `proposed`
or `not eligible`, 2026-08-30 — an accepted proposal being traced by the cross run's own entry). **Target:** a finished session's transcript, or the current
session's transcript as of spawn — the live-write race is declared in the report; for the current
session (a self-cross run) the head freezes a `/tmp` copy of the transcript and grants the copy
alone, because the live file keeps growing while the lane reads it. The timing of the frozen
copy and any follow-up reflection follows CUSTOMISATION.md's closing rule in
"Session hand-off after a queue item". The close's follow-up check lists the owner turns with
`handsoff.py extract-transcript --session <id>`, once for each session the close covers; its extraction
reads both carriers, typed user records and `queued_command` attachments.

**Mechanism.** The head agent spawns a READ-ONLY reflector lane (delegate skill,
`templates/brief-reflector.md`) that applies Steps 1–5, except 2b (head-only), to the target transcript. The lane extracts
the transcript's human turns and assistant prose (tool-result records excluded) to /tmp and reads
that extraction in full, reporting "read k of N turns". **Horizon control** (replaces Step 2's
nonce, which only proves one's *own* session): target file exists and is non-zero; human-turn count
verified against the extraction; coverage declared, never claimed complete.

**Witness ruling.** Proposer ≠ behaving agent, so a transcript-grounded observation (file + line)
IS the external witness Step 3's self-conduct rule demands — cross mode is where unwitnessed
conduct faults become recordable.

**Scope v1:** the head transcript only; lane-internal events appear only as the lane reports
embedded in it. **Output:** findings, never writes — the FULL named candidate table including every
discard with the page that killed it (an aggregate count hides the dedup evidence). Step 5b is not
re-run on cross output — duplicative cost, since the head's re-verify widens instead: dedup checks
AND a re-read of each cited transcript span before the preview, done by a read-only checking helper that quotes each span's deciding line, under CUSTOMISATION.md's Transcripts rule, using a helper independent of the reflection; that helper also answers Step 5b's experience questions, and a lesson it has not answered is not applied; before applying an item the head lists
the fresh dedup probe it ran for it and the span it re-read, and a correction to an existing line is
logged as its own synthesis entry. Owner approval stays line-by-line for what needs it;
the head writes approved items and what the experience bound admits under Step 7, each write clock-stamped. **`--yes` never applies to cross runs.** **Qualified 2026-09-06 (owner ruling):** it does apply to the hands-off boundary form, where a reflector lane reads the head's OWN session at the head's request — the lane proposes, the head re-verifies each proposal (dedup, evidence) and writes only within the `--yes` path bounds (design D36). **Qualified 2026-10-01 (owner ruling), with its reach settled on 10 October 2026 (a provisional choice under the owner's rule on provisional choices):** an attended session's own cross-reflection may run with `--yes` under the same path bounds, and so may that cross-reflection when the session's successor runs it over the session's transcript (for example because the session's context was full); the head re-verifies each proposal as above, and every register entry it writes under CLAUDE.md §12 is listed in its report so the owner can strike it.

**Hands-off boundaries (2026-09-05, hands-off design D36; `--yes` admitted for this form by owner
ruling 2026-09-06).** At every phase boundary of a hands-off run the head does not run this skill in
its own context. It builds the lane's inputs with `handsoff.py reflect-inputs --run R --session SID
--out DIR` (a directory outside the store): the extraction of its own transcript (the human turns and
the assistant prose, a count file beside them), Step 2b's table rendered from the run record alone
(every figure read from a field, none recalled, so Step 2b's head-only rule is satisfied by the
primitive rather than by the head's memory), and a filtered copy of the record. It then spawns a
reflector lane (headless, `lane.py`, fenced
Bash, the routing's model) granted DIR alone beside the wiki and this skill, and it receives the full
named candidate table including every discard. Before applying any item the head re-verifies it
exactly as this section prescribes: the dedup checks and a re-read of the cited transcript span. With
`--yes` the head then writes the items that pass, inside the `--yes` path bounds below and nowhere
else (create-and-append inside `wiki/`, the experience bound's lesson edits, plus the corrections of aiMyth's own working records the
bounds name; never `developments/`, `known-issues.md` or any other file outside the wiki), logging
each write as `synthesis`; every item the bounds exclude, and every item that
fails re-verification, goes to the run's morning report with the full named table for the owner's
line-by-line approval. With `--yes` the experience bound applies to this form as Step 6's table sets it: checked lessons are applied and listed in the morning report under Undo if you disagree; what the bound excludes goes to the morning
report under Approve, each with its exact edit, for the session that walks it to apply on his yes.
Without `--yes` the head applies nothing and the whole table goes to the
morning report. An ineligible cross run has no automatic experience grant, which prevents applying
another session's lessons without its required authority. Any other cross run over another session's transcript stays outside `--yes` whatever the run.

## `--yes` — opt-in auto-approval (off by default)
Set per run (`/reflect --yes`) or as a standing owner setting. It means **writing without waiting, never
writing without telling**: the step 6 table and the step 7 report still appear.

Bounded **by path, and on experience pages by label and field**, never by judgement:
- **May**: create pages in `wiki/concepts/`, `wiki/entities/`, `wiki/tools/`, `wiki/models/`,
  `wiki/benchmarks/`, `wiki/syntheses/`; **append** to an existing wiki page outside `wiki/experience/`,
  or to `index.md`;
  **correct** aiMyth's own working records outside the wiki (a hand-off, a run's stage or status file)
  where a checked finding shows them wrong, each correction listed in the report for the owner to undo.
- **The experience bound** (in the modes of Step 6): on an existing page in `wiki/experience/`,
  add, reword or retire a `lesson` entry by one anchored edit inside `## Rules`, once the independent
  check failed to refute it, with Step 7's duties and records, and nothing else on the page. No automatic
  write creates a page or a pointer, edits an `owner` entry, changes the fixed preamble, removes a section
  or retires a page's last entry, which goes to the owner as the page's joint retirement with its
  pointer. A contradiction takes CLAUDE.md §4.4's block through his word, never this bound.
- **Never**: `wiki/user/` (the owner curates it, CLAUDE.md §1) · `wiki/developments/` and
  `known-issues.md` (a framework surface, and a register append logs nothing, so an unapproved one would
  leave no trace at all) · `CLAUDE.md`, `.claude/**`, `CUSTOMISATION.md`, `MANUAL.md`, `README.md` ·
  anything else outside `wiki/` · **rewriting** any existing page — appends only, the experience bound
  apart.
- Every auto-approved write **is logged**, so it is always traceable.

> **One stated judgement call.** `wiki/syntheses/` also carries `query` Step 5's ask. The owner's standing
> opt-in *is* the consent that ask exists to collect, given in advance, and it binds **only reflect's own
> writes** — `query` keeps asking when `query` runs. This is stated here in plain sight rather than
> applied silently.

## Hard constraints
- **Explicit trigger only.** Never automatic; passive context never fires it.
- **Never claim a complete sweep.** Only a bounded one, with the boundary named.
- **Never invent a lesson.** Every candidate carries the event it came from.
- **The bar stays narrow.** The unrecorded essentials only, every survivor reported; no instruction
  widens the bar itself.
- **The in-flight lane is not weakened.** This is not a place to defer to: if something is worth filing
  while working, file it then, exactly as now.
- **Approval terminates at the owner.** A subagent may propose; it may never approve. A `lesson` needs
  the independent check and the head's judgement within the experience bound; an `owner` entry changes
  only under CLAUDE.md §12, which protects his rule text from an automatic rewrite.
- Write in British/UK English.

