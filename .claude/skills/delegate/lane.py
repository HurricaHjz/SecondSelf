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
    lane.py resume --run ID --lane ID --brief FILE [--detach [--no-wait]]   (the spawn's reason is carried forward)
    lane.py resume --run ID --lane ID --beat                                (the held-lane beat: no brief, no report)

The commands and what they guarantee
------------------------------------
`init` is idempotent. It writes the lane home's settings (one PreToolUse hook on Bash running
the fence, no other hooks, no MCP servers), a copy of the fence, and the contract slices the
thin classes read by path instead of inheriting: `contract/schema-s4.md` (the schema section
of the vault contract) and `contract/confidence-rubric.md` (the confidence design page, body
only). Each is written to a temporary file and renamed into place, and regenerated only when
its source's hash changes, so two concurrent spawns can never read a half-written slice. It
also lists the skill slices found under the delegate skill's `lane-home-src/` (each spawn reads
them there; init installs no `skills/` link and removes one an earlier init left), makes
the memory directory of every class whose definition declares `memory: local` (the
memory-hunter's) a real directory under the home synced from the vault's copy, and prints what
it created, kept or regenerated.

The memory directory (register 2026-09-04). `--restricted` resolves a symlink before it confines
Write and Edit to the working directories; a link into the vault cannot authorise a memory edit.
A real directory inside the home passes. `init` removes a link an
earlier init left (the link alone, never the vault directory behind it) and copies the vault's
files in; every `lane-closed` of such a class copies back the files the lane changed. Neither
direction overwrites a file the other side changed since the last sync (the hashes both sides held
then sit in the home's state file): `init` keeps such a home copy and names it; the close leaves
such a vault file as it is, lists it under `memory_sync.conflicts` and prints one line.

A row's literal grants name the live vault, so a fixture-bound lane takes `--grants-only`:
the literals are dropped (and recorded), the row's per-call slots are still filled from the
call, and `--grant`/`--write` become the lane's whole scope — plus the lane home, /tmp and
/dev, which the fence sanctions for every lane.

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
within the row's options. Task kind decides the model: opus (Opus 5.5) for closed work, Astra
through codex-lane.py for open work, opus 5.5 on every Claude seat and fable only on the owner's word
(a by-name `--model fable` is recorded as outside the options, never refused); the `top` and `cheap`
presets resolve the model to opus through the table's `preset_model` (owner rulings 2026-09-22 and
2026-09-29). Effort on opus: xhigh the anchor, max only after a failed
xhigh or for a genuinely hard or very extensive task. Every close carries `fallback`, read from the
result's modelUsage ids against the alias map in prices.json (`models`): a second non-helper id,
or one other than the alias's recorded resolution, is a transparent safeguard fallback (Opus 5.5
re-routes some tasks with no refusal to see); the wrapper then moves the task's remaining work to
Astra itself — a derived brief, one detached `codex-lane.py spawn` of `<lane>-astra` with the same
class, write scope, effort and regime, a `lane-swapped` line — and the summary and stderr say
FALLBACK with the new lane; `--no-swap` opts out; the run console alerts on the close and the
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
`permissions.allow` rules `Edit(//path)` / `Write(//path)` for every write grant; whether
that list beats the harness's sensitive-path guard under `.claude/` is recorded beside
`settings_for` below. A FILE grant whose parent is the vault root or a home directory earns one
stderr warning naming that parent, since the grant reaches the whole directory (register
2026-09-08, the judge-brief entry); a warning, never a refusal.

Controls (D19): a brief line `CONTROL+: <phrase> in <file>` is a positive control the wrapper
checks before the spawn — the phrase as a fixed string in that file (a relative file resolves
against the vault). A zero match, a missing file or a malformed line refuses the spawn (exit 2,
no record written); the matches are recorded as `controls_checked`.

Brief paths and closed runs. A brief line carrying a doubled root refuses the spawn or the resume
(exit 2, the line quoted, before any record line; register 2026-09-09 19:03): a root path (led by
`~`, a `$VARIABLE`, a hidden directory name, or an absolute path of the home, temporary or system
families) that embeds a second absolute path, whatever its lead (`embedded_root` says what counts),
or the vault root twice inside one path token. A spawn onto a closed run, whose record holds a
`run-close` with no later `run-open` or `run-resume` whatever else follows it, prints one warning
naming the close and proceeds (register 2026-09-03, two head processes on one session id). Both run
in the caller before any detach.

The watchdog (D20)
------------------
While it waits, the wrapper checks every `--poll-s` seconds (default 30) the NEWER of the lane
transcript's mtime and the lane's progress file's mtime (`/tmp/<run>-<lane>.progress`, which a
lane appends to inside long calls; the path also reaches the lane as
`LLM_WIKI_LANE_PROGRESS`). Silence past `--silence-s` is a stall, never reasoning: the
threshold is per call, because the transcript is silent for the whole of any tool call, so a
brief that runs a long suite passes a larger value; `--silence-s 0` disables the watch. No
transcript within `--no-transcript-s` (default 120) of the spawn is a stall of reason `no
transcript`. Action: SIGTERM to the process group, the kill grace, SIGKILL; a `stall` event;
`exit_class` `stall`; exit 5.

`watch` attaches the same loop to a lane already running (pid, wrapper pid and session id
from the record). It never kills a live wrapper's lane for silence unless `--silence-s` was
passed to `watch` itself. When the recorded wrapper is gone and no `lane-closed` exists, it
waits for the lane process (bounded by the recorded deadline) and then closes the lane from
its transcript: `exit_class: watch-closed`, `cost_src: transcript-estimate`, `denials:
unknown`. It returns `still-running` (exit 8) after `--max-wait-s` so a head can re-issue it
as a bounded blocking call. A watch that finds the lane already closed waits up to `--appear-s`
for a newer `lane-resumed` before it refuses: a resume issued with `--detach --no-wait` writes that
line a moment after it returns, and the close that counts is the one after the latest open or
resume, never the previous call's (the rule codex-lane.py's watch shares).

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
it, exiting with the worker's exit code once `lane-closed` appears; `--detach --no-wait`
prints `detached pid N session S` and exits 0 at once. `lane-spawned` carries `wrapper_pid`,
the process that will write the close. `resume` takes the same two flags (register 2026-09-10
15:22). The caller, not the worker, opens the run's console, before the worker starts, and hands
the worker `--viewer none` (appended, so it wins over any `--viewer` the command carried).
(register 2026-09-09 11:21; the opener itself is handsoff.py's).

`resume` (D25) re-enters a finished lane's session (`--resume <session id>`, the follow-up
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
exit class and `config_sha256`. That hash is the resolved command line's configuration — every
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
names it on its line.
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

The report (D8): stdout carries the complete report by default. An explicit preview
preview request uses `--report-words N` and names the full persisted text in its pointer.
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
budget stop, max-turns or deadline; 5 a stall; 6 an account or usage limit (`exit_class`
`limit`: the transcript's last assistant record carries a synthetic model with zero usage —
the shape a limit stop leaves, as the watermark hook documents — or the result names a usage
limit); 8 `watch` returned `still-running`. Permission denials are NOT an error: they are
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
    hard_src names the deciding term. An explicit --budget-usd raises only; an exhausted envelope
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
  - silence threshold, default 900 s: a compatibility bound, set by judgement, unmeasured for
    a new workload. `--baseline-lane` raises it to 1.5 × the predecessor's runtime when larger;
    the multiplier is set by judgement, unmeasured.
  - no-transcript bound, 120 s: the harness writes the transcript file on the first user
    message, seconds after the spawn; 120 s is generous headroom, set by judgement.
  - resume window, 55 min: the 1-hour cache tier minus 5 min headroom (D25).
  - reports print in full unless the caller explicitly requests a preview.
  - limit text guard, 60 words: a limit stop is a sentence, a report is hundreds of words, so
    a successful result mentioning "limit" and "usage" counts only under that length or on an
    error; set by judgement, unmeasured.
  - watch bound, 570 s: the shell tool's 600 s cap less 30 s so the wrapper returns before
    the tool kills it; set by judgement.
  - doubled-root depth, 2 path components: a vault root of fewer (`/`, `/tmp`) sits inside every
    path, so the repeated-root pattern is skipped for it; set by judgement, unmeasured.
  - core injection shape: an appended system-prompt file, verified with a marker control below.

Core injection
--------------
The appended system-prompt file carries the lane core and skill slices. Do not assume that
an inline agent definition preloads skills: verify the selected harness path with a marker
control. The core comes from `--append-core FILE`, then the lane-home copy, then the shipped
`templates/lane-core.md`. `--no-core` drops the core and keeps the slices. Every spawn records
`appended` and `appended_bytes` so its actual context remains auditable.

    So the appended file is the single carrier. Per spawn the wrapper concatenates the lane
    core, then every slice the class row's `skills.default` names, then any `--skill` extra it
    can resolve, each introduced by a one-line heading naming the slice and its source path,
    strips each source's YAML frontmatter (metadata for a loader that is not running here),
    writes the result to the run store as `<RUN>-appended-<LANE>.md` beside the definition
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
import fcntl
import glob as globmod
import hashlib
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
DEFAULT_SILENCE_S = 900         # compatibility default; set by judgement, unmeasured for a new workload
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
MEMORY_STATE_KEY = "memory-sync:%s"   # the home state file's key for one memory directory's last-synced hashes
EXIT_CODES = {"completed": 0, "stall": 5, "limit": 6}    # every other class exits 3
EXIT_STILL_RUNNING = 8
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
    Missing and empty records are valid; an unreadable or malformed record cannot prove absence."""
    try:
        with open(record_path, "r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except ValueError as exc:
                    die("cannot check lane ids in %s at line %d: %s" % (record_path, number, exc))
                if not isinstance(event, dict):
                    die("cannot check lane ids in %s at line %d: event is not an object"
                        % (record_path, number))
                existing = event.get("lane")
                if isinstance(existing, str) and existing.casefold() == lane_id.casefold():
                    die("--lane %r is case-equivalent to existing lane %r in %s — "
                        "spawn needs a fresh lane id" % (lane_id, existing, record_path))
    except FileNotFoundError:
        return
    except (OSError, UnicodeError) as exc:
        die("cannot check lane ids in %s: %s" % (record_path, exc))


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


def grant_parent_warnings(values, vault, flag):
    """One stderr line per FILE grant whose parent is the vault root or a home directory: the file
    tools can only be widened by directory, so such a grant hands the lane that whole directory
    (register 2026-09-08, the judge-brief entry; delegate skill section 3, slot 2). A warning,
    never a refusal; a path that does not exist is left to the spawn's own check. A home directory
    is the caller's own home or any directory beside it, unless the home's parent is the
    filesystem root."""
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
        else:
            continue
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


def caller_checks(args):
    """What a spawn checks in the caller's own terminal before any detach (a detached worker skips
    them): the brief is there and carries no doubled root, and the two warnings — a file grant
    reaching a whole vault or home directory, a spawn onto a closed run."""
    vault = vault_root()
    if not os.path.isfile(args.brief):
        die("brief file not found: %s" % args.brief)
    brief = read_text(args.brief, "the brief")
    if not brief.strip():
        die("brief file is empty: %s" % args.brief)
    refuse_doubled_root(args.brief, brief, vault)
    grant_parent_warnings(args.grant, vault, "--grant")
    grant_parent_warnings(args.write, vault, "--write")
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


def resolve_slice(name, home, vault):
    """A slice's text, from the lane home first (a slice placed there by hand; init installs none)
    then the shipped source. Returns (source path, body with its frontmatter stripped) or (None,
    None)."""
    for candidate in (os.path.join(home, "skills", name, "SKILL.md"),
                      os.path.join(slice_sources(vault), name, "SKILL.md"),
                      os.path.join(home, "skills", "%s.md" % name)):
        if os.path.isfile(candidate):
            return candidate, strip_frontmatter(read_text(candidate, "slice %s" % name))
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

    # A memory directory per class whose definition declares `memory: local`, a real directory at
    # the relative path the vault uses. Keyed on the declaration, so a future memory class is
    # covered without editing this list.
    agents_dir = os.path.join(vault, ".claude", "agents")
    memory_classes = []
    for name in sorted(os.listdir(agents_dir)) if os.path.isdir(agents_dir) else []:
        if not name.endswith(".md"):
            continue
        fields, _ = parse_frontmatter(read_text(os.path.join(agents_dir, name), "a definition"))
        if fields.get("memory") == "local":
            memory_classes.append(name[:-3])
    for cls_name in memory_classes:
        mem_rel = os.path.join(".claude", "agent-memory-local", cls_name)
        vault_mem = os.path.join(vault, mem_rel)
        home_mem = os.path.join(home, mem_rel)
        if not os.path.isdir(vault_mem):
            missing.append(mem_rel)
            continue
        os.makedirs(os.path.dirname(home_mem), exist_ok=True)
        # A real directory, never a link into the vault: `--restricted` resolves a link before it
        # confines Write and Edit to the working directories; a link cannot widen the grant for the
        # hunter's own MEMORY.md edit (register 2026-09-04). A link an earlier init left is
        # removed — the link alone, never the vault directory behind it — and replaced.
        if os.path.islink(home_mem):
            os.unlink(home_mem)
            report.append(("replaced", mem_rel + " (a symlink into the vault; now a real directory)"))
        elif os.path.exists(home_mem) and not os.path.isdir(home_mem):
            report.append(("kept", mem_rel + " (a file, not a directory: left alone, not synced)"))
            continue
        os.makedirs(home_mem, mode=0o700, exist_ok=True)
        recorded = state.setdefault(MEMORY_STATE_KEY % mem_rel, {})
        copied, kept, unchanged = sync_memory_down(vault_mem, home_mem, recorded)
        report.append(("synced", "%s (from the vault: %d copied, %d unchanged%s)" % (
            mem_rel, len(copied), len(unchanged),
            (", %d kept: changed in the home since the last sync: %s" % (len(kept), ", ".join(kept)))
            if kept else "")))
    if not memory_classes:
        missing.append("a class declaring `memory: local`")

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

def load_routing(path, parse_float=float):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle, parse_float=parse_float)
    except OSError as exc:
        die("routing table unreadable (%s): %s" % (path, exc))
    except ValueError as exc:
        die("routing table is not JSON (%s): %s" % (path, exc))
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
    the per-call departure is recorded by the caller, never re-resolved here."""
    model_opts = field(row, cls, "model", "options")
    model_default = field(row, cls, "model", "default")
    effort_opts = field(row, cls, "effort", "options")
    effort_default = field(row, cls, "effort", "default")
    model_order = routing["order"]["model"]
    effort_order = routing["order"]["effort"]
    model, model_weak, _ = pick(model_order, model_opts, model_default, throttle)
    pinned = preset_model(routing, throttle)   # owner ruling 2026-09-29: `top` and `cheap` resolve to opus
    if pinned is not None:
        if pinned not in model_opts:
            die("routing `preset_model.%s` names %r, which class `%s` does not list among its model "
                "options %r" % (throttle, pinned, cls, model_opts))
        model = pinned
    effort, effort_weak, effort_strong = pick(effort_order, effort_opts, effort_default, throttle)
    if throttle == "cheap":
        effort = effort_strong   # cheap constrains spend on the model axis; effort stays the ceiling (throttle.py's table, 2026-09-06)
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


def envelope_remainder(run, record_path):
    """(remainder, reason, envelope) for the run the lane joins: handsoff.py's `envelope_left`
    over the run record, imported lazily from beside this script so the wrapper still runs
    without it. The remainder is None wherever no number can be had — no module, no record,
    no `run-open`, no `envelope_usd` on it, or a meter that gave no session total — and the
    reason says which, for the record's `hard_src`."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(here, "handsoff.py")):
        return None, "handsoff.py not found beside lane.py", None
    if here not in sys.path:
        sys.path.insert(0, here)
    sys.dont_write_bytecode = True   # the import must never leave a __pycache__ in the skill directory
    try:
        import handsoff
    except Exception as exc:         # a sibling script that does not import is a reason, never a crash
        return None, "handsoff.py did not import (%s)" % exc, None
    if not os.path.isfile(record_path):
        return None, "no run record at %s" % record_path, None
    events, _ = handsoff.read_record(record_path)
    if handsoff.last_index(events, ("run-open",)) < 0:
        return None, "no run-open event in the run record", None
    envelope_of = getattr(handsoff, "envelope_of", None)   # the latest figure: raise-envelope (2026-09-13)
    envelope = (envelope_of(events)[0] if envelope_of
                else handsoff.run_open(events).get("envelope_usd"))
    start = handsoff.last_index(events, handsoff.SESSION_EVENTS)
    remainder, reason = handsoff.envelope_left(events, run, None, start)
    if remainder is None:
        return None, reason, envelope
    return float(remainder), reason, float(envelope)


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


def cost_caps(explicit, expect, run, record_path, term="composed"):
    """(hard_usd, hard_src): min(5 × estimate, envelope remainder), then raise-only.
    Without a metered remainder the estimate decides and the source names the missing
    premise. An exhausted envelope requires the existing explicit override (2026-09-07)."""
    if explicit is not None and (not math.isfinite(explicit) or explicit <= 0):
        die("--budget-usd must be a positive finite dollar figure")
    base, base_src = hard_base(expect)
    remainder, reason, envelope = envelope_remainder(run, record_path)
    if remainder is None:
        hard, src = base, "%s (envelope unmetered: %s)" % (base_src, reason)
    elif remainder <= 0:
        if explicit is None:
            die("run %s: the envelope has nothing left (remainder $%.2f of $%.2f: %s) — no lane "
                "runs on a cap of nothing; raise the envelope or pass --budget-usd with a reason"
                % (run, remainder, envelope, reason))
        return (float(explicit),
                "explicit --budget-usd (override of an exhausted envelope $%.2f, remainder $%.2f)"
                % (envelope, remainder))
    elif remainder < base:
        hard = remainder
        src = ("envelope remainder $%.2f (envelope $%.2f, spent $%.2f; below %s = $%.2f)"
               % (remainder, envelope, envelope - remainder, base_src, base))
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


def fold_into_routing(path, folded, data, raw):
    """Write each drifted class's cost block into the routing table, and return (classes
    written, the indent kept).

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

def thin_definition(vault, cls, tools, description_fallback):
    """The class's own body with a thin frontmatter: the row's tools and skills, no `effort:`
    (ignored on the headless path), `memory: local` only where the source definition had it."""
    path = os.path.join(vault, ".claude", "agents", "%s.md" % cls)
    if not os.path.isfile(path):
        die("no definition for class `%s` at %s" % (cls, path))
    text = read_text(path, "the class definition")
    fields, body = parse_frontmatter(text)
    if not body.strip():
        die("definition %s has an empty body" % path)
    # Do not depend on a `skills:` key in the inline --agents JSON.
    # The slices travel in the appended system-prompt file instead.
    agent = {"description": fields.get("description") or description_fallback,
             "prompt": body.rstrip() + "\n",
             "tools": list(tools)}
    if fields.get("memory") == "local":
        agent["memory"] = "local"
    return path, sha(text), agent


def definition_markdown(cls, agent, model, effort):
    lines = ["---", "name: %s" % cls, "description: %s" % agent["description"],
             "tools: %s" % ", ".join(agent["tools"])]
    if agent.get("memory"):
        lines.append("memory: %s" % agent["memory"])
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


def memory_dir(home, cls):
    """The class's own memory directory inside the lane home, when it has one. Keyed on the
    directory `init` materialises for a class whose definition declares `memory: local`, not
    on a class name or a placeholder's wording, so a future memory class is covered."""
    path = os.path.join(home, ".claude", "agent-memory-local", cls)
    return path if os.path.isdir(path) else None


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


def memory_files(directory):
    """Every regular file under a memory directory, relative to it; links are skipped, since the
    sync copies content and never follows a link somewhere else."""
    out = []
    for base, dirs, names in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(base, d)))
        for name in sorted(names):
            path = os.path.join(base, name)
            if os.path.isfile(path) and not os.path.islink(path):
                out.append(os.path.relpath(path, directory))
    return out


def copy_atomic(source, target):
    """Copy a file's bytes to `target` through a temporary name beside it and a rename, so no
    reader of either copy ever sees half a file."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temp = "%s.%d.lane-sync.tmp" % (target, os.getpid())
    shutil.copyfile(source, temp)
    os.replace(temp, target)


def sync_memory_down(vault_mem, home_mem, recorded):
    """`init`'s direction, the vault's copy to the home's: (copied, kept, unchanged). A home file
    that differs from the vault's is replaced only while it still holds what the last sync left
    there (`recorded`: relative path -> sha); one changed since — a lane's write whose close never
    synced it back — is kept and named, never overwritten."""
    copied, kept, unchanged = [], [], []
    for rel in memory_files(vault_mem):
        source, target = os.path.join(vault_mem, rel), os.path.join(home_mem, rel)
        vault_sha = file_sha(source)
        if vault_sha is None:
            continue
        if os.path.isdir(target) or os.path.islink(target):
            kept.append(rel)
            continue
        home_sha = file_sha(target) if os.path.exists(target) else None
        if home_sha == vault_sha:
            recorded[rel] = vault_sha
            unchanged.append(rel)
        elif home_sha is None or home_sha == recorded.get(rel):
            copy_atomic(source, target)
            recorded[rel] = vault_sha
            copied.append(rel)
        else:
            kept.append(rel)
    return copied, kept, unchanged


def sync_memory_back(home, cls, vault):
    """A memory class's close, the home's copy to the vault's: each file the lane changed since the
    last sync is copied to the vault, unless the vault's own file changed since then too — a
    conflict left for the head, both copies kept as they are. None for a class with no real memory
    directory in the home (every class but a memory one, and a home still holding the old link). A
    failure is recorded on the result, never raised: the close line is written whatever happens."""
    if not cls:
        return None
    rel_dir = os.path.join(".claude", "agent-memory-local", cls)
    home_mem, vault_mem = os.path.join(home, rel_dir), os.path.join(vault, rel_dir)
    if not os.path.isdir(home_mem) or os.path.islink(home_mem):
        return None
    out = {"dir": rel_dir, "copied": [], "conflicts": [], "error": None}
    if not os.path.isdir(vault_mem):
        out["error"] = "the vault has no %s to sync to" % rel_dir
    else:
        try:
            state = load_state(home)
            recorded = state.setdefault(MEMORY_STATE_KEY % rel_dir, {})
            for rel in memory_files(home_mem):
                source, target = os.path.join(home_mem, rel), os.path.join(vault_mem, rel)
                home_sha = file_sha(source)
                if home_sha is None:
                    continue
                vault_sha = file_sha(target) if os.path.isfile(target) else None
                last = recorded.get(rel)
                if home_sha == vault_sha:
                    recorded[rel] = home_sha
                elif home_sha == last:
                    continue      # the lane left it alone; the vault's newer copy comes down at the next init
                elif vault_sha == last and not os.path.isdir(target):
                    copy_atomic(source, target)   # the vault's copy is as the last sync left it (or absent on both sides then)
                    recorded[rel] = home_sha
                    out["copied"].append(rel)
                else:
                    out["conflicts"].append(rel)
            write_atomic(state_path(home), json.dumps(state, indent=1, sort_keys=True) + "\n")
        except OSError as exc:
            out["error"] = str(exc)
    if out["copied"] or out["conflicts"] or out["error"]:
        sys.stderr.write("lane.py: memory sync to the vault's %s: %d copied%s%s\n" % (
            rel_dir, len(out["copied"]),
            (" · conflict (changed on both sides since the last sync, both kept): %s"
             % ", ".join(out["conflicts"])) if out["conflicts"] else "",
            (" · error: %s" % out["error"]) if out["error"] else ""))
    return out


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


def settings_for(home, write_entries):
    """The per-spawn settings: the home's hooks plus Edit and Write allow rules for every
    write grant, in both spellings (design D18). Sensitive-path restrictions still bind;
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
    out = {"hooks": hooks}
    if allow:
        out["permissions"] = {"allow": allow}
    return out, allow


# ---------------------------------------------------------------------- controls -----------

CONTROL_RE = re.compile(r"^.*?\bCONTROL\+:\s*(.+?)\s*$")   # Accept a control after a label as well as at the start of a line.


def unwrap(text):
    text = text.strip()
    if 1 < len(text) and text[0] == text[-1] and text[0] in "\"'`":
        return text[1:-1]
    return text


def parse_controls(brief):
    """Every `CONTROL+: <phrase> in <file>` line of a brief; the split is on the LAST ` in `,
    so a phrase may contain the word and a file path may not."""
    out = []
    for number, line in enumerate(brief.splitlines(), 1):
        match = CONTROL_RE.match(line)
        if not match:
            continue
        body = match.group(1)
        cut = body.rfind(" in ")
        phrase = unwrap(body[:cut]) if cut != -1 else ""
        path = unwrap(body[cut + 4:]) if cut != -1 else ""
        if not phrase or not path:
            die("brief line %d: malformed control line (want `CONTROL+: <phrase> in <file>`): %s"
                % (number, line.strip()))
        out.append({"line": number, "phrase": phrase, "file": path})
    return out


def check_controls(controls, vault):
    """Each phrase as a fixed string in its file; a zero match refuses the spawn (design D19)."""
    checked = []
    for control in controls:
        path = os.path.expanduser(control["file"])
        if not os.path.isabs(path):
            path = os.path.join(vault, path)
        path = os.path.realpath(path)
        if not os.path.isfile(path):
            die("brief line %d: control file not found: %s" % (control["line"], control["file"]))
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            count = handle.read().count(control["phrase"])
        if count == 0:
            die("brief line %d: control phrase %r matches nothing in %s — the spawn is refused"
                % (control["line"], control["phrase"], path))
        checked.append({"phrase": control["phrase"], "file": path, "matches": count})
    return checked


# ------------------------------------------------------------------- transcript ------------

def find_transcript(projects_root, home, session_id):
    direct = os.path.join(projects_root, dashed(home), "%s.jsonl" % session_id)
    if os.path.isfile(direct):
        return direct
    hits = sorted(globmod.glob(os.path.join(projects_root, "*", "%s.jsonl" % session_id)))
    return hits[0] if hits else None


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


def parse_transcript(path):
    """Everything the close line reports, read from JSON records, never by substring grep on
    the raw file: efforts applied, cache write tiers, peak call context, fence denials, a
    refusal, the last assistant text, token totals, and the limit-stop shape (the last
    assistant record carrying a synthetic model with all-zero usage)."""
    out = {"efforts": [], "tiers": [], "peak": 0, "fence_denials": 0, "fence_allows": 0,
           "refusal": False, "last_text": "", "records": 0, "unparseable": 0,
           "transcript": path, "calls": 0, "synthetic_stop": False, "last_model": None,
           "tokens": dict((key, 0) for key in USAGE_KEYS)}
    if not path or not os.path.isfile(path):
        out["transcript"] = None
        return out
    final = {}
    order = []
    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        out["transcript"] = None
        return out
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
    return out


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


def append_record(path, payload):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        die("spawn record is not writable (%s): %s" % (path, exc))


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


def limit_signal(parsed, result_text, stderr_text, subtype, failed):
    """Where a lane hit an account or usage limit (design: the account plan, C2 N12), the
    evidence as one phrase; None otherwise. A budget cap (`error_max_budget_usd`) is never a
    limit."""
    if parsed.get("synthetic_stop"):
        return "transcript: last assistant record has model %s with zero usage" % parsed.get("last_model")
    sub = (subtype or "").lower()
    if "limit" in sub and "budget" not in sub:
        return "subtype %s" % subtype
    low = (result_text or "").lower()
    if "limit" in low and ("reset" in low or "usage" in low):
        if failed or sub not in ("", "success") or len(low.split()) <= LIMIT_TEXT_WORDS:
            return "result text names a limit"
    low = (stderr_text or "").lower()
    if failed and "limit" in low and ("reset" in low or "usage" in low):
        return "stderr names a limit"
    return None


def classify(killed, stall, parsed, result, subtype, returncode, parse_error, stderr):
    """The close line's exit_class and, for a limit, the evidence."""
    if stall:
        return "stall", None
    if killed:
        return "deadline", None
    failed = bool(result.get("is_error")) or returncode != 0
    signal_text = limit_signal(parsed, result.get("result") or "", stderr, subtype, failed)
    if signal_text:
        return "limit", signal_text
    if parsed["refusal"]:
        return "refusal", None
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
        except OSError:
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
    except OSError:
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
        return process.communicate()


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


def resolve_silence(args, record_path):
    """The stall threshold and where it came from; 0 disables the watch."""
    if args.silence_s is not None and args.silence_s < 0:
        die("--silence-s must be 0 (watch disabled) or a positive number of seconds")
    if args.silence_s == 0:
        return 0, "--silence-s 0 (watch disabled)"
    base = DEFAULT_SILENCE_S if args.silence_s is None else args.silence_s
    source = "default" if args.silence_s is None else "--silence-s"
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
SWAP_TIMEOUT_S = 180                # bound with headroom: a detached Codex spawn returns in seconds (set by judgement)
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
    """Move a probe-confirmed fallen-back task's remaining work to Astra (rule 3, owner ruling
    2026-09-22): a derived brief (the swap notice, then the CURRENT pass's brief verbatim), one
    detached `codex-lane.py spawn` of `<lane>-astra` (a name the record has not opened) with the
    same class, write scope, effort, regime and record, confirmed by the successor's own lane-spawned
    line (its pid; a lane-open alone proves nothing). Returns (summary, record line): the caller appends the close line first, then the
    `lane-swapped` line, so the close carries the outcome. Never raises: a brief that cannot be
    written spawns nothing; a spawn that fails, returns without opening, or cannot run is
    recorded with its error and the warning names the command to run by hand. The Astra lane
    closes through codex-lane.py, which has no swap of its own, so a swap never loops."""
    open_line = ctx.get("open_line") or {}
    run, lane, cls = ctx["run"], ctx["lane"], ctx["cls"]
    fallback = close_line.get("fallback") or {}
    ids = ",".join(fallback.get("non_helper") or []) or "?"
    expected = fallback.get("expected") or "one id"
    to_lane = unused_name(record_lane_ids(record_path), "%s-astra" % lane)
    writes = [w for w in (open_line.get("writes") or []) if isinstance(w, str) and w]
    store = os.path.join(store_root(), "spawn-records")     # the run store, never beside a custom record path
    out = {"to": to_lane, "harness": "codex", "ok": False, "brief": None, "command": None, "error": None,
           "stderr_tail": None}
    line = {"ts": None, "run": run, "lane": lane, "event": "lane-swapped", "to": to_lane, "harness": "codex",
            "ok": False, "ids": ids, "expected": expected, "brief": None, "writes": writes,
            "effort": ctx.get("effort") or "xhigh", "command": None, "stdout_tail": None,
            "stderr_tail": None, "error": None, "wrapper_pid": os.getpid()}

    def finish():
        line.update({"ts": now(), "ok": out["ok"], "brief": out["brief"], "command": out["command"],
                     "error": out["error"], "stderr_tail": out["stderr_tail"]})
        return out, line

    src = ctx.get("brief_current") or open_line.get("brief_copy") or open_line.get("brief")
    if not (isinstance(src, str) and os.path.isfile(src)):
        out["error"] = "the current brief is not on disk (%r)" % (src,)
        return finish()
    try:
        with open(src, encoding="utf-8", errors="replace") as handle:
            original = handle.read()
    except OSError as exc:
        out["error"] = "current brief unreadable: %s" % exc
        return finish()
    try:
        os.makedirs(store, exist_ok=True)
        names = set(os.listdir(store))
    except OSError as exc:
        out["error"] = "run store unreadable: %s" % exc
        return finish()
    stems = set(n[:-3] for n in names if n.endswith(".md"))     # compared without the suffix (verifier review, claim 4)
    brief = os.path.join(store, unused_name(stems, "%s-brief-%s-astra" % (run, lane)) + ".md")
    notice = ("SWAP NOTICE (lane.py, owner ruling 2026-09-22): this lane continues lane %s of run %s, whose "
              "Claude-side result named %s where %s was expected — a transparent safeguard fallback confirmed "
              "by a live probe of the alias. Its work so far sits under %s; continue from what is on disk, do "
              "not redo what is complete, and if any part of the task reads as cyber or biology work, report "
              "that in your findings rather than proceed. The brief of the pass that fell back follows, "
              "verbatim.\n\n" % (lane, run, ids, expected, ", ".join(writes) or "no write directory"))
    try:
        write_atomic(brief, notice + original)      # the wrapper's one write path (temp file, then rename)
        out["brief"] = brief
    except OSError as exc:
        out["error"] = "derived brief not written: %s" % exc
        return finish()                             # nothing is spawned on a brief that is not there
    codex = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codex-lane.py")
    effort = line["effort"]                         # effort carries across the swap (owner ruling 2026-09-14)
    argv = ["--run", run, "--lane", to_lane, "--class", cls, "--brief", brief, "--record", record_path,
            "--reason", "(a) fallback swap: lane %s fell back to %s; the task's remaining work moves to Astra "
                        "(owner ruling 2026-09-22)" % (lane, ids),
            "--choice-reason", "gpt-6-astra %s: the Claude lane's result named %s where %s was expected; "
                               "effort carried across the swap" % (effort, ids, expected),
            "--effort", effort, "--delegation", open_line.get("mode") or "single",
            "--delegation-src", open_line.get("mode_src") or "head", "--detach", "--no-wait"]
    if writes:
        argv += ["--cwd", writes[0]]
        for w in writes:
            argv += ["--write", w]
    else:
        argv += ["--cwd", vault_root()]
    stub = os.environ.get(SWAP_CMD_ENV)
    try:
        prefix = shlex.split(stub) if stub else [sys.executable, codex, "spawn"]
    except ValueError as exc:
        out["error"] = "%s is not a shell command: %s" % (SWAP_CMD_ENV, exc)
        return finish()
    cmd = prefix + argv
    out["command"] = " ".join(shlex.quote(part) for part in cmd)
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=SWAP_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        out["error"] = "codex-lane.py spawn did not run: %s" % exc
        return finish()
    line["stdout_tail"] = (done.stdout or "").strip()[-300:]
    out["stderr_tail"] = (done.stderr or "").strip()[-300:] or None
    if done.returncode != 0:
        out["error"] = "codex-lane.py spawn exit %d: %s" % (done.returncode, (done.stderr or done.stdout).strip()[-300:])
        return finish()
    started, why = successor_started(record_path, to_lane, SWAP_OPEN_WAIT_S)
    if not started:
        out["error"] = "the spawn returned 0 but %s" % why
        return finish()
    out["ok"] = True
    return finish()


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
        if verdict == "fallback":
            line += (" · swapped to %s" % swap["to"]) if swap.get("ok") else (
                " · swap not done (%s)" % (swap.get("error") or "not attempted"))
    elif isinstance(fallback, dict) and fallback.get("detected") is None and fallback.get("reason"):
        # A check that could not run is said, never hidden (critic finding 3, 2026-09-22).
        line += " · fallback unread: %s" % fallback["reason"]
    return line


def emit(summary, close, report_words, fmt, open_line=None, text=None):
    """Print the summary, full-text pointer and complete report by default.
    An explicitly requested preview keeps the pointer to the complete report (D8)."""
    report_path = close.get("report")
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
                          "report_path": report_path, "report_text": shown,
                          "report_words": n_total, "report_shown": n_shown,
                          "report_cut": cut}, indent=1))
        return
    print(summary)
    if report_path:
        print("report: %s" % report_path)
    if close.get("parse_error"):
        print("note: %s" % close["parse_error"])
    if report_path:
        if shown:
            print(shown)
        print("(%d of %d words shown; full text: %s)" % (n_shown, n_total, report_path))


def wait_process(process, stdin_text, started, deadline, silence, poll, no_transcript_s,
                 locate, progress):
    """Feed the brief and wait, checking liveness every `poll` seconds while a silence
    threshold is set. Returns (stdout, stderr, killed for the deadline?, stall dict or None)."""
    first, stall, killed = True, None, False
    stdout = stderr = None
    while True:
        remaining = deadline - (time.time() - started)
        if remaining <= 0:
            killed = True
            stdout, stderr = kill_group(process)
            break
        timeout = min(poll, remaining) if (silence and poll and poll > 0) else remaining
        try:
            stdout, stderr = process.communicate(input=stdin_text if first else None,
                                                 timeout=timeout)
            break
        except subprocess.TimeoutExpired:
            first = False
        if silence and silence > 0:
            silent_s, reason, bound = silence_of(started, locate(), progress, silence,
                                                 no_transcript_s)
            if silent_s > bound:
                stall = {"silent_s": silent_s, "threshold_s": bound, "reason": reason}
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
    if ctx.get("pre_event"):
        # A resume records itself BEFORE its process starts, as a spawn records lane-open before its
        # own: a start that fails still follows its lane-resumed, and a watch finds the resume at
        # once; lane-respawned below then carries the process (register 2026-09-10 15:22).
        pre = {"ts": now(), "run": run, "lane": lane, "event": None, "session_id": ctx["session_id"],
               "wrapper_pid": os.getpid(), "class": ctx["cls"], "detached": ctx.get("detached", False),
               "mechanism": "lane.py headless, model %s, effort %s" % (ctx["model"], ctx["effort"])}
        pre.update(ctx["pre_event"])
        append_record(record_path, pre)
    started = time.time()
    try:
        process = subprocess.Popen(
            ctx["command"], cwd=ctx["home"], env=ctx["env"], start_new_session=True, text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        append_record(record_path, {"ts": now(), "run": run, "lane": lane,
                                    "event": "lane-closed", "session_id": ctx["session_id"],
                                    "class": ctx["cls"], "exit_class": "spawn-failed",
                                    "error": str(exc), "exit_code": 3,
                                    "soft_usd": ctx.get("soft_usd"),
                                    "soft_src": ctx.get("soft_src"), "soft_exceeded": None,
                                    "fallback": fallback_check(None, ctx["model"], load_model_facts()),
                                    "wrapper_pid": os.getpid()})
        sys.stderr.write("lane.py: could not start the lane process: %s\n" % exc)
        return 3

    spawned = {"ts": now(), "run": run, "lane": lane, "event": ctx["spawn_event"],
               "session_id": ctx["session_id"], "pid": process.pid, "wrapper_pid": os.getpid(),
               "class": ctx["cls"], "detached": ctx.get("detached", False),
               "mechanism": "lane.py headless, model %s, effort %s" % (ctx["model"], ctx["effort"])}
    spawned.update(ctx.get("spawn_extra") or {})
    append_record(record_path, spawned)

    def locate():
        return find_transcript(ctx["projects_root"], ctx["home"], ctx["session_id"])

    stdout, stderr, killed, stall = wait_process(
        process, ctx["stdin"], started, ctx["deadline"], ctx["silence"], ctx["poll"],
        ctx["no_transcript_s"], locate, ctx["progress"])
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
    parsed = parse_transcript(transcript)

    response_text = (result.get("result") or "").strip()
    resumed = (ctx.get("pre_event") or {}).get("event") == "lane-resumed"
    # A resumed pass must not borrow an earlier transcript message as its new report.
    report_text = response_text if resumed else response_text or parsed["last_text"]
    empty_response = resumed and not response_text
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
    exit_class, limit_text = classify(killed, stall, parsed, result, subtype,
                                      process.returncode, parse_error, stderr or "")
    if exit_class == "completed" and empty_response:
        exit_class = "empty"
    exit_code = EXIT_CODES.get(exit_class, 3)

    close_line = {
        "ts": now(), "run": run, "lane": lane, "event": "lane-closed",
        "session_id": result.get("session_id") or ctx["session_id"], "class": ctx["cls"],
        "exit_class": exit_class, "exit_code": exit_code, "process_exit": process.returncode,
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
        "limit_signal": limit_text, "silence_s": ctx["silence"],
        "stall": stall, "wrapper_pid": os.getpid(),
        "stderr_tail": (stderr or "").strip()[-400:] or None,
        "parse_error": parse_error,
        "fallback": fallback_check(result.get("modelUsage"), ctx["model"], ctx.setdefault("model_facts_pair", load_model_facts()))}
    ctx["model_facts"] = ctx["model_facts_pair"][0]
    close_line.update(ctx.get("close_extra") or {})
    memory = sync_memory_back(ctx["home"], ctx["cls"], vault_root())
    if memory is not None:
        close_line["memory_sync"] = memory     # a memory class's files synced back (register 2026-09-04)
    swapped_line = None
    fallback = close_line.get("fallback") or {}
    if fallback.get("detected"):
        fallback_decide(ctx, fallback)                # the live alias probe: confirmed, stale map, or unconfirmed
    if fallback.get("verdict") == "fallback":
        if ctx.get("no_swap"):
            close_line["swap"] = {"to": None, "ok": False, "error": "swap off (--no-swap)", "command": None}
        else:
            close_line["swap"], swapped_line = fallback_swap(ctx, close_line, record_path)
    append_record(record_path, close_line)
    if swapped_line:
        append_record(record_path, swapped_line)
    ids_text = ",".join(fallback.get("non_helper") or [])
    if fallback.get("verdict") == "stale-map":
        sys.stderr.write((STALE_LINE + "\n") % (run, lane, (fallback.get("probe") or {}).get("alias"),
                                                ",".join((fallback.get("probe") or {}).get("ids") or []),
                                                fallback.get("expected")))
    elif fallback.get("verdict") == "unconfirmed":
        sys.stderr.write((FALLBACK_LINE + "\n") % (
            run, lane, "unconfirmed: the alias probe failed, %s" % (fallback.get("probe") or {}).get("reason"),
            ids_text, fallback.get("expected") or "one id",
            "no swap was attempted; if the brief was not cyber- or biology-shaped, swap by hand with "
            "codex-lane.py spawn --class %s --brief <the pass's brief>" % ctx["cls"]))
    elif fallback.get("verdict") == "fallback":
        swap = close_line.get("swap") or {}
        where = ("swapped to lane %s on Astra%s" % (swap.get("to"), (" (%s)" % swap["stderr_tail"]) if swap.get("stderr_tail") else "")
                 if swap.get("ok") else
                 "swap NOT done: %s; run it by hand: %s" % (swap.get("error"), swap.get("command") or "codex-lane.py spawn … (see the lane-swapped line)"))
        sys.stderr.write((FALLBACK_LINE + "\n") % (run, lane, "confirmed by a live probe of the alias",
                                                   ids_text, fallback.get("expected") or "one id", where))

    summary = summary_of(run, lane, ctx["cls"], ctx["model"], ctx["effort"], close_line)
    emit(summary, close_line, ctx["report_words"], ctx["format"], ctx.get("open_line"),
         text=report_text)
    return exit_code


def run_beat(ctx):
    """The held-lane beat (handsoff.py hold, 2026-09-17): the resumed session asked for one word
    under the spawn's own configuration and cap. No report, no pass file, no lane-resumed or
    lane-closed line; the one record line is `hold-beat`, carrying the call's usage from the
    harness result, so the closing meter's rewrite causes can show whether the cache held. The
    call is bounded by BEAT_TIMEOUT_S and killed past it; a non-zero exit, a limit or a refusal
    is recorded with ok false and its exit class, and never retried here."""
    record_path, run, lane = ctx["record"], ctx["run"], ctx["lane"]
    started = time.time()
    by = os.environ.get(BEAT_BY_ENV) or "hand"
    base = {"run": run, "lane": lane, "event": "hold-beat", "harness": "claude",
            "session_id": ctx["session_id"], "class": ctx["cls"], "model": ctx["model"],
            "effort": ctx["effort"], "n": ctx["beat_n"], "by": by, "prompt": BEAT_PROMPT,
            "config_sha256": ctx["config_sha256"], "config_src": ctx["config_src"],
            "config_match": ctx["config_match"], "budget_usd": ctx["budget"],
            "hard_src": ctx["hard_src"], "last_call_age_s": ctx["age_s"],
            "last_call_src": ctx["age_src"], "wrapper_pid": os.getpid()}
    try:
        process = subprocess.Popen(
            ctx["command"], cwd=ctx["home"], env=ctx["env"], start_new_session=True, text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        line = dict(base, ts=now(), ok=False, exit_class="spawn-failed", exit_code=3,
                    process_exit=None, duration_s=0.0, usage=None, total_cost_usd=None,
                    error=str(exc))
        append_record(record_path, line)
        sys.stderr.write("lane.py: the beat could not start the lane process: %s\n" % exc)
        return 3
    timed_out = False
    try:
        stdout, stderr = process.communicate(input=BEAT_PROMPT + "\n", timeout=BEAT_TIMEOUT_S)
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
    parsed = parse_transcript(find_transcript(ctx["projects_root"], ctx["home"], ctx["session_id"]))
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
    append_record(record_path, line)
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
    if ctx["format"] == "json":
        print(json.dumps({"summary": summary, "beat": line}, indent=1))
    else:
        print(summary)
    return line["exit_code"]


def close_from_transcript(record_path, run, lane, opened, spawned, home, projects_root,
                          note, report_words, extra=None):
    """The close line `watch` writes for a lane whose wrapper is gone: everything the
    transcript shows, the cost marked as a transcript estimate (token totals, no dollar
    figure — the wrapper has no price table, and a wrong figure is worse than none)."""
    session_id = spawned.get("session_id") or opened.get("session_id")
    transcript = find_transcript(projects_root, home, session_id)
    parsed = parse_transcript(transcript)
    pass_n = 1 + sum(1 for event in load_record(record_path)
                     if event.get("lane") == lane and event.get("event") == "lane-resumed")
    report_path = pass_report_path(store_paths(run, lane)["report"], pass_n)
    report_text = parsed["last_text"] or "(no report text: closed by watch, wrapper gone)"
    try:
        write_atomic(report_path, report_text.rstrip() + "\n")
        report_written = report_path
    except OSError as exc:
        report_written = None
        sys.stderr.write("lane.py: report not written (%s)\n" % exc)
    shown, n_shown, n_total, cut = cut_words(report_text, report_words)
    started = parse_ts(spawned.get("ts"))
    ended = os.path.getmtime(transcript) if transcript and os.path.isfile(transcript) else None
    duration = round(ended - started, 1) if (started and ended and ended >= started) else None
    close_line = {
        "ts": now(), "run": run, "lane": lane, "event": "lane-closed",
        "session_id": session_id, "class": opened.get("class"),
        "exit_class": "watch-closed", "exit_code": 0, "process_exit": None,
        "duration_s": duration, "subtype": None, "is_error": None,
        "num_turns": parsed.get("calls"), "total_cost_usd": None,
        "cost_src": "transcript-estimate",
        "soft_usd": opened.get("soft_usd"), "soft_src": opened.get("soft_src"),
        "soft_exceeded": None,
        "usage": {"modelUsage": None, "peak_context": parsed["peak"],
                  "calls": parsed.get("calls", 0),
                  "first_call_context": parsed.get("first_call_context"),
                  "tokens": parsed.get("tokens")},
        "fallback": fallback_check(None, opened.get("model"), load_model_facts()),
        "effort_applied": sorted(set(parsed["efforts"])) or None,
        "cache_write_tier": parsed["tiers"] or None,
        "denials": "unknown", "fence_denials_transcript": parsed["fence_denials"],
        "permission_denials": [], "transcript": parsed["transcript"],
        "report": report_written, "report_words": n_total, "report_shown": n_shown,
        "report_cut": cut, "limit_signal": None, "note": note,
        "wrapper_pid": spawned.get("wrapper_pid"), "stderr_tail": None, "parse_error": None}
    close_line.update(extra or {})
    memory = sync_memory_back(home, opened.get("class"), vault_root())
    if memory is not None:
        close_line["memory_sync"] = memory     # a memory class's files synced back (register 2026-09-04)
    append_record(record_path, close_line)
    return close_line


def log_tail(path, lines=6):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-lines:])
    except OSError:
        return ""


def watch_lane(run, lane, record_path, home, projects_root, silence, poll, no_transcript_s,
               max_wait, report_words, fmt, session_id=None, worker=None, log_path=None,
               since=None):
    """The shared waiting loop of `watch` and the `--detach` foreground. Never kills a live
    wrapper's lane for silence unless `silence` is set; closes an orphaned lane (wrapper gone,
    no lane-closed) from its transcript once its process is gone or its recorded deadline
    passes. Returns the exit code."""
    began = time.time()
    unwatched = False
    stalled = None
    killed_at = None
    while True:
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
                if lane_alive:
                    deadline_at = started + float(opened.get("deadline_s") or DEFAULT_DEADLINE_S)
                    reason = None
                    if time.time() > deadline_at:
                        reason = "deadline"
                    elif silence and silence > 0:
                        silent_s, label, bound = silence_of(started, transcript, progress,
                                                            silence, no_transcript_s)
                        if silent_s > bound and label == "silent":
                            reason = "stall"
                            stalled = stall_event(run, lane, spawned.get("session_id"), silent_s,
                                                  bound, label, "watch")
                            append_record(record_path, stalled)
                    if reason is None:
                        if max_wait and time.time() - began > max_wait:
                            print("still-running: lane %s/%s (wrapper gone, lane pid %s alive)"
                                  % (run, lane, lane_pid))
                            return EXIT_STILL_RUNNING
                        time.sleep(poll)
                        continue
                    kill_pid_group(lane_pid)
                    note = "closed by watch (wrapper gone; lane killed: %s)" % reason
                else:
                    note = "closed by watch (wrapper gone)"
                close_from_transcript(record_path, run, lane, opened, spawned, home,
                                      projects_root, note, report_words)
                continue
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
                        kill_pid_group(lane_pid)
                        killed_at = time.time()
        elif worker is None:
            die("lane %s/%s is unknown in %s (no lane-open and lane-spawned)"
                % (run, lane, record_path))
        if max_wait and time.time() - began > max_wait:
            print("still-running: lane %s/%s after %.0f s" % (run, lane, time.time() - began))
            return EXIT_STILL_RUNNING
        time.sleep(poll if spawned else min(poll, 1.0))


# ------------------------------------------------------------------------ spawn -------------

def detach_spawn(args):
    """The double fork for a spawn: the session id is chosen here and handed to the worker, which
    runs the whole spawn and writes every record line."""
    session_id = args.session_id or str(uuid.uuid4())
    extra = [] if args.session_id else ["--session-id", session_id]
    home = os.path.realpath(os.path.expanduser(args.home or default_home()))
    projects_root = projects_root_for(args.projects_root, args.config_dir)
    return detach_worker(args, session_id, extra, home, projects_root)


def detach_worker(args, session_id, extra, home, projects_root, since=None):
    """The double fork shared by spawn and resume: a worker (its own session) re-runs this command
    and writes every record line; the foreground watches it, or with --no-wait returns at once.

    The caller opens the run's console first, in its own context, and the worker gets `--viewer
    none`, appended so it wins over any --viewer the command carried.
    (register 2026-09-09 11:21, update
    2026-09-12). `since`, for a resume, is the record's
    event count before the detach, so the foreground waits for a lane-resumed after it and never
    takes the previous call's close for this one's."""
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
        print("detached pid %d session %s" % (worker.pid, session_id))
        return 0
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


def cmd_spawn(args):
    require_lane_id(args.lane)
    require_estimate(args.expect_usd)
    paths = store_paths(args.run, args.lane, args.record)
    require_new_lane_id(args.lane, paths["record"])
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
        caller_checks(args)      # the doubled-root refusal and the two warnings, in the caller's terminal
    if args.detach and not args.dry_run:
        return detach_spawn(args)
    if args.no_wait:
        die("--no-wait goes with --detach")
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
    controls_checked = check_controls(parse_controls(brief), vault)

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

    # A row's per-call slot is filled by the call. `--write` fills a write slot (and the
    # class's own memory directory fills one by itself, when the home holds it); `--grant`
    # fills a read slot, and so does `--write`, since a path a lane may write is necessarily
    # one it may read. A slot the call left empty is a premise failure that names the flag
    # which fills it.
    own_memory = memory_dir(home, cls)
    for slot in write_slots:
        if call_writes:
            continue
        if own_memory and not args.grants_only:
            # Under --grants-only the call is the lane's whole scope, so the class's own memory
            # directory is not added by itself and the slot takes a --write like any other.
            add_entry(writes, dir_entry(own_memory))
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

    tools = ([t.strip() for t in args.tools.split(",") if t.strip()] if args.tools
             else list(field(row, cls, "tools")))
    if not tools:
        die("class `%s` resolves to an empty tool list" % cls)

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

    definition_path, definition_sha, agent = thin_definition(
        vault, cls, tools, "thin %s lane" % cls)
    agents_json = json.dumps({cls: agent})

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
                             strip_frontmatter(read_text(core_path, "the lane core"))))
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
    silence, silence_src = resolve_silence(args, record_path)
    # The estimate sets both lines; its sanity note was printed in the caller before detach.
    hard_usd, hard_src = cost_caps(args.budget_usd, args.expect_usd, args.run, record_path)
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
    settings, settings_allow = settings_for(home, writes)
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
        "ts": now(), "run": args.run, "lane": args.lane, "event": "lane-open",
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
        "row_literals_dropped": dropped,
        "controls_checked": controls_checked,
        "settings": paths["settings"], "settings_allow": settings_allow,
        "config_dir": config_dir, "projects_root": projects_root,
        "skills": skills, "mcp": ([args.mcp_config] if args.mcp_config else []),
        "appended": appended_names, "appended_bytes": appended_bytes,
        "appended_file": paths["appended"] if appended_text else None,
        "cache_tier_expected": row.get("cache", "unstated"),
        "session_id": session_id, "budget_usd": budget, "breadth": breadth,
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
    if throttle_note:
        open_line["throttle_note"] = throttle_note

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

    ctx = {"run": args.run, "lane": args.lane, "cls": cls, "model": model, "effort": effort,
           "command": command, "env": env, "home": home,
           "stdin": None if args.prompt_arg else brief, "deadline": deadline,
           "silence": silence, "poll": args.poll_s, "no_transcript_s": args.no_transcript_s,
           "record": record_path, "report_path": paths["report"],
           "projects_root": projects_root, "session_id": session_id, "progress": progress,
           "report_words": args.report_words, "format": args.format,
           "spawn_event": "lane-spawned", "detached": bool(args.as_worker), "viewer": args.viewer,
           "open_line": open_line, "soft_usd": soft_usd, "soft_src": soft_src,
           "no_swap": bool(getattr(args, "no_swap", False)), "brief_current": brief_abs}
    return run_lane(ctx)


# ----------------------------------------------------------------------- watch --------------

def cmd_watch(args):
    paths = store_paths(args.run, args.lane, args.record)
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
        # A resume issued with --detach --no-wait writes its lane-resumed a moment after it returns,
        # and a watch issued in that moment still sees the previous call's close: wait up to
        # --appear-s for a newer lane-resumed before calling the lane closed.
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
    """Stop a running lane deliberately and close its record, so no lane is ever killed by hand.

    This deliberate path signals the recorded processes, then writes the close the wrapper did not
    write, with `exit_class: killed`, the `--reason` the caller gave and the cost estimated
    from the transcript exactly as the `watch-closed` path estimates it (token totals, no
    dollar figure: the wrapper holds no price table).

    The order matters. The wrapper is signalled first, so it cannot race this command to write
    a close of its own, then the lane process, which the wrapper started in a session of its
    own and which a signal to the wrapper therefore never reaches. The wrapper is signalled as
    ONE PROCESS and the lane by process GROUP: a wrapper shares its group with whoever started
    it, so a group signal there would kill the caller too. The lane is a session leader and
    its group holds nothing but the lane and its children.

    The bound: each of the two is SIGTERM, then up to KILL_GRACE_S (5 s) of waiting, then
    SIGKILL — `kill_pid_group`, the same sequence the stall path uses — so the close is written
    within 2 x KILL_GRACE_S = 10 s of the call in the worst case, and at once where both
    processes go on the SIGTERM. The headroom inside the 5 s is the kill grace's own, quoted
    from its derivation above: long enough for the CLI to flush its transcript, short enough
    that a hung lane does not hold the head. There is no second bound to set here: this command
    waits for nothing else.

    Premises (each refuses with exit 2 and writes NOTHING): no record; a lane with no
    `lane-open` and no spawn in it; a lane whose latest spawn already carries a `lane-closed`.
    A recorded pid that is already gone is NOT a premise failure — the close is exactly what is
    missing then — so the close is written and one line on stdout says the pid had gone. Where a
    record carries two spawns of one lane name, the latest spawn is the lane (`lane_state`), and
    a close belonging to the earlier spawn does not stand in the way of killing the later one.

    Exit 0 once the close is written; 2 on any premise failure."""
    paths = store_paths(args.run, args.lane, args.record)
    if not os.path.isfile(paths["record"]):
        die("no spawn record at %s" % paths["record"])
    opened, spawned, closed = lane_state(load_record(paths["record"]), args.lane)
    if not opened and not spawned:
        die("lane %s/%s is unknown in %s (no lane-open and no spawn) — nothing was signalled "
            "and nothing was written" % (args.run, args.lane, paths["record"]))
    if not spawned:
        die("lane %s/%s has a lane-open but never spawned in %s — there is no process to kill "
            "and no close to write" % (args.run, args.lane, paths["record"]))
    if closed:
        die("lane %s/%s is already closed (%s at %s) — a second close would double-count it; "
            "nothing was signalled and nothing was written"
            % (args.run, args.lane, closed.get("exit_class"), closed.get("ts")))
    opened = opened or {}
    wrapper_pid = spawned.get("wrapper_pid")
    lane_pid = spawned.get("pid")
    gone = []
    for name, pid in (("wrapper", wrapper_pid), ("lane", lane_pid)):
        if not pid:
            gone.append("%s (no pid recorded)" % name)
        elif pid_alive(pid) is False:
            gone.append("%s pid %s" % (name, pid))
    if wrapper_pid:
        kill_pid_group(wrapper_pid, group=False)
    if lane_pid and lane_pid != wrapper_pid:
        kill_pid_group(lane_pid)
    home = os.path.realpath(os.path.expanduser(args.home or opened.get("cwd") or default_home()))
    projects_root = projects_root_for(args.projects_root or opened.get("projects_root"),
                                      opened.get("config_dir"))
    note = "killed by lane.py kill: %s" % args.reason
    close_line = close_from_transcript(
        paths["record"], args.run, args.lane, opened, spawned, home, projects_root, note,
        args.report_words,
        extra={"exit_class": "killed", "exit_code": EXIT_CODES.get("killed", 3),
               "reason": args.reason, "killed_by": "lane.py kill",
               "killed_pids": {"wrapper": wrapper_pid, "lane": lane_pid},
               "kill_grace_s": KILL_GRACE_S})
    if gone:
        print("kill: already gone before the signal: %s; the close is written anyway (that "
              "missing close is the defect this command exists for)" % ", ".join(gone))
    print(summary_of(args.run, args.lane, close_line.get("class") or opened.get("class"),
                     opened.get("model"), opened.get("effort"), close_line))
    print("kill: lane %s/%s closed as killed (%s); record %s"
          % (args.run, args.lane, args.reason, paths["record"]))
    return 0


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
    if cls == "refusal":
        print("advise: family-fallback · %s · a refusal is never resumed (CLAUDE.md section 11)" % inputs)
        return 0
    if cls in ("deadline", "stall", "error", "spawn-failed", "killed", "max-turns"):
        print("advise: restart · %s · a %s close restarts from the partial output, never a resume "
              "(the skill's rule: re-spawned once with a changed brief and the failure note)" % (inputs, cls))
        return 0
    if cls == "budget":
        print("advise: restart · %s · a budget close is re-spawned with a changed brief, or resumed only "
              "through `resume` with a raised --budget-usd inside its window" % inputs)
        return 0
    if cls == "completed":
        print("advise: restart · %s · a completed lane is re-spawned with a follow-up brief, or resumed through "
              "`resume` inside its window for a follow-up only" % inputs)
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
              "a limit close resumes (D29)" % inputs)
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


def cmd_resume(args):
    if args.no_wait and not args.detach:
        die("--no-wait goes with --detach")
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
    if age > RESUME_WINDOW_S and not after_limit:
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
        brief, controls_checked = None, None    # the beat's prompt is BEAT_PROMPT, below
    else:
        if not os.path.isfile(args.brief):
            die("brief file not found: %s" % args.brief)
        brief = read_text(args.brief, "the follow-up brief")
        if not brief.strip():
            die("brief file is empty: %s" % args.brief)
        refuse_doubled_root(args.brief, brief, vault)
        controls_checked = check_controls(parse_controls(brief), vault)

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
    if not find_transcript(projects_root, home, session_id):
        die("lane %s/%s: no transcript for session %s under %s — the session cannot be re-entered; "
            "re-spawn the lane with the finding in the brief instead"
            % (args.run, args.lane, session_id, projects_root))
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
            silence, silence_src = DEFAULT_SILENCE_S, "default"
    else:
        silence, silence_src = resolve_silence(args, paths["record"])
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
        # Every premise above ran in the caller's terminal; the worker repeats them and writes
        # every record line, lane-resumed first (register 2026-09-10 15:22).
        return detach_worker(args, session_id, [], home, projects_root,
                             since=len(load_record(paths["record"])))

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
                           "controls_checked": controls_checked, "budget_usd": budget,
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
           "soft_usd": soft_usd, "soft_src": soft_src}
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
    script). It writes at the file's own indent and never sorts its keys, so the diff of a fold
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
        routing_path = args.routing or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    "routing.json")
        raw = read_text(routing_path, "the routing table")
        data = load_routing(routing_path)
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

def add_wait_flags(parser):
    parser.add_argument("--silence-s", type=float, default=None,
                        help="stall threshold in seconds (default %d; 0 disables the watch)"
                             % DEFAULT_SILENCE_S)
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
    spawn.add_argument("--plant", default="")
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
                       help="run the lane in a worker that survives the caller; the foreground "
                            "watches it")
    spawn.add_argument("--no-wait", action="store_true",
                       help="with --detach: print `detached pid N session S` and return at once")
    spawn.add_argument("--dry-run", action="store_true")
    spawn.add_argument("--as-worker", action="store_true", help=argparse.SUPPRESS)
    add_wait_flags(spawn)
    spawn.set_defaults(func=cmd_spawn)

    watch = sub.add_parser("watch", help="wait on a running lane; close it if its wrapper is gone")
    watch.add_argument("--run", required=True)
    watch.add_argument("--lane", required=True)
    watch.add_argument("--max-wait-s", type=float, default=WATCH_MAX_WAIT_S,
                       help="return `still-running` (exit %d) after this many seconds "
                            "(default %d; 0 waits without bound)"
                            % (EXIT_STILL_RUNNING, WATCH_MAX_WAIT_S))
    watch.add_argument("--appear-s", type=float, default=WATCH_APPEAR_S,
                       help="seconds to wait for a just-detached lane's record lines before "
                            "calling it unknown (default %d)" % WATCH_APPEAR_S)
    add_wait_flags(watch)
    watch.set_defaults(func=cmd_watch)

    kill = sub.add_parser("kill", help="stop a running lane and write its lane-closed with "
                                       "exit_class killed (never kill a lane by hand)")
    kill.add_argument("--run", required=True)
    kill.add_argument("--lane", required=True)
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

    resume = sub.add_parser("resume", help="re-enter a finished lane's session with a follow-up "
                                           "brief (D29: after a `limit` close the cache window is "
                                           "waived and `lane-resumed` records after_limit and "
                                           "age_s; after a `budget` close only a raised "
                                           "--budget-usd resumes the lane; existing per-pass report or brief paths refuse before writes)")
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
                        help="run the resumed call in a worker that survives the caller; the "
                             "foreground watches it and returns on the resumed call's close")
    resume.add_argument("--no-wait", action="store_true",
                        help="with --detach: print `detached pid N session S` and return at once")
    resume.add_argument("--as-worker", action="store_true", help=argparse.SUPPRESS)
    add_wait_flags(resume)
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
                              "routing table --routing names, at the file's own indent and in "
                              "its own key order, so the diff is the fields that changed; "
                              "nothing drifted writes nothing. This is the only path in "
                              "`cost-figures` that writes at all")
    figures.add_argument("--format", choices=("text", "json"), default="text")
    figures.set_defaults(func=cmd_cost_figures)
    return parser


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
