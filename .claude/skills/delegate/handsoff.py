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
  run-resume   a later head records itself likewise: every head the starter starts (the fixed
               resume instruction sends each one here before any item work, the run's first
               after a seeded launch included) or a head on a pasted resume prompt; the session
               meter counts the helpers spawned after it as that head's. It writes the same two
               files (a list it is not given is carried from the file);
               refused with exit 9 while another live head holds the run (two heads, below)
  boundary     meter, compute the five waste fields, measure the head's context, append the
               phase-boundary event, add the trace row, re-derive `## In flight` from the record,
               refresh the morning report's figures, list the vault root's untracked entries and
               checkpoint-commit (--commit MSG); the disposition's HD-<n> references are checked
               against the record's decision events (the fixes of 2026-10-10 below)
  item-done    an explicit completion record for each item named, with no meter, for items worked
               side by side, which one boundary's from and to fit badly; refused on a closed run
  ledger       one row in the hand-off's findings ledger plus an observation event; a
               `## Findings ledger` section that holds prose and no table gets the table
               created directly under its heading first, the prose kept below it, and one line
               says so (as `decision` does; register entry 2026-09-14 19:35); a hand-off with no
               such heading, two such headings
               (whether or not the first holds a table; both lines named), or pipe-led lines
               that make no table is refused as before (exit 2, nothing written);
               `--observation "<what>"` instead appends the observation alone, with no ledger
               row, to any record, creating it for a run that has none yet (the plain-lane-run
               shape below, before its first spawn)
  decision     an owner-behalf decision before the act: the `decision` event (phase, what,
               grant) and one findings-ledger row in one call, the decision's identifier HD-<n>
               printed for the disposition that acts on it to name (the decision subcommand below)
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
  decisions-read
               read-only: the decisions file's lines no accepted ack has covered (all of it when
               no ack on the record carries a digest) and the file's sha256, which the next --ack
               passes as --ack-digest (the decisions channel below); on a head with no ack of its
               own it prints the whole file, and it takes the file from the record once bound
  decisions-ack
               the acknowledgement between gates, which a held spawn asks for; shares decisions_hold
               (the decisions channel below)
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
               `## In flight` from the run record (the pack-age guard below). With no
               successor left on the run's cap, --final writes the pack it was given and NO
               head-exit, and exits 10 (the hand-over checks below)
  successor    called BY the exiting head: sizes the cap from the envelope minus recorded spend
               when the record's last head-exit is a seed exit (`budget_src: envelope (seed)`,
               register entry 2026-09-07, since a seed session has no transcript to meter);
               records head-exit when missing (refused while a head-successor follows the
               last head-exit; where the supervisor's `head exited` observation follows that
               head-successor with no head-exit after it, an older record, the refusal names
               the missing head-exit and the repair `handoff --final --band limit`), then
               starts a
               DETACHED starter that waits for the predecessor to die, starts the successor
               head (claude -p, the fixed resume instruction on standard input, never the
               hand-off's `## Resume prompt`, which is the owner's) and stays as its
               supervisor (D30); returns at once. A launcher-supplied pid that is the caller's
               own long-lived ancestor is refused, and a seed predecessor with no pid is not
               waited on (the seed pid below); --pack-fresh records the launcher's word that
               the hand-off is current (the pack-age guard below). Otherwise the cap is the
               envelope minus the run's spend, the gate's and the close's figure; --seed-pid hands
               the starter a seed process that exits SEED_PID_S after the call, for an attended
               head whose own process does not exit at the end of a reply; the head runs on
               --model, else the newest head start's model on the record, and a record that names
               none is refused (the fixes of 2026-10-10 below). With no successor left on the
               run's cap it refuses before the model, the meter and any head-exit (exit 10), and
               it names each background task the calling head's own process still runs beside
               the call, the call going on (the hand-over checks below)
  supervise    attach the same supervisor to a head already running (the head calls it about
               itself); detaches at once and returns one line
  resume-head  after a limit the run stood down on (D42): resume the record's last head in
               place, armed, evented and supervised (the owner's command after the reset);
               detaches at once; --pack-fresh, the model and its refusal as for successor
  watch        the read-only console for a run: header, items, lanes, timeline, feed; `q` quits
               and `r` resumes a stopped head. Writes only the timeline report, at the close
  heartbeat    an attended head's idle-cache beat (D32): a background call that returns after
               --minutes with one line, so the harness's re-invocation refreshes the cache;
               never for a -p head, which has no idle state, and refused (exit 2, nothing
               armed) under AIMYTH_HANDSOFF=1, which every head the starter starts carries
  wait-reset   the supervisor's reset wait as a command, kept for --dry-run parser checks and
               for a hand-run wait; no longer a head-side blocking call (D28). It sleeps to the
               reset time the stop text names and sends no probe unless --probe is passed
  close        final meter, run-close, the heartbeat stop marker, commit and push on grant; on a
               plain record (below) the run-close is written from the lane events alone;
               decisions_on_owner_behalf counts the `decision` events and the ledger
               observations whose what opens with the word decision; held with exit 6 by the
               decisions channel as gate is, the file read once more just before the first write
               (below); --items is required unless --dry-run, and an absent --register, --log or
               --lint is noted on stderr; it lists each started item with no completion record
               before it writes and carries them as `items_unresolved`, converting none; once
               run-close is written the run's arming markers are removed (disarm)
  disarm       after the close: remove the arming marker armed-<sid> of every head session the
               run names whose pointer run-<sid> still names this run, a marker another run owns
               or whose pointer cannot be read left in place; refused on a run with no run-close
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
               waits for that head to exit); --lanes A,B,… also requires every planned
               first-batch helper to have opened and to show activity after its open, or to have
               closed completed: exit 0 STARTED CLEAN, 1 NOT CLEAN (the first batch below); the
               wait keeps the start's terminal states (a run-close, a head-exit, an exited head)
               and holds to one head process: a newer start by its pid moves the anchor, and one
               by another pid or none is verified afresh, certifying nothing until it is; every
               certification reads the clock after its last read or probe, so a start or a first
               batch first seen ready past the deadline is late, never certified
  open-console the run's console window on demand: one when none is alive (the one-window rule
               below); --check opens nothing and prints the live console's pid, or NO CONSOLE
               with exit 1
  run-spend    the run's spend BY RUN (the run figure below): one line per head and per lane
               and a summary line; exit 1 when the figure is a floor, 2 on a premise failure
  waste-table  Step 2b's usage-and-waste table rendered from the run record alone (D36); for
               a closed run with no --out it prints to stdout and leaves the stored table alone
  extract-transcript
               the head's own transcript extracted for a reflector lane (D36)
  reflect-inputs
               that reflector lane's whole input set in one directory: the extraction, the
               waste table and a filtered copy of the run record (D36); a record with no run-open
               is read in its attended form (--session's transcript, or --transcript), and --out
               may be the run's own <store>/stages/<run>/reflect (the fixes of 2026-10-10 below)
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
stripped from every event kept. The drop is legacy: it serves records written before the reflection
controls were retired, when a spawner registered them with `handsoff.py ledger --phase controls-<LANE> …`;
no run records one now. The reflector stays blind to what the head expected of it, and the filtered copy is written before the `reflect-inputs` event that
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
≈ <n>` or `session USD <n>` into the heads' total (2026-09-09 15:43; the row was the run total
until 2026-10-10, when the run total became the run spend the last boundary or close recorded:
register entry 2026-09-20 01:09). The extraction (2026-09-07,
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
`error`. The same loop guards run before every fresh start, the starter's and the supervisor's
alike. `repeat-exit` has two rules. The attempt comparison stops a start when the last two
head-exits, both at band 80 or 90, name the same unfinished item. Each exit's window begins at
its latest head start: allowed items less completed boundaries must leave exactly one item,
and every refused item must have an allowed gate in that window. A completed boundary reached
before any allowed gate, reading backwards, names no item. The no-progress rule stops it
when two heads in turn each exited at band 80 or 90 after a refused gate on the same item, with
no allowed gate and no completed boundary between the two refusals, since a third head would
only be refused again. Accepted residual: heads that repeatedly allow multiple unfinished
items, or re-allow work and refuse an item never allowed in their window, can loop past both
repeat-exit rules; the successor cap and the run's envelope are their only bound. Packed
hand-overs without boundaries also escape repeat-stop; repeat-exit bounds such a chain where
its exits name one item at band 80 or 90, otherwise only the cap and envelope bound it.
`successor-cap` (the run's grants file, then AIMYTH_MAX_SUCCESSORS, then the default of 20) is
the backstop, applied by `handoff --final` and `successor` at call time as well (the hand-over
checks below). A
resume runs only after the process has exited, refuses (duplicate-resume) when a
head-resumed or head-successor already follows this head's start, and is capped at two per
session (RESUME_CAP: a third would-be resume takes the successor path). Two consecutive
stops whose heads each made no progress end in successor-aborted reason repeat-stop, the
successor cap being only the backstop (the repeat-stop design of 2026-10-11, Revision 2, after
its design review). A stop pairs when the supervisor would follow it with an automatic start:
error, budget, completed (a head that exits with neither a head-exit nor a run-close),
unsucceeded without its head's own packed head-exit after its latest start, and any other class
that falls through to the successor path; never limit,
closed, handed-over, classifier-missing, a waiting exit, or a stop the stop marker stood down.
Progress is a phase-boundary written by the stopped head's own process: `boundary` records
caller_pid from the foreground shell command, allowing one session-leading shell directly
below the harness; caller_pid_src is head-command, or null and none for uncertain authorship. A head invocation is
one process: its window opens at the first start event naming its pid after the stop recorded
before its start (a later run-resume by the same process stays inside it; a head-resumed is a
new process and a new window) and closes at its stop. The verdict is computed once, at the
stop, and recorded on the supervisor's `head exited` observation as pid, progress (yes, no or
unknown) and progress_note: yes for a boundary in the window whose caller_pid is that pid;
otherwise unknown when no start event names the pid, a boundary in the window carries no
caller_pid, an unparseable record line lies inside the window (each placed among the events as
they are read, so one written between the start and an attach counts too), or the record's
malformed lines rose while the head was watched; otherwise no. The
guard fires when this stop and the previous recorded stop both pair and both read no; an
observation written without the field reads unknown, unknown never fires, and an abort followed
by a restart resets nothing. A head-exit
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
hand), plus every lane on the record — what its lane-closed costs come to, session by session
(a running total's last figure, never its sum: lane_recorded, the weekly reader's reading), and
where any close of
a Claude lane lacks a cost, the lane is still open, or an open pass follows its last close (a
lane-resumed or a respawn as its latest event), its transcript metered and the LARGER of the
recorded figure and the transcript's figure taken; a lane with two session ids is metered per
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
--on-limit, --viewer or --max-successors alone changes that key alone; a named list replaces the
file's, as before, and a flag-less `run-resume` still leaves the file untouched. run-open, grants
and a rewriting run-resume record both lists on their event. The shrink guard's baseline is the
record's lists whenever the record holds them (the last run-open, grants or rewriting
run-resume event that recorded both), with any path the file adds, whatever the file holds
now: a file already narrowed, by hand or by an older primitive, is never the contract a rewrite
is checked against. With no recorded lists the file's lists are the baseline. Any rewrite that
would lose a path from either list, the read list or the write list, by a call that names a
list or not, prints the delta and refuses (exit 2, nothing written), whether the file is
present, narrowed, missing or unreadable, unless the call passes --replace, the explicit word
that the lists it names replace the run's; that rewrite is written with each list's delta on
stderr (register entry 2026-09-29 20:49: a call naming one extra path replaced a run's whole
write list). --add-grant and --add-write add paths to the baseline's list instead; with no
trustworthy baseline (no recorded lists and a grants file missing or unreadable) an addition
is refused rather than added to the defaults. --grant with --add-grant, --write with
--add-write, --replace with an add form or with no list are refused, and run-open, which writes
the first file, takes neither an add form nor --replace. The file also carries
`max_successors`, the run's successor cap (`run-open --max-successors N`, `grants
--max-successors N` and `run-resume --max-successors N`, a rewrite of that key alone, write
it, refusing a value below 1; every other rewrite carries it; register entry 2026-09-24
07:3x: the cap lived only in a wrapper's environment), which the starter reads before
AIMYTH_MAX_SUCCESSORS and MAX_SUCCESSORS_DEFAULT, naming its source in a refusal; `handoff
--final`, `successor`, `gate`, `run-resume` and the hard-band hook read the same count through
successors_left; a key this script does not manage is carried through every rewrite.

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
before the successor starts (derive_inflight; register entry 2026-09-25 17:4x: a `Next:` line
from the head's own pack where that pack is newer than the last boundary — carried with that
pack's stamp through every later re-derivation until a newer boundary — else a copy of that
boundary's `next` field, which carries the run's shape as it stood then; every lane still open
on the WHOLE record with its spawn line and its liveness; the `decision` events since the
boundary; every relayed AUTHOR line since the run-open; the replaced pack's hand-written lines
verbatim under their own header — under `- pack re-derived from the record at <ts> (the head's
pack was stale)` and the heading `## In flight (re-derived from the record at <ts>)`, which a
head's own pack resets) and records an observation `what: stale-pack`;
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
point — the furthest the record reached when a call that wrote a `gate` event or an `ack: …`
observation read it, which each records as `decisions_seen` (a relay appended between that read
and the call's own write stays pending, so an ack recorded by a close its recheck then holds
covers nothing it never showed; an event without the field, written before it existed, reaches
its own place, and one whose value is not a whole number from 0 to the count of the events
before it covers nothing, so a relay it would have hidden stays pending until a valid ack), else
its last run-open or run-resume, else its first line — or while `--decisions-file PATH` (no
default) holds content other than what the last accepted ack read (its sha256 and size, on the
ack: keyed on the content, never on an mtime): the held call prints one line per such
observation and the file's unacknowledged lines, and writes nothing. `--ack "<one line naming
what was read>"` with `--ack-digest <sha256>`, the digest `decisions-read` prints, records an
observation `what: ack: <line>` carrying the digest, and the call proceeds; an empty ack, a
digest with no ack or with no decisions file, and a digest that is not a whole sha256 are
refused (exit 2), while an ack with no digest, or with one the file has grown past since its
read, holds again (exit 6), printing the lines appended since. `close` reads the file once more
just before its first write (the owner's provisional choice of 2026-10-10): content changed
since the ack holds that same close, as does an AUTHOR observation anywhere after the record
the call checked (its own ack alone left out), and a close that goes through records
`decisions_file`, `decisions_digest`, `decisions_size`, `decisions_cutoff` and its note on the
run-close: nothing
written to the file after that cutoff is covered. A named decisions file that does not exist is
a premise failure (exit 2), since a mistyped path would never hold. A run's file is bound on its
record, by `run-open --decisions-file` or else by the first gate or accepted ack that names it:
`gate`, `close`, `decisions-read` and both launchers then find it there, and another path that
exists is refused (exit 2). `run-is-closed --run R`
exits 0 on a record with a run-close and 1 on one without (2 with no record), for a wrapper
that warns before it spawns into a closed run.

The decision subcommand (register entry 2026-09-06): the primitive that writes the `decision`
events the close counts, so an owner-behalf decision is never left as a ledger row alone.
`decision --run R --phase P --what … --grant …` writes the `decision` event (phase, what, grant:
the design's trace schema) and one findings-ledger row — What `decision: <what>`, Evidence
`grant: <grant>`, Routing --routing (default `no action`) — in one call, before the act. It
records no observation beside them, and `close` counts the `decision` events plus the
observations whose `what` opens with the word decision (the ledger form heads used before), so
each decision is counted once. Since 2026-10-10 the call assigns the event `decision_id` HD-<n>,
the next free number on the record, under the record's lock, and prints it; `boundary` reads the
HD-<n> identifiers its --disposition names (explicit references, never prose matching: the
owner's provisional choice of 2026-10-10) and warns, its exit unchanged, for one the record
holds no decision for, or two, recording `decision_refs` on its event; an owner decision (D<n>)
is never checked, and a decision described in words and not named is not seen.

Exit codes: 0 done · 2 premise failure (PROBE FAILED, nothing written) · 3 event written but
the hand-off not refreshed (a section is missing: fix the document) · 4 gate refused on the
band (armed) · 7 gate refused on the second unmetered miss (armed), or wait-reset gave up at
--max-wait-s, or wait-reset ended limit-unparsed or limit-model (no reset time and no --probe, or a limit scoped to one model: the hand-off is
the recovery) · 8 wait-reset still running (re-issue the call) · 1 from an internal supervisor
whose run ended in successor-aborted (a stand-down, supervisor-stood-down, exits 0: the
designed default, never an abort) · 5 gate refused on the envelope · 6 gate, close or decisions-ack
held by the decisions channel (re-run with --ack and --ack-digest) · 9 run-resume, gate or
decisions-ack refused while another live head holds the run · 10 handoff --final or successor
refused: no successor left on
the run's cap; nothing started, and handoff --final still wrote the pack · 1 also from
run-is-closed on an open run.

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
The numbers of 2026-10-10: CONSOLE_CONFIRM_HOLD_S 3 s, SEED_PID_S 2 s, NEEDLE_MIN 8 and
NEEDLE_HEAD 40 characters (derived, or named as judgement, beside the constants).
The numbers of 2026-10-30: MAX_SUCCESSORS_DEFAULT 20 (a night run's measured lead length; it
was 6), EXIT_NO_SUCCESSOR 10 (the lowest unused code), STARTER_GONE_TICKS 3 (a pid-waiting
starter's measured 0 to 2 s; unmeasured below the default tick) and SILENCE_POLL_S 5 s
(wait_silent's existing poll), each derived beside the constant.

The hand-over checks (2026-10-30; register entries 2026-10-30 16:11 and 2026-10-25 16:28). The
successor count is one reading, successors_left: the head-successor events on the record against
the run's cap, as the starter's successor-cap guard reads it. `gate` and `run-resume` print it on
every line ("successors: k of N started, M left"), and the gate event records it. `handoff
--final` and `successor` apply the starter's own test before either writes a head-exit, and
again under the record's lock just before the append: with none left each exits 10 and records
one observation (`handoff --final refused: no successor left`, `successor refused: no successor
left`), `handoff --final` still writing the pack, so the run's last lead stays the lead and
closes the run with its morning report; a gate refusal with none left says close the run rather
than hand over. A cap that falls back past a grants file whose own cap cannot be read
(unreadable, not a JSON object, an unusable value) is named as that fault, with how to recover
the cap, and whether the run's last lead has come is then undecided; a readable grants file with
no cap key is a run that set none, and its fallback is the decided cap. `successor` reads the
process table once and names each session-leading shell child of the calling head's own process
other than its own shell: a background task, which keeps a print-mode head alive after its last
reply; the call goes on, and "none" is printed only when the same read showed the call's own
shell there (the control); a process chain it cannot walk whole is undecided, never none. The
supervisor's wait on an `unsucceeded` stop shrinks to STARTER_GONE_TICKS ticks once the head's
own starter has aborted and a re-called starter would wait on a pid (SILENCE_PROXY_S +
SILENCE_POLL_S + a tick when it would wait for silence), and the starter's timeout note names the
head's own process and its shell children. At the hard band the hook `handsoff-gate.py` admits
TaskStop and `handsoff.py close` for the run's last lead alone (no successor left on a decided
cap, and the calling session the record's current head), through last_lead_state; when that
cannot be read its deny stands (the owner's decision of 2026-10-30).

The fixes of 2026-10-10 (the register entries each names). The run figure (run_spend) is a floor
while any lane still runs — no close yet, or an open pass after its last close — and a closed lane
whose every close is priced is still metered from its transcript, the larger figure taken, so the
figure never falls while a lane spends (2026-09-30 03:21). `successor` and the supervisor size the
next head on the envelope minus that same figure, as the gate and the close read it (2026-09-26
02:2x). The head's model is structured on every head start (`model`, `model_src`): `run-open
--model` records the launch's, `successor` and `resume-head` take --model or the newest start's,
the supervisor's own successor start passes its head's, and a start with none is refused before
any process (2026-09-23 12:5x); `launch-check` refuses to certify a head start with no readable
model, reading a run-resume's from the start naming its session. The starter's
first line names every lane open on the record and its liveness (2026-09-24 00:4x). The first
batch (owner decision D21 (c) of 2026-10-10): `launch-check --lanes` reads each planned helper's
latest attempt since the confirmed head start — `missing`, `opening`, `silent`, `progressing`,
`done`, `failed` or `unverified` — and progress is observable activity after the open, a
LAUNCH_LANE_ACTIVITY record event or a transcript or session-file record stamped after it, never a
live process alone. The console probe reads pgrep's exit status (a sighting is exit 0 with a pid;
any other status confirms nothing) and its pattern counts `--run R` anywhere after watch.py or
`handsoff.py watch` (2026-09-22 19:03); a console first seen is confirmed only if a successful
probe still finds it CONSOLE_CONFIRM_HOLD_S later, and one gone by then is reported
started-then-exited with the by-hand line and not retried (2026-09-20 01:48); every command handed
on names the absolute interpreter (interpreter(), 2026-09-30 17:36). A console lock that cannot be
worked (any errno but EWOULDBLOCK or EAGAIN) is named and not taken, never read as contention
(2026-09-18 20:0x). The extraction counts compaction summaries and cross-session lines out of the
human turns, keeps a mid-turn owner message the harness queued as an attachment, names every
tool's main field and shows a newline in a call as ` ⏎ ` (2026-09-13 03:53, 2026-10-02 06:19);
reflect-inputs reads an attended record (no run-open) from --session's transcript or --transcript
(2026-09-26 03:5x), writes into the run's own <store>/stages/<run>/reflect when asked (2026-09-17
21:08), and withholds any extraction line that names a control a legacy record holds, matched before a
tool line is cut and across a turn's line breaks, so a wrapped control goes with every line it
touches (2026-10-11). The waste table's
limit waits end at the first head start after the stop (2026-09-24 13:1x), its run total is the
run spend the last boundary or close recorded (2026-09-20 01:09), and a closed run's table is
printed rather than rewritten (2026-10-03 07:48); the boundary records the lanes' fence and
sandbox denials beside the head fence's (2026-10-02 16:42). `ledger --observation` creates a
missing record (2026-09-19 02:55); `close` requires --items (2026-09-20 02:12) and removes the
run's arming markers after its run-close, which `disarm` repeats (2026-09-30 18:48); `heartbeat`
refuses a head under AIMYTH_HANDSOFF=1 (2026-09-25 18:2x).
Every --dry-run prints what would be written and writes nothing.
"""
import sys
sys.dont_write_bytecode = True   # the hook import must never leave bytecode in the vault
import argparse
import calendar
import collections
import contextlib
import functools
import errno
import glob as globmod
import hashlib
import importlib.util
import json
import math
import os
import re
import shlex
import subprocess
import time
import uuid
import http.client
import urllib.parse

try:
    import fcntl   # record_lock's advisory lock; absent off POSIX, where no lock is taken
except ImportError:
    fcntl = None

HEAD_EVENTS = ("run-open", "run-resume", "head-exit", "head-successor")
SESSION_EVENTS = ("run-open", "run-resume", "head-successor")   # each names the head's session
START_EVENTS = SESSION_EVENTS + ("head-resumed",)   # each starts a head process the supervisor owns
HEAD_EFFORT_DEFAULT = "max"   # the owner's head rule of 2026-09-04, where nothing else names one
# A head at work on an item.
ITEM_WORK_EVENTS = ("decision", "lane-open", "lane-resumed", "phase-boundary")
BOUNDARY_LINE_RE = re.compile(r"handsoff\.py\s+boundary\b|`boundary`")   # the command, never the word
# A typed clock placeholder (register entry 2026-10-15 01:33 d): an hour, a colon, one minute digit
# and x, standing alone; a bracketed register stamp is a heading's name, and is cut out first.
CLOCK_PLACEHOLDER_RE = re.compile(r"(?<![\d:.\-])(?:[01]\d|2[0-3]):[0-5][xX](?![A-Za-z0-9])")
REGISTER_STAMP_RE = re.compile(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d[xX](?: [a-z])?\]")
STAGE_SCAN_FILES = 40           # stage documents read at a boundary: set by judgement, unmeasured
STAGE_SCAN_BYTES = 1000000      # the largest one read: set by judgement, unmeasured
ITEM_DONE_RE = re.compile(r"\b(?:done|passed|closed|complete|completed|finished)\b", re.I)
ITEM_UNDONE_RE = re.compile(r"\b(?:not|never|nearly|almost)\b[^.;]{0,20}\b(?:done|passed|closed|"
                            r"complete|completed|finished)\b", re.I)
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
# wait_silent's poll of the transcript's last write: its existing literal, hoisted unchanged so the
# supervisor's bound on a re-called silence-waiting starter (starter_gone) can name it.
SILENCE_POLL_S = 5
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
# The hand-over refused at the successor cap (register entry 2026-10-30 16:11): `handoff --final`
# and `successor` exit 10 when no successor is left. 10 is the lowest code no subcommand uses:
# 0 to 9 are taken (the docstring's exit codes), and no subcommand exits 10 or above.
EXIT_NO_SUCCESSOR = 10
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
# The record length a call's decisions check read, kept on the ack observation and the gate event
# it writes: what that check covered, which the next call's reference point is (decisions_covered,
# the one reader of it: absent is the legacy reading, a malformed value covers nothing).
DECISIONS_SEEN = "decisions_seen"
# The file a run is bound to, a canonical path on its run-open, a gate or an accepted ack
# (decisions_binding, the one reader): how a launcher, which takes no --decisions-file, finds it.
DECISIONS_FILE = "decisions_file"
# What a held spawn prints of the unread lines, the newest first kept; decisions-read prints them
# all. A burst repeats it once per refused call. Sized from a two-day run's decisions file (median
# line 89 bytes, longest 1,004): 12 median lines take about 1,100 bytes and 4,000 holds about four
# of the longest. The rest is set by judgement, unmeasured.
HOLD_SHOWN_LINES = 12
HOLD_SHOWN_BYTES = 4000
HOLD_REREAD_S = 0.25   # lane.py's ACK_POLL_S: one more look at a torn line; set by judgement, unmeasured
HOLD_TRIAL_PREFIX = "decisions-hold trial: "   # lane.py's trial line, read back to log once a head
PACK_FRESH_WHAT = "pack-fresh"   # the launcher's word that the hand-off is current
TWO_HEADS_WHAT = "two heads"     # the observation a two-heads refusal records
DECISION_WHAT_RE = re.compile(r"^\s*decision\b", re.I)   # a ledger row recording a decision
# The ack digest (IDEAS 171 (b); register entry 2026-09-20 14:29): the decisions file's whole
# sha256, as `decisions-read` prints it and --ack-digest repeats it — 64 hexadecimal characters,
# never a prefix, since a prefix is a weaker claim about the same bytes.
DIGEST_RE = re.compile(r"[0-9a-f]{64}")
# A head decision's stable identifier, which `decision` assigns and a boundary's disposition
# names to say which decision it rests on (register entry 2026-10-05 20:18: decisions recorded
# after the close went unnoticed). `HD-` keeps a head decision apart from an owner decision,
# which the decisions file numbers `D<n>`; only these references are checked, never prose.
HEAD_DECISION_PREFIX = "HD-"
HEAD_DECISION_RE = re.compile(r"(?<![A-Za-z0-9])HD-(\d{1,6})(?![0-9])")
# The successor cap's default when neither the grants file nor AIMYTH_MAX_SUCCESSORS sets one (the
# owner's amendment of 2026-10-30: 6 was too few for a night run). Derived from the night run of
# 29 to 30 October 2026 (register entry 2026-10-30 16:11): its eight leads that handed over ran 36
# to 148 minutes from head start to their own head-exit, 86.8 minutes (1.45 h) on average, so a
# 20-hour run takes about 14 leads (20 / 1.45 = 13.8) and 20 leaves six of headroom; the ninth lead
# closed the run. It stays a backstop: the repeat-exit and repeat-stop guards and
# the envelope are the real bounds, and the call-time check (successors_left) makes the run's last
# lead close the run rather than hand over into nothing. A pre-flight sizes the run's own cap
# (run-open --max-successors N), which the grants file carries and which wins over this default.
MAX_SUCCESSORS_DEFAULT = 20
# `successor --seed-pid` (register entry 2026-09-23 00:5x): an attended head's own process does
# not exit at the end of a reply, so the starter is handed a seed process that exits this many
# seconds after the call instead. Two seconds outlast the call's own return; set by judgement,
# unmeasured. The starter polls a pid once a second (wait_dead), so it starts within ~3 s.
SEED_PID_S = 2
# A recorded pid above this names no process: the platform's pid is a signed 32-bit integer and
# os.kill raises OverflowError past it (measured), so a larger figure is a corrupt record.
PID_MAX = 2 ** 31 - 1
# The bound on one `ps` call (ps_row, process_age_s): the literal every such call carried; set
# by judgement, unmeasured. It is a CAP, never a floor: the launch check cuts each probe to the
# budget left of its deadline (probe_bound), so a 60 s deadline still hands a `ps` call 10 s and
# a 1 s deadline hands it 1 s (critic review pass 2 finding 3).
PS_TIMEOUT_S = 10
# The shells a harness runs a head's shell calls in (head_event_caller's set, hoisted so the
# background-task check of `successor` reads the same one).
SHELLS = ("sh", "bash", "zsh", "dash", "ksh", "fish")
# The supervisor's wait after the head's own starter has already aborted (register entry
# 2026-10-25 16:28): only a starter the head called again could still start a successor, and one
# that waits on a pid wrote its head-successor 0 to 2 s after the predecessor's exit in the four
# clean hand-overs of 29 to 30 October 2026 (polling once a second, wait_dead). Three ticks are
# 180 s at the default 60 s tick, over two minutes of margin; unmeasured below the default tick.
STARTER_GONE_TICKS = 3
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
PACK_REMAINING_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?Remaining:[ \t]*(\d+|\d{1,3}(?:,\d{3})+)"
    r"[ \t]*(k?)(?:[ \t]+tokens)?[ \t]*$", re.M | re.I)
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


# The grants file's keys this script writes itself; any other key a file carries (a setting a
# newer tool wrote) is carried through every rewrite unchanged, never dropped by a rebuild.
MANAGED_GRANT_KEYS = ("run", "grants", "writes", "on_limit", "viewer", "network",
                      "max_successors", "written", "source")


def grants_payload(run, source, grants, writes, on_limit=ON_LIMIT_DEFAULT,
                   viewer=VIEWER_DEFAULT, network=None, max_successors=None, carry=None):
    """The defaults first (critic C1 F2: the head's own primitives are never denied), then the
    paths given, every one in both spellings, de-duplicated in order; `on_limit` is the limit
    gate (D42), `viewer` the console window's key, `network` the hosts the head fence's network
    check allows (an empty list: none) and `max_successors` the run's successor cap (written only
    when set), each carried by this file alone. `carry` is the file's current payload: every key
    of it that this script does not manage is kept as it stands."""
    def merge(paths):
        out = []
        for p in paths:
            for s in spellings(p):
                if s not in out:
                    out.append(s)
        return out
    payload = {}
    if isinstance(carry, dict):
        payload.update((k, v) for k, v in carry.items() if k not in MANAGED_GRANT_KEYS)
    payload.update({"run": run,
                    "grants": merge([vault_given(), store_given(), state_dir(), projects_given(),
                                     lane_home_given(), "/tmp"] + list(grants or [])),
                    "writes": merge([store_given(), state_dir()] + list(writes or [])),
                    "on_limit": on_limit, "viewer": viewer, "network": list(network or [])})
    if max_successors is not None:
        payload["max_successors"] = max_successors
    payload.update({"written": now(), "source": source})
    return payload


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


def on_limit_choice(a, path, current=None):
    """(value, source) the next write of the grants file carries: --on-limit when given, else
    the file's own value carried forward (D42; critic C1 M5: a rebuild must not reset it), else
    the default. `current` is the file's payload where the caller has read it already, so one
    read feeds every key of a plan (grants_plan); absent, the file is read here."""
    chosen = getattr(a, "on_limit", None)
    if chosen in ON_LIMIT_VALUES:
        return chosen, "--on-limit"
    return on_limit_of(read_grants(path) if current is None else current)


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


def viewer_choice(a, path, current=None):
    """(value, source) the next write of the grants file carries: --viewer when given, else the
    file's own value carried forward (a rebuild must not reset it, as for the limit gate), else
    the default. The grants file is this key's only home (D42's rule for on_limit): no second
    file and no environment fallback for the key itself. `current` as for on_limit_choice."""
    chosen = getattr(a, "viewer", None)
    if chosen in VIEWER_VALUES:
        return chosen, "arg"
    return viewer_of(read_grants(path) if current is None else current)


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


def network_choice(a, path, current=None):
    """(hosts, source) the next write of the grants file carries: --network when given, else the
    file's own value carried forward (a rebuild never resets it, as for on_limit and viewer), else
    none. `current` as for on_limit_choice."""
    chosen = getattr(a, "network", None)
    if chosen is not None:
        return parse_network(chosen), "arg"
    return network_of(read_grants(path) if current is None else current)


def network_shown(hosts):
    """The network value on an output line: none, or the hosts comma-separated."""
    return ",".join(hosts) if hosts else NETWORK_NONE


def grants_file_state(path):
    """How the grants file reads, in words, for a refusal that names it: `missing`, `unreadable
    (<why>)`, `not a JSON object` or `readable`."""
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError) as exc:
        return "unreadable (%s)" % one_line(str(exc))[:80]
    return "readable" if isinstance(payload, dict) else "not a JSON object"


def max_successors_of(payload):
    """(cap, source) from a grants payload: the `max_successors` key when it is a whole number of
    at least 1, else (None, why). A file without the key is no cap of its own (register entry
    2026-09-24 07:3x: the cap lived only in a wrapper's environment, so a direct call of this
    script ran under the default and refused a run past its sixth successor)."""
    value = payload.get("max_successors") if isinstance(payload, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value, "grants"
    if not payload:
        return None, "no grants file"
    if value is None:
        return None, "key absent"
    return None, "unusable value %s" % ("%r" % (value,))[:40]


def max_successors_choice(a, path, current=None):
    """(cap, source) the next write of the grants file carries: --max-successors when given (a
    whole number of at least 1, else a premise failure), else the file's own value carried
    forward, as on_limit and viewer are, else none. `current` as for on_limit_choice."""
    chosen = getattr(a, "max_successors", None)
    if chosen is not None:
        if isinstance(chosen, bool) or not isinstance(chosen, int) or chosen < 1:
            die("--max-successors must be a whole number of at least 1, got %r" % (chosen,))
        return chosen, "arg"
    return max_successors_of(read_grants(path) if current is None else current)


def grants_cap_read(path):
    """(payload, state) from ONE read of the grants file, for the successor cap: the payload ({}
    unless the file holds a JSON object) and the file's state in words — `missing`, `unreadable
    (<why>)`, `not a JSON object`, `readable, no max_successors key`, `readable, unusable
    max_successors value …`, or `readable` when the key holds a usable cap. read_grants returns
    {} for a readable `{}` and for an unreadable file alike; this names each as it is."""
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {}, "missing"
    except (OSError, ValueError) as exc:
        return {}, "unreadable (%s)" % one_line(str(exc))[:80]
    if not isinstance(payload, dict):
        return {}, "not a JSON object"
    return payload, cap_state_of(payload)


def cap_state_of(payload):
    """A grants payload's cap state in grants_cap_read's words — `readable, no max_successors
    key`, `readable, unusable max_successors value …` or `readable` — for a payload in hand: the
    file as read, or the payload a dry run would write (successor_cap_read's `planned`)."""
    if "max_successors" not in payload:
        return "readable, no max_successors key"
    if max_successors_of(payload)[0] is None:
        return "readable, unusable max_successors value %s" % (
            "%r" % (payload["max_successors"],))[:40]
    return "readable"


# The grants file states in which its own cap cannot be read although the file is there: the file
# unreadable, not a JSON object (no grants payload is ever written so), or its max_successors value
# unusable. A cap that falls back past such a file is not the run's decided cap
# (successor_cap_read's `fault`), so whether the run's last lead has come is undecided. A readable
# file with NO max_successors key is not among them: grants_payload writes the key only when a cap
# is set, so a keyless file is a run that set no cap, and the fallback (AIMYTH_MAX_SUCCESSORS, else
# MAX_SUCCESSORS_DEFAULT) is its decided cap (build review RV-CAP finding F5).
CAP_FAULT_STATES = ("unreadable", "not a JSON object", "readable, unusable")
CAP_OWN_SRC = "the grants file %s"   # the cap's source when the run's grants file carries it


def successor_cap_read(run, planned=None):
    """(cap, source, fault) for the run's successor cap: the run's grants file first (the key
    `run-open --max-successors` and `grants --max-successors` write), then AIMYTH_MAX_SUCCESSORS,
    then MAX_SUCCESSORS_DEFAULT; the source names which, and a fallback names the grants file's
    real state (grants_cap_read). `fault` is that state when the file is present but its cap
    cannot be read — unreadable, not a JSON object, or an unusable max_successors value — else
    None: the number is the starter's either way, but a fallback past a faulty file is not the
    run's decided cap, so the call-time checks name the fault, say the last-lead question is
    undecided, and the hard-band hook denies (review CR-CAP2 finding 6). A missing file and a
    readable file with no key are no fault: grants_payload writes the key only when a cap is set,
    so such a run set no cap and the fallback is its decided cap (build review RV-CAP finding F5).
    `planned`, a grants payload in hand, is read in the file's place: the count a dry run's
    rewrite would leave, nothing being written. An unusable environment value is named on stderr
    and passed over."""
    path = grants_path(run)
    payload, state = (grants_cap_read(path) if planned is None
                      else (planned, cap_state_of(planned)))
    value, _ = max_successors_of(payload)
    if value is not None:
        return value, CAP_OWN_SRC % path, None
    fault = state if state.startswith(CAP_FAULT_STATES) else None
    raw = os.environ.get("AIMYTH_MAX_SUCCESSORS")
    if raw:
        try:
            n = int(raw)
        except ValueError:
            n = 0
        if n >= 1:
            return n, "AIMYTH_MAX_SUCCESSORS=%d (the grants file: %s)" % (n, state), fault
        note("AIMYTH_MAX_SUCCESSORS=%r is not a whole number of at least 1: passed over" % raw)
    return (MAX_SUCCESSORS_DEFAULT,
            "the default (the grants file: %s; no AIMYTH_MAX_SUCCESSORS)" % state, fault)


def successor_cap(run):
    """(cap, source) for the successor-cap guard (successor_cap_read without its fault)."""
    cap, src, _ = successor_cap_read(run)
    return cap, src


def successors_left(events, run, planned=None):
    """The run's successor count, ONE reading for every caller (register entry 2026-10-30 16:11):
    `handoff --final` and `successor` at call time, `gate` and `run-resume` on every line, the
    starter's and the supervisor's successor-cap guard (start_guards) and the hard-band hook
    (last_lead_state). A dict: `used`, the record's head-successor events (every head start, the
    seeded first lead's included); `cap` and `src`, the run's cap and where it came from
    (successor_cap_read, or the default where no run id names a grants file); `own`, whether the
    run's grants file carries it; `fault`, as successor_cap_read gives it; `left`, cap less used;
    and `run`. `planned` is a grants payload read in the file's place (a dry run's rewrite)."""
    used = sum(1 for e in events if e.get("event") == "head-successor")
    if TOKEN_RE.fullmatch(run or ""):
        cap, src, fault = successor_cap_read(run, planned)
    else:
        cap, src, fault = (MAX_SUCCESSORS_DEFAULT,
                           "the default (no run id to read a grants file)", None)
    return {"used": used, "cap": cap, "src": src, "left": cap - used, "fault": fault,
            "own": src.startswith(CAP_OWN_SRC % ""), "run": run}


def successors_clause(s):
    """The count as every gate, run-resume and hand-over refusal prints it: the short form when
    the run's grants file carries the cap (`successors: 8 of 14 started, 6 left`), the source in
    full for a fallback, the run's-last-lead guidance when none is left, and the file's fault
    instead of that guidance when the cap fell back past a faulty grants file."""
    src = "" if s["own"] else " (%s)" % s["src"]
    head = "successors: %d of %d started" % (s["used"], s["cap"])
    fix = "`handsoff.py grants --run %s --max-successors N` writes the run's cap" % s["run"]
    if s["fault"] and s["left"] <= 0:
        return ("%s, none left on a fallback cap%s — the run's own cap cannot be read from its "
                "grants file, so whether this is the run's last lead is undecided: %s"
                % (head, src, fix))
    if s["left"] <= 0:
        return ("%s, none left%s — this is the run's last lead: work within your band and close "
                "the run with its morning report; a hand-over would start no successor"
                % (head, src))
    if s["fault"]:
        return ("%s, %d left%s — warn: the run's own cap cannot be read from its grants file: %s"
                % (head, s["left"], src, fix))
    return "%s, %d left%s" % (head, s["left"], src)


def last_lead_state(sid):
    """("last" | "not-last" | "undecided", text) for the hard-band hook (handsoff-gate.py; the
    owner's decision of 2026-10-30 that the run's last lead may still stop its background tasks
    and close the run at the 90 % edge). `last` only when the run has no successor left on a
    decided cap AND `sid` is the record's current head session (head_session), so another armed
    session of the run is never let through (review CR-CAP2 finding 1). The run is found as the
    head fence finds it: AIMYTH_HANDSOFF_RUN, else the state directory's `run-<sid>` pointer (one
    line). It never raises and never prints to stdout: a premise failure, die()'s SystemExit
    included, is `undecided` with the premise named, and the hook then keeps its deny. A record
    with any unreadable line (read_record's count: a torn or malformed row) is such a premise,
    whatever its readable rows show, since that line may be a newer head start or resume, which
    would change the count or the current lead (build review RV-CAP4 finding F1)."""
    try:
        run = (os.environ.get("AIMYTH_HANDSOFF_RUN") or "").strip()
        if run:
            if not TOKEN_RE.fullmatch(run):
                return "undecided", "AIMYTH_HANDSOFF_RUN %r is not a run id" % run[:60]
        else:
            if not isinstance(sid, str) or not TOKEN_RE.fullmatch(sid):
                return "undecided", ("no run: no AIMYTH_HANDSOFF_RUN, and session id %r cannot "
                                     "name a run pointer" % (str(sid)[:60],))
            pointer = os.path.join(state_dir(), "run-" + sid)
            try:
                with open(pointer, encoding="utf-8") as handle:
                    run = handle.readline().strip()
            except FileNotFoundError:
                return "undecided", ("no run: no AIMYTH_HANDSOFF_RUN and no run pointer at %s"
                                     % pointer)
            except (OSError, ValueError) as exc:
                return "undecided", "the run pointer %s is unreadable (%s)" % (
                    pointer, one_line(str(exc))[:80])
            if not TOKEN_RE.fullmatch(run):
                return "undecided", "the run pointer %s holds %r, which is not a run id" % (
                    pointer, run[:60])
        path = record_path(run)
        if not os.path.isfile(path):
            return "undecided", "the run record %s is missing" % path
        events, bad = read_record(path)
        if bad:
            return "undecided", ("the run record %s has %d unreadable line(s), any of which may "
                                 "be a newer head start or resume" % (path, bad))
        if last_index(events, ("run-open",)) < 0:
            return "undecided", "the run record %s carries no run-open" % path
        s = successors_left(events, run)
        clause = successors_clause(s)
        if s["fault"]:
            return "undecided", "%s: the grants file is %s" % (clause, s["fault"])
        if s["left"] > 0:
            return "not-last", clause
        lead, _ = head_session(events)
        if lead is None:
            return "undecided", "%s, but the record names no current head session" % clause
        if sid != lead:
            return "not-last", ("successors: %d of %d started, none left; this session (%s) is "
                                "not the run's current lead: the record's current head session "
                                "is %s" % (s["used"], s["cap"], str(sid)[:60], lead))
        return "last", clause
    except BaseException as exc:   # die() raises SystemExit; nothing may escape to the hook
        return "undecided", "%s: %s" % (type(exc).__name__, one_line(str(exc))[:160])


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
    path the file adds), else the file's lists, and `against` names what was compared. `sources`
    names where each list came from (`grants`, `writes`) and where each key's value did
    (`on_limit`, `viewer`, `network`, `max_successors`). The file is read ONCE and every key
    and list is taken from that read, so a caller that records its event from the payload and
    these sources reports exactly what it writes (critic finding F3 of the second review of
    2026-10-11: run-resume read the cap for its event apart from the plan, before its lock, and a
    cap written between the two reads went to the file while the event and stdout named the
    older one)."""
    current = read_grants(path)
    on_limit, on_limit_src = on_limit_choice(a, path, current)
    viewer, viewer_src = viewer_choice(a, path, current)
    network, network_src = network_choice(a, path, current)
    cap, cap_src = max_successors_choice(a, path, current)
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
    lists, sources = {}, {}
    for key, flag, given, addflag, added in (
            ("grants", "--grant", a.grant, "--add-grant", getattr(a, "add_grant", None) or []),
            ("writes", "--write", a.write, "--add-write", getattr(a, "add_write", None) or [])):
        carried = path_list(current, key)
        if given:
            lists[key], sources[key] = list(given), flag
        elif added:
            # An addition merges into the baseline (register entry 2026-09-29 20:49: a call
            # naming one extra path replaced the whole list). With no trustworthy baseline — no
            # recorded lists and a grants file that is missing or unreadable — it refuses rather
            # than adding to the defaults, which would pass a narrowing off as preservation.
            if old[key] is None:
                die("%s adds to the run's %s list, but there is no trustworthy baseline to add to: "
                    "the record holds no recorded lists and the grants file %s is %s; pass the "
                    "whole list with %s and --replace; nothing written"
                    % (addflag, "write" if key == "writes" else "read", path,
                       grants_file_state(path), flag))
            lists[key] = list(old[key]) + [p for p in added if p not in old[key]]
            sources[key] = "%s (%d path(s) added to %s)" % (addflag, len(added), against)
        elif carried is not None:
            lists[key], sources[key] = carried, "carried (file)"
        else:
            lists[key], sources[key] = [], "defaults (nothing to carry)"
    payload = grants_payload(a.run, source, lists["grants"], lists["writes"], on_limit, viewer,
                             network, cap, carry=current)
    sources.update(on_limit=on_limit_src, viewer=viewer_src, network=network_src,
                   max_successors=cap_src)
    dropped = {}
    for key in ("grants", "writes"):
        lost = [p for p in (old[key] or []) if p not in payload[key]]
        if lost:
            dropped[key] = lost
    return payload, sources, dropped, against


def guard_shrink(a, what, dropped, against):
    """The shrink guard (register entries 2026-09-11 04:17 and 2026-09-29 20:49): a rewrite that
    would lose a path from either list — the read list or the write list — prints the delta and
    refuses (exit 2, nothing written) unless the call passes --replace, the explicit word that the
    lists it names replace the run's; a replacement is written, each list's delta on stderr, and
    becomes the baseline of the next call. A call that only adds (--add-grant, --add-write) never
    loses a path from the list it names."""
    deltas = ["the %s list loses %d path(s) against %s: %s"
              % ("write" if key == "writes" else "read", len(dropped[key]), against,
                 ", ".join(dropped[key]))
              for key in ("writes", "grants") if key in dropped]
    if not deltas:
        return
    if getattr(a, "replace", False):
        note("%s: %s (--replace: the lists named replace the run's, so it is written)"
             % (what, " · ".join(deltas)))
        return
    die("%s would shrink the run's grants and passes no --replace: %s; to add a path pass "
        "--add-grant or --add-write, to narrow the lists on purpose pass them whole with --grant "
        "and --write and --replace; nothing written" % (what, " · ".join(deltas)))


def check_grant_forms(a, what, opening=False):
    """The grant flags' parser rules, before anything is read or written: --grant and --add-grant
    are two forms for one list (pass one), as are --write and --add-write; --replace rewrites the
    lists it names, so it takes --grant or --write and never an add form; and run-open, which
    writes the run's first grants file, takes neither an add form nor --replace."""
    add_g = getattr(a, "add_grant", None) or []
    add_w = getattr(a, "add_write", None) or []
    replace = getattr(a, "replace", False)
    if opening and (add_g or add_w or replace):
        die("%s writes the run's first grants file: name its lists with --grant and --write "
            "(there is nothing to add to or replace yet); nothing written" % what)
    if a.grant and add_g:
        die("%s: --grant replaces the run's read list and --add-grant adds to it: pass one form "
            "for the read list; nothing written" % what)
    if a.write and add_w:
        die("%s: --write replaces the run's write list and --add-write adds to it: pass one form "
            "for the write list; nothing written" % what)
    if replace and (add_g or add_w):
        die("%s: --replace rewrites the lists it names and --add-grant/--add-write add to the "
            "current ones: pass one form; nothing written" % what)
    if replace and not (a.grant or a.write):
        die("%s: --replace names no list: pass the whole list(s) the run keeps with --grant and "
            "--write; nothing written" % what)


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

def read_record(path, marks=None):
    """(events, unparseable lines): a torn last line — a wrapper writing concurrently — is
    counted, never guessed at. `marks`, a list when given, receives one placeholder per skipped
    line: the number of parsed events before it, so a reader can place each unreadable line
    among the events (the repeat-stop guard alone passes one: critic finding 3 of the review of
    2026-10-11). Every other reader's call and result are unchanged."""
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
                    if marks is not None:
                        marks.append(len(events))
                    continue
                if isinstance(rec, dict):
                    events.append(rec)
                else:
                    bad += 1
                    if marks is not None:
                        marks.append(len(events))
    except OSError as exc:
        die("cannot read the run record %s: %s" % (path, exc))
    try:
        events = [row for row in events if row.get("event") != "lane-closed" or
                  a3_shared().a3_close_valid(row)]
    except (a3_shared().A3Premise, OSError) as exc:
        die("authoritative close unavailable: %s" % exc)
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


def a3_shared():
    """Use the very same module instance and lock transaction in embedded callers. The lane
    wrapper is the one lane_module() reads: AIMYTH_LANE_PY, else lane.py beside this script, so a
    copy under test runs its record transaction through the wrapper its suite names."""
    path = os.environ.get("AIMYTH_LANE_PY") or os.path.join(HERE, "lane.py")
    path = os.path.realpath(os.path.expanduser(path))
    for module in list(sys.modules.values()):
        if getattr(module, "__file__", None) and os.path.realpath(module.__file__) == path \
                and hasattr(module, "a3_record_lock"):
            return module
    spec = importlib.util.spec_from_file_location("_delegate_a3", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def append_record(path, payload):
    try:
        a3_shared().append_record(path, payload)
    except (OSError, a3_shared().A3Premise) as exc:
        die("run record transaction failed (%s): %s" % (path, exc))


def a3_find_notice(path, run, identifier, version, digest):
    module = a3_shared()
    for journal in module.a3_journals(path, run):
        for notice in journal.get("notices") or []:
            if notice["notice_id"] == identifier and notice["version"] == version:
                if notice["payload_sha256"] != digest:
                    die("notice payload digest does not match the saved version")
                return journal, notice
    die("notice identifier/version is not in the retained journal namespace")


def a3_receipt(a, path):
    """Only the explicit head ledger command writes a receipt; publishing never calls this."""
    module = a3_shared()
    fields = (a.notice_id, a.notice_version, a.notice_sha256)
    if not all(value is not None for value in fields) or not a.observation:
        die("notice receipt requires --observation and the exact id/version/sha256 triple")
    caller = head_event_caller()
    with module.a3_record_lock(path):
        journal, notice = a3_find_notice(path, a.run, *fields)
        rows, _ = module.a3_record_rows(path)
        identity = module.a3_digest(module.a3_json(list(fields)))
        existing = [row for row in rows if row.get("event") == "observation"
                    and row.get("notice_receipt") == identity]
        row = {"ts": now(), "event": "observation", "run": a.run, "phase": a.phase or "",
               "what": a.observation, "notice_id": fields[0], "notice_version": fields[1],
               "notice_sha256": fields[2], "notice_payload": notice["payload"],
               "notice_receipt": identity, "author": "head", "route": "hands-off"}
        row["caller_pid"], row["caller_pid_src"] = caller
        if existing and (len(existing) != 1 or any(existing[0].get(key) != row[key] for key in
                ("notice_id", "notice_version", "notice_sha256", "notice_payload", "author", "route"))):
            die("conflicting notice delivery receipt")
        if not existing and not a.dry_run:
            append_record(path, row)
        if a.dry_run:
            say("notice receipt: dry run; no acknowledgement")
        else:
            say("notice receipt: record:%s · no hand-off row" % identity)
    return 0


def a3_open_notices(path, run):
    """The notices still owed a receipt: a3_pending less every version below one already
    acknowledged for the same notice id (register entry 2026-10-30 21:40 f). A receipt for
    version n settles the older versions, whose facts version n replaced, so they are not printed
    again with recovery commands; a newer version stays owed, as a receipt is for what it read."""
    module = a3_shared()
    settled = {}
    for journal in module.a3_journals(path, run):
        for ack in journal.get("acknowledgements") or []:
            settled[ack["notice_id"]] = max(settled.get(ack["notice_id"], 0), ack["version"])
    return [notice for notice in module.a3_pending(path, run)
            if notice["version"] > settled.get(notice["notice_id"], 0)]


def cmd_notices(a):
    module = a3_shared()
    path = getattr(a, "record", None) or record_path(a.run)
    try:
        if not a.ack:
            notices = a3_open_notices(path, a.run)
            if a.format == "json":
                print(module.a3_json({"pending": notices, "count": len(notices)}))
            else:
                print("pending notices: %d" % len(notices))
                for notice in notices:
                    print(module.a3_notice_text(notice))
            return 0
        if not all(getattr(a, key, None) is not None for key in
                   ("notice_id", "notice_version", "notice_sha256", "receipt", "route")):
            die("acknowledgement requires the notice triple, route and durable receipt locator")
        with module.a3_record_lock(path):
            journal, notice = a3_find_notice(path, a.run, a.notice_id, a.notice_version, a.notice_sha256)
            if a.route == "hands-off":
                rows, _ = module.a3_record_rows(path)
                expected = module.a3_digest(module.a3_json(
                    [a.notice_id, a.notice_version, a.notice_sha256]))
                receipts = [row for row in rows if row.get("notice_receipt") == expected
                            and row.get("event") == "observation" and row.get("author") == "head"
                            and row.get("notice_payload") == notice["payload"]
                            and row.get("notice_id") == a.notice_id
                            and row.get("notice_version") == a.notice_version
                            and row.get("notice_sha256") == a.notice_sha256]
                if a.receipt != "record:" + expected or len(receipts) != 1:
                    die("acknowledgement has no matching durable head observation receipt")
                receipt_digest = module.a3_digest(module.a3_json(receipts[0]))
            else:
                # An attended receiver supplies its durable emitted-reply artefact. Mere stdout
                # or a poll is no receipt. A missing/unverifiable artefact remains pending.
                data = module.read_bytes(a.receipt)
                if data is None or not a.receipt_sha256 or module.a3_digest(data) != a.receipt_sha256:
                    die("attended reply receipt is unreadable or its digest is unverified")
                text = data.decode("utf-8")
                if module.a3_notice_text(notice) not in text:
                    die("attended reply receipt does not contain this factual notice version")
                receipt_digest = a.receipt_sha256
            ack = {"notice_id": a.notice_id, "version": a.notice_version,
                   "payload_sha256": a.notice_sha256, "route": a.route,
                   "receipt": a.receipt, "receipt_sha256": receipt_digest}
            keys = ("notice_id", "version", "payload_sha256")
            if not any(all(old[key] == ack[key] for key in keys)
                       for old in journal.get("acknowledgements") or []):
                journal.setdefault("acknowledgements", []).append(ack)
                module.a3_save_journal(journal)
        print("notice acknowledged: %s v%d" % (a.notice_id, a.notice_version))
        return 0
    except (module.A3Premise, OSError, UnicodeError) as exc:
        die(str(exc))


def a3_expose_notices(function):
    @functools.wraps(function)
    def wrapped(a, *args, **kwargs):
        path = getattr(a, "record", None) or record_path(a.run)
        try:
            notices = a3_open_notices(path, a.run)
        except (a3_shared().A3Premise, OSError) as exc:
            die("notice census failed: %s" % exc)
        for notice in notices:
            say(a3_shared().a3_notice_text(notice))
        return function(a, *args, **kwargs)
    return wrapped


def a3_observe_helpers(path, run):
    module = a3_shared()
    journals = module.a3_journals(path, run)
    lanes = sorted({journal["lane"] for journal in journals})
    for lane_id in lanes:
        result = module.a3_observe(path, run, lane_id)
        if result and result["state"] == "orphan":
            say(module.a3_notice_text(result["journal"]["notices"][-1]))


def a3_can_beat(path, run, lane_id):
    module = a3_shared()
    journal = module.a3_latest(path, run, lane_id)
    current = module.a3_latest(path, run, lane_id, include_beats=True)
    if current and not module.a3_committed(current):
        return False
    if journal and journal["disposition"].get("decision") == "held":
        return False
    return True


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


def clock_placeholders(text):
    """The typed clock placeholders in a text, a bracketed register stamp apart."""
    return CLOCK_PLACEHOLDER_RE.findall(REGISTER_STAMP_RE.sub("", str(text or "")))


def refuse_placeholder(who, texts):
    """A premise failure when the head's own text carries a typed clock placeholder: a time label
    comes from a command or the record, never a rounded guess, and the owner reads these records
    (the clock-label rule of 2 October). `texts` maps each flag to its text; nothing is written."""
    for flag, text in texts.items():
        hits = clock_placeholders(text)
        if hits:
            die("%s: --%s carries the typed clock placeholder %s: read the time from a command or "
                "the record and write it whole, or name a register heading in its brackets; "
                "nothing written" % (who, flag, ", ".join(hits)))


def stage_placeholders(run, since):
    """[(document, placeholders)] for the top-level `.md` files of the run's stage changed at or
    after `since`, capped by STAGE_SCAN_FILES and STAGE_SCAN_BYTES. A head writes these with its
    own tools, so the check can only name them after the fact, and refuses nothing."""
    folder = os.path.join(store_root(), "stages", token(run, "run id"))
    try:
        names = sorted(name for name in os.listdir(folder) if name.endswith(".md"))
    except OSError:
        return []
    found = []
    for name in names[:STAGE_SCAN_FILES]:
        document = os.path.join(folder, name)
        try:
            st = os.stat(document)
            if st.st_mtime < since or st.st_size > STAGE_SCAN_BYTES:
                continue
            with open(document, encoding="utf-8", errors="replace") as handle:
                hits = clock_placeholders(handle.read())
        except OSError:
            continue
        if hits:
            found.append((document, hits))
    return found


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


DERIVED_HEADING_MARK = "(re-derived from the record at "


def set_section(lines, key, value, derived=False):
    """Replace a named section's body. For `## In flight`, a pack derived from the record is
    written under its OWN heading, `## In flight (re-derived from the record at <ts>)`, never
    under a heading that names another pack (register entry 2026-09-25 17:4x: a re-derived
    section sat under an earlier head's FINAL-pack heading); a head's own pack written later
    restores the plain `## In flight` over a derived heading, and leaves any other heading as
    it is."""
    i = heading_index(lines, SECTIONS[key])
    if i < 0:
        return False
    if key == "inflight" and derived:
        lines[i] = INFLIGHT_DERIVED_HEADING % now()
    elif key == "inflight" and DERIVED_HEADING_MARK in lines[i]:
        lines[i] = "## %s" % SECTIONS[key]
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
_WEEKLY = None
SpendSource = collections.namedtuple("SpendSource", "obj n")   # a record line, as the reader names it


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


def head_event_caller():
    """Attribute a foreground shell command, allowing the harness's session-leading shell.

    One session transition is allowed only from that shell to its direct harness parent.
    Arbitrary workers, extra transitions and other process-group changes remain unattributed.
    """
    pid = os.getppid()
    shells = set(SHELLS)
    try:
        session = os.getsid(0)
        command_group = os.getpgid(0)
        # Same 32-link ceiling as head_pid; set by judgement, unmeasured.
        for _ in range(32):
            row = ps_row(pid)
            if row is None or os.getsid(pid) != session or os.getpgid(pid) != command_group:
                return None, "none"
            _, parent, command = row
            name = os.path.basename(command)
            if name == HARNESS:
                return pid, "head-command"
            if name not in shells or parent <= 1 or parent == pid:
                return None, "none"
            if os.getsid(parent) != session:
                parent_row = ps_row(parent)
                if (pid == session and parent_row is not None
                        and os.path.basename(parent_row[2]) == HARNESS):
                    return parent, "head-command"
                return None, "none"
            pid = parent
    except (OSError, ValueError):
        pass
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


def console_pattern(run):
    """The `pgrep -f` pattern for this run's console: the script — `handsoff.py watch` as it is
    launched, `watch.py` as it runs — at a word or path boundary on its left, so `lanewatch.py`
    never counts, then `--run R` or `--run=R` ANYWHERE after it, the run id followed by a space or
    the end, so a longer run id never counts for its prefix (register entry 2026-09-22 19:03: a
    console started with `--vault` before `--run` was invisible, and the run opened extra
    windows). The run id is escaped."""
    rid = re.escape(token(run, "run id"))
    return (r"(^|[[:space:]/])(handsoff\.py[[:space:]]+watch|watch\.py)([[:space:]].*)?"
            r"[[:space:]]--run(=|[[:space:]]+)%s([[:space:]]|$)" % rid)


def console_probe(run, timeout=None):
    """(status, pids, detail): one `pgrep -f` for this run's console (console_pattern), its exit
    status read as the premise it is (critic finding 8 of the batch's design review: output from
    a failed probe was taken for a sighting). `found`: exit 0 with at least one pid that is not
    this process; `none`: exit 1, no match; `unverified`: any other exit, a timeout, a probe that
    cannot run, or exit 0 with no readable pid — the probe said nothing that can be trusted, so
    nothing may be confirmed on it. The pattern is passed as an argv item, never through a shell,
    so the probe never matches its own command line. `timeout` bounds the call (VIEWER_TIMEOUT_S
    by default; wait_console passes the time left of its bound)."""
    try:
        proc = subprocess.run(["pgrep", "-f", console_pattern(run)], capture_output=True,
                              text=True,
                              timeout=VIEWER_TIMEOUT_S if timeout is None else max(0.0, timeout))
    except (OSError, subprocess.SubprocessError) as exc:
        return "unverified", [], "the probe could not run (%s: %s)" % (type(exc).__name__, exc)
    if proc.returncode == 1:
        return "none", [], "pgrep exit 1: no match"
    if proc.returncode != 0:
        tail = one_line((proc.stderr or "").strip())[:120]
        return "unverified", [], "pgrep exit %d%s" % (proc.returncode,
                                                       ": " + tail if tail else "")
    pids = []
    for field in proc.stdout.split():
        try:
            pid = int(field)
        except ValueError:
            continue
        if pid != os.getpid():
            pids.append(pid)
    if not pids:
        return "unverified", [], "pgrep exit 0 with no readable pid other than this process's"
    return "found", pids, "pgrep exit 0"


def console_alive(run, timeout=None):
    """The pids of the processes already showing this run's console. Two spellings count: the
    command as it is launched (`handsoff.py watch --run R`) and the command as it RUNS, since
    `watch` execs watch.py in place and its process reads `… /watch.py --run R`.
    A pattern on the first spelling alone misses that process.
    The pattern (console_pattern) counts `--run R` anywhere after the script, and the probe's
    status is read (console_probe): only a probe that succeeded names pids. A probe that could
    not tell is no console here, with one stderr note — the caller that must CONFIRM a console
    reads console_probe's status itself. `timeout` bounds the pgrep call."""
    status, pids, detail = console_probe(run, timeout)
    if status == "unverified":
        note("viewer: cannot probe for a live console (%s)" % detail)
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


def interpreter():
    """The absolute path of the interpreter running this script, for every command handed to the
    owner or to a head: a bare `python3` resolves through the reader's own shell, which may map it
    to another program (register entry 2026-09-30 17:36: an interactive shell ran ipython3, which
    took --run as its own option). sys.executable is absolute whenever Python could find itself;
    the bare word is the fallback only when it could not."""
    exe = sys.executable
    return exe if exe and os.path.isabs(exe) else "python3"


def by_hand_line(run):
    """The line the owner runs when no window could be opened; the same derived paths, the
    interpreter named by its absolute path (interpreter())."""
    return "%s -B %s watch --run %s" % (shlex.quote(interpreter()),
                                        shlex.quote(os.path.abspath(__file__)),
                                        token(run, "run id"))


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
        pids, waited, _, detail = wait_console(run)
        if not pids:
            mark_console_failed(path)
            line = ("viewer: no Terminal window (command file %s; %s exited 0 but no console "
                    "process for the run appeared within %d s; the last probe: %s); run by "
                    "hand: %s" % (path, opener, CONSOLE_START_GRACE_S, detail,
                                  by_hand_line(run)))
            note(line)
            viewer_log(log, line)
            return False
        # The hold after the first sighting (IDEAS 170 (1)): gone within the hold is a failure
        # with no retry — the console ended itself, so a second open would end the same way — and
        # a probe that cannot tell after the hold claims nothing (critic finding 8).
        state, alive, held, hdetail = hold_console(run, pids)
        if state == "exited":
            mark_console_failed(path)
            line = ("viewer: console started (pid %s at %.1f s) but exited within %.1f s · no "
                    "Terminal window stays on the run (command file %s via %s; not retried: the "
                    "console ended itself, so a second open would end the same way); run by "
                    "hand: %s" % (", ".join(str(p) for p in pids), waited, held, path, opener,
                                  by_hand_line(run)))
            note(line)
            viewer_log(log, line)
            return False
        if state == "unverified":
            line = ("viewer: console pid %s seen at %.1f s, but the probe after the %.0f s hold "
                    "could not tell (%s): the window is not confirmed (command file %s via %s); "
                    "check with `open-console --check`, or run by hand: %s"
                    % (", ".join(str(p) for p in pids), waited, CONSOLE_CONFIRM_HOLD_S, hdetail,
                       path, opener, by_hand_line(run)))
            note(line)
            viewer_log(log, line)
            return False
        confirmed = (" · console pid %s confirmed after %.1f s (first seen at %.1f s, still "
                     "alive after the %.0f s hold)" % (", ".join(str(p) for p in alive),
                                                        waited + held, waited,
                                                        CONSOLE_CONFIRM_HOLD_S))
    line = "viewer: Terminal window opened on %s via %s (%s)%s%s" % (
        path, opener, "first attempt" if not failures else "retry, after %s" % failures[0],
        confirmed, " · " + why if why else "")
    say(line)
    viewer_log(log, line)
    return True


def wait_console(run, bound=None, step=None):
    """(pids, seconds waited, probes made, the detail of the last probe that answered, else of the
    first that could not tell): the run's console pids once
    a probe that succeeded (console_probe) finds any inside `bound`, polled every `step` (the
    confirmation constants by default); ([], waited, probes, detail) when none showed inside it,
    a probe that could not tell counting as no sighting. The bound is checked before a result is
    accepted and
    each probe's own timeout is the lower of its cap and the time left of it (probe_bound), so
    the wait never runs past the bound and a pid that shows only after it is a timeout, never a
    window; the probes are capped at
    ceil(bound / step), 30 at the defaults."""
    bound = CONSOLE_START_GRACE_S if bound is None else bound
    step = CONSOLE_CONFIRM_STEP_S if step is None else step
    cap = max(1, int(math.ceil(bound / step))) if step > 0 else 1
    t0 = time.monotonic()
    probes = 0
    detail = "no probe ran"
    while True:
        left = bound - (time.monotonic() - t0)
        if left <= 0 or probes >= cap:
            return [], time.monotonic() - t0, probes, detail
        probes += 1
        # A sighting is a probe that SUCCEEDED (critic finding 8 of the batch's design review):
        # output from a pgrep that failed is never a pid, so an unverified probe waits on.
        status, pids, said = console_probe(run, timeout=probe_bound(VIEWER_TIMEOUT_S, left))
        # The detail handed back is the last probe that ran to an answer (found or none), else
        # the first that could not tell: a final probe the bound cut short says less than the
        # one before it.
        if status != "unverified" or detail == "no probe ran":
            detail = said
        waited = time.monotonic() - t0
        if status == "found" and waited <= bound:
            return pids, waited, probes, detail
        if waited >= bound or probes >= cap:
            return [], waited, probes, detail
        time.sleep(max(0.0, min(step, bound - waited)))


# The hold after the first sighting (IDEAS 170 (1); register entry 2026-09-20 01:48): the window
# counts as open only when a console first seen is still there this long after, since a watcher
# that exited at its own start-up probe was reported `console pid N confirmed after 1.6 s`. 3 s
# is longer than the 0.5 to 2 s the two dead windows of that night lived; set by judgement from
# those two observations, unmeasured beyond them. It adds 3 s to an open that confirms.
CONSOLE_CONFIRM_HOLD_S = 3


def hold_console(run, first, hold=None):
    """(state, pids, seconds held, detail) one probe after the hold: `confirmed` with the pids
    first seen that a SUCCESSFUL probe still finds; `exited` when a successful probe finds none of
    them — the console that was seen is gone, and a replacement pid confirms nothing; `unverified`
    when that probe failed (critic finding 8: a pgrep exit other than 0 or 1, a timeout, or
    unusable output), so nothing is claimed either way."""
    hold = CONSOLE_CONFIRM_HOLD_S if hold is None else hold
    t0 = time.monotonic()
    time.sleep(max(0.0, hold))
    status, again, detail = console_probe(run)
    held = time.monotonic() - t0
    if status == "unverified":
        return "unverified", [], held, detail
    alive = [pid for pid in first if pid in again]
    return ("confirmed" if alive else "exited"), alive, held, detail


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
    except OSError as exc:
        if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
            pid, phase = read_console_claim(fd)
            os.close(fd)
            return False, None, ("another opener (%s) holds this run's console claim (%s)"
                                 % (console_holder_text(pid, phase), lock))
        # Any other errno says the lock cannot be worked at all on this file system (register
        # entry 2026-09-18 20:0x: an ENOLCK read as contention left the run with no window and no
        # by-hand line). That is the tri-state's None: the caller says so and opens anyway, as it
        # does with no fcntl, since a viewer failure never fails a launch. lane.py's session claim
        # keeps refusing on the same errno: a session claim that cannot be worked must not let a
        # second call into one session.
        os.close(fd)
        return None, None, ("the console claim %s cannot be locked (%s: %s), so it is not taken"
                            % (lock, errno.errorcode.get(exc.errno, exc.errno), exc.strerror))
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


def past_deadline(t0, wait):
    """(elapsed, late): the launch check's clock read again at the moment a start would be
    certified or bound, after the last read or probe that result rests on, and whether that is
    past the deadline. It is the one deadline check before every path that certifies a start —
    the head path's STARTED, a replacement head start's binding during the first batch's wait,
    and the first batch's STARTED CLEAN — and each refuses when `late` (critic finding N2 of the
    third review of 2026-10-11: helper readiness first seen past the deadline, through a delayed
    re-read or a slow helper probe, still certified, since the time was read before them).
    `--wait 0`, the single read, has no deadline and is never late."""
    elapsed = time.monotonic() - t0
    return elapsed, bool(wait) and elapsed > wait


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
    model, effort = start_model(events, hi)
    return "started", "%s · pid %d alive (%s, running %d s) · model %s effort %s" % (
        label, pid, row[2] if row else "command unread", age, model or "none", effort or "none")


# The first batch (owner decision D21 (c) of 2026-10-10, register entry 2026-10-04 01:02): the
# launch check certifies a clean start only when every planned first-batch helper has opened and
# is making progress. "Making progress" is observable activity of the helper's latest attempt
# after its open (the owner's provisional choice of 2026-10-10 under his D19): a record event the
# helper's wrapper writes only once its model call has begun (LAUNCH_LANE_ACTIVITY), or a
# transcript or session-file record stamped after the open. A process that is merely alive is
# not progress.
LAUNCH_LANE_STARTS = ("lane-open", "lane-resumed")         # an attempt of a helper begins here
LAUNCH_LANE_SPAWNS = ("lane-spawned", "lane-respawned")    # its process started
LAUNCH_LANE_ACTIVITY = ("lane-session",)                   # the Codex CLI's thread began: a model call


def parse_lane_list(text):
    """The --lanes ids, in order: each a plain token, none twice, at least one — an empty list
    would certify a start that has no helper at all, so it is a premise failure (exit 2)."""
    names = [part.strip() for part in str(text or "").split(",")]
    names = [n for n in names if n]
    if not names:
        die("--lanes names no helper: pass the planned first batch's lane ids, comma-separated "
            "(an empty list would certify a start with no helper)")
    seen = []
    for name in names:
        token(name, "lane id")
        if name in seen:
            die("--lanes names %s twice: each planned helper once" % name)
        seen.append(name)
    return seen


def launch_anchor(events):
    """The index of the head start the check confirmed (the record's last head start, when no
    head-exit follows it), else -1. A helper attempt counts for this launch only after it: an
    attempt a previous head made is not this launch's."""
    i = last_index(events, LAUNCH_HEAD_EVENTS)
    return i if i >= 0 and events[i].get("event") != "head-exit" else -1


def lane_activity_stamp(events, start, lane, opened, spawned):
    """(epoch, how) of the helper's latest activity in its transcript or session file, else
    (None, why). A Claude helper: the last stamped record of the transcript its session id names
    under the projects root. A Codex helper: the last stamped record of its session file under the
    Codex home (the thread id from its lane-session line), else the mtime of the wrapper's events
    log, which its stream writes."""
    if (opened or {}).get("harness") == "codex" or (spawned or {}).get("harness") == "codex":
        thread = None
        for ev in events[start + 1:]:
            if ev.get("lane") == lane and ev.get("event") == "lane-session" and ev.get("session_id"):
                thread = ev.get("session_id")
        path = codex_session_file(thread) if thread else None
        if path:
            t, how = file_last_stamp(path)
            if t is not None:
                return t, "Codex session file (%s)" % how
        log = (opened or {}).get("events")
        if isinstance(log, str) and os.path.isfile(log):
            try:
                return os.path.getmtime(log), "the wrapper's events log mtime"
            except OSError:
                pass
        return None, "no Codex session file and no events log"
    sid = (spawned or {}).get("session_id") or (opened or {}).get("session_id")
    if not isinstance(sid, str) or not TOKEN_RE.fullmatch(sid):
        return None, "no session id on the record"
    path, why = lane_transcript_path(sid)
    if path is None:
        return None, why
    t, how = file_last_stamp(path)
    if t is None:
        return None, "the transcript %s is unreadable" % path
    return t, "transcript (%s)" % how


def lane_attempt_verdict(events, anchor, lane):
    """(state, detail) for one planned helper of the first batch, read from its LATEST attempt
    after the anchor (launch_anchor). `missing` (no attempt since the head started), `opening`
    (opened, no process yet), `silent` (its process is alive and no activity followed its open),
    `progressing` (activity after its open: a LAUNCH_LANE_ACTIVITY record event, or a transcript
    or session-file record stamped after it), `done` (closed `completed`, its report on disk where
    the close names one), `failed` (closed any other way, or its wrapper and lane pids both gone
    with no close) or `unverified` (an open with no readable timestamp, a completed close whose
    report is missing, or no usable pid and no activity). Timestamps are compared as epochs,
    whatever their offsets, never as text."""
    start = None
    for i in range(len(events) - 1, anchor, -1):
        if events[i].get("lane") == lane and events[i].get("event") in LAUNCH_LANE_STARTS:
            start = i
            break
    if start is None:
        earlier = any(e.get("lane") == lane and e.get("event") in LAUNCH_LANE_STARTS
                      for e in events[:anchor + 1])
        return "missing", ("no attempt since the head started%s"
                           % ("; an attempt before that head is not this launch's"
                              if earlier else ""))
    opened, later = events[start], events[start + 1:]
    close = next((e for e in later if e.get("lane") == lane and e.get("event") == "lane-closed"),
                 None)
    if close is not None:
        cls = close.get("exit_class")
        if cls == "completed":
            report = close.get("report")
            if isinstance(report, str) and report and not os.path.isfile(report):
                return "unverified", ("closed completed at %s, but the report it names (%s) is "
                                      "not on disk" % (close.get("ts", "no ts"), report))
            return "done", "closed completed at %s" % close.get("ts", "no ts")
        return "failed", "closed %s at %s" % (cls or "with no exit class", close.get("ts", "no ts"))
    t_open = parse_ts(opened.get("ts"))
    if t_open is None:
        return "unverified", ("its %s carries no readable timestamp (%r), so no activity can be "
                              "placed after it" % (opened.get("event"), opened.get("ts")))
    spawned = next((e for e in later if e.get("lane") == lane
                    and e.get("event") in LAUNCH_LANE_SPAWNS), None)
    activity = None
    for ev in later:
        t = parse_ts(ev.get("ts"))
        if ev.get("lane") == lane and ev.get("event") in LAUNCH_LANE_ACTIVITY \
                and t is not None and t >= t_open:
            activity = "record %s at %s" % (ev.get("event"), ev.get("ts"))
            break
    if activity is None:
        t, how = lane_activity_stamp(events, start, lane, opened, spawned)
        if t is not None and t > t_open:
            activity = "%s at %s" % (how, fmt_ts(t))
    if spawned is None:
        return "opening", "%s at %s, and no process started yet (no %s)" % (
            opened.get("event"), opened.get("ts"), " or ".join(LAUNCH_LANE_SPAWNS))
    pids = [usable_pid(spawned.get(key)) for key in ("wrapper_pid", "pid")]
    pids = [p for p in pids if p is not None]
    if not pids:
        alive, live = None, ("no usable pid on its %s (wrapper_pid %r, pid %r): liveness "
                             "unverifiable" % (spawned.get("event"), spawned.get("wrapper_pid"),
                                               spawned.get("pid")))
    else:
        alive = any(pid_alive(p) for p in pids)
        live = "pid %s %s" % ("/".join(str(p) for p in pids), "alive" if alive else "gone")
    if alive is False:
        return "failed", "no close, and its %s" % live
    if activity:
        return "progressing", "%s · %s" % (activity, live)
    if alive is None:
        return "unverified", "no activity since its open at %s, and %s" % (opened.get("ts"), live)
    return "silent", ("opened at %s, %s, and no record or transcript event since its open"
                      % (opened.get("ts"), live))


def lanes_text(verdicts):
    return ", ".join("%s %s (%s)" % (lane, state, detail) for lane, (state, detail) in verdicts)


def start_model(events, i):
    """(model, effort) the head start at index i runs under: its own fields, else, for a
    run-resume, those of the newest earlier start naming its session. A head's first act is a
    run-resume whose model sits in its free-text --head, never parsed; the head-successor that
    started it carries the fields (register entry 2026-10-15 01:33 c, the status of 28 October)."""
    ev = events[i]
    model, effort = ev.get("model") or None, ev.get("effort") or None
    if ev.get("event") == "run-resume":
        sid = start_session(ev)
        for prior in reversed(events[:i]):
            if prior.get("event") in START_EVENTS and start_session(prior) == sid:
                model, effort = model or prior.get("model"), effort or prior.get("effort")
    return model or None, effort or None


def model_unreadable(events, anchor):
    """Why the confirmed head start can be certified on no model, else None (register entries
    2026-09-23 12:5x and 2026-10-15 01:33 c): a start that names none, or a run-resume whose
    session no start names one for, may be running on the harness default, and a certificate that
    printed `model none` would pass a head on the wrong model alike."""
    if anchor < 0 or start_model(events, anchor)[0]:
        return None
    ev = events[anchor]
    return ("the %s at %s carries no readable model (model_src %s), so it may run on the harness "
            "default: stop it and start it again with --model unless the default was meant, or "
            "name it with `run-resume --model`"
            % (ev.get("event"), ev.get("ts", "no ts"), ev.get("model_src") or "unrecorded"))


def launch_ended(events, anchor):
    """The terminal states head_start_verdict reads, kept through the first batch's wait without
    its probes (critic finding 2 of the review of 2026-10-11): the reason the check ends on at
    once, else None — a run-close anywhere on the record, a head-exit as the newest head event
    (`anchor` -1; a successor-aborted after it named), or a `head exited` observation naming the
    session of the start at `anchor`."""
    ci = last_index(events, ("run-close",))
    if ci >= 0:
        return "the run closed (run-close at %s)" % events[ci].get("ts", "no ts")
    if anchor < 0:
        hx = last_index(events, ("head-exit",))
        if hx < 0:
            return "the record names no head start any more"
        aborted = next((e for e in events[hx + 1:] if e.get("event") == "successor-aborted"),
                       None)
        return "the head-exit at %s followed it%s" % (
            events[hx].get("ts", "no ts"),
            "" if aborted is None else " and the starter aborted (successor-aborted %s at %s)"
            % (aborted.get("reason", "?"), aborted.get("ts", "no ts")))
    ev = events[anchor]
    sid = start_session(ev)
    exited = next((e for e in events[anchor + 1:] if e.get("event") == "observation"
                   and e.get("what") == "head exited"
                   and sid != "?" and sid in str(e.get("note", ""))), None)
    if exited is not None:
        return "the head of the %s at %s exited (head exited at %s)" % (
            ev.get("event"), ev.get("ts", "no ts"), exited.get("ts", "no ts"))
    return None


def launch_lanes(a, path, events, bad, lanes, detail, t0, wait, step, reads, budget=None):
    """The first batch (D21 (c)), once the head start is confirmed: every planned helper's
    latest attempt since that start must have opened and show activity, or have closed
    completed. One helper that failed ends the check at once; anything else short of that is
    re-read inside the same deadline, and at it the line names each helper's state. The
    confirmation is bound to ONE head invocation, the process head_start_verdict confirmed, which
    is never re-verified against the shrinking deadline (a probe with no time left would read
    the confirmed head as unverifiable). Every re-read keeps head_start_verdict's terminal states
    (launch_ended: a run-close, a head-exit, a `head exited` naming the start's session) and the
    pid's liveness (critic finding 2 of the review of 2026-10-11: only liveness was kept, so a
    close during the wait still certified). Each re-read takes the record's newest head start as
    the anchor: one naming the same pid — the head's own run-resume, its first act — moves the
    anchor and keeps the confirmation; one naming another pid, or none, is a replacement whose
    identity head_start_verdict verifies afresh on the shared `budget`: it binds the confirmation
    once `started` inside the deadline — the time is read again after the verification's probes,
    and a replacement confirmed past the deadline ends the check NOT CLEAN, as the head path
    refuses a late start — ends the check at once when `failed`, and while unverified certifies
    nothing, being NOT CLEAN at the deadline. A record with an unparseable line never certifies
    (a torn tail is retried meanwhile). STARTED CLEAN, like every certification, is decided on
    the clock read after the last re-read and the helper probes (past_deadline): a first batch
    first seen ready past the deadline, through a delayed re-read or a slow probe, is NOT CLEAN,
    while `--wait 0`, the single read, keeps no deadline (critic finding N2 of the third review
    of 2026-10-11)."""
    first = launch_anchor(events)
    bound = event_pid(events[first]) if first >= 0 else None   # the confirmed invocation's pid
    while True:
        elapsed = time.monotonic() - t0
        skipped = " · %d unparseable line(s) skipped" % bad if bad else ""
        anchor = launch_anchor(events)
        ended = launch_ended(events, anchor)
        pending = None
        if ended is None:
            pid = event_pid(events[anchor])
            if pid is None or pid != bound:
                state, why = head_start_verdict(events, budget=budget)
                # The verification's probes draw on the shared budget and can run to the deadline
                # or past it, so the time is read again after them, and a replacement confirmed
                # past the deadline is refused as the head path refuses a late start (critic
                # finding F2 of the second review of 2026-10-11: the time read before the probes
                # let a late replacement certify) — the one check, past_deadline.
                elapsed, late = past_deadline(t0, wait)
                if state == "started" and late:
                    ended = ("a newer head start replaced it, and %sthe replacement was confirmed "
                             "only %.1f s after the check began, past the %d s deadline (%s)"
                             % (UNVERIFIABLE, elapsed, wait, why))
                elif state == "started":
                    bound, detail = pid, "%s (a replacement start, its identity verified)" % why
                elif state == "failed":
                    ended = "a newer head start replaced it and could not be confirmed: %s" % why
                else:
                    pending = why   # unverified: it certifies nothing while it stands
            elif not pid_alive(pid):
                ended = "its pid %d no longer answers" % pid
        if ended is not None:
            say("launch-check: %s NOT CLEAN · the head started (%s), but %s before the first batch "
                "was confirmed · %.0f s after the check began (%d read(s))%s"
                % (a.run, detail, ended, elapsed, reads, skipped))
            return 1
        if pending is not None:
            if elapsed >= wait:
                say("launch-check: %s NOT CLEAN · the head started (%s), but a newer head start "
                    "replaced it and its identity was not verified within the %d s deadline: %s "
                    "(%d read(s))%s" % (a.run, detail, wait, pending, reads, skipped))
                return 1
            time.sleep(max(0.0, min(step, wait - elapsed)))
            events, bad = read_record(path)
            reads += 1
            continue
        verdicts = [(lane, lane_attempt_verdict(events, anchor, lane)) for lane in lanes]
        # The clock again, after the last re-read and the helper probes the verdicts made (each
        # transcript or session-file read): a readiness first seen past the deadline is a late
        # start, never a clean one (critic finding N2 of the third review of 2026-10-11).
        elapsed, late = past_deadline(t0, wait)
        failed = [lane for lane, (st, _) in verdicts if st == "failed"]
        progressing = all(st in ("progressing", "done") for _, (st, _) in verdicts)
        if failed:
            say("launch-check: %s NOT CLEAN · the head started (%s) · first batch: %s · %s "
                "failed · %.0f s after the check began (%d read(s))%s"
                % (a.run, detail, lanes_text(verdicts), ", ".join(failed), elapsed, reads,
                   skipped))
            return 1
        if progressing and not bad and late:
            say("launch-check: %s NOT CLEAN · the head started (%s) · first batch: %s · the first "
                "batch was confirmed only %.1f s after the check began, past the %d s deadline, "
                "and a start is certified only inside it; run the check again with a longer "
                "--wait (%d read(s))%s"
                % (a.run, detail, lanes_text(verdicts), elapsed, wait, reads, skipped))
            return 1
        if progressing and not bad:
            why = model_unreadable(events, anchor)
            if why:
                say("launch-check: %s NOT CLEAN · the head started (%s) · first batch: %s · %s "
                    "(%d read(s))" % (a.run, detail, lanes_text(verdicts), why, reads))
                return 1
            say("launch-check: %s STARTED CLEAN · %s · first batch (%d): %s · seen %.0f s "
                "after the check began (%d read(s))"
                % (a.run, detail, len(lanes), lanes_text(verdicts), elapsed, reads))
            return 0
        if elapsed >= wait:
            why = ("the record has %d unparseable line(s), and a malformed record never certifies "
                   "a clean start" % bad if bad and progressing
                   else "not every planned helper is open and making progress within the %d s "
                        "deadline" % wait)
            say("launch-check: %s NOT CLEAN · the head started (%s) · first batch: %s · %s "
                "(%d read(s))%s" % (a.run, detail, lanes_text(verdicts), why, reads, skipped))
            return 1
        time.sleep(max(0.0, min(step, wait - elapsed)))
        events, bad = read_record(path)
        reads += 1


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
    started, 1 not started or with no readable model to certify (model_unreadable), 2 on a premise.
    `--wait 0` performs a single read. The deadline is computed
    ONCE, at the start, and governs every read and every probe inside a read: each `ps` probe is
    bounded by the lower of its own cap and what is left of that one budget (probe_budget and
    probe_bound; a single read keeps the probe's own cap, having no deadline to run past), a
    start is accepted only inside it — STARTED, a replacement's binding and STARTED CLEAN each on
    the clock read after the last read or probe it rests on (past_deadline) — and a start whose
    identity could not be verified by the deadline is a named non-success; probes share one
    remaining-time budget."""
    wait, step = max(0, int(a.wait)), max(0.05, float(a.poll_s))
    t0, reads = time.monotonic(), 1
    # Include the initial record read and its preceding probes in the one shared deadline.
    budget = probe_budget(wait, t0)
    path = record_path(a.run)
    lanes = parse_lane_list(a.lanes) if getattr(a, "lanes", None) is not None else None
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
    while True:
        state, detail = head_start_verdict(events, budget=budget)
        elapsed, late = past_deadline(t0, wait)   # after this read's probes: the one check
        skipped = " · %d unparseable line(s) skipped" % bad if bad else ""
        if state == "started" and late:
            say("launch-check: %s NOT STARTED · %sthe start was confirmed only %.1f s after the "
                "check began, past the %d s deadline (%s); run the check again with a longer "
                "--wait (%d read(s))%s" % (a.run, UNVERIFIABLE, elapsed, wait, detail, reads, skipped))
            return 1
        if state == "started" and lanes is not None:
            return launch_lanes(a, path, events, bad, lanes, detail, t0, wait, step, reads,
                                budget=budget)
        if state == "started":
            why = model_unreadable(events, launch_anchor(events))
            if why:
                say("launch-check: %s NOT CERTIFIED · the head started (%s), but %s · %.0f s after "
                    "the check began (%d read(s))%s" % (a.run, detail, why, elapsed, reads, skipped))
                return 1
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
    oi = last_index(events, ("run-open",))
    # An attended record carries no run-open (the plain-lane-run shape, reflect-inputs' attended
    # form): its window opens at the record's first stamped event, and the source says so.
    ro = events[oi] if oi >= 0 else {}
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
    return start, end, "%s %s → %s %s" % (
        "run-open" if oi >= 0 else "the record's first event (no run-open: an attended record)",
        start, how, end)


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


def head_records(path):
    """[(epoch, True when the record is the head's own)] for every record of its transcript that
    is not a sidechain and carries a parseable timestamp, in time order, a tie keeping the file's
    order. None when the transcript is missing, unreadable or holds no head call, so the caller
    falls back to the record and says so, as head_calls does."""
    if not path or not os.path.isfile(path):
        return None
    found = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or rec.get("isSidechain"):
                    continue
                t = parse_ts(rec.get("timestamp"))
                if t is not None:
                    found.append((t, rec.get("type") == "assistant"))
    except OSError:
        return None
    found.sort(key=lambda record: record[0])
    return found if any(own for _, own in found) else None


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


def head_idle_s(records, running, t0, t1):
    """Seconds of [t0, t1] inside a transcript gap above IDLE_GAP_S and outside every lane
    interval, where the gap ends in something other than the head's own record: a gap the head's
    record ends is its own generation, thinking or writing, and never idleness (register entry
    2026-10-15 01:33 e). The span's edges are the head's own acts (the previous boundary, this
    one), so a gap to the last edge counts as a wait."""
    points = [(t0, False)] + [r for r in records if t0 < r[0] < t1] + [(t1, False)]
    idle = 0.0
    for (a, _), (b, ends_in_head) in zip(points, points[1:]):
        if b - a <= IDLE_GAP_S or ends_in_head:
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
    """Count omitted preview words; complete reports contribute zero, and so does a preview the
    head asked to be empty (`--report-words 0`, shown as 0), since it reads the report itself and
    the wrapper cut nothing. Legacy records without the display fields use their historical
    format's shown count."""
    if not isinstance(words, int) or isinstance(words, bool):
        return 0
    if "report_cut" not in ev:
        return max(0, words - REPORT_CAP_WORDS)
    if ev.get("report_cut") is not True:
        return 0
    shown = ev.get("report_shown")
    if isinstance(shown, int) and not isinstance(shown, bool) and 0 <= shown <= words:
        return words - shown if shown else 0
    return max(0, words - REPORT_CAP_WORDS)


def waste_fields(events, since, transcript=None, now_ts=None, meter_lanes=True):
    """The waste classes over the events after index `since` (the previous boundary, else
    run-open), each with its derivation (register entries of 2026-09-05):
      - idle_min: head idleness — the time in the span (that event's timestamp to now) when
        no lane was running and the head was waiting, a transcript gap counting only above
        IDLE_GAP_S and only when it ends in something other than the head's own record
        (head_idle_s). Lane running time comes from the record (lane-open or lane-resumed to the
        lane's next lane-closed); the transcript is `transcript`, the path measure_head found,
        labelled idle_src `transcript`, idle_rule `waits`. When the transcript is missing or
        carries no timestamped call, the record alone measures it as the rule before this one
        did — silence after each lane close until the head's next recorded act, summed per
        close — labelled idle_src `record`, which under parallel lanes overstates.
      - denials: the LANES' tool denials, summed from the wrappers' counts; head_denials,
        beside it and never added to it, is the head fence's own denies in the span
        (head_fence_denials, head_denials_src; register entry 2026-09-06). fence_denials and
        sandbox_denials, each in its own labelled field and never added to `denials`, sum the
        lanes' own fence and sandbox counts from their closes (register entry 2026-10-02
        16:42: a Codex lane's sandbox denials sat on its close while every boundary read 0).
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
    fence_denials, sandbox_denials = 0, 0
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
            denials += denial_count(d.get("tool"))
            # The lanes' own fence and sandbox denials, each in its own labelled field beside the
            # tool denials and never added to them (register entry 2026-10-02 16:42: a Codex
            # lane's sandbox denials sat on its close while every boundary reported denials 0).
            fence_denials += denial_count(d.get("fence"))
            sandbox_denials += denial_count(d.get("sandbox"))
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
    records = head_records(transcript)
    if records is not None and span_start is not None and now_ts > span_start:
        idle = head_idle_s(records, lane_intervals(events, span_start, now_ts),
                           span_start, now_ts) / 60.0
        src = "transcript"
    else:
        idle, src = silence, "record"
    head_denials, head_denials_src = head_fence_denials(events, since, now_ts)
    return {"idle_min": round(idle, 1), "idle_src": src,
            "idle_rule": "waits" if src == "transcript" else None, "denials": denials,
            "fence_denials": fence_denials, "sandbox_denials": sandbox_denials,
            "head_denials": head_denials, "head_denials_src": head_denials_src,
            "over_cap_reports": over, "respawn_cost_usd": bucket_figure(lost),
            "respawn_src": bucket_src(lost), "respawn_excluded": excluded,
            "limit_cut_resumed": cut_count, "limit_cut_resumed_usd": bucket_figure(cut),
            "limit_cut_src": bucket_src(cut)}, unmeasured


def denial_count(value):
    """One denial counter from a lane close as a whole number: an int (never a bool) at or above
    zero, a numeric string, else 0 — a counter a wrapper did not write is no denial."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return 0


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


def root_untracked(vault):
    """(entries, line): the untracked, unignored entries at the vault's top level that a
    checkpoint commit's `git add -A` is about to take — files, and directories as `<name>/` —
    listed before the commit, advisory: the commit is not stopped (register entry 2026-10-02
    06:19: a head's stray downloads sat in the vault root, and the boundary commit takes the whole
    work tree). The listing is NUL-delimited, so any file name reads as it is; an entry below the
    top level is not listed. A listing git could not give is `unverified (<why>)`, never an empty
    list."""
    rc, out, err = git(vault, ["ls-files", "--others", "--exclude-standard", "--directory", "-z"])
    if rc != 0:
        why = "unverified (git ls-files exit %d%s)" % (rc, ": " + tail_of(out, err)
                                                       if tail_of(out, err) else "")
        return why, "untracked at the vault root: %s; the commit goes ahead" % why
    entries = [e for e in out.split("\0") if e]
    top = [e for e in entries if "/" not in e.rstrip("/")]
    if not top:
        return [], ("untracked at the vault root: none (%d untracked entr%s below it)"
                    % (len(entries), "y" if len(entries) == 1 else "ies"))
    return top, ("untracked at the vault root (advisory: the commit takes them with the rest): "
                 "%s" % ", ".join(top))


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
    """The next moment after now_ts at which the local clock reads hour:minute, as an epoch. Each
    day's candidate is built from that day's date (mktime normalises the day), never as the day
    before plus 86,400 s, which is an hour out across a clock change (25 October 2026 has 25 hours
    in Europe/London). A time the clock shows twice (the repeated hour when clocks go back) takes
    the later instant, so a wait never ends early; a time it skips (clocks going forward) takes
    mktime's normalised reading."""
    lt = time.localtime(now_ts)
    candidate = now_ts
    for days in (0, 1, 2):
        fields = (lt.tm_year, lt.tm_mon, lt.tm_mday + days, hour, minute, 0, 0, 0)
        exact = []
        for dst in (0, 1):
            t = time.mktime(fields + (dst,))
            r = time.localtime(t)
            if (r.tm_hour, r.tm_min, r.tm_isdst) == (hour, minute, dst):
                exact.append(t)
        candidate = max(exact) if exact else time.mktime(fields + (-1,))
        if candidate > now_ts:
            return candidate
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


def nothing_ran(events):
    """True when the record names no head that ran (every head session it names is a seed, or it
    names none) and no lane: the run's spend is then zero by construction, and a meter that finds
    nothing to read is no premise failure (a launcher's first successor on a seeded record)."""
    ids, seeds = run_heads(events)
    return not [sid for sid in ids if sid not in seeds] and not run_lanes(events)


def envelope_left(events, run, meter_override, start, path=None, spend_out=None,
                  write_cache=True):
    """(remainder, source): the envelope — its latest figure, `envelope_of` — minus the RUN's
    spend as the gate, the boundary and the close read it (run_spend: every head session metered
    alone plus every lane on the record), so the successor and the supervisor size the next head
    on the figure that refuses an item (register entry 2026-09-26 02:2x: the successor summed every
    head-exit's session total, a resumed or repaired head counted twice and each head's lanes with
    it, and aborted a run the close still metered USD 333 under its envelope). Where part of the
    figure is a floor the remainder is `at most` and the source says so. (None, reason) when the
    envelope is absent or nothing on the record could be metered or read — except a record on
    which nothing has run yet (nothing_ran), whose spend is zero. `start` is kept for the callers'
    signature; `meter_override` is the current head's billed line in hand. lane.py's spawn cap
    reads this same remainder: `spend_out`, a dict when given, receives the run_spend figure read,
    so a caller can print `at most` where its `floor` is set (register entry 2026-09-30 03:21), and
    `write_cache=False` leaves the meter cache unwritten, as a dry-run gate does."""
    envelope, esrc = envelope_of(events)
    if envelope is None:
        return None, esrc
    shown = envelope if esrc == "run-open" else "%s (%s)" % (envelope, esrc)
    spend = run_spend(events, run, path if path is not None else record_path(run),
                      session_line=meter_override, write_cache=write_cache)
    if isinstance(spend_out, dict):
        spend_out.update(spend)
    if not spend["measured"]:
        if nothing_ran(events):
            return round(float(envelope), 2), (
                "envelope $%s minus $0.00: nothing has run yet (%s)" % (shown, spend["src"]))
        return None, "the run's spend could not be metered: %s" % spend["src"]
    return round(float(envelope) - spend["usd"], 2), (
        "envelope $%s minus the run's spend %s%s (run_spend: %s)"
        % (shown, "at least " if spend["floor"] else "", usd(spend["usd"]), spend["src"]))


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
                                            "last": None, "lines": []})
        if ev.get("event") in ("lane-closed", "hold-beat"):
            lane["lines"].append(("close" if ev.get("event") == "lane-closed" else "beat", ev))
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


def weekly_reader():
    """(module, why): the weekly waste reader imported by file path for its reading of a session's
    costs, never copied (`classify` and `spend_line`, its Priced spend rule of 27 October); (None,
    why) when it is missing or does not import. AIMYTH_WEEKLY_WASTE names it for a staged copy."""
    global _WEEKLY
    if _WEEKLY is not None:
        return _WEEKLY
    path = os.environ.get("AIMYTH_WEEKLY_WASTE") or os.path.join(
        HERE, os.pardir, "weekly-audit", "weekly-waste.py")
    path = os.path.realpath(os.path.expanduser(path))
    if not os.path.isfile(path):
        _WEEKLY = (None, "no weekly reader at %s" % path)
        return _WEEKLY
    try:
        spec = importlib.util.spec_from_file_location("weekly_waste", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:   # a torn or broken file: report it and keep the sum
        _WEEKLY = (None, "the weekly reader at %s does not import: %s" % (path, exc))
        return _WEEKLY
    if not all(callable(getattr(module, name, None)) for name in ("classify", "spend_line")):
        _WEEKLY = (None, "the weekly reader at %s has no classify() or spend_line()" % path)
        return _WEEKLY
    _WEEKLY = (module, None)
    return _WEEKLY


def lane_recorded(name, lines, damaged):
    """(dollars, note) for one lane's recorded closes and beats, `lines` being (kind, event) in
    record order (register entry 2026-10-16 10:04). A Claude helper's total_cost_usd is a running
    total of its session, so each later close repeats the earlier passes, while records before 19
    September carry per-pass costs: each session is read from its own lines by the weekly reader's
    rule. Read as running totals it counts its last total, never the sum; read as per-pass costs,
    or as one line, its costs. What cannot be read stays the sum, an overstatement and the safe
    direction, and the note says why: a session that reads as neither, a line naming no session
    (which could be one of any session's), a damaged record line (likewise) and a missing reader.
    A session begun before this record counts its earlier passes too: the same direction."""
    costs = [money(ev.get("total_cost_usd")) for _, ev in lines]
    summed = sum(cost for cost in costs if cost is not None)
    if len(lines) < 2:
        return summed, ""
    if damaged:
        return summed, "summed: a damaged record line could be one of its sessions'"
    groups = {}
    for kind, ev in lines:
        sid = ev.get("session_id")
        if not isinstance(sid, str) or not sid.strip():
            return summed, "summed: a line names no session, so none can be read alone"
        groups.setdefault(sid, []).append((kind, ev))
    reader, why = weekly_reader()
    if reader is None:
        return summed, "summed: %s" % why
    total, notes = 0.0, []
    for sid, group in groups.items():
        priced = [money(ev.get("total_cost_usd")) for _, ev in group]
        priced = [cost for cost in priced if cost is not None]
        try:
            # The reader reads a price as JSON wrote it, an exact Decimal, never a float.
            seq = [reader.spend_line(SpendSource(json.loads(json.dumps(ev),
                                                            parse_float=reader.Decimal), n),
                                     kind, name) for n, (kind, ev) in enumerate(group, 1)]
            usable = all(line.basis == "priced" for line in seq)
            reading, evidence = reader.classify(seq) if usable else ("unclassified", None)
        except (ArithmeticError, AttributeError, KeyError, TypeError, ValueError) as exc:
            reading, evidence = "unclassified", "the reader failed on it: %s" % exc
        if reading == "running":
            total += priced[-1]
            notes.append("session %s reads as running totals: its last $%.2f, not the sum $%.2f"
                         % (sid[:8], priced[-1], sum(priced)))
        else:
            total += sum(priced)
            if reading == "unclassified" and len(group) > 1:
                notes.append("session %s summed: it reads neither as running totals nor as "
                             "per-pass costs" % sid[:8])
    return total, "; ".join(notes)


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
    so. Lanes: per lane, what its lane-closed costs AND its `hold-beat` costs come to, session by
    session (lane_recorded: a running total's last figure, never its sum; a held lane's beats are
    billable calls: the fold of 2026-09-17); a beat that recorded no cost is a
    gap like an unpriced close, so the lane reads as a floor and is named among the unmeasured,
    and the transcript fallback covers a lane's beats along with its passes, since a beat
    re-enters the session the transcript already holds — the larger of the recorded figure and the
    transcript is taken, so nothing is counted twice and a beat adds no pass. Where any close of a Claude lane
    lacks a cost, the lane has no close yet, or an open pass follows its last close (a
    lane-resumed or a respawn as its latest event: the fold of 2026-09-17), its transcript is
    metered and the LARGER of the recorded figure and the transcript's whole figure taken (the
    transcript covers every pass, so the two are never
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
    (something could not be metered, a line was malformed, or a lane is still running — no close
    yet, or an open pass after its last close — so it still spends: the figure is `at least`;
    register entry 2026-09-30 03:21), still_open (those lanes), src (the derivation in words) and
    meter_calls (how many meter runs this call made). A lane whose every close is priced is
    still metered from its transcript and the larger figure taken, so the figure never falls
    when a lane's source changes from its transcript to a lower recorded cost."""
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

    heads, skipped, unmetered, still_open = [], [], [], []
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
        priced = sum(1 for cost, _ in lane["closes"] if cost is not None)
        # The lane's beats (critic finding 3 of review): a beat that recorded a cost counts in
        # the lane's figure, and a beat that recorded none is a gap, so the figure reads as a
        # floor and the lane is named among the unmeasured rather than silently understated.
        beats_recorded = sum(cost for cost, _ in lane["beats"] if cost is not None)
        beats_priced = sum(1 for cost, _ in lane["beats"] if cost is not None)
        beats_free = sum(1 for cost, _ in lane["beats"] if cost is None)
        recorded, reading = lane_recorded(name, lane["lines"], bad)
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
        # A lane still running (no close yet, or an open pass after its last close) is still
        # spending: the run figure is a floor while any is (register entry 2026-09-30 03:21).
        if not lane["closes"] or open_pass:
            still_open.append(name)
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
        elif lane["sids"]:
            # Every close priced: the transcript is still metered and the LARGER of the two taken
            # (register entry 2026-09-30 03:21: a lane's figure changed source at its close, from
            # its transcript to a lower recorded cost, and the run figure fell while lanes still
            # spent). A lane whose transcript cannot be found or metered keeps its recorded figure.
            transcript, why = lane_transcript_path(lane["sids"][0])
            usd, how = (None, why) if transcript is None else meter(lane["sids"][0], transcript)
            if usd is not None and usd > recorded:
                fig, kind = usd, "metered"
                src = ("the larger of the transcript's $%.2f (%s) and the recorded $%.2f (%s)"
                       % (usd, how, recorded, src))
            elif usd is not None:
                src += " · its transcript's $%.2f is not larger" % usd
        lanes_out.append((name, fig, "%s · %s" % (src, reading) if reading else src, kind))
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
    if still_open:
        parts.append("still running: %s (the figure is a floor while a lane spends)"
                     % ", ".join(still_open))
    if bad:
        parts.append("%d malformed record line(s) skipped" % bad)
    return {"usd": round(heads_usd + lanes_usd, 2), "heads_usd": round(heads_usd, 2),
            "lanes_usd": round(lanes_usd, 2), "heads": heads, "lanes": lanes_out,
            "metered_heads": metered_n, "lanes_n": len(lanes_out), "plan": plan,
            "skipped": skipped, "unmetered": unmetered, "malformed": bad,
            "still_open": still_open, "measured": measured,
            "floor": bool(unmetered or bad or still_open),
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


@a3_expose_notices
def cmd_run_open(a):
    refuse_grants_file(a)
    check_grant_forms(a, "run-open", opening=True)
    path = record_path(a.run)
    events = read_record(path)[0] if os.path.isfile(path) else []
    if last_index(events, ("run-open",)) >= 0:
        die("run %s already has a run-open; a later head records run-resume" % a.run)
    token(a.session, "session id")
    handoff = os.path.realpath(os.path.expanduser(a.handoff))
    if not os.path.isfile(handoff):
        die("hand-off document not found: %s" % handoff)
    runbook_note = check_runbook(a)
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
    if getattr(a, "model", None):
        # The run's head model as a structured field (never parsed out of the free-text --head):
        # the model a successor or a resume inherits when it names none (resolve_head_model).
        ev["model"], ev["model_src"] = a.model, "arg"
    if getattr(a, "effort", None):
        ev["effort"], ev["effort_src"] = a.effort, "arg"      # read by resolve_head_effort
    if a.envelope_usd is not None:
        ev["envelope_usd"] = a.envelope_usd
    if a.expect_items:
        ev["expect_items"] = parse_expect_items(a.expect_items)
    ev["grants_file"] = grants_path(a.run)
    ev["on_limit"], ev["on_limit_src"] = on_limit_choice(a, ev["grants_file"])
    ev["viewer"], ev["viewer_src"] = viewer_choice(a, ev["grants_file"])
    ev["network"], ev["network_src"] = network_choice(a, ev["grants_file"])
    cap, cap_src = max_successors_choice(a, ev["grants_file"])
    if cap is not None:
        ev["max_successors"], ev["max_successors_src"] = cap, cap_src
    payload = grants_payload(a.run, "run-open", a.grant, a.write, ev["on_limit"], ev["viewer"],
                             ev["network"], cap, carry=read_grants(ev["grants_file"]))
    # The lists on the event are the contract the shrink guard reads when the file is gone.
    ev["grants"], ev["writes"] = payload["grants"], payload["writes"]
    if a.decisions_file:
        ev[DECISIONS_FILE] = decisions_digest_of(a.decisions_file)[0]   # a missing file refuses here
    trace, seeded = seed_trace(read_text(handoff, "hand-off").split("\n"))
    ev["trace_table"] = trace
    # The findings ledger, the same check once at the open (register entry 2026-09-14 19:35): a
    # seed whose section holds prose and no table is repaired before the first head starts.
    ledger, seeded = seed_ledger(seeded)
    ev["ledger_table"] = ledger
    say(runbook_note)
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


def check_runbook(a):
    """A premise failure when the run's runbook never names the boundary command (register entry
    2026-09-20 20:0x): the console draws an item's end from `phase-boundary` and `item-done` records
    alone, so a head that follows such a runbook reads as idle and its finished items as pending.
    The runbook is --runbook, else `<store>/stages/<run>/RUNBOOK.md`; with neither there, nothing is checked
    and the returned line says so. The check is on the command, never the bare word `boundary`,
    which a runbook can use of a hand-off row; it cannot tell that each item carries the line."""
    named = getattr(a, "runbook", None)
    path = (os.path.expanduser(named) if named else
            os.path.join(store_root(), "stages", token(a.run, "run id"), "RUNBOOK.md"))
    if not os.path.isfile(path):
        if named:
            die("--runbook %s is not a file; nothing written" % named)
        return "run-open: no runbook at %s, so no boundary line was checked" % path
    if not BOUNDARY_LINE_RE.search(read_text(path, "runbook")):
        die("the runbook %s never names `handsoff.py boundary`: the console draws an item's end "
            "from boundary and item-done records alone, so its items would read as pending though "
            "done; add the line for each item's end and open again; nothing written" % path)
    return "run-open: the runbook %s names the boundary command" % path


def resume_grant_fields(ev, payload, sources):
    """The grants keys and lists a rewriting run-resume records, each taken from the payload it
    writes and from the sources of the same plan (grants_plan), in the order the event has always
    carried them: the cap (where the payload sets one), on_limit, viewer, network, then the two
    lists — a rewrite records the lists it writes, as run-open and grants do, so the shrink
    guard's baseline follows an explicit narrowing and never a file narrowed by hand."""
    if "max_successors" in payload:
        ev["max_successors"] = payload["max_successors"]
        ev["max_successors_src"] = sources["max_successors"]
    ev["on_limit"], ev["on_limit_src"] = payload["on_limit"], sources["on_limit"]
    ev["viewer"], ev["viewer_src"] = payload["viewer"], sources["viewer"]
    ev["network"], ev["network_src"] = payload["network"], sources["network"]
    ev["grants"], ev["writes"] = payload["grants"], payload["writes"]
    ev["grants_src"], ev["writes_src"] = sources["grants"], sources["writes"]


@a3_expose_notices
def cmd_run_resume(a):
    refuse_grants_file(a)
    check_grant_forms(a, "run-resume")
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
    if getattr(a, "effort", None):
        ev["effort"], ev["effort_src"] = a.effort, "arg"      # read by resolve_head_effort
    if getattr(a, "model", None):
        ev["model"], ev["model_src"] = a.model, "arg"         # read by resolve_head_model
    ev["grants_file"] = grants_path(a.run)
    # Carry the run's configured write grants into its successor; a default-only rewrite
    # would silently narrow the successor's authorised scope.
    # --on-limit, --viewer or --max-successors alone rewrites that key alone: a list the call does
    # not name is carried from the file, under the shrink guard (register entry 2026-09-11 04:17).
    # The cap is one of the keys a resume rewrites (critic finding 7 of the review of 2026-10-11:
    # a cap-only resume kept the file and dropped the cap unread, a zero included); its value is
    # checked before anything is written (max_successors_choice: a whole number of at least 1).
    keep = (not a.grant and not a.write and getattr(a, "on_limit", None) is None
            and getattr(a, "viewer", None) is None
            and getattr(a, "max_successors", None) is None
            and not getattr(a, "add_grant", None) and not getattr(a, "add_write", None)
            and os.path.isfile(ev["grants_file"]))
    if getattr(a, "max_successors", None) is not None:
        max_successors_choice(a, ev["grants_file"])   # a given cap is checked first; no read
    if keep:
        # A kept file is read once for what the event reports; nothing is written to it.
        current = read_grants(ev["grants_file"])
        ev["on_limit"], ev["on_limit_src"] = on_limit_choice(a, ev["grants_file"], current)
        ev["viewer"], ev["viewer_src"] = viewer_choice(a, ev["grants_file"], current)
        ev["network"], ev["network_src"] = network_choice(a, ev["grants_file"], current)
        ev["grants"] = "kept"
        if a.dry_run:
            # The count on the dry run's line too (build review RV-CAP finding F6): a kept file is
            # the cap the real call would leave.
            say("run-resume: dry run · %s · %s"
                % (json.dumps(ev, ensure_ascii=False),
                   successors_clause(successors_left(events, a.run))))
            return 0
        write_pointer(a.run, sid)
        append_record(path, ev)
    elif a.dry_run:
        payload, sources, dropped, against = grants_plan(a, ev["grants_file"], events,
                                                         "run-resume")
        guard_shrink(a, "run-resume", dropped, against)
        resume_grant_fields(ev, payload, sources)
        # The count the rewrite would leave, read from the payload it plans (nothing is written),
        # as the real call's line reads it after its write (build review RV-CAP finding F6).
        say("run-resume: dry run · %s · %s"
            % (json.dumps(ev, ensure_ascii=False),
               successors_clause(successors_left(events, a.run, planned=payload))))
        return 0
    else:
        # A rewrite plans, writes the file and records its lists under the record's lock, the
        # record re-read inside it, so two calls adding a path each cannot lose either addition
        # (critic finding 4 of the batch's design review: concurrent lost additions). The event
        # takes every grants key from that one plan, never from a read before the lock (critic
        # finding F3 of the second review of 2026-10-11).
        with record_lock(path):
            events, _ = read_record(path)
            payload, sources, dropped, against = grants_plan(a, ev["grants_file"], events,
                                                             "run-resume")
            guard_shrink(a, "run-resume", dropped, against)
            resume_grant_fields(ev, payload, sources)
            write_grants(ev["grants_file"], payload)
            write_pointer(a.run, sid)
            append_record(path, ev)
    if stale is not None:
        append_record(path, event(a.run, "observation", phase="", what="stale-pack",
                                  note="run-resume: " + stale))
    added = bool(getattr(a, "add_grant", None) or getattr(a, "add_write", None))
    carried = not keep and not a.grant and not a.write and not added
    say("run-resume: %s · session %s (%s) · pid %s (%s) · grants %s%s · on_limit %s · viewer %s · "
        "network %s%s · %s"
        % (a.run, sid[:8], how, "none" if pid is None else pid, src, ev["grants_file"],
           " (kept)" if keep else (" (lists carried)" if carried
                                   else " (paths added)" if added else ""),
           ev["on_limit"], ev["viewer"], network_shown(ev["network"]),
           " · max_successors %d (%s)" % (ev["max_successors"], ev["max_successors_src"])
           if "max_successors" in ev else "",
           # the count every head sees at its first act (register entry 2026-10-30 16:11),
           # read after any cap this call wrote
           successors_clause(successors_left(events, a.run))))
    return 0


LEDGER_HINT = (" — a record with no run-open is a plain lane run: `ledger --observation \"<what>\"`"
               " writes an observation there, with no hand-off row")


def ledger_observation(a, path):
    """`ledger --observation`: ONE observation event on any record that exists, and no hand-off
    row. On a plain record (no `run-open`) it is the only ledger form there is; on a record with
    a `run-open` it is the head's aside that is not a finding, so the findings ledger keeps only
    findings. `--phase` is optional and the phase is empty without it. A run with no record yet
    gets one, holding this observation alone (register entry 2026-09-19 02:55: a plain lane run
    has no record until its first spawn, and the skill records the peer name before any spawn);
    the line says the record was created, so a mistyped run id is visible at once. An ack-shaped
    observation covers only this call's snapshot, including zero events for a new record;
    a relay appended after the read must stay pending, as with an explicit --ack."""
    events = []
    if not os.path.isfile(path):
        shape = "new record (created by this observation: a run with no record yet)"
    else:
        events = read_existing_record(path)
        shape = "plain lane run (no run-open)" if is_plain_run(events) else "run-open present"
    ev = event(a.run, "observation", phase=a.phase or "", what=a.observation)
    ev["caller_pid"], ev["caller_pid_src"] = head_event_caller()
    if str(ev.get("what") or "").startswith(ACK_PREFIX):
        ev[DECISIONS_SEEN] = len(events)
    if a.dry_run:
        say("ledger --observation: dry run · %s · %s"
            % (shape, json.dumps(ev, ensure_ascii=False)))
        return 0
    append_record(path, ev)
    say("ledger: observation recorded (%s) · %s · no hand-off row"
        % (one_line(a.observation)[:70], shape))
    return 0


def cmd_ledger(a):
    path = getattr(a, "record", None) or record_path(a.run)
    if any(getattr(a, key, None) is not None for key in
           ("notice_id", "notice_version", "notice_sha256")):
        try:
            return a3_receipt(a, path)
        except (a3_shared().A3Premise, OSError) as exc:
            die(str(exc))
    refuse_placeholder("ledger", {key: getattr(a, key, None) for key in
                                  ("observation", "phase", "what", "evidence", "routing")})
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
    # The row form can acknowledge too; its coverage is the checked snapshot, never a later
    # read or the event's eventual place behind a relay that raced this call.
    if str(ev.get("what") or "").startswith(ACK_PREFIX):
        ev[DECISIONS_SEEN] = len(events)
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
    one call and before the act; no observation beside them. The event carries `decision_id`
    HD-<n>, the next free number on the record, assigned under the record's lock and printed, so
    the disposition of the boundary that acts on it can name it (register entry 2026-10-05
    20:18; decision_refs)."""
    path = record_path(a.run)
    events = require_record(path, " — a plain lane run has no hand-off for the ledger row; "
                                  "`ledger --observation \"decision: …\"` records it there")
    what, grant = one_line(a.what or ""), one_line(a.grant or "")
    if not what or not grant:
        die("decision needs a non-empty --what and --grant")
    refuse_placeholder("decision", {"what": what, "grant": grant, "routing": a.routing})
    ho = handoff_of(events, a.handoff)
    lines = read_text(ho, "hand-off").split("\n")
    span, lines, seeded = ledger_table(lines, ho, "decision")
    row = "| %s | %s | %s | %s | %s |" % (hhmm(), cell(a.phase), cell("decision: " + what),
                                         cell("grant: " + grant), cell(a.routing))
    n = span[1] - span[0]
    if a.dry_run:
        ev = event(a.run, "decision", phase=a.phase, what=what, grant=grant,
                   decision_id=next_decision_id(events))
        say("decision: dry run · %s · ledger row %d would be %s%s"
            % (json.dumps(ev, ensure_ascii=False), n, row,
               " · the table would be created under the heading first" if seeded else ""))
        return 0
    # The identifier is assigned under the record's lock from the record re-read there, so two
    # decisions written at once never share one (critic finding 9 of the batch's design review:
    # a disposition names the decision it rests on by this identifier, never by prose).
    with record_lock(path):
        ev = event(a.run, "decision", phase=a.phase, what=what, grant=grant,
                   decision_id=next_decision_id(read_record(path)[0]))
        lines.insert(span[1] + 1, row)
        write_atomic(ho, "\n".join(lines))
        append_record(path, ev)
    if seeded:
        say(LEDGER_SEEDED_LINE % "decision")
    say("decision: recorded %s (%s · grant %s) · ledger row %d appended · a boundary's "
        "disposition names it as %s" % (ev["decision_id"], what[:60], grant[:40], n,
                                         ev["decision_id"]))
    return 0


def decision_warning(refs):
    """The boundary's warning lines for decision_refs: the missing identifiers, then the
    ambiguous ones; nothing when every named identifier has exactly one decision event."""
    if refs["missing"]:
        say("boundary: warn: the disposition names head decision(s) with no decision event on the "
            "record: %s — record each with `handsoff.py decision` before its act; the boundary is "
            "written as asked%s" % (", ".join(refs["missing"]),
                                    " (unverifiable: %s)" % refs["unverifiable"]
                                    if refs["unverifiable"] else ""))
    if refs["ambiguous"]:
        say("boundary: warn: unverifiable: %s each carried by more than one decision event, so the "
            "reference does not name one decision" % ", ".join(refs["ambiguous"]))


def next_decision_id(events):
    """The next head-decision identifier, `HD-<n>`: one above both the highest identifier the
    record's decision events carry and their count, so an older decision written without one
    never shares a number with a new one."""
    top = sum(1 for e in events if e.get("event") == "decision")
    for e in events:
        if e.get("event") != "decision":
            continue
        m = HEAD_DECISION_RE.fullmatch(str(e.get("decision_id") or ""))
        if m:
            top = max(top, int(m.group(1)))
    return "%s%d" % (HEAD_DECISION_PREFIX, top + 1)


def decision_refs(events, disposition, bad=0):
    """The head decisions a boundary's disposition names, checked against the record (owner's
    provisional choice of 2026-10-10: explicit references, never prose matching). Returns a dict:
    `named` (each HD-<n> the text carries, in order), `missing` (no decision event carries it),
    `ambiguous` (two or more do) and `unverifiable` (a reason, when the record has unparseable
    lines and an absent identifier may sit in one). An owner decision (`D<n>`) is not a head
    decision and is never checked; a disposition naming no HD- identifier is checked for nothing.
    Coverage limit, stated: a decision the text describes in words and does not name by its
    identifier is not seen, and the check reads whether a record exists, not whether it was
    written before the act."""
    named = []
    for m in HEAD_DECISION_RE.finditer(disposition or ""):
        ref = "%s%s" % (HEAD_DECISION_PREFIX, int(m.group(1)))
        if ref not in named:
            named.append(ref)
    ids = [str(e.get("decision_id")) for e in events
           if e.get("event") == "decision" and e.get("decision_id")]
    missing = [r for r in named if ids.count(r) == 0]
    ambiguous = [r for r in named if ids.count(r) > 1]
    return {"named": named, "missing": missing, "ambiguous": ambiguous,
            "unverifiable": ("%d unparseable record line(s): an identifier may sit in one" % bad
                             if bad and missing else None)}


def decisions_covered(events, i):
    """(count, flaw) for the gate event or ack observation at index `i`: how many of the record's
    leading events the decisions check behind it covered, and why a present DECISIONS_SEEN was
    refused (None when it was not). It is the one reading of the field: the gate's hold, the
    close's hold and the pending list all reach it through decisions_reference, so no two readers
    can disagree. Coverage fails closed (the head's provisional replacement, under the owner's
    rule on stopped designs, of the reading three critic reviews of 2026-10-11 found faulty; the
    third review's finding N1: a malformed value fell back to full coverage and hid the relay it
    stood behind):
    - the field ABSENT, an event written before it existed: the legacy reading, through the
      event's own place (i + 1), as every event covered before;
    - the field a whole number (never a boolean) from 0 to `i`, the count of the events before
      this one and so the most a check that read the record before this event was appended can
      have read: that many (critic finding F1 of the second review: a close held by its final
      recheck had already recorded its ack, behind the owner's relay that raced its read);
    - the field present with any other value (a string, a boolean, null, a float, a negative
      number, or a number above `i`): 0, covering nothing, so a relay it would have hidden stays
      pending until a fresh, valid acknowledgement."""
    ev = events[i]
    if DECISIONS_SEEN not in ev:
        return i + 1, None
    seen = ev[DECISIONS_SEEN]
    if isinstance(seen, int) and not isinstance(seen, bool) and 0 <= seen <= i:
        return seen, None
    try:
        shown = json.dumps(seen, ensure_ascii=False)
    except (TypeError, ValueError):
        shown = repr(seen)
    return 0, ("%s %s, not a whole number from 0 to %d (the events before it)"
               % (DECISIONS_SEEN, shown[:40], i))


def decisions_reference(events):
    """(index, label) of the decisions channel's reference point: the last record event covered
    by the furthest-reaching decisions check behind a `gate` event or an `ack: …` observation
    (decisions_covered — the record as that check read it, so what was appended between a call's
    read and its own write stays pending), else the record's last run-open or run-resume, else
    the record's start (-1). An AUTHOR observation after the index is pending. Where no AUTHOR
    observation sits between that read and the event's own place — every call no relay raced,
    and every event written before DECISIONS_SEEN existed — the index and the label are the
    event's own, the later of the last gate and the last ack, exactly as before. A gate or ack
    whose DECISIONS_SEEN is refused takes part with a coverage of 0 rather than being passed over:
    passed over, it could leave a later run-resume as the reference and so hide the relays before
    that resume. Where no other gate or ack covers anything, the reference is the record's start,
    every AUTHOR observation is pending, and the label names the refused value."""
    best, at, flaw = 0, -1, None
    for i, ev in enumerate(events):
        if ev.get("event") == "gate" or (ev.get("event") == "observation"
                                         and str(ev.get("what") or "").startswith(ACK_PREFIX)):
            covered, why = decisions_covered(events, i)
            if covered >= best:   # a tie names the later event
                best, at, flaw = covered, i, why
    if at < 0:
        i = last_index(events, ("run-open", "run-resume"))
        if i < 0:
            return -1, "the record's start"
        return i, "the %s at %s" % (events[i].get("event"), events[i].get("ts", "no ts"))
    kind = "gate" if events[at].get("event") == "gate" else "ack observation"
    stamp = events[at].get("ts", "no ts")
    if flaw is not None:
        return -1, ("the record's start, since the %s at %s carries %s and so covers nothing"
                    % (kind, stamp, flaw))
    if any(e.get("event") == "observation" and AUTHOR_RE.match(str(e.get("what") or ""))
           for e in events[best:at]):
        return best - 1, "the record's first %d event(s), as the %s at %s read it" % (
            best, kind, stamp)
    return at, "the %s at %s" % (kind, stamp)


def decisions_pending(events, dfile, content=None):
    """(the AUTHOR observations after the reference, the decisions file's line or None, the
    reference's label). A named file is pending unless its whole content matches the digest and
    size the last accepted ack recorded, whatever any timestamp says (IDEAS 171 (b): the hold is
    keyed on the content, never on an mtime). A missing or unreadable file is a premise failure:
    a mistyped path would never hold. `content` is the (path, bytes, digest) the caller already
    read, so the hold and the ack check read the file once."""
    ref, label = decisions_reference(events)
    authored = [e for e in events[ref + 1:] if e.get("event") == "observation"
                and AUTHOR_RE.match(str(e.get("what") or ""))]
    changed = None
    if dfile is not None:
        fpath, data, digest = content if content is not None else decisions_digest_of(dfile)
        ack = last_digest_ack(events)
        if ack is None or ack["digest"] != digest or ack["size"] != len(data):
            changed = ("the decisions file %s has content no accepted ack covers (%d byte(s), "
                       "sha256 %s): read it" % (fpath, len(data), digest))
    return authored, changed, label


def decisions_hold(a, path, events, what):
    """The decisions channel before a gate or a close (register entry 2026-09-13 03:53): exit 6
    with the pending lines, writing nothing; None to proceed — when nothing is pending, or once
    --ack's observation is recorded. With --decisions-file the ack also carries --ack-digest, the
    file's whole sha256 as decisions-read printed it (IDEAS 171 (b); register entry 2026-09-20
    14:29: a close cleared its hold on an ack composed from memory and dropped two owner lines;
    register entry 2026-09-24 12:3x: a gate's ack cited an older line than the file held): a
    missing digest, or one that is not the file's at the call, holds (exit 6) with the unread
    lines and nothing recorded, and an accepted ack records the digest and the size it covered.
    A run with no decisions file acks with --ack alone, as before. Returns (code or None, the
    (path, bytes, digest) the call read or None) — the close keeps the content it acknowledged
    for its final recheck. The ack observation this call appends is kept on `a.own_ack`, so the
    close's recheck can leave out that one event and no other (close_recheck). It carries
    DECISIONS_SEEN, the length of the record this call checked, and covers that much and no
    more: a relay appended after the read stays pending for the next call even where the ack
    lands after it, so a close its recheck holds leaves nothing acknowledged that it never showed
    (decisions_covered)."""
    ack = getattr(a, "ack", None)
    if ack is not None and not one_line(ack):
        die("--ack is empty: name what was read, in one line")
    dfile = a.decisions_file = bound_file(a, events)
    given = ack_digest_given(ack, dfile, getattr(a, "ack_digest", None))
    content = decisions_digest_of(dfile) if dfile is not None else None
    authored, changed, label = decisions_pending(events, dfile, content)
    if ack is not None:
        line = one_line(ack)
        proof, shown = {}, ""
        if dfile is not None:
            fpath, data, digest = content
            if given != digest:
                return ack_digest_hold(a, events, what, fpath, data, digest, given), content
            proof = {"digest": digest, "size": len(data), DECISIONS_FILE: fpath}
            shown = " · digest %s… is the decisions file's at the call (%s, %d byte(s))" % (
                digest[:12], fpath, len(data))
        if not a.dry_run:
            own = event(a.run, "observation", phase="", what=ACK_PREFIX + line,
                        note="%s: %d AUTHOR observation(s) after %s%s" % (
                            what, len(authored), label, "; " + changed if changed else ""),
                        **proof)
            # What this ack covers is the record this call read, never its own place: a relay
            # appended between the read and this append stays pending (decisions_covered).
            own[DECISIONS_SEEN] = len(events)
            append_record(path, own)
            a.own_ack = own
        say("%s: ack %s (%s) · %d AUTHOR observation(s)%s pending at the call%s"
            % (what, "would be recorded" if a.dry_run else "recorded", line[:80], len(authored),
               " and a changed decisions file" if changed else "", shown))
        return None, content
    if not authored and not changed:
        return None, content
    say("%s: HOLD (decisions channel, exit %d) — %d AUTHOR observation(s)%s after %s: read them, "
        "then re-run with --ack \"<one line naming what was read>\"%s"
        % (what, EXIT_HOLD, len(authored), " and a changed decisions file" if changed else "",
           label, " --ack-digest <the sha256 decisions-read prints>" if dfile is not None else ""))
    for e in authored:
        text = "%s · %s" % (e.get("ts", "no ts"), one_line(e.get("what") or ""))
        if e.get("note"):
            text += " · " + one_line(e["note"])
        say("  " + text[:NOTE_CUT])
    if changed:
        say("  " + changed)
        start, which = decisions_unread(events, content[1])
        unread = text_lines(content[1][start:])
        say("  %d unread line(s), %s:" % (len(unread), which))
        for line in unread:
            say("  | " + line)
    if dfile is not None:
        say("  " + decisions_read_hint(a.run, dfile))
    return EXIT_HOLD, content


def decisions_binding(events):
    """The run's decisions file as its record binds it: the newest DECISIONS_FILE on a run-open, a
    gate or an accepted ack, else None. A close's own field and a lane's line never bind."""
    for ev in reversed(events):
        value = ev.get(DECISIONS_FILE)
        if isinstance(value, str) and value and (
                ev.get("event") in ("run-open", "gate")
                or (ev.get("event") == "observation"
                    and str(ev.get("what") or "").startswith(ACK_PREFIX))):
            return value
    return None


def bound_file(a, events):
    """The file this call acts on: --decisions-file, else the record's binding, else None. A path
    other than the binding is refused (exit 2): the one way a binding could silently move to a copy
    nobody writes, such as a helper's staged reference copy."""
    given = getattr(a, "decisions_file", None)
    bound = decisions_binding(events)
    if given is None:
        return bound
    real = os.path.realpath(os.path.expanduser(given))
    if bound is not None and real != bound and os.path.isfile(real):
        die("--decisions-file %s is not this run's decisions file (%s, bound on its record): a run "
            "keeps one file, so read that one; if it has moved, put it back at that path" % (
                real, bound))
    return given


def decisions_read_hint(run, dfile):
    """The one instruction every digest hold ends with: read the file with decisions-read, then
    ack with the digest it printed."""
    return ("read it with `handsoff.py decisions-read --run %s --decisions-file %s`, then re-run "
            "with --ack \"<one line naming what was read>\" --ack-digest <the digest it prints>"
            % (run, shlex.quote(os.path.realpath(os.path.expanduser(dfile)))))


def ack_digest_given(ack, dfile, raw):
    """--ack-digest normalised to lower case, or None when it was not given. Refused before
    anything is read (exit 2): a digest with no --ack (it proves an ack's read and travels with
    one), a digest with no --decisions-file (nothing names the content it would be checked
    against), and any value that is not a whole sha256."""
    if raw is None:
        return None
    if ack is None:
        die("--ack-digest was given without --ack: the digest proves the read an ack names, so it "
            "travels with one; pass --ack \"<one line naming what was read>\" beside it")
    if dfile is None:
        die("--ack-digest was given without --decisions-file: the digest names a decisions "
            "file's content and no file was named to check it against; pass --decisions-file "
            "<the file decisions-read read>, or drop the digest on a run with no decisions file")
    value = raw.strip().lower()
    if not DIGEST_RE.fullmatch(value):
        die("--ack-digest %r is not a whole sha256 (64 hexadecimal characters, %d given): pass the "
            "full `digest:` value decisions-read printed; a prefix is refused"
            % (raw[:80], len(value)))
    return value


def decisions_digest_of(dfile):
    """(real path, bytes, sha256) of the decisions file at this call — the content an ack's
    digest is checked against and decisions-read prints. A file missing or unreadable at the call
    is a premise failure naming the path (exit 2), never a pass."""
    fpath = os.path.realpath(os.path.expanduser(dfile))
    if not os.path.isfile(fpath):
        die("--decisions-file %s is not a file at this call (%s): create it (empty is fine) or "
            "pass the path the run's decisions are written to; nothing is acknowledged against a "
            "file that is not there" % (dfile, fpath))
    try:
        with open(fpath, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        die("cannot read the decisions file %s (%s): a file this call cannot read is never "
            "acknowledged" % (fpath, exc))
    return fpath, data, hashlib.sha256(data).hexdigest()


def last_digest_ack(events):
    """The record's last `ack: …` observation carrying a digest and a size — an ack accepted
    against the decisions file's content — else None. An ack without them (a run with no
    decisions file, or one recorded before the digest) says nothing about the file, so it is
    passed over rather than read as covering none of it."""
    for ev in reversed(events):
        if ev.get("event") != "observation" or \
                not str(ev.get("what") or "").startswith(ACK_PREFIX):
            continue
        digest, size = ev.get("digest"), ev.get("size")
        if isinstance(digest, str) and DIGEST_RE.fullmatch(digest) and isinstance(size, int) \
                and not isinstance(size, bool) and size >= 0:
            return ev
    return None


def decisions_unread(events, data):
    """(offset, which) for the part of the decisions file the run has not acknowledged: the bytes
    after the size the last accepted ack covered, when the file's first that-many bytes still
    hash to that ack's digest (the file was only appended to since); else the whole file — no
    accepted ack, or its prefix no longer matches (edited or cut since). `which` says which."""
    ack = last_digest_ack(events)
    if ack is None:
        return 0, "the whole file: the record carries no accepted ack with a digest"
    size, stamp = ack["size"], ack.get("ts", "no ts")
    if size > len(data) or hashlib.sha256(data[:size]).hexdigest() != ack["digest"]:
        return 0, ("the whole file: the %d-byte prefix the last accepted ack (%s) covered no "
                   "longer hashes to its digest, so the file was edited or cut since, not only "
                   "appended to" % (size, stamp))
    which = ("the lines after byte %d, the size the last accepted ack (%s) covered (that prefix "
             "is unchanged)" % (size, stamp))
    if 0 < size < len(data) and data[size - 1:size] != b"\n":
        which += ("; byte %d falls inside line %d, so the first line below continues it"
                  % (size, data[:size].count(b"\n") + 1))
    return size, which


def text_lines(data):
    """Bytes as text lines split at newlines alone — a final newline ends the last line and opens
    no empty one — undecodable bytes replaced, never dropped."""
    text = data.decode("utf-8", "replace")
    lines = text.split("\n") if text else []
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def digest_prefix(data, given):
    """The length of the prefix of `data`, ending at a line end or at the end of the file, whose
    sha256 is `given` — the file as the read that digest names saw it, when the file has only
    grown since — else None. One incremental pass: hexdigest() leaves the hash open to update."""
    h = hashlib.sha256()
    if h.hexdigest() == given:
        return 0
    start = 0
    while start < len(data):
        end = data.find(b"\n", start)
        end = len(data) if end < 0 else end + 1
        h.update(data[start:end])
        if h.hexdigest() == given:
            return end
        start = end
    return None


def ack_digest_hold(a, events, what, fpath, data, digest, given):
    """The hold on an ack whose digest is missing or is not the decisions file's at the call
    (exit 6, nothing recorded): why, the unread lines — those appended after the read the given
    digest names, when it names a prefix of the file as it stands, else those after the last
    accepted ack — and the instruction to read the file with decisions-read."""
    if given is None:
        why = ("the ack carries no --ack-digest: with --decisions-file an ack repeats the sha256 "
               "decisions-read printed for the file, so it names a read, never one composed from "
               "memory")
        start, which = decisions_unread(events, data)
    else:
        why = ("the ack's digest %s… is not the decisions file's at the call (%s…): the file is "
               "not what the read it names saw" % (given[:12], digest[:12]))
        grown = digest_prefix(data, given)
        if grown is not None:
            start = grown
            which = ("the lines appended since that read (the digest is the file's first %d "
                     "byte(s)%s)" % (grown, ", through line %d" % data[:grown].count(b"\n")
                                    if grown else ": the file was empty at that read"))
        else:
            start, which = decisions_unread(events, data)
            which = "the digest names no line-end prefix of the file, so " + which
    lines = text_lines(data[start:])
    say("%s: HOLD (decisions channel, exit %d) — %s; nothing recorded"
        % (what, EXIT_HOLD, why))
    say("  %s · %d byte(s) at the call · %d unread line(s), %s:"
        % (fpath, len(data), len(lines), which))
    for line in lines:
        say("  | " + line)
    say("  " + decisions_read_hint(a.run, fpath))
    return EXIT_HOLD


def head_unacknowledged(events):
    """True when the record's last digest ack is an earlier head's: it stands before this head's
    run-open or run-resume. A fresh head inherits that ack and has read nothing."""
    ack = last_digest_ack(events)
    at = max((n for n, ev in enumerate(events) if ev is ack), default=-1)
    return ack is not None and at < last_index(events, ("run-open", "run-resume"))


def cmd_decisions_read(a):
    """`decisions-read --run R [--decisions-file F]` (IDEAS 171 (b)): the lines of F the run has not
    acknowledged — after the size the last accepted ack covered, or the whole file when there is
    none, its prefix no longer matches or the ack is an earlier head's, the first line saying which
    — then one line `digest: <sha256 of the whole file at this read>`, the value --ack-digest
    takes. F defaults to the file the record binds. It reads the record and the file and writes
    nothing; exit 2 on a missing record, on no file named or bound, or on a file missing or
    unreadable at the read."""
    events = read_existing_record(getattr(a, "record", None) or record_path(a.run))
    dfile = bound_file(a, events)
    if dfile is None:
        die("no decisions file: this record binds none and --decisions-file was not given")
    fpath, data, digest = decisions_digest_of(dfile)
    start, which = decisions_unread(events, data)
    if head_unacknowledged(events):
        start, which = 0, "the whole file: this head has acknowledged nothing yet"
    lines = text_lines(data[start:])
    say("decisions-read: %s · %d byte(s) · %d unread line(s), %s"
        % (fpath, len(data), len(lines), which))
    for line in lines:
        say(line)
    say("digest: %s" % digest)
    return 0


def cmd_decisions_ack(a):
    """`decisions-ack --run R --ack LINE --ack-digest SHA256`: the acknowledgement between gates,
    which a spawn hold asks for. It is decisions_hold's own ack: one `ack:` observation carrying
    the digest and decisions_seen, or a hold (exit 6) on a stale digest, nothing recorded. A
    spawn never acknowledges for the head, and a peer session cannot acknowledge for it (exit 9)."""
    if a.ack is None:
        die("decisions-ack needs --ack \"<one line naming what was read>\"")
    path = getattr(a, "record", None) or record_path(a.run)
    events = require_record(path)
    refused = refuse_two_heads(a, path, events, "decisions-ack")
    if refused is not None:
        return refused
    held, _ = decisions_hold(a, path, events, "decisions-ack")
    return held if held is not None else 0


def record_admits_damage(path):
    """True when the strict reader accepts the record's damaged lines: a `record-tail-repaired`
    repair keeps the line in place, so read_record still counts it as unparseable."""
    shared = a3_shared()
    try:
        shared.a3_record_rows(path)
    except (shared.A3Premise, OSError):
        return False
    return True


def hold_logged(state, events):
    """`state` with `logged` set when this head's trial line already stands for this digest and
    reason, so a burst or a long run logs a state once and every line can be read against the file."""
    start = max(0, last_index(events, ("run-open", "run-resume")))
    state["logged"] = any(ev.get("event") == "observation"
                          and str(ev.get("what") or "").startswith(HOLD_TRIAL_PREFIX)
                          and ev.get("digest") == state["digest"] and ev.get("note") == state["why"]
                          for ev in events[start:])
    return state


def decisions_spawn_state(path):
    """What a launcher reads before it starts a helper: a dict with `state` clear, hold or unknown,
    `why`, `lines` (the unread text), `file`, `digest`, `size`, `route` (what clears an unknown) and
    `logged` (hold_logged). Reads only. Clear: no record yet; a plain lane run, which has no head to
    acknowledge; a closed run, which has none either; nothing pending. Hold: an unread AUTHOR
    observation, a file no accepted ack covers, or a file this head has not acknowledged itself
    (a fresh head inherits its predecessor's ack, and has read nothing). Unknown: the record or the
    bound file cannot be read, or a record line cannot be parsed, where a relay may sit."""
    state = {"state": "clear", "why": "", "lines": [], "file": None, "digest": None, "size": None,
             "route": "", "logged": False}
    if not os.path.lexists(path):
        state["why"] = "no record yet"
        return state
    try:
        events, bad = read_record(path)
        if bad:   # a torn last line can be a wrapper writing now (read_record): one more look
            time.sleep(HOLD_REREAD_S)
            events, bad = read_record(path)
        if bad and record_admits_damage(path):
            bad = 0
    except SystemExit:
        state.update(state="unknown", why="the run record %s cannot be read" % path)
        return state
    if bad:
        state.update(state="unknown", why="%d unparseable line(s) in %s: a relay may sit in one"
                                          % (bad, path),
                     route="a line a writer tore clears by itself once it completes; a damaged one "
                           "stays until `lane.py recover --run R --lane L --pass P "
                           "--repair-projection` on the pass that tore it admits it")
        return hold_logged(state, events)
    if is_plain_run(events):
        state["why"] = "a plain lane run: no head to acknowledge"
        return state
    if last_index(events, ("run-close",)) > last_index(events, ("run-open", "run-resume")):
        state["why"] = "a closed run: no head to acknowledge"
        return state
    dfile = decisions_binding(events)
    content = None
    if dfile is not None:
        state["file"] = dfile
        try:
            with open(dfile, "rb") as handle:
                data = handle.read()
            content = (dfile, data, hashlib.sha256(data).hexdigest())
        except (OSError, ValueError) as exc:
            state.update(state="unknown", why="the decisions file %s cannot be read (%s)"
                                              % (dfile, exc),
                         route="a run keeps one file: put it back at that path")
            return hold_logged(state, events)
        state["digest"], state["size"] = content[2], len(data)
    authored, changed, label = decisions_pending(events, dfile, content)
    lines = ["%s · %s" % (e.get("ts", "no ts"), one_line(e.get("what") or "")) for e in authored]
    why = []
    if authored:
        why.append("%d unread AUTHOR observation(s) after %s" % (len(authored), label))
    if changed:
        start, which = decisions_unread(events, content[1])
        lines += text_lines(content[1][start:])
        why.append("content no accepted ack covers (%s)" % which)
    elif dfile is not None and head_unacknowledged(events):
        lines += text_lines(content[1])
        why.append("this head has acknowledged nothing yet: the ack on the record is an earlier "
                   "head's")
    if why:
        state.update(state="hold", why="; ".join(why), lines=lines)
        hold_logged(state, events)
    return state


def decisions_spawn_lines(state, verb, lane, run, path=None, trial=False):
    """The text of a held or undecided spawn: what stopped it, a bounded view of the unread lines,
    the newest kept since the hold is about the newest decision, and the commands that clear it (a
    launcher takes no --ack). A record other than the run's default rides on each command. Under a
    trial the call goes on, so the text asks for no second spawn."""
    held = state["state"] == "hold"
    out = ["%s of lane %s: %s (decisions channel) — %s" % (
        verb, lane, "HOLD" if held else "CANNOT DECIDE", state["why"])]
    shown, size = [], 0
    for line in reversed(state["lines"]):
        if len(shown) >= HOLD_SHOWN_LINES or size + len(line) > HOLD_SHOWN_BYTES:
            break
        shown.insert(0, line)
        size += len(line)
    if state["lines"] and not shown:
        shown = [state["lines"][-1][:HOLD_SHOWN_BYTES]]
    if len(state["lines"]) > len(shown):
        out.append("  … %d earlier line(s) cut: decisions-read prints them all"
                   % (len(state["lines"]) - len(shown)))
    out += ["  | " + line for line in shown]
    named = ""
    if path and os.path.realpath(path) != os.path.realpath(record_path(run)):
        named = " --record %s" % shlex.quote(path)
    if held:
        if state["file"]:
            out.append("  read: handsoff.py decisions-read --run %s%s" % (run, named))
        out.append("  then: handsoff.py decisions-ack --run %s%s --ack \"<one line naming what was "
                   "read>\"%s%s" % (run, named, " --ack-digest <the digest it prints>"
                                    if state["file"] else "",
                                    "" if trial else ", and %s again" % verb))
    elif state.get("route"):
        out.append("  " + state["route"])
    return out


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
    """`run-is-closed --run R`: exit 0 when closed by event order, 1 when open,
    2 when the record cannot establish either answer; this does not establish liveness."""
    # A skipped line could be the resume that invalidates an earlier close. Read strictly,
    # once, without changing the tolerant reader used by the other commands.
    events = []
    try:
        with open(record_path(a.run), encoding="utf-8") as record:
            for number, line in enumerate(record, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if (not isinstance(row, dict) or not isinstance(row.get("event"), str)
                            or not row["event"]):
                        raise ValueError("expected an object with a non-empty event name")
                except ValueError as exc:
                    die("run-is-closed: %s unresolved (invalid record line %d: %s)"
                        % (a.run, number, exc))
                events.append(row)
    except (OSError, UnicodeError) as exc:
        die("run-is-closed: %s unresolved (cannot read run record: %s)" % (a.run, exc))
    if not events:
        die("run-is-closed: %s unresolved (empty run record)" % a.run)
    i = last_index(events, ("run-close",))
    if run_is_closed(events):
        say("run-is-closed: %s closed (run-close at %s after last run-open/run-resume)"
            % (a.run, events[i].get("ts", "no ts")))
        return 0
    if i >= 0:
        opened = events[last_index(events, ("run-open", "run-resume"))]
        say("run-is-closed: %s open (%s at %s after last run-close)"
            % (a.run, opened["event"], opened.get("ts", "no ts")))
    else:
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


def item_token(value):
    """A record's item string as the console keys it: its leading `item<id>` token, else itself."""
    text = str(value if value is not None else "").strip()
    found = re.match(r"item[A-Za-z0-9]*\b", text)
    return found.group(0) if found else text


def unbounded_items(events, lines):
    """The items the hand-off's `## In flight` names done with no phase-boundary from them on the
    record (register entry 2026-11-05 12:41: the console reads an item's end from boundary events
    alone, so a run that kept its item status in the hand-off read as idle, and its close as
    skipped). A line counts when it opens on an item the run declared or gated and a done word
    follows, unnegated: the status lines a lead writes, such as `item2 build · done, all tests`."""
    names, closed = set(), set()
    for ev in events:
        kind = ev.get("event")
        if kind == "gate":
            names.add(item_token(ev.get("item")))
        elif kind == "expect-items":
            names.update(item_token(name) for name in ev.get("items") or {})
        elif kind == "run-open":
            names.update(item_token(name) for name in ev.get("expect_items") or {})
        elif kind == "phase-boundary":
            closed.add(item_token(ev.get("from")))
        elif kind == "item-done":
            closed.update(item_token(name) for name in ev.get("items") or [])
    found = []
    for line in (section_text(lines, SECTIONS["inflight"]) or "").split("\n"):
        text = re.sub(r"^\s*(?:[-*]\s+)?\**", "", line)
        token = item_token(text.split(" ", 1)[0].rstrip(":·"))
        rest = text[len(token):]
        if (token in names and token not in closed and token not in found
                and ITEM_DONE_RE.search(rest) and not ITEM_UNDONE_RE.search(rest)):
            found.append(token)
    return found


def item_warning(who, events, lines):
    """One warning line for unbounded_items; the writer goes on as asked."""
    items = unbounded_items(events, lines)
    if items:
        say("%s: warn: the hand-off names %s done with no completion on the record, so the console "
            "reads %s as unfinished and the close as unresolved: record each with `item-done <item>`"
            ", late if need be" % (who, ", ".join(items), "it" if len(items) == 1 else "them"))


def items_unresolved(events):
    """[(item, its first start's time)] for the items the record started and shows no explicit
    completion of, in the order they started (register entry 2026-11-05 12:41). A gate, a lane's
    --item or an event whose `phase` names a declared item is activity and never completion; a
    phase-boundary from an item or an item-done ends it. A boundary's `to` alone is no start, but
    a lane with no --item starts the item in hand, as the console reads it. item0, the orientation
    row, is the one exception and follows watch.py's rule word for word: measured orientation, or
    work on phase item0, then the first allowed gate, on item1, settles it."""
    started, ended = {}, set()
    declared = {item_token(name) for name in declared_items(events)}
    current, oriented, first_work = "", False, True
    for ev in events:
        kind = ev.get("event")
        if first_work and item_token(ev.get("phase")) == "item0":
            oriented = True
        if ev.get("phase") and item_token(ev["phase"]) in declared:
            started.setdefault(item_token(ev["phase"]), ev.get("ts", "no ts"))
        if kind == "gate" and ev.get("item"):
            current = item_token(ev["item"])
            started.setdefault(current, ev.get("ts", "no ts"))
            if first_work:
                if isinstance(ev.get("orientation_tokens"), (int, float)):
                    oriented = True
                if ev.get("decision") == "allow" and current != "item0":
                    if current == "item1" and oriented:
                        ended.add("item0")
                    first_work = False
        elif kind == "lane-open":
            item = item_token(ev.get("item")) or current
            if item:
                started.setdefault(item, ev.get("ts", "no ts"))
        elif kind == "phase-boundary":
            if ev.get("from"):
                ended.add(item_token(ev["from"]))
            current = item_token(ev.get("to")) or current
        elif kind == "item-done":
            ended.update(item_token(name) for name in ev.get("items") or [])
    return [(item, at) for item, at in started.items() if item not in ended]


def items_on_record(events):
    """Every item the record names: declared, gated, a boundary's two ends or a lane's --item."""
    names = {item_token(name) for name in declared_items(events)}
    for ev in events:
        kind = ev.get("event")
        if kind in ("gate", "lane-open"):
            names.add(item_token(ev.get("item")))
        elif kind == "phase-boundary":
            names.update((item_token(ev.get("from")), item_token(ev.get("to"))))
    return names - {""}


def cmd_item_done(a):
    """`item-done --run R ITEM...`: an explicit completion record for each item, with no meter: what
    the console reads as done beside a boundary's `from`, for items worked side by side (register
    entry 2026-11-05 12:41). A name the record does not hold is written with a warning, since a pack
    can list an item no gate has reached. A closed run takes none: the board is the close's. Exit 9
    refuses a peer session, as gate does."""
    path = getattr(a, "record", None) or record_path(a.run)
    events = require_record(path)
    refused = refuse_two_heads(a, path, events, "item-done")
    if refused is not None:
        return refused
    if last_index(events, ("run-close",)) > last_index(events, ("run-open", "run-resume")):
        die("run %s is closed: a completion recorded after its close changes no verdict; nothing "
            "written" % a.run)
    refuse_placeholder("item-done", {"note": a.note})
    items = [item_token(name) for name in a.items]
    if not all(items):
        die("item-done: an empty item name; nothing written")
    known = items_on_record(events)
    for item in items:
        if item not in known:
            say("item-done: warn: %s is not on this record: check its spelling, since the console "
                "adds a row for it" % item)
    ev = event(a.run, "item-done", items=items)
    if a.note:
        ev["note"] = one_line(a.note)
    if a.dry_run:
        say("item-done: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        return 0
    append_record(path, ev)
    say("item-done: %s recorded on %s" % (", ".join(items), a.run))
    return 0


@a3_expose_notices
def cmd_boundary(a):
    path = record_path(a.run)
    events = require_record(path)
    refuse_placeholder("boundary", {key: getattr(a, key, None) for key in
                                    ("disposition", "next", "waste", "shipped", "waits", "saving")})
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
    # Credit only the head's foreground shell command, including its session-leading shell
    # directly below the harness. Workers and other session/group changes record null with
    # caller_pid_src none; the supervisor reads uncertain authorship as unknown.
    ev["caller_pid"], ev["caller_pid_src"] = head_event_caller()
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
    # The head decisions the disposition names (register entry 2026-10-05 20:18; the owner's
    # provisional choice of 2026-10-10: explicit HD-<n> references): a warning, never a refusal —
    # the exit status is the boundary's own and no event is invented for a missing decision.
    refs = decision_refs(events, a.disposition, read_record(path)[1])
    if refs["named"]:
        ev["decision_refs"] = refs
    # In flight re-derived at every boundary (register entry 2026-09-14 00:06: a hand-off named
    # item2 as next after five boundaries), keeping the relayed owner lines and the hand-written
    # lines of the pack it replaces; a hand-off with no In flight section is said, never a problem.
    current = section_text(lines, SECTIONS["inflight"])
    inflight = None
    if current is not None:
        inflight = derive_inflight(events + [ev], current=current, boundary=ev)
        set_section(lines, "inflight", inflight, derived=True)
    if a.dry_run:
        say("boundary: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        if not a.meter_line:
            say("boundary: dry run · meter invoked as %s" % meter_command_text(events, a.run))
        if problems:
            say("hand-off: would NOT refresh — %s" % "; ".join(problems))
        say("in flight: %s" % ("would be re-derived (%d lines)" % len(inflight.split("\n"))
                               if inflight is not None
                               else "the hand-off has no '## In flight' section: nothing to "
                                    "re-derive"))
        decision_warning(refs)
        return 0
    write_atomic(ho, "\n".join(lines))
    if a.commit is not None:
        # What a checkpoint commit will take from the vault root (register entry 2026-10-02
        # 06:19: a head's stray downloads sat in the vault root, and `git add -A` takes them).
        ev["root_untracked"], root_line = root_untracked(vault_root())
        say("boundary: %s" % root_line)
        ev["commit"] = checkpoint_commit(vault_root(), a.commit)
    append_record(path, ev)
    respawn = fields["respawn_cost_usd"]
    cut_usd = fields["limit_cut_resumed_usd"]
    say("boundary: %s → %s · idle %s min · denials %d · over-cap %d · %s · "
        "rewrites %s · context %s%s%s · idle src %s · rewrites since %s%s%s · head fence denials %s"
        " · lane fence denials %d · lane sandbox denials %d"
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
           "unmeasured" if fields["head_denials"] is None else fields["head_denials"],
           fields["fence_denials"], fields["sandbox_denials"]))
    say("in flight: %s" % ("re-derived from the record (%d lines; the relayed owner lines and "
                           "the pack's hand-written lines kept)" % len(inflight.split("\n"))
                           if inflight is not None
                           else "the hand-off has no '## In flight' section: nothing re-derived"))
    decision_warning(refs)
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
    item_warning("boundary", events + [ev], read_text(ho, "hand-off").split("\n"))
    for document, hits in stage_placeholders(a.run, parse_ts(events[prev].get("ts")) or 0):
        say("boundary: warn: the stage document %s carries the typed clock placeholder %s: read "
            "the time from a command or the record and correct it" % (document, ", ".join(hits)))
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


def resumed_item_work(events, scope):
    """The first item action (a decision, a lane spawned or resumed, a boundary) of a successor's
    session before its first gate, or None (register entry 2026-10-16 03:30): the head went on with
    the item in flight first, so the gate's context carries that work as well as its reading. The
    opening head of a run has no item in flight, so its own first gate is left measured."""
    if scope < 1 or events[scope - 1].get("event") not in ("run-resume", "head-successor"):
        return None
    return next((e["event"] for e in events[scope:] if e.get("event") in ITEM_WORK_EVENTS), None)


def orientation(events, scope, m):
    """(tokens, note) for a session's first gate (D41): the context now minus the transcript's
    first-call context; None with the reason when either is absent, and always None after a
    head-resumed event or a same-session run-resume, whose first call carries the whole
    session, or after resumed item work (resumed_item_work), which is not start-up reading."""
    if any(e.get("event") == "head-resumed" for e in events[scope:]):
        return None, "unmeasured after a resume"
    if same_session_resume(events, scope):
        return None, "unmeasured after a same-session resume"
    work = resumed_item_work(events, scope)
    if work:
        return None, "unmeasured: resumed item work (%s) before the first gate" % work
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


def envelope_stop(path, a, env_text, env_why, figure, clause=""):
    """The envelope stop: the stop-condition event (which envelope, lane head, the figures in
    its note) and the gate's exit 5. The run ends here; a successor refuses on the same figure.
    `clause` is the gate's successor count (successors_clause), appended so the line names both
    bounds the owner may have to lift."""
    figures = env_text[len("envelope: "):]
    append_record(path, event(
        a.run, "stop-condition", which="envelope", lane="head",
        action="gate refused item %s: the envelope is spent" % a.to,
        note="%s (%s)" % (figures, env_why)))
    say("gate: %s · %s · %s · REFUSED (stop-condition envelope: the remainder is at or below "
        "zero) → the run stops here; the owner tops the envelope up before any successor: "
        "handsoff.py raise-envelope --run %s --to USD --reason \"…\"%s"
        % (a.to, figure, env_text, a.run, " · " + clause if clause else ""))
    return EXIT_ENVELOPE


def gate_arrow(s, usual):
    """A gate refusal's instruction: `usual` (the hand-over) while a successor is left; with none
    left, close the run instead (register entry 2026-10-30 16:11); with none left on a fallback
    past a faulty grants file, the fault to repair first (review CR-CAP2 finding 6)."""
    if s["left"] > 0:
        return usual
    if s["fault"]:
        return ("→ no successor is left on a fallback cap, and the run's own cap cannot be read "
                "(the grants file is %s), so whether this head is the run's last lead is undecided: "
                "`handsoff.py grants --run %s --max-successors N` writes it (the cap the run "
                "set, which its record names) before %s" % (s["fault"], s["run"], usual[2:]))
    return ("→ no successor is left (successors: %d of %d started): watch in-flight lanes to "
            "their close while the room lasts, then close the run with its morning report "
            "(handoff --set bullets, then close)" % (s["used"], s["cap"]))


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
    # The top-up is checked against the RUN's spend, the figure the gate refuses on (register
    # entry 2026-09-17 21:08: the head-only figure let a top-up through that the gate would read
    # as already spent). A floor is compared as the floor it is; a run nothing could be metered
    # of falls back to the recorded head-exits, which the source says. A dry run leaves the
    # meter cache unwritten (critic finding 9 of the review of 2026-10-11).
    spend = run_spend(events, a.run, path, session_line=a.meter_line, write_cache=not a.dry_run)
    if spend["measured"]:
        spent = spend["usd"]
        ssrc = "the run's spend%s (run_spend: %s)" % (" at least" if spend["floor"] else "",
                                                       spend["src"])
    else:
        recorded, _ = spent_sum(events, last_index(events, SESSION_EVENTS))
        spent = recorded
        ssrc = ("every head-exit's spent_usd, since the run's spend could not be metered (%s)"
                % spend["src"])
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


def pack_remaining(events, ho):
    """Tokens left of the item in flight, from the optional `Remaining:` line of the hand-off's
    in-flight pack (`- Remaining: 120k`), or None (register entry 2026-09-23 20:3x). The line is
    read only from a pack written at or after the last gate, where the fit estimate's own figures
    stop, so a stale pack never replaces a fresher estimate."""
    if not ho:
        return None
    try:
        with open(ho, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().split("\n")
    except OSError:
        return None
    written, _ = pack_stamp(lines)
    gi = last_index(events, ("gate",))
    gated = parse_ts(events[gi].get("ts")) if gi >= 0 else None
    if written is None or (gated is not None and written < gated):
        return None
    found = PACK_REMAINING_RE.search(section_text(lines, SECTIONS["inflight"]) or "")
    if not found:
        return None
    return int(found.group(1).replace(",", "")) * (1000 if found.group(2) else 1)


def remaining_of(a, events):
    """The pack's figure for a supervisor or a hand-run resume, or None: the caller's hand-off,
    else the run-open's. Nothing here may stop a supervisor, so a missing one is simply no figure."""
    i = last_index(events, ("run-open",))
    return pack_remaining(events, getattr(a, "handoff", None)
                          or (events[i].get("handoff") if i >= 0 else None))


def resume_guard(events, m, start, remaining=None):
    """The hand-run resume's guard: (verdict, why, stop_class, stopped_at). `ok` only for a sound
    stop (never a refusal or an error) whose resume fits and is cheap; else `resume-refused` or
    `resume-unfit` with the reason the successor path is the answer. `remaining` is the pack's
    figure (pack_remaining), which sizes the resume in place of the estimate."""
    stop = next((e for e in reversed(events[start:]) if e.get("event") == "observation"
                 and e.get("what") == "head exited"), None)
    stop_cls = str((stop or {}).get("exit_class") or "limit")
    stopped_at = parse_ts((stop or {}).get("ts")) if stop else None
    if stop_cls in ("refusal", "error"):
        return ("resume-refused", "the head's last stop was a %s: never resumed by hand (a refusal "
                "re-flags; an error's state is not trusted); start the successor from the hand-off"
                % stop_cls, stop_cls, stopped_at)
    if not resume_in_place(events, m, stopped_at, remaining):
        return ("resume-unfit", "the rest of the item does not fit under the belt, or the resume is "
                "not cheap (cache cold, memory over a fresh start's orientation): start the "
                "successor from the hand-off", stop_cls, stopped_at)
    return ("ok", "", stop_cls, stopped_at)


def resume_in_place(events, m, stopped_at, remaining=None):
    """After a sound stop (limit, budget, a hand repair): resume the head in place only when the
    rest of its item fits under the belt AND the resume is cheap: the cache is still warm, or the
    memory is under a fresh head's orientation cost. The rest of the item is `remaining`, the
    hand-off's own figure (pack_remaining), and with none a whole item, conservatively. No memory
    figure: never; no estimate is impossible once a figure exists. The old 60 % rule stays as the
    fallback for an empty record shape (no gate ever metered and nothing declared: the prior
    then decides, which at 1M lands near the old mark)."""
    if m.get("context") is None:
        return False
    w, e = window(), edges()
    cost = remaining if remaining is not None else fit_estimate(events, None, m["context"])[0]
    warm = stopped_at is not None and (time.time() - stopped_at) <= CACHE_LIFE_S
    small = m["context"] <= int(w * ORIENTATION_SHARE)
    return fits(m["context"], cost, w, belt_of(e)) and (warm or small)


def report_hardstops_text(events):
    """The warnings bullet beside the limit stops: every head stop-condition whose `which` is not
    a limit, every lane closed other than completed or limit, and apart from those every completed
    lane that met denials, each count stated (owner ruling 2026-09-14: a hard stop is reported
    clearly, never searched-and-empty; register entry 2026-10-31 01:57: a denial stops nothing)."""
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
    denied = ["%s at %s (%s)" % (
                  ev.get("lane") or "unnamed lane", ev.get("ts", "no ts"),
                  ",".join("%s %s" % (k, v) for k, v in sorted(ev["denials"].items())
                           if k in DENIAL_KEYS and v))
              for ev in events if ev.get("event") == "lane-closed"
              and ev.get("exit_class") == "completed" and isinstance(ev.get("denials"), dict)
              and any(ev["denials"].get(k) for k in DENIAL_KEYS)]
    return ("%d hard stop(s) on the head other than a limit%s · %d lane(s) closed other than "
            "completed or limit%s · %d completed lane(s) met denials, none a stop%s · read from "
            "the record at the close" % (
                len(heads), ": " + "; ".join(heads) if heads else "",
                len(lanes), ": " + "; ".join(lanes) if lanes else "",
                len(denied), ": " + "; ".join(denied) if denied else ""))


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


def stale_references(run, decisions_file=None):
    """[(copy, source)] for each file of `<store>/stages/<run>/refs/` whose bytes differ from its
    source (register entry 2026-10-30 21:40 b): helpers read those copies so that none needs a
    grant on the vault root, and the gate's own digest reads only the live decisions file. The
    source of a copy is --decisions-file where the names agree, then the run's own
    `<store>/stages/<run>/decisions.md`, else the file of that name at the vault root; a copy
    with none has no source to compare, so it is left out. A warning alone, never a hold: most
    differences touch no helper's task, and the head can tell."""
    folder = os.path.join(store_root(), "stages", token(run, "run id"), "refs")
    decisions_file = decisions_file or os.path.join(os.path.dirname(folder), "decisions.md")
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    found = []
    for name in names:
        copy = os.path.join(folder, name)
        named = (decisions_file and os.path.basename(decisions_file) == name
                 and os.path.expanduser(decisions_file))
        source = named or os.path.join(vault_root(), name)
        if not os.path.isfile(copy) or not os.path.isfile(source):
            continue
        try:
            with open(copy, "rb") as one, open(source, "rb") as other:
                if one.read() != other.read():
                    found.append((copy, source))
        except OSError as exc:
            note("gate: the reference copy %s could not be compared (%s)" % (copy, exc))
    return found


@a3_expose_notices
def cmd_gate(a):
    path = record_path(a.run)
    events = require_record(path)
    # Two heads first (register entry 2026-09-03): a peer's gate reaches neither the hold nor the
    # meter. Then the decisions channel (register entry 2026-09-13 03:53). A gate has no final
    # recheck, so an owner's relay arriving while it meters is the next call's to hold: its event
    # and its ack therefore cover only `events`, the record this check read (DECISIONS_SEEN), and
    # never their own later place (critic finding F1 of the second review of 2026-10-11).
    refused = refuse_two_heads(a, path, events, "gate")
    if refused is not None:
        return refused
    held, content = decisions_hold(a, path, events, "gate")
    if held is not None:
        return held
    bound = {DECISIONS_FILE: content[0]} if content else {}
    sid, sev = head_session(events)
    scope = last_index(events, SESSION_EVENTS) + 1
    prior = [e for e in events[scope:] if e.get("event") == "gate"]
    # The successor count on every line and event (register entry 2026-10-30 16:11), so a head
    # knows before any hand-over whether it is the run's last lead.
    count = successors_left(events, a.run)
    clause = successors_clause(count)
    count_fields = {"successors_used": count["used"], "successors_cap": count["cap"],
                    "successors_left": count["left"], "successors_src": count["src"]}
    m = measure_head(sid)
    is_armed, how = armed(sid)
    warning = grants_warning(events, a.run, sid)
    if warning:
        say(warning)
    for copy, source in stale_references(a.run, getattr(a, "decisions_file", None)):
        say("gate: warn: the staged reference copy %s differs from its source %s: a helper spawned "
            "now reads the older text; refresh the copy before the next spawn" % (copy, source))
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
                   armed=is_armed, decision=decision, metered=False, **spend_fields,
                   **count_fields)
        ev[DECISIONS_SEEN] = len(events)   # what this gate's decisions check covered
        ev.update(bound)
        if orient is not None:
            ev["orientation_tokens"], ev["orientation_note"] = orient
        obs = event(a.run, "observation", phase=a.phase, what="gate unmetered",
                    note="item %s: %s%s" % (a.to, m["reason"],
                                            "; second consecutive" if second else ""))
        if a.dry_run:
            say("gate: dry run · unmetered (%s) · %s · %s · %s" % (m["reason"], decision, env_text,
                                                                clause))
            return 0
        append_record(path, ev)
        append_record(path, obs)
        if spent_out:
            return envelope_stop(path, a, env_text, env_why, "unmetered (%s)" % m["reason"],
                                 clause)
        if decision == "refuse":
            append_record(path, event(
                a.run, "stop-condition", which="unmetered", lane="head",
                action="gate refused item %s: second consecutive unmetered gate (armed by %s)"
                       % (a.to, how), note=m["reason"]))
            say("gate: unmetered (%s) · second consecutive · armed (%s) · REFUSED item %s %s · "
                "%s · %s"
                % (m["reason"], how, a.to,
                   gate_arrow(count, "→ handoff --final --band unmetered, then successor"),
                   env_text, clause))
            return 7
        say("gate: unmetered (%s) · %s · item %s allowed%s · %s · %s" % (
            m["reason"], "second consecutive" if second else "first miss", a.to,
            " · soft: fix the metering" if second else "", env_text, clause))
        return 0
    fit = fits(m["context"], cost_next, w, belt)
    over = not fit
    band_refusal = over and is_armed
    spend_refusal = spend_miss and second and is_armed
    decision = "refuse" if (band_refusal or spent_out or spend_refusal) else "allow"
    ev = event(a.run, "gate", item=a.to, context=m["context"], percent=m["percent"],
               band=m["band"], armed=is_armed, decision=decision, metered=True,
               fit=fit, cost_next=cost_next, cost_src=cost_src, belt=belt, **spend_fields,
               **count_fields)
    ev[DECISIONS_SEEN] = len(events)   # what this gate's decisions check covered
    ev.update(bound)
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
        say("gate: dry run · %s · %s · %s · %s%s · %s" % (a.to, figure, decision, env_text,
                                                         " · " + miss if miss else "", clause))
        return 0
    append_record(path, ev)
    if spend_miss:
        append_record(path, event(
            a.run, "observation", phase=a.phase, what="gate unmetered",
            note="item %s: the run's spend could not be metered: %s%s"
                 % (a.to, spend["src"], "; second consecutive" if second else "")))
    if spent_out:
        return envelope_stop(path, a, env_text, env_why, figure, clause)
    if band_refusal:
        append_record(path, event(
            a.run, "stop-condition", which="band", lane="head",
            action="gate refused item %s at %d %% (fit: next %s, %s, over the belt %d %%; armed by %s)"
                   % (a.to, m["percent"], format(cost_next, ","), cost_src, belt, how),
            note=gate_arrow(count, "→ handoff --final --band %d, watch in-flight lanes, then "
                                   "successor" % threshold)[2:]))
        say("gate: %s · %s · REFUSED (stop-condition band) %s · %s · %s"
            % (a.to, figure, gate_arrow(count, "→ handoff --final --band %d, watch in-flight "
                                               "lanes, then successor" % threshold),
               env_text, clause))
        return 4
    if spend_refusal:
        append_record(path, event(
            a.run, "stop-condition", which="unmetered", lane="head",
            action="gate refused item %s: second consecutive unmetered gate (the run's spend "
                   "unmetered; armed by %s)" % (a.to, how), note=spend["src"]))
        say("gate: %s · %s · %s · armed (%s) · REFUSED item %s %s · %s · %s"
            % (a.to, figure, miss, how, a.to,
               gate_arrow(count, "→ handoff --final --band unmetered, then successor"),
               env_text, clause))
        return 7
    warn = (" · warn: at or above the second edge (%d %%), soft — finish what is in flight, "
            "start nothing new" % threshold) if over else ""
    if spend_miss:
        warn += " · %s · item %s allowed%s" % (miss, a.to,
                                                " · soft: fix the metering" if second else "")
    say("gate: %s · %s · allow%s · %s · %s" % (a.to, figure, warn, env_text, clause))
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


PACK_DERIVED_PREFIX = "- pack re-derived from the record at "
# The Next a derivation takes from a head-written pack newer than the last phase-boundary. Its
# own words carry the pack's stamp, so a later derivation reads both back (HEAD_NEXT_RE) and
# keeps that Next until a genuinely newer boundary supersedes it (critic finding 4 of the review
# of 2026-10-11: a second derivation fell back to the older boundary's next).
HEAD_NEXT_LINE = "- Next: %s (from the head's own pack written %s, newer than %s)"
HEAD_NEXT_RE = re.compile(r"^- Next: (.*) \(from the head's own pack written ([^\s,]+), "
                          r"newer than .*\)$")
KEPT_HEADER = "- Kept from the pack this rewrite replaced (its hand-written lines, verbatim):"
OWNER_LINE = "- Owner (an AUTHOR observation on the record at %s): %s"
INFLIGHT_DERIVED_HEADING = "## In flight (re-derived from the record at %s)"
NEXT_LINE_RE = re.compile(r"^\s*(?:[-*]\s+)?Next:\s*(.*)$")


def open_lane_attempts(events):
    """[(lane, its latest lane-open or lane-resumed, the lane-spawned or lane-respawned after it
    or None)] for every lane whose latest attempt has no lane-closed after it, read over the WHOLE
    record (register entry 2026-09-25 17:4x: a scan from the last boundary missed a lane opened
    before it whose process died with no close), in the order the attempts began."""
    latest = {}
    for i, ev in enumerate(events):
        lane, kind = ev.get("lane"), ev.get("event")
        if not lane:
            continue
        if kind in LAUNCH_LANE_STARTS:
            latest[lane] = [i, ev, None]
        elif kind in LAUNCH_LANE_SPAWNS and latest.get(lane) is not None:
            latest[lane][2] = ev
        elif kind == "lane-closed":
            latest[lane] = None
    found = sorted((v for v in latest.values() if v is not None), key=lambda v: v[0])
    return [(v[1].get("lane"), v[1], v[2]) for v in found]


def lane_liveness(spawned):
    """How an open lane's processes stand, read from its spawn line and never acted on: each
    recorded pid alive or gone, an unusable pid named, and no spawn line or no pid at all said as
    unknown. Nothing here restarts or signals a process."""
    if spawned is None:
        return "no process on the record yet (no lane-spawned): liveness unknown"
    parts = []
    for key, label in (("wrapper_pid", "wrapper"), ("pid", "lane")):
        raw = spawned.get(key)
        if raw is None:
            continue
        pid = usable_pid(raw)
        if pid is None:
            parts.append("%s pid %r unusable: unknown" % (label, raw))
        else:
            parts.append("%s pid %d %s" % (label, pid, "alive" if pid_alive(pid) else "gone"))
    return ", ".join(parts) if parts else "no pid on the record: liveness unknown"


def pack_parts(current):
    """(the pack's stamp as an epoch or None, the stamp as written or None, its Next texts, the
    lines a rewrite keeps) from an In flight body. A head-written pack (its first line `- pack
    written: <ts>`) keeps every line but its stamp and its Next lines, which the rewrite
    supersedes; a derived pack keeps only the lines under its own KEPT_HEADER, since every line
    above that header is the record's and is derived again — except a Next it took from a
    head-written pack (HEAD_NEXT_LINE), returned with that pack's stamp, so the derivation that
    replaces it applies the same rule again: the head's Next stands while the pack is newer than
    the last phase-boundary, and a newer boundary's next supersedes it."""
    body = [line for line in str(current or "").split("\n")]
    while body and not body[0].strip():
        body.pop(0)
    if body and body[0].startswith(PACK_DERIVED_PREFIX):
        kept = []
        top = body
        if KEPT_HEADER in body:
            kept = body[body.index(KEPT_HEADER) + 1:]
            top = body[:body.index(KEPT_HEADER)]
        stamp, stamp_text, nexts = None, None, []
        for line in top:
            m = HEAD_NEXT_RE.match(line)
            if m and (stamp_text is None or m.group(2) == stamp_text):
                stamp_text = m.group(2)
                nexts.append(m.group(1))
        if stamp_text is not None:
            stamp = parse_ts(stamp_text)
            if stamp is None:
                stamp_text, nexts = None, []
        return stamp, stamp_text, nexts, [line for line in kept if line.strip()]
    stamp, stamp_text, nexts, kept = None, None, [], []
    for line in body:
        m = PACK_STAMP_RE.match(line)
        if m:
            if stamp_text is None:
                stamp_text, stamp = m.group(1), parse_ts(m.group(1))
            continue
        n = NEXT_LINE_RE.match(line)
        if n:
            nexts.append(n.group(1).strip())
            continue
        if line.strip():
            kept.append(line)
    return stamp, stamp_text, nexts, kept


def derive_inflight(events, current=None, boundary=None):
    """`## In flight` derived from the run record, under the header the guard writes; the D41
    labels are kept, so a derived pack passes the same label check a head's own pack must pass,
    and an empty class says so rather than going silent.
    - Next: at a boundary (`boundary`, its event), that boundary's own `next`; else the newest
      head-written pack's Next where the pack is newer than the last phase-boundary (register
      entry 2026-09-25 17:4x: a day-old boundary's `next` stood in for the dead head's current
      pack), else the last phase-boundary's `next`. A derived pack that carries a head pack's
      Next hands it on with that pack's own stamp (pack_parts), so re-deriving again keeps it
      until a newer boundary.
    - Needs: every lane open on the WHOLE record (open_lane_attempts) with its spawn line and its
      liveness as the record names it.
    - Decided: the decision events since the anchor (the previous boundary at a boundary).
    - Acknowledged: each `ack:` observation since that anchor, so a message's receipt is in the
      hand-off a successor reads.
    - Owner: every relayed owner instruction on the record since the run's last run-open (an
      observation whose `what` opens with AUTHOR), so a rewrite never drops one (register entry
      2026-09-14 00:06, the R-REF status: a re-derivation dropped a relayed owner line).
    - Kept: the hand-written lines of the pack it replaces (pack_parts), verbatim, under their own
      header — every line but its stamp and its Next."""
    stamp, stamp_text, nexts, kept = pack_parts(current)
    if boundary is not None:
        lines = [PACK_DERIVED_PREFIX + "%s (at the boundary %s → %s)"
                 % (now(), boundary.get("from", "?"), boundary.get("to", "?"))]
        lines.append("- Next: %s (the `next` of this boundary, %s → %s)"
                     % (one_line(boundary.get("next") or "unstated"), boundary.get("from", "?"),
                        boundary.get("to", "?")))
        prev = last_index(events[:-1], ("phase-boundary",))
        if prev < 0:
            prev = last_index(events, ("run-open",))
        since = events[prev + 1:]
    else:
        lines = [PACK_DERIVED % now()]
        j = last_index(events, ("phase-boundary",))
        bts = parse_ts(events[j].get("ts")) if j >= 0 else None
        if nexts and stamp is not None and (j < 0 or (bts is not None and stamp > bts)):
            for text in nexts:
                lines.append(HEAD_NEXT_LINE
                             % (one_line(text), stamp_text,
                                "the last phase-boundary at %s" % events[j].get("ts", "no ts")
                                if j >= 0 else "any phase-boundary (the record carries none)"))
        elif j >= 0 and events[j].get("next"):
            lines.append("- Next: %s (a copy of the `next` field of the phase-boundary at %s: the "
                         "run's shape as it stood at that boundary, which any later instruction "
                         "supersedes)" % (one_line(events[j]["next"]), events[j].get("ts", "no ts")))
        elif j >= 0:
            lines.append("- Next: unstated — the phase-boundary at %s carries no `next` field"
                         % events[j].get("ts", "no ts"))
        else:
            lines.append("- Next: unstated — the record carries no phase-boundary event")
        i = boundary_index(events)
        since = events[i + 1:] if i >= 0 else list(events)
    open_lanes = open_lane_attempts(events)
    for lane, opened, spawned in open_lanes:
        lines.append("- Needs: lane %s open since %s · %s · %s"
                     % (lane, opened.get("ts", "no ts"), spawn_line(opened),
                        lane_liveness(spawned)))
    if not open_lanes:
        lines.append("- Needs: no lane is open on the record (every lane-open and lane-resumed "
                     "has its lane-closed)")
    decisions = [ev for ev in since if ev.get("event") == "decision"]
    for ev in decisions:
        lines.append("- Decided: %s (%s, at %s%s)"
                     % (one_line(ev.get("what") or "unstated"),
                        one_line(ev.get("grant") or "grant unstated"), ev.get("ts", "no ts"),
                        ", %s" % ev["decision_id"] if ev.get("decision_id") else ""))
    if not decisions:
        lines.append("- Decided: no decision event since the %s"
                     % ("previous boundary" if boundary is not None else "boundary"))
    for ev in since:
        if ev.get("event") == "observation" and str(ev.get("what") or "").startswith(ACK_PREFIX):
            lines.append("- Acknowledged: %s (at %s)" % (
                one_line(str(ev["what"])[len(ACK_PREFIX):]), ev.get("ts", "no ts")))
    oi = last_index(events, ("run-open",))
    for ev in events[max(0, oi):]:
        if ev.get("event") == "observation" and AUTHOR_RE.match(str(ev.get("what") or "")):
            text = one_line(ev.get("what") or "")
            if ev.get("note"):
                text += " · " + one_line(ev["note"])
            lines.append(OWNER_LINE % (ev.get("ts", "no ts"), text))
    if kept:
        lines.append(KEPT_HEADER)
        lines.extend(kept)
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
    current = section_text(lines, SECTIONS["inflight"])
    if current is None or not set_section(lines, "inflight",
                                          derive_inflight(events, current=current), derived=True):
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


def apply_set(lines, key, value, derived=False):
    if key in BULLETS:
        if not set_bullet(lines, key, value):
            die("no '## Morning report' section")
    elif key in SECTIONS:
        if not set_section(lines, key, value, derived=derived):
            die("no '## %s' section" % SECTIONS[key])
    elif key in APPEND_ONLY:
        die("the ledger and the trace are append-only: use `ledger` and `boundary`")
    else:
        die("unknown key %r; bullets: %s; sections: %s"
            % (key, ", ".join(sorted(BULLETS)), ", ".join(sorted(SECTIONS))))
    return key


NO_SUCCESSOR_WHAT = "%s refused: no successor left"   # the refusal's observation `what`


def newer_successor(fresh, count):
    """The newest head-successor on `fresh` when the record now holds more of them than `count`
    (successors_left's reading before the lock) saw, else None: another head started while the
    call ran, the case the starter's duplicate guard refuses (review CR-CAP2 finding 9)."""
    if count is None or successors_left(fresh, count["run"])["used"] <= count["used"]:
        return None
    i = last_index(fresh, ("head-successor",))
    return fresh[i] if i >= 0 else None


def no_successor_refusal(cmd, s, kept, raced=None):
    """The REFUSED (exit 10) text `handoff --final` and `successor` print when no successor is
    left (register entry 2026-10-30 16:11). `kept` says what the call wrote; `raced` is a
    head-successor that landed while the call ran (then another head has started, and this head
    is no longer the run's lead). No text tells the head to run `--final` again."""
    count = "%d of %d head starts on its cap (%s)" % (s["used"], s["cap"], s["src"])
    if raced is not None:
        return ("%s: REFUSED (exit %d): a head-successor (session %s, at %s) landed on the record "
                "while this call ran, leaving no successor on the cap (%s): another head has "
                "started, the duplicate the starter's own guard refuses, so this head is no longer "
                "the run's lead. %s; this head starts nothing, and its next gate or run-resume "
                "names the head that holds the run."
                % (cmd, EXIT_NO_SUCCESSOR, raced.get("session_id"), raced.get("ts", "no ts"),
                   count, kept))
    if s["fault"]:
        # A fallback past a faulty grants file is no decided cap (CAP_FAULT_STATES): whether this
        # head is the run's last lead is undecided, so the text names the fault and how to recover
        # the cap, and never the close a last lead makes (build review RV-CAP finding F4).
        return ("%s: REFUSED (exit %d): run %s's own successor cap cannot be read — its grants "
                "file is %s — and the fallback gives %s, at which the starter would refuse a "
                "successor, so whether this head is the run's last lead is undecided. %s, so "
                "this head stays the run's lead. Recover the cap: `handsoff.py grants --run %s "
                "--max-successors N` writes it, N being the cap the run set, which its record "
                "names (the last run-open, run-resume or grants event carrying max_successors), or "
                "one the owner gives; meanwhile work on within your band, and the next gate prints "
                "the count the recovered cap gives."
                % (cmd, EXIT_NO_SUCCESSOR, s["run"], s["fault"], count, kept, s["run"]))
    return ("%s: REFUSED (exit %d): no successor left for run %s — %s, the test the starter "
            "applies. %s, so this head stays the run's lead (register 2026-10-30 16:11). Work on "
            "within your band; when the work cannot finish within it, close the run with its "
            "morning report (handoff --set bullets, then close --items …); from 90 %% the hook "
            "still lets handoff, ledger, TaskStop and close through for the run's last lead. The "
            "owner can raise the cap instead (grants --run %s --max-successors N)."
            % (cmd, EXIT_NO_SUCCESSOR, s["run"], count, kept, s["run"]))


def refuse_no_successor(path, a, cmd, s, kept, raced=None):
    """Record the refusal's one observation (never on --dry-run), print its text and return
    EXIT_NO_SUCCESSOR. Nothing else is written: no head-exit, pack-fresh, seed, console or
    starter."""
    if not a.dry_run:
        note_text = successors_clause(s)
        if raced is not None:
            note_text += "; a head-successor (session %s) landed while the call ran" % (
                raced.get("session_id"),)
        append_record(path, event(a.run, "observation", phase="",
                                  what=NO_SUCCESSOR_WHAT % ("handoff --final" if cmd == "handoff"
                                                            else cmd),
                                  note=note_text))
    say(no_successor_refusal(cmd, s, kept, raced))
    return EXIT_NO_SUCCESSOR


@a3_expose_notices
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
        a.inflight = derive_inflight(events, current=section_text(lines, SECTIONS["inflight"]))
        derived = True
        say("handoff: '## In flight' derived from the record · %d lines"
            % len(a.inflight.split("\n")))
        if a.dry_run:
            for line in a.inflight.split("\n"):
                say(line)
    if a.final and a.inflight is None:
        die("--final needs the next-task pack: --inflight-file PATH (or --inflight TEXT) "
            "carrying Next:, Needs: and Decided: (D41)")
    if a.inflight is not None:
        if not derived:
            refuse_placeholder("handoff", {"inflight": a.inflight})
        missing = pack_missing(a.inflight)
        if missing and a.final:
            die("the next-task pack lacks %s (each label at the start of a line; an optional "
                "'- ' bullet is allowed)" % ", ".join(missing))
        if missing:
            say("handoff: warn: the in-flight pack lacks %s (a --final pack would be refused)"
                % ", ".join(missing))
        changes.append(apply_set(lines, "inflight",
                                 a.inflight if derived else stamp_pack(a.inflight),
                                 derived=derived))
    for spec in a.set or []:
        key, sep, value = spec.partition("=")
        if not sep:
            die("--set needs key=value, got %r" % spec)
        refuse_placeholder("handoff", {"set " + key.strip(): value})
        changes.append(apply_set(lines, key.strip(), value))
    for spec in a.set_file or []:
        key, sep, fpath = spec.partition("=")
        if not sep:
            die("--set-file needs key=path, got %r" % spec)
        value = read_text(fpath, "--set-file " + key)
        refuse_placeholder("handoff", {"set-file " + key.strip(): value})
        changes.append(apply_set(lines, key.strip(), value))
    exit_ev, have_exit, refused, raced, count = None, None, None, None, None
    if a.final:
        xi = stop_exit(events)
        count = successors_left(events, a.run) if xi < 0 else None
        if xi >= 0:
            # This stop's head-exit is already recorded, by the supervisor or an earlier repair,
            # and no head has started since (register entry 2026-09-14 05:13; review finding
            # 2): a second one would count the stop twice.
            have_exit = events[xi]
        elif count["left"] <= 0:
            # The cap at call time, before any head-exit (register entry 2026-10-30 16:11): with
            # no successor left the starter would refuse one, so this head stays the run's lead,
            # its pack still written below, and no head-exit is left behind for repeat-exit or
            # stop_class to read.
            refused = count
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
    if not changes and exit_ev is None and refused is None:
        say("handoff: nothing to do (no --inflight, --set, --set-file or --final)")
        return 0
    if a.dry_run and refused is not None:
        say("handoff: dry run · would rewrite %s · REFUSED (exit %d): %s; nothing written"
            % (", ".join(changes) or "nothing", EXIT_NO_SUCCESSOR, successors_clause(refused)))
        return EXIT_NO_SUCCESSOR
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
            elif successors_left(fresh, a.run)["left"] <= 0:
                # A head-successor or a lowered cap landed while this call measured: the same
                # refusal, decided on the record as it stands under the lock.
                refused, exit_ev = successors_left(fresh, a.run), None
                raced = newer_successor(fresh, count)
            else:
                append_record(path, exit_ev)
    if refused is not None:
        return refuse_no_successor(
            path, a, "handoff", refused,
            "The pack is written to '## In flight' (%s rewritten) and no head-exit was recorded"
            % (", ".join(changes) or "nothing"), raced)
    say("handoff: %s rewritten%s%s" % (
        ", ".join(changes) if changes else "nothing",
        " · head-exit recorded (band %s, %s)" % (exit_ev["band"], exit_ev["context"])
        if exit_ev else "", exit_recorded_text(have_exit)))
    item_warning("handoff", events, lines)
    return 0


def resume_instruction(run, ho):
    """The first message of every head started fresh from the hand-off (the starter `successor`
    detaches and the supervisor's own successor start, both through start_head): fixed text
    naming the run and the hand-off's absolute path, composed here and never read from the
    hand-off. The hand-off's `## Resume prompt` (the `resume-prompt` key of `handoff --set`) is
    the owner's prompt for the next attended session and reaches no head (register entry
    2026-10-08 23:12: a launched head received the owner's morning prompt as its first message).
    The path is the real path run-open records; the hand-off must still be readable, and no
    section of it is required here.

    The message also carries the bootstrap (the delegate skill's section 4), which launch kits
    used to write into the section now set aside, so it would otherwise have no carrier (the
    fix's review, 2026-10-09): EVERY head started here, the run's first included, reads the run
    record's tail and `git status`, then runs `run-resume` through this script's own absolute
    path, before any item work. The first head is not exempt (the fix's second review,
    2026-10-09): the session meter (fable-share.py's read_spawn_record) places a lane in the
    partition the latest run-open or run-resume opened and reads no head-successor, so a first
    head that skips run-resume has every helper it spawns counted under the launcher's seed
    session and none under its own. What the record decides is only where the head starts: with
    no gate an earlier head of the run wrote, it begins, as the run's first head does, at the
    gate In flight names (worded so, rather than calling the head the first, because a successor
    whose predecessor never gated takes that branch too); otherwise it continues from In flight.
    The head reads the record and decides; the text is the same for every start. The command is
    spelled as by_hand_line spells the owner's: the absolute interpreter (interpreter(), never a
    bare `python3`, which a shell may map to another program: register entry 2026-09-30 17:36),
    `-B`, the derived path."""
    path = os.path.realpath(ho)
    read_text(path, "hand-off")   # an unreadable hand-off stops the start, as it always has
    rid = token(run, "run id")
    resume = ("%s -B %s run-resume --run %s --session auto --head '<your model and effort>' "
              "--detail '<the item you start or resume>'"
              % (shlex.quote(interpreter()), shlex.quote(os.path.abspath(__file__)),
                 shlex.quote(rid)))
    return ("You are the next head of hands-off run %s, started by handsoff.py.\n"
            "Hand-off: %s\n"
            "Read that hand-off whole, starting with its `## In flight` section: In flight is the "
            "authority for what you do next. Then read the RUNBOOK and the decisions file the "
            "hand-off names.\n"
            "Before any item work, whether you are the run's first head or a later one: read the "
            "tail of the run record %s and `git status`, then run `%s`. That registers your "
            "session on the record, which the session meter needs to count your helpers as "
            "yours.\n"
            "%s"
            "Then, if that record shows no `gate` event written by an earlier head of this run, "
            "begin, as the run's first head does, at the gate In flight names; otherwise continue "
            "the run from In flight.\n"
            "Any prompt the hand-off holds for the owner's next attended session, its "
            "`## Resume prompt` section included, is addressed to the owner: it is not an "
            "instruction to you.\n" % (rid, path, record_path(rid), resume,
                                        rule_files_note(record_path(rid))))


# What both start messages ask of a head about the rule files: `git log` and `git status` carry the
# change, so nothing is fingerprinted, and a fresh head holds the new text already. What it lacks is
# knowing that its pack and RUNBOOK were written under the old.
RULE_FILES_NOTE = (
    "Then run git log --oneline --since=%s -- CLAUDE.md CUSTOMISATION.md "
    "CUSTOMISATION-definitions.md .claude/skills/delegate/SKILL.md. A line there, or one of those "
    "files in the status, means a rule file changed since the run began: read what changed, as far "
    "as your pack and RUNBOOK rest on it, before your next item.\n")


def rule_files_note(path):
    """RULE_FILES_NOTE with the run-open's time, from the record at `path`; empty on a record with
    no run-open or no time on it."""
    events = read_record(path)[0] if os.path.isfile(path) else []
    at = last_index(events, ("run-open",))
    ts = events[at].get("ts") if at >= 0 else None
    return RULE_FILES_NOTE % shlex.quote(ts) if ts else ""


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


def process_table(timeout=None):
    """(table, why): one read of `ps -A -o pid=,ppid=,stat=,etime=,args=`, bounded by
    PS_TIMEOUT_S, as {pid: (ppid, stat, etime, args)}; (None, what could not be read) on a
    failure, a timeout, a non-zero exit or a read with no parseable row. One function, so a leg
    can plant a table."""
    bound = PS_TIMEOUT_S if timeout is None else max(0.0, timeout)
    try:
        proc = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,stat=,etime=,args="],
                              capture_output=True, text=True, timeout=bound)
    except subprocess.TimeoutExpired:
        return None, "the process table read timed out after %s s" % bound
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "the process table could not be read (%s)" % one_line(str(exc))[:80]
    if proc.returncode != 0:
        return None, "ps exited %d reading the process table" % proc.returncode
    table = {}
    for line in proc.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        table[pid] = (ppid, parts[2], parts[3], parts[4] if len(parts) > 4 else "")
    if not table:
        return None, "the process table read gave no parseable row"
    return table, ""


def shell_name(args):
    """The program name a process table's args column starts with (a login shell's `-` dropped)."""
    first = (args.split(None, 1) or [""])[0]
    return os.path.basename(first).lstrip("-")


def harness_command(command):
    """True when a command names the harness: head_pid's test."""
    return command == HARNESS or command.endswith(os.sep + HARNESS)


def task_command(table, pid):
    """What a shell child runs: its first child's args, else its own, cut at 160 characters."""
    kids = sorted(p for p, row in table.items() if row[0] == pid)
    return one_line(table[kids[0]][3] if kids else table[pid][3])[:160]


BACKGROUND_TASKS_ADVICE = (
    "A task still running keeps this process alive, and the starter then waits up to %d s with "
    "the run unled (register 2026-10-25 16:28), or it dies with the session. Stop each now with "
    "TaskStop and note in the pack which steps the next lead re-runs; work that must outlive you "
    "runs detached, its pid in the pack. The successor starts the moment this process exits. At "
    "the hard band TaskStop is denied to a lead with a successor left: the successor then starts "
    "only when the tasks end, and the run has no acting lead meanwhile.")


def background_tasks(seed, pred, wait_s):
    """(kind, lines) for `successor`'s background-task check (register entry 2026-10-25 16:28):
    each session-leading shell child of the head's own process `pred` other than this call's own
    shell is a task the harness still runs, and a print-mode head whose task still runs does not
    exit. `kind` is `found`, `none`, `undecided` or `not-checked`. `none` needs the same read's
    control: this call's own shell, the member of its process chain whose parent is `pred`, is
    in the table as a session-leading shell. A failed read, a table missing `pred`, a failed
    control or a chain walk that is not whole is `undecided`, never `none`. Not checked, with no
    table read: a seed process, no pid, a pid outside this call's chain, or a pid that is not
    the harness. Read-only: nothing is signalled."""
    def not_checked(what):
        return "not-checked", ["successor: background tasks: not checked — the starter waits on %s"
                               % what]

    def undecided(what):
        return "undecided", ["successor: warn: the background-task check could not run (%s): no "
                             "task is counted — stop each task you started with TaskStop before "
                             "your last reply" % what]
    if seed:
        return not_checked("the seed process")
    if pred is None:
        return not_checked("no pid")
    chain, whole = process_chain_read()
    if not whole:
        # Any walk that is not whole is undecided, a pid found in the part read included: the
        # check stands only on a chain read to its top (build review RV-CAP finding F7).
        return undecided("this call's process chain could not be walked whole, %s"
                         % ("pid %d is in the part read" % pred if pred in chain[1:] else
                            "so whether pid %d is in it is unknown" % pred))
    if pred not in chain[1:]:
        return not_checked("pid %d, outside this call's process chain" % pred)
    row = ps_row(pred)
    if row is None:
        return undecided("pid %d's command could not be read" % pred)
    if not harness_command(row[2]):
        return not_checked("pid %d, which is not the harness (%s)" % (pred, row[2]))
    own = chain[chain.index(pred, 1) - 1]
    table, why = process_table()
    if table is None:
        return undecided(why)
    if pred not in table:
        return undecided("pid %d is not in the process table" % pred)
    mine = table.get(own)
    if (mine is None or mine[0] != pred or shell_name(mine[3]) not in SHELLS
            or "s" not in mine[1]):
        return undecided("the control failed: this call's own process under pid %d (pid %d) is "
                         "not a session-leading shell in the table" % (pred, own))
    tasks = [p for p, r in sorted(table.items())
             if r[0] == pred and p != own and "s" in r[1] and "Z" not in r[1]
             and shell_name(r[3]) in SHELLS]
    if not tasks:
        return "none", ["successor: background tasks: none seen beside this call under head pid "
                        "%d (control: this call's own shell, pid %d, is a session-leading shell "
                        "under it; a task the process table cannot show is not counted)"
                        % (pred, own)]
    lines = ["successor: warn: head pid %d still runs %d background task(s) beside this call:"
             % (pred, len(tasks))]
    lines += ["  pid %d (running %s): %s" % (p, table[p][2], task_command(table, p))
              for p in tasks]
    lines.append(BACKGROUND_TASKS_ADVICE % wait_s)
    return "found", lines


def recorded_predecessor(events, exit_ev):
    """(pid, source, kind) of the process a starter waits on by the record alone — `successor`'s
    own rule with no --seed-pid or --predecessor-pid: the head-exit's pid, else no wait for a seed
    predecessor, else the session event's pid, else transcript silence. `kind` is `pid`, `seed`
    or `silence`; the supervisor's wait after the head's own starter aborted reads it
    (starter_gone), so the two cannot disagree."""
    _, sev = head_session(events)
    if exit_ev is not None and exit_ev.get("pid") is not None:
        return int(exit_ev["pid"]), "head-exit", "pid"
    if seed_predecessor(events):
        return None, "none: the predecessor is a seed session with no pid, so no wait", "seed"
    if sev is not None and sev.get("pid") is not None:
        return int(sev["pid"]), sev["event"], "pid"
    return None, "none: %d s of transcript silence is the proxy" % SILENCE_PROXY_S, "silence"


def starter_gone(events, start, tick_s, wait_s):
    """(bound in seconds, the line naming it) for the supervisor's wait on an `unsucceeded` stop
    once the head's own starter has gone, else (None, ""). The head's last head-exit after its
    start is the one stop_class read; a successor-aborted after it with no head-successor means
    the starter it called has already aborted (register entry 2026-10-25 16:28), so only a
    starter the head called again could still start a successor. One that would wait on a pid,
    or on nothing (a seed), starts within a second of the exit (wait_dead polls once a second):
    STARTER_GONE_TICKS ticks. One that would wait for transcript silence starts within
    SILENCE_PROXY_S and one SILENCE_POLL_S poll of the last write, which precedes the exit, plus
    a tick. Never longer than `wait_s`."""
    after = events[start + 1:]
    hi = last_index(after, ("head-exit",))
    if hi < 0:
        return None, ""
    tail = after[hi + 1:]
    ai = last_index(tail, ("successor-aborted",))
    if ai < 0 or any(e.get("event") == "head-successor" for e in tail):
        return None, ""
    _, _, kind = recorded_predecessor(events, after[hi])
    bound = (STARTER_GONE_TICKS * tick_s if kind in ("pid", "seed")
             else SILENCE_PROXY_S + SILENCE_POLL_S + tick_s)
    bound = min(wait_s, bound)
    ab = tail[ai]
    ts = str(ab.get("ts") or "")
    return bound, ("supervisor: the head's own starter already aborted (%s at %s): waiting %s s "
                   "for a re-called starter, not %s s"
                   % (ab.get("reason") or "no reason", ts[11:19] or "no ts",
                      ("%g" % bound), ("%g" % wait_s)))


def shell_children_text(pid):
    """The starter's timeout note's list of the head's shell children, labelled unverified; an
    unreadable table says so rather than reading as none (review CR-CAP2 finding 9)."""
    table, why = process_table()
    if table is None:
        return "its shell children could not be read (%s)" % why
    kids = [p for p, row in sorted(table.items()) if row[0] == pid and shell_name(row[3]) in SHELLS]
    if not kids:
        return ("its shell children now: none seen (a task the process table cannot show is "
                "not counted)")
    return "its shell children now: %s (not verified as tasks)" % "; ".join(
        "pid %d (running %s) %s" % (p, table[p][2], task_command(table, p)) for p in kids)


def cmd_successor(a):
    if a.seed_pid and a.predecessor_pid is not None:
        # An argument conflict is refused before anything is read (K3a0b95c3's review).
        die("--seed-pid and --predecessor-pid each name the process the starter waits for: pass "
            "one; nothing written")
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
    # The cap at call time, before the model, the meter and any head-exit (register entry
    # 2026-10-30 16:11): the starter's own test, applied while this head is still the lead.
    count = successors_left(events, a.run)
    if count["left"] <= 0:
        return refuse_no_successor(path, a, "successor", count,
                                   "Nothing was written (dry run)" if a.dry_run else
                                   "Nothing was written but this refusal's observation")
    ro = run_open(events)
    ho = handoff_of(events, a.handoff)
    prompt = resume_instruction(a.run, ho)
    # The head's model, before anything is written (K3dbf76d5): --model, else the newest head
    # start's structured model on the record; none at all refuses the call, since a hands-off
    # head never starts on the harness default.
    model, msrc = resolve_head_model(events, a.model)
    if model is None:
        die("successor needs a model for the next head: %s; pass --model (a hands-off head never "
            "starts on the harness default); nothing written" % msrc)
    effort, esrc = resolve_head_effort(events, a.effort)
    xi = last_index(events, ("head-exit",))
    envelope, _ = envelope_of(events)
    if a.budget_usd is not None:
        budget, bsrc = float(a.budget_usd), "--budget-usd"
    elif xi >= 0 and seed_exit(events[xi]) and isinstance(envelope, (int, float)) \
            and not isinstance(envelope, bool):
        # A seed head-exit records a session that never ran: it left no transcript, so the
        # meter has nothing to read of it and the remainder is the envelope minus the run's
        # spend on what did run — never a premise failure (register entry 2026-09-07). The run
        # figure is the gate's and the close's (register entry 2026-09-26 02:2x).
        # A dry run leaves the meter cache unwritten (critic finding 9 of the review of
        # 2026-10-11), as the gate's and the close's dry runs do.
        spend = run_spend(events, a.run, path, session_line=a.meter_line,
                          write_cache=not a.dry_run)
        spent = spend["usd"] if spend["measured"] else 0.0
        budget = round(float(envelope) - spent, 2)
        bsrc = ("envelope (seed): the last head-exit is a seed exit, so envelope $%s minus the "
                "run's spend %s$%.2f, the session that never ran unmetered (run_spend: %s)"
                % (envelope, "at least " if spend["floor"] else "", spent, spend["src"]))
    else:
        budget, bsrc = envelope_left(events, a.run, a.meter_line,
                                     last_index(events, SESSION_EVENTS), path,
                                     write_cache=not a.dry_run)
        if budget is None:
            die("%s; pass --budget-usd" % bsrc)
    # One refusal for every budget computed here rather than given (critic finding 6 of the review
    # of 2026-10-11: the seed branch computed a remainder at or below zero and went on to launch):
    # a spent envelope stops the call before any head-exit, detach or start.
    if a.budget_usd is None and budget <= 0:
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
    if a.seed_pid:
        # An attended head's own process does not exit at the end of a reply, so the starter
        # would wait its whole bound on it (register entry 2026-09-23 00:5x): it is handed a seed
        # process instead, started below once every check has passed, which exits SEED_PID_S
        # after this call.
        pred, psrc = None, ("--seed-pid: a seed process that exits %d s after this call, standing "
                            "in for an attended head whose own process does not exit at the end "
                            "of a reply" % SEED_PID_S)
    elif a.predecessor_pid is not None:
        pred, psrc = int(a.predecessor_pid), "--predecessor-pid"
    else:
        # The record's own rule, shared with the supervisor's wait after an abort (starter_gone).
        pred, psrc, _ = recorded_predecessor(events, exit_ev)
    # A launcher-supplied pid that is this caller's own long-lived ancestor would hold the starter
    # on the caller itself (register entries 2026-09-10 10:51 and 2026-09-12 20:0x). A pid the
    # walk found is the exiting head's own, which the starter must outlive, so it is not tested.
    seed = seed_run_open(events)
    refuse_own_ancestor([(a.pid, "--pid"), (a.predecessor_pid, "--predecessor-pid"),
                         (pred if seed is not None and pred is not None
                          and pred == seed.get("pid") else None, "the seed run-open's pid")])
    # The background tasks the head's own process still runs beside this call (register entry
    # 2026-10-25 16:28): named, never refused; a dry run prints them, a real call after its
    # starter line, so the instruction is the last thing the head reads before its next act.
    _, task_lines = background_tasks(a.seed_pid, pred, a.wait_s)
    if not have_exit:
        exit_ev["pack"] = False
    if a.reset_at:
        parse_reset_at(a.reset_at, time.time())   # refuse a malformed value now, not at 3 am
    out, _ = next_out(a.run)
    transcript = transcript_for(sid) if sid else ""
    plan = ("starter: wait ≤%d s for pid %s (%s); abort if a head-successor already follows "
            "the head-exit, if the previous head-exit was unmetered too, or on timeout; then "
            "from %s start the successor with the fixed resume instruction (%d chars) on stdin, "
            "env "
            "AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=%s%s, budget $%.2f (budget_src: %s), model %s "
            "(model_src: %s), effort %s (effort_src: %s), output %s, and supervise it (D30)" % (
                a.wait_s, "the seed's" if a.seed_pid else ("none" if pred is None else pred),
                psrc, vault_root(), len(prompt),
                a.run, " CLAUDE_CONFIG_DIR=%s" % a.config_dir if a.config_dir else "", budget,
                bsrc, model, msrc, effort, esrc, out))
    cmd = head_command(a.harness_bin, "<fresh uuid4>", budget, model, effort)
    if a.dry_run:
        say("successor: dry run · %s" % plan)
        say("command: %s < resume instruction" % " ".join(cmd))
        if a.pack_fresh:
            say("successor: dry run · would record observation pack-fresh (the launcher's word "
                "that the hand-off is current)")
        open_console_if_dark(a.run, dry_run=True)
        for line in task_lines:
            say(line)
        return 0
    if not have_exit:
        refused = raced = None
        with record_lock(path):   # the supervisor or a repair may have written it meanwhile
            fresh, _ = read_record(path)
            ri = last_index(fresh, START_EVENTS + ("head-exit",))
            if ri >= 0 and fresh[ri].get("event") == "head-exit":
                have_exit = True
            elif successors_left(fresh, a.run)["left"] <= 0:
                # The call-time cap again, on the record as it stands under the lock.
                refused = successors_left(fresh, a.run)
                raced = newer_successor(fresh, count)
            else:
                append_record(path, exit_ev)
        if refused is not None:
            return refuse_no_successor(path, a, "successor", refused,
                                       "Nothing was written but this refusal's observation",
                                       raced)
    if a.pack_fresh:
        record_pack_fresh(path, a.run, "successor")
    if a.seed_pid:
        # The seed, started only now that every check has passed: its own session, its streams on
        # /dev/null, never waited on here; the starter waits for it as for any predecessor.
        seedproc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(%d)"
                                     % SEED_PID_S], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    start_new_session=True, close_fds=True)
        pred = seedproc.pid
        plan = plan.replace("pid the seed's", "pid %d" % pred, 1)
    starter = [sys.executable, "-B", os.path.abspath(__file__), "_starter", "--run", a.run,
               "--handoff", ho, "--budget", "%.2f" % budget, "--out", out, "--wait-s",
               str(a.wait_s), "--harness-bin", a.harness_bin, "--transcript", transcript,
               "--max-wait-s", str(a.max_wait_s), "--probe-interval-s",
               str(a.probe_interval_s), "--tick-s", str(a.tick_s)]
    starter += ["--model", model, "--model-src", msrc]   # resolved above: never the default
    if effort:
        starter += ["--effort", effort, "--effort-src", esrc]
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
    for line in task_lines:
        say(line)
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
        time.sleep(SILENCE_POLL_S)
    return False


def start_guards(events, hi, gone=True, why="", run=None):
    """The starter's loop guards over the record's last head-exit (index hi): (reason, detail)
    for a successor-aborted event, or (None, None) when the start may go ahead. The successor
    cap is the run's own (successor_cap: the grants file, then AIMYTH_MAX_SUCCESSORS, then the
    default), so a direct call of this script and a call through a wrapper read one number; the
    count is successors_left's, the one `handoff --final`, `successor`, `gate` and the hard-band
    hook read, so the call-time refusal and this backstop cannot disagree."""
    if hi < 0:
        return "no-head-exit", "the record carries no head-exit to succeed"
    if any(e.get("event") == "head-successor" for e in events[hi + 1:]):
        return "duplicate", "a head-successor already follows the head-exit"
    if not gone:
        return "timeout", why
    earlier = [e for e in events[:hi] if e.get("event") == "head-exit"]
    run = run or str(events[hi].get("run") or "")
    count = successors_left(events, run)

    def item_before(idx):
        """The sole unfinished item proved by this head's window, else None. The latest
        START_EVENTS event opens the window. Allowed items less completed boundaries must
        leave exactly one item; a refusal on any item never allowed in the window means a
        hand-over for room, regardless of gate order. A completed boundary reached before
        any allowed gate on the backward read still names no item. Missing or malformed
        gates cannot prove an attempt, and an earlier head's open items do not count.
        Accepted residual: repeatedly allowing multiple unfinished items, or re-allowing
        work and refusing an item never allowed in the window, can evade both repeat-exit
        rules. The allowed gates prevent no_progress from catching those chains; only the
        successor cap and the run's envelope bound them."""
        start = last_index(events[:idx], START_EVENTS)
        if start < 0:
            return None
        allowed, refused, completed = set(), set(), set()
        for e in reversed(events[start + 1:idx]):
            kind = e.get("event")
            if kind == "gate":
                item, decision = e.get("item"), e.get("decision")
                if not isinstance(item, str) or not item or decision not in ("allow", "refuse"):
                    return None
                (allowed if decision == "allow" else refused).add(item)
            elif kind == "phase-boundary":
                if not allowed:
                    return None
                item = e.get("from")
                if not isinstance(item, str) or not item:
                    return None
                completed.add(item)
        unfinished = allowed - completed
        if refused - allowed or len(unfinished) != 1:
            return None
        return next(iter(unfinished))
    if events[hi].get("band") == "unmetered" and earlier and \
            earlier[-1].get("band") == "unmetered":
        return "unmetered-loop", ("the previous head-exit was unmetered too: an unmetered "
                                  "fault buys at most one restart")
    if count["left"] <= 0:
        return "successor-cap", ("%d successors already started for this run, at its cap of %d "
                                 "(%s); `handsoff.py grants --run %s --max-successors N` raises it"
                                 % (count["used"], count["cap"], count["src"], run or "<run>"))
    if earlier and item_before(hi) is not None and \
            item_before(hi) == item_before(events.index(earlier[-1])) and \
            str(events[hi].get("band")) in ("80", "90") and \
            str(earlier[-1].get("band")) in ("80", "90"):
        return "repeat-exit", ("the last two head-exits followed a gate on the same item "
                               "(%s): the item does not fit the window; the hand-off is the "
                               "recovery" % item_before(hi))
    stalled = no_progress(events, hi)
    if stalled is not None:
        return "repeat-exit", ("the last two head-exits, by two heads in turn at band 80 or 90, "
                               "each followed a refused gate on the same item (%s) with no "
                               "allowed gate and no completed boundary between the two "
                               "refusals: no progress, and a third head would only pay another "
                               "start to be refused again; the hand-off is the recovery"
                               % stalled)
    return None, None


def refused_exit(events, idx):
    """(index, item) of the refused gate the head-exit at `idx` followed, else None. Read
    backwards from the exit, the first gate or completed boundary decides: a refused gate naming
    a non-empty string item answers; an allowed gate or a `phase-boundary` means the head did
    not hand over at a refusal. A head start or an earlier head-exit ends the read with none, so the refusal is
    always this head's own and never one an earlier exit already answered for."""
    for j in range(idx - 1, -1, -1):
        e = events[j]
        kind = e.get("event")
        if kind == "gate":
            item = e.get("item")
            if e.get("decision") == "refuse" and isinstance(item, str) and item:
                return j, item
            return None
        if kind == "phase-boundary" or kind == "head-exit" or kind in START_EVENTS:
            return None
    return None


def no_progress(events, hi):
    """The pending item when the record's last two head-exits show no progress, else None
    (start_guards' second repeat-exit rule, beside the attempt comparison; the fix's second
    review, 2026-10-09). A refusal on an item never allowed in the head's window names no attempt,
    so two heads in turn that are each refused at the same item would otherwise be bounded by the
    successor cap alone. The rule holds when every part is read off the record: the two exits
    (the last head-exit and the one before it) are by two different heads, the session each
    exit's latest run-open, run-resume or head-successor names, both readable and unequal (a
    head resumed in place keeps its session and is the same head); both sit at band 80 or 90;
    each followed a refused gate on the same item (refused_exit); and between those two refusals
    the record holds no allowed gate and no completed boundary. A part the record does not show
    leaves the start alone: the guard never fires on a premise it cannot read."""
    exits = [i for i in range(hi) if events[i].get("event") == "head-exit"]
    if hi < 0 or not exits:
        return None
    pi = exits[-1]
    if str(events[hi].get("band")) not in ("80", "90") or \
            str(events[pi].get("band")) not in ("80", "90"):
        return None
    first, second = refused_exit(events, pi), refused_exit(events, hi)
    if first is None or second is None or first[1] != second[1]:
        return None
    sid_first, sid_second = head_session(events[:pi])[0], head_session(events[:hi])[0]
    if sid_first is None or sid_second is None or sid_first == sid_second:
        return None
    short_sid, full_sid = sorted((sid_first, sid_second), key=len)
    if len(short_sid) >= 8 and full_sid.startswith(short_sid):
        return None
    for e in events[first[0] + 1:second[0]]:
        kind = e.get("event")
        if kind == "phase-boundary" or (kind == "gate" and e.get("decision") != "refuse"):
            return None
    return second[1]


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


def head_model_fields(a, model=None, model_src=None, effort=None, effort_src=None):
    """The model and effort a head start runs under, as its command line carries them
    (head_command), for the head-successor and head-resumed events (register entry 2026-09-10
    20:29: watch.py's header reads them from the record alone), with each one's provenance:
    `arg`, or the record event it was inherited from (resolve_head_model, resolve_head_effort)."""
    model = model or getattr(a, "model", None) or None
    src = model_src or getattr(a, "model_src", None) or ("arg" if model else
                                                         "harness default (no --model)")
    effort = effort or getattr(a, "effort", None) or None
    esrc = effort_src or getattr(a, "effort_src", None) or ("arg" if effort else "none")
    return {"model": model, "effort": effort, "model_src": src, "effort_src": esrc}


def resolve_head_model(events, explicit=None):
    """(model, source) for a head this script is about to start: an explicit --model wins; else
    the `model` field of the record's NEWEST head-start event that carries one — a head-resumed,
    a head-successor, or a run-open or run-resume given --model — so a later resumed model wins
    over an earlier start's; else (None, why). The free-text `head` description a run-open or
    run-resume carries is never parsed for a model name (critic finding 5 of the batch's design
    review). Register entry 2026-09-23 12:5x, and this run's own recurrence of 2026-10-10 13:36:
    a successor started with no --model ran its head on the harness default."""
    if explicit:
        return explicit, "arg"
    for ev in reversed(events):
        if ev.get("event") not in START_EVENTS:
            continue
        model = ev.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip(), "record: the %s at %s" % (ev.get("event"), ev.get("ts", "no ts"))
    return None, ("the record names no head model: no head-start event carries a `model` field "
                  "(the free-text head description is never read as one)")


def resolve_head_effort(events, explicit=None):
    """(effort, source) for a head this script is about to start (register entry 2026-10-04 22:58,
    the owner's A4 of 4 October): an explicit --effort wins; else the `effort` of the record's
    newest head-start event that carries one, so the effort a head was launched at survives a
    resume and a succession; else HEAD_EFFORT_DEFAULT, which holds only where nothing was named."""
    if explicit:
        return explicit, "arg"
    for ev in reversed(events):
        if ev.get("event") not in START_EVENTS:
            continue
        effort = ev.get("effort")
        if isinstance(effort, str) and effort.strip():
            return effort.strip(), "record: the %s at %s" % (ev.get("event"), ev.get("ts", "no ts"))
    return HEAD_EFFORT_DEFAULT, "default: no head start on the record names one"


def launch_effort(a, path):
    """(effort, source) for one actual head start (start_head, resume_head): the caller's effort
    when it has one, else resolved from the record as it stands now (resolve_head_effort), so a
    supervisor attached with no --effort inherits the newest at every start."""
    if getattr(a, "effort", None):
        return a.effort, getattr(a, "effort_src", None) or "arg"
    return resolve_head_effort(read_record(path)[0])


def launch_model(a, path):
    """(model, source) for one actual head start (start_head, resume_head): the caller's model
    when it has one (its own --model, or one resolved and passed on by `successor` or
    `resume-head`), else resolved from the record as it stands now (resolve_head_model), so a
    supervisor attached with no model inherits the newest at every start; (None, why) when there
    is none, and the start is refused before any harness process exists."""
    if getattr(a, "model", None):
        return a.model, getattr(a, "model_src", None) or "arg"
    return resolve_head_model(read_record(path)[0])


def start_head(a, path, budget, out, t0, watch=None):
    """A fresh head on the fixed resume instruction naming the run and its hand-off (the start
    path the starter has always used; never the hand-off's `## Resume prompt`, which is the
    owner's), then the head-successor and supervise events: (proc, sid, out, offset, start
    index) or None after successor-aborted, reason start-failed or model-unknown. A start with
    no model to run (launch_model) is refused before any harness process exists: a hands-off head
    never runs on the harness default (register entry 2026-09-23 12:5x; this run's recurrence of
    2026-10-10 13:36 was the supervisor's own successor)."""
    model, msrc = launch_model(a, path)
    if model is None:
        abort(path, a.run, "model-unknown", "no model for the next head: %s; no harness process "
              "was started — start the successor by hand with --model" % msrc)
        return None
    ho = handoff_of(read_record(path)[0], a.handoff)
    guard_pack(a, path, ho)          # a pack older than the last boundary is re-derived first
    prompt = resume_instruction(a.run, ho)
    sid = str(uuid.uuid4())
    effort, esrc = launch_effort(a, path)
    cmd = head_command(a.harness_bin, sid, budget, model, effort)
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
                              **head_model_fields(a, model, msrc, effort, esrc)))
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
    result), kept whole for terminal classification. Structured assistant/user/system records
    are not stderr. A missing, empty or JSON-less file gives an empty result and a note naming
    the premise, never a guess."""
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
    result, where, structured = {}, -1, set()
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped.startswith("{"):
            continue
        try:
            rec = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(rec, dict):
            if rec.get("type") in ("assistant", "user", "system"):
                structured.add(i)
            if not result and rec.get("type") in (None, "result") and "result" in rec and (
                    "subtype" in rec or "is_error" in rec):
                result, where = rec, i
    tail = "\n".join(line for i, line in enumerate(lines) if i != where and i not in structured)
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
    start_event = events[start] if 0 <= start < len(events) else {}
    boundary = start_event.get("transcript_boundary", {"unknown": True}) if start_event.get("event") == "head-resumed" else None
    parsed = lane.parse_transcript(transcript, boundary)
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
        if cls in ("network", "limit"):
            text = signal
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


# No model request or credentials: HEAD on the provider origin only.
NETWORK_PROBE_TIMEOUT_S = 10   # set by judgement, unmeasured: bounds a connection attempt
NETWORK_POLL_S = 30            # set by judgement, unmeasured: two checks per minute during an outage
NETWORK_TICK_MIN_S = 0.01       # set by judgement, unmeasured: avoids a busy loop with a zero tick
NETWORK_BACKOFF_FIRST_S = 60   # set by judgement, unmeasured: first repeated stop without progress
NETWORK_BACKOFF_MAX_S = 1800   # set by judgement, unmeasured: about two resumes per hour at the cap
NETWORK_NO_WORK_LIMIT = 2      # Owner-approved rule: stop after two consecutive no-work resumes.


def network_resume_evidence(events, start, pid, record_uncertain=False):
    """Separate positive work, readable absence and unknown; observe model answers separately.

    Model-answer evidence is diagnostic only: the no-work count needs readable absence of
    work while the provider answers. Unknown progress neither increments nor clears it.
    The older boolean progress reader remains the backoff rule, never a no-work verdict.
    """
    own = usable_pid(pid) is not None and any(
        e.get("caller_pid") == pid and e.get("event") not in (None, "heartbeat")
        for e in events[start + 1:])
    evidence = {"progress": "yes" if own else "unknown", "model_answer": "unknown",
                "note": "head-authored event" if own else "progress evidence unavailable"}
    resumed = events[start] if 0 <= start < len(events) else {}
    boundary = resumed.get("transcript_boundary")
    classifier, _, _ = lane_module()
    if classifier is None or not isinstance(boundary, dict):
        return evidence
    try:
        raw, uncertainty = classifier.a3_suffix(boundary)
        if uncertainty:
            evidence["note"] += "; " + uncertainty
            return evidence
        with open(boundary["path"], "rb") as handle:
            prefix = handle.read(boundary["size"])
        if classifier.a3_digest(prefix) != boundary["prefix_sha256"]:
            return evidence
        seen = set()
        for line in prefix.splitlines():
            row = json.loads(line)
            if not isinstance(row, dict):
                return evidence
            if isinstance(row.get("uuid"), str):
                seen.add(row["uuid"])
        uncertain, reached, worked = record_uncertain, False, own
        for line in raw.splitlines():
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError, RecursionError):
                uncertain = True
                continue
            if not isinstance(row, dict):
                uncertain = True
                continue
            if row.get("type") != "assistant":
                continue
            message = row.get("message")
            if not isinstance(message, dict):
                uncertain = True
                continue
            model = message.get("model")
            if isinstance(model, str) and model.startswith("<synthetic"):
                continue
            identity = row.get("uuid")
            if not isinstance(model, str) or not model or not isinstance(identity, str) or not identity:
                uncertain = True
                continue
            if identity in seen:
                continue
            reached = True
            content = message.get("content")
            if not isinstance(content, list):
                uncertain = True
                continue
            if any(isinstance(block, dict) and (block.get("type") == "tool_use" or
                    block.get("type") == "text" and isinstance(block.get("text"), str)
                    and block["text"].strip()) for block in content):
                worked = True
        return {"progress": "yes" if worked else "unknown" if uncertain else "no",
                "model_answer": "yes" if reached else "unknown" if uncertain else "not-observed",
                "note": "new head work" if worked else "unreadable progress evidence" if uncertain
                        else "readable evidence contains no new head work"}
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return evidence


def network_progress(events, start, pid, out, offset):
    """New head-authored events or new real-model transcript content; never stdout."""
    if usable_pid(pid) is not None and any(
            e.get("caller_pid") == pid and e.get("event") not in (None, "heartbeat")
            for e in events[start + 1:]):
        return True
    resumed = events[start] if 0 <= start < len(events) else {}
    boundary = resumed.get("transcript_boundary")
    classifier, _, _ = lane_module()
    if classifier is None or not isinstance(boundary, dict):
        return False
    raw, uncertainty = classifier.a3_suffix(boundary)
    if uncertainty:
        return False
    try:
        with open(boundary["path"], "rb") as handle:
            prefix = handle.read(boundary["size"])
        if classifier.a3_digest(prefix) != boundary["prefix_sha256"]:
            return False
        seen = set()
        for line in prefix.splitlines():
            row = json.loads(line)
            if isinstance(row, dict) and isinstance(row.get("uuid"), str):
                seen.add(row["uuid"])
        for line in raw.splitlines():
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(row, dict) or row.get("type") != "assistant":
                continue
            identity = row.get("uuid")
            if not isinstance(identity, str) or not identity or identity in seen:
                continue
            message = row.get("message")
            if not isinstance(message, dict):
                continue
            model = message.get("model")
            if not isinstance(model, str) or not model or model.startswith("<synthetic"):
                continue
            content = message.get("content")
            if isinstance(content, list) and any(isinstance(block, dict) and (
                    block.get("type") == "tool_use" or block.get("type") == "text"
                    and isinstance(block.get("text"), str) and block["text"].strip())
                    for block in content):
                return True
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return False


def network_delay(events, start, sid, pid, out, offset):
    resumed = events[start] if 0 <= start < len(events) else {}
    if (resumed.get("event") != "head-resumed" or resumed.get("session_id") != sid
            or resumed.get("exit_class") != "network"
            or network_progress(events, start, pid, out, offset)):
        return 0
    previous = resumed.get("network_delay_s") or 0
    return min(NETWORK_BACKOFF_MAX_S, max(NETWORK_BACKOFF_FIRST_S, previous * 2))


def connectivity_check():
    """True/False for reachability; None when a credential-free HTTPS probe is impossible."""
    try:
        origin = urllib.parse.urlsplit(os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com")
        if origin.scheme != "https" or not origin.hostname or origin.username or origin.password:
            return None
        port = origin.port
    except ValueError:
        return None
    conn = http.client.HTTPSConnection(origin.hostname, port, timeout=NETWORK_PROBE_TIMEOUT_S)
    try:
        conn.request("HEAD", "/")
        response = conn.getresponse()
        # Authentication and not-found answers prove reachability; server errors do not.
        return 200 <= response.status < 500
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def wait_for_network(a, path, start, stopped_at, watch, delay=0):
    append_record(path, event(a.run, "stop-condition", which="network", lane="head",
                              action="wait for a no-usage HTTPS answer, then resume"))
    say("supervisor: network — waiting for the API; no model usage")
    next_probe, ready_at = 0.0, None
    while True:
        if watch.check():
            return "stood-down", "network", time.time() - stopped_at
        events, _ = read_record(path)
        if any(e.get("event") == "run-close" for e in events[start + 1:]):
            return "closed", "network", time.time() - stopped_at
        if any(e.get("event") in ("head-resumed", "head-successor") for e in events[start + 1:]):
            watch.reason, watch.detail = "resumed-by-hand", "another head continuation was recorded"
            return "stood-down", "network", time.time() - stopped_at
        current = time.monotonic()
        if ready_at is None and current >= next_probe:
            answer = connectivity_check()
            if answer is None:
                abort(path, a.run, "network-probe-impossible",
                      "provider origin cannot support a credential-free HTTPS probe; no resume")
                return "probe-impossible", "invalid provider origin", time.time() - stopped_at
            if answer:
                ready_at = time.monotonic() + delay
                append_record(path, event(a.run, "network-backoff", delay_s=delay,
                                          reason="repeated network stop without head progress" if delay else "initial stop or head progress"))
                say("supervisor: API answers; network delay %s s" % delay)
                continue  # recheck stop and close after the connectivity check, even at zero delay
            next_probe = current + NETWORK_POLL_S
        if ready_at is not None and current >= ready_at:
            return "ok", "no-usage HTTPS answer", time.time() - stopped_at
        due = ready_at if ready_at is not None else next_probe
        time.sleep(min(max(a.tick_s, NETWORK_TICK_MIN_S), max(NETWORK_TICK_MIN_S, due - time.monotonic())))


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
    "anything else in that item, subject to D29 and lane.py advise. For a network close, check "
    "the saved work, then use lane.py advise: resume is the default; "
    "a fresh start is the head's judgement. Stop after two consecutive resumes with no new "
    "work while the provider answers; unreadable progress neither advances nor resets that count.\n")


def resume_head(a, path, sid, budget, bsrc, out, m, cls, waited, source, stopped_at,
                network_delay_s=0, network_no_work_n=0, successor_fallback=False):
    """`claude -p --resume <sid>` from the vault with the resume note on standard input, its
    output appended to the same .out (D30, D31): (proc, out, offset, start index) or None after
    a refusal. A supervisor that can try the successor path records a non-terminal refusal;
    a standalone resume still aborts and ends its holds."""
    def refused(reason, detail):
        if successor_fallback:
            append_record(path, event(a.run, "head-resume-refused", reason=reason, note=detail))
            say("supervisor: resume refused — %s: %s; considering the successor path"
                % (reason, detail))
        else:
            abort(path, a.run, reason, detail)

    if cls == "network":
        opening = ("RESUMED after a network failure; the API answers again (%s).\n"
                   "Read and check the unfinished work on disk before continuing.\n" % source)
    elif cls == "limit":
        opening = ("RESUMED after the account window reset. The limit stopped this head at %s; "
                   "the window reset at %s (%s).\n"
                   % (fmt_ts(stopped_at), fmt_ts(stopped_at + waited), source))
    else:
        opening = ("RESUMED after a budget stop. The harness's cap stopped this head at %s; the "
                   "new cap is $%.2f (%s).\n" % (fmt_ts(stopped_at), budget, bsrc))
    classifier, _, _ = lane_module()
    if cls in ("limit", "network"):
        problem = (classifier.resume_transcript_error(transcript_for(sid)) if classifier
                   else "transcript reader unavailable")
        if problem:
            refused("resume-transcript", "cannot resume the head: " + problem)
            return None
    model, msrc = launch_model(a, path)
    if model is None:
        abort(path, a.run, "model-unknown", "no model to resume the head on: %s; no harness "
              "process was started — resume by hand with --model" % msrc)
        return None
    if out in (None, "none"):
        out, _ = next_out(a.run)
    effort, esrc = launch_effort(a, path)
    cmd = head_command(a.harness_bin, sid, budget, model, effort, resume=True)
    message = opening + RESUME_NOTE + rule_files_note(path)   # before the start: a read may refuse
    offset = out_size(out)
    classifier, _, _ = lane_module()
    try:
        boundary = classifier.a3_boundary(transcript_for(sid)) if classifier else {"known": False}
    except OSError:
        boundary = {"unknown": True}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "ab") as handle:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=handle, stderr=handle,
                                    cwd=vault_root(), env=head_env(a.run, a.config_dir),
                                    start_new_session=True)
        except OSError as exc:
            refused("resume-failed", "cannot start %s --resume %s: %s" % (a.harness_bin, sid, exc))
            return None
    feed(proc, message)
    events, _ = read_record(path)
    n = 1 + sum(1 for e in events
                if e.get("event") == "head-resumed" and e.get("session_id") == sid)
    append_record(path, event(a.run, "head-resumed", session_id=sid, pid=proc.pid,
                              context=m.get("context"), waited_s=round(waited),
                              reset_source=source, resume_n=n, out=out, budget=budget,
                              exit_class=cls, network_delay_s=network_delay_s,
                              **({"network_no_work_n": network_no_work_n} if cls == "network" else {}),
                              transcript_boundary=boundary,
                              **head_model_fields(a, model, msrc, effort, esrc)))
    events, _ = read_record(path)
    start = last_index(events, ("head-resumed",))
    append_record(path, event(a.run, "supervise", mode="launched", pid=proc.pid, session_id=sid,
                              out=out, supervisor_pid=os.getpid(), services_holds=True))
    say("supervisor: head-resumed pid %d session %s (resume %d) at %s tokens (%s) after %d s "
        "→ %s" % (proc.pid, sid, n, format(m["context"], ",") if m.get("context") is not None else "unknown", m.get("source"), waited, out))
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
    """The shared, stable record sidecar; nested appends reuse this transaction."""
    with a3_shared().a3_record_lock(path):
        yield


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
        """A head-exit, a later head process (head-successor, head-resumed), or a run-open or
        run-resume naming ANOTHER session after this head's start. The head's own run-resume —
        the first act of every head this script starts — is not a later head: counting it left
        an unparsed limit stop with no head-exit (register entry 2026-09-23 12:4x; the replay of
        that run's record lines 1 to 179)."""
        for e in events[start + 1:]:
            kind = e.get("event")
            if kind in ("head-exit", "head-successor", "head-resumed"):
                return True
            if kind in ("run-open", "run-resume") and start_session(e) != sid:
                return True
        return False
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
    reason, detail = start_guards(events, last_index(events, ("head-exit",)), run=a.run)
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
    return (previous_stop_event(events)[1] or {}).get("exit_class")


def previous_stop_event(events):
    """(index, event) of the stop previous_stop reads — the last supervisor `head exited`
    observation, a seed exit skipped by the same test — else (-1, None). The repeat-stop guard
    reads the stop's recorded `progress` from it."""
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("event") == "observation" and ev.get("what") == "head exited":
            if any(seed_exit(x) for x in events[max(0, i - 1):i + 2]):
                continue
            return i, ev
    return -1, None


# The repeat-stop guard's pairing classes (the repeat-stop design of 2026-10-11, Revision 2): a stop
# pairs when the supervisor would follow it with an automatic start. Never paired: a limit (its
# wait and resume), closed, handed-over (its own successor call), classifier-missing (it aborts),
# and a `waiting` exit, which the held-waits design keeps outside this guard; a stop the stop
# marker stood down is excluded by stood_down_after. An unsucceeded head with its own packed
# head-exit after its latest start has handed over; only its successor call is missing, which
# the supervisor's existing wait covers, so it does not pair.
REPEAT_STOP_PAIRED = ("error", "budget", "completed", "unsucceeded")
REPEAT_STOP_UNPAIRED = ("limit", "closed", "handed-over", "classifier-missing", "waiting")


def stop_pairs(cls, events=None, stop_i=None, pid=None):
    """Whether a stop of class `cls` can be one of a repeat-stop pair: a named pairing class, or
    any other named class that falls through to the successor path; never an unpaired class and
    never a stop with no class. With the record, an unsucceeded head's own head-exit with
    pack exactly True after its latest start does not pair. An absent pack field is not a
    packed hand-over; a present non-boolean value cannot prove pairing and leaves it unpaired.
    stop_i bounds a recorded stop;
    absent, the current stop is at the end of events. A missing start or conflicting stop
    identity cannot prove a pairing premise. Head-exits may omit pid (the hand-off command's
    schema); the start window then attributes them. A different explicit pid does not count,
    except the seed's explicit pid on a --pid seed record: final_pid writes it for every head.
    An unreadable exit pid or owner cannot prove pairing either. Without events this answers
    only the class rule, for callers inspecting the class list. Accepted residual: packed
    hand-overs without boundaries no longer pair; repeat-exit bounds such a chain where its
    exits name one item at band 80 or 90, otherwise the successor cap and the envelope alone
    bound it. Re-allowed work with multiple unfinished items or a refusal on an item never
    allowed in the window can evade both repeat-exit rules."""
    if cls == "network":
        return False
    if cls == "unsucceeded" and events is not None:
        end = len(events) if stop_i is None else stop_i
        start = last_index(events[:end], START_EVENTS)
        if start < 0:
            return False
        if stop_i is not None:
            pid = events[stop_i].get("pid")
        owner = event_pid(events[start])
        if pid is not None and (usable_pid(pid) is None or owner != usable_pid(pid)):
            return False
        # final_pid writes a seed's explicit pid on every head's handoff --final on a seeded
        # record, so that pid names no other head: the window attributes the exit.
        seed = seed_run_open(events[:end])
        seed_pid = (usable_pid(seed.get("pid"))
                    if seed is not None and seed.get("pid_src") == "arg" else None)
        for ev in events[start + 1:end]:
            if ev.get("event") != "head-exit":
                continue
            if "pack" in ev and not isinstance(ev["pack"], bool):
                return False
            if ev.get("pack") is not True:
                continue
            if "pid" not in ev:
                return False
            exit_pid = usable_pid(ev.get("pid"))
            if exit_pid is None or owner is None or exit_pid in (owner, seed_pid):
                return False
    if cls in REPEAT_STOP_PAIRED:
        return True
    return isinstance(cls, str) and cls != "" and cls not in REPEAT_STOP_UNPAIRED


def stood_down_after(events, i):
    """True when a `supervisor-stood-down` follows the stop observation at index `i`: its
    supervisor stood down instead of starting anything, so that stop never pairs."""
    return any(e.get("event") == "supervisor-stood-down" for e in events[i + 1:])


def head_progress(events, pid, start, bad_watch, bad_stop, bad_at=None):
    """(verdict, note) for the head that just stopped: `yes`, `no` or `unknown`, whether its own
    process recorded progress (the repeat-stop design of 2026-10-11, Revision 2).

    A head invocation is one process. Its window opens at the first start event (START_EVENTS)
    naming `pid` after the stop recorded before `start` — this head's start event as the
    supervisor holds it, since a hand-over's own observation is written once its successor has
    started — so a later run-resume by the same process stays inside it and a head-resumed, a new
    process, opens its own. Progress is a `phase-boundary` in the window whose caller_pid is
    `pid`: `yes`. Otherwise the verdict is `unknown` where the premise cannot be read — no usable
    pid, no start event naming it, a boundary in the window with no caller_pid, an unparseable
    record line inside the window, or more unparseable lines at the stop (`bad_stop`) than when
    the watch began (`bad_watch`), a line that may hold a boundary — and `no` where the window
    holds no boundary of its own. `bad_at`, when given, places each unparseable line among
    `events` (read_record's marks, from the same read): a line placed after the window's start
    event lies inside it, from that start to this stop, whenever the watch began — an attach or a
    console opened before the watch included (critic finding 3 of the review of 2026-10-11); a
    line before the start event never disables the guard. A boundary another process wrote never
    counts. A guard never fires on a premise it cannot read, so `unknown` never fires."""
    pid = usable_pid(pid)
    if pid is None:
        return "unknown", "the supervisor holds no usable pid for the head"
    upto = start if 0 <= start < len(events) else len(events)
    floor = next((i for i in range(upto - 1, -1, -1)
                  if events[i].get("event") == "observation"
                  and events[i].get("what") == "head exited"), -1)
    opened = next((i for i in range(floor + 1, len(events))
                   if events[i].get("event") in START_EVENTS and event_pid(events[i]) == pid), -1)
    if opened < 0:
        return "unknown", "no start event names pid %d after the previous stop" % pid
    own = unattributed = foreign = 0
    for ev in events[opened + 1:]:
        if ev.get("event") != "phase-boundary":
            continue
        caller = usable_pid(ev.get("caller_pid"))
        if caller == pid:
            own += 1
        elif caller is None:
            unattributed += 1
        else:
            foreign += 1
    where = "since its %s at %s" % (events[opened].get("event"), events[opened].get("ts", "no ts"))
    if own:
        return "yes", "%d boundary event(s) by pid %d %s" % (own, pid, where)
    if unattributed:
        return "unknown", ("%d boundary event(s) %s carry no caller_pid, so whose they are cannot "
                           "be read" % (unattributed, where))
    inside = [k for k in (bad_at or ()) if k > opened]
    if inside:
        return "unknown", ("%d unparseable record line(s) lie inside this head's window, after its "
                           "%s at %s: a line that cannot be read may hold its boundary"
                           % (len(inside), events[opened].get("event"),
                              events[opened].get("ts", "no ts")))
    if bad_stop > bad_watch:
        return "unknown", ("the record's unparseable lines rose from %d to %d while this head was "
                           "watched: a line that cannot be read may hold its boundary"
                           % (bad_watch, bad_stop))
    return "no", "no boundary event by pid %d %s%s" % (
        pid, where, " (%d by another process)" % foreign if foreign else "")


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
    if not a3_can_beat(path, a.run, lane):
        die("a held or unsettled task disposition is not a cache hold")
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
    invocation = uuid.uuid4().hex
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
        env["A3_BEAT_INVOCATION"] = invocation
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
                              invocation_id=invocation, observation_only=True,
                              harness_may_survive=rc not in (2,) and os.path.isfile(wrapper),
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
        if not a3_can_beat(path, a.run, lane):
            say("supervisor: held or unsettled task disposition; no beat")
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
                a3_observe_helpers(path, a.run)
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
        # The unparseable-line count as this head's watch begins: a rise by its stop is a line
        # inside its window that cannot be read, and one from before it never disables the guard.
        bad_watch = read_record(path)[1]
        rc = wait_head(a, path, proc, pid)
        if proc is not None:
            pid = proc.pid
        stopped_at = time.time()
        # Where each unparseable line sits among the events, read with them (critic finding 3 of
        # the review of 2026-10-11): a line written after the head's start event and before this
        # watch began — an attach, or the console opened after the start — lies inside its window
        # as surely as one the watch saw arrive.
        bad_at = []
        events, bad_stop = read_record(path, bad_at)
        cls, d = stop_class(events, start, out, offset, rc, transcript_for(sid) if sid else None)
        unsucceeded_wait = a.wait_s
        if cls == "unsucceeded":
            # C2 N4: the head's own successor call may still be on its way (the starter's wait).
            # Once that starter has aborted, only a re-called one could start a successor, and
            # its own wait bounds this one (starter_gone; register entry 2026-10-25 16:28).
            gone_bound, gone_line = starter_gone(events, start, a.tick_s, a.wait_s)
            if gone_bound is not None:
                unsucceeded_wait = gone_bound
                say(gone_line)
            deadline = stopped_at + unsucceeded_wait
            while time.time() < deadline:
                time.sleep(max(0.0, min(a.tick_s, deadline - time.time())))
                bad_at = []
                events, bad_stop = read_record(path, bad_at)
                cls, d = stop_class(events, start, out, offset, rc, None)
                if cls != "unsucceeded":
                    break
        before_i, before_ev = previous_stop_event(events)
        before = (before_ev or {}).get("exit_class")
        progress, progress_note = head_progress(events, pid, start, bad_watch, bad_stop, bad_at)
        append_record(path, event(a.run, "observation", phase="", what="head exited",
                                  exit_class=cls, pid=pid, progress=progress,
                                  progress_note=progress_note,
                                  note="session %s exit %s after %d s → %s (%s); output %s"
                                       % (sid, "unknown" if rc is None else rc,
                                          stopped_at - t0, cls, d["note"], out)))
        say("supervisor: session %s exit %s → %s (%s) · progress %s (%s)"
            % (sid, "unknown" if rc is None else rc, cls, d["note"], progress, progress_note))
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
        # Two stops in a row whose heads each made no progress end the loop, the successor cap
        # being only the backstop (the repeat-stop design of 2026-10-11, Revision 2, after its
        # design review): this stop and the previous recorded one both pair (stop_pairs, any mix
        # of classes; the previous one not stood down) and both read `progress: no`, a boundary by
        # neither head's own process. A head that recorded a boundary breaks the pair; `unknown`
        # on either side — and an observation written before the field existed reads unknown —
        # leaves the start to the successor cap and the stop marker. An abort and a restart
        # between the two reset nothing: a restarted head breaks the pair with a boundary.
        # An unsucceeded head's own packed exit also breaks the pair: its hand-over is on the
        # record, and the wait above already covered its missing successor call.
        if stop_pairs(cls, events, pid=pid) and progress == "no" and before_ev is not None and \
                stop_pairs(before, events, before_i) and not stood_down_after(events, before_i) and \
                before_ev.get("progress") == "no":
            return abort(path, a.run, "repeat-stop", "two consecutive %s and %s stops with no "
                         "progress (%s; %s): the head does not get a third start without one"
                         % (before, cls, before_ev.get("progress_note", "no note"),
                            progress_note))
        waited, source, watch = 0.0, "none: no wait after a %s stop" % cls, None
        delay = 0
        network_no_work_n = 0
        if cls == "network":
            if not sid:
                return abort(path, a.run, "session-unknown", "network stop has no head session to resume")
            resumed = events[start] if 0 <= start < len(events) else {}
            is_network_resume = (resumed.get("event") == "head-resumed" and
                                 resumed.get("session_id") == sid and resumed.get("exit_class") == "network")
            if is_network_resume:
                network_no_work_n = resumed.get("network_no_work_n")
                if type(network_no_work_n) is not int or network_no_work_n < 0:
                    return abort(path, a.run, "network-state-unknown", "unreadable network resume count")
            evidence = network_resume_evidence(events, start, pid,
                record_uncertain=bad_stop > bad_watch or any(k > start for k in bad_at))
            delay = network_delay(events, start, sid, pid, out, offset)
            watch = StandDown(a.run, transcript_for(sid) if sid else None, "resume", "network")
            status, source, waited = wait_for_network(a, path, start, stopped_at, watch, delay)
            if status == "stood-down":
                return stand_down(path, a.run, watch.reason, watch.detail, "resume", "network", waited)
            if status == "closed":
                return 0
            if status != "ok":
                return 1
            # A provider wait is not a resume. Once it answers, judge the completed resume:
            # readable absence counts, positive work resets, unknown progress does neither.
            if is_network_resume:
                if evidence["progress"] == "yes":
                    network_no_work_n = 0
                elif evidence["progress"] == "no":
                    network_no_work_n += 1
            append_record(path, event(a.run, "network-resume-judged", session_id=sid, pid=pid,
                                      resumed=is_network_resume, provider_answer=True,
                                      no_work_n=network_no_work_n, **evidence))
            if network_no_work_n >= NETWORK_NO_WORK_LIMIT:
                return abort(path, a.run, "network-no-progress",
                             "two network resumes did no new work while the provider answered")
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
        # Every start below needs a model (K3dbf76d5): one refusal here, before either fork, so
        # a resume that cannot start never falls through to a successor that cannot either.
        model, msrc = launch_model(a, path)
        if model is None:
            return abort(path, a.run, "model-unknown", "no model for the next head: %s; no "
                         "harness process was started — start the successor by hand with "
                         "--model" % msrc)
        if cls == "unsucceeded":
            say("supervisor: the head-exit has no successor after %d s — starting one at $%.2f "
                "(%s)" % (unsucceeded_wait, budget, bsrc))
            started = succeed_exit(a, path, budget, t0)
            if started is None:
                return 1
            proc, sid, out, offset, start = started
            continue
        m = head_context(sid, events, start)
        resumes = sum(1 for e in events
                      if e.get("event") == "head-resumed" and e.get("session_id") == sid)
        if (cls in ("limit", "network", "budget") and m.get("context") is not None and
                resume_in_place(events, m, stopped_at, remaining_of(a, events))
                and resumes < RESUME_CAP):
            events, _ = read_record(path)
            if any(e.get("event") in ("head-resumed", "head-successor")
                   for e in events[start + 1:]):
                return abort(path, a.run, "duplicate-resume", "a head-resumed or head-successor "
                             "already follows this head's start: another supervisor got there "
                             "first")
            if any(e.get("event") == "run-close" for e in events[start + 1:]):
                return 0
            if watch is not None and watch.check():   # the last act before a start (D43)
                return stand_down(path, a.run, watch.reason, watch.detail, watch.on_limit,
                                  watch.src, waited)
            resumed = resume_head(a, path, sid, budget, bsrc, out, m, cls, waited, source,
                                  stopped_at, network_delay_s=delay, network_no_work_n=network_no_work_n,
                                  successor_fallback=cls in ("limit", "network"))
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


def open_lanes_line(events):
    """The starter's first line: every lane open on the whole record (open_lane_attempts) with
    its processes' liveness as the record names them — read, never signalled or restarted
    (register entry 2026-09-24 00:4x: detached lanes died at hand-overs, and nothing showed which
    were open when the successor path ran)."""
    lanes = open_lane_attempts(events)
    if not lanes:
        return "starter: open lanes at the start: none on the record"
    return "starter: open lanes at the start (%d): %s" % (len(lanes), "; ".join(
        "%s open since %s (%s)" % (lane, opened.get("ts", "no ts"), lane_liveness(spawned))
        for lane, opened, spawned in lanes))


@a3_expose_notices
def cmd_starter(a):
    t0 = time.time()
    path = record_path(a.run)
    say(open_lanes_line(read_record(path)[0]))
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
            evs = read_record(path)[0]
            si = last_index(evs, START_EVENTS)
            if (si >= 0 and event_pid(evs[si]) == a.predecessor_pid and row is not None
                    and harness_command(row[2])):
                # The head's own process outlived its hand-over (register entry 2026-10-25
                # 16:28): the reason stays `timeout`, which launch-check reads; the note names
                # the likely cause and what follows.
                why += (" (%s, running %s): the head's own process, still alive after its "
                        "hand-over — a print-mode head stays alive while a background task it "
                        "started runs; %s; its supervisor starts the successor once it exits, "
                        "within three ticks of the exit"
                        % (row[2], "for an unknown time" if age is None else "%d s" % age,
                           shell_children_text(a.predecessor_pid)))
            else:
                why += (" (%s, running %s): a long-lived process — a launcher's own, or an "
                        "attended conversation's — does not exit at the end of a reply; a seed "
                        "pid must belong to a process that exits within seconds"
                        % (row[2] if row else "command unknown",
                           "for an unknown time" if age is None else "%d s" % age))
    else:
        say("starter: %s pid %d waits for transcript silence" % (now(), os.getpid()))
        gone = wait_silent(a.transcript, SILENCE_PROXY_S, a.wait_s)
        why = "transcript %s still changing after %d s" % (a.transcript, a.wait_s)
    events, _ = read_record(path)
    reason, detail = start_guards(events, last_index(events, ("head-exit",)), gone, why,
                                  run=a.run)
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
           "--tick-s", str(a.tick_s), "--wait-s", str(a.wait_s),
           "--beat-timeout-s", str(a.beat_timeout_s)]
    if a.probe:
        cmd += ["--probe"]   # never on its own: only when this caller opted in (2026-09-06)
    for flag, value in (("--reset-at", a.reset_at), ("--model", a.model), ("--effort", a.effort),
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


@a3_expose_notices
def cmd_resume_head(a):
    """`resume-head` (D42's recovery; critic C2 M4): resume the record's last head session in
    place — armed, evented and supervised — the owner's command after a limit the run stood down
    on, instead of an unarmed hand-run `claude -p --resume`. Detaches at once, like `supervise`.
    The head resumes on --model, else the newest head start's structured model on the record;
    a record naming none is refused before anything is written (register entry 2026-09-23 12:5x)."""
    path = record_path(a.run)
    events = require_record(path)
    sid, sev = head_session(events)
    if not sid:
        die("no head session in the record: run-open first")
    # The model the head is resumed on, before anything detaches (K3dbf76d5): --model, else the
    # newest head start's structured model on the record; none refuses the call.
    model, msrc = resolve_head_model(events, a.model)
    if model is None:
        die("resume-head needs a model to resume the head on: %s; pass --model (a hands-off head "
            "never starts on the harness default); nothing written" % msrc)
    effort, esrc = resolve_head_effort(events, a.effort)
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
           "--tick-s", str(a.tick_s), "--wait-s", str(a.wait_s), "--effort", effort,
           "--effort-src", esrc,
           "--beat-timeout-s", str(a.beat_timeout_s), "--model", model, "--model-src", msrc]
    if a.probe:
        cmd += ["--probe"]
    for flag, value in (("--reset-at", a.reset_at),
                        ("--config-dir", a.config_dir), ("--handoff", a.handoff),
                        ("--meter-line", a.meter_line)):
        if value:
            cmd += [flag, value]
    if a.budget_usd is not None:
        cmd += ["--budget-usd", "%.2f" % a.budget_usd]
    if a.dry_run:
        say("resume-head: dry run · session %s · out %s (%s) · model %s (%s) · would detach %s%s"
            % (sid, out, osrc, model, msrc, " ".join(cmd[3:]),
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
        # The path sought is named (register entry 2026-09-24 07:3x: the abort said `no
        # transcript` of a head whose transcript existed, and nothing said where it had looked).
        sought = m.get("transcript") or transcript_for(a.session)
        return abort(path, a.run, "resume-unsized", "the head's context cannot be sized: no "
                     "usable transcript (sought %s: %s) and no gate event with a context in the "
                     "session's span: start the successor from the hand-off instead"
                     % (sought, one_line(str(m.get("reason") or "unknown"))[:NOTE_CUT]))
    verdict, why, stop_cls, stopped_at = resume_guard(events, m, start, remaining_of(a, events))
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
    name is carried from the file; --add-grant and --add-write add to the baseline's lists; and
    the shrink guard refuses any rewrite that would lose a path from either list unless the call
    passes --replace (register entries 2026-09-12 21:3x and 2026-09-29 20:49). --network rewrites
    the network key and --max-successors the run's successor cap; without them the file's values
    are carried."""
    refuse_grants_file(a)
    check_grant_forms(a, "grants")
    path = record_path(a.run)
    events = require_record(path)
    sid, _ = head_session(events)
    if not sid:
        die("no head session in the record: run-open first")
    gpath = grants_path(a.run)

    def plan(events):
        on_limit, osrc = on_limit_choice(a, gpath)
        viewer, vsrc = viewer_choice(a, gpath)
        network, nsrc = network_choice(a, gpath)
        cap, csrc = max_successors_choice(a, gpath)
        payload, sources, dropped, against = grants_plan(a, gpath, events, "grants")
        guard_shrink(a, "grants", dropped, against)
        ev = event(a.run, "grants", grants_file=gpath, grants=payload["grants"],
                   writes=payload["writes"], session=sid, on_limit=on_limit, on_limit_src=osrc,
                   viewer=viewer, viewer_src=vsrc, network=network, network_src=nsrc,
                   grants_src=sources["grants"], writes_src=sources["writes"])
        if cap is not None:
            ev["max_successors"], ev["max_successors_src"] = cap, csrc
        return payload, sources, ev

    if a.dry_run:
        _, _, ev = plan(events)
        say("grants: dry run · %s" % json.dumps(ev, ensure_ascii=False))
        return 0
    # The plan, the file and the event under the record's lock, the record re-read inside it: two
    # calls adding a path each serialise here, so neither addition is lost (critic finding 4 of
    # the batch's design review).
    with record_lock(path):
        events, _ = read_record(path)
        payload, sources, ev = plan(events)
        write_grants(gpath, payload)
        write_pointer(a.run, sid)
        append_record(path, ev)
    say("grants: %s · %d grants (%s) · %d writes (%s) · on_limit %s (%s) · viewer %s (%s) · "
        "network %s (%s)%s · pointer run-%s"
        % (ev["grants_file"], len(payload["grants"]), sources["grants"], len(payload["writes"]),
           sources["writes"], ev["on_limit"], ev["on_limit_src"], ev["viewer"],
           ev["viewer_src"], network_shown(ev["network"]), ev["network_src"],
           " · max_successors %d (%s)" % (ev["max_successors"], ev["max_successors_src"])
           if "max_successors" in ev else "", sid[:8]))
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
    # Before the record, the pid file, the stop marker or any wait (register entry 2026-09-25
    # 18:2x: a `-p` head armed the run's one heartbeat and blocked the attended watch's beat): a
    # caller under AIMYTH_HANDSOFF=1 is a hands-off head, which has no idle state for a beat to
    # refresh, so the call is refused with one line and touches nothing.
    if os.environ.get("AIMYTH_HANDSOFF") == "1":
        die("heartbeat refused: this caller runs under AIMYTH_HANDSOFF=1, a hands-off head, which "
            "has no idle state for a beat to refresh; the run's one heartbeat belongs to an "
            "attended session; nothing armed, stopped or written")
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
    `which` opens `limit`) with the first head start that followed it — a head-successor,
    run-resume or head-resumed (register entry 2026-09-24 13:1x) — and the minutes between, and
    every lane closed `limit`; each count stated, so none reads as searched-and-empty."""
    heads = []
    for i, ev in enumerate(events):
        if ev.get("event") != "stop-condition" or not str(ev.get("which") or "").startswith("limit"):
            continue
        who = ev.get("lane") or "head"
        # The stop ends at the first head start after it (WAIT_END_EVENTS; register entry
        # 2026-09-24 13:1x), so a successor that took over is named rather than a later resume.
        resumed = next((x for x in events[i + 1:] if x.get("event") in WAIT_END_EVENTS), None)
        t0 = parse_ts(ev.get("ts"))
        t1 = parse_ts(resumed.get("ts")) if resumed is not None else None
        if resumed is None:
            heads.append("%s at %s (%s), no head start after it" % (who, ev.get("ts", "no ts"),
                                                                    ev.get("which")))
        elif t0 is not None and t1 is not None and t1 >= t0:
            heads.append("%s at %s (%s) → %s %s, %s min" % (
                who, ev.get("ts"), ev.get("which"), resumed.get("event"), resumed.get("ts"),
                fmt_min((t1 - t0) / 60.0)))
        else:
            heads.append("%s at %s (%s) → %s %s" % (
                who, ev.get("ts", "no ts"), ev.get("which"), resumed.get("event"),
                resumed.get("ts", "no ts")))
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


def close_plain(a, path, events, acked=None, seen=None):
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
    held, fields = close_recheck(a, path, acked, len(events) if seen is None else seen)
    if held is not None:
        return held
    ev.update(fields)
    ev["holds_ended"] = end_open_holds(path, a.run, events, "close")
    append_record(path, ev)
    say("close: %s · plain lane run (no run-open) · lanes %d (%s) · spend $%.2f (%s) · "
        "decisions %d · no hand-off row, no commit, no push"
        % (a.run, len(names), tally, spend, src, decisions))
    return 0


def close_statements(a):
    """The close's statements, checked before anything is read or written (register entry
    2026-09-20 02:12: a run-close carried items, register, log and lint `unstated`, and the
    record's own verdict on the items lived only in a hand-off). --items is required: absent or
    blank, the close is refused (exit 2) — a dry run reads it as unstated with a note, since it
    writes nothing. An absent --register, --log or --lint is written `unstated` with one stderr
    note each."""
    if a.items is None or not str(a.items).strip():
        if not a.dry_run:
            die("close needs --items: the record's own verdict on the run's items (for example "
                "\"item1 done; item2 held: <why>\"); nothing written")
        note("close: --items absent: a real close refuses that; this dry run reads it as "
             "unstated")
        a.items = "unstated"
    for flag in ("register", "log", "lint"):
        value = getattr(a, flag, None)
        if value is None or not str(value).strip():
            note("close: --%s absent: written as unstated" % flag)
            setattr(a, flag, "unstated")


def close_recheck(a, path, acked, seen):
    """The final recheck of the decisions channel, after the close has prepared everything and
    before its first write (critic finding 6 of the batch's design review: an append racing the
    acknowledgement was caught only by a next call, and a close has none). The owner's
    provisional choice of 2026-10-10: the close re-reads the decisions file and the record's
    AUTHOR observations at this point, holds (exit 6, nothing written) when either moved after the
    call's own read, and otherwise records the cutoff it acknowledges — what arrives after it (in
    the close's own writes, its commit or its push) is not covered by this close, and the
    run-close says so. `seen` is the length of the very snapshot the decisions channel checked,
    never a later read (critic finding 1 of the review of 2026-10-11: an AUTHOR observation
    appended between the check and a second read fell behind the cursor unread); every event
    after it is rechecked except this call's own acknowledgement (`a.own_ack`), left out once.
    Returns (code or None, the run-close's decisions fields)."""
    cutoff = now()
    since = list(read_record(path)[0][seen:])
    own = getattr(a, "own_ack", None)
    if own is not None and own in since:
        since.remove(own)   # the first equal event only: the call's own ack, and nothing else
    authored = [e for e in since if e.get("event") == "observation"
                and AUTHOR_RE.match(str(e.get("what") or ""))]
    dfile = getattr(a, "decisions_file", None)
    changed = None
    if dfile is not None and acked is not None:
        fpath, data, digest = decisions_digest_of(dfile)
        if digest != acked[2]:
            changed = (fpath, data, digest)
    if authored or changed:
        say("close: HOLD (decisions channel, exit %d) — %s arrived while the close was preparing, "
            "after its read at the call and before its first write: nothing written; read %s and "
            "run the close again" % (EXIT_HOLD, " and ".join(
                part for part in ("%d AUTHOR observation(s)" % len(authored) if authored else "",
                                  "a change to the decisions file" if changed else "") if part),
                "them" if authored and changed else "it"))
        for e in authored:
            say("  %s · %s" % (e.get("ts", "no ts"), one_line(e.get("what") or ""))[:NOTE_CUT])
        if changed:
            fpath, data, digest = changed
            grown = digest_prefix(data, acked[2])
            lines = text_lines(data[grown:]) if grown is not None else text_lines(data)
            say("  %s · %d byte(s) now · %s:" % (
                fpath, len(data), "%d line(s) appended since the call's read" % len(lines)
                if grown is not None else "edited, not only appended to, since the call's read: "
                                          "the whole file"))
            for line in lines:
                say("  | " + line)
            say("  " + decisions_read_hint(a.run, dfile))
        return EXIT_HOLD, {}
    fields = {"decisions_cutoff": cutoff,
              "decisions_cutoff_note": "the close re-read the decisions channel at this time, "
                                       "after its preparation and before its first write; what "
                                       "arrives after it is not covered by this close"}
    if dfile is not None and acked is not None:
        fields.update(decisions_file=acked[0], decisions_digest=acked[2],
                      decisions_size=len(acked[1]))
    return None, fields


def disarm_markers(run, events, dry_run=False):
    """[(session, outcome, detail)] for the arming marker `armed-<sid>` of every head session the
    record names (register entry 2026-09-30 18:48: markers of ended sessions were never removed).
    A marker is removed only where this run still owns its session — the state directory's
    pointer `run-<sid>` names this run (critic finding 3 of the batch's design review: a session
    can belong to a later run since) — and kept where the pointer names another run; a missing,
    unreadable or malformed pointer leaves the marker in place as `unresolved`, its ownership
    unread. A marker already gone is `absent`, a success; a removal the system refuses is
    `failed`, named, and `disarm` retries it. A dry run removes nothing (`would remove`)."""
    results = []
    for sid in run_heads(events)[0]:
        marker = os.path.join(state_dir(), "armed-" + sid)
        pointer = os.path.join(state_dir(), "run-" + sid)
        if not os.path.lexists(marker):
            results.append((sid, "absent", "no marker"))
            continue
        try:
            with open(pointer, encoding="utf-8") as handle:
                owner = handle.read().strip()
        except FileNotFoundError:
            results.append((sid, "unresolved", "no pointer %s, so whose arming this is cannot be "
                                               "read: the marker is kept" % pointer))
            continue
        except OSError as exc:
            results.append((sid, "unresolved", "the pointer %s is unreadable (%s): the marker is "
                                               "kept" % (pointer, exc)))
            continue
        if not TOKEN_RE.fullmatch(owner or ""):
            results.append((sid, "unresolved", "the pointer %s names no single run (%r): the "
                                               "marker is kept" % (pointer, owner[:60])))
            continue
        if owner != run:
            results.append((sid, "kept", "its pointer names run %s, which owns the session now"
                                         % owner))
            continue
        if dry_run:
            results.append((sid, "would remove", marker))
            continue
        try:
            os.remove(marker)
            results.append((sid, "removed", marker))
        except FileNotFoundError:
            results.append((sid, "absent", "removed meanwhile"))
        except OSError as exc:
            results.append((sid, "failed", "%s: %s — `handsoff.py disarm --run %s` retries it"
                                           % (marker, exc, run)))
    return results


def disarm_line(run, results):
    """One summary line for disarm_markers' results, each session short and its outcome."""
    counts = {}
    for _, outcome, _ in results:
        counts[outcome] = counts.get(outcome, 0) + 1
    shown = " · ".join("%s %d" % (k, counts[k]) for k in sorted(counts)) or "no head session"
    detail = "; ".join("%s %s (%s)" % (sid[:8], outcome, detail)
                       for sid, outcome, detail in results if outcome != "absent")
    return "disarm: %s · %s%s" % (run, shown, " · " + detail if detail else "")


def cmd_disarm(a):
    """`disarm --run R [--dry-run]`: the arming markers of the run's head sessions removed after
    its close (disarm_markers): the retry for a removal the close could not make, and the form
    for a run closed before the close removed them. A run with no run-close is refused (exit 2):
    a live run's head stays armed. Exit 0 when every marker is removed, kept for another run or
    already absent; 1 when any is unresolved or failed. An environment arming (AIMYTH_HANDSOFF=1
    in a process) is not a marker, and this verb claims nothing about it."""
    path = record_path(a.run)
    events = read_existing_record(path)
    ci = last_index(events, ("run-close",))
    if ci < 0:
        die("run %s carries no run-close: disarm follows the close, and a live run's head stays "
            "armed; nothing removed" % a.run)
    results = disarm_markers(a.run, events, a.dry_run)
    say(disarm_line(a.run, results) + (" (dry run: nothing removed)" if a.dry_run else ""))
    if os.environ.get("AIMYTH_HANDSOFF") == "1":
        say("disarm: note: AIMYTH_HANDSOFF=1 is set in this process's environment; an environment "
            "arming is not a marker, and disarm cannot clear it")
    return 1 if any(outcome in ("unresolved", "failed") for _, outcome, _ in results) else 0


@a3_expose_notices
def cmd_close(a):
    close_statements(a)   # --items before anything is read or written (register 2026-09-20 02:12)
    path = record_path(a.run)
    events = read_existing_record(path)
    held, acked = decisions_hold(a, path, events, "close")   # the decisions channel (2026-09-13)
    if held is not None:
        return held
    # The recheck's cursor is the snapshot the decisions channel checked, never a second read
    # (critic finding 1 of the review of 2026-10-11): anything appended since — an owner's relay
    # that raced the call included — is rechecked, the call's own ack alone left out. That ack
    # records this same length as what it covers (DECISIONS_SEEN), so when the recheck holds, the
    # next call still finds the relay pending (critic finding F1 of the second review).
    seen = len(events)
    if is_plain_run(events):
        return close_plain(a, path, events, acked, seen)
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
    unresolved = items_unresolved(events)
    if unresolved:
        ev["items_unresolved"] = [item for item, _ in unresolved]
        say("close: %d item(s) started with no completion record, which the console reads as "
            "unresolved: %s. This close converts none: run `item-done <item>` first for each one "
            "that finished" % (len(unresolved), ", ".join(
                "%s (started %s)" % row for row in unresolved)))
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
        say("close: dry run · %s" % disarm_line(a.run, disarm_markers(a.run, events, True)))
        return 0
    # The final recheck (G1, critic finding 6): the last read before the first write.
    held, fields = close_recheck(a, path, acked, seen)
    if held is not None:
        return held
    ev.update(fields)
    if refreshed:
        write_atomic(ho, "\n".join(lines))
    if report is not None and report_changed:
        write_atomic(report, report_text)   # before the commit, so the checkpoint carries it
    if a.commit is not None:
        ev["root_untracked"], root_line = root_untracked(vault_root())
        say("close: %s" % root_line)
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
    say("decisions: %s" % ("the decisions file as read at the call (sha256 %s…, %d byte(s)) "
                           "unchanged at the cutoff %s; what arrives after it is not covered by "
                           "this close" % (fields["decisions_digest"][:12],
                                           fields["decisions_size"], fields["decisions_cutoff"])
                           if "decisions_digest" in fields
                           else "no decisions file named; the AUTHOR observations re-read at the "
                                "cutoff %s" % fields["decisions_cutoff"]))
    # The arming markers of the run's head sessions, once run-close is on the record (K9dd0b7fb).
    say(disarm_line(a.run, disarm_markers(a.run, read_record(path)[0])))
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
    ("fence_denials", "lane fence denials", "arguable", "count"),
    ("sandbox_denials", "lane sandbox denials", "arguable", "count"),
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
          "excludes, take a structural row of their own; the heads' total reads a billed line "
          "carried by hand as `session ≈ <n>` or `session USD <n>` as well as the meter's "
          "`session $<n>`, and names the form it read. The two rows added that day appear only "
          "on boundaries that carry their fields. The run total (2026-09-20 01:09) is the run's "
          "spend as the last boundary or close recorded it, every head alone plus every lane, "
          "never the heads' total plus the lanes, since a head's session figure may already hold "
          "some of them." % (
              IDLE_GAP_S, REPORT_CAP_WORDS, WORDS_TO_TOKENS))
# What each of the three re-defined fields means on a given boundary, read off the marker
# fields the boundary command writes beside them; a boundary written before the rule has none
# and is labelled as recorded, never re-read under the new meaning.
FIELD_MEANINGS = {
    "idle_min": lambda ev: {
        "transcript": ("head idle: no lane running and the head waiting, gaps above %d s that end "
                       "in something other than the head's own record, read from its transcript "
                       "(idle_src transcript)" % IDLE_GAP_S if ev.get("idle_rule") == "waits" else
                       "head idle: no lane running and no head call, gaps above %d s, the "
                       "head's calls from its transcript (idle_src transcript)" % IDLE_GAP_S),
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
    "fence_denials": lambda ev: ("the lanes' own fence denials, summed from each lane close's "
                                 "denials.fence (beside the tool denials, never added to them)"),
    "sandbox_denials": lambda ev: ("the lanes' sandbox denials, summed from each lane close's "
                                   "denials.sandbox (a Codex lane's; beside the tool denials, "
                                   "never added to them)"),
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


# The head starts that end a limit wait (register entry 2026-09-24 13:1x): a successor head, a
# head's own run-resume and an in-place resume each mean a head is working again.
WAIT_END_EVENTS = ("head-successor", "run-resume", "head-resumed")


def fmt_min(minutes):
    """Minutes with one decimal, or two where the second is not zero (0.75 min reads 0.75)."""
    text = "%.2f" % minutes
    return text[:-1] if text.endswith("0") else text


def limit_waits(events):
    """[(stop-condition, the head start that ended the wait, minutes)] for every recorded LIMIT
    stop (a stop-condition whose `which` opens `limit`; a band or envelope stop is no wait) that a
    head start follows: the wait ends at the FIRST head-successor, run-resume or head-resumed after
    the stop, so it never runs on through a successor that was working (register entry 2026-09-24
    13:1x: waits of 622.5 and 229.7 minutes where the record showed a successor 0.75 and 19.4
    minutes after the stop). The limits ruling makes that wait a cost of the chosen shape, so
    the table gives it a structural row of its own rather than leaving it inside idle_min's real
    class (register entry 2026-09-06)."""
    found = []
    for i, ev in enumerate(events):
        if ev.get("event") != "stop-condition" or \
                not str(ev.get("which") or "").startswith("limit"):
            continue
        ended = next((x for x in events[i + 1:] if x.get("event") in WAIT_END_EVENTS), None)
        if ended is None:
            continue
        t0, t1 = parse_ts(ev.get("ts")), parse_ts(ended.get("ts"))
        if t0 is None or t1 is None or t1 < t0:
            continue
        found.append((ev, ended, (t1 - t0) / 60.0))
    return found


def limit_wait_rows(events):
    """One structural row per recorded limit wait; none where the record holds no such pair."""
    rows = []
    for stop, ended, minutes in limit_waits(events):
        rows.append(("limit wait · %s → %s at %s"
                     % (stop.get("which", "stop-condition"), ended.get("event"),
                        ended.get("ts", "no ts")),
                     "%s min · stop-condition at %s to the first head start after it, the %s at "
                     "%s · a cost of the chosen shape (the limits ruling), not head idleness: a "
                     "boundary whose span covers it counts the same minutes under idle_min"
                     % (fmt_min(minutes), stop.get("ts", "no ts"), ended.get("event"),
                        ended.get("ts", "no ts")),
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
        oi = last_index(events, ("run-open",))
        t0 = parse_ts(events[previous].get("ts")) if 0 <= previous < len(events) else \
            parse_ts((events[oi] if oi >= 0 else events[0]).get("ts"))
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


# The heads' total's reader (register entry 2026-09-09 15:43): a boundary's billed line is the
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


def recorded_run_total(events):
    """The waste table's run total, or None when no event carries one (register entry 2026-09-20
    01:09: the row read the heads' session figures alone, USD 20.40, while the boundary's run
    spend read USD 78.63 with the lanes): the run's spend as the latest phase-boundary or
    run-close recorded it, the figure its own line printed — every head metered alone plus every
    lane on the record (run_spend) — so no lane is counted twice, as adding the lanes to a head's
    session figure, which may already hold some of them, would. Lane closes and beats recorded
    after that event are named, the figure predating them."""
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.get("event") not in ("phase-boundary", "run-close") or "run_spend_usd" not in ev:
            continue
        where = "the %s at %s" % (ev["event"], ev.get("ts", "no ts"))
        src = one_line(str(ev.get("run_spend_src") or "no source recorded"))
        later = []
        for e in events[i + 1:]:
            if e.get("event") in ("lane-closed", "hold-beat") and e.get("lane") \
                    and str(e["lane"]) not in later:
                later.append(str(e["lane"]))
        tail = (" · it predates the lane close(s) or beat(s) recorded after it: %s"
                % ", ".join(later) if later else "")
        figure = money(ev.get("run_spend_usd"))
        if figure is None:
            return "unmeasured · %s recorded no run figure (%s)%s" % (where, src, tail)
        return "%s$%.2f · run_spend_usd of %s, the figure its line printed (%s)%s" % (
            "at least " if ev.get("run_spend_floor") else "", figure, where, src, tail)
    return None


def billed_rows(events, metered=None):
    """The billed line at every boundary, quoted as the meter printed it, and the whole-run
    rows: the heads' total as a shown sum of the per-head figures head_totals derives, with the
    envelope base beside it, and the run total as the last boundary or close recorded it
    (recorded_run_total), never a sum of the two. An unmetered or failed line is quoted, never
    zeroed."""
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
    recorded = recorded_run_total(events)
    if not rows and not totals and recorded is None:
        return rows
    oi = last_index(events, ("run-open",))
    envelope = events[oi].get("envelope_usd") if oi >= 0 else None
    base = (" · envelope base $%.2f (run-open.envelope_usd)" % float(envelope)
            if isinstance(envelope, (int, float)) and not isinstance(envelope, bool)
            else " · no envelope base (%s)" % ("run-open carries no envelope_usd" if oi >= 0
                                                else "no run-open: an attended record"))
    seeds = seed_sessions(events)
    skipped = (" · seed (skipped): %s, marked seed by run-open and never a head"
               % ", ".join(seeds) if seeds else "")
    heads_usd = round(sum(usd for _, usd, _ in totals), 2)
    if totals:
        shown = " + ".join("$%.2f" % usd for _, usd, _ in totals)
        fig = "%s = $%.2f · per head: %s%s%s%s" % (
            shown, heads_usd,
            "; ".join("%s %s" % (sid, why) for sid, _, why in totals), base, skipped,
            "; %d boundary line(s) carried no session figure and are quoted above, never read "
            "as zero" % quoted if quoted else "")
    elif oi < 0:
        fig = ("unavailable · the record carries no run-open (an attended session's record), so "
               "no head session is on it and no head figure is read%s" % base)
    else:
        fig = ("unmeasured · no boundary billed line carried a `session $` figure and no "
               "head-exit recorded spend; the %d line(s) are quoted above, never read as "
               "zero%s%s" % (quoted, base, skipped))
    rows.append(("heads' total (shown sum)", fig, "billed", FIX_NA))
    rows.append(("run total (recorded run spend)", recorded if recorded is not None else (
        "unrecorded · no phase-boundary or run-close on the record carries run_spend_usd (a "
        "record older than the run figure, or one that reached no boundary): `handsoff.py "
        "run-spend` meters it, every head alone plus every lane, and the heads' total above is no "
        "run total"), "billed", FIX_NA))
    return rows


def context_rows(events):
    """Context per item, read off the gate events as the delta between consecutive gates of one
    head session. A gate opens its item, so the delta at a gate is the growth of the item before
    it, and the row names that item; a head's first gate is differenced with nothing, since the
    context across a hand-over is two heads' and no item's growth. A gate after an unmetered gate
    is differenced with nothing too: that interval spans two items, so it is neither's growth."""
    gates = [e for e in events if e.get("event") == "gate"]
    if not gates:
        return [("context per item", "no gate events in the record · Step 2b drops the context "
                 "column for this run", "context", FIX_NA)]
    rows, prev, prev_item, sid, seen = [], None, None, None, False
    for e in events:
        if e.get("event") in SESSION_EVENTS and start_session(e) != sid:
            sid, prev, prev_item = start_session(e), None, None
            continue
        if e.get("event") != "gate":
            continue
        item = "context · item %s at %s" % (e.get("item", "?"), e.get("ts", "no ts"))
        value = e.get("context")
        if not isinstance(value, int):
            rows.append((item, "unmeasured · the gate is unmetered (band %s)"
                         % e.get("band", "?"), "context", FIX_NA))
            prev, prev_item = None, None
            continue
        if prev is None and seen:
            rows.append((item, "%s tokens · no comparable preceding gate: nothing is differenced"
                         % format(value, ","), "context", FIX_NA))
        elif prev is None:
            rows.append((item, "%s tokens · the first metered gate, no earlier gate to "
                         "difference%s" % (format(value, ","),
                                           " (one gate event only)" if len(gates) == 1 else ""),
                         "context", FIX_NA))
        else:
            delta = value - prev
            rows.append(("context · item %s, to the gate of item %s at %s"
                         % (prev_item, e.get("item", "?"), e.get("ts", "no ts")),
                         "%s%s tokens · gate context %s → %s"
                         % ("+" if delta >= 0 else "-", format(abs(delta), ","),
                            format(prev, ","), format(value, ",")), "context", FIX_NA))
        prev, prev_item, seen = value, e.get("item", "?"), True
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
    attended = last_index(events, ("run-open",)) < 0
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
    ]
    if attended:
        header.append("Head figures: unavailable — the record carries no run-open (an attended "
                      "session's record, the plain-lane-run shape), so no head session is on it: "
                      "the head rows say unmeasured or unavailable, and the lane rows are the "
                      "record's evidence.")
    header += [
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
    events = read_existing_record(path)   # a record with no run-open renders too (its own header)
    bad = read_record(path)[1]
    out_path = (os.path.realpath(os.path.expanduser(a.out)) if a.out else
                os.path.join(store_root(), "spawn-records", "%s-waste-table.md" % a.run))
    metered = metered_heads(events, a.run, a.no_meter, meter_overrides(a.meter_line))
    text, _, counts = waste_table(events, a.run, path, bad, metered, meter_lanes=not a.no_meter)
    summary = "%d rows from %d boundaries, %d gates, %d lanes" % (
        counts["rows"], counts["boundaries"], counts["gates"], counts["lanes"])
    ci = last_index(events, ("run-close",))
    if not a.out and ci >= 0:
        # A closed run's stored table is left as it is (register entry 2026-10-03 07:48: reading
        # an earlier run's table re-rendered and replaced its stored copy): the render goes to
        # standard output, and --out names a file when one is wanted.
        if a.dry_run:
            say("waste-table: dry run · %s · run %s is closed: would print to standard output and "
                "leave %s as it is" % (summary, a.run, out_path))
            return 0
        sys.stdout.write(text)
        sys.stdout.flush()
        note("waste-table: %s · run %s is closed (run-close at %s): printed to standard output; "
             "the stored table %s is left as it is (pass --out PATH to write a file)"
             % (summary, a.run, events[ci].get("ts", "no ts"), out_path))
        return 0
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
# The harness's interrupt marker: a user record the owner never typed, never a human turn. A
# marker beside the owner's own words is cut from them, as a system reminder is (register entry
# 2026-09-13 03:53, its recurrence of 2026-09-20: a marker counted as a human turn).
INTERRUPT_RE = re.compile(r"^\s*\[Request interrupted by user[^\]]*\]\s*$")
INTERRUPT_ANY_RE = re.compile(r"\[Request interrupted by user[^\]]*\]")
# A message relayed from another session (a peer's or a launcher's): never the owner's words,
# whichever record carries it, though it may relay them (register entry 2026-09-13 03:53, the
# status of 2026-10-01: counting it would read a relay of the owner's word as his consent).
# A message relayed from another session, in either wrapper (register entry 2026-10-25 17:23). The
# session tool closes `<session_message>` and then adds its own one-line reply note, which belongs
# to the relay: read as text beside it, that note became an owner turn.
CROSS_SESSION_RE = re.compile(r"^\s*<(?:cross-session-message|session_message)\b")
CROSS_SESSION_SPAN_RE = re.compile(
    r"<(cross-session-message|session_message)\b.*?</\1>"
    r"(?:\s*Replying is optional\. If a response is needed, call \w+ with this session_id\.)?", re.S)
# The harness's compaction summary: a user record carrying the earlier context the harness wrote
# itself, never a human turn (register entry 2026-09-13 03:53, the recurrence of 2026-10-02).
COMPACT_SUMMARY_RE = re.compile(r"^\s*This session is being continued from a previous "
                                r"conversation")


# An assistant record's tool calls carried into the extraction (register entry 2026-09-07): the
# call, never its result — the tool_result exclusion above stands, so the reflector reads what
# the head DID and not what came back. One line per call: the tool's name and the input field
# that says what it acted on, each line cut at TOOL_CALL_CHARS characters (set by the head as a
# bound on one line, unmeasured; a cut line ends with the marker so the cut is visible). A tool
# outside the table prints its name alone rather than a guessed field.
TOOL_CALL_CHARS = 300
TOOL_CALL_CUT = " …[cut]"
# The field naming what a call acted on, the first one present; the Skill, WebFetch and WebSearch
# fields joined the table with register entry 2026-10-02 06:19 (a reflector could not tell which
# skill the head loaded).
TOOL_ARG_KEYS = {"Bash": ("command",), "Read": ("file_path",), "Write": ("file_path",),
                 "Edit": ("file_path",), "Grep": ("pattern",), "Glob": ("pattern",),
                 "Skill": ("skill", "command", "name"), "WebFetch": ("url",),
                 "WebSearch": ("query",)}
# Tools whose listed fields are ALL shown, joined: a subagent call's type and its description.
TOOL_ALL_KEYS = {"Agent": ("subagent_type", "description"),
                 "Task": ("subagent_type", "description")}
# A line break inside one call's field, shown rather than joined with a space (register entry
# 2026-10-02 06:19: two statements of a command read as one).
NEWLINE_MARK = " ⏎ "


def call_value(value):
    """One input field on one line: each of its own line breaks shown as NEWLINE_MARK, the lines'
    outer white space stripped, empty lines dropped."""
    parts = [part.strip() for part in str(value).splitlines()]
    return NEWLINE_MARK.join(part for part in parts if part)


def tool_call_line(block, controls=None):
    """`- <tool>: <what it acted on>` for one tool_use block, or `- <tool>` where the tool is
    not in the tables above or its input carries none of that tool's fields. A line break inside
    a field shows as NEWLINE_MARK; the line is cut at TOOL_CALL_CHARS characters, the cut
    marked. `controls` (control_patterns, the blind reflector's) is matched on the whole line
    BEFORE the cut, so a control the cut would shorten past recognition is withheld whole
    (critic finding 5 of the review of 2026-10-11)."""
    name = str(block.get("name") or "tool")
    data = block.get("input") if isinstance(block.get("input"), dict) else {}
    value = ""
    if name in TOOL_ALL_KEYS:
        value = " · ".join(v for v in (call_value(data[k]) for k in TOOL_ALL_KEYS[name]
                                       if data.get(k) not in (None, "")) if v)
    else:
        for key in TOOL_ARG_KEYS.get(name, ()):
            if data.get(key) not in (None, ""):
                value = call_value(data[key])
                break
    line = "- %s: %s" % (name, value) if value else "- %s" % name
    if controls is not None and names_control(line, controls):
        return WITHHELD_LINE
    if len(line) > TOOL_CALL_CHARS:
        line = line[:TOOL_CALL_CHARS - len(TOOL_CALL_CUT)] + TOOL_CALL_CUT
    return line


def tool_call_lines(blocks, controls=None):
    """The tool-call lines of one assistant record, in the order the record holds them."""
    return [tool_call_line(b, controls) for b in blocks if b.get("type") == "tool_use"]


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
    pattern), is `notification`; a message relayed from another session is `cross_session` (a
    closed span of one beside the owner's own words is cut from them); a text of interrupt
    markers alone is `interrupt`, and a marker beside the owner's words is cut from them;
    anything else is `owner`, the text left, with `cut` True when a span, a marker or a reminder
    was cut from it."""
    left = NOTIFICATION_SPAN_RE.sub("", REMINDER_RE.sub("", text)).strip()
    if not left or any(pattern.match(left) for pattern in tuple(NOTIFICATION_RES) + tuple(extra)):
        return "notification", "", False
    if CROSS_SESSION_RE.match(left):
        rest = CROSS_SESSION_SPAN_RE.sub("", left).strip()
        if not rest or CROSS_SESSION_RE.match(rest):
            return "cross_session", "", False
        left = rest
    if INTERRUPT_RE.match(left) or not INTERRUPT_ANY_RE.sub("", left).strip():
        return "interrupt", "", False
    left = INTERRUPT_ANY_RE.sub("", left).strip()
    return "owner", left, left != text.strip()


def queued_text(lane, prompt):
    """The text a `queued_command` attachment carries in its `prompt`: a string as it is, or the
    text blocks of a content list joined by lane.py's own block reader; "" for anything else."""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        return turn_text(lane, [b for b in prompt if isinstance(b, dict)])
    if isinstance(prompt, dict):
        return turn_text(lane, [prompt])
    return ""


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


def extract_turns(lane, path, extra, withheld=None):
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
    harness's own shape is unverified here). Since 2026-10-10 (register entry 2026-09-13 03:53):
    a mid-turn owner message the harness queued as an `attachment` of type `queued_command` is a
    human turn (noted under `notes.queued_commands`); a compaction summary (isCompactSummary, or
    the summary's own opening) is `excluded.compaction` and a message relayed from another
    session (a `<cross-session-message>` or `<session_message>` span and nothing else) is
    `excluded.cross_session`, never the owner's; an interruption marker inside a text block is cut from the owner's text,
    and a text that is nothing but markers is `excluded.interrupt`. Notes are never buckets.
    `withheld`, the blind reflector's control texts (control_needles), is applied here, before
    any text is split into lines or cut (critic finding 5 of the review of 2026-10-11): each tool
    line is matched whole before its cut, and each turn's whole text across its line breaks
    (redact_turns); the lines withheld are counted under `notes.controls_redacted`."""
    controls = control_patterns(withheld) if withheld is not None else None
    turns = []
    counts = {"records": 0, "human_turns": 0, "assistant_turns": 0, "tool_call_turns": 0,
              "excluded": {"tool_result": 0, "meta": 0, "notification": 0, "interrupt": 0,
                           "replay": 0, "synthetic": 0, "unparseable": 0, "other": 0,
                           "compaction": 0, "cross_session": 0},
              "other_types": {},
              "notes": {"replay_trimmed": 0, "injections_cut": 0, "tool_result_with_text": 0,
                        "queued_commands": 0, "controls_redacted": 0}}
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
                if record.get("isCompactSummary") is True or COMPACT_SUMMARY_RE.match(text):
                    out["compaction"] += 1    # the harness's own summary, never the owner's words
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
                calls = tool_call_lines(blocks, controls)
                if controls is not None:
                    notes["controls_redacted"] += calls.count(WITHHELD_LINE)
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
            elif kind == "attachment" and isinstance(record.get("attachment"), dict) \
                    and record["attachment"].get("type") == "queued_command":
                # A message sent while a turn was running (register entry 2026-09-13 03:53, the
                # shape confirmed 2026-09-30): no user record carries it, so an extractor keyed on
                # user records dropped it. It is classified by its wrapper as a user record's text
                # is: a task notification or a relay from another session is not the owner's.
                text = queued_text(lane, record["attachment"].get("prompt")).strip()
                verdict, kept, cut = owner_text(text, extra) if text else ("other", "", False)
                if verdict == "other":
                    other("attachment: queued_command with no text")
                    continue
                if verdict != "owner":
                    out[verdict] += 1     # notification, cross_session or interrupt
                    continue
                notes["queued_commands"] += 1
                if cut:
                    notes["injections_cut"] += 1
                counts["human_turns"] += 1
                turns.append(("human", stamp, kept))
            elif kind == "attachment":
                att = record.get("attachment")
                other("attachment: %s" % (att.get("type") or "untyped" if isinstance(att, dict)
                                          else "no attachment object"))
            else:
                other(str(kind) if isinstance(kind, str) and kind else "(no type)")
    counts["extracted"] = counts["human_turns"] + counts["assistant_turns"]
    if withheld is not None:
        turns, spanned = redact_turns(turns, withheld)
        notes["controls_redacted"] += spanned
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
        "%d synthetic assistant record(s), %d unparseable line(s), %d record(s) of other "
        "types (%s), %d compaction summar%s and %d message(s) relayed from another session." % (
            out["tool_result"], out["meta"], out["notification"], out["interrupt"],
            out["replay"], out["synthetic"], out["unparseable"], out["other"],
            other_list(counts), out["compaction"], "y" if out["compaction"] == 1 else "ies",
            out["cross_session"]),
        "Replays: %d record(s) in which the harness re-sent a whole prior conversation as one "
        "user record (a turn marker at the opening and at least two in all, whatever the size) "
        "were trimmed to the text after their last `User:` marker, which is the turn the owner "
        "typed, and read as human turns (notes.replay_trimmed); a replay with no owner message "
        "left is dropped and counted under excluded.replay." % counts["notes"]["replay_trimmed"],
        "Mid-turn messages: %d user record(s) read as human turns after a task-notification "
        "span or a system reminder was cut from their text (notes.injections_cut), %d "
        "record(s) carrying a tool result beside owner text read as human turns "
        "(notes.tool_result_with_text), and %d message(s) the owner sent while a turn ran, "
        "carried by a `queued_command` attachment, read as human turns (notes.queued_commands); "
        "a record that is nothing but notifications stays excluded, and an interrupt marker is "
        "never a human turn. %d line(s) naming a registered control were withheld "
        "(notes.controls_redacted)." % (
            counts["notes"]["injections_cut"], counts["notes"]["tool_result_with_text"],
            counts["notes"]["queued_commands"], counts["notes"]["controls_redacted"]),
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
    frozen = getattr(a, "transcript", None)
    if frozen:
        # A frozen copy of the session's transcript (the self-cross remedy, register entry
        # 2026-09-06: a copy taken BEFORE the controls line was written cannot carry it).
        path = os.path.realpath(os.path.expanduser(frozen))
        if not os.path.isfile(path):
            die("--transcript %s is not a file: pass the frozen copy of session %s's transcript"
                % (frozen, sid))
    else:
        root = os.path.realpath(os.path.expanduser(a.projects_root)) if a.projects_root else None
        path = transcript_for(sid, root)
        if not os.path.isfile(path):
            die("no transcript for session %s at %s" % (sid, path))
    try:
        extra = [re.compile(pattern) for pattern in (a.notification_re or [])]
    except re.error as exc:
        die("--notification-re is not a regular expression: %s" % exc)
    return lane, sid, path, extra


def write_extraction(lane, sid, path, out_dir, extra, withheld=None):
    """turns.md and counts.json under out_dir, and the counts behind them — one writer for
    `extract-transcript` and `reflect-inputs`, so the two can never differ. `withheld` is the
    blind reflector's list of control texts (control_needles): every line naming one is withheld
    inside the extraction, before its texts are split or cut and before anything is written."""
    try:
        turns, counts = extract_turns(lane, path, extra, withheld)
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
            "synthetic %d, unparseable %d, other %d, compaction %d, cross_session %d" % (
                out["tool_result"], out["meta"], out["notification"], out["interrupt"],
                out["replay"], out["synthetic"], out["unparseable"], out["other"],
                out["compaction"], out["cross_session"]))


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

# Legacy: a record written before the reflection controls were retired may hold them as an observation
# whose phase starts `controls` (`handsoff.py ledger --phase controls-<LANE> …`); no run records one now.
# A lane event carries the brief it was given and any test device recorded for it. None of that is the P4
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


# The blind reflector's view of the head's transcript (critic finding 2 of the batch's design
# review: a control the spawner registered survived in the extraction through the Bash command
# that registered it). A control's text is withheld wherever it shows, and so is every line of
# the registration command itself, whose phase opens `controls` by convention.
CONTROL_MARK_RE = re.compile(r"--phase(?:=|\s+)['\"]?controls")
WITHHELD_LINE = "[withheld from the blind reflector: a line naming a registered control]"
NEEDLE_MIN = 8      # a control text shorter than this is too common a string to withhold by
NEEDLE_HEAD = 40    # a cut tool line keeps a long text's head: matched on its first 40 characters
REFLECTOR_CLASS = "reflector"   # the one lane class whose controls the reflector is blind to


def control_needles(events):
    """The texts the blind reflector must not read, from the record: the `what` and `note` of
    every observation whose phase starts CONTROL_PHASE, and the `controls_checked` and `plant`
    values (strings, or lists and mappings of them) of any event not known to be another class's,
    each at least NEEDLE_MIN characters. A lane's CONTROL+ check is a reading-list check of its
    own class, never a control the reflector is blind to (register entry 2026-10-23 03:48), so
    only a `reflector` lane's count; an event whose class cannot be found stays a needle, since
    this guard errs towards a lost line. A lane-resumed takes its lane's lane-open class."""
    classes = {str(ev["lane"]): ev["class"] for ev in events
               if ev.get("event") == "lane-open" and ev.get("lane") and ev.get("class")}
    found = []

    def add(value):
        if isinstance(value, str):
            text = one_line(value)
            if len(text) >= NEEDLE_MIN and text not in found:
                found.append(text)
        elif isinstance(value, (list, tuple)):
            for item in value:
                add(item)
        elif isinstance(value, dict):
            for item in value.values():
                add(item)
    for ev in events:
        phase = ev.get("phase")
        if ev.get("event") == "observation" and isinstance(phase, str) \
                and phase.startswith(CONTROL_PHASE):
            add(ev.get("what"))
            add(ev.get("note"))
        if (ev.get("class") or classes.get(str(ev.get("lane")))) in (None, "", REFLECTOR_CLASS):
            for key in ("controls_checked", "plant"):
                if key in ev:
                    add(ev[key])
    return found


def flat_text(text):
    """A text as the redaction matches it: each NEWLINE_MARK (a tool line's own line break) a
    space, every run of white space one space, the ends stripped."""
    return re.sub(r"\s+", " ", str(text).replace(NEWLINE_MARK.strip(), " ")).strip()


def path_like(text):
    """True for a flattened needle that reads as a file path, not prose."""
    return text.startswith(("/", "~")) or ("/" in text and not re.search(r"\s", text))


def control_patterns(needles):
    """[(whole, head)] for the control texts: each text flattened (flat_text), matched whole
    wherever it shows, and its first NEEDLE_HEAD characters where only its head was kept. A path
    matches whole alone: its head is the folder it shares with every path under the same root."""
    found = []
    for needle in needles or ():
        whole = flat_text(needle)
        head = whole if path_like(whole) else whole[:NEEDLE_HEAD]
        if whole and (whole, head) not in found:
            found.append((whole, head))
    return found


def names_control(text, controls):
    """True when the flattened text carries the controls registration command or any control's
    whole text or head (control_patterns)."""
    flat = flat_text(text)
    return bool(CONTROL_MARK_RE.search(flat)) or any(
        whole in flat or head in flat for whole, head in controls)


def redact_text(text, controls):
    """(text, lines withheld) for one turn's whole text: the lines are flattened and joined, so
    a control wrapped across a line break — or the registration command so wrapped — is matched
    across it, and every line a match touches is replaced by WITHHELD_LINE (critic finding 5 of
    the review of 2026-10-11: each line was matched alone, so a wrapped control survived). A
    line already withheld is not counted again."""
    lines = text.split("\n")
    flat, spans = "", []
    for line in lines:
        norm = flat_text(line)
        if not norm:
            spans.append(None)
            continue
        if flat:
            flat += " "
        spans.append((len(flat), len(flat) + len(norm)))
        flat += norm
    found = [(m.start(), m.end()) for m in CONTROL_MARK_RE.finditer(flat)]
    for whole, head in controls:
        for pattern in (whole, head):
            at = flat.find(pattern)
            while at >= 0:
                found.append((at, at + len(pattern)))
                at = flat.find(pattern, at + 1)
    hit = set()
    for start, end in found:
        for i, span in enumerate(spans):
            if span is not None and span[0] < end and start < span[1]:
                hit.add(i)
    if not hit:
        return text, 0
    counted = sum(1 for i in hit if lines[i] != WITHHELD_LINE)
    return "\n".join(WITHHELD_LINE if i in hit else line for i, line in enumerate(lines)), counted


def redact_turns(turns, needles):
    """(turns, lines withheld): every line of every turn that carries a control's text — whole,
    or its first NEEDLE_HEAD characters — or the controls registration command, each matched
    across the turn's line breaks (redact_text), replaced by WITHHELD_LINE; every other line,
    ordinary tool calls and unrelated prose included, kept."""
    controls = control_patterns(needles)
    out, withheld = [], 0
    for role, stamp, text in turns:
        text, n = redact_text(text, controls)
        withheld += n
        out.append((role, stamp, text))
    return out, withheld


def stage_reflect_dir(run):
    """The run's own reflection directory under its stage root, `<store>/stages/<run>/reflect`,
    as a real path: the one place inside the store a reflection input set may be written (the
    owner's provisional choice of 2026-10-10 on register entry 2026-09-17 21:08), since the stage
    root (G19) is where the run's held work lives and the reflector is granted this directory
    alone."""
    return os.path.realpath(os.path.join(store_root(), "stages", token(run, "run id"), "reflect"))


def refuse_out_inside(out_dir, what, root, carve=None):
    """A premise failure when --out sits in a directory the blind lane is not granted: the
    reflector is granted its own directory alone, and an input set written into the store or
    the projects root either needs a grant it must not have or is read as the run's own. `carve`
    is the one directory, and its subtree, allowed inside `root` (stage_reflect_dir), compared as
    real paths, so a sibling, another run's, a prefix lookalike or a symlink leading out of it is
    refused like any other path in the store."""
    real = os.path.realpath(os.path.expanduser(out_dir))
    if carve and (real == carve or real.startswith(carve + os.sep)):
        return
    for spelling in spellings(root):
        if real == spelling or real.startswith(spelling + os.sep):
            die("--out %s is inside the %s (%s): the reflector lane is granted its output "
                "directory alone, so the input set is written outside both — allowed: any "
                "directory outside the run store (%s) and the projects root (%s), such as one "
                "under /tmp%s" % (out_dir, what, spelling, store_root(), projects_root(),
                                 ", or the run's own %s" % carve if carve else ""))


def refuse_out_nonempty(out_dir):
    """A premise failure when --out already holds anything (register entry 2026-10-15 01:33 f):
    the input set goes by fixed names, so a second session into one directory would silently
    replace the first's extraction and leave a reflection with one of the run's heads."""
    try:
        held = sorted(os.listdir(out_dir))
    except FileNotFoundError:
        return
    except OSError as exc:
        die("cannot read --out %s: %s" % (out_dir, exc))
    if held:
        die("--out %s is not empty (%d entr%s, first %s): the input set goes by fixed names, so a "
            "second extraction here would replace the first; nothing written, name a fresh "
            "directory for each session" % (out_dir, len(held), "y" if len(held) == 1 else "ies",
                                            held[0]))


def cmd_reflect_inputs(a):
    """The P4 boundary reflection's whole input set in one directory (D36): the extraction, the
    waste table and a filtered copy of the run record, written before the event that records
    them so the copy never carries its own line. A record with no run-open is read in its
    attended form (register entry 2026-09-26 03:5x): --session's transcript, or the frozen copy
    --transcript names, with Step 2b rendered from the record's lane events; a record whose
    run-open line may be the torn one is refused rather than read as attended. --out may be the
    run's own <store>/stages/<run>/reflect (stage_reflect_dir, register entry 2026-09-17 21:08),
    and any extraction line that names a control a legacy record holds is withheld and counted."""
    path = record_path(a.run)
    events = read_existing_record(path)
    bad = read_record(path)[1]
    if is_plain_run(events) and bad:
        # The attended form takes a record with no run-open; a record whose run-open line may be
        # the torn one is not that (critic finding 2 of the batch's design review: malformed
        # history must not become an attended record because its run-open was skipped).
        die("the record %s carries no readable run-open and %d unparseable line(s): an attended "
            "record must read whole, since a torn run-open would pass for one; nothing written"
            % (path, bad))
    out_dir = os.path.realpath(os.path.expanduser(a.out))
    refuse_out_inside(out_dir, "run store", store_root(), carve=stage_reflect_dir(a.run))
    refuse_out_inside(out_dir, "projects root", projects_root())
    refuse_out_nonempty(out_dir)
    lane, sid, tpath, extra = extraction_inputs(a)
    needles = control_needles(events)
    if a.dry_run:
        try:
            turns, counts = extract_turns(lane, tpath, extra, needles)
        except OSError as exc:
            die("cannot read the transcript %s: %s" % (tpath, exc))
        _, _, wcounts = waste_table(events, a.run, path, bad,
                                    metered_heads(events, a.run, a.no_meter,
                                                  meter_overrides(a.meter_line)),
                                    meter_lanes=not a.no_meter)
        kept, dropped, stripped = blinded_events(events)
        say("reflect-inputs: dry run · %s%d turns (%d human, %d assistant) of %d records · %d "
            "tool-call turn(s) · %d line(s) naming a control withheld · %d waste row(s) · %d "
            "event(s) kept, %d controls observation(s) dropped, %d stripped of %s · would write "
            "turns.md, counts.json, waste-table.md and record-filtered.jsonl under %s and append "
            "one reflect-inputs event"
            % ("attended record (no run-open) · " if is_plain_run(events) else "",
               counts["extracted"], counts["human_turns"], counts["assistant_turns"],
               counts["records"], counts["tool_call_turns"], counts["notes"]["controls_redacted"],
               wcounts["rows"], len(kept), dropped, stripped, "/".join(BLINDED_KEYS), out_dir))
        return 0
    counts = write_extraction(lane, sid, tpath, out_dir, extra, withheld=needles)
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
               "controls_redacted": counts["notes"]["controls_redacted"],
               "excluded": sum(counts["excluded"].values()),
               "in_no_bucket": reconciliation(counts)[1]}
    shape = "attended" if is_plain_run(events) else "hands-off"
    append_record(path, event(a.run, "reflect-inputs", session=sid, out=out_dir,
                              counts=summary, shape=shape, transcript=tpath))
    say("reflect-inputs: %s%d turns (%d human, %d assistant) of %d records · %d tool-call "
        "turn(s) · %d line(s) naming a control withheld · %d waste row(s) · %d event(s) kept, %d "
        "controls observation(s) dropped, %d stripped of %s → %s"
        % ("attended record (no run-open) · " if shape == "attended" else "",
           summary["turns"], summary["human_turns"], summary["assistant_turns"],
           summary["records"], summary["tool_call_turns"], summary["controls_redacted"],
           summary["waste_rows"], summary["events_kept"], summary["controls_dropped"],
           summary["events_stripped"], "/".join(BLINDED_KEYS), out_dir))
    return 0


# ------------------------------------------------------------------------------ main -------

def main():
    ap = argparse.ArgumentParser(description="hands-off run primitives; see the module docstring")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, handoff=True):
        p.add_argument("--run", required=True, help="run id (the record's file stem)")
        p.add_argument("--record", default=None, help="explicit run record for notice/receipt operations")
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
                            "run-resume carry that list forward; a replacement that would lose "
                            "a read path is refused unless --replace")
        p.add_argument("--write", action="append", default=[], metavar="PATH",
                       help="a write grant (repeatable); the store and the state directory are "
                            "always present; given, it replaces the file's write list, and "
                            "absent, that list is carried forward: a rewrite that would lose a "
                            "path from either list is refused unless --replace")
        p.add_argument("--add-grant", action="append", default=[], metavar="PATH",
                       help="add a read grant to the run's current read list (repeatable; "
                            "grants and run-resume): every path the run holds is kept")
        p.add_argument("--add-write", action="append", default=[], metavar="PATH",
                       help="add a write grant to the run's current write list (repeatable; "
                            "grants and run-resume): every path the run holds is kept")
        p.add_argument("--replace", action="store_true",
                       help="the lists named with --grant/--write replace the run's even where "
                            "they lose a path (the delta on stderr): the explicit narrowing, and "
                            "the next call's baseline")
        p.add_argument("--max-successors", type=int, default=None, metavar="N",
                       help="the run's successor cap, written to the grants file and read by "
                            "the starter before AIMYTH_MAX_SUCCESSORS and the default %d; "
                            "absent, the file's own value is carried forward"
                            % MAX_SUCCESSORS_DEFAULT)
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
                       help="the run's decisions file (no default): content that no accepted "
                            "ack's digest covers holds the call with exit 6, as a newer AUTHOR "
                            "observation does; a named file that does not exist is refused")
        p.add_argument("--ack", default=None, metavar="LINE",
                       help="one line naming what was read: records an observation 'ack: LINE' "
                            "and the held call proceeds")
        p.add_argument("--ack-digest", default=None, metavar="SHA256",
                       help="required with --ack whenever --decisions-file is given: the whole "
                            "sha256 `decisions-read` printed for the file; missing, or not the "
                            "file's at the call, the call is held (exit 6) with the unread lines "
                            "and nothing is recorded")
        return p

    p = common(sub.add_parser("run-open", help="record the run's opening"), handoff=False)
    p.add_argument("--decisions-file", default=None, metavar="PATH",
                   help="the run's decisions file, bound on the record: gate, close and both "
                        "launchers read it from there; a named file that does not exist is refused")
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
    p.add_argument("--model", default=None,
                   help="the run's head model as a structured field on the run-open event: a "
                        "successor or a resume that names no --model inherits the newest such "
                        "field on the record (never parsed out of --head)")
    p.add_argument("--effort", default=None,
                   help="the run's head effort as a structured field: a successor or a resume "
                        "that names no --effort inherits the newest such field on the record")
    p.add_argument("--runbook", default=None,
                   help="the run's runbook, refused if it never names `handsoff.py boundary`; "
                        "absent, <store>/stages/<run>/RUNBOOK.md is read when it is there")
    grants(p)
    network_flag(p)

    p = common(sub.add_parser("run-resume", help="a later head records itself"), handoff=False)
    p.add_argument("--session", default="auto", help="session id, or auto (the last head-successor's)")
    p.add_argument("--head", required=True)
    p.add_argument("--detail", required=True)
    p.add_argument("--pid", type=int, default=None)
    p.add_argument("--model", default=None,
                   help="this head's model as a structured field, read as run-open's is: a head "
                        "no start of this script named has no other readable model")
    p.add_argument("--effort", default=None,
                   help="this head's effort as a structured field, read as run-open's is")
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
    p = common(sub.add_parser("notices", help="read pending notice versions or acknowledge a receipt"), handoff=False)
    p.add_argument("--pending", action="store_true")
    p.add_argument("--ack", action="store_true")
    p.add_argument("--notice-id")
    p.add_argument("--notice-version", type=int)
    p.add_argument("--notice-sha256")
    p.add_argument("--receipt")
    p.add_argument("--receipt-sha256")
    p.add_argument("--route", choices=("hands-off", "attended"))
    p.add_argument("--format", choices=("text", "json"), default="text")

    p = common(sub.add_parser("ledger", help="one findings-ledger row plus an observation, or "
                                             "--observation alone on any record"))
    # The four are required together (cmd_ledger refuses a partial set by name); they are not
    # argparse-required, because --observation is a complete call on its own.
    p.add_argument("--phase", default=None)
    p.add_argument("--what", default=None)
    p.add_argument("--evidence", default=None)
    p.add_argument("--routing", default=None)
    p.add_argument("--notice-id")
    p.add_argument("--notice-version", type=int)
    p.add_argument("--notice-sha256")
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

    p = common(sub.add_parser("handoff", help="rewrite named sections or bullets; --final records head-exit, "
                                              "refused (exit 10, the pack still written) with no successor left"))
    p.add_argument("--inflight", default=None)
    p.add_argument("--inflight-file", default=None)
    p.add_argument("--inflight-from-record", action="store_true",
                   help="derive '## In flight' from the run record (the last boundary's next, "
                        "the lanes open since it, the decisions since it) instead of taking a "
                        "pack: the pack-age guard's own rewrite, as a command")
    p.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="bullets: %s; sections: %s" % (", ".join(sorted(BULLETS)), ", ".join(sorted(SECTIONS))))
    p.add_argument("--set-file", action="append", metavar="KEY=PATH")
    p.add_argument("--final", action="store_true",
                   help="record head-exit; needs the next-task pack (D41); with no successor left "
                        "on the run's cap no head-exit is written and the call exits 10")
    p.add_argument("--band", default=None, help="the band edge crossed, unmetered, limit or error (default: measured)")
    p.add_argument("--pid", type=int, default=None)
    p.add_argument("--meter-line", default=None, help="a billed line in hand for head-exit's spent_usd (skips the meter)")

    def head_options(p):
        p.add_argument("--model", default=None,
                       help="the head's model; absent, the newest head start's structured model "
                            "on the record, and with none a start is refused (a hands-off head "
                            "never starts on the harness default)")
        p.add_argument("--model-src", default=None, help=argparse.SUPPRESS)
        p.add_argument("--effort", default=None,
                       help="effort for the head; absent, the newest head start's effort on the "
                            "record, and with none %s (the owner's head rule)" % HEAD_EFFORT_DEFAULT)
        p.add_argument("--effort-src", default=None, help=argparse.SUPPRESS)
        p.add_argument("--config-dir", default=None, help="optional; unused by default (a run stays on one login, D28)")
        p.add_argument("--harness-bin", default=HARNESS, help="the harness binary (a suite substitutes a stub)")
        return p

    p = common(sub.add_parser("successor", help="record head-exit, start the detached starter (which supervises); returns at once; "
                                                "refused (exit 10) with no successor left; names the head's background tasks"))
    head_options(p)
    p.add_argument("--budget-usd", type=float, default=None, help="default: the envelope's remainder (N5)")
    p.add_argument("--predecessor-pid", type=int, default=None)
    p.add_argument("--seed-pid", action="store_true",
                   help="for an attended head handing over: the starter waits on a seed process "
                        "that exits %d s after this call, not on the head's own process, which "
                        "does not exit at the end of a reply; refused beside --predecessor-pid"
                        % SEED_PID_S)
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
    p.add_argument("--config-dir", default=None, help="optional; unused by default (a run stays on one login, D28)")
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
                        "projects root, which the lane is not granted, except the run's own "
                        "<store>/stages/<run>/reflect/ (the stage root's reflection directory)")
    p.add_argument("--projects-root", default=None, metavar="P",
                   help="default: AIMYTH_PROJECTS_DIR, else ~/.claude/projects")
    p.add_argument("--transcript", default=None, metavar="FILE",
                   help="a frozen copy of the session's transcript, read instead of the live "
                        "one: for a self-cross reflection, a copy taken before the controls "
                        "were registered")
    p.add_argument("--notification-re", action="append", default=[], metavar="REGEX",
                   help="an extra injected-user-record marker, matched at the start (repeatable)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the counts and what would be written; write and record nothing")
    window_meter(p)

    p = two_heads(common(sub.add_parser(
        "item-done", help="an explicit completion record for each item named, with no meter: what "
                          "the console reads as done, for items worked side by side"), handoff=False))
    p.add_argument("items", nargs="+", metavar="ITEM", help="an item, as the pack or a gate names it")
    p.add_argument("--note", default="", help="one line on what finished it")

    p = common(sub.add_parser("close", help="final meter, run-close, commit and push on grant"))
    p.add_argument("--commit", default=None, metavar="MSG")
    p.add_argument("--push", action="store_true")
    p.add_argument("--items", default=None,
                   help="required: the record's own verdict on the run's items (a close without "
                        "it is refused, exit 2; a dry run reads it as unstated)")
    p.add_argument("--register", default=None, help="absent: written unstated, with a note")
    p.add_argument("--log", default=None, help="absent: written unstated, with a note")
    p.add_argument("--lint", default=None, help="absent: written unstated, with a note")
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

    p = sub.add_parser("decisions-read", help="the decisions file's lines the run has not "
                       "acknowledged, then `digest: <sha256>`, the value an ack's --ack-digest "
                       "repeats (IDEAS 171 (b); reads, writes nothing)")
    p.add_argument("--run", required=True, help="run id (the record's file stem)")
    p.add_argument("--record", default=None, help="explicit run record (default: the run's)")
    p.add_argument("--decisions-file", default=None, metavar="PATH",
                   help="the run's decisions file (default: the one its record binds)")

    two_heads(decisions_channel(common(sub.add_parser(
        "decisions-ack", help="the acknowledgement between gates, which a held spawn asks for: "
                              "--ack and, with a decisions file, --ack-digest"), handoff=False)))

    p = common(sub.add_parser("disarm", help="after the run's close: remove the arming marker of "
                                             "every head session the run names whose pointer "
                                             "still names this run (close does it too; this is "
                                             "the retry); exit 1 when any is unresolved or "
                                             "failed"),
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
    p.add_argument("--lanes", default=None, metavar="ID[,ID...]",
                   help="the planned first batch of helpers: after the head starts, the check "
                        "waits inside the same --wait deadline until every one has opened and "
                        "shows activity since its open (a record or transcript event) or has "
                        "closed completed, then prints STARTED CLEAN (exit 0); a helper that "
                        "failed, or any not progressing at the deadline, is NOT CLEAN (exit 1), "
                        "each helper's state named; an empty or repeated list is refused (exit "
                        "2). A first batch starts minutes after its head: pass a --wait that "
                        "covers it")

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
                "item-done": cmd_item_done,
                "notices": cmd_notices, "ledger": cmd_ledger, "gate": cmd_gate, "handoff": cmd_handoff, "expect": cmd_expect,
                "successor": cmd_successor, "_starter": cmd_starter,
                "supervise": cmd_supervise, "_supervise": cmd_supervise_internal,
                "resume-head": cmd_resume_head, "_resume-head": cmd_resume_head_internal,
                "heartbeat": cmd_heartbeat, "grants": cmd_grants,
                "wait-reset": cmd_wait_reset, "close": cmd_close,
                "waste-table": cmd_waste_table,
                "extract-transcript": cmd_extract_transcript,
                "reflect-inputs": cmd_reflect_inputs, "watch": cmd_watch,
                "raise-envelope": cmd_raise_envelope, "decision": cmd_decision,
                "decisions-read": cmd_decisions_read, "decisions-ack": cmd_decisions_ack,
                "disarm": cmd_disarm,
                "run-is-closed": cmd_run_is_closed, "run-spend": cmd_run_spend,
                "launch-check": cmd_launch_check, "open-console": cmd_open_console,
                "hold": cmd_hold, "release": cmd_release,
                "hold-verdict": cmd_hold_verdict}
    sys.exit(handlers[a.cmd](a) or 0)


if __name__ == "__main__":
    main()
