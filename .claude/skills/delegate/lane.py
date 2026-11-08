#!/usr/bin/env python3
"""lane.py — spawn a thin headless lane from a lane home, with its context, tools, model and
effort set per call, and its spawn record written before the process starts.

An in-session lane inherits the whole contract, the whole tool set and the skills listing. A
thin lane is a headless session started from a LANE HOME — a directory outside the vault
holding the lane-side settings, the fence hook and the contract slices, and no CLAUDE.md —
whose context is its brief plus exactly the directories the head grants.

    lane.py init   [--home DIR]                    build or refresh the base lane home
    lane.py spawn  --run ID --lane ID --class CLASS --brief FILE --expect-usd USD --reason "(a) WHY" [options]
    lane.py watch  --run ID --lane ID [--silence-s N] [--max-wait-s N]
    lane.py wait   --run ID --lane ID [--silence-s N]
    lane.py resume --run ID --lane ID --brief FILE [--detach [--no-wait]]   (the spawn's reason is carried forward)
    lane.py resume --run ID --lane ID --beat                                (the held-lane beat: no brief, no report)

The commands and what they guarantee
------------------------------------
`init` is idempotent. It writes the lane home's settings (one PreToolUse hook on Bash running
the fence, no other hooks, no MCP servers), a copy of the fence, and the contract slices the
thin classes read by path instead of inheriting: `contract/schema-s4.md` (the schema section
of the vault contract) and `contract/confidence-rubric.md` (the grading guide page, body
only). Each is written to a temporary file and renamed into place, and regenerated only when
its source's hash changes, so two concurrent spawns can never read a half-written slice. It
also lists the skill slices found under the delegate skill's `lane-home-src/` (each spawn reads
them there; init installs no `skills/` link and removes one an earlier init left), and prints what
it created, kept or regenerated.

A row's literal grants name the live vault, so a fixture-bound lane takes `--grants-only`:
the literals are dropped (and recorded), the row's per-call slots are still filled from the
call, and `--grant`/`--write` become the lane's whole scope — plus the lane home, and /tmp and
/dev, which the fence sanctions for every lane's shell (a lane without Bash does not reach them).
A lane continuing another's work takes `--grants-from <lane>`: that lane's read and write grants,
from its lane-open in this run's record, join the call's, and lane-open names the copy.

`spawn` resolves the class row from `routing.json` (schema 2) under the active throttle,
builds the class's THIN definition from the vault's `.claude/agents/<class>.md` — the same
body, frontmatter rewritten to the row's tools and skills, with no `effort:` field, since the
definition's effort is ignored on the headless path and `--effort` is what
applies — and passes it INLINE with `--agents`, so parallel spawns never share a definition
file. It writes the `lane-open` record line BEFORE starting the process, a `lane-spawned`
line carrying the session id once it has started (the meter matches headless lanes by that
id), and a `lane-closed` line carrying the metered figures at the end, with the class's
soft-cap check (`soft_usd`, `soft_src`, `soft_exceeded`: the soft line and the hard cap below).

`--reason` is required at the spawn and names the instrument-rule letter CLAUDE.md section 2.2
asks for; omitted, whitespace-only and letterless take one refusal (exit 2), before any record
line. `resume` needs no reason of its own: the lane's reason has not changed, so `lane-resumed`
carries the reason its `lane-open` recorded, and `--reason` there is an override for a record
whose reason carries no letter (one written before the check) and is refused against a record
that carries one.

The per-call pick (owner ruling 2026-09-07 17:0x; built 2026-09-08; the tier rules of 2026-09-22
19:0x): under the throttle `auto` — the default preset, and the fallback for a missing Settings
line — the row's marked defaults are ANCHORS, and the head picks `--model` and `--effort` per call
within the row's options. Which model serves which work is the routing table's (`routing.json`, with
the delegate skill §2): opus 5.5 the anchor on every Claude seat, sonnet per call under that
section's test (owner ruling 2026-11-01), and fable only on the owner's word
(a by-name `--model fable` is recorded as outside the options, never refused); the `top` and `cheap`
presets resolve the model to opus through the table's `preset_model` (owner rulings 2026-09-22 and
2026-09-29). Effort on opus: xhigh the anchor, max only after a failed
xhigh or for a genuinely hard or very extensive task. Every close carries `fallback`, read from the
result's modelUsage ids against the alias map in prices.json (`models`): a second non-helper id,
or one other than the alias's recorded resolution, is a transparent safeguard fallback (Opus 5.5
re-routes some tasks with no refusal to see); the wrapper then moves the task's remaining work to
Astra itself — a derived brief, one detached `codex-lane.py spawn` of `<lane>-astra` with the same
class, write scope, effort and regime, a `lane-swapped` line — and the summary and stderr say
FALLBACK with the new lane; `--no-swap` opts out; a pass that changed its write folders starts no
successor and waits for the head, since nothing it produced is kept (`a3_fallback_writes`), and no
display shows a confirmed fallback's report (`void_report_line`); the run console alerts on the close and the
swap, and the head tells the owner once (owner ruling 2026-09-29: the owner is told of every refused
or re-routed task, which falls back to GPT-6 Astra at the same effort rung). The
`lane-open` line records where each axis came from: `model_src`/`effort_src` read `anchor` (no
override, or one equal to the anchor), `auto: <text>` (a departure, carrying `--choice-reason`'s
text), `throttle <name>` (a hand-set preset's own value) or `explicit` (a departure from a
hand-set preset's value, which needs no reason), and `choice_reason` carries the text or null.
Under `auto` a departure with no `--choice-reason` is refused exactly as a missing `--reason` is
(exit 2, before any record line, `--dry-run` included). `--choice-reason` says why this model and
effort for this task; `--reason` says why a lane at all, stays required, and the two are never
merged. `resume` makes no new pick: it copies the three fields from the lane's latest
`lane-open`, `unrecorded` and null for a record from before them.

The `lane-open` line's `mode` is the run's delegation regime, `single` or `multi`, with its
source in `mode_src` (`owner`: the Settings line, or the owner's word for this run; `head`:
the head's per-run resolution under delegation `auto`) and where it came from in
`mode_from`. `--delegation` with `--delegation-src` sets them; without the flags the Settings
line `- **delegation**:` (the pre-rename `- **mode**:` line as a fallback) supplies a
`single`/`multi` word with source `owner`, and `auto`, an absent line or any other value is
a premise failure: the head resolves the run first (`role-style-anchor.py set-delegation`)
and passes the resolution, so a record never carries a regime nobody chose.

Grants (hands-off D17, D18)
---------------------------
`--grant` and `--write` accept a FILE as well as a directory. The fence sees the path itself
(`LLM_WIKI_LANE_GRANTS` / `LLM_WIKI_LANE_WRITES`, real paths), while the file tools, which
`--add-dir` can only widen by directory, get the file's parent. Every `--add-dir` value is
passed in both spellings when the path as given and its real path differ (a symlinked store,
a symlinked fixture), since the harness compares the spelling a tool call uses. Each spawn
gets its own input directory `<store>/<run>-in-<lane>/`, created by the wrapper with the brief
copied into it, granted read; the store itself is granted only when a call names it, so a
blind lane never sees sibling reports or the record. `--grant-vault-root` grants the vault
root itself (a lane may then read root files such as MANUAL.md without a copy). A per-spawn
settings file `<store>/<run>-settings-<lane>.json` carries the home's hooks plus
`permissions.allow` rules `Edit(//path)` / `Write(//path)` for every write grant, and the rule
`WebSearch` where the lane gets that tool (below, "Tools beyond the class row"); whether
that list beats the harness's sensitive-path guard under `.claude/` is recorded beside
`settings_for` below. A FILE grant whose parent holds anything else earns one stderr warning
naming that parent, since the grant reaches the whole directory (register
2026-09-08, the judge-brief entry); a warning, never a refusal.

Controls and declared inputs (D19; the grammar beside `parse_declarations`). A brief declares
what the wrapper checks before the spawn on lines of one grammar: a marker standing unquoted on a
line declares, at its start, after a bullet or a label (`VERIFICATION: CONTROL+: …`) or after
prose, one per line; a declaration with nothing after its marker refuses. A marker in a fenced
code block or a block quote declares nothing, and so does one quoted in prose unless the quoted
form names files that exist (then it is read as the declaration it spells out); any other quoted
form is a mention, said on stderr. Every refusal exits 2 before any record line, in the caller
before any detach. The read grants a declaration is checked against are what the lane's tools
reach (`lane_read_roots`): its grants, its input directory and the lane home, plus /tmp and /dev
only for a lane holding Bash, since those are the fence's shell grant and the file tools never
reach them (review CR-B4L finding 4).
  - `CONTROL+: <phrase> in <file>`: a positive control the lane must be able to hit — the phrase
    as a fixed string in that file (a relative file resolves against the vault), which must lie
    inside the lane's read grants. A zero match, a missing file, a file outside the grants or a
    malformed line refuses; the matches are recorded as `controls_checked`. The file
    `<<REPORT>>` names this pass's own report: that control is recorded as pending
    (`controls_pending`) and checked at the close against this pass's fresh report text alone
    (`controls_deferred`, each `checked`, `failed` or `unverified`; the summary line says so; a
    process that never starts closes them unverified, on the record and stderr).
  - `READ+: <path>`: a declared input. It must exist, be readable and lie inside the read grants
    (its real path, on a component boundary); a regular file of zero bytes refuses with its
    path, and a directory must hold a file with content. Recorded as `inputs_checked`.
  - `RUBRIC+: <rubric> in <tree>`: every relative folder the rubric names must exist under the
    tree and hold a file with content; the rubric and the tree lie inside the read grants.
  - `WEB+: <what>`: declared web work. A declaration whose text opens with `search:` needs search
    alone, and is admitted where the lane gets WebSearch (its class definition allows it and its
    tool list holds it, below); any other declaration needs page fetches, which a Claude lane cannot
    do (nothing admits WebFetch, and no shell network is granted), so the spawn is refused and
    pointed to codex-lane.py with `--search`, as is a search declaration on a lane without
    WebSearch. A resume admits a search declaration where its lane-open's tools and settings
    carry WebSearch.
`<<STAGED_COPY>>` names a staged copy, which this wrapper never makes: a declaration using it
refuses here (codex-lane.py resolves it after staging).

Tools beyond the class row. `--tools` sets the tool list, never a permission, and with prompts off
a listed tool no rule admits is refused at every call (register 2026-09-29 21:08). A tool outside
the row is admitted only where something admits it — the read tools need no rule, Bash has the
fence's explicit allow, Edit and Write the settings' rules on a write grant, WebSearch the
settings' rule where the class definition allows it — and any other refuses the spawn (exit 2,
before any record line), WebFetch, and WebSearch on a class that does not allow it, pointed to
codex-lane.py `--search`. WebSearch (2026-10-10) is a server-side tool and needs no client
network: a class whose definition allows it gets it, joined to the row's tools when the call
names no `--tools` of its own and admitted by a `WebSearch` rule in the per-spawn settings
(`settings_for`). A definition that blocks it never gets it. WebFetch stays withheld, and the
fence's network rule stands. The other way round, a tool the class definition allows that the lane
will not have — off the tool list, or on it with no per-spawn permission to admit it — is never
dropped silently: the spawn prints one `tools withheld:` line naming them and the web path, and
`lane-open` records them as `tools_withheld`. WebFetch is always among them where the definition
allows it, and WebSearch is among them only where an explicit `--tools` leaves it out. Nothing is
refused, and the grant is unchanged. A
definition without a `tools:` allowlist allows what its `disallowedTools:` leaves, read over Edit,
Write, WebSearch and WebFetch (`definition_allows`). A definition with no frontmatter allows them
all; one whose frontmatter cannot be read (a `---` block that never closes, an opener behind a
byte-order mark) refuses the spawn and the resume (exit 2, before any record line or process),
since read as absent its restrictions would vanish (review CR-B4L finding 3).

Brief paths and closed runs. A brief line carrying a doubled root refuses the spawn or the resume
(exit 2, the line quoted, before any record line; register 2026-09-09 19:03): a root path (led by
`~`, a `$VARIABLE`, a hidden directory name, or an absolute path of the home, temporary or system
families) that embeds a second absolute path, whatever its lead (`embedded_root` says what counts),
or the vault root twice inside one path token. A spawn onto a closed run, whose record holds a
`run-close` with no later `run-open` or `run-resume` whatever else follows it, prints one warning
naming the close and proceeds (register 2026-09-03, two head processes on one session id). Both run
in the caller before any detach, as every other argument, grant and cost check does (`--detach`, below).

The spawn hold (register 2026-10-14 01:33 b). A spawn, or a resume with a brief, reads the run's
decisions channel in the caller before any detach, through handsoff.py's `decisions_spawn_state`:
content no accepted ack covers, an unread `AUTHOR` observation, or a head that has acknowledged
nothing itself holds the call. Under `enforce` that exits 7 and a state that cannot be read exits 2,
each with nothing started and no record line; under `trial` (`DECISIONS_HOLD_MODE`) the same text
prints, one observation per digest and head is written and the call goes on. A dry run prints and
writes nothing. A plain lane run, a closed run, a no-work beat and a recorded movement are not held.

The watchdog (D20)
------------------
While it waits, the wrapper checks every `--poll-s` seconds (default 30) the NEWER of the lane
transcript's mtime and the lane's progress file's mtime (`/tmp/<run>-<lane>.progress`, which a
lane appends to inside long calls; the path also reaches the lane as
`LLM_WIKI_LANE_PROGRESS`). Silence past `--silence-s` is a stall, never reasoning: the
threshold is per call, because the transcript is silent for the whole of any tool call, so a
brief that runs a long suite passes a larger value; `--silence-s 0` disables the watch; with no
`--silence-s` a spawn takes its class default and a resume keeps its lane-open's threshold (the
numbers below). No transcript within `--no-transcript-s` (default 120) of the spawn is a stall of
reason `no transcript`. Action: SIGTERM to the process group, the kill grace, SIGKILL; a `stall`
event; `exit_class` `stall`; exit 5.

Keeping the host awake (owner decision of 2026-10-09; register 2026-10-08 21:21). The silence
watch reads the wall clock, so a host that sleeps while a lane runs has the sleep recorded as a
stall. Beside every lane process it starts — a spawn's or a resume's, in the foreground or inside
a detached worker — the wrapper therefore starts `/usr/bin/caffeinate -i -w <lane pid>`, which
holds an idle-sleep assertion and exits by itself when that process exits (`start_awake`). It runs
in a session of its own with its standard streams on /dev/null and inherits no other descriptor,
so it never holds the wrapper's input or output or the lane's input pipe, and it is never waited
on. A `lane-awake` line follows `lane-spawned` (or `lane-respawned`): `awake` reads `started`
with `caffeinate_pid`, or `skipped` when the binary is absent (another platform) or does not
start, with the why in `note`; `watched_pid` is the lane process. A skip never fails the spawn,
and a caffeinate that dies early changes nothing about the lane. `-i` prevents idle sleep only: a
closed lid or a sleep asked for by hand still suspends the host. `AIMYTH_CAFFEINATE` names a
stand-in binary by path, for a suite. The held-lane beat (below) starts one beside its model
process too, under the same rules; its record contract is one `hold-beat` line, so the state
rides on that line as added fields (`awake`, `caffeinate_pid`, `watched_pid`, and `note` when
skipped; `beat_awake_fields`) and no `lane-awake` line is written.

Keeping a helper's signals inside its box (owner decision of 2026-11-04; register 2026-11-04
14:03: one helper's malformed `pkill` stopped a whole run). Every process a helper starts, by any
route, may signal only processes inside that helper's own box, because the wrapper starts the lane
process through `/usr/bin/sandbox-exec -p BOX_PROFILE` (`boxed`, called by the spawn's and resume's
`run_lane` and by the beat). `sandbox-exec` replaces itself with the command, so the recorded pid
and birth time stay the helper's. The rule binds the sender's own signal call: work handed to a
service outside the box is beyond it, and a helper's fixture left by an earlier pass is outside the
new box, so the lead stops it. `ps` and `top` run outside the box by a narrow exception, since
neither can signal. The sandbox refuses any other setuid or setgid program (`sudo`, `crontab`, `at`,
`atq`, `quota`) with exit 71. A helper's shell `kill -0` on an outside process reads "not permitted",
which a shell test reads as dead, though this wrapper, handsoff.py and watch.py read Python's
PermissionError as alive. The configuration hash stays the unboxed command's: `boxed` never reads or
writes `ctx["command"]`, it returns a new list. Before each start it checks its premise with
`/bin/sh -c 'kill -0 $PPID'` inside the box (a timeout of BOX_PROBE_S): refused means the rule holds
and `box` reads `on`; allowed means this wrapper is already inside a box of the same profile, whose
helpers can reach each other, and `box` reads `on: inside a box already`; anything else (exit 71, a
missing binary, a timeout) runs the helper unboxed, and `box` reads `off: <reason>`. A command not on
the child's PATH also starts unboxed, so that `Popen` raises as it always has and the close records
`spawn-failed`. A failure of this check never stops a helper. `lane-spawned`, `lane-respawned`, the
close and the beat's `hold-beat` line carry `box`. Any value but `on` also shows in the close summary,
which the lead reads, and on stderr. `AIMYTH_LANE_BOX` names a stand-in binary by path, for a suite;
`off` leaves helpers unboxed, recorded. Codex helpers take no wrapper, since Codex runs each of their
commands inside its own sandbox and a second profile inside would be refused.

`watch` attaches the same loop to a lane already running (pid, wrapper pid and session id
from the record). It never kills a live wrapper's lane for silence unless `--silence-s` was
passed to `watch` itself. When the recorded wrapper is gone and no `lane-closed` exists, it
waits for the lane process (bounded by the recorded deadline) and then closes the lane from
its transcript: `exit_class: watch-closed`, `cost_src: transcript-estimate`, `denials:
unknown`. It returns `still-running` (exit 8) after `--max-wait-s` so a head can re-issue it
as a bounded blocking call. A watch that finds the lane already closed waits up to `--appear-s`
for a newer `lane-resumed` before it refuses: a resume whose `--detach --no-wait` returned
unconfirmed (exit 4) can write that line after it returns (an acknowledged one wrote it before
returning), and the close that counts is the one after the latest open or resume, never the
previous call's (the rule codex-lane.py's watch shares).

For a background wait, `wait` runs this same loop without a time bound, returning only on
the latest pass's close or a named watcher error. It prints the same output and returns the
same exit code as `watch`, including its already-closed and orphan handling. A foreground
check uses `watch`, whose default bound remains 570 s (the derivation is below).

`kill --run --lane --reason` deliberately stops a lane and records its close so readers can
distinguish a stopped lane from a running one. It signals the recorded wrapper first (so the wrapper cannot race it to
a close of its own) and then the lane process, SIGTERM and then SIGKILL after the kill grace
for each, and writes the close the wrapper never wrote: `exit_class: killed`, the reason, and
the cost estimated from the transcript the way `watch-closed` estimates it. A pid already gone
is not a failure — the missing close is the whole point — and one line says so. An unknown
lane, a lane that never spawned and a lane already closed each refuse with exit 2 and write
nothing. `watch` stays the interim path for a lane whose wrapper has simply gone.

`--detach` is a double fork: a worker process (its own session, so it survives the caller's
exit) runs the lane and writes every record line, and the foreground stays as the watch over
it, exiting with the worker's exit code once `lane-closed` appears. `resume` takes the same two
flags (register 2026-09-10 15:22). Every argument, grant and cost check of spawn and resume runs in
the caller before the worker starts, so a refused call exits 2 in the caller's terminal with no
worker started (register 2026-09-29 16:57); the caller hands its composed cost cap to the worker,
which repeats every other check. `--detach --no-wait` then waits, bounded by `--ack-wait-s`
(default 60 s, the derivation below), for the worker's acknowledgement of THIS call: its own
`lane-open` for a spawn or its own `lane-resumed` for a resume, each matched on the worker's pid as
`wrapper_pid` after the record's length at the detach, never an older line. The pid, not the
session id, is the key: a caller may name its own `--session-id`, and two calls on one lane can
share it, while only this call's worker carries its pid. Four outcomes:
acknowledged, it prints `detached pid N session S` and exits 0; the worker exits before
acknowledging, it prints the worker's log tail and exits non-zero (the worker's own code, else 3);
the worker lives but no acknowledgement arrives within the bound, or the record cannot be read, it
prints `detached pid N, unconfirmed after S s` and exits 4, leaving the worker running, which may
still start the lane: nothing re-spawns it until that worker has exited with no line of this call
on the record; a refused argument or grant exits 2 before any worker starts. The caller names its
worker on stderr the moment it starts (`worker pid N started (log L)`), so a caller stopped before
its outcome line still says which process may yet start the lane. `lane-open`, `lane-resumed` and
`lane-spawned` carry `wrapper_pid`, the process that will write the close. The caller, not the worker, opens the run's console, before
the worker starts, and hands the worker `--viewer none` (appended, so it wins over any `--viewer` the command carried).
(register 2026-09-09 11:21; the opener itself is handsoff.py's).

A second pass on a helper's work goes to a fresh helper with a compact hand-off: the earlier
report's path, the findings to fold, the held files and what must not change. Use `resume`
only for a long write cut short by a usage limit, whose work is on disk and checked, or for
the multi-expert panel's round 2. These are recommendations; the resume checks are unchanged.

`resume` (D25) re-enters a finished lane's session (`--resume <session id>`, the continuation
brief on standard input) with the model, effort, tools, grants and settings its `lane-open`
recorded, refusing when the lane's last call (`lane-closed.ts`) is older than the resume
window, since the cache has lapsed by then and a fresh spawn costs less. It records
`lane-resumed` BEFORE the process starts, as a spawn records `lane-open`, then `lane-respawned`
carrying the process's `pid` and `wrapper_pid`, and a new `lane-closed` (2026-09-13: the pid moved
from `lane-resumed` to `lane-respawned`, the pair codex-lane.py already writes).
D29: after a `limit` close the window is WAIVED — one cold re-read is the accepted token loss —
and `lane-resumed` carries `after_limit` and `age_s`; a lane whose transcript cannot be found is
re-spawned, never resumed (exit 2). The window's reference is the lane's last call: its
`lane-closed.ts`, or a later successful `hold-beat` (below), whichever is later, and
`lane-resumed.age_src` names which.

`resume --beat` (the held-lane beat, 2026-09-17) is the no-work resume handsoff.py's
supervisor issues for a held lane: the same command line as a resume — the lane-open's model,
effort, tools, grants, settings and appended file, `--resume <session id>` in place of the
spawn's `--session-id` — with the fixed line BEAT_PROMPT on standard input in place of a brief.
It writes no report, no `-pass<n>` file and no `lane-resumed` or `lane-closed` line; its one
record line is `hold-beat`, carrying the call's usage from the harness result (`modelUsage`,
this invocation's own calls: input, output, cache read and cache write tokens), the cost, the
exit class, `config_sha256` and the keep-awake state ("Keeping the host awake", above). That
hash is the resolved command line's configuration — every
token but the session flag pair and the two wrapper-side bounds (`--max-budget-usd`,
`--max-turns`), plus the bytes of the appended system-prompt file and the settings file — and is
recorded on `lane-open` and `lane-resumed` too; a beat whose hash differs from the lane-open's
is refused before any process starts (`config_match false`), since a changed configuration is
a rewrite, not a beat. A beat also refuses, exit 2 and nothing written: a brief beside `--beat`,
a lane still running, a close outside BEAT_EXITS (a limit or budget close is the head's own
resume decision), a lapsed window, a missing transcript. The beat runs in the foreground under
BEAT_TIMEOUT_S with the spawn's own cap, never `--detach`. A beat that fails — a non-zero exit,
a limit, a refusal — is recorded with `ok false` and its exit class; the supervisor never
retries it within its tick.
While a beat or a real resume runs, it holds an ADVISORY LOCK on `<run>-<lane>-beat.pid.lock`
beside the record (`fcntl.flock`, LOCK_EX|LOCK_NB, taken for the length of the call), and any
other entry to that lane's session — a real resume, a second beat, through either wrapper — is
refused while that lock is held (critic F4, 2026-09-17: the beat's own record line lands only
when the call returns, so nothing else told a resume the session was busy). The lock, not the
existence of a file, is the claim (critic finding 2 of review, 2026-09-18): it is taken
atomically before the file has any content, so no second entrant can read an empty claim as
stale; the kernel releases it when the holder dies, so a crashed call wedges no lane shut and no
reader removes anything; and a real resume claims it immediately before it writes or starts
anything, so two calls arriving in either order cannot both pass. A call that cannot claim the
session refuses and starts nothing, a body it cannot write included. The locked file's body
(`<pid> <kind> <timestamp>`) is the diagnostic a refusal quotes, never the claim.
`advise` reads the same reference as `resume` — the close, or a later successful beat — and
names it on its line. For a retry it points to the delegate skill's rule by name. A `stall`,
`deadline`, `budget` or `max-turns` close follows "Progress-judged retries" (2026-10-11), and a
budget close may instead resume with a raised cap. Other failures (`error`, `spawn-failed`,
`killed`) keep the skill's one fresh re-spawn, and a second failure returns the step to the head.
After a `budget` close — the CLI's own `--max-budget-usd` stop, `error_max_budget_usd` — the
recorded cap is NOT re-used: resume refuses (exit 2, no record line) unless `--budget-usd` is
given and is above the cap of the pass that stopped (`hard_usd`, or legacy `budget_usd`):
the latest `lane-resumed` before that close, else `lane-open` (critic F2, 2026-09-15). Either the CLI's running total survives the resume and the same cap kills
the lane on its first turn, or it does not and the lane silently gets a second full helping of it;
neither is a resume. Raised, `hard_src` reads `explicit --budget-usd (raised over a budget close
from $<cap>)` and `lane-resumed` carries `after_budget: true` beside `after_limit`. Its premise
cases, each exit 2: a `budget` close whose pass start carries neither `hard_usd` nor `budget_usd`
(a torn or pre-class-caps record) refuses because the cap it stopped at is unknown; a
`--budget-usd` equal to the recorded cap refuses, since equal is not above; a non-numeric recorded
cap refuses as a broken premise. Every other close class resumes from its recorded estimate, and there
`--budget-usd` is raise-only against the cap the resume composed (owner ruling, 2026-09-07):
at or below it the composed cap is kept, `hard_src` says so and the resume prints one line.

The report (D8): stdout carries the complete report by default. An explicit preview request
uses `--report-words N` and names the full persisted text in its pointer.
The record carries `report_words` and `report_cut`. Since 2026-09-15 the first report keeps its filename;
resumes use `<run>-report-<lane>-pass<n>.md`, starting at n=2. Watch reads the latest close
and uses the same pass numbering when recovering a report from an orphaned transcript.
Spawn reserves only numeric `-pass<n>` lane-id endings
in any letter case, and refuses case-equivalent lane ids in the run record. Historical
`-r<n>` and `-resume-<n>` lane-id endings remain legal; follow-up briefs use `-pass<n>`.
Spawn and resume check destination directory listings case-insensitively before writing,
including directories and dangling symlinks; spawn also checks before starting a detached worker. A resumed response with no
report text is `empty` (exit 3); an earlier transcript message cannot supply its report.

Exit codes: 0 the lane completed; 2 a premise failed before the spawn (no record written), or
`watch` names a lane that is unknown or already closed; 3 the lane ended in error, refusal,
budget stop, max-turns or deadline; 4 `--detach --no-wait` could not confirm its worker's start
within `--ack-wait-s` (the worker left running); 5 a stall; 6 an account or usage limit (`exit_class`
`limit`: the transcript's last assistant record carries a synthetic model with zero usage —
the shape a limit stop leaves, as the watermark hook documents — or the result names a usage
limit); 7 a spawn or a resume held by the run's decisions channel, nothing started; 8 `watch`
returned `still-running`. Permission denials are NOT an error: they are
reported on the summary line, and the head reads them as a re-brief signal.

Numbers that decide, each with its derivation
---------------------------------------------
  - deadline, default 14400 s (4 h): a compatibility bound, set by judgement, unmeasured for
    a new workload. The cost cap bounds spend; `--deadline-s` sets wall time per call.
    Review this allowance against completed runtimes and unfinished healthy work.
  - cost caps: every spawn supplies the head's own positive,
    finite --expect-usd. It is the soft line (soft_src: expect), logged at close, never enforced
    itself. The hard base is HARD_MULTIPLIER × that estimate, rounded to cents. The multiplier
    is 5, set by judgement and unmeasured for a new installation. The hard stop is the
    smaller of this base and the run's envelope remainder, or the base alone when unmetered;
    hard_src names the deciding term. The remainder is the envelope minus the run's spend as the
    gate reads it (`at most` where that spend is a floor), never the head-exits' summed session
    totals. An explicit --budget-usd raises only; an exhausted envelope
    still refuses unless that explicit override is given.
    The class median (usual_usd) is an advisory reference: above 3 × it or below it ÷ 3 prints
    one comparison and records estimate_advisory; exact decimal comparison keeps equality
    quiet, with no division or rounding (estimate × 3 is compared with the median). The factor 3 is
    an advisory sanity band, set by judgement, unmeasured. A class without figures
    records "no class figures" and uses the estimate in the same composition.
    Resume composes from lane-open expect_usd with today's remainder, applying raise-only;
    a budget close still needs an explicit cap above the recorded cap. A resume --expect-usd
    changes its soft line alone. A missing or invalid recorded estimate is a broken premise,
    never a guess from the old class cap. The envelope may sit below the estimate; the soft
    line stays recorded even then. Missing, non-positive or non-finite estimates exit 2 before
    any record line, including a dry run. cost-figures and --check retain their dated medians
    and maximum-plus-25-percent figures; --fold still refreshes those routing blocks only when
    explicitly requested. The floor of three completed lanes is set by judgement, unmeasured.
  - kill grace, 5 s between SIGTERM and SIGKILL to the process group: set by judgement,
    unmeasured — long enough for the CLI to flush its transcript, short enough that a hung
    lane does not hold the head.
  - silence threshold, the class default when a spawn passes no `--silence-s`: 2400 s for the
    writer, critic, builder and planner classes, whose healthy steps run long and quiet, and 900 s
    for every other class. Both are compatibility bounds, set by judgement, unmeasured for a new
    workload; the cost of the longer one is that a genuine stall in those classes is detected later.
    `--silence-s N` replaces the class default and `--silence-s 0` disables the watch;
    `--baseline-lane` raises the threshold to 1.5 × the predecessor's runtime when larger (the
    multiplier set by judgement, unmeasured); a resume keeps its lane-open's threshold, and
    takes the class default only where that lane-open records none.
  - no-transcript bound, 120 s: the harness writes the transcript file on the first user
    message, seconds after the spawn; 120 s is generous headroom, set by judgement.
  - resume window, 55 min: the 1-hour cache tier minus 5 min headroom (D25).
  - reports print in full unless the caller explicitly requests a preview.
  - limit text guard, 60 words: a limit stop is a sentence, a report is hundreds of words, so
    a successful result mentioning "limit" and "usage" counts only under that length or on an
    error; set by judgement, unmeasured.
  - watch bound, 570 s: the shell tool's 600 s cap less 30 s so the wrapper returns before
    the tool kills it; set by judgement.
  - acknowledgement bound, 60 s (`--ack-wait-s`): a waiting limit, not a stall controller. A
    detached worker repeats the caller's checks before it acknowledges; the longest bounded steps
    there are codex-lane.py's two probes (`codex --version`, 30 s; `git rev-parse`, 20 s), 50 s
    together, while this wrapper's worker, handed the caller's composed cap, starts no process
    before its `lane-open`. 60 s is those 50 s plus 10 s of headroom, set by judgement; a large
    staged copy can outlast it, and the outcome is then `unconfirmed`, never a kill.
  - fallback swap timeout, 180 s (SWAP_TIMEOUT_S): it bounds the whole detached Codex caller,
    whose bounded steps are its two probes (50 s, as above), the run's console opener (the swap
    passes no `--viewer`, so the caller opens the console: handsoff.py's live-console probe and
    its two `open` attempts at VIEWER_TIMEOUT_S, 10 s each, then the console's confirmation within
    CONSOLE_START_GRACE_S, 15 s; 45 s) and the acknowledgement wait (60 s): 155 s together. The
    other 25 s are for its unbounded steps (the interpreter's start, the record, brief and control
    reads), set by judgement and unmeasured. Past the timeout the caller is stopped while a worker
    it started may still run, so the swap reads that outcome as unconfirmed, never as a spawn that
    did not run, as it does a caller ended by a signal or an uncaught error, whose exit is no
    account of its worker (fallback_swap).
  - doubled-root depth, 2 path components: a vault root of fewer (`/`, `/tmp`) sits inside every
    path, so the repeated-root pattern is skipped for it; set by judgement, unmeasured.
  - core injection shape: an appended system-prompt file, verified with a marker control below.

Core injection
--------------
The appended system-prompt file carries the lane core and skill slices. Do not assume that
an inline agent definition preloads skills: verify the selected harness path with a marker
control. The core comes from `--append-core FILE`, then the lane-home copy, then the shipped
`templates/lane-core.md`. `--no-core` drops the core and keeps the slices. Every spawn records
`appended` and `appended_bytes` so its actual context remains auditable. A lane-home core that
differs from its template draws one stderr line at the spawn, naming whether it is older than the
template or matches neither the template nor its recorded build (a hand edit in the built copy):
`init` rebuilds it, and the line never stops a spawn.

    So the appended file is the single carrier. Per spawn the wrapper concatenates the lane
    core, then every slice the class row's `skills.default` names, then any `--skill` extra it
    can resolve, each introduced by a one-line heading naming the slice and its source path,
    strips each source's YAML frontmatter (metadata for a loader that is not running here) and
    its vault-local blocks (by the export's own pattern, so a lane reads each sentence once and
    sees what a public copy's lane sees), writes the result to the run store as `<RUN>-appended-<LANE>.md` beside the definition
    copy — so the audit shows exactly what the lane carried — and passes that one file with
    `--append-system-prompt-file`. `lane-core` in a row's slice list IS the core, so it is
    never concatenated twice; `--no-core` drops the core and keeps the slices; a class whose
    DEFAULT slice cannot be resolved is a premise failure. `init` installs no `skills/` links: each
    slice is read from the delegate skill's `lane-home-src/`, and a link an earlier init left is
    removed (register 2026-09-06: a lane's Glob does not traverse a directory link, so the links
    can read as absent slices; every spawn reads the slice source directly).

Reading the transcript
----------------------
The lane's transcript is `<projects-root>/<home path with every non-alphanumeric character
turned into a dash>/<session-id>.jsonl`, with a glob on the session id as the fallback, so a
change in the harness's directory naming degrades to a slower search rather than to silence.
The projects root is `<CLAUDE_CONFIG_DIR>/projects` under `--config-dir` (or that variable in
the head's own environment), else `~/.claude/projects`. From the transcript the wrapper reads
the effort actually applied, the cache write tier, the peak call context, the fence's denials
(a tool result carrying a `lane-fence:` reason), a refusal (`stop_reason`), the last
assistant text when the result field came back empty, and the limit-stop shape.
"""

import argparse
import contextlib
import datetime
from decimal import Decimal, InvalidOperation, localcontext
import errno
import fcntl
import functools
import glob as globmod
import hashlib
import inspect
import io
import json
import math
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
import threading
import uuid

SCHEMA = 2                      # routing.json schema this wrapper speaks
CORE_NAME = "lane-core.md"      # the core's filename in templates/ and the home
CORE_SLICE = "lane-core"        # its name in a class row's skills.default
KILL_GRACE_S = 5                # SIGTERM -> SIGKILL, see the derivation above
DEFAULT_DEADLINE_S = 14400      # see the derivation above (raised from 3600 on 2026-09-16)
DEFAULT_BREADTH = "standard"
ESTIMATE_SANITY_FACTOR = 3       # advisory factor; set by judgement, unmeasured
HARD_MULTIPLIER = 5             # hard stop = 5 × the head's estimate; set by judgement, unmeasured for a new installation
SOFT_HEADROOM = 1.25            # soft = the class's completed maximum × 1.25 (token-efficiency findings 2026-09-07, proposal T3: a bound over the completed maximum kills no lane of its class)
COST_FLOOR_N = 3                # fewest completed lanes a class needs before it carries a cost block; set by judgement, unmeasured (see the derivation above). `cost-figures` spells this number out as `three`
THROTTLES = ("auto", "top", "default", "cheap", "fast", "cheap-fast")   # `auto` first: the default preset, and the fallback for a missing Settings line (owner ruling 2026-09-07 17:0x, built 2026-09-08)
REGIMES = ("single", "multi")   # what a run actually runs under; `auto` is resolved to one per run
DEFAULT_SILENCE_S = 900         # class default for every class but LONG_SILENCE_CLASSES; set by judgement, unmeasured for a new workload
LONG_SILENCE_CLASSES = ("writer", "critic", "builder", "planner")   # classes whose healthy steps run long and quiet (see the derivation above)
LONG_SILENCE_S = 2400           # their class default; set by judgement, unmeasured for a new workload
BASELINE_FACTOR = 1.5           # --baseline-lane multiplier, set by judgement, unmeasured
POLL_S = 30                     # the watchdog's tick (design D20)
NO_TRANSCRIPT_S = 120           # see the derivation above
REPORT_WORDS = None             # The default report is complete; previews require an explicit request.
RESUME_WINDOW_S = 55 * 60       # the 1-hour cache tier less 5 min headroom (design D25)
ORIENTATION_TOKENS = 85000      # fallback only when first_call_context is absent; set by judgement, unmeasured for a new deployment
ADVISE_REPORT_MIN_BYTES = 400   # a wrapper placeholder report is shorter; a lane's real report is longer (set by judgement, unmeasured)
LIMIT_TEXT_WORDS = 60           # see the derivation above
WATCH_MAX_WAIT_S = 570          # see the derivation above
WATCH_APPEAR_S = 5              # record-appearance wait; set by judgement, unmeasured for a new installation
MIN_ROOT_DEPTH = 2              # the doubled-root check skips a shallower vault root: see the derivation above
EXIT_CODES = {"completed": 0, "stall": 5, "limit": 6}    # every other class exits 3
EXIT_STILL_RUNNING = 8
# A spawn or resume held by the run's decisions channel, nothing started. Not 6: a lead's spawn line
# shows only `rc=`, and on a spawn 6 means an account limit, which the resume note says to resume.
EXIT_DECISIONS_HOLD = 7
# The spawn hold's one mode. `trial` logs what it would have held and holds nothing, as a new check
# that can block first must; anything else holds. One constant, so no record can lose a mode: the
# owner's word to enforce is this one word, at an install.
DECISIONS_HOLD_MODE = "trial"
EXIT_UNCONFIRMED = 4            # a detached call's worker lives but its acknowledgement was not seen: the lowest code neither wrapper uses (they use 0, 2, 3, 5, 6, 7 and 8; 1 is Python's own for an uncaught error)
ACK_WAIT_S = 60                 # see the derivation above: how long --detach --no-wait waits for this call's acknowledgement
ACK_POLL_S = 0.25               # record reads while it waits; set by judgement, unmeasured
STALL_ACTION = "SIGTERM process group, %d s, SIGKILL" % KILL_GRACE_S
# The held-lane beat (2026-09-17): the fixed no-work line, the bound on one beat, the
# close classes a beat re-enters (handsoff.py's HOLDABLE_EXITS, the same tuple), who issued it,
# and the flag pairs the configuration hash leaves out — the session flag, which differs between
# a spawn and its resume by design, and the two wrapper-side bounds, which never reach the model.
BEAT_PROMPT = "beat: reply with the single word ok"
BEAT_TIMEOUT_S = 600            # a cached one-word reply answers in seconds; the shell tool's own cap (set by judgement, unmeasured)
BEAT_EXITS = ("completed", "empty", "watch-closed")
BEAT_BY_ENV = "AIMYTH_BEAT_BY"
CONFIG_DROP_PAIRS = ("--session-id", "--resume", "--max-budget-usd", "--max-turns")
# A beat in flight is announced on disk, not only at its end (critic F4, 2026-09-17): the beat's
# own record line is written when the call returns, so without this marker, between a beat's start
# and its end, nothing would have
# told a second `resume` that the session was busy, and two processes on one session can be one
# command apart. The marker names the pid, and a resume of either wrapper
# refuses while that pid is alive; a marker whose pid is gone is stale and removed, so a crashed
# beat blocks nothing.
BEAT_MARKER_SUFFIX = "-beat.pid"
SESSION_LOCK_SUFFIX = ".lock"   # the advisory lock beside it: the claim on a lane's session
# Keeping the host awake beside each lane process (owner decision of 2026-10-09; see "Keeping the
# host awake" above): macOS's own tool, absent on other platforms, where the start is skipped with
# a note; the environment variable names a stand-in binary by path, for a suite.
CAFFEINATE_BIN = "/usr/bin/caffeinate"
CAFFEINATE_ENV = "AIMYTH_CAFFEINATE"
AWAKE_EVENT = "lane-awake"
# The box around each helper process (owner decision of 2026-11-04; see "Keeping a helper's signals
# inside its box" above). Every signal is denied but one to the helper's own box; `ps` and `top`,
# which the sandbox would otherwise refuse as setuid programs and which cannot signal, run outside it.
BOX_BIN = "/usr/bin/sandbox-exec"
BOX_ENV = "AIMYTH_LANE_BOX"
BOX_OFF = "off"                 # the switch's one word; any other value names a stand-in binary
BOX_ON = "on"
BOX_NESTED = "on: inside a box already"
BOX_PROFILE = ('(version 1)(allow default)(deny signal)(allow signal (target same-sandbox))'
               '(allow process-exec (literal "/bin/ps") (with no-sandbox))'
               '(allow process-exec (literal "/usr/bin/top") (with no-sandbox))')
# The premise check's bound. Set by judgement, unmeasured as a limit; the check itself measured a
# mean of 13.8 ms over 20 runs on 2026-11-04 (Darwin 27.0.0), so only a hang reaches this.
BOX_PROBE_S = 10
BOX_NOTE_CHARS = 160            # how much of a refusal's stderr the `box` value keeps; by judgement


# ----------------------------------------------------------------- premise and paths -------

def die(reason):
    """A premise failure: say what broke, write nothing, exit 2."""
    sys.stderr.write("lane.py: PROBE FAILED: %s\n" % reason)
    sys.exit(2)


# The instrument-rule letter a `lane-open` reason carries (CLAUDE.md section 2.2, the four
# reasons a lane may be spawned for): the bracketed form anywhere in the text, or a leading bare
# letter followed by a colon or a spaced dash — `(a)`, `a:`, `a —`, `a -` — the forms heads have
# written live (register, 2026-09-06). The meter's tally reads the same forms (fable-share.py,
# REASON_LEAD_RE); the two expressions are twins kept in step by hand.
REASON_BRACKET_RE = re.compile(r"\(([a-dA-D])\)")
REASON_LEAD_RE = re.compile(r"^\s*([a-dA-D])\s*(?::|[\u2014-](?=\s|$))")
REASON_FORMS = "`(a)`, `a —`, `a -` or `a:` (letters a to d)"


def reason_letters(text):
    """The lower-case instrument-rule letters a reason names, as the meter tallies them."""
    letters = {letter.lower() for letter in REASON_BRACKET_RE.findall(text or "")}
    lead = REASON_LEAD_RE.match(text or "")
    if lead:
        letters.add(lead.group(1).lower())
    return letters


def require_reason_letter(text):
    """One refusal for every reason that names no instrument-rule letter: omitted, whitespace-only
    and letterless alike. A spawn whose record carries no letter is a defect for the register
    (CLAUDE.md section 2.2) and the meter tallies it as `none`, so the omitted form — recorded as
    "" until now — takes the refusal the letterless one has taken since 2026-09-06 (register,
    2026-09-07). Called before anything is written, so a refused spawn leaves no record line."""
    if not reason_letters(text):
        die("--reason %r carries no instrument-rule letter: open it with one of %s, as CLAUDE.md "
            "section 2.2 requires of every spawn — refused rather than recorded"
            % ((text or "")[:60], REASON_FORMS))


def vault_root():
    """The vault is three levels above this script (.claude/skills/delegate/lane.py); an
    explicit CLAUDE_PROJECT_DIR wins, so a copy of the script can be pointed at a vault."""
    return os.path.realpath(vault_given())


def vault_given():
    """The vault root as spelled by the caller (symlinks unresolved), for the second spelling."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        os.pardir, os.pardir, os.pardir))


def store_root():
    """The machine-local run store (hand-off documents, spawn records, parity fixtures)."""
    given = os.environ.get("LLM_WIKI_STORE") or os.path.join(os.path.expanduser("~"), ".llm-wiki")
    return os.path.realpath(os.path.expanduser(given))   # real paths in every record (D17)


def default_home():
    return os.environ.get("LLM_WIKI_LANE_HOME") or os.path.join(store_root(), "lane-home")


def store_paths(run, lane, record_override=None):
    """Every per-lane artefact path in the run store, keyed by name."""
    store = os.path.join(store_root(), "spawn-records")
    return {"store": store,
            "record": record_override or os.path.join(store, "%s.jsonl" % run),
            "definition_copy": os.path.join(store, "%s-definition-%s.md" % (run, lane)),
            "appended": os.path.join(store, "%s-appended-%s.md" % (run, lane)),
            "report": os.path.join(store, "%s-report-%s.md" % (run, lane)),
            "settings": os.path.join(store, "%s-settings-%s.json" % (run, lane)),
            "input_dir": os.path.join(store, "%s-in-%s" % (run, lane)),
            "detach_log": os.path.join(store, "%s-detached-%s.log" % (run, lane))}


def require_lane_id(lane_id):
    """Reserve report and prompt pass endings in any letter case (critic fold, 2026-09-16).
    Reports and follow-up prompts use -pass<n>; historical lane endings remain legal."""
    match = re.search(r"-pass[0-9]+$", lane_id, re.IGNORECASE)
    if match:
        die("--lane %r ends in reserved per-pass suffix %s (-pass<n>); "
            "choose a lane id without that ending" % (lane_id, match.group()))


def require_absent_paths(paths, empty_dirs=()):
    """Refuse case-equivalent artefacts, including directories and dangling symlinks.
    Directory listings keep the same rule on case-sensitive and insensitive filesystems.
    Only explicitly named, exactly spelt empty directories may be reused as staging paths.
    Symlinks and case-equivalent spellings never qualify.
    This read-only check precedes spawn/resume writes, staging and detached workers."""
    reusable = {os.path.abspath(path) for path in empty_dirs}
    for path in paths:
        parent, name = os.path.split(os.path.abspath(path))
        try:
            names = os.listdir(parent)
        except FileNotFoundError:
            continue
        except OSError as exc:
            die("cannot check per-pass path %s: %s" % (path, exc))
        for existing in (entry for entry in names if entry.casefold() == name.casefold()):
            if os.path.abspath(path) in reusable and existing == name:
                try:
                    empty = stat.S_ISDIR(os.lstat(path).st_mode) and not os.listdir(path)
                except OSError as exc:
                    die("cannot check empty stage directory %s: %s" % (path, exc))
                if empty:
                    continue
            die("per-pass path already exists: %s (case-equivalent destination %s) — "
                "no existing artefact is overwritten" % (path, os.path.join(parent, existing)))


def require_new_lane_id(lane_id, record_path):
    """A spawn cannot reuse any case-equivalent lane identity in its run record.
    Missing and empty records are valid; an unreadable record, or damage no journalled repair
    admits, cannot prove absence. The strict reader decides, so a repaired record spawns again."""
    try:
        rows, _ = a3_record_rows(record_path)
    except (A3Premise, OSError, UnicodeError) as exc:
        die("cannot check lane ids in %s: %s" % (record_path, exc))
    for event in rows:
        existing = event.get("lane")
        if isinstance(existing, str) and existing.casefold() == lane_id.casefold():
            die("--lane %r is case-equivalent to existing lane %r in %s — "
                "spawn needs a fresh lane id" % (lane_id, existing, record_path))


def pass_report_path(first_path, pass_n):
    """Keep pass one unsuffixed; the first resume is pass two (2026-09-15)."""
    if pass_n == 1:
        return first_path
    stem, suffix = os.path.splitext(first_path)
    return "%s-pass%d%s" % (stem, pass_n, suffix)


def progress_path(run, lane):
    """The lane's liveness file: /tmp by design (the fence sanctions it for every lane); the
    directory is overridable so a suite can keep its fixtures inside one temporary root."""
    return os.path.join(os.environ.get("LLM_WIKI_PROGRESS_DIR") or "/tmp",
                        "%s-%s.progress" % (run, lane))


# ------------------------------------------------------------ the caller's own checks -------
# Check embedded absolute roots and repeated vault prefixes, regardless of the root spelling.
# (register 2026-09-09
# 19:03). The check is keyed on that property, whatever the path's lead or the store's name.
# `embedded_root` defines every accepted root shape.
ROOT_FAMILIES = ("Users", "home", "tmp", "private", "var", "opt")   # the first segment of an absolute path on macOS and Linux: the homes, the temporary roots and the system roots
HOME_FAMILIES = ("Users", "home")          # a home is one of these followed by a name
FIRMLINK_CHILDREN = ("tmp", "var", "etc")  # macOS keeps these under /private, so /private/tmp is one absolute path; set by judgement from the platform layout, unmeasured here
PATH_TOKEN_CHARS = r"[^\s\"'`<>()\[\]{},;:|=]"   # what a path token holds: never a space, a quote, a bracket or a list separator (a colon joins two paths, as in a PATH list)
PATH_TOKEN_RE = re.compile(PATH_TOKEN_CHARS + "+")
PATH_TOKEN_GAP = PATH_TOKEN_CHARS + "*?"   # what may sit between two roots in one path


def root_lead(segments, absolute):
    """How many leading `segments` are the token's own root, or 0 when it is not a root path. A
    root path is led by `~`, a `$VARIABLE`, a hidden directory name (`.name`), or an absolute path
    whose first segment is one of ROOT_FAMILIES; any other token (a relative path, a path on
    another volume, a sed expression, a word pair such as `local/private`) is never judged. A
    home's lead is its family and name; a macOS firmlink root's is `private` and its child."""
    first = segments[0] if segments else ""
    if not first:
        return 0
    if not absolute:
        return 1 if re.match(r"~|\$\w|\.[^./]", first) else 0
    if first not in ROOT_FAMILIES:
        return 0
    second = segments[1] if len(segments) > 1 else ""
    if (first in HOME_FAMILIES and second) or (first == "private" and second in FIRMLINK_CHILDREN):
        return 2
    return 1


def embedded_root(token):
    """What makes `token` a root path that embeds a second absolute path, or None. Past the
    token's own lead (`root_lead`), a segment of ROOT_FAMILIES begins a second absolute path when
    it is observably the start of one:
      - a home: `Users` or `home` followed by a name (`~/.store/Users/name`, `/private/Users/name`);
      - a macOS firmlink root: `private` followed by tmp, var, etc or another family;
      - a join mark: the segment follows an empty one (`~/.store//tmp/x`), what joining a root
        and an absolute path as strings leaves;
      - the path's own first two segments repeated from it (`/tmp/k/stage/tmp/k`).
    A bare tmp, var or opt meeting none of these is read as an ordinary directory of that name
    (`~/tmp`, a Homebrew prefix's `opt` and `var`) and never scores: set by judgement, unmeasured.
    The converse limit: an ordinary directory named `home` or `Users` with a child, inside a root
    path, reads as a home and scores."""
    absolute = token.startswith("/")
    segments = token.lstrip("/").split("/")
    lead = root_lead(segments, absolute)
    if not lead:
        return None
    own = [part for part in segments if part]
    if absolute and len(own) > 1 and own[0] == "private" and own[1] in FIRMLINK_CHILDREN:
        own = own[1:]
    for i in range(lead, len(segments)):
        segment = segments[i]
        if segment not in ROOT_FAMILIES:
            continue
        after = segments[i + 1] if i + 1 < len(segments) else ""
        if segment in HOME_FAMILIES and after:
            return "the home /%s/%s embedded in a root path" % (segment, after)
        if segment == "private" and (after in FIRMLINK_CHILDREN or after in ROOT_FAMILIES):
            return "the absolute path /private/%s embedded in a root path" % after
        if segments[i - 1] == "":
            return "an absolute path joined into a root path at //%s" % segment
        if absolute and len(own) > 1 and [part for part in segments[i:] if part][:2] == own[:2]:
            return "the path's own root /%s repeated inside it" % "/".join(own[:2])
    return None


def doubled_root_hits(text, roots):
    """(line number, line, what) for each line of `text` carrying a doubled root: one of `roots`
    twice inside one path token, or a path token that is a root path embedding a second absolute
    path (`embedded_root`). A root of fewer than MIN_ROOT_DEPTH components is skipped by the first
    check, never matched, since it sits inside every path; a URL is never judged."""
    patterns = []
    for root in sorted({str(r).rstrip(os.sep) for r in roots or [] if r}):
        if len([part for part in root.split(os.sep) if part]) < MIN_ROOT_DEPTH:
            continue
        patterns.append(("the vault root %s twice in one path" % root,
                         re.compile(re.escape(root) + PATH_TOKEN_GAP + re.escape(root))))
    hits = []
    for number, line in enumerate((text or "").splitlines(), 1):
        what = next((label for label, pattern in patterns if pattern.search(line)), None)
        if what is None:
            for match in PATH_TOKEN_RE.finditer(line):
                token = match.group(0)
                if token.startswith("//") and line[max(0, match.start() - 1):match.start()] == ":":
                    continue                    # a URL's authority and path, not a filesystem path
                what = embedded_root(token)
                if what:
                    break
        if what:
            hits.append((number, line, what))
    return hits


def refuse_doubled_root(brief_path, text, vault):
    """Exit 2, quoting the first offending line, when a brief carries a doubled root; called before
    any record line (a spawn's caller, a resume, codex-lane.py's prepare)."""
    hits = doubled_root_hits(text, [vault, vault_given()])
    if hits:
        number, line, what = hits[0]
        die("brief %s line %d carries a doubled root (%s): %s%s — its paths were mangled before "
            "the spawn; rewrite them and spawn again"
            % (brief_path, number, what, line.strip()[:240],
               "" if len(hits) == 1 else " (and %d more line(s))" % (len(hits) - 1)))


def grant_parent_warnings(values, vault, flag, covered=()):
    """One stderr line per FILE grant whose parent holds anything else: the file tools can only be
    widened by directory, so such a grant hands the lane that whole directory (register 2026-09-08,
    the judge-brief entry; delegate skill section 3, slot 2). The line names the vault root or a
    home directory where the parent is one, and otherwise says how much else it holds. A file alone
    in its directory earns none, and so does one whose parent lies inside `covered`, the real
    directories this spawn grants in any case, since the file grant then widens nothing. `.DS_Store`
    is the system's, not a sibling. A warning, never a refusal; a path that does not exist, or a
    parent that cannot be listed, is left to the spawn's own check. A home directory is the caller's
    own home or any directory beside it, unless the home's parent is the filesystem root."""
    home = os.path.realpath(os.path.expanduser("~"))
    homes = os.path.dirname(home)
    vault_real = os.path.realpath(vault)
    lines = []
    for value in values or []:
        given = os.path.expanduser(str(value))
        if not os.path.isabs(given):
            given = os.path.join(vault, given)
        real = os.path.realpath(given)
        if not os.path.isfile(real):
            continue
        parent = os.path.dirname(real)
        if parent == vault_real:
            what = "the vault root"
        elif parent == home or (homes != os.sep and os.path.dirname(parent) == homes):
            what = "a home directory"
        elif within_roots(parent, covered):
            continue
        else:
            try:
                others = [name for name in os.listdir(parent)
                          if name not in (os.path.basename(real), ".DS_Store")]
            except OSError:
                continue
            if not others:
                continue
            what = "it holds %d other %s" % (len(others), "entry" if len(others) == 1 else "entries")
        line = ("lane.py: warning: %s %s is a file, and a file grant reaches its whole parent %s "
                "(%s) through --add-dir; stage the file in a directory of its own (delegate skill "
                "section 3, slot 2)" % (flag, os.path.abspath(given), parent, what))
        sys.stderr.write(line + "\n")
        lines.append(line)
    return lines


REOPEN_EVENTS = ("run-open", "run-resume")   # what a head writes on taking a run; handsoff.py refuses a second run-open, so a closed run is taken again by run-resume


def closed_run_warning(record_path, who="lane.py"):
    """One stderr line when the run is closed: the record holds a `run-close` and no `run-open` or
    `run-resume` after the latest one, whatever else follows it (observations, lane lines, a
    heartbeat). A spawn onto a closed run is how a second head on one session shows itself
    (register 2026-09-03). The key is the close left
    standing, not the close being the last line. Later events do not reopen a closed run. A
    warning, never a refusal, since a deliberate lane after the close is legitimate; a missing,
    empty or unreadable record, or one with no parseable run-close, says nothing."""
    close, since = None, 0
    try:
        with open(record_path, "r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                name = event.get("event")
                if name == "run-close":
                    close, since = event, 0
                elif name in REOPEN_EVENTS:
                    close, since = None, 0
                elif close is not None:
                    since += 1
    except (OSError, TypeError):
        return None
    if close is None:
        return None
    line = ("%s: warning: run %s is closed: its run-close at %s has no later run-open or "
            "run-resume (%d event(s) since), so a spawn onto it may be a second head on one "
            "session (known-issues 2026-09-03); proceeding"
            % (who, close.get("run") or "?", close.get("ts") or "no ts", since))
    sys.stderr.write(line + "\n")
    return line


def decisions_spawn_check(record_path, run, lane_id, who="lane.py", verb="spawn", dry_run=False):
    """A helper starts only after the newest owner decision has been read (register 2026-10-14
    01:33 b). The caller's terminal, before any detach and any record line. Enforcing, a hold exits
    EXIT_DECISIONS_HOLD and a state that cannot be read exits 2, nothing started. Under `trial` the
    same text prints, one observation per digest and head goes on the record, and the call goes on.
    A dry run prints and writes nothing, since a rehearsal starts no helper. A run with no record
    yet has nothing to read, so it pays for no import."""
    if not os.path.lexists(record_path):
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    sys.dont_write_bytecode = True   # the import must never leave a __pycache__ in the skill directory
    trial = DECISIONS_HOLD_MODE == "trial"
    try:
        import handsoff
        state = handsoff.decisions_spawn_state(record_path)
        lines = handsoff.decisions_spawn_lines(state, verb, lane_id, run, record_path, trial=trial)
    except (Exception, SystemExit) as exc:   # the check itself failed: that is a state, never a pass
        state = {"state": "unknown", "why": "the decisions check failed: %s" % exc}
        lines = ["%s of lane %s: the decisions check failed: %s" % (verb, lane_id, exc)]
    if state["state"] == "clear":
        return None
    held = state["state"] == "hold"
    if dry_run:
        sys.stderr.write("%s: dry run, would %s: %s\n" % (
            who, "hold" if held else "refuse", "\n".join(lines)))
        return None
    if not trial:
        sys.stderr.write("%s: %s\n" % (who, "\n".join(lines)))
        sys.exit(EXIT_DECISIONS_HOLD if held else 2)
    sys.stderr.write("%s: trial, nothing held: %s\n" % (who, "\n".join(lines)))
    if state.get("logged"):
        return None
    try:
        append_record(record_path, {"ts": now(), "run": run, "event": "observation", "phase": "",
                                    "what": "decisions-hold trial: would %s %s of lane %s"
                                            % ("hold" if held else "refuse", verb, lane_id),
                                    "digest": state.get("digest"), "size": state.get("size"),
                                    "note": state["why"]})
    except (OSError, A3Premise) as exc:
        sys.stderr.write("%s: the trial's line was not written (%s)\n" % (who, exc))
    return None


def caller_checks(args, row_grants=()):
    """What a spawn checks in the caller's own terminal before any detach (a detached worker skips
    them): the brief is there and carries no doubled root, and the two warnings — a file grant
    reaching a directory that holds anything else, a spawn onto a closed run. `row_grants` are the
    class's literal defaults this spawn keeps, which reach their directories whatever the call says."""
    vault = vault_root()
    if not os.path.isfile(args.brief):
        die("brief file not found: %s" % args.brief)
    brief = read_text(args.brief, "the brief")
    if not brief.strip():
        die("brief file is empty: %s" % args.brief)
    refuse_doubled_root(args.brief, brief, vault)
    covered = []
    for value in list(args.grant or []) + list(args.write or []) + list(row_grants):
        given = os.path.expanduser(str(value))
        real = os.path.realpath(given if os.path.isabs(given) else os.path.join(vault, given))
        if os.path.isdir(real):
            covered.append(real)
    grant_parent_warnings(args.grant, vault, "--grant", covered)
    grant_parent_warnings(args.write, vault, "--write", covered)
    closed_run_warning(store_paths(args.run, args.lane, args.record)["record"])


def config_home(config_dir):
    """The harness configuration directory a lane runs under, or None for the default."""
    return config_dir or os.environ.get("CLAUDE_CONFIG_DIR") or None


def projects_root_for(override, config_dir):
    if override:
        return override
    base = config_home(config_dir) or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(base, "projects")


def config_argv(command, drop_pairs=CONFIG_DROP_PAIRS, drop_tail=0):
    """The command line's configuration: every token but the named flag pairs (each flag and
    the value after it) and the last `drop_tail` tokens (a prompt argument, a marker)."""
    parts = list(command)[:len(command) - drop_tail] if drop_tail else list(command)
    out, skip = [], False
    for part in parts:
        if skip:
            skip = False
            continue
        if part in drop_pairs:
            skip = True
            continue
        out.append(part)
    return out


def config_sha256(command, extra_texts=(), drop_pairs=CONFIG_DROP_PAIRS, drop_tail=0):
    """The hash a spawn, a resume and a beat record: the configuration argv NUL-joined, then the
    bytes of each extra text (the files the command names whose content reaches the harness).
    Two calls whose hashes agree run the model under one configuration."""
    digest = hashlib.sha256()
    for part in config_argv(command, drop_pairs, drop_tail):
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\0")
    for text in extra_texts:
        digest.update(b"\0file\0")
        digest.update(text if isinstance(text, bytes) else str(text).encode("utf-8"))
    return digest.hexdigest()


def read_bytes(path):
    """A file's bytes, or None when it cannot be read (the hash then says so)."""
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def beat_usage(result):
    """The beat's own usage from the harness result's modelUsage (this invocation's calls,
    summed over models): input, output, cache read and cache write tokens, the models named.
    An absent or malformed modelUsage reads as None, never as zero tokens."""
    usage = result.get("modelUsage") if isinstance(result, dict) else None
    if not isinstance(usage, dict) or not usage:
        return None
    out = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
           "cache_creation_input_tokens": 0, "models": sorted(str(k) for k in usage)}
    keys = (("inputTokens", "input_tokens"), ("outputTokens", "output_tokens"),
            ("cacheReadInputTokens", "cache_read_input_tokens"),
            ("cacheCreationInputTokens", "cache_creation_input_tokens"))
    for per_model in usage.values():
        if not isinstance(per_model, dict):
            continue
        for theirs, ours in keys:
            value = per_model.get(theirs)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[ours] += int(value)
    context = out["input_tokens"] + out["cache_read_input_tokens"] + out["cache_creation_input_tokens"]
    # a reading, not a verdict: the share of the call's context that was read from the cache;
    # the closing meter's rewrite causes decide (a beat that hits shows no rewrite)
    out["cache_read_share"] = round(out["cache_read_input_tokens"] / context, 2) if context else None
    return out


def sha(text):
    if isinstance(text, str):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def read_text(path, what):
    try:
        owners = [owner for owner in _A3_OWNERS.values()
                  if getattr(owner.args, "brief", None) and
                  a3_canonical(owner.args.brief) == a3_canonical(path)]
        if owners:
            with open(path, "rb") as handle:
                data = handle.read()
            for owner in owners:
                owner.source_bytes = data
            return data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        die("cannot read %s (%s): %s" % (what, path, exc))


def write_atomic(path, text, binary=False):
    """Temp file in the same directory, then rename: a concurrent reader sees the old file or
    the new one, never a half-written one."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temp = os.path.join(directory, ".%s.%s.tmp" % (os.path.basename(path), uuid.uuid4().hex))
    try:
        with open(temp, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        a3_sync_directory(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def dashed(path):
    """The harness's project-directory encoding: every non-alphanumeric character becomes a
    dash."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(path))


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def strip_vault_local(text, label):
    """The text as a public copy holds it: every vault-local block out, by the export's own Markdown
    pattern, so a lane reads each sentence once instead of a sentence and its local twin. A nested or
    unmatched marker leaves the text as it stands with one stderr line: a doubled sentence costs a
    lane little, and a refused spawn costs a run its helper."""
    depth = 0
    for match in re.finditer(r"<!-- *vault-local:(begin|end) *-->", text):
        opening = match.group(1) == "begin"
        if opening == bool(depth):
            sys.stderr.write("lane.py: %s has a nested or unmatched vault-local marker; appended as it "
                             "stands\n" % label)
            return text
        depth = 1 if opening else 0
    if depth:
        sys.stderr.write("lane.py: %s has an unmatched vault-local marker; appended as it stands\n" % label)
        return text
    return re.sub(r"[ \t]*<!-- *vault-local:begin *-->.*?<!-- *vault-local:end *-->[ \t]*\n?", "", text,
                  flags=re.S)


def core_drift_note(home, vault):
    """One line when the lane-home core differs from its template, else None. The home core is what a
    spawn appends, so a template edit reaches no lane until `init` rebuilds it (register 2026-10-04 00:09).
    It tells a stale build from a hand edit by the sha `init` recorded. A note, never a stop."""
    home_core, template = os.path.join(home, CORE_NAME), core_source(vault)
    if not (os.path.isfile(home_core) and os.path.isfile(template)):
        return None
    current = sha(read_text(home_core, "the lane core"))
    if current == sha(read_text(template, "the lane core")):
        return None
    recorded = (load_state(home).get(CORE_NAME) or {}).get("out_sha")
    if current == recorded:
        return "lane.py: the lane-home core is older than its template; `lane.py init` rebuilds it"
    return ("lane.py: the lane-home core matches neither its recorded build nor its template (a hand "
            "edit in the built copy?); `lane.py init` rebuilds it, so carry such an edit into the template first")


def item_name(value):
    """--item's value: an empty one is refused at the parser (exit 2), before anything starts."""
    if not value.strip():
        raise argparse.ArgumentTypeError("--item is empty: name the run item, or leave the flag out")
    return value.strip()


def item_warning(record_path, item, who="lane.py"):
    """One stderr line when a spawn on a hands-off run names no --item: the console then files the
    lane under the item in hand and marks it inferred (register 2026-11-05 12:41). A warning, never
    a refusal, and said only where a run-open stands on the record."""
    if item or not os.path.isfile(record_path):
        return None
    try:
        with open(record_path, "r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("event") == "run-open":
                    sys.stderr.write("%s: warning: no --item on this spawn of a hands-off run: the "
                                     "console files the lane under the item in hand, marked "
                                     "inferred\n" % who)
                    return True
    except OSError:
        return None
    return None


def parse_frontmatter(text):
    """The small subset the agent definitions use: `key: value` lines between --- fences."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fields = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields, text[end + 4:].lstrip("\n")


def customisation_value(field_name, fallback):
    """Read a `- **field**: value — comment` line out of the preference layer."""
    path = os.path.join(vault_root(), "CUSTOMISATION.md")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                match = re.match(r"^-\s+\*\*%s\*\*:\s*([^\s—]+)" % re.escape(field_name), line)
                if match:
                    return match.group(1).strip()
    except OSError:
        return fallback
    return fallback


def resolve_delegation(args):
    """The run's delegation regime for the record: (regime, source, where it came from).
    `--delegation` with `--delegation-src` wins; else the Settings line's `single`/`multi`
    word, source `owner`; `auto`, an absent line or any other value is a premise failure,
    since a record must never carry a regime nobody chose."""
    if bool(args.delegation) != bool(args.delegation_src):
        die("--delegation and --delegation-src go together: --delegation single|multi "
            "--delegation-src head|owner")
    if args.delegation:
        return args.delegation, args.delegation_src, "--delegation"
    word = customisation_value("delegation", None)
    line = "delegation"
    if word is None:
        word = customisation_value("mode", None)
        line = "mode (the pre-rename line)"
    if word in REGIMES:
        return word, "owner", "the Settings `%s` line" % line
    reads = "absent" if word is None else "`%s`" % word
    die("delegation regime unresolved: the Settings line is %s — resolve this run first "
        "(role-style-anchor.py set-delegation) and pass --delegation single|multi "
        "--delegation-src head|owner" % reads)


# --------------------------------------------------------------------------- init ----------

def slice_sources(vault):
    """One directory per slice, each holding a SKILL.md; `init` reports it when absent."""
    return os.path.join(vault, ".claude", "skills", "delegate", "lane-home-src")


def core_source(vault):
    """The shipped lane core, materialised into the home so a spawn needs no vault read."""
    return os.path.join(vault, ".claude", "skills", "delegate", "templates", CORE_NAME)


# The reflect slice's local blocks carry a rule with no public twin, so a reflector needs them. An
# export removes the blocks, so only a lane on this vault reads them and a public copy is unchanged.
KEEP_LOCAL_SLICES = {"reflect-slice"}


def resolve_slice(name, home, vault):
    """A slice's text, from the lane home first (a slice placed there by hand; init installs none)
    then the shipped source. Returns (source path, body with its frontmatter stripped, and its
    vault-local blocks too unless KEEP_LOCAL_SLICES names it) or (None, None)."""
    for candidate in (os.path.join(home, "skills", name, "SKILL.md"),
                      os.path.join(slice_sources(vault), name, "SKILL.md"),
                      os.path.join(home, "skills", "%s.md" % name)):
        if os.path.isfile(candidate):
            body = strip_frontmatter(read_text(candidate, "slice %s" % name))
            return candidate, body if name in KEEP_LOCAL_SLICES else strip_vault_local(body, "slice %s" % name)
    return None, None


def display_path(path, vault):
    """Vault-relative where it can be, absolute otherwise: the audit heading stays readable
    and carries no machine-specific prefix for anything that lives in the vault. Symlinks are
    resolved first, so a slice linked into the lane home names the shipped file it came
    from — the path a reader can go and check."""
    path = os.path.realpath(path)
    try:
        relative = os.path.relpath(path, vault)
    except ValueError:
        return path
    return relative if not relative.startswith(os.pardir) else path


def extract_schema_section(vault):
    """The contract's page-schema section: from its heading to the next same-level heading."""
    path = os.path.join(vault, "CLAUDE.md")
    text = read_text(path, "the vault contract")
    match = re.search(r"^## \d+\. Wiki Page Schema.*?$", text, re.M)
    if not match:
        die("CLAUDE.md has no wiki page schema heading — the contract slice cannot be built")
    start = match.start()
    nxt = re.search(r"^## ", text[match.end():], re.M)
    body = text[start:match.end() + nxt.start()] if nxt else text[start:]
    return path, body.rstrip() + "\n"


def extract_confidence_rubric(vault):
    path = os.path.join(vault, "wiki", "developments", "wiki-confidence-levels.md")
    if not os.path.exists(path):
        # A fresh clone lacks the vault-local rubric; lanes rely on the schema slice's section 4.6 summary.
        return path, None
    return path, strip_frontmatter(read_text(path, "the confidence rubric page")).rstrip() + "\n"


def state_path(home):
    return os.path.join(home, ".lane-home-state.json")


def load_state(home):
    try:
        with open(state_path(home), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def materialise(home, rel, source_path, source_text, content, state, report):
    """Write `content` at `rel` under the home, but only when the source changed or the file
    drifted. Returns the verb for the report line."""
    target = os.path.join(home, rel)
    src_sha = sha(source_text)
    out_sha = sha(content)
    previous = state.get(rel) or {}
    current = None
    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as handle:
                current = sha(handle.read())
        except OSError:
            current = None
    if current is None:
        verb = "created"
    elif previous.get("src_sha") == src_sha and current == out_sha:
        state[rel] = {"src_sha": src_sha, "out_sha": out_sha, "source": source_path}
        report.append(("kept", rel))
        return "kept"
    else:
        verb = "regenerated"
    write_atomic(target, content)
    state[rel] = {"src_sha": src_sha, "out_sha": out_sha, "source": source_path}
    report.append((verb, rel))
    return verb


def cmd_init(args):
    vault = vault_root()
    home = os.path.realpath(os.path.expanduser(args.home or default_home()))
    os.makedirs(home, mode=0o700, exist_ok=True)
    state = load_state(home)
    report = []

    fence_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lane-fence.py")
    fence_text = read_text(fence_src, "the fence hook")
    materialise(home, "lane-fence.py", fence_src, fence_text, fence_text, state, report)
    os.chmod(os.path.join(home, "lane-fence.py"), 0o700)

    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{
        "type": "command",
        "command": "%s %s" % (shlex.quote(sys.executable),
                              shlex.quote(os.path.join(home, "lane-fence.py")))}]}]}}
    settings_text = json.dumps(settings, indent=2) + "\n"
    materialise(home, "lane-settings.json", "(computed)", settings_text, settings_text,
                state, report)

    src, body = extract_schema_section(vault)
    materialise(home, os.path.join("contract", "schema-s4.md"), src, body, body, state, report)
    src, body = extract_confidence_rubric(vault)
    if body is None:
        report.append(("absent", os.path.join("contract", "confidence-rubric.md")
                       + " (no rubric page in this vault: a fresh clone; optional)"))
    else:
        materialise(home, os.path.join("contract", "confidence-rubric.md"), src, body, body,
                    state, report)

    # Skills: the harness discovers project skills under <cwd>/.claude/skills, and the design
    # names the home's directory `skills/`; the symlink lets one directory serve both.
    skills_dir = os.path.join(home, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    dot_claude = os.path.join(home, ".claude")
    os.makedirs(dot_claude, exist_ok=True)
    link = os.path.join(dot_claude, "skills")
    if not os.path.islink(link) and not os.path.exists(link):
        os.symlink(skills_dir, link)
        report.append(("created", ".claude/skills -> skills"))
    else:
        report.append(("kept", ".claude/skills -> skills"))

    core_src = core_source(vault)
    installed, missing = [], []
    if os.path.isfile(core_src):
        core_text = read_text(core_src, "the lane core")
        materialise(home, CORE_NAME, core_src, core_text, core_text, state, report)
    else:
        missing.append(os.path.relpath(core_src, vault))

    source_dir = slice_sources(vault)
    if os.path.isdir(source_dir):
        for name in sorted(os.listdir(source_dir)):
            entry = os.path.join(source_dir, name)
            if not os.path.isdir(entry):
                continue          # only a directory holding a SKILL.md is a slice
            installed.append(name)
    else:
        missing.append(os.path.relpath(source_dir, vault))
    # No `skills/` links (register 2026-09-06, owner-gated). They were installed for a skills preload
    # that is no longer used. A lane's Glob does not traverse a directory link; every spawn reads a
    # slice from `lane-home-src/` itself (resolve_slice). A link an earlier init left is removed — the
    # link alone, never the slice it points at — when it points at a `lane-home-src/<name>`; anything
    # else under `skills/` is left alone.
    if os.path.isdir(skills_dir) and not os.path.islink(skills_dir):
        for name in sorted(os.listdir(skills_dir)):
            target = os.path.join(skills_dir, name)
            if os.path.islink(target) and \
                    os.readlink(target).rstrip(os.sep).endswith(os.path.join("lane-home-src", name)):
                os.unlink(target)
                report.append(("removed", os.path.join("skills", name)
                               + " (a link into lane-home-src; the slice is read there)"))

    write_atomic(state_path(home), json.dumps(state, indent=1, sort_keys=True) + "\n")

    print("lane home: %s" % home)
    for verb, rel in report:
        print("  %-12s %s" % (verb, rel))
    print("  skill slices available to append: %s"
          % (", ".join(installed) if installed else "none installed"))
    if missing:
        print("  not present (init succeeds without them): %s" % ", ".join(missing))
    trust = trust_state(home)
    print("  workspace trust entry: %s" % {True: "accepted", False: "declined",
                                           None: "absent"}[trust])
    return 0


def trust_state(home, config_dir=None):
    """A headless run on an untrusted workspace can degrade silently (delegate skill section
    2). Returns True/False/None; the wrapper records it and `--require-trust` enforces it.
    Under a configuration directory the entry lives in that directory's `.claude.json`."""
    path = os.path.join(config_home(config_dir) or os.path.expanduser("~"), ".claude.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    entry = (data.get("projects") or {}).get(os.path.realpath(home))
    if not isinstance(entry, dict) or "hasTrustDialogAccepted" not in entry:
        return None
    return bool(entry["hasTrustDialogAccepted"])


# ------------------------------------------------------------------------ routing ----------

OVERLAY_NAME = "routing.local.json"   # a user's own routing choices, in the user's layer
CORE_LIST_NAME = "core-paths"         # present in a user's copy, whose table is core


def routing_home(path):
    """The folder three levels above a routing table: `.claude` in a vault. A user's overlay and
    the core list sit there, for a table named by `--routing` too."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path))))


def routing_layers_module():
    """routing_layers.py from beside this script, imported only where an overlay or the core list
    calls for it, so this script copied on its own runs as it did without that file."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    sys.dont_write_bytecode = True   # the import must never leave a __pycache__ in the skill directory
    try:
        import routing_layers
    except ImportError as exc:
        die("a routing overlay needs routing_layers.py beside lane.py (%s)" % exc)
    return routing_layers


def load_routing(path, parse_float=float, merged=True):
    """The table at `path`, with a user's overlay merged over it unless `merged` is False. An
    overlay that fails stops here, never a fall back to the table alone."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle, parse_float=parse_float)
    except OSError as exc:
        die("routing table unreadable (%s): %s" % (path, exc))
    except ValueError as exc:
        die("routing table is not JSON (%s): %s" % (path, exc))
    if merged and os.path.lexists(os.path.join(routing_home(path), OVERLAY_NAME)):
        layers = routing_layers_module()
        try:
            data = layers.load(path, parse_float=parse_float)
        except layers.Broken as exc:
            die(str(exc))
    if data.get("schema") != SCHEMA:
        die("routing table %s is schema %r, this wrapper speaks schema %d — the v2 table with "
            "per-class option sets, grants, tools, skills, mcp and cache is required"
            % (path, data.get("schema"), SCHEMA))
    for field_name in ("order", "classes"):
        if field_name not in data:
            die("routing table %s has no `%s` field" % (path, field_name))
    for field_name in ("model", "effort"):
        if field_name not in (data.get("order") or {}):
            die("routing table %s has no `order.%s` list" % (path, field_name))
    return data


def field(row, cls, *keys):
    node = row
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            die("routing class `%s` has no `%s` field" % (cls, ".".join(keys)))
        node = node[key]
    return node


def pick(order, options, default, throttle):
    """Map the throttle onto one class's option set; strength follows the global order."""
    known = [o for o in options if o in order]
    if not known:
        die("no option in %r appears in the global order %r" % (options, order))
    strongest = max(known, key=order.index)
    weakest = min(known, key=order.index)
    return {"auto": default, "top": strongest, "cheap": weakest, "default": default,
            "fast": None, "cheap-fast": None}.get(throttle, default), weakest, strongest


def preset_model(routing, throttle):
    """The model a preset resolves to on every class, from the routing table's optional
    `preset_model` block (owner ruling 2026-09-29: `top` and `cheap` both resolve to opus until a
    stronger Claude model arrives and the owner says so), or None. A block that is not an object,
    or a named value that is not a model in `order.model`, is a premise failure, never a guess;
    throttle.py validates the same block, so the two resolvers agree on every preset."""
    block = routing.get("preset_model")
    if block is None:
        return None
    if not isinstance(block, dict):
        die("routing `preset_model` is not an object")
    value = block.get(throttle)
    if value is None:
        return None
    if not isinstance(value, str) or value not in routing["order"]["model"]:
        die("routing `preset_model.%s` value %r is not a model in `order.model`" % (throttle, value))
    return value


def resolve_tier(routing, row, cls, throttle):
    """(model, effort, model options, effort options): the row's tier under the throttle. `auto`
    and `default` both return the row's marked defaults; under `auto` they are the ANCHORS the
    head picks around per call within the two option lists (owner ruling 2026-09-07 17:0x), and
    the per-call departure is recorded by the caller, never re-resolved here. `cheap` takes the
    row's default effort and never exceeds it; an explicit `--effort` still overrides any preset
    here, recorded as `explicit`."""
    model_opts = field(row, cls, "model", "options")
    model_default = field(row, cls, "model", "default")
    effort_opts = field(row, cls, "effort", "options")
    effort_default = field(row, cls, "effort", "default")
    # Every preset reads the row's VALIDATED defaults, as throttle.py's validate_v2 does: a default
    # outside its own options is a broken premise, never a value to fall back from.
    for axis, default, options in (("model", model_default, model_opts),
                                   ("effort", effort_default, effort_opts)):
        if not isinstance(options, list) or default not in options:
            die("routing class `%s` %s default %r is not one of its options %r"
                % (cls, axis, default, options))
    model_order = routing["order"]["model"]
    effort_order = routing["order"]["effort"]
    model, model_weak, _ = pick(model_order, model_opts, model_default, throttle)
    pinned = preset_model(routing, throttle)   # owner ruling 2026-09-29: `top` and `cheap` resolve to opus
    if pinned is not None:
        if pinned in model_opts:
            model = pinned
        elif cls not in routing.get("preset_free", ()):   # a user's overlay left it out: `pick` stands
            die("routing `preset_model.%s` names %r, which class `%s` does not list among its model "
                "options %r" % (throttle, pinned, cls, model_opts))
    effort, effort_weak, _ = pick(effort_order, effort_opts, effort_default, throttle)
    if throttle == "cheap":
        # The row's default effort, never above it (register 2026-09-06: `cheap` at the ceiling
        # resolved dearer than `default`, and with `preset_model` both on opus it was dearer on
        # every class whose default sits below its ceiling); throttle.py's table, the same rule.
        effort = effort_default
    elif throttle == "fast":
        model, effort = model_default, effort_weak
    elif throttle == "cheap-fast":
        model, effort = model_weak, effort_weak
    return model, effort, model_opts, effort_opts


# ------------------------------------------------------------------- cost caps -------------

def class_cost(row, cls):
    """The dated class figures, used as an advisory reference since 2026-09-15.
    A present but malformed block is a broken premise; a missing block is valid.
    cost-figures retains the floor of three completed lanes (set by judgement, unmeasured)."""
    cost = row.get("cost")
    if cost is None:
        return None
    if not isinstance(cost, dict):
        die("routing class `%s` has a `cost` field that is not an object" % cls)
    for key in ("soft_usd", "usual_usd"):
        value = cost.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) or not math.isfinite(value) or value <= 0:
            die("routing class `%s` has a `cost` block whose `%s` is not a positive number (%r)"
                % (cls, key, value))
    return cost


def envelope_remainder(run, record_path, write_cache=True):
    """(remainder, reason, envelope, floor) for the run the lane joins: handsoff.py's
    `envelope_left` over the run record, imported lazily from beside this script so the wrapper
    still runs without it. That remainder is the envelope minus the run's spend as the gate and
    the close read it, the one the successor sizes a head on, never the head-exits' summed
    session totals (register entry 2026-09-26 02:2x). `floor` is True where that spend is a floor
    (a lane still running, a head or lane the meter could not read, a malformed record line:
    register entry 2026-09-30 03:21), the remainder then being at most the figure. The record
    path is handed on, so the figure is that of the record this call read, and
    `write_cache=False` (a dry run) leaves the run's meter cache unwritten; a handsoff.py whose
    `envelope_left` takes neither keyword is called as before, its figure read as exact. The
    remainder is None wherever no number can be had — no module, no record, no `run-open`, no
    `envelope_usd` on it, or a run whose spend could not be metered — and the reason says which,
    for the record's `hard_src`."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(here, "handsoff.py")):
        return None, "handsoff.py not found beside lane.py", None, False
    if here not in sys.path:
        sys.path.insert(0, here)
    sys.dont_write_bytecode = True   # the import must never leave a __pycache__ in the skill directory
    try:
        import handsoff
    except Exception as exc:         # a sibling script that does not import is a reason, never a crash
        return None, "handsoff.py did not import (%s)" % exc, None, False
    if not os.path.isfile(record_path):
        return None, "no run record at %s" % record_path, None, False
    events, _ = handsoff.read_record(record_path)
    if handsoff.last_index(events, ("run-open",)) < 0:
        return None, "no run-open event in the run record", None, False
    envelope_of = getattr(handsoff, "envelope_of", None)   # the latest figure: raise-envelope (2026-09-13)
    envelope = (envelope_of(events)[0] if envelope_of
                else handsoff.run_open(events).get("envelope_usd"))
    start = handsoff.last_index(events, handsoff.SESSION_EVENTS)
    spend = {}
    if "spend_out" in inspect.signature(handsoff.envelope_left).parameters:
        remainder, reason = handsoff.envelope_left(events, run, None, start, path=record_path,
                                                   spend_out=spend, write_cache=write_cache)
    else:
        remainder, reason = handsoff.envelope_left(events, run, None, start)
    if remainder is None:
        return None, reason, envelope, False
    return float(remainder), reason, float(envelope), bool(spend.get("floor"))


def require_estimate(expect, source="--expect-usd"):
    """A positive finite estimate, with no silent fallback to class figures."""
    if expect is None:
        die("%s is required: the estimate is the head's own figure" % source)
    # Validate the numeric record/cap schema separately; the caller retains its original
    # Decimal for the exact advisory. Signalling NaNs and oversized integers also refuse.
    try:
        numeric = float(expect) if not isinstance(expect, bool) and isinstance(expect, (int, float, Decimal)) else float("nan")
    except (ValueError, OverflowError):
        numeric = float("nan")
    if not math.isfinite(numeric) or numeric <= 0:
        die("%s %r is not a positive dollar figure (finite required) — the estimate is the "
            "head's own figure" % (source, expect))
    expect = numeric
    if not math.isfinite(HARD_MULTIPLIER * expect) or round(HARD_MULTIPLIER * expect, 2) <= 0:
        die("%s %r cannot produce a positive finite hard stop rounded to cents" % (source, expect))
    return float(expect)


def decimal_estimate(text):
    """Keep CLI decimal text intact for the advisory; validation remains a spawn premise."""
    try:
        return Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError("not a decimal dollar figure: %s" % text)


def estimate_advisory(expect, cost, cls):
    """Compare the original decimal text exactly; equality at either boundary is quiet."""
    if cost is None:
        return "no class figures"
    estimate, usual = Decimal(str(expect)), Decimal(str(cost["usual_usd"]))
    # Decimal multiplication is context-bound. A product needs at most the sum of its
    # operands' digit counts, so preserve every accepted digit rather than rounding at 28.
    with localcontext() as context:
        context.prec = max(len(estimate.as_tuple().digits), len(usual.as_tuple().digits)) + len(str(ESTIMATE_SANITY_FACTOR))
        above = estimate > ESTIMATE_SANITY_FACTOR * usual
        below = estimate * ESTIMATE_SANITY_FACTOR < usual
    # Keep cents padded for ordinary figures; expose extra decimals when the comparison uses them.
    dollars = lambda value: format(value, ".2f") if value.as_tuple().exponent >= -2 else format(value, "f")
    if above:
        return "estimate $%s above %d × class %s median $%s" % (
            dollars(estimate), ESTIMATE_SANITY_FACTOR, cls, dollars(usual))
    if below:
        return "estimate $%s below class %s median $%s ÷ %d" % (
            dollars(estimate), cls, dollars(usual), ESTIMATE_SANITY_FACTOR)
    return None


def hard_base(expect):
    """The head's estimate times HARD_MULTIPLIER, in cents."""
    expect = require_estimate(expect)
    base = round(HARD_MULTIPLIER * expect, 2)
    return base, "%d × estimate $%.2f" % (HARD_MULTIPLIER, expect)


def raise_only(explicit, class_hard, class_src, term="composed"):
    """Raise the composed cap only.
    An explicit figure at or below it keeps the cap and records both figures.
    `term` names the composed spawn cap or the resumed cap; the caller prints the note."""
    if explicit is None:
        return class_hard, class_src
    if float(explicit) > float(class_hard):
        return (float(explicit),
                "explicit --budget-usd (raised over %s $%.2f: %s)" % (term, class_hard, class_src))
    return class_hard, ("explicit --budget-usd $%.2f at or below %s cap $%.2f: %s cap kept (%s)"
                        % (explicit, term, class_hard, term, class_src))


def cost_caps(explicit, expect, run, record_path, term="composed", dry_run=False):
    """(hard_usd, hard_src): min(5 × estimate, envelope remainder), then raise-only.
    Without a metered remainder the estimate decides and the source names the missing
    premise. An exhausted envelope requires the existing explicit override (2026-09-07).
    Where the run's spend is a floor the remainder reads `at most` and the spend `at least`,
    the words the gate prints for the same figure; a dry run leaves the meter cache unwritten."""
    if explicit is not None and (not math.isfinite(explicit) or explicit <= 0):
        die("--budget-usd must be a positive finite dollar figure")
    base, base_src = hard_base(expect)
    remainder, reason, envelope, floor = envelope_remainder(run, record_path,
                                                            write_cache=not dry_run)
    most, least = ("at most ", "at least ") if floor else ("", "")
    if remainder is None:
        hard, src = base, "%s (envelope unmetered: %s)" % (base_src, reason)
    elif remainder <= 0:
        if explicit is None:
            die("run %s: the envelope has nothing left (remainder %s$%.2f of $%.2f: %s) — no lane "
                "runs on a cap of nothing; raise the envelope or pass --budget-usd with a reason"
                % (run, most, remainder, envelope, reason))
        return (float(explicit),
                "explicit --budget-usd (override of an exhausted envelope $%.2f, remainder %s$%.2f)"
                % (envelope, most, remainder))
    elif remainder < base:
        hard = remainder
        src = ("envelope remainder %s$%.2f (envelope $%.2f, spent %s$%.2f; below %s = $%.2f)"
               % (most, remainder, envelope, least, envelope - remainder, base_src, base))
    else:
        hard, src = base, base_src
    return raise_only(explicit, hard, src, term=term)


def soft_line(expect, soft=None, hard_usd=None):
    """The estimate is the soft line (2026-09-15), even when the envelope caps below it.
    The optional positional arguments keep older callers compatible; neither sets the line."""
    return require_estimate(expect), "expect"


def soft_check(cost, soft):
    """`soft_exceeded` for a close: True or False against a billed figure, None when the class
    has no figures or the close carries no dollar figure (a torn result, a watch close)."""
    if soft is None or isinstance(cost, bool) or not isinstance(cost, (int, float)):
        return None
    return float(cost) > float(soft)


# --------------------------------------------------------------- cost-figures (read-only) ---

def median(values):
    """The middle value; an even count takes the mean of the two middle ones."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def fold_costs(records_dir):
    """(per class figures, counts): the run store's completed lane costs folded read-only.

    One observation is a `lane-closed` event with `exit_class` `completed` and a numeric
    `total_cost_usd`; a line that does not parse is skipped and COUNTED, so a torn record
    never passes as an absence. `usual_usd` is the median, `soft_usd` the maximum × the
    headroom, both rounded to two decimals — the fold that wrote the shipped blocks. A
    directory that is not there, holds no `.jsonl`, or holds no completed close is a premise
    failure, never a clean zero. This function opens files for reading only."""
    if not os.path.isdir(records_dir):
        die("no records directory at %s" % records_dir)
    files = sorted(globmod.glob(os.path.join(records_dir, "*.jsonl")))
    if not files:
        die("no .jsonl record file under %s" % records_dir)
    costs, dates, torn, closes = {}, {}, 0, 0
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError as exc:
            die("record file unreadable (%s): %s" % (path, exc))
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                torn += 1
                continue
            if not isinstance(event, dict) or event.get("event") != "lane-closed":
                continue
            if event.get("exit_class") != "completed":
                continue
            billed = event.get("total_cost_usd")
            if isinstance(billed, bool) or not isinstance(billed, (int, float)):
                continue
            cls = event.get("class") or "unnamed-class"
            costs.setdefault(cls, []).append(float(billed))
            stamp = event.get("ts")
            if isinstance(stamp, str) and len(stamp) >= 10:
                dates.setdefault(cls, []).append(stamp[:10])
            closes += 1
    if not closes:
        die("no completed lane-closed with a numeric total_cost_usd in %d record file(s) "
            "under %s" % (len(files), records_dir))
    folded = {}
    for cls, values in costs.items():
        window = sorted(dates.get(cls) or [])
        folded[cls] = {"n": len(values),
                       "window": "%s..%s" % (window[0], window[-1]) if window else "no ts",
                       "usual_usd": round(median(values), 2),
                       "max_usd": round(max(values), 2),
                       "soft_usd": round(max(values) * SOFT_HEADROOM, 2)}
    return folded, {"files": len(files), "closes": closes, "torn": torn}


def cost_verdict(row, block):
    """`--check`'s word for one class: `same`, `drift (…)`, `no block (n < 3)` or `fold due`.
    The table's figures are on the left of each arrow, the fold's on the right; a class the
    fold has too few closes for carries no block, so a block on such a class is a drift with
    `none` on the right. Returns (verdict, is a drift)."""
    n = row["n"] if row else 0
    if n < COST_FLOOR_N:
        if block is None:
            return "no block (n < %d)" % COST_FLOOR_N, False
        return ("drift (soft $%.2f → none · usual $%.2f → none · n %s → %d)"
                % (float(block["soft_usd"]), float(block["usual_usd"]),
                   block.get("n", "absent"), n), True)
    if block is None:
        return "fold due (n=%d ≥ %d, no block)" % (n, COST_FLOOR_N), True
    same = (round(float(block["soft_usd"]), 2) == row["soft_usd"]
            and round(float(block["usual_usd"]), 2) == row["usual_usd"]
            and block.get("n") == row["n"])
    if same:
        return "same", False
    return ("drift (soft $%.2f → $%.2f · usual $%.2f → $%.2f · n %s → %d)"
            % (float(block["soft_usd"]), row["soft_usd"], float(block["usual_usd"]),
               row["usual_usd"], block.get("n", "absent"), row["n"]), True)


def cost_source_text():
    """The `source` sentence a folded block carries: what the figures are, from where, on what
    day and by which hand — so a block read a month later carries its own derivation."""
    return ("the run store's spawn records: the completed lane-closed events of this class with "
            "a numeric total_cost_usd, folded %s by `lane.py cost-figures --fold`; usual_usd is "
            "their median, soft_usd their maximum plus %g %% headroom (token-efficiency findings "
            "2026-09-07, proposal T3), both rounded to two decimals; a class with fewer than "
            "%d completed lanes carries no block"
            % (time.strftime("%Y-%m-%d"), round((SOFT_HEADROOM - 1) * 100, 2), COST_FLOOR_N))


def file_indent(raw, path):
    """The indent the file itself keeps, read from its own first indented line.

    Reading the indent from the file means a fold touches the fields it changes and nothing
    else. A file with no indented line at all is a premise failure: there is no width to keep."""
    found = re.search(r"^([ \t]+)\S", raw, re.M)
    if not found:
        die("routing table %s has no indented line to read an indent from — it is not the "
            "pretty-printed table this fold writes back" % path)
    return found.group(1)


def fold_source(routing_path):
    """(path, raw, data): the one file a fold reads and writes. It is never the merged record,
    whose rows would be written back into the wrong file. A vault folds into its table. A user's
    copy holds the core list, its table is core, and the fold goes to the overlay, where it writes
    `classes.<name>.cost` and nothing else."""
    if os.path.lexists(os.path.join(routing_home(routing_path), CORE_LIST_NAME)):
        layers = routing_layers_module()
        try:
            return layers.fold_source(routing_path)
        except layers.Broken as exc:
            die(str(exc))
    return (routing_path, read_text(routing_path, "the routing table"),
            load_routing(routing_path, merged=False))


def fold_into_routing(path, folded, data, raw):
    """Write each drifted class's cost block into the file `fold_source` named, and return
    (classes written, the indent kept).

    What is written: for a class at or above the floor, `soft_usd`, `usual_usd`, `n`, `window`
    and `source`, into the block already there (so any other key of that block, and the order
    of every key in the file, survive) or as a new `cost` block at the end of the class's own
    object where it had none. For a class the table carries a block for and the fold now counts
    fewer than the floor of completed lanes, the block is REMOVED: that is what `--check` calls
    a drift to `none`. A class the fold has no figures for at all is not touched — this reads
    the run store, and a class absent from the store is unmeasured, not free.

    How it is written: `json.dumps` at the file's own indent, never `sort_keys` (the table's key
    order is meaningful and is the file's, not this script's), `ensure_ascii=False` (the table
    holds `·`, `×` and `§`, and escaping them would rewrite every line that carries one), and
    through `write_atomic`, so a reader sees the old file or the new one and never a half-written
    one. Folding a file twice in a row therefore leaves it byte-identical the second time."""
    classes = data.get("classes") or {}
    written = []
    for cls in sorted(classes):
        row = classes[cls]
        if not isinstance(row, dict):
            continue
        figures = folded.get(cls)
        block = row.get("cost")
        if figures is None:
            continue
        if figures["n"] < COST_FLOOR_N:
            if block is not None:
                del row["cost"]
                written.append("%s (block removed: n=%d below the floor of %d)"
                               % (cls, figures["n"], COST_FLOOR_N))
            continue
        verdict, is_drift = cost_verdict(figures, class_cost(row, cls))
        if not is_drift:
            continue
        if not isinstance(block, dict):
            block = {}
            row["cost"] = block
        block["soft_usd"] = figures["soft_usd"]
        block["usual_usd"] = figures["usual_usd"]
        block["n"] = figures["n"]
        block["window"] = figures["window"]
        block["source"] = cost_source_text()
        written.append("%s (%s)" % (cls, verdict))
    indent = file_indent(raw, path)
    if written:
        if os.path.basename(path) == OVERLAY_NAME:   # the rows `fold_source` added and nothing filled
            data["classes"] = {cls: row for cls, row in classes.items() if row}
        write_atomic(path, json.dumps(data, indent=indent, ensure_ascii=False) + "\n")
    return written, indent


def cost_figures_report(folded, counts, table, check, records_dir, fmt):
    """(lines, drifted): what `cost-figures` prints. One line per class, then the run's own
    count line — the positive control of the fold: a zero anywhere in it is visible beside the
    files and closes it was computed from. With `--check` the classes are the union of the
    fold's and the table's, so a block on a class with no completed close is seen too."""
    names = sorted(set(folded) | (set(table) if check else set()))
    drifted, rows, lines = False, [], []
    for cls in names:
        row = folded.get(cls)
        n = row["n"] if row else 0
        if n < COST_FLOOR_N:
            text = "%s · n=%d (below the floor of three: no block)" % (cls, n)
        else:
            text = ("%s · n=%d · %s · usual $%.2f · max $%.2f · soft $%.2f"
                    % (cls, n, row["window"], row["usual_usd"], row["max_usd"],
                       row["soft_usd"]))
        entry = dict(row or {"n": 0})
        entry["class"] = cls
        if check:
            verdict, is_drift = cost_verdict(row, table.get(cls))
            drifted = drifted or is_drift
            text += " · %s" % verdict
            entry["verdict"] = verdict
        rows.append(entry)
        lines.append(text)
    tail = ("cost-figures: %d record file(s), %d completed close(s), %d torn line(s)"
            % (counts["files"], counts["closes"], counts["torn"]))
    if fmt == "json":
        return [json.dumps({"records_dir": records_dir, "files": counts["files"],
                            "completed": counts["closes"], "torn": counts["torn"],
                            "floor_n": COST_FLOOR_N, "headroom": SOFT_HEADROOM,
                            "checked": bool(check), "drift": drifted, "classes": rows},
                           indent=1, sort_keys=True)], drifted
    return lines + [tail], drifted


# ------------------------------------------------------------------ definition -------------

def frontmatter_problem(text):
    """Why a definition's frontmatter cannot be read, or None (review CR-B4L finding 3). Two shapes
    make the readers here (parse_frontmatter, frontmatter_list) see no frontmatter at all, and so a
    definition that restricts nothing and allows every tool: a block opened by `---` that never
    closes, and a `---` opener behind a byte-order mark. A definition with no opener is valid
    absence and gives None."""
    if text.startswith("\ufeff") and text.lstrip("\ufeff").startswith("---"):
        return "opens its frontmatter behind a byte-order mark, where the reader cannot see it"
    if text.startswith("---") and text.find("\n---", 3) == -1:
        return "opens a frontmatter block with `---` that never closes"
    return None


def thin_definition(vault, cls, tools, description_fallback, allowed_out=None):
    """The class's own body with a thin frontmatter: the row's tools and skills, no `effort:`
    (ignored on the headless path).
    `allowed_out`, a list, receives the tools the source definition allows (definition_allows),
    read from the same bytes the returned hash covers. A frontmatter that cannot be read refuses
    (exit 2, before any record line or process): read as absent, its restrictions would vanish and
    the lane would gain the tools they block (frontmatter_problem)."""
    path = os.path.join(vault, ".claude", "agents", "%s.md" % cls)
    if not os.path.isfile(path):
        die("no definition for class `%s` at %s" % (cls, path))
    text = read_text(path, "the class definition")
    problem = frontmatter_problem(text)
    if problem:
        die("definition %s %s: the tools it allows and blocks cannot be read, and a parse failure is "
            "never taken for no restriction — close the block (a `---` line after its fields) or "
            "remove what precedes the opener" % (path, problem))
    if allowed_out is not None:
        allowed_out.extend(definition_allows(text))
    fields, body = parse_frontmatter(text)
    if not body.strip():
        die("definition %s has an empty body" % path)
    # Do not depend on a `skills:` key in the inline --agents JSON.
    # The slices travel in the appended system-prompt file instead.
    agent = {"description": fields.get("description") or description_fallback,
             "prompt": body.rstrip() + "\n",
             "tools": list(tools)}
    return path, sha(text), agent


def definition_markdown(cls, agent, model, effort):
    lines = ["---", "name: %s" % cls, "description: %s" % agent["description"],
             "tools: %s" % ", ".join(agent["tools"])]
    lines += ["# model and effort are spawn flags, not definition fields, on the headless path",
              "# spawned with: model %s, effort %s" % (model, effort), "---", "",
              agent["prompt"]]
    return "\n".join(lines)


# ---------------------------------------------------------------------- grants -------------

def split_placeholders(values):
    """A routing row states some directories literally and leaves the rest to the call. A
    `<…>` value is one of those per-call slots, not a path."""
    literals, slots = [], []
    for value in values or []:
        value = str(value)
        (slots if ("<" in value or ">" in value) else literals).append(value)
    return literals, slots


def file_sha(path):
    """The sha256 of a file's bytes, or None when it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 16), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def entry_for(value, vault, what, files_ok):
    """One grant: its spelling as given (absolute, symlinks unresolved), its real path and
    whether it is a file. Vault-relative names resolve against the vault."""
    given = os.path.expanduser(str(value))
    if not os.path.isabs(given):
        given = os.path.join(vault, given)
    given = os.path.abspath(given)
    real = os.path.realpath(given)
    if not os.path.exists(real):
        die("%s does not exist: %s" % (what, given))
    if os.path.isdir(real):
        return {"given": given, "real": real, "file": False}
    if not files_ok:
        die("%s must be a directory, not a file: %s (grant its directory instead)"
            % (what, given))
    return {"given": given, "real": real, "file": True}


def dir_entry(path):
    """An entry for a directory the wrapper itself names (the input directory, the vault root)."""
    given = os.path.abspath(path)
    return {"given": given, "real": os.path.realpath(given), "file": False}


def add_entry(target, entry):
    if entry["real"] not in [e["real"] for e in target]:
        target.append(entry)


def resolve_entries(values, vault, what, files_ok):
    out = []
    for value in values or []:
        add_entry(out, entry_for(value, vault, what, files_ok))
    return out


def reals(entries):
    return [e["real"] for e in entries]


def files_of(entries):
    return [e["real"] for e in entries if e["file"]]


def spellings(given, real):
    return [real] if given == real else [real, given]


SYMLINK_ROOTS = [os.path.expanduser("~/.llm-wiki")]   # roots the vault addresses through a symlink


def add_unique(target, items):
    for item in items:
        if item not in target:
            target.append(item)


def add_dirs_for(entries):
    """The `--add-dir` values: each entry's directory (a file's parent) in every spelling,
    real path first. The harness compares the spelling a tool call uses, so a symlinked path
    granted in one spelling alone cannot authorise the other."""
    out = []
    for entry in entries:
        real_dir = os.path.dirname(entry["real"]) if entry["file"] else entry["real"]
        given_dir = os.path.dirname(entry["given"]) if entry["file"] else entry["given"]
        add_unique(out, spellings(given_dir, real_dir))
        # a grant given as the real path still gets the symlinked spelling a brief may use
        # Resolve both path spellings so a symlink cannot make an authorised grant unreachable.
        for root in SYMLINK_ROOTS:
            if os.path.islink(root):
                real_root = os.path.realpath(root)
                if real_dir == real_root or real_dir.startswith(real_root + os.sep):
                    add_unique(out, [root + real_dir[len(real_root):]])
    return out


def allow_pattern(path, is_dir):
    """A harness permission-rule path: a doubled leading separator marks an absolute
    filesystem path (a single one would be project-relative); a directory covers everything
    beneath it."""
    pattern = os.sep + os.sep + path.lstrip(os.sep)
    return pattern + (os.sep + "**" if is_dir else "")


def settings_for(home, write_entries, search=False):
    """The per-spawn settings: the home's hooks plus Edit and Write allow rules for every
    write grant, in both spellings (design D18), and the `WebSearch` rule where `search` says the
    lane gets that tool (2026-10-10; WebFetch never). Sensitive-path restrictions still bind;
    use the authorised shell write channel when structured edits cannot reach a granted path."""
    base_path = os.path.join(home, "lane-settings.json")
    try:
        with open(base_path, "r", encoding="utf-8") as handle:
            base = json.load(handle)
    except (OSError, ValueError) as exc:
        die("lane settings unreadable (%s): %s" % (base_path, exc))
    hooks = base.get("hooks") if isinstance(base, dict) else None
    if not hooks:
        die("lane settings %s carry no hooks — run `lane.py init`" % base_path)
    allow = []
    for entry in write_entries:
        for spelling in spellings(entry["given"], entry["real"]):
            pattern = allow_pattern(spelling, not entry["file"])
            add_unique(allow, ["Edit(%s)" % pattern, "Write(%s)" % pattern])
    if search:
        add_unique(allow, ["WebSearch"])
    out = {"hooks": hooks}
    if allow:
        out["permissions"] = {"allow": allow}
    return out, allow


# ---------------------------------------------------------------------- controls -----------
# The brief's declarations: the lines the wrapper reads and checks before a spawn (design D19 for
# the controls; register 2026-09-17 22:19 for the grammar; 2026-09-14 00:06 and 2026-09-19 10:18 for
# the declared inputs; 2026-09-20 17:01 for an empty input; 2026-09-10 02:49 for a rubric's folders;
# 2026-09-20 01:58 for a control on the lane's own report; 2026-09-25 04:3x for the staged copy).
#
# One grammar for every marker. A marker that stands UNQUOTED on a line declares, wherever it
# stands — at the start, after a bullet, after a label (`VERIFICATION: CONTROL+: …`, the labelled
# form a rehearsal once ran unchecked) or after prose — and its declaration runs to the line's end;
# one line holds one such marker. A declaration with nothing after its marker refuses like a
# malformed one: a bare marker that passed with zero controls was the defect of 2026-09-17. A
# marker in a fenced code block or a block quote declares nothing, and neither does one QUOTED in
# prose — inside a code span, inside double quotes, or right after a quote mark — unless the quoted
# form names files that exist: then it is read as the declaration it spells out, its body ending at
# the closing quote (briefs have written real controls in backticks with prose after them). Any
# other quoted form is a mention, said on stderr, so a brief may quote the form without being
# refused (the other half of 2026-09-17) and a quoted control is never dropped unseen. A code fence
# that never closes and would hide a marker refuses.
#
# A grammar keyed on the line's start alone would miss controls written after prose, and one that
# reads every quoted form as a mention would drop those in backticks; this one reads both as before.
DECL_MARKERS = ("CONTROL+", "READ+", "RUBRIC+", "WEB+")
STAGED_TOKEN = "<<STAGED_COPY>>"   # a staged copy's path, substituted after staging (codex-lane.py --stage-from)
REPORT_TOKEN = "<<REPORT>>"        # this pass's own report, as a CONTROL+ file: checked at the close
_MARKER_ALT = "|".join(re.escape(marker) for marker in DECL_MARKERS)
MARKER_ANY_RE = re.compile(r"(?:" + _MARKER_ALT + r"):")
FENCE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<rest>.*)$")
QUOTE_PAIRS = {"`": "`", '"': '"', "'": "'", "“": "”", "‘": "’", "«": "»"}
DECL_FORMS = {"CONTROL+": "CONTROL+: <phrase> in <file>", "READ+": "READ+: <path>",
              "RUBRIC+": "RUBRIC+: <rubric file> in <reviewers' tree>",
              "WEB+": "WEB+: <the web work the lane must do>"}
# What a Claude lane's tools reach beyond its class row (register 2026-09-29 21:08): `--tools` sets the
# tool LIST, never a permission, and with prompts off a listed tool no rule admits is refused at every
# call. The read tools need no rule inside the add-dirs; Bash is admitted by the lane fence's explicit
# allow; Edit and Write by settings_for's rules, which exist on a write grant only; WebSearch by its
# rule there, which exists where the class definition allows it (2026-10-10). Nothing admits WebFetch,
# and no other tool is known to work unprompted, so each refuses the spawn.
TOOLS_UNPROMPTED = ("Read", "Grep", "Glob", "LS", "Bash")
TOOLS_ON_WRITE_GRANT = ("Edit", "Write")
TOOLS_WEB = ("WebSearch", "WebFetch")


def unwrap(text):
    text = text.strip()
    if 1 < len(text) and text[0] == text[-1] and text[0] in "\"'`":
        return text[1:-1]
    return text


def quote_opener(line, index):
    """The quote mark opening the quoted span that holds position `index`, or None where the
    position is not quoted: a code span (an odd count of backticks before it), a double-quoted span
    (an odd count of straight double quotes, or more opening curly ones than closing), or a quote
    mark right before it. Single quotes are not counted as spans: in English they are apostrophes
    as often as quotes."""
    before = line[:index]
    if before.count("`") % 2 == 1:
        return "`"
    if before.count('"') % 2 == 1:
        return '"'
    if before.count("“") > before.count("”"):
        return "“"
    if before and before[-1] in QUOTE_PAIRS:
        return before[-1]
    return None


def quoted_at(line, index):
    """Whether the marker at `index` sits inside quoted prose (quote_opener)."""
    return quote_opener(line, index) is not None


def split_in(body):
    """(left, right) on the LAST ` in `, each unwrapped, so a phrase may contain the word and a
    path may not; ("", "") when the body has no ` in `."""
    cut = body.rfind(" in ")
    if cut == -1:
        return "", ""
    return unwrap(body[:cut]), unwrap(body[cut + 4:])


def plain_path(text, vault):
    """The absolute path a declared plain path names (a relative one against the vault), or None
    for a token form, which names no file before the spawn."""
    if STAGED_TOKEN in text or REPORT_TOKEN in text or not text:
        return None
    given = os.path.expanduser(text)
    if not os.path.isabs(given):
        if not vault:
            return None
        given = os.path.join(vault, given)
    return os.path.abspath(given)


def quoted_declares(marker, body, vault):
    """Whether a QUOTED form spells out a declaration it means: its plain paths all exist. A quoted
    form naming no existing path is a mention — the form documented, a fold note quoting a critic —
    and a quoted web declaration is always one."""
    if marker == "CONTROL+":
        phrase, path = split_in(body)
        path = plain_path(path, vault)
        return bool(phrase) and path is not None and os.path.isfile(path)
    if marker == "READ+":
        path = plain_path(unwrap(body), vault)
        return path is not None and os.path.exists(path)
    if marker == "RUBRIC+":
        rubric, tree = split_in(body)
        rubric, tree = plain_path(rubric, vault), plain_path(tree, vault)
        return rubric is not None and tree is not None and os.path.isfile(rubric) and os.path.isdir(tree)
    return False


def declare(out, number, line, marker, body):
    """One declaration into `out`, refusing an empty or malformed one."""
    if not body:
        die("brief line %d: an empty %s declaration (want `%s`): %s"
            % (number, marker, DECL_FORMS[marker], line.strip()))
    if marker == "CONTROL+":
        phrase, path = split_in(body)
        if not phrase or not path:
            die("brief line %d: malformed control line (want `CONTROL+: <phrase> in <file>`): %s"
                % (number, line.strip()))
        out["controls"].append({"line": number, "phrase": phrase, "file": path})
    elif marker == "READ+":
        out["reads"].append({"line": number, "path": unwrap(body)})
    elif marker == "RUBRIC+":
        rubric, tree = split_in(body)
        if not rubric or not tree:
            die("brief line %d: malformed RUBRIC+ line (want `%s`): %s"
                % (number, DECL_FORMS[marker], line.strip()))
        out["rubrics"].append({"line": number, "rubric": rubric, "tree": tree})
    else:
        out["web"].append({"line": number, "what": body})


def parse_declarations(brief, vault=None):
    """Every declaration of a brief under the grammar above, as
    {"controls": [...], "reads": [...], "rubrics": [...], "web": [...]}, each entry carrying its
    line number. Refuses (exit 2) on an empty or malformed declaration, two unquoted markers on one
    line, and an unclosed code fence that would hide a marker. With `vault`, a quoted form that names
    existing files is read as the declaration it spells out; any other quoted form is a mention,
    said on stderr when it holds more than the bare marker."""
    out = {"controls": [], "reads": [], "rubrics": [], "web": []}
    fence, fence_line, hidden = None, 0, []
    for number, line in enumerate((brief or "").splitlines(), 1):
        opened = FENCE_RE.match(line)
        if fence is not None:
            if opened and opened.group("fence")[0] == fence[0] \
                    and len(opened.group("fence")) >= len(fence) and not opened.group("rest").strip():
                fence, hidden = None, []
            elif MARKER_ANY_RE.search(line):
                hidden.append(number)
            continue
        if opened:
            fence, fence_line = opened.group("fence"), number
            continue
        if line.lstrip().startswith(">"):
            continue                   # a block quote quotes; it never declares
        found = list(MARKER_ANY_RE.finditer(line))
        if not found:
            continue
        unquoted = [m for m in found if quote_opener(line, m.start()) is None]
        if len(unquoted) > 1:
            die("brief line %d: %d markers stand unquoted on one line, and a line holds one "
                "declaration: %s" % (number, len(unquoted), line.strip()[:240]))
        for match in found:
            marker = match.group(0)[:-1]
            opener = quote_opener(line, match.start())
            if opener is None:
                declare(out, number, line, marker, line[match.end():].strip())
                continue
            close = line.find(QUOTE_PAIRS[opener], match.end())
            body = line[match.end():close if close != -1 else len(line)].strip()
            if body and quoted_declares(marker, body, vault):
                declare(out, number, line, marker, body)
            elif body:
                sys.stderr.write("lane.py: note: brief line %d quotes a %s form that names no existing "
                                 "file, so it is read as a mention, not a declaration; write it unquoted "
                                 "to declare it\n" % (number, marker))
    if fence is not None and hidden:
        die("brief line %d opens a code fence that never closes, and it would hide the marker on "
            "line(s) %s: close the fence, or the declaration is never read"
            % (fence_line, ", ".join(str(n) for n in hidden)))
    return out


def parse_controls(brief):
    """The CONTROL+ declarations alone (parse_declarations' `controls`)."""
    return parse_declarations(brief)["controls"]


def temp_read_roots():
    """The read roots the fence grants every lane besides its own: /tmp in both spellings and /dev."""
    return sorted({"/tmp", os.path.realpath("/tmp"), "/dev"})


def lane_read_roots(tools, grants, input_dir, home):
    """The real roots a lane's tools can read, against which its declared inputs and controls are
    checked (review CR-B4L finding 4). The file tools reach the working directory (the lane home)
    and the `--add-dir` grants, the input directory among them (`--restricted`). The fence's
    temporary roots (temp_read_roots: /tmp in both spellings, /dev) are a shell grant, reached
    through Bash alone (lane-fence.py), so they count only where the tool list holds Bash. A planner
    (no Bash) given an ungranted /tmp input is therefore refused, as its Read would be."""
    roots = list(grants) + [input_dir, home]
    if "Bash" in (tools or []):
        roots += temp_read_roots()
    return roots


def within_roots(real, roots):
    """Whether a real path lies inside one of the real roots, on a component boundary."""
    for root in roots or []:
        root = root.rstrip(os.sep) or os.sep
        if real == root or real.startswith(root if root == os.sep else root + os.sep):
            return True
    return False


def resolve_declared(text, vault, line, what, stage=None):
    """(absolute path as declared, real path, staged?) for a declared path. A relative path
    resolves against the vault, as a grant does. `<<STAGED_COPY>>` resolves into the stage path the
    caller passes — the actual copy, after staging — and refuses where none applies; a token-derived
    path that escapes the copy through `..` or a symlink refuses, since it would certify something
    other than the copy."""
    if STAGED_TOKEN in text:
        if not text.startswith(STAGED_TOKEN):
            die("brief line %d: %s may only lead a path: %s" % (line, STAGED_TOKEN, text))
        rest = text[len(STAGED_TOKEN):]
        if rest and not rest.startswith("/"):
            die("brief line %d: %s is followed by `/` or nothing: %s" % (line, STAGED_TOKEN, text))
        if stage is None:
            die("brief line %d: the %s %s names a staged copy, and this spawn has none (codex-lane.py "
                "--stage-from makes one; lane.py never does)" % (line, what, text))
        stage_given = os.path.abspath(stage)
        given = os.path.normpath(stage_given + rest)
        stage_real = os.path.realpath(stage_given)
        real = os.path.realpath(given)
        if not within_roots(given, [stage_given]) or not within_roots(real, [stage_real]):
            die("brief line %d: the %s %s leaves the staged copy %s (through `..` or a symlink), so "
                "it cannot certify the copy" % (line, what, text, stage_given))
        return given, real, True
    given = os.path.expanduser(text)
    if not os.path.isabs(given):
        given = os.path.join(vault, given)
    given = os.path.abspath(given)
    return given, os.path.realpath(given), False


def outside_grants(real, roots, line, what, given):
    die("brief line %d: the %s %s lies outside the lane's read grants, so the lane cannot reach it "
        "— grant it (--grant, or --write for a path it also writes) or drop it from the brief "
        "(read roots: %s)" % (line, what, given, ", ".join(roots)))


def check_controls(controls, vault, roots=None, stage=None, report=None):
    """Each phrase as a fixed string in its file; a zero match refuses the spawn (design D19).
    With `roots` (lane.py's read grants), a control file outside them refuses: the lane must be
    able to hit the control it is given. A control on `<<REPORT>>` is not checked here: it names
    this pass's own report (`report`), which does not exist until the close, and is returned as
    pending for the close to check (register 2026-09-20 01:58). Returns (checked, pending); a caller
    that reads a list alone takes `check_controls(...)[0]`."""
    checked, pending = [], []
    for control in controls:
        name = control["file"]
        if REPORT_TOKEN in name:
            if name != REPORT_TOKEN:
                die("brief line %d: %s stands alone as a control's file (this pass's report): %s"
                    % (control["line"], REPORT_TOKEN, name))
            if not report:
                die("brief line %d: a control on %s needs a report this call writes, and it writes "
                    "none" % (control["line"], REPORT_TOKEN))
            pending.append({"line": control["line"], "phrase": control["phrase"], "target": "report",
                            "report": report})
            continue
        given, path, staged = resolve_declared(name, vault, control["line"], "control file", stage)
        if not os.path.isfile(path):
            die("brief line %d: control file not found%s: %s"
                % (control["line"], " in the staged copy" if staged else "", name))
        if roots is not None and not staged and not within_roots(path, roots):
            outside_grants(path, roots, control["line"], "control file", given)
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            count = handle.read().count(control["phrase"])
        if count == 0:
            die("brief line %d: control phrase %r matches nothing in %s — the spawn is refused"
                % (control["line"], control["phrase"], path))
        entry = {"phrase": control["phrase"], "file": path, "matches": count}
        if staged:
            entry["staged"] = True
        checked.append(entry)
    return checked, pending


def dir_has_content(path):
    """Whether a directory holds at least one regular file of non-zero size anywhere beneath it.
    Symlinked directories are not followed; a symlinked file counts by what it points to."""
    for base, dirs, names in os.walk(path):
        for name in names:
            full = os.path.join(base, name)
            try:
                if os.path.isfile(full) and os.path.getsize(full) > 0:
                    return True
            except OSError:
                continue
    return False


def require_input(given, real, line, what):
    """A declared input that a lane can use: it exists, is readable, a regular file holds bytes and
    a directory holds at least one file with content. Returns its kind and size for the record."""
    try:
        info = os.stat(real)
    except OSError as exc:
        die("brief line %d: the %s %s cannot be read (%s)" % (line, what, given, exc.strerror or exc))
    if stat.S_ISDIR(info.st_mode):
        if not os.access(real, os.R_OK | os.X_OK):
            die("brief line %d: the %s %s is a directory the wrapper cannot list" % (line, what, given))
        if not dir_has_content(real):
            die("brief line %d: the %s %s holds no file with content — an empty folder supplies "
                "nothing the brief promises" % (line, what, given))
        return "directory", None
    if not stat.S_ISREG(info.st_mode):
        die("brief line %d: the %s %s is neither a regular file nor a directory" % (line, what, given))
    if not os.access(real, os.R_OK):
        die("brief line %d: the %s %s is not readable" % (line, what, given))
    if info.st_size == 0:
        die("brief line %d: the %s %s is empty (0 bytes) — a transfer that leaves an empty file passes "
            "an existence check, so the spawn is refused (register 2026-09-20 17:01)" % (line, what, given))
    return "file", info.st_size


# A relative folder a rubric names: segments ending in `/`, standing alone — not the tail of an
# absolute path or a URL (no `/`, `:`, `~`, `$`, `.` or word character before it) and not the head of
# a longer path (no word character or `-` after it).
RUBRIC_FOLDER_RE = re.compile(r"(?<![\w./~$:@-])((?:[A-Za-z0-9_][A-Za-z0-9_.-]*/)+)(?![\w-])")


def rubric_folders(text):
    """The relative folders a rubric names, in order of first mention, each once."""
    seen = []
    for match in RUBRIC_FOLDER_RE.finditer(text or ""):
        folder = match.group(1)
        if folder not in seen:
            seen.append(folder)
    return seen


def check_inputs(declared, vault, roots=None, stage=None):
    """The READ+ and RUBRIC+ declarations of a brief, checked before the spawn (each refusal exit 2,
    no record line), as the `inputs_checked` record field.

    READ+ <path>: the input exists, is readable, a regular file holds bytes (a zero-byte file
    refuses with its path: a transfer that leaves one passes an existence check, register 2026-09-20
    17:01) and a directory holds at least one file with content; with `roots` it lies inside the read
    grants on a component boundary, its real path tested, so a symlink out of a grant refuses.

    RUBRIC+ <rubric> in <tree>: every relative folder the rubric names exists under the tree and
    holds a file with content (register 2026-09-10 02:49: a rubric promised summaries under a folder
    the reviewers' tree did not carry, and an empty folder would have passed an existence check);
    with `roots` the rubric and the tree lie inside the read grants. A rubric naming no folder is
    recorded with an empty list, never read as a clean tree.

    A `<<STAGED_COPY>>` path resolves into `stage`, the actual copy, and is checked there."""
    out = []
    for read in declared.get("reads") or []:
        given, real, staged = resolve_declared(read["path"], vault, read["line"], "declared input", stage)
        if not os.path.lexists(given):
            die("brief line %d: the declared input %s does not exist%s"
                % (read["line"], given, " in the staged copy" if staged else ""))
        kind, size = require_input(given, real, read["line"], "declared input")
        if roots is not None and not staged and not within_roots(real, roots):
            outside_grants(real, roots, read["line"], "declared input", given)
        entry = {"line": read["line"], "path": real, "kind": kind}
        if size is not None:
            entry["bytes"] = size
        if staged:
            entry["staged"] = True
        out.append(entry)
    for rub in declared.get("rubrics") or []:
        given, real, staged = resolve_declared(rub["rubric"], vault, rub["line"], "rubric", stage)
        if not os.path.lexists(given):
            die("brief line %d: the rubric %s does not exist" % (rub["line"], given))
        kind, _size = require_input(given, real, rub["line"], "rubric")
        if kind != "file":
            die("brief line %d: the rubric %s is a directory, not a file" % (rub["line"], given))
        tree_given, tree_real, tree_staged = resolve_declared(rub["tree"], vault, rub["line"],
                                                              "reviewers' tree", stage)
        if not os.path.isdir(tree_real):
            die("brief line %d: the reviewers' tree %s is not a directory" % (rub["line"], tree_given))
        if roots is not None:
            if not staged and not within_roots(real, roots):
                outside_grants(real, roots, rub["line"], "rubric", given)
            if not tree_staged and not within_roots(tree_real, roots):
                outside_grants(tree_real, roots, rub["line"], "reviewers' tree", tree_given)
        try:
            with open(real, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as exc:
            die("brief line %d: the rubric %s cannot be read (%s)" % (rub["line"], given, exc))
        folders = rubric_folders(text)
        missing = []
        for folder in folders:
            target = os.path.join(tree_real, folder)
            if not os.path.isdir(target):
                missing.append("%s (absent)" % folder)
            elif not within_roots(os.path.realpath(target), [tree_real]):
                missing.append("%s (a link out of the tree)" % folder)
            elif not dir_has_content(target):
                missing.append("%s (no file with content)" % folder)
        if missing:
            die("brief line %d: the rubric %s names %d folder(s) the reviewers' tree %s does not "
                "carry with content: %s — build them or strike them from the rubric before a reviewer "
                "spawns" % (rub["line"], given, len(missing), tree_given, "; ".join(missing)))
        out.append({"line": rub["line"], "rubric": real, "tree": tree_real, "folders": folders})
    return out


# A WEB+ declaration that needs search alone opens with `search:`; any other needs page fetches.
# Set by judgement, unmeasured: the opener is explicit so that an unmarked declaration stays refused
# on a Claude lane, as every one was before WebSearch was admitted.
WEB_SEARCH_RE = re.compile(r"search\s*:", re.IGNORECASE)


def web_search_only(web):
    """True where a WEB+ declaration needs search alone (its text opens with `search:`)."""
    return bool(WEB_SEARCH_RE.match(web.get("what") or ""))


def refuse_web(declared, how, search_ok=False):
    """WEB+ declares web work the lane must do (register 2026-09-14 00:06, the recurrence of
    2026-10-04: a write lane told to check cited pages had no web access and wrote nothing). `how`
    is None where the spawn can grant it; otherwise the refusal names what grants it. With
    `search_ok`, a declaration that needs search alone passes (`web_search_only`)."""
    for web in declared.get("web") or []:
        if how and not (search_ok and web_search_only(web)):
            die("brief line %d declares web work (%s), and %s" % (web["line"], web["what"][:120], how))


def deferred_verdicts(pending, report_path, text, fresh, persisted, closed_as):
    """The verdict on each control a pass declared on its own report (`<<REPORT>>`), at its close:
    `checked` (the phrase is in this pass's fresh report, which was written), `failed` (a fresh,
    written report without it) or `unverified` (no completed pass, no fresh report text, a report
    that was not written, or a declaration naming another report). Only the exact current pass's
    report counts, from the response this pass returned: an earlier pass's report, a sibling's, a
    file on disk and the wrapper's own placeholder text never stand in for it."""
    out = []
    for control in pending or []:
        entry = {"line": control.get("line"), "phrase": control.get("phrase"), "target": "report",
                 "report": control.get("report"), "result": "unverified", "matches": None, "why": None}
        phrase = control.get("phrase")
        if not isinstance(phrase, str) or not phrase:
            entry["why"] = "the pending control carries no phrase"
        elif closed_as not in ("completed", "watch-closed"):
            entry["why"] = "the pass closed %s, so its report is not a finished response" % closed_as
        elif control.get("report") != report_path:
            entry["why"] = "the declaration names %s, not this pass's report %s" % (
                control.get("report"), report_path)
        elif not fresh:
            entry["why"] = "this pass returned no report text of its own"
        elif not persisted:
            entry["why"] = "this pass's report was not written to %s" % report_path
        else:
            count = (text or "").count(phrase)
            entry["matches"] = count
            entry["result"] = "checked" if count else "failed"
            if not count:
                entry["why"] = "the phrase is not in this pass's report"
        out.append(entry)
    return out


def deferred_text(verdicts):
    """The summary clause for a close's report controls, or "" when the pass declared none."""
    if not verdicts:
        return ""
    counts = {}
    for verdict in verdicts:
        counts[verdict["result"]] = counts.get(verdict["result"], 0) + 1
    if counts.get("failed"):
        head = "report controls FAILED %d of %d" % (counts["failed"], len(verdicts))
    elif counts.get("unverified"):
        head = "report controls UNVERIFIED %d of %d" % (counts["unverified"], len(verdicts))
    else:
        return " · report controls checked %d of %d" % (len(verdicts), len(verdicts))
    why = next((v["why"] for v in verdicts if v["result"] != "checked" and v.get("why")), None)
    return " · %s%s" % (head, (" (%s)" % why) if why else "")


def tool_refusal(tool, writes, search=False):
    """Why a tool outside the class row cannot work in this spawn, or None when it can. `search`:
    the class definition allows WebSearch, so the per-spawn settings admit it (settings_for)."""
    if tool in TOOLS_UNPROMPTED:
        return None
    if tool in TOOLS_ON_WRITE_GRANT:
        return None if writes else ("the per-spawn settings allow Edit and Write on a write grant "
                                    "only, and this spawn has none: add --write")
    if tool == "WebSearch" and search:
        return None
    if tool in TOOLS_WEB:
        return ("no per-spawn permission admits %s, so every call would be refused: web work goes "
                "through codex-lane.py --search" % tool)
    return "no per-spawn permission admits %s, and permission prompts are off" % tool


# What a class definition allows that its headless lane will not have (D24, 2026-10-10): the thin
# definition carries the row's tools, so a tool the vault's definition allows is dropped silently
# unless it is named. An allowlist (`tools:`) allows what it names. A definition with none allows
# every tool its `disallowedTools:` does not name (the harness's rule, and throttle.py's: an
# allowlist wins over a denylist); that open set is read here over the tools whose grant the per-spawn
# settings decide, Edit and Write and the web tools, since the read tools and Bash work wherever the
# tool list holds them and the list itself is recorded beside. Reported, never refused.
TOOLS_SETTINGS_DECIDE = TOOLS_ON_WRITE_GRANT + TOOLS_WEB


def frontmatter_list(text, key):
    """A frontmatter field read as a list of names, or None where the key is absent: an inline
    comma list (`tools: Read, Grep`, brackets allowed) or a block list (`tools:` then `  - Read`)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    lines = text[4:end].splitlines()
    for index, line in enumerate(lines):
        if line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        name, _, value = line.partition(":")
        if name.strip() != key:
            continue
        value = value.split("#", 1)[0].strip().strip("[]")
        if value:
            return [part.strip().strip("\"'") for part in value.split(",") if part.strip()]
        items = []
        for follow in lines[index + 1:]:
            item = follow.strip()
            if not item.startswith("-"):
                break
            if item[1:].strip():
                items.append(item[1:].strip().strip("\"'"))
        return items
    return None


def definition_allows(text):
    """The tools a class definition allows, in its own order: its `tools:` allowlist where it has
    one, else those of TOOLS_SETTINGS_DECIDE its `disallowedTools:` does not name."""
    allowed = frontmatter_list(text, "tools")
    if allowed is None:
        denied = frontmatter_list(text, "disallowedTools") or []
        allowed = [tool for tool in TOOLS_SETTINGS_DECIDE if tool not in denied]
    out = []
    for tool in allowed:
        if tool not in out:
            out.append(tool)
    return out


def tools_withheld(allowed, tools, writes):
    """The tools a definition allows that this lane will not have: absent from the spawn's tool
    list, or on it where no per-spawn permission admits a call (tool_refusal; WebSearch is
    admitted wherever the definition allows it)."""
    search = "WebSearch" in allowed
    return [tool for tool in allowed
            if tool not in tools or tool_refusal(tool, writes, search) is not None]


def withheld_notice(cls, withheld):
    """The one stderr line a spawn prints when its class definition allows tools the lane will not
    have, or None when there are none."""
    if not withheld:
        return None
    extra = ""
    if any(tool in TOOLS_ON_WRITE_GRANT for tool in withheld):
        extra = "; Edit and Write need a --write grant"
    web = "web work goes"
    if "WebFetch" in withheld and "WebSearch" not in withheld:
        web = "page fetches go"
    return ("tools withheld: %s — class `%s`'s definition allows them, but this spawn's tool list and "
            "per-spawn settings do not grant them%s; %s through codex-lane.py --search"
            % (", ".join(withheld), cls, extra, web))


# ------------------------------------------------------------------- transcript ------------

def find_transcript(projects_root, home, session_id):
    direct = os.path.join(projects_root, dashed(home), "%s.jsonl" % session_id)
    if os.path.isfile(direct):
        return direct
    hits = sorted(globmod.glob(os.path.join(projects_root, "*", "%s.jsonl" % session_id)))
    return hits[0] if hits else None


def resume_transcript_error(path):
    """D29: require one parseable session record, tolerating torn or malformed other lines."""
    if not path or not os.path.isfile(path):
        return "no transcript"
    try:
        with open(path, "rb") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except (ValueError, UnicodeError, RecursionError):
                    continue
                if isinstance(record, dict):
                    return None
    except OSError:
        return "unparseable transcript: cannot read the session records"
    return "unparseable transcript: no parseable session record"


def block_text(block):
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        content = block.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(block_text(item) for item in content)
        return str(block.get("text") or "")
    return ""


USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
              "output_tokens")


def parse_transcript(path, boundary=None):
    """Everything the close line reports, read from JSON records, never by substring grep on
    the raw file: efforts applied, cache write tiers, peak call context, fence denials, a
    refusal, the last assistant text, token totals, and the limit-stop shape (the last
    assistant record carrying a synthetic model with all-zero usage)."""
    out = {"efforts": [], "tiers": [], "peak": 0, "fence_denials": 0, "fence_allows": 0,
           "refusal": False, "last_text": "", "records": 0, "unparseable": 0,
           "transcript": path, "calls": 0, "synthetic_stop": False, "last_model": None,
           "tokens": dict((key, 0) for key in USAGE_KEYS)}
    if boundary is not None:
        raw, uncertainty = a3_suffix(boundary)
    else:
        raw = read_bytes(path) if path else None
        uncertainty = None if raw is not None else "evidence unavailable"
    if raw is None or uncertainty:
        out["transcript"] = None
        out.update(a3_native_evidence(b"", "claude"))
        out.update(uncertainty=uncertainty, refusal_count=None)
        return out
    final = {}
    order = []
    handle = io.StringIO(raw.decode("utf-8", errors="replace"))
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out["records"] += 1
            try:
                record = json.loads(line)
            except ValueError:
                out["unparseable"] += 1
                continue
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            message = record.get("message") if isinstance(record.get("message"), dict) else {}
            if kind == "assistant":
                if not isinstance(message.get("model"), str) or not message["model"]:
                    out["unparseable"] += 1
                    continue  # No assistant outcome: retain the paired candidate.
                if record.get("effort"):
                    out["efforts"].append(record["effort"])
                if message.get("stop_reason") == "refusal":
                    out["refusal"] = True
                mid = message.get("id") or "anon-%d" % out["records"]
                if mid not in final:
                    order.append(mid)
                final[mid] = message
                text = " ".join(block_text(b) for b in (message.get("content") or [])
                                if isinstance(b, dict) and b.get("type") == "text")
                if text.strip():
                    out["last_text"] = text.strip()
                usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                stock = sum(int(usage.get(key) or 0) for key in USAGE_KEYS)
                out["last_model"] = str(message.get("model") or "")
                out["synthetic_stop"] = out["last_model"].startswith("<synthetic") and stock == 0
                out["terminal_synthetic_text"] = text.strip() if out["synthetic_stop"] else None
                out["terminal_synthetic_event"] = {"uuid": record.get("uuid"), "order": out["records"]}
            # A fence DENIAL is a tool result whose text starts with the fence prefix; the
            # lane's own prose quoting that prefix back (it does, when the brief asks it to
            # report the reason) is not a denial, so the test is the record kind and the
            # start of the text, never a substring search over the whole record.
            if kind == "user":
                for block in (message.get("content") or []):
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        text = block_text(block).lstrip()
                        if text.startswith("lane-fence:") and "within grants" not in text:
                            out["fence_denials"] += 1
            elif kind == "attachment":
                attachment = record.get("attachment")
                stdout = (attachment or {}).get("stdout") if isinstance(attachment, dict) else ""
                if isinstance(stdout, str) and "lane-fence: within grants" in stdout:
                    out["fence_allows"] += 1
    for mid in order:
        usage = final[mid].get("usage") or {}
        context = (int(usage.get("input_tokens") or 0)
                   + int(usage.get("cache_creation_input_tokens") or 0)
                   + int(usage.get("cache_read_input_tokens") or 0))
        out["peak"] = max(out["peak"], context)
        for key in USAGE_KEYS:
            out["tokens"][key] += int(usage.get(key) or 0)
        creation = usage.get("cache_creation")
        if isinstance(creation, dict):
            for key, label in (("ephemeral_1h_input_tokens", "1h"),
                               ("ephemeral_5m_input_tokens", "5m")):
                if int(creation.get(key) or 0) > 0 and label not in out["tiers"]:
                    out["tiers"].append(label)
        elif int(usage.get("cache_creation_input_tokens") or 0) > 0 and "untiered" not in out["tiers"]:
            out["tiers"].append("untiered")
    if order:
        first = final[order[0]].get("usage") or {}
        out["first_call_context"] = (int(first.get("input_tokens") or 0)
                                     + int(first.get("cache_creation_input_tokens") or 0)
                                     + int(first.get("cache_read_input_tokens") or 0))
    out["calls"] = len(order)
    out.update(a3_native_evidence(raw, "claude"))
    out["source"] = path
    return out


def a3_native_evidence(raw, harness):
    """Structured current-pass outcome ordering and whole, identity-deduplicated report."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    messages, order, refusals, refusal_texts = {}, [], {}, []
    last_refusal = last_completion = last_work = 0
    turn = 0
    refusal_turn = None
    final_turn = None
    terminal_error, terminal_failure = "", False
    synthetic = {"synthetic_stop": False, "terminal_synthetic_text": None}
    malformed = 0
    for position, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            malformed += 1
            continue
        if not isinstance(event, dict):
            malformed += 1
            continue
        kind = event.get("type")
        message, message_id, text, refused = {}, None, "", False
        if harness == "claude" and kind == "assistant":
            message = event.get("message") if isinstance(event.get("message"), dict) else {}
            if not isinstance(message.get("model"), str) or not message["model"]:
                malformed += 1
                continue  # Missing outcome evidence cannot retire a terminal candidate.
            message_id = message.get("id") or event.get("uuid") or "assistant-%d" % position
            content = message.get("content")
            if isinstance(content, list):
                text = "\n".join(block_text(block) for block in content if isinstance(block, dict)
                                  and block.get("type") in ("text", "refusal"))
                refused = any(isinstance(block, dict) and block.get("type") == "refusal"
                              for block in content)
            elif isinstance(content, str):
                text = content
            refused = refused or message.get("stop_reason") == "refusal"
            usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
            model = str(message.get("model") or "")
            zero = sum(int(usage.get(key) or 0) for key in USAGE_KEYS) == 0
            synthetic = {"synthetic_stop": model.startswith("<synthetic") and zero,
                         "last_model": model,
                         "terminal_synthetic_text": text.strip() if model.startswith("<synthetic") and zero else None,
                         "terminal_synthetic_event": {"uuid": event.get("uuid"), "order": position}}
            last_work = position
            if message.get("stop_reason") == "end_turn":
                last_completion = position
        elif harness == "codex":
            if kind == "turn.started":
                turn += 1
                last_work = position
                final_turn = "started"
                terminal_error, terminal_failure = "", False
            elif kind == "turn.failed":
                last_work = position
                final_turn = "failed"
                terminal_error, terminal_failure = terminal_error_text(event.get("error")), True
            elif kind == "turn.completed":
                last_completion = position
                final_turn = "completed"
                terminal_error, terminal_failure = "", False
            elif kind == "error" and not terminal_failure and final_turn != "completed":
                terminal_error = terminal_error_text(event.get("message") or event.get("error"))
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            if isinstance(kind, str) and kind.startswith("item."):
                item_type = item.get("type")
                message_id = item.get("id") or "item-%d" % position
                if item_type in ("agent_message", "refusal"):
                    text = item.get("text") if isinstance(item.get("text"), str) else ""
                    refused = item_type == "refusal" or item.get("stop_reason") == "refusal"
                else:
                    message_id = None
            if kind == "refusal":
                message_id = event.get("id") or "refusal-%d" % position
                refused = True
            error = event.get("error") if isinstance(event.get("error"), dict) else {}
            # E5: preserve the accepted recorded failed-turn form, never quoted tool/report text.
            # The preceding generic error event is not another refusal.
            error_text = error.get("message") if isinstance(error.get("message"), str) else ""
            if kind == "turn.failed" and error_text.startswith(
                    "This content was flagged for possible cybersecurity risk. If this seems wrong, try rephrasing your request."):
                refused = True
        if message_id and text:
            if message_id not in messages:
                order.append(message_id)
            messages[message_id] = text
        if refused:
            if text and text not in refusal_texts:
                refusal_texts.append(text)
            key = str(message_id or "event-%d" % position)
            if key not in refusals:
                refusals[key] = {"event": position, "message_id": key, "kind": kind}
            last_refusal = position
            refusal_turn = turn
    return {**(synthetic if harness == "claude" else
                {"terminal_error": terminal_error, "terminal_failure": terminal_failure}),
            "refusal": bool(refusals), "refusal_count": len(refusals),
            "refusal_evidence": list(refusals.values()), "last_refusal": last_refusal,
            "last_completion": last_completion, "last_work": last_work,
            "final_turn": final_turn, "later_completion": last_completion > last_refusal > 0,
            "same_turn_completion": bool(harness == "codex" and refusals and
                                          refusal_turn == turn and last_completion > last_refusal),
            "report_text": "\n\n".join(messages[key] for key in order),
            "report_message_ids": order, "evidence_malformed": malformed,
            "refusal_texts": refusal_texts,
            "uncertainty": "malformed evidence records" if malformed else None}


def terminal_error_text(error):
    """Complete failed-turn text; display truncation is a separate operation."""
    if isinstance(error, dict):
        message = terminal_error_text(error.get("message"))
        if message:
            return message
        rest = {key: value for key, value in error.items() if value not in (None, "", {}, [])}
        return json.dumps(rest, sort_keys=True) if rest else ""
    if isinstance(error, str):
        return "" if error.strip().lower() in ("", "none", "null") else error.strip()
    return "" if error in (None, {}, []) else str(error)


def a3_stop_evidence(evidence, harness):
    """Selected stop facts survive refusal priority, guards and explicit recovery."""
    if harness == "codex":
        text = evidence.get("terminal_error") or None
        limit = text if text and CODEX_USAGE_STOP_RE.search(text) else None
        network = text if text and not limit and NETWORK_RE.search(text) else None
    else:
        result = evidence.get("cli_result") or {}
        subtype = str(result.get("subtype") or "")
        failed = bool(result.get("is_error")) or evidence.get("process_exit") not in (0, None)
        args = (evidence, result.get("result") or "", evidence.get("native_stderr") or "",
                subtype, failed, bool(result.get("is_error")) or subtype.startswith("error"))
        text = terminal_stop_text(*args)
        limit, network = limit_signal(*args), network_signal(*args)
    return {"terminal_stop_text": text, "limit_signal": limit, "network_signal": network}


def a3_final_success(harness, evidence, process_exit, successful_result=True, stopped=False):
    if process_exit != 0 or stopped or not successful_result or evidence.get("uncertainty"):
        return False
    if evidence.get("last_completion", 0) <= evidence.get("last_refusal", 0):
        return False
    if harness == "codex":
        return (evidence.get("final_turn") == "completed"
                and evidence.get("last_work", 0) < evidence.get("last_completion", 0))
    return evidence.get("last_work", 0) <= evidence.get("last_completion", 0)


# ----------------------------------------------------------------------- record -------------

def open_console_for_spawn(run, viewer=None):
    """Put the run's console on screen when none is alive, right after the lane's record lines
    exist, so every run that spawns a lane is watched whatever its shape: a hands-off run
    (`run-open` opens it first), an attended run's headless lanes (here), an in-session Agent
    lane (the spawn-record guard's allow path). One window per run (owner ruling 2026-09-08):
    handsoff.open_console_if_dark
    refuses while a console is alive or was opened within its grace window, so a second lane, a
    re-spawn or a detached worker never doubles it, and the live console shows the new lane
    itself. Opt-outs: `--viewer none`, AIMYTH_VIEWER=none, or `viewer: none` in the run's
    grants file. The opener's lines go to stderr (stdout is this wrapper's report channel) and
    any failure is one stderr line: a viewer failure never fails a spawn (SystemExit included:
    handsoff's token check exits on a malformed run id, critic F1). Placement: after the
    `lane-open` line and before the child starts, so the opener's worst case (pgrep, two `open`
    attempts and the console's confirmation: handsoff VIEWER_TIMEOUT_S three times plus
    CONSOLE_START_GRACE_S) delays the start, never the child's own brief clock (critic F6). The
    opener is `/usr/bin/open` (handsoff OPEN_BIN, the owner's absolute path; AIMYTH_OPEN_BIN
    overrides it for a suite's stub) on the run's `<run>-console.command` file, confirmed by a
    live `watch` process (2026-09-18); no AppleScript is run on this path."""
    viewer = viewer or os.environ.get("AIMYTH_VIEWER") or None
    if viewer not in (None, "terminal", "none"):
        sys.stderr.write("lane.py: viewer %r is neither terminal nor none · the grants file decides\n" % viewer)
        viewer = None
    if viewer == "none":
        sys.stderr.write("lane.py: viewer none · no window\n")
        return False
    try:
        sys.dont_write_bytecode = True      # no __pycache__ in the skill directory (the suite's write proof)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import handsoff
        with contextlib.redirect_stdout(sys.stderr):
            return handsoff.open_console_if_dark(run, viewer=viewer)
    except (Exception, SystemExit) as exc:
        sys.stderr.write("lane.py: viewer skipped (%s: %s)\n" % (type(exc).__name__, exc))
        return False


# A3 lock order: lifetime gate, legacy session gate when applicable, record transaction.
# Observers use only the last of these. A transaction never waits for a process or report.
_A3_RECORD_MUTEX = threading.RLock()
_A3_RECORD_HELD = threading.local()
_A3_OWNERS = {}
_A3_BARRIER = None
A3_SCHEMA = 1  # First version of the lifetime-ownership journal.
# What each writer's close leaves out or fixes because it does not apply to that harness, so that a
# reader can tell it from a field that is missing (register 2026-10-13 06:43). A key names a field
# of the close, its value why; the fields themselves stay as they were, so no count changes kind.
CLOSE_NOT_APPLICABLE = {
    "claude": {"denials.sandbox": "a Claude lane has no sandbox channel: its denials are the tool "
                                  "and fence channels"},
    "codex": {"denials.tool": "a Codex lane has no tool channel: the zero is a constant, not a count",
              "denials.fence": "a Codex lane has no fence channel: the zero is a constant, not a count",
              "soft_usd": "plan usage is never priced, so a Codex lane has no soft line",
              "soft_src": "plan usage is never priced, so a Codex lane has no soft line",
              "soft_exceeded": "plan usage is never priced, so a Codex lane has no soft line"}}
A3_FAMILY_HOLD = "no untried model family remains"
A3_FAMILY_RULE = ("both families refused: hold; the head may rewrite the brief once "
                  "(harmless purpose stated, exact files and change, nothing from the refused replies) "
                  "or park the task for the owner; a second double refusal parks it.")


class A3Premise(Exception):
    """An unusable premise is never evidence of a clean or absent pass."""


def a3_public(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (A3Premise, OSError) as exc:
            die(str(exc))
    return wrapped


def a3_barrier(name, journal):
    """Native fixture controllers may pause the actual lifecycle through this hook."""
    if _A3_BARRIER is not None:
        _A3_BARRIER(name, journal)


def a3_canonical(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def a3_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def a3_digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def a3_namespace(record):
    return a3_canonical(record) + ".a3"


def a3_lane_key(record, run, lane_id):
    # Case-equivalent lane names already share the base's exclusion rule.
    return a3_digest(a3_json([a3_canonical(record), run, lane_id.casefold()]))


def a3_gate_path(record, run, lane_id):
    return os.path.join(a3_namespace(record), a3_lane_key(record, run, lane_id) + ".lock")


def a3_sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def a3_record_lock(path):
    """Stable sidecar lock, re-entrant in one thread, serialised between local threads."""
    path = a3_canonical(path)
    with _A3_RECORD_MUTEX:
        held = getattr(_A3_RECORD_HELD, "paths", {})
        _A3_RECORD_HELD.paths = held
        if path in held:
            yield
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        descriptor = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        os.set_inheritable(descriptor, False)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            held[path] = descriptor
            try:
                yield
            finally:
                del held[path]
        finally:
            os.close(descriptor)


def a3_scan_record(raw):
    rows, damage = [], []
    for number, line in enumerate(raw.splitlines(keepends=True), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("record is not an object")
            rows.append(row)
            if not line.endswith(b"\n"):
                damage.append((number, line))
        except (ValueError, UnicodeError):
            damage.append((number, line))
    return rows, damage


def a3_record_rows(path, allow_tail=False):
    """Strict reads admit damaged bytes only after an explicit, journalled append-only repair."""
    raw = read_bytes(path)
    if raw is None:
        if os.path.lexists(path):
            raise A3Premise("record unreadable: %s" % path)
        return [], b""
    rows, damage = a3_scan_record(raw)
    if damage and not allow_tail:
        admitted = set()
        content_ends = {}
        offset = 0
        for number, line in enumerate(raw.splitlines(keepends=True), 1):
            content_ends[number] = offset + len(line.rstrip(b"\r\n"))
            offset += len(line)
        for row in rows:
            if row.get("event") != "record-tail-repaired":
                continue
            journal = a3_read_journal(path, row.get("pass_id"))
            saved = (journal.get("record_repairs") or {}).get(row.get("repair_id"))
            if not saved or saved.get("damaged_rows") != row.get("damaged_rows"):
                raise A3Premise("record repair has no authoritative journal witness")
            through = saved.get("observed_bytes")
            if isinstance(through, bool) or not isinstance(through, int) or not 0 <= through <= len(raw) or \
                    a3_digest(raw[:through]) != saved.get("observed_sha256"):
                raise A3Premise("record repair witness no longer matches its observed prefix")
            admitted.update((number, a3_digest(line.rstrip(b"\r\n"))) for number, line in damage
                            if content_ends[number] <= through
                            and a3_digest(line.rstrip(b"\r\n")) in saved["damaged_rows"])
        unknown = [(number, line) for number, line in damage
                   if (number, a3_digest(line.rstrip(b"\r\n"))) not in admitted]
        if unknown:
            raise A3Premise("damaged record row %d in %s; explicit recovery required" %
                            (unknown[0][0], path))
    return rows, raw



def a3_process_identity(pid):
    """Return a process birth identity, or an explicit unknown; never rely on a PID alone."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        if sys.platform == "darwin":
            import ctypes
            # proc_bsdinfo from the Darwin libproc ABI: twelve uint32 fields, names,
            # six uint32 fields, then the two uint64 process-start timeval fields.
            class BSDInfo(ctypes.Structure):
                _fields_ = [("head", ctypes.c_uint32 * 12),
                            ("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32),
                            ("tail", ctypes.c_uint32 * 6),
                            ("seconds", ctypes.c_uint64), ("microseconds", ctypes.c_uint64)]
            info = BSDInfo()
            library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            count = library.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
            # 3 is PROC_PIDTBSDINFO in that ABI, not a timeout or empirical threshold.
            if count != ctypes.sizeof(info) or not info.seconds:
                return None
            return {"pid": pid, "birth": "%d.%06d" % (info.seconds, info.microseconds),
                    "source": "proc_pidinfo"}
        if sys.platform.startswith("linux"):
            with open("/proc/%d/stat" % pid, encoding="ascii") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
            with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as handle:
                boot = handle.read().strip()
            # Field 22, with field 3 at index 0 after the parenthesised command.
            return {"pid": pid, "birth": boot + ":" + fields[19], "source": "proc-stat"}
    except (OSError, ValueError, IndexError, AttributeError):
        return None
    return None


def a3_liveness(identity):
    """alive, dead or unknown. Reuse proves the old process dead, never the new child safe."""
    if not isinstance(identity, dict) or not identity.get("birth"):
        return "unknown"
    pid = identity.get("pid")
    if pid_alive(pid) is False:
        return "dead"
    current = a3_process_identity(pid)
    if current is None:
        return "unknown"
    return "alive" if current == identity else "dead"


class A3Gate:
    def __init__(self, record, run, lane_id):
        self.record, self.run, self.lane = a3_canonical(record), run, lane_id
        self.descriptor = None

    def __enter__(self):
        path = a3_gate_path(self.record, self.run, self.lane)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            self.descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
            os.set_inheritable(self.descriptor, False)
            fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if self.descriptor is not None:
                os.close(self.descriptor)
                self.descriptor = None
            if exc.errno in (errno.EAGAIN, errno.EACCES):
                raise A3Premise("lifetime gate busy; the existing owner remains responsible")
            raise A3Premise("lifetime gate unusable: %s" % exc)
        return self

    def __exit__(self, *exc):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None


def a3_journal_path(record, pass_id):
    # UUID.hex encodes sixteen bytes as thirty-two hexadecimal characters.
    if not isinstance(pass_id, str) or not re.fullmatch(r"[0-9a-f]{32}", pass_id):
        raise A3Premise("invalid immutable pass identifier")
    return os.path.join(a3_namespace(record), pass_id + ".json")


def a3_read_journal(record, pass_id):
    path = a3_journal_path(record, pass_id)
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError) as exc:
        raise A3Premise("journal unreadable at %s: %s" % (path, exc))
    if not isinstance(value, dict) or value.get("schema") != A3_SCHEMA or \
            value.get("pass_id") != pass_id or value.get("record") != a3_canonical(record):
        raise A3Premise("contradictory journal identity at %s" % path)
    if value.get("execution") not in ("running", "finalising", "prepared", "closed"):
        raise A3Premise("invalid execution phase at %s" % path)
    disposition = value.get("disposition")
    if not isinstance(disposition, dict) or disposition.get("phase") not in (
            "none", "awaiting-head", "awaiting-input", "sealed", "launch-intent", "resolved"):
        raise A3Premise("invalid disposition at %s" % path)
    close = value.get("close")
    if close and (close.get("pass_id") != pass_id or close.get("close_id") != value.get("close_id")):
        raise A3Premise("conflicting close identity at %s" % path)
    if value["execution"] in ("prepared", "closed") and not close:
        raise A3Premise("missing prepared close at %s" % path)
    for index, notice in enumerate(value.get("notices") or [], 1):
        if notice.get("version") != index or notice.get("notice_id") != value.get("notice_id") or \
                notice.get("payload_sha256") != a3_digest(a3_json(notice.get("payload"))):
            raise A3Premise("invalid notice version at %s" % path)
    versions = {(notice["notice_id"], notice["version"], notice["payload_sha256"])
                for notice in value.get("notices") or []}
    for acknowledgement in value.get("acknowledgements") or []:
        if not isinstance(acknowledgement, dict) or tuple(acknowledgement.get(key) for key in
                ("notice_id", "version", "payload_sha256")) not in versions or \
                acknowledgement.get("route") not in ("hands-off", "attended") or \
                not acknowledgement.get("receipt") or not acknowledgement.get("receipt_sha256"):
            raise A3Premise("contradictory notice acknowledgement at %s" % path)
    return value


def a3_save_journal(journal):
    write_atomic(a3_journal_path(journal["record"], journal["pass_id"]), a3_json(journal) + "\n")


def a3_journals(record, run=None):
    """The directory is the census; a projection or optional index cannot hide a notice."""
    directory = a3_namespace(record)
    if not os.path.lexists(directory):
        return []
    try:
        names = sorted(os.listdir(directory))
    except OSError as exc:
        raise A3Premise("journal census incomplete: %s" % exc)
    values = []
    for name in names:
        if name.endswith(".json"):
            journal = a3_read_journal(record, name[:-5])
            if run is None or journal.get("run") == run:
                values.append(journal)
    return values


def a3_latest(record, run, lane_id, include_beats=False):
    values = [j for j in a3_journals(record, run) if j.get("lane") == lane_id
              and (include_beats or j.get("kind") != "beat")]
    if not values:
        return None
    return max(values, key=lambda j: j["ordinal"])


def a3_committed(journal):
    return journal["execution"] == "closed" and journal["disposition"]["phase"] == "resolved"


def a3_close_valid(row):
    if not row.get("pass_id"):
        return True
    journal = a3_read_journal(row.get("record") or row.get("a3_record"), row["pass_id"])
    return (journal["execution"] == "closed" and journal.get("close_id") == row.get("close_id")
            and journal.get("close") == row)


def a3_current(record, run, lane_id):
    return _A3_OWNERS.get((a3_canonical(record), run, lane_id))


def a3_boundary(path):
    if not path:
        return {"path": None, "known": False, "reason": "no current-pass evidence path"}
    path = a3_canonical(path)
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
            stat_value = os.fstat(handle.fileno())
        return {"path": path, "known": True, "exists": True, "size": len(raw),
                "prefix_sha256": a3_digest(raw), "device": stat_value.st_dev,
                "inode": stat_value.st_ino}
    except FileNotFoundError:
        return {"path": path, "known": True, "exists": False, "size": 0,
                "prefix_sha256": a3_digest(b"")}
    except OSError as exc:
        return {"path": path, "known": False, "reason": str(exc)}


def a3_suffix(boundary):
    if not boundary or not boundary.get("known") or not boundary.get("path"):
        return b"", "final-message, boundary unknown"
    try:
        with open(boundary["path"], "rb") as handle:
            raw = handle.read()
            stat_value = os.fstat(handle.fileno())
    except OSError as exc:
        return b"", "evidence unavailable: %s" % exc
    size = boundary["size"]
    if len(raw) < size or a3_digest(raw[:size]) != boundary["prefix_sha256"]:
        return b"", "final-message, boundary unknown: evidence prefix changed or truncated"
    if boundary.get("exists") and (stat_value.st_dev != boundary["device"] or
                                   stat_value.st_ino != boundary["inode"]):
        return b"", "final-message, boundary unknown: evidence file replaced"
    if size and raw[size - 1:size] != b"\n":
        return b"", "final-message, boundary unknown: start splits a record"
    return raw[size:], None


def a3_recovery_command(journal):
    wrapper = journal["wrapper"]
    parts = [sys.executable, wrapper, "recover", "--run", journal["run"], "--lane", journal["lane"],
             "--record", journal["record"], "--pass", journal["pass_id"]]
    return " ".join(shlex.quote(part) for part in parts)


def a3_pass_history(journal):
    """Validate the immutable ancestry captured when this pass was published."""
    history = journal.get("movement_history")
    if history is None:
        # A pre-history A3 pass is its own task; no predecessor is guessed from lane names.
        history = [{"pass_id": journal["pass_id"], "family": journal["harness"],
                    "run": journal["run"], "lane": journal["lane"],
                    "refusal_locator": a3_journal_path(journal["record"], journal["pass_id"])
                                       + "#evidence.refusal_evidence"}]
    if not isinstance(history, list) or not history or any(
            not isinstance(row, dict) or row.get("family") not in ("claude", "codex")
            or not row.get("pass_id") or not row.get("refusal_locator") for row in history):
        raise A3Premise("invalid task movement history")
    if history[-1]["pass_id"] != journal["pass_id"] or history[-1]["family"] != journal["harness"]:
        raise A3Premise("task movement history does not end at this pass")
    return json.loads(a3_json(history))


def a3_task_history(journal):
    """Union local pass locators by task identity, including a resumed source's successors."""
    task_id = journal.get("task_id") or journal["pass_id"]
    related = [other for other in a3_journals(journal["record"])
               if (other.get("task_id") or other["pass_id"]) == task_id
               and other["pass_id"] != journal["pass_id"] and other.get("kind") != "beat"]
    related.append(journal)
    # Each saved ancestry establishes its own order. Merge shorter prefixes first; creation
    # time orders independent resumed branches. The pass id gives deterministic ties.
    related.sort(key=lambda other: (len(other.get("movement_history") or []),
                                    other.get("created", ""), other["pass_id"]))
    history, seen = [], {}
    for other in related:
        for row in a3_pass_history(other):
            previous = seen.get(row["pass_id"])
            if previous is not None and previous != row:
                raise A3Premise("conflicting task movement history")
            if previous is None:
                seen[row["pass_id"]] = row
                history.append(row)
    return history


def a3_families_exhausted(journal):
    return {row["family"] for row in a3_task_history(journal)} == {"claude", "codex"}


def a3_family_rule_context(journal):
    """N5 belongs to this pass's saved ancestry, never to its later successors."""
    history = a3_pass_history(journal)
    evidence, outcome = journal.get("evidence") or {}, journal.get("outcome") or {}
    triggered = evidence.get("refusal_count") or (outcome.get("fallback") or {}).get("verdict") == "fallback"
    if journal.get("kind") == "beat" or journal["disposition"].get("decision") == "moved" \
            or not triggered or {row["family"] for row in history} != {"claude", "codex"}:
        return None
    return {"task_id": journal.get("task_id") or history[0]["pass_id"],
            "movement_history": history,
            "families_tried": list(dict.fromkeys(row["family"] for row in history)),
            "rule": A3_FAMILY_RULE}


def a3_family_rule_text(payload):
    return "task %s · families tried %s · local refusal locators %s\n%s" % (
        payload["task_id"], " → ".join(payload["families_tried"]),
        a3_json(payload["movement_history"]), payload["rule"])


def a3_notice(journal, kind=None):
    """Called under the record transaction. Equal facts create no new obligation."""
    outcome = journal.get("outcome") or {}
    evidence = journal.get("evidence") or {}
    process_exit = outcome.get("process_exit")
    if process_exit is None:
        process_exit = evidence.get("process_exit")
    if not (kind or evidence.get("refusal_count") or outcome.get("fallback", {}).get("detected")
            or journal["disposition"]["phase"] in ("awaiting-head", "awaiting-input")):
        return None
    payload = {"pass_id": journal["pass_id"], "run": journal["run"], "lane": journal["lane"],
               "subject": journal.get("kind", "task"),
               "kind": kind or "outcome", "refusal_count": evidence.get("refusal_count"),
               "evidence": evidence.get("refusal_evidence") or [],
               "source": evidence.get("source"), "stop_cause": journal.get("stop_cause"),
               "uncertainty": evidence.get("uncertainty"),
               "process_exit": process_exit, "exit_class": outcome.get("exit_class"),
               "record_repairs": sorted((journal.get("record_repairs") or {}).keys()),
               "report": journal.get("report"), "report_sha256": outcome.get("report_sha256"),
               "disposition": journal["disposition"], "recover": a3_recovery_command(journal)}
    history = a3_pass_history(journal)
    payload.update(task_id=journal.get("task_id") or history[0]["pass_id"],
                   movement_history=history,
                   families_tried=list(dict.fromkeys(row["family"] for row in history)))
    if kind == "orphan" or journal.get("recovered_orphan") and process_exit is None:
        payload["wording"] = "launcher gone; process outcome unknown"
        if process_exit is not None:
            payload["wording"] = "launcher gone; native process result %s saved" % process_exit
        if journal.get("child_started") is False and journal.get("child_start_pending") is False:
            payload["wording"] = "launcher gone; model process never started"
        if evidence.get("refusal_count"):
            payload["wording"] = "refusal detected; " + payload["wording"]
        payload["later_completion"] = evidence.get("later_completion")
    notices = journal.setdefault("notices", [])
    if a3_family_rule_context(journal) and journal["disposition"]["phase"] in ("awaiting-head", "resolved"):
        # The record transaction serialises the task's single durable N5 version,
        # including later resumes. Replaying that same version remains a no-op.
        task_notices = [notice for other in a3_journals(journal["record"])
                        if other["pass_id"] != journal["pass_id"]
                        and (other.get("task_id") or other["pass_id"]) == payload["task_id"]
                        for notice in other.get("notices", [])]
        previous = next((notice for notice in task_notices + notices if notice["payload"].get("rule")), None)
        if previous is None or (notices and previous is notices[-1]
                                and previous["payload"] == dict(payload, rule=A3_FAMILY_RULE)):
            payload["rule"] = A3_FAMILY_RULE
    digest = a3_digest(a3_json(payload))
    if notices and notices[-1]["payload_sha256"] == digest:
        return notices[-1]
    notice = {"notice_id": journal["notice_id"], "version": len(notices) + 1,
              "payload_sha256": digest, "payload": json.loads(a3_json(payload))}
    notices.append(notice)
    return notice


def a3_pending(record, run=None):
    notices = []
    for journal in a3_journals(record, run):
        acknowledgements = {tuple(a[k] for k in ("notice_id", "version", "payload_sha256"))
                            for a in journal.get("acknowledgements") or []}
        for notice in journal.get("notices") or []:
            key = tuple(notice[k] for k in ("notice_id", "version", "payload_sha256"))
            if key not in acknowledgements:
                notices.append(dict(notice, journal=a3_journal_path(record, journal["pass_id"])))
    return sorted(notices, key=lambda n: (n["notice_id"], n["version"]))


def a3_notice_text(notice):
    if not notice:
        return ""
    payload = notice["payload"]
    rendered = ("notice %s v%d sha256 %s · %s · refusal count %s · stop %s · %s · report %s\n"
            "recovery inspection: %s" %
            (notice["notice_id"], notice["version"], notice["payload_sha256"],
             payload.get("wording") or payload.get("exit_class") or payload["kind"],
             payload.get("refusal_count") if payload.get("refusal_count") is not None else "unknown",
             payload.get("stop_cause") or "none recorded",
             a3_json(payload["disposition"]), payload.get("report"), payload["recover"]))
    if payload.get("rule"):
        rendered += "\n" + a3_family_rule_text(payload)
    return rendered


def a3_entry(harness):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(args):
            # The detached parent validates and observes; only its worker can own.
            if getattr(args, "dry_run", False) or (getattr(args, "detach", False)
                                                   and not getattr(args, "as_worker", False)):
                return function(args)
            record = store_paths(args.run, args.lane, getattr(args, "record", None))["record"]
            try:
                with A3Gate(record, args.run, args.lane) as gate:
                    rows, _ = a3_record_rows(record)
                    native_beats = {row.get("invocation_id") for row in rows
                                    if row.get("event") == "hold-beat" and not row.get("observation_only")}
                    if any(row.get("lane") == args.lane and row.get("harness_may_survive")
                           and row.get("invocation_id") not in native_beats for row in rows):
                        raise A3Premise("a beat harness may survive; its invocation needs explicit reconciliation")
                    previous = a3_latest(record, args.run, args.lane, include_beats=True)
                    if previous and (not a3_committed(previous) or
                                     a3_liveness(previous.get("child")) != "dead"
                                     and previous.get("child") is not None):
                        raise A3Premise("predecessor disposition or child is unsettled; use recover")
                    owner = A3Owner(gate, harness, args, previous)
                    key = (gate.record, args.run, args.lane)
                    if key in _A3_OWNERS:
                        raise A3Premise("nested lifetime owner")
                    _A3_OWNERS[key] = owner
                    try:
                        return function(args)
                    except BaseException as exc:
                        if owner.journal and owner.journal["execution"] != "closed":
                            owner.infrastructure_failure(exc)
                            a3_render(owner.journal, getattr(args, "format", "text"),
                                      getattr(args, "report_words", None))
                            return 3
                        raise
                    finally:
                        _A3_OWNERS.pop(key, None)
            except (A3Premise, OSError) as exc:
                die(str(exc))
        return wrapped
    return decorate


class A3Owner:
    """Authority belongs to this gate holder from publication through durable finalisation."""
    def __init__(self, gate, harness, args, previous):
        self.gate, self.harness, self.args, self.previous = gate, harness, args, previous
        self.journal, self.ctx, self.process = None, None, None
        self.source_bytes = None
        self.stream_settler = None
        self.identity = a3_process_identity(os.getpid())
        self.recovering = False

    def begin(self, ctx, line, source_bytes, delivered, transformations=None):
        if self.journal is not None:
            raise A3Premise("the owner already published a pass")
        identity = a3_process_identity(os.getpid())
        if not identity:
            raise A3Premise("wrapper process birth identity unavailable")
        self.ctx = ctx
        base = dict(ctx.get("open_line") or {}, **line)
        source_pass = getattr(self.args, "source_pass", None)
        source_disposition = getattr(self.args, "source_disposition", None)
        source = None
        if bool(source_pass) != bool(source_disposition):
            raise A3Premise("successor source pass and disposition must be supplied together")
        if source_pass:
            source = a3_read_journal(self.gate.record, source_pass)
            decision = source["disposition"]
            if decision.get("id") != source_disposition or decision.get("phase") != "launch-intent" or \
                    decision.get("successor") != ctx["lane"] or decision.get("target") != self.harness:
                raise A3Premise("successor does not match the reserved launch intent")
            for name in ("grants", "writes"):
                expected, actual = decision.get(name), base.get(name)
                if not isinstance(actual, list) or not isinstance(expected, list) or \
                        len(actual) != len(expected) or set(actual) != set(expected):
                    raise A3Premise("successor %s differ in membership or length" % name)
            if base.get("effort") != decision.get("effort") or base.get("model") != decision.get("model") or \
                    base.get("expect_usd") != decision.get("estimate") or \
                    a3_digest(source_bytes) != decision.get("brief_sha256"):
                raise A3Premise("successor model, effort, estimate or brief provenance differs")
        beat = ctx.get("a3_kind") == "beat"
        pass_id = os.environ.get("A3_BEAT_INVOCATION") if beat else None
        pass_id = pass_id or uuid.uuid4().hex
        journal_path = a3_journal_path(self.gate.record, pass_id)
        if os.path.lexists(journal_path):
            raise A3Premise("invocation identifier already has an authoritative journal")
        paths = store_paths(ctx["run"], ctx["lane"], self.gate.record)
        report = ctx.get("report_path") or ctx.get("report")
        if report:
            require_absent_paths((report,))
        if self.harness == "claude":
            evidence_path = find_transcript(ctx["projects_root"], ctx["home"], ctx["session_id"])
            if evidence_path is None:
                evidence_path = os.path.join(ctx["projects_root"], dashed(ctx["home"]),
                                             ctx["session_id"] + ".jsonl")
        else:
            evidence_path = ctx["events"]
        boundary = a3_boundary(evidence_path)
        directory = a3_namespace(self.gate.record)
        source_path = os.path.join(directory, pass_id + ".source")
        snapshot_path = os.path.join(directory, pass_id + ".brief")
        delivered_bytes = delivered.encode("utf-8")
        if not beat:
            write_atomic(source_path, source_bytes, binary=True)
            write_atomic(snapshot_path, delivered_bytes, binary=True)
        estimate = line.get("expect_usd")
        if estimate is None and self.previous:
            estimate = self.previous.get("input", {}).get("estimate")
        estimate_source = ("current --expect-usd" if getattr(self.args, "expect_usd", None) is not None
                           else "carried from " + self.previous["pass_id"] if self.previous
                           else "current validated invocation")
        if getattr(self.args, "a3_estimate_source", None):
            estimate_source = "carried from " + self.args.a3_estimate_source
        if estimate is not None:
            estimate = require_estimate(estimate)
        provenance = {"source": os.path.abspath(self.args.brief) if self.args.brief else None,
                      "source_copy": source_path if not beat else None,
                      "source_sha256": a3_digest(source_bytes), "snapshot": snapshot_path if not beat else None,
                      "snapshot_sha256": a3_digest(delivered_bytes), "transformations": transformations or [],
                      "estimate": estimate, "estimate_source": estimate_source, "pass_id": pass_id}
        ordinal = self.previous["ordinal"] + 1 if self.previous else 1
        journal = {"schema": A3_SCHEMA, "record": self.gate.record, "run": ctx["run"],
                   "lane": ctx["lane"], "harness": self.harness, "pass_id": pass_id,
                   "kind": "beat" if beat else "task",
                   "ordinal": ordinal, "owner": identity, "original_owner": identity,
                   "wrapper": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "lane.py" if self.harness == "claude" else "codex-lane.py"),
                   "execution": "running", "disposition": {"id": uuid.uuid4().hex, "phase": "none"},
                   "notice_id": uuid.uuid4().hex, "notices": [], "acknowledgements": [],
                   "start": base, "boundary": boundary, "input": provenance, "report": report,
                   "child": None, "child_started": False, "child_start_pending": False,
                   "stop_intent": None, "stop_cause": None,
                   "evidence": {"refusal_count": None, "refusal_evidence": [], "settled": False},
                   "no_swap": bool(getattr(self.args, "no_swap", False)), "created": now()}
        ancestor = source or (self.previous if getattr(self.args, "command", None) == "resume"
                              or beat else None)
        history = a3_task_history(ancestor) if ancestor else []
        history.append({"pass_id": pass_id, "family": self.harness,
                        "run": ctx["run"], "lane": ctx["lane"],
                        "refusal_locator": journal_path + "#evidence.refusal_evidence"})
        journal.update(task_id=(ancestor.get("task_id") or history[0]["pass_id"])
                       if ancestor else pass_id, movement_history=history,
                       source_pass=source_pass, source_disposition=source_disposition)
        if os.path.exists(self.gate.record):
            record_stat = os.stat(self.gate.record)
            journal["record_identity"] = {"device": record_stat.st_dev, "inode": record_stat.st_ino}
        with a3_record_lock(self.gate.record):
            # A legacy open invocation is not retroactively made safe by this new owner.
            rows, _ = a3_record_rows(self.gate.record)
            opened, spawned, closed = lane_state(rows, ctx["lane"])
            if (opened or spawned) and not closed and not self.previous:
                raise A3Premise("unsupported open legacy pass; explicit reconciliation is required")
            a3_save_journal(journal)
        self.journal = journal
        ctx["a3_pass_id"] = pass_id
        line.update({"pass_id": pass_id, "pass_ordinal": ordinal, "owner": identity,
                     "a3_record": self.gate.record, "input_provenance": provenance,
                     "evidence_boundary": boundary, "report": report})
        return journal

    def refresh(self):
        self.journal = a3_read_journal(self.gate.record, self.journal["pass_id"])
        if not self.recovering and self.journal["owner"] != self.identity:
            raise A3Premise("journal owner identity conflicts with the lifetime gate holder")
        return self.journal

    def bind_transcript(self, path):
        """Bind a fresh session's first discovered transcript after the entry census found none."""
        if not path or self.harness != "claude":
            return path
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            boundary = journal["boundary"]
            resolved = a3_canonical(path)
            if resolved == boundary.get("path"):
                return path
            if (getattr(self.args, "command", None) != "spawn" or boundary.get("exists")
                    or boundary.get("size") != 0 or not boundary.get("known")
                    or os.path.basename(resolved) != self.ctx["session_id"] + ".jsonl"
                    or os.path.commonpath([resolved, a3_canonical(self.ctx["projects_root"])])
                       != a3_canonical(self.ctx["projects_root"])):
                return path  # A resume or contradictory path cannot invent an empty prefix.
            boundary.update(path=resolved, discovery="fresh session absent from entry census")
            a3_save_journal(journal)
        return path

    def record_child(self, process):
        self.process = process
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            journal["child_started"] = True
            journal["child_start_pending"] = False
            journal["child"] = a3_process_identity(process.pid)
            journal["child_pid"] = process.pid
            if journal["child"] is None:
                journal["evidence"]["uncertainty"] = "child process birth identity unavailable"
            a3_save_journal(journal)
        a3_barrier("child-started", journal)

    def prelaunch(self):
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            journal["child_start_pending"] = True
            a3_save_journal(journal)

    def start_failed(self):
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            journal["child_start_pending"] = False
            a3_save_journal(journal)

    def capture(self, evidence, settled=False):
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            if journal["execution"] == "closed":
                raise A3Premise("evidence arrived after immutable execution closure")
            previous = journal["evidence"]
            saved = {a3_json(e): e for e in previous.get("refusal_evidence") or []}
            saved.update({a3_json(e): e for e in evidence.get("refusal_evidence") or []})
            value = dict(evidence)
            value.update(a3_stop_evidence(value, self.harness))
            if evidence.get("uncertainty"):
                for key in ("terminal_stop_text", "limit_signal", "network_signal"):
                    if previous.get(key):
                        value[key] = previous[key]
            if "streams_complete" not in value and "streams_complete" in previous:
                value["streams_complete"] = previous["streams_complete"]
            settled = bool(settled and value.get("streams_complete") is not False)
            if value.get("streams_complete") is False and not value.get("uncertainty"):
                value["uncertainty"] = "native streams did not reach EOF"
            value["refusal_evidence"] = list(saved.values())
            value["refusal_count"] = max(previous.get("refusal_count") or 0,
                                         evidence.get("refusal_count") or 0, len(saved))
            if value["refusal_count"] == 0 and (value.get("uncertainty") or not settled):
                value["refusal_count"] = None
            value["refusal_texts"] = list(dict.fromkeys(
                (previous.get("refusal_texts") or []) + (evidence.get("refusal_texts") or [])))
            if not settled or evidence.get("uncertainty") or (
                    (previous.get("refusal_count") or 0) > (evidence.get("refusal_count") or 0)):
                value.pop("native_exit_class", None)
            if previous.get("report_text") and not value.get("report_text"):
                value["report_text"] = previous["report_text"]
            value["settled"] = bool(settled)
            journal["evidence"] = value
            if settled:
                journal["execution"] = "finalising"
            if value.get("refusal_count"):
                a3_notice(journal, "refusal-detected")
            a3_save_journal(journal)
        a3_barrier("native-evidence", journal)
        return value

    def stop_request(self):
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            return journal.get("stop_intent")

    def observe_model(self, value):
        observation = a3_model_observation(value)
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            if observation["subject"] != "helper" or observation["identity"] != journal["pass_id"]:
                raise A3Premise("model observation belongs to another lifecycle")
            if journal["disposition"]["phase"] != "none":
                raise A3Premise("model observation arrived after disposition preparation")
            journal.setdefault("model_observations", []).append(observation)
            a3_save_journal(journal)

    def stop(self, cause, explicit=False, reason=None):
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            if journal["disposition"]["phase"] in ("sealed", "launch-intent", "resolved"):
                return False
            journal["stop_cause"] = cause
            if explicit:
                journal["stop_intent"] = {"cause": cause, "explicit": True, "reason": reason,
                                          "requester": a3_process_identity(os.getpid()), "ts": now()}
            a3_save_journal(journal)
        a3_barrier("child-stop-request", journal)
        return True

    def infrastructure_failure(self, exc):
        # Only a process actually started may be settled here. The launcher result is never invented.
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            if journal["execution"] in ("prepared", "closed"):
                return
            if self.process is not None:
                journal.update(child_started=True, child_start_pending=False, child_pid=self.process.pid)
                journal["child"] = journal.get("child") or a3_process_identity(self.process.pid)
            a3_save_journal(journal)
        if not journal.get("stop_cause"):
            self.stop("infrastructure-failure")
        if self.process is not None and self.process.poll() is None:
            signal_group(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=KILL_GRACE_S)
            except subprocess.TimeoutExpired:
                signal_group(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=KILL_GRACE_S)
        settled = self.journal["evidence"].get("settled", False)
        if self.process is not None and not settled:
            if self.stream_settler is not None:
                evidence, settled = self.stream_settler()
            else:
                try:
                    self.process.communicate(timeout=KILL_GRACE_S)
                    settled = True
                except subprocess.TimeoutExpired:
                    settled = False
                raw, uncertainty = a3_suffix(self.journal["boundary"])
                evidence = a3_native_evidence(raw, self.harness)
                evidence.update(source=self.journal["boundary"].get("path"), uncertainty=uncertainty,
                                process_exit=self.process.returncode, streams_complete=settled)
            self.capture(evidence, settled=settled)
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            if journal["execution"] in ("prepared", "closed"):
                return  # Saved authoritative outcome wins over a later infrastructure error.
            journal["evidence"]["uncertainty"] = "infrastructure failure: %s" % exc
            unknown_launch = self.process is None and journal.get("child_start_pending") is not False
            if (journal["child_started"] or unknown_launch) and not journal["evidence"].get("refusal_count"):
                journal["evidence"]["refusal_count"] = None
            elif not journal["child_started"]:
                journal["evidence"]["refusal_count"] = 0
            journal["evidence"]["settled"] = not unknown_launch and (self.process is None or bool(settled))
            a3_save_journal(journal)
        if journal["report"] and journal["evidence"].get("report_text") and not os.path.exists(journal["report"]):
            write_atomic(journal["report"], journal["evidence"]["report_text"].rstrip() + "\n")
        close = dict(journal.get("outcome") or {})
        close["native_error"] = close.get("error")
        close.update({"event": "lane-closed", "ts": now(), "run": journal["run"], "lane": journal["lane"],
                 "exit_class": "refusal" if journal["evidence"].get("refusal_count") else
                               "error" if journal["child_started"] or unknown_launch else "setup-failed", "exit_code": 3,
                 "process_exit": self.process.returncode if self.process is not None else None,
                 "error": str(exc), "report": journal["report"], "class": journal["start"].get("class"),
                 "wrapper_pid": os.getpid(), "child_started": journal["child_started"]})
        if journal.get("kind") == "beat":
            close.update(event="hold-beat", ok=False)
            self.finish_beat(close)
            return
        self.finish(close, allow_move=False)

    def finish_beat(self, line):
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            if (journal.get("stop_intent") or {}).get("explicit"):
                line.update(exit_class="killed", exit_code=3, ok=False, stop_cause="explicit-stop")
            line.update({key: journal["evidence"].get(key) for key in
                         ("terminal_stop_text", "limit_signal", "network_signal")})
            line.update(pass_id=journal["pass_id"], invocation_id=journal["pass_id"],
                        close_id=journal.setdefault("close_id", uuid.uuid4().hex),
                        a3_record=journal["record"], event="hold-beat",
                        refusal_count=journal["evidence"].get("refusal_count"),
                        refusal_evidence=journal["evidence"].get("refusal_evidence") or [])
            journal["outcome"] = line
            if not journal["evidence"].get("settled"):
                line["ok"], line["exit_code"] = False, 3
                if line.get("exit_class") == "completed":
                    line["exit_class"] = "evidence-incomplete"
                journal["execution"] = "finalising"
                journal["disposition"].update(phase="awaiting-head", reason="beat evidence incomplete")
                a3_notice(journal, "beat-incomplete")
                line["notice"] = journal["notices"][-1]
                a3_save_journal(journal)
                return line
            journal["disposition"].update(phase="resolved", decision="none",
                                           reason="beat invocation never disposes a task")
            journal["child_settled"] = True
            if journal["evidence"].get("uncertainty"):
                line["ok"], line["exit_code"] = False, 3
                if line.get("exit_class") == "completed":
                    line["exit_class"] = "evidence-incomplete"
                a3_notice(journal, "beat-incomplete")
            if line.get("refusal_count"):
                a3_notice(journal, "beat-refusal")
            line["notice"] = journal["notices"][-1] if journal["notices"] else None
            journal["close"] = dict(line)
            journal["execution"] = "closed"
            a3_save_journal(journal)
            records, _ = a3_record_rows(self.gate.record)
            native = [row for row in records if row.get("event") == "hold-beat"
                      and row.get("invocation_id") == journal["pass_id"] and not row.get("observation_only")]
            if native and native != [line]:
                raise A3Premise("conflicting native beat result")
            if not native:
                _append_record_unlocked(self.gate.record, line)
        return line

    def finish(self, close, allow_move=True):
        """Persist native facts, seal once, attempt at most once, then project one close."""
        report_digest = file_sha(close["report"]) if close.get("report") else None
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            if journal["execution"] == "closed":
                return journal["close"]
            journal["execution"] = "finalising"
            close = dict(close)
            close.setdefault("harness", journal["harness"])
            close.setdefault("not_applicable", dict(CLOSE_NOT_APPLICABLE.get(journal["harness"], {})))
            close.update({key: journal["evidence"].get(key) for key in
                          ("terminal_stop_text", "limit_signal", "network_signal")})
            if journal["child_started"] and journal.get("report") and report_digest is None:
                close["report_error"] = "report was not durably saved at %s" % journal["report"]
                if not journal["evidence"].get("uncertainty"):
                    journal["evidence"]["uncertainty"] = close["report_error"]
            close.update({"pass_id": journal["pass_id"], "pass_ordinal": journal["ordinal"],
                          "a3_record": journal["record"], "child_started": journal["child_started"],
                          "stop_cause": journal.get("stop_cause"),
                          "refusal_count": journal["evidence"].get("refusal_count"),
                          "refusal_evidence": journal["evidence"].get("refusal_evidence"),
                          "evidence_complete": bool(journal["evidence"].get("settled", False)
                                                    and not journal["evidence"].get("uncertainty"))})
            close["model_observations"] = journal.get("model_observations") or []
            if (not journal["evidence"].get("settled") or journal["evidence"].get("uncertainty")) \
                    and close.get("exit_class") == "completed":
                close["exit_class"], close["exit_code"] = "evidence-incomplete", 3
            close["report_sha256"] = report_digest
            pending = journal["start"].get("controls_pending") or []
            if pending and ("controls_deferred" not in close or close.get("exit_class") != "completed"
                            and any(v.get("result") == "checked" for v in close.get("controls_deferred") or [])):
                close["controls_deferred"] = deferred_verdicts(
                    pending, close.get("report"), journal["evidence"].get("report_text") or "",
                    bool(journal["evidence"].get("report_text")) and close["evidence_complete"],
                    report_digest is not None, close.get("exit_class"))
            journal["child_settled"] = not journal.get("child_start_pending") and (
                self.process is None or self.process.poll() is not None)
            journal["outcome"] = close
            if not journal["evidence"].get("settled"):
                journal["disposition"].update(phase="awaiting-head", reason="incomplete evidence; no final close")
                close["exit_code"] = 3
                a3_notice(journal, "evidence-incomplete")
                close["notice"] = journal["notices"][-1]
                a3_save_journal(journal)
                return close
            a3_save_journal(journal)
        a3_barrier("outcome-saved", journal)
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
        prepared = a3_prepare_disposition(journal, allow_move=allow_move)
        a3_barrier("before-seal", journal)
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            intent = journal.get("stop_intent")
            if intent and intent.get("explicit"):
                close["exit_class"], close["exit_code"] = "killed", EXIT_CODES.get("killed", 3)
                close["stop_cause"] = journal["stop_cause"] = "explicit-stop"
                if journal["start"].get("controls_pending"):
                    close["controls_deferred"] = deferred_verdicts(journal["start"]["controls_pending"],
                        close.get("report"), journal["evidence"].get("report_text") or "", False,
                        report_digest is not None, "killed")
                prepared = {"phase": "awaiting-head" if close.get("refusal_count") else "resolved",
                            "decision": "pending" if close.get("refusal_count") else "held",
                            "reason": intent.get("reason") or "explicit stop"}
            journal["disposition"].update(prepared)
            journal["outcome"] = close
            a3_save_journal(journal)  # Stop recheck and durable seal are one record transaction.
        a3_barrier("decision-sealed", journal)
        if journal["disposition"]["phase"] == "sealed":
            a3_launch(self)
        with a3_record_lock(self.gate.record):
            journal = self.refresh()
            close["disposition"] = json.loads(a3_json(journal["disposition"]))
            close["close_id"] = journal.setdefault("close_id", uuid.uuid4().hex)
            journal["close"] = close
            journal["execution"] = "prepared"
            a3_notice(journal)
            close["notice"] = journal["notices"][-1] if journal["notices"] else None
            journal["close"] = close
            a3_save_journal(journal)
        a3_barrier("prepared-outcome", journal)
        a3_project(self, repair=False)
        a3_barrier("notice-rendering", self.journal)
        return self.journal["close"]


A3_WRITE_SCAN_LIMIT = 200000   # entries walked in a fallen-back pass's write folders; set by judgement, unmeasured
A3_WRITE_SAMPLE = 20           # paths a held disposition names; set by judgement, unmeasured


def a3_fallback_writes(journal):
    """(paths, why) for a confirmed fallback's write folders. After a silent fallback nothing the
    fallen-back model produced is kept and the pass restarts from the state before it (owner's
    Safety-FP rule), and no snapshot of that state exists, so the only clean move is one with
    nothing to undo. `paths` are the files and directories changed since the pass began, read from
    their modification times, a directory's standing for what was removed from it; the pass's own
    report is left out. `why` is set when the check cannot finish, and then `paths` proves nothing.
    The read is coarse on the safe side: a sibling's write in a shared folder, or a write in the
    pass's first second, reads as changed, and the head sees the paths."""
    writes = (journal.get("start") or {}).get("writes") or []
    began = parse_ts(journal.get("created"))
    if not writes:
        return [], None
    if began is None:
        return [], "the pass's start time is unreadable"
    report = journal.get("report")
    changed, walked = [], 0
    for root in writes:
        stack = [root]
        while stack:
            path = stack.pop()
            walked += 1
            if walked > A3_WRITE_SCAN_LIMIT:
                return changed, "the write folders hold more than %d entries" % A3_WRITE_SCAN_LIMIT
            try:
                info = os.lstat(path)
                if stat.S_ISDIR(info.st_mode):
                    stack.extend(os.path.join(path, name) for name in os.listdir(path))
            except FileNotFoundError:
                changed.append(path)   # a write grant the pass removed
                continue
            except OSError as exc:
                return changed, "%s cannot be read: %s" % (path, exc)
            if max(info.st_mtime, info.st_ctime) >= began and path != report:   # ctime too: a write can keep its old mtime
                changed.append(path)
    return sorted(changed, key=os.path.isdir), None   # files first: they say what the pass wrote


def a3_prepare_disposition(journal, allow_move=True):
    outcome, evidence = journal.get("outcome") or {}, journal["evidence"]
    fallback = outcome.get("fallback") or {}
    detected = bool(evidence.get("refusal_count"))
    confirmed = fallback.get("verdict") == "fallback"
    if not detected and not confirmed:
        if not evidence.get("settled") or evidence.get("uncertainty"):
            return {"phase": "awaiting-head", "reason": "incomplete evidence"}
        if not allow_move and journal.get("recovered_orphan"):
            return {"phase": "awaiting-head", "reason": "head judgement required"}
        return {"phase": "resolved", "decision": "none", "reason": "no movement trigger"}
    if not evidence.get("settled") or evidence.get("uncertainty"):
        return {"phase": "awaiting-head", "reason": "incomplete or uncertain evidence"}
    if not allow_move or outcome.get("exit_class") == "refusal-continued" and not confirmed:
        return {"phase": "awaiting-head", "reason": "head judgement required"}
    # E3–E5 head judgement and evidence holds precede E7 ordinary option/exhaustion holds.
    if (confirmed or outcome.get("exit_class") == "refusal") and a3_families_exhausted(journal):
        return {"phase": "resolved", "decision": "held", "reason": A3_FAMILY_HOLD}
    if journal.get("no_swap"):
        return {"phase": "resolved", "decision": "held", "reason": "movement disabled (--no-swap)"}
    if confirmed:
        # Only the automatic move stops here: the head's own `recover --decision move` is the check.
        changed, why = a3_fallback_writes(journal)
        if changed or why:
            return {"phase": "awaiting-head", "fallback_writes": {
                        "count": len(changed), "paths": changed[:A3_WRITE_SAMPLE], "unread": why},
                    "reason": "a confirmed fallback may have changed its write folders (%s), and its "
                              "successor would inherit them: restore them, then recover --decision "
                              "move" % (why or "%d path(s), first %s" % (len(changed), changed[0]))}
    return a3_prepare_move(journal)


def a3_prepare_move(journal):
    """Read only the immutable task snapshot; output evidence is never continuation input."""
    if a3_families_exhausted(journal):
        return {"phase": "resolved", "decision": "held", "reason": A3_FAMILY_HOLD}
    provenance = journal.get("continuation_input") or journal.get("input") or {}
    start = journal["start"]
    snapshot = provenance.get("snapshot")
    try:
        data = read_bytes(snapshot) if snapshot else None
        if data is None or a3_digest(data) != provenance.get("snapshot_sha256"):
            raise A3Premise("current task snapshot unavailable or integrity check failed")
        estimate = provenance.get("estimate")
        if isinstance(estimate, bool) or not isinstance(estimate, (float, int)) or \
                not math.isfinite(estimate) or estimate <= 0:
            raise A3Premise("validated current-pass estimate unavailable")
        reads, writes = start.get("grants"), start.get("writes")
        if not isinstance(reads, list) or not isinstance(writes, list):
            raise A3Premise("exact read/write grant capability unavailable")
        if len(reads) != len(set(reads)) or len(writes) != len(set(writes)):
            raise A3Premise("grant membership/length mismatch")
        # Known flagged inputs require a separate reviewed safe input; never filter them silently.
        if journal["evidence"].get("flagged_input") or journal["evidence"].get("input_isolation_unknown"):
            raise A3Premise("safe-input isolation capability unavailable")
        forbidden = [journal.get("report"), journal.get("boundary", {}).get("path")]
        text = data.decode("utf-8")
        if any(payload in text for payload in journal["evidence"].get("refusal_texts") or []):
            raise A3Premise("current brief overlaps a retained refused response")
        if any(path and path in text for path in forbidden):
            raise A3Premise("task snapshot refers to refused output or transcript")
        effort = start.get("effort")
        target = "codex" if journal["harness"] == "claude" else "claude"
        if target == "codex":
            model = "gpt-6-astra"
            if effort not in ("low", "medium", "high", "xhigh", "max"):
                raise A3Premise("same-effort target capability unavailable")
            routing = {"source": "configured Codex family target", "model": model}
        else:
            route_path = start.get("routing_path") or os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "routing.json")
            route = load_routing(route_path)
            row = route.get("classes", {}).get(start.get("class"))
            if not row:
                raise A3Premise("configured Claude class routing unavailable")
            model = row.get("model", {}).get("default")
            if model not in row.get("model", {}).get("options", []) or \
                    effort not in row.get("effort", {}).get("options", []):
                raise A3Premise("configured Claude routing or same-effort capability unavailable")
            routing = {"source": route_path, "sha256": file_sha(route_path), "model": model}
        successor = journal["lane"] + "-" + target + "-" + journal["disposition"]["id"]
        derived = os.path.join(a3_namespace(journal["record"]), journal["pass_id"] + ".continuation")
        header = ("MOVEMENT: task pass %s continues as %s at effort %s. "
                  "Only the recorded task brief follows.\n\n" % (journal["pass_id"], successor, effort))
        write_atomic(derived, header.encode("utf-8") + data, binary=True)
        wrapper = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "codex-lane.py" if target == "codex" else "lane.py")
        command = [sys.executable, wrapper, "spawn", "--run", journal["run"], "--lane", successor,
                   "--class", start["class"], "--brief", derived, "--record", journal["record"],
                   "--reason", "(a) recorded task movement", "--choice-reason", "same effort family movement",
                   "--model", model, "--effort", effort, "--expect-usd", str(estimate),
                   "--delegation", start.get("mode") or "single",
                   "--delegation-src", start.get("mode_src") or "head", "--detach", "--no-wait"]
        command += ["--source-pass", journal["pass_id"], "--source-disposition", journal["disposition"]["id"]]
        for value in reads:
            command += ["--grant", value]
        for value in writes:
            command += ["--write", value]
        if target == "codex":
            command += ["--cwd", writes[0] if writes else start.get("cwd") or vault_root()]
            if not writes:
                command += ["--read-only"]
        else:
            command += ["--grants-only", "--routing", routing["source"]]
        return {"phase": "sealed", "decision": "move", "target": target, "model": model,
                "effort": effort, "grants": reads, "writes": writes, "routing": routing,
                "successor": successor, "brief": derived, "brief_sha256": file_sha(derived),
                "source_snapshot_sha256": provenance["snapshot_sha256"],
                "estimate": estimate, "estimate_source": provenance["estimate_source"],
                "command": command}
    except (A3Premise, OSError, ValueError, TypeError, SystemExit) as exc:
        return {"phase": "awaiting-input", "decision": "pending", "reason": str(exc)}


def a3_launch(owner):
    with a3_record_lock(owner.gate.record):
        journal = owner.refresh()
        disposition = journal["disposition"]
        if disposition["phase"] != "sealed" or disposition.get("attempted"):
            return
        disposition.update(phase="launch-intent", attempted=True, launch_intent=now())
        a3_save_journal(journal)
    a3_barrier("launch-intent", journal)
    command = list(disposition["command"])
    stub = os.environ.get(SWAP_CMD_ENV)
    if stub:
        command = shlex.split(stub) + command[3:]
    result, error = None, None
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=SWAP_TIMEOUT_S,
                                close_fds=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = str(exc)
    a3_barrier("successor-returned", journal)
    with a3_record_lock(owner.gate.record):
        journal = owner.refresh()
        rows, _ = a3_record_rows(owner.gate.record)
        starts = [r for r in rows if r.get("lane") == disposition["successor"]
                  and r.get("event") in ("lane-spawned", "lane-respawned") and r.get("pid")]
        journal["disposition"].update(
            phase="resolved", decision="moved" if starts else "held",
            reason="successor start recorded" if starts else "launch outcome unconfirmed",
            launch_returncode=result.returncode if result is not None else None,
            launch_error=error,
            acknowledgement=starts[-1] if starts else None)
        a3_save_journal(journal)


def a3_project(owner, repair=False):
    with a3_record_lock(owner.gate.record):
        journal = owner.refresh()
        if journal["execution"] not in ("prepared", "closed"):
            raise A3Premise("no prepared execution close to project")
        record = journal["record"]
        if os.path.exists(record):
            record_stat = os.stat(record)
            identity = {"device": record_stat.st_dev, "inode": record_stat.st_ino}
            if journal.get("record_identity") not in (None, identity):
                raise A3Premise("record replacement prevents close projection")
        try:
            rows, _ = a3_record_rows(record)
        except A3Premise:
            if not repair:
                raise
            rows, raw = a3_record_rows(record, allow_tail=True)
            before = os.stat(record)
            identity = {"device": before.st_dev, "inode": before.st_ino}
            if journal.get("record_identity") not in (None, identity):
                raise A3Premise("record replacement prevents projection repair")
            damage = [a3_digest(line.rstrip(b"\r\n")) for _, line in a3_scan_record(raw)[1]]
            repair_id = a3_digest(a3_json([journal["pass_id"], damage]))
            witness = {"damaged_rows": damage, "record_identity": identity,
                       "observed_sha256": a3_digest(raw), "observed_bytes": len(raw)}
            journal.setdefault("record_repairs", {}).setdefault(repair_id, witness)
            a3_save_journal(journal)
            marker = {"event": "record-tail-repaired", "pass_id": journal["pass_id"],
                      "repair_id": repair_id, "damaged_rows": damage, "run": journal["run"],
                      "lane": journal["lane"], "record": record}
            current = os.stat(record)
            if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                    before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
                raise A3Premise("unsupported concurrent writer during projection repair")
            separator = bool(raw and not raw.endswith(b"\n"))
            # Retain every existing byte, including the damaged row. Repair never rewrites
            # the record, so a writer that ignores our lock cannot have its complete rows erased.
            _append_record_unlocked(record, marker, separator=separator)
            expected = raw + (b"\n" if separator else b"") + (json.dumps(marker) + "\n").encode("utf-8")
            if read_bytes(record) != expected or os.stat(record).st_ino != before.st_ino:
                raise A3Premise("unsupported writer or record replacement during repair")
            a3_notice(journal, "projection-repaired")
            a3_save_journal(journal)
            rows, _ = a3_record_rows(record)
        matches = [r for r in rows if r.get("event") == journal["close"]["event"]
                   and r.get("pass_id") == journal["pass_id"]]
        if matches and (len(matches) != 1 or matches[0] != journal["close"]):
            raise A3Premise("conflicting close projection")
        if not matches:
            _append_record_unlocked(record, journal["close"])
    a3_barrier("close-projection", journal)
    with a3_record_lock(owner.gate.record):
        journal = owner.refresh()
        journal["execution"] = "closed"
        a3_save_journal(journal)
    a3_barrier("committed-journal", journal)


def a3_observe(record, run, lane_id):
    """Observe without acquiring lifetime authority, signalling or reading mutable evidence."""
    journal = a3_latest(record, run, lane_id)
    if journal is None:
        return None
    if journal["execution"] == "closed":
        return {"state": "closed", "journal": journal}
    identity = journal["owner"]
    live = a3_liveness(identity)
    if live != "dead":
        return {"state": "running" if live == "alive" else "uncertain", "journal": journal}
    a3_barrier("observer-snapshot", journal)
    with a3_record_lock(record):
        current = a3_latest(record, run, lane_id)
        if current is None or current["pass_id"] != journal["pass_id"]:
            raise A3Premise("pass changed during orphan observation")
        journal = current
        if journal["execution"] == "closed":
            return {"state": "closed", "journal": journal}
        if journal["owner"] != identity or a3_liveness(journal["owner"]) != "dead":
            return {"state": "uncertain", "journal": journal}
        rows, _ = a3_record_rows(record)
        observation = {"event": "orphan-observed", "ts": now(), "run": run, "lane": lane_id,
                       "pass_id": journal["pass_id"], "a3_record": a3_canonical(record),
                       "owner": identity, "child_state": a3_liveness(journal.get("child")),
                       "phase": journal["execution"], "stop_cause": journal.get("stop_cause"),
                       "report": journal.get("report"), "notice_id": journal["notice_id"],
                       "recover": a3_recovery_command(journal)}
        if not any(r.get("event") == "orphan-observed" and r.get("pass_id") == journal["pass_id"]
                   for r in rows):
            _append_record_unlocked(record, observation)
        a3_notice(journal, "orphan")
        a3_save_journal(journal)
    return {"state": "orphan", "journal": journal}


def a3_request_stop(record, run, lane_id, pass_id, cause, reason, explicit=False):
    with a3_record_lock(record):
        journal = a3_latest(record, run, lane_id, include_beats=True)
        if journal is None or journal["pass_id"] != pass_id:
            raise A3Premise("stop request names a stale pass")
        if journal["disposition"]["phase"] in ("sealed", "launch-intent", "resolved") or \
                journal["execution"] == "closed":
            return False, journal
        if not explicit and journal["execution"] != "running":
            return False, journal
        previous = journal.get("stop_intent")
        if previous and previous.get("explicit"):
            return True, journal
        intent = {"cause": cause, "reason": reason, "explicit": explicit, "ts": now(),
                  "requester": a3_process_identity(os.getpid())}
        journal["stop_intent"], journal["stop_cause"] = intent, cause
        a3_save_journal(journal)
        _append_record_unlocked(record, {"event": "stop-requested", "ts": now(), "run": run,
                                         "lane": lane_id, "pass_id": pass_id, "intent": intent})
        return True, journal


def a3_exit_code(journal):
    """Pending or uncertain public outcomes use the existing refusal/orphan status, 3 (E6)."""
    close = journal.get("close") or journal.get("outcome") or {}
    if close.get("refusal_count") or journal["evidence"].get("uncertainty") or not a3_committed(journal):
        return 3
    return close.get("exit_code", 3)


def void_report_line(close):
    """The line that stands in for a void report, or None. A pass with a confirmed fallback is void:
    nothing the fallen-back model produced is kept, its report among it, so no display of a close
    shows that text (register 2026-10-21 16:46 d). The file stays on disk for the record. Names the
    continuation's report where the task moved."""
    if (close.get("fallback") or {}).get("verdict") != "fallback":
        return None
    disposition = close.get("disposition_current") or close.get("disposition") or {}
    successor = disposition.get("successor") if disposition.get("decision") == "moved" else None
    line = "report void: a confirmed fallback ran this pass, so nothing it produced is kept"
    if successor and close.get("report"):
        name = "%s-report-%s.md" % (close.get("run"), successor)
        return "%s; the continuation is lane %s, report: %s" % (
            line, successor, os.path.join(os.path.dirname(close["report"]), name))
    return "%s; no continuation has started (%s)" % (line, disposition.get("reason") or "no disposition")


def a3_render(journal, fmt="text", report_words=None):
    close = dict(journal.get("close") or journal.get("outcome") or {})
    notice = journal["notices"][-1] if journal.get("notices") else None
    close["notice"] = notice
    close["disposition_current"] = journal["disposition"]
    # Inspection supplies N5 before an orphan decision, without changing durable notices.
    family_rule = a3_family_rule_context(journal)
    decisions = []
    if not a3_committed(journal) and a3_liveness(journal.get("owner")) == "dead" \
            and journal["evidence"].get("streams_complete") is not False:
        decisions = ["hold", "recovered"]
        triggered = journal["evidence"].get("refusal_count") or \
                    (journal.get("outcome") or {}).get("fallback", {}).get("verdict") == "fallback"
        if triggered and journal.get("kind") != "beat" and not journal.get("no_swap") \
                and not a3_families_exhausted(journal):
            decisions.append("move")
    if fmt == "json":
        print(a3_json({"state": journal["execution"], "pass_id": journal["pass_id"],
                       "close": close or None, "notice": notice,
                       "allowed_decisions": decisions, "family_rule": family_rule,
                       "public_exit_code": a3_exit_code(journal),
                       "recover": a3_recovery_command(journal)}))
    else:
        print("lane %s/%s · pass %s · %s · %s" %
              (journal["run"], journal["lane"], journal["pass_id"], journal["execution"],
               close.get("exit_class") or "process outcome unknown"))
        if notice:
            print(a3_notice_text(notice))
        else:
            print("recovery inspection: " + a3_recovery_command(journal))
        if family_rule and not (notice and notice["payload"].get("rule")):
            print(a3_family_rule_text(family_rule))
        print("allowed decisions: " + (", ".join(decisions) or "none; observation only"))
        path = journal.get("report")
        void = void_report_line(close)
        if void:
            print(void)
        elif path and os.path.isfile(path):
            shown = cut_words(read_text(path, "saved report"), report_words)[0]
            if shown:
                print(shown)
    return a3_exit_code(journal)


def a3_visible_close(journal):
    close = dict(journal["close"])
    close["notice"] = journal["notices"][-1] if journal.get("notices") else None
    close["disposition_current"] = journal["disposition"]
    return close


def a3_render_claude_close(journal, fmt, report_words):
    close, opened = a3_visible_close(journal), journal["start"]
    emit(summary_of(journal["run"], journal["lane"], opened.get("class"),
                    opened.get("model"), opened.get("effort"), close),
         close, report_words, fmt, opened)
    return a3_exit_code(journal)


def a3_watch(record, run, lane_id, fmt="text", report_words=None, max_wait=0, poll=1,
             appear=0, silence=None, worker=None, renderer=None):
    if a3_latest(record, run, lane_id) is None:
        return None
    began, running_seen, requested_stop = time.monotonic(), False, False
    while True:
        state = a3_observe(record, run, lane_id)
        if state is None:
            if worker is None:
                return None  # Legacy records remain readable by their existing renderer.
            if worker.poll() is not None:
                print("detached worker exited before publishing its pass")
                return worker.returncode or 3
            time.sleep(min(poll, 0.5))
            continue
        journal = state["journal"]
        if worker is not None and journal["original_owner"]["pid"] != worker.pid:
            if worker.poll() is not None:
                print("detached worker exited without publishing this invocation")
                return worker.returncode or 3
            time.sleep(min(poll, 0.5))
            continue
        if state["state"] == "closed":
            if not running_seen and time.monotonic() - began < appear:
                time.sleep(min(poll, 0.5))
                continue
            if renderer:
                code = renderer(journal)
            elif journal["harness"] == "claude":
                code = a3_render_claude_close(journal, fmt, report_words)
            else:
                code = a3_render(journal, fmt, report_words)
            if journal.get("close", {}).get("refusal_count") or journal["evidence"].get("uncertainty") \
                    or not a3_committed(journal):
                return a3_exit_code(journal)
            if not running_seen and worker is None:
                sys.stderr.write("lane %s/%s is already closed (%s)\n" %
                                 (run, lane_id, journal["close"].get("exit_class")))
                return 2  # Base already-closed observation convention.
            if requested_stop:
                return code
            return code if journal["harness"] == "codex" or worker is not None else 0
        running_seen = True
        if state["state"] == "orphan":
            a3_render(journal, fmt, report_words)
            return 3
        if silence and journal["execution"] == "running":
            path = journal["boundary"].get("path")
            silent_s, label, bound = silence_of(
                parse_ts(journal["created"]) or time.time(), path,
                progress_path(run, lane_id), silence, silence)
            if silent_s > bound and label != "no transcript":
                accepted, _ = a3_request_stop(record, run, lane_id, journal["pass_id"], "stall",
                                              "watch silence request", explicit=False)
                requested_stop = requested_stop or accepted
        if max_wait and time.monotonic() - began >= max_wait:
            if fmt == "json":
                print(a3_json({"state": state["state"], "pass_id": journal["pass_id"],
                               "result": "still-running"}))
            else:
                print("still-running: lane %s/%s · %s" % (run, lane_id, state["state"]))
            return EXIT_STILL_RUNNING
        pause = max(0.01, poll)  # Minimum poll is set by judgement, unmeasured.
        if max_wait:
            pause = min(pause, max(0.0, max_wait - (time.monotonic() - began)))
        time.sleep(pause)


def a3_recover(args, harness, explicit_kill=False):
    record = a3_canonical(store_paths(args.run, args.lane, args.record)["record"])
    try:
        journal = a3_latest(record, args.run, args.lane, include_beats=True)
        if journal is None:
            raise A3Premise("legacy invocation has no A3 journal; ownership cannot be inferred")
        if journal["pass_id"] != args.pass_id:
            raise A3Premise("recovery names a stale pass")
        if journal["harness"] != harness:
            raise A3Premise("recovery names the wrong wrapper family")
        if journal.get("kind") == "beat" and args.decision == "move":
            raise A3Premise("a beat has no task movement disposition")
        if args.decision == "move" and a3_families_exhausted(journal):
            raise A3Premise(A3_FAMILY_HOLD + "; allowed decisions: hold, recovered")
        if args.decision == "move" and journal.get("no_swap"):
            raise A3Premise("movement disabled (--no-swap); allowed decisions: hold, recovered")
        if not args.decision and not args.repair_projection and not explicit_kill:
            return a3_render(journal, args.format, args.report_words) or 3
        if args.decision and not (args.reason or "").strip():
            raise A3Premise("a recovery decision requires --reason")
        with A3Gate(record, args.run, args.lane) as gate:
            journal = a3_read_journal(record, args.pass_id)
            current = a3_latest(record, args.run, args.lane, include_beats=True)
            if current["pass_id"] != args.pass_id:
                raise A3Premise("pass changed before recovery acquired ownership")
            if a3_liveness(journal["owner"]) != "dead":
                raise A3Premise("launcher is live or its death cannot be proved")
            owner = A3Owner(gate, harness, args, None)
            owner.journal = journal
            owner.recovering = True
            if a3_committed(journal):
                if args.repair_projection:
                    a3_project(owner, repair=True)
                code = a3_render(owner.journal, args.format, args.report_words)
                return 0 if explicit_kill and journal["close"]["exit_class"] == "killed" else code
            with a3_record_lock(record):
                journal = owner.refresh()
                journal["owner"] = owner.identity
                if not journal["owner"]:
                    raise A3Premise("recovery process birth identity unavailable")
                journal["recovery_owner"] = owner.identity
                journal["recovered_orphan"] = journal["execution"] != "closed"
                a3_save_journal(journal)
            owner.recovering = False
            if args.repair_projection and journal["execution"] in ("prepared", "closed"):
                a3_project(owner, repair=True)
                journal = owner.refresh()
                if not args.decision and not explicit_kill:
                    return a3_render(journal, args.format, args.report_words)
            if journal.get("child_start_pending"):
                raise A3Premise("child launch was interrupted; a surviving child cannot be excluded")
            child = journal.get("child")
            state = (a3_liveness(child) if journal.get("child_started") and
                     not journal.get("child_settled") else "dead")
            if state == "unknown":
                raise A3Premise("child identity unavailable; recovery cannot settle it")
            if state == "alive":
                if not args.stop_child and not explicit_kill:
                    print("recovery pending: verified child remains alive; no execution close")
                    return 3
                owner.stop("explicit-stop" if explicit_kill else "recovery-stop",
                           explicit=explicit_kill, reason=args.reason)
                if a3_process_identity(child["pid"]) != child:
                    raise A3Premise("child identity changed before signal")
                kill_pid_group(child["pid"])
                if a3_liveness(child) != "dead":
                    print("recovery pending: child death is not proved")
                    return 3
            with a3_record_lock(record):
                journal = owner.refresh()
                journal.setdefault("authorisations", []).append(
                    {"decision": "explicit-stop" if explicit_kill else args.decision,
                     "reason": args.reason, "head": a3_process_identity(os.getpid()), "ts": now()})
                journal["owner"] = a3_process_identity(os.getpid())
                if not journal["owner"]:
                    raise A3Premise("recovery process birth identity unavailable")
                if explicit_kill:
                    journal["stop_intent"] = {"explicit": True, "reason": args.reason,
                                               "cause": "explicit-stop"}
                    journal["stop_cause"] = "explicit-stop"
                a3_save_journal(journal)
            if journal["evidence"].get("streams_complete") is False:
                with a3_record_lock(record):
                    journal = owner.refresh()
                    journal["disposition"].update(phase="awaiting-head",
                        reason="native stream settlement unavailable; rereading a file cannot prove EOF")
                    a3_notice(journal, "orphan")
                    a3_save_journal(journal)
                return a3_render(journal, args.format, args.report_words) or 3
            if not journal["evidence"].get("settled"):
                if journal.get("child_started") is False and journal.get("child_start_pending") is False:
                    # The launch-intent journal precedes Popen. Its absence proves no model ran.
                    evidence = {"refusal_count": 0, "refusal_evidence": [], "report_text": "",
                                "source": "child never started", "uncertainty": None,
                                "native_exit_class": "setup-failed", "process_exit": None}
                else:
                    raw, uncertainty = a3_suffix(journal.get("boundary"))
                    evidence = a3_native_evidence(raw, harness)
                    evidence["source"] = journal.get("boundary", {}).get("path")
                    evidence["uncertainty"] = uncertainty
                owner.capture(evidence, settled=True)  # Child death freezes even unavailable evidence.
            journal = owner.refresh()
            if (not journal["evidence"].get("settled") or journal["evidence"].get("uncertainty")) \
                    and not journal["evidence"].get("refusal_count"):
                with a3_record_lock(record):
                    journal["disposition"].update(phase="awaiting-head",
                                                   reason="classification unavailable")
                    a3_notice(journal, "evidence-unavailable")
                    a3_save_journal(journal)
                return a3_render(journal, args.format, args.report_words) or 3
            evidence = journal["evidence"]
            if journal.get("kind") == "beat":
                line = dict(journal.get("outcome") or {})
                line.update(event="hold-beat", ts=now(), run=args.run, lane=args.lane, ok=False,
                            exit_class="killed" if explicit_kill else "refusal" if
                            evidence.get("refusal_count") else "error", exit_code=3,
                            process_exit=evidence.get("process_exit"), usage=line.get("usage"),
                            reason=args.reason)
                owner.finish_beat(line)
                a3_render(owner.journal, args.format, args.report_words)
                return 0 if explicit_kill and owner.journal["execution"] == "closed" else 3
            if args.decision == "move" and not (evidence.get("refusal_count") or
                    (journal.get("outcome") or {}).get("fallback", {}).get("verdict") == "fallback"):
                raise A3Premise("no refusal or confirmed fallback; movement is not authorised")
            if journal["execution"] not in ("prepared", "closed"):
                close = dict(journal.get("outcome") or {})
                close.update({"event": "lane-closed", "ts": now(), "run": args.run, "lane": args.lane,
                              "exit_class": "killed" if explicit_kill else
                              "refusal" if evidence.get("refusal_count") else "error",
                              "exit_code": 3, "process_exit": close.get("process_exit"),
                              "report": journal["report"], "recovered_by": os.getpid(),
                              "process_outcome": "unknown" if close.get("process_exit") is None else "observed"})
                if not explicit_kill and evidence.get("native_exit_class"):
                    close["exit_class"] = evidence["native_exit_class"]
                elif not explicit_kill and not evidence.get("refusal_count"):
                    if evidence.get("limit_signal"):
                        close["exit_class"] = "limit"
                    elif evidence.get("network_signal"):
                        close["exit_class"] = "network"
                if close.get("process_exit") is None and evidence.get("process_exit") is not None:
                    close["process_exit"] = evidence["process_exit"]
                    close["process_outcome"] = "observed"
                if evidence.get("report_text") and journal["report"] and not os.path.exists(journal["report"]):
                    write_atomic(journal["report"], evidence["report_text"].rstrip() + "\n")
                # The wrapper that knew the box is gone; its start line still names it, and the
                # close summary is the box's one reader.
                spawned_box = (lane_state(load_record(record), args.lane)[1] or {}).get("box")
                if spawned_box and not close.get("box"):
                    close["box"] = spawned_box
                owner.finish(close, allow_move=False)
                journal = owner.refresh()
            elif journal["execution"] == "prepared":
                a3_project(owner, repair=bool(args.repair_projection))
                journal = owner.refresh()
            if explicit_kill:
                a3_render(journal, args.format, args.report_words)
                return 0 if journal["close"]["exit_class"] == "killed" else 3
            if journal["disposition"]["phase"] != "resolved":
                if args.brief:
                    data = read_bytes(args.brief)
                    if data is None:
                        raise A3Premise("reviewed continuation brief unreadable")
                    snapshot = os.path.join(a3_namespace(record), journal["pass_id"] + ".reviewed")
                    write_atomic(snapshot, data, binary=True)
                    journal.setdefault("continuation_input", dict(journal["input"])).update(
                        snapshot=snapshot, snapshot_sha256=a3_digest(data),
                        reviewed_source=os.path.abspath(args.brief))
                if args.expect_usd is not None:
                    journal.setdefault("continuation_input", dict(journal["input"])).update(
                        estimate=require_estimate(args.expect_usd), estimate_source="explicit head recovery")
                attempted = journal["disposition"].get("attempted")
                if attempted:
                    prepared = {"phase": "resolved", "decision": "held",
                                "reason": "launch outcome unconfirmed; prior attempt is not retried"}
                elif args.decision == "move":
                    prepared = a3_prepare_move(journal)
                else:
                    prepared = {"phase": "resolved", "decision": "recovered" if
                                args.decision == "recovered" else "held", "reason": args.reason}
                with a3_record_lock(record):
                    journal["disposition"].update(prepared)
                    journal["disposition"]["head_reason"] = args.reason
                    a3_save_journal(journal)
                if journal["disposition"]["phase"] == "sealed":
                    a3_launch(owner)
                with a3_record_lock(record):
                    journal = owner.refresh()
                    rows, _ = a3_record_rows(record)
                    if journal["disposition"]["phase"] == "resolved" and not any(
                            row.get("event") == "disposition-resolved" and
                            row.get("disposition_id") == journal["disposition"]["id"] for row in rows):
                        _append_record_unlocked(record, {"event": "disposition-resolved", "ts": now(),
                            "run": args.run, "lane": args.lane, "pass_id": journal["pass_id"],
                            "disposition_id": journal["disposition"]["id"],
                            "disposition": journal["disposition"]})
                    a3_notice(journal, "disposition-resolved")
                    a3_save_journal(journal)
            return a3_render(journal, args.format, args.report_words)
    except (A3Premise, OSError) as exc:
        die(str(exc))


def a3_kill(args, harness):
    if not hasattr(args, "format"):
        args.format = "text"
    if not hasattr(args, "report_words"):
        args.report_words = None
    record = store_paths(args.run, args.lane, args.record)["record"]
    try:
        journal = a3_latest(record, args.run, args.lane, include_beats=True)
        if journal is None:
            raise A3Premise("legacy pass has no proven process identities; explicit reconciliation required")
        if journal["execution"] == "closed":
            a3_render(journal, args.format, args.report_words)
            return 0 if journal["close"]["exit_class"] == "killed" else 3
        accepted, journal = a3_request_stop(record, args.run, args.lane, journal["pass_id"],
                                            "explicit-stop", args.reason, explicit=True)
        if not accepted:
            print("kill: disposition already sealed; its recorded decision won")
            a3_render(journal, args.format, args.report_words)
            return 3
        child = journal.get("child")
        if child and a3_liveness(child) == "alive" and a3_process_identity(child["pid"]) == child:
            signal_group(child["pid"], signal.SIGTERM)
        deadline = time.monotonic() + KILL_GRACE_S
        while time.monotonic() < deadline:
            journal = a3_read_journal(record, journal["pass_id"])
            if journal["execution"] == "closed":
                a3_render(journal, args.format, args.report_words)
                return 0 if journal["close"]["exit_class"] == "killed" else 3
            if a3_liveness(journal["owner"]) == "dead":
                break
            time.sleep(0.05)  # Poll interval set by judgement, unmeasured.
        if a3_liveness(journal["owner"]) == "alive" and getattr(args, "escalate", False):
            identity = journal["owner"]
            if a3_process_identity(identity["pid"]) == identity:
                kill_pid_group(identity["pid"], group=False)
        if a3_liveness(journal["owner"]) != "dead":
            print("kill pending: wrapper remains live or uncertain; no ownership transfer")
            return 3
        recovery = argparse.Namespace(**vars(args))
        recovery.pass_id, recovery.decision, recovery.stop_child = journal["pass_id"], None, True
        recovery.repair_projection = True
        recovery.brief = recovery.expect_usd = None
        return a3_recover(recovery, harness, explicit_kill=True)
    except (A3Premise, OSError) as exc:
        die(str(exc))


def a3_add_recover_parser(subparsers, harness):
    parser = subparsers.add_parser("recover", help="inspect or explicitly resolve one immutable pass")
    parser.add_argument("--run", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--record")
    parser.add_argument("--pass", dest="pass_id", required=True)
    parser.add_argument("--decision", choices=("move", "hold", "recovered"))
    parser.add_argument("--reason", default="")
    parser.add_argument("--brief")
    parser.add_argument("--expect-usd", type=float)
    parser.add_argument("--stop-child", action="store_true")
    parser.add_argument("--repair-projection", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--report-words", type=int)
    parser.set_defaults(func=lambda args: a3_recover(args, harness))


def a3_model_observation(value):
    """Typed seam only; this function detects nothing and grants no disposal authority."""
    required = ("subject", "identity", "requested_model", "observed_model", "provenance", "confirmed")
    if not isinstance(value, dict) or set(value) != set(required) or \
            value.get("subject") not in ("head", "helper") or not isinstance(value.get("confirmed"), bool) or \
            any(not isinstance(value.get(key), str) or not value[key] for key in required[1:-1]):
        raise A3Premise("invalid model-observation input")
    return dict(value)


def a3_begin_beat(ctx, harness):
    owner = a3_current(ctx["record"], ctx["run"], ctx["lane"])
    if owner is None:
        raise A3Premise("a beat requires the lifetime/session gate")
    task = a3_latest(ctx["record"], ctx["run"], ctx["lane"])
    if task and (not a3_committed(task) or task["disposition"].get("decision") == "held"):
        raise A3Premise("a held or unsettled task disposition cannot authorise a cache beat")
    context = dict(ctx, a3_kind="beat", report=None, report_path=None)
    line = {"event": "hold-beat-started", "class": ctx["cls"], "model": ctx["model"],
            "effort": ctx["effort"], "session_id": ctx.get("session_id"), "wrapper_pid": os.getpid()}
    owner.begin(context, line, BEAT_PROMPT.encode("utf-8"), BEAT_PROMPT + "\n", ["fixed beat prompt"])
    owner.prelaunch()
    return owner


def _append_record_unlocked(path, payload, separator=False):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(("\n" if separator else "") + json.dumps(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        a3_sync_directory(os.path.dirname(path) or ".")
    except OSError as exc:
        die("spawn record is not writable (%s): %s" % (path, exc))


def append_record(path, payload):
    path = a3_canonical(path)
    with a3_record_lock(path):
        owner = a3_current(path, payload.get("run"), payload.get("lane"))
        if owner or a3_journals(path):
            a3_record_rows(path)
        if owner and owner.journal:
            payload.setdefault("pass_id", owner.journal["pass_id"])
            payload.setdefault("a3_record", path)
        if payload.get("event") == "lane-closed" and payload.get("pass_id"):
            raise A3Premise("A3 close projection requires the lifetime owner's commit")
        if payload.get("event") == "lane-closed" and a3_latest(
                path, payload.get("run"), payload.get("lane")):
            raise A3Premise("unsupported writer cannot close an A3 pass without its commit identity")
        _append_record_unlocked(path, payload)
        if owner and owner.journal and payload.get("event") in ("lane-open", "lane-resumed"):
            journal = owner.refresh()
            record_stat = os.stat(path)
            journal["record_identity"] = {"device": record_stat.st_dev, "inode": record_stat.st_ino}
            a3_save_journal(journal)
    if owner and owner.journal and payload.get("event") in ("lane-open", "lane-resumed"):
        a3_barrier("published-start", owner.journal)


def load_record(path):
    """Every JSON line of a record; an unparseable line (a torn write) is skipped, not fatal."""
    if not os.path.isfile(path):
        die("no spawn record at %s" % path)
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                out.append(record)
    return out


def lane_state(records, lane, session_id=None):
    """The lane's latest open, its latest spawn-ish event (lane-spawned, lane-resumed or lane-respawned) and
    the lane-closed that follows it, if any; with a session id, only that session's lines,
    so a re-spawn of a lane id never reads its predecessor's close as its own."""
    opened = spawned = closed = None
    for record in records:
        if record.get("lane") != lane:
            continue
        if session_id and record.get("session_id") not in (None, session_id):
            continue
        event = record.get("event")
        if event == "lane-open":
            opened, spawned, closed = record, None, None
        elif event in ("lane-spawned", "lane-resumed", "lane-respawned"):
            spawned, closed = record, None
        elif event == "lane-closed":
            if a3_close_valid(record) and (not spawned or not spawned.get("pass_id") or
                                            record.get("pass_id") == spawned.get("pass_id")):
                closed = record
    return opened, spawned, closed


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def parse_ts(ts):
    """A record timestamp (the `now()` shape) as an epoch, or None when unparseable."""
    try:
        return datetime.datetime.strptime(str(ts), "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except (TypeError, ValueError):
        return None


# -------------------------------------------------------------- watching and closing -------

def cut_words(text, limit):
    """The first `limit` words with their line structure kept: (shown, shown count, total,
    cut?). A limit of None shows the whole text (the default: no cut); 0 shows nothing and
    leaves the pointer line to name the file."""
    total = len(text.split())
    if limit is None:
        return text.rstrip(), total, total, False
    if limit <= 0:
        return "", 0, total, total > 0
    if total <= limit:
        return text.rstrip(), total, total, False
    count = 0
    for match in re.finditer(r"\S+", text):
        count += 1
        if count == limit:
            return text[:match.end()].rstrip(), limit, total, True
    return text.rstrip(), total, total, False


NETWORK_RE = re.compile(
    r"\b(?:ENOTFOUND|ECONNREFUSED|ECONNRESET|ETIMEDOUT|EAI_AGAIN)\b|"
    r"can(?:not|'t|’t) (?:reach|connect to) (?:the )?API server|"
    r"connection (?:refused|reset|timed out|failed)|(?:request|connection|API) timeout|"
    r"(?:request|connection) timed out|network (?:error|unreachable)|"
    r"error (?:sending request|connecting)|stream disconnected", re.I)
# Preserve the installed limit + (usage or reset) predicate on the selected terminal
# source, in either order and across lines. This also retains a model-scoped limit's
# complete evidence for the supervisor's existing no-probe, no-resume handling.
USAGE_STOP_RE = re.compile(
    r"usage limit|rate limit|too many requests|quota|\b429\b|"
    r"limit[\s\S]*(?:reset|usage)|(?:reset|usage)[\s\S]*limit", re.I)
CODEX_USAGE_STOP_RE = re.compile(USAGE_STOP_RE.pattern + r"|limit reached", re.I)


def terminal_stop_text(parsed, result_text, stderr_text, subtype, failed, result_is_error=None):
    """Select one complete terminal source before classifying it; never search model prose."""
    error_result = str(subtype or "").startswith("error") if result_is_error is None else result_is_error
    if error_result and isinstance(result_text, str) and result_text.strip():
        return result_text.strip()
    synthetic = parsed.get("terminal_synthetic_text")
    if isinstance(synthetic, str) and synthetic.strip():
        return synthetic.strip()
    if failed:
        for line in reversed((stderr_text or "").splitlines()):
            if line.strip() and (re.search(r"\berror\b|\bfailed\b", line, re.I)
                                 or USAGE_STOP_RE.search(line) or NETWORK_RE.search(line)):
                return line.strip()
    return None


def network_signal(parsed, result_text, stderr_text, subtype, failed, result_is_error=None):
    text = terminal_stop_text(parsed, result_text, stderr_text, subtype, failed, result_is_error)
    if text and not USAGE_STOP_RE.search(text) and NETWORK_RE.search(text):
        return text
    return None


def limit_signal(parsed, result_text, stderr_text, subtype, failed, result_is_error=None):
    text = terminal_stop_text(parsed, result_text, stderr_text, subtype, failed, result_is_error)
    if text:
        if USAGE_STOP_RE.search(text):
            return text
        if NETWORK_RE.search(text):
            return None
    # No named terminal cause: preserve the old synthetic/subtype decisions, never invent network.
    if parsed.get("synthetic_stop"):
        return "transcript: last assistant record has model %s with zero usage" % parsed.get("last_model")
    sub = (subtype or "").lower()
    if "limit" in sub and "budget" not in sub:
        return "subtype %s" % subtype
    return None


def classify(killed, stall, parsed, result, subtype, returncode, parse_error, stderr):
    """The close line's exit_class and, for a limit, the evidence."""
    if parsed.get("refusal"):
        succeeded = bool(result) and result.get("subtype") == "success" and not result.get("is_error")
        stopped = bool(killed or stall or "max_budget" in subtype or "max_turns" in subtype)
        continued = a3_final_success("claude", parsed, returncode, succeeded, stopped)
        return "refusal-continued" if continued else "refusal", None
    if stall:
        return "stall", None
    if killed:
        return "deadline", None
    failed = bool(result.get("is_error")) or returncode != 0
    result_is_error = bool(result.get("is_error")) or subtype.startswith("error")
    network = network_signal(parsed, result.get("result") or "", stderr, subtype, failed, result_is_error)
    if network:
        return "network", network
    signal_text = limit_signal(parsed, result.get("result") or "", stderr, subtype, failed, result_is_error)
    if signal_text:
        return "limit", signal_text
    if "max_budget" in subtype:
        return "budget", None
    if "max_turns" in subtype:
        return "max-turns", None
    if failed or parse_error:
        return "error", None
    return "completed", None


def beat_marker_path(record, run, lane_id):
    """The base name of one lane's session claim, beside its record: `<run>-<lane>-beat.pid`.
    It sits beside the record rather than in a fixed directory so a run under `--record` (a
    suite, a rehearsal on a copy) claims its own lane and never a live run's. The claim itself
    is the advisory lock on `<this>.lock` (session_lock_path); a file of this bare name, left by
    the earlier pid-marker form, holds nothing."""
    return os.path.join(os.path.dirname(os.path.abspath(record)),
                        "%s-%s%s" % (run, lane_id, BEAT_MARKER_SUFFIX))


def session_lock_path(marker):
    """The lock file whose advisory lock IS the claim on a lane's session."""
    return marker + SESSION_LOCK_SUFFIX


def lock_contended(exc):
    """Whether a non-blocking `flock` failed because another holder has the lock (EWOULDBLOCK or
    EAGAIN, the same value on most platforms), as against any other errno — ENOLCK, an unsupported
    filesystem — which says the lock cannot be worked at all (register 2026-09-18 20:0x)."""
    return getattr(exc, "errno", None) in (errno.EWOULDBLOCK, errno.EAGAIN)


def unusable_lock_text(lock, exc, who):
    """The refusal for a lock that cannot be worked, naming the errno and the path, so it is never
    read as another call holding the session."""
    code = getattr(exc, "errno", None)
    name = errno.errorcode.get(code, str(code)) if isinstance(code, int) else "no errno"
    return ("the session lock %s cannot be worked (%s: %s), so %s cannot tell whether another call "
            "holds the session — this is not contention; a session claim that cannot be worked never "
            "starts a call" % (lock, name, getattr(exc, "strerror", None) or exc, who))


def read_session_body(fd):
    """(pid, kind) from a held lock's body `<pid> <kind> <timestamp>`. A body that is empty or
    unreadable — the instant between a holder's lock and its write — still belongs to a holder,
    so the pid reads -1 rather than None and no reader mistakes a live claim for a stale one."""
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        parts = os.read(fd, 96).decode("utf-8", "replace").strip().split()
    except OSError:
        parts = []
    try:
        pid = int(parts[0]) if parts else -1
    except ValueError:
        pid = -1
    kind = parts[1] if len(parts) > 1 and parts[1] in ("beat", "resume") else "beat"
    return (pid if pid > 0 else -1), kind


def holder_text(pid):
    """How a refusal names the holder of a lane's session."""
    return ("pid %d" % pid if isinstance(pid, int) and pid > 0
            else "a pid the lock's body does not name yet")


def session_holder(marker):
    """(pid, kind) of the live call holding the lane's session, else (None, "").

    The claim is an advisory lock, never the presence of a file, so this reader decides by
    ATTEMPTING the same lock non-blocking: the attempt fails → the session is held, and the
    lock file's body names the holder for the diagnostic; it succeeds → nothing holds the
    session, and the probe's own lock is released at once. A reader creates nothing and removes
    nothing, so the read-then-remove race and the empty-file window of the pid-marker form are
    both gone by construction (review finding 2, 2026-09-18). A bare `<run>-<lane>-beat.pid`
    of the earlier form, with no lock file beside it, holds nothing and is ignored; a dead
    holder's lock is released by the kernel, so there is no stale state to clear.

    The probe's own lock is the one cost: a claim arriving during that instant is refused rather
    than admitted, which fails closed — the caller retries — and never lets two calls in."""
    lock = session_lock_path(marker)
    if not os.path.exists(lock):
        return None, ""
    try:
        fd = os.open(lock, os.O_RDWR)
    except OSError:
        return None, ""
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if not lock_contended(exc):
                # The lock cannot be worked at all (ENOLCK, an unsupported filesystem): nothing can
                # tell whether a call holds the session, so this reader refuses as the claim does.
                die(unusable_lock_text(lock, exc, "a reader of the lane's session"))
            return read_session_body(fd)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None, ""
    finally:
        os.close(fd)


def beat_in_flight(marker):
    """The pid holding the lane's session, -1 where one holds it but its body names no pid yet,
    else None (the kind dropped)."""
    return session_holder(marker)[0]


def hold_session(marker, kind, refusal):
    """A context manager holding the lane's session for the length of one call, releasing it
    after, whatever the call did. `refusal` is the caller's own words, printed after the reason
    when the session cannot be claimed: a call that cannot claim it does not run.

    The claim is an ADVISORY LOCK the kernel holds and releases — `fcntl.flock(fd, LOCK_EX |
    LOCK_NB)` on `<marker>.lock` — rather than a file whose existence is the claim (review
    finding 2, 2026-09-18). Three faults of the marker form go with it:
    - the lock is taken atomically before any file content exists, so there is no window in
      which a second entrant sees an empty file and reads it as stale;
    - the kernel releases the lock when the holder dies, so a crashed call wedges no lane shut
      and no reader has to remove anything, which is what the read-then-remove race needed;
    - the check and the claim are one operation, so two callers in either order cannot both pass.

    The body `<pid> <kind> <timestamp>` is written into the locked file for the DIAGNOSTIC
    alone — what a refusal names. A body that cannot be written refuses the call and releases
    the lock: the previous fold's ruling stands (a call that cannot claim the session never
    continues), and a claim whose body is empty for good would leave every later refusal naming
    nobody.

    A `flock` that fails refuses either way, and the refusal says which way (register 2026-09-18
    20:0x): EWOULDBLOCK or EAGAIN is contention, another call holding the session, and names the
    holder; any other errno (ENOLCK, a filesystem that cannot lock) means the lock cannot be worked
    at all, and the refusal names the errno and the lock, never a holder. Refusing in both cases is
    this claim's conservative choice, unlike the run console's viewer opener, which opens anyway on
    an unusable lock: a session claim that cannot be worked must not start a second call on one
    session, while a doubled viewer window costs nothing.

    The one exposure that stays: the descriptor is non-inheritable (PEP 446), so the lock dies
    with this wrapper rather than with a harness child the wrapper leaves behind. That is the
    exposure a pid marker carries too — it records the wrapper's pid, not the harness's — and
    what closes it is the wrapper's own bound (BEAT_TIMEOUT_S) and its process-group kill."""
    lock = session_lock_path(marker)
    try:
        os.makedirs(os.path.dirname(lock) or ".", exist_ok=True)
    except OSError:
        pass
    try:
        fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
    except OSError as exc:
        die("this %s cannot take the lane's session: the lock %s could not be opened (%s) — %s"
            % (kind, lock, exc, refusal))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if not lock_contended(exc):
            os.close(fd)
            die("this %s cannot take the lane's session: %s — %s"
                % (kind, unusable_lock_text(lock, exc, "the claim"), refusal))
        pid, held = read_session_body(fd)
        os.close(fd)
        die("this %s cannot take the lane's session: a held-lane %s is in flight (%s, lock %s) "
            "— %s" % (kind, held, holder_text(pid), lock, refusal))
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, ("%d %s %s\n" % (os.getpid(), kind, now())).encode("utf-8"))
        os.fsync(fd)
    except OSError as exc:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        die("this %s cannot take the lane's session: the lock %s was taken and released again "
            "because its body could not be written (%s), so any refusal it caused would name "
            "nobody — %s" % (kind, lock, exc, refusal))

    class _Held(object):
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass
            return False
    return _Held()


def hold_beat_marker(marker):
    """The beat's own session hold (the name codex-lane.py calls)."""
    return hold_session(marker, "beat", "a second call on one session is the "
                                        "two-processes-on-one-session fault; wait for the call in flight, or end the "
                                        "process that holds it — the kernel releases its lock")


def pid_alive(pid):
    """True/False, or None when the pid is missing or unreadable."""
    if not pid:
        return None
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError):
        return None
    return True


def signal_group(pid, sig):
    try:
        os.killpg(os.getpgid(int(pid)), sig)
        return True
    except (OSError, ValueError):
        try:
            os.kill(int(pid), sig)
            return True
        except (OSError, ValueError):
            return False


def signal_pid(pid, sig):
    """One process, never its group. The wrapper shares a process group with whoever started it
    — a head's own terminal among them — so signalling ITS group would take the caller down with
    the lane; only a lane process, which the wrapper starts in a session of its own, is safe to
    signal by group."""
    try:
        os.kill(int(pid), sig)
        return True
    except (OSError, ValueError):
        return False


def kill_group(process):
    """SIGTERM the lane's process group, wait the grace, SIGKILL; returns (stdout, stderr)."""
    signal_group(process.pid, signal.SIGTERM)
    try:
        return process.communicate(timeout=KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        signal_group(process.pid, signal.SIGKILL)
        try:
            return process.communicate(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired as exc:
            process._a3_stream_incomplete = True
            for pipe in (process.stdout, process.stderr):
                if pipe:
                    pipe.close()
            process.wait(timeout=KILL_GRACE_S)
            return output_text(exc.output), output_text(exc.stderr)


def kill_pid_group(pid, group=True):
    """The same sequence for a lane the wrapper does not own (watch's orphan path): SIGTERM,
    up to KILL_GRACE_S of waiting, then SIGKILL. `group=False` signals the one process instead
    of its group, which is what `kill` does to a WRAPPER pid — see signal_pid."""
    send = signal_group if group else signal_pid
    send(pid, signal.SIGTERM)
    waited = 0.0
    while waited < KILL_GRACE_S and pid_alive(pid):
        time.sleep(0.5)
        waited += 0.5
    if pid_alive(pid):
        send(pid, signal.SIGKILL)


def boxed(command, env):
    """(the command to start, the `box` value) for one lane process (owner decision of 2026-11-04;
    the docstring's "Keeping a helper's signals inside its box"). `command` is never changed and the
    caller's ctx["command"] is never touched, so every configuration hash stays the unboxed
    command's. Called before the owner's prelaunch, so a slow or failing check leaves no launch
    pending. Nothing here may stop a helper: any failure returns the plain command with `off: <why>`."""
    plain = list(command)
    try:
        if shutil.which(plain[0], path=os.pathsep.join(os.get_exec_path(env))) is None:
            # Plain, so Popen raises as it always has and the close records spawn-failed; through
            # the box a failed exec would be exit 71 and no OSError.
            return plain, "%s: %s is not on the helper's PATH" % (BOX_OFF, plain[0])
        path = env.get(BOX_ENV) or BOX_BIN
        if path == BOX_OFF:
            return plain, "%s: %s=%s" % (BOX_OFF, BOX_ENV, BOX_OFF)
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            return plain, "%s: no executable box program at %s" % (BOX_OFF, path)
        box = [path, "-p", BOX_PROFILE]
        probe = subprocess.Popen(box + ["/bin/sh", "-c", "kill -0 $PPID"], env=env, text=True,
                                 errors="replace", stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                 start_new_session=True)
        try:
            _, stderr = probe.communicate(timeout=BOX_PROBE_S)
        except subprocess.TimeoutExpired:
            signal_group(probe.pid, signal.SIGKILL)
            try:
                probe.communicate(timeout=KILL_GRACE_S)
            except subprocess.TimeoutExpired:
                pass
            return plain, "%s: the premise check did not finish within %d s" % (BOX_OFF, BOX_PROBE_S)
        code, words = probe.returncode, " ".join((stderr or "").split())[:BOX_NOTE_CHARS]
        if code == 0:
            return box + plain, BOX_NESTED
        if code == 1 and "not permitted" in words:
            return box + plain, BOX_ON
        return plain, "%s: the premise check exited %s (%s)" % (BOX_OFF, code, words or "no stderr")
    except Exception as exc:          # a failure of the guard's premise never stops a helper
        return plain, "%s: the premise check failed (%s: %s)" % (BOX_OFF, type(exc).__name__, exc)


def box_note(run, lane, box):
    """Any `box` value but `on` on stderr, where a by-hand caller sees it; the close summary carries
    it to the lead. A stderr that cannot be written is never the helper's failure."""
    if box == BOX_ON:
        return
    try:
        sys.stderr.write("lane.py: lane %s/%s box %s\n" % (run, lane, box))
    except (OSError, ValueError):
        pass


def start_awake(pid):
    """Keep the host awake while the lane process `pid` runs (owner decision of 2026-10-09; the
    docstring's "Keeping the host awake"): start `caffeinate -i -w <pid>` beside it. Returns
    (process or None, the fields of the `lane-awake` line). The process gets a session of its own,
    so a signal to the caller's group or the lane's never reaches it; /dev/null for its standard
    streams and no other inherited descriptor, so it holds neither the wrapper's input or output
    nor the lane's input pipe, whose end of file the lane waits for; and nobody waits on it, so it
    never blocks. An absent or non-executable binary, or a start that fails in any way, is
    `skipped` with the why in `note`, never an error: the spawn goes on. Both wrappers call this."""
    path = os.environ.get(CAFFEINATE_ENV) or CAFFEINATE_BIN
    command = [path, "-i", "-w", str(pid)]
    fields = {"awake": "skipped", "caffeinate_pid": None, "watched_pid": pid, "command": command}
    after = "the host may sleep while pid %s runs, and a sleep reads as silence" % pid
    if not os.path.isfile(path):
        fields["note"] = "no caffeinate at %s (another platform, or a missing binary): %s" % (path, after)
        return None, fields
    if not os.access(path, os.X_OK):
        fields["note"] = "caffeinate at %s is not executable: %s" % (path, after)
        return None, fields
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, close_fds=True,
                                   start_new_session=True)
    except Exception as exc:          # any failure to start is a note, never a failed spawn
        fields["note"] = "caffeinate did not start (%s: %s): %s" % (type(exc).__name__, exc, after)
        return None, fields
    fields.update(awake="started", caffeinate_pid=process.pid,
                  note="caffeinate pid %d holds an idle-sleep assertion until pid %s exits"
                       % (process.pid, pid))
    return process, fields


def beat_awake_fields(fields):
    """The keep-awake state as the held-lane beat records it (review CR-AWAKE finding 1): added
    fields on its one `hold-beat` line, never a line of its own — `awake`, `caffeinate_pid` and
    `watched_pid` from start_awake's fields, and `note` with the why only when skipped. Both
    wrappers' beats call this, so the two lines cannot drift apart."""
    added = {"awake": fields.get("awake"), "caffeinate_pid": fields.get("caffeinate_pid"),
             "watched_pid": fields.get("watched_pid")}
    if fields.get("awake") != "started":
        added["note"] = fields.get("note")
    return added


def reap_awake(process):
    """Collect an exited caffeinate without waiting for one still running, which exits by itself
    once its lane process has; a failure here is never the lane's."""
    if process is None:
        return
    try:
        process.poll()
    except Exception:
        pass


def silence_of(started, transcript, progress, threshold, no_transcript_s):
    """Seconds since the lane last showed life (the newer of the transcript and the progress
    file, never earlier than the spawn), the reason label and the bound that applies."""
    marks = [started]
    if progress and os.path.isfile(progress):
        marks.append(os.path.getmtime(progress))
    if transcript and os.path.isfile(transcript):
        marks.append(os.path.getmtime(transcript))
        reason, bound = "silent", threshold
    else:
        reason, bound = "no transcript", no_transcript_s
    return round(time.time() - max(marks), 1), reason, bound


def class_silence(cls):
    """The silence threshold a class takes when the call passes no `--silence-s`, and its source
    for the record: LONG_SILENCE_S for the LONG_SILENCE_CLASSES, DEFAULT_SILENCE_S for every other
    class (register 2026-09-26 03:5x). Spawn, resume and resolve_silence all read it here, so the
    paths that resolve a threshold cannot drift apart."""
    seconds = LONG_SILENCE_S if cls in LONG_SILENCE_CLASSES else DEFAULT_SILENCE_S
    return seconds, "class default for %s" % cls


def resolve_silence(args, record_path, cls):
    """The stall threshold and where it came from; 0 disables the watch. The precedence: `--silence-s
    0` disables; `--silence-s N` replaces the class default; `--baseline-lane` then raises either
    one when 1.5 x the predecessor's duration is larger."""
    if args.silence_s is not None and args.silence_s < 0:
        die("--silence-s must be 0 (watch disabled) or a positive number of seconds")
    if args.silence_s == 0:
        return 0, "--silence-s 0 (watch disabled)"
    if args.silence_s is None:
        base, source = class_silence(cls)
    else:
        base, source = args.silence_s, "--silence-s"
    if getattr(args, "baseline_lane", None):
        duration = None
        for record in load_record(record_path):
            if record.get("event") == "lane-closed" and record.get("lane") == args.baseline_lane:
                duration = record.get("duration_s")
        if not isinstance(duration, (int, float)):
            die("--baseline-lane %s has no lane-closed with a duration_s in %s"
                % (args.baseline_lane, record_path))
        derived = round(BASELINE_FACTOR * float(duration), 1)
        if base < derived:
            base, source = derived, "%s x baseline %s (%.1f s)" % (BASELINE_FACTOR,
                                                                  args.baseline_lane, duration)
    return base, source


def stall_event(run, lane, session_id, silent_s, threshold_s, reason, by):
    return {"ts": now(), "run": run, "lane": lane, "event": "stall", "session_id": session_id,
            "silent_s": silent_s, "threshold_s": threshold_s, "reason": reason,
            "action": STALL_ACTION, "by": by}


ALIAS_RE = re.compile(r"^[a-z][a-z-]*$")     # an alias is a bare word: opus, fable, sonnet; an id carries a digit


def load_model_facts(path=None):
    """The `models` block of prices.json beside this script: the ids the harness aliases resolve
    to on this account and the helper families the harness calls beside every lane. Returns
    (facts, None) or (None, reason): a missing file, a missing block, an alias that is not a bare
    word, an id that is not a non-empty string, or a helper list that is empty or carries a blank
    entry is a premise failure reported by its reason, never a fallback flag or a silent pass."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.json")
    try:
        with open(path, encoding="utf-8") as handle:
            table = json.load(handle)
    except (OSError, ValueError) as exc:
        return None, "prices.json unreadable or not JSON (%s)" % exc
    block = table.get("models") if isinstance(table, dict) else None
    if not isinstance(block, dict):
        return None, "prices.json carries no `models` block (aliases and helpers)"
    aliases, helpers = block.get("aliases"), block.get("helpers")
    if not isinstance(aliases, dict) or not aliases:
        return None, "prices.json `models.aliases` is missing or empty"
    for key, value in aliases.items():
        if not isinstance(key, str) or not ALIAS_RE.match(key):
            return None, "prices.json `models.aliases` key %r is not a bare alias word" % (key,)
        if not isinstance(value, str) or not value.strip() or ALIAS_RE.match(value):
            return None, "prices.json `models.aliases[%s]` is not a model id: %r" % (key, value)
    if not isinstance(helpers, list) or not helpers:
        return None, "prices.json `models.helpers` is missing or empty"
    if any(not isinstance(h, str) or not h.strip() for h in helpers):
        return None, "prices.json `models.helpers` carries a blank or non-string entry"
    return {"aliases": dict((k, v.strip()) for k, v in aliases.items()),
            "helpers": [h.strip().lower() for h in helpers]}, None


def fallback_check(model_usage, requested, facts):
    """The transparent-fallback read of one close (owner ruling 2026-09-22, rule 3). The ids the
    result's modelUsage names, minus the helper families, must be exactly the id the requested
    alias resolves to: a second id, or a different one, is a safeguard fallback (Opus 5.5
    re-routes some tasks to another model with no refusal to see; the vendor names Opus 4.8 for
    cyber work). `detected` is True, False, or None when nothing can be read, with `reason`
    saying which: no modelUsage on the result (an error close), no non-helper id, or no `models`
    block in prices.json (the premise), never a guess. A requested model the alias map does not
    know takes the count rule alone and says so in `rule`."""
    out = {"detected": None, "models": [], "non_helper": [], "expected": None, "rule": None,
           "reason": None}
    if not isinstance(model_usage, dict) or not model_usage:
        out["reason"] = "no modelUsage on the result"
        return out
    ids = sorted(str(k) for k in model_usage)
    out["models"] = ids
    if isinstance(facts, tuple):                  # the (facts, reason) pair load_model_facts returns
        facts, facts_reason = facts
    else:
        facts_reason = "prices.json carries no usable `models` block (aliases and helpers)"
    if facts is None:
        out["reason"] = facts_reason
        return out
    seen = [i for i in ids if not any(h in i.lower() for h in facts["helpers"])]
    out["non_helper"] = seen
    if not seen:
        out["reason"] = "only helper-family ids reported"
        return out
    requested = str(requested or "")
    if requested in facts["aliases"]:
        expected, rule = facts["aliases"][requested], "alias map and count"
    elif requested and not ALIAS_RE.match(requested):
        # An explicit id (it carries a digit or a dot: claude-opus-5, claude-opus-5-5) is its own
        # expectation whether or not the map lists it (critic finding 3, 2026-09-22).
        expected, rule = requested, "explicit id and count"
    else:
        expected, rule = None, "count only (alias %r unprobed in prices.json)" % requested
    out["expected"], out["rule"] = expected, rule
    out["detected"] = len(seen) > 1 or (expected is not None and seen != [expected])
    return out


FALLBACK_LINE = ("lane.py: FALLBACK on lane %s/%s (%s): the result names %s where %s was expected "
                 "— a transparent safeguard fallback (owner ruling 2026-09-22): %s; warn the owner once; "
                 "never re-run it on the same model to see, and re-read the brief for anything cyber- "
                 "or biology-shaped")
STALE_LINE = ("lane.py: STALE MAP on lane %s/%s: the alias %r now resolves to %s, not %s; no fallback — "
              "update the `models` block of prices.json (a re-probe on this account) and nothing else")
SWAP_CMD_ENV = "AIMYTH_SWAP_CMD"    # a suite stub in place of `python3 codex-lane.py spawn`; records its argv
SWAP_TIMEOUT_S = 180                # the whole detached Codex caller: 155 s of bounded steps and 25 s for the rest (the derivation in the docstring)
SWAP_OPEN_WAIT_S = 20               # bound with headroom: a detached spawn writes its lane-open within a second or two
PROBE_PROMPT = "Reply with the single word ok."
PROBE_TIMEOUT_S = 90                # bound with headroom: a one-word call answers in seconds; a limit stop is read as a failed probe


def probe_alias(ctx, alias):
    """One one-word call through the same harness and environment as the lane, to learn what the
    alias resolves to NOW: returns (non-helper ids, None) or (None, reason). The call is the same
    shape as a minimal alias-resolution request."""
    facts = ctx.get("model_facts") or {}
    helpers = facts.get("helpers") or []
    cmd = ["claude", "-p", "--model", alias, "--output-format", "json", "--max-turns", "1"]
    try:
        done = subprocess.run(cmd, input=PROBE_PROMPT, capture_output=True, text=True,
                              timeout=PROBE_TIMEOUT_S, env=ctx.get("env") or None, cwd=ctx.get("home") or None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "probe did not run: %s" % exc
    if done.returncode != 0:
        return None, "probe exit %d: %s" % (done.returncode, (done.stderr or done.stdout).strip()[-200:])
    try:
        result = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        return None, "probe result unreadable: %s" % exc
    if not isinstance(result, dict):
        return None, "probe result is not an object"
    if result.get("is_error"):
        return None, "probe result is an error (%s)" % (str(result.get("result") or "")[:120] or "no text")
    usage = result.get("modelUsage")
    if not isinstance(usage, dict) or not usage:
        return None, "probe result carries no modelUsage"
    ids = sorted(str(k) for k in usage if not any(h in str(k).lower() for h in helpers))
    if not ids:
        return None, "probe reported only helper-family ids"
    if len(ids) != 1:
        # A one-word call answers on one model; a probe that names two non-helper ids proves nothing
        # about the alias (critic round 3, finding 4) and never yields a stale-map verdict.
        return None, "probe reported %d non-helper ids (%s): unusable" % (len(ids), ",".join(ids))
    return ids, None


def fallback_decide(ctx, fallback):
    """Turn a detection into a verdict by probing the alias live (critic round 2, finding 5): the
    lane's ids all among what the alias resolves to now → the map is stale, not a fallback
    (`detected` false, `stale_map` true, a distinct warning, no swap); the probe fails → the
    detection stands `unconfirmed` and nothing swaps by itself; otherwise `fallback`, confirmed."""
    requested = str((ctx.get("open_line") or {}).get("model") or ctx.get("model") or "")
    alias = requested if ALIAS_RE.match(requested) else requested
    ids, why = probe_alias(ctx, alias)
    fallback["probe"] = {"alias": alias, "ids": ids, "ok": ids is not None, "reason": why}
    if ids is None:
        fallback["verdict"] = "unconfirmed"
        return fallback
    if set(fallback.get("non_helper") or []) <= set(ids):
        fallback["detected"] = False
        fallback["stale_map"] = True
        fallback["verdict"] = "stale-map"
        fallback["reason"] = "the alias %r now resolves to %s, not the map's %s: update prices.json" % (
            alias, ",".join(ids), fallback.get("expected"))
        return fallback
    fallback["verdict"] = "fallback"
    return fallback


def unused_name(existing, base):
    """base, base2, base3 …: the first not in `existing`, compared case-blind (the wrappers refuse a
    lane id that is case-equivalent to one already opened)."""
    taken = set(str(e).casefold() for e in existing)
    name, n = base, 1
    while name.casefold() in taken:
        n += 1
        name = "%s%d" % (base, n)
    return name


def record_lane_ids(record_path):
    """Every lane id the record has opened (lane-open lines of any harness)."""
    out = set()
    try:
        with open(record_path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("event") == "lane-open" and row.get("lane"):
                    out.add(str(row["lane"]))
    except OSError:
        pass
    return out


def successor_started(record_path, to_lane, wait_s):
    """(True, None) once the record carries a `lane-spawned` line for the successor (the pid line
    the wrapper writes after the process started) and no close for it; (False, why) when a close
    appears first (a spawn that failed at once) or the wait runs out. A `lane-open` alone proves
    nothing: the Codex wrapper writes it before the process starts (critic round 3, finding 3)."""
    deadline = time.time() + wait_s
    while True:
        spawned, closed = False, None
        try:
            with open(record_path, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(row, dict) or str(row.get("lane") or "") != to_lane:
                        continue
                    if row.get("event") == "lane-spawned":
                        spawned = True
                    elif row.get("event") == "lane-closed":
                        closed = str(row.get("exit_class") or "closed")
        except OSError:
            pass
        if closed is not None:
            return False, "the successor closed at once (%s)" % closed
        if spawned:
            return True, None
        if time.time() >= deadline:
            return False, "no lane-spawned for %s within %d s" % (to_lane, int(wait_s))
        time.sleep(0.5)


def fallback_swap(ctx, close_line, record_path):
    """Retired unowned disposition entry point; the lifetime owner prepares and launches."""
    raise A3Premise("legacy fallback disposition is retired; the pass owner or explicit recover decides")


def output_text(value):
    """A captured stream as text: subprocess hands a timed-out call's partial output back as bytes
    even in text mode, and None when there was none."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def swap_exit_accounts(code):
    """Whether a detached Codex caller's non-zero exit is its own account that nothing of its call
    runs: a refusal before any worker started (2), or a worker that exited before acknowledging,
    whose code await_ack passes on (else 3). A negative code is a signal that ended the caller,
    Python's 1 an uncaught error, and a code above 128 a shell's report of a signal: each can end
    the caller after its worker started, which survives it in its own session, so none of them
    says anything of the worker (critic CR-ADD3 finding 2). EXIT_UNCONFIRMED is never an account."""
    return (isinstance(code, int) and not isinstance(code, bool) and 1 < code <= 128
            and code != EXIT_UNCONFIRMED)


def swap_worker_pid(stdout, stderr):
    """The detached Codex worker's pid from its caller's output: the outcome line on stdout
    (`detached pid N …`), else the announcement await_ack writes to stderr the moment the worker
    starts (`… worker pid N started …`), which a caller stopped at the swap's timeout leaves
    behind. None when neither is there."""
    for text, pattern in ((stdout, r"^detached pid (\d+)\b"), (stderr, r"\bworker pid (\d+) started\b")):
        match = re.search(pattern, text or "", re.M)
        if match:
            return int(match.group(1))
    return None


def successor_after(record_path, to_lane):
    """One read of the record once the swap's worker has been checked: (`started`, None) for a
    lane-spawned with no close, (`closed (<class>)`, None) for a close, (`absent`, None) for
    neither, and (None, the error) for a record that cannot be read, which is never absence."""
    rows, error = record_snapshot(record_path)
    if rows is None:
        return None, error
    spawned, closed = False, None
    for row in rows:
        if str(row.get("lane") or "") != to_lane:
            continue
        if row.get("event") == "lane-spawned":
            spawned = True
        elif row.get("event") == "lane-closed":
            closed = str(row.get("exit_class") or "closed")
    if closed is not None:
        return "closed (%s)" % closed, None
    return ("started" if spawned else "absent"), None


def swap_where(swap):
    """The fallback warning's account of the swap (FALLBACK_LINE): done; unconfirmed, which never
    offers a hand re-run while the swap's worker may still start the lane, nor on the record's
    silence alone (critic CR-ADD2 finding 2); or not done, with the command to run by hand, said
    only where nothing of the swap can still start it."""
    command = swap.get("command") or "codex-lane.py spawn … (see the lane-swapped line)"
    if swap.get("ok"):
        return "swapped to lane %s on Astra%s" % (
            swap.get("to"), (" (%s)" % swap["stderr_tail"]) if swap.get("stderr_tail") else "")
    error = str(swap.get("error") or "")
    if error.startswith("unconfirmed: "):
        pid = swap.get("worker_pid")
        gone = ("pid %d has exited" % pid if isinstance(pid, int) and not isinstance(pid, bool)
                else "no codex-lane.py worker for lane %s is running" % swap.get("to"))
        return ("swap UNCONFIRMED: %s; do NOT run it by hand while that worker may still start it: "
                "once %s and the record shows no lane-spawned for %s, the by-hand command is: %s"
                % (error[len("unconfirmed: "):], gone, swap.get("to"), command))
    return "swap NOT done: %s; run it by hand: %s" % (swap.get("error"), command)


def summary_of(run, lane, cls, model, effort, close):
    cost = close.get("total_cost_usd")
    denials = close.get("denials") or {}
    if not isinstance(denials, dict):
        denials = {"tool": denials, "fence": denials}
    usage = close.get("usage") or {}
    line = ("lane %s/%s: %s %s·%s · %s · %s turns · $%s · denials tool %s fence %s · "
            "effort applied %s · tier %s · peak %s · session %s"
            % (run, lane, cls, model, effort, close.get("exit_class"),
               close.get("num_turns") if close.get("num_turns") is not None else "?",
               ("%.2f" % cost) if isinstance(cost, (int, float)) else "?",
               denials.get("tool", "?"), denials.get("fence", "?"),
               ",".join(close.get("effort_applied") or []) or "unread",
               ",".join(close.get("cache_write_tier") or []) or "unread",
               format(usage.get("peak_context") or 0, ","), close.get("session_id")))
    if close.get("report_words") is not None:
        line += " · report %s/%s words%s" % (close.get("report_shown", "?"),
                                              close["report_words"],
                                              " (cut)" if close.get("report_cut") else "")
    if close.get("soft_exceeded") and isinstance(cost, (int, float)):
        # The soft cap is logged, never enforced: the line says so and nothing else changes.
        # It spells whose line was crossed — the head's own --expect-usd or the class figure —
        # since the two carry different weight for the reader (owner ruling, 2026-09-07). A
        # record written before soft_src existed has no source to name and reads as the class.
        line += " · soft-cap: $%.2f over $%.2f (%s)" % (
            cost, close.get("soft_usd"),
            "expect" if close.get("soft_src") == "expect" else "class %s" % cls)
    fallback = close.get("fallback")
    if isinstance(fallback, dict) and fallback.get("stale_map"):
        line += " · stale alias map: %s now resolves to %s (no fallback)" % (
            (fallback.get("probe") or {}).get("alias"), ",".join((fallback.get("probe") or {}).get("ids") or []))
    elif isinstance(fallback, dict) and fallback.get("detected"):
        verdict = fallback.get("verdict") or "unverified"
        line += " · FALLBACK (%s): ran on %s, expected %s" % (
            "confirmed" if verdict == "fallback" else "unconfirmed, probe failed" if verdict == "unconfirmed" else verdict,
            ",".join(fallback.get("non_helper") or []), fallback.get("expected") or "one id")
        swap = close.get("swap") or {}
        error = str(swap.get("error") or "not attempted")
        if verdict == "fallback":
            disposition = close.get("disposition_current") or close.get("disposition")
            if disposition:
                line += " · disposition %s (%s)%s" % (
                    disposition.get("decision") or disposition["phase"], disposition.get("reason") or "",
                    " · successor " + disposition["successor"] if disposition.get("successor") else "")
            else:
                # Legacy closes retain their saved swap rendering.
                line += (" · swapped to %s" % swap["to"]) if swap.get("ok") else (
                    " · swap UNCONFIRMED (%s)" % error[len("unconfirmed: "):] if error.startswith("unconfirmed: ")
                    else " · swap not done (%s)" % error)
    elif isinstance(fallback, dict) and fallback.get("detected") is None and fallback.get("reason"):
        # A check that could not run is said, never hidden (critic finding 3, 2026-09-22).
        line += " · fallback unread: %s" % fallback["reason"]
    deferred = close.get("controls_deferred")
    if isinstance(deferred, list) and all(isinstance(v, dict) and "result" in v for v in deferred):
        line += deferred_text(deferred)
    if close.get("box") and close["box"] != BOX_ON:
        # The one reader of a helper that ran without the rule (review CR-DESIGN finding F4).
        line += " · box %s" % close["box"]
    return line


def emit(summary, close, report_words, fmt, open_line=None, text=None):
    """Print the summary, full-text pointer and complete report by default.
    An explicitly requested preview keeps the pointer to the complete report (D8)."""
    report_path = close.get("report")
    void = void_report_line(close)
    if void:
        report_path, text = None, ""
    if text is None:
        text = ""
        if report_path and os.path.isfile(report_path):
            try:
                with open(report_path, "r", encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
            except OSError:
                text = ""
    shown, n_shown, n_total, cut = cut_words(text, report_words)
    if fmt == "json":
        print(json.dumps({"summary": summary, "open": open_line, "close": close,
                          "report_path": report_path, "report_text": shown, "report_void": void,
                          "report_words": n_total, "report_shown": n_shown,
                          "report_cut": cut}, indent=1))
        return
    print(summary)
    if close.get("notice"):
        print(a3_notice_text(close["notice"]))
    if void:
        print(void)
    if report_path:
        print("report: %s" % report_path)
    if close.get("parse_error"):
        print("note: %s" % close["parse_error"])
    if report_path:
        if shown:
            print(shown)
        print("(%d of %d words shown; full text: %s)" % (n_shown, n_total, report_path))


def start_lane_process(command, cwd, env, stdin_text):
    """Start one lane process with its input already on its standard input, so nothing the wrapper
    does after the start can hold the brief back (register 2026-11-04 15:38: on a busy machine the
    record lines and the keep-awake start took 9 s, past the CLI's 3 s wait for stdin, and the lane
    died with no model run). The pipe is the wrapper's own, filled by a thread from before the
    start: the CLI reads a pipe as it always has, a brief longer than the pipe's buffer goes on
    feeding while the wrapper writes its record lines, and the end of the text closes the pipe.
    `None` (a brief passed as the prompt argument) closes it at once. A lane that exits unread ends
    the feed on a broken pipe, which its own close reports. Raises what Popen raises."""
    data = (stdin_text or "").encode("utf-8")
    read_end, write_end = os.pipe()

    def feed():
        try:
            with os.fdopen(write_end, "wb") as sink:
                sink.write(data)
        except OSError:
            pass

    threading.Thread(target=feed, name="lane-stdin", daemon=True).start()
    try:
        return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True, text=True,
                                stdin=read_end, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        os.close(read_end)


def wait_process(process, started, deadline, silence, poll, no_transcript_s, locate, progress,
                 owner=None):
    """Wait for a started lane, checking liveness every `poll` seconds while a silence threshold
    is set. Returns (stdout, stderr, killed for the deadline?, stall dict or None)."""
    stall, killed = None, False
    stdout = stderr = None
    exited_at = None
    while True:
        if owner:
            evidence = parse_transcript(locate(), owner.journal["boundary"])
            if evidence.get("refusal_count"):
                owner.capture(evidence)
            request = owner.stop_request()
            if request:
                owner.stop(request["cause"])
                if request["cause"] == "stall":
                    stall = {"silent_s": None, "threshold_s": silence, "reason": "watch request"}
                stdout, stderr = kill_group(process)
                break
        remaining = deadline - (time.time() - started)
        if remaining <= 0:
            killed = True
            if owner:
                owner.stop("deadline")
            stdout, stderr = kill_group(process)
            break
        # One second bounds normal stop-request latency; set by judgement, unmeasured.
        timeout = min(poll if poll and poll > 0 else 1.0, remaining, 1.0)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            break
        except subprocess.TimeoutExpired as exc:
            if process.poll() is not None:
                exited_at = exited_at or time.monotonic()
                if time.monotonic() - exited_at >= KILL_GRACE_S:
                    process._a3_stream_incomplete = True
                    stdout, stderr = output_text(exc.output), output_text(exc.stderr)
                    for pipe in (process.stdout, process.stderr):
                        if pipe:
                            pipe.close()
                    break
        if silence and silence > 0:
            silent_s, reason, bound = silence_of(started, locate(), progress, silence,
                                                 no_transcript_s)
            if silent_s > bound:
                stall = {"silent_s": silent_s, "threshold_s": bound, "reason": reason}
                if owner:
                    owner.stop("stall")
                stdout, stderr = kill_group(process)
                break
    return stdout, stderr, killed, stall


def run_lane(ctx):
    """Start the lane process, feed the brief, watch it, write the close line and print the
    summary. Shared by spawn and resume. Returns the wrapper's exit code."""
    record_path, run, lane = ctx["record"], ctx["run"], ctx["lane"]
    try:
        os.makedirs(os.path.dirname(ctx["progress"]) or ".", exist_ok=True)
    except OSError:
        pass          # the lane's own append will report it; /tmp exists on every platform
    open_console_for_spawn(run, ctx.get("viewer"))   # before the child: its clocks start below
    owner = a3_current(record_path, run, lane)
    if owner is None:
        raise A3Premise("task execution requires a lifetime owner")
    if owner.journal is None:
        owner.begin(ctx, ctx["pre_event"], owner.source_bytes, ctx["stdin"],
                    ["universal newline decoding"])
    if ctx.get("pre_event"):
        # A resume records itself BEFORE its process starts, as a spawn records lane-open before its
        # own: a start that fails still follows its lane-resumed, and a watch finds the resume at
        # once; lane-respawned below then carries the process (register 2026-09-10 15:22).
        pre = {"ts": now(), "run": run, "lane": lane, "event": None, "session_id": ctx["session_id"],
               "wrapper_pid": os.getpid(), "class": ctx["cls"], "detached": ctx.get("detached", False),
               "mechanism": "lane.py headless, model %s, effort %s" % (ctx["model"], ctx["effort"])}
        pre.update(ctx["pre_event"])
        append_record(record_path, pre)
    # The box, before the launch is marked pending and before the clocks start (`boxed`).
    command, box = boxed(ctx["command"], ctx["env"])
    box_note(run, lane, box)
    started = time.time()
    owner.prelaunch()
    try:
        owner.process = process = start_lane_process(command, ctx["home"], ctx["env"], ctx["stdin"])
    except OSError as exc:
        owner.start_failed()
        failed = {"ts": now(), "run": run, "lane": lane,
                  "event": "lane-closed", "session_id": ctx["session_id"],
                  "class": ctx["cls"], "exit_class": "spawn-failed", "box": box,
                  "error": str(exc), "exit_code": 3,
                  "soft_usd": ctx.get("soft_usd"),
                  "soft_src": ctx.get("soft_src"), "soft_exceeded": None,
                  "fallback": fallback_check(None, ctx["model"], load_model_facts()),
                  "wrapper_pid": os.getpid()}
        if ctx.get("controls_pending"):
            # The pass's report controls get their verdict at this close as at every other (review
            # CR-B4L finding 9): a process that never started returned no report, so unverified.
            failed["controls_deferred"] = deferred_verdicts(
                ctx["controls_pending"], ctx["report_path"], "", False, False, "spawn-failed")
        owner.capture({"refusal_count": 0, "refusal_evidence": [], "source": "child never started"}, settled=True)
        failed = owner.finish(failed, allow_move=False)
        sys.stderr.write("lane.py: could not start the lane process: %s\n" % exc)
        if failed.get("controls_deferred"):
            sys.stderr.write("lane.py: lane %s/%s%s\n" % (run, lane, deferred_text(failed["controls_deferred"])))
        return 3

    owner.record_child(process)
    spawned = {"ts": now(), "run": run, "lane": lane, "event": ctx["spawn_event"],
               "session_id": ctx["session_id"], "pid": process.pid, "wrapper_pid": os.getpid(),
               "class": ctx["cls"], "detached": ctx.get("detached", False), "box": box,
               "mechanism": "lane.py headless, model %s, effort %s" % (ctx["model"], ctx["effort"])}
    spawned.update(ctx.get("spawn_extra") or {})
    append_record(record_path, spawned)
    # The keep-awake process beside the lane, after lane-spawned so that line is as it was
    # (owner decision of 2026-10-09; start_awake): its own line, started or skipped.
    awake, awake_fields = start_awake(process.pid)
    awake_line = {"ts": now(), "run": run, "lane": lane, "event": AWAKE_EVENT,
                  "session_id": ctx["session_id"], "wrapper_pid": os.getpid(), "class": ctx["cls"],
                  "detached": ctx.get("detached", False)}
    awake_line.update(awake_fields)
    append_record(record_path, awake_line)

    def locate():
        return owner.bind_transcript(find_transcript(ctx["projects_root"], ctx["home"], ctx["session_id"]))

    stdout, stderr, killed, stall = wait_process(
        process, started, ctx["deadline"], ctx["silence"], ctx["poll"],
        ctx["no_transcript_s"], locate, ctx["progress"], owner=owner)
    ctx["a3_incomplete_stream"] = bool(getattr(process, "_a3_stream_incomplete", False))
    duration = round(time.time() - started, 1)
    if stall:
        append_record(record_path, stall_event(run, lane, ctx["session_id"], stall["silent_s"],
                                               stall["threshold_s"], stall["reason"], "spawn"))

    result, parse_error = None, None
    if stdout and stdout.strip():
        try:
            result = json.loads(stdout)
        except ValueError as exc:
            parse_error = "result JSON unparseable: %s" % exc
    if not isinstance(result, dict):
        result = {} if result is None else {"result": str(result)}

    transcript = locate()
    parsed = parse_transcript(transcript, owner.journal["boundary"])
    parsed.update(process_exit=process.returncode, cli_result=result, native_stderr=stderr,
                  parse_error=parse_error)
    parsed["native_exit_class"] = classify(killed, stall, parsed, result,
        result.get("subtype") or "", process.returncode, parse_error, stderr or "")[0]
    parsed["streams_complete"] = not ctx.get("a3_incomplete_stream")
    parsed.update(owner.capture(parsed, settled=parsed["streams_complete"]))
    parsed["refusal"] = bool(parsed.get("refusal_count"))
    response_text = (result.get("result") or "").strip()
    resumed = (ctx.get("pre_event") or {}).get("event") == "lane-resumed"
    # A resumed pass must not borrow an earlier transcript message as its new report.
    report_text = parsed.get("report_text") or response_text
    if parsed.get("uncertainty"):
        ctx["a3_report_scope"] = "final-message, boundary unknown"
    empty_response = resumed and not report_text
    if not report_text:
        report_text = "(no report text: exit %s%s%s)" % (
            process.returncode, ", deadline reached" if killed else "",
            ", stall (%s)" % stall["reason"] if stall else "")
    try:
        write_atomic(ctx["report_path"], report_text.rstrip() + "\n")
        report_written = ctx["report_path"]
    except OSError as exc:
        report_written = None
        sys.stderr.write("lane.py: report not written (%s)\n" % exc)
    shown, n_shown, n_total, cut = cut_words(report_text, ctx["report_words"])

    denials = result.get("permission_denials")
    denial_count = len(denials) if isinstance(denials, list) else 0
    subtype = result.get("subtype") or ""
    if "max_budget" in subtype:
        owner.stop("budget")
    elif "max_turns" in subtype:
        owner.stop("max-turns")
    exit_class, limit_text = classify(killed, stall, parsed, result, subtype,
                                      process.returncode, parse_error, stderr or "")
    if exit_class == "completed" and empty_response:
        exit_class = "empty"
    exit_code = EXIT_CODES.get(exit_class, 3)

    close_line = {
        "ts": now(), "run": run, "lane": lane, "event": "lane-closed",
        "session_id": result.get("session_id") or ctx["session_id"], "class": ctx["cls"],
        "exit_class": exit_class, "exit_code": exit_code, "process_exit": process.returncode,
        "box": box,
        "duration_s": duration, "subtype": subtype, "is_error": bool(result.get("is_error")),
        "num_turns": result.get("num_turns"), "total_cost_usd": result.get("total_cost_usd"),
        "cost_src": "result",
        "soft_usd": ctx.get("soft_usd"), "soft_src": ctx.get("soft_src"),
        "soft_exceeded": soft_check(result.get("total_cost_usd"), ctx.get("soft_usd")),
        "usage": {"modelUsage": result.get("modelUsage"),
                  "peak_context": parsed["peak"], "calls": parsed.get("calls", 0),
                  "first_call_context": parsed.get("first_call_context"),
                  "tokens": parsed.get("tokens")},
        "effort_applied": sorted(set(parsed["efforts"])) or None,
        "cache_write_tier": parsed["tiers"] or None,
        "denials": {"tool": denial_count, "fence": parsed["fence_denials"],
                    "fence_allows": parsed["fence_allows"]},
        "permission_denials": denials if isinstance(denials, list) else [],
        "transcript": parsed["transcript"], "report": report_written,
        "report_words": n_total, "report_shown": n_shown, "report_cut": cut,
        "limit_signal": parsed.get("limit_signal"), "network_signal": parsed.get("network_signal"),
        "silence_s": ctx["silence"],
        "stall": stall, "wrapper_pid": os.getpid(),
        "stderr_tail": (stderr or "").strip()[-400:] or None,
        "parse_error": parse_error,
        "fallback": fallback_check(result.get("modelUsage"), ctx["model"], ctx.setdefault("model_facts_pair", load_model_facts()))}
    ctx["model_facts"] = ctx["model_facts_pair"][0]
    close_line.update(ctx.get("close_extra") or {})
    pending = ctx.get("controls_pending") or []
    if pending:
        # The controls this pass declared on its own report, checked against the text this pass
        # returned — never the file on disk or the placeholder above (register 2026-09-20 01:58).
        fresh = bool(response_text) if resumed else bool(response_text or parsed["last_text"])
        fresh = fresh and not parsed.get("uncertainty")
        close_line["controls_deferred"] = deferred_verdicts(
            pending, ctx["report_path"], report_text if fresh else "", fresh,
            report_written is not None, exit_class)
    close_line["report_scope"] = ctx.get("a3_report_scope", "whole current pass")
    close_line["stop_cause"] = owner.refresh().get("stop_cause")
    fallback = close_line.get("fallback") or {}
    if fallback.get("detected"):
        fallback_decide(ctx, fallback)
    close_line = owner.finish(close_line)
    exit_code = a3_exit_code(owner.journal)
    if any(v["result"] != "checked" for v in close_line.get("controls_deferred") or []):
        sys.stderr.write("lane.py: lane %s/%s%s\n" % (run, lane, deferred_text(close_line["controls_deferred"])))
    summary = summary_of(run, lane, ctx["cls"], ctx["model"], ctx["effort"], close_line)
    emit(summary, close_line, ctx["report_words"], ctx["format"], ctx.get("open_line"),
         text=report_text)
    reap_awake(awake)
    return exit_code


def run_beat(ctx):
    """The held-lane beat (handsoff.py hold, 2026-09-17): the resumed session asked for one word
    under the spawn's own configuration and cap. No report, no pass file, no lane-resumed or
    lane-closed line; the one record line is `hold-beat`, carrying the call's usage from the
    harness result, so the closing meter's rewrite causes can show whether the cache held. The
    call is bounded by BEAT_TIMEOUT_S and killed past it; a non-zero exit, a limit or a refusal
    is recorded with ok false and its exit class, and never retried here. The keep-awake process
    starts beside the model process (start_awake) and its state rides on the hold-beat line
    (beat_awake_fields); a beat whose process never started has nothing to keep awake. The beat's
    process runs in the box like any other (`boxed`, before the prelaunch inside a3_begin_beat), and
    the box's state rides on the same line."""
    record_path, run, lane = ctx["record"], ctx["run"], ctx["lane"]
    command, box = boxed(ctx["command"], ctx["env"])
    box_note(run, lane, box)
    started = time.time()
    owner = a3_begin_beat(ctx, "claude")
    by = os.environ.get(BEAT_BY_ENV) or "hand"
    base = {"run": run, "lane": lane, "event": "hold-beat", "harness": "claude",
            "session_id": ctx["session_id"], "class": ctx["cls"], "model": ctx["model"],
            "effort": ctx["effort"], "n": ctx["beat_n"], "by": by, "prompt": BEAT_PROMPT,
            "config_sha256": ctx["config_sha256"], "config_src": ctx["config_src"],
            "config_match": ctx["config_match"], "budget_usd": ctx["budget"],
            "hard_src": ctx["hard_src"], "last_call_age_s": ctx["age_s"],
            "last_call_src": ctx["age_src"], "wrapper_pid": os.getpid(), "box": box}
    try:
        owner.process = process = start_lane_process(command, ctx["home"], ctx["env"],
                                                     BEAT_PROMPT + "\n")
    except OSError as exc:
        line = dict(base, ts=now(), ok=False, exit_class="spawn-failed", exit_code=3,
                    process_exit=None, duration_s=0.0, usage=None, total_cost_usd=None,
                    error=str(exc))
        owner.start_failed()
        owner.capture({"refusal_count": 0, "refusal_evidence": []}, settled=True)
        owner.finish_beat(line)
        sys.stderr.write("lane.py: the beat could not start the lane process: %s\n" % exc)
        return 3
    owner.record_child(process)
    # The keep-awake process beside the beat's model process (owner decision of 2026-10-09: each
    # helper keeps the host awake while it runs, a beat included; start_awake), its state on the
    # one hold-beat line below.
    awake, awake_fields = start_awake(process.pid)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=BEAT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        stdout, stderr = kill_group(process)
        timed_out = True
    duration = round(time.time() - started, 1)
    result, parse_error = None, None
    if stdout and stdout.strip():
        try:
            result = json.loads(stdout)
        except ValueError as exc:
            parse_error = "result JSON unparseable: %s" % exc
    if not isinstance(result, dict):
        result = {} if result is None else {"result": str(result)}
    parsed = parse_transcript(find_transcript(ctx["projects_root"], ctx["home"], ctx["session_id"]),
                              owner.journal["boundary"])
    parsed.update(process_exit=process.returncode, cli_result=result, native_stderr=stderr)
    parsed["streams_complete"] = not getattr(process, "_a3_stream_incomplete", False)
    parsed.update(owner.capture(parsed, settled=parsed["streams_complete"]
                               and not parsed.get("uncertainty")))
    subtype = result.get("subtype") or ""
    exit_class, limit_text = classify(timed_out, None, parsed, result, subtype,
                                      process.returncode, parse_error, stderr or "")
    ok = exit_class == "completed"
    reply = (result.get("result") or "").strip()
    line = dict(base, ts=now(), session_id=result.get("session_id") or ctx["session_id"],
                ok=ok, exit_class=exit_class, exit_code=0 if ok else EXIT_CODES.get(exit_class, 3),
                process_exit=process.returncode, duration_s=duration, subtype=subtype,
                is_error=bool(result.get("is_error")), num_turns=result.get("num_turns"),
                total_cost_usd=result.get("total_cost_usd"), cost_src="result",
                usage=beat_usage(result),
                usage_src="result modelUsage (this invocation's own calls)",
                peak_context=parsed["peak"], cache_write_tier=parsed["tiers"] or None,
                reply=reply[:80], limit_signal=limit_text, timed_out=timed_out,
                parse_error=parse_error, stderr_tail=(stderr or "").strip()[-400:] or None)
    line.update(beat_awake_fields(awake_fields))
    line = owner.finish_beat(line)
    ok, exit_class = line["ok"], line["exit_class"]
    usage = line["usage"] or {}
    summary = ("beat %s/%s: %s %s·%s · %s · $%s · %.1f s · cache read %s · write %s · input %s · "
               "output %s · config %s · %s"
               % (run, lane, ctx["cls"], ctx["model"], ctx["effort"],
                  "ok" if ok else "FAILED (%s)" % exit_class,
                  ("%.4f" % line["total_cost_usd"])
                  if isinstance(line["total_cost_usd"], (int, float)) else "?",
                  duration, usage.get("cache_read_input_tokens", "?"),
                  usage.get("cache_creation_input_tokens", "?"), usage.get("input_tokens", "?"),
                  usage.get("output_tokens", "?"),
                  {True: "match", False: "MISMATCH", None: "unrecorded"}[ctx["config_match"]],
                  by))
    if box != BOX_ON:
        summary += " · box %s" % box
    if ctx["format"] == "json":
        print(json.dumps({"summary": summary, "beat": line}, indent=1))
    else:
        print(summary)
        if line.get("notice"):
            print(a3_notice_text(line["notice"]))
    reap_awake(awake)
    return line["exit_code"]


def start_pending(record_path, lane):
    """The `controls_pending` of the lane's latest start (`lane-open` or `lane-resumed`), else []:
    what a recovery close must still check, read from the record because its wrapper is gone."""
    pending = []
    for event in load_record(record_path):
        if event.get("lane") == lane and event.get("event") in ("lane-open", "lane-resumed"):
            value = event.get("controls_pending")
            pending = value if isinstance(value, list) else []
    return pending


def close_from_transcript(record_path, run, lane, opened, spawned, home, projects_root,
                          note, report_words, extra=None):
    """Retired observer closer. Legacy records remain readable without granting close authority."""
    raise A3Premise("legacy transcript closure is retired; explicit head reconciliation is required")


def log_tail(path, lines=6):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-lines:])
    except OSError:
        return ""


def watch_lane(run, lane, record_path, home, projects_root, silence, poll, no_transcript_s,
               max_wait, report_words, fmt, session_id=None, worker=None, log_path=None,
               since=None):
    """The shared waiting loop of `watch`, `wait` and the `--detach` foreground. Never kills a live
    wrapper's lane for silence unless `silence` is set; closes an orphaned lane (wrapper gone,
    no lane-closed) from its transcript once its process is gone or its recorded deadline
    passes. Returns the exit code."""
    result = a3_watch(record_path, run, lane, fmt, report_words, max_wait, poll,
                      silence=silence, worker=worker)
    if result is not None:
        return result
    began = time.time()
    unwatched = False
    stalled = None
    killed_at = None
    while True:
        result = a3_watch(record_path, run, lane, fmt, report_words, max_wait, poll,
                          silence=silence, worker=worker)
        if result is not None:
            return result
        records = load_record(record_path) if os.path.isfile(record_path) else []
        opened, spawned, closed = lane_state(records, lane, session_id)
        if since is not None and not any(r.get("lane") == lane and r.get("event") == "lane-resumed"
                                         for r in records[since:]):
            spawned = closed = None     # a detached resume has written nothing yet: the close in view is the previous call's
        if closed:
            cls = closed.get("class") or (opened or {}).get("class")
            summary = summary_of(run, lane, cls, (opened or {}).get("model"),
                                 (opened or {}).get("effort"), closed)
            emit(summary, closed, report_words, fmt, opened)
            if stalled:
                return EXIT_CODES["stall"]
            if worker is not None:
                code = closed.get("exit_code")
                if isinstance(code, int):
                    return code
                try:
                    return worker.wait(timeout=KILL_GRACE_S)
                except subprocess.TimeoutExpired:
                    return 0
            return 0
        if worker is not None and worker.poll() is not None and not spawned:
            # The worker died before it started the lane: a premise failure or a crash; its
            # log holds the reason.
            sys.stderr.write(log_tail(log_path) if log_path else "")
            sys.stderr.write("lane.py: detached worker exited %s before lane-spawned\n"
                             % worker.returncode)
            return worker.returncode if worker.returncode else 3
        if opened and spawned:
            lane_pid = spawned.get("pid")
            wrapper_pid = spawned.get("wrapper_pid")
            if worker is not None:
                wrapper_alive = worker.poll() is None
            else:
                wrapper_alive = pid_alive(wrapper_pid) if wrapper_pid else None
            lane_alive = pid_alive(lane_pid)
            started = parse_ts(spawned.get("ts")) or began
            transcript = find_transcript(projects_root, home, spawned.get("session_id"))
            progress = progress_path(run, lane)
            orphan = (wrapper_alive is False
                      or (wrapper_alive is None and lane_alive is False
                          and time.time() - began > 2 * poll))
            if orphan:
                print("orphaned: legacy pass has no A3 ownership or birth identity; explicit head reconciliation required")
                return 3
            if killed_at is not None:
                if time.time() - killed_at > KILL_GRACE_S + 2 * poll:
                    print("stall: lane %s/%s killed; its wrapper wrote no lane-closed within "
                          "%d s" % (run, lane, KILL_GRACE_S + 2 * poll))
                    return EXIT_CODES["stall"]
            elif silence and silence > 0:
                silent_s, label, bound = silence_of(started, transcript, progress, silence,
                                                    no_transcript_s)
                if silent_s > bound:
                    if label == "no transcript":
                        if not unwatched:
                            append_record(record_path, {
                                "ts": now(), "run": run, "lane": lane, "event": "unwatched",
                                "session_id": spawned.get("session_id"),
                                "note": "no transcript found under %s after %.0f s; the "
                                        "deadline stays the only bound" % (projects_root, silent_s)})
                            unwatched = True
                    else:
                        stalled = stall_event(run, lane, spawned.get("session_id"), silent_s,
                                              bound, label, "watch")
                        append_record(record_path, stalled)
                        print("watch: legacy wrapper cannot consume a durable stop request; explicit head stop required")
                        return 3
        elif worker is None:
            die("lane %s/%s is unknown in %s (no lane-open and lane-spawned)"
                % (run, lane, record_path))
        if max_wait and time.time() - began > max_wait:
            print("still-running: lane %s/%s after %.0f s" % (run, lane, time.time() - began))
            return EXIT_STILL_RUNNING
        time.sleep(poll if spawned else min(poll, 1.0))


# ------------------------------------------------------------------------ spawn -------------

def record_snapshot(path):
    """(rows, error) for the acknowledgement wait: no rows and no error while the record does not
    exist yet (a new run's worker has not written), the parsed lines once it does, a torn line
    skipped; an unreadable record is (None, the error), so the wait reports that it could not
    tell rather than reading the failure as absence. Reads only."""
    if not os.path.lexists(path):
        return [], None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError as exc:
        return None, "%s: %s" % (type(exc).__name__, exc)
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows, None


def require_ack_wait(value):
    """--ack-wait-s is checked in the caller, before any worker starts."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or value <= 0:
        die("--ack-wait-s must be a positive finite number of seconds, got %r" % (value,))


def worker_caps(text):
    """(hard_usd, hard_src) as the detached caller composed them, handed to its worker so the worker
    neither composes the cap a second time (the envelope read can run the meter) nor records one
    that differs from the cap the caller checked."""
    try:
        caps = json.loads(text)
    except ValueError:
        caps = None
    usd = caps.get("hard_usd") if isinstance(caps, dict) else None
    src = caps.get("hard_src") if isinstance(caps, dict) else None
    if isinstance(usd, bool) or not isinstance(usd, (int, float)) or not math.isfinite(usd) \
            or usd <= 0 or not isinstance(src, str) or not src:
        die("--worker-caps %r is not a composed cap (a positive hard_usd and its hard_src)"
            % (str(text)[:120],))
    return float(usd), src


def await_ack(worker, record_path, since, match, wait_s, log_path, ack_line, what, who="lane.py"):
    """The bounded acknowledgement wait of `--detach --no-wait` (register 2026-09-29 16:57), shared
    with codex-lane.py: the record is read until a line after `since` satisfies `match(row,
    worker.pid)` — this call's own line, never an older one. Returns the exit code:
      acknowledged  `ack_line` on stdout, 0;
      exited        the worker ended first: its log tail on stderr, its own code (else 3);
      unconfirmed   the worker lives past `wait_s`, or the record cannot be read: `detached pid N,
                    unconfirmed after S s` on stdout, the reason on stderr, EXIT_UNCONFIRMED; the
                    worker is never signalled.
    The worker's state is read BEFORE the record on each look, so a worker that wrote its line and
    then exited is seen acknowledging. The worker is named on stderr before the wait begins, so a
    caller stopped mid-wait (the fallback swap past its timeout) still says which process may yet
    start the lane. Reads only."""
    sys.stderr.write("%s: worker pid %d started (log %s); waiting up to %g s for %s\n"
                     % (who, worker.pid, log_path, wait_s, what))
    sys.stderr.flush()
    began = time.monotonic()
    while True:
        exited = worker.poll() is not None
        rows, error = record_snapshot(record_path)
        if rows is not None and any(match(row, worker.pid) for row in rows[since:]):
            print(ack_line)
            return 0
        waited = time.monotonic() - began
        if exited and rows is not None:
            tail = log_tail(log_path)
            if tail:
                sys.stderr.write(tail if tail.endswith("\n") else tail + "\n")
            sys.stderr.write("%s: the detached worker pid %d exited %s before writing %s; nothing "
                             "of this call is running (log %s)\n"
                             % (who, worker.pid, worker.returncode, what, log_path))
            code = worker.returncode
            return code if isinstance(code, int) and 0 < code < 256 else 3
        if exited or waited >= wait_s:
            print("detached pid %d, unconfirmed after %d s" % (worker.pid, round(waited)))
            why = ("the record %s cannot be read (%s)" % (record_path, error) if error
                   else "%s did not appear within %d s" % (what, round(waited)))
            state = ("it has exited %s, so whether it acknowledged is unknown" % worker.returncode
                     if exited else "it is still running and was left alone")
            sys.stderr.write("%s: %s; %s — read the record or the log %s before acting\n"
                             % (who, why, state, log_path))
            return EXIT_UNCONFIRMED
        time.sleep(min(ACK_POLL_S, max(0.01, wait_s - waited)))


def detach_spawn(args, session_id, home, projects_root, caps):
    """The double fork for a spawn, once every check has passed in the caller: the session id
    chosen there and the cap it composed are handed to the worker, which runs the whole spawn and
    writes every record line. The acknowledgement is this call's own lane-open: the lane, the
    session id, and the worker's own pid as `wrapper_pid`. The pid is what this call alone carries:
    a session id can be the caller's own --session-id, which a second call on the same lane may
    share (critic CR-ADD2 finding 3), and the record count excludes only older lines."""
    extra = ([] if args.session_id else ["--session-id", session_id]) \
        + ["--worker-caps", json.dumps(caps)]
    rows, _ = record_snapshot(store_paths(args.run, args.lane, args.record)["record"])
    ack = ("this call's lane-open (session %s, its wrapper_pid the worker's)" % session_id,
           len(rows or []),
           lambda row, pid: (row.get("lane") == args.lane and row.get("event") == "lane-open"
                             and row.get("session_id") == session_id
                             and row.get("wrapper_pid") == pid))
    return detach_worker(args, session_id, extra, home, projects_root, ack=ack)


def detach_worker(args, session_id, extra, home, projects_root, since=None, ack=None):
    """The double fork shared by spawn and resume: a worker (its own session) re-runs this command
    and writes every record line; the foreground watches it, or with --no-wait returns once the
    worker has acknowledged this call, or says why it could not tell (await_ack).

    The caller opens the run's console first, in its own context, and the worker gets `--viewer
    none`, appended so it wins over any --viewer the command carried.
    (register 2026-09-09 11:21, update
    2026-09-12). `since`, for a resume, is the record's
    event count before the detach, so the foreground waits for a lane-resumed after it and never
    takes the previous call's close for this one's. `ack` is (what, record count, match) for
    --no-wait's bounded acknowledgement wait (await_ack)."""
    argv = [a for a in sys.argv[1:] if a not in ("--detach", "--no-wait")]
    argv += list(extra) + ["--viewer", "none", "--as-worker"]
    paths = store_paths(args.run, args.lane, args.record)
    open_console_for_spawn(args.run, args.viewer)
    try:
        os.makedirs(os.path.dirname(paths["detach_log"]), exist_ok=True)
        fd = os.open(paths["detach_log"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError as exc:
        die("detach log is not writable (%s): %s" % (paths["detach_log"], exc))
    try:
        worker = subprocess.Popen([sys.executable, "-B", os.path.abspath(__file__)] + argv,
                                  stdin=subprocess.DEVNULL, stdout=fd, stderr=fd,
                                  start_new_session=True, close_fds=True)
    except OSError as exc:
        os.close(fd)
        die("could not start the detached worker: %s" % exc)
    os.close(fd)
    if args.no_wait:
        what, count, match = ack
        return await_ack(worker, paths["record"], count, match, args.ack_wait_s, paths["detach_log"],
                         "detached pid %d session %s" % (worker.pid, session_id), what)
    # The worker runs the silence watch itself; the foreground never kills for silence.
    return watch_lane(args.run, args.lane, paths["record"], home, projects_root, None,
                      args.poll_s, args.no_transcript_s, 0, args.report_words, args.format,
                      session_id=session_id, worker=worker, log_path=paths["detach_log"],
                      since=since)


# ------------------------------------------------------------- the per-call pick ------------

def pick_sources(throttle, model, effort, row_default, choice_reason):
    """(model_src, effort_src) for the lane-open line: where each axis's value came from, in the
    four words the record carries (owner ruling 2026-09-07 17:0x; built 2026-09-08).
      anchor           under `auto`: no override, or one equal to the row default (the anchor)
      auto: <text>     under `auto`: an override departing from the anchor; the --choice-reason text
      throttle <name>  under a hand-set preset: no override, or one equal to the preset's value
      explicit         under a hand-set preset: a departure; a reason is recorded if given, never required
    Under `auto` a departure with no --choice-reason (absent or whitespace) is refused exactly as
    a missing --reason is — exit 2, before any record line, --dry-run included — and the refusal
    names every axis that departs. An out-of-range value is a departure like any other here; its
    `outside_options` note stays the caller's."""
    reason = (choice_reason or "").strip()
    sources, departures = {}, []
    for axis, value in (("model", model), ("effort", effort)):
        anchor = row_default[axis]
        if value == anchor:
            sources[axis] = "anchor" if throttle == "auto" else "throttle %s" % throttle
        elif throttle == "auto":
            departures.append("--%s %s departs from the anchor %s" % (axis, value, anchor))
            sources[axis] = "auto: %s" % reason
        else:
            sources[axis] = "explicit"
    if departures and not reason:
        die("%s under throttle auto; pass --choice-reason" % " and ".join(departures))
    return sources["model"], sources["effort"]


def recorded_source(opened, key):
    """The pick source a lane-open recorded, or `unrecorded` for a record from before the pick
    fields (every lane opened before 2026-09-08). A resume makes no new pick: it copies."""
    value = opened.get(key)
    return value if isinstance(value, str) and value else "unrecorded"


def resolve_spawn_pick(args):
    """The class row, its tier under the throttle and the per-call pick, resolved before anything
    else a spawn does: (routing, row, cls, pick). `pick` holds the lane-open fields `throttle`,
    `throttle_note`, `model`, `effort`, `row_default`, `outside`, `model_src`, `effort_src` and
    `choice_reason`. Resolving it first is what lets an unreasoned departure under `auto` be
    refused before the detach, before --dry-run prints and before any record line."""
    routing_path = args.routing or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "routing.json")
    routing = load_routing(routing_path, parse_float=Decimal)
    cls = getattr(args, "class")
    if cls not in routing["classes"]:
        die("unknown class `%s` (routing table has: %s)"
            % (cls, ", ".join(sorted(routing["classes"]))))
    row = routing["classes"][cls]

    # `auto` is the default preset and the fallback for a missing Settings line (2026-09-08;
    # `default` until then), in step with throttle.py's active_throttle.
    throttle = args.throttle or customisation_value("throttle", "auto")
    throttle_note = None
    if throttle not in THROTTLES:
        throttle_note = "unknown throttle %r, treated as `auto`" % throttle
        sys.stderr.write("lane.py: %s\n" % throttle_note)
        throttle = "auto"
    model, effort, model_opts, effort_opts = resolve_tier(routing, row, cls, throttle)
    row_default = {"model": model, "effort": effort}   # the row's tier under the throttle, before any override (2026-09-06); under `auto` the anchor
    outside = []
    if args.model:
        if args.model not in model_opts:
            outside.append("model %s outside the class options %s" % (args.model, model_opts))
        model = args.model
    if args.effort:
        if args.effort not in effort_opts:
            outside.append("effort %s outside the class options %s" % (args.effort, effort_opts))
        effort = args.effort
    model_src, effort_src = pick_sources(throttle, model, effort, row_default, args.choice_reason)
    return routing, row, cls, {
        "throttle": throttle, "throttle_note": throttle_note, "model": model, "effort": effort,
        "row_default": row_default, "outside": outside, "model_src": model_src,
        "effort_src": effort_src, "choice_reason": (args.choice_reason or "").strip() or None}


def grants_from_lane(args, record_path):
    """`--grants-from LANE`: the read and write grants the named lane opened with join this call's,
    so a lane continuing another's work starts with its scope (register 2026-09-14 00:06, the shape
    of 16 October). They are read from that lane's latest lane-open in this run's record, which
    holds what it really had, the class's own defaults among them. A lane the record does not know
    is refused; a copied path gone from disk meets the spawn's own check. Returns what lane-open
    records, or None with no flag."""
    if not args.grants_from:
        return None
    opened = None
    for row in load_record(record_path):
        if row.get("event") == "lane-open" and row.get("lane") == args.grants_from:
            opened = row
    if opened is None:
        die("--grants-from %s: that lane has no lane-open in %s" % (args.grants_from, record_path))
    reads, writes = opened.get("grants"), opened.get("writes")
    if not isinstance(reads, list) or not isinstance(writes, list):
        die("--grants-from %s: its lane-open in %s records no grants" % (args.grants_from, record_path))
    args.write = list(args.write or []) + writes
    args.grant = list(args.grant or []) + [path for path in reads if path not in writes]
    return {"lane": args.grants_from, "grants": len(reads), "writes": len(writes)}


@a3_entry("claude")
def cmd_spawn(args):
    require_lane_id(args.lane)
    require_estimate(args.expect_usd)
    paths = store_paths(args.run, args.lane, args.record)
    require_new_lane_id(args.lane, paths["record"])
    grants_from = grants_from_lane(args, paths["record"])
    destinations = [paths[key] for key in ("definition_copy", "appended", "report", "settings", "input_dir")]
    if args.detach and not args.as_worker:
        destinations.append(paths["detach_log"])
    require_absent_paths(destinations)
    # After the estimate, `--reason` is checked: an omitted, an
    # empty and a letterless reason take one refusal, before any record line and before --dry-run
    # prints anything (register, 2026-09-07). The per-call pick is resolved next, so that an
    # unreasoned departure under `auto` is refused the same way, before the detach (2026-09-08).
    require_reason_letter(args.reason)
    routing, row, cls, pick = resolve_spawn_pick(args)
    cost = class_cost(row, cls)
    advisory = estimate_advisory(args.expect_usd, cost, cls)
    args.expect_usd = require_estimate(args.expect_usd)
    if advisory is not None and not args.as_worker:
        sys.stderr.write("estimate advisory: %s\n" % advisory)
    if not args.as_worker:
        # the doubled-root refusal and the two warnings, in the caller's terminal
        caller_checks(args, () if args.grants_only else
                      split_placeholders(field(row, cls, "grants", "default"))[0])
    # A dry run never detaches, so --no-wait is refused here unless the call really detaches, before
    # the controls. Every check below then runs in the caller too: the detach comes after the last
    # of them, so a refused grant exits 2 here with no worker started (register 2026-09-29 16:57).
    if args.no_wait and not (args.detach and not args.dry_run):
        die("--no-wait goes with --detach")
    if args.detach and not args.dry_run:
        require_ack_wait(args.ack_wait_s)
    if not args.as_worker and not getattr(args, "source_pass", None):
        # A recorded movement continues a started pass with no head in the loop, and a3_launch is
        # single-shot: a hold there would lose it. Its --source-pass is checked against a real
        # launch-intent journal at publication, so it is no way round this check.
        decisions_spawn_check(paths["record"], args.run, args.lane, dry_run=args.dry_run)
    vault = vault_root()
    home = os.path.realpath(os.path.expanduser(args.home or default_home()))
    for required in ("lane-settings.json", "lane-fence.py"):
        if not os.path.isfile(os.path.join(home, required)):
            die("lane home %s has no %s — run `lane.py init` first" % (home, required))

    throttle, throttle_note = pick["throttle"], pick["throttle_note"]
    model, effort, row_default, outside = pick["model"], pick["effort"], pick["row_default"], pick["outside"]
    mode, mode_src, mode_from = resolve_delegation(args)

    if not os.path.isfile(args.brief):
        die("brief file not found: %s" % args.brief)
    brief = read_text(args.brief, "the brief")
    if not brief.strip():
        die("brief file is empty: %s" % args.brief)
    # The brief's declarations: parsed here, checked once the read grants are resolved below,
    # every refusal before any record line and in the caller before any detach.
    declared = parse_declarations(brief, vault)
    # Page fetches refuse here; a declaration that needs search alone waits for the tool list below.
    refuse_web(declared, "a Claude lane cannot fetch pages: no per-spawn permission admits WebFetch "
                         "and lane.py grants no shell network (a declaration that needs search alone "
                         "opens with `search:`) — spawn it through codex-lane.py with --search",
               search_ok=True)

    config_dir = None
    if args.config_dir:
        config_dir = os.path.abspath(os.path.expanduser(args.config_dir))
        if not os.path.isdir(config_dir):
            die("--config-dir is not a directory: %s (a second login needs its own directory, "
                "logged in by the owner first)" % config_dir)

    grant_literals, grant_slots = split_placeholders(field(row, cls, "grants", "default"))
    write_literals, write_slots = split_placeholders(field(row, cls, "writes"))
    call_grants = resolve_entries(args.grant, vault, "granted path", True)
    call_writes = resolve_entries(args.write, vault, "write path", True)
    # A row's literal defaults (`wiki`, `raw`, `assets`) name the LIVE vault. A lane working on
    # a fixture must see none of it, so --grants-only drops them and makes the call the whole
    # scope; the dropped tokens go into the record rather than disappearing quietly.
    dropped = []
    if args.grants_only:
        if not call_grants:
            die("--grants-only needs at least one --grant: it drops the row's literal "
                "defaults, so the call is the lane's whole read scope")
        dropped = sorted(set(grant_literals + write_literals))
        grant_literals, write_literals = [], []
    grants = resolve_entries(grant_literals, vault, "class default grant", False)
    writes = resolve_entries(write_literals, vault, "class write directory", False)

    # A row's per-call slot is filled by the call. `--write` fills a write slot; `--grant`
    # fills a read slot, and so does `--write`, since a path a lane may write is necessarily
    # one it may read. A slot the call left empty is a premise failure that names the flag
    # which fills it.
    for slot in write_slots:
        if call_writes:
            continue
        die("class `%s` leaves `%s` to the call: needs --write for %s"
            % (cls, slot, slot))
    for slot in grant_slots:
        if call_grants or call_writes:
            continue
        flag = "--write" if slot in write_slots else "--grant"
        die("class `%s` leaves `%s` to the call: needs %s for %s" % (cls, slot, flag, slot))

    for entry in call_grants:
        add_entry(grants, entry)
    for entry in call_writes:
        add_entry(writes, entry)
    for entry in writes:
        add_entry(grants, entry)
    if args.grant_vault_root:
        add_entry(grants, {"given": vault_given(), "real": vault, "file": False})

    row_tools = list(field(row, cls, "tools"))
    tools = ([t.strip() for t in args.tools.split(",") if t.strip()] if args.tools
             else list(row_tools))
    if not tools:
        die("class `%s` resolves to an empty tool list" % cls)
    # What the class definition allows, from the bytes the thin definition hashes: WebSearch joins
    # the row's tools where the definition allows it and the call named no --tools, and the
    # per-spawn settings admit it (2026-10-10). WebFetch never joins.
    allowed = []
    definition_path, definition_sha, agent = thin_definition(
        vault, cls, tools, "thin %s lane" % cls, allowed_out=allowed)
    search = "WebSearch" in allowed
    if search and not args.tools and "WebSearch" not in tools:
        tools.append("WebSearch")
        agent["tools"] = list(tools)
    for tool in tools:
        why = None if tool in row_tools else tool_refusal(tool, writes, search)
        if why:
            die("--tools names %s, outside class `%s`'s tools (%s): %s"
                % (tool, cls, ", ".join(row_tools), why))
    search = search and "WebSearch" in tools
    refuse_web(declared, "this lane gets no WebSearch for it (class `%s`'s definition does not allow "
                         "it, or --tools leaves it out) — spawn it through codex-lane.py with --search"
                         % cls, search_ok=search)

    # The controls and the declared inputs, against the roots the lane's tools reach: the grants
    # (the writes among them), its input directory and the lane home, and the temporary roots only
    # where its tools hold Bash (lane_read_roots). A control on `<<REPORT>>` is pending until the close.
    read_roots = lane_read_roots(tools, reals(grants), dir_entry(paths["input_dir"])["real"], home)
    controls_checked, controls_pending = check_controls(declared["controls"], vault, read_roots,
                                                        report=paths["report"])
    inputs_checked = check_inputs(declared, vault, read_roots)

    skills = list(field(row, cls, "skills", "default")) + list(args.skill or [])
    seen, ordered = set(), []
    for name in skills:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    skills = ordered
    defaults = field(row, cls, "skills", "default")

    mcp_default = field(row, cls, "mcp", "default")
    if mcp_default and not args.mcp_config:
        die("class `%s` names default MCP servers %r but no --mcp-config was passed"
            % (cls, mcp_default))

    agents_json = json.dumps({cls: agent})
    # What the definition allows and this lane will not have: one line in the caller's terminal and
    # `tools_withheld` on lane-open; the tool list and the settings stay as composed (D24).
    withheld = tools_withheld(allowed, tools, writes)
    notice = withheld_notice(cls, withheld)
    if notice and not args.as_worker:
        sys.stderr.write(notice + "\n")

    # The appended file: the one carrier of everything the lane reads besides its brief.
    # Order is the row's, core first; `lane-core` in the row list IS the core, so naming it
    # there never doubles it.
    sections, appended_names = [], []
    if not args.no_core:
        if args.append_core:
            if not os.path.isfile(args.append_core):
                die("--append-core file not found: %s" % args.append_core)
            core_path = os.path.abspath(args.append_core)
        else:
            core_path = os.path.join(home, CORE_NAME)
            drift = core_drift_note(home, vault)
            if drift and not args.as_worker:
                sys.stderr.write(drift + "\n")
            if not os.path.isfile(core_path):
                core_path = core_source(vault)
        if not os.path.isfile(core_path):
            if CORE_SLICE in defaults:
                die("class `%s` names the default slice `%s`, but no lane core is installed "
                    "(looked in the lane home and %s) — run `lane.py init`"
                    % (cls, CORE_SLICE, display_path(core_source(vault), vault)))
            sys.stderr.write("lane.py: no lane core found; spawning without one\n")
        else:
            sections.append((CORE_SLICE, core_path,
                             strip_vault_local(strip_frontmatter(read_text(core_path, "the lane core")),
                                               "the lane core")))
            appended_names.append(CORE_SLICE)
    for name in skills:
        if name == CORE_SLICE:
            continue
        path, body = resolve_slice(name, home, vault)
        if path is None:
            if name in defaults:
                die("class `%s` needs the default skill slice `%s`, which resolves nowhere "
                    "(looked in the lane home's skills/ and %s) — run `lane.py init` after "
                    "the slice is installed"
                    % (cls, name, display_path(slice_sources(vault), vault)))
            sys.stderr.write("lane.py: skill `%s` resolves to no slice; it is not appended\n"
                             % name)
            continue
        sections.append((name, path, body))
        appended_names.append(name)
    appended_text = ""
    for name, path, body in sections:
        appended_text += ("## Lane slice: %s — source: %s\n\n%s\n\n"
                          % (name, display_path(path, vault), body.strip()))
    appended_bytes = len(appended_text.encode("utf-8"))

    session_id = args.session_id or str(uuid.uuid4())
    breadth = customisation_value("breadth", DEFAULT_BREADTH)
    deadline = args.deadline_s or DEFAULT_DEADLINE_S
    trust = trust_state(home, config_dir)
    if args.require_trust and trust is not True:
        die("lane home %s has no accepted workspace-trust entry in .claude.json (state: %s) "
            "— a headless run on an untrusted workspace degrades silently"
            % (home, {True: "accepted", False: "declined", None: "absent"}[trust]))

    paths = store_paths(args.run, args.lane, args.record)
    record_path = paths["record"]
    silence, silence_src = resolve_silence(args, record_path, cls)
    # The estimate sets both lines; its sanity note was printed in the caller before detach. A
    # detached worker takes the cap its caller composed and checked (one envelope read per spawn).
    if args.as_worker and args.worker_caps:
        hard_usd, hard_src = worker_caps(args.worker_caps)
    else:
        hard_usd, hard_src = cost_caps(args.budget_usd, args.expect_usd, args.run, record_path,
                                       dry_run=args.dry_run)
        if "cap kept" in hard_src:
            sys.stderr.write("lane cap: %s\n" % hard_src)
    soft_usd, soft_src = soft_line(args.expect_usd)
    budget = hard_usd
    projects_root = projects_root_for(args.projects_root, config_dir)
    progress = progress_path(args.run, args.lane)

    # The lane's own input directory: the brief copied in, the head's hand inputs beside it,
    # granted read in both spellings; the store itself only when the call names it.
    input_entry = dir_entry(paths["input_dir"])
    brief_abs = os.path.abspath(args.brief)
    if os.path.realpath(brief_abs).startswith(input_entry["real"] + os.sep):
        brief_copy = brief_abs
    else:
        brief_copy = os.path.join(paths["input_dir"], "%s-brief-%s.md" % (args.run, args.lane))
    add_dirs = add_dirs_for(grants + [input_entry])
    grants_env = os.pathsep.join(reals(grants) + [input_entry["real"], home, "/tmp"])
    writes_env = os.pathsep.join(reals(writes))
    settings, settings_allow = settings_for(home, writes, search)
    settings_text = json.dumps(settings, indent=2) + "\n"   # the bytes written below, hashed above them
    env = dict(os.environ)
    env.update({"LLM_WIKI_LANE": "1", "LLM_WIKI_LANE_RUN": args.run, "LLM_WIKI_LANE_ID": args.lane,
                "LLM_WIKI_LANE_GRANTS": grants_env, "LLM_WIKI_LANE_WRITES": writes_env,
                "LLM_WIKI_LANE_PROGRESS": progress})
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = config_dir

    command = ["claude", "-p", "--agents", agents_json, "--agent", cls,
               "--model", model, "--effort", effort, "--restricted",
               "--tools", ",".join(tools),
               "--settings", paths["settings"],
               "--strict-mcp-config", "--session-id", session_id,
               "--max-budget-usd", str(budget), "--permission-prompts", "none",
               "--output-format", "json"]
    for path in add_dirs:
        command += ["--add-dir", path]
    if args.mcp_config:
        command += ["--mcp-config", args.mcp_config]
    if appended_text:
        command += ["--append-system-prompt-file", paths["appended"]]
    if args.max_turns:
        command += ["--max-turns", str(args.max_turns)]
    if writes:
        command += ["--permission-mode", "acceptEdits"]
    if args.prompt_arg:
        command.append(brief)

    open_line = {
        "ts": now(), "run": args.run, "lane": args.lane, "event": "lane-open", "harness": "claude",
        "class": cls, "definition": os.path.relpath(definition_path, vault),
        "definition_sha256": definition_sha, "definition_copy": paths["definition_copy"],
        "model": model, "effort": effort, "throttle": throttle, "row_default": row_default,
        "model_src": pick["model_src"], "effort_src": pick["effort_src"],
        "choice_reason": pick["choice_reason"], "tools": tools,
        "grants": reals(grants), "writes": reals(writes),
        "grants_files": files_of(grants), "writes_files": files_of(writes),
        "add_dirs": add_dirs, "input_dir": paths["input_dir"],
        "grant_vault_root": bool(args.grant_vault_root),
        "grants_env": grants_env, "writes_env": writes_env,
        "row_literals_dropped": dropped, "grants_from": grants_from,
        "controls_checked": controls_checked, "controls_pending": controls_pending,
        "inputs_checked": inputs_checked,
        "settings": paths["settings"], "settings_allow": settings_allow,
        "config_dir": config_dir, "projects_root": projects_root,
        "skills": skills, "mcp": ([args.mcp_config] if args.mcp_config else []),
        "appended": appended_names, "appended_bytes": appended_bytes,
        "appended_file": paths["appended"] if appended_text else None,
        "cache_tier_expected": row.get("cache", "unstated"),
        # the process that writes this line and the close: a detached caller's acknowledgement
        # matches its own worker's pid here, since a session id can be shared (detach_spawn)
        "session_id": session_id, "wrapper_pid": os.getpid(), "budget_usd": budget, "breadth": breadth,
        "hard_usd": hard_usd, "hard_src": hard_src, "soft_usd": soft_usd,
        "soft_src": soft_src, "expect_usd": args.expect_usd, "estimate_advisory": advisory,
        "max_turns": args.max_turns, "deadline_s": deadline,
        "silence_s": silence, "silence_src": silence_src, "poll_s": args.poll_s,
        "progress_file": progress, "report_words_cap": args.report_words,
        "reason": args.reason, "plant": args.plant, "reading_list": args.reading_list,
        "brief": brief_abs, "brief_copy": brief_copy, "mode": mode, "mode_src": mode_src,
        "mode_from": mode_from, "baseline": args.baseline,
        "baseline_lane": args.baseline_lane or None,
        "cwd": home, "workspace_trust": trust,
        # the configuration a resume or a beat must carry byte for byte (the held-lane beat,
        # 2026-09-17): the command line minus the session flag and the wrapper-side bounds,
        # plus the appended file's and the settings file's bytes, as written below
        "config_sha256": config_sha256(command, (appended_text, settings_text),
                                       drop_tail=1 if args.prompt_arg else 0),
        "mechanism": "lane.py headless (claude -p --agents/--agent, --restricted, "
                     "lane-side fence hook, per-spawn settings, silence watch)"}
    if outside:
        open_line["outside_options"] = outside
    if args.item:
        open_line["item"] = args.item
    if not args.as_worker and not getattr(args, "source_pass", None):
        item_warning(paths["record"], args.item)
    if throttle_note:
        open_line["throttle_note"] = throttle_note
    if withheld:
        open_line["tools_withheld"] = withheld

    if args.dry_run:
        print("command:")
        print("  " + " ".join(shlex.quote(part) for part in command))
        print("environment:")
        for key in ("LLM_WIKI_LANE", "LLM_WIKI_LANE_RUN", "LLM_WIKI_LANE_ID",
                    "LLM_WIKI_LANE_GRANTS", "LLM_WIKI_LANE_WRITES", "LLM_WIKI_LANE_PROGRESS"):
            print("  %s=%s" % (key, env[key]))
        if config_dir:
            print("  CLAUDE_CONFIG_DIR=%s" % config_dir)
        print("add-dirs: %s" % " ".join(add_dirs))
        print("settings (%s): allow %s" % (paths["settings"], settings_allow or "none"))
        print("controls checked: %s" % json.dumps(controls_checked))
        if controls_pending:
            print("controls pending (checked at the close, on this pass's report): %s"
                  % json.dumps(controls_pending))
        if inputs_checked:
            print("inputs checked: %s" % json.dumps(inputs_checked))
        print("silence: %s s (%s)" % (silence, silence_src))
        print("hard cap: $%.2f (%s) · soft line: %s"
              % (hard_usd, hard_src,
                 ("$%.2f (%s)" % (soft_usd, soft_src)) if soft_usd is not None
                 else "none"))
        print("brief delivery: %s" % ("prompt argument" if args.prompt_arg else "stdin"))
        print("appended system prompt (%s, %d bytes): %s"
              % (paths["appended"], appended_bytes, ", ".join(appended_names) or "nothing"))
        print("model_src: %s" % pick["model_src"])
        print("effort_src: %s" % pick["effort_src"])
        if pick["choice_reason"]:
            print("choice_reason: %s" % pick["choice_reason"])
        print("record line (%s):" % record_path)
        print("  " + json.dumps(open_line))
        print("would write: %s · %s · %s · %s/%s"
              % (paths["definition_copy"], paths["report"], paths["settings"],
                 paths["input_dir"], os.path.basename(brief_copy)))
        return 0

    if args.detach:
        # Every check above ran here, in the caller's terminal; the worker repeats them under the
        # session id and the cap chosen here and writes every record line.
        return detach_spawn(args, session_id, home, projects_root,
                            {"hard_usd": hard_usd, "hard_src": hard_src})
    ctx = {"run": args.run, "lane": args.lane, "cls": cls, "model": model, "effort": effort,
           "command": command, "env": env, "home": home,
           "stdin": None if args.prompt_arg else brief, "deadline": deadline,
           "silence": silence, "poll": args.poll_s, "no_transcript_s": args.no_transcript_s,
           "record": record_path, "report_path": paths["report"],
           "projects_root": projects_root, "session_id": session_id, "progress": progress,
           "report_words": args.report_words, "format": args.format,
           "spawn_event": "lane-spawned", "detached": bool(args.as_worker), "viewer": args.viewer,
           "open_line": open_line, "soft_usd": soft_usd, "soft_src": soft_src,
           "no_swap": bool(getattr(args, "no_swap", False)), "brief_current": brief_abs,
           "controls_pending": controls_pending}
    owner = a3_current(record_path, args.run, args.lane)
    open_line["routing_path"] = os.path.abspath(args.routing or os.path.join(os.path.dirname(__file__), "routing.json"))
    owner.begin(ctx, open_line, owner.source_bytes, brief, ["universal newline decoding"])
    append_record(record_path, open_line)
    if appended_text:
        try:
            write_atomic(paths["appended"], appended_text)
        except OSError as exc:
            die("the appended system-prompt file is not writable (%s): %s"
                % (paths["appended"], exc))
    try:
        write_atomic(paths["settings"], settings_text)
    except OSError as exc:
        die("the per-spawn settings file is not writable (%s): %s" % (paths["settings"], exc))
    try:
        os.makedirs(paths["input_dir"], exist_ok=True)
        if brief_copy != brief_abs:
            shutil.copyfile(brief_abs, brief_copy)
    except OSError as exc:
        die("the lane's input directory is not writable (%s): %s" % (paths["input_dir"], exc))
    try:
        write_atomic(paths["definition_copy"], definition_markdown(cls, agent, model, effort))
    except OSError as exc:
        sys.stderr.write("lane.py: definition copy not written (%s)\n" % exc)

    return run_lane(ctx)


# ----------------------------------------------------------------------- watch --------------

def cmd_wait(args):
    """Background wait: the watch loop, without its still-running time bound."""
    args.max_wait_s = 0
    return cmd_watch(args)


def cmd_watch(args):
    paths = store_paths(args.run, args.lane, args.record)
    result = a3_watch(paths["record"], args.run, args.lane, args.format, args.report_words,
                      args.max_wait_s, args.poll_s, args.appear_s, args.silence_s)
    if result is not None:
        return result
    # A detached worker writes lane-open and lane-spawned within a second of its start; a
    # watch issued right after `--detach --no-wait` waits up to --appear-s for them.
    opened = spawned = closed = None
    waited = 0.0
    while True:
        if os.path.isfile(paths["record"]):
            opened, spawned, closed = lane_state(load_record(paths["record"]), args.lane)
        if (opened and spawned) or waited >= args.appear_s:
            break
        time.sleep(0.5)
        waited += 0.5
    if not os.path.isfile(paths["record"]):
        die("no spawn record at %s" % paths["record"])
    if not opened or not spawned:
        die("lane %s/%s is unknown in %s (no lane-open and lane-spawned)"
            % (args.run, args.lane, paths["record"]))
    if closed:
        # A resume whose --detach --no-wait returned unconfirmed (exit 4) can write its lane-resumed
        # after it returns (an acknowledged one wrote it before returning), and a watch issued in
        # that moment still sees the previous call's close: wait up to --appear-s for a newer
        # lane-resumed before calling the lane closed.
        waited = 0.0
        while closed and waited < args.appear_s:
            time.sleep(0.5)
            waited += 0.5
            opened, spawned, closed = lane_state(load_record(paths["record"]), args.lane)
    if closed:
        summary = summary_of(args.run, args.lane, closed.get("class") or opened.get("class"),
                             opened.get("model"), opened.get("effort"), closed)
        emit(summary, closed, args.report_words, args.format, opened)
        die("lane %s/%s is already closed (%s at %s)"
            % (args.run, args.lane, closed.get("exit_class"), closed.get("ts")))
    home = os.path.realpath(os.path.expanduser(args.home or opened.get("cwd") or default_home()))
    projects_root = projects_root_for(args.projects_root or opened.get("projects_root"),
                                      opened.get("config_dir"))
    silence = args.silence_s if (args.silence_s and args.silence_s > 0) else None
    return watch_lane(args.run, args.lane, paths["record"], home, projects_root, silence,
                      args.poll_s, args.no_transcript_s, args.max_wait_s, args.report_words,
                      args.format, session_id=spawned.get("session_id"))


# ------------------------------------------------------------------------ kill --------------

def cmd_kill(args):
    return a3_kill(args, "claude")


# ---------------------------------------------------------------------- resume --------------

def cmd_advise(args):
    """The head's resume-or-restart recommendation for a closed lane, computed from the record
    (2026-09-14): the stop reason first, then the cost. Prints one
    line `advise: <resume|restart|family-fallback|unknown> · <the inputs>` and exits 0; a lane
    with no close, or a close with no usable figures, reads `unknown` with the reason (never a
    guess). D29's window in `resume` stays the enforced rule; this is the head's counsel. The
    age is measured from the lane's last call on `resume`'s own reference — the close, or a later
    successful `hold-beat` — and the line names which (critic F8, 2026-09-17)."""
    paths = store_paths(args.run, args.lane, args.record)
    if not os.path.isfile(paths["record"]):
        die("no spawn record at %s" % paths["record"])
    records = load_record(paths["record"])
    opened, spawned, closed = lane_state(records, args.lane)
    if not closed:
        print("advise: unknown · lane %s/%s has no lane-closed yet (watch it first)" % (args.run, args.lane))
        return 0
    cls = str(closed.get("exit_class") or "unstated")
    last = parse_ts(closed.get("ts"))
    # The lane's last call, on the same reference `resume` enforces (critic F8, 2026-09-17): a
    # successful held-lane beat after the close IS the last call, so counsel on a held lane reads
    # its real age instead of ageing it from a close the beats have outlived. A failed beat moved
    # nothing and is not counted, as in `resume` and in `hold`.
    age_src = "lane-closed ts"
    if last is not None:
        close_index = next((i for i, r in enumerate(records) if r is closed), len(records))
        for r in records[close_index + 1:]:
            if r.get("lane") != args.lane or r.get("event") != "hold-beat" or \
                    r.get("ok") is not True:
                continue
            t = parse_ts(r.get("ts"))
            if t is not None and t > last:
                last, age_src = t, "hold-beat ts"
    age = (time.time() - last) if last is not None else None
    usage = closed.get("usage") if isinstance(closed.get("usage"), dict) else {}
    memory = usage.get("peak_context")          # the wrapper's memory at close (never a sum over calls)
    if not isinstance(memory, int):
        memory = None
    orientation = usage.get("first_call_context")
    if not isinstance(orientation, int) or orientation <= 0:
        orientation = ORIENTATION_TOKENS
    report = args.report or closed.get("report") or paths.get("report")
    on_disk = []
    if report and os.path.isfile(report) and os.path.getsize(report) > ADVISE_REPORT_MIN_BYTES:
        on_disk.append("report")
    if args.stage and os.path.isdir(args.stage) and any(
            os.path.getsize(os.path.join(r, f)) > 0 for r, _, fs in os.walk(args.stage) for f in fs):
        on_disk.append("stage")
    inputs = "exit %s · age %s (%s) · memory at close %s · on disk %s" % (
        cls, "unknown" if age is None else "%.0f s" % age, age_src,
        "unknown" if memory is None else format(memory, ","),
        ", ".join(on_disk) if on_disk else "nothing")
    if cls == "network":
        inputs += " · wait until the API answers; no usage-limit reset wait"
    if cls == "refusal":
        print("advise: family-fallback · %s · a refusal is never resumed (CLAUDE.md section 11)" % inputs)
        return 0
    # The retry rule is the delegate skill's, named rather than restated (2026-10-11): §4's
    # "Progress-judged retries" for these four classes, one fresh re-spawn for other failures.
    if cls in ("deadline", "stall", "max-turns"):
        print("advise: restart · %s · a %s close restarts from the partial output, never a resume; "
              "another attempt follows the skill's \"Progress-judged retries\" (a fresh lane, a changed "
              "brief and the failure note, only with a fix for a new, clear cause; else the step returns "
              "to the head)" % (inputs, cls))
        return 0
    if cls in ("error", "spawn-failed", "killed"):
        print("advise: restart · %s · a %s close restarts from the partial output, never a resume; "
              "the skill's rule for other failures: one fresh re-spawn with a changed brief and the "
              "failure note, and a second failure returns the step to the head" % (inputs, cls))
        return 0
    if cls == "budget":
        print("advise: restart · %s · a budget close follows the skill's \"Progress-judged retries\" (a "
              "fresh lane with a changed brief only with a fix for a new, clear cause; else the step "
              "returns to the head), or is resumed only through `resume` with a raised --budget-usd "
              "inside its window" % inputs)
        return 0
    if cls == "completed":
        print("advise: restart · %s · a second pass goes to a fresh helper with a compact hand-off: "
              "the earlier report's path, the findings to fold, the held files and what must not change. "
              "Use `resume` only for a long write cut short by a usage limit or dropped connection, whose work is on disk "
              "and checked, or for the multi-expert panel's round 2" % inputs)
        return 0
    if age is None:
        print("advise: unknown · %s · the close carries no parseable ts" % inputs)
        return 0
    warm = age <= RESUME_WINDOW_S
    if warm:
        print("advise: resume · %s · the cache is warm (under %d min)" % (inputs, RESUME_WINDOW_S // 60))
        return 0
    if memory is None:
        print("advise: resume · %s · the memory at close is unknown, so the stop-reason rule alone applies: "
              "a limit or network close resumes (D29)" % inputs)
        return 0
    if not on_disk:
        print("advise: resume · %s · the cache is cold but nothing of the lane's work is on disk, so one cold "
              "re-read beats re-running the whole task (D29)" % inputs)
        return 0
    if memory is not None and memory <= orientation:
        print("advise: resume · %s · the cache is cold but the memory is under the lane's own orientation "
              "cost (%s, its first call)" % (inputs, format(orientation, ",")))
        return 0
    print("advise: restart · %s · the cache is cold, the work is on disk and the memory is %s: a re-spawn from "
          "the partial output is the cheaper path" % (inputs, "large" if memory is not None else "unknown"))
    return 0


def stopped_pass_cap(records, lane_id, closed):
    """The cap of the pass that closed: its latest start, never an earlier pass's cap.
    A resumed start with missing cap fields is a broken premise, not a fallback estimate."""
    start = None
    for event in records:
        if event.get("lane") != lane_id:
            continue
        if event.get("event") in ("lane-open", "lane-resumed"):
            start = event
        if event is closed:
            break
    if start is None:
        die("budget close has no preceding lane-open or lane-resumed")
    source = start["event"]
    value, key = start.get("hard_usd"), "hard_usd"
    if value is None:
        value, key = start.get("budget_usd"), "budget_usd"
    if value is None:
        die("budget close: %s records neither hard_usd nor budget_usd; the cap it stopped at is unknown"
            % source)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        die("budget close: %s %s is %r, not a number" % (source, key, value))
    if not math.isfinite(value) or value <= 0:
        die("budget close: %s %s is not a positive finite cap" % (source, key))
    return float(value), "%s %s" % (source, key)


@a3_entry("claude")
def cmd_resume(args):
    if args.no_wait and not args.detach:
        die("--no-wait goes with --detach")
    if args.detach:
        require_ack_wait(args.ack_wait_s)
    vault = vault_root()
    paths = store_paths(args.run, args.lane, args.record)
    if not os.path.isfile(paths["record"]):
        die("no spawn record at %s" % paths["record"])
    records = load_record(paths["record"])
    opened, spawned, closed = lane_state(records, args.lane)
    if not opened or not spawned:
        die("lane %s/%s is unknown in %s (no lane-open and lane-spawned)"
            % (args.run, args.lane, paths["record"]))
    if not closed:
        die("lane %s/%s has no lane-closed yet — resume re-enters a finished lane; `watch` it "
            "first" % (args.run, args.lane))
    if closed.get("exit_class") == "spawn-failed":
        die("lane %s/%s never started (spawn-failed); re-spawn it" % (args.run, args.lane))
    # Nothing else may enter the session while a beat is in flight (critic F4, 2026-09-17): the
    # beat's own record line lands only when its call returns, so the session claim is what a
    # resume — a real one or a second beat — can see meanwhile. This is the early reading, for a
    # refusal in the caller's own terms; the claim itself is taken below, immediately before this
    # call writes or starts anything. The exposure is seconds normally and the beat's whole bound
    # at worst; the alternative is two processes on one session.
    beat_marker = beat_marker_path(paths["record"], args.run, args.lane)
    holder, holder_kind = session_holder(beat_marker)
    if holder is not None:
        die("lane %s/%s: a held-lane %s is in flight (%s, lock %s): a second call on one "
            "session is the two-processes-on-one-session fault — wait for the call (bounded by %d s) or, if "
            "that process is wedged, end it and the kernel releases its lock"
            % (args.run, args.lane, holder_kind, holder_text(holder),
               session_lock_path(beat_marker), BEAT_TIMEOUT_S))
    # The held-lane beat (2026-09-17): a no-work resume with a fixed prompt, refused with a brief,
    # a worker or a close a beat cannot re-enter; a plain resume needs its brief.
    beat = bool(getattr(args, "beat", False))
    if beat and args.brief:
        die("--beat takes no --brief: the beat's prompt is the fixed line %r" % BEAT_PROMPT)
    if not beat and not args.brief:
        die("--brief is required: a resume carries a follow-up brief (the no-work form is --beat)")
    if beat and args.detach:
        die("--beat runs in the foreground: one bounded call, no worker")
    if beat and closed.get("exit_class") not in BEAT_EXITS:
        die("lane %s/%s closed %s: a beat re-enters only a close in %s (a limit or budget close "
            "is resumed by the head's own decision, never beaten)"
            % (args.run, args.lane, closed.get("exit_class") or "unstated", "/".join(BEAT_EXITS)))
    if not beat and not args.as_worker:
        decisions_spawn_check(paths["record"], args.run, args.lane, verb="resume")
    last = parse_ts(closed.get("ts"))
    if last is None:
        die("lane %s/%s: lane-closed carries no parseable ts (%r)"
            % (args.run, args.lane, closed.get("ts")))
    # The window's reference is the lane's last call: the close, or a later successful beat,
    # which is what a hold buys (the held-lane mechanism, 2026-09-17).
    age_src = "lane-closed ts"
    close_index = next((i for i, r in enumerate(records) if r is closed), len(records))
    for r in records[close_index + 1:]:
        if r.get("lane") != args.lane or r.get("event") != "hold-beat" or r.get("ok") is not True:
            continue
        t = parse_ts(r.get("ts"))
        if t is not None and t > last:
            last, age_src = t, "hold-beat ts"
    age = time.time() - last
    # D29: the window is a cost rule, not a safety rule, and a lane stopped by the account limit
    # is resumed after the reset however long that took — one cold re-read of its context, once
    # per lane, against the whole task re-run that a re-spawn would cost.
    after_limit = closed.get("exit_class") == "limit"
    after_network = closed.get("exit_class") == "network"
    if age > RESUME_WINDOW_S and not (after_limit or after_network):
        die("lane %s/%s: last call %.0f min ago (%s), over the %d-minute resume window — the "
            "cache has lapsed; %s"
            % (args.run, args.lane, age / 60.0, age_src, RESUME_WINDOW_S // 60,
               "nothing is warm to beat" if beat
               else "re-spawn with the finding in the brief instead"))
    if after_limit and age > RESUME_WINDOW_S:
        print("lane %s/%s: closed on a limit %.0f min ago — the %d-minute cache window is waived "
              "(D29); expect a cold re-read of the lane's context on this first call"
              % (args.run, args.lane, age / 60.0, RESUME_WINDOW_S // 60))
    # A `budget` close is the CLI's own `--max-budget-usd` stop (`error_max_budget_usd`), and it
    # is the one close class whose recorded cap must not be re-used: either the CLI's running
    # total survives the resume and the same cap kills the lane on its first turn, or it does not
    # and the lane silently takes a second full helping of it. So the caller raises the stop
    # explicitly, above the figure the lane already spent, or re-spawns (SKILL.md §2a). The guard
    # is keyed on exit_class, never on a lane or run id, and it refuses before anything is
    # written. Premise cases: no recorded cap (a torn or pre-class-caps record), a cap that is
    # not a number, and a --budget-usd equal to the cap rather than above it.
    after_budget = closed.get("exit_class") == "budget"
    recorded_cap = None
    if after_budget:
        recorded_cap, cap_source = stopped_pass_cap(records, args.lane, closed)
        if args.budget_usd is None or args.budget_usd <= recorded_cap:
            die("lane %s/%s closed on its budget cap of $%.2f (%s)%s: a budget close "
                "resumes only with an explicit --budget-usd ABOVE that figure, since the recorded "
                "cap either kills the lane again at once or gives it a second full helping"
                % (args.run, args.lane, recorded_cap, cap_source,
                   "" if args.budget_usd is None
                   else ", and --budget-usd $%.2f is not above it" % args.budget_usd))
    if beat:
        brief, declared = None, None    # the beat's prompt is BEAT_PROMPT, below
    else:
        if not os.path.isfile(args.brief):
            die("brief file not found: %s" % args.brief)
        brief = read_text(args.brief, "the follow-up brief")
        if not brief.strip():
            die("brief file is empty: %s" % args.brief)
        refuse_doubled_root(args.brief, brief, vault)
        declared = parse_declarations(brief, vault)     # checked below, against the lane-open's grants
        # A declaration that needs search alone passes where the lane-open's tools and settings
        # carry WebSearch; page fetches never do.
        search_ok = "WebSearch" in (opened.get("tools") or []) and \
            "WebSearch" in (opened.get("settings_allow") or [])
        refuse_web(declared, "a Claude lane cannot fetch pages: no per-spawn permission admits "
                             "WebFetch and lane.py grants no shell network (search alone needs a "
                             "`search:` declaration and a lane-open carrying WebSearch) — re-spawn it "
                             "through codex-lane.py with --search", search_ok=search_ok)

    # The lane's reason has not changed, so the resumed call is tallied under the letter its spawn
    # gave: `lane-resumed` records the reason carried from lane-open, and the command needs no flag
    # of its own. `--reason` is the override for a record whose reason names no letter — one
    # written before the 2026-09-06 check, or an empty one from before the 2026-09-07 fix — and
    # never a re-label: against a record that already carries a letter it is refused and the
    # recorded reason stands. Both refusals come before anything is written.
    recorded_reason = (opened.get("reason") or "").strip()
    if reason_letters(recorded_reason):
        if args.reason.strip():
            die("lane %s/%s already records the reason %r on its lane-open, and a resume does not "
                "re-label a lane: --reason overrides only a record whose reason names no "
                "instrument-rule letter, so the recorded reason stands"
                % (args.run, args.lane, recorded_reason[:60]))
        lane_reason, lane_reason_src = recorded_reason, "lane-open"
    else:
        require_reason_letter(args.reason)
        lane_reason, lane_reason_src = args.reason, "--reason (the lane-open records none)"

    cls = opened.get("class")
    model, effort = opened.get("model"), opened.get("effort")
    tools = opened.get("tools") or []
    if not (cls and model and effort and tools):
        die("lane %s/%s: lane-open lacks class, model, effort or tools" % (args.run, args.lane))
    session_id = closed.get("session_id") or spawned.get("session_id") or opened.get("session_id")
    home = os.path.realpath(os.path.expanduser(args.home or opened.get("cwd") or default_home()))
    config_dir = opened.get("config_dir")
    if config_dir and not os.path.isdir(config_dir):
        die("lane %s/%s: recorded config_dir %s is gone" % (args.run, args.lane, config_dir))
    projects_root = projects_root_for(args.projects_root or opened.get("projects_root"), config_dir)
    # D29: a resume re-enters a session by its transcript. No transcript, no session to re-enter —
    # the harness would start a fresh one under the old id and the lane would answer from nothing.
    transcript = find_transcript(projects_root, home, session_id)
    problem = (resume_transcript_error(transcript) if after_limit or after_network
               else "no transcript" if not transcript else None)
    if problem:
        die("lane %s/%s: %s for session %s under %s — the session cannot be re-entered; "
            "re-spawn the lane with the finding in the brief instead"
            % (args.run, args.lane, problem, session_id, projects_root))
    settings = opened.get("settings") or os.path.join(home, "lane-settings.json")
    if not os.path.isfile(settings):
        die("lane %s/%s: settings file %s is gone" % (args.run, args.lane, settings))
    add_dirs = list(opened.get("add_dirs") or opened.get("grants") or [])
    for path in add_dirs:
        if not os.path.exists(path):
            die("lane %s/%s: granted path %s is gone" % (args.run, args.lane, path))
    writes = list(opened.get("writes") or [])
    appended = opened.get("appended_file")
    if appended and not os.path.isfile(appended):
        die("lane %s/%s: appended file %s is gone" % (args.run, args.lane, appended))
    definition_path, definition_sha, agent = thin_definition(vault, cls, tools, "thin %s lane" % cls)
    if beat:
        # A beat carries the spawn's own cap and composes none: no estimate, no envelope read,
        # no meter — a beat is cheap by construction and must stay so.
        recorded_cap = opened.get("hard_usd")
        if recorded_cap is None:
            recorded_cap = opened.get("budget_usd")
        if isinstance(recorded_cap, bool) or not isinstance(recorded_cap, (int, float)) \
                or not math.isfinite(recorded_cap) or recorded_cap <= 0:
            die("lane %s/%s: lane-open records no positive cap (hard_usd or budget_usd): a beat "
                "carries the spawn's own cap and composes none" % (args.run, args.lane))
        budget, hard_src = float(recorded_cap), "lane-open cap (a beat carries the spawn's own)"
        expect, soft_usd, soft_src = None, None, None
    else:
        # Resume uses the spawn's estimate (2026-09-15), never the former class-median cap.
        recorded_expect = require_estimate(opened.get("expect_usd"), "lane-open expect_usd (--expect-usd)")
        if args.as_worker and args.worker_caps:
            budget, hard_src = worker_caps(args.worker_caps)   # composed and checked by the detached caller
        else:
            budget, hard_src = cost_caps(args.budget_usd, recorded_expect, args.run, paths["record"],
                                         term="resumed")
            if after_budget and hard_src.startswith("explicit --budget-usd (raised over resumed"):
                hard_src = "explicit --budget-usd (raised over a budget close from $%.2f)" % recorded_cap
            if "cap kept" in hard_src:
                sys.stderr.write("lane cap: %s\n" % hard_src)
        expect = args.expect_usd if args.expect_usd is not None else recorded_expect
        soft_usd, soft_src = soft_line(expect)
    deadline = args.deadline_s or opened.get("deadline_s") or DEFAULT_DEADLINE_S
    if args.silence_s is None:
        silence = opened.get("silence_s")
        silence_src = "lane-open"
        if silence is None:
            # a lane-open from before silence_s: the class default, as a spawn would resolve it
            silence, silence_src = class_silence(cls)
    else:
        silence, silence_src = resolve_silence(args, paths["record"], cls)
    progress = progress_path(args.run, args.lane)
    resume_n = 1 + sum(1 for r in records
                       if r.get("lane") == args.lane and r.get("event") == "lane-resumed")
    if beat:
        brief_abs = brief_copy = None    # no pass file of any kind: a beat is not a pass
    else:
        paths["report"] = pass_report_path(paths["report"], resume_n + 1)
        brief_abs = os.path.abspath(args.brief)
        brief_copy = os.path.join(paths["input_dir"], "%s-brief-%s-pass%d.md"
                                  % (args.run, args.lane, resume_n + 1))
        require_absent_paths((paths["report"], brief_copy))
    controls_checked = controls_pending = inputs_checked = None
    if not beat:
        # The follow-up brief's controls and inputs, against the roots the lane-open's tools reach
        # (lane_read_roots: its grants, input directory and home; the temporary roots with Bash
        # alone) and this pass's own report path. A lane-open from before `grants` was recorded
        # gives the fence's own list, its temporary roots kept only where the tools hold Bash.
        if isinstance(opened.get("grants"), list):
            input_dir = opened.get("input_dir")
            roots = lane_read_roots(tools, opened["grants"],
                                    os.path.realpath(input_dir) if isinstance(input_dir, str) else home,
                                    home)
        else:
            fence = [p for p in (opened.get("grants_env") or "").split(os.pathsep) if p] or [home]
            roots = (fence + temp_read_roots() if "Bash" in tools
                     else [p for p in fence if p not in temp_read_roots()])
        controls_checked, controls_pending = check_controls(declared["controls"], vault, roots,
                                                            report=paths["report"])
        inputs_checked = check_inputs(declared, vault, roots)

    grants_env = opened.get("grants_env") or os.pathsep.join(
        list(opened.get("grants") or []) + [home, "/tmp"])
    writes_env = opened.get("writes_env") or os.pathsep.join(writes)
    env = dict(os.environ)
    env.update({"LLM_WIKI_LANE": "1", "LLM_WIKI_LANE_RUN": args.run, "LLM_WIKI_LANE_ID": args.lane,
                "LLM_WIKI_LANE_GRANTS": grants_env, "LLM_WIKI_LANE_WRITES": writes_env,
                "LLM_WIKI_LANE_PROGRESS": progress})
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = config_dir

    command = ["claude", "-p", "--resume", session_id, "--agents", json.dumps({cls: agent}),
               "--agent", cls, "--model", model, "--effort", effort, "--restricted",
               "--tools", ",".join(tools), "--settings", settings, "--strict-mcp-config",
               "--max-budget-usd", str(budget), "--permission-prompts", "none",
               "--output-format", "json"]
    for path in add_dirs:
        command += ["--add-dir", path]
    if appended:
        command += ["--append-system-prompt-file", appended]
    max_turns = args.max_turns or opened.get("max_turns")
    if max_turns:
        command += ["--max-turns", str(max_turns)]
    if writes:
        command += ["--permission-mode", "acceptEdits"]

    # The configuration this call runs under, hashed as the spawn hashed its own (the held-lane
    # beat, 2026-09-17): a beat whose hash differs from the lane-open's would rewrite the
    # context, so it is refused before any process starts; a resume records the comparison.
    config_sha = config_sha256(command, ((read_bytes(appended) if appended else b"") or b"",
                                         read_bytes(settings) or b""))
    recorded_sha = opened.get("config_sha256")
    config_src = "lane-open" if isinstance(recorded_sha, str) and recorded_sha else \
        "unrecorded (a lane-open from before config_sha256)"
    config_match = (config_sha == recorded_sha) if isinstance(recorded_sha, str) and recorded_sha \
        else None
    if beat and config_match is False:
        die("lane %s/%s: the resolved configuration differs from the lane-open's (config_sha256 "
            "%s against the recorded %s): a beat carries the spawn's configuration byte for byte "
            "or it is a rewrite, not a beat — nothing started; resume by hand or re-spawn"
            % (args.run, args.lane, config_sha[:12], str(recorded_sha)[:12]))
    if beat:
        ctx = {"run": args.run, "lane": args.lane, "cls": cls, "model": model, "effort": effort,
               "command": command, "env": env, "home": home, "record": paths["record"],
               "projects_root": projects_root, "session_id": session_id, "format": args.format,
               "config_sha256": config_sha, "config_src": config_src, "config_match": config_match,
               "budget": budget, "hard_src": hard_src, "age_s": round(age, 1), "age_src": age_src,
               "beat_n": 1 + sum(1 for r in records
                                 if r.get("lane") == args.lane and r.get("event") == "hold-beat")}
        with hold_beat_marker(beat_marker):
            return run_beat(ctx)

    if args.detach:
        # Every premise above ran in the caller's terminal; the worker repeats them under the cap
        # composed here and writes every record line, lane-resumed first (register 2026-09-10
        # 15:22). The acknowledgement is a lane-resumed after this count whose wrapper_pid is the
        # worker's own pid: the lane's earlier passes share its session id.
        since = len(load_record(paths["record"]))
        ack = ("this call's lane-resumed (its wrapper_pid the worker's)", since,
               lambda row, pid: (row.get("lane") == args.lane and row.get("event") == "lane-resumed"
                                 and row.get("wrapper_pid") == pid))
        return detach_worker(args, session_id,
                             ["--worker-caps", json.dumps({"hard_usd": budget, "hard_src": hard_src})],
                             home, projects_root, since=since, ack=ack)

    try:
        os.makedirs(paths["input_dir"], exist_ok=True)
        shutil.copyfile(brief_abs, brief_copy)
    except OSError as exc:
        die("the lane's input directory is not writable (%s): %s" % (paths["input_dir"], exc))

    ctx = {"run": args.run, "lane": args.lane, "cls": cls, "model": model, "effort": effort,
           "command": command, "env": env, "home": home, "stdin": brief, "deadline": deadline,
           "silence": silence, "poll": args.poll_s, "no_transcript_s": args.no_transcript_s,
           "record": paths["record"], "report_path": paths["report"],
           "projects_root": projects_root, "session_id": session_id, "progress": progress,
           "report_words": args.report_words, "format": args.format,
           "spawn_event": "lane-respawned", "detached": bool(args.as_worker),
           "viewer": args.viewer, "open_line": opened, "spawn_extra": {"resume_n": resume_n},
           "no_swap": bool(getattr(args, "no_swap", False)), "brief_current": brief_abs,
           "pre_event": {"event": "lane-resumed", "reason": lane_reason, "reason_src": lane_reason_src,
                           "brief": brief_abs, "brief_copy": brief_copy, "resume_n": resume_n,
                           "report": paths["report"],
                           "resumes_close_ts": closed.get("ts"), "age_s": round(age, 1),
                           "age_src": age_src, "config_sha256": config_sha,
                           "config_src": config_src, "config_match": config_match,
                           "after_limit": after_limit, "after_budget": after_budget,
                           "controls_checked": controls_checked,
                           "controls_pending": controls_pending, "inputs_checked": inputs_checked,
                           "budget_usd": budget,
                           "hard_usd": budget, "hard_src": hard_src, "soft_usd": soft_usd,
                           "soft_src": soft_src, "expect_usd": expect,
                           "deadline_s": deadline, "silence_s": silence,
                           "silence_src": silence_src, "definition_sha256": definition_sha,
                           # No new pick on a resume: the open's pick fields are copied, and a
                           # record from before them reads `unrecorded` (2026-09-08).
                           "model_src": recorded_source(opened, "model_src"),
                           "effort_src": recorded_source(opened, "effort_src"),
                           "choice_reason": (opened.get("choice_reason")
                                             if isinstance(opened.get("choice_reason"), str) else None)},
           "close_extra": {"resumed": True, "resume_n": resume_n},
           "soft_usd": soft_usd, "soft_src": soft_src, "controls_pending": controls_pending}
    # The session is claimed HERE, immediately before the first thing this resume writes or
    # starts, and not only checked at the top (critic finding 2 of review): a beat that took the
    # session while this call was preparing must turn it back at the door, whichever of the two
    # arrived first. The detach path above returned already, so the claim is the worker's own.
    with hold_session(beat_marker, "resume",
                      "a beat holds the lane's session; wait for it (bounded by %d s) and resume "
                      "again" % BEAT_TIMEOUT_S):
        return run_lane(ctx)


# ------------------------------------------------------------------ cost-figures ------------

def cmd_cost_figures(args):
    """Fold the run store's completed lane costs per class and print them; with `--check`,
    compare them against the routing table's `cost` blocks; with `--fold`, write the drifted
    ones back into that table.

    Without `--fold` it reads and prints and nothing else — it creates, modifies, moves and
    deletes nothing, so it is safe to run against a live store. `--fold` is the one writing
    path, and it writes ONE file: the routing table `--routing` names (else the one beside this
    script), or in a user's copy that copy's overlay (`fold_source`). It reads that file alone,
    never the merged record. It writes at the file's own indent and never sorts its keys, so the diff of a fold
    is the fields that changed and nothing else; a fold with nothing drifted writes nothing at
    all and says so; and a second fold of an already-folded file is a no-op, since every class
    then reads `same`.

    Exit 0 when nothing drifts, 1 when `--check` alone finds a drift or a class due its first
    block (with `--fold` the drift has been closed, so a successful fold exits 0), 2 on a broken
    premise (no records directory, no `.jsonl` in it, no completed close in any of them, an
    unreadable or malformed routing table, a table with no indent to keep)."""
    records_dir = args.records or os.path.join(store_root(), "spawn-records")
    folded, counts = fold_costs(records_dir)
    table, data, raw, routing_path = {}, None, None, None
    if args.check or args.fold:
        routing_path, raw, data = fold_source(
            args.routing or os.path.join(os.path.dirname(os.path.abspath(__file__)), "routing.json"))
        classes = data.get("classes") or {}
        if not isinstance(classes, dict) or not classes:
            die("routing table %s carries no classes to check against" % routing_path)
        for cls, row in classes.items():
            table[cls] = class_cost(row, cls)   # a malformed block is a premise failure
    lines, drifted = cost_figures_report(folded, counts, table, args.check or args.fold,
                                         records_dir, args.format)
    for line in lines:
        print(line)
    if args.fold:
        written, indent = fold_into_routing(routing_path, folded, data, raw)
        if written:
            said = ("cost-figures --fold: wrote %d class block(s) into %s at the file's own "
                    "indent (%d character(s)): %s"
                    % (len(written), routing_path, len(indent), " · ".join(written)))
        else:
            said = "cost-figures --fold: nothing drifted; %s was not written to" % routing_path
        # Under --format json stdout is one object a caller parses, so the fold's own line goes
        # to stderr rather than breaking it.
        if args.format == "json":
            sys.stderr.write(said + "\n")
        else:
            print(said)
        return 0
    return 1 if (args.check and drifted) else 0


# ------------------------------------------------------------------------- cli --------------

def add_wait_flags(parser, silence_default):
    parser.add_argument("--silence-s", type=float, default=None,
                        help="stall threshold in seconds (default: %s; 0 disables the watch)"
                             % silence_default)
    parser.add_argument("--poll-s", type=float, default=POLL_S,
                        help="liveness check interval in seconds (default %d)" % POLL_S)
    parser.add_argument("--no-transcript-s", type=float, default=NO_TRANSCRIPT_S,
                        help="seconds without a transcript that count as a stall (default %d)"
                             % NO_TRANSCRIPT_S)
    parser.add_argument("--report-words", type=int, default=REPORT_WORDS,
                        help="optional preview: print the first N words (default: the whole "
                             "report; 0 prints the pointer line only)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--record", help="spawn record path (default: the run store)")
    parser.add_argument("--projects-root")
    parser.add_argument("--home")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="lane.py", description="Spawn a thin headless lane from a lane home.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="build or refresh the base lane home")
    init.add_argument("--home", help="lane home (default: $LLM_WIKI_LANE_HOME or the run store)")
    init.set_defaults(func=cmd_init)

    spawn = sub.add_parser("spawn", help="spawn one lane and record it")
    spawn.add_argument("--run", required=True)
    spawn.add_argument("--lane", required=True, help="fresh lane id; only -pass<n> endings are reserved, in any letter case; existing destinations refuse")
    spawn.add_argument("--class", required=True, dest="class")
    spawn.add_argument("--brief", required=True)
    spawn.add_argument("--model")
    spawn.add_argument("--effort")
    spawn.add_argument("--viewer", choices=("terminal", "none"),
                       help="the run's console window: opened on this spawn when none is alive "
                            "(default: the grants file's viewer key, else terminal); none opts "
                            "out, as does AIMYTH_VIEWER=none")
    spawn.add_argument("--grant", action="append", default=[],
                       help="a directory or file the lane may read (repeatable)")
    spawn.add_argument("--write", action="append", default=[],
                       help="a directory or file the lane may write (repeatable)")
    spawn.add_argument("--grant-vault-root", action="store_true",
                       help="grant the vault root itself as a read grant")
    spawn.add_argument("--grants-from", metavar="LANE",
                       help="add the read and write grants this run's lane LANE opened with, from "
                            "the run record (a lane continuing another's work)")
    spawn.add_argument("--grants-only", action="store_true",
                       help="drop the row's literal grants and writes, so the call's --grant "
                            "and --write are the lane's whole scope (a fixture-bound lane)")
    spawn.add_argument("--config-dir", help="CLAUDE_CONFIG_DIR for the lane process only "
                                            "(a second login)")
    spawn.add_argument("--tools", help="comma-separated override of the class tool set")
    spawn.add_argument("--skill", action="append", default=[])
    spawn.add_argument("--mcp-config")
    spawn.add_argument("--no-swap", action="store_true",
                       help="do not move a fallen-back task to Astra at the close (probes, suites); the close still records the fallback")
    spawn.add_argument("--no-core", action="store_true",
                       help="leave the lane core out of the appended file (slices still go in)")
    spawn.add_argument("--append-core", metavar="FILE",
                       help="use this file as the lane core instead of the home's copy")
    spawn.add_argument("--reason", default="",
                       help="REQUIRED: why a lane rather than the head, opening with the "
                            "instrument-rule letter CLAUDE.md section 2.2 asks for — %s. "
                            "Omitted, whitespace-only and letterless take one refusal (exit 2), "
                            "before any record line" % REASON_FORMS)
    spawn.add_argument("--choice-reason", default="",
                       help="why THIS model and effort for this task (distinct from --reason, "
                            "which says why a lane at all). Under throttle auto a --model or "
                            "--effort departing from the row's anchor is refused without it "
                            "(exit 2, before any record line); recorded on lane-open as "
                            "choice_reason and, for a departing axis, as `auto: <text>` in "
                            "model_src/effort_src. Never required under a hand-set preset")
    spawn.add_argument("--plant", default="",
                       help="a test device the owner has explicitly permitted, recorded on the lane's record; "
                            "leave empty otherwise (CLAUDE.md section 12)")
    spawn.add_argument("--reading-list", default="")
    spawn.add_argument("--budget-usd", type=float,
                       help="RAISE the hard stop above the smaller of 5 x --expect-usd and the "
                            "run's envelope remainder; at or below it the composed cap is kept "
                            "and noted (raise-only, 2026-09-07)")
    spawn.add_argument("--expect-usd", type=decimal_estimate,
                       help="REQUIRED: the head's own positive finite dollar estimate; the soft "
                            "line (soft_src expect) and the base for a 5 x hard stop. Outside "
                            "the class median's factor-3 band prints an advisory only; exact decimal "
                            "comparison keeps equality quiet (2026-09-16)")
    spawn.add_argument("--max-turns", type=int)
    spawn.add_argument("--deadline-s", type=int)
    spawn.add_argument("--baseline-lane", default="",
                       help="raise the stall threshold to 1.5 x this lane's recorded duration")
    spawn.add_argument("--session-id")
    spawn.add_argument("--throttle")
    spawn.add_argument("--routing")
    spawn.add_argument("--source-pass", help=argparse.SUPPRESS)
    spawn.add_argument("--source-disposition", help=argparse.SUPPRESS)
    spawn.add_argument("--baseline", default="")
    spawn.add_argument("--delegation", choices=REGIMES,
                       help="the run's delegation regime for the record (required while the "
                            "Settings line reads auto); goes with --delegation-src")
    spawn.add_argument("--delegation-src", choices=("head", "owner"),
                       help="who chose it: head (resolved under auto) or owner")
    spawn.add_argument("--require-trust", action="store_true",
                       help="treat a missing workspace-trust entry as a premise failure")
    spawn.add_argument("--prompt-arg", action="store_true",
                       help="pass the brief as the prompt argument instead of on stdin")
    spawn.add_argument("--detach", action="store_true",
                       help="run the lane in a worker that survives the caller, once every argument "
                            "and grant check has passed in the caller (a refusal exits 2 and starts "
                            "no worker); the foreground watches it")
    spawn.add_argument("--no-wait", action="store_true",
                       help="with --detach: wait up to --ack-wait-s for THIS call's own lane-open "
                            "(its wrapper_pid the worker's), then: acknowledged, print `detached pid "
                            "N session S` and exit 0; the worker exits first, print its log tail and "
                            "exit non-zero; the worker lives but no lane-open arrives in time, or the "
                            "record cannot be read, print `detached pid N, unconfirmed after S s` "
                            "and exit %d, the worker left running" % EXIT_UNCONFIRMED)
    spawn.add_argument("--ack-wait-s", type=float, default=ACK_WAIT_S,
                       help="with --detach --no-wait: the acknowledgement bound in seconds (default "
                            "%d; a waiting limit, not a stall controller)" % ACK_WAIT_S)
    spawn.add_argument("--item", default=None, metavar="ITEM", type=item_name,
                       help="the run item this lane works on, recorded on lane-open: it starts the "
                            "item's bar and the console files the lane there; with none on a "
                            "hands-off run, the lane sits under the item in hand, marked inferred")
    spawn.add_argument("--dry-run", action="store_true")
    spawn.add_argument("--as-worker", action="store_true", help=argparse.SUPPRESS)
    spawn.add_argument("--worker-caps", default=None, help=argparse.SUPPRESS)
    add_wait_flags(spawn, "the class default, %d for the %s and %s classes and %d for every other"
                   % (LONG_SILENCE_S, ", ".join(LONG_SILENCE_CLASSES[:-1]), LONG_SILENCE_CLASSES[-1],
                      DEFAULT_SILENCE_S))
    spawn.set_defaults(func=cmd_spawn)

    for command in ("watch", "wait"):
        watch = sub.add_parser(command, help=("wait on a running lane; close it if its wrapper is gone"
                               if command == "watch" else
                               "background wait without a time bound; return on the latest close or a watcher error"))
        watch.add_argument("--run", required=True)
        watch.add_argument("--lane", required=True)
        if command == "watch":
            watch.add_argument("--max-wait-s", type=float, default=WATCH_MAX_WAIT_S,
                               help="return `still-running` (exit %d) after this many seconds "
                                    "(default %d; 0 waits without bound)"
                                    % (EXIT_STILL_RUNNING, WATCH_MAX_WAIT_S))
        else:
            watch.set_defaults(max_wait_s=0)
        watch.add_argument("--appear-s", type=float, default=WATCH_APPEAR_S,
                           help="seconds to wait for a just-detached lane's record lines before "
                                "calling it unknown (default %d)" % WATCH_APPEAR_S)
        add_wait_flags(watch, "none: this watch requests an owner stop only when given a threshold")
        watch.set_defaults(func=cmd_watch if command == "watch" else cmd_wait)

    kill = sub.add_parser("kill", help="stop a running lane and write its lane-closed with "
                                       "exit_class killed (never kill a lane by hand)")
    kill.add_argument("--run", required=True)
    kill.add_argument("--lane", required=True)
    kill.add_argument("--escalate", action="store_true", help="explicitly stop a verified unresponsive wrapper")
    kill.add_argument("--reason", required=True,
                      help="why the lane is being stopped, in the caller's own words; it is "
                           "written into the close line and printed. REQUIRED: a kill with no "
                           "reason on the record is the hand kill this command replaces")
    kill.add_argument("--report-words", type=int, default=REPORT_WORDS,
                      help="optional preview of the lane's last report (default: the whole report)")
    kill.add_argument("--record", help="spawn record path (default: the run store)")
    kill.add_argument("--projects-root")
    kill.add_argument("--home")
    kill.set_defaults(func=cmd_kill)

    resume_help = ("resume a long write cut short by a usage limit, with work "
                   "on disk and checked, or the multi-expert panel's round 2; "
                   "a second pass goes to a fresh helper with a compact hand-off "
                   "(D29: after a `limit` close the cache window is "
                   "waived and `lane-resumed` records after_limit and "
                   "age_s; after a `budget` close only a raised "
                   "--budget-usd resumes the lane; existing per-pass report or brief paths refuse before writes)")
    resume = sub.add_parser("resume", help=resume_help, description=resume_help)
    resume.add_argument("--run", required=True)
    resume.add_argument("--lane", required=True)
    resume.add_argument("--brief", default=None,
                        help="the follow-up brief, on standard input to the resumed session; "
                             "REQUIRED unless --beat")
    resume.add_argument("--beat", action="store_true",
                        help="the held-lane beat (handsoff.py hold): the same command line as "
                             "a resume, the fixed line %r on standard input, no report, no "
                             "pass file, one hold-beat record line with the call's usage; "
                             "refused when the resolved configuration differs from the "
                             "lane-open's config_sha256" % BEAT_PROMPT)
    resume.add_argument("--budget-usd", type=float,
                        help="RAISE the hard stop for the resumed call above the cap the resume "
                             "composed (5 x the lane-open expect_usd, or the run's "
                             "envelope remainder where that is smaller); a value at or below it "
                             "is not applied: that cap is kept and one line says so (2026-09-07). "
                             "REQUIRED, and above the stopped pass's recorded cap, after a `budget` close, "
                             "which never resumes on the cap that stopped it")
    resume.add_argument("--expect-usd", type=float,
                        help="optional soft-line estimate for this pass; defaults to lane-open "
                             "expect_usd. The hard base always uses the lane-open estimate")
    resume.add_argument("--reason", default="",
                        help="NOT needed in the ordinary case: `lane-resumed` carries the reason "
                             "the lane-open recorded. Pass it only where that record names no "
                             "instrument-rule letter (one written before the check); against a "
                             "record that carries one it is refused and the recorded reason stands")
    resume.add_argument("--max-turns", type=int)
    resume.add_argument("--deadline-s", type=int)
    resume.add_argument("--baseline-lane", default="")
    resume.add_argument("--no-swap", action="store_true",
                        help="as on spawn: no Astra swap at this pass's close")
    resume.add_argument("--viewer", choices=("terminal", "none"),
                        help="the run's console window, as on spawn; a detached resume's caller "
                             "opens it and runs its worker under none")
    resume.add_argument("--detach", action="store_true",
                        help="run the resumed call in a worker that survives the caller, once every "
                             "check has passed in the caller (a refusal exits 2 and starts no "
                             "worker); the foreground watches it and returns on the resumed call's close")
    resume.add_argument("--no-wait", action="store_true",
                        help="with --detach: wait up to --ack-wait-s for THIS call's own "
                             "lane-resumed (its wrapper_pid the worker's), then: acknowledged, print "
                             "`detached pid N session S` and exit 0; the worker exits first, print "
                             "its log tail and exit non-zero; the worker lives but no lane-resumed "
                             "arrives in time, or the record cannot be read, print `detached pid N, "
                             "unconfirmed after S s` and exit %d, the worker left running"
                             % EXIT_UNCONFIRMED)
    resume.add_argument("--ack-wait-s", type=float, default=ACK_WAIT_S,
                        help="with --detach --no-wait: the acknowledgement bound in seconds "
                             "(default %d; a waiting limit, not a stall controller)" % ACK_WAIT_S)
    resume.add_argument("--as-worker", action="store_true", help=argparse.SUPPRESS)
    resume.add_argument("--worker-caps", default=None, help=argparse.SUPPRESS)
    add_wait_flags(resume, "the lane-open's threshold, else the class default")
    resume.set_defaults(func=cmd_resume)

    advise = sub.add_parser("advise", help="the head's resume-or-restart counsel for a closed lane, "
                                           "from its close record: the stop reason first, then the "
                                           "cost (cache age, memory at close, work on disk); prints "
                                           "one line, writes nothing")
    advise.add_argument("--run", required=True)
    advise.add_argument("--lane", required=True)
    advise.add_argument("--record", default=None, help="spawn record path (default: the run store)")
    advise.add_argument("--stage", default=None, help="the lane's stage directory, if it has one")
    advise.add_argument("--report", default=None, help="the lane's report file (default: latest close report, else the first-pass path)")
    advise.set_defaults(func=cmd_advise)
    figures = sub.add_parser("cost-figures",
                             help="fold the run store's completed lane costs per class and "
                                  "print them (writes nothing without --fold); --check "
                                  "compares them with the routing table's cost blocks and "
                                  "--fold writes the drifted ones back into that table")
    figures.add_argument("--records", help="directory of *.jsonl spawn records (default: the "
                                           "run store's spawn-records)")
    figures.add_argument("--routing", help="routing table to check against (default: the one "
                                           "beside this script)")
    figures.add_argument("--check", action="store_true",
                         help="compare each class with its cost block: exit 1 on any drift or "
                              "a class of %d or more completed lanes with no block"
                              % COST_FLOOR_N)
    figures.add_argument("--fold", action="store_true",
                         help="WRITES: fold every drifted class's figures back into the "
                              "routing table --routing names, or in a user's copy into its "
                              "overlay, at the file's own indent and in "
                              "its own key order, so the diff is the fields that changed; "
                              "nothing drifted writes nothing. This is the only path in "
                              "`cost-figures` that writes at all")
    figures.add_argument("--format", choices=("text", "json"), default="text")
    figures.set_defaults(func=cmd_cost_figures)
    a3_add_recover_parser(sub, "claude")
    return parser


@a3_public
def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
