#!/usr/bin/env python3
"""handsoff.py — the hands-off run's head-side primitives (delegate skill, hands-off mode).

One script, one line per action; every write is a record event or a named hand-off section.
Run store: LLM_WIKI_STORE (default ~/.llm-wiki, resolved to its real path), file
spawn-records/<run>.jsonl; the hand-off document is the path the run's run-open event names.

Subcommands
  run-open     record the run's opening: session, head, regime, hand-off path, envelope, pid,
               and --session-kind seed|head written as `session_kind` (default head; seed marks
               a launcher's placeholder session, which no reader counts as a head that ran, and
               records no pid unless --pid is given, since a seed never runs); writes the grants
               file and the state directory's run-<sid> pointer (D34), warns when the hand-off's
               `## Trace` section holds no table and seeds the five-column header under it (the
               boundary appends its rows there), does the same for a `## Findings ledger`
               section holding prose and no table (the ledger's header seeded under the heading,
               the prose kept below; register entry 2026-09-14 19:35), and opens the console
               window unless --viewer none (the console window below)
  run-resume   a later head (a successor, or a pasted resume prompt) records itself likewise,
               and writes the same two files (a list it is not given is carried from the file);
               refused with exit 9 while another live head holds the run (two heads, below)
  boundary     meter, compute the five waste fields, measure the head's context, append the
               phase-boundary event, add the trace row, refresh the morning report's figures,
               checkpoint-commit (--commit MSG)
  ledger       one row in the hand-off's findings ledger plus an observation event; a
               `## Findings ledger` section that holds prose and no table gets the table
               created directly under its heading first, the prose kept below it, and one line
               says so (as `decision` does; register entry 2026-09-14 19:35); a hand-off with no
               such heading, two such headings
               (whether or not the first holds a table; both lines named), or pipe-led lines
               that make no table is refused as before (exit 2, nothing written);
               `--observation "<what>"` instead appends the observation alone, with no ledger
               row, to any record that exists (the plain-lane-run shape below)
  decision     an owner-behalf decision before the act: the `decision` event (phase, what,
               grant) and one findings-ledger row in one call (the decision subcommand below)
  gate         fit and envelope check before an item: a gate event; exit 4 when armed and the
               next item does not fit under the belt (memory + its estimated cost + the pack allowance; the 80 % mark only where no figure exists); exit 5 on the envelope
               `which: envelope` when the run's spend has reached the run's envelope (the latest
               `envelope` event's figure, else run-open's envelope_usd: the envelope policy
               below); the unmetered policy below; the first gate
               of a session records the orientation cost (D41), null after a resume — a
               head-resumed event, or a run-resume naming the session of the head event before
               it WHEN that session already gated, either of which leaves the whole session in
               the transcript's first call (a successor's own first gate stays measured); exit 6
               holds the item while the decisions channel carries an unread AUTHOR observation
               or a changed --decisions-file (below), and exit 9 refuses the caller while another
               live head holds the run (two heads, below)
  raise-envelope
               the owner's top-up: an `envelope` event with the new figure, which the gate, the
               successor and the supervisor read as the run's envelope (the envelope policy
               below)
  handoff      rewrite named sections or morning-report bullets, atomically; --final records
               head-exit with --band and requires the next-task pack (D41), and prints the pid
               it wrote and why (pid discovery below); where the record already holds this
               stop's head-exit (a `head exited` observation after the head's last start, a
               head-resumed included, and a head-exit after that start, the supervisor's or
               a repair's) it writes none and prints `head-exit already recorded`, the check
               repeated under a lock on the record just before the append. --inflight and
               --inflight-file stamp the pack with its age; --inflight-from-record re-derives
               `## In flight` from the run record (the pack-age guard below)
  successor    called BY the exiting head: sizes the cap from the envelope minus recorded spend
               when the record's last head-exit is a seed exit (`budget_src: envelope (seed)`,
               register entry 2026-09-07, since a seed session has no transcript to meter);
               records head-exit when missing (refused while a head-successor follows the
               last head-exit; where the supervisor's `head exited` observation follows that
               head-successor with no head-exit after it, an older record, the refusal names
               the missing head-exit and the repair `handoff --final --band limit`), then
               starts a
               DETACHED starter that waits for the predecessor to die, starts the successor
               head (claude -p, the resume prompt on standard input) and stays as its
               supervisor (D30); returns at once. A launcher-supplied pid that is the caller's
               own long-lived ancestor is refused, and a seed predecessor with no pid is not
               waited on (the seed pid below); --pack-fresh records the launcher's word that
               the hand-off is current (the pack-age guard below)
  supervise    attach the same supervisor to a head already running (the head calls it about
               itself); detaches at once and returns one line
  resume-head  after a limit the run stood down on (D42): resume the record's last head in
               place, armed, evented and supervised (the owner's command after the reset);
               detaches at once; --pack-fresh as for successor
  watch        the read-only console for a run: header, items, lanes, timeline, feed; `q` quits
               and `r` resumes a stopped head. Writes only the timeline report, at the close
  heartbeat    an attended head's idle-cache beat (D32): a background call that returns after
               --minutes with one line, so the harness's re-invocation refreshes the cache;
               never for a -p head, which has no idle state
  wait-reset   the supervisor's reset wait as a command, kept for --dry-run parser checks and
               for a hand-run wait; no longer a head-side blocking call (D28). It sleeps to the
               reset time the stop text names and sends no probe unless --probe is passed
  close        final meter, run-close, the heartbeat stop marker, commit and push on grant; on a
               plain record (below) the run-close is written from the lane events alone;
               decisions_on_owner_behalf counts the `decision` events and the ledger
               observations whose what opens with the word decision; held with exit 6 by the
               decisions channel as gate is (below)
  run-is-closed
               exit 0 when the record carries a run-close, 1 when it does not, 2 with no record
               (for a wrapper that warns before it spawns into a closed run)
  launch-check the launch kit's start confirmation (register entry 2026-09-17
               16:32: a hand-written single read raced the detached starter): polls the record
               to a deadline (--wait, default LAUNCH_CHECK_WAIT_S) for a head start — a
               head-successor, a head-resumed, or a run-open or run-resume carrying a pid —
               whose pid is alive and whose process started when the event says (a reused pid
               is named, never counted, and a start whose age or timestamp cannot be read is
               `pid identity unverifiable`, never started); every ps probe bounded by the lower
               of its own cap and the budget left of the one deadline, which successive probes
               share; one line per outcome; exit 0 started, 1 not started (the
               deadline, a run-close, an aborted starter, a dead or exited head, a reused or
               unverifiable pid, a malformed pid named), 2 on a premise (no record, no run-open,
               or run from inside the run's own head without --detach-safe: a head that called
               successor about itself must never wait on its own replacement, since the starter
               waits for that head to exit)
  open-console the run's console window on demand: one when none is alive (the one-window rule
               below); --check opens nothing and prints the live console's pid, or NO CONSOLE
               with exit 1
  run-spend    the run's spend BY RUN (the run figure below): one line per head and per lane
               and a summary line; exit 1 when the figure is a floor, 2 on a premise failure
  waste-table  Step 2b's usage-and-waste table rendered from the run record alone (D36)
  extract-transcript
               the head's own transcript extracted for a reflector lane (D36)
  reflect-inputs
               that reflector lane's whole input set in one directory: the extraction, the
               waste table and a filtered copy of the run record (D36)
  hold         keep a finished lane warm (the held lanes below): a `hold` event naming the lane,
               its wrapper, the cap and the lane's last call; --renew extends an open hold with
               a fresh count; --beat-after-s sets the interval (the rehearsal of a fresh run
               uses the 50-minute default; a shorter value is for a suite or a check by hand)
  release      end a lane's hold by hand: a `hold-ended` event with reason `released`
  hold-verdict what each of the run's beats did to the cache, read from the record alone and
               read-only: per beat the lane, the harness, the beat number, ok, config_match, the
               usage figures and the cached share, then `hit` where the cached read is at least
               HOLD_VERDICT_FRACTION of the call's whole input, `rewrite` where the uncached part
               is, else `open` with the figures; a beat that failed, carries no usage or is
               missing a field is `open (unmeasured: what is missing)`. The fraction is the
               closing meter's own rewrite rule mirrored, never a new number. Exit 0 every beat
               hit, 1 any rewrite, 2 any open or no beat on the record. This is the acceptance
               evidence for a Codex beat, whose usage the closing meter does not read

Held lanes. A finished lane the head
still expects to resume — a chair between rounds, a builder awaiting its critic — is held rather
than left to go cold: `hold --run R --lane L [--cap N]` records the hold, and the supervisor
services every open hold at each tick of its wait on the head. HOLD_BEAT_S (50 minutes) after
the lane's last call it issues a no-work resume through the lane's OWN wrapper — `lane.py resume
--beat` for a Claude lane, `codex-lane.py resume --beat` for a Codex lane — whose beat carries
the spawn's model, effort and configuration byte for byte (the wrapper compares the resolved
command line's `config_sha256` with the lane-open's and refuses a beat that differs), sends the
fixed line `beat: reply with the single word ok`, writes no report and no pass file, and records
one `hold-beat` event with the call's usage, so the closing meter's rewrite causes show whether
the cache held (a beat that hits reads its context from the cache; one that misses is a rewrite).
The lane's last call is read per wrapper: a Claude lane's is the last assistant record of its
transcript; a Codex lane's the last event of its session file under the Codex home, else the
mtime of the wrapper's own events log in the store; a later `hold-beat` moves the reference, so
a failed beat is never retried within the tick and the next attempt waits a full interval. The
hold ends with `hold-ended` and one of five reasons: `released` (the head's `release`), `cap`
(the beats issued reached the cap when the next fell due; `hold --renew [--cap N]` starts a fresh
count), `lane-closed` (the lane ran again and closed with a class a beat cannot re-enter — a
limit, a budget stop, a kill), `run-close` (`close` ends every open hold) and `stood-down` (the
supervisor stood down, so no tick would service the hold). A hold is refused, with nothing
written, on a record with no run-open, a run whose supervisor has stood down or been asked to
stop (nothing would service it), a closed run, an unknown lane, a lane still running, a close
outside HOLDABLE_EXITS, a lane whose last call — or last SUCCESSFUL beat — is past the resume
window (nothing is warm), a lane already held unless --renew, a --cap outside 1 to HOLD_CAP_MAX
and a --beat-after-s outside 1 s to the resume window. It warns, and proceeds, where no
supervisor is on the record yet (the re-attach case) or the attached one predates this mechanism,
and where the lane's own `cache_write_tier` is shorter than the interval asks. While a held lane
runs again no beat is issued (two processes must never share one session), and the
re-read that precedes every beat re-checks that the lane is still closed. The watcher draws a
held lane beside running and closed.

The plain-lane-run shape. A record opened by the lane wrapper alone carries lane events and no
`run-open`: an attended session spawned lanes, so there is no hands-off run, no head session on
the record, no envelope and no hand-off document. Three primitives accept it, and the test is
always the record's own events, never the run's name. `ledger --observation "<what>"` appends one
observation and no ledger row; the plain `ledger` still refuses (no hand-off to write a row in)
and its refusal names `--observation`. `close` writes a `run-close` carrying `shape:
"plain-lane-run"`, the lanes counted by exit class and the spend summed from the `lane-closed`
events' own costs, with no head meter, no hand-off rewrite and no hand-off row; `--commit` and
`--push` are refused there (exit 2, nothing written), since neither has a head's grant behind it.
`watch --run` renders the lanes, the timeline and the feed with no items panel. Every other
primitive needs the head a `run-open` names and refuses as before.

The boundary reflection (D36). At a hands-off boundary the head reflects in a lane rather than
in its own context, and two primitives feed that lane. `waste-table --run R` renders the reflect
skill's Step 2b table from `<store>/spawn-records/<run>.jsonl` — no recalled figure, and the one
meter call is the whole-run rows' own (T6 of the token-efficiency findings, 2026-09-07: each head
metered over the RUN's window, run-open to run-close or to the record's last event, by the
meter's `--start`/`--end`, so a session shared with attended work is never counted whole against
one run; `--no-meter` renders from the record alone and `--meter-line SID=LINE` stands in for one
head). Where that meter gives no figure a head's row falls back to the LATER of its last boundary
billed line and its `head-exit.spent_usd`, so a head that exited without a boundary loses no
spend, and the envelope base is printed beside the total (register entry 2026-09-06). Head
sessions are counted by distinct session id, a session `run-open --session-kind seed` marks is
skipped as a launcher's placeholder and named once in the header's `seed (skipped)` line (T7),
and a recorded limit wait (stop-condition to head-resumed) takes a structural row of its own. The
rest is read from fields: one row per waste field per phase-boundary event (each naming its event
by from → to and timestamp) — the preview row carrying the CUT TAIL alone, the words omitted
from a requested preview at 1.3 tokens per word (set by judgement, unmeasured) and the model's
output rate from prices.json, never the lane's whole cost (T8) — the billed line at every boundary, context
per item as the delta between consecutive gate events, the
orientation cost per head from the first gate's `orientation_tokens` (D41), and the lost-lane
cost of every lane-closed whose exit class is not `completed`. A field the event does not carry
is `field absent`, never 0; a field that is there and null is `unmeasured`; every figure carries
its derivation. Kinds are assigned mechanically and the legend line says how. When no row
carries a measured cost the table ends with a `no waste found` row naming what was searched,
which is the zero-findings control. A record with no phase-boundary events still renders the
gate, orientation and lane rows and says `no phase-boundary events`; no record at all is a
premise failure. Output goes to --out (default `<store>/spawn-records/<run>-waste-table.md`) and
one line to stdout; --dry-run prints the counts and writes nothing.
`extract-transcript --session SID` writes `turns.md` (the human turns, the assistant prose and
the assistant's tool CALLS, each headed `## turn N · role · timestamp`) and `counts.json` (the
`read k of N` figure the reflector verifies) under --out (default `/tmp/aimyth-extract-<sid>/`).
An assistant record holding only tool calls is a tool-call turn headed `assistant · tool calls`:
one line per call with the tool's name and the input field naming what it acted on (Bash
`command`, Read/Edit/Write `file_path`, Grep/Glob `pattern`, any other tool its name alone), each
cut at 300 characters; a record holding both prose and calls keeps its prose turn and the lines
go under it. Tool-call records are retained (register entry 2026-09-07).
They are counted under `tool_call_turns`,
so records = extracted + tool_call_turns + every exclusion. Tool RESULTS are never carried:
tool-result records and the two injected user-record classes the reflector template names are
excluded and counted;
`"type":"user"` alone does not mean a human turn. The transcript is found as the gate finds it
(--projects-root overrides the root), the block reader is lane.py's own, and an unparseable line
is counted under `excluded.unparseable` rather than being fatal. Two harness shapes are handled
where they would otherwise read as the head's own words: a resume replay — a whole prior
conversation re-sent as ONE user record, recognised by a turn marker at its opening and at least
two in all, never by its size — is trimmed to the text after its last `User:` marker and read as
a human turn (`notes.replay_trimmed`; a replay with no owner message left is `excluded.replay`);
an assistant record whose model field opens `<synthetic` is the
harness's own stop text and is skipped, counted under `excluded.synthetic`, as the watermark
hook's measure() skips it.
`reflect-inputs --run R --session SID --out DIR` writes that lane's whole input set into DIR and
nothing else: `turns.md` and `counts.json` (the extraction above, same options), `waste-table.md`
(the table above) and `record-filtered.jsonl`, the run record with every observation whose phase
starts `controls` dropped and the keys `controls_checked`, `brief_copy`, `brief` and `plant`
stripped from every event kept. The convention behind the drop is the spawner's control
pre-registration, `handsoff.py ledger --phase controls-<LANE> …`: the reflector is blind to what
the head expected of it, and the filtered copy is written before the `reflect-inputs` event that
records the run, the session, the directory and the counts, so the copy never carries its own
line. An --out inside the run store or the projects root is a premise failure (exit 2), since the
lane is granted DIR alone, and --dry-run prints the same counts, writes nothing and records
nothing. The orientation rows carry one row per session id — a head-successor and the run-resume
that follows it are two spans of one session — and a measured figure wins over an unmeasured one.

Meters, waste fields, the extraction and the close, amended 2026-09-13 (register entries named).
The boundary meter (2026-09-09 15:27, 2026-09-10 02:49): fable-share.py prints every refusal on
standard output with standard error empty, so `meter_line` reads both streams for the
no-lane-transcript refusal before it meters the head alone under `--lanes none`, that billed
line ending `· head alone (--lanes none): …`; any other refusal is never retried and the line
reads `failed: exit N · <the meter's own words>`; `boundary --dry-run` prints `meter invoked as
<the command>`. The waste fields (2026-09-07, 2026-09-10 03:05, 2026-09-06): a lane closed with
`total_cost_usd` null (a lane killed with its head) is billed from its own transcript by the
meter (`respawn_src` says `metered (transcript)`), one that cannot be leaves `respawn_cost_usd`
null — `unmeasured`, never $0.00 — and a plan-usage (Codex) lane is counted, never priced;
`limit_cut_resumed_usd`, with `limit_cut_resumed` and `limit_cut_src`, carries the first
attempts of lanes closed `limit` and resumed afterwards, which respawn_cost_usd excludes; and
`head_denials`, with `head_denials_src`, counts the head fence's deny lines in the state
directory's events.log for the span's head sessions, beside the lanes' tool `denials` and never
added to them, null when the log is absent. The boundary line adds `head fence denials N` and,
when any, `limit-cut resumed $X`. The waste table labels the lanes' field `lane tool denials`,
renders rows for the two new fields on boundaries that carry them, bills a lane closed with no
cost from its transcript unless --no-meter, and reads a billed line carried by hand as `session
≈ <n>` or `session USD <n>` into the run total (2026-09-09 15:43). The extraction (2026-09-07,
2026-09-13 03:53) puts every record in exactly one bucket: `excluded` gains `interrupt` and
`other`, `other_types` names each record type `other` holds, and `notes` (`replay_trimmed`,
`injections_cut`, `tool_result_with_text`) are never buckets; turns.md and the command's line
print `Records = … = N, against N records read: reconciles`, else `DOES NOT RECONCILE`; a
closed task-notification span is cut from a user record's text as a system reminder is, and
the owner's words left are a human turn. `close --report PATH` (2026-09-10 17:43) re-reads the
record after the run report was written and, before the commit, adds or replaces one bullet
`Closing meter (handsoff.py close)` carrying the close's billed line under the page's first
`## Spend…` heading and one bullet `Limit stops on the record (handsoff.py close)` under its
first `## Warnings…` heading, naming every limit stop with the head-resumed after it and every
lane closed `limit`; the head's own prose is never rewritten, a named report that is not a file
is refused (exit 2, nothing written), a missing section is named and exits 3 after the close
is written, and a plain lane run's close refuses --report. `head-successor` and `head-resumed`
carry the head's `model` (null when no --model was passed, `model_src` saying so) and `effort`
(2026-09-10 20:29).

One account (D28–D32). The vault runs under one login, so a limit stops the head and every
lane at once and nothing can wait for the reset from inside the session. The supervisor is
the process that started the head (the starter) or one attached with `supervise`: it waits on
its own head's process without bound and with no API call (only the predecessor-pid wait keeps
STARTER_WAIT_S, and the reset wait keeps --max-wait-s), and on exit classifies the stop with
the lane wrapper's own classifier (`classify` and `limit_signal`, imported from lane.py beside
this script; the .out result's subtype and text, the transcript's synthetic zero-usage
record). `handed-over` (a head-exit follows this head's start AND a head-successor follows
that head-exit within the starter's wait: the head left by design and its own `successor`
call owns the next head) and `closed` (a run-close follows) end the supervisor with one line;
a head-exit with no head-successor after that wait means the head died between `handoff
--final` and `successor`, and the supervisor runs the successor path itself (idempotent: the
duplicate guard refuses when a head-successor appears meanwhile). Every head-exit records
`spent_usd`, the session's billed total metered once at exit, and the remainder any next head
is sized at is the envelope minus every head-exit's spent_usd minus the current session's
total — the envelope is never re-granted per head.
`limit` is decided by the run's limit gate — the grants file's `on_limit` (design D42, the
pre-flight's class L): `stop`, the default, stands the supervisor down at once (event
supervisor-stood-down reason limit-stop, exit 0, the hand-off the recovery — the designed
default, never an abort); `resume` (the pre-flight's limit-off) waits: the explicit --reset-at first, else the reset parsed from the stop text; the
sleep runs in SUPERVISE_TICK_S ticks so a run-close written meanwhile ends it, and --max-wait-s
bounds it (successor-aborted, reason reset-timeout). During that wait, and as the last act
before a resume or a successor start, the supervisor stands down when the head transcript
changed (someone continued the session by hand: reason resumed-by-hand) or the marker
<run>-supervisor.stop appeared (`supervise --stop`, or `close`; reason stopped) — design D43,
keyed on the observable, the baseline taken after the stop is classified. THE PROBE IS OPT-IN AND OFF BY DEFAULT
(owner ruling 2026-09-06, CLAUDE.md §11: no agent probes or adjusts to an account limit without
explicit approval): with --probe, and only then, a haiku probe under the same login every
PROBE_INTERVAL_S ends the wait on the first success; the supervisor never passes --probe on its
own, and forwards it to its detached half only when its own caller passed it. Without the flag
and with no reset time to parse there is no wait at all: a stop-condition `which:
limit-unparsed` is recorded and the hand-off is the recovery (the supervisor first writes
a head-exit with band `limit`, `pack: false` beside a `pack_src` naming the supervisor, the
head's context, the spent figure and the pid, each null with a `_src` field naming why where
nothing gives it, so that a successor started by hand passes its premise — register entry
2026-09-14 05:13 — then ends successor-aborted, reason limit-unparsed; wait-reset exits 7 and
writes no head-exit, since a hand-run wait records the stop of any lane and holds no head's
pid). A stop text naming a limit scoped to ONE model (`reached your <model> limit`, `switch to another model`) takes neither the wait nor the probe, since neither can clear it: `which: limit-model` with the scope on the event, reason `limit-model[-<scope>]` after the same head-exit, and the recovery is a successor on a model the account can still run. After the reset a head whose context (its transcript, else the last
gate event) fits the rest of its item under the belt and is cheap to resume (fit-based continuation; the first band edge only where no figure exists) is resumed in place (`claude -p --resume <sid>`, the
resume note on standard input, the same .out, the envelope's remainder as its cap; event
head-resumed) and supervised again; at or above the edge a head-exit with band `limit` is
written and the successor path runs from the hand-off. `budget` (the harness's cap) takes the
same fork with no wait when the remainder (the envelope minus the meter's session total) is
positive, else successor-aborted reason budget (the owner tops up). `error` and a `completed`
head that neither handed over nor closed get one successor from the hand-off under the loop
guards (repeat-exit, successor-cap, unmetered-loop); an error exit's head-exit carries band
`error`. A resume runs only after the process has exited, refuses (duplicate-resume) when a
head-resumed or head-successor already follows this head's start, and is capped at two per
session (RESUME_CAP: a third would-be resume takes the successor path); two consecutive
error or budget stops, in any mix, and two consecutive completed stops (a head that exits
completed with neither a head-exit nor a run-close, whose successor does the same) end in
successor-aborted reason repeat-stop, the successor cap being only the backstop. A head-exit
recording a session that left no transcript (`unmetered (transcript missing …)` with no metered
spend: a seeded record whose head never ran) is not a stop the guard counts (register
2026-09-06), and the waste table leaves that session out of its head count. Without lane.py the supervisor cannot classify: successor-aborted, reason
classifier-missing, and the hand-off is the recovery. The heartbeat is the attended head's
answer to the idle cache: one beat per --minutes of idleness, one-shot, re-armed by the head
in the reply the beat re-invokes; a pid file refuses a second arming while one is alive.

Blocking calls and the shell tool: wait-reset returns `still-running <seconds left>` (exit 8)
after --max-block-s (default 540 s, under the shell tool's 600 s cap) and a hand-run caller
re-issues it. Nothing the head calls blocks: successor and supervise hand their waits to a
detached process, heartbeat is a background call by design, and boundary only runs the meter.

The gate's unmetered policy (amendments N1, F4): no transcript or no usage record → the line
`gate: unmetered (<reason>)`, an observation, the item allowed (exit 0); a gate whose run-spend
figure cannot be computed (nothing metered or recorded: `run_spend_usd` null on its event,
`run_spend_src` naming the failure) is a miss on the same count (2026-09-17), its line ending
`unmetered spend (first miss)`; the SECOND consecutive
unmetered gate of either kind — counted over gate events after the last run-open, run-resume or
head-successor, never record-wide, a measured gate resetting the count — exits 7 with
stop-condition `which: unmetered` when the
session is armed, so the head runs `handoff --final --band unmetered` then `successor`; the
starter refuses (successor-aborted, reason unmetered-loop) when the previous head-exit also
carried band unmetered, so an unmetered fault buys at most one restart. Unarmed, the second
miss is a warning line and exit 0 (soft bands never stop a run, D2); the observation stands.

The gate's envelope policy (register entry 2026-09-07: an envelope stated in the pre-flight and
measured nowhere cannot stop anything). Every gate computes the run's spend against the run's
envelope — the latest `envelope` event's `envelope_usd`, which `raise-envelope` writes, else
run-open's — and prints it on its line as `envelope: $<spent> of $<envelope>, remainder $<r> ·
run: <derivation>`. The spend is the RUN figure (`run_spend`; register entries 2026-09-14 19:35
and 00:06: a session line can read `lanes $0.00` under a successor head that wrote no run-resume,
and a lane closed on its deadline with a null cost is left out of a plain sum): every head
session the record names on a head start
(head-successor, head-resumed, run-resume, run-open; a seed is skipped and named), each metered
alone by its whole transcript (the current head's `head $` taken from a `--meter-line` in
hand), plus every lane on the record — the sum of its lane-closed costs, and where any close of
a Claude lane lacks a cost, the lane is still open, or an open pass follows its last close (a
lane-resumed or a respawn as its latest event), its transcript metered and the LARGER of the
recorded sum and the transcript's figure taken; a lane with two session ids is metered per
transcript and always listed under the floor; a lane with no priced close and no meterable
transcript prints `unmeasured`, never $0.00 (a recorded zero prints `$0.00` beside `recorded`);
and a Codex lane runs on
plan usage: counted, never priced. Nothing depends on which head spawned or resumed a lane or on
a run-resume marker existing. Metered figures are cached per session by transcript size and mtime
in `<store>/spawn-records/<run>-spend-cache.json`, and the meter calls a gate makes beyond the
session's own share RUN_SPEND_BUDGET_S of wall clock. The gate, the boundary and the close carry
the figure on their events as `run_spend_usd` (null when nothing could be metered),
`run_spend_floor` and `run_spend_src`; the boundary and the close print it as `run spend: …` and
the morning report's spend bullet carries `run $<x> of $<envelope>` after the session line, which
stays what the log entries quote; `run-spend --run R` prints the whole derivation. Where a part
could not be metered (no transcript, a meter refusal, the price table missing, a second session id,
the budget spent) or a record line is malformed, the line reads `envelope: at least $<spent> of
$<envelope>, remainder at most $<r>` and the gate treats the floor as the floor it is: it refuses
when the floor is already at or above the envelope. A remainder at or below zero refuses the
item, armed or not, with a stop-condition event — `{"event": "stop-condition", "which":
"envelope", "lane": "head", "action": …, "note": <the figures>}` — and exit 5: the run stops
there, and the owner tops the envelope up with `raise-envelope` before any successor (which
refuses on the same figure), the refusal line naming that command. A record with no envelope
prints `envelope: none` and allows; a run of which no head and no lane could be metered or read
prints `envelope: unmeasured (<reason>)` and allows, never a refusal and never a zero. The
successor's cap and the supervisor's resume cap keep `envelope_left` (every head-exit's spent_usd
plus this session's billed total): their logic is out of this change's scope. A warning
threshold stays the head's rule: the gate writes no warning event.
`raise-envelope --run R --to USD --reason …` (register entry 2026-09-10 20:02)
appends {"event":
"envelope", "envelope_usd": <to>, "previous_usd": …, "spent_usd": …, "spent_src": …, "reason":
…}. It refuses, with exit 2 and nothing written, a record with no run-open, a closed run (a
run-close on the record), an empty reason, a figure that is not a finite positive number or is
not above the current envelope, and a figure at or below the run's spend — every head-exit's
spent_usd plus this session's billed total when --meter-line or the meter gives one, the
recorded spend alone otherwise, the event saying which — since the gate refuses a remainder at
or below zero.

Armed: AIMYTH_HANDSOFF=1 in the environment, or the marker file armed-<sid> in AIMYTH_STATE_DIR
(default ~/.aimyth/handoffs; the hooks' handsoff-gate.py convention). Bands: AIMYTH_BANDS
(two or three ascending edges; the second is the gate's threshold) and AIMYTH_CONTEXT_WINDOW,
read through the watermark hook's own bands() and window() so gate and prompt line agree. The
head's transcript is <sid>.jsonl under the vault's dashed project directory beneath
AIMYTH_PROJECTS_DIR (default ~/.claude/projects), the session id from the LAST run-open,
run-resume or head-successor event; the dashed form replaces every non-alphanumeric character
with a dash (the harness's encoding, checked against a live projects root). measure() is
imported from the hooks directory's context-watermark.py beside this script's tree, never
from the watermark log: a headless head's transcript may hold one prompt and no hook line.

pid discovery (N4): walk upward from the parent process with `ps -o pid=,ppid=,comm=` to the
nearest ancestor whose command is the harness binary → pid, pid_src parent-walk; none (an
attended head) → no pid, pid_src none, and the starter falls back to 120 s of transcript
silence; --pid N overrides with pid_src arg.

The seed pattern (register entries 2026-09-07, 2026-09-10 10:51 and 2026-09-12 20:0x). A
launcher that opens a run for a head which has not started yet calls `run-open --session-kind
seed`, `handoff --final` and `successor` with NO --pid. A seed never runs, so its run-open
records no pid, and on a SEEDED record (its run-open marks `session_kind: seed`) neither
`handoff --final` nor `successor` runs the parent walk for the head-exit it writes: from a
launcher, that walk reaches the launcher's own long-lived process (an attended conversation's
`claude`, or a launcher script), which does not exit at the end of a reply, and the first
starter then waited on it for its whole bound. A seed run-open's pid is taken only when its
`pid_src` is `arg`, and each command prints the pid and its source on one line:
`successor: pid none (run-open, seed: no pid)`, or `pid <n> (run-open, seed)` for a seed opened
with --pid, and on a head record `(parent-walk)`, `(arg)` or `(none)`. The starter skips its
wait when the predecessor is a seed session with no usable pid (nothing ran, so there is nothing
to outlive). A pid a launcher does pass belongs to a process that exits within seconds of the
launch, never to the launcher itself: `$$` names the shell that expands it, and even
inside a `( … )` subshell it still names the launcher's shell. `successor` refuses (exit 2) a
--pid, a --predecessor-pid or a seed run-open's pid that is the caller's own ancestor and has
run longer than ANCESTOR_AGE_S, the starter aborts (`own-ancestor`) on the same test, and a
predecessor still alive at the starter's bound ends `timeout` with the process's command and age
named.

The grants file (D34): run-open and run-resume write <store>/spawn-records/<run>-grants.json,
its only path — `--grants-file` is retired and refused naming that path (register entry
2026-09-06: the head fence resolves the default path from the run id alone, so an override was a
file nothing enforced) — with `grants` and `writes` as real paths — every path given is
expanded, made absolute and resolved, and kept in both spellings when the given and the real
path differ — plus the defaults that keep the head's own primitives inside the fence: grants
carry the vault root, the store root, the state directory, the projects root and /tmp; writes
carry the store root and the state directory. The same two commands write the pointer file
run-<sid> (one line, the run id) under the state directory, so the head fence finds the run
from a session id when AIMYTH_HANDSOFF_RUN is absent. gate and boundary print one warning
line when the session is armed and the grants file is missing: the head fence is fail-open.
A list is never reset by a flag that does not name it. Flag-specific updates preserve all other
grants and writes: `grants` and a rewriting `run-resume` take the
file's `grants` list when no --grant is given and its `writes` list when no --write is given, so
--on-limit or --viewer alone changes that key alone; a named list replaces the file's, as
before, and a flag-less `run-resume` still leaves the file untouched. run-open, grants and a
rewriting run-resume record both lists on their event. The shrink guard's baseline is the
record's lists whenever the record holds them (the last run-open, grants or rewriting
run-resume event that recorded both), with any path the file adds, whatever the file holds
now: a file already narrowed, by hand or by an older primitive, is never the contract a rewrite
is checked against. With no recorded lists the file's lists are the baseline. A call naming
neither --grant nor --write that would lose a write path prints the delta and refuses (exit 2,
nothing written), whether the file is present, narrowed, missing or unreadable; a lost read
path alone, or any loss by a call that names a list, is written with the delta on one stderr
line.

The network key. The grants file carries `network`, the host names the head fence's network
check lets a command address; an empty list means none, and a file written before the key
existed reads as none, never as an error. `run-open --network none|HOST[,HOST…]` sets it
(absent: an existing file's value, else none), `grants --network` rewrites it, and every other
rewrite (`grants` without the flag, a rewriting `run-resume`) carries the file's value forward,
as on_limit and viewer are carried. A host is a bare DNS name, lower-cased and de-duplicated,
with no scheme, port, path, user or wildcard; any other item, an empty item or `none` inside a
list is a premise failure (exit 2, nothing written). run-open, run-resume and grants record the
value on their event as `network` with `network_src` (arg, grants, or the default's reason).

The console window. The grants file carries a
second key beside `on_limit` and built the same way: `viewer`, either `terminal` (the default,
and what a file without the key reads) or `none`. `run-open --viewer terminal|none` sets it,
`grants --viewer` rewrites it, `grants --grant PATH` and a flag-less `run-resume` carry it
forward, and run-open records it on its event as `viewer` with `viewer_src` (arg, grants, or
default (key absent)). The grants file is the key's only home: no second file and no environment
fallback for the key itself. On `terminal`, `open_console(run)` writes
<store>/spawn-records/<run>-console.command (mode 0755: a title line, then `exec env
LLM_WIKI_STORE=<store> CLAUDE_PROJECT_DIR=<vault> <this interpreter> -B <this script> watch
--run R`, every path derived, rewritten when stale; no `cd`, since every path is absolute and a
`.command` file runs in a fresh login shell) and opens it with `/usr/bin/open -g <that file>`
(the owner's absolute path, OPEN_BIN; AIMYTH_OPEN_BIN overrides it for a suite's stub) — Launch
Services hands a `.command` file to Terminal, which starts a new window by typing the file's
path into a fresh shell, and `-g` keeps Terminal in the background so a key the owner presses as
the window appears stays where it was typed instead of landing in that command (register
2026-09-22; no script text is compiled) — retried once with the same command when the first
attempt fails, and counted open only once `console_alive(run)` finds the run's `watch` process,
polled for at most CONSOLE_START_GRACE_S after `open` returns, no probe running past that bound
and a pid found after it a timeout (2026-09-18). Two
routes are retired and are no fallback: `open -a Terminal <path>` (register entry 2026-09-09
11:21), which can type the path into a new shell with a stray character in front, and an
AppleScript opener (register entry 2026-09-17 20:29), whose script variable named after a
Terminal dictionary term makes every attempt open a tab and type nothing. Every attempt's opener path,
outcome and standard error are printed, and written to the detach log when the caller names one,
and the success line names the command file, the opener, the attempt that opened it and the
console pid it confirmed. AIMYTH_VIEWER_CMD, when set, REPLACES the whole opener, retry
included: it is split with shlex, the command file's path is appended as its last argument and
it is run in list form, never through a shell, and its console is not confirmed (the command is
the caller's own; the suites' stubs start no process). A VIEWER FAILURE NEVER FAILS A LAUNCH:
every failure — no binary, a timeout, a non-zero exit, an `open` that exits 0 with no console
process inside the bound — prints one line to standard error (`viewer: no Terminal window
(command file <path>; first attempt: <why>; retry: <why>); run by hand: python3 -B <this
script> watch --run R`) and the calling primitive still exits 0. `open-console --run R` runs the
same opener on demand and `open-console --run R --check` prints the live console's pid or `NO
CONSOLE`. run-open opens at once, since a
run's first act can have no console yet; `successor` and `resume-head` (each BEFORE it detaches
its worker, the viewer lines written to the worker's log too and the worker handed
`--viewer-opened`, so its first start opens nothing) and the supervisor's own later successor
and in-place-resume starts open
one only when `console_alive(run)` finds none, so the owner's `q` gets a fresh window while a
running console is never doubled. Which of several openers that is, is settled by an ADVISORY
LOCK on <store>/spawn-records/<run>-console.lock (`fcntl.flock`, LOCK_EX | LOCK_NB), taken before
the first live probe and held until the confirmation has ended, so the probe and the claim cannot
be interleaved and a caller that observed no console before it queued for the lock discards that
observation; a caller that cannot take the lock opens nothing and names the holder on standard
error, and the kernel releases a dead holder's lock, so nothing is renamed, taken over or aged
out (the ruling on the №163 fold, 2026-09-18; lane.py's session claim of №161 is the same
mechanism). The `<command file>.opening` claim file of №162 is retired, and a leftover one is
inert. That probe is `pgrep -f` on both spellings of the command —
`handsoff.py watch --run R` as it is launched and `watch.py --run R` as it runs, since `watch`
execs watch.py in place — the run id escaped and the pattern passed as an argv item, so it never
matches its own command line. Away runs are included: the key alone decides. Every --dry-run
prints the opener's command line, opens nothing and writes no command file.

Paths for a staged copy: AIMYTH_HOOKS_DIR names the hooks directory holding
context-watermark.py (default two levels up from this script, beside the skill tree) and
AIMYTH_LANE_PY names the lane wrapper (default lane.py beside this script), so a copy under
test can be pointed at the shipped modules the way CLAUDE_PROJECT_DIR points it at a vault.

The pack-age guard (D41's pack, the successor's brief). `handoff --inflight`/`--inflight-file`
writes the section under a first line `- pack written: <ISO timestamp>`, replacing any earlier
stamp, so the pack carries its own age. `run-resume` and every successor start (the starter,
and `supervise` where its loop starts a successor) compare that stamp with the timestamp of the
record's last `phase-boundary` or `head-exit` event: a pack older than that boundary is STALE —
the head moved on and the pack did not. A head-exit carrying `pack: false` is never the head's
own hand-over (`handoff --final` writes `pack: true`): `successor` and the supervisor write it at
the moment of their call, and keying on it would judge every hand-off a launcher amended between
a head's stop and that call stale (register entry 2026-09-12 21:2x). For that anchor the guard
takes the head's LAST ACTIVITY instead — the latest of its own events since its start (the start
event, gate, phase-boundary, decision, a `pack: true` head-exit), the supervisor's `head exited`
observation and the head transcript's mtime; no other observation is taken, since its author is
not on the event — and the pack is fresh when its stamp is at or after that activity or the
hand-off's mtime is at least REWRITE_SLACK_S past it. `successor --pack-fresh` and `resume-head
--pack-fresh` record an observation `what: pack-fresh`, the launcher's word that the hand-off is
current: a pack whose anchor that observation follows is fresh by it, while a later anchor (the
new head has acted since) is judged as usual. On a stale pack the starter rewrites
`## In flight` from the record
before the successor starts (a `Next:` line that says it is a copy of the last boundary's `next`
field, which carries the run's shape as it stood then, the lanes still open since it with
their spawn lines, the `decision` events since it, one line each, under `- pack re-derived from
the record at <ts> (the head's pack was stale)`) and records an observation `what: stale-pack`;
`run-resume` prints one warning line and records the same observation. No boundary in the record
means the pack is fresh by definition; a pack with no stamp at all (a hand-off written by hand,
or before this guard) is reported `unstamped` and left alone, since re-deriving over it would
overwrite the head's own judgement. `handoff --inflight-from-record` is the same derivation as a
command, for a head that wants it, and it keeps the three D41 labels so a re-derived pack passes
the same label check a head's own pack must pass.

Two heads on one run (register entry 2026-09-03): a harness resume can start a second process on
a session whose first process still runs. `run-resume` and `gate` read the record's last head
start — the last `run-open`, `run-resume`, `head-successor` or `head-resumed` event (a seed
run-open is skipped: a seed never runs) — and refuse with exit 9, one `TWO HEADS` line and an
observation `what: two heads`, on positive evidence only, when all of these hold: it names a
pid above 1 and within PID_MAX; no `head-exit` follows it; that pid is alive; the caller's own
process chain (this process, its parent and every ancestor the `ps` walk reaches) was read to
the top of the tree and the pid is not in it, which is how a head's own later call is told from
a peer's; and the process's age and the event's time were both read and show the process
started no later than the event plus PID_START_SLACK_S (a pid the system reused after that head
died is another process). A live pid outside the chain that cannot be placed, because the walk
stopped on a row it could not read (no `ps`, a failing `ps`, an unparseable row) or the age or
the event's time is unreadable, gets one `warn:` line naming what could not be read, and the
call proceeds with no observation written: a guard never fires on its own broken premise.
`--i-am-pid PID` adds a pid to the chain, for a caller whose head process the walk cannot reach
(no `ps`, or a call detached from its head's process tree); a caller the walk reaches never
needs it. A dead pid, a reused pid, a head start with no pid, or a head-exit after it clears the
check.

The decisions channel (register entry 2026-09-13 03:53).
`gate` and `close` hold with exit 6
while the record carries an `observation` whose `what` opens with the whole word `AUTHOR` (a
non-letter or the end follows it: `AUTHOR ruling`, `AUTHOR-side note` and `AUTHOR: …` count,
`AUTHORED the page` does not) after the reference
point — the later of the record's last `gate` event and its last `ack: …` observation, else its
last run-open or run-resume, else its first line — or while `--decisions-file PATH` (no
default) has an mtime later than that reference's timestamp: the held call prints one line per
such observation and one naming the file, and writes nothing. `--ack "<one line naming what was
read>"` records an observation `what: ack: <line>` and the call proceeds; an empty ack is
refused. A named decisions file that does not exist is a premise failure (exit 2), since a
mistyped path would never hold. `run-is-closed --run R` exits 0 on a record with a run-close
and 1 on one without (2 with no record), for a wrapper that warns before it spawns into a
closed run.

The decision subcommand (register entry 2026-09-06): the primitive that writes the `decision`
events the close counts, so an owner-behalf decision is never left as a ledger row alone.
`decision --run R --phase P --what … --grant …` writes the `decision` event (phase, what, grant:
the design's trace schema) and one findings-ledger row — What `decision: <what>`, Evidence
`grant: <grant>`, Routing --routing (default `no action`) — in one call, before the act. It
records no observation beside them, and `close` counts the `decision` events plus the
observations whose `what` opens with the word decision (the ledger form heads used before), so
each decision is counted once.

Exit codes: 0 done · 2 premise failure (PROBE FAILED, nothing written) · 3 event written but
the hand-off not refreshed (a section is missing: fix the document) · 4 gate refused on the
band (armed) · 7 gate refused on the second unmetered miss (armed), or wait-reset gave up at
--max-wait-s, or wait-reset ended limit-unparsed or limit-model (no reset time and no --probe, or a limit scoped to one model: the hand-off is
the recovery) · 8 wait-reset still running (re-issue the call) · 1 from an internal supervisor
whose run ended in successor-aborted (a stand-down, supervisor-stood-down, exits 0: the
designed default, never an abort) · 5 gate refused on the envelope · 6 gate or close held by the
decisions channel (re-run with --ack) · 9 run-resume or gate refused while another live head
holds the run · 1 also from run-is-closed on an open run.

Numbers: REPORT_CAP_WORDS decodes legacy records only; starter wait 600 s and silence
proxy 120 s (design, context bands; set by judgement, unmeasured); --max-block-s 540 s (the
shell tool's 600 s cap minus a minute of slack, set by judgement); probe interval 900 s and
budget $0.05 (design, account plan); commit timeout 300 s (set by judgement, unmeasured — a
cloud-synced work tree); the reset wait's bound 8 h (the existing waiter's bound, design D30);
the supervisor's sleep tick 60 s (set by judgement, unmeasured: a run-close is seen within a
minute and the tick costs nothing); the resume decision is FIT plus the cost rule (
2026-09-14; the first band edge, 60 % by default, only where no figure exists); heartbeat 50 min (the 1-hour cache
tier less 10 min for the re-invocation's latency, set by judgement, design D32) in 30 s ticks
(design D32); the stop-condition note is cut at 300 characters (the waiter's existing cut); the
viewer's timeout 10 s (the bound on one `open` call, which returns once Launch Services has
handed the file to Terminal; set by judgement, unmeasured), its console confirmation
CONSOLE_START_GRACE_S in CONSOLE_CONFIRM_STEP_S polls (at most 30), the one-window claim (a lock
the kernel holds and releases: no life to derive), one `ps` call's bound PS_TIMEOUT_S, which the
launch check cuts to the budget left of its deadline, and that check's deadline
LAUNCH_CHECK_WAIT_S and poll LAUNCH_CHECK_POLL_S (derived, or named as judgement, beside the
constants).
The run-lifecycle numbers: ANCESTOR_AGE_S 60 s (set by judgement, unmeasured: a seed pid's
process exits within seconds, a launcher's lives for minutes or hours); PID_START_SLACK_S 2 s and
REWRITE_SLACK_S 1 s (the record's whole-second timestamps and `ps -o etime=`'s whole seconds);
exit codes 6 and 9 (the run design's, both unused here before); PID_MAX 2**31 - 1 (a signed
32-bit pid: os.kill overflows past it, measured); a host name's labels at most 63 characters and
253 in all (the DNS name limits).
Every --dry-run prints what would be written and writes nothing.
"""
import sys
sys.dont_write_bytecode = True   # the hook import must never leave bytecode in the vault
import argparse
import calendar
import contextlib
import glob as globmod
import importlib.util
import json
import math
import os
import re
import shlex
import subprocess
import time
import uuid

try:
    import fcntl   # record_lock's advisory lock; absent off POSIX, where no lock is taken
except ImportError:
    fcntl = None

HEAD_EVENTS = ("run-open", "run-resume", "head-exit", "head-successor")
SESSION_EVENTS = ("run-open", "run-resume", "head-successor")   # each names the head's session
START_EVENTS = SESSION_EVENTS + ("head-resumed",)   # each starts a head process the supervisor owns
WRAPPER_EVENTS = ("lane-closed", "stall")   # written while the head waits, never by the head
SESSION_KINDS = ("seed", "head")   # run-open --session-kind: a launcher's placeholder, or a head
# The cut tail of a requested report preview, priced in the waste table (T8):
# omitted words from cut_words, converted at this many tokens per word
# and charged at the lane's model's OUTPUT rate from prices.json. The ratio is set by judgement,
# unmeasured — no tokeniser is read here — and every row it prices says so.
WORDS_TO_TOKENS = 1.3
DEFAULT_EDGES = (60, 80, 90)                # fallback only; the watermark hook's bands() decides
# Fit-based continuation (2026-09-14): the gate asks whether the
# next item fits under the belt instead of comparing the total with a fixed mark; the marks stay
# as the fallbacks for a missing figure. Shares of the window, so every window size scales.
PRIOR_ITEM_SHARE = 0.125       # compatibility prior; set by judgement, unmeasured for a new workload
PACK_ALLOWANCE_SHARE = 0.02    # the boundary's hand-off write and successor spawn (set by judgement, unmeasured)
ORIENTATION_SHARE = 0.085      # compatibility prior; set by judgement, unmeasured for a new workload
FIT_MARGIN = 1.25              # over the largest measured item of a run (set by judgement, unmeasured)
CACHE_LIFE_S = 3600            # assumed one-hour prompt-cache life; set by judgement, unmeasured; lane.py's RESUME_WINDOW_S keeps 5 min headroom
DEFAULT_WINDOW = 1000000
REPORT_CAP_WORDS = 800   # Legacy format: the default shown count before report_cut/report_shown fields.
STARTER_WAIT_S = 600
SILENCE_PROXY_S = 120
MAX_BLOCK_S = 540
MAX_WAIT_S = 8 * 3600          # the reset wait's bound (design D30: the existing waiter's bound)
PROBE_INTERVAL_S = 900
PROBE_BUDGET_USD = 0.05
PROBE_TIMEOUT_S = 120
COMMIT_TIMEOUT_S = 300
METER_TIMEOUT_S = 600
# The run figure's OTHER meter calls at a gate, a boundary or the close (every earlier head, and
# every lane closed without a cost or still open) share one wall-clock budget, so a gate that
# meters many transcripts stays a bounded call: 240 s leaves the session meter its own bound
# inside the shell tool's 600 s cap when the cache is cold, and a warm cache (spend_cache_path:
# every static transcript is metered once) makes the budget moot; set by judgement, unmeasured.
# A session the budget leaves unmetered is named and the figure is a floor, never a zero.
RUN_SPEND_BUDGET_S = 240
# The lane events the run figure folds a lane's session ids and closes from (run_lanes).
LANE_SPEND_EVENTS = ("lane-open", "lane-spawned", "lane-session", "lane-resumed",
                     "lane-respawned", "lane-closed", "hold-beat")
# `hold-beat` joined the list on 2026-09-17 (critic finding 3 of review): a held lane's beats
# Include held-lane beats in run spend independently of whether a final close has arrived.
SUPERVISE_TICK_S = 60          # the supervisor's sleep tick (set by judgement, unmeasured)
RESUME_CAP = 2                 # resumes per head session (critic C2 N6, set by judgement)
HEARTBEAT_MINUTES = 50.0       # the 1-hour cache tier less 10 min latency (design D32, judgement)
HEARTBEAT_TICK_S = 30          # design D32
# Held lanes: a finished lane the head still expects to resume is kept warm by a no-work beat
# through its own wrapper. Every number here is set by judgement, unmeasured.
HOLD_BEAT_S = 50 * 60          # the beat falls due this long after the lane's last call: the 1-hour cache tier less 10 min for the beat's own latency, as HEARTBEAT_MINUTES
HOLD_CAP_DEFAULT = 1           # beats a hold allows before it ends unless the head renews it
HOLD_WINDOW_S = 55 * 60        # lane.py's RESUME_WINDOW_S: a lane whose last call is older keeps nothing warm, so a hold on it is refused
HOLD_CAP_MAX = 24              # the ceiling on --cap (critic F8, 2026-09-17): 24 beats at the 50-minute interval span 20 hours; cap set by judgement, unmeasured; a hold that must outlive it is renewed
HOLD_BEAT_WRAPPER_BOUND_S = 600   # lane.py's BEAT_TIMEOUT_S, the bound the WRAPPER puts on its own harness call (a suite leg asserts the two agree)
HOLD_BEAT_GRACE_S = 120        # the supervisor's outer bound sits this far above the wrapper's own (critic F2, 2026-09-17): equal bounds let subprocess.run kill the wrapper first, and the harness it started with start_new_session then survives on the lane's session, so a later real resume is a second process on one session. Two minutes covers the wrapper's own kill path (SIGTERM, a 5 s wait, SIGKILL) and its record write on a loaded machine with a wide margin; set by judgement, unmeasured
HOLD_BEAT_TIMEOUT_S = HOLD_BEAT_WRAPPER_BOUND_S + HOLD_BEAT_GRACE_S   # the beat wrapper call's bound, the wrapper's own plus the grace: the wrapper times out, kills its process group and records the failure before this fires
HOLDABLE_EXITS = ("completed", "empty", "watch-closed")   # the close classes a beat re-enters: lane.py's BEAT_EXITS, the same tuple (a suite leg asserts it); a limit or budget close is the head's own decision (D29, the resume rules), a killed, stalled or errored lane is re-spawned
HOLD_ENDED_REASONS = ("released", "cap", "lane-closed", "run-close", "stood-down")
HOLD_TIER_1H = "1h"           # the cache write tier a 50-minute beat rests on, as lane.py records it on a close (`cache_write_tier`); a shorter tier is warned about, never refused (critic F5c)
HOLD_KINDS = ("hold", "hold-beat", "hold-ended")
BEAT_BY_ENV = "AIMYTH_BEAT_BY"          # the wrapper records who issued a beat; the supervisor sets it
BEAT_WRAPPER_DIR_ENV = "AIMYTH_BEAT_WRAPPER_DIR"   # a directory holding lane.py and codex-lane.py (a suite's stubs); default: beside this file
CODEX_HOME_ENV = "CODEX_HOME"           # the Codex CLI's home, whose sessions/ tree holds a lane's session file
TAIL_BYTES = 65536             # how much of a session file's tail is read for its last timestamp: a session line is a few KB at most (set by judgement)
ON_LIMIT_VALUES = ("stop", "resume")   # the limit gate (design D42): the pre-flight's class L
ON_LIMIT_DEFAULT = "stop"              # respect the limit; `resume` is the pre-flight's limit-off
VIEWER_VALUES = ("terminal", "none")   # the viewer key: a Terminal window on the run's console
VIEWER_DEFAULT = "terminal"            # a run the owner can see; `none` is the opt-out
# Use an absolute opener path; tests may override it with the supported stub setting.
# /usr/bin/open, never the word resolved on PATH. AIMYTH_OPEN_BIN overrides the path, which is
# how a suite points the route at a recording stub without a window server (open_bin).
OPEN_BIN = "/usr/bin/open"
# The opener's bound on one `open` call, and on console_alive's pgrep: `open <file>.command`
# returns once Launch Services has handed the file to Terminal. The bound is set by judgement,
# unmeasured. wait_console shortens a probe's bound to the time left of
# its own, so no probe runs past the confirmation bound.
VIEWER_TIMEOUT_S = 10
# Retry a failed opener using the same command. Retired routes are not fallbacks: their shell
# and application-dictionary failure modes must not be reintroduced.
# References: register entry 2026-09-09.
VIEWER_RETRIES = 1
# The console's confirmation after `open` returns: the window is counted open only
# once console_alive finds the run's `watch` process, polled every CONSOLE_CONFIRM_STEP_S for at
# most CONSOLE_START_GRACE_S (below: the same interval, from the opener's return to the process
# showing in the table, that the grace stamp already covers). The step caps the probes at
# CONSOLE_START_GRACE_S / CONSOLE_CONFIRM_STEP_S = 30 per open (wait_console enforces the cap
# and the bound: a probe never runs past the time left, and a pid that shows only after the
# bound is a timeout, never a window — critic review finding 3); 0.5 s is set by judgement,
# unmeasured. An `open` that exits 0 and starts no console inside the bound is a failure by
# name: an attempt that exits clean and shows nothing is the empty-window class.
CONSOLE_CONFIRM_STEP_S = 0.5
# The launch check's default deadline is set by judgement, unmeasured for a new installation.
# A seed launch's starter starts the head at once, with no predecessor to outlive.
# A head-called successor's starter first waits for its predecessor to exit,
# up to `--wait-s` (STARTER_WAIT_S), so a check on that shape passes --wait above that bound
# plus this default; the pending line says so while the predecessor's pid is alive. The poll
# bounds the check's observation latency — how long after the starter's append the check sees
# the line — and nothing derives it: the record's whole-second timestamps say when an event was
# stamped, not when its line lands, so a finer poll does see a line sooner (a suite runs at
# 0.2 s); 1 s is set by judgement, unmeasured. The deadline is computed ONCE, at the start, and
# every probe of every read draws on that one budget: each is bounded by the lower of its own cap
# and what is left (probe_bound), so two probes cannot each spend the whole remainder, and a
# start confirmed only after the deadline is not a start (critic review finding 3, pass 2).
LAUNCH_CHECK_WAIT_S = 60
LAUNCH_CHECK_POLL_S = 1.0
# The run report's two sections the close patches (register entry 2026-09-10 17:43), matched by
# the opening words of their level-two headings as the hands-off run reports write them, and the
# keys of the one bullet the close owns in each.
REPORT_SPEND_HEADING = "Spend"
REPORT_WARNINGS_HEADING = "Warnings"
REPORT_METER_KEY = "Closing meter (handsoff.py close)"
REPORT_STOPS_KEY = "Limit stops on the record (handsoff.py close)"
REPORT_HARDSTOPS_KEY = "Hard stops on the record (handsoff.py close)"
DENIAL_KEYS = ("tool", "fence", "sandbox")   # a lane close's denial counters; its allow counters never count
CONSOLE_TITLE = "aiMyth hands-off · %s"   # the console window's custom title, per run
CONSOLE_START_GRACE_S = 15     # a console opened this recently counts as alive before its process
                               # shows in the table. This grace is set by judgement, unmeasured.
                               # (reference №140).
                               # №162.
# The one-window claim (open_console_if_dark): the advisory lock on <run>-console.lock beside the
# run's record. It carries no life and no threshold — the kernel holds it while its opener lives
# and releases it when that opener dies — which is why the ruling on the №163 fold (2026-09-18)
# put the claim on a lock: an age-based claim needed a takeover, and the takeover was the race.
# The `<command file>.opening` claim of №162 and its life constant are retired with it (a
# leftover file of that name is read by nothing). lane.py's session claim (hold_session, №161)
# is the same mechanism, and the phase words below are that claim's `kind` field.
CONSOLE_LOCK_SUFFIX = "-console.lock"
CONSOLE_PHASE_CHECK = "check"   # the holder is probing for a live console, nothing opened yet
CONSOLE_PHASE_OPEN = "open"     # the holder has gone to `open` and its confirmation wait
NOTE_CUT = 300                 # the stop-condition note's cut (the waiter's existing cut)
# The gate's envelope stop (register entry 2026-09-07): 5 is the lowest exit code no subcommand
# uses — 0 done, 1 a supervisor or starter failure, 2 a premise failure, 3 boundary's hand-off
# not refreshed, 4 the band stop, 7 unmetered or limit, 8 still-running, 124/127 the shell's.
EXIT_ENVELOPE = 5
# The decisions channel's hold and the two-heads refusal (register entries 2026-09-13 03:53 and
# 2026-09-03): the codes are the run design's, and no subcommand used either — 6 sits between the
# envelope's 5 and the unmetered 7, and 9 is the first code past still-running's 8.
EXIT_HOLD = 6
EXIT_TWO_HEADS = 9
# A launcher-supplied pid that is the caller's own ancestor and has run longer than this is
# refused by `successor` and the starter, which would otherwise wait on the caller itself
# (register entries 2026-09-10 10:51 and 2026-09-12 20:0x). A seed pid's process exits within
# seconds and a launcher's lives for minutes or hours; 60 s is set by judgement, unmeasured.
ANCESTOR_AGE_S = 60
# A live pid whose process started more than this after the head start that recorded it is a
# reused pid, not that head: the record's timestamps and `ps -o etime=` both count whole seconds,
# so each contributes up to one second (set by those two resolutions).
PID_START_SLACK_S = 2
# A hand-off whose mtime is at least this past the head's last activity was rewritten after it:
# the record's timestamps are whole seconds, so a write inside the same second cannot be ordered
# against an event (set by that resolution).
REWRITE_SLACK_S = 1
# A relayed owner instruction's `what` opens with the whole word AUTHOR, a non-letter or the end
# following it (`AUTHOR ruling`, `AUTHOR-side note`, `AUTHOR: …`); `AUTHORED the page` is not one.
AUTHOR_RE = re.compile(r"AUTHOR(?![^\W\d_])")
ACK_PREFIX = "ack: "             # the head's acknowledgement observation's `what`
PACK_FRESH_WHAT = "pack-fresh"   # the launcher's word that the hand-off is current
TWO_HEADS_WHAT = "two heads"     # the observation a two-heads refusal records
DECISION_WHAT_RE = re.compile(r"^\s*decision\b", re.I)   # a ledger row recording a decision
# A recorded pid above this names no process: the platform's pid is a signed 32-bit integer and
# os.kill raises OverflowError past it (measured), so a larger figure is a corrupt record.
PID_MAX = 2 ** 31 - 1
# The bound on one `ps` call (ps_row, process_age_s): the literal every such call carried; set
# by judgement, unmeasured. It is a CAP, never a floor: the launch check cuts each probe to the
# budget left of its deadline (probe_bound), so a 60 s deadline still hands a `ps` call 10 s and
# a 1 s deadline hands it 1 s (critic review pass 2 finding 3).
PS_TIMEOUT_S = 10
NETWORK_NONE = "none"   # --network's word for no network; the grants file holds it as []
# A host --network accepts: dot-separated labels of lower-case letters, digits and inner hyphens,
# each at most 63 characters and 253 in all (the DNS name limits).
HOST_RE = re.compile(r"(?=[a-z0-9.-]{1,253}\Z)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
                     r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*")
# The trace table the boundary appends its rows to (time, from → to, disposition, billed line,
# waste): run-open seeds this header under a `## Trace` heading that holds no table.
TRACE_HEADER = ("| Time | Item | Decision and its rule | Billed line | Waste so far |",
                "|---|---|---|---|---|")
# The findings-ledger table `ledger` and `decision` append their rows to: created under a
# `## Findings ledger` heading that holds prose and no table (register entry 2026-09-14 19:35).
LEDGER_HEADER = ("| Time | Item | Finding | Evidence | Routing |", "|---|---|---|---|---|")
# The events a head writes about its own work, for the pack-age guard's last-activity anchor;
# observations are left out, since their author is not on the event (a launcher relays some).
HEAD_ACTS = START_EVENTS + ("gate", "phase-boundary", "decision")
PACK_LABELS = ("Next:", "Needs:", "Decided:")   # the next-task pack (design D41)
PACK_LINE_RE = re.compile(r"^\s*(?:[-*]\s+)?(Next|Needs|Decided):", re.M)
PACK_STAMP = "- pack written: "                 # the pack's age stamp (the pack-age guard)
PACK_DERIVED = "- pack re-derived from the record at %s (the head's pack was stale)"
PACK_STAMP_RE = re.compile(r"^\s*[-*]\s+pack (?:written:|re-derived from the record at)\s*"
                           r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
                           r"(?:Z|[+-]\d{2}:?\d{2})?)", re.M)
BOUNDARY_EVENTS = ("phase-boundary", "head-exit")   # the pack-age guard's anchor
HARNESS = "claude"
TOKEN_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")
TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?"
                   r"(Z|[+-]\d{2}:?\d{2})?$")
BULLETS = {"shipped": "What shipped", "waits": "Waits for you", "register": "Register delta",
           "spend": "Spend against the envelope", "saving": "Measured head-load saving",
           "warnings": "Warnings raised and handling", "resume": "Resume prompt"}
SECTIONS = {"inflight": "In flight", "resume-prompt": "Resume prompt", "plan": "Plan of record",
            "pointers": "Pointers", "grants": "Grants"}
APPEND_ONLY = ("ledger", "findings-ledger", "trace")
HERE = os.path.dirname(os.path.abspath(__file__))


# ----------------------------------------------------------------- premise and paths -------

def die(reason):
    """A premise failure: say what broke, write nothing, exit 2."""
    sys.stderr.write("handsoff.py: PROBE FAILED: %s\n" % reason)
    sys.exit(2)


def note(msg):
    sys.stderr.write("handsoff.py: %s\n" % msg)


def say(line):
    print(line, flush=True)


def vault_root():
    """Three levels above this script; an explicit CLAUDE_PROJECT_DIR wins, so a copy can be
    pointed at a fixture vault."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return os.path.realpath(env)
    return os.path.realpath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))


def store_root():
    """The machine-local run store, as its real path (the default is a symlink)."""
    return os.path.realpath(os.path.expanduser(
        os.environ.get("LLM_WIKI_STORE") or os.path.join("~", ".llm-wiki")))


def projects_root():
    return os.path.realpath(os.path.expanduser(
        os.environ.get("AIMYTH_PROJECTS_DIR") or os.path.join("~", ".claude", "projects")))


def state_dir():
    return os.path.expanduser(os.environ.get("AIMYTH_STATE_DIR")
                              or os.path.join("~", ".aimyth", "handoffs"))


def dashed(path):
    """The harness's project-directory encoding: every non-alphanumeric character becomes a
    dash."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(path))


def vault_given():
    """The vault root as the caller spelled it (symlinks unresolved), for the second spelling."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))


def store_given():
    return os.path.abspath(os.path.expanduser(
        os.environ.get("LLM_WIKI_STORE") or os.path.join("~", ".llm-wiki")))


def projects_given():
    return os.path.abspath(os.path.expanduser(
        os.environ.get("AIMYTH_PROJECTS_DIR") or os.path.join("~", ".claude", "projects")))


def lane_home_given():
    """The lane-home root as lane.py spells it: LLM_WIKI_LANE_HOME, else lane-home under the
    store (critic C2 N8: a head reads its lanes' homes)."""
    return os.path.abspath(os.path.expanduser(
        os.environ.get("LLM_WIKI_LANE_HOME") or os.path.join(store_given(), "lane-home")))


def spellings(path):
    """The path expanded and made absolute, in its real spelling and — when the two differ,
    as under a symlinked store — the given one as well."""
    given = os.path.abspath(os.path.expanduser(path))
    real = os.path.realpath(given)
    return [real] if real == given else [real, given]


def grants_path(run):
    """The grants file the head fence loads (D34): beside the record, and nowhere else — the
    --grants-file override is retired (register entry 2026-09-06), since the fence and the
    supervisor resolve this path from the run id alone."""
    return os.path.join(store_root(), "spawn-records", token(run, "run id") + "-grants.json")


def refuse_grants_file(a):
    """The retired option's refusal, before anything is read or written; it names the one path
    the head fence reads, so the caller knows where the grants file is."""
    if getattr(a, "grants_file", None) is not None:
        die("--grants-file is retired: the grants file is always %s, the one path the head fence "
            "and the supervisor read (register entry 2026-09-06); drop the option"
            % grants_path(a.run))


def grants_payload(run, source, grants, writes, on_limit=ON_LIMIT_DEFAULT,
                   viewer=VIEWER_DEFAULT, network=None):
    """The defaults first (critic C1 F2: the head's own primitives are never denied), then the
    paths given, every one in both spellings, de-duplicated in order; `on_limit` is the limit
    gate (D42), `viewer` the console window's key and `network` the hosts the head fence's
    network check allows (an empty list: none), each carried by this file alone."""
    def merge(paths):
        out = []
        for p in paths:
            for s in spellings(p):
                if s not in out:
                    out.append(s)
        return out
    return {"run": run,
            "grants": merge([vault_given(), store_given(), state_dir(), projects_given(),
                             lane_home_given(), "/tmp"] + list(grants or [])),
            "writes": merge([store_given(), state_dir()] + list(writes or [])),
            "on_limit": on_limit, "viewer": viewer, "network": list(network or []),
            "written": now(), "source": source}


def read_grants(path):
    """The grants file's payload, or {} when absent or unreadable (a missing file is the fence's
    fail-open case and the gate's default, never an error here)."""
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def on_limit_of(payload):
    """(value, source) from a grants payload: the key when it holds a known value, else the
    default `stop` with the reason (D42: a file written before the gate existed reads stop)."""
    value = payload.get("on_limit") if isinstance(payload, dict) else None
    if value in ON_LIMIT_VALUES:
        return value, "grants"
    if not payload:
        return ON_LIMIT_DEFAULT, "default (no grants file)"
    if value is None:
        return ON_LIMIT_DEFAULT, "default (key absent)"
    return ON_LIMIT_DEFAULT, "default (unknown value %r)" % (value,)


def on_limit_choice(a, path):
    """(value, source) the next write of the grants file carries: --on-limit when given, else
    the file's own value carried forward (D42; critic C1 M5: a rebuild must not reset it), else
    the default."""
    chosen = getattr(a, "on_limit", None)
    if chosen in ON_LIMIT_VALUES:
        return chosen, "--on-limit"
    return on_limit_of(read_grants(path))


def viewer_of(payload):
    """(value, source) from a grants payload, as on_limit_of reads the limit gate: the key when
    it holds a known value, else the default `terminal` with the reason. A grants file written
    before the viewer existed reads `terminal`, so an old run still gets its window."""
    value = payload.get("viewer") if isinstance(payload, dict) else None
    if value in VIEWER_VALUES:
        return value, "grants"
    if not payload:
        return VIEWER_DEFAULT, "default (no grants file)"
    if value is None:
        return VIEWER_DEFAULT, "default (key absent)"
    return VIEWER_DEFAULT, "default (unknown value %r)" % (value,)


def viewer_choice(a, path):
    """(value, source) the next write of the grants file carries: --viewer when given, else the
    file's own value carried forward (a rebuild must not reset it, as for the limit gate), else
    the default. The grants file is this key's only home (D42's rule for on_limit): no second
    file and no environment fallback for the key itself."""
    chosen = getattr(a, "viewer", None)
    if chosen in VIEWER_VALUES:
        return chosen, "arg"
    return viewer_of(read_grants(path))


def parse_network(text):
    """The hosts --network names: `none` gives [], else a comma-separated list of bare DNS names,
    each stripped and lower-cased, duplicates dropped in order. A premise failure (exit 2, nothing
    written) for an empty value, an empty item, `none` inside a list, or an item that is not a bare
    host name (a scheme, a port, a path, a user or a wildcard), since the head fence matches the
    host a command addresses against these names as written."""
    items = [part.strip().lower() for part in str(text).split(",")]
    if items == [NETWORK_NONE]:
        return []
    if not any(items):
        die("--network is empty: pass none, or host names separated by commas")
    hosts = []
    for item in items:
        if not item:
            die("--network %r has an empty item: pass none, or host names separated by single "
                "commas" % text)
        if item == NETWORK_NONE:
            die("--network %r puts none inside a list: pass none alone, or the host names alone"
                % text)
        if not HOST_RE.fullmatch(item):
            die("--network item %r is not a bare host name (letters, digits, dots and inner "
                "hyphens; no scheme, port, path, user or wildcard)" % item)
        if item not in hosts:
            hosts.append(item)
    return hosts


def network_of(payload):
    """(hosts, source) from a grants payload: the `network` key when it is a list of bare host
    names, else none with the reason. A file written before the key existed reads as none (key
    absent), never as an error, and so does a value this reader cannot trust."""
    value = payload.get("network") if isinstance(payload, dict) else None
    if isinstance(value, list) and all(isinstance(h, str) and HOST_RE.fullmatch(h)
                                       for h in value):
        return list(value), "grants"
    if not payload:
        return [], "default (no grants file)"
    if value is None:
        return [], "default (key absent)"
    return [], "default (unreadable value %s)" % ("%r" % (value,))[:60]


def network_choice(a, path):
    """(hosts, source) the next write of the grants file carries: --network when given, else the
    file's own value carried forward (a rebuild never resets it, as for on_limit and viewer), else
    none."""
    chosen = getattr(a, "network", None)
    if chosen is not None:
        return parse_network(chosen), "arg"
    return network_of(read_grants(path))


def network_shown(hosts):
    """The network value on an output line: none, or the hosts comma-separated."""
    return ",".join(hosts) if hosts else NETWORK_NONE


def path_list(payload, key):
    """The payload's list under key when it is a list of strings, else None."""
    value = payload.get(key) if isinstance(payload, dict) else None
    if isinstance(value, list) and all(isinstance(p, str) for p in value):
        return value
    return None


def recorded_lists(events):
    """(grants, writes, label) from the last `run-open`, `grants` or rewriting `run-resume` event
    that recorded both lists, else (None, None, None): the run's contract as its primitives last
    wrote it, the baseline the shrink guard compares every rewrite with."""
    for ev in reversed(events):
        if ev.get("event") not in ("run-open", "grants", "run-resume"):
            continue
        g, w = path_list(ev, "grants"), path_list(ev, "writes")
        if g is not None and w is not None:
            return g, w, "the %s event at %s" % (ev.get("event"), ev.get("ts", "no ts"))
    return None, None, None


def grants_plan(a, path, events, source):
    """The next grants payload (register entries 2026-09-11 04:17 and 2026-09-12 21:3x): a list
    the call does not name is carried from the file, so --on-limit or --viewer alone changes that
    key and keeps the run's literal grants and writes, while a named list replaces the file's;
    the network key is carried the same way unless --network names it. Returns (payload,
    sources, dropped, against): `dropped` maps a list to the paths it would lose against the
    baseline, which is the record's last recorded lists whenever the record holds them (with any
    path the file adds), else the file's lists, and `against` names what was compared."""
    on_limit, _ = on_limit_choice(a, path)
    viewer, _ = viewer_choice(a, path)
    network, _ = network_choice(a, path)
    current = read_grants(path)
    lists, sources = {}, {}
    for key, flag, given in (("grants", "--grant", a.grant), ("writes", "--write", a.write)):
        carried = path_list(current, key)
        if given:
            lists[key], sources[key] = list(given), flag
        elif carried is not None:
            lists[key], sources[key] = carried, "carried (file)"
        else:
            lists[key], sources[key] = [], "defaults (nothing to carry)"
    payload = grants_payload(a.run, source, lists["grants"], lists["writes"], on_limit, viewer,
                             network)
    # The baseline is the record's lists whenever it holds them, with any path the file adds: a
    # file already narrowed (by hand, or by a primitive older than this guard) is never the
    # contract it is checked against. With no recorded lists, the file's lists are the baseline.
    rg, rw, label = recorded_lists(events)
    fg, fw = path_list(current, "grants"), path_list(current, "writes")
    if rg is not None:
        old = {"grants": rg + [p for p in (fg or []) if p not in rg],
               "writes": rw + [p for p in (fw or []) if p not in rw]}
        against = (label if fg is None and fw is None
                   else "%s and the grants file %s" % (label, path))
    else:
        old, against = {"grants": fg, "writes": fw}, "the grants file %s" % path
    dropped = {}
    for key in ("grants", "writes"):
        lost = [p for p in (old[key] or []) if p not in payload[key]]
        if lost:
            dropped[key] = lost
    return payload, sources, dropped, against


def guard_shrink(a, what, dropped, against):
    """The shrink guard (register entry 2026-09-11 04:17): a rewrite that would lose a path from
    the write list prints the delta and refuses (exit 2, nothing written) unless the call passes
    --grant or --write explicitly; an explicit call is written, each list's delta on stderr."""
    deltas = ["the %s list loses %d path(s) against %s: %s"
              % ("write" if key == "writes" else "read", len(dropped[key]), against,
                 ", ".join(dropped[key]))
              for key in ("writes", "grants") if key in dropped]
    if not deltas:
        return
    if a.grant or a.write:
        note("%s: %s (the call passes --grant/--write, so it is written)"
             % (what, " · ".join(deltas)))
        return
    if "writes" in dropped:
        die("%s would shrink the run's write list and passes no --grant or --write: %s; pass the "
            "paths with --write (and --grant) to rewrite explicitly; nothing written"
            % (what, " · ".join(deltas)))
    note("%s: %s (the write list is whole, so it is written)" % (what, " · ".join(deltas)))


def write_grants(path, payload):
    try:
        write_atomic(path, json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    except OSError as exc:
        die("cannot write the grants file %s: %s" % (path, exc))
    return path


def write_pointer(run, sid):
    """The state directory's run-<sid> file: one line, the run id (D34)."""
    path = os.path.join(state_dir(), "run-" + sid)
    try:
        write_atomic(path, run + "\n")
    except OSError as exc:
        die("cannot write the run pointer %s: %s" % (path, exc))
    return path


def grants_warning(events, run, sid):
    """One line when the session is armed and the grants file is missing (D34: the head fence
    is fail-open); None otherwise."""
    is_armed, _ = armed(sid)
    if not is_armed:
        return None
    path = grants_path(run)   # the one path the head fence reads (--grants-file is retired)
    if os.path.isfile(path):
        return None
    return "warn: armed with no grants file at %s: the head fence is fail-open" % path


def heartbeat_files(run):
    """(pid file, stop marker) beside the record (design D32)."""
    base = os.path.join(store_root(), "spawn-records", token(run, "run id") + "-heartbeat")
    return base + ".pid", base + ".stop"


def token(value, what):
    if not isinstance(value, str) or not TOKEN_RE.fullmatch(value):
        die("%s %r is not a plain token" % (what, value))
    return value


def record_path(run):
    return os.path.join(store_root(), "spawn-records", token(run, "run id") + ".jsonl")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def hhmm():
    return time.strftime("%H:%M")


def fmt_ts(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(epoch))


def parse_ts(value):
    """Epoch seconds from a record timestamp (seconds optional, offset +0100, +01:00 or Z; a
    naive stamp reads as local time), else None."""
    m = TS_RE.match(str(value or "").strip())
    if not m:
        return None
    y, mo, d, hh, mm = (int(m.group(i)) for i in range(1, 6))
    ss = int(m.group(6) or 0)
    tz = m.group(7)
    try:
        if not tz:
            return time.mktime((y, mo, d, hh, mm, ss, 0, 0, -1))
        base = calendar.timegm((y, mo, d, hh, mm, ss, 0, 0, 0))
    except (OverflowError, ValueError):
        return None
    if tz == "Z":
        return float(base)
    digits = tz[1:].replace(":", "")
    offset = int(digits[:2]) * 3600 + int(digits[2:]) * 60
    return float(base - offset if tz[0] == "+" else base + offset)


def read_text(path, what):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        die("cannot read %s (%s): %s" % (what, path, exc))


def write_atomic(path, text):
    """Temp file in the same directory, then rename: a concurrent reader sees the old file or
    the new one, never a half-written one."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temp = os.path.join(directory, ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


# ------------------------------------------------------------------------ the record -------

def read_record(path):
    """(events, unparseable lines): a torn last line — a wrapper writing concurrently — is
    counted, never guessed at."""
    events, bad = [], 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if isinstance(rec, dict):
                    events.append(rec)
                else:
                    bad += 1
    except OSError as exc:
        die("cannot read the run record %s: %s" % (path, exc))
    return events, bad


PLAIN_SHAPE = "plain-lane-run"   # the `shape` a plain record's run-close carries (see close_plain)


def read_existing_record(path):
    """The record's events with NO `run-open` requirement: the file must exist and parse.

    A record `lane.py` opened holds lane events and no `run-open` — the plain-lane-run shape of
    the register entries of 2026-09-06 and 2026-09-07. The guard on `run-open` belongs to the
    caller that needs a head (a boundary, a gate, a hand-off rewrite), never to the reader."""
    if not os.path.isfile(path):
        die("no run record at %s — run-open first" % path)
    events, bad = read_record(path)
    if bad:
        note("%d unparseable line(s) in %s skipped" % (bad, path))
    return events


def is_plain_run(events):
    """True for the plain-lane-run shape: a record with no `run-open` event. The test is the
    record's own events, never the run's name or the store it sits in."""
    return last_index(events, ("run-open",)) < 0


def require_record(path, hint=""):
    """The events of a record that must carry a `run-open`; `hint` names the form that works on
    a record without one, for the commands that have such a form."""
    events = read_existing_record(path)
    if is_plain_run(events):
        die("no run-open event in %s%s" % (path, hint))
    return events


def append_record(path, payload):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        die("run record is not writable (%s): %s" % (path, exc))


def event(run, kind, **fields):
    payload = {"ts": now(), "run": run, "event": kind}
    payload.update(fields)
    return payload


def last_index(events, kinds):
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("event") in kinds:
            return i
    return -1


def run_open(events):
    i = last_index(events, ("run-open",))
    if i < 0:
        die("no run-open event")
    return events[i]


def head_session(events):
    """(session id, the event naming it) from the LAST run-open, run-resume or head-successor
    event; (None, None) when the record names no session."""
    i = last_index(events, SESSION_EVENTS)
    if i < 0:
        return None, None
    ev = events[i]
    sid = ev.get("session_id") if ev.get("event") == "head-successor" else ev.get("session")
    return (sid if isinstance(sid, str) and TOKEN_RE.fullmatch(sid) else None), ev


def handoff_of(events, override=None):
    path = os.path.expanduser(override) if override else run_open(events).get("handoff")
    if not path:
        die("run-open carries no hand-off path; pass --handoff")
    if not os.path.isfile(path):
        die("hand-off document not found: %s" % path)
    return path


# ---------------------------------------------------------------- hand-off sections --------

def heading_index(lines, name):
    """The first level-two heading whose text starts with the name (the shipped documents
    suffix their headings)."""
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower().startswith(name.lower()):
            return i
    return -1


def section_end(lines, start):
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("# "):
            return i
    return len(lines)


def section_text(lines, name):
    i = heading_index(lines, name)
    if i < 0:
        return None
    body = lines[i + 1:section_end(lines, i)]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body)


def table_span(lines, name):
    """(first row, last row) of the first table under the heading, else None: the first
    contiguous block of pipe-led lines after the heading, header and separator included."""
    i = heading_index(lines, name)
    if i < 0:
        return None
    end = section_end(lines, i)
    j = i + 1
    while j < end and not lines[j].strip():
        j += 1
    if j >= end or not lines[j].lstrip().startswith("|"):
        return None
    k = j
    while k + 1 < end and lines[k + 1].lstrip().startswith("|"):
        k += 1
    if k - j < 1:
        return None
    return j, k


def table_rows(lines, name):
    span = table_span(lines, name)
    return 0 if span is None else max(0, span[1] - span[0] - 1)


def seed_trace(lines):
    """(state, lines) for the hand-off's `## Trace` section at run-open (register entry
    2026-09-11 04:20; trace-table seeding):
    `table` when a table opens the section; `seeded` when the section holds
    no pipe-led line at all — the five-column header is then inserted under the heading and the
    prose kept below it after a blank line; `misplaced` when a table sits below prose (nothing
    seeded, since two tables would split the trace); `no section` when the heading is absent
    (nothing seeded: where the section goes is the document's choice)."""
    i = heading_index(lines, "Trace")
    if i < 0:
        return "no section", lines
    if table_span(lines, "Trace") is not None:
        return "table", lines
    if any(line.lstrip().startswith("|") for line in lines[i + 1:section_end(lines, i)]):
        return "misplaced", lines
    return "seeded", lines[:i + 1] + list(TRACE_HEADER) + [""] + lines[i + 1:]


def ledger_headings(lines):
    """The indices of every level-two heading whose text opens `Findings ledger` (the shipped
    documents suffix their headings; the case is ignored, as heading_index ignores it)."""
    return [i for i, line in enumerate(lines)
            if line.startswith("## ") and line[3:].strip().lower().startswith("findings ledger")]


def seed_ledger(lines):
    """Return (state, lines) for the first Findings ledger section.
    `table` means its existing table is usable. `seeded` means no pipe-led lines existed and
    the five-column header was inserted while preserving prose. `misplaced` means pipe-led
    lines do not form a table and must not be doubled. `two headings` is checked before any
    other state and identifies both headings. `no section` remains an explicit fault."""
# References: register entry 2026-09-14.
    found = ledger_headings(lines)
    if not found:
        return "no section", lines
    if len(found) > 1:
        return "two headings", lines
    if table_span(lines, "Findings ledger") is not None:
        return "table", lines
    i = found[0]
    if any(line.lstrip().startswith("|") for line in lines[i + 1:section_end(lines, i)]):
        return "misplaced", lines
    return "seeded", lines[:i + 1] + list(LEDGER_HEADER) + [""] + lines[i + 1:]


def ledger_table(lines, ho, what):
    """(the table's span, the seeded lines, seeded?) for a `ledger` or `decision` row: the
    table under the first `## Findings ledger` heading, created there when the section holds
    prose and no table (seed_ledger); a premise the repair does not cover dies naming it —
    two headings (both lines named), a broken table, no section — and nothing is written."""
    state, lines = seed_ledger(lines)
    if state == "two headings":
        found = ledger_headings(lines)
        die("two '## Findings ledger' headings in %s (lines %d and %d): nothing written — keep "
            "one heading" % (ho, found[0] + 1, found[1] + 1))
    span = table_span(lines, "Findings ledger")
    if span is None:
        die("no table under a '## Findings ledger' heading in %s%s"
            % (ho, ": nothing written" if what == "decision" else ""))
    return span, lines, state == "seeded"


LEDGER_SEEDED_LINE = ("%s: the '## Findings ledger' section held prose and no table — the "
                      "five-column header was created directly under the heading, the prose "
                      "kept below it (register entry 2026-09-14 19:35)")


def ledger_warning(state, dry_run):
    """Return a warning when the first ledger append would lack an appendable table, else None."""
# References: register entry 2026-09-14.
    if state == "seeded":
        return ("run-open: warn: the hand-off's '## Findings ledger' section held no table — the "
                "five-column header %s under the heading, so the first ledger call has a table "
                "to append to" % ("would be seeded" if dry_run else "was seeded"))
    if state == "misplaced":
        return ("run-open: warn: the hand-off's '## Findings ledger' section holds pipe-led lines "
                "that make no table: ledger and decision will refuse until it is a table")
    if state == "two headings":
        return ("run-open: warn: the hand-off has two '## Findings ledger' headings: ledger and "
                "decision will refuse until one heading remains")
    if state == "no section":
        return ("run-open: warn: the hand-off has no '## Findings ledger' section: ledger and "
                "decision refuse (exit 2) until the section and its table exist")
    return None


def trace_warning(state, dry_run):
    """run-open's one warning line for a Trace section the boundary cannot append to, or None."""
    if state == "seeded":
        return ("run-open: warn: the hand-off's '## Trace' section held no table — the five-column "
                "header %s under the heading, so boundary appends its rows there"
                % ("would be seeded" if dry_run else "was seeded"))
    if state == "misplaced":
        return ("run-open: warn: the hand-off's '## Trace' table sits below prose, where boundary "
                "cannot find it: move the table under the heading")
    if state == "no section":
        return ("run-open: warn: the hand-off has no '## Trace' section: boundary records its "
                "events and adds no row (exit 3) until the section and its table exist")
    return None


def one_line(text):
    return re.sub(r"\s*\n\s*", " ", str(text)).strip()


def cell(text):
    return one_line(text).replace("|", "\\|")


def set_bullet(lines, key, value, number_only=False):
    """Rewrite one morning-report bullet (`- **Label:** text`), adding it when absent. With
    number_only, refresh only a `(N lines` figure inside the existing text."""
    label = BULLETS[key]
    i = heading_index(lines, "Morning report")
    if i < 0:
        return False
    end = section_end(lines, i)
    pat = re.compile(r"^(\s*[-*]\s+\*\*%s:?\*\*:?\s*)(.*)$" % re.escape(label))
    for j in range(i + 1, end):
        m = pat.match(lines[j])
        if not m:
            continue
        if number_only and re.search(r"\(\d+ lines?", m.group(2)):
            lines[j] = m.group(1) + re.sub(r"\((\d+) (lines?)", "(%s \\2" % value,
                                           m.group(2), count=1)
        elif number_only:
            lines[j] = m.group(1) + "see `## Findings ledger` (%s lines)" % value
        else:
            lines[j] = m.group(1) + one_line(value)
        return True
    insert = end
    while insert > i + 1 and not lines[insert - 1].strip():
        insert -= 1
    text = ("see `## Findings ledger` (%s lines)" % value) if number_only else one_line(value)
    lines.insert(insert, "- **%s:** %s" % (label, text))
    return True


def set_section(lines, key, value):
    i = heading_index(lines, SECTIONS[key])
    if i < 0:
        return False
    lines[i + 1:section_end(lines, i)] = value.rstrip("\n").split("\n") + [""]
    return True


# --------------------------------------------------------------- context and arming --------

_WATERMARK = None


def hooks_dir():
    """The hooks directory: AIMYTH_HOOKS_DIR wins (a staged copy), else beside the skill tree."""
    env = os.environ.get("AIMYTH_HOOKS_DIR")
    if env:
        return os.path.realpath(os.path.expanduser(env))
    return os.path.normpath(os.path.join(HERE, os.pardir, os.pardir, "hooks"))


def watermark():
    """(module, path): the hook imported by file path; (None, path) when it is not there."""
    global _WATERMARK
    if _WATERMARK is not None:
        return _WATERMARK
    path = os.path.join(hooks_dir(), "context-watermark.py")
    if not os.path.isfile(path):
        _WATERMARK = (None, path)
        return _WATERMARK
    spec = importlib.util.spec_from_file_location("context_watermark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _WATERMARK = (module, path)
    return _WATERMARK


_LANE = None


def lane_module():
    """(module, path, error): the lane wrapper imported by file path for its classifier, never
    copied; (None, path, reason) when it is missing or does not import (a torn write)."""
    global _LANE
    if _LANE is not None:
        return _LANE
    path = os.environ.get("AIMYTH_LANE_PY") or os.path.join(HERE, "lane.py")
    path = os.path.realpath(os.path.expanduser(path))
    if not os.path.isfile(path):
        _LANE = (None, path, "lane.py not found at %s" % path)
        return _LANE
    try:
        spec = importlib.util.spec_from_file_location("lane_wrapper", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:   # a torn or broken file: report it, never classify from a copy
        _LANE = (None, path, "lane.py at %s does not import: %s" % (path, exc))
        return _LANE
    for name in ("classify", "limit_signal", "parse_transcript"):
        if not callable(getattr(module, name, None)):
            _LANE = (None, path, "lane.py at %s has no %s()" % (path, name))
            return _LANE
    _LANE = (module, path, None)
    return _LANE


def window():
    module, _ = watermark()
    if module is not None and hasattr(module, "window"):
        return module.window()
    try:
        w = int(os.environ.get("AIMYTH_CONTEXT_WINDOW") or 0)
    except ValueError:
        w = 0
    return w if w > 0 else DEFAULT_WINDOW


def edges():
    module, _ = watermark()
    if module is not None and hasattr(module, "bands"):
        found = tuple(module.bands())
        if len(found) >= 2:
            return found
    raw = os.environ.get("AIMYTH_BANDS") or ""
    parts = [p.strip() for p in raw.split(",")] if raw else []
    if 2 <= len(parts) <= 3 and all(p.isdigit() for p in parts):
        found = tuple(int(p) for p in parts)
        if found[0] > 0 and found[-1] <= 100 and list(found) == sorted(found):
            return found
    return DEFAULT_EDGES


def band_edge(context, w, e):
    """The highest edge the figure has reached (lower edge inclusive), 0 below the first."""
    reached = [edge for edge in e if context * 100 >= edge * w]
    return reached[-1] if reached else 0


def transcript_for(sid, root=None):
    """The head's transcript: the vault's project directory first, then a unique hit across
    the projects root (a head started elsewhere); else the direct path, so the unmetered
    reason names where it was expected. `root` overrides the projects root for a caller that
    was given one (extract-transcript's --projects-root); everything else is unchanged."""
    root = root or projects_root()
    direct = os.path.join(root, dashed(vault_root()), "%s.jsonl" % sid)
    if os.path.isfile(direct):
        return direct
    hits = sorted(globmod.glob(os.path.join(root, "*", "%s.jsonl" % sid)))
    return hits[0] if len(hits) == 1 else direct


def measure_head(sid):
    """The watermark hook's measure() on the head's transcript, plus percent and band edge."""
    module, path = watermark()
    if not sid:
        return {"reason": "no head session in the record", "transcript": None}
    if module is None:
        return {"reason": "context-watermark.py not found at %s" % path, "transcript": None}
    tp = transcript_for(sid)
    m = dict(module.measure(tp))
    m["transcript"] = tp
    if m.get("context") is None:
        m["reason"] = "%s: %s" % (m.get("reason", "unknown"), tp)
        return m
    w, e = window(), edges()
    m["percent"] = m["context"] * 100 // w
    m["band"] = band_edge(m["context"], w, e)
    return m


def context_text(m):
    if m.get("context") is None:
        return "unmetered (%s)" % m.get("reason", "unknown")
    return "%s tokens (%d %%)" % (format(m["context"], ","), m["percent"])


def armed(sid):
    """(armed, how): the environment first, then the marker file the hooks also honour."""
    if os.environ.get("AIMYTH_HANDSOFF") == "1":
        return True, "env"
    if sid and TOKEN_RE.fullmatch(sid) and os.path.isfile(
            os.path.join(state_dir(), "armed-" + sid)):
        return True, "marker"
    return False, "none"


def probe_bound(cap, left):
    """The bound on ONE probe: its own cap, cut to the budget left of the caller's deadline and
    never below zero; `left` None — no deadline — keeps the cap whole. Successive probes drawn
    from one budget therefore share it, the second bounded by what the first left, while each
    keeps the individual cap its own helper documents."""
    return cap if left is None else max(0.0, min(cap, left))


def probe_bound_text(bound, left, cap):
    """How an outcome line names the bound a probe ran under: the budget where the deadline cut
    it, else the probe's own cap."""
    return ("the %.1f s left of the deadline" % bound) if left is not None and bound < cap \
        else "%d s" % cap


def ps_row(pid, timeout=None):
    """(pid, ppid, command) from one `ps` row, else None; `timeout` bounds the call
    (PS_TIMEOUT_S by default; the launch check passes the lower of that cap and the budget left
    of its deadline, probe_bound)."""
    try:
        out = subprocess.run(["ps", "-o", "pid=,ppid=,comm=", "-p", str(pid)],
                             capture_output=True, text=True,
                             timeout=PS_TIMEOUT_S if timeout is None else max(0.0, timeout)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    parts = out.split(None, 2)
    if len(parts) < 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), parts[2].strip()
    except ValueError:
        return None


def head_pid(arg):
    """(pid, pid_src): --pid wins; else the nearest ancestor whose command is the harness."""
    if arg is not None:
        return int(arg), "arg"
    pid = os.getppid()
    for _ in range(32):
        row = ps_row(pid)
        if row is None:
            break
        _, ppid, comm = row
        if comm == HARNESS or comm.endswith(os.sep + HARNESS):
            return pid, "parent-walk"
        if ppid <= 1 or ppid == pid:
            break
        pid = ppid
    return None, "none"


def pid_alive(pid):
    """Whether a process answers signal 0. A value os.kill cannot take — not an int, or outside
    the platform's signed 32-bit range — names no process and is not alive.
    Callers reading a pid from an event validate it first (usable_pid)."""
    if isinstance(pid, bool) or not isinstance(pid, int) or not -PID_MAX - 1 <= pid <= PID_MAX:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def parse_etime(text):
    """Seconds from one `ps -o etime=` field ([[dd-]hh:]mm:ss), else None."""
    m = re.fullmatch(r"\s*(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)\s*", text or "")
    if not m:
        return None
    days, hours, minutes, seconds = (int(g) if g else 0 for g in m.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def process_age_s(pid, timeout=None):
    """The process's age in whole seconds from `ps -o etime=`, else None: no ps, no such
    process, a row this parser does not read, or a call that ran past `timeout` (PS_TIMEOUT_S by
    default; the launch check passes the lower of that cap and the budget left of its deadline,
    probe_bound)."""
    try:
        out = subprocess.run(["ps", "-o", "etime=", "-p", str(pid)], capture_output=True,
                             text=True,
                             timeout=PS_TIMEOUT_S if timeout is None else max(0.0, timeout)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    rows = out.strip().splitlines()
    return parse_etime(rows[0]) if rows else None


def process_chain_read():
    """(chain, whole): this process, its parent and every ancestor the `ps` walk reaches, nearest
    first (the caller's own process tree, inside which a head's own calls run), and whether the
    walk reached the top of the tree (a parent at or below pid 1, or a pid already in the chain).
    A walk that stops on a row it cannot read (no `ps`, a failing `ps`, an unparseable row) or at
    the parent walk's bound of 32 steps is not whole: a pid outside it may still be an ancestor."""
    chain = [os.getpid(), os.getppid()]
    pid = os.getppid()
    if pid <= 1:
        return chain, True
    for _ in range(32):
        row = ps_row(pid)
        if row is None:
            return chain, False
        _, ppid, _ = row
        if ppid <= 1 or ppid in chain:
            return chain, True
        chain.append(ppid)
        pid = ppid
    return chain, False


def process_chain():
    """The chain process_chain_read() walks, whole or not (own_ancestor's use: a pid the walk
    cannot place is not refused there either)."""
    return process_chain_read()[0]


def own_ancestor(pid):
    """(age in seconds, command) when pid is one of this caller's ancestors and has run longer
    than ANCESTOR_AGE_S, else None — also when its age cannot be read, since the starter's
    bounded wait still ends with a named reason. This process itself is never a predecessor."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 1 or pid not in process_chain()[1:]:
        return None
    age = process_age_s(pid)
    if age is None or age <= ANCESTOR_AGE_S:
        return None
    row = ps_row(pid)
    return age, (row[2] if row else "command unknown")


def refuse_own_ancestor(candidates):
    """The launcher's-own-pid refusal for `successor` (register entries 2026-09-10 10:51 and
    2026-09-12 20:0x): exit 2 naming the pid, its source, command and age, before anything is
    written. `candidates` are (pid, source) pairs a launcher can supply."""
    for pid, source in candidates:
        found = own_ancestor(pid)
        if found:
            die("%s %s is this caller's own ancestor (%s, running %d s, over the %d s bound): the "
                "starter would wait on the caller itself and never start the head; a seed pid "
                "must belong to a process that exits within seconds, never the launcher (`$$` "
                "names the launcher's shell, inside a subshell too), or pass no pid"
                % (source, pid, found[1], found[0], ANCESTOR_AGE_S))


def usable_pid(value):
    """The value as a pid this file may act on — an int (never a bool) from 2 to PID_MAX — else
    None: pid 1 is init, never a head, and past PID_MAX os.kill overflows. Every pid read from
    an event passes through here (or head_start_pid) before any call acts on it."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 1 or value > PID_MAX:
        return None
    return value


def head_start_pid(ev):
    """The pid a head-start event names when it can be a live head: a usable pid (an int above
    1, since pid 1 is init and never a head, and within PID_MAX, since a larger figure names no
    process), and never a seed run-open's (a seed never runs)."""
    if ev.get("event") == "run-open" and ev.get("session_kind") == "seed":
        return None
    return usable_pid(ev.get("pid"))


def foreign_head(events, extra_pids=()):
    """The two-heads check (register entry 2026-09-03): None when the record's last head start
    names no other live head, else (verdict, event, pid, detail). `refuse` stands on positive
    evidence only: no head-exit follows the start, its pid is alive, this caller's process chain
    was read to the top of the tree and the pid is outside it (`extra_pids`, --i-am-pid,
    included), and the process's age and the event's time were both read and show the process
    started no later than the event plus PID_START_SLACK_S. `unverified` is a live pid outside
    the chain that cannot be placed, because the walk stopped on a row it could not read or the
    age or the event's time is unreadable: the caller warns and proceeds, since a guard never
    fires on its own broken premise."""
    i = last_index(events, START_EVENTS)
    if i < 0:
        return None
    ev = events[i]
    pid = head_start_pid(ev)
    if pid is None or any(e.get("event") == "head-exit" for e in events[i + 1:]):
        return None
    chain, whole = process_chain_read()
    mine = set(chain) | {int(p) for p in extra_pids if p is not None}
    if pid in mine or not pid_alive(pid):
        return None
    age, ts = process_age_s(pid), parse_ts(ev.get("ts"))
    if age is not None and ts is not None and time.time() - age > ts + PID_START_SLACK_S:
        return None   # the process started after the event: a reused pid, not that head
    unread = [name for name, missing in (
        ("this caller's process chain (the ps walk stopped on a row it could not read)",
         not whole),
        ("the process's age", age is None),
        ("the head start's time", ts is None)) if missing]
    named = "the %s at %s names pid %d" % (ev.get("event"), ev.get("ts", "no ts"), pid)
    if unread:
        return ("unverified", ev, pid,
                "%s, alive with no head-exit after it and outside the %d pid(s) read from pid %d, "
                "but %s could not be read" % (named, len(mine), os.getpid(),
                                              " and ".join(unread)))
    return ("refuse", ev, pid,
            "%s, alive for %d s, with no head-exit after it, outside this caller's process chain "
            "(%d pid(s) from pid %d)" % (named, age, len(mine), os.getpid()))


def refuse_two_heads(a, path, events, what):
    """Exit 9 with one line and an observation when another live head holds the run, on positive
    evidence only; one `warn:` line and None when a live head start cannot be placed (the check
    could not read what it needs); None to go on. The observation is the evidence on the record;
    a dry run writes nothing."""
    found = foreign_head(events, [getattr(a, "i_am_pid", None)])
    if found is None:
        return None
    verdict, _, _, detail = found
    if verdict != "refuse":
        say("warn: %s: the two-heads check cannot verify the run's last head start: %s; the call "
            "proceeds (the check refuses only on a live head it can place outside this caller's "
            "process chain; --i-am-pid names this caller's own head when the walk cannot reach "
            "it)" % (what, detail))
        return None
    if not a.dry_run:
        append_record(path, event(a.run, "observation", phase="", what=TWO_HEADS_WHAT,
                                  note="%s refused: %s" % (what, detail)))
    say("%s: TWO HEADS — REFUSED (exit %d): %s; another head holds run %s, so this caller stands "
        "down (a caller whose own head process the parent walk cannot reach passes --i-am-pid)"
        % (what, EXIT_TWO_HEADS, detail, a.run))
    return EXIT_TWO_HEADS


# ------------------------------------------------------------------ the console window -----

def console_command_path(run):
    """The run's opener script, beside its record in the run store (never a temp path, so a
    stale one is found and rewritten rather than accumulating)."""
    return os.path.join(store_root(), "spawn-records",
                        token(run, "run id") + "-console.command")


def console_command_text(run):
    """The opener script's whole content: a title line, then this interpreter, this script,
    `watch --run R`, with the run store and the vault carried as environment so the console
    reads the record its writer used whatever the login shell Terminal starts it in exports. A
    `.command` file runs in a fresh login shell whose working directory is the home directory,
    so no `cd` is written: every path here is absolute. Line 2 titles the window with the run's
    name (a live console can be told from an empty tab); line 3 is the exec. Every path is
    derived — sys.executable, this file's own absolute path, store_root(), vault_root() — so the
    shipped source carries none of them as a literal."""
    rid = token(run, "run id")
    return ("#!/bin/sh\nprintf '\\033]0;%%s\\007' %s\n"
            "exec env LLM_WIKI_STORE=%s CLAUDE_PROJECT_DIR=%s %s -B %s watch --run %s\n"
            % (shlex.quote(CONSOLE_TITLE % rid), shlex.quote(store_root()),
               shlex.quote(vault_root()), shlex.quote(sys.executable),
               shlex.quote(os.path.abspath(__file__)), shlex.quote(rid)))


def write_console_command(run):
    """The opener script written 0755, rewritten when stale (the interpreter or this file moved,
    or the run store was rebuilt): the path, or None with a note when it cannot be written."""
    path = console_command_path(run)
    text = console_command_text(run)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        current = None
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                current = handle.read()
        if current != text:
            write_atomic(path, text)
        os.chmod(path, 0o755)
    except OSError as exc:
        note("viewer: cannot write the console command %s: %s" % (path, exc))
        return None
    return path


def console_alive(run, timeout=None):
    """The pids of the processes already showing this run's console. Two spellings count: the
    command as it is launched (`handsoff.py watch --run R`) and the command as it RUNS, since
    `watch` execs watch.py in place and its process reads `… /watch.py --run R`.
    A pattern on the first spelling alone misses that process.
    The run id is escaped and the pattern is passed as an argv item to `pgrep`, never through a
    shell, so this probe never matches its own command line. `timeout` bounds the pgrep call
    (VIEWER_TIMEOUT_S by default; wait_console passes the time left of its bound); a probe that
    runs past it is no console, with one stderr note."""
    rid = re.escape(token(run, "run id"))
    pattern = r"(handsoff\.py watch|watch\.py) --run %s([[:space:]]|$)" % rid
    try:
        proc = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True,
                              timeout=VIEWER_TIMEOUT_S if timeout is None else max(0.0, timeout))
    except (OSError, subprocess.SubprocessError) as exc:
        note("viewer: cannot probe for a live console (%s: %s)" % (type(exc).__name__, exc))
        return []
    pids = []
    for field in proc.stdout.split():
        try:
            pid = int(field)
        except ValueError:
            continue
        if pid != os.getpid():
            pids.append(pid)
    return pids


def console_starting(run):
    """The age in seconds of a console opened within CONSOLE_START_GRACE_S, else None: the
    opener sets the command file's mtime at every open (mark_console_opening) and pushes it into
    the past on a failed open (mark_console_failed), so a fresh mtime means a window Terminal is
    still bringing up, whose process console_alive cannot see yet. A
    missing file, an old file or an unreadable mtime is None: no claim."""
    path = console_command_path(run)
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return None
    return age if 0 <= age < CONSOLE_START_GRACE_S else None


def mark_console_opening(path):
    """Stamp the command file with the clock just before the opener runs, whatever its content
    (write_console_command rewrites only stale content, so the stamp is explicit)."""
    try:
        os.utime(path, None)
    except OSError as exc:
        note("viewer: cannot stamp the console command %s: %s" % (path, exc))


def mark_console_failed(path):
    """Push the command file's mtime past the grace window after a failed open, so the failure
    never reads as a console still starting."""
    past = time.time() - 2 * CONSOLE_START_GRACE_S
    try:
        os.utime(path, (past, past))
    except OSError as exc:
        note("viewer: cannot unstamp the console command %s: %s" % (path, exc))


def viewer_argv(path, run):
    """(argv, source) for the opener. AIMYTH_VIEWER_CMD, when set, REPLACES the whole opener
    command: it is split with shlex, the command file's path is appended as the last argument,
    and it is run in list form — never a shell string, so no word of it is re-parsed by a shell.
    The default opener uses /usr/bin/open -g with the command file. Opening in the background keeps
    keyboard input in the current application. The executable is the configured absolute opener path,
    and the existing override can select a recording stub or a platform-specific opener. A failed attempt is retried
    VIEWER_RETRIES time(s) with the same command. The run is unused here since the title moved
    into the command file; callers still pass it."""
    custom = os.environ.get("AIMYTH_VIEWER_CMD")
    if custom:
        return shlex.split(custom) + [path], "AIMYTH_VIEWER_CMD"
    return [open_bin(), "-g", path], "open"


def open_bin():
    """The opener's executable: AIMYTH_OPEN_BIN when set and non-empty (a suite's recording
    stub, or a platform whose `open` lives elsewhere), else OPEN_BIN, the absolute /usr/bin/open
    used by default."""
    return os.environ.get("AIMYTH_OPEN_BIN") or OPEN_BIN


def which(word):
    """The executable a bare command word resolves to on PATH, else the word itself: the
    opener's path, named on the viewer's lines."""
    if not word or os.sep in word:
        return word
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(folder, word)
        if folder and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return word


def run_viewer(argv):
    """(True, "", stderr) when the command exits 0, else (False, why, stderr). Never raises and
    never fails a caller: a missing binary, a timeout and a non-zero exit are all one class. The
    command's standard error is returned either way, cut at NOTE_CUT characters, so a caller
    can log it (register entry 2026-09-09 11:21)."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=VIEWER_TIMEOUT_S)
    except FileNotFoundError:
        return False, ("%s not found (no such file)" % argv[0] if os.sep in argv[0]
                       else "%s not on PATH" % argv[0]), ""
    except subprocess.TimeoutExpired:
        return False, "%s timed out after %d s" % (argv[0], VIEWER_TIMEOUT_S), ""
    except (OSError, subprocess.SubprocessError) as exc:
        return False, "%s: %s" % (argv[0], exc), ""
    err = (proc.stderr or "").strip().replace("\n", " ")[:NOTE_CUT]
    if proc.returncode == 0:
        return True, "", err
    tail = (proc.stderr or proc.stdout or "").strip().replace("\n", " ")[:120]
    return False, "%s exit %d%s" % (argv[0], proc.returncode, ": " + tail if tail else ""), err


def viewer_log(log, line):
    """One timestamped viewer line appended to a detach log, when the caller names one; a log
    that cannot be written is one stderr note, never a failure."""
    if not log:
        return
    try:
        os.makedirs(os.path.dirname(log) or ".", exist_ok=True)
        with open(log, "a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (now(), line))
    except OSError as exc:
        note("viewer: cannot write the detach log %s: %s" % (log, exc))


def run_viewer_key(run):
    """(value, source): the run's viewer key from the DEFAULT grants path — the one file the
    head fence and the status hook read too, and the key's only home (as `on_limit`, D42). A
    missing file or key is the default `terminal`, and the source says which."""
    return viewer_of(read_grants(grants_path(run)))


def by_hand_line(run):
    """The line the owner runs when no window could be opened; the same derived paths."""
    return "python3 -B %s watch --run %s" % (os.path.abspath(__file__), token(run, "run id"))


def open_console(run, viewer=None, dry_run=False, why="", log=None):
    """Put a Terminal window on this run's console (`handsoff.py watch --run R`), the window
    part of the console. Returns True when a window was opened.

    A VIEWER FAILURE NEVER FAILS A LAUNCH: every path here ends in one stderr line naming the
    reason and the by-hand command, and the calling primitive still exits 0. `viewer: none`
    opens nothing; --dry-run prints the command line, opens nothing and writes no file. A failed
    first attempt is retried VIEWER_RETRIES time(s) with the same command; every attempt's opener
    path, outcome and standard error are printed, and written to `log` (the detach log) when the
    caller names one; the success line names the command file, the opener and the attempt that
    opened it (register entry 2026-09-09 11:21)."""
    if viewer is None:
        viewer, _ = run_viewer_key(run)
    if viewer != "terminal":
        line = "viewer: none (grants) · no window%s" % (" · " + why if why else "")
        say(line)
        viewer_log(log, line)
        return False
    path = console_command_path(run)
    argv, source = viewer_argv(path, run)
    if dry_run:
        say("viewer: dry run · command file %s (not written) · would run: %s · retry: the same "
            "command %d time(s) on a failure (%s)"
            % (path, " ".join(shlex.quote(w) for w in argv), VIEWER_RETRIES, source))
        return False
    written = write_console_command(run)
    if written is None:
        line = ("viewer: no Terminal window (the console command could not be written); run by "
                "hand: %s" % by_hand_line(run))
        note(line)
        viewer_log(log, line)
        return False
    mark_console_opening(path)
    opener = which(argv[0])
    failures = []
    ok = False
    for attempt in range(1 + VIEWER_RETRIES):
        label = "first attempt" if attempt == 0 else "retry"
        ok, fail, err = run_viewer(argv)
        viewer_log(log, "viewer: %s via %s (%s) on %s · %s%s" % (
            label, opener, source, path, "opened" if ok else "failed: %s" % fail,
            " · stderr: %s" % err if err else ""))
        if ok:
            if err:
                note("viewer: %s printed on standard error: %s" % (opener, err))
            break
        failures.append("%s: %s" % (label, fail))
    if not ok:
        mark_console_failed(path)
        line = ("viewer: no Terminal window (command file %s; %s); run by hand: %s"
                % (path, "; ".join(failures), by_hand_line(run)))
        note(line)
        viewer_log(log, line)
        return False
    confirmed = ""
    if source != "AIMYTH_VIEWER_CMD":
        # `open` returns once Launch Services has handed the file to Terminal and never sees
        # the console start, so the window is counted open only once the run's `watch` process
        # shows in the table. A clean opener exit alone does not prove a console exists.
        # A custom viewer command is not confirmed: it is
        # the caller's own, and the suites' stubs start no process.
        pids, waited, _ = wait_console(run)
        if not pids:
            mark_console_failed(path)
            line = ("viewer: no Terminal window (command file %s; %s exited 0 but no console "
                    "process for the run appeared within %d s); run by hand: %s"
                    % (path, opener, CONSOLE_START_GRACE_S, by_hand_line(run)))
            note(line)
            viewer_log(log, line)
            return False
        confirmed = " · console pid %s confirmed after %.1f s" % (
            ", ".join(str(p) for p in pids), waited)
    line = "viewer: Terminal window opened on %s via %s (%s)%s%s" % (
        path, opener, "first attempt" if not failures else "retry, after %s" % failures[0],
        confirmed, " · " + why if why else "")
    say(line)
    viewer_log(log, line)
    return True


def wait_console(run, bound=None, step=None):
    """(pids, seconds waited, probes made): the run's console pids once console_alive finds any
    inside `bound`, polled every `step` (the confirmation constants by default); ([], waited,
    probes) when none showed inside it. The bound is checked before a result is accepted and
    each probe's own timeout is the lower of its cap and the time left of it (probe_bound), so
    the wait never runs past the bound and a pid that shows only after it is a timeout, never a
    window; the probes are capped at
    ceil(bound / step), 30 at the defaults."""
    bound = CONSOLE_START_GRACE_S if bound is None else bound
    step = CONSOLE_CONFIRM_STEP_S if step is None else step
    cap = max(1, int(math.ceil(bound / step))) if step > 0 else 1
    t0 = time.monotonic()
    probes = 0
    while True:
        left = bound - (time.monotonic() - t0)
        if left <= 0 or probes >= cap:
            return [], time.monotonic() - t0, probes
        probes += 1
        pids = console_alive(run, timeout=probe_bound(VIEWER_TIMEOUT_S, left))
        waited = time.monotonic() - t0
        if pids and waited <= bound:
            return pids, waited, probes
        if waited >= bound or probes >= cap:
            return [], waited, probes
        time.sleep(max(0.0, min(step, bound - waited)))


def console_lock_path(run):
    """The lock file whose advisory lock IS this run's one-window claim, beside the run's record
    (never a temp path, so every opener of the run queues on the same one). The file itself holds
    only the diagnostic body and is never removed: its LOCK STATE is the claim, so a file left
    behind claims nothing."""
    return os.path.join(store_root(), "spawn-records",
                        token(run, "run id") + CONSOLE_LOCK_SUFFIX)


def console_claim_body(phase):
    """The claim's body `<pid> <ts> <phase>`, written into the locked file for the DIAGNOSTIC
    alone — what a second opener's refusal names. Nothing decides on it; the lock decides."""
    return "%d %s %s\n" % (os.getpid(), now(), phase)


def read_console_claim(fd):
    """(pid, phase) from a held lock's body. A body that is empty or unreadable — the instant
    between a holder's lock and its write, or a write that failed — still belongs to a holder, so
    the pid reads -1 rather than None and no reader mistakes a live claim for a free one
    (lane.py's read_session_body, the same shape on the same mechanism)."""
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        parts = os.read(fd, 128).decode("utf-8", "replace").strip().split()
    except OSError:
        parts = []
    try:
        pid = int(parts[0]) if parts else -1
    except ValueError:
        pid = -1
    return (pid if pid > 0 else -1), (parts[2] if len(parts) > 2 else "")


def console_holder_text(pid, phase):
    """How a refusal names the holder of this run's console claim."""
    who = ("pid %d" % pid if isinstance(pid, int) and pid > 0
           else "a pid the claim's body does not name yet")
    return who + (", phase %s" % phase if phase else "")


def take_console_lock(run):
    """This run's one-window claim, as an advisory lock: (True, fd, "") when this caller now
    holds it, (False, None, why) when another opener holds it, (None, None, why) when the lock
    cannot be worked at all — no fcntl off POSIX, or a lock file that will not open — and the
    caller then opens without a claim, because a viewer failure never fails a launch.

    `fcntl.flock(fd, LOCK_EX | LOCK_NB)` is ONE operation, so the check and the claim cannot be
    interleaved; the kernel releases it when its holder dies, so a crashed opener leaves nothing
    to take over; and the lock exists before any content does, so there is no empty-file instant
    to read as free. That is why the ruling on the №163 fold put the claim here rather than on a
    file whose existence, and whose age, were the claim (critic review pass 2, findings 2 and
    the release window). Nothing is renamed, replaced or removed on any path of this helper.
    lane.py's hold_session (№161) is the same mechanism; this is its twin rather than a call into
    it, because lane.py imports handsoff.py — a call the other way would re-enter that import —
    and because the two answer a failed body write differently, by their own contracts."""
    lock = console_lock_path(run)
    if fcntl is None:
        return None, None, "no fcntl on this platform, so the console claim cannot be locked"
    try:
        os.makedirs(os.path.dirname(lock), exist_ok=True)
    except OSError:
        pass
    try:
        fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
    except OSError as exc:
        return None, None, "cannot open the console claim %s (%s)" % (lock, exc)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        pid, phase = read_console_claim(fd)
        os.close(fd)
        return False, None, ("another opener (%s) holds this run's console claim (%s)"
                             % (console_holder_text(pid, phase), lock))
    return True, fd, ""


def write_console_claim(fd, phase):
    """The claim's body written under the lock: True when it is on disk, False after a NAMED,
    NON-FATAL viewer outcome — one stderr line, the opener runs on, still holding the lock, and
    the primitive still exits 0. The body is the diagnostic alone, so losing it costs a later
    refusal the holder's name and nothing else. A body-write failure must leave the opener and
    lock release available. This is where the twin parts from lane.py's
    hold_session, which refuses the call instead: a session claim whose body is empty for good
    would leave every later refusal naming nobody, while a viewer failure never fails a launch."""
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, console_claim_body(phase).encode("utf-8"))
        os.fsync(fd)
    except OSError as exc:
        note("viewer: claim body not written (%s): opening anyway" % exc)
        return False
    return True


def release_console_lock(fd):
    """Unlock and close once the whole open-and-confirm has ended, whatever its outcome. Neither
    step can fail the caller, and neither removes the file: an unlock that fails is named, and
    the kernel releases the lock when this process ends either way."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError as exc:
        note("viewer: the console claim could not be released (%s): the kernel releases it when "
             "this process ends" % exc)
    try:
        os.close(fd)
    except OSError as exc:
        note("viewer: the console claim's descriptor could not be closed (%s): the kernel closes "
             "it when this process ends" % exc)


def open_console_if_dark(run, viewer=None, dry_run=False, log=None):
    """The opener for a primitive that starts a head into a run that may already be watched:
    one window per run, so the owner's `q` and a by-hand restart get a fresh one while a running
    console is never doubled. Away runs included — the key alone decides.

    Concurrent openers (N Agent lanes in one message run N spawn-guard hooks at once; two lane.py
    workers a second apart) settle on ONE ADVISORY LOCK, `<run>-console.lock` beside the record,
    taken before this caller's first live-console probe and held until its confirmation, or its
    give-up, has ended (take_console_lock). Three
    properties decide, and each retired a fault of the claim file of №162:
    - the check and the claim are one kernel operation, so no interleaving of two callers admits
      both, and there is no read-then-replace window for a plant to widen;
    - the live probe runs UNDER the lock, so a caller that saw no console before it queued
      discards that observation: by the time it holds the lock, the caller ahead of it has
      opened, confirmed and released (the same pass's first new finding, the release window);
    - the kernel releases the lock when its holder dies, so a crashed opener leaves nothing
      stale, nothing to take over and nothing to age out — no rename, no unlink, no threshold.
    A caller that cannot take the lock opens nothing: one line on standard error naming the
    holder from the claim's body, no window, and exit 0 at the primitive, as at every viewer
    outcome. The grace stamp stays as the second guard under the lock, for the window Terminal is
    still bringing up when a previous opener has already released.
    Neither opt-out takes the lock: `viewer: none` opens nothing and a dry run writes nothing."""
    if viewer is None:
        viewer, _ = run_viewer_key(run)
    if viewer != "terminal" or dry_run:
        return open_console(run, viewer=viewer, dry_run=dry_run, log=log)
    held, fd, why = take_console_lock(run)
    if held is False:
        line = "viewer: %s · no second window" % why
        note(line)
        viewer_log(log, line)
        return False
    if held is None:
        note("viewer: %s; opening anyway" % why)
    body = bool(held) and write_console_claim(fd, CONSOLE_PHASE_CHECK)
    try:
        live = console_alive(run)
        if live:
            line = ("viewer: a console is already alive (pid %s) · no second window"
                    % ", ".join(str(p) for p in live))
            say(line)
            viewer_log(log, line)
            return False
        age = console_starting(run)
        if age is not None:
            line = ("viewer: a console was opened %.0f s ago and may still be starting · no "
                    "second window" % age)
            say(line)
            viewer_log(log, line)
            return False
        if body:   # a body that could not be written is not written again: one line per open
            write_console_claim(fd, CONSOLE_PHASE_OPEN)
        return open_console(run, viewer=viewer, dry_run=False,
                            why="no console was alive" + (" · " + why if why else ""), log=log)
    finally:
        if fd is not None:
            release_console_lock(fd)


def cmd_open_console(a):
    """`open-console --run R`: the console window on demand — one when none is alive, on the
    one-window rule (open_console_if_dark: the run's console lock, then the live probe and the
    grace stamp under it); a viewer failure is one stderr line and exit 0, as at every other
    opener call. A second opener while another holds the lock opens nothing, names the holder on
    standard error and still exits 0, and takes nothing over. `--check`
    opens nothing: it prints the pid(s) of the run's live console and exits 0, or `NO CONSOLE`
    (with the age of a window still inside its start grace, when there is one) and exits 1 —
    the live check the register entry of 2026-09-17 20:29 asked for."""
    run = token(a.run, "run id")
    if a.check:
        pids = console_alive(run)
        if pids:
            say("console: pid %s alive on watch --run %s"
                % (", ".join(str(p) for p in pids), run))
            return 0
        age = console_starting(run)
        say("NO CONSOLE for %s%s" % (
            run, " (a window was opened %.0f s ago and may still be starting)" % age
            if age is not None else ""))
        return 1
    # Both opt-outs, as at every other opener call: --viewer for this call, else AIMYTH_VIEWER
    # in the environment, else the grants file's key.
    viewer = a.viewer or os.environ.get("AIMYTH_VIEWER") or None
    if viewer is not None and viewer not in VIEWER_VALUES:
        note("open-console: AIMYTH_VIEWER=%r is neither terminal nor none · the grants file "
             "decides" % viewer)
        viewer = None
    open_console_if_dark(run, viewer=viewer, dry_run=a.dry_run)
    return 0


# ------------------------------------------------------------------ the launch check -------

LAUNCH_HEAD_EVENTS = START_EVENTS + ("head-exit",)   # the events the check reads as the head's state


def start_session(ev):
    """The session a head event names: `session_id` on a head-successor or head-resumed,
    `session` on a run-open or run-resume; `?` when neither is a string."""
    sid = ev.get("session_id") if ev.get("event") in ("head-successor", "head-resumed") \
        else ev.get("session")
    return sid if isinstance(sid, str) else "?"


def event_pid(ev):
    """The pid an event carries as an int above 1 and within PID_MAX, else None (a seed run-open
    excluded, as head_start_pid excludes it)."""
    return head_start_pid(ev)


UNVERIFIABLE = "pid identity unverifiable: "   # the launch check's prefix for a start it cannot verify


def probe_budget(wait, start=None):
    """The check's ONE deadline, as a callable: the seconds left of `start + wait` at the moment
    it is called, or None where there is no deadline (`--wait 0`, the single read, whose probes
    keep their own caps). Computed once from the start of the check, never per probe and never
    per read, so every probe of every read draws on the same budget (critic review pass 2
    finding 3)."""
    if not wait:
        return lambda: None
    t0 = time.monotonic() if start is None else start
    return lambda: max(0.0, wait - (time.monotonic() - t0))


def head_start_verdict(events, budget=None):
    """The launch check's reading of one record: (state, detail) with state `started` (a head
    start whose pid is alive and whose process started when the event says — both read),
    `pending` (keep polling: no head start after the last head-exit, or only the seed run-open
    so far), `unverified` (keep polling while time remains, then a named non-success: the start
    names a live pid whose age could not be read inside its probe bound, so a reused pid cannot be
    excluded) or `failed` (a terminal reason the check ends on at once: a run-close, an aborted
    starter, a head that exited or whose pid is dead, a reused pid, a start naming no usable pid
    or no readable timestamp). Positive evidence only: a `head exited` observation counts
    against a start only when its note names that start's session, since the OLD head's
    supervisor writes its observation after the new head has started; and identity evidence
    that cannot be read never passes. `budget` is the caller's
    shared deadline, a callable giving the seconds left (probe_budget): each `ps` call is bounded
    by the LOWER of its own cap, PS_TIMEOUT_S, and what is left at the moment it starts, so the
    age probe and the command probe cannot each spend the whole remainder (critic review pass 2
    finding 3). No budget is no deadline, and every probe keeps its own cap."""
    ci = last_index(events, ("run-close",))
    if ci >= 0:
        return "failed", "the run is closed (run-close at %s)" % events[ci].get("ts", "no ts")
    hi = last_index(events, LAUNCH_HEAD_EVENTS)
    if hi < 0:
        return "pending", "no head event on the record yet"
    ev, later = events[hi], events[hi + 1:]
    stamp = ev.get("ts", "no ts")
    if ev.get("event") == "head-exit":
        aborted = next((e for e in later if e.get("event") == "successor-aborted"), None)
        if aborted is not None:
            return "failed", "the starter aborted after the head-exit at %s (successor-aborted %s at %s: %s)" % (
                stamp, aborted.get("reason", "?"), aborted.get("ts", "no ts"),
                str(aborted.get("note", ""))[:NOTE_CUT])
        pid = usable_pid(ev.get("pid"))
        if pid is not None and pid_alive(pid):
            how = ("its pid %d is alive, so the starter waits for it up to its --wait-s (%d s "
                   "by default): pass --wait above that bound" % (pid, STARTER_WAIT_S))
        elif pid is not None:
            how = "its pid %d is gone" % pid
        elif ev.get("pid") is None:
            how = ("no pid on it, so the starter has nothing to wait on: a seed exit, or an "
                   "exit recorded without a pid")
        else:
            how = ("its pid %r is not a usable pid (an integer from 2 to %d), so the starter "
                   "has nothing to wait on" % (ev.get("pid"), PID_MAX))
        return "pending", "the last head event is the head-exit at %s (%s); no head start after it" % (stamp, how)
    sid = start_session(ev)
    label = "%s at %s (session %s)" % (ev.get("event"), stamp, sid)
    exited = next((e for e in later if e.get("event") == "observation"
                   and e.get("what") == "head exited"
                   and sid != "?" and sid in str(e.get("note", ""))), None)
    if exited is not None:
        return "failed", "the head of the %s exited (head exited at %s: %s)" % (
            label, exited.get("ts", "no ts"), str(exited.get("note", ""))[:NOTE_CUT])
    pid = event_pid(ev)
    if pid is None:
        if ev.get("event") == "run-open" and ev.get("session_kind") == "seed":
            return "pending", "only the seed run-open at %s so far: no head start yet" % stamp
        return "failed", "the %s names no usable pid (%r): a live head cannot be confirmed from it" % (
            label, ev.get("pid"))
    if not pid_alive(pid):
        return "failed", "the %s names pid %d, which is not alive" % (label, pid)
    ts = parse_ts(stamp)
    if ts is None:
        return "failed", "%sthe %s carries %s, so when pid %d started cannot be checked against it and a reused pid cannot be excluded" % (
            UNVERIFIABLE, label,
            "no timestamp" if ev.get("ts") is None else "an unreadable timestamp (%r)" % ev.get("ts"),
            pid)
    left = budget() if budget is not None else None
    bound = probe_bound(PS_TIMEOUT_S, left)
    age = process_age_s(pid, timeout=bound)
    if age is None:
        return "unverified", "%sthe %s names pid %d, which is alive, but its age could not be read (`ps -o etime=` gave nothing within %s), so a reused pid cannot be excluded" % (
            UNVERIFIABLE, label, pid, probe_bound_text(bound, left, PS_TIMEOUT_S))
    if time.time() - age > ts + PID_START_SLACK_S:
        return "failed", ("the %s names pid %d, which is alive but started %d s after the event: "
                          "a reused pid, not that head" % (label, pid,
                                                           int(round(time.time() - age - ts))))
    # The second probe of this read draws on what the first left, never on the whole remainder.
    row = ps_row(pid, timeout=probe_bound(PS_TIMEOUT_S, budget() if budget is not None else None))
    return "started", "%s · pid %d alive (%s, running %d s) · model %s effort %s" % (
        label, pid, row[2] if row else "command unread", age,
        ev.get("model") or "none", ev.get("effort") or "none")


def inside_head(events):
    """How this shell sits inside the run's own head, or None: AIMYTH_HANDSOFF=1 in the
    environment (the starter arms every head process with it, and the head's shell tool
    inherits it); the pid the starter waits for — the last head-exit's, else the last head
    start's — among this process's ancestors; or the session marker armed-<sid> for the record's
    head session while a harness process is an ancestor of this shell. A check run there would
    wait on its own replacement: the starter waits for that head to exit."""
    if os.environ.get("AIMYTH_HANDSOFF") == "1":
        return "AIMYTH_HANDSOFF=1 is set in this shell's environment"
    chain = process_chain()[1:]
    for i in (last_index(events, ("head-exit",)), last_index(events, START_EVENTS)):
        if i < 0:
            continue
        pid = usable_pid(events[i].get("pid"))
        if pid is not None and pid in chain:
            return "pid %d, named by the %s at %s, is an ancestor of this shell" % (
                pid, events[i].get("event"), events[i].get("ts", "no ts"))
    sid, _ = head_session(events)
    is_armed, how = armed(sid)
    if is_armed and how == "marker" and head_pid(None)[0] is not None:
        return ("the session marker armed-%s is on disk and this shell runs under a %s process"
                % (sid, HARNESS))
    return None


def cmd_launch_check(a):
    """`launch-check --run R [--wait S] [--poll-s S] [--detach-safe]`: the launch kit's start
    confirmation. Read-only: it polls the record to the deadline for a head start
    whose pid is alive and started when the event says, prints one line per outcome and exits 0
    started, 1 not started, 2 on a premise. `--wait 0` performs a single read. The deadline is computed
    ONCE, at the start, and governs every read and every probe inside a read: each `ps` probe is
    bounded by the lower of its own cap and what is left of that one budget (probe_budget and
    probe_bound; a single read keeps the probe's own cap, having no deadline to run past), a
    start is accepted only inside it, and a start whose identity could not be verified by the
    deadline is a named non-success; probes share one remaining-time budget."""
    path = record_path(a.run)
    if not os.path.isfile(path):
        die("no run record at %s: run-open never ran, so there is no launch to confirm" % path)
    events, bad = read_record(path)
    if is_plain_run(events):
        die("no run-open event in %s: a plain lane record has no head to confirm" % path)
    if not a.detach_safe:
        how = inside_head(events)
        if how:
            die("launch-check REFUSED inside the run's own head (%s): a head that called "
                "successor about itself must never wait on its own replacement, since the "
                "starter waits for that head to exit; run the check from the launcher's shell, "
                "or pass --detach-safe when this shell is not that head" % how)
    wait, step = max(0, int(a.wait)), max(0.05, float(a.poll_s))
    t0, reads = time.monotonic(), 1
    budget = probe_budget(wait, t0)   # one deadline for the whole check; every probe draws on it
    while True:
        state, detail = head_start_verdict(events, budget=budget)
        elapsed = time.monotonic() - t0
        skipped = " · %d unparseable line(s) skipped" % bad if bad else ""
        if state == "started" and wait and elapsed > wait:
            say("launch-check: %s NOT STARTED · %sthe start was confirmed only %.1f s after the "
                "check began, past the %d s deadline (%s); run the check again with a longer "
                "--wait (%d read(s))%s" % (a.run, UNVERIFIABLE, elapsed, wait, detail, reads, skipped))
            return 1
        if state == "started":
            say("launch-check: %s STARTED · %s · seen %.0f s after the check began (%d read(s))%s"
                % (a.run, detail, elapsed, reads, skipped))
            return 0
        if state == "failed":
            say("launch-check: %s NOT STARTED · %s · %.0f s after the check began (%d read(s))%s"
                % (a.run, detail, elapsed, reads, skipped))
            return 1
        if elapsed >= wait:
            if state == "unverified":
                say("launch-check: %s NOT STARTED · %s · %.0f s after the check began (%d read(s))%s"
                    % (a.run, detail, elapsed, reads, skipped))
                return 1
            say("launch-check: %s NOT STARTED · no live head within the %d s deadline: %s "
                "(%d read(s))%s" % (a.run, wait, detail, reads, skipped))
            return 1
        time.sleep(max(0.0, min(step, wait - elapsed)))
        events, bad = read_record(path)
        reads += 1


# ------------------------------------------------------------------ meter and waste --------

def billed_field(line, pattern, cast):
    m = re.search(pattern, line or "")
    if not m:
        return None
    try:
        return cast(m.group(1))
    except ValueError:
        return None


def seed_sessions(events):
    """The session ids the record marks as a launcher's placeholder: `run-open --session-kind
    seed` (T7 of the token-efficiency findings, 2026-09-07). A seed session never ran, so it is
    no head: the table skips it and the meter is never asked to read a transcript it has none
    of. The marking is the record's own field, never the run's or the session's name."""
    found = []
    for ev in events:
        if ev.get("event") == "run-open" and ev.get("session_kind") == "seed":
            sid = ev.get("session")
            if isinstance(sid, str) and sid not in found:
                found.append(sid)
    return found


def run_window(events):
    """(start, end, source): the run's OWN window as the record spells it — the run-open
    timestamp to the run-close timestamp, or to the record's last event where the record holds
    no run-close (T6, 2026-09-07). Metering a head over this window rather than over its whole
    session stops a session shared with attended work from being counted whole against one run.
    (None, None, reason) where the record carries no usable timestamp."""
    stamps = [ev.get("ts") for ev in events if isinstance(ev.get("ts"), str) and ev.get("ts")]
    ro = run_open(events)
    start = ro.get("ts") if isinstance(ro.get("ts"), str) else (stamps[0] if stamps else None)
    close = next((ev for ev in reversed(events) if ev.get("event") == "run-close"), None)
    if close is not None and isinstance(close.get("ts"), str):
        end, how = close["ts"], "run-close"
    elif stamps:
        end, how = stamps[-1], "the record's last event (no run-close)"
    else:
        end, how = None, "no timestamped event"
    if not start or not end:
        return None, None, "the record carries no usable window (%s)" % how
    return start, end, "run-open %s → %s %s" % (start, how, end)


def meter_cmd(meter, run, sid, ro, lanes, start=None, end=None):
    """The meter's command line for one head session, over a window when one is given: the
    `--start`/`--end` pair the meter already takes (its own main), so the head is metered over
    the run's window rather than over its whole session (T6)."""
    vault, root = vault_root(), projects_root()
    cmd = [sys.executable, "-B", meter, "--session", sid, "--lanes", lanes,
           "--spawn-record", record_path(run), "--projects-root", root, "--vault", vault,
           "--project-dir", os.path.join(root, dashed(vault))]
    if ro.get("regime") in ("single", "multi") and ro.get("regime_src") in ("owner", "head"):
        cmd += ["--delegation", ro["regime"], "--delegation-src", ro["regime_src"]]
    if start:
        cmd += ["--start", start]
    if end:
        cmd += ["--end", end]
    return cmd


# Read both meter output streams for the no-transcript refusal. Its die() prints to stdout;
# stderr-only detection would lose that reason (register entries 2026-09-09 15:27 and 2026-09-10 02:49).
METER_NO_LANES = "no readable lane transcript"
METER_REFUSALS = ("fable share: unmetered", "billed: unbilled")   # the meter's own refusal lines
HEAD_ALONE = (" · head alone (--lanes none): the meter found no readable lane transcript under "
              "--lanes auto")


def meter_says(proc):
    """The meter's own words on a non-zero exit: its last refusal line from standard output,
    else the last line of standard error, else the last line of standard output, else ""."""
    out = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    err = [line.strip() for line in (proc.stderr or "").splitlines() if line.strip()]
    said = [line for line in out if line.startswith(METER_REFUSALS)]
    return (said or err or out or [""])[-1]


def meter_command_text(events, run):
    """The boundary's own meter invocation, quoted for a shell, for `boundary --dry-run` (the
    register entry of 2026-09-09 15:27 asks for it printed): the --lanes auto call, and the
    --lanes none retry the no-transcript refusal takes."""
    sid = head_session(events)[0]
    if not sid:
        return "none: no head session in the record"
    if sid in seed_sessions(events):
        return "none: run-open marks session %s a seed" % sid
    cmd = meter_cmd(os.path.join(HERE, "fable-share.py"), run, sid, run_open(events), "auto")
    return "%s (then --lanes none when the meter says '%s')" % (
        " ".join(shlex.quote(word) for word in cmd), METER_NO_LANES)


def meter_line(events, run, override=None, start=None, end=None, session=None):
    """The meter's billed line for the head session, or `failed: exit N · <the meter's own
    refusal>`. Lanes come from the record (--lanes auto); when the record's lanes have written
    no transcript yet the meter refuses, that refusal is read from standard output and standard
    error alike, and the head alone is metered (--lanes none), the line ending `· head alone
    (--lanes none): …` so it says so. Any other refusal is never retried. `session` meters a
    named head rather than the record's last one, and `start`/`end` meter it over a window
    (T6): both are for the waste table's whole-run rows, and every other caller's behaviour is
    unchanged."""
    if override:
        return override
    sid = session or head_session(events)[0]
    if not sid:
        return "failed: no head session in the record"
    if sid in seed_sessions(events):
        return "seed (skipped): run-open marks session %s a seed, which never ran" % sid
    meter = os.path.join(HERE, "fable-share.py")
    if not os.path.isfile(meter):
        return "failed: fable-share.py not found beside handsoff.py"
    ro = run_open(events)
    base = meter_cmd(meter, run, sid, ro, "auto", start, end)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for lanes in ("auto", "none"):
        cmd = list(base)
        cmd[cmd.index("--lanes") + 1] = lanes
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=METER_TIMEOUT_S,
                                  env=env)
        except subprocess.TimeoutExpired:
            return "failed: the meter did not finish in %d s" % METER_TIMEOUT_S
        except OSError as exc:
            return "failed: %s" % exc
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if line.startswith("billed ("):
                    return line.strip() + (HEAD_ALONE if lanes == "none" else "")
            return "failed: the meter printed no billed line"
        if lanes == "auto" and METER_NO_LANES in (proc.stdout or "") + (proc.stderr or ""):
            continue
        said = meter_says(proc)
        return "failed: exit %d%s" % (proc.returncode, " · " + one_line(said)[:300] if said else "")
    return "failed: the meter refused both lane modes"


def count_words(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return len(handle.read().split())
    except OSError:
        return None


# A head gap counts as idle only above this many seconds: the brief's threshold for the head-idle
# measure (2026-09-06), set by judgement, unmeasured. A tool call that runs longer reads as idle,
# since a transcript's timestamps cannot tell a long tool run from a wait.
IDLE_GAP_S = 60
REWRITES_RE = r"rewrites (\d+) \("


def head_calls(path):
    """Epoch timestamps of the head's own calls: every assistant record of its transcript that
    is not a sidechain (a lane's context, never the head's) and carries a parseable timestamp,
    sorted. None when the transcript is missing, unreadable or holds no such record, so the
    caller falls back to the record and says so."""
    if not path or not os.path.isfile(path):
        return None
    stamps = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '"assistant"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if (not isinstance(rec, dict) or rec.get("type") != "assistant"
                        or rec.get("isSidechain")):
                    continue
                t = parse_ts(rec.get("timestamp"))
                if t is not None:
                    stamps.append(t)
    except OSError:
        return None
    return sorted(stamps) or None


def merge_intervals(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def lane_intervals(events, t0, t1):
    """The lane running time inside [t0, t1], merged: from each lane-open or lane-resumed to
    that lane's next lane-closed (t1 when none has come). A lane-closed whose open the record
    does not place is taken as running from t0, the earliest the record can put it — the
    direction that hides idle time rather than inventing it."""
    starts, found = {}, []
    for ev in events:
        kind, lane = ev.get("event"), ev.get("lane")
        if lane is None or kind not in ("lane-open", "lane-resumed", "lane-closed"):
            continue
        t = parse_ts(ev.get("ts"))
        if kind != "lane-closed":
            if t is not None:
                starts[lane] = t
            continue
        start = starts.pop(lane, None)
        if t is not None:
            found.append((start if start is not None else t0, t))
    found += [(start, t1) for start in starts.values()]
    clipped = [(max(a, t0), min(b, t1)) for a, b in found if min(b, t1) > max(a, t0)]
    return merge_intervals(clipped)


def head_idle_s(calls, running, t0, t1):
    """Seconds of [t0, t1] inside a head gap above IDLE_GAP_S and outside every lane interval:
    the span's edges are the head's own acts (the previous boundary, this one)."""
    points = [t0] + [t for t in calls if t0 < t < t1] + [t1]
    idle = 0.0
    for a, b in zip(points, points[1:]):
        if b - a <= IDLE_GAP_S:
            continue
        busy = sum(max(0.0, min(b, y) - max(a, x)) for x, y in running)
        idle += (b - a) - busy
    return idle


def resumed_after(later, close):
    """The first lane-resumed for the same lane among the events after its close, else None;
    the lane session id is matched too when both events carry one."""
    for ev in later:
        if ev.get("event") != "lane-resumed" or ev.get("lane") != close.get("lane"):
            continue
        a, b = ev.get("session_id"), close.get("session_id")
        if a and b and a != b:
            continue
        return ev
    return None


def lane_open_of(events, index, close):
    """The last lane-open before `index` for the lane a lane-closed names, matched on the lane
    session id too when both events carry one; None when the record holds none."""
    for ev in reversed(events[:index]):
        if ev.get("event") != "lane-open" or ev.get("lane") != close.get("lane"):
            continue
        a, b = ev.get("session_id"), close.get("session_id")
        if a and b and a != b:
            continue
        return ev
    return None


def is_plan_lane(events, index, close):
    """A plan-usage lane — a Codex lane, `harness: codex` on its close or its lane-open — whose
    usage sits on the owner's plan: counted, never priced (register entry 2026-09-10 17:43)."""
    if close.get("harness") == "codex":
        return True
    opened = lane_open_of(events, index, close)
    return bool(opened and opened.get("harness") == "codex")


def lane_transcript_bill(close):
    """(dollars, how) for a lane-closed that carries no cost, billed from the lane's own
    transcript by the meter; (None, why not) otherwise. A lane CLI killed with its head returns
    no result, so the wrapper records total_cost_usd null, while the transcript survives the
    kill (register entry 2026-09-07). The close's session id names the transcript under the
    projects root; exactly one hit is metered with --lanes none as a head of its own, and the
    billed line's `head $` figure is the lane's cost. No hit, several hits or a meter refusal is
    a reason, never a zero."""
    sid = close.get("session_id")
    if not isinstance(sid, str) or not TOKEN_RE.fullmatch(sid):
        return None, "the close names no lane session id"
    transcript, why = lane_transcript_path(sid)
    if transcript is None:
        return None, why
    return session_bill(sid, transcript)


def lane_transcript_path(sid):
    """(path, None) for the one transcript a lane session id names under the projects root —
    any project directory, never a guessed one; (None, why) when there is none or several."""
    root = projects_root()
    hits = sorted(globmod.glob(os.path.join(root, "*", sid + ".jsonl")))
    if not hits:
        return None, "no transcript for lane session %s under %s" % (sid, root)
    if len(hits) > 1:
        return None, "%d transcripts for lane session %s under %s" % (len(hits), sid, root)
    return hits[0], None


def head_figure(line):
    """The `head $` figure of a billed line — the session's own list dollars, the same under
    --lanes auto and --lanes none — else None."""
    return billed_field(line, r"head \$([0-9]+(?:\.[0-9]+)?)", float)


def session_bill(sid, transcript, timeout=None):
    """(dollars, how) for one session metered ALONE by fable-share.py (--lanes none) from its
    transcript path: the billed line's `head $` figure. (None, why) on a missing meter, a
    timeout, a refusal (the `unbilled` premise, a missing price table included) or a line with
    no figure — a reason, never a zero. `timeout` bounds the call (default METER_TIMEOUT_S)."""
    meter = os.path.join(HERE, "fable-share.py")
    if not os.path.isfile(meter):
        return None, "fable-share.py not found beside handsoff.py"
    bound = int(timeout) if timeout else METER_TIMEOUT_S
    cmd = [sys.executable, "-B", meter, "--session", sid, "--lanes", "none", "--project-dir",
           os.path.dirname(transcript), "--projects-root", projects_root(), "--vault",
           vault_root()]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=bound,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    except subprocess.TimeoutExpired:
        return None, "the transcript meter did not finish in %d s" % bound
    except OSError as exc:
        return None, "the transcript meter could not run (%s)" % exc
    line = next((x.strip() for x in (proc.stdout or "").splitlines() if x.startswith("billed (")),
                None)
    usd = head_figure(line) if line else None
    if proc.returncode != 0 or usd is None:
        said = meter_says(proc)
        return None, "the transcript meter gave no figure (exit %d%s)" % (
            proc.returncode, ": " + one_line(said)[:160] if said else "")
    return usd, "metered (transcript) %s" % transcript


def price_close(events, index, close, bucket, meter_lanes):
    """Add one non-completed lane-closed to a cost bucket: its recorded cost; else, for a
    plan-usage lane, a name counted and never priced; else its transcript bill when
    `meter_lanes` allows; else a name with the reason it is unmeasured."""
    name = str(close.get("lane") or "unnamed lane")
    cost = close.get("total_cost_usd")
    if isinstance(cost, str):
        try:
            cost = float(cost)
        except ValueError:
            pass
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        bucket["usd"] += float(cost)
        bucket["priced"] += 1
        return
    if is_plan_lane(events, index, close):
        bucket["plan"].append(name)
        return
    if cost is not None:
        bucket["unmeasured"].append((name, "total_cost_usd %s is not a number" % one_line(str(cost))[:40]))
        return
    if not meter_lanes:
        bucket["unmeasured"].append((name, "the close carries no cost and no transcript meter was run"))
        return
    usd, how = lane_transcript_bill(close)
    if usd is None:
        bucket["unmeasured"].append((name, how))
        return
    bucket["usd"] += usd
    bucket["metered"].append((name, usd, how))


def new_bucket():
    return {"usd": 0.0, "priced": 0, "metered": [], "plan": [], "unmeasured": []}


def bucket_figure(bucket):
    """The bucket's dollars, or None (`unmeasured`, never $0.00) when any lane in it is."""
    return None if bucket["unmeasured"] else round(bucket["usd"], 2)


def bucket_src(bucket):
    """How a bucket's figure was made, every lane in it named by the part it took."""
    parts = ["%d close cost(s) as recorded" % bucket["priced"]]
    if bucket["metered"]:
        parts.append("%d metered (transcript): %s" % (len(bucket["metered"]), "; ".join(
            "%s $%.2f" % (name, usd) for name, usd, _ in bucket["metered"])))
    if bucket["plan"]:
        parts.append("%d plan-usage lane(s) counted, never priced: %s"
                     % (len(bucket["plan"]), ", ".join(bucket["plan"])))
    if bucket["unmeasured"]:
        parts.append("unmeasured: %d lane(s) with no cost and no metered transcript (%s), beside "
                     "a priced part of $%.2f" % (len(bucket["unmeasured"]), "; ".join(
                         "%s: %s" % (name, why) for name, why in bucket["unmeasured"]),
                         bucket["usd"]))
    return " · ".join(parts)


# The head fence's own series (head-fence.py log_event): tab-separated lines of timestamp,
# session, component, action and detail under the state directory; its two deny actions.
FENCE_EVENTS_LOG = "events.log"
FENCE_COMPONENT = "head-fence"
FENCE_DENIES = ("deny", "deny-no-grants")


def head_fence_denials(events, since, now_ts):
    """(count or None, source): the head fence's denies inside the span — events.log lines
    whose component is head-fence, whose action is deny or deny-no-grants, whose session is a
    head session in force during the span and whose timestamp falls between the span's start
    and now (register entry 2026-09-06: the boundary's `denials` counts the lanes' tool denials
    alone, and the head's fence denies entered no field). None with the reason when the span has
    no timestamp, the record names no head session or the log is absent or unreadable: a
    missing log is not a measured zero. The source names how many head-fence lines were read,
    the control that the log was reached."""
    t0 = parse_ts(events[since].get("ts")) if 0 <= since < len(events) else None
    if t0 is None:
        return None, "unmeasured: the span's start carries no timestamp"
    sessions = set()
    for i in range(since + 1, len(events) + 1):
        sid = session_at(events, i)
        if sid:
            sessions.add(sid)
    if not sessions:
        return None, "unmeasured: the record names no head session for the span"
    path = os.path.join(state_dir(), FENCE_EVENTS_LOG)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError:
        return None, "unmeasured: no events.log at %s" % path
    except OSError as exc:
        return None, "unmeasured: events.log unreadable at %s (%s)" % (path, exc)
    fence = count = 0
    for line in lines:
        cols = line.split("\t")
        if len(cols) < 4 or cols[2] != FENCE_COMPONENT:
            continue
        fence += 1
        t = parse_ts(cols[0])
        if cols[3] in FENCE_DENIES and cols[1] in sessions and t is not None and t0 <= t <= now_ts:
            count += 1
    return count, ("%d head-fence deny line(s) for session(s) %s in the span, of %d head-fence "
                   "line(s) among %d read from %s" % (count, ", ".join(sorted(sessions)), fence,
                                                        len(lines), path))


def cut_words(ev, words):
    """Count omitted preview words; complete reports contribute zero. Legacy records
    without the display fields use their historical format's shown count."""
    if not isinstance(words, int) or isinstance(words, bool):
        return 0
    if "report_cut" not in ev:
        return max(0, words - REPORT_CAP_WORDS)
    if ev.get("report_cut") is not True:
        return 0
    shown = ev.get("report_shown")
    if isinstance(shown, int) and not isinstance(shown, bool) and 0 <= shown <= words:
        return words - shown
    return max(0, words - REPORT_CAP_WORDS)


def waste_fields(events, since, transcript=None, now_ts=None, meter_lanes=True):
    """The waste classes over the events after index `since` (the previous boundary, else
    run-open), each with its derivation (register entries of 2026-09-05):
      - idle_min: head idleness — the time in the span (that event's timestamp to now) when
        no lane was running and the head made no call, a head gap counting only above
        IDLE_GAP_S. Lane running time comes from the record (lane-open or lane-resumed to the
        lane's next lane-closed); the head's calls from its transcript (`transcript`, the path
        measure_head found), labelled idle_src `transcript`. When the transcript is missing or
        carries no timestamped call, the record alone measures it as the rule before this one
        did — silence after each lane close until the head's next recorded act, summed per
        close — labelled idle_src `record`, which under parallel lanes overstates.
      - denials: the LANES' tool denials, summed from the wrappers' counts; head_denials,
        beside it and never added to it, is the head fence's own denies in the span
        (head_fence_denials, head_denials_src; register entry 2026-09-06).
      - over_cap_reports: reports with omitted preview words; complete reports contribute zero.
      - respawn_cost_usd: the cost of lanes that closed other than `completed` and were NOT
        resumed afterwards (a lane-resumed for the same lane later in the record): a lane
        resumed from intact staging lost nothing. `respawn_excluded` counts the resumed ones.
        A close carrying no cost (a lane killed with its head) is billed from its transcript
        when `meter_lanes` allows (lane_transcript_bill); one that can be neither makes the
        figure null, `unmeasured`, never $0.00; a plan-usage (Codex) lane is counted, never
        priced; respawn_src names every lane by the part it took (register entry 2026-09-07).
      - limit_cut_resumed_usd: the first attempts' cost of the lanes closed `limit` and resumed
        afterwards — excluded from respawn_cost_usd, since their work was kept, but money spent
        again (register entry 2026-09-10 03:05) — with `limit_cut_resumed` their count and
        limit_cut_src the derivation, null on the same unmeasured rule.
    Rewrites come from the billed line (rewrites_delta). Also returns how many reports could
    not be word-counted."""
    window_events = events[since + 1:]
    now_ts = time.time() if now_ts is None else now_ts
    silence, denials, over, unmeasured, excluded = 0.0, 0, 0, 0, 0
    lost, cut, cut_count = new_bucket(), new_bucket(), 0
    for k, ev in enumerate(window_events):
        if ev.get("event") != "lane-closed":
            continue
        t0 = parse_ts(ev.get("ts"))
        if t0 is not None:
            t1 = None
            for later in window_events[k + 1:]:
                if later.get("event") in WRAPPER_EVENTS:
                    continue
                t = parse_ts(later.get("ts"))
                if t is not None and t >= t0:
                    t1 = t
                    break
            silence += ((t1 if t1 is not None else now_ts) - t0) / 60.0
        d = ev.get("denials")
        if isinstance(d, dict):
            denials += int(d.get("tool") or 0)
        elif isinstance(d, int):
            denials += d
        else:
            denials += len(ev.get("permission_denials") or [])
        words = ev.get("report_words")
        if not isinstance(words, int):
            words = count_words(ev.get("report"))
        if words is None:
            unmeasured += 1
        elif cut_words(ev, words) > 0:
            over += 1
        if ev.get("exit_class") not in (None, "completed"):
            index = since + 1 + k
            if resumed_after(window_events[k + 1:], ev) is not None:
                excluded += 1
                if ev.get("exit_class") == "limit":
                    cut_count += 1
                    price_close(events, index, ev, cut, meter_lanes)
                continue
            price_close(events, index, ev, lost, meter_lanes)
    span_start = parse_ts(events[since].get("ts")) if 0 <= since < len(events) else None
    calls = head_calls(transcript)
    if calls is not None and span_start is not None and now_ts > span_start:
        idle = head_idle_s(calls, lane_intervals(events, span_start, now_ts),
                           span_start, now_ts) / 60.0
        src = "transcript"
    else:
        idle, src = silence, "record"
    head_denials, head_denials_src = head_fence_denials(events, since, now_ts)
    return {"idle_min": round(idle, 1), "idle_src": src, "denials": denials,
            "head_denials": head_denials, "head_denials_src": head_denials_src,
            "over_cap_reports": over, "respawn_cost_usd": bucket_figure(lost),
            "respawn_src": bucket_src(lost), "respawn_excluded": excluded,
            "limit_cut_resumed": cut_count, "limit_cut_resumed_usd": bucket_figure(cut),
            "limit_cut_src": bucket_src(cut)}, unmeasured


def rewrites_delta(events, sid, meter):
    """(rewrites, total, since): the billed line's rewrites figure is cumulative over the head
    session, so the field is its change since the same head's previous boundary that carried
    one — a head's first boundary keeps the figure, the change since the head started. None
    throughout when this line carries no figure; a record naming no head session cannot tell
    one head's boundaries from another's, so its figure is kept and the label says why."""
    total = billed_field(meter, REWRITES_RE, int)
    if total is None:
        return None, None, None
    if not sid:
        return total, total, "head start (no head session in the record)"
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("event") != "phase-boundary" or session_at(events, i) != sid:
            continue
        prev = billed_field(ev.get("meter"), REWRITES_RE, int)
        if prev is not None:
            return total - prev, total, boundary_label(ev)
    return total, total, "head start"


# ------------------------------------------------------------------------------ git --------

def git(vault, args, timeout=COMMIT_TIMEOUT_S):
    try:
        proc = subprocess.run(["git"] + args, cwd=vault, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "timed out after %d s" % timeout
    except OSError as exc:
        return 127, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def ident(text):
    m = re.match(r"^(.*?)\s*<([^>]*)>", text.strip())
    return (m.group(1), m.group(2)) if m else (text.strip(), "")


def tail_of(out, err):
    lines = (err or out or "").strip().splitlines()
    return lines[-1][:160] if lines else ""


def checkpoint_commit(vault, msg):
    """git add -A and git commit as the owner: author must equal committer, no attribution
    line; the short sha on success, `none (nothing to commit)`, or `failed <reason>` — never
    retried, never reset."""
    for bad in ("Co-Authored", "Generated"):
        if bad in msg:
            return "failed the message carries '%s'" % bad
    rc, out, err = git(vault, ["rev-parse", "--is-inside-work-tree"])
    if rc != 0 or out.strip() != "true":
        return "failed %s is not a git work tree (%s)" % (vault, tail_of(out, err))
    rc, author, err = git(vault, ["var", "GIT_AUTHOR_IDENT"])
    rc2, committer, err2 = git(vault, ["var", "GIT_COMMITTER_IDENT"])
    if rc or rc2:
        return "failed identity unresolved (%s)" % tail_of("", err or err2)
    if ident(author) != ident(committer):
        return "failed author ident %s <%s> differs from committer ident %s <%s>" % (
            ident(author) + ident(committer))
    rc, out, err = git(vault, ["add", "-A"])
    if rc:
        return "failed git add (%s)" % tail_of(out, err)
    rc, out, err = git(vault, ["diff", "--cached", "--quiet"])
    if rc == 0:
        return "none (nothing to commit)"
    if rc != 1:
        return "failed git diff --cached (%s)" % tail_of(out, err)
    rc, out, err = git(vault, ["commit", "-q", "-m", msg])
    if rc:
        return "failed git commit exit %d (%s)" % (rc, tail_of(out, err))
    rc, out, err = git(vault, ["log", "-1", "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B"])
    if rc:
        return "failed commit made but unreadable (%s)" % tail_of(out, err)
    sha, an, ae, cn, ce, body = (out.split("\x00", 5) + [""] * 6)[:6]
    if (an, ae) != (cn, ce):
        return "failed author %s <%s> != committer %s <%s> (%s)" % (an, ae, cn, ce, sha[:7])
    for bad in ("Co-Authored", "Generated"):
        if bad in body:
            return "failed the commit body carries '%s' (%s)" % (bad, sha[:7])
    return sha[:7]


def push(vault):
    rc, out, err = git(vault, ["push", "-q"], timeout=COMMIT_TIMEOUT_S)
    if rc == 0:
        return "ok"
    return "failed %s" % (tail_of(out, err) or "exit %d" % rc)


# ---------------------------------------------------------------------- reset times --------

AMPM_RE = re.compile(r"resets?\s*(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I)
ISO_IN_TEXT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?")
# A limit scoped to ONE model, not to the account: the harness names the scope ("You've reached
# your Fable limit") and the remedy ("Switch to another model"), and states no reset time, so
# neither the reset wait nor the haiku probe can clear it - a probe runs on a model that is not
# the exhausted one and answers for the wrong question. Keyed on the wording, never on a model
# name, so the next model fires it too (CLAUDE.md section 12: a guard keys on the property it
# tests). The parser distinguishes a named-model limit from an unparseable reset.
MODEL_LIMIT_RE = re.compile(r"(?i:reached|hit)\s+(?i:your|the)\s+([A-Z][A-Za-z0-9.\-]{0,23})\s+(?i:limit)")
SWITCH_MODEL_RE = re.compile(r"switch\s+to\s+(?:another|a\s+different)\s+model", re.I)
LIMIT_SENTENCE_RE = re.compile(r"[.;!?\n·]+")          # a sentence is the unit the scope word governs
LIMIT_WORD_RE = re.compile(r"\blimits?\b", re.I)         # the standalone word only (never cc_cli_limit_message)
SCOPE_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-']*")
PERIOD_TOKEN_RE = re.compile(r"\d+-?(?:hour|day|week|month|minute)s?", re.I)
BEFORE_LIMIT_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9\-']*)\s+limits?\b", re.I)
NO_SCOPE_WORDS = frozenset(("your", "the", "a", "an", "this", "that", "its", "my", "our", "of",
                            "current", "own"))
ACCOUNT_SCOPES = frozenset((
    "usage", "rate", "account", "weekly", "week", "session", "message", "hour", "hourly",
    "daily", "day", "monthly", "month", "claude", "plan", "credit", "spend", "budget", "token",
    "context", "output", "input", "quota", "request", "api", "overall", "total",
    "subscription", "cap", "cost", "bill", "billing", "window", "wide", "use", "allowance",
    "tier", "throughput", "concurrency", "concurrent", "rolling"))


def account_word(word):
    """True where a scope word names the account, not a model: the word, its singular, its stem
    without -ing or -ly (spending, credits, hourly) against ACCOUNT_SCOPES."""
    w = word.lower().strip("'.")
    if PERIOD_TOKEN_RE.fullmatch(w):
        return True            # a 5-hour or 7-day limit is a window, not a model
    if "-" in w:               # a compound (account-wide, per-user) is tested by its parts
        return any(account_word(part) for part in w.split("-") if part)
    forms = {w, w.rstrip("s")}
    if w.endswith("ing"):
        forms.add(w[:-3])
    if w.endswith("ly"):
        forms.add(w[:-2])
    return bool(forms & ACCOUNT_SCOPES)


def next_clock(hour, minute, now_ts):
    lt = time.localtime(now_ts)
    candidate = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hour, minute, 0, 0, 0, -1))
    if candidate <= now_ts:
        candidate += 86400
    return candidate


def parse_reset_text(text, now_ts):
    """(epoch, source) from a stop text: an ISO time, else `resets (at) h[:mm] [am|pm]`;
    (None, None) when neither is there — the caller falls back, never guesses."""
    m = ISO_IN_TEXT_RE.search(text)
    if m:
        t = parse_ts(m.group(0))
        if t is not None:
            return t, "stop text ISO %s" % m.group(0)
    m = AMPM_RE.search(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        meridian = (m.group(3) or "").lower()
        if meridian == "pm" and hour < 12:
            hour += 12
        if meridian == "am" and hour == 12:
            hour = 0
        if hour <= 23 and minute <= 59:
            return next_clock(hour, minute, now_ts), "stop text '%s'" % m.group(0).strip()
    return None, None


def model_limit(text):
    """The scope of a model-scoped limit as a word ("Fable"), "" where only the remedy is stated,
    or None where the text is not model-scoped and the account-wide handling stands. Either
    marker is decisive on its own: the text names the scope, or it tells the reader to switch
    model. A text whose limit sentence carries an account-wide scope word anywhere (usage,
    weekly, spending, 5-hour, account-wide, rolling window, ...) is never model-scoped, whatever
    else it says; an unknown lower-case scope word right before "limit" is account-wide too; a
    scope word is a model only as a proper noun after "reached" or "hit"; the remedy sentence
    decides only where no limit sentence names a scope; a text naming neither marker falls back
    to the account-wide path."""
    if not text:
        return None
    for sentence in LIMIT_SENTENCE_RE.split(text):
        if not LIMIT_WORD_RE.search(sentence):
            continue
        if any(account_word(w) for w in SCOPE_WORD_RE.findall(sentence)):
            return None        # an account-wide scope word in any sentence that names a limit wins
        for m in BEFORE_LIMIT_RE.finditer(sentence):
            w = m.group(1)
            if w.lower() not in NO_SCOPE_WORDS and not w[:1].isupper():
                return None    # a scope word the vocabulary does not know, in lower case, is never a model
    m = MODEL_LIMIT_RE.search(text)
    if m:
        return m.group(1)      # a proper-noun scope names the model (Fable, Opus, ...)
    if SWITCH_MODEL_RE.search(text):
        return ""
    return None


def model_limit_token(scope):
    """The successor-aborted reason as one status-line word (the anchor hook's [a-z0-9-]
    alphabet, cut at 24): the scope where there is one, else the bare class."""
    word = re.sub(r"[^a-z0-9-]", "", (scope or "").lower())[:11]
    return "limit-model-%s" % word if word else "limit-model"


def parse_reset_at(value, now_ts):
    if re.fullmatch(r"\+\d+s", value):
        return now_ts + int(value[1:-1])
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if m and int(m.group(1)) <= 23 and int(m.group(2)) <= 59:
        return next_clock(int(m.group(1)), int(m.group(2)), now_ts)
    t = parse_ts(value)
    if t is not None:
        return t
    die("--reset-at %r is neither HH:MM, +Ns nor an ISO time" % value)


# ------------------------------------------------------------------ subcommands ------------

def band_value(arg, m):
    """A band edge, `unmetered`, `limit` (a head the account window stopped, D30) or `error`
    (a head the supervisor found stopped in error, C2 N6)."""
    band = arg if arg is not None else (str(m["band"]) if m.get("context") is not None
                                        else "unmetered")
    if band not in ("unmetered", "limit", "error") and not band.isdigit():
        die("--band must be a band edge, 'unmetered', 'limit' or 'error', got %r" % band)
    return int(band) if band.isdigit() else band


def session_spent(line):
    return billed_field(line, r"session \$([0-9.]+)", float)


def spent_sum(events, start):
    """(Σ spent_usd over every head-exit, this session's own head-exit if one follows its start
    index): critic C2 N5, the envelope is never re-granted per head."""
    total, own = 0.0, None
    for i, e in enumerate(events):
        if e.get("event") != "head-exit":
            continue
        if isinstance(e.get("spent_usd"), (int, float)):
            total += float(e["spent_usd"])
        if i > start:
            own = e
    return round(total, 2), own


def envelope_of(events):
    """(envelope_usd, source): the latest `envelope` event's figure (`raise-envelope`, register
    entry 2026-09-10 20:02), else run-open's envelope_usd; (None, reason) when neither is a
    number."""
    for ev in reversed(events):
        value = ev.get("envelope_usd")
        if ev.get("event") == "envelope" and isinstance(value, (int, float)) \
                and not isinstance(value, bool):
            return value, "the envelope event at %s" % ev.get("ts", "no ts")
    value = run_open(events).get("envelope_usd")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value, "run-open"
    return None, "run-open carries no envelope_usd"


def envelope_left(events, run, meter_override, start):
    """(remainder, source): the envelope — its latest figure, `envelope_of` — minus every
    head-exit's spent_usd minus this session's billed total — taken from its own head-exit when
    that carries spent_usd, else metered now. (None, reason) when the envelope is absent or the
    meter gives no session total."""
    envelope, esrc = envelope_of(events)
    if envelope is None:
        return None, esrc
    shown = envelope if esrc == "run-open" else "%s (%s)" % (envelope, esrc)
    spent, own = spent_sum(events, start)
    if own is not None and isinstance(own.get("spent_usd"), (int, float)):
        return round(float(envelope) - spent, 2), (
            "envelope $%s minus $%.2f spent over every head-exit" % (shown, spent))
    total = session_spent(meter_line(events, run, meter_override))
    if total is None:
        return None, "the meter gave no session total"
    return round(float(envelope) - spent - total, 2), (
        "envelope $%s minus $%.2f spent by earlier heads minus session $%.2f"
        % (shown, spent, total))


# ------------------------------------------------------------ the run's spend, by run -------
# Register entries 2026-09-14 19:35 and 2026-09-14 00:06: the per-session billed line's lane half
# depends on a `run-resume` partition a successor head may never write, and a lane closed without a
# cost (a deadline or stall close) is left out of a plain sum of the lane-closed lines, so the
# envelope gate, the boundary and the close can undercount a run. The figure below is the RUN's
# spend and depends on neither.

def money(raw):
    """A recorded cost as a non-negative finite float; None for null, a bool, a non-number or a
    string that is not one — a null cost is unmeasured, never $0.00."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def run_heads(events):
    """(session ids, seeds): every session the record names on a head start — `head-successor`
    and `head-resumed` (session_id), `run-open` and `run-resume` (session) — in first-seen
    order, one entry however many starts name it (a head-successor and the run-resume its
    successor writes share one session BY DESIGN, so no head is counted twice); the seeds among
    them are the sessions `run-open --session-kind seed` marks, which never ran."""
    ids = []
    for ev in events:
        kind = ev.get("event")
        if kind not in START_EVENTS:
            continue
        sid = ev.get("session_id") if kind in ("head-successor", "head-resumed") \
            else ev.get("session")
        if isinstance(sid, str) and TOKEN_RE.fullmatch(sid) and sid not in ids:
            ids.append(sid)
    return ids, seed_sessions(events)


def run_lanes(events):
    """{lane: {sids, plan, closes}} over every lane event of the record (LANE_SPEND_EVENTS), in
    first-seen order: the lane's session ids (every pass of a lane shares one id; a second id
    is what makes a lane unmeterable), whether it runs on plan usage (a Codex lane: `harness:
    codex` or `cost_src: codex-plan` on any of its events) and its closes as (cost or None,
    exit class, and its beats as (cost or None, ok) from `hold-beat`. Nothing here depends on
    which head session opened or resumed the lane."""
    lanes = {}
    for ev in events:
        name = ev.get("lane")
        if not name or ev.get("event") not in LANE_SPEND_EVENTS:
            continue
        lane = lanes.setdefault(str(name), {"sids": [], "plan": False, "closes": [], "beats": [],
                                            "last": None})
        if ev.get("event") == "hold-beat":
            # A beat is one more call inside the pass the lane already closed (the held lanes,
            # D47): its cost counts, but it is no pass of its own — it adds no session to meter
            # and never becomes the lane's `last` event, so it opens no pass and asks for no
            # transcript fallback of its own (critic finding 3 of review).
            lane["beats"].append((money(ev.get("total_cost_usd")), ev.get("ok")))
            if ev.get("harness") == "codex" or ev.get("cost_src") == "codex-plan":
                lane["plan"] = True
            continue
        sid = ev.get("session_id")
        if isinstance(sid, str) and sid and sid not in lane["sids"]:
            lane["sids"].append(sid)
        if ev.get("harness") == "codex" or ev.get("cost_src") == "codex-plan":
            lane["plan"] = True
        if ev.get("event") == "lane-closed":
            lane["closes"].append((money(ev.get("total_cost_usd")), ev.get("exit_class")))
        lane["last"] = ev.get("event")   # a last event other than lane-closed is an open pass
    return lanes


def spend_cache_path(run):
    """The run figure's meter cache beside the record: one metered figure per session, keyed
    on the transcript's path, size and mtime, so a static transcript (an earlier head, a closed
    lane) is metered once and a transcript that grew is metered again."""
    return os.path.join(store_root(), "spawn-records",
                        token(run, "run id") + "-spend-cache.json")


def load_spend_cache(run):
    try:
        with open(spend_cache_path(run), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_spend_cache(run, cache):
    try:
        write_atomic(spend_cache_path(run), json.dumps(cache, indent=1, sort_keys=True) + "\n")
    except OSError as exc:
        note("run spend: the meter cache %s was not written (%s)" % (spend_cache_path(run), exc))


def run_spend(events, run, path=None, session_line=None, use_cache=True, write_cache=True,
              budget_s=RUN_SPEND_BUDGET_S):
    """The run's spend at list prices, by run and never by head session.

    Heads: every session `run_heads` names, each metered ALONE (--lanes none, its whole
    transcript, as the gate's session figure always was) and its `head $` taken; the current
    head's figure is read off `session_line` — the billed line in hand (--meter-line, or the
    boundary's and the close's own meter) — when that carries one; a seed is skipped and says
    so. Lanes: per lane, the sum of its lane-closed costs AND of its `hold-beat` costs (a held
    lane's beats are billable calls: the fold of 2026-09-17); a beat that recorded no cost is a
    gap like an unpriced close, so the lane reads as a floor and is named among the unmeasured,
    and the transcript fallback covers a lane's beats along with its passes, since a beat
    re-enters the session the transcript already holds — the larger of the recorded sum and the
    transcript is taken, so nothing is counted twice and a beat adds no pass. Where any close of a Claude lane
    lacks a cost, the lane has no close yet, or an open pass follows its last close (a
    lane-resumed or a respawn as its latest event: the fold of 2026-09-17), its transcript is
    metered and the LARGER of the recorded sum and the transcript's whole figure taken (the
    recorded costs are per pass; the transcript covers every pass, so the two are never
    summed); a lane whose events name two session ids is metered per transcript, the larger of
    the recorded sum and the transcripts' sum taken, and always listed under the floor (the
    passes across ids cannot be reconciled exactly); a lane with no priced close and no
    meterable transcript is `unmeasured` — never a dollar figure — while a recorded zero prints
    `$0.00` beside the word `recorded`; a Codex lane runs on plan usage — counted, named,
    never priced. A meter figure is cached per session by transcript size and mtime
    (spend_cache_path), and the other meter calls share `budget_s` of wall clock.

    Returns a dict: usd (the total, or the floor), heads_usd, lanes_usd, heads as (sid,
    dollars or None, source) rows and lanes as (name, dollars or None, source, kind) rows —
    kind one of recorded, metered, plan, unmeasured — metered_heads, lanes_n, plan, skipped,
    unmetered, malformed (the record's unparseable lines), measured (any head or lane gave a
    figure: when False nothing is printed as a number, the `unbilled` premise standing), floor
    (something could not be metered or a line was malformed: the figure is `at least`), src
    (the derivation in words) and meter_calls (how many meter runs this call made)."""
    bad = read_record(path)[1] if path and os.path.isfile(path) else 0
    ids, seeds = run_heads(events)
    current = head_session(events)[0]
    cache = load_spend_cache(run) if use_cache else {}
    state = {"changed": False, "calls": 0}
    deadline = time.monotonic() + budget_s

    def meter(sid, transcript):
        """(usd, how) through the cache and the budget; a success is cached."""
        try:
            st = os.stat(transcript)
        except OSError as exc:
            return None, "the transcript %s cannot be read (%s)" % (transcript, exc)
        key = {"path": transcript, "size": st.st_size, "mtime": st.st_mtime}
        hit = cache.get(sid)
        if (isinstance(hit, dict) and all(hit.get(k) == v for k, v in key.items())
                and isinstance(hit.get("usd"), (int, float)) and not isinstance(hit.get("usd"), bool)):
            return float(hit["usd"]), "cached: %s unchanged (%d bytes)" % (transcript, st.st_size)
        left = deadline - time.monotonic()
        if left < 1:
            return None, "the run meter's %d s budget was spent before %s" % (budget_s, transcript)
        state["calls"] += 1
        usd, how = session_bill(sid, transcript, timeout=min(METER_TIMEOUT_S, int(left)))
        if usd is not None:
            cache[sid] = dict(key, usd=usd)
            state["changed"] = True
        return usd, how

    heads, skipped, unmetered = [], [], []
    for sid in ids:
        short = sid[:8]
        if sid in seeds:
            skipped.append("head %s" % short)
            heads.append((sid, None, "skipped: run-open marks the session a seed, which never ran"))
            continue
        if sid == current and session_line:
            usd = head_figure(session_line)
            if usd is not None:
                heads.append((sid, usd, "the session's billed line in hand (head $)"))
                continue
        transcript = transcript_for(sid)
        if not os.path.isfile(transcript):
            how = "no transcript at %s" % transcript
            usd = None
        else:
            usd, how = meter(sid, transcript)
        if usd is None:
            unmetered.append("head %s (%s)" % (short, how))
        heads.append((sid, usd, how))
    lanes_out, lanes_usd, plan, known = [], 0.0, 0, 0
    for name, lane in run_lanes(events).items():
        if lane["plan"]:
            plan += 1
            lanes_out.append((name, None, "plan usage (a Codex lane): counted, never priced "
                                          "(%d close(s))" % len(lane["closes"]), "plan"))
            continue
        recorded = sum(cost for cost, _ in lane["closes"] if cost is not None)
        priced = sum(1 for cost, _ in lane["closes"] if cost is not None)
        # The lane's beats (critic finding 3 of review): a beat that recorded a cost is added to
        # the lane's figure, and a beat that recorded none is a gap, so the figure reads as a
        # floor and the lane is named among the unmeasured rather than silently understated.
        beats_recorded = sum(cost for cost, _ in lane["beats"] if cost is not None)
        beats_priced = sum(1 for cost, _ in lane["beats"] if cost is not None)
        beats_free = sum(1 for cost, _ in lane["beats"] if cost is None)
        recorded += beats_recorded
        missing = [str(cls) for cost, cls in lane["closes"] if cost is None]
        open_pass = bool(lane["closes"]) and lane["last"] != "lane-closed"
        several = len(lane["sids"]) > 1
        # A recorded figure is a figure (a genuine zero included, the word `recorded` beside
        # it); no priced close is no figure at all, never $0.00 (the fold of 2026-09-17).
        fig, kind = (recorded, "recorded") if (priced or beats_priced) else (None, "unmeasured")
        src = "%d close cost(s) as recorded" % priced
        if beats_priced:
            src += " + %d beat cost(s) ($%.2f)" % (beats_priced, beats_recorded)
        if priced or beats_priced:
            known += 1
        gaps = []
        if missing:
            gaps.append("close(s) without a cost: %s" % ", ".join(missing))
        if not lane["closes"]:
            gaps.append("no close yet (still open)")
        if open_pass:
            gaps.append("an open pass after the last close (latest event %s)" % lane["last"])
        if beats_free:
            gaps.append("%d beat(s) without a cost" % beats_free)
        if several:
            gaps.append("%d session ids: the passes across ids cannot be reconciled exactly"
                        % len(lane["sids"]))
        if gaps:
            gap = "; ".join(gaps)
            metered_sum, metered_n, hows = 0.0, 0, []
            for sid in lane["sids"]:
                transcript, why = lane_transcript_path(sid)
                usd, how = (None, why) if transcript is None else meter(sid, transcript)
                if usd is None:
                    hows.append("%s: %s" % (sid[:8], how))
                else:
                    metered_sum += usd
                    metered_n += 1
                    hows.append("%s: $%.2f (%s)" % (sid[:8], usd, how))
            if not lane["sids"]:
                hows.append("the record names no session id for the lane")
            if metered_n:
                known += 1
                fig, kind = max(metered_sum, recorded), "metered"
                src = ("the larger of the %s $%.2f (%s; %s) and the recorded $%.2f (%s)"
                       % ("transcripts'" if metered_n > 1 else "transcript's", metered_sum,
                          gap, "; ".join(hows), recorded, src))
            else:
                src += " · unmetered: %s (%s)" % (gap, "; ".join(hows))
            if metered_n < max(1, len(lane["sids"])) or several or beats_free:
                unmetered.append("lane %s (%s; %s; %s)" % (
                    name, gap, "; ".join(hows),
                    "recorded $%.2f" % recorded if (priced or beats_priced)
                    else "no priced close"))
        lanes_out.append((name, fig, src, kind))
        if fig is not None:
            lanes_usd += fig
    if state["changed"] and use_cache and write_cache:
        save_spend_cache(run, cache)
    heads_usd = sum(usd for _, usd, _ in heads if usd is not None)
    metered_n = sum(1 for _, usd, _ in heads if usd is not None)
    measured = bool(metered_n or known)
    seeds_part = "; %d seed skipped" % len(skipped) if skipped else ""
    plan_part = "; %d on plan usage, never priced" % plan if plan else ""
    if not measured:
        # No figure at all is never printed as a number (the meter's own `unbilled` premise).
        parts = ["nothing metered or recorded (%d head(s)%s; %d lane(s)%s)"
                 % (len(heads), seeds_part, len(lanes_out), plan_part)]
    else:
        figured = sum(1 for _, fig, _, _ in lanes_out if fig is not None)
        unmeasured_n = sum(1 for _, _, _, kind in lanes_out if kind == "unmeasured")
        unmeasured_part = "; %d unmeasured" % unmeasured_n if unmeasured_n else ""
        if not lanes_out:
            lane_part = "lanes: none on the record"
        elif figured:
            lane_part = "lanes $%.2f (%d of %d with a figure%s%s)" % (
                lanes_usd, figured, len(lanes_out), unmeasured_part, plan_part)
        else:
            lane_part = "lanes: none with a figure (%d on the record%s%s)" % (
                len(lanes_out), unmeasured_part, plan_part)
        parts = ["heads $%.2f (%d metered%s)" % (heads_usd, metered_n, seeds_part) if metered_n
                 else "heads: none metered%s" % seeds_part, lane_part]
    if unmetered:
        parts.append("unmetered: %s" % "; ".join(unmetered))
    if bad:
        parts.append("%d malformed record line(s) skipped" % bad)
    return {"usd": round(heads_usd + lanes_usd, 2), "heads_usd": round(heads_usd, 2),
            "lanes_usd": round(lanes_usd, 2), "heads": heads, "lanes": lanes_out,
            "metered_heads": metered_n, "lanes_n": len(lanes_out), "plan": plan,
            "skipped": skipped, "unmetered": unmetered, "malformed": bad,
            "measured": measured, "floor": bool(unmetered or bad),
            "src": " · ".join(parts), "meter_calls": state["calls"]}


def run_spend_short(spend, envelope=None):
    """`$302.00 of $360.00`, `at least $302.00 of $360.00` or `unmeasured`: the run figure as
    the morning report's spend bullet and the boundary and close lines carry it."""
    if not spend["measured"]:
        return "unmeasured"
    text = ("at least " if spend["floor"] else "") + usd(spend["usd"])
    if isinstance(envelope, (int, float)) and not isinstance(envelope, bool):
        text += " of %s" % usd(float(envelope))
    return text


def run_spend_line(spend, envelope=None):
    """The whole run-spend line: the figure, the remainder against the envelope where there is
    one, and the derivation."""
    head = run_spend_short(spend, envelope)
    if spend["measured"] and isinstance(envelope, (int, float)) and not isinstance(envelope, bool):
        left = round(float(envelope) - spend["usd"], 2)
        head += ", remainder %s%s" % ("at most " if spend["floor"] else "", usd(left))
    return "%s · %s" % (head, spend["src"])


def cmd_run_open(a):
    refuse_grants_file(a)
    path = record_path(a.run)
    events = read_record(path)[0] if os.path.isfile(path) else []
    if last_index(events, ("run-open",)) >= 0:
        die("run %s already has a run-open; a later head records run-resume" % a.run)
    token(a.session, "session id")
    handoff = os.path.realpath(os.path.expanduser(a.handoff))
    if not os.path.isfile(handoff):
        die("hand-off document not found: %s" % handoff)
    if a.session_kind == "seed" and a.pid is None:
        # A seed never runs, and a parent walk from here reaches the launcher's own long-lived
        # process, which the first starter would then wait on (register entry 2026-09-12 20:0x).
        pid, src, shown = None, "none", "none (seed: no pid unless --pid)"
    else:
        pid, src = head_pid(a.pid)
        shown = src
    ev = event(a.run, "run-open", session=a.session, head=a.head, regime=a.regime,
               regime_src=a.regime_src, handoff=handoff, detail=a.detail, pid_src=src,
               session_kind=a.session_kind)
    if pid is not None:
        ev["pid"] = pid
    if a.envelope_usd is not None:
        ev["envelope_usd"] = a.envelope_usd
    if a.expect_items:
        ev["expect_items"] = parse_expect_items(a.expect_items)
    ev["grants_file"] = grants_path(a.run)
    ev["on_limit"], ev["on_limit_src"] = on_limit_choice(a, ev["grants_file"])
    ev["viewer"], ev["viewer_src"] = viewer_choice(a, ev["grants_file"])
    ev["network"], ev["network_src"] = network_choice(a, ev["grants_file"])
    payload = grants_payload(a.run, "run-open", a.grant, a.write, ev["on_limit"], ev["viewer"],
                             ev["network"])
    # The lists on the event are the contract the shrink guard reads when the file is gone.
    ev["grants"], ev["writes"] = payload["grants"], payload["writes"]
    trace, seeded = seed_trace(read_text(handoff, "hand-off").split("\n"))
    ev["trace_table"] = trace
    # The findings ledger, the same check once at the open (register entry 2026-09-14 19:35): a
    # seed whose section holds prose and no table is repaired before the first head starts.
    ledger, seeded = seed_ledger(seeded)
    ev["ledger_table"] = ledger
    if a.dry_run:
        say("run-open: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        if trace_warning(trace, True):
            say(trace_warning(trace, True))
        if ledger_warning(ledger, True):
            say(ledger_warning(ledger, True))
        open_console(a.run, viewer=ev["viewer"], dry_run=True)
        return 0
    write_grants(ev["grants_file"], payload)
    write_pointer(a.run, a.session)
    if trace == "seeded" or ledger == "seeded":
        write_atomic(handoff, "\n".join(seeded))
    append_record(path, ev)
    say("run-open: %s · session %s (session_kind %s) · pid %s (%s) · hand-off %s · grants %s · "
        "on_limit %s (%s) · viewer %s (%s) · network %s (%s)"
        % (a.run, a.session[:8], ev["session_kind"], "none" if pid is None else pid, shown,
           handoff, ev["grants_file"], ev["on_limit"], ev["on_limit_src"], ev["viewer"],
           ev["viewer_src"], network_shown(ev["network"]), ev["network_src"]))
    if trace_warning(trace, False):
        say(trace_warning(trace, False))
    if ledger_warning(ledger, False):
        say(ledger_warning(ledger, False))
    # The run's own window, at once and unguarded: a run-open is the run's first act, so no
    # console can be alive for it yet. A viewer failure never fails the launch.
    open_console(a.run, viewer=ev["viewer"])
    return 0


def cmd_run_resume(a):
    refuse_grants_file(a)
    path = record_path(a.run)
    events = require_record(path)
    refused = refuse_two_heads(a, path, events, "run-resume")
    if refused is not None:
        return refused
    sid, how = a.session, "arg"
    if sid == "auto":
        i = last_index(events, ("head-successor",))
        if i < 0:
            die("--session auto needs a head-successor event; pass --session ID")
        sid, how = events[i].get("session_id"), "head-successor"
    token(sid, "session id")
    pid, src = head_pid(a.pid)
    ho = run_open(events).get("handoff")
    stale = None
    if ho and os.path.isfile(ho):
        state, why = pack_state(events, ho)
        if state == "stale":
            stale = why
            say("warn: the hand-off's in-flight pack is stale — %s; re-derive it with `handoff "
                "--inflight-from-record` or write a fresh pack before the next item" % why)
    ev = event(a.run, "run-resume", session=sid, head=a.head, detail=a.detail, pid_src=src)
    if pid is not None:
        ev["pid"] = pid
    ev["grants_file"] = grants_path(a.run)
    # Carry the run's configured write grants into its successor; a default-only rewrite
    # would silently narrow the successor's authorised scope.
    # --on-limit or --viewer alone rewrites that key alone: a list the call does not name is
    # carried from the file, under the shrink guard (register entry 2026-09-11 04:17).
    keep = (not a.grant and not a.write and getattr(a, "on_limit", None) is None
            and getattr(a, "viewer", None) is None
            and os.path.isfile(ev["grants_file"]))
    ev["on_limit"], ev["on_limit_src"] = on_limit_choice(a, ev["grants_file"])
    ev["viewer"], ev["viewer_src"] = viewer_choice(a, ev["grants_file"])
    ev["network"], ev["network_src"] = network_choice(a, ev["grants_file"])
    payload = None
    if keep:
        ev["grants"] = "kept"
    else:
        payload, sources, dropped, against = grants_plan(a, ev["grants_file"], events,
                                                         "run-resume")
        guard_shrink(a, "run-resume", dropped, against)
        # A rewrite records the lists it writes, as run-open and grants do, so the shrink guard's
        # baseline follows an explicit narrowing and never a file narrowed by hand.
        ev["grants"], ev["writes"] = payload["grants"], payload["writes"]
        ev["grants_src"], ev["writes_src"] = sources["grants"], sources["writes"]
    if a.dry_run:
        say("run-resume: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        return 0
    if payload is not None:
        write_grants(ev["grants_file"], payload)
    write_pointer(a.run, sid)
    append_record(path, ev)
    if stale is not None:
        append_record(path, event(a.run, "observation", phase="", what="stale-pack",
                                  note="run-resume: " + stale))
    carried = not keep and not a.grant and not a.write
    say("run-resume: %s · session %s (%s) · pid %s (%s) · grants %s%s · on_limit %s · viewer %s · "
        "network %s"
        % (a.run, sid[:8], how, "none" if pid is None else pid, src, ev["grants_file"],
           " (kept)" if keep else (" (lists carried)" if carried else ""),
           ev["on_limit"], ev["viewer"], network_shown(ev["network"])))
    return 0


LEDGER_HINT = (" — a record with no run-open is a plain lane run: `ledger --observation \"<what>\"`"
               " writes an observation there, with no hand-off row")


def ledger_observation(a, path):
    """`ledger --observation`: ONE observation event on any record that exists, and no hand-off
    row. On a plain record (no `run-open`) it is the only ledger form there is; on a record with
    a `run-open` it is the head's aside that is not a finding, so the findings ledger keeps only
    findings. `--phase` is optional and the phase is empty without it."""
    events = read_existing_record(path)
    shape = "plain lane run (no run-open)" if is_plain_run(events) else "run-open present"
    ev = event(a.run, "observation", phase=a.phase or "", what=a.observation)
    if a.dry_run:
        say("ledger --observation: dry run · %s · %s"
            % (shape, json.dumps(ev, ensure_ascii=False)))
        return 0
    append_record(path, ev)
    say("ledger: observation recorded (%s) · %s · no hand-off row"
        % (one_line(a.observation)[:70], shape))
    return 0


def cmd_ledger(a):
    path = record_path(a.run)
    if a.observation is not None:
        return ledger_observation(a, path)
    missing = [f for f in ("phase", "what", "evidence", "routing") if getattr(a, f) is None]
    if missing:
        die("ledger needs %s, or --observation \"<what>\" for an observation with no ledger row"
            % ", ".join("--" + m for m in missing))
    events = require_record(path, LEDGER_HINT)
    ho = handoff_of(events, a.handoff)
    lines = read_text(ho, "hand-off").split("\n")
    span, lines, seeded = ledger_table(lines, ho, "ledger")
    row = "| %s | %s | %s | %s | %s |" % (hhmm(), cell(a.phase), cell(a.what),
                                         cell(a.evidence), cell(a.routing))
    ev = event(a.run, "observation", phase=a.phase, what=a.what,
               note="evidence: %s · routing: %s" % (one_line(a.evidence), one_line(a.routing)))
    n = span[1] - span[0]
    if a.dry_run:
        say("ledger: dry run · row %d would be %s%s" % (
            n, row, " · the table would be created under the heading first" if seeded else ""))
        return 0
    lines.insert(span[1] + 1, row)
    write_atomic(ho, "\n".join(lines))
    append_record(path, ev)
    if seeded:
        say(LEDGER_SEEDED_LINE % "ledger")
    say("ledger: row %d appended (%s) · observation recorded" % (n, one_line(a.what)[:70]))
    return 0


def decision_count(events):
    """(total, decision events, ledger observations) for close (register entry 2026-09-06): the
    `decision` events plus the observations whose `what` opens with the word decision — the
    ledger form heads used before the `decision` subcommand. The subcommand writes no
    observation, so no decision is counted twice."""
    devents = sum(1 for e in events if e.get("event") == "decision")
    drows = sum(1 for e in events if e.get("event") == "observation"
                and DECISION_WHAT_RE.match(str(e.get("what") or "")))
    return devents + drows, devents, drows


def cmd_decision(a):
    """`decision --run R --phase P --what … --grant …` (register entry 2026-09-06): the `decision`
    event the design's trace schema fixes (phase, what, grant) and one findings-ledger row, in
    one call and before the act; no observation beside them."""
    path = record_path(a.run)
    events = require_record(path, " — a plain lane run has no hand-off for the ledger row; "
                                  "`ledger --observation \"decision: …\"` records it there")
    what, grant = one_line(a.what or ""), one_line(a.grant or "")
    if not what or not grant:
        die("decision needs a non-empty --what and --grant")
    ho = handoff_of(events, a.handoff)
    lines = read_text(ho, "hand-off").split("\n")
    span, lines, seeded = ledger_table(lines, ho, "decision")
    row = "| %s | %s | %s | %s | %s |" % (hhmm(), cell(a.phase), cell("decision: " + what),
                                         cell("grant: " + grant), cell(a.routing))
    ev = event(a.run, "decision", phase=a.phase, what=what, grant=grant)
    n = span[1] - span[0]
    if a.dry_run:
        say("decision: dry run · %s · ledger row %d would be %s%s"
            % (json.dumps(ev, ensure_ascii=False), n, row,
               " · the table would be created under the heading first" if seeded else ""))
        return 0
    lines.insert(span[1] + 1, row)
    write_atomic(ho, "\n".join(lines))
    append_record(path, ev)
    if seeded:
        say(LEDGER_SEEDED_LINE % "decision")
    say("decision: recorded (%s · grant %s) · ledger row %d appended" % (what[:60], grant[:40], n))
    return 0


def decisions_reference(events):
    """(index, label) of the decisions channel's reference point: the later of the record's last
    `gate` event and its last `ack: …` observation, else its last run-open or run-resume, else
    the record's start (-1)."""
    gi = last_index(events, ("gate",))
    ai = next((i for i in range(len(events) - 1, -1, -1)
               if events[i].get("event") == "observation"
               and str(events[i].get("what") or "").startswith(ACK_PREFIX)), -1)
    i = max(gi, ai)
    if i < 0:
        i = last_index(events, ("run-open", "run-resume"))
    if i < 0:
        return -1, "the record's start"
    kind = "ack observation" if i == ai else events[i].get("event")
    return i, "the %s at %s" % (kind, events[i].get("ts", "no ts"))


def decisions_pending(events, dfile):
    """(the AUTHOR observations after the reference, the decisions file's line or None, the
    reference's label). A named file that does not exist is a premise failure: a mistyped path
    would never hold."""
    ref, label = decisions_reference(events)
    authored = [e for e in events[ref + 1:] if e.get("event") == "observation"
                and AUTHOR_RE.match(str(e.get("what") or ""))]
    changed = None
    if dfile is not None:
        fpath = os.path.realpath(os.path.expanduser(dfile))
        if not os.path.isfile(fpath):
            die("--decisions-file %s is not a file: create it (empty is fine) or pass the path the "
                "run's decisions are written to" % dfile)
        mtime = os.path.getmtime(fpath)
        ref_ts = parse_ts(events[ref].get("ts")) if ref >= 0 else None
        if ref_ts is None or mtime > ref_ts:
            changed = ("the decisions file %s changed at %s, after %s: read it"
                       % (fpath, fmt_ts(mtime), label))
    return authored, changed, label


def decisions_hold(a, path, events, what):
    """The decisions channel before a gate or a close (register entry 2026-09-13 03:53): exit 6
    with the pending lines, writing nothing; None to proceed — when nothing is pending, or once
    --ack's observation is recorded."""
    ack = getattr(a, "ack", None)
    if ack is not None and not one_line(ack):
        die("--ack is empty: name what was read, in one line")
    authored, changed, label = decisions_pending(events, getattr(a, "decisions_file", None))
    if ack is not None:
        line = one_line(ack)
        if not a.dry_run:
            append_record(path, event(
                a.run, "observation", phase="", what=ACK_PREFIX + line,
                note="%s: %d AUTHOR observation(s) after %s%s" % (
                    what, len(authored), label, "; " + changed if changed else "")))
        say("%s: ack %s (%s) · %d AUTHOR observation(s)%s pending at the call"
            % (what, "would be recorded" if a.dry_run else "recorded", line[:80], len(authored),
               " and a changed decisions file" if changed else ""))
        return None
    if not authored and not changed:
        return None
    say("%s: HOLD (decisions channel, exit %d) — %d AUTHOR observation(s)%s after %s: read them, "
        "then re-run with --ack \"<one line naming what was read>\""
        % (what, EXIT_HOLD, len(authored), " and a changed decisions file" if changed else "",
           label))
    for e in authored:
        text = "%s · %s" % (e.get("ts", "no ts"), one_line(e.get("what") or ""))
        if e.get("note"):
            text += " · " + one_line(e["note"])
        say("  " + text[:NOTE_CUT])
    if changed:
        say("  " + changed)
    return EXIT_HOLD


def cmd_run_spend(a):
    """`run-spend --run R`: the run's spend by run (run_spend), one line per head and per lane
    and one summary line, stdout only apart from the meter cache (`--no-cache` reads and writes
    none; `--dry-run` reads it and writes none). Exit 0 when every part was metered or read, 1
    when the figure is a floor (`at least`), 2 on a premise failure (no record, no run-open)."""
    path = record_path(a.run)
    events = require_record(path)
    line = a.meter_line
    spend = run_spend(events, a.run, path, session_line=line, use_cache=not a.no_cache,
                      write_cache=not a.dry_run, budget_s=a.budget_s)
    for sid, figure, src in spend["heads"]:
        say("head %s: %s · %s" % (sid, "unmetered" if figure is None else usd(figure), src))
    for name, figure, src, kind in spend["lanes"]:
        shown = ("on plan usage" if kind == "plan" else "unmeasured" if figure is None
                 else usd(figure))
        say("lane %s: %s · %s" % (name, shown, src))
    envelope = envelope_of(events)[0]
    say("run-spend: %s · %s · %d meter call(s)%s" % (
        a.run, run_spend_line(spend, envelope), spend["meter_calls"],
        " · AT LEAST" if spend["floor"] else " · complete" if spend["measured"] else ""))
    return 1 if spend["floor"] or not spend["measured"] else 0


def cmd_run_is_closed(a):
    """`run-is-closed --run R`: exit 0 when the record carries a run-close, 1 when it does not,
    2 with no record — for a wrapper that warns before it spawns into a closed run."""
    events = read_existing_record(record_path(a.run))
    i = last_index(events, ("run-close",))
    if i >= 0:
        say("run-is-closed: %s closed (run-close at %s)" % (a.run, events[i].get("ts", "no ts")))
        return 0
    say("run-is-closed: %s open (no run-close in %d event(s))" % (a.run, len(events)))
    return 1


def refresh_figures(lines, ro, meter, a=None, run_text=None):
    """The morning report's spend and warnings bullets, plus shipped, waits and saving when
    given; `run_text` is the run figure (run_spend_short) the spend bullet carries after the
    session line and the envelope. False when the section is missing."""
    spend = meter + (" · envelope $%s" % ro["envelope_usd"]
                     if ro.get("envelope_usd") is not None else "")
    if run_text:
        spend += " · run %s" % run_text
    if not set_bullet(lines, "spend", spend):
        return False
    set_bullet(lines, "warnings", str(table_rows(lines, "Findings ledger")), number_only=True)
    for key in ("shipped", "waits", "saving"):
        value = getattr(a, key, None)
        if value is not None:
            set_bullet(lines, key, value)
    return True


def cmd_boundary(a):
    path = record_path(a.run)
    events = require_record(path)
    ro = run_open(events)
    ho = handoff_of(events, a.handoff)
    prev = last_index(events, ("phase-boundary",))
    if prev < 0:
        prev = last_index(events, ("run-open",))
    meter = meter_line(events, a.run, a.meter_line)
    sid, _ = head_session(events)
    warning = grants_warning(events, a.run, sid)
    if warning:
        say(warning)
    m = measure_head(sid)
    fields, unmeasured = waste_fields(events, prev, transcript=m.get("transcript"))
    ev = event(a.run, "phase-boundary", **{"from": a.from_, "to": a.to})
    ev.update(disposition=a.disposition, meter=meter, waste=a.waste, context=context_text(m),
              next=a.next)
    ev.update(fields)
    ev["rewrites"], ev["rewrites_total"], ev["rewrites_since"] = rewrites_delta(events, sid, meter)
    # The run's spend beside the session line (register entries 2026-09-14): its own fields on
    # the event, its own line, and the spend bullet; a dry run reads the meter cache and never
    # writes it.
    envelope = envelope_of(events)[0]
    spend = run_spend(events, a.run, path, session_line=meter, write_cache=not a.dry_run)
    ev.update(run_spend_usd=spend["usd"] if spend["measured"] else None,
              run_spend_floor=spend["floor"], run_spend_src=spend["src"])
    lines = read_text(ho, "hand-off").split("\n")
    problems = []
    span = table_span(lines, "Trace")
    if span is None:
        problems.append("no table under a '## Trace' heading")
    else:
        lines.insert(span[1] + 1, "| %s | %s → %s | %s | %s | %s |" % (
            hhmm(), cell(a.from_), cell(a.to), cell(a.disposition), cell(meter), cell(a.waste)))
    if not refresh_figures(lines, ro, meter, a, run_spend_short(spend, envelope)):
        problems.append("no '## Morning report' section")
    if a.dry_run:
        say("boundary: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        if not a.meter_line:
            say("boundary: dry run · meter invoked as %s" % meter_command_text(events, a.run))
        if problems:
            say("hand-off: would NOT refresh — %s" % "; ".join(problems))
        return 0
    write_atomic(ho, "\n".join(lines))
    if a.commit is not None:
        ev["commit"] = checkpoint_commit(vault_root(), a.commit)
    append_record(path, ev)
    respawn = fields["respawn_cost_usd"]
    cut_usd = fields["limit_cut_resumed_usd"]
    say("boundary: %s → %s · idle %s min · denials %d · over-cap %d · %s · "
        "rewrites %s · context %s%s%s · idle src %s · rewrites since %s%s%s · head fence denials %s"
        % (a.from_, a.to, fields["idle_min"], fields["denials"], fields["over_cap_reports"],
           "re-spawn unmeasured" if respawn is None else "re-spawn $%.2f" % respawn,
           "n/a" if ev["rewrites"] is None else ev["rewrites"],
           ev["context"], " · commit %s" % ev["commit"] if "commit" in ev else "",
           " · %d report(s) not word-counted" % unmeasured if unmeasured else "",
           fields["idle_src"], ev["rewrites_since"] or "n/a",
           " · %d resumed lane(s) excluded from re-spawn" % fields["respawn_excluded"]
           if fields["respawn_excluded"] else "",
           " · limit-cut resumed %s (%d lane(s): first attempts, excluded from re-spawn)"
           % ("unmeasured" if cut_usd is None else "$%.2f" % cut_usd, fields["limit_cut_resumed"])
           if fields["limit_cut_resumed"] else "",
           "unmeasured" if fields["head_denials"] is None else fields["head_denials"]))
    # bucket_src joins its parts with " · ": a source of one part is recorded costs alone, and
    # anything more (a transcript bill, a plan-usage lane, an unmeasured lane) is printed.
    if " · " in fields["respawn_src"]:
        say("re-spawn: %s" % fields["respawn_src"])
    if fields["limit_cut_resumed"] and " · " in fields["limit_cut_src"]:
        say("limit-cut resumed: %s" % fields["limit_cut_src"])
    say("meter: %s" % meter)
    say("run spend: %s" % run_spend_line(spend, envelope))
    if problems:
        say("hand-off: NOT refreshed — %s" % "; ".join(problems))
        return 3
    return 0


def first_usage(path):
    """The stock of the transcript's FIRST qualifying assistant usage record, read from the
    file start under the watermark's own rule (not sidechain, role assistant, model not
    synthetic, stock above zero); None when there is none or the file is unreadable."""
    module, _ = watermark()
    keys = getattr(module, "USAGE_KEYS", None) or (
        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    to_int = getattr(module, "_int", None) or (lambda v: int(v) if isinstance(v, int) else 0)
    if not path:
        return None
    try:
        handle = open(path, "rb")
    except OSError:
        return None
    with handle:
        for line in handle:
            if b'"usage"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict) or str(msg.get("model", "")).startswith("<synthetic"):
                continue
            stock = sum(to_int(usage.get(k)) for k in keys)
            if stock > 0:
                return stock
    return None


def same_session_resume(events, scope):
    """True when the session event this gate's scope opens at is a run-resume that names the
    session the previous session-naming head event named AND that session already recorded a
    gate before the resume. The resumed process kept its context, so its transcript's first call
    after the resume carries the whole session rather than the head's orientation read;
    null that gate regardless of its size (register entry of 2026-09-05).
    The earlier gate is what makes the test sound: a head-successor and the run-resume its
    successor writes share a session id BY DESIGN, so the shared id alone would null every
    successor's first gate, which is a real orientation figure. A session that has already
    gated once has been measured once; a fresh one has not."""
    i = scope - 1
    if i < 0 or events[i].get("event") != "run-resume":
        return False
    sid = events[i].get("session")
    if not sid:
        return False
    start, prior = -1, None
    for j in range(i - 1, -1, -1):
        if events[j].get("event") in SESSION_EVENTS:
            start = j
            prior = (events[j].get("session_id")
                     if events[j].get("event") == "head-successor" else events[j].get("session"))
            break
    if prior != sid:
        return False
    return any(e.get("event") == "gate" for e in events[start + 1:i])


def orientation(events, scope, m):
    """(tokens, note) for a session's first gate (D41): the context now minus the transcript's
    first-call context; None with the reason when either is absent, and always None after a
    head-resumed event or a same-session run-resume, whose first call carries the whole
    session."""
    if any(e.get("event") == "head-resumed" for e in events[scope:]):
        return None, "unmeasured after a resume"
    if same_session_resume(events, scope):
        return None, "unmeasured after a same-session resume"
    if m.get("context") is None:
        return None, "unmetered gate: %s" % m.get("reason", "unknown")
    first = first_usage(m.get("transcript"))
    if first is None:
        return None, "no qualifying first usage record in %s" % m.get("transcript")
    return m["context"] - first, None


def usd(value):
    """A signed dollar figure with the sign before the symbol: `$80.38`, `-$9.62`."""
    return ("-$%.2f" % -value) if value < 0 else ("$%.2f" % value)


def envelope_status(events, run, meter_override, path=None, write_cache=True):
    """(the gate line's envelope text, the remainder or None, the source, the run figure):
    `envelope: none` when run-open carries no envelope_usd (the run figure still follows);
    `envelope: unmeasured (<reason>)` when no head and no lane could be metered or read (the
    `unbilled` premise: never a zero); else `envelope: $<spent> of $<envelope>, remainder $<r>
    · run: <derivation>`, spent being the RUN's spend (run_spend: every head session metered
    alone plus every lane on the record, whichever head spawned or resumed it), and, where a
    part could not be metered, `envelope: at least $<spent> of $<envelope>, remainder at most
    $<r>`, the floor the gate then compares with the envelope. `meter_override` is the billed
    line in hand for the current head (--meter-line)."""
    envelope, esrc = envelope_of(events)
    spend = run_spend(events, run, path, session_line=meter_override, write_cache=write_cache)
    if envelope is None:
        return "envelope: none · run: %s" % run_spend_line(spend), None, esrc, spend
    if not spend["measured"]:
        return "envelope: unmeasured (%s)" % spend["src"], None, spend["src"], spend
    left = round(float(envelope) - spend["usd"], 2)
    if spend["floor"]:
        text = "envelope: at least %s of %s, remainder at most %s" % (
            usd(spend["usd"]), usd(float(envelope)), usd(left))
    else:
        text = "envelope: %s of %s, remainder %s" % (usd(spend["usd"]), usd(float(envelope)),
                                                     usd(left))
    return "%s · run: %s" % (text, spend["src"]), left, "the run's spend: %s" % spend["src"], spend


def envelope_stop(path, a, env_text, env_why, figure):
    """The envelope stop: the stop-condition event (which envelope, lane head, the figures in
    its note) and the gate's exit 5. The run ends here; a successor refuses on the same figure."""
    figures = env_text[len("envelope: "):]
    append_record(path, event(
        a.run, "stop-condition", which="envelope", lane="head",
        action="gate refused item %s: the envelope is spent" % a.to,
        note="%s (%s)" % (figures, env_why)))
    say("gate: %s · %s · %s · REFUSED (stop-condition envelope: the remainder is at or below "
        "zero) → the run stops here; the owner tops the envelope up before any successor: "
        "handsoff.py raise-envelope --run %s --to USD --reason \"…\""
        % (a.to, figure, env_text, a.run))
    return EXIT_ENVELOPE


def cmd_raise_envelope(a):
    """`raise-envelope --run R --to USD --reason …` (register entry 2026-09-10 20:02): the owner's
    top-up, one `envelope` event that `envelope_of` — and so the gate, the successor and the
    supervisor — reads as the run's envelope. Premise failures write nothing: no run-open, a
    closed run, an empty reason, a figure that is not a finite positive number or not above the
    current envelope, and a figure at or below the run's spend."""
    path = record_path(a.run)
    events = require_record(path, " — a plain lane run has no envelope to raise")
    ci = last_index(events, ("run-close",))
    if ci >= 0:
        die("run %s is closed (run-close at %s): a closed run's envelope is not raised"
            % (a.run, events[ci].get("ts", "no ts")))
    reason = one_line(a.reason or "")
    if not reason:
        die("--reason is empty: a top-up carries the owner's reason on the record")
    if not math.isfinite(a.to) or a.to <= 0:
        die("--to %r is not a finite positive figure" % a.to)
    current, csrc = envelope_of(events)
    if current is not None and a.to <= float(current):
        die("--to $%.2f is not above the current envelope $%.2f (%s): raise-envelope only raises"
            % (a.to, float(current), csrc))
    start = last_index(events, SESSION_EVENTS)
    recorded, own = spent_sum(events, start)
    if own is not None and isinstance(own.get("spent_usd"), (int, float)):
        spent, ssrc = recorded, "every head-exit's spent_usd (this session has exited)"
    else:
        total = session_spent(meter_line(events, a.run, a.meter_line))
        if total is None:
            spent, ssrc = recorded, ("every head-exit's spent_usd; this session unmeasured (the "
                                     "meter gave no session total)")
        else:
            spent = round(recorded + total, 2)
            ssrc = "every head-exit's spent_usd plus this session's $%.2f" % total
    if a.to <= spent:
        die("--to $%.2f is at or below the run's spend $%.2f (%s): the gate refuses a remainder at "
            "or below zero, so the run would stay stopped" % (a.to, spent, ssrc))
    ev = event(a.run, "envelope", envelope_usd=round(float(a.to), 2), previous_usd=current,
               previous_src=csrc, spent_usd=spent, spent_src=ssrc, reason=reason)
    if a.dry_run:
        say("raise-envelope: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        return 0
    append_record(path, ev)
    say("raise-envelope: %s · envelope %s → $%.2f · spend $%.2f (%s) · remainder $%.2f"
        % (a.run, "none" if current is None else "$%.2f" % float(current), a.to, spent, ssrc,
           a.to - spent))
    return 0


def parse_expect_items(text):
    """`item0=40k,item1=90000` → {"item0": 40000, "item1": 90000}; a bad token dies by name."""
    out = {}
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            die("--expect-items: %r is not ITEM=TOKENS" % part)
        item, value = part.split("=", 1)
        v = value.strip().lower()
        try:
            n = int(v[:-1]) * 1000 if v.endswith("k") else int(v)
        except ValueError:
            die("--expect-items: %r is not a token count" % value)
        if n <= 0:
            die("--expect-items: %r must be positive" % value)
        name = item.strip()
        if not name:
            die("--expect-items: %r has no item name" % part)
        if name in out:
            die("--expect-items: %r is declared twice" % name)
        out[name] = n
    if not out:
        die("--expect-items: nothing declared")
    return out


def declared_items(events):
    """The declared cost per item: the last `expect-items` event, else run-open's field, else {}."""
    for e in reversed(events):
        if e.get("event") == "expect-items" and isinstance(e.get("items"), dict):
            return e["items"]
    for e in events:
        if e.get("event") == "run-open":
            return e.get("expect_items") or {}
    return {}


def item_deltas(events):
    """The head's memory growth per completed item, as (item, tokens): consecutive metered gates
    of one head session, positive deltas only; a new session (successor, resume by hand) starts a
    fresh series, so a hand-over's drop never counts."""
    out, base, base_item, base_allowed = [], None, None, False
    for g in events:
        if g.get("event") in SESSION_EVENTS:
            base, base_item, base_allowed = None, None, False
            continue
        if g.get("event") != "gate" or not g.get("metered") or not isinstance(g.get("context"), int):
            continue
        if base is not None and g.get("item") == base_item:
            base_allowed = base_allowed or g.get("decision") == "allow"   # a retry never moves the baseline
            continue
        if base is not None and base_allowed and g["context"] > base:
            out.append((base_item, g["context"] - base))
        base, base_item, base_allowed = g["context"], g.get("item"), g.get("decision") == "allow"
    return out


def fit_estimate(events, item, now=None):
    """(tokens, source) for the next item's memory cost: the declared cost corrected by the run's
    measured ratio; else the largest measured item × FIT_MARGIN; else the prior share of the
    window. `now`, the memory at this call, adds the item in flight (its growth since the last
    recorded gate) to the measured deltas, since that gate's own delta is not on the record yet.
    Never None: the gate always has an estimate once it has a memory figure."""
    w = window()
    declared = declared_items(events)
    deltas = item_deltas(events)
    if isinstance(now, int) and item is not None:
        base, base_item, base_allowed = None, None, False
        for g in events:
            if g.get("event") in SESSION_EVENTS:
                base, base_item, base_allowed = None, None, False
            elif g.get("event") == "gate" and g.get("metered") and isinstance(g.get("context"), int):
                if base is not None and g.get("item") == base_item:
                    base_allowed = base_allowed or g.get("decision") == "allow"
                else:
                    base, base_item, base_allowed = g["context"], g.get("item"), g.get("decision") == "allow"
        if base is not None and base_allowed and now > base and item != base_item:
            deltas = deltas + [(base_item, now - base)]   # the item just completed; never the one in flight
    if declared:
        pairs = [(d, declared[i]) for i, d in deltas if i in declared and declared[i] > 0]
        ratio = (float(sum(a for a, _ in pairs)) / sum(b for _, b in pairs)) if pairs else 1.0
        if item is not None and item in declared:
            return int(declared[item] * ratio), "declared×%.2f" % ratio
        by_declared = int(max(declared.values()) * ratio)
        if deltas and int(max(d for _, d in deltas) * FIT_MARGIN) > by_declared:
            return int(max(d for _, d in deltas) * FIT_MARGIN), "largest-measured×%.2f" % FIT_MARGIN
        return by_declared, "declared-max×%.2f" % ratio
    if deltas:
        return int(max(d for _, d in deltas) * FIT_MARGIN), "largest-measured×%.2f" % FIT_MARGIN
    return int(w * PRIOR_ITEM_SHARE), "prior"


def belt_of(e):
    """The belt: the third edge where the bands give three, else 90 %."""
    return e[2] if len(e) >= 3 else 90


def fits(context, cost, w, belt):
    return context + cost + int(w * PACK_ALLOWANCE_SHARE) <= (belt * w) // 100


def resume_guard(events, m, start):
    """The hand-run resume's guard: (verdict, why, stop_class, stopped_at). `ok` only for a sound
    stop (never a refusal or an error) whose resume fits and is cheap; else `resume-refused` or
    `resume-unfit` with the reason the successor path is the answer."""
    stop = next((e for e in reversed(events[start:]) if e.get("event") == "observation"
                 and e.get("what") == "head exited"), None)
    stop_cls = str((stop or {}).get("exit_class") or "limit")
    stopped_at = parse_ts((stop or {}).get("ts")) if stop else None
    if stop_cls in ("refusal", "error"):
        return ("resume-refused", "the head's last stop was a %s: never resumed by hand (a refusal "
                "re-flags; an error's state is not trusted); start the successor from the hand-off"
                % stop_cls, stop_cls, stopped_at)
    if not resume_in_place(events, m, stopped_at):
        return ("resume-unfit", "the rest of the item does not fit under the belt, or the resume is "
                "not cheap (cache cold, memory over a fresh start's orientation): start the "
                "successor from the hand-off", stop_cls, stopped_at)
    return ("ok", "", stop_cls, stopped_at)


def resume_in_place(events, m, stopped_at):
    """After a sound stop (limit, budget, a hand repair): resume the head in place only when the
    rest of its item fits under the belt (a whole item, conservatively) AND the resume is cheap:
    the cache is still warm, or the memory is under a fresh head's orientation cost. No memory
    figure: never; no estimate is impossible once a figure exists. The old 60 % rule stays as the
    fallback for an empty record shape (no gate ever metered and nothing declared: the prior
    then decides, which at 1M lands near the old mark)."""
    if m.get("context") is None:
        return False
    w, e = window(), edges()
    cost, _ = fit_estimate(events, None, m["context"])
    warm = stopped_at is not None and (time.time() - stopped_at) <= CACHE_LIFE_S
    small = m["context"] <= int(w * ORIENTATION_SHARE)
    return fits(m["context"], cost, w, belt_of(e)) and (warm or small)


def report_hardstops_text(events):
    """The warnings bullet beside the limit stops: every head stop-condition whose `which` is not
    a limit, and every lane closed other than completed or limit, each count stated (owner ruling
    2026-09-14: a hard stop is reported clearly, never searched-and-empty)."""
    heads = ["%s at %s (%s)" % (ev.get("which"), ev.get("ts", "no ts"),
                                one_line(str(ev.get("action") or ""))[:80])
             for ev in events if ev.get("event") == "stop-condition"
             and not str(ev.get("which") or "").startswith("limit")]
    heads += ["head exit %s at %s" % (ev.get("exit_class"), ev.get("ts", "no ts"))
              for ev in events if ev.get("event") == "observation" and ev.get("what") == "head exited"
              and ev.get("exit_class") not in (None, "completed", "handed-over", "closed", "limit",
                                               "unsucceeded")]
    lanes = ["%s at %s (%s)" % (ev.get("lane") or "unnamed lane", ev.get("ts", "no ts"),
                                ev.get("exit_class"))
             for ev in events if ev.get("event") == "lane-closed"
             and ev.get("exit_class") not in ("completed", "limit")]
    lanes += ["%s at %s (completed with denials %s)" % (
                  ev.get("lane") or "unnamed lane", ev.get("ts", "no ts"),
                  ",".join("%s %s" % (k, v) for k, v in sorted(ev["denials"].items())
                           if k in DENIAL_KEYS and v))
              for ev in events if ev.get("event") == "lane-closed"
              and ev.get("exit_class") == "completed" and isinstance(ev.get("denials"), dict)
              and any(ev["denials"].get(k) for k in DENIAL_KEYS)]
    return ("%d hard stop(s) on the head other than a limit%s · %d lane(s) closed other than "
            "completed or limit%s · read from the record at the close" % (
                len(heads), ": " + "; ".join(heads) if heads else "",
                len(lanes), ": " + "; ".join(lanes) if lanes else ""))


def cmd_expect(a):
    """Declare the expected memory cost per item on the record (an `expect-items` event)."""
    path = record_path(a.run)
    require_record(path)
    items = parse_expect_items(a.items)
    ev = event(a.run, "expect-items", items=items, src="expect")
    if a.dry_run:
        say("expect: dry run · %s" % json.dumps(items))
        return 0
    append_record(path, ev)
    say("expect: %d item cost(s) recorded: %s" % (len(items), ", ".join(
        "%s=%s" % (k, format(v, ",")) for k, v in items.items())))
    return 0


def cmd_gate(a):
    path = record_path(a.run)
    events = require_record(path)
    # Two heads first (register entry 2026-09-03): a peer's gate reaches neither the hold nor the
    # meter. Then the decisions channel (register entry 2026-09-13 03:53).
    refused = refuse_two_heads(a, path, events, "gate")
    if refused is not None:
        return refused
    held = decisions_hold(a, path, events, "gate")
    if held is not None:
        return held
    sid, sev = head_session(events)
    scope = last_index(events, SESSION_EVENTS) + 1
    prior = [e for e in events[scope:] if e.get("event") == "gate"]
    m = measure_head(sid)
    is_armed, how = armed(sid)
    warning = grants_warning(events, a.run, sid)
    if warning:
        say(warning)
    w, e = window(), edges()
    threshold = e[1]
    belt = belt_of(e)
    cost_next, cost_src = fit_estimate(events, a.to, m.get("context"))
    orient = orientation(events, scope, m) if not prior else None
    # The envelope (register entry 2026-09-07): measured at every gate against the RUN's spend
    # (register entries 2026-09-14, run_spend); a remainder at or below zero is the stop, armed
    # or not, and a floor already over the envelope refuses too.
    env_text, env_left, env_why, spend = envelope_status(events, a.run, a.meter_line, path,
                                                         write_cache=not a.dry_run)
    spent_out = env_left is not None and env_left <= 0
    spend_fields = {"run_spend_usd": spend["usd"] if spend["measured"] else None,
                    "run_spend_floor": spend["floor"], "run_spend_src": spend["src"]}
    # A gate whose run-spend figure could not be computed is an unmetered gate for the
    # two-unmetered-gates rule, exactly as a gate without a context measurement is: the first miss is allowed
    # with the warning and its event says so (run_spend_usd null, run_spend_src the failure), the
    # second consecutive miss refuses with exit 7 when armed, and a measured gate resets the count.
    spend_miss = not spend["measured"]
    second = bool(prior) and gate_missed(prior[-1])
    if m.get("context") is None:
        decision = "refuse" if ((second and is_armed) or spent_out) else "allow"
        ev = event(a.run, "gate", item=a.to, context=None, percent=None, band="unmetered",
                   armed=is_armed, decision=decision, metered=False, **spend_fields)
        if orient is not None:
            ev["orientation_tokens"], ev["orientation_note"] = orient
        obs = event(a.run, "observation", phase=a.phase, what="gate unmetered",
                    note="item %s: %s%s" % (a.to, m["reason"],
                                            "; second consecutive" if second else ""))
        if a.dry_run:
            say("gate: dry run · unmetered (%s) · %s · %s" % (m["reason"], decision, env_text))
            return 0
        append_record(path, ev)
        append_record(path, obs)
        if spent_out:
            return envelope_stop(path, a, env_text, env_why, "unmetered (%s)" % m["reason"])
        if decision == "refuse":
            append_record(path, event(
                a.run, "stop-condition", which="unmetered", lane="head",
                action="gate refused item %s: second consecutive unmetered gate (armed by %s)"
                       % (a.to, how), note=m["reason"]))
            say("gate: unmetered (%s) · second consecutive · armed (%s) · REFUSED item %s → "
                "handoff --final --band unmetered, then successor · %s"
                % (m["reason"], how, a.to, env_text))
            return 7
        say("gate: unmetered (%s) · %s · item %s allowed%s · %s" % (
            m["reason"], "second consecutive" if second else "first miss", a.to,
            " · soft: fix the metering" if second else "", env_text))
        return 0
    fit = fits(m["context"], cost_next, w, belt)
    over = not fit
    band_refusal = over and is_armed
    spend_refusal = spend_miss and second and is_armed
    decision = "refuse" if (band_refusal or spent_out or spend_refusal) else "allow"
    ev = event(a.run, "gate", item=a.to, context=m["context"], percent=m["percent"],
               band=m["band"], armed=is_armed, decision=decision, metered=True,
               fit=fit, cost_next=cost_next, cost_src=cost_src, belt=belt, **spend_fields)
    figure = "context %s (%d %%) · band %d · armed %s" % (
        format(m["context"], ","), m["percent"], m["band"], how if is_armed else "no")
    figure += " · fit %s (next %s, %s; belt %d %%)" % (
        "yes" if fit else "no", format(cost_next, ","), cost_src, belt)
    if orient is not None:
        ev["orientation_tokens"] = orient[0]
        if orient[1]:
            ev["orientation_note"] = orient[1]
        else:
            figure += " · orientation %s" % format(orient[0], ",")
    miss = ("unmetered spend (%s)" % ("second consecutive" if second else "first miss")
            if spend_miss else "")
    if a.dry_run:
        say("gate: dry run · %s · %s · %s · %s%s" % (a.to, figure, decision, env_text,
                                                    " · " + miss if miss else ""))
        return 0
    append_record(path, ev)
    if spend_miss:
        append_record(path, event(
            a.run, "observation", phase=a.phase, what="gate unmetered",
            note="item %s: the run's spend could not be metered: %s%s"
                 % (a.to, spend["src"], "; second consecutive" if second else "")))
    if spent_out:
        return envelope_stop(path, a, env_text, env_why, figure)
    if band_refusal:
        append_record(path, event(
            a.run, "stop-condition", which="band", lane="head",
            action="gate refused item %s at %d %% (fit: next %s, %s, over the belt %d %%; armed by %s)"
                   % (a.to, m["percent"], format(cost_next, ","), cost_src, belt, how),
            note="handoff --final --band %d, watch in-flight lanes, then successor" % threshold))
        say("gate: %s · %s · REFUSED (stop-condition band) → handoff --final --band %d, watch "
            "in-flight lanes, then successor · %s" % (a.to, figure, threshold, env_text))
        return 4
    if spend_refusal:
        append_record(path, event(
            a.run, "stop-condition", which="unmetered", lane="head",
            action="gate refused item %s: second consecutive unmetered gate (the run's spend "
                   "unmetered; armed by %s)" % (a.to, how), note=spend["src"]))
        say("gate: %s · %s · %s · armed (%s) · REFUSED item %s → handoff --final --band "
            "unmetered, then successor · %s" % (a.to, figure, miss, how, a.to, env_text))
        return 7
    warn = (" · warn: at or above the second edge (%d %%), soft — finish what is in flight, "
            "start nothing new" % threshold) if over else ""
    if spend_miss:
        warn += " · %s · item %s allowed%s" % (miss, a.to,
                                                " · soft: fix the metering" if second else "")
    say("gate: %s · %s · allow%s · %s" % (a.to, figure, warn, env_text))
    return 0


def gate_missed(ev):
    """True when a gate event is a miss for the two-unmetered-gates rule: no context measurement
    (`metered` false), or a run-spend figure the gate could not compute (`run_spend_usd` present
    and null). A gate written before the run figure existed carries no such key and is no miss
    on that count; a floor (a partly unmetered figure) is a figure, not a miss."""
    return ev.get("metered") is False or ("run_spend_usd" in ev and ev.get("run_spend_usd") is None)


def pack_missing(text):
    """The next-task pack's labels (D41) absent from the text: each must start a line, after
    an optional `- ` or `* ` bullet."""
    found = set(PACK_LINE_RE.findall(text or ""))
    return [label for label in PACK_LABELS if label[:-1] not in found]


def stamp_pack(text):
    """The in-flight pack under one `- pack written: <ISO>` first line: an earlier stamp, or a
    re-derivation header, is dropped first, so the section's age is the age of this write."""
    body = [line for line in str(text).rstrip("\n").split("\n") if not PACK_STAMP_RE.match(line)]
    while body and not body[0].strip():
        body.pop(0)
    return "\n".join([PACK_STAMP + now()] + body)


def pack_stamp(lines):
    """(epoch, the stamp as written) of the `## In flight` section's age stamp; (None, reason)
    when the section, the stamp or a parsable timestamp is missing."""
    text = section_text(lines, SECTIONS["inflight"])
    if text is None:
        return None, "the hand-off carries no '## In flight' section"
    m = PACK_STAMP_RE.search(text)
    if not m:
        return None, "the in-flight pack carries no `%s<timestamp>` stamp" % PACK_STAMP.strip()
    epoch = parse_ts(m.group(1))
    if epoch is None:
        return None, "the pack stamp %r is not a timestamp this script parses" % m.group(1)
    return epoch, m.group(1)


def boundary_index(events):
    """The index of the pack-age guard's anchor — the last phase-boundary or head-exit, a
    `pack: true` head-exit skipped (see boundary_stamp) — or -1. Both the age comparison and the
    re-derivation read it, so `since the boundary` means the same span in each."""
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("event") not in BOUNDARY_EVENTS:
            continue
        if ev.get("event") == "head-exit" and ev.get("pack") is True:
            continue
        return i
    return -1


def boundary_stamp(events):
    """(epoch, event) of the record's last phase-boundary or head-exit — the pack-age guard's
    anchor — else (None, None). A head-exit carrying `pack: true` is skipped: `handoff --final`
    writes the pack and that head-exit in one call, so the pack cannot be older than it, and
    the literal rule would call every good hand-over pack stale on the second boundary."""
    i = boundary_index(events)
    if i < 0:
        return None, None
    return parse_ts(events[i].get("ts")), events[i]


def head_activity(events, i):
    """(epoch, label) of the head's last activity before index i — a head-exit `successor` or the
    supervisor wrote (`pack: false`) — else (None, reason); register entry 2026-09-12 21:2x. Taken:
    the head's own events since its start (HEAD_ACTS and a `pack: true` head-exit), the
    supervisor's `head exited` observation, and the head transcript's mtime. No other observation
    is taken: its author is not on the event, and a launcher relays some."""
    start = last_index(events[:i], START_EVENTS)
    if start < 0:
        return None, "no head start before the head-exit"
    best, label = None, None
    for e in events[start:i]:
        kind = e.get("event")
        if not (kind in HEAD_ACTS or (kind == "head-exit" and e.get("pack") is True)
                or (kind == "observation" and e.get("what") == "head exited")):
            continue
        t = parse_ts(e.get("ts"))
        if t is not None and (best is None or t >= best):
            best = t
            label = "%s at %s" % ("the `head exited` observation" if kind == "observation"
                                  else kind, e.get("ts"))
    sev = events[start]
    sid = sev.get("session_id") if sev.get("event") in ("head-successor", "head-resumed") \
        else sev.get("session")
    if isinstance(sid, str) and TOKEN_RE.fullmatch(sid):
        try:
            mtime = os.path.getmtime(transcript_for(sid))
        except OSError:
            mtime = None
        if mtime is not None and (best is None or mtime > best):
            best, label = mtime, "the head transcript's mtime %s" % fmt_ts(mtime)
    if best is None:
        return None, "the head's span carries no timestamped activity and no transcript"
    return best, label


def pack_state(events, ho):
    """(state, note) for the hand-off's in-flight pack against that anchor: `no-boundary` (the
    head has closed nothing yet, so the pack is fresh by definition), `fresh`, `stale` (older
    than the boundary: the head moved on and the pack did not), `unstamped` (a hand-off written
    before this guard, or by hand: left alone, since re-deriving over it would overwrite the
    head's judgement) or `unmeasured`. A `pack: false` head-exit is written by `successor` or the
    supervisor at the moment of their call, never by the head, so for that anchor the pack is
    judged against the head's last activity (head_activity): fresh when its stamp is at or after
    it, or when the hand-off's mtime is REWRITE_SLACK_S or more past it (register entry 2026-09-12
    21:2x). A `pack-fresh` observation after the anchor — `--pack-fresh`, the launcher's word —
    makes the pack fresh. The note names both timestamps."""
    btime, bev = boundary_stamp(events)
    if bev is None:
        return "no-boundary", ("the record carries no phase-boundary or head-exit event: the "
                               "pack is fresh by definition")
    i = boundary_index(events)
    label = "%s at %s" % (bev.get("event"), bev.get("ts", "no ts"))
    word = next((e for e in events[i + 1:] if e.get("event") == "observation"
                 and e.get("what") == PACK_FRESH_WHAT), None)
    if word is not None:
        return "fresh", ("--pack-fresh recorded at %s, after the %s: the launcher's word that the "
                         "hand-off is current" % (word.get("ts", "no ts"), label))
    ptime, detail = pack_stamp(read_text(ho, "hand-off").split("\n"))
    if ptime is None:
        return "unstamped", "%s; the anchor is the %s" % (detail, label)
    if bev.get("event") == "head-exit" and bev.get("pack") is False:
        htime, hlabel = head_activity(events, i)
        if htime is not None:
            try:
                mtime = os.path.getmtime(ho)
            except OSError:
                mtime = None
            if ptime >= htime:
                return "fresh", ("the pack was written %s, at or after the head's last activity "
                                 "(%s)" % (detail, hlabel))
            if mtime is not None and mtime >= htime + REWRITE_SLACK_S:
                return "fresh", ("the hand-off was rewritten at %s, after the head's last "
                                 "activity (%s), though its pack stamp reads %s"
                                 % (fmt_ts(mtime), hlabel, detail))
            return "stale", ("the pack was written %s and the hand-off last rewritten %s, both "
                             "before the head's last activity (%s)"
                             % (detail, "at an unknown time" if mtime is None else fmt_ts(mtime),
                                hlabel))
    if btime is None:
        return "unmeasured", ("the %s carries no parsable timestamp, so the pack stamped %s "
                              "cannot be compared with it" % (bev.get("event"), detail))
    if ptime < btime:
        return "stale", "the pack was written %s, before the %s" % (detail, label)
    return "fresh", "the pack was written %s, at or after the %s" % (detail, label)


def spawn_line(ev):
    """A lane-open event as one line: the spawn fields the wrapper writes that are there."""
    parts = []
    for key in ("class", "model", "reason", "brief"):
        if ev.get(key):
            parts.append("%s %s" % (key, one_line(ev[key])))
    return " · ".join(parts) or "the lane-open event carries no class, model, reason or brief"


def derive_inflight(events):
    """`## In flight` derived from the run record: the last boundary's `next`, the lanes still
    open since that boundary with their spawn lines, and the decisions since it, one line each,
    under the header the guard writes. The D41 labels are kept, so a derived pack passes the
    same label check a head's own pack must pass; an empty class says so rather than going
    silent, since a missing line and nothing to report are different claims."""
    i = boundary_index(events)
    since = events[i + 1:] if i >= 0 else list(events)
    lines = [PACK_DERIVED % now()]
    j = last_index(events, ("phase-boundary",))
    if j >= 0 and events[j].get("next"):
        lines.append("- Next: %s (a copy of the `next` field of the phase-boundary at %s: the "
                     "run's shape as it stood at that boundary, which any later instruction "
                     "supersedes)" % (one_line(events[j]["next"]), events[j].get("ts", "no ts")))
    elif j >= 0:
        lines.append("- Next: unstated — the phase-boundary at %s carries no `next` field"
                     % events[j].get("ts", "no ts"))
    else:
        lines.append("- Next: unstated — the record carries no phase-boundary event")
    open_lanes = []
    for ev in since:
        if not ev.get("lane"):
            continue
        if ev.get("event") == "lane-open":
            open_lanes.append(ev)
        elif ev.get("event") == "lane-closed":
            open_lanes = [e for e in open_lanes if e.get("lane") != ev.get("lane")]
    for ev in open_lanes:
        lines.append("- Needs: lane %s open since %s · %s"
                     % (ev.get("lane"), ev.get("ts", "no ts"), spawn_line(ev)))
    if not open_lanes:
        lines.append("- Needs: no lane is open in the record since the boundary")
    decisions = [ev for ev in since if ev.get("event") == "decision"]
    for ev in decisions:
        lines.append("- Decided: %s (%s, at %s)"
                     % (one_line(ev.get("what") or "unstated"),
                        one_line(ev.get("grant") or "grant unstated"), ev.get("ts", "no ts")))
    if not decisions:
        lines.append("- Decided: no decision event since the boundary")
    return "\n".join(lines)


def guard_pack(a, path, ho):
    """The pack-age guard before a successor starts: a stale `## In flight` is rewritten from
    the record, so the successor is briefed by the record rather than by a pack the head wrote
    before its last boundary. Returns the state; the observation says which."""
    events, _ = read_record(path)
    state, why = pack_state(events, ho)
    if state != "stale":
        say("pack: %s — %s" % (state, why))
        return state
    lines = read_text(ho, "hand-off").split("\n")
    if not set_section(lines, "inflight", derive_inflight(events)):
        append_record(path, event(a.run, "observation", phase="", what="stale-pack",
                                  note="not re-derived (no '## In flight' section): " + why))
        say("pack: STALE — %s · the hand-off carries no '## In flight' section, so nothing was "
            "re-derived" % why)
        return "stale-unwritten"
    write_atomic(ho, "\n".join(lines))
    append_record(path, event(a.run, "observation", phase="", what="stale-pack",
                              note="'## In flight' re-derived from the record: " + why))
    say("pack: STALE — %s · '## In flight' re-derived from the record before the successor "
        "starts" % why)
    return "stale"


def record_pack_fresh(path, run, who):
    """`--pack-fresh` (register entry 2026-09-12 21:2x): an observation `what: pack-fresh` after
    every anchor the record holds — the launcher's word that the hand-off is current, which
    pack_state reads as fresh until a later anchor (the new head has acted since)."""
    append_record(path, event(run, "observation", phase="", what=PACK_FRESH_WHAT,
                              note="%s --pack-fresh: the launcher's word that the hand-off's "
                                   "'## In flight' is current at %s" % (who, now())))


def apply_set(lines, key, value):
    if key in BULLETS:
        if not set_bullet(lines, key, value):
            die("no '## Morning report' section")
    elif key in SECTIONS:
        if not set_section(lines, key, value):
            die("no '## %s' section" % SECTIONS[key])
    elif key in APPEND_ONLY:
        die("the ledger and the trace are append-only: use `ledger` and `boundary`")
    else:
        die("unknown key %r; bullets: %s; sections: %s"
            % (key, ", ".join(sorted(BULLETS)), ", ".join(sorted(SECTIONS))))
    return key


def cmd_handoff(a):
    path = record_path(a.run)
    events = require_record(path)
    ho = handoff_of(events, a.handoff)
    lines = read_text(ho, "hand-off").split("\n")
    changes = []
    if a.inflight_file is not None:
        a.inflight = read_text(a.inflight_file, "--inflight-file")
    derived = False
    if a.inflight_from_record:
        if a.inflight is not None:
            die("--inflight-from-record and --inflight/--inflight-file are two sources for one "
                "section: pass one")
        a.inflight, derived = derive_inflight(events), True
        say("handoff: '## In flight' derived from the record · %d lines"
            % len(a.inflight.split("\n")))
        if a.dry_run:
            for line in a.inflight.split("\n"):
                say(line)
    if a.final and a.inflight is None:
        die("--final needs the next-task pack: --inflight-file PATH (or --inflight TEXT) "
            "carrying Next:, Needs: and Decided: (D41)")
    if a.inflight is not None:
        missing = pack_missing(a.inflight)
        if missing and a.final:
            die("the next-task pack lacks %s (each label at the start of a line; an optional "
                "'- ' bullet is allowed)" % ", ".join(missing))
        if missing:
            say("handoff: warn: the in-flight pack lacks %s (a --final pack would be refused)"
                % ", ".join(missing))
        changes.append(apply_set(lines, "inflight",
                                 a.inflight if derived else stamp_pack(a.inflight)))
    for spec in a.set or []:
        key, sep, value = spec.partition("=")
        if not sep:
            die("--set needs key=value, got %r" % spec)
        changes.append(apply_set(lines, key.strip(), value))
    for spec in a.set_file or []:
        key, sep, fpath = spec.partition("=")
        if not sep:
            die("--set-file needs key=path, got %r" % spec)
        changes.append(apply_set(lines, key.strip(), read_text(fpath, "--set-file " + key)))
    exit_ev, have_exit = None, None
    if a.final:
        xi = stop_exit(events)
        if xi >= 0:
            # This stop's head-exit is already recorded, by the supervisor or an earlier repair,
            # and no head has started since (register entry 2026-09-14 05:13; review finding
            # 2): a second one would count the stop twice.
            have_exit = events[xi]
        else:
            sid, _ = head_session(events)
            m = measure_head(sid)
            pid, psrc = final_pid(events, a.pid)
            say("handoff: pid %s (%s)" % ("none" if pid is None else pid, psrc))
            exit_ev = event(a.run, "head-exit", band=band_value(a.band, m),
                            context=context_text(m), handoff=ho, pack=True,
                            spent_usd=session_spent(meter_line(events, a.run, a.meter_line)))
            if pid is not None:
                exit_ev["pid"] = pid
    if not changes and exit_ev is None:
        say("handoff: nothing to do (no --inflight, --set, --set-file or --final)")
        return 0
    if a.dry_run:
        say("handoff: dry run · would rewrite %s%s%s" % (
            ", ".join(changes) or "nothing",
            " · head-exit %s" % json.dumps(exit_ev, ensure_ascii=False) if exit_ev else "",
            exit_recorded_text(have_exit)))
        return 0
    if changes:
        write_atomic(ho, "\n".join(lines))
    if exit_ev is not None:
        with record_lock(path):   # the same stop's exit may have landed while this call measured
            fresh, _ = read_record(path)
            xi = stop_exit(fresh)
            if xi >= 0:
                exit_ev, have_exit = None, fresh[xi]
            else:
                append_record(path, exit_ev)
    say("handoff: %s rewritten%s%s" % (
        ", ".join(changes) if changes else "nothing",
        " · head-exit recorded (band %s, %s)" % (exit_ev["band"], exit_ev["context"])
        if exit_ev else "", exit_recorded_text(have_exit)))
    return 0


def resume_prompt(ho):
    text = section_text(read_text(ho, "hand-off").split("\n"), "Resume prompt")
    if not text:
        die("the hand-off's '## Resume prompt' section is missing or empty: %s" % ho)
    return text


def next_out(run):
    n = 1
    while True:
        out = os.path.join(store_root(), "spawn-records", "%s-head-%d.out" % (run, n))
        if not os.path.exists(out):
            return out, n
        n += 1


def head_command(binary, sid, budget, model, effort=None, resume=False):
    """The head's command line: a fresh session (--session-id) or, with resume, the same
    session continued (--resume, D30); model and effort as given."""
    cmd = [binary, "-p", "--resume" if resume else "--session-id", sid, "--output-format",
           "json", "--permission-mode", "bypassPermissions", "--max-budget-usd", "%.2f" % budget]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]   # the head runs at max (owner rule 2026-09-04); absent, the harness default applies
    return cmd


def cmd_successor(a):
    path = record_path(a.run)
    events = require_record(path)
    hi = last_index(events, HEAD_EVENTS)
    if hi >= 0 and events[hi].get("event") == "head-successor":
        oi = exited_last(events)
        if oi >= 0:
            die(missing_exit_refusal(events, hi, oi, path, a.run))
        die("a head-successor (session %s) already follows the last head-exit in %s: nothing "
            "started, since its own run-resume is the next head event"
            % (events[hi].get("session_id"), path))
    ro = run_open(events)
    ho = handoff_of(events, a.handoff)
    prompt = resume_prompt(ho)
    xi = last_index(events, ("head-exit",))
    envelope, _ = envelope_of(events)
    if a.budget_usd is not None:
        budget, bsrc = float(a.budget_usd), "--budget-usd"
    elif xi >= 0 and seed_exit(events[xi]) and isinstance(envelope, (int, float)) \
            and not isinstance(envelope, bool):
        # A seed head-exit records a session that never ran: it left no transcript, so the
        # meter has nothing to read and the remainder is the envelope minus the spend the
        # record already holds — never a premise failure (register entry 2026-09-07).
        spent, _ = spent_sum(events, last_index(events, SESSION_EVENTS))
        budget = round(float(envelope) - spent, 2)
        bsrc = ("envelope (seed): the last head-exit is a seed exit, so envelope $%s minus "
                "$%.2f spent over every head-exit, unmetered" % (envelope, spent))
    else:
        budget, bsrc = envelope_left(events, a.run, a.meter_line,
                                     last_index(events, SESSION_EVENTS))
        if budget is None:
            die("%s; pass --budget-usd" % bsrc)
        if budget <= 0:
            if not a.dry_run:
                append_record(path, event(a.run, "successor-aborted", reason="budget",
                                          note="the envelope is spent (%s leaves $%.2f): the "
                                               "owner tops up" % (bsrc, budget)))
            die("the envelope is spent (%s leaves $%.2f): the owner raises it with `handsoff.py "
                "raise-envelope --run %s --to USD --reason …`, or pass --budget-usd to extend it"
                % (bsrc, budget, a.run))
    # A head-resumed after the last head-exit starts a new head whose exit is not recorded yet
    # (review finding 2): that head's own call writes its head-exit.
    ri = last_index(events, START_EVENTS + ("head-exit",))
    have_exit = ri >= 0 and events[ri].get("event") == "head-exit"
    sid, sev = head_session(events)
    m = measure_head(sid)
    # The same rule `handoff --final` carries, through the same helper: on a SEEDED record with
    # no --pid the seed's own run-open pid is taken and the parent walk is not run. The walk
    # must not substitute the attended caller for the launcher's explicitly recorded pid.
    # References (register entries 2026-09-07
    # and 2026-09-08).
    own_pid, own_src = final_pid(events, a.pid)
    if have_exit:
        exit_ev = events[hi]
    else:
        exit_ev = event(a.run, "head-exit", band=band_value(a.band, m),
                        context=context_text(m), handoff=ho,
                        spent_usd=session_spent(meter_line(events, a.run, a.meter_line)))
        if own_pid is not None:
            exit_ev["pid"] = own_pid
        say("successor: pid %s (%s)" % ("none" if own_pid is None else own_pid, own_src))
    if a.predecessor_pid is not None:
        pred, psrc = int(a.predecessor_pid), "--predecessor-pid"
    elif exit_ev.get("pid") is not None:
        pred, psrc = int(exit_ev["pid"]), "head-exit"
    elif seed_predecessor(events):
        pred, psrc = None, "none: the predecessor is a seed session with no pid, so no wait"
    elif sev is not None and sev.get("pid") is not None:
        pred, psrc = int(sev["pid"]), sev["event"]
    else:
        pred, psrc = None, "none: %d s of transcript silence is the proxy" % SILENCE_PROXY_S
    # A launcher-supplied pid that is this caller's own long-lived ancestor would hold the starter
    # on the caller itself (register entries 2026-09-10 10:51 and 2026-09-12 20:0x). A pid the
    # walk found is the exiting head's own, which the starter must outlive, so it is not tested.
    seed = seed_run_open(events)
    refuse_own_ancestor([(a.pid, "--pid"), (a.predecessor_pid, "--predecessor-pid"),
                         (pred if seed is not None and pred is not None
                          and pred == seed.get("pid") else None, "the seed run-open's pid")])
    if not have_exit:
        exit_ev["pack"] = False
    if a.reset_at:
        parse_reset_at(a.reset_at, time.time())   # refuse a malformed value now, not at 3 am
    out, _ = next_out(a.run)
    transcript = transcript_for(sid) if sid else ""
    plan = ("starter: wait ≤%d s for pid %s (%s); abort if a head-successor already follows "
            "the head-exit, if the previous head-exit was unmetered too, or on timeout; then "
            "from %s start the successor with the resume prompt (%d chars) on stdin, env "
            "AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=%s%s, budget $%.2f (budget_src: %s), output %s, and "
            "supervise it (D30)" % (
                a.wait_s, "none" if pred is None else pred, psrc, vault_root(), len(prompt),
                a.run, " CLAUDE_CONFIG_DIR=%s" % a.config_dir if a.config_dir else "", budget,
                bsrc, out))
    cmd = head_command(a.harness_bin, "<fresh uuid4>", budget, a.model, a.effort)
    if a.dry_run:
        say("successor: dry run · %s" % plan)
        say("command: %s < resume prompt" % " ".join(cmd))
        if a.pack_fresh:
            say("successor: dry run · would record observation pack-fresh (the launcher's word "
                "that the hand-off is current)")
        open_console_if_dark(a.run, dry_run=True)
        return 0
    if not have_exit:
        with record_lock(path):   # the supervisor or a repair may have written it meanwhile
            fresh, _ = read_record(path)
            ri = last_index(fresh, START_EVENTS + ("head-exit",))
            if ri >= 0 and fresh[ri].get("event") == "head-exit":
                have_exit = True
            else:
                append_record(path, exit_ev)
    if a.pack_fresh:
        record_pack_fresh(path, a.run, "successor")
    starter = [sys.executable, "-B", os.path.abspath(__file__), "_starter", "--run", a.run,
               "--handoff", ho, "--budget", "%.2f" % budget, "--out", out, "--wait-s",
               str(a.wait_s), "--harness-bin", a.harness_bin, "--transcript", transcript,
               "--max-wait-s", str(a.max_wait_s), "--probe-interval-s",
               str(a.probe_interval_s), "--tick-s", str(a.tick_s)]
    if a.model:
        starter += ["--model", a.model]
    if a.effort:
        starter += ["--effort", a.effort]
    if a.config_dir:
        starter += ["--config-dir", a.config_dir]
    if pred is not None:
        starter += ["--predecessor-pid", str(pred)]
    if a.reset_at:
        starter += ["--reset-at", a.reset_at]
    if a.probe:
        starter += ["--probe"]   # forwarded only when this caller opted in (2026-09-06)
    if a.meter_line:
        starter += ["--meter-line", a.meter_line]
    log = out + ".starter.log"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # Open the successor window before detaching and record its result in the starter log.
    # Tell the starter the viewer is open so its first start opens nothing.
    # See register entry 2026-09-09 11:21. One window per
    # run, so the owner's `q` gets a fresh one and a console still running is never doubled. A
    # viewer failure never fails the launch.
    open_console_if_dark(a.run, log=log)
    starter += ["--viewer-opened"]
    with open(log, "ab") as handle:
        proc = subprocess.Popen(starter, stdin=subprocess.DEVNULL, stdout=handle, stderr=handle,
                                start_new_session=True, cwd=vault_root(),
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    say("successor: %s · starter pid %d detached (log %s) · %s" % (
        "head-exit already recorded" if have_exit
        else "head-exit recorded (band %s)" % exit_ev["band"], proc.pid, log, plan))
    return 0


def wait_dead(pid, limit):
    """True once the pid is gone; a limit of 0 or less waits without bound (a supervisor)."""
    end = time.time() + limit if limit > 0 else None
    while end is None or time.time() < end:
        if not pid_alive(pid):
            return True
        time.sleep(1)
    return not pid_alive(pid)


def wait_silent(transcript, quiet, limit):
    if not transcript or not os.path.isfile(transcript):
        return True
    end = time.time() + limit
    while time.time() < end:
        try:
            age = time.time() - os.path.getmtime(transcript)
        except OSError:
            return True
        if age >= quiet:
            return True
        time.sleep(5)
    return False


def start_guards(events, hi, gone=True, why=""):
    """The starter's loop guards over the record's last head-exit (index hi): (reason, detail)
    for a successor-aborted event, or (None, None) when the start may go ahead."""
    if hi < 0:
        return "no-head-exit", "the record carries no head-exit to succeed"
    if any(e.get("event") == "head-successor" for e in events[hi + 1:]):
        return "duplicate", "a head-successor already follows the head-exit"
    if not gone:
        return "timeout", why
    earlier = [e for e in events[:hi] if e.get("event") == "head-exit"]
    succ = [e for e in events if e.get("event") == "head-successor"]
    cap = int(os.environ.get("AIMYTH_MAX_SUCCESSORS", "6"))   # backstop, set by judgement:
    # a 20-hour run at ~3 h per head; the repeat-exit check below is the real guard

    def item_before(idx):
        """The item the head was on when it exited: the last gate before the exit, unless
        a head event sits between (then the head exited before any gate)."""
        for e in reversed(events[:idx]):
            if e.get("event") == "gate":
                return e.get("item")
            if e.get("event") in START_EVENTS:
                return None
        return None
    if events[hi].get("band") == "unmetered" and earlier and \
            earlier[-1].get("band") == "unmetered":
        return "unmetered-loop", ("the previous head-exit was unmetered too: an unmetered "
                                  "fault buys at most one restart")
    if len(succ) >= cap:
        return "successor-cap", ("%d successors already started for this run "
                                 "(AIMYTH_MAX_SUCCESSORS=%d)" % (len(succ), cap))
    if earlier and item_before(hi) is not None and \
            item_before(hi) == item_before(events.index(earlier[-1])) and \
            str(events[hi].get("band")) in ("80", "90") and \
            str(earlier[-1].get("band")) in ("80", "90"):
        return "repeat-exit", ("the last two head-exits followed a gate on the same item "
                               "(%s): the item does not fit the window; the hand-off is the "
                               "recovery" % item_before(hi))
    return None, None


def abort(path, run, reason, detail):
    """The supervisor's last act: `successor-aborted` and exit 1.

    Every open hold ends first, with the same `stood-down` reason a stand-down writes (critic
    finding 1 of review, 2026-09-17): an abort ends the supervision, so a hold left open would
    sit on the board as `held · beat due` with nobody ticking. A hold can never block an abort, so
    the ending is guarded.
    """
    try:
        ended = end_open_holds(path, run, read_record(path)[0], "supervisor", reason="stood-down",
                               note="the supervisor aborted (%s): no tick would service the hold"
                                    % reason)
    except (Exception, SystemExit) as exc:
        ended = 0
        say("supervisor: the open holds could not be ended at the abort (%s: %s); they stay open "
            "on the record" % (type(exc).__name__, exc))
    append_record(path, event(run, "successor-aborted", reason=reason, note=detail,
                              holds_ended=ended))
    say("supervisor: aborted — %s: %s (the hand-off is the recovery)%s"
        % (reason, detail, " (%d hold(s) ended)" % ended if ended else ""))
    return 1


def head_env(run, config_dir):
    """Every head the starter starts is armed and knows its run (D34: the head fence reads
    AIMYTH_HANDSOFF_RUN before the state directory's pointer)."""
    env = dict(os.environ, AIMYTH_HANDSOFF="1", AIMYTH_HANDSOFF_RUN=run)
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = config_dir
    return env


def feed(proc, text):
    try:
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
    except (BrokenPipeError, OSError) as exc:
        say("supervisor: the head closed stdin early: %s" % exc)


def out_size(out):
    if not out or out == "none" or not os.path.exists(out):
        return 0
    return os.path.getsize(out)


def head_model_fields(a):
    """The model and effort a head start runs under, as its command line carries them
    (head_command), for the head-successor and head-resumed events (register entry 2026-09-10
    20:29: watch.py's header reads them from the record alone). A start with no --model runs
    the harness's default model: the field is null and model_src says so."""
    model = getattr(a, "model", None) or None
    return {"model": model, "effort": getattr(a, "effort", None) or None,
            "model_src": "arg" if model else "harness default (no --model)"}


def start_head(a, path, budget, out, t0, watch=None):
    """A fresh head from the hand-off's resume prompt (the start path the starter has always
    used), then the head-successor and supervise events: (proc, sid, out, offset, start index)
    or None after successor-aborted, reason start-failed."""
    ho = handoff_of(read_record(path)[0], a.handoff)
    guard_pack(a, path, ho)          # a pack older than the last boundary is re-derived first
    prompt = resume_prompt(ho)
    sid = str(uuid.uuid4())
    cmd = head_command(a.harness_bin, sid, budget, a.model, a.effort)
    offset = out_size(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if watch is not None and watch.check():   # the last act before the start (D43; C2 H1: after
        return "stood-down"                     # the meter and the pack guard, nothing follows)
    with open(out, "ab") as handle:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=handle, stderr=handle,
                                    cwd=vault_root(), env=head_env(a.run, a.config_dir),
                                    start_new_session=True)
        except OSError as exc:
            abort(path, a.run, "start-failed", "cannot start %s: %s" % (a.harness_bin, exc))
            return None
    feed(proc, prompt)
    append_record(path, event(a.run, "head-successor", session_id=sid, pid=proc.pid,
                              config_dir=a.config_dir, budget=budget,
                              started_after_s=round(time.time() - t0), out=out,
                              **head_model_fields(a)))
    events, _ = read_record(path)
    start = last_index(events, ("head-successor",))
    append_record(path, event(a.run, "supervise", mode="launched", pid=proc.pid, session_id=sid,
                              out=out, supervisor_pid=os.getpid(), services_holds=True))
    say("supervisor: head-successor pid %d session %s after %d s → %s"
        % (proc.pid, sid, time.time() - t0, out))
    if getattr(a, "viewer_opened", False):
        a.viewer_opened = False    # the caller opened it before the detach; later starts open when dark
        say("viewer: the caller ran the opener before the detach (its lines are above in this log)")
    else:
        open_console_if_dark(a.run)   # the supervisor's own successor start after a head exit
    return proc, sid, out, offset, start


def out_result(out, offset):
    """(result, tail, note) from the .out written after `offset`: the LAST JSON object line is
    the harness's result; every other line is the tail text (a limit printed to stderr with no
    result), cut to its last 4,000 characters. A missing, empty or JSON-less file gives an
    empty result and a note naming the premise, never a guess."""
    if not out or out == "none":
        return {}, "", "no .out file: transcript-only classification"
    try:
        with open(out, "rb") as handle:
            handle.seek(offset)
            data = handle.read()
    except OSError as exc:
        return {}, "", "cannot read %s: %s" % (out, exc)
    text = data.decode("utf-8", "replace")
    if not text.strip():
        return {}, "", ("%s is empty" % out if offset == 0
                        else "nothing appended to %s since this head started" % out)
    lines = text.splitlines()
    result, where = {}, -1
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped.startswith("{"):
            continue
        try:
            rec = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(rec, dict):
            result, where = rec, i
            break
    tail = "\n".join(line for i, line in enumerate(lines) if i != where)[-4000:]
    if not result:
        return {}, tail, "no JSON result line in %s" % out
    return result, tail, "result subtype %s" % result.get("subtype", "?")


def stop_class(events, start, out, offset, rc, transcript):
    """The head's stop, classified (D30): `closed` and `handed-over` from the record after this
    head's start event, the rest from the lane wrapper's own classifier over the .out result,
    the exit code and the transcript. (class, detail) with detail's `text` the stop text."""
    after = events[start + 1:]
    if any(e.get("event") == "run-close" for e in after):
        return "closed", {"note": "a run-close follows this head's start", "text": ""}
    hi = last_index(after, ("head-exit",))
    if hi >= 0:
        if any(e.get("event") == "head-successor" for e in after[hi + 1:]):
            return "handed-over", {"note": "a head-exit follows this head's start and a "
                                           "head-successor follows it: its own successor call "
                                           "owns the next head", "text": ""}
        return "unsucceeded", {"note": "a head-exit follows this head's start with no "
                                       "head-successor after it", "text": ""}
    result, tail, note = out_result(out, offset)
    lane, _, err = lane_module()
    if lane is None:
        return "classifier-missing", {"note": err, "text": ""}
    parsed = lane.parse_transcript(transcript)
    subtype = str(result.get("subtype") or "")
    cls, signal = lane.classify(False, False, parsed, result, subtype, 0 if rc is None else rc,
                                not result, tail)
    text = one_line(result.get("result") or "")
    if not text and tail.strip():
        text = one_line(tail.strip().splitlines()[-1])
    if cls in ("refusal", "max-turns"):
        note, cls = "%s (%s)" % (note, cls), "error"
    if signal:
        note = "%s · %s" % (note, signal)
    return cls, {"note": note, "text": text, "subtype": subtype}


def head_context(sid, events, start):
    """The head's context for the resume decision: its transcript through measure_head, else
    the last gate event of its session (the fallback D30 names), else unmetered."""
    m = measure_head(sid)
    if m.get("context") is not None:
        m["source"] = "transcript"
        return m
    session_start = last_index(events[:start + 1], SESSION_EVENTS)
    for e in reversed(events[session_start + 1:]):
        if e.get("event") == "gate" and isinstance(e.get("context"), int):
            w, ed = window(), edges()
            return {"context": e["context"], "percent": e["context"] * 100 // w,
                    "band": band_edge(e["context"], w, ed), "source": "last gate event",
                    "transcript": m.get("transcript")}
    m["source"] = "none"
    return m


def remainder(events, a, cls, start):
    """(budget, source) for the next head: the envelope minus every head-exit's spent_usd
    minus this session's total (G9, C2 N5); when the session total cannot be metered, the cap
    this supervisor holds (--budget), never above what the envelope has left — except after a
    budget stop, whose unknown remainder is never re-spent. (None, reason) means
    successor-aborted, reason budget: the owner tops up."""
    left, why = envelope_left(events, a.run, a.meter_line, start)
    if left is not None:
        if left <= 0:
            return None, "the envelope is spent: %s leaves $%.2f" % (why, left)
        return left, why
    known = a.budget
    if cls == "budget" or known is None:
        return None, "%s: the remainder is unknown%s" % (
            why, " and a budget stop never re-spends its cap" if known is not None else "")
    cap = float(known)
    envelope, _ = envelope_of(events)
    if envelope is not None:
        cap = min(cap, round(float(envelope) - spent_sum(events, start)[0], 2))
    if cap <= 0:
        return None, "%s: the cap in hand is spent against the envelope" % why
    return cap, "%s: the cap in hand $%.2f reused" % (why, cap)


def supervisor_stop_file(run):
    """The supervisor's stop marker (D43): `supervise --stop` and `close` write it; a sleeping
    supervisor stands down at its next tick, and a supervisor whose head exits with the marker
    on disk stands down before any successor decision (register entry 2026-09-07).

    It is cleared at exactly three sites, and a bare arming is not one of them: `resume-head`,
    a `successor` CALLED BY A HEAD (the detached `_starter`, which only cmd_successor spawns),
    and the run's own `close`, which writes it as the last thing it does."""
    return os.path.join(store_root(), "spawn-records", token(run, "run id") + "-supervisor.stop")


def clear_stop_marker(run):
    """A marker left by an earlier --stop or close is not this arming's (the heartbeat's rule).
    Called from the three sites supervisor_stop_file names, and nowhere else."""
    marker = supervisor_stop_file(run)
    if os.path.exists(marker):
        try:
            os.remove(marker)
            say("supervisor: a stale stop marker removed (%s)" % marker)
        except OSError as exc:
            note("stale stop marker not removed: %s" % exc)


def run_on_limit(events, run):
    """(value, source, grants file): the run's limit gate (D42) from the grants path — the one
    file the head fence and the status hook read too (C2 H2; the --grants-file override that
    once sat outside the gate is retired, register entry 2026-09-06). A missing file or key is
    the default `stop`, and the source says which."""
    path = grants_path(run)
    value, src = on_limit_of(read_grants(path))
    return value, src, path


class StandDown(object):
    """The limit wait's stand-down watch (D43): the head transcript's byte size and mtime,
    baselined AFTER the stop is classified (so the harness's own stop record sits inside the
    baseline), plus the stop marker. check() records the reason and detail and returns True."""

    def __init__(self, run, transcript, on_limit, src):
        self.run, self.on_limit, self.src = run, on_limit, src
        self.path = transcript if transcript and os.path.isfile(transcript) else None
        self.size, self.mtime = self._stat()
        self.marker = supervisor_stop_file(run)
        self.reason = self.detail = None

    def _stat(self):
        if not self.path:
            return None, None
        try:
            st = os.stat(self.path)
            return st.st_size, st.st_mtime
        except OSError:
            return None, None

    def label(self):
        if self.path and self.size is not None:
            return "transcript %s (%d bytes)" % (self.path, self.size)
        return "unwatched (no transcript file)"

    def check(self):
        if os.path.exists(self.marker):
            self.reason, self.detail = "stopped", "the stop marker %s appeared" % self.marker
            return True
        if self.path:
            size, mtime = self._stat()
            if (size, mtime) != (self.size, self.mtime):
                self.reason = "resumed-by-hand"
                self.detail = ("the head transcript changed during the wait (someone continued "
                               "the session): %s → %s bytes, mtime %s → %s; %s"
                               % (self.size, "gone" if size is None else size,
                                  fmt_ts(self.mtime) if self.mtime else "?",
                                  fmt_ts(mtime) if mtime else "gone", self.path))
                return True
        return False


def stand_down(path, run, reason, detail, on_limit, src, waited):
    """The designed stop (D42, D43): a supervisor-stood-down event and exit 0 — never an abort.

    Every open hold ends first (critic F6, 2026-09-17): the stood-down supervisor is the only
    process that services holds, so a hold left open is a lane the board draws `held · beat due`
    with nobody ticking. The reason is `stood-down`; ending them costs nothing and the head
    re-holds whatever it still wants warm under the next supervisor."""
    try:
        ended = end_open_holds(path, run, read_record(path)[0], "supervisor",
                               reason="stood-down",
                               note="the supervisor stood down (%s): no tick would service the "
                                    "hold" % reason)
    except (Exception, SystemExit) as exc:   # a stand-down is never blocked by a hold
        ended = 0
        say("supervisor: the open holds could not be ended at the stand-down (%s: %s); they stay "
            "open on the record" % (type(exc).__name__, exc))
    append_record(path, event(run, "supervisor-stood-down", reason=reason, on_limit=on_limit,
                              on_limit_src=src, waited_s=round(waited), note=detail,
                              holds_ended=ended))
    say("supervisor: stood down (%s) — %s; the hand-off is the recovery%s"
        % (reason, detail, " (%d hold(s) ended)" % ended if ended else ""))
    return 0


def wait_for_reset(a, path, start, text, stopped_at, watch=None):
    """The limit wait (D28, D30): --reset-at first, else the stop text's reset time, and — only
    when --probe was passed (opt-in, owner ruling 2026-09-06) — the haiku probe under the same
    login every --probe-interval-s; sleeps in --tick-s ticks so a run-close written meanwhile
    ends it; bounded by --max-wait-s. Returns (status, source, waited_s) with status ok, closed,
    reset-timeout, limit-model (a limit scoped to one model: no wait and no probe can
    clear it) or limit-unparsed (no reset time and no --probe: the hand-off is the
    recovery); the record says which. For those two no wait follows, so the supervise loop
    writes the stop's head-exit (owe_limit_exit) before its successor-aborted."""
    now_ts = time.time()
    if a.reset_at:
        target, source = parse_reset_at(a.reset_at, now_ts), "--reset-at %s" % a.reset_at
    else:
        target, source = parse_reset_text(text, now_ts) if text else (None, None)
    scope = model_limit(text) if target is None else None
    if scope is not None:
        append_record(path, event(
            a.run, "stop-condition", which="limit-model", lane="head",
            model=scope or "unstated",
            action="the stop text names a limit scoped to one model and states no reset time: "
                   "neither a wait nor a probe can clear it (a probe answers for "
                   "another model), so the recovery is a successor on a model the "
                   "account can still run",
            note=one_line(text or "")[:NOTE_CUT]))
        say("supervisor: limit — the %s limit is exhausted and the stop text states no "
            "reset time: no wait and no probe; the recovery is a successor on another "
            "model" % (scope or "current model"))
        return "limit-model", model_limit_token(scope), time.time() - stopped_at
    if target is None and not a.probe:
        append_record(path, event(
            a.run, "stop-condition", which="limit-unparsed", lane="head",
            action="no reset time in the stop text, no --reset-at and no --probe (the probe is "
                   "opt-in, owner ruling 2026-09-06): the hand-off is the recovery",
            note=one_line(text or "")[:NOTE_CUT]))
        say("supervisor: limit — no reset time could be parsed and --probe was not passed: no "
            "probe is sent and the hand-off is the recovery")
        return "limit-unparsed", "none", time.time() - stopped_at
    if target is not None:
        plan = "wait until %s (%s)" % (fmt_ts(target), source)
    else:
        plan = "probe every %d s under %s" % (
            a.probe_interval_s,
            "CLAUDE_CONFIG_DIR=%s" % a.config_dir if a.config_dir else "the same login")
    extra = ({"watch": watch.label(), "on_limit": watch.on_limit, "on_limit_src": watch.src}
             if watch is not None else {"watch": "unwatched (hand-run wait)"})
    append_record(path, event(a.run, "stop-condition", which="limit", lane="head",
                              action=plan, note=one_line(text or "")[:NOTE_CUT], **extra))
    say("supervisor: limit — %s" % plan)

    def closed():
        events, _ = read_record(path)
        return any(e.get("event") == "run-close" for e in events[start + 1:])

    def ended(what):
        append_record(path, event(a.run, "observation", phase="", what="wait-reset ended",
                                  note=what))
        say("supervisor: " + what)

    def waited():
        return time.time() - stopped_at

    if target is not None:
        if target - now_ts > a.max_wait_s:
            abort(path, a.run, "reset-timeout", "the reset at %s is %d s away, past --max-wait-s "
                  "%d" % (fmt_ts(target), target - now_ts, a.max_wait_s))
            return "reset-timeout", source, waited()
        while time.time() < target:
            if closed():
                ended("closed during the wait: a run-close follows this head's start")
                return "closed", source, waited()
            if watch is not None and watch.check():
                return "stood-down", source, waited()
            time.sleep(max(0.0, min(a.tick_s, target - time.time())))
        ended("reset reached at %s after %d s" % (fmt_ts(target), waited()))
        return "ok", source, waited()
    last_probe = None
    while True:
        if time.time() - now_ts > a.max_wait_s:
            abort(path, a.run, "reset-timeout", "no probe succeeded in %d s (--max-wait-s %d)"
                  % (time.time() - now_ts, a.max_wait_s))
            return "reset-timeout", "probe", waited()
        due = (last_probe + a.probe_interval_s) if last_probe else time.time()
        while time.time() < due:
            if closed():
                ended("closed during the wait: a run-close follows this head's start")
                return "closed", "probe", waited()
            if watch is not None and watch.check():
                return "stood-down", "probe", waited()
            time.sleep(max(0.0, min(a.tick_s, due - time.time())))
        ok, what = probe(a.harness_bin, a.config_dir)
        last_probe = time.time()
        append_record(path, event(a.run, "observation", phase="", what="wait-reset probe",
                                  note=what))
        if ok:
            ended("probe succeeded after %d s: %s" % (waited(), what))
            return "ok", "probe (%s)" % what, waited()


RESUME_NOTE = (
    "Before anything else run tail -8 on the run record and git status --short; then continue "
    "the item in flight from your own context. The hand-off document may be older than your "
    "last action: trust the record and your context, and refresh the hand-off at the next "
    "boundary.\nLanes closed with exit class limit: resume each with lane.py resume before "
    "anything else in that item.\n")


def resume_head(a, path, sid, budget, bsrc, out, m, cls, waited, source, stopped_at):
    """`claude -p --resume <sid>` from the vault with the resume note on standard input, its
    output appended to the same .out (D30, D31): (proc, out, offset, start index) or None after
    successor-aborted, reason resume-failed."""
    if cls == "limit":
        opening = ("RESUMED after the account window reset. The limit stopped this head at %s; "
                   "the window reset at %s (%s).\n"
                   % (fmt_ts(stopped_at), fmt_ts(stopped_at + waited), source))
    else:
        opening = ("RESUMED after a budget stop. The harness's cap stopped this head at %s; the "
                   "new cap is $%.2f (%s).\n" % (fmt_ts(stopped_at), budget, bsrc))
    if out in (None, "none"):
        out, _ = next_out(a.run)
    cmd = head_command(a.harness_bin, sid, budget, a.model, a.effort, resume=True)
    offset = out_size(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "ab") as handle:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=handle, stderr=handle,
                                    cwd=vault_root(), env=head_env(a.run, a.config_dir),
                                    start_new_session=True)
        except OSError as exc:
            abort(path, a.run, "resume-failed",
                  "cannot start %s --resume %s: %s" % (a.harness_bin, sid, exc))
            return None
    feed(proc, opening + RESUME_NOTE)
    events, _ = read_record(path)
    n = 1 + sum(1 for e in events
                if e.get("event") == "head-resumed" and e.get("session_id") == sid)
    append_record(path, event(a.run, "head-resumed", session_id=sid, pid=proc.pid,
                              context=m["context"], waited_s=round(waited),
                              reset_source=source, resume_n=n, out=out, budget=budget,
                              **head_model_fields(a)))
    events, _ = read_record(path)
    start = last_index(events, ("head-resumed",))
    append_record(path, event(a.run, "supervise", mode="launched", pid=proc.pid, session_id=sid,
                              out=out, supervisor_pid=os.getpid(), services_holds=True))
    say("supervisor: head-resumed pid %d session %s (resume %d) at %s tokens (%s) after %d s "
        "→ %s" % (proc.pid, sid, n, format(m["context"], ","), m.get("source"), waited, out))
    if getattr(a, "viewer_opened", False):
        a.viewer_opened = False    # `resume-head` opened it before the detach
        say("viewer: the caller ran the opener before the detach (its lines are above in this log)")
    else:
        open_console_if_dark(a.run)   # the supervisor's in-place resume after a limit reset
    return proc, out, offset, start


def successor_path(a, path, m, band, cls, budget, pid, t0, watch=None):
    """The head-exit the supervisor owes (the head wrote none), then one successor from the
    hand-off under the loop guards: (proc, sid, out, offset, start index) or None."""
    events, _ = read_record(path)
    exit_ev = event(a.run, "head-exit", band=band, context=context_text(m),
                    handoff=handoff_of(events, a.handoff), pack=False, exit_class=cls,
                    spent_usd=session_spent(meter_line(events, a.run, a.meter_line)))
    if pid is not None:
        exit_ev["pid"] = pid
    append_record(path, exit_ev)
    return succeed_exit(a, path, budget, t0, watch)


# The pack_src of the head-exit the supervisor writes on a limit stop no wait can clear (register
# entry 2026-09-14 05:13): `handoff --final` recognises the supervisor's own head-exit by it.
LIMIT_EXIT_PACK_SRC = "supervisor: the last head-written pack stands"


def limit_exit_event(a, events, sid, start, pid, stopped_at, which):
    """The head-exit the supervisor owes on a limit stop no wait can clear (register entry
    2026-09-14 05:13): wait_for_reset returned limit-unparsed or limit-model, so no resume in
    place follows and the recovery is a successor, whose premise check keys on a head-exit after
    the head's start; a successor started by hand requires that event. The caller appends
    it before successor-aborted.

    Every figure is one the record, the transcript or the meter gives, and a premise that fails
    never raises: `context` is head_context's (the transcript, else the session's last gate
    event), else null with `context_src` naming why; `spent_usd` is the billed line's session
    total (--meter-line when passed, else the meter), else null with `spent_src` naming why;
    `pid` is the head process this supervisor holds, else null with `pid_src`. `pack` is false
    with `pack_src` LIMIT_EXIT_PACK_SRC: the supervisor writes no pack, so the last pack a head
    wrote stands. `stopped_at` is the stop's own time, since the event follows the meter."""
    ev = event(a.run, "head-exit", band="limit", which=which, exit_class="limit",
               stopped_at=fmt_ts(stopped_at))
    try:
        m = head_context(sid, events, start)
    except Exception as exc:   # a broken hook must not cost the stop its head-exit
        m = {"reason": "the context measure raised %s: %s" % (type(exc).__name__, exc)}
    if m.get("context") is not None:
        ev["context"] = context_text(m)
    else:
        ev["context"], ev["context_src"] = None, "none: %s" % m.get("reason", "unknown")
    has_open = last_index(events, ("run-open",)) >= 0
    ho = getattr(a, "handoff", None) or (run_open(events).get("handoff") if has_open else None)
    if ho:
        ev["handoff"] = os.path.expanduser(ho)
    ev["pack"], ev["pack_src"] = False, LIMIT_EXIT_PACK_SRC
    if not has_open:
        line = "the record carries no run-open, so the meter has no run to read"
    else:
        try:
            line = meter_line(events, a.run, getattr(a, "meter_line", None))
        except Exception as exc:   # the same rule: a figure missing, never the event missing
            line = "the meter call raised %s: %s" % (type(exc).__name__, exc)
    ev["spent_usd"] = session_spent(line)
    if ev["spent_usd"] is None:
        ev["spent_src"] = "none: %s" % one_line(line)[:NOTE_CUT]
    ev["pid"] = pid
    if pid is None:
        ev["pid_src"] = "none: this supervisor holds no pid for the head"
    return ev


@contextlib.contextmanager
def record_lock(path):
    """An advisory exclusive lock on the run record itself, held only around a head-exit's
    re-check and append (review finding 2 on register entry 2026-09-14 05:13): the supervisor,
    `handoff --final` and `successor` each take it there, so two writers that measured in
    parallel cannot both record a head-exit for one stop. The record is opened for append, so
    the lock creates no file; without fcntl (off POSIX) no lock is taken."""
    handle = open(path, "a", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        handle.close()   # closing the descriptor releases the lock


def stop_exit(events):
    """The index of the head-exit the record already holds for its current stop, else -1. The
    current stop is a `head exited` observation after the last head start (START_EVENTS, a
    head-resumed included, since a resumed head is a new stop's head); its head-exit is any
    head-exit after that start, written before or after the observation. A record with no
    observation after its last start has no stop yet (a live head's own hand-off), so -1: a
    head that runs `handoff --final` twice still records both, as before."""
    s = last_index(events, START_EVENTS)
    tail = events[s + 1:]
    if not any(e.get("event") == "observation" and e.get("what") == "head exited" for e in tail):
        return -1
    i = last_index(tail, ("head-exit",))
    return -1 if i < 0 else s + 1 + i


def exit_recorded_text(ev):
    """`handoff --final`'s clause for a head-exit already recorded for the stop, else ""."""
    if not ev:
        return ""
    return (" · head-exit already recorded (%s at %s for this stop, band %s, pid %s): none "
            "written" % ("the supervisor's" if ev.get("pack_src") == LIMIT_EXIT_PACK_SRC
                         else "the one", ev.get("ts", "no ts"), ev.get("band"), ev.get("pid")))


def owe_limit_exit(a, path, sid, start, pid, stopped_at, which):
    """Append limit_exit_event's head-exit unless this stop already has one or a later head
    start supersedes it, so a stop never carries two: checked before the meter, which it spares,
    and again under record_lock just before the append, since a hand repair can land while the
    meter runs (review finding 2)."""
    def superseded(events):
        return last_index(events[start + 1:], START_EVENTS + ("head-exit",)) >= 0
    events, _ = read_record(path)
    if superseded(events):
        say("supervisor: a head-exit or a later head start already follows this head's start: "
            "none written")
        return None
    ev = limit_exit_event(a, events, sid, start, pid, stopped_at, which)
    with record_lock(path):
        if superseded(read_record(path)[0]):
            say("supervisor: a head-exit or a later head start was recorded while the meter "
                "ran: none written")
            return None
        append_record(path, ev)
    say("supervisor: head-exit recorded (band limit, %s, pid %s) before successor-aborted, so "
        "`successor` passes its premise" % (
            ev["context"] if ev["context"] is not None else ev["context_src"],
            "none" if pid is None else pid))
    return ev


def exited_last(events):
    """The index of the supervisor's `head exited` observation when it is the record's last
    head event (no run-open, run-resume, head-successor, head-resumed or head-exit after it),
    else -1."""
    for i in range(len(events) - 1, -1, -1):
        kind = events[i].get("event")
        if kind == "observation" and events[i].get("what") == "head exited":
            return i
        if kind in START_EVENTS or kind == "head-exit":
            return -1
    return -1


def missing_exit_refusal(events, hi, oi, path, run):
    """The successor's premise refusal on an older record (register entry 2026-09-14 05:13):
    the head a head-successor started (index hi) has exited, the supervisor's observation
    (index oi) says so, and no head-exit follows it, so the refusal names the missing event and
    the hand repair rather than a head-successor still starting. The band is the stop's exit
    class where `handoff --band` takes it (limit, error), else left to the caller."""
    cls = events[oi].get("exit_class")
    hpid = events[hi].get("pid")
    return ("the head-exit is missing: no head-exit follows the supervisor's `head exited` "
            "observation at %s (exit class %s) in %s, so the head that head-successor started "
            "(session %s) is gone, not starting (a record written before the supervisor "
            "recorded a limit stop's head-exit); repair: `handsoff.py handoff --final --band %s "
            "--run %s --pid %s --inflight-file <the last pack>`, then successor again"
            % (events[oi].get("ts", "no ts"), cls or "unrecorded", path,
               events[hi].get("session_id"),
               cls if cls in ("limit", "error") else "<a band edge or unmetered>", run,
               hpid if hpid is not None else "<the head's pid>"))


def succeed_exit(a, path, budget, t0, watch=None):
    """One successor after the record's last head-exit, under the loop guards (idempotent: a
    head-successor that appeared meanwhile is the duplicate guard's refusal)."""
    events, _ = read_record(path)
    reason, detail = start_guards(events, last_index(events, ("head-exit",)))
    if reason:
        abort(path, a.run, reason, detail)
        return None
    out, _ = next_out(a.run)
    return start_head(a, path, budget, out, t0, watch)


def seed_run_open(events):
    """The record's `run-open` event when it marks a seed session (`session_kind: seed`, T7),
    else None. The marking is the record's own field, never the run's or the session's name."""
    for ev in events:
        if ev.get("event") == "run-open" and ev.get("session_kind") == "seed":
            return ev
    return None


def seed_predecessor(events):
    """True when the head a starter would outlive is a seed session with no usable pid: the
    record's last session event is a seed run-open whose pid is absent or not given by --pid
    (register entry 2026-09-12 20:0x). Nothing ran, so there is nothing to wait for."""
    i = last_index(events, SESSION_EVENTS)
    if i < 0:
        return False
    ev = events[i]
    return (ev.get("event") == "run-open" and ev.get("session_kind") == "seed"
            and (ev.get("pid") is None or ev.get("pid_src") != "arg"))


def final_pid(events, arg):
    """(pid, source) for the head-exit `handoff --final` writes. --pid wins, as everywhere.

    On a SEEDED record use the seed's explicitly supplied pid without a parent walk.
    A seed without that explicit pid yields no pid; head records retain normal resolution.
    References (register entry 2026-09-07).
    References (register entry 2026-09-12 20:0x)."""
    if arg is not None:
        return int(arg), "arg"
    ro = seed_run_open(events)
    if ro is not None:
        if ro.get("pid_src") == "arg" and ro.get("pid") is not None:
            try:
                return int(ro["pid"]), "run-open, seed"
            except (TypeError, ValueError):
                pass
        if ro.get("pid") is not None:
            return None, "run-open, seed: its %s pid is not a seed's own" % ro.get("pid_src",
                                                                                "unsourced")
        return None, "run-open, seed: no pid"
    return head_pid(None)


def seed_exit(ev):
    """True when a head-exit records a session that left no transcript: its context reads
    `unmetered (transcript missing …)` and no spend was metered. That is a record opened for a
    head which never ran — a seeded record — and nothing about it is a stop. The test is the
    event's own observable fields; the run's or the session's name is never the key."""
    if ev.get("event") != "head-exit":
        return False
    context = str(ev.get("context") or "")
    return (context.startswith("unmetered") and "transcript missing" in context
            and ev.get("spent_usd") is None)


def previous_stop(events):
    """The exit class of the last head stop the record holds (the supervisor's own `head
    exited` observation), or None. A stop whose head-exit shows the session left no transcript
    is skipped: nothing ran, so it cannot be the first of two consecutive faults (register
    2026-09-06). The head-exit is looked for beside the observation, which the supervisor and
    `handoff --final` write in either order."""
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("event") == "observation" and ev.get("what") == "head exited":
            if any(seed_exit(x) for x in events[max(0, i - 1):i + 2]):
                continue
            return ev.get("exit_class")
    return None


# ------------------------------------------------------------------- held lanes ------------
# A finished lane the head still expects to resume is kept warm: `hold` records it,
# and the supervisor issues a no-work beat through
# the lane's own wrapper HOLD_BEAT_S after the lane's last call, and the hold ends at its cap, on
# a close a beat cannot re-enter, on `release` or on the run's close. The record is the whole
# state: a `hold` event opens it (a renew is a `hold` with renew true and a fresh count), the
# wrapper's `hold-beat` events count against the cap, a `hold-ended` closes it.

def is_lane_hold(ev):
    """A lane hold, never the schema's older decision hold (class, what, route): the event names
    a lane and carries a cap."""
    return ev.get("event") == "hold" and isinstance(ev.get("lane"), str) and "cap" in ev


def hold_state(events, lane):
    """The lane's open hold, else None: the latest lane `hold` event naming it (a renew is one)
    with no `hold-ended` for the lane after it. `cap` is that event's, `beats` the hold-beat
    events since it, so a renew starts a fresh count."""
    idx = -1
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("lane") != lane:
            continue
        if ev.get("event") == "hold-ended":
            return None
        if is_lane_hold(ev):
            idx = i
            break
    if idx < 0:
        return None
    hold = events[idx]
    beats = [e for e in events[idx + 1:]
             if e.get("event") == "hold-beat" and e.get("lane") == lane]
    cap = hold.get("cap")
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        cap = HOLD_CAP_DEFAULT
    return {"index": idx, "hold": hold, "cap": cap, "beats": beats,
            "ok": sum(1 for b in beats if b.get("ok") is True),
            "failed": sum(1 for b in beats if b.get("ok") is not True)}


def open_holds(events):
    """{lane: hold_state} for every lane whose hold is open, in lane order."""
    found = {}
    for lane in sorted({e.get("lane") for e in events if is_lane_hold(e)}):
        state = hold_state(events, lane)
        if state is not None:
            found[lane] = state
    return found


def lane_open_event(events, lane):
    for ev in reversed(events):
        if ev.get("event") == "lane-open" and ev.get("lane") == lane:
            return ev
    return None


def lane_start_index(events, lane):
    """The index of the lane's latest lane-open or lane-resumed, else -1."""
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("lane") == lane and \
                events[i].get("event") in ("lane-open", "lane-resumed"):
            return i
    return -1


def lane_close_after(events, lane, start):
    """The index of the first lane-closed for the lane after `start`, else -1 (still running)."""
    for i in range(start + 1, len(events)):
        if events[i].get("lane") == lane and events[i].get("event") == "lane-closed":
            return i
    return -1


def lane_session_of(events, lane, opened, closed):
    """The session a beat re-enters: the close's, else the lane's last recorded session (a Codex
    lane's lane-session line, a spawn's), else the open's; None when the record names none."""
    sid = closed.get("session_id") if closed else None
    if not sid:
        for ev in reversed(events):
            if ev.get("lane") == lane and ev.get("session_id") and \
                    ev.get("event") in ("lane-session", "lane-spawned", "lane-respawned"):
                sid = ev["session_id"]
                break
    return sid or (opened or {}).get("session_id")


def lane_harness(opened):
    return "codex" if (opened or {}).get("harness") == "codex" else "claude"


def file_last_stamp(path):
    """(epoch, how) from the last JSON record in the file's tail that carries a parseable
    `timestamp`, else the file's mtime; (None, None) when the file cannot be read."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            handle.seek(max(0, size - TAIL_BYTES))
            tail = handle.read().decode("utf-8", "replace")
    except OSError:
        return None, None
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        t = parse_ts(rec.get("timestamp")) if isinstance(rec, dict) else None
        if t is not None:
            return t, "timestamp"
    try:
        return os.path.getmtime(path), "mtime"
    except OSError:
        return None, None


def codex_session_file(thread):
    """The Codex CLI's session file for a thread — `<CODEX_HOME or ~/.codex>/sessions/<year>/
    <month>/<day>/rollout-<stamp>-<thread>.jsonl` — else None. The layout is the CLI's own,
    read here and never written; a miss falls back to the wrapper's events log."""
    if not isinstance(thread, str) or not TOKEN_RE.fullmatch(thread):
        return None
    root = os.environ.get(CODEX_HOME_ENV) or os.path.join(os.path.expanduser("~"), ".codex")
    hits = sorted(globmod.glob(os.path.join(root, "sessions", "*", "*", "*",
                                            "rollout-*-%s.jsonl" % thread)))
    return hits[-1] if hits else None


def lane_last_call(events, lane, opened, closed):
    """(epoch, source) of the lane's last model call, read per wrapper. A Claude lane: the last
    assistant record's timestamp of its transcript (the close names the file, else the wrapper's
    own locator finds it). A Codex lane: the last event of its session file, else the mtime of
    the wrapper's copy of the event stream in the store, which the last event's arrival wrote.
    Either: the lane-closed stamp. The source is recorded on the hold and on every beat."""
    harness = lane_harness(opened)
    sid = lane_session_of(events, lane, opened, closed)
    if harness == "codex":
        path = codex_session_file(sid)
        if path:
            t, how = file_last_stamp(path)
            if t is not None:
                return t, "codex session file (%s) %s" % (how, path)
        log = (opened or {}).get("events")
        if isinstance(log, str) and os.path.isfile(log):
            try:
                return os.path.getmtime(log), "codex events log mtime %s" % log
            except OSError:
                pass
    else:
        path = closed.get("transcript") if closed else None
        if not (isinstance(path, str) and os.path.isfile(path)):
            module, _, _ = lane_module()
            home = (opened or {}).get("cwd")
            if module is not None and sid and isinstance(home, str):
                root = (opened or {}).get("projects_root") or projects_root()
                path = module.find_transcript(root, home, sid)
        if isinstance(path, str) and os.path.isfile(path):
            stamps = head_calls(path)
            if stamps:
                return stamps[-1], "transcript last assistant record %s" % path
    t = parse_ts((closed or {}).get("ts"))
    if t is not None:
        return t, "lane-closed ts"
    return None, "none: no transcript, session file, events log or parseable lane-closed ts"


def beat_reference(state, last_call, src, ok_only=False):
    """The later of the lane's last call and its last recorded beat.

    The SERVICE reference (ok_only false) counts a failed beat too: one attempt per interval, so
    a failure is never retried tick after tick. The WINDOW reference (ok_only true) counts only a
    beat that succeeded, because only a call that ran kept the cache warm — a failed beat moved
    nothing, and measuring the window from it would hold a lane whose context has lapsed (critic
    F5a, 2026-09-17). lane.py's `resume` and `advise` read the same ok-only reference."""
    ref, rsrc = last_call, src
    for b in (state or {}).get("beats") or []:
        ok = b.get("ok") is True
        if ok_only and not ok:
            continue
        t = parse_ts(b.get("ts"))
        if t is not None and (ref is None or t > ref):
            ref, rsrc = t, "hold-beat ts (%s)" % ("ok" if ok else "failed")
    return ref, rsrc


def hold_supervision(events):
    """(state, note) on whether a supervisor that services holds is watching this run, read from
    the record's own events rather than from the presence of a `run-open` (critic F5b,
    2026-09-17): a hold is serviced by a supervisor's tick, so what the guard must test is the
    supervisor, not the run.

    `stood-down` — the latest supervisor event is a `supervisor-stood-down`: nothing would ever
    service the hold. `stopping` — a `supervise --stop` was requested: the supervisor stands down
    at the head's exit. `ticking` — a supervisor attached or launched itself and its event says it
    services holds. `unmarked` — a supervisor whose `supervise` event carries no `services_holds`,
    which is one started before this mechanism shipped: its wait blocks on the head's process and
    never reads a hold. `none` — the record carries no supervisor event at all, which is the
    re-attach case a hold is allowed to precede (suite leg H5)."""
    latest, mode = None, None
    for ev in events:
        kind = ev.get("event")
        if kind == "supervisor-stood-down":
            latest, mode = ev, "stood-down"
        elif kind == "supervise" and ev.get("mode") in ("launched", "attached"):
            latest, mode = ev, "ticking" if ev.get("services_holds") is True else "unmarked"
        elif kind == "supervise" and ev.get("mode") == "stop-requested":
            latest, mode = ev, "stopping"
    if mode is None:
        return "none", ("the record carries no supervise event: a hold written before a "
                        "supervisor attaches is serviced at its first tick")
    when = latest.get("ts", "no ts")
    if mode == "stood-down":
        return mode, "supervisor-stood-down (%s) at %s" % (latest.get("reason") or "unstated", when)
    if mode == "stopping":
        return mode, ("a supervisor stop was requested at %s: the supervisor stands down at the "
                      "head's exit and services no hold after it" % when)
    if mode == "unmarked":
        return mode, ("the supervisor attached at %s records no services_holds: a supervisor "
                      "started before the held-lane code blocks on the head and never reads a "
                      "hold" % when)
    return mode, "a hold-servicing supervisor attached at %s (pid %s)" % (when, latest.get("pid"))


def hold_service_blocked(a, path, events=None):
    """(why, terminal): why no hold of this run may be beaten any more — a supervisor stop
    requested (its marker on disk, or the `supervise` event), a closed run, or a supervisor that
    has stood down — else ("", False). Critic finding 1 of review, 2026-09-17.

    `terminal` says whether the block can still be lifted: a closed run and a stood-down
    supervisor never tick again, so their open holds are ended rather than left on the board,
    while a REQUESTED stop can still be cleared (`resume-head`, a head's own successor, `close`),
    so its holds stand and the supervisor says why.

    The supervisor's tick reads this before the service with the marker alone (`events=()`), and
    `service_holds` reads it again from the record it has just read, so a stop that landed
    between the two is still caught before any process starts. `events=None` reads the record."""
    marker = supervisor_stop_file(a.run)
    if os.path.isfile(marker):
        return "a supervisor stop is requested (the marker %s)" % marker, False
    if events is None:
        events, _ = read_record(path)
    if run_is_closed(events):
        return ("the run is closed (run-close at %s)"
                % events[last_index(events, ("run-close",))].get("ts", "no ts")), True
    state, note = hold_supervision(events)
    if state == "stood-down":
        return note, True
    if state == "stopping":
        return note, False
    return "", False


def tier_note(closed, interval):
    """A warning line where the lane's own cache write tier is shorter than the beat's interval,
    else "" (critic F5c, 2026-09-17): the 50-minute interval rests on the 1-hour tier, and
    `lane-closed.cache_write_tier` is what the harness actually wrote, so the guard reads that
    list rather than assuming the tier. A close from before the field, or one naming the 1-hour
    tier, warns about nothing."""
    tiers = (closed or {}).get("cache_write_tier")
    if not isinstance(tiers, (list, tuple)) or not tiers:
        return ""
    named = [str(t) for t in tiers]
    if HOLD_TIER_1H in named or interval <= 5 * 60:
        return ""
    return ("the lane's last call wrote the cache at tier %s, not %s: a beat %.0f min later "
            "re-sends the whole context (a counted rewrite on the closing meter), so shorten "
            "--beat-after-s or expect a cold re-send"
            % ("/".join(named), HOLD_TIER_1H, interval / 60.0))


def hold_interval(state):
    """The hold event's own beat_after_s, else HOLD_BEAT_S."""
    value = state["hold"].get("beat_after_s")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return HOLD_BEAT_S
    return value


def run_is_closed(events):
    return last_index(events, ("run-close",)) > last_index(events, ("run-open", "run-resume"))


def end_hold(path, run, lane, state, reason, by, note):
    """One hold-ended event (reason in HOLD_ENDED_REASONS) and one line."""
    ev = event(run, "hold-ended", lane=lane, reason=reason, by=by, cap=state["cap"],
               beats=len(state["beats"]), beats_ok=state["ok"], beats_failed=state["failed"],
               held_since=state["hold"].get("ts"), note=note)
    append_record(path, ev)
    say("hold-ended: %s/%s (%s) · %d beat(s), %d ok, %d failed · %s"
        % (run, lane, reason, len(state["beats"]), state["ok"], state["failed"], note))
    return ev


def end_open_holds(path, run, events, by, reason="run-close", note="the run closed"):
    """Every open hold ended with one reason: the count ended. `close` uses it before it writes
    the run-close, and a stand-down uses it with `stood-down` (critic F6), since a supervisor
    that has stood down services no hold."""
    holds = open_holds(events)
    for lane, state in holds.items():
        end_hold(path, run, lane, state, reason, by, note)
    return len(holds)


def cmd_hold(a):
    path = record_path(a.run)
    events = require_record(path, " — a hold needs a supervised head; an attended session beats "
                                  "by hand with `lane.py resume --beat`")
    if run_is_closed(events):
        die("run %s is closed (run-close at %s): a hold outlives no run"
            % (a.run, events[last_index(events, ("run-close",))].get("ts", "no ts")))
    # The supervisor, not the run, is what services a hold (critic F5b): a stand-down or a
    # requested stop means nothing will, so the hold is refused before anything is written; a
    # supervisor that predates this mechanism, or none yet (the re-attach case), is a warning.
    supervision, snote = hold_supervision(events)
    if supervision in ("stood-down", "stopping"):
        die("run %s has no supervisor to service a hold: %s — hold a lane only under a run "
            "whose own supervisor is running. A live run's supervisor is never stopped and "
            "re-attached for this: an install is attended and between runs, and a rehearsal "
            "opens the next run under that run's own fresh supervisor"
            % (a.run, snote))
    lane = token(a.lane, "lane id")
    opened = lane_open_event(events, lane)
    if opened is None:
        die("lane %s/%s is unknown in %s (no lane-open)" % (a.run, lane, path))
    if a.cap is not None and not 1 <= a.cap <= HOLD_CAP_MAX:
        die("--cap takes 1 to %d beat(s), got %d: %d beats at the default interval span about "
            "%d hours, past any recorded run, so a larger cap is a slip — renew instead"
            % (HOLD_CAP_MAX, a.cap, HOLD_CAP_MAX, HOLD_CAP_MAX * HOLD_BEAT_S // 3600))
    if not 1 <= a.beat_after_s <= HOLD_WINDOW_S:
        die("--beat-after-s takes 1 to %d s, got %d: a beat due after the %d-minute resume window "
            "arrives at a cache that has already lapsed, so it would re-send the whole context "
            "rather than refresh it" % (HOLD_WINDOW_S, a.beat_after_s, HOLD_WINDOW_S // 60))
    state = hold_state(events, lane)
    if a.renew:
        if state is None:
            die("lane %s/%s has no open hold to renew" % (a.run, lane))
    elif state is not None:
        die("lane %s/%s is already held (hold at %s, cap %d, %d beat(s) so far): `hold --renew` "
            "extends it" % (a.run, lane, state["hold"].get("ts", "no ts"), state["cap"],
                            len(state["beats"])))
    start = lane_start_index(events, lane)
    close_i = lane_close_after(events, lane, start)
    if close_i < 0:
        die("lane %s/%s has no lane-closed after its latest start: a hold keeps a FINISHED lane "
            "warm; `watch` it first" % (a.run, lane))
    closed = events[close_i]
    cls = closed.get("exit_class")
    if cls not in HOLDABLE_EXITS:
        die("lane %s/%s closed %s: a beat re-enters only a close in %s (a limit or budget close "
            "is the head's own resume decision, D29; a killed, stalled or errored lane is "
            "re-spawned)" % (a.run, lane, cls or "unstated", "/".join(HOLDABLE_EXITS)))
    harness = lane_harness(opened)
    sid = lane_session_of(events, lane, opened, closed)
    if not sid:
        die("lane %s/%s records no session id: a beat has nothing to re-enter" % (a.run, lane))
    last_call, src = lane_last_call(events, lane, opened, closed)
    # The window is measured from the lane's last call or a beat that SUCCEEDED (critic F5a): a
    # failed beat kept nothing warm, so it is no evidence of a warm cache even though the service
    # counts it to avoid a retry.
    ref, rsrc = beat_reference(state, last_call, src, ok_only=True)
    if ref is None:
        die("lane %s/%s: no last call could be read (%s)" % (a.run, lane, src))
    age = time.time() - ref
    if age > HOLD_WINDOW_S:
        die("lane %s/%s: last call %.0f min ago (%s), past the %d-minute window: nothing is warm "
            "to hold; resume cold (D29) or re-spawn" % (a.run, lane, age / 60.0, rsrc,
                                                        HOLD_WINDOW_S // 60))
    cap = a.cap if a.cap is not None else HOLD_CAP_DEFAULT
    tier = tier_note(closed, a.beat_after_s)
    ev = event(a.run, "hold", lane=lane, harness=harness, cap=cap, beat_after_s=a.beat_after_s,
               session_id=sid, exit_class=cls, last_call=fmt_ts(ref), last_call_src=rsrc,
               last_call_age_s=round(age), renew=bool(a.renew),
               beats_before=len(state["beats"]) if state else 0, pid=os.getpid(),
               supervision=supervision, cache_write_tier=(closed.get("cache_write_tier")
                                                          if closed else None),
               tier_warning=tier or None)
    due = fmt_ts(ref + a.beat_after_s)
    if a.dry_run:
        say("hold: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        return 0
    append_record(path, ev)
    say("hold: %s/%s %s · %s lane · cap %d beat(s) · last call %s (%s, %.0f min ago) · next beat "
        "due %s · the supervisor's tick services it"
        % (a.run, lane, "renewed" if a.renew else "held", harness, cap, fmt_ts(ref), rsrc,
           age / 60.0, due))
    if supervision in ("none", "unmarked"):
        say("hold: warning · %s" % snote)
    if tier:
        say("hold: warning · %s" % tier)
    return 0


def cmd_release(a):
    path = record_path(a.run)
    events = require_record(path)
    lane = token(a.lane, "lane id")
    state = hold_state(events, lane)
    if state is None:
        die("lane %s/%s has no open hold to release" % (a.run, lane))
    if a.dry_run:
        say("release: dry run · would end the hold on %s/%s (held since %s, %d beat(s))"
            % (a.run, lane, state["hold"].get("ts", "no ts"), len(state["beats"])))
        return 0
    end_hold(path, a.run, lane, state, "released", "release", "released by hand")
    return 0


# The mirrored rewrite rule (review finding 4, 2026-09-18). The closing meter classifies a
# full-context rewrite with ONE fraction and no other number: `fable-share.py`'s
# REWRITE_FRACTION — 0.9, defined at its constants block (line 313 on 2026-09-18) and applied in
# its `aggregate()` classifier, whose rule is "a call is a rewrite when its cache write is at
# least 0.9 × BOTH its own context and the previous call's". A beat's verdict mirrors that
# fraction rather than choosing one of its own, so what `hold-verdict` says and what the closing
# meter's rewrite causes say cannot drift apart. It is a classifier, not a decision threshold,
# there as here: it labels a beat and decides nothing about the run. A suite leg greps both
# files and asserts the two constants are equal, because a copy is only as good as its check.
HOLD_VERDICT_FRACTION = 0.9
HOLD_VERDICT_EXITS = {"hit": 0, "rewrite": 1, "open": 2}


def beat_usage_figures(beat):
    """(whole, cached, uncached, missing) for one `hold-beat`, per harness: what the call's whole
    input was, how much of it the cache served, and how much was not. `missing` names the field
    or premise that is absent, in which case the three figures are None.

    Claude (the harness's own usage record): the whole input is `cache_read_input_tokens` +
    `cache_creation_input_tokens` + `input_tokens`, the cached part the read, the uncached part
    the creation plus the input. Codex (the CLI's `turn.completed`): the whole input is
    `input_tokens`, of which `cached_input_tokens` is a part. Their difference is the uncached
    input. `cache_write_input_tokens` is carried beside them; an absent cache-write figure
    proves nothing and enters no verdict."""
    if beat.get("ok") is not True:
        return None, None, None, ("the beat did not succeed (%s)"
                                  % (beat.get("error") or beat.get("exit_class") or "ok false"))
    usage = beat.get("usage")
    if not isinstance(usage, dict) or not usage:
        return None, None, None, "the beat carries no usage"
    if beat.get("usage_complete") is False:
        return None, None, None, "the wrapper recorded usage_complete false"
    codex = beat.get("harness") == "codex"
    fields = (("input_tokens", "cached_input_tokens") if codex
              else ("cache_read_input_tokens", "cache_creation_input_tokens", "input_tokens"))
    values = {}
    for field in fields:
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None, None, None, "usage.%s is %r" % (field, value)
        values[field] = value
    if codex:
        whole, cached = values["input_tokens"], values["cached_input_tokens"]
        if cached > whole:
            return None, None, None, ("usage.cached_input_tokens (%d) is larger than "
                                      "usage.input_tokens (%d)" % (cached, whole))
        return whole, cached, whole - cached, ""
    cached = values["cache_read_input_tokens"]
    uncached = values["cache_creation_input_tokens"] + values["input_tokens"]
    return cached + uncached, cached, uncached, ""


def beat_verdict(beat):
    """(verdict, note, figures) for one `hold-beat`: `hit` where the cached read is at least
    HOLD_VERDICT_FRACTION of the call's whole input, `rewrite` where the uncached part is, else
    `open` with the figures. A beat whose premise is missing — it failed, it carries no usage, a
    field is absent or incoherent, or the whole input reads zero — is `open` and says what is
    missing, never a verdict drawn from nothing."""
    whole, cached, uncached, missing = beat_usage_figures(beat)
    if missing:
        return "open", "unmeasured: %s" % missing, (None, None, None)
    if whole <= 0:
        return "open", "unmeasured: the call's whole input reads 0 tokens", (whole, cached, uncached)
    if cached >= HOLD_VERDICT_FRACTION * whole:
        return "hit", "", (whole, cached, uncached)
    if uncached >= HOLD_VERDICT_FRACTION * whole:
        return "rewrite", "", (whole, cached, uncached)
    return "open", "neither side reaches %.2f of the whole input" % HOLD_VERDICT_FRACTION, \
        (whole, cached, uncached)


def hold_verdict_rows(events, lane=None):
    """One row per `hold-beat` on the record, in record order, for `lane` or every lane."""
    rows = []
    for ev in events:
        if ev.get("event") != "hold-beat":
            continue
        if lane is not None and ev.get("lane") != lane:
            continue
        verdict, note, (whole, cached, uncached) = beat_verdict(ev)
        rows.append({
            "lane": ev.get("lane") or "?", "harness": ev.get("harness") or "claude",
            "n": ev.get("n"), "ts": ev.get("ts"), "by": ev.get("by"),
            "ok": ev.get("ok") is True,
            "config_match": ev.get("config_match"),
            "whole_input_tokens": whole, "cached_input_tokens": cached,
            "uncached_input_tokens": uncached,
            "cached_share": round(cached / whole, 3) if whole else None,
            "verdict": verdict, "note": note})
    return rows


def cmd_hold_verdict(a):
    """`hold-verdict --run R [--lane L] [--format text|json]`: what each of the run's held-lane
    beats did to the cache, read from the record and from nothing else (review finding 4,
    2026-09-18 — the acceptance evidence the rehearsal reads for a Codex lane, where the closing
    meter's rewrite causes cover only the Claude side).

    READ-ONLY: it opens the record, prints, and creates, modifies, moves and deletes nothing, so
    it is safe against a live run's store. The verdict mirrors the closing meter's own rewrite
    fraction (HOLD_VERDICT_FRACTION) and introduces no number of its own.

    Exit 0 when every beat read `hit`, 1 when any read `rewrite` and none read `open`, 2 when any
    read `open` — an unmeasured beat leaves the run's reading incomplete, which is a premise
    failure rather than a verdict, so it outranks a rewrite (builder's reading of the ruling's
    three codes, 2026-09-18) — and 2 on a record with no `hold-beat` at all."""
    path = record_path(a.run)
    events, bad = read_record(path)
    lane = token(a.lane, "lane id") if a.lane else None
    rows = hold_verdict_rows(events, lane)
    counts = {"hit": 0, "rewrite": 0, "open": 0}
    for row in rows:
        counts[row["verdict"]] += 1
    if not rows:
        say("hold-verdict: %s · no hold-beat on the record%s: nothing to read"
            % (a.run, " for lane %s" % lane if lane else ""))
        if a.format == "json":
            say(json.dumps({"run": a.run, "lane": lane, "beats": [], "counts": counts,
                            "exit": 2, "skipped_lines": bad}, ensure_ascii=False))
        return 2
    code = 2 if counts["open"] else (1 if counts["rewrite"] else 0)
    if a.format == "json":
        say(json.dumps({"run": a.run, "lane": lane, "beats": rows, "counts": counts,
                        "rewrite_fraction": HOLD_VERDICT_FRACTION, "exit": code,
                        "skipped_lines": bad}, ensure_ascii=False))
        return code
    for row in rows:
        figures = ("cached %s of %s (%s) · uncached %s"
                   % (row["cached_input_tokens"], row["whole_input_tokens"],
                      "share %.3f" % row["cached_share"] if row["cached_share"] is not None
                      else "share unreadable", row["uncached_input_tokens"])
                   if row["whole_input_tokens"] is not None else "no figures")
        say("hold-verdict: %s · %s · beat %s · ok %s · config %s · %s · %s%s"
            % (row["lane"], row["harness"], row["n"], "true" if row["ok"] else "false",
               {True: "match", False: "MISMATCH", None: "unrecorded"}.get(row["config_match"],
                                                                         "unrecorded"),
               figures, row["verdict"], " (%s)" % row["note"] if row["note"] else ""))
    say("hold-verdict: %s · %d beat(s) · hit %d · rewrite %d · open %d · exit %d%s"
        % (a.run, len(rows), counts["hit"], counts["rewrite"], counts["open"], code,
           " · %d unparseable line(s) skipped" % bad if bad else ""))
    return code


def beat_wrapper(harness):
    """The wrapper a beat goes through: the lane's own (lane.py or codex-lane.py) beside this
    file, or under BEAT_WRAPPER_DIR_ENV (a suite's stubs)."""
    root = os.environ.get(BEAT_WRAPPER_DIR_ENV) or HERE
    return os.path.join(root, "codex-lane.py" if harness == "codex" else "lane.py")


def issue_beat(a, path, lane, harness, state, age, src):
    """One beat attempt through the lane's wrapper: `<wrapper> resume --run R --lane L --beat`.
    The wrapper writes the hold-beat with the usage; when it writes none (a refusal, a crash, a
    timeout) the supervisor writes one with ok false, so every attempt is on the record exactly
    once and the reference moves — no retry within this tick or the next interval."""
    wrapper = beat_wrapper(harness)
    n = len(state["beats"]) + 1
    before = len(read_record(path)[0])
    t0 = time.time()
    rc, err = None, ""
    if not os.path.isfile(wrapper):
        err = "no wrapper at %s" % wrapper
    else:
        cmd = [sys.executable, "-B", wrapper, "resume", "--run", a.run, "--lane", lane,
               "--beat", "--format", "json"]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", AIMYTH_VIEWER="none")
        env[BEAT_BY_ENV] = "supervisor"
        timeout = getattr(a, "beat_timeout_s", HOLD_BEAT_TIMEOUT_S)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                  cwd=vault_root(), env=env)
            rc = proc.returncode
            err = (proc.stderr or "").strip() or (proc.stdout or "").strip()
        except subprocess.TimeoutExpired:
            # Past the wrapper's own bound plus the grace (critic F2): the wrapper should have
            # killed its process group and recorded the failure itself, so reaching here means
            # the wrapper is wedged and its harness may survive on the lane's session — the
            # record says so, since a later real resume would then be a second process on it.
            err = ("the beat wrapper did not finish in %d s (its own bound is %d s plus a %d s "
                   "grace, so it did not kill its own harness: check the lane's session for a "
                   "stray process before any real resume)"
                   % (timeout, HOLD_BEAT_WRAPPER_BOUND_S, HOLD_BEAT_GRACE_S))
        except OSError as exc:
            err = "the beat wrapper could not start: %s" % exc
    duration = round(time.time() - t0, 1)
    events, _ = read_record(path)
    written = [e for e in events[before:] if e.get("event") == "hold-beat" and e.get("lane") == lane]
    if written:
        ok = written[-1].get("ok") is True
        say("supervisor: hold %s/%s · beat %d/%d through %s after %.0f min (%s): %s in %.1f s"
            % (a.run, lane, n, state["cap"], os.path.basename(wrapper), age / 60.0, src,
               "ok" if ok else "FAILED (%s)" % (written[-1].get("error") or written[-1].get("exit_class") or "unstated"),
               duration))
        return ok
    append_record(path, event(a.run, "hold-beat", lane=lane, harness=harness, ok=False, n=n,
                              by="supervisor", wrapper=wrapper, process_exit=rc,
                              duration_s=duration, usage=None,
                              error=one_line(err)[-NOTE_CUT:] if err else "exit %s" % rc,
                              note="the wrapper recorded no hold-beat: this line stands for the "
                                   "attempt, which is not retried within the interval"))
    say("supervisor: hold %s/%s · beat %d/%d through %s after %.0f min (%s): FAILED, exit %s "
        "(%s)" % (a.run, lane, n, state["cap"], os.path.basename(wrapper), age / 60.0, src,
                  "none" if rc is None else rc, one_line(err)[:160] or "no output"))
    return False


def apply_hold_block(a, path, events, blocked, terminal, when):
    """What the service does about a block it has just read: a TERMINAL one — the run closed, or
    the supervisor stood down — ends every open hold (`hold-ended`, reason `stood-down`, by
    `supervisor`, the note naming the block and where it was seen), since nothing will ever tick
    again and a hold left open reads `held · beat due` on a board with no supervisor behind it. A
    non-terminal one — a REQUESTED stop, which `resume-head`, a head's own successor or `close`
    can still clear — leaves the holds and says why. Returns the number of open holds it saw.

    Called at both of the service's stop checks, so the two read the same way (review finding 1,
    2026-09-18): the check at the pass's opening, and the one on the fresh events read
    immediately before a beat."""
    holds = open_holds(events)
    if holds and terminal:
        for lane, state in holds.items():
            end_hold(path, a.run, lane, state, "stood-down", "supervisor",
                     "the hold service stopped %s: %s" % (when, blocked))
    elif holds:
        say("supervisor: %d open hold(s) not serviced and not ended: %s" % (len(holds), blocked))
    return len(holds)


def service_holds(a, path):
    """One pass over the record's open holds: a beat through the lane's own wrapper when its
    interval has passed since the lane's last call (or its last beat); the hold ended at the
    cap when the next beat falls due, or on a close a beat cannot re-enter; a held lane that is
    running again is left alone. One attempt per lane per pass, never a retry inside it."""
    events, _ = read_record(path)
    # Nothing beats on a run that has stopped (critic finding 1 of review): a requested stop, a
    # run-close or a stand-down on the record ends the service here, before any beat. A terminal
    # block — the run closed, or the supervisor stood down — also ends the open holds, so no lane
    # is left reading `held` with nobody ticking; a requested stop is not terminal (the head can
    # still clear the marker with `resume-head`), so its holds stand and the line says why.
    blocked, terminal = hold_service_blocked(a, path, events)
    if blocked:
        apply_hold_block(a, path, events, blocked, terminal, "before the pass")
        return
    now_ts = time.time()
    for lane, state in open_holds(events).items():
        opened = lane_open_event(events, lane)
        if opened is None:
            end_hold(path, a.run, lane, state, "lane-closed", "supervisor",
                     "the record holds no lane-open for the held lane")
            continue
        start = lane_start_index(events, lane)
        close_i = lane_close_after(events, lane, start)
        if close_i < 0:
            continue    # resumed for real and still running: a beat would be a second process on one session
        closed = events[close_i]
        if close_i > state["index"] and closed.get("exit_class") not in HOLDABLE_EXITS:
            end_hold(path, a.run, lane, state, "lane-closed", "supervisor",
                     "the lane closed %s after the hold: a beat cannot re-enter that close"
                     % (closed.get("exit_class") or "unstated"))
            continue
        last_call, src = lane_last_call(events, lane, opened, closed)
        ref, rsrc = beat_reference(state, last_call, src)
        if ref is None:
            ref, rsrc = parse_ts(state["hold"].get("ts")), "hold ts (no last call readable)"
        if ref is None:
            say("supervisor: hold %s/%s · no readable last call and no hold ts: skipped"
                % (a.run, lane))
            continue
        interval = hold_interval(state)
        if now_ts < ref + interval:
            continue
        if len(state["beats"]) >= state["cap"]:
            end_hold(path, a.run, lane, state, "cap", "supervisor",
                     "%d beat(s) issued against a cap of %d and the next fell due; `hold --renew` "
                     "would have extended it" % (len(state["beats"]), state["cap"]))
            continue
        # The last act before a beat: the record re-read, since an earlier lane's beat in this
        # pass can take minutes and a release, a renew or a second supervisor's beat may have
        # landed meanwhile. A changed hold is left to the next tick; the residue (two supervisors
        # reading inside one wrapper call) is narrowed, not closed, and costs one spare beat.
        fresh, _ = read_record(path)
        # The same re-read re-checks the RUN's stop state, not only this lane's hold (review
        # finding 1, 2026-09-18): the opening check above can be minutes old by now — an earlier
        # lane's beat is bounded by HOLD_BEAT_TIMEOUT_S — so a stop requested, a run closed or a
        # supervisor stood down meanwhile must never buy another beat. The marker is re-read
        # inside hold_service_blocked, so a `supervise --stop` that wrote nothing to the record
        # yet is caught here too; a terminal block ends the open holds at this point.
        blocked, terminal = hold_service_blocked(a, path, fresh)
        if blocked:
            apply_hold_block(a, path, fresh, blocked, terminal, "during the pass")
            return
        again = hold_state(fresh, lane)
        if again is None or again["index"] != state["index"] or \
                len(again["beats"]) != len(state["beats"]):
            continue
        # The same re-read re-checks the lane itself, not only its hold (critic F3, 2026-09-17):
        # a real resume that landed during this pass leaves the lane RUNNING, and a beat would be
        # a second process on one session. Without this the wrapper refuses, the refusal is
        # recorded as a failed beat, and the hold ends at the cap having beaten nothing.
        fresh_start = lane_start_index(fresh, lane)
        fresh_close = lane_close_after(fresh, lane, fresh_start)
        if fresh_close < 0:
            say("supervisor: hold %s/%s · the lane started again during this pass: no beat, no "
                "record line, and the hold stands for the next tick" % (a.run, lane))
            continue
        if fresh_close > again["index"] and \
                fresh[fresh_close].get("exit_class") not in HOLDABLE_EXITS:
            say("supervisor: hold %s/%s · the lane closed %s during this pass: no beat; the next "
                "tick ends the hold" % (a.run, lane,
                                        fresh[fresh_close].get("exit_class") or "unstated"))
            continue
        issue_beat(a, path, lane, lane_harness(opened), state, now_ts - ref, rsrc)


def wait_head(a, path, proc, pid):
    """The supervisor's wait on the head's process, servicing the record's open holds every
    --tick-s meanwhile (the held-lane mechanism): the process's exit code, or None in attach
    mode once the pid is gone. A hold whose premise breaks costs the head nothing.

    The order inside a tick is the head, then this supervisor's own stop state, and only then
    the holds. A head that has gone returns here before any beat
    is issued, and a requested stop skips the service altogether.

    The FIRST service waits one whole tick after the attach, for the same reason: a head that
    stops at once is classified before any hold is
    serviced. One tick costs a hold nothing, since a beat falls due HOLD_BEAT_S (50 min) after
    the lane's last call and the supervisor's tick is a minute."""
    next_service = time.time() + a.tick_s
    while True:
        # The head first: a process that has exited, or an attached pid that has gone, ends the
        # wait now. `poll` does not block, so this costs the tick nothing.
        if proc is not None:
            code = proc.poll()
            if code is not None:
                return code
        elif not pid_alive(pid):
            return None
        if time.time() >= next_service:
            try:
                # This supervisor's own stop state, read before the service and again inside it
                # from the record it reads anyway: a stop asked for by marker is honoured at
                # once, without waiting for the stand-down the head's exit will write.
                blocked = hold_service_blocked(a, path, ())[0]
                if blocked:
                    say("supervisor: the open holds are not serviced: %s" % blocked)
                else:
                    service_holds(a, path)
            # A broken hold must never cost the head its supervisor. SystemExit is caught by
            # name as well (critic F1, 2026-09-17): the record readers and writers this service
            # calls end on `die`, which is sys.exit(2), and a bare `except Exception` lets that
            # through — a torn record line would have ended the supervisor of a live run. Only
            # KeyboardInterrupt and the like still pass, which is what a stop must do.
            except (Exception, SystemExit) as exc:
                say("supervisor: hold service raised %s (%s): the holds are left as they are and "
                    "the next tick tries again" % (type(exc).__name__, exc))
            next_service = time.time() + a.tick_s
        if proc is not None:
            try:
                return proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue
        if not pid_alive(pid):
            return None
        time.sleep(1)


def supervise_loop(a, path, sid, proc, pid, out, offset, start, t0):
    """The supervisor (D30): wait for the head's process with no API call, classify its stop,
    act — end, wait and resume, or one successor — and supervise whatever it started, in a
    loop. Exit 0 when the run ended or was handed over, 1 after successor-aborted. The wait
    ticks every --tick-s to service the record's open holds."""
    while True:
        rc = wait_head(a, path, proc, pid)
        if proc is not None:
            pid = proc.pid
        stopped_at = time.time()
        events, _ = read_record(path)
        cls, d = stop_class(events, start, out, offset, rc, transcript_for(sid) if sid else None)
        if cls == "unsucceeded":
            # C2 N4: the head's own successor call may still be on its way (the starter's wait)
            deadline = stopped_at + a.wait_s
            while time.time() < deadline:
                time.sleep(max(0.0, min(a.tick_s, deadline - time.time())))
                events, _ = read_record(path)
                cls, d = stop_class(events, start, out, offset, rc, None)
                if cls != "unsucceeded":
                    break
        before = previous_stop(events)
        append_record(path, event(a.run, "observation", phase="", what="head exited",
                                  exit_class=cls,
                                  note="session %s exit %s after %d s → %s (%s); output %s"
                                       % (sid, "unknown" if rc is None else rc,
                                          stopped_at - t0, cls, d["note"], out)))
        say("supervisor: session %s exit %s → %s (%s)"
            % (sid, "unknown" if rc is None else rc, cls, d["note"]))
        if cls in ("handed-over", "closed"):
            append_record(path, event(a.run, "observation", phase="", what="supervisor ended",
                                      note="%s: %s" % (cls, d["note"])))
            say("supervisor: %s — ended" % cls)
            return 0
        # The owner's stop outranks every fork below (register entry 2026-09-07). A marker on disk
        # when the head exits stands the supervisor down BEFORE any successor decision, whatever
        # the exit was classified as, a signalled head included. It sits under the two forks
        # above because neither decides anything: `closed` is this run's own close, which writes
        # this very marker, and `handed-over` already has its successor.
        marker = supervisor_stop_file(a.run)
        if os.path.exists(marker):
            on_limit, osrc, _ = run_on_limit(events, a.run)
            return stand_down(path, a.run, "stopped",
                              "a stop marker was on disk at the head's exit (%s): no successor "
                              "and no resume after a %s stop" % (marker, cls),
                              on_limit, osrc, time.time() - stopped_at)
        if cls == "classifier-missing":
            return abort(path, a.run, "classifier-missing", d["note"])
        # Two stops of the same fault end the loop, the successor cap being only the backstop:
        # `error` and `budget` in either order, and `completed` against itself — a head that
        # exits completed with neither a head-exit nor a run-close leaves nothing behind for
        # its successor to do differently, so the second such exit is a loop, not progress.
        if (cls in ("error", "budget") and before in ("error", "budget")) or \
                (cls == "completed" and before == "completed"):
            return abort(path, a.run, "repeat-stop", "two consecutive %s and %s stops: the "
                         "head does not get a third start on the same fault" % (before, cls))
        waited, source, watch = 0.0, "none: no wait after a %s stop" % cls, None
        if cls == "limit":
            on_limit, osrc, gpath = run_on_limit(events, a.run)
            if on_limit != "resume":   # the gate's default (D42): stand down, no wait
                append_record(path, event(a.run, "stop-condition", which="limit", lane="head",
                                          action="stand-down: on_limit stop", on_limit=on_limit,
                                          on_limit_src=osrc, grants_file=gpath,
                                          note=one_line(d["text"] or "")[:NOTE_CUT]))
                say("supervisor: limit — on_limit stop (%s): no wait, no resume" % osrc)
                return stand_down(path, a.run, "limit-stop",
                                  "on_limit stop (%s): the limit ends this run's supervision"
                                  % osrc, on_limit, osrc, 0.0)
            watch = StandDown(a.run, transcript_for(sid) if sid else None, on_limit, osrc)
            status, source, waited = wait_for_reset(a, path, start, d["text"], stopped_at,
                                                    watch)
            if status == "stood-down":
                return stand_down(path, a.run, watch.reason, watch.detail, on_limit, osrc,
                                  waited)
            if status == "closed":
                append_record(path, event(a.run, "observation", phase="", what="supervisor ended",
                                          note="closed during the reset wait"))
                say("supervisor: closed — ended")
                return 0
            if status in ("limit-model", "limit-unparsed"):
                # No wait can clear this stop, so no resume in place follows: the recovery is a
                # successor, whose premise check keys on a head-exit after this head's start
                # (register entry 2026-09-14 05:13). Written before successor-aborted.
                owe_limit_exit(a, path, sid, start, pid, stopped_at, status)
            if status == "limit-model":
                return abort(path, a.run, source,
                             "the stop text names a limit scoped to one model, not the "
                             "account, and states no reset time: a wait cannot clear it, "
                             "so the hand-off is the recovery and a successor needs "
                             "another model")
            if status == "limit-unparsed":
                return abort(path, a.run, "limit-unparsed",
                             "no reset time could be parsed from the stop text and --probe was "
                             "not passed (the probe is opt-in, owner ruling 2026-09-06)")
            if status != "ok":
                return 1
        events, _ = read_record(path)
        budget, bsrc = remainder(events, a, cls, start)
        if budget is None:
            return abort(path, a.run, "budget", bsrc)
        if cls == "unsucceeded":
            say("supervisor: the head-exit has no successor after %d s — starting one at $%.2f "
                "(%s)" % (a.wait_s, budget, bsrc))
            started = succeed_exit(a, path, budget, t0)
            if started is None:
                return 1
            proc, sid, out, offset, start = started
            continue
        m = head_context(sid, events, start)
        resumes = sum(1 for e in events
                      if e.get("event") == "head-resumed" and e.get("session_id") == sid)
        if cls in ("limit", "budget") and m.get("context") is not None and \
                resume_in_place(events, m, stopped_at) and resumes < RESUME_CAP:
            events, _ = read_record(path)
            if any(e.get("event") in ("head-resumed", "head-successor")
                   for e in events[start + 1:]):
                return abort(path, a.run, "duplicate-resume", "a head-resumed or head-successor "
                             "already follows this head's start: another supervisor got there "
                             "first")
            if watch is not None and watch.check():   # the last act before a start (D43)
                return stand_down(path, a.run, watch.reason, watch.detail, watch.on_limit,
                                  watch.src, waited)
            resumed = resume_head(a, path, sid, budget, bsrc, out, m, cls, waited, source,
                                  stopped_at)
            if resumed is not None:
                proc, out, offset, start = resumed
                continue
        band = {"limit": "limit", "error": "error"}.get(cls) or band_value(None, m)
        say("supervisor: successor path — context %s (%s), band %s, resumes %d, budget $%.2f "
            "(%s)" % (context_text(m), m.get("source"), band, resumes, budget, bsrc))
        started = successor_path(a, path, m, band, cls, budget, pid, t0, watch)
        if started == "stood-down":
            return stand_down(path, a.run, watch.reason, watch.detail, watch.on_limit,
                              watch.src, waited)
        if started is None:
            return 1
        proc, sid, out, offset, start = started


def cmd_starter(a):
    t0 = time.time()
    path = record_path(a.run)
    # No ancestor test here: during a normal hand-over the exiting head's own process is this
    # starter's ancestor until `successor` returns, so the test cannot tell a launcher's pid from
    # the head's. `successor` refuses a launcher-supplied one; a wait that outlives its bound
    # names the process instead.
    if not a.predecessor_pid and seed_predecessor(read_record(path)[0]):
        # A seed session never ran: no process and no transcript to outlive (register entry
        # 2026-09-12 20:0x), so the head starts at once.
        say("starter: %s pid %d starts at once: the predecessor is a seed session with no pid"
            % (now(), os.getpid()))
        gone, why = True, ""
    elif a.predecessor_pid:
        say("starter: %s pid %d waits for pid %d" % (now(), os.getpid(), a.predecessor_pid))
        gone = wait_dead(a.predecessor_pid, a.wait_s)
        why = "predecessor pid %d alive after %d s" % (a.predecessor_pid, a.wait_s)
        if not gone:
            age, row = process_age_s(a.predecessor_pid), ps_row(a.predecessor_pid)
            why += (" (%s, running %s): a long-lived process — a launcher's own, or an attended "
                    "conversation's — does not exit at the end of a reply; a seed pid must "
                    "belong to a process that exits within seconds"
                    % (row[2] if row else "command unknown",
                       "for an unknown time" if age is None else "%d s" % age))
    else:
        say("starter: %s pid %d waits for transcript silence" % (now(), os.getpid()))
        gone = wait_silent(a.transcript, SILENCE_PROXY_S, a.wait_s)
        why = "transcript %s still changing after %d s" % (a.transcript, a.wait_s)
    events, _ = read_record(path)
    reason, detail = start_guards(events, last_index(events, ("head-exit",)), gone, why)
    if reason:
        return abort(path, a.run, reason, detail)
    # One of the marker's three clearing sites: this starter is detached by cmd_successor and by
    # nothing else (the only `_starter` spawn in this file), so reaching here means a HEAD called
    # `successor`, and the head's own hand-over clears an earlier arming's marker. The supervisor's
    # own successor path does not come through here — it calls succeed_exit in process, under the
    # stand-down check at the head's exit.
    clear_stop_marker(a.run)
    started = start_head(a, path, a.budget, a.out, t0)
    if started is None:
        return 1
    proc, sid, out, offset, start = started
    return supervise_loop(a, path, sid, proc, None, out, offset, start, t0)


def cmd_supervise_internal(a):
    """The detached half of `supervise`: attach to a running head and run the loop."""
    t0 = time.time()
    path = record_path(a.run)
    events, _ = read_record(path)
    start = last_index(events, START_EVENTS)
    alive = pid_alive(a.pid)
    offset = out_size(a.out) if alive else 0   # a head already gone wrote its result before now
    a.budget = a.budget_usd
    say("supervisor: %s pid %d attached to head pid %d (%s) session %s · out %s" % (
        now(), os.getpid(), a.pid, "alive" if alive else "already gone", a.session, a.out))
    # No clear here: arming a supervisor is not one of the marker's three clearing sites
    # (resume-head, a successor called by a head, close). A run the owner stopped stays stopped
    # across a re-arming, and this supervisor stands down at the head's exit.
    return supervise_loop(a, path, a.session, None, a.pid, a.out, offset, start, t0)


def cmd_supervise(a):
    path = record_path(a.run)
    events = require_record(path)
    if a.stop:   # before any pid resolution: a stopped run has no live head (D43, C1 L8)
        marker = supervisor_stop_file(a.run)
        if a.dry_run:
            say("supervise: dry run · would write the stop marker %s" % marker)
            return 0
        write_atomic(marker, now() + "\n")
        append_record(path, event(a.run, "supervise", mode="stop-requested", marker=marker,
                                  pid=os.getpid()))
        say("supervise: stop marker written (%s) — a sleeping supervisor stands down at its "
            "next tick, at most %d s" % (marker, a.tick_s))
        return 0
    sid, sev = head_session(events)
    if not sid:
        die("no head session in the record: run-open first")
    pid, src = head_pid(a.pid)
    if pid is None:
        die("no harness ancestor to supervise (an attended head has no idle-exit); pass --pid N")
    if a.pid is not None and not pid_alive(pid):
        die("pid %d is not alive: a stopped run has no head to supervise; after a limit use "
            "resume-head or successor (D42; C2 L5)" % pid)
    if a.reset_at:
        parse_reset_at(a.reset_at, time.time())
    out, osrc = a.out, "--out"
    if not out and sev is not None and sev.get("event") == "head-successor" and sev.get("out"):
        out, osrc = sev["out"], "head-successor"
    if not out:
        hits = sorted(globmod.glob(os.path.join(store_root(), "spawn-records",
                                                "%s-head-*.out" % token(a.run, "run id"))),
                      key=os.path.getmtime)
        if hits:
            out, osrc = hits[-1], "newest .out"
    if not out:
        out, osrc = "none", "transcript-only"
    log = os.path.join(store_root(), "spawn-records", "%s-supervise.log" % a.run)
    cmd = [sys.executable, "-B", os.path.abspath(__file__), "_supervise", "--run", a.run,
           "--pid", str(pid), "--session", sid, "--out", out, "--harness-bin", a.harness_bin,
           "--max-wait-s", str(a.max_wait_s), "--probe-interval-s", str(a.probe_interval_s),
           "--tick-s", str(a.tick_s), "--wait-s", str(a.wait_s), "--effort", a.effort,
           "--beat-timeout-s", str(a.beat_timeout_s)]
    if a.probe:
        cmd += ["--probe"]   # never on its own: only when this caller opted in (2026-09-06)
    for flag, value in (("--reset-at", a.reset_at), ("--model", a.model),
                        ("--config-dir", a.config_dir), ("--handoff", a.handoff),
                        ("--meter-line", a.meter_line)):
        if value:
            cmd += [flag, value]
    if a.budget_usd is not None:
        cmd += ["--budget-usd", "%.2f" % a.budget_usd]
    if a.dry_run:
        say("supervise: dry run · pid %d (%s) session %s · out %s (%s) · would detach %s"
            % (pid, src, sid, out, osrc, " ".join(cmd[3:])))
        return 0
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "ab") as handle:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=handle, stderr=handle,
                                start_new_session=True, cwd=vault_root(),
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    append_record(path, event(a.run, "supervise", mode="attached", pid=pid, session_id=sid,
                              out=out, supervisor_pid=proc.pid, log=log, services_holds=True))
    say("supervise: pid %d session %s · out %s · detached pid %d" % (pid, sid, out, proc.pid))
    return 0


def cmd_watch(a):
    """`watch --run R` or `watch --session S`: hand the tty to watch.py beside this file (exec,
    so the keys work). `--session` is the attended-session view — one row per background job of
    that session, read from its transcript and the harness's job directory (A4)."""
    script = os.path.join(HERE, "watch.py")
    if not os.path.isfile(script):
        die("no watch.py beside handsoff.py at %s" % script)
    argv = ["--session", a.session] if a.session else ["--run", a.run]
    for flag, value in (("--refresh", a.refresh), ("--vault", a.vault)):
        if value is not None:
            argv += [flag, str(value)]
    for flag, on in (("--once", a.once), ("--plain", a.plain), ("--no-notify", a.no_notify)):
        if on:
            argv.append(flag)
    os.execv(sys.executable, [sys.executable, "-B", script] + argv)


def cmd_resume_head(a):
    """`resume-head` (D42's recovery; critic C2 M4): resume the record's last head session in
    place — armed, evented and supervised — the owner's command after a limit the run stood down
    on, instead of an unarmed hand-run `claude -p --resume`. Detaches at once, like `supervise`."""
    path = record_path(a.run)
    events = require_record(path)
    sid, sev = head_session(events)
    if not sid:
        die("no head session in the record: run-open first")
    out, osrc = a.out, "--out"
    if not out and sev is not None and sev.get("out"):
        out, osrc = sev["out"], sev.get("event")
    if not out:
        hits = sorted(globmod.glob(os.path.join(store_root(), "spawn-records",
                                                "%s-head-*.out" % token(a.run, "run id"))),
                      key=os.path.getmtime)
        if hits:
            out, osrc = hits[-1], "newest .out"
    if not out:
        out, osrc = next_out(a.run)[0], "fresh"
    log = os.path.join(store_root(), "spawn-records", "%s-supervise.log" % a.run)
    cmd = [sys.executable, "-B", os.path.abspath(__file__), "_resume-head", "--run", a.run,
           "--session", sid, "--out", out, "--harness-bin", a.harness_bin,
           "--max-wait-s", str(a.max_wait_s), "--probe-interval-s", str(a.probe_interval_s),
           "--tick-s", str(a.tick_s), "--wait-s", str(a.wait_s), "--effort", a.effort,
           "--beat-timeout-s", str(a.beat_timeout_s)]
    if a.probe:
        cmd += ["--probe"]
    for flag, value in (("--reset-at", a.reset_at), ("--model", a.model),
                        ("--config-dir", a.config_dir), ("--handoff", a.handoff),
                        ("--meter-line", a.meter_line)):
        if value:
            cmd += [flag, value]
    if a.budget_usd is not None:
        cmd += ["--budget-usd", "%.2f" % a.budget_usd]
    if a.dry_run:
        say("resume-head: dry run · session %s · out %s (%s) · would detach %s%s"
            % (sid, out, osrc, " ".join(cmd[3:]),
               " · would record observation pack-fresh" if a.pack_fresh else ""))
        open_console_if_dark(a.run, dry_run=True)
        return 0
    os.makedirs(os.path.dirname(log), exist_ok=True)
    # A by-hand resume-head is the owner at the desk: a window unless one is already alive,
    # opened here before the detach and logged to the supervise log (register entry 2026-09-09
    # 11:21); the detached half is told, so its first start opens nothing.
    open_console_if_dark(a.run, log=log)
    cmd += ["--viewer-opened"]
    with open(log, "ab") as handle:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=handle, stderr=handle,
                                start_new_session=True, cwd=vault_root(),
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if a.pack_fresh:
        record_pack_fresh(path, a.run, "resume-head")
    append_record(path, event(a.run, "supervise", mode="resume-head", session_id=sid, out=out,
                              supervisor_pid=proc.pid, log=log))
    say("resume-head: session %s · out %s (%s) · detached pid %d" % (sid, out, osrc, proc.pid))
    return 0


def cmd_resume_head_internal(a):
    """The detached half of `resume-head`: size the head, resume it in place, supervise it."""
    t0 = time.time()
    path = record_path(a.run)
    events, _ = read_record(path)
    start = last_index(events, START_EVENTS)
    a.budget = a.budget_usd
    budget, bsrc = remainder(events, a, "limit", start)
    if budget is None:
        return abort(path, a.run, "budget", bsrc)
    m = head_context(a.session, events, start)
    if m.get("context") is None:
        return abort(path, a.run, "resume-unsized", "the head's context cannot be sized (no "
                     "transcript, no gate event): start the successor from the hand-off instead")
    verdict, why, stop_cls, stopped_at = resume_guard(events, m, start)
    if verdict != "ok":
        return abort(path, a.run, verdict, why)
    clear_stop_marker(a.run)
    resumed = resume_head(a, path, a.session, budget, bsrc, a.out, m, stop_cls, 0.0,
                          "resume-head (by hand, after the reset)",
                          stopped_at if stopped_at is not None else time.time())
    if resumed is None:
        return 1
    proc, out, offset, start = resumed
    return supervise_loop(a, path, a.session, proc, None, out, offset, start, t0)


def cmd_grants(a):
    """Rewrite the run's grants file and run-<sid> pointer (C2 N7): for a head whose file is
    missing or wrong, since a second run-open is refused by design. A list the call does not
    name is carried from the file, and the shrink guard refuses a rewrite that would lose a
    write path the call does not re-issue (register entry 2026-09-12 21:3x). --network rewrites
    the network key, and without it the file's value is carried."""
    refuse_grants_file(a)
    path = record_path(a.run)
    events = require_record(path)
    sid, _ = head_session(events)
    if not sid:
        die("no head session in the record: run-open first")
    gpath = grants_path(a.run)
    on_limit, osrc = on_limit_choice(a, gpath)
    viewer, vsrc = viewer_choice(a, gpath)
    network, nsrc = network_choice(a, gpath)
    payload, sources, dropped, against = grants_plan(a, gpath, events, "grants")
    guard_shrink(a, "grants", dropped, against)
    ev = event(a.run, "grants", grants_file=gpath, grants=payload["grants"],
               writes=payload["writes"], session=sid, on_limit=on_limit, on_limit_src=osrc,
               viewer=viewer, viewer_src=vsrc, network=network, network_src=nsrc,
               grants_src=sources["grants"], writes_src=sources["writes"])
    if a.dry_run:
        say("grants: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        return 0
    write_grants(gpath, payload)
    write_pointer(a.run, sid)
    append_record(path, ev)
    say("grants: %s · %d grants (%s) · %d writes (%s) · on_limit %s (%s) · viewer %s (%s) · "
        "network %s (%s) · pointer run-%s"
        % (ev["grants_file"], len(payload["grants"]), sources["grants"], len(payload["writes"]),
           sources["writes"], on_limit, osrc, viewer, vsrc, network_shown(network), nsrc,
           sid[:8]))
    return 0


def read_pidfile(path):
    """(pid, end epoch) from a heartbeat pid file, (None, None) when absent or unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            parts = handle.read().split()
        return int(parts[0]), float(parts[1])
    except (OSError, ValueError, IndexError):
        return None, None


def cmd_heartbeat(a):
    path = record_path(a.run)
    require_record(path)
    pid_file, stop_file = heartbeat_files(a.run)
    if a.stop:
        if a.dry_run:
            say("heartbeat: dry run · would write the stop marker %s" % stop_file)
            return 0
        write_atomic(stop_file, now() + "\n")
        append_record(path, event(a.run, "heartbeat", action="stopped", pid=os.getpid(),
                                  minutes=None, note="--stop"))
        say("heartbeat: %s · stop marker written (%s)" % (a.run, stop_file))
        return 0
    if a.minutes <= 0:
        die("--minutes must be positive, got %r" % a.minutes)
    armed_pid, armed_end = read_pidfile(pid_file)
    if armed_pid and pid_alive(armed_pid):
        left = max(0.0, ((armed_end or time.time()) - time.time()) / 60.0)
        if not a.dry_run:
            append_record(path, event(a.run, "heartbeat", action="already-armed", pid=armed_pid,
                                      minutes=round(left, 2)))
        say("heartbeat: already armed (pid %d, %d min left)" % (armed_pid, math.ceil(left)))
        return 0
    parent = a.parent_pid if a.parent_pid is not None else os.getppid()
    end = time.time() + a.minutes * 60
    if a.dry_run:
        say("heartbeat: dry run · would arm %g min (until %s), parent pid %d, pid file %s"
            % (a.minutes, fmt_ts(end), parent, pid_file))
        return 0
    if os.path.exists(stop_file):
        os.remove(stop_file)   # a marker left by an earlier --stop or close, not this arming's
    write_atomic(pid_file, "%d %d\n" % (os.getpid(), end))
    append_record(path, event(a.run, "heartbeat", action="armed", minutes=a.minutes,
                              pid=os.getpid(), parent_pid=parent))

    def end_quietly(action, note):
        if os.path.exists(pid_file):
            os.remove(pid_file)
        append_record(path, event(a.run, "heartbeat", action=action, minutes=a.minutes,
                                  pid=os.getpid(), note=note))
        return 0

    while time.time() < end:
        if os.path.exists(stop_file):
            return end_quietly("stopped", "the stop marker appeared")
        if not pid_alive(parent):
            return end_quietly("orphaned", "parent pid %d is gone" % parent)
        time.sleep(max(0.0, min(a.tick_s, end - time.time())))
    if os.path.exists(pid_file):
        os.remove(pid_file)
    append_record(path, event(a.run, "heartbeat", action="beat", minutes=a.minutes,
                              pid=os.getpid()))
    say("heartbeat: %s · %g min · the cache is refreshed by this re-invocation; re-arm if "
        "still idle" % (a.run, a.minutes))
    return 0


def open_wait(events):
    """Index of the open limit stop-condition (no observation ended it), else -1."""
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("event") == "observation" and ev.get("what") == "wait-reset ended":
            return -1
        if ev.get("event") == "stop-condition" and str(ev.get("which") or "").startswith("limit"):
            return i   # every limit kind (limit, limit-model, limit-unparsed) is an open wait, 2026-09-16
    return -1


def probe(binary, config_dir):
    """One haiku call under the same login (D28): (ok, what). A limited account answers with
    the limit text at no cost; a config directory is optional and unused by default."""
    cmd = [binary, "-p", "--model", "haiku", "--max-budget-usd", "%.2f" % PROBE_BUDGET_USD,
           "--output-format", "json"]
    env = dict(os.environ)
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = config_dir
    try:
        proc = subprocess.run(cmd, input="Reply with the single word OK.", capture_output=True,
                              text=True, timeout=PROBE_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        return False, "probe timed out after %d s" % PROBE_TIMEOUT_S
    except OSError as exc:
        return False, "probe could not start: %s" % exc
    result = {}
    if proc.stdout.strip():
        try:
            result = json.loads(proc.stdout.strip().splitlines()[-1])
        except ValueError:
            result = {}
    if not isinstance(result, dict):
        result = {}
    ok = (proc.returncode == 0 and not result.get("is_error")
          and result.get("subtype", "success") == "success")
    return ok, "exit %d · subtype %s · cost $%s" % (
        proc.returncode, result.get("subtype", "?"), result.get("total_cost_usd", "?"))


def cmd_wait_reset(a):
    path = record_path(a.run)
    events = require_record(path)
    text = a.stop_text if a.stop_text is not None else (
        read_text(a.stop_file, "--stop-file") if a.stop_file else "")
    now_ts = time.time()
    target, source = parse_reset_text(text, now_ts) if text else (None, None)
    if target is None and a.reset_at:
        target, source = parse_reset_at(a.reset_at, now_ts), "--reset-at %s" % a.reset_at
    scope = model_limit(text) if target is None else None
    if scope is not None:
        if a.dry_run:
            say("wait-reset: dry run · a limit scoped to one model (%s) and no reset "
                "time · would record stop-condition limit-model and end with the "
                "hand-off as the recovery" % (scope or "scope unstated"))
            return 0
        append_record(path, event(
            a.run, "stop-condition", which="limit-model", lane=a.lane,
            model=scope or "unstated",
            action="the stop text names a limit scoped to one model and states no reset time: "
                   "neither a wait nor a probe can clear it (a probe answers for "
                   "another model), so the recovery is a successor on a model the "
                   "account can still run",
            note=one_line(text)[:NOTE_CUT]))
        say("wait-reset: the %s limit is exhausted and the stop text states no reset "
            "time · stop-condition limit-model recorded · the hand-off is the recovery"
            % (scope or "current model"))
        return 7
    if target is None and not a.probe:
        # Opt-in probe (owner ruling 2026-09-06): with no reset time to sleep to there is no
        # wait to run, so the stop condition is recorded and the hand-off is the recovery.
        if a.dry_run:
            say("wait-reset: dry run · no reset time, no --reset-at and no --probe · would "
                "record stop-condition limit-unparsed and end with the hand-off as the recovery")
            return 0
        append_record(path, event(
            a.run, "stop-condition", which="limit-unparsed", lane=a.lane,
            action="no reset time in the stop text, no --reset-at and no --probe (the probe is "
                   "opt-in, owner ruling 2026-09-06): the hand-off is the recovery",
            note=one_line(text)[:NOTE_CUT]))
        say("wait-reset: no reset time could be parsed and --probe was not passed · "
            "stop-condition limit-unparsed recorded · the hand-off is the recovery")
        return 7
    oi = open_wait(events)
    started = parse_ts(events[oi]["ts"]) if oi >= 0 else None
    if started is None:
        started = now_ts
    plan = ("until %s (%s)" % (fmt_ts(target), source)) if target is not None else (
        "probe every %d s under %s" % (
            a.probe_interval_s,
            "CLAUDE_CONFIG_DIR=%s" % a.config_dir if a.config_dir else "the same login"))
    if a.dry_run:
        say("wait-reset: dry run · %s · %s" % (
            plan, "%d s to go" % (target - now_ts) if target is not None else "no target"))
        return 0
    if oi < 0:
        append_record(path, event(a.run, "stop-condition", which="limit", lane=a.lane,
                                  action="wait-reset " + plan, note=one_line(text)[:300]))
    block_end = now_ts + a.max_block_s
    say("wait-reset: %s · waited %d s so far · this call blocks at most %d s"
        % (plan, now_ts - started, a.max_block_s))

    def ended(what, code):
        append_record(path, event(a.run, "observation", phase="", what="wait-reset ended",
                                  note=what))
        say("wait-reset: " + what)
        return code

    if target is not None:
        if target - started > a.max_wait_s:
            return ended("gave up: reset at %s is %d s after the wait began, past --max-wait-s %d"
                         % (fmt_ts(target), target - started, a.max_wait_s), 7)
        if target > block_end:
            time.sleep(max(0.0, block_end - time.time()))
            say("still-running %d" % max(0, round(target - time.time())))
            return 8
        time.sleep(max(0.0, target - time.time()))
        return ended("reset reached at %s after %d s" % (fmt_ts(target), time.time() - started), 0)
    last_probe = None
    for ev in (events[oi + 1:] if oi >= 0 else []):
        if ev.get("event") == "observation" and ev.get("what") == "wait-reset probe":
            last_probe = parse_ts(ev.get("ts"))
    while True:
        elapsed = time.time() - started
        if elapsed > a.max_wait_s:
            return ended("gave up after %d s of probing (--max-wait-s %d)"
                         % (elapsed, a.max_wait_s), 7)
        due = (last_probe + a.probe_interval_s) if last_probe else time.time()
        if due > block_end:
            time.sleep(max(0.0, block_end - time.time()))
            say("still-running %d" % max(0, round(a.max_wait_s - (time.time() - started))))
            return 8
        time.sleep(max(0.0, due - time.time()))
        ok, what = probe(a.harness_bin, a.config_dir)
        last_probe = time.time()
        append_record(path, event(a.run, "observation", phase="", what="wait-reset probe",
                                  note=what))
        if ok:
            return ended("probe succeeded after %d s: %s" % (time.time() - started, what), 0)


def report_stops_text(events):
    """The warnings bullet's text: every head limit stop on the record (a stop-condition whose
    `which` opens `limit`) with the head-resumed that followed it and the minutes between, and
    every lane closed `limit`; each count stated, so none reads as searched-and-empty."""
    heads = []
    for i, ev in enumerate(events):
        if ev.get("event") != "stop-condition" or not str(ev.get("which") or "").startswith("limit"):
            continue
        who = ev.get("lane") or "head"
        resumed = next((x for x in events[i + 1:] if x.get("event") == "head-resumed"), None)
        t0 = parse_ts(ev.get("ts"))
        t1 = parse_ts(resumed.get("ts")) if resumed is not None else None
        if resumed is None:
            heads.append("%s at %s (%s), no head-resumed after it" % (who, ev.get("ts", "no ts"),
                                                                     ev.get("which")))
        elif t0 is not None and t1 is not None and t1 >= t0:
            heads.append("%s at %s (%s) → head-resumed %s, %.1f min" % (
                who, ev.get("ts"), ev.get("which"), resumed.get("ts"), (t1 - t0) / 60.0))
        else:
            heads.append("%s at %s (%s) → head-resumed %s" % (
                who, ev.get("ts", "no ts"), ev.get("which"), resumed.get("ts", "no ts")))
    lanes = ["%s at %s" % (ev.get("lane") or "unnamed lane", ev.get("ts", "no ts"))
             for ev in events if ev.get("event") == "lane-closed" and ev.get("exit_class") == "limit"]
    return "%d limit stop(s)%s · %d lane(s) closed limit%s · read from the record at the close" % (
        len(heads), ": " + "; ".join(heads) if heads else "", len(lanes),
        ": " + "; ".join(lanes) if lanes else "")


def patch_report(text, events, meter):
    """(text, changed keys, problems) for the run report page (register entry 2026-09-10 17:43).
    One
    bullet under the page's first `## Spend…` heading carries the close's billed line and one
    under its first `## Warnings…` heading names every limit stop on the record; each is added
    after the section's last line, or replaced where an earlier close wrote it, and not a word
    of the head's own prose is rewritten. A section the page lacks is a problem named, never a
    guess; a bullet already current is left as it is."""
    lines = text.split("\n")
    changed, problems = [], []
    for heading, key, value in ((REPORT_SPEND_HEADING, REPORT_METER_KEY, meter),
                                (REPORT_WARNINGS_HEADING, REPORT_STOPS_KEY,
                                 report_stops_text(events)),
                                (REPORT_WARNINGS_HEADING, REPORT_HARDSTOPS_KEY,
                                 report_hardstops_text(events))):
        i = heading_index(lines, heading)
        if i < 0:
            problems.append("no '## %s…' section" % heading)
            continue
        bullet = "- **%s:** %s" % (key, one_line(str(value)))
        end = section_end(lines, i)
        prefix = "- **%s:**" % key
        found = next((j for j in range(i + 1, end) if lines[j].startswith(prefix)), None)
        if found is not None:
            if lines[found] == bullet:
                continue
            lines[found] = bullet
        else:
            j = end
            while j - 1 > i and not lines[j - 1].strip():
                j -= 1
            block = [bullet]
            if not lines[j - 1].lstrip().startswith("- "):
                block = [""] + block        # a list after prose or the heading needs a blank line
            if j < len(lines) and lines[j].strip():
                block = block + [""]        # and the next heading keeps its blank line
            lines[j:j] = block
        changed.append(key)
    return "\n".join(lines), changed, problems


def plain_totals(events):
    """(lane names, counts by exit class, spend, the spend's source) for a record with no
    `run-open`. Every figure is read from the lane events alone, since they are the whole
    record: the classes come from `lane-closed.exit_class`, the spend from those events'
    `total_cost_usd`, and a lane opened but never closed is counted under `open`. Costs are
    summed by reading each event, never by a pattern over the file."""
    names, closed_names = set(), set()
    by_exit, spend, priced, unpriced = {}, 0.0, 0, 0
    for e in events:
        kind, lane = e.get("event"), e.get("lane")
        if kind not in ("lane-open", "lane-resumed", "lane-closed") or lane is None:
            continue
        names.add(str(lane))
        if kind != "lane-closed":
            continue
        closed_names.add(str(lane))
        cls = str(e.get("exit_class") or "unstated")
        by_exit[cls] = by_exit.get(cls, 0) + 1
        cost = e.get("total_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            spend += float(cost)
            priced += 1
        else:
            unpriced += 1
    still_open = len(names - closed_names)
    if still_open:
        by_exit["open"] = by_exit.get("open", 0) + still_open
    src = "sum of %d lane-closed total_cost_usd" % priced
    if unpriced:
        src += "; %d lane-closed carried no cost and are unpriced" % unpriced
    return sorted(names), by_exit, round(spend, 2), src


def close_plain(a, path, events):
    """`close` on the plain-lane-run shape (the register entry of 2026-09-06, widened
    2026-09-07): the `run-close` is written from the lane events alone.

    No head meter — the record names no head session to meter; no hand-off rewrite — no
    `run-open` names a pack; no hand-off row anywhere; and no commit and no push, since those
    write the vault under a head's grant and this record carries no head. The event says its
    own shape, so the console and the waste table can tell it from a hands-off close. The
    heartbeat and supervisor markers are not written either: a plain lane run arms neither."""
    if getattr(a, "report", None) is not None:
        die("a plain lane run's close patches no run report (--report was given): the record has "
            "no run-open, so no head wrote one; nothing written")
    if a.commit is not None or a.push:
        die("a plain lane run's close never commits and never pushes (%s was given): the record "
            "has no run-open, so no head's grant stands behind a vault write; nothing written"
            % ("--commit" if a.commit is not None else "--push"))
    names, by_exit, spend, src = plain_totals(events)
    tally = " · ".join("%s %d" % (k, n) for k, n in sorted(by_exit.items())) or "none"
    decisions, devents, drows = decision_count(events)
    ev = event(a.run, "run-close", shape=PLAIN_SHAPE, lanes=len(names), lanes_by_exit=by_exit,
               spend_usd=spend, spend_src=src, decisions_on_owner_behalf=decisions,
               decisions_src="%d decision event(s) + %d ledger observation(s)" % (devents, drows),
               meter="none: a plain lane run names no head session to meter",
               items=a.items, register=a.register, log=a.log, lint=a.lint)
    if a.dry_run:
        say("close: dry run · plain lane run (no run-open) · %s"
            % json.dumps(ev, ensure_ascii=False))
        say("close: lanes %d (%s) · spend $%.2f (%s) · would write no hand-off row, no commit, "
            "no push" % (len(names), tally, spend, src))
        return 0
    ev["holds_ended"] = end_open_holds(path, a.run, events, "close")
    append_record(path, ev)
    say("close: %s · plain lane run (no run-open) · lanes %d (%s) · spend $%.2f (%s) · "
        "decisions %d · no hand-off row, no commit, no push"
        % (a.run, len(names), tally, spend, src, decisions))
    return 0


def cmd_close(a):
    path = record_path(a.run)
    events = read_existing_record(path)
    held = decisions_hold(a, path, events, "close")   # the decisions channel (2026-09-13 03:53)
    if held is not None:
        return held
    if is_plain_run(events):
        return close_plain(a, path, events)
    ro = run_open(events)
    ho = handoff_of(events, a.handoff)
    meter = meter_line(events, a.run, a.meter_line)
    report = None
    if a.report is not None:
        report = os.path.realpath(os.path.expanduser(a.report))
        if not os.path.isfile(report):
            die("--report %s is not a file: the close re-reads the run report written before it, "
                "so the page must exist (register entry 2026-09-10 17:43); nothing written"
                % a.report)
    per_item, prev = [], None
    for g in events:
        if g.get("event") != "gate" or not g.get("metered"):
            continue
        item = {"item": g.get("item"), "context": g.get("context"), "percent": g.get("percent")}
        if isinstance(g.get("context"), int):
            if prev is not None:
                item["delta"] = g["context"] - prev
            prev = g["context"]
        per_item.append(item)
    lanes = sorted({str(e.get("lane")) for e in events
                    if e.get("event") == "lane-open" and e.get("lane") is not None})
    decisions, devents, drows = decision_count(events)
    tally = billed_field(meter, r"\(reasons: (.*?)\) · ", str) or "n/a"
    lines = read_text(ho, "hand-off").split("\n")
    # The run's spend at the close (register entries 2026-09-14): the session line stays what
    # the log entries quote, and the run figure is its own field and line beside it.
    envelope = envelope_of(events)[0]
    spend = run_spend(events, a.run, path, session_line=meter, write_cache=not a.dry_run)
    ev = event(a.run, "run-close", items=a.items, lanes=len(lanes), reason_tally=tally,
               decisions_on_owner_behalf=decisions,
               decisions_src="%d decision event(s) + %d ledger observation(s)" % (devents, drows),
               register=a.register, log=a.log,
               trace="%d rows under '## Trace' in %s" % (table_rows(lines, "Trace"), ho),
               lint=a.lint, meter=meter,
               run_spend_usd=spend["usd"] if spend["measured"] else None,
               run_spend_floor=spend["floor"], run_spend_src=spend["src"])
    if a.parity is not None:
        ev["parity"] = a.parity
    if per_item:
        ev["head_context_per_item"] = per_item
    refreshed = refresh_figures(lines, ro, meter, run_text=run_spend_short(spend, envelope))
    report_text, report_changed, report_problems = None, [], []
    if report is not None:
        # The close's re-read (register entry 2026-09-10 17:43): the record as it stands at the
        # close, after the head wrote the report, and this close's own meter line.
        report_text, report_changed, report_problems = patch_report(
            read_text(report, "run report"), events, meter)
        ev["report"] = report
        ev["report_patched"] = report_changed
        if report_problems:
            ev["report_problems"] = report_problems
    if a.dry_run:
        say("close: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        if report is not None:
            say("report: dry run · would patch %s (%s)%s" % (
                report, ", ".join(report_changed) or "nothing: already current",
                " · NOT patched: %s" % "; ".join(report_problems) if report_problems else ""))
        return 0
    if refreshed:
        write_atomic(ho, "\n".join(lines))
    if report is not None and report_changed:
        write_atomic(report, report_text)   # before the commit, so the checkpoint carries it
    if a.commit is not None:
        ev["commit"] = checkpoint_commit(vault_root(), a.commit)
    if a.push:
        ev["push"] = push(vault_root())
    ev["holds_ended"] = end_open_holds(path, a.run, events, "close")   # every open hold ends first
    append_record(path, ev)
    try:
        write_atomic(heartbeat_files(a.run)[1], now() + "\n")   # an armed heartbeat ends (D32)
        write_atomic(supervisor_stop_file(a.run), now() + "\n")  # a sleeping supervisor ends (D43)
    except OSError as exc:
        note("heartbeat stop marker not written: %s" % exc)
    say("close: %s · lanes %d · decisions %d · gates %d%s%s%s" % (
        a.run, len(lanes), decisions, len(per_item),
        " · commit %s" % ev["commit"] if "commit" in ev else "",
        " · push %s" % ev["push"] if "push" in ev else "",
        "" if refreshed else " · morning report NOT refreshed (section missing)"))
    say("meter: %s" % meter)
    say("run spend: %s" % run_spend_line(spend, envelope))
    if report is not None:
        say("report: %s · %s%s" % (
            report, "patched %s" % ", ".join(report_changed) if report_changed
            else "already current, not rewritten",
            " · NOT patched: %s" % "; ".join(report_problems) if report_problems else ""))
        if report_problems:
            return 3
    return 0


# ----------------------------------------------------------------- the waste table ---------

MISSING = object()   # the field is not on the event at all: `field absent`, never 0

# Kind assignment is mechanical (design D36; the reflect skill's Step 2b): a lost output is
# real, an output bought too dearly is arguable, a cost of the chosen shape is structural.
BOUNDARY_FIELDS = (
    ("idle_min", "idle minutes", "real", "min"),
    ("over_cap_reports", "reports the wrapper cut", "arguable", "count"),
    ("denials", "lane tool denials", "arguable", "count"),
    ("respawn_cost_usd", "lost-lane cost re-spawned", "real", "usd"),
    ("rewrites", "rewrites after a lapsed cache", "structural", "count"),
)
# Fields a boundary carries from 2026-09-13, each rendered only on a boundary that has the key:
# a boundary written before them gets no such row rather than a `field absent` one, since the
# field did not exist then. Kinds follow the precedents above: a denial is arguable, as the
# lanes' denials are; a limit cut is a cost of the chosen shape (the limits ruling), as the
# limit-wait row is.
LATER_BOUNDARY_FIELDS = (
    ("head_denials", "head fence denials", "arguable", "count"),
    ("limit_cut_resumed_usd", "first attempts of limit-cut lanes later resumed", "structural",
     "usd"),
)
TABLE_HEAD = ("| Item | ≈ $ or idle min | Kind | Fix and where it lands |", "|---|---|---|---|")
LEGEND = ("Kinds are mechanical, never judged here: idle minutes and lost lanes are real; "
          "over-cap reports and denials are arguable; rewrites and the orientation cost are "
          "structural. Rows marked `billed`, `context` and `control` are Step 2b's other "
          "requirements and carry no waste kind. Field meanings (2026-09-06): idle minutes are "
          "head idleness — the time in the boundary's span when no lane was running and the "
          "head made no call, a gap counting only above %d s — read from the head's transcript "
          "(idle_src transcript) or, when it is unavailable, from the record alone as silence "
          "after each lane close (idle_src record, an overstatement under parallel lanes); the "
          "lost-lane cost sums lanes closed other than `completed` and not resumed afterwards; "
          "rewrites are the change since the same head's previous boundary, a head's first "
          "boundary keeping the billed line's cumulative figure. A boundary written before "
          "these meanings is quoted as recorded and its source cell says so. Field meanings "
          "(T8): the preview row carries the CUT TAIL alone — omitted preview words; legacy "
          "records without display fields use their historical %d-word default. Convert at %s "
          "tokens per word, set by judgement, unmeasured, and charge the model's output rate "
          "from prices.json. A whole report contributes nothing; a lane whose model the "
          "record does not name is counted in words and left unpriced. The whole-run rows meter "
          "each head over the RUN's window (run-open to run-close, else the record's last "
          "event), so a session shared with attended work is not counted whole against this "
          "run; where that meter gives no figure the row falls back to the later of the head's "
          "last boundary billed line and its head-exit spend, and says which. A recorded limit "
          "wait (stop-condition to head-resumed) has a structural row of its own, and an idle "
          "row whose span covers one says how many of its minutes it holds. A `soft-cap` cell "
          "is a lane billed over its soft line (`lane-closed.soft_exceeded`; `soft_src` says "
          "whether the line was the class's completed maximum plus its headroom or the head's "
          "own --expect-usd): the line is logged, never a stop, and the head ledgers it at the "
          "lane's close. Field meanings (2026-09-13): the tool denials row counts the LANES' "
          "tool denials (the wrappers' counts on lane-closed), and the head fence denials row, "
          "beside it and never added to it, counts the head fence's deny lines in events.log "
          "for the span's head sessions; a lane closed with no cost (a lane killed with its "
          "head) is billed from its own transcript by the meter and says `metered "
          "(transcript)`, one that cannot be metered leaves the lost-lane figure `unmeasured`, "
          "never $0.00, and a plan-usage (Codex) lane is counted, never priced; the first "
          "attempts of lanes closed `limit` and resumed afterwards, which the lost-lane cost "
          "excludes, take a structural row of their own; the run total reads a billed line "
          "carried by hand as `session ≈ <n>` or `session USD <n>` as well as the meter's "
          "`session $<n>`, and names the form it read. The two rows added that day appear only "
          "on boundaries that carry their fields." % (
              IDLE_GAP_S, REPORT_CAP_WORDS, WORDS_TO_TOKENS))
# What each of the three re-defined fields means on a given boundary, read off the marker
# fields the boundary command writes beside them; a boundary written before the rule has none
# and is labelled as recorded, never re-read under the new meaning.
FIELD_MEANINGS = {
    "idle_min": lambda ev: {
        "transcript": "head idle: no lane running and no head call, gaps above %d s, the "
                      "head's calls from its transcript (idle_src transcript)" % IDLE_GAP_S,
        "record": "record-only fallback: silence after each lane close until the head's next "
                  "recorded act, summed per close, an overstatement under parallel lanes "
                  "(idle_src record)"}.get(
        ev.get("idle_src"), "as recorded: per-lane silence after each close, a boundary written "
                            "before the head-idle rule (no idle_src)"),
    "respawn_cost_usd": lambda ev: (
        ("lanes closed other than completed and not resumed afterwards (%d resumed lane(s) "
         "excluded)" % ev["respawn_excluded"] if isinstance(ev.get("respawn_excluded"), int)
         else "as recorded: every lane closed other than completed, a boundary written before "
              "the resume exclusion")
        + (" · %s" % ev["respawn_src"] if isinstance(ev.get("respawn_src"), str) else "")),
    "head_denials": lambda ev: "the head fence's deny lines in events.log for the span (%s)" % (
        ev.get("head_denials_src") or "no source recorded"),
    "limit_cut_resumed_usd": lambda ev: (
        "the first attempts of %s lane(s) closed limit and resumed afterwards, excluded from "
        "respawn_cost_usd (%s)" % (ev.get("limit_cut_resumed", "?"),
                                   ev.get("limit_cut_src") or "no source recorded")),
    "rewrites": lambda ev: (
        "change since %s (this head's billed line cumulative: %d)"
        % (ev.get("rewrites_since") or "unstated", ev["rewrites_total"])
        if isinstance(ev.get("rewrites_total"), int) and not isinstance(ev.get("rewrites_total"), bool)
        else "as recorded: the billed line's session-cumulative figure, a boundary written "
             "before the delta rule"),
}
FIX_OPEN = ("unrouted: the reflector lane proposes one of a plan phase, a `known-issues` entry, "
            "an IDEAS todo or `accepted`; the owner approves")
FIX_NONE = "no fix: this row carries no measured cost"
FIX_NA = "n/a"


def figure(value, unit, source):
    """(cell, is a finding): a figure with its derivation beside it, `field absent` where the
    event has no such key, `unmeasured` where the key is there and null. A missing field and a
    measured zero are different claims (Step 2b), and a bare number is never written."""
    if value is MISSING:
        return "field absent", False
    if value is None:
        return "unmeasured (the field is null) · %s" % source, False
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "%s (as recorded) · %s" % (cell(value), source), False
    if unit == "usd":
        text = "$%.2f" % float(value)
    elif unit == "min":
        text = "%s min" % value
    else:
        text = format(value, ",") if isinstance(value, int) else str(value)
    return "%s · %s" % (text, source), float(value) > 0


def boundary_label(ev):
    return "%s → %s at %s" % (ev.get("from", "?"), ev.get("to", "?"), ev.get("ts", "no ts"))


def session_at(events, index):
    """The head session in force at an event: the last run-open, run-resume or head-successor
    before it, since a phase-boundary names no session of its own."""
    i = last_index(events[:index], SESSION_EVENTS)
    if i < 0:
        return None
    ev = events[i]
    sid = ev.get("session_id") if ev.get("event") == "head-successor" else ev.get("session")
    return sid if isinstance(sid, str) else None


def output_rate(model):
    """(rate in $ per MTok, family) for a model id, read from prices.json beside this script by
    that file's own matching rule — the id lower-cased, the first family name it contains in the
    file's stated order winning. (None, reason) where the file, the id or the family is missing:
    the row then carries the words alone and says it is unpriced, never a guessed rate."""
    path = os.path.join(HERE, "prices.json")
    if not isinstance(model, str) or not model.strip():
        return None, "the record names no model for this lane"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            table = json.load(handle)
    except (OSError, ValueError) as exc:
        return None, "prices.json unreadable (%s)" % exc
    order = table.get("family_order") or list(table.get("families") or {})
    for family in order:
        if family in model.lower():
            rate = (table.get("families") or {}).get(family, {}).get("output")
            if isinstance(rate, (int, float)) and not isinstance(rate, bool):
                return float(rate), family
            return None, "prices.json carries no output rate for %s" % family
    return None, "the model %s matches no price family" % one_line(model)[:60]


def lane_model(events, index, close):
    """The model of the lane a lane-closed event names: the last lane-open for the same lane
    before the close (the wrapper records the model there, not on the close), matched on the
    lane session id too when both events carry one. None when no lane-open names one."""
    for ev in reversed(events[:index]):
        if ev.get("event") != "lane-open" or ev.get("lane") != close.get("lane"):
            continue
        a, b = ev.get("session_id"), close.get("session_id")
        if a and b and a != b:
            continue
        return ev.get("model")
    return None


def cut_tail_rows(events, lo, hi):
    """[(lane, words cut, cost or None, note)] for every lane-closed between the event indices lo
    (exclusive) and hi (inclusive) whose report the wrapper cut: the CUT TAIL alone — cut_words(),
    at WORDS_TO_TOKENS tokens per word, charged at the lane's model's output rate — and never the
    lane's whole cost (T8). A report shown whole contributes nothing."""
    found = []
    for i in range(max(0, lo + 1), min(hi + 1, len(events))):
        ev = events[i]
        if ev.get("event") != "lane-closed":
            continue
        over = cut_words(ev, ev.get("report_words"))
        if over <= 0:
            continue
        model = lane_model(events, i, ev)
        if is_plan_lane(events, i, ev):
            found.append((ev.get("lane") or "unnamed lane", over, None,
                          "plan usage: a Codex lane is counted in words, never priced"))
            continue
        rate, why = output_rate(model)
        if rate is None:
            found.append((ev.get("lane") or "unnamed lane", over, None, "unpriced: %s" % why))
            continue
        cost = over * WORDS_TO_TOKENS / 1000000.0 * rate
        found.append((ev.get("lane") or "unnamed lane", over, cost,
                      "%s output $%.2f/MTok" % (why, rate)))
    return found


def cut_tail_text(found):
    """The over-cap row's cut-tail cell: the priced tail with its derivation, or the statement
    that the wrapper cut no report in the span."""
    if not found:
        return "cut tail $0.00 · the wrapper cut no report in this span"
    priced = [c for _, _, c, _ in found if c is not None]
    total = ("$%.2f" % sum(priced)) if priced else "unpriced"
    parts = ["%s %d words over" % (lane, over) + (
        " = $%.4f (%s)" % (cost, note) if cost is not None else " (%s)" % note)
        for lane, over, cost, note in found]
    return ("cut tail %s%s · the tail alone (the words cut), never the lane's whole cost: "
            "%s · %s tokens per word, set by judgement, unmeasured" % (
                total, "" if len(priced) == len(found) else " over the priced tail(s)",
                "; ".join(parts), WORDS_TO_TOKENS))


def limit_waits(events):
    """[(stop-condition, head-resumed, minutes)] for every recorded limit stop the record shows
    a head resumed from: the span between the two events. The limits ruling makes that wait a
    cost of the chosen shape, so the table gives it a structural row of its own rather than
    leaving it inside idle_min's real class (register entry 2026-09-06)."""
    found = []
    for i, ev in enumerate(events):
        if ev.get("event") != "stop-condition":
            continue
        resumed = next((x for x in events[i + 1:] if x.get("event") == "head-resumed"), None)
        if resumed is None:
            continue
        t0, t1 = parse_ts(ev.get("ts")), parse_ts(resumed.get("ts"))
        if t0 is None or t1 is None or t1 < t0:
            continue
        found.append((ev, resumed, (t1 - t0) / 60.0))
    return found


def limit_wait_rows(events):
    """One structural row per recorded limit wait; none where the record holds no such pair."""
    rows = []
    for stop, resumed, minutes in limit_waits(events):
        rows.append(("limit wait · %s → head-resumed at %s"
                     % (stop.get("which", "stop-condition"), resumed.get("ts", "no ts")),
                     "%.1f min · stop-condition at %s to head-resumed at %s · a cost of the "
                     "chosen shape (the limits ruling), not head idleness: a boundary whose "
                     "span covers it counts the same minutes under idle_min"
                     % (minutes, stop.get("ts", "no ts"), resumed.get("ts", "no ts")),
                     "structural", FIX_NONE))
    return rows


def overlap_min(waits, t0, t1):
    """The recorded limit-wait minutes inside a boundary's span, 0.0 when none overlap."""
    if t0 is None or t1 is None:
        return 0.0
    total = 0.0
    for stop, resumed, _ in waits:
        a, b = parse_ts(stop.get("ts")), parse_ts(resumed.get("ts"))
        if a is None or b is None:
            continue
        total += max(0.0, min(b, t1) - max(a, t0))
    return total / 60.0


def field_rows(events):
    """One row per waste field per phase-boundary event, each naming its event and, for the
    three fields re-defined on 2026-09-06, what the figure means on that boundary. The over-cap
    row carries the cut tail's price (T8) and an idle row whose span covers a recorded limit
    wait says how many of its minutes that wait holds (register entry 2026-09-06)."""
    rows = []
    waits = limit_waits(events)
    previous = -1
    for i, ev in enumerate(events):
        if ev.get("event") != "phase-boundary":
            continue
        label = boundary_label(ev)
        t0 = parse_ts(events[previous].get("ts")) if 0 <= previous < len(events) else \
            parse_ts(run_open(events).get("ts"))
        waited = overlap_min(waits, t0, parse_ts(ev.get("ts")))
        for key, what, kind, unit in BOUNDARY_FIELDS:
            meaning = FIELD_MEANINGS[key](ev) if key in FIELD_MEANINGS else None
            source = "phase-boundary.%s · %s%s" % (key, "%s · " % meaning if meaning else "",
                                                   label)
            fig, finding = figure(ev.get(key, MISSING), unit, source)
            measured = ev.get(key, MISSING) is not MISSING and ev.get(key) is not None
            if key == "over_cap_reports" and measured:
                fig = "%s · %s" % (fig, cut_tail_text(cut_tail_rows(events, previous, i)))
            if key == "idle_min" and measured and waited > 0:
                fig = ("%s · of which %.1f min is a recorded limit wait (stop-condition → "
                       "head-resumed), structural rather than real" % (fig, waited))
            rows.append(("%s · %s" % (what, label), fig, kind,
                         FIX_OPEN if finding else FIX_NONE))
        for key, what, kind, unit in LATER_BOUNDARY_FIELDS:
            if key not in ev:
                continue
            source = "phase-boundary.%s · %s · %s" % (key, FIELD_MEANINGS[key](ev), label)
            fig, finding = figure(ev.get(key), unit, source)
            rows.append(("%s · %s" % (what, label), fig, kind,
                         FIX_OPEN if finding else FIX_NONE))
        previous = i
    return rows


# The run total's reader (register entry 2026-09-09 15:43): a boundary's billed line is the
# meter's `session $<n>`, or a line the head carried by hand after a meter failure, written
# `session ≈ <n>` or `session USD <n>`; all three are read and the row names the form. The
# envelope's own reader, session_spent, keeps the meter's literal form.
SESSION_FIGURE_RE = re.compile(r"\bsession (\$|≈ ?\$?|USD ?\$?)([0-9][0-9,]*(?:\.[0-9]+)?)")


def billed_session(line):
    """(dollars, form) for a billed line's session figure in any of the three forms, else
    (None, None): `session ≈ n/a`, a bare `session` and a session id are no figure."""
    m = SESSION_FIGURE_RE.search(line or "")
    if not m:
        return None, None
    try:
        value = float(m.group(2).replace(",", ""))
    except ValueError:
        return None, None
    marker = m.group(1)
    form = ("session $" if marker == "$" else "session ≈" if marker.startswith("≈")
            else "session USD")
    return value, form


def head_totals(events, metered=None):
    """[(sid, dollars or None, source)] — one entry per head session the table counts, in
    record order. Each head's figure is, in order of preference: the meter's own reading over
    the RUN's window when one was taken (T6, so a session shared with attended work is never
    counted whole against this run), else the LATER of that head's last boundary billed line
    and its head-exit's `spent_usd` — a head that exited without a boundary loses nothing
    (register entry 2026-09-06). None where the record and the meter both give no figure."""
    found = []
    for sid in head_ids(events):
        billed_i, billed, exit_i, spent = -1, None, -1, None
        billed_form = "session $"
        for i, ev in enumerate(events):
            if session_at(events, i) != sid:
                continue
            if ev.get("event") == "phase-boundary" and isinstance(ev.get("meter"), str):
                value, form = billed_session(ev["meter"])
                if value is not None:
                    billed_i, billed, billed_form = i, value, form
            elif ev.get("event") == "head-exit":
                value = ev.get("spent_usd")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    exit_i, spent = i, float(value)
        if spent is not None and (billed is None or exit_i > billed_i):
            record, why = spent, "head-exit.spent_usd $%.2f%s" % (
                spent, ", later in the record than the last boundary billed line $%.2f" % billed
                if billed is not None else ", the head recorded no boundary billed line")
        elif billed is not None:
            record, why = billed, "the last boundary billed line's `%s` $%.2f%s%s" % (
                billed_form, billed,
                "" if billed_form == "session $" else " (a figure carried by hand)",
                ", later than head-exit.spent_usd $%.2f" % spent if spent is not None else "")
        else:
            record, why = None, "no boundary billed line and no head-exit.spent_usd"
        line = (metered or {}).get(sid)
        window = session_spent(line) if isinstance(line, str) else None
        if window is not None:
            found.append((sid, window, "metered over the run's window: $%.2f (the record gives "
                                       "%s)" % (window, why)))
        else:
            found.append((sid, record, "%s%s" % (why, "" if line is None else
                                                 " · the window meter gave no figure: %s"
                                                 % one_line(str(line))[:120])))
    return found


def billed_rows(events, metered=None):
    """The billed line at every boundary, quoted as the meter printed it, and the whole-run
    rows: a run total as a shown sum of the per-head figures head_totals derives, with the
    envelope base beside it. An unmetered or failed line is quoted, never zeroed."""
    rows, quoted = [], 0
    for i, ev in enumerate(events):
        if ev.get("event") != "phase-boundary":
            continue
        sid = session_at(events, i) or "unnamed head"
        line = ev.get("meter", MISSING)
        text = "field absent" if line is MISSING else cell(one_line(line))
        rows.append(("billed line · head %s · %s" % (sid, boundary_label(ev)), text, "billed",
                     FIX_NA))
        if not (isinstance(line, str) and billed_session(line)[0] is not None):
            quoted += 1
    totals = [(sid, usd, why) for sid, usd, why in head_totals(events, metered)
              if usd is not None]
    if not rows and not totals:
        return rows
    envelope = run_open(events).get("envelope_usd")
    base = (" · envelope base $%.2f (run-open.envelope_usd)" % float(envelope)
            if isinstance(envelope, (int, float)) and not isinstance(envelope, bool)
            else " · no envelope base (run-open carries no envelope_usd)")
    seeds = seed_sessions(events)
    skipped = (" · seed (skipped): %s, marked seed by run-open and never a head"
               % ", ".join(seeds) if seeds else "")
    if totals:
        shown = " + ".join("$%.2f" % usd for _, usd, _ in totals)
        fig = "%s = $%.2f · per head: %s%s%s%s" % (
            shown, round(sum(usd for _, usd, _ in totals), 2),
            "; ".join("%s %s" % (sid, why) for sid, _, why in totals), base, skipped,
            "; %d boundary line(s) carried no session figure and are quoted above, never read "
            "as zero" % quoted if quoted else "")
    else:
        fig = ("unmeasured · no boundary billed line carried a `session $` figure and no "
               "head-exit recorded spend; the %d line(s) are quoted above, never read as "
               "zero%s%s" % (quoted, base, skipped))
    rows.append(("run total (shown sum)", fig, "billed", FIX_NA))
    return rows


def context_rows(events):
    """Context per item, read off the gate events as the delta between consecutive gates."""
    gates = [e for e in events if e.get("event") == "gate"]
    if not gates:
        return [("context per item", "no gate events in the record · Step 2b drops the context "
                 "column for this run", "context", FIX_NA)]
    rows, prev = [], None
    for g in gates:
        item = "context · item %s at %s" % (g.get("item", "?"), g.get("ts", "no ts"))
        value = g.get("context")
        if not isinstance(value, int):
            rows.append((item, "unmeasured · the gate is unmetered (band %s)"
                         % g.get("band", "?"), "context", FIX_NA))
            continue
        if prev is None:
            rows.append((item, "%s tokens · the first metered gate, no earlier gate to "
                         "difference%s" % (format(value, ","),
                                           " (one gate event only)" if len(gates) == 1 else ""),
                         "context", FIX_NA))
        else:
            delta = value - prev
            rows.append((item, "%s%s tokens · gate context %s → %s"
                         % ("+" if delta >= 0 else "-", format(abs(delta), ","),
                            format(prev, ","), format(value, ",")), "context", FIX_NA))
        prev = value
    return rows


def head_spans(events):
    """[(session id, start, end)] for the head sessions the table counts, in record order. A
    span holding a head-exit that records no transcript is a session that never ran (see
    seed_exit) and is left out: counting it would put an `unmeasured` head in the table beside
    the heads that did run. A session `run-open --session-kind seed` marks is left out for the
    same reason, on the record's own field rather than on the absence of a transcript (T7)."""
    starts = [i for i, e in enumerate(events) if e.get("event") in SESSION_EVENTS]
    seeds = seed_sessions(events)
    spans = []
    for k, i in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(events)
        if any(seed_exit(e) for e in events[i:end]):
            continue
        sid = session_at(events, i + 1) or "unnamed head"
        if sid in seeds:
            continue
        spans.append((sid, i, end))
    return spans


def head_ids(events):
    """The distinct head session ids the table counts, in record order. One id however many
    spans it holds: a head-successor and the run-resume that follows it name ONE session, so
    counting spans instead would count one head twice (register entry 2026-09-06).
    """
    ids = []
    for sid, _, _ in head_spans(events):
        if sid not in ids:
            ids.append(sid)
    return ids


def orientation_rows(events):
    """The orientation cost per head (D41): the first gate of each head's span carries
    `orientation_tokens`; anything else is `unmeasured` with the reason. One row per session
    id — a head-successor and the run-resume that follows it are two spans of ONE session — and
    a measured figure wins over an unmeasured one, so a resumed head's null does not hide the
    figure its own first gate recorded."""
    spans = head_spans(events)
    if not spans:
        return [("orientation cost", "unmeasured · the record names no head session that ran",
                 "structural", FIX_NONE)]
    found = []       # (session id, row, measured): one row per id survives, measured first
    for sid, i, end in spans:
        item = "orientation cost · head %s" % sid
        gate = next((e for e in events[i:end] if e.get("event") == "gate"), None)
        if gate is None:
            found.append((sid, (item, "unmeasured · no gate event in this head's span",
                                "structural", FIX_NONE), False))
            continue
        value = gate.get("orientation_tokens", MISSING)
        source = "gate.orientation_tokens · item %s at %s" % (gate.get("item", "?"),
                                                              gate.get("ts", "no ts"))
        if value is None:
            note = gate.get("orientation_note") or "the field is null"
            found.append((sid, (item, "unmeasured · %s · %s" % (note, source), "structural",
                                FIX_NONE), False))
            continue
        if value is MISSING:
            found.append((sid, (item, "field absent", "structural", FIX_NONE), False))
            continue
        fig, finding = figure(value, "count", source)
        found.append((sid, (item, fig.replace(" · ", " tokens · ", 1), "structural",
                            FIX_OPEN if finding else FIX_NONE), True))
    chosen = {}
    order = []
    for sid, row, measured in found:
        if sid not in chosen:
            order.append(sid)
        if sid not in chosen or (measured and not chosen[sid][1]):
            chosen[sid] = (row, measured)
    return [chosen[sid][0] for sid in order]


def soft_cap_note(ev):
    """` · soft-cap: $<billed> over $<soft>` for a close the wrapper flagged, else "". The
    soft threshold is logged at the close and never stops a lane (lane.py's two-tier caps),
    so the flag is rendered in this row; the head ledgers
    the line at the lane's close. A flag with no dollar figure beside it says `unmeasured`
    rather than a number nobody recorded."""
    if ev.get("soft_exceeded") is not True:
        return ""
    def money(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "unmeasured"
        return "$%.2f" % float(value)
    return " · soft-cap: %s over %s (%s)" % (money(ev.get("total_cost_usd")),
                                             money(ev.get("soft_usd")),
                                             ev.get("soft_src") or "class")


def lane_rows(events, meter_lanes=False):
    """Lost-lane cost: every lane-closed whose exit class is not `completed`, with the cost
    field as recorded and `unmeasured` where the event carries none. A cut lane that a later
    lane-resumed picked up again lost nothing: its row says so and carries no fix, matching
    the boundary field's exclusion. A close flagged `soft_exceeded` carries its soft-cap note
    on the same row, and a COMPLETED lane so flagged — which has no row otherwise — gets one
    of its own, arguable in kind: the money bought a result, and whether it was waste is the
    reflector's call, not this table's."""
    rows = []
    for i, ev in enumerate(events):
        if ev.get("event") != "lane-closed":
            continue
        cls = ev.get("exit_class", MISSING)
        note = soft_cap_note(ev)
        if cls == "completed":
            if note:
                rows.append(("soft-cap lane · %s · exit class completed"
                             % (ev.get("lane") or "unnamed lane"),
                             "%s · lane-closed.soft_exceeded · logged at the close, never a "
                             "stop" % note.lstrip(" ·").strip(), "arguable", FIX_OPEN))
            continue
        lane = ev.get("lane") or "unnamed lane"
        stamped = "%s at %s" % (lane, ev.get("ts", "no ts"))
        if cls is MISSING:
            rows.append(("lost lane · %s · exit class" % lane, "field absent", "real", FIX_NONE))
            continue
        cost = ev.get("total_cost_usd", MISSING)
        if cost is None and is_plan_lane(events, i, ev):
            fig, finding = ("plan usage (a Codex lane): counted, never priced · "
                            "lane-closed.total_cost_usd null · %s%s" % (stamped, note)), False
        elif cost is None and meter_lanes:
            # A close with no cost (a lane killed with its head, register entry 2026-09-07) is
            # billed from its surviving transcript; a lane that cannot be stays unmeasured.
            usd, how = lane_transcript_bill(ev)
            if usd is not None:
                fig, finding = ("metered (transcript) $%.2f · lane-closed.total_cost_usd null · "
                                "%s · %s%s" % (usd, how, stamped, note)), usd > 0
            else:
                fig, finding = figure(None, "usd", "lane-closed.total_cost_usd · %s%s · "
                                      "transcript meter: %s" % (stamped, note, how))
        else:
            fig, finding = figure(cost, "usd",
                                  "lane-closed.total_cost_usd · %s%s" % (stamped, note))
        resumed = resumed_after(events[i + 1:], ev)
        if resumed is not None:
            rows.append(("cut lane · %s · exit class %s · resumed" % (lane, cls),
                         "%s · resumed at %s, so not lost (excluded from respawn_cost_usd)"
                         % (fig, resumed.get("ts", "no ts")), "real", FIX_NONE))
            continue
        rows.append(("lost lane · %s · exit class %s" % (lane, cls), fig, "real",
                     FIX_OPEN if finding else FIX_NONE))
    return rows


def waste_table(events, run, path, bad, metered=None, meter_lanes=False):
    """(text, rows, counts): the whole document, rendered from the record and — for the
    whole-run rows alone — the meter's reading of each head over the run's own window, which
    the caller takes and passes in (T6). Every other figure is read from a field."""
    boundaries = [e for e in events if e.get("event") == "phase-boundary"]
    gates = [e for e in events if e.get("event") == "gate"]
    lanes = [e for e in events if e.get("event") == "lane-closed"]
    lost = [e for e in lanes if e.get("exit_class", MISSING) != "completed"]
    heads = head_ids(events)   # distinct ids: a session that never ran is not a head
    rows = []
    if not boundaries:
        rows.append(("phase-boundary events", "no phase-boundary events · the waste fields and "
                     "the billed lines are read from these events", "control", FIX_NA))
    rows += field_rows(events)
    rows += billed_rows(events, metered)
    rows += context_rows(events)
    rows += orientation_rows(events)
    rows += limit_wait_rows(events)
    rows += lane_rows(events, meter_lanes)
    if not any(row[3] == FIX_OPEN for row in rows):
        rows.append(("no waste found", "searched: %d phase-boundary event(s) for %s; %d "
                     "lane-closed event(s) for an exit class other than `completed`; %d gate "
                     "event(s) for `orientation_tokens` and the context deltas"
                     % (len(boundaries), ", ".join(k for k, _, _, _ in BOUNDARY_FIELDS),
                        len(lanes), len(gates)),
                     "control", "n/a · the zero-findings control names what was searched"))
    _, _, window_src = run_window(events)
    seeds = seed_sessions(events)
    header = [
        "# Waste table · run %s" % run,
        "",
        "Step 2b of the reflect skill, rendered by `handsoff.py waste-table` from the run "
        "record: every figure but the whole-run rows is read from a field, none is recalled, "
        "and the only meter calls are the ones those rows name (hands-off design D36; T6 of "
        "the token-efficiency findings, 2026-09-07) and, unless --no-meter, the transcript "
        "meter of a lane closed with no cost (register entry 2026-09-07).",
        "Record: %s" % path,
        "Rendered: %s" % now(),
        "Events read: %d phase-boundary%s, %d gate, %d lane-closed (%d not completed), %d head "
        "session(s)%s." % (len(boundaries), " (no phase-boundary events)" if not boundaries
                           else "", len(gates), len(lanes), len(lost), len(heads),
                           "; %d unparseable line(s) skipped" % bad if bad else ""),
        "Head sessions are counted by DISTINCT session id (%s): a head-successor and the "
        "run-resume that follows it are one session, not two." % (", ".join(heads) or "none"),
        "Run window for the whole-run rows: %s." % window_src,
        "seed (skipped): %s." % ("%s — marked `session_kind: seed` by run-open, a launcher's "
                                 "placeholder that never ran, so it is neither metered nor "
                                 "counted as a head session" % ", ".join(seeds) if seeds else
                                 "none — no run-open in this record marks a seed session"),
        "Legend: %s" % LEGEND,
        "",
        "## Waste table",
        "",
    ]
    body = list(TABLE_HEAD) + ["| %s | %s | %s | %s |" % tuple(cell(x) for x in row)
                               for row in rows]
    counts = {"rows": len(rows), "boundaries": len(boundaries), "gates": len(gates),
              "lanes": len(lanes)}
    return "\n".join(header + body) + "\n", rows, counts


def meter_overrides(pairs):
    """{session id: billed line} from `--meter-line SID=LINE` (repeatable): a line already in
    hand for one head, so the whole-run rows can be rendered without running the meter."""
    found = {}
    for pair in pairs or []:
        sid, sep, line = pair.partition("=")
        if not sep or not sid.strip() or not line.strip():
            die("--meter-line takes SID=LINE; got %s" % one_line(pair)[:80])
        found[sid.strip()] = line.strip()
    return found


def metered_heads(events, run, no_meter=False, overrides=None):
    """{session id: billed line or its failure} for every head session the table counts, each
    metered over the RUN's own window (T6). `no_meter` renders from the record alone, which is
    what a caller with no transcripts to read passes; an override stands in for the meter."""
    overrides = overrides or {}
    if no_meter and not overrides:
        return {}
    start, end, _ = run_window(events)
    found = {}
    for sid in head_ids(events):
        if sid in overrides:
            found[sid] = overrides[sid]
        elif not no_meter:
            found[sid] = meter_line(events, run, None, start, end, sid)
    return found


def cmd_waste_table(a):
    path = record_path(a.run)
    events = require_record(path)
    bad = read_record(path)[1]
    out_path = (os.path.realpath(os.path.expanduser(a.out)) if a.out else
                os.path.join(store_root(), "spawn-records", "%s-waste-table.md" % a.run))
    metered = metered_heads(events, a.run, a.no_meter, meter_overrides(a.meter_line))
    text, _, counts = waste_table(events, a.run, path, bad, metered, meter_lanes=not a.no_meter)
    summary = "%d rows from %d boundaries, %d gates, %d lanes" % (
        counts["rows"], counts["boundaries"], counts["gates"], counts["lanes"])
    if a.dry_run:
        say("waste-table: dry run · %s · would write %s" % (summary, out_path))
        return 0
    try:
        write_atomic(out_path, text)
    except OSError as exc:
        die("cannot write the waste table %s: %s" % (out_path, exc))
    say("waste-table: %s → %s" % (summary, out_path))
    return 0


# ------------------------------------------------------- the head's own transcript ----------

# The two injected user-record classes the reflector template names, plus the tool results:
# `"type":"user"` alone does not mean a human turn. A Skill-tool injection carries
# `isMeta: true` and opens "Base directory for this skill" (the reflect skill's Step 2). A
# harness injection is recognised by its opening, or by a record whose whole text is one or
# more system-reminder blocks. RESIDUE, stated rather than hidden: the harness's exact
# task-notification wrapper is unverified here, so a notification matching none of these
# markers is extracted as a human turn — an over-count the reflector can see, rather than a
# dropped human turn it cannot. `--notification-re` adds a marker without editing this list.
SKILL_INJECTION_RE = re.compile(r"^\s*Base directory for this skill")
REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
# A resume replay: the harness sends a whole prior conversation as ONE user record, opening
# with a turn marker and carrying at least two of them (the same predicate
# the anchor hook's `_owner_text` carries, copied rather than imported because that hook is
# machine-local). The markers are the property, never the size. The hook drops such a prompt
# whole; the extraction keeps its trailing owner message — the words the owner actually typed
# this turn — as a human turn noted under `notes.replay_trimmed`, and a replay with no owner
# message left is counted under `excluded.replay` (one bucket per record, 2026-09-13).
REPLAY_OPEN_RE = re.compile(r"\s*(?:User|Assistant|Human):")
TURN_MARK_RE = re.compile(r"(?m)^(?:User|Assistant|Human):")
HUMAN_MARK_RE = re.compile(r"(?m)^(?:User|Human):")
# The harness's own stop record: an assistant record whose model field opens with this and
# whose text is "No response requested." is the harness speaking, not the head. The watermark
# hook's measure() skips the same records (context-watermark.py, the `<synthetic` model test).
SYNTHETIC_MODEL = "<synthetic"
NOTIFICATION_RES = (
    re.compile(r"^\s*<task-notification\b"),
    re.compile(r"^\s*Caveat: The messages below were generated by the user while running local "
               r"commands"),
)
# Cut closed task-notification spans from user text; any remaining owner message remains a
# human turn. A record containing only notifications is excluded (register entry 2026-09-13 03:53).
NOTIFICATION_SPAN_RE = re.compile(r"<task-notification\b.*?</task-notification>", re.S)
# The harness's interrupt marker: a user record the owner never typed, never a human turn.
INTERRUPT_RE = re.compile(r"^\s*\[Request interrupted by user[^\]]*\]\s*$")


# An assistant record's tool calls carried into the extraction (register entry 2026-09-07): the
# call, never its result — the tool_result exclusion above stands, so the reflector reads what
# the head DID and not what came back. One line per call: the tool's name and the input field
# that says what it acted on, each line cut at TOOL_CALL_CHARS characters (set by the head as a
# bound on one line, unmeasured; a cut line ends with the marker so the cut is visible). A tool
# outside the table prints its name alone rather than a guessed field.
TOOL_CALL_CHARS = 300
TOOL_CALL_CUT = " …[cut]"
TOOL_ARG_KEYS = {"Bash": ("command",), "Read": ("file_path",), "Write": ("file_path",),
                 "Edit": ("file_path",), "Grep": ("pattern",), "Glob": ("pattern",)}


def tool_call_line(block):
    """`- <tool>: <what it acted on>` for one tool_use block, or `- <tool>` where the tool is
    not in the table above or its input carries none of that tool's fields. Cut at
    TOOL_CALL_CHARS characters, the cut marked."""
    name = str(block.get("name") or "tool")
    data = block.get("input") if isinstance(block.get("input"), dict) else {}
    value = ""
    for key in TOOL_ARG_KEYS.get(name, ()):
        if data.get(key) not in (None, ""):
            value = one_line(str(data[key]))
            break
    line = "- %s: %s" % (name, value) if value else "- %s" % name
    if len(line) > TOOL_CALL_CHARS:
        line = line[:TOOL_CALL_CHARS - len(TOOL_CALL_CUT)] + TOOL_CALL_CUT
    return line


def tool_call_lines(blocks):
    """The tool-call lines of one assistant record, in the order the record holds them."""
    return [tool_call_line(b) for b in blocks if b.get("type") == "tool_use"]


def blocks_of(message):
    content = message.get("content")
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def turn_text(lane, blocks, kinds=("text",)):
    """The record's prose, joined by lane.py's own block reader (never a second parser)."""
    return " ".join(lane.block_text(b) for b in blocks if b.get("type") in kinds).strip()


def is_notification(text, extra):
    if not REMINDER_RE.sub("", text).strip():
        return True
    return any(pattern.match(text) for pattern in tuple(NOTIFICATION_RES) + tuple(extra))


def owner_text(text, extra):
    """(verdict, kept text, cut) for a user record's text. The system reminders and the closed
    task-notification spans are cut out first. Nothing left, or what is left still opening with
    a harness marker (an unclosed notification, the local-command caveat, an --notification-re
    pattern), is `notification`; the bare interrupt marker is `interrupt`; anything else is
    `owner`, the text left, with `cut` True when a span or a reminder was cut from it."""
    left = NOTIFICATION_SPAN_RE.sub("", REMINDER_RE.sub("", text)).strip()
    if not left or any(pattern.match(left) for pattern in tuple(NOTIFICATION_RES) + tuple(extra)):
        return "notification", "", False
    if INTERRUPT_RE.match(left):
        return "interrupt", "", False
    return "owner", left, left != text.strip()


def reconciliation(counts):
    """(bucketed, in no bucket): extracted + tool_call_turns + every exclusion, and the records
    that sum leaves out, which the classification keeps at 0 (register entry 2026-09-07)."""
    bucketed = (counts["extracted"] + counts["tool_call_turns"]
                + sum(counts["excluded"].values()))
    return bucketed, counts["records"] - bucketed


def reconciliation_text(counts):
    _, missing = reconciliation(counts)
    return ("reconciles" if missing == 0
            else "DOES NOT RECONCILE: %d record(s) in no bucket" % missing)


def other_list(counts):
    return ", ".join("%s %d" % (kind, n) for kind, n in sorted(counts["other_types"].items())) \
        or "none"


def replay_tail(text):
    """(is_replay, kept text) for a resume replay the harness sent as one user record: everything
    after its LAST human turn marker, which in the observed shape is the message the owner typed
    this turn. The kept text is "" when the replay carries no human marker at all or nothing
    after it, and a record that is not a replay comes back unchanged. The tail is NOT cut at any
    later marker: where the last marker is not the owner's — a typed prompt that opens by quoting
    a conversation — cutting drops the owner's own words, and this file's residue note already
    prefers an over-inclusive turn the reflector can see to a dropped one it cannot."""
    if not (REPLAY_OPEN_RE.match(text) and len(TURN_MARK_RE.findall(text)) >= 2):
        return False, text
    marks = list(HUMAN_MARK_RE.finditer(text))
    return True, (text[marks[-1].end():].strip() if marks else "")


def extract_turns(lane, path, extra):
    """(turns, counts) from a transcript: human turns, assistant prose and the assistant's tool
    calls in file order, with the tool results and the injected user-record classes counted
    out. EVERY record lands in exactly one bucket (register entry 2026-09-07), so
    records = extracted + tool_call_turns + every exclusion holds by construction and the
    header prints it: a record of any other type (progress, summary,
    system, file-history-snapshot, queue-operation, one with no type) and an assistant record
    with neither prose nor a tool call (thinking alone, no content) go under `excluded.other`,
    each named in `other_types`. An unparseable line is counted, never fatal. An assistant record
    carrying only tool calls is a tool-call turn — one line per call, the call and never its
    result — counted under `tool_call_turns`. A record carrying both prose and tool calls keeps
    its prose turn and the lines go under it, so the turn count still matches the head's
    messages. A resume replay keeps its trailing owner message as a human turn, noted under
    `notes.replay_trimmed`; a replay with no owner message left is `excluded.replay`; a synthetic
    assistant record is `excluded.synthetic`. A user record's system reminders and closed
    task-notification spans are cut from its text and what is left is the owner's (owner_text,
    register entry 2026-09-13 03:53), noted under `notes.injections_cut`; the bare interrupt
    marker is `excluded.interrupt`; a record carrying a tool result beside owner text is a human
    turn noted under `notes.tool_result_with_text` (over-inclusive and visible, since the
    harness's own shape is unverified here). Notes are never buckets."""
    turns = []
    counts = {"records": 0, "human_turns": 0, "assistant_turns": 0, "tool_call_turns": 0,
              "excluded": {"tool_result": 0, "meta": 0, "notification": 0, "interrupt": 0,
                           "replay": 0, "synthetic": 0, "unparseable": 0, "other": 0},
              "other_types": {},
              "notes": {"replay_trimmed": 0, "injections_cut": 0, "tool_result_with_text": 0}}
    out = counts["excluded"]
    notes = counts["notes"]

    def other(kind):
        out["other"] += 1
        counts["other_types"][kind] = counts["other_types"].get(kind, 0) + 1
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            counts["records"] += 1
            try:
                record = json.loads(line)
            except ValueError:
                out["unparseable"] += 1
                continue
            if not isinstance(record, dict):
                out["unparseable"] += 1
                continue
            kind = record.get("type")
            message = record.get("message") if isinstance(record.get("message"), dict) else {}
            blocks = blocks_of(message)
            stamp = record.get("timestamp") or record.get("ts") or "no timestamp"
            if kind == "user":
                text = turn_text(lane, blocks)
                if record.get("toolUseResult") is not None or \
                        any(b.get("type") == "tool_result" for b in blocks):
                    verdict, kept, _ = owner_text(text, extra) if text else ("empty", "", False)
                    if verdict != "owner":
                        out["tool_result"] += 1
                        continue
                    notes["tool_result_with_text"] += 1
                    counts["human_turns"] += 1
                    turns.append(("human", stamp, kept))
                    continue
                if record.get("isMeta") is True or SKILL_INJECTION_RE.match(text):
                    out["meta"] += 1
                    continue
                replayed, text = replay_tail(text)
                if replayed and not text:
                    out["replay"] += 1        # a replay with no owner message left: nothing to keep
                    continue
                if replayed:
                    notes["replay_trimmed"] += 1
                if text:
                    verdict, kept, cut = owner_text(text, extra)
                    if verdict != "owner":
                        out[verdict] += 1     # notification or interrupt
                        continue
                    if cut:
                        notes["injections_cut"] += 1
                    text = kept
                counts["human_turns"] += 1
                turns.append(("human", stamp, text or "(this record carries no text content)"))
            elif kind == "assistant":
                if str(message.get("model") or "").startswith(SYNTHETIC_MODEL):
                    out["synthetic"] += 1   # the harness's stop record, never the head's prose
                    continue
                prose = turn_text(lane, blocks)
                calls = tool_call_lines(blocks)
                if prose:
                    counts["assistant_turns"] += 1
                    body = prose + ("\n\nTool calls:\n" + "\n".join(calls) if calls else "")
                    turns.append(("assistant", stamp, body))
                elif calls:
                    counts["tool_call_turns"] += 1
                    turns.append(("assistant · tool calls", stamp, "\n".join(calls)))
                else:
                    shapes = sorted(set(str(b.get("type") or "untyped") for b in blocks))
                    other("assistant: %s" % ("+".join(shapes) if shapes else "no content"))
            else:
                other(str(kind) if isinstance(kind, str) and kind else "(no type)")
    counts["extracted"] = counts["human_turns"] + counts["assistant_turns"]
    return turns, counts


def extraction_text(sid, path, turns, counts):
    out = counts["excluded"]
    head = [
        "# Transcript extraction · session %s" % sid,
        "",
        "Source: %s" % path,
        "Extracted: %s by `handsoff.py extract-transcript` (hands-off design D36): the human "
        "turns and the assistant prose, in order." % now(),
        "Excluded: %d tool-result record(s), %d Skill-tool injection(s) marked `isMeta`, %d "
        "harness injection(s), %d interrupt marker(s), %d replay(s) with no owner message left, "
        "%d synthetic assistant record(s), %d unparseable line(s), and %d record(s) of other "
        "types (%s)." % (
            out["tool_result"], out["meta"], out["notification"], out["interrupt"],
            out["replay"], out["synthetic"], out["unparseable"], out["other"],
            other_list(counts)),
        "Replays: %d record(s) in which the harness re-sent a whole prior conversation as one "
        "user record (a turn marker at the opening and at least two in all, whatever the size) "
        "were trimmed to the text after their last `User:` marker, which is the turn the owner "
        "typed, and read as human turns (notes.replay_trimmed); a replay with no owner message "
        "left is dropped and counted under excluded.replay." % counts["notes"]["replay_trimmed"],
        "Mid-turn messages: %d user record(s) read as human turns after a task-notification "
        "span or a system reminder was cut from their text (notes.injections_cut), and %d "
        "record(s) carrying a tool result beside owner text read as human turns "
        "(notes.tool_result_with_text); a record that is nothing but notifications stays "
        "excluded, and the bare interrupt marker is never a human turn." % (
            counts["notes"]["injections_cut"], counts["notes"]["tool_result_with_text"]),
        "An assistant record carrying only tool calls is a tool-call turn, headed `assistant · "
        "tool calls`: one line per call with the tool's name and the input field naming what it "
        "acted on, each line cut at %d characters. The calls are carried, never their results, "
        "so the tool-result exclusion above stands. A record carrying both prose and tool calls "
        "keeps its prose turn and its lines go under it." % TOOL_CALL_CHARS,
        "Read %d of %d records as turns (%d human, %d assistant), and %d record(s) of tool "
        "calls alone. Records = %d extracted + %d tool-call + %d excluded = %d, against %d "
        "records read: %s." % (
            counts["extracted"], counts["records"], counts["human_turns"],
            counts["assistant_turns"], counts["tool_call_turns"], counts["extracted"],
            counts["tool_call_turns"], sum(out.values()), reconciliation(counts)[0],
            counts["records"], reconciliation_text(counts)),
        "",
    ]
    body = []
    for n, (role, stamp, text) in enumerate(turns, 1):
        body += ["## turn %d · %s · %s" % (n, role, stamp), "", text, ""]
    return "\n".join(head + body) + "\n"


def extraction_inputs(a):
    """(lane module, session id, transcript path, extra notification patterns) for the two
    commands that read the head's own transcript; every missing premise is a premise failure."""
    lane, _, err = lane_module()
    if lane is None:
        die("the transcript helpers are lane.py's, never a second parser of the same shape: %s"
            % err)
    sid = token(a.session, "session id")
    root = os.path.realpath(os.path.expanduser(a.projects_root)) if a.projects_root else None
    path = transcript_for(sid, root)
    if not os.path.isfile(path):
        die("no transcript for session %s at %s" % (sid, path))
    try:
        extra = [re.compile(pattern) for pattern in (a.notification_re or [])]
    except re.error as exc:
        die("--notification-re is not a regular expression: %s" % exc)
    return lane, sid, path, extra


def write_extraction(lane, sid, path, out_dir, extra):
    """turns.md and counts.json under out_dir, and the counts behind them — one writer for
    `extract-transcript` and `reflect-inputs`, so the two can never differ."""
    try:
        turns, counts = extract_turns(lane, path, extra)
    except OSError as exc:
        die("cannot read the transcript %s: %s" % (path, exc))
    counts["session"] = sid
    payload = {"session": sid, "records": counts["records"],
               "human_turns": counts["human_turns"],
               "assistant_turns": counts["assistant_turns"],
               "tool_call_turns": counts["tool_call_turns"], "excluded": counts["excluded"],
               "extracted": counts["extracted"], "other_types": counts["other_types"],
               "notes": counts["notes"], "bucketed": reconciliation(counts)[0],
               "in_no_bucket": reconciliation(counts)[1],
               "reconciles": reconciliation(counts)[1] == 0}
    try:
        write_atomic(os.path.join(out_dir, "turns.md"),
                     extraction_text(sid, path, turns, counts))
        write_atomic(os.path.join(out_dir, "counts.json"),
                     json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    except OSError as exc:
        die("cannot write the extraction under %s: %s" % (out_dir, exc))
    return counts


def excluded_text(out):
    return ("excluded tool_result %d, meta %d, notification %d, interrupt %d, replay %d, "
            "synthetic %d, unparseable %d, other %d" % (
                out["tool_result"], out["meta"], out["notification"], out["interrupt"],
                out["replay"], out["synthetic"], out["unparseable"], out["other"]))


def cmd_extract_transcript(a):
    lane, sid, path, extra = extraction_inputs(a)
    out_dir = (os.path.realpath(os.path.expanduser(a.out)) if a.out
               else os.path.join("/tmp", "aimyth-extract-%s" % sid))
    counts = write_extraction(lane, sid, path, out_dir, extra)
    say("extract-transcript: %d turns (%d human, %d assistant) of %d records · %d tool-call "
        "turn(s) · %s · %s → %s"
        % (counts["extracted"], counts["human_turns"], counts["assistant_turns"],
           counts["records"], counts["tool_call_turns"], excluded_text(counts["excluded"]),
           reconciliation_text(counts), out_dir))
    return 0


# ------------------------------------------------- the blind reflector's whole input set -----

# A spawner pre-registers its controls in the record as an observation whose phase starts
# `controls` (the convention: `handsoff.py ledger --phase controls-<LANE> …`), and a lane event
# carries the brief it was given and the case planted for it. None of that is the P4
# reflector's to read: that lane is blind to what the head expected, so `reflect-inputs` drops
# those observations from the copy it writes and strips these keys from every event it keeps.
CONTROL_PHASE = "controls"
BLINDED_KEYS = ("controls_checked", "brief_copy", "brief", "plant")


def blinded_events(events):
    """(kept events, observations dropped, events stripped) for the blind reflector's copy of
    the run record: an observation whose phase starts `controls` goes whole, and every event
    kept loses the keys carrying a control, a brief or a planted case."""
    kept, dropped, stripped = [], 0, 0
    for ev in events:
        phase = ev.get("phase")
        if ev.get("event") == "observation" and isinstance(phase, str) \
                and phase.startswith(CONTROL_PHASE):
            dropped += 1
            continue
        copy = dict((k, v) for k, v in ev.items() if k not in BLINDED_KEYS)
        if len(copy) != len(ev):
            stripped += 1
        kept.append(copy)
    return kept, dropped, stripped


def refuse_out_inside(out_dir, what, root):
    """A premise failure when --out sits in a directory the blind lane is not granted: the
    reflector is granted its own directory alone, and an input set written into the store or
    the projects root either needs a grant it must not have or is read as the run's own."""
    real = os.path.realpath(os.path.expanduser(out_dir))
    for spelling in spellings(root):
        if real == spelling or real.startswith(spelling + os.sep):
            die("--out %s is inside the %s (%s): the reflector lane is granted its output "
                "directory alone, so the input set is written outside both — allowed: any "
                "directory outside the run store (%s) and the projects root (%s), such as one "
                "under /tmp" % (out_dir, what, spelling, store_root(), projects_root()))


def cmd_reflect_inputs(a):
    """The P4 boundary reflection's whole input set in one directory (D36): the extraction, the
    waste table and a filtered copy of the run record, written before the event that records
    them so the copy never carries its own line."""
    path = record_path(a.run)
    events = require_record(path)
    bad = read_record(path)[1]
    out_dir = os.path.realpath(os.path.expanduser(a.out))
    refuse_out_inside(out_dir, "run store", store_root())
    refuse_out_inside(out_dir, "projects root", projects_root())
    lane, sid, tpath, extra = extraction_inputs(a)
    if a.dry_run:
        try:
            _, counts = extract_turns(lane, tpath, extra)
        except OSError as exc:
            die("cannot read the transcript %s: %s" % (tpath, exc))
        _, _, wcounts = waste_table(events, a.run, path, bad,
                                    metered_heads(events, a.run, a.no_meter,
                                                  meter_overrides(a.meter_line)),
                                    meter_lanes=not a.no_meter)
        kept, dropped, stripped = blinded_events(events)
        say("reflect-inputs: dry run · %d turns (%d human, %d assistant) of %d records · %d "
            "tool-call turn(s) · %d waste row(s) · %d event(s) kept, %d controls observation(s) "
            "dropped, %d stripped of %s · would write turns.md, counts.json, waste-table.md and "
            "record-filtered.jsonl under %s and append one reflect-inputs event"
            % (counts["extracted"], counts["human_turns"], counts["assistant_turns"],
               counts["records"], counts["tool_call_turns"], wcounts["rows"], len(kept),
               dropped, stripped, "/".join(BLINDED_KEYS), out_dir))
        return 0
    counts = write_extraction(lane, sid, tpath, out_dir, extra)
    text, _, wcounts = waste_table(events, a.run, path, bad,
                                   metered_heads(events, a.run, a.no_meter,
                                                 meter_overrides(a.meter_line)),
                                   meter_lanes=not a.no_meter)
    kept, dropped, stripped = blinded_events(events)
    try:
        write_atomic(os.path.join(out_dir, "waste-table.md"), text)
        write_atomic(os.path.join(out_dir, "record-filtered.jsonl"),
                     "".join(json.dumps(ev, ensure_ascii=False) + "\n" for ev in kept))
    except OSError as exc:
        die("cannot write the reflection inputs under %s: %s" % (out_dir, exc))
    summary = {"turns": counts["extracted"], "human_turns": counts["human_turns"],
               "assistant_turns": counts["assistant_turns"],
               "tool_call_turns": counts["tool_call_turns"], "records": counts["records"],
               "waste_rows": wcounts["rows"], "events_kept": len(kept),
               "controls_dropped": dropped, "events_stripped": stripped,
               "excluded": sum(counts["excluded"].values()),
               "in_no_bucket": reconciliation(counts)[1]}
    append_record(path, event(a.run, "reflect-inputs", session=sid, out=out_dir,
                              counts=summary))
    say("reflect-inputs: %d turns (%d human, %d assistant) of %d records · %d tool-call turn(s) "
        "· %d waste row(s) · %d event(s) kept, %d controls observation(s) dropped, %d stripped "
        "of %s → %s"
        % (summary["turns"], summary["human_turns"], summary["assistant_turns"],
           summary["records"], summary["tool_call_turns"], summary["waste_rows"],
           summary["events_kept"], summary["controls_dropped"], summary["events_stripped"],
           "/".join(BLINDED_KEYS), out_dir))
    return 0


# ------------------------------------------------------------------------------ main -------

def main():
    ap = argparse.ArgumentParser(description="hands-off run primitives; see the module docstring")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, handoff=True):
        p.add_argument("--run", required=True, help="run id (the record's file stem)")
        if handoff:
            p.add_argument("--handoff", default=None, help="hand-off path (default: run-open's)")
        p.add_argument("--dry-run", action="store_true", help="print what would be written")
        return p

    def grants(p):
        p.add_argument("--grants-file", nargs="?", const="", default=None, metavar="PATH",
                       help="retired (register entry 2026-09-06): refused, naming the one path "
                            "the head fence reads, <store>/spawn-records/<run>-grants.json")
        p.add_argument("--grant", action="append", default=[], metavar="PATH",
                       help="a read grant (repeatable); the defaults are always present; given, "
                            "it replaces the file's read list, and absent, grants and "
                            "run-resume carry that list forward")
        p.add_argument("--write", action="append", default=[], metavar="PATH",
                       help="a write grant (repeatable); the store and the state directory are "
                            "always present; given, it replaces the file's write list, and "
                            "absent, that list is carried forward: a rewrite that would lose a "
                            "write path with neither --grant nor --write is refused")
        p.add_argument("--on-limit", choices=ON_LIMIT_VALUES, default=None,
                       help="the limit gate (D42, the pre-flight's class L): stop (the default: "
                            "the supervisor stands down on a limit, the hand-off is the recovery) "
                            "or resume (the pre-flight's limit-off: sleep to the reset, then "
                            "resume); absent, the file's own value is carried forward")
        p.add_argument("--viewer", choices=VIEWER_VALUES, default=None,
                       help="the console window (the pre-flight's viewer key): terminal (the "
                            "default: run-open opens a Terminal window on `watch --run R`, and "
                            "successor and resume-head open one when none is alive) or none; "
                            "absent, the file's own value is carried forward")
        return p

    def network_flag(p):
        p.add_argument("--network", default=None, metavar="HOSTS",
                       help="the hosts the head fence's network check lets a command address: "
                            "bare host names, comma-separated, or none; absent, run-open writes "
                            "none (or an existing grants file's value) and grants carries the "
                            "file's value, which a file written before the key reads as none")
        return p

    def supervision(p):
        p.add_argument("--reset-at", default=None, metavar="HH:MM|+Ns|ISO",
                       help="the reset time after a limit stop; wins over the stop text")
        p.add_argument("--max-wait-s", type=int, default=MAX_WAIT_S,
                       help="the reset wait's bound (successor-aborted reset-timeout past it)")
        p.add_argument("--probe", action="store_true",
                       help="opt in to the $0.05 haiku probe when no reset time can be parsed; "
                            "OFF by default (owner ruling 2026-09-06), and the supervisor never "
                            "passes it on its own — without it an unparsed limit records "
                            "stop-condition limit-unparsed and the hand-off is the "
                            "recovery; a limit scoped to one model takes no probe even "
                            "with the flag, since a probe on another model answers for "
                            "the wrong model")
        p.add_argument("--probe-interval-s", type=int, default=PROBE_INTERVAL_S)
        p.add_argument("--tick-s", type=int, default=SUPERVISE_TICK_S,
                       help="the sleep tick, so a run-close ends a wait (a suite shortens it)")
        p.add_argument("--meter-line", default=None,
                       help="a billed line in hand for the remainder (skips the meter)")
        p.add_argument("--beat-timeout-s", type=int, default=HOLD_BEAT_TIMEOUT_S,
                       help="the bound on one held-lane beat through the lane's wrapper (default "
                            "%d s: the wrapper's own %d s bound plus a %d s grace, so the "
                            "wrapper kills its harness and records the failure before this "
                            "fires); past it the attempt is recorded failed"
                            % (HOLD_BEAT_TIMEOUT_S, HOLD_BEAT_WRAPPER_BOUND_S,
                               HOLD_BEAT_GRACE_S))
        return p

    def two_heads(p):
        p.add_argument("--i-am-pid", type=int, default=None, metavar="PID",
                       help="this caller's own head process, only when the parent walk cannot "
                            "reach it (no ps, or a call detached from its head's process tree): "
                            "the two-heads check (exit 9) then treats PID as the caller's own")
        return p

    def decisions_channel(p):
        p.add_argument("--decisions-file", default=None, metavar="PATH",
                       help="the run's decisions file (no default): an mtime after the last gate "
                            "or ack holds the call with exit 6, as a newer AUTHOR observation "
                            "does; a named file that does not exist is refused")
        p.add_argument("--ack", default=None, metavar="LINE",
                       help="one line naming what was read: records an observation 'ack: LINE' "
                            "and the held call proceeds")
        return p

    p = common(sub.add_parser("run-open", help="record the run's opening"), handoff=False)
    p.add_argument("--session", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--regime", required=True, choices=("single", "multi"))
    p.add_argument("--regime-src", required=True, choices=("owner", "head"))
    p.add_argument("--handoff", required=True)
    p.add_argument("--detail", required=True)
    p.add_argument("--pid", type=int, default=None, help="the head's pid (default: parent walk)")
    p.add_argument("--envelope-usd", type=float, default=None)
    p.add_argument("--expect-items", default=None, metavar="ITEM=TOKENS,...",
                   help="the pre-flight's expected memory cost per item (item0=40k,item1=90000,...), "
                        "recorded on the run-open event and read by the gate's fit estimate; a later "
                        "`expect` event overrides it")
    p.add_argument("--session-kind", choices=SESSION_KINDS, default="head",
                   help="seed: a launcher's placeholder session that never runs, written as "
                        "session_kind on the run-open event; the waste table and the meter skip "
                        "it rather than reading it as a head that spent nothing (default: head)")
    grants(p)
    network_flag(p)

    p = common(sub.add_parser("run-resume", help="a later head records itself"), handoff=False)
    p.add_argument("--session", default="auto", help="session id, or auto (the last head-successor's)")
    p.add_argument("--head", required=True)
    p.add_argument("--detail", required=True)
    p.add_argument("--pid", type=int, default=None)
    two_heads(p)
    grants(p)

    p = common(sub.add_parser("boundary", help="meter, waste fields, event, trace row, figures, commit"))
    p.add_argument("--from", dest="from_", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--disposition", required=True)
    p.add_argument("--waste", required=True, help="the three classes, free text")
    p.add_argument("--next", required=True)
    p.add_argument("--commit", default=None, metavar="MSG", help="checkpoint commit in the vault")
    p.add_argument("--shipped", default=None)
    p.add_argument("--waits", default=None)
    p.add_argument("--saving", default=None)
    p.add_argument("--meter-line", default=None, help="a billed line already in hand (skips the meter)")

    p = common(sub.add_parser("expect", help="declare the expected memory cost per item "
                                             "(item0=40k,item1=90000): an expect-items event "
                                             "the gate's fit estimate reads, overriding run-open"))
    p.add_argument("--items", required=True, metavar="ITEM=TOKENS,...")
    p = common(sub.add_parser("ledger", help="one findings-ledger row plus an observation, or "
                                             "--observation alone on any record"))
    # The four are required together (cmd_ledger refuses a partial set by name); they are not
    # argparse-required, because --observation is a complete call on its own.
    p.add_argument("--phase", default=None)
    p.add_argument("--what", default=None)
    p.add_argument("--evidence", default=None)
    p.add_argument("--routing", default=None)
    p.add_argument("--observation", default=None, metavar="WHAT",
                   help="append one observation event and NO hand-off row, to any record that "
                        "exists: the form a record with no run-open (a plain lane run) takes, "
                        "and a head's aside on a record that has one. --phase is optional")

    p = common(sub.add_parser("gate", help="band and envelope check before an item: exit 4 on "
                                           "the band stop, 5 on the envelope stop (the run's "
                                           "spend has reached its envelope: the latest "
                                           "raise-envelope figure, else run-open's "
                                           "envelope_usd), 6 held by the decisions channel, 7 "
                                           "on the second consecutive unmetered gate, 9 when "
                                           "another live head holds the run"),
               handoff=False)
    p.add_argument("--to", required=True, metavar="ITEM")
    p.add_argument("--phase", default="", help="for the observation on an unmetered gate")
    p.add_argument("--meter-line", default=None,
                   help="a billed line in hand for the envelope remainder (skips the meter)")
    decisions_channel(p)
    two_heads(p)

    p = common(sub.add_parser("raise-envelope", help="the owner's top-up: an envelope event the "
                                                     "gate, the successor and the supervisor "
                                                     "read as the run's envelope"),
               handoff=False)
    p.add_argument("--to", required=True, type=float, metavar="USD")
    p.add_argument("--reason", required=True)
    p.add_argument("--meter-line", default=None,
                   help="a billed line in hand for this session's spend (skips the meter)")

    p = common(sub.add_parser("decision", help="an owner-behalf decision before the act: the "
                                               "decision event and one findings-ledger row"))
    p.add_argument("--phase", required=True)
    p.add_argument("--what", required=True)
    p.add_argument("--grant", required=True, help="the grant the decision is taken under")
    p.add_argument("--routing", default="no action",
                   help="the ledger row's routing (default: no action)")

    p = common(sub.add_parser("handoff", help="rewrite named sections or bullets; --final records head-exit"))
    p.add_argument("--inflight", default=None)
    p.add_argument("--inflight-file", default=None)
    p.add_argument("--inflight-from-record", action="store_true",
                   help="derive '## In flight' from the run record (the last boundary's next, "
                        "the lanes open since it, the decisions since it) instead of taking a "
                        "pack: the pack-age guard's own rewrite, as a command")
    p.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="bullets: %s; sections: %s" % (", ".join(sorted(BULLETS)), ", ".join(sorted(SECTIONS))))
    p.add_argument("--set-file", action="append", metavar="KEY=PATH")
    p.add_argument("--final", action="store_true", help="record head-exit; needs the next-task pack (D41)")
    p.add_argument("--band", default=None, help="the band edge crossed, unmetered, limit or error (default: measured)")
    p.add_argument("--pid", type=int, default=None)
    p.add_argument("--meter-line", default=None, help="a billed line in hand for head-exit's spent_usd (skips the meter)")

    def head_options(p):
        p.add_argument("--model", default=None)
        p.add_argument("--effort", default="max", help="effort for the head (default max; the owner's head rule)")
        p.add_argument("--config-dir", default=None, help="optional; unused by default (single account, D28)")
        p.add_argument("--harness-bin", default=HARNESS, help="the harness binary (a suite substitutes a stub)")
        return p

    p = common(sub.add_parser("successor", help="record head-exit, start the detached starter (which supervises); returns at once"))
    head_options(p)
    p.add_argument("--budget-usd", type=float, default=None, help="default: the envelope's remainder (N5)")
    p.add_argument("--predecessor-pid", type=int, default=None)
    p.add_argument("--band", default=None)
    p.add_argument("--pid", type=int, default=None)
    p.add_argument("--wait-s", type=int, default=STARTER_WAIT_S, help="the predecessor-pid wait's bound")
    p.add_argument("--pack-fresh", action="store_true",
                   help="the launcher's word that the hand-off's '## In flight' is current: "
                        "records an observation pack-fresh, so the starter does not re-derive it")
    supervision(p)

    p = common(sub.add_parser("_starter", help="internal: the detached starter and supervisor"))
    head_options(p)
    p.add_argument("--viewer-opened", action="store_true",
                   help="internal: the caller (successor) ran the console opener before the "
                        "detach, so the first head start opens nothing")
    p.add_argument("--budget", type=float, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--wait-s", type=int, default=STARTER_WAIT_S)
    p.add_argument("--transcript", default="")
    p.add_argument("--predecessor-pid", type=int, default=None)
    supervision(p)

    p = common(sub.add_parser("supervise", help="attach the supervisor to a running head (the head calls it about itself); detaches at once"))
    head_options(p)
    p.add_argument("--pid", type=int, default=None, help="the head's pid (default: the nearest claude ancestor)")
    p.add_argument("--out", default=None, help="the head's .out (default: the record's, else the newest, else none)")
    p.add_argument("--budget-usd", type=float, default=None, help="the cap in hand when the meter cannot size the remainder")
    p.add_argument("--wait-s", type=int, default=STARTER_WAIT_S, help="how long a head-exit may wait for its head-successor")
    p.add_argument("--stop", action="store_true",
                   help="write the supervisor's stop marker and exit: a sleeping supervisor stands down at its next tick (D43)")
    supervision(p)

    p = common(sub.add_parser("_supervise", help="internal: the detached supervisor"))
    head_options(p)
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-usd", type=float, default=None)
    p.add_argument("--wait-s", type=int, default=STARTER_WAIT_S)
    supervision(p)

    p = common(sub.add_parser("resume-head", help="after a limit the run stood down on (D42): resume the record's last head in place — armed, evented, supervised; detaches at once"))
    head_options(p)
    p.add_argument("--out", default=None, help="the head's .out (default: the record's, else the newest)")
    p.add_argument("--budget-usd", type=float, default=None, help="the cap in hand when the meter cannot size the remainder")
    p.add_argument("--wait-s", type=int, default=STARTER_WAIT_S)
    p.add_argument("--pack-fresh", action="store_true",
                   help="the launcher's word that the hand-off's '## In flight' is current "
                        "(records an observation pack-fresh), as for successor")
    supervision(p)

    p = common(sub.add_parser("_resume-head", help="internal: the detached resume-head"))
    head_options(p)
    p.add_argument("--viewer-opened", action="store_true",
                   help="internal: the caller (resume-head) ran the console opener before the "
                        "detach, so the resumed start opens nothing")
    p.add_argument("--session", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-usd", type=float, default=None)
    p.add_argument("--wait-s", type=int, default=STARTER_WAIT_S)
    supervision(p)

    p = common(sub.add_parser("heartbeat", help="an attended head's idle-cache beat (D32): a background call"), handoff=False)
    p.add_argument("--minutes", type=float, default=HEARTBEAT_MINUTES)
    p.add_argument("--stop", action="store_true", help="write the stop marker and exit")
    p.add_argument("--parent-pid", type=int, default=None, help="end quietly when this pid is gone (default: the parent)")
    p.add_argument("--tick-s", type=float, default=HEARTBEAT_TICK_S, help="the sleep tick (a suite shortens it)")

    p = common(sub.add_parser("grants", help="rewrite the run's grants file and run-<sid> pointer (N7)"), handoff=False)
    grants(p)
    network_flag(p)

    p = common(sub.add_parser("wait-reset", help="the reset wait as a command, for --dry-run checks and a hand-run "
                              "wait: blocks at most --max-block-s and re-issues on `still-running` (exit 8)"),
               handoff=False)
    p.add_argument("--stop-text", default=None)
    p.add_argument("--stop-file", default=None)
    p.add_argument("--reset-at", default=None, metavar="HH:MM|+Ns|ISO")
    p.add_argument("--probe", action="store_true", help="opt in to a $0.05 haiku probe every --probe-interval-s until one succeeds; OFF by default (owner ruling 2026-09-06): without it an unparsed reset records stop-condition limit-unparsed and ends (exit 7), the hand-off being the recovery; a limit scoped to one model records limit-model and ends the same way, with or without the flag")
    p.add_argument("--config-dir", default=None, help="optional; unused by default (single account, D28)")
    p.add_argument("--probe-interval-s", type=int, default=PROBE_INTERVAL_S)
    p.add_argument("--max-wait-s", type=int, default=8 * 3600, help="give up (exit 7) past this, from the wait's start")
    p.add_argument("--max-block-s", type=int, default=MAX_BLOCK_S, help="one call blocks at most this long")
    p.add_argument("--lane", default="", help="the lane the limit stopped, for the stop-condition event")
    p.add_argument("--harness-bin", default=HARNESS)

    def window_meter(p):
        p.add_argument("--no-meter", action="store_true",
                       help="render the whole-run rows from the record alone: no meter call "
                            "(the pre-2026-09-07 behaviour, for a caller with no transcripts)")
        p.add_argument("--meter-line", action="append", default=[], metavar="SID=LINE",
                       help="a billed line already in hand for one head session (repeatable), "
                            "used in place of metering that head over the run's window")
        return p

    p = common(sub.add_parser("waste-table", help="render Step 2b's waste table from the run "
                              "record, the whole-run rows metered over the run's window (D36)"),
               handoff=False)
    p.add_argument("--out", default=None, metavar="PATH",
                   help="default: <store>/spawn-records/<run>-waste-table.md")
    window_meter(p)

    p = sub.add_parser("extract-transcript", help="the head's own transcript extracted for a "
                       "reflector lane: human turns and assistant prose (D36)")
    p.add_argument("--session", required=True, metavar="SID")
    p.add_argument("--out", default=None, metavar="DIR",
                   help="default: /tmp/aimyth-extract-<sid>/")
    p.add_argument("--projects-root", default=None, metavar="P",
                   help="default: AIMYTH_PROJECTS_DIR, else ~/.claude/projects")
    p.add_argument("--notification-re", action="append", default=[], metavar="REGEX",
                   help="an extra injected-user-record marker, matched at the start (repeatable)")

    p = sub.add_parser("watch", help="the read-only console: --run for a hands-off run (header, "
                       "items, lanes, timeline, feed) or --session for an attended session's "
                       "background jobs; q quits, r resumes a stopped head (writes only the "
                       "timeline report at the close, and the per-suite totals cache)")
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--run")
    what.add_argument("--session", metavar="SID",
                      help="a transcript stem, or a unique prefix of one: the background-job view")
    p.add_argument("--once", action="store_true")
    p.add_argument("--plain", action="store_true")
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--refresh", type=float, default=None)
    p.add_argument("--vault", default=None)
    p = sub.add_parser("reflect-inputs", help="the P4 boundary reflection's whole input set in "
                       "one directory for a blind reflector lane (D36)")
    p.add_argument("--run", required=True, help="run id (the record's file stem)")
    p.add_argument("--session", required=True, metavar="SID")
    p.add_argument("--out", required=True, metavar="DIR",
                   help="the reflector lane's own directory: never inside the run store or the "
                        "projects root, which the lane is not granted")
    p.add_argument("--projects-root", default=None, metavar="P",
                   help="default: AIMYTH_PROJECTS_DIR, else ~/.claude/projects")
    p.add_argument("--notification-re", action="append", default=[], metavar="REGEX",
                   help="an extra injected-user-record marker, matched at the start (repeatable)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the counts and what would be written; write and record nothing")
    window_meter(p)

    p = common(sub.add_parser("close", help="final meter, run-close, commit and push on grant"))
    p.add_argument("--commit", default=None, metavar="MSG")
    p.add_argument("--push", action="store_true")
    p.add_argument("--items", default="unstated")
    p.add_argument("--register", default="unstated")
    p.add_argument("--log", default="unstated")
    p.add_argument("--lint", default="unstated")
    p.add_argument("--parity", default=None)
    p.add_argument("--meter-line", default=None)
    p.add_argument("--report", default=None, metavar="PATH",
                   help="the run report page, written before the close: the close re-reads the "
                        "record and adds or replaces one bullet under its '## Spend' section "
                        "(the closing meter line) and one under its '## Warnings' section (every "
                        "limit stop on the record), before the commit; a PATH that is not a file "
                        "is refused, a missing section exits 3")
    decisions_channel(p)

    p = common(sub.add_parser("run-is-closed", help="exit 0 when the record carries a run-close, "
                                                    "1 when it does not, 2 with no record"),
               handoff=False)

    p = common(sub.add_parser("launch-check", help="the launch kit's start confirmation: poll "
                                                   "the record to a deadline for a head start "
                                                   "whose pid is alive and verified (its age "
                                                   "and the event's timestamp both read); exit "
                                                   "0 started, 1 not started (the deadline, an "
                                                   "unverifiable pid, a run-close, an "
                                                   "aborted starter, a dead head, a reused pid), "
                                                   "2 on a premise (no record, or run inside the "
                                                   "run's own head without --detach-safe)"),
               handoff=False)
    p.add_argument("--wait", type=int, default=LAUNCH_CHECK_WAIT_S, metavar="S",
                   help="the deadline in seconds from the check's start (default %d: a seed "
                        "launch starts its head at once; a head-called successor's starter "
                        "first waits for its predecessor up to --wait-s, so pass more than that "
                        "there); 0 is one read. Every ps probe of every read draws on this one "
                        "budget, bounded by the lower of its own cap and what is left of it"
                        % LAUNCH_CHECK_WAIT_S)
    p.add_argument("--poll-s", type=float, default=LAUNCH_CHECK_POLL_S, metavar="S",
                   help="how often the record is re-read (default %.0f s: the bound on how long "
                        "after the starter's append the check sees the line, set by judgement; "
                        "a suite shortens it)" % LAUNCH_CHECK_POLL_S)
    p.add_argument("--detach-safe", action="store_true",
                   help="run even where the check reads as inside the run's own head "
                        "(AIMYTH_HANDSOFF=1, the head's pid among this shell's ancestors, or "
                        "the session marker under a harness process): only when this shell is "
                        "NOT the head the starter waits for")

    p = common(sub.add_parser("open-console", help="the run's console window on demand, one "
                                                   "when none is alive; --check prints the live "
                                                   "console's pid or NO CONSOLE (exit 1)"),
               handoff=False)
    p.add_argument("--check", action="store_true",
                   help="open nothing: print the pid(s) of the run's live console (exit 0) or "
                        "NO CONSOLE (exit 1)")
    p.add_argument("--viewer", choices=VIEWER_VALUES, default=None,
                   help="terminal or none for this call alone (default: the grants file's key)")

    p = common(sub.add_parser("run-spend", help="the run's spend BY RUN, the figure the gate, the "
                                                "boundary and the close compare with the "
                                                "envelope: every head session metered alone plus "
                                                "every lane on the record; exit 1 when the figure "
                                                "is a floor (something could not be metered)"),
               handoff=False)
    p.add_argument("--meter-line", default=None,
                   help="a billed line in hand for the current head (its `head $` is taken)")
    p.add_argument("--no-cache", action="store_true",
                   help="neither read nor write the per-session meter cache beside the record")
    p.add_argument("--budget-s", type=int, default=RUN_SPEND_BUDGET_S,
                   help="wall-clock budget for the meter calls (default %d s; a session left "
                        "unmetered by it is named and the figure is a floor)" % RUN_SPEND_BUDGET_S)

    p = common(sub.add_parser("hold", help="keep a finished lane warm (the held lanes): a hold "
                                           "event the supervisor services with a no-work beat "
                                           "through the lane's own wrapper %d s after its "
                                           "last call; ends at --cap beats unless renewed"
                                           % HOLD_BEAT_S),
               handoff=False)
    p.add_argument("--lane", required=True, help="the lane id; its latest close must be one a "
                                                 "beat re-enters (%s)" % ", ".join(HOLDABLE_EXITS))
    p.add_argument("--cap", type=int, default=None,
                   help="beats the hold allows before it ends (default %d, at most %d); with "
                        "--renew, the fresh count's cap" % (HOLD_CAP_DEFAULT, HOLD_CAP_MAX))
    p.add_argument("--renew", action="store_true",
                   help="extend an open hold: a new hold event with a fresh beat count")
    p.add_argument("--beat-after-s", type=int, default=HOLD_BEAT_S,
                   help="seconds after the lane's last call at which a beat falls due (default "
                        "%d, the cache tier less ten minutes; 1 to %d, the resume window, past "
                        "which the cache has lapsed); the rehearsal of the next hands-off "
                        "run uses the default, so a shorter value is for a suite or a check by "
                        "hand"
                        % (HOLD_BEAT_S, HOLD_WINDOW_S))
    p = common(sub.add_parser("release", help="end a lane's hold by hand: hold-ended released"),
               handoff=False)
    p.add_argument("--lane", required=True)

    p = common(sub.add_parser("hold-verdict", help="what each held-lane beat did to the cache, "
                                                   "read from the record alone (read-only): hit "
                                                   "when the cached read is at least %.2f of the "
                                                   "call's whole input, rewrite when the uncached "
                                                   "part is, else open with the figures; the "
                                                   "fraction is the closing meter's own. Exit 0 "
                                                   "every beat hit, 1 any rewrite, 2 any open or "
                                                   "no beat at all" % HOLD_VERDICT_FRACTION),
               handoff=False)
    p.add_argument("--lane", default=None, help="one lane's beats (default: every lane's)")
    p.add_argument("--format", choices=("text", "json"), default="text")

    a = ap.parse_args()
    handlers = {"run-open": cmd_run_open, "run-resume": cmd_run_resume, "boundary": cmd_boundary,
                "ledger": cmd_ledger, "gate": cmd_gate, "handoff": cmd_handoff, "expect": cmd_expect,
                "successor": cmd_successor, "_starter": cmd_starter,
                "supervise": cmd_supervise, "_supervise": cmd_supervise_internal,
                "resume-head": cmd_resume_head, "_resume-head": cmd_resume_head_internal,
                "heartbeat": cmd_heartbeat, "grants": cmd_grants,
                "wait-reset": cmd_wait_reset, "close": cmd_close,
                "waste-table": cmd_waste_table,
                "extract-transcript": cmd_extract_transcript,
                "reflect-inputs": cmd_reflect_inputs, "watch": cmd_watch,
                "raise-envelope": cmd_raise_envelope, "decision": cmd_decision,
                "run-is-closed": cmd_run_is_closed, "run-spend": cmd_run_spend,
                "launch-check": cmd_launch_check, "open-console": cmd_open_console,
                "hold": cmd_hold, "release": cmd_release,
                "hold-verdict": cmd_hold_verdict}
    sys.exit(handlers[a.cmd](a) or 0)


if __name__ == "__main__":
    main()
