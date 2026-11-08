#!/usr/bin/env python3
"""codex-lane.py — spawn a headless Codex lane (GPT-6 Astra by default) that writes the same
run-record lines as a Claude lane, so the console, the hand-off, the supervisor and the meter
read it unchanged. An installed, authenticated Codex CLI is required.

    codex-lane.py spawn  --run ID --lane ID --class CLASS --brief FILE --cwd DIR --reason "(a) WHY" --choice-reason "WHY" [options]
    codex-lane.py resume --run ID --lane ID --brief FILE [--stage-from DIR] [--detach [--no-wait]] [options]
    codex-lane.py resume --run ID --lane ID --beat                (the held-lane beat: no brief, no report)
    codex-lane.py watch  --run ID --lane ID [--max-wait-s N] [--appear-s N] [--poll-s N]
    codex-lane.py wait   --run ID --lane ID [--appear-s N] [--poll-s N]
    codex-lane.py kill   --run ID --lane ID --reason WHY

What a spawn does, in order
---------------------------
1. Premise checks, before any record line: `--reason` opens with the instrument-rule letter
   (`lane.require_reason_letter`, shared with lane.py); `--choice-reason` is non-empty (no
   routing row anchors a Codex model, so every pick carries its reason); omitted effort takes the
   class's anchor in the routing table (`resolve_spawn_effort`); a `verifier` or `builder`
   spawn has a write scope (`--stage-writable` or `--write`) or says `--read-only` (register
   2026-09-23 18:0x: such a lane spawned read-only by default could do none of its work), and
   `--read-only` beside either is refused; the class has a definition in
   `.claude/agents/<class>.md`; the brief exists, is non-empty, its declarations parse
   (`lane.parse_declarations`, the one grammar lane.py documents: CONTROL+, READ+, RUBRIC+, WEB+)
   and no line carries a doubled root (`lane.refuse_doubled_root`: a root path embedding
   a second absolute path, or the vault root twice in one path; register 2026-09-09 19:03); its
   controls hit, its declared inputs exist with content (a zero-byte file refuses with its path)
   and a rubric's folders are in the reviewers' tree with content; declared web work (WEB+) needs
   `--search`, which the shell's `--network` does not stand in for; the cwd is a directory; with
   `--write`, the cwd lies inside one of the write
   directories (under Codex's `workspace-write` the cwd itself becomes writable, so a cwd outside
   the write set would widen the grant silently); the `codex` executable resolves and answers
   `--version`. Codex reads are unrestricted, so no read grant is tested: the brief's reading list
   is the grant. A control's file `<<REPORT>>` names this pass's report: recorded as
   `controls_pending` and checked at the close on the response this pass returned
   (`controls_deferred`: checked, failed or unverified, on the record and the summary line; a
   process that never starts closes them unverified, on the record and stderr).
2. The prompt: the class definition's body (Codex has no `--agents`), the lane core the Claude
   lanes carry, a Codex addendum naming what differs (the sandbox is the fence, the final message
   is the report, no progress file, no web search unless granted), then the brief. It goes to
   Codex on stdin (`codex exec -`) and a copy sits in the run store.
3. The `lane-open` line, then the process (`start_new_session`, so a kill reaches the whole
   group), then `lane-spawned` with the pid, then `lane-awake` for the keep-awake process started
   beside it (`lane.start_awake`: `/usr/bin/caffeinate -i -w <pid>`, `started` with its pid or
   `skipped` with the why, never a failed spawn; lane.py's "Keeping the host awake", owner
   decision of 2026-10-09; a beat starts one too, its state on its one `hold-beat` line, Beat
   below); a `lane-session` line when `thread.started` names
   the Codex thread; `lane-closed` at the end with the exit class, the token usage summed over
   turns, `total_cost_usd: null` and `cost_src: codex-plan` (usage sits on the ChatGPT plan,
   outside fable-share.py; a null cost is unpriced, never zero). Codex reports usage only on a
   completed turn, so the close accounts in four states (`usage_state`): `missing`, no completed
   turn reported a readable count, whether no turn completed or each that did carried no usage
   object or only unreadable values (`usage_complete` false; the close line reads `unknown`, never
   a zero); `zero`, a measured zero (complete, shown as 0); `complete`, the sum of every completed
   turn; `incomplete`, the readable counts summed while a completed turn carried no usage object
   or a malformed one, a turn failed, a turn started and never finished, the wrapper stopped the
   run, or the process ended non-zero after its last completed turn (`usage_complete` false, the
   reasons in `usage_incomplete`, the close line marking the figures an incomplete subtotal). A
   count joins the close's sum only as a non-negative integer, so a negative, a float (JSON's 1e309
   parses as infinity), a string or a bool can neither turn the subtotal negative, overflow it nor
   stand in for a measurement. The numeric subtotal is always kept. This accounting is the
   close's alone (`parse_close_events`): the held-lane beat reads its stream with the earlier
   parser (`parse_events`), whose sum, reading of a malformed value and ways of failing are
   unchanged, and keeps its own `usage_complete` rule, so the hold verdict reads every beat as it
   did before the close accounting (critic CR-ADD3 finding 1).
4. The watchdog: every POLL_S the wrapper checks the time since the last line arrived on stdout
   or stderr (`--json` streams one JSON object per line as items complete). Silence past
   `--silence-s` is a stall (SIGTERM the group, KILL_GRACE_S, SIGKILL); the deadline is the hard
   bound. Both are per call; reasoning at `max` is quiet for long stretches, so the silence
   default is generous (set by judgement, unmeasured: 1800 s).

Defaults: `--ignore-user-config` and every setting
passed explicitly; approval `never`; sandbox `read-only`, or `workspace-write` with `--write`
(every write directory beyond the cwd goes to `--add-dir`); web search disabled unless
`--search`; shell network off unless `--network`; memories off; the 872,000-token window and the
800,000 compaction limit; key-, secret- and token-named environment variables withheld from
spawned commands; `--skip-git-repo-check` only when the cwd is outside a git repository; never
`--ephemeral` (resume needs the session).

Exit classes and codes (aligned with lane.py's EXIT_CODES): `completed` 0 · `stall` 5 ·
`limit` 6 · everything else 3 (`empty`: a turn completed with no report text, the round's
"returns nothing" case; `failed`, `deadline`, `killed`, `spawn-failed`); a premise failure
exits 2 before any record line; `--detach --no-wait` that cannot confirm its worker's start
exits 4 (lane.py's EXIT_UNCONFIRMED, below).

A spawn onto a closed run (the record holds a `run-close` with no later `run-open` or
`run-resume`, whatever else follows it) prints one warning naming the close and proceeds
(`lane.closed_run_warning`; register 2026-09-03). A spawn or a resume with a brief passes the same
hold as lane.py's (`lane.decisions_spawn_check`): one the decisions channel holds exits 7, nothing
started.

Resume
------
`resume` continues the recorded Codex thread and re-declares what the spawn chose unless the resume
passes its own: the model, the effort and the `--config` overrides, read back from the lane's
`lane-open` (`model`, `effort`, `config_extra`, which every lane-open records since 2026-09-13; for
an older record the extras are the `config_overrides` entries after the default block, and a list
that does not start with that block carries none, with one line saying so). `lane-resumed` names
what it carried in `carried_from_open` (register 2026-09-13 04:11), so an `xhigh` lane spawned with
`--config features.multi_agent=true` is never resumed at the default `max` without it. The delegation
pair is carried the same way (register 2026-09-30 18:22): with neither `--delegation` nor
`--delegation-src`, a resume or a beat takes the lane-open's `mode` and `mode_src` together, when
they read `single`/`multi` and `head`/`owner`, and `lane-resumed` records the pair it used with
`mode_from` naming the lane-open; a complete explicit pair wins; one flag without its partner is
refused, as the resolver requires the pair; a recorded pair that is missing or unusable falls to
the Settings line, and with that unresolved the resume is refused before any write or process.
`--stage-from DIR` on a resume refreshes the lane's existing staged copy in place (register
2026-09-11 23:37): the cwd path the thread knows is kept, a file present in DIR replaces its copy,
a file only in the copy (the lane's own output) stays, and `lane-resumed` records the counts under
`stage.refreshed`. It is refused, naming the cwd, for a lane whose recorded cwd was never a staged
copy and for a `--cwd` naming another directory. With `--detach` the caller validates and its
worker copies. The refresh holds the stage lock while it copies (the staged copy, below).
Each resumed pass writes `<run>-report-<lane>-pass<n>.md`, n=2 for the first
resume and increasing per recorded resume. The first pass keeps its unsuffixed filename;
`lane-closed.report` and watch name the latest pass's report, preserving earlier reports.
The prompt uses the same per-pass suffix and `prompt_file` retains that pass's bytes. Spawn
reserves only numeric `-pass<n>` lane-id endings in any letter case, and refuses
case-equivalent lane ids in the run record. Historical `-r<n>` and `-resume-<n>` endings are legal. Spawn and resume check destination directory
listings case-insensitively before any write, stage refresh or detached worker, including
directories and dangling symlinks (critic fold, 2026-09-16). Only the lane's exactly spelt,
empty stage directory may be reused; dry runs remove the copy they checked before returning. Classification uses the current JSONL response alone; an existing output file
cannot turn an empty response into completion.

Beat
----
`resume --beat` (the held-lane beat, 2026-09-17) is the no-work resume handsoff.py's
supervisor issues for a held Codex lane: `codex exec … resume <thread> -` under the lane-open's
model, effort, sandbox, add-dirs and `--config` overrides — the same command line a resume
builds, less the `-o` report path, since a beat writes no report and no `-pass<n>` file — with the
fixed line lane.py's BEAT_PROMPT names on standard input in place of the composed prompt. It
writes no `lane-resumed` or `lane-closed` line; its one record line is `hold-beat`, carrying the
turn's usage (`turn.completed`: input, cached input, cache write, output and reasoning tokens),
the exit class and `config_sha256` — the resolved command line less `-o`, the `resume <id>` pair
and the prompt marker, recorded on `lane-open` and `lane-resumed` too. A beat whose hash differs
from the lane-open's is refused before any process starts; so is a beat with a brief, a stage
refresh or a worker, on a lane still running, on a close outside lane.py's BEAT_EXITS, on a lapsed
window or with no recorded thread. The beat's events append to the lane's events log, so its
mtime stays the last call. The Codex executable is the lane-open's recorded one unless --codex
names another. Beside the codex process the beat starts the keep-awake process
(`lane.start_awake`, the spawn's rules) and, its record contract being the one line, carries the
state on `hold-beat` as added fields (`lane.beat_awake_fields`: `awake`, `caffeinate_pid`,
`watched_pid`, and `note` when skipped), never a `lane-awake` line.
A beat, and a real resume, hold lane.py's session claim — an advisory lock (`fcntl.flock`,
LOCK_EX|LOCK_NB) on `<run>-<lane>-beat.pid.lock` beside the record — for the length of the call;
any other entry to that lane's session through either wrapper is refused while that lock is held,
and a resume claims it immediately before it writes its `lane-resumed` line, so two calls in
either order cannot both pass (critic F4, 2026-09-17; critic finding 2 of review, the lock
2026-09-18). The `hold-beat` line carries `usage_basis` and each turn's own figures
beside the sum: each `codex exec` invocation emits
one `turn.completed` whose usage is that invocation's own turn summed over its API calls, not a
running total over the thread, so a beat's single event is the beat's own call and its
`cached_input_tokens / input_tokens` is the beat's own cached share. What stays unmeasured is the
OpenAI prompt cache's retention at the beat's interval, which only a live Codex beat can give.

Watch
-----
`watch --run --lane` waits for the next close after the latest start or resume, never an old close,
bounded by `--max-wait-s` (below). It returns on a `lane-closed`
# References: register 2026-09-10.
that follows the latest `lane-open` or `lane-resumed` for the lane in record order, never on an
earlier close; prints the close's summary line and its whole report by default; and exits
with the close's exit code. A lane already closed when the watch starts waits up to `--appear-s`
for a newer open or resume (a resume whose `--detach --no-wait` returned unconfirmed, exit 4, can
write its lane-resumed after it returns; an acknowledged one wrote it before returning), then
prints that close and exits 2, as lane.py watch does.
`still-running` exits 8 after `--max-wait-s`; a lane whose recorded wrapper has gone with no close
after it exits 3 and names `kill` as the way to close the record. The watch reads the record and
writes nothing.

For a background wait, `wait` uses this same loop without the still-running time bound,
including the latest-pass, already-closed and orphan rules and exit codes. A foreground
check uses `watch`, whose default remains lane.py's 570 s bound (600 s shell cap less 30 s).

A second pass on a helper's work goes to a fresh helper with a compact hand-off: the earlier
report's path, the findings to fold, the held files and what must not change. Use `resume`
only for a long write cut short by a usage limit, whose work is on disk and checked, or for
the multi-expert panel's round 2. These are recommendations; the resume checks are unchanged.

Console: with `--detach` the caller opens the run's console before the worker starts, and the
worker runs under `--viewer none` (register 2026-09-09 11:21; the opener itself is handsoff.py's).

Detach: every premise of spawn and resume (`prepare`, the per-pass paths, the delegation pair) runs
in the caller before the worker starts, so a refusal exits 2 with no worker started. The caller
then waits, bounded by `--ack-wait-s` (lane.py's ACK_WAIT_S, 60 s, derived there), for the
worker's acknowledgement of THIS call: its own `lane-open` for a spawn or its own `lane-resumed`
for a resume, each matched on the worker's pid as `wrapper_pid` after the record's length at the
detach, never an older line (lane.await_ack, register 2026-09-29 16:57). Four outcomes:
acknowledged, `detached pid N (log L)` and exit 0; the worker exits first, its log tail and its
own non-zero code (else 3); the worker lives but no acknowledgement arrives in time, or the record
cannot be read, `detached pid N, unconfirmed after S s` and exit 4, the worker left running; a
refused argument exits 2 before any worker. Without `--no-wait` the same wait runs first; a worker
that exits before acknowledging returns as above, and otherwise the caller then waits for the worker
and exits with its code. The caller names its worker on stderr the moment it starts (`codex-lane.py:
worker pid N started (log L); …`), so a caller stopped before its own outcome line (lane.py's
fallback swap past its timeout) still says which process may yet start the lane.

Blind reviews: `--stage-from SRC [--stage-exclude PATTERN]...` copies SRC into
`<store>/<run>-cwd-<lane>/` without the excluded names (`.git` always) and makes the copy the
cwd, so a reviewer never has the other reviewers' reports or the head's verdict within reach of
its working tree (critic CR1, finding 3). Reads elsewhere on the disk stay technically possible
under Codex's sandbox and are recorded as `reads: unrestricted`.

The staged copy and its checks (registers 2026-09-22 21:55, 2026-09-25 04:3x and 2026-09-16 12:46;
review CR-B4L findings 1, 2 and 8; review CR-B4L2 findings 1 and 2). Every check that does not need
the copy runs first. Then one attempt makes the copy in a directory of its own, created exclusively
beside the stage path, and moves it to the stage path with one rename, which the kernel performs
only where that path is absent or an empty directory. A stage holding anything (another attempt's
copy, a file that appeared after the caller's guard) refuses with PROBE FAILED, exit 2, and stays
exactly as found. So does one the kernel will not replace (`chflags uchg`). Nothing an attempt did
not make is ever removed. The attempt owns its own directory from its creation, a partial or
interrupted copy included, and the copy at the stage path by its identity (device and inode). Any
refusal, interrupt or crash before the lane-open removes what it owns before exit, so a retry under
the same lane id is never stopped by a leftover; a copy that cannot be removed is named on a second
stderr line. The rename into place, each removal of a copy at the stage path and a resume's refresh
hold the stage's one lock (`fcntl.flock` on `.<run>-cwd-<lane>.lock` beside it, a file that exists
only while the lock is held or awaited), so none of them runs inside another: the identity check and
the deletion after it are one step that no publication can enter, and the deletion empties only the
directory it checked, by names relative to it. A lock held past STAGE_LOCK_WAIT_S (60 s, derived at
its definition) refuses, exit 2, with nothing at the stage path touched. Then the checks only the
finished, exclusion-filtered copy can answer run on it:
- a declaration written with `<<STAGED_COPY>>` (the copy's path, substituted in the brief the lane
  receives and counted on lane-open as `staged_copy_token`);
- a declared input or rubric inside SRC, read as lane.py resolves a declared path (a relative one
  against the vault). Its staged version is the one checked, recorded and delivered: the brief the
  lane receives names the copy, and `staged_declarations` on the record names those lines. A file
  the copy lacks, an excluded one among them, therefore refuses and is never checked or read
  through its original;
- a rubric's folders in the copy.
A token-derived path that leaves the copy through `..` or a symlink refuses; a token with no copy
to name refuses. A dry run checks the real copy and removes it; a detached caller checks its copy
and removes it before its worker starts, and the worker makes and checks its own. A resumed pass
resolves the token to its recorded copy, and a path inside any source that copy mirrors (the
lane-open's, each refresh a recorded resume made, this call's own) to its place in the copy, by the
latest of them that holds it. A resume that refreshes without copying (a dry run, a detached
caller) checks such a path as written, and its worker maps it.

The decisive error (register 2026-09-26 00:16). A stream retries before it fails, so a failed or
limit close leads with the LAST meaningful turn.failed message, else the last meaningful error
(the last that reads as a limit, for a limit), else a fallback saying the turn failed with no
text; an empty error object is counted, never written as "None". The close line's `error`, the
summary's `error:` and the saved report carry it — a report holding the lane's last message
starts with one wrapper line naming the failure, the lane's text whole below it — and `errors`
keeps the last five texts, beside `errors_total`.
"""

import argparse
import contextlib
import errno
import fcntl
import filecmp
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True   # importing lane.py must leave no __pycache__ in the skill home (its suite checks)
import lane  # noqa: E402  (the Claude wrapper: shared store, record and premise helpers)

HARNESS = "codex"
DEFAULT_MODEL = "gpt-6-astra"
DEFAULT_EFFORT = "max"
EFFORTS = ("low", "medium", "high", "xhigh", "max")   # Codex's ladder for Astra
KNOWN_MODELS = ("gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")   # the catalogue of 2026-09-08
CONTEXT_WINDOW = 872000          # the catalogue maximum for gpt-6-astra (models_cache.json, 2026-09-08)
COMPACT_LIMIT = 800000           # compact below the window, not at the 272K default
DEFAULT_DEADLINE_S = 14400       # four hours; set by judgement, unmeasured for a new workload; --deadline-s overrides it
DEFAULT_SILENCE_S = 1800         # set by judgement, unmeasured: reasoning at max is quiet for long stretches
POLL_S = 15
KILL_GRACE_S = 5
REPORT_WORDS = None             # The default report is complete; previews require an explicit request.
WATCH_POLL_S = 5                 # set by judgement, unmeasured: one record read per tick; five seconds bounds how late a close is reported
VERSION_TIMEOUT_S = 30           # `codex --version` answers in seconds; set by judgement (lane.py's ACK_WAIT_S is sized over this and GIT_TIMEOUT_S)
GIT_TIMEOUT_S = 20               # `git rev-parse` answers at once; set by judgement
USAGE_REQUIRED = ("input_tokens", "output_tokens")   # what a measured turn.completed usage object always carries; set by judgement from the CLI's event shape, unmeasured for other CLI versions
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens",
              "reasoning_output_tokens")             # the counts the close sums (parse_close_events); the beat's parse_events sums the same keys by its own earlier rule
EXIT_CODES = {"completed": 0, "stall": 5, "limit": 6}   # every other class exits 3; premise 2
LIMIT_RE = lane.CODEX_USAGE_STOP_RE  # Native closes and recovered outcomes use the same predicate.
DENIAL_RE = re.compile(r"operation not permitted|permission denied|not permitted by the sandbox|sandbox denied", re.I)
CORE_NAME = "lane-core.md"
# The configuration hash (the held-lane beat, 2026-09-17): the command line less the report path
# pair, the `resume <thread>` pair and the trailing prompt marker, so a spawn, its resumes and
# its beats hash alike when they run the model under one configuration.
CONFIG_DROP_PAIRS = ("-o", "resume")
TURN_USAGE_KEEP = 8             # per-turn usage figures kept on a record line (critic F7, 2026-09-17): a beat is one turn and a resume a handful, so eight entries hold every case seen while bounding the line; set by judgement, unmeasured
ERRORS_KEEP = 5                 # error texts kept on a close line: the LAST five, where the decisive one sits (register 2026-09-26 00:16); five as before, set by judgement, unmeasured
WRITE_CLASSES = ("verifier", "builder")   # classes whose work needs a write scope: a spawn gives one, or says --read-only (register 2026-09-23 18:0x)
# The stage lock (review CR-B4L2 finding 1): how long a call waits for another to finish putting a
# copy in place, removing one or refreshing one, before it refuses and touches nothing. Removing the
# largest staged copy in the build machine's run store (18,419 files in 6,019 folders) took 4.3 s
# there (measured 2026-10-11, two trials); 60 s is fourteen times that, room for a slower disk or a
# busy host, while a holder past it is taken as wedged rather than waited on for ever.
STAGE_LOCK_WAIT_S = 60
STAGE_LOCK_POLL_S = 0.1          # set by judgement, unmeasured: ten tries a second against a lock held for a rename or a removal

ADDENDUM = """CODEX LANE ADDENDUM (this lane runs under OpenAI Codex, not in a Claude lane home)
- Your working directory is {cwd}. The sandbox is the fence: {write_clause}
- Your brief's reading list is your read grant. Files outside it may be within the sandbox's technical reach; they are outside your grant, so do not open them.
- The `contract/` slices, the progress file `$LLM_WIKI_LANE_PROGRESS` and the fence denials named in LANE CORE do not exist in this lane; the rules your task needs are in your brief, and anything missing is a gap to report. Keep long commands in the foreground.
- Web search is {search_clause}. There is no browser, no MCP server and no memory store in this lane.
- Your REPORT is your final message: put the whole report there, in the shape the brief names, since the launcher writes your final message to the report file. Write files only where the brief grants a write directory and asks for them.
- Instruction files Codex loads from the workspace (AGENTS.md) describe the project. Where they conflict with this brief, the brief governs: the owner authorised this task and its outputs.
- Work headless: never stop to ask a question. Record an assumption you had to make in your report under GAPS and continue with the part that does not depend on it.
"""


# ------------------------------------------------------------------- premise helpers --------

def die(reason):
    sys.stderr.write("codex-lane.py: PROBE FAILED: %s\n" % reason)
    sys.exit(2)


def now():
    return lane.now()


LEGACY_RESUME_EFFORT = DEFAULT_EFFORT   # a resume whose record names no effort; never a spawn's default


def resolve_spawn_effort(args):
    """Explicit effort wins, with no routing read. Omitted, it is this class's anchor in the sibling
    routing.json (or --routing), read at each spawn: the effort default of the row's Codex half where
    it has one, else the row's own. A class the table does not anchor is refused, never guessed."""
    if args.effort is not None:
        args.effort_src = "explicit"
        return args.effort
    path = os.path.abspath(args.routing or os.path.join(HERE, "routing.json"))
    try:
        routing = lane.load_routing(path)      # one reader of the table for both wrappers
    except AttributeError:
        die("routing table %s is not an object, so omitted --effort has no anchor" % path)
    classes = routing.get("classes")
    if not isinstance(classes, dict):
        die("routing table %s has no classes object for omitted --effort" % path)
    if args.cls not in classes:
        die("unknown routing class %r in %s for omitted --effort" % (args.cls, path))
    row = classes[args.cls]
    harness = row.get("harness") if isinstance(row, dict) else None
    half = harness.get("codex") if isinstance(harness, dict) else None
    effort = half.get("effort") if isinstance(half, dict) else None
    if not isinstance(effort, dict) and isinstance(row, dict):
        effort = row.get("effort")
    anchor = effort.get("default") if isinstance(effort, dict) else None
    if not isinstance(anchor, str) or anchor not in EFFORTS:
        die("routing class %r in %s has a missing or unsupported effort anchor %r; expected one of %s"
            % (args.cls, path, anchor, ", ".join(EFFORTS)))
    args.routing = path
    args.effort_src = "routing class anchor"
    return anchor


def resolve_codex(explicit):
    """The executable and its version, recorded on lane-open so one runtime is named per run."""
    path = explicit or shutil.which("codex")
    if not path:
        die("no `codex` executable on PATH and no --codex given")
    path = os.path.realpath(os.path.expanduser(path))
    if not os.access(path, os.X_OK):
        die("codex executable is not runnable: %s" % path)
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True,
                             timeout=VERSION_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        die("`codex --version` failed: %s" % exc)
    version = (out.stdout or out.stderr or "").strip().splitlines()
    return path, (version[0] if version else "unknown")


def definition_of(vault, cls):
    path = os.path.join(vault, ".claude", "agents", "%s.md" % cls)
    if not os.path.isfile(path):
        die("no definition for class `%s` at %s" % (cls, lane.display_path(path, vault)))
    text = lane.read_text(path, "the class definition")
    return path, hashlib.sha256(text.encode("utf-8")).hexdigest(), lane.strip_frontmatter(text)


def core_text(vault, explicit):
    """The lane core the Claude lanes carry: the lane home's copy, else the template, its vault-local
    blocks out as lane.py does it, so a lane reads each sentence once."""
    if explicit:
        if not os.path.isfile(explicit):
            die("--append-core file not found: %s" % explicit)
        return explicit, lane.strip_vault_local(lane.read_text(explicit, "the lane core"), "the lane core")
    home = lane.default_home()
    for candidate in (os.path.join(home, CORE_NAME), lane.core_source(vault)):
        if os.path.isfile(candidate):
            return candidate, lane.strip_vault_local(lane.read_text(candidate, "the lane core"), "the lane core")
    return None, ""


def in_git_repo(cwd):
    git = shutil.which("git") or "/usr/bin/git"
    try:
        out = subprocess.run([git, "-C", cwd, "rev-parse", "--is-inside-work-tree"],
                             capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def remove_tree(path):
    """Remove a tree this process made, write permission restored on the way where a copied
    read-only directory would stop it. Raises OSError when something still cannot go."""
    def retry(func, target, *_exc):
        for node in (os.path.dirname(target), target):
            try:
                if os.path.isdir(node) and not os.path.islink(node):
                    os.chmod(node, os.stat(node).st_mode | stat.S_IRWXU)
            except OSError:
                pass
        func(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


class StageLockRefused(Exception):
    """The stage's lock was not taken (held past STAGE_LOCK_WAIT_S, or a lock that cannot be worked):
    what needed it was not done, and nothing at the stage path was touched."""


def stage_lock_path(dest):
    """The stage's lock file, beside it in the run store: `.<run>-cwd-<lane>.lock`. It exists only
    while a call holds the lock or waits for it (stage_lock), so a dry run, like any call, leaves the
    store as it found it."""
    parent, name = os.path.split(os.path.abspath(dest))
    return os.path.join(parent, ".%s.lock" % name)


@contextlib.contextmanager
def stage_lock(dest, doing):
    """Hold the stage's one exclusive lock while `doing` changes what the stage path holds (review
    CR-B4L2 finding 1): putting a copy in place, removing one, refreshing one. Each of those takes
    it, so none of them runs inside another, and an identity checked under the lock still holds
    when the deletion that follows it runs.

    The lock is `fcntl.flock` on stage_lock_path, which the kernel drops when its holder exits, so a
    crashed holder wedges nothing. The file goes when the lock does: its holder removes it while
    still holding the lock, as its last step. A call that takes the lock therefore checks that the
    file it locked is still the one at the path; a file its last holder has since removed is let go
    and the path opened afresh, so two calls never hold locks on two files at one path. The wait is
    bounded on every retry, the contended one and the one after a replaced file alike (review CR-B4L3
    finding 3: the replaced-file retry once looped without reading the clock): a lock not taken
    within STAGE_LOCK_WAIT_S, or one that cannot be worked at all (an errno other than contention,
    as lane.lock_contended reads it), raises StageLockRefused before anything at the stage path is
    touched. The holder's pid and task are written into the file, for a waiter's refusal to name."""
    lock = stage_lock_path(dest)
    unchanged = "so %s was not done and nothing at the stage path %s was touched" % (doing, dest)
    deadline = time.monotonic() + STAGE_LOCK_WAIT_S
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o644)   # never through a link
        except OSError as exc:
            raise StageLockRefused("the stage lock %s cannot be opened (%s), %s" % (lock, exc, unchanged))
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if not lane.lock_contended(exc):
                os.close(fd)
                raise StageLockRefused("the stage lock %s cannot be worked (%s), %s" % (lock, exc, unchanged))
            if time.monotonic() >= deadline:
                try:
                    holder = os.read(fd, 200).decode("utf-8", "replace").strip()
                except OSError:
                    holder = ""
                os.close(fd)
                raise StageLockRefused(
                    "another call has held the stage lock %s for over %s s (%s), %s; retry once it has "
                    "finished, or end it if it is wedged (the kernel then frees its lock)"
                    % (lock, STAGE_LOCK_WAIT_S, "holder: pid " + holder if holder
                       else "its holder has not named itself yet", unchanged))
            os.close(fd)
            time.sleep(STAGE_LOCK_POLL_S)
            continue
        try:
            held, there = os.fstat(fd), os.lstat(lock)
            current = (held.st_dev, held.st_ino) == (there.st_dev, there.st_ino)
        except FileNotFoundError:
            current = False
        except OSError as exc:
            os.close(fd)
            raise StageLockRefused("the stage lock %s cannot be checked (%s), %s" % (lock, exc, unchanged))
        if current:
            break
        os.close(fd)                    # a lock file its holder has removed: let go and start again
        if time.monotonic() >= deadline:
            raise StageLockRefused(
                "the stage lock %s was replaced by another call each time this call took it, for over "
                "%s s, %s; retry once the other calls have finished" % (lock, STAGE_LOCK_WAIT_S, unchanged))
    try:
        try:
            os.ftruncate(fd, 0)
            os.write(fd, ("%d, %s, since %s\n" % (os.getpid(), doing, now())).encode("utf-8"))
        except OSError:
            pass                        # the line only names the holder in a waiter's refusal
        yield lock
    finally:
        try:
            os.unlink(lock)             # still held: the file at the path is this call's own
        except OSError:
            pass
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def open_dir(name, ident, dir_fd=None):
    """A descriptor on the directory `name` (relative to `dir_fd` where one is given), opened without
    following a link, provided it carries `ident` (device, inode); None, with nothing changed, for one
    that does not. On the directory found to carry it, the owner's read, write and search are
    restored where a copied mode withholds them, so its entries can be listed and removed."""
    try:
        fd = os.open(name, DIR_FLAGS, dir_fd=dir_fd)
    except PermissionError:
        info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        if (info.st_dev, info.st_ino) != ident or not stat.S_ISDIR(info.st_mode):
            return None
        os.chmod(name, stat.S_IMODE(info.st_mode) | stat.S_IRWXU, dir_fd=dir_fd)
        fd = os.open(name, DIR_FLAGS, dir_fd=dir_fd)
    try:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != ident or not stat.S_ISDIR(info.st_mode):
            os.close(fd)
            return None
        if stat.S_IMODE(info.st_mode) & stat.S_IRWXU != stat.S_IRWXU:
            os.fchmod(fd, stat.S_IMODE(info.st_mode) | stat.S_IRWXU)
    except BaseException:
        os.close(fd)
        raise
    return fd


def remove_entries(fd):
    """Remove everything inside the directory open at `fd`, every step by a name relative to a
    directory already opened and checked, never by a path: what goes is what that directory holds,
    whatever a path to it names by now."""
    for name in os.listdir(fd):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            sub = open_dir(name, (info.st_dev, info.st_ino), fd)
            if sub is None:
                raise OSError(errno.EBUSY, "a directory changed while it was being removed", name)
            try:
                remove_entries(sub)
            finally:
                os.close(sub)
            os.rmdir(name, dir_fd=fd)
        else:
            os.unlink(name, dir_fd=fd)


class Stage(object):
    """One spawn attempt's ownership of its staged copy (register 2026-09-22 21:55; critic finding 1
    of the 2026-10-10 design review; review CR-B4L findings 1 and 8; review CR-B4L2 finding 1). The
    attempt copies into a directory of its own, made by exclusive creation beside the stage path, and
    puts the finished copy in place with one rename, which the kernel performs only where the stage
    path is absent or an EMPTY directory. So a stage that holds anything (another attempt's copy, a
    late file) refuses the rename and is never touched, and an empty one is replaced whole.
    Ownership is identity, not a flag: the device and inode of the directory the attempt made.

    `release` removes only what that identity still names: the attempt's own directory while the
    copy is under way, a partial or interrupted copy included, or the copy at the stage path
    afterwards. The rename into place, every removal of a copy at the stage path and a resume's
    refresh each run under the stage's one lock (stage_lock), so the identity check and the deletion
    that follows it are one step that no publication can enter: a populated copy another attempt
    puts in place after this attempt's check waits for the lock, and lands only once this attempt's
    copy has gone. The deletion is also bound to the directory checked: it empties the directory as
    opened and found to carry the identity, by names relative to it, so even a writer that ignores
    the lock and renames a directory onto the path cannot have its files removed. A lock not free
    within STAGE_LOCK_WAIT_S refuses the release, which removes nothing at the stage path and says
    so. The attempt's own directory, unpublished, is never a stage, and goes without the lock.

    A dry run releases after its checks ran on the real copy. A refusal or an interrupt releases
    before it exits. A detached caller releases its checked copy before its worker starts, and the
    worker makes and checks its own. A spawn that writes its lane-open hands the copy to the recorded
    lane."""

    def __init__(self, dest, consumed_empty=False):
        self.dest = dest
        self.consumed_empty = consumed_empty   # the copy replaced an empty stage directory found at the path
        self.attempt = None                    # the attempt's own directory while it copies
        self.ident = None                      # (device, inode) of that directory: the copy's identity
        self.owned = False                     # the copy stands at the stage path
        self.lock_refused = False              # the last release was refused for the stage lock

    def holds_copy(self):
        """Whether the stage path is still this attempt's copy (its identity), never another's."""
        if self.ident is None:
            return False
        try:
            info = os.lstat(self.dest)
        except OSError:
            return False
        return stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == self.ident

    def holds_attempt(self):
        """Whether the attempt's own directory still stands where it was made (not yet put in place)."""
        try:
            info = os.lstat(self.attempt)
        except FileNotFoundError:
            return False
        return stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == self.ident

    def release(self):
        """Remove what this attempt made; None, or the reason something stays in place (with
        `lock_refused` set where that reason is the stage lock). Its own directory, not yet put in
        place, goes whole, and nothing at the stage path is looked at. A copy at the stage path goes
        under the stage lock: the identity check, then the copy's contents, emptied through the
        directory that carries the identity, then the stage directory itself with `rmdir`, while the
        path still names it. A failure at that last step leaves an EMPTY stage, which the next
        attempt under the lane id reuses as the guard allows. An empty directory the copy replaced is
        left in its place, emptied, as it was found."""
        self.lock_refused = False
        try:
            if self.attempt is not None:
                # No identity yet means the directory was made but never read back, so never put in
                # place either: it is still the attempt's own.
                if self.ident is None or self.holds_attempt():
                    if os.path.lexists(self.attempt):
                        remove_tree(self.attempt)
                    self.attempt, self.owned, self.ident = None, False, None
                    return None                 # the copy never reached the stage path
                self.attempt = None
            if self.ident is not None:
                with stage_lock(self.dest, "removing this attempt's staged copy"):
                    if self.holds_copy():                   # the identity check, under the lock
                        fd = open_dir(self.dest, self.ident)  # None: the path names another directory now
                        ours = fd is not None
                        if ours:
                            try:
                                remove_entries(fd)          # bound to the directory checked
                            finally:
                                os.close(fd)
                        if ours and not self.consumed_empty and self.holds_copy():
                            try:
                                os.rmdir(self.dest)
                            except OSError as exc:
                                # Taken by a writer outside the lock since the check: the copy's
                                # own directory went with that rename, and what stands there now
                                # is not this attempt's to remove.
                                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST) or self.holds_copy():
                                    raise
            self.owned, self.ident = False, None
        except StageLockRefused as exc:
            self.lock_refused = True
            return str(exc)
        except OSError as exc:
            return "%s: %s" % (type(exc).__name__, exc)
        return None

    def left_empty(self):
        """Whether what a failed release left is an empty stage directory (reusable by a retry)."""
        try:
            return os.path.isdir(self.dest) and not os.path.islink(self.dest) and not os.listdir(self.dest)
        except OSError:
            return False


def leftover_text(stage, left):
    """What a failed release leaves, for the caller who must act on it."""
    if stage.lock_refused:
        return ("nothing at the stage path %s was removed (%s): it stays exactly as it was, so remove "
                "this attempt's copy there by hand once that call has finished, before a retry under "
                "this lane id" % (stage.dest, left))
    if stage.attempt is not None and os.path.lexists(stage.attempt):
        return ("the attempt's own copy %s could not be removed (%s): remove it by hand; it blocks "
                "no retry, since each attempt copies into a directory of its own" % (stage.attempt, left))
    if stage.left_empty():
        return ("the staged copy %s was emptied but its directory could not be removed (%s); the "
                "empty stage stays, and a retry under this lane id reuses it" % (stage.dest, left))
    return ("the staged copy %s could not be removed (%s): remove it by hand before a retry under "
            "this lane id" % (stage.dest, left))


def release_or_say(stage):
    """Release a stage on a refusal's way out, saying so on stderr if anything stays behind: the
    refusal already printed, so the leftover is the second thing the caller must know."""
    if stage is None:
        return
    left = stage.release()
    if left:
        sys.stderr.write("codex-lane.py: PROBE FAILED: and %s\n" % leftover_text(stage, left))


def stage_path(args):
    """Where a spawn's staged copy stands: `<store>/<run>-cwd-<lane>`."""
    return os.path.join(store_paths(args.run, args.lane, args.record)["store"],
                        "%s-cwd-%s" % (args.run, args.lane))


def stage_copy(args, stage=None):
    """A blind working copy: SRC minus the excluded names, under the run store, as the cwd. Returns
    the Stage that owns it: `stage` where the caller made one before the copy, so that its own
    handler can release whatever the attempt holds when it is stopped.

    The copy is made in a directory of the attempt's own, created exclusively beside the stage path
    (`.<run>-cwd-<lane>.attempt-*`), and moved to the stage path with one rename. That rename lands
    only where the path is absent or an EMPTY directory (review CR-B4L finding 1: an attempt that
    claimed the path before it existed could, losing a race, delete the winner's files). A stage
    that holds anything therefore refuses with PROBE FAILED, exit 2 and no record line, and stays
    exactly as found. That covers another attempt's copy and a file that appeared after the caller's
    require_absent_paths guard (register 2026-09-16 12:46). An empty stage is replaced. A directory
    the kernel will not replace (`chflags uchg`) refuses the same way, never with a traceback. A copy
    that fails part-way, or is interrupted, is removed before the refusal (finding 8); nothing at
    the stage path is touched by either. The rename takes the stage lock (stage_lock; review CR-B4L2
    finding 1), so it waits while another call removes or refreshes a copy there; a lock not free
    within STAGE_LOCK_WAIT_S refuses the same way, the stage path untouched and the attempt's own
    copy removed."""
    src = real_dir(args.stage_from, "--stage-from")
    paths = store_paths(args.run, args.lane, args.record)
    dest = stage_path(args)
    excludes = [".git"] + list(args.stage_exclude or [])
    real_dest = os.path.realpath(dest)
    if inside(real_dest, src) or inside(src, real_dest):
        die("--stage-from %s and the stage %s overlap: a copy would hold itself" % (src, dest))
    if os.path.lexists(dest) and (os.path.islink(dest) or not os.path.isdir(dest)):
        die("the stage path %s exists and is not a directory; nothing was removed or staged" % dest)
    if stage is None:
        stage = Stage(dest)
    stage.dest = dest
    try:
        os.makedirs(paths["store"], exist_ok=True)
        stage.attempt = tempfile.mkdtemp(prefix=".%s-cwd-%s.attempt-" % (args.run, args.lane),
                                         dir=paths["store"])
        info = os.lstat(stage.attempt)
        stage.ident = (info.st_dev, info.st_ino)
        shutil.copytree(src, stage.attempt, symlinks=True, ignore=shutil.ignore_patterns(*excludes),
                        dirs_exist_ok=True)
    except OSError as exc:
        left = stage.release()
        die("staging %s into %s failed: %s; %s" % (
            src, dest, exc, "the partial copy was removed" if left is None else leftover_text(stage, left)))
    except BaseException:
        stage.release()           # an interrupt mid-copy: the attempt's own directory goes first
        raise
    # The rename runs under the stage lock (review CR-B4L2 finding 1), so it never lands between
    # another attempt's identity check and the deletion that follows it.
    try:
        with stage_lock(dest, "putting a staged copy in place"):
            stage.consumed_empty = os.path.isdir(dest) and not os.path.islink(dest)
            os.rename(stage.attempt, dest)
    except StageLockRefused as exc:
        left = stage.release()
        die("%s; %s" % (exc, "the attempt's copy was removed" if left is None else leftover_text(stage, left)))
    except OSError as exc:
        found = os.path.isdir(dest) and not os.path.islink(dest)
        left = stage.release()
        what = "the attempt's copy was removed" if left is None else leftover_text(stage, left)
        if found:
            die("cannot remove the empty stage %s to put the copy in its place: %s — the stage is "
                "left exactly as found%s; %s" % (
                    dest, exc, " (it holds what another attempt or a late writer put there)"
                    if exc.errno in (errno.ENOTEMPTY, errno.EEXIST) else "", what))
        die("cannot put the copy in place at %s: %s; %s" % (dest, exc, what))
    except BaseException:
        stage.release()
        raise
    stage.attempt, stage.owned = None, True
    count = sum(len(files) for _, _, files in os.walk(dest))
    args.stage_report = {"staged_from": src, "stage_excludes": excludes, "stage_files": count,
                         "stage_dir": dest}
    return stage


def refresh_stage(args, opened, copy=True):
    """`resume --stage-from`: refresh the lane's existing staged copy in place (register 2026-09-11
    23:37), so a resume reads the source the head repaired rather than its original copy. The path the
    Codex thread knows is kept; a file present in the source replaces its copy; a file only in the
    copy (the lane's own output under --stage-writable) stays. Refused, naming the cwd, for a lane
    whose recorded cwd was never a staged copy and for a --cwd naming another directory; a type
    clash (a directory in the copy where the source has a file) refuses before anything is copied.
    `copy=False` counts without copying (a dry run, or a detached caller whose worker copies). A
    refresh that copies holds the stage lock throughout (stage_lock); a lock not free within
    STAGE_LOCK_WAIT_S refuses with nothing refreshed."""
    stage = opened.get("stage") if isinstance(opened.get("stage"), dict) else {}
    recorded_cwd, dest = opened.get("cwd"), stage.get("stage_dir")
    if not (isinstance(dest, str) and isinstance(recorded_cwd, str)
            and os.path.realpath(dest) == os.path.realpath(recorded_cwd)):
        die("resume --stage-from refreshes a staged copy, and lane %s/%s's recorded cwd %s is not "
            "one (the lane was spawned without --stage-from): copy the files into that cwd by "
            "hand, or re-spawn" % (args.run, args.lane, recorded_cwd))
    dest = os.path.realpath(dest)
    if args.cwd and os.path.realpath(os.path.expanduser(args.cwd)) != dest:
        die("resume --stage-from refreshes the lane's own staged copy %s; --cwd %s names another "
            "directory" % (dest, args.cwd))
    src = real_dir(args.stage_from, "--stage-from")
    if inside(src, dest) or inside(dest, src):
        die("--stage-from %s and the staged copy %s overlap: a refresh would copy a tree into "
            "itself" % (src, dest))
    excludes = [".git"]
    for name in list(stage.get("stage_excludes") or []) + list(args.stage_exclude or []):
        if isinstance(name, str) and name not in excludes:
            excludes.append(name)
    ignore = shutil.ignore_patterns(*excludes)
    plan, seen = [], set()
    counts = {"replaced": 0, "added": 0, "unchanged": 0, "kept_only_in_copy": 0}
    # A refresh that copies changes what the stage path holds, so it holds the stage lock from its
    # plan to its last file (review CR-B4L2 finding 1); one that only counts takes none.
    guard = (stage_lock(dest, "refreshing the staged copy from %s" % src) if copy
             else contextlib.nullcontext())
    try:
        with guard:
            for base, dirs, names in os.walk(src):
                skipped = ignore(base, dirs + names)
                linked = [d for d in dirs if os.path.islink(os.path.join(base, d))]
                dirs[:] = sorted(d for d in dirs if d not in skipped and d not in linked)
                for name in sorted(set(names) | set(linked)):
                    if name in skipped:
                        continue
                    source = os.path.join(base, name)
                    rel = os.path.relpath(source, src)
                    target = os.path.join(dest, rel)
                    seen.add(rel)
                    if os.path.islink(source):
                        same = os.path.islink(target) and os.readlink(target) == os.readlink(source)
                    else:
                        same = (os.path.isfile(target) and not os.path.islink(target)
                                and filecmp.cmp(source, target, shallow=False))
                    if same:
                        counts["unchanged"] += 1
                        continue
                    if os.path.isdir(target) and not os.path.islink(target):
                        die("the staged copy holds a directory at %s where %s has a file; nothing was "
                            "refreshed" % (target, source))
                    counts["replaced" if os.path.lexists(target) else "added"] += 1
                    plan.append((source, target, rel))
            if copy:
                for source, target, rel in plan:
                    try:
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        if os.path.lexists(target):
                            os.remove(target)
                        if os.path.islink(source):
                            os.symlink(os.readlink(source), target)
                        else:
                            shutil.copy2(source, target)
                    except OSError as exc:
                        die("refreshing %s from %s failed at %s: %s" % (dest, src, rel, exc))
            if os.path.isdir(dest):
                for base, dirs, names in os.walk(dest):
                    for name in names:
                        if os.path.relpath(os.path.join(base, name), dest) not in seen:
                            counts["kept_only_in_copy"] += 1
    except StageLockRefused as exc:
        die(str(exc))
    args.stage_report = {"staged_from": src, "stage_excludes": excludes, "stage_dir": dest,
                         "refreshed": dict(counts, copied=bool(copy))}
    return dest


def global_instructions_bytes():
    """Codex loads ~/.codex/AGENTS.override.md or ~/.codex/AGENTS.md whatever `--ignore-user-config`
    says; the size is recorded and a non-empty file is warned about (critic CR1, finding 3)."""
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    for name in ("AGENTS.override.md", "AGENTS.md"):
        path = os.path.join(home, name)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            if size:
                return path, size
    return None, 0


def real_dir(value, what):
    path = os.path.realpath(os.path.expanduser(value))
    if not os.path.isdir(path):
        die("%s is not a directory: %s" % (what, value))
    return path


def inside(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def toml_string(value):
    return '"%s"' % str(value).replace("\\", "\\\\").replace('"', '\\"')


def config_overrides(args, network):
    """The `-c key=value` list, every value in TOML form; recorded on lane-open as given."""
    pairs = [
        ("model_reasoning_effort", toml_string(args.effort)),
        ("web_search", toml_string("live" if args.search else "disabled")),
        ("features.memories", "false"),
        ("memories.use_memories", "false"),
        ("memories.generate_memories", "false"),
        ("features.multi_agent", "false"),     # on by default: a lane never spawns Codex subagents (critic CR1 F4)
        ("features.apps", "false"),            # on by default: no apps or connectors in a lane (critic CR1 F4)
        ("model_context_window", str(args.context_window)),
        ("model_auto_compact_token_limit", str(args.compact_limit)),
        ("shell_environment_policy.ignore_default_excludes", "false"),
    ]
    if network:
        pairs.append(("sandbox_workspace_write.network_access", "true"))
    for extra in args.config or []:
        if "=" not in extra:
            die("--config takes key=value, got %r" % extra)
        pairs.append(tuple(extra.split("=", 1)))
    return ["%s=%s" % (k, v) for k, v in pairs]


def recorded_config_extra(opened):
    """(extras, source) as the lane-open recorded them: its `config_extra`, else, for a record from
    before that field, the `config_overrides` entries after the default block this adapter writes
    first. ([], "none: <why>") when neither can be read, so the caller can say what it could not
    carry."""
    extra = opened.get("config_extra")
    if isinstance(extra, list) and all(isinstance(item, str) for item in extra):
        return list(extra), "lane-open config_extra"
    recorded = opened.get("config_overrides")
    if not isinstance(recorded, list) or not all(isinstance(item, str) for item in recorded):
        return [], "none: the lane-open records neither config_extra nor a config_overrides list"
    probe = argparse.Namespace(effort=opened.get("effort") or LEGACY_RESUME_EFFORT,
                               search=bool(opened.get("search")), context_window=CONTEXT_WINDOW,
                               compact_limit=COMPACT_LIMIT, config=None)
    keys = [pair.split("=", 1)[0] for pair in config_overrides(probe, bool(opened.get("network")))]
    if [pair.split("=", 1)[0] for pair in recorded[:len(keys)]] != keys:
        return [], "none: the lane-open's config_overrides do not start with the default block"
    return list(recorded[len(keys):]), "lane-open config_overrides after the default block"


def build_command(codex, args, cwd, sandbox, add_dirs, overrides, report_path, resume_id=None):
    """The argv array; never a shell string. Global flags before `exec`, exec flags after it
    and before `resume`, since `-C`, `-s` and `--add-dir` belong to `exec` alone; `resume <id>`
    takes the prompt marker last, as `codex exec resume --help` shows.
    """
    command = [codex, "-a", "never", "exec", "--ignore-user-config",
               "-C", cwd, "-s", sandbox, "-m", args.model]
    for override in overrides:
        command += ["-c", override]
    for path in add_dirs:
        command += ["--add-dir", path]
    if not in_git_repo(cwd):
        command.append("--skip-git-repo-check")
    if args.schema:
        command += ["--output-schema", os.path.abspath(args.schema)]
    command.append("--json")
    if report_path is not None:        # a beat writes no report: no -o
        command += ["-o", report_path]
    if resume_id:
        command += ["resume", resume_id, "-"]
    else:
        command.append("-")
    return command


# ----------------------------------------------------------------------- events ------------

def parse_events(lines):
    """The held-lane beat's reading of its JSONL events (run_beat): every line is parsed with
    json.loads; an unparseable one is counted, never grepped for meaning. This is the reading every
    close and beat used before the close accounting, kept as it was (fix plan addendum F7: the
    hold-beat path is unchanged; critic CR-ADD3 finding 1): what it sums, how it reads a malformed
    value and how it can fail are what handsoff.py's hold verdict has always read. The close reads
    its stream with parse_close_events."""
    out = {"records": 0, "unparseable": 0, "turns_completed": 0, "turns_failed": 0,
           "errors": [], "items": {}, "last_message": "", "session_id": None,
           "sandbox_denials": 0, "commands": 0, "turn_usage": [],
           "usage": {"input_tokens": 0, "cached_input_tokens": 0, "cache_write_input_tokens": 0,
                     "output_tokens": 0, "reasoning_output_tokens": 0}}
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        out["records"] += 1
        try:
            event = json.loads(raw)
        except ValueError:
            out["unparseable"] += 1
            continue
        if not isinstance(event, dict):
            out["unparseable"] += 1
            continue
        kind = event.get("type") or ""
        if kind == "thread.started":
            out["session_id"] = event.get("thread_id") or event.get("id") or out["session_id"]
        elif kind == "turn.completed":
            out["turns_completed"] += 1
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            for key in out["usage"]:
                try:
                    out["usage"][key] += int(usage.get(key) or 0)
                except (TypeError, ValueError):
                    pass
            # Each turn's own figures, not only their sum (critic F7, 2026-09-17): whether the
            # CLI reports per-turn usage or a running total over the thread is unmeasured here,
            # and a sum is the same number either way, so a cached-share reading cannot be
            # trusted until one beat's turns are on the record side by side. Bounded at
            # TURN_USAGE_KEEP entries so a long call's record line stays small.
            if len(out["turn_usage"]) < TURN_USAGE_KEEP:
                out["turn_usage"].append(
                    {key: usage.get(key) for key in
                     ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                      "output_tokens")})
        elif kind == "turn.failed":
            out["turns_failed"] += 1
            error = event.get("error")
            out["errors"].append(str(error.get("message") if isinstance(error, dict) else error))
        elif kind == "error":
            out["errors"].append(str(event.get("message") or event.get("error") or raw[:300]))
        elif kind.startswith("item."):
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            itype = str(item.get("type") or "unknown")
            if kind == "item.completed":
                out["items"][itype] = out["items"].get(itype, 0) + 1
            if itype == "agent_message" and kind == "item.completed":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    out["last_message"] = text.strip()
            if itype == "command_execution" and kind == "item.completed":
                out["commands"] += 1
                output = str(item.get("aggregated_output") or item.get("output") or "")
                if DENIAL_RE.search(output):
                    out["sandbox_denials"] += 1
    return out


def parse_close_events(lines):
    """Everything the close line reports (run_lane), from the JSONL events Codex printed. Every
    line is parsed with json.loads; an unparseable one is counted, never grepped for meaning. No
    line can end the parse: a nesting too deep for the decoder counts as unparseable, and a `type`
    that is not a string is no event this reader knows, so a malformed stream never costs the
    close. A turn's usage joins the sum only as read_usage admits it, and the counts kept beside
    the sum (turns started, usage objects absent, malformed or reported) are what close_usage
    reads. Only the close reads this: the beat's figures stay parse_events' (critic CR-ADD3
    finding 1: one parser shared by both changed the beat's sums and its hold verdict)."""
    out = {"records": 0, "unparseable": 0, "turns_started": 0, "turns_completed": 0,
           "turns_failed": 0, "errors": [], "failures": [], "failures_blank": 0, "items": {},
           "last_message": "", "session_id": None,
           "sandbox_denials": 0, "commands": 0,
           "usage_absent": 0, "usage_malformed": 0, "usage_reported": 0,
           "usage": {"input_tokens": 0, "cached_input_tokens": 0, "cache_write_input_tokens": 0,
                     "output_tokens": 0, "reasoning_output_tokens": 0}}
    lines = list(lines)
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        out["records"] += 1
        try:
            event = json.loads(raw)
        except (ValueError, RecursionError):
            out["unparseable"] += 1
            continue
        if not isinstance(event, dict):
            out["unparseable"] += 1
            continue
        kind = event.get("type")
        kind = kind if isinstance(kind, str) else ""
        if kind == "thread.started":
            out["session_id"] = event.get("thread_id") or event.get("id") or out["session_id"]
        elif kind == "turn.started":
            # A turn that starts and never completes or fails is a turn whose usage Codex never
            # reported (an error, a crash, a signal from outside the wrapper): close_usage reads
            # the difference.
            out["turns_started"] += 1
        elif kind == "turn.completed":
            out["turns_completed"] += 1
            # One predicate decides both what this turn reported and what joins the sum, so a
            # value judged malformed never enters it (critic CR-ADD2 finding 1: a negative turned
            # the subtotal negative and 1e309 raised OverflowError before the close was written).
            counts, problem = read_usage(event.get("usage"))
            if problem == "absent":
                out["usage_absent"] += 1
            elif problem:
                out["usage_malformed"] += 1
            if counts:
                out["usage_reported"] += 1
            for key, value in counts.items():
                out["usage"][key] += value
        elif kind == "turn.failed":
            # The turn's own error text, kept only where it says something: an empty object, a
            # null or a blank message is counted, never written down as "None" (critic finding 7 of
            # the 2026-10-10 design review), so the decisive-error selector can pass over it.
            out["turns_failed"] += 1
            text = failure_text(event.get("error"))
            if text:
                out["failures"].append(text)
                out["errors"].append(text)
            else:
                out["failures_blank"] += 1
        elif kind == "error":
            out["errors"].append(str(event.get("message") or event.get("error") or raw[:300]))
        elif kind.startswith("item."):
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            itype = str(item.get("type") or "unknown")
            if kind == "item.completed":
                out["items"][itype] = out["items"].get(itype, 0) + 1
            if itype == "agent_message" and kind == "item.completed":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    out["last_message"] = text.strip()
            if itype == "command_execution" and kind == "item.completed":
                out["commands"] += 1
                output = str(item.get("aggregated_output") or item.get("output") or "")
                if DENIAL_RE.search(output):
                    out["sandbox_denials"] += 1
    out.update(lane.a3_native_evidence("".join(lines), "codex"))
    return out


def usage_count(value):
    """Whether one token count may join the sum: a non-negative integer, and a bool is not one. A
    negative, a float (JSON's 1e309 parses as infinity), a string or a null never joins it, so a
    malformed value can neither turn the subtotal negative, overflow it nor stand in for a
    measurement."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def read_usage(usage):
    """(counts, problem) for one turn.completed usage object: the counts the sum may read (only
    those usage_count admits), and the problem: None for a measurement, `absent` when the turn
    carried no object, `malformed` otherwise. A measurement carries every USAGE_REQUIRED count and
    no unreadable one, so an empty object or a value read as 0 is never taken for one; a malformed
    object's readable counts still join the sum, which is then an incomplete subtotal."""
    if usage is None:
        return {}, "absent"
    if not isinstance(usage, dict):
        return {}, "malformed"
    present = [key for key in USAGE_KEYS if key in usage]
    counts = {key: usage[key] for key in present if usage_count(usage[key])}
    if len(counts) < len(present) or any(key not in usage for key in USAGE_REQUIRED):
        return counts, "malformed"
    return counts, None


def close_usage(parsed, killed_by, returncode):
    """(state, complete, reasons) for the close line and the lane-closed record (register
    2026-09-30 10:56). Codex reports usage only on turn.completed, so the evidence decides:
      missing     no completed turn reported a readable count, whether no turn completed or each
                  that did carried no usage object or only unreadable values: the zeros are no
                  measurement and the close line reads `unknown` (critic CR-ADD2 finding 4);
      incomplete  readable counts were reported, but a completed turn carried no usage object or a
                  malformed one, a turn failed, a turn started and never finished, the wrapper
                  stopped the run, or the process ended non-zero after its last completed turn
                  (finding 5): the sum covers only what was reported;
      zero        a measured zero, complete and shown as 0;
      complete    the sum of every completed turn.
    The reasons name why the counts are short: for `missing`, what the completed turns lacked; for
    `incomplete`, that and how the run ended. The numeric subtotal is the record's in every state.
    `parsed` is parse_close_events'. The held-lane beat keeps its own earlier reading and rule
    (parse_events, run_beat), which handsoff.py's hold verdict reads."""
    reported = []
    if parsed["usage_absent"]:
        reported.append("%d completed turn(s) carried no usage object" % parsed["usage_absent"])
    if parsed["usage_malformed"]:
        reported.append("%d usage object(s) malformed" % parsed["usage_malformed"])
    if not parsed["usage_reported"]:
        return "missing", False, ["no completed turn reported usage"] + reported
    ended = []
    if parsed["turns_failed"]:
        ended.append("%d turn(s) failed with usage unreported" % parsed["turns_failed"])
    unfinished = parsed["turns_started"] - parsed["turns_completed"] - parsed["turns_failed"]
    if killed_by:
        ended.append("the wrapper stopped the run (%s)" % killed_by)   # a turn it cut short is the stop's
    elif unfinished > 0:
        ended.append("%d turn(s) started and never finished (process exit %s)" % (unfinished, returncode))
    elif returncode != 0 and not parsed["turns_failed"]:
        # No turn is seen in flight, yet the process failed after its last completed turn: a CLI
        # that names no turn.started could have been in one, so the sum is not affirmed whole.
        ended.append("the process exited %s after its last completed turn" % returncode)
    if reported or ended:
        return "incomplete", False, reported + ended
    if not any(parsed["usage"].values()):
        return "zero", True, []
    return "complete", True, []


def usage_text(close):
    """The close line's usage clause: `unknown` for missing usage, the figures for a complete or
    measured-zero close, the figures marked an incomplete subtotal otherwise. A close written before
    `usage_state` (or by `kill`, with no usage) is read from `usage_complete` and the turn count."""
    usage = close.get("usage") if isinstance(close.get("usage"), dict) else {}
    state = close.get("usage_state")
    if state not in ("missing", "zero", "complete", "incomplete"):
        if not usage:
            state = "missing"
        elif close.get("usage_complete") is False:
            state = "incomplete" if usage.get("calls") else "missing"
        else:
            state = "complete"
    if state == "missing":
        return "in unknown (cached unknown) · out unknown"
    figures = "in %s (cached %s) · out %s" % (usage.get("input_tokens"),
                                              usage.get("cached_input_tokens"),
                                              usage.get("output_tokens"))
    if state != "incomplete":
        return figures
    reasons = [r for r in (close.get("usage_incomplete") or []) if isinstance(r, str)]
    return figures + " (incomplete subtotal%s)" % ((": " + "; ".join(reasons)) if reasons else "")


def meaningful(text):
    """An error text that says something, stripped, or "": a blank, `None` or `null` says nothing."""
    text = text.strip() if isinstance(text, str) else ""
    return "" if text.lower() in ("", "none", "null") else text


def failure_text(error):
    """Complete terminal text; the shared reader also serves explicit recovery."""
    return lane.terminal_error_text(error)


def decisive_error(parsed, exit_class):
    """The one error a failed close leads with (register 2026-09-26 00:16: seven lanes closed
    showing only the first reconnect messages while the decisive 401 sat last in the events log).
    A limit close names the last error that reads as a limit; any other failed close names the last
    meaningful turn.failed message, else the last meaningful error, else a truthful fallback. Every
    choice is the LAST, never the first: a stream retries before it fails, so the first errors are
    the retries and the last is what ended the turn."""
    if "terminal_error" in parsed:
        text = parsed["terminal_error"]
        if text:
            return text[:300]
        return "turn failed with no error text" if parsed.get("terminal_failure") else None
    errors = [meaningful(e) for e in parsed.get("errors") or []]
    errors = [e for e in errors if e]
    if exit_class == "limit":
        for text in reversed(errors):
            if LIMIT_RE.search(text):
                return text[:300]
    for text in reversed(parsed.get("failures") or []):
        if meaningful(text):
            return meaningful(text)[:300]
    if errors:
        return errors[-1][:300]
    if parsed.get("turns_failed"):
        return "turn failed with no error text (%d turn.failed event(s), none carrying a message)" \
            % parsed["turns_failed"]
    return None


def classify(killed_by, parsed, returncode, report_text):
    """The execution outcome. A task outcome (complete, partial, blocked) is the report's and
    the head verifies it on disk."""
    if parsed.get("refusal_count"):
        continued = lane.a3_final_success("codex", parsed, returncode, stopped=bool(killed_by))
        return ("refusal-continued" if continued else "refusal"), None
    if killed_by == "deadline":
        return "deadline", "deadline reached"
    if killed_by == "stall":
        return "stall", "silence past the bound"
    if killed_by == "signal":
        return "killed", "wrapper signalled"
    terminal = parsed.get("terminal_error") or ""
    if not (parsed.get("terminal_failure") or returncode not in (0, None) or not parsed["turns_completed"]):
        terminal = ""
    if terminal and LIMIT_RE.search(terminal):
        return "limit", terminal[:300]
    if terminal and lane.NETWORK_RE.search(terminal):
        return "network", terminal[:300]
    if parsed.get("terminal_failure") or (terminal and not parsed["turns_completed"]):
        return "failed", terminal[:300] or "turn failed"
    if returncode not in (0, None):
        return "failed", "process exit %s" % returncode
    if not parsed["turns_completed"]:
        return "failed", "no turn.completed event (%d records, %d unparseable)" % (
            parsed["records"], parsed["unparseable"])
    if not report_text.strip():
        return "empty", "turn completed with no report text"   # the round's "returns nothing" case
    return "completed", None


# ------------------------------------------------------------------------ run --------------

class Runner:
    """Starts the process, streams its events to the events file, watches for silence and the
    deadline, and returns what the close line needs."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.lines, self.stderr_chunks = [], []
        self.last_activity = time.time()
        self.session_id = None
        self.killed_by = None
        self.process = None
        self.awake = None          # the keep-awake process beside it (lane.start_awake), if one started
        self._lock = threading.Lock()
        self.owner = lane.a3_current(ctx["record"], ctx["run"], ctx["lane"])
        self.reader_errors = []
        self.streams_complete = False
        self.threads = []
        if self.owner is not None:
            self.owner.stream_settler = self.settle_failure

    def settle_failure(self):
        """Drain an exceptionally stopped child before the owner can freeze its outcome."""
        self.process = self.process or self.owner.process
        readers = self.threads[:2]
        if not any(thread.ident is not None for thread in readers):
            try:
                stdout, stderr = self.process.communicate(timeout=KILL_GRACE_S)
                self.streams_complete = True
            except subprocess.TimeoutExpired as exc:
                stdout, stderr = lane.output_text(exc.output), lane.output_text(exc.stderr)
                self.streams_complete = False
            with self._lock:
                self.lines = (stdout or "").splitlines(keepends=True)
                self.stderr_chunks = [stderr or ""]
        else:
            for thread in readers:
                if thread.ident is not None:
                    thread.join(timeout=KILL_GRACE_S)
            self.streams_complete = (len(readers) == 2 and not self.reader_errors
                                     and all(t.ident is not None and not t.is_alive() for t in readers))
        with self._lock:
            evidence = parse_close_events(list(self.lines))
        evidence.update(source=self.ctx["events"], process_exit=self.process.returncode,
                        native_stderr="".join(self.stderr_chunks), streams_complete=self.streams_complete)
        if not self.streams_complete:
            evidence["uncertainty"] = "incomplete streams after infrastructure failure"
        return evidence, self.streams_complete

    def _record(self, payload):
        base = {"ts": now(), "run": self.ctx["run"], "lane": self.ctx["lane"], "harness": HARNESS}
        base.update(payload)
        lane.append_record(self.ctx["record"], base)

    def _read_stdout(self):
        with open(self.ctx["events"], "a", encoding="utf-8") as handle:
            for raw in self.process.stdout:
                handle.write(raw)
                handle.flush()
                with self._lock:
                    self.lines.append(raw)
                    self.last_activity = time.time()
                    evidence = lane.a3_native_evidence("".join(self.lines), "codex")
                if self.owner and self.owner.journal and evidence.get("refusal_count"):
                    evidence["source"] = self.ctx["events"]
                    self.owner.capture(evidence)
                if self.session_id is None:
                    try:
                        event = json.loads(raw)
                    except (ValueError, RecursionError):
                        continue
                    if isinstance(event, dict) and event.get("type") == "thread.started":
                        self.session_id = event.get("thread_id") or event.get("id")
                        self._record({"event": "lane-session", "session_id": self.session_id,
                                      "pid": self.process.pid})

    def _read_stderr(self):
        with open(self.ctx["stderr"], "a", encoding="utf-8") as handle:
            for raw in self.process.stderr:
                handle.write(raw)
                handle.flush()
                with self._lock:
                    self.stderr_chunks.append(raw)
                    self.last_activity = time.time()

    def _feed_stdin(self):
        try:
            self.process.stdin.write(self.ctx["prompt"])
            self.process.stdin.close()
        except (OSError, ValueError):
            pass

    def _drain(self, reader):
        try:
            reader()
        except BaseException as exc:
            self.reader_errors.append("%s: %s" % (reader.__name__, exc))

    def _kill(self, why):
        if self.owner and self.owner.journal:
            self.owner.stop("explicit-stop" if why == "signal" else why,
                            explicit=why == "signal", reason="wrapper signalled" if why == "signal" else None)
        self.killed_by = why
        lane.signal_group(self.process.pid, signal.SIGTERM)
        waited = 0.0
        while waited < KILL_GRACE_S and self.process.poll() is None:
            time.sleep(0.5)
            waited += 0.5
        if self.process.poll() is None:
            lane.signal_group(self.process.pid, signal.SIGKILL)

    def run_process(self):
        """Returns the duration in seconds; raises OSError when the process cannot start."""
        started = time.time()
        # The stream is JSON, so UTF-8; a byte that does not decode is replaced, never raised, so
        # a reader thread cannot die mid-stream and leave the rest of the events (and any usage in
        # them) out of the close.
        if self.owner is None or self.owner.journal is None:
            raise lane.A3Premise("process start requires a lifetime owner")
        self.owner.prelaunch()
        self.owner.process = self.process = subprocess.Popen(self.ctx["command"], cwd=self.ctx["cwd"], env=self.ctx["env"],
                                        text=True, encoding="utf-8", errors="replace",
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
        if self.owner and self.owner.journal:
            self.owner.record_child(self.process)
        self._record({"event": self.ctx.get("spawn_event", "lane-spawned"),
                      "session_id": self.ctx.get("session_id"), "pid": self.process.pid,
                      "wrapper_pid": os.getpid(), "class": self.ctx["cls"],
                      "detached": bool(self.ctx.get("detached")),
                      "mechanism": "codex-lane.py headless, model %s, effort %s"
                                   % (self.ctx["model"], self.ctx["effort"])})
        # The keep-awake process beside the codex process (owner decision of 2026-10-09;
        # lane.start_awake), recorded before the readers start so lane-session follows it.
        self.awake, awake_fields = lane.start_awake(self.process.pid)
        awake_line = {"event": lane.AWAKE_EVENT, "session_id": self.ctx.get("session_id"),
                      "wrapper_pid": os.getpid(), "class": self.ctx["cls"],
                      "detached": bool(self.ctx.get("detached"))}
        awake_line.update(awake_fields)
        self._record(awake_line)
        threads = self.threads = [threading.Thread(target=self._drain, args=(self._read_stdout,), daemon=True),
                   threading.Thread(target=self._drain, args=(self._read_stderr,), daemon=True),
                   threading.Thread(target=self._feed_stdin, daemon=True)]
        for thread in threads:
            thread.start()

        def on_signal(signum, frame):
            if self.killed_by is None:
                self._kill("signal")
        signal.signal(signal.SIGTERM, on_signal)
        signal.signal(signal.SIGINT, on_signal)

        deadline, silence = self.ctx["deadline"], self.ctx["silence"]
        tick = 1.0        # a poll a second: cheap, and a finished or signalled lane closes within it
        while self.process.poll() is None:
            time.sleep(tick)
            if self.owner and self.owner.journal:
                request = self.owner.stop_request()
                if request:
                    self._kill("signal" if request.get("explicit") else request["cause"])
            if self.killed_by:
                break
            elapsed = time.time() - started
            with self._lock:
                silent = time.time() - self.last_activity
            if elapsed > deadline:
                self._kill("deadline")
                break
            if silence and silent > silence:
                self._record({"event": "stall", "session_id": self.session_id,
                              "silent_s": round(silent, 1), "threshold_s": silence,
                              "reason": "silent", "by": "spawn"})
                self._kill("stall")
                break
        for thread in threads[:2]:
            thread.join(timeout=KILL_GRACE_S)
        self.streams_complete = not self.reader_errors and all(not thread.is_alive() for thread in threads[:2])
        try:
            self.process.wait(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            lane.signal_group(self.process.pid, signal.SIGKILL)
            self.process.wait()
        return round(time.time() - started, 1)


def emit_summary(ctx, close, report_text):
    if ctx["format"] == "json":
        print(json.dumps(close))
        return
    deferred = close.get("controls_deferred")
    deferred_ok = isinstance(deferred, list) and all(isinstance(v, dict) and "result" in v
                                                     for v in deferred)
    print("lane %s/%s · codex %s·%s · %s · %ss · %s turns · %s · report %s (%s words)%s%s"
          % (ctx["run"], ctx["lane"], ctx["model"], ctx["effort"], close.get("exit_class"),
             close.get("duration_s"), close.get("num_turns"), usage_text(close),
             close.get("report"), close.get("report_words"),
             (" · error: %s" % close.get("error")) if close.get("error") else "",
             lane.deferred_text(deferred) if deferred_ok else ""))
    if close.get("notice"):
        print(lane.a3_notice_text(close["notice"]))
    shown, n_shown, n_total, cut = lane.cut_words(report_text, ctx["report_words"])
    if shown:
        print(shown)
    if cut:
        print("(%d of %d words shown; full text: %s)" % (n_shown, n_total, close.get("report")))


def run_lane(ctx):
    """Shared by spawn and resume: the process, the events, the close line, the summary."""
    lane.open_console_for_spawn(ctx["run"], ctx.get("viewer"))
    owner = lane.a3_current(ctx["record"], ctx["run"], ctx["lane"])
    if owner is None or owner.journal is None:
        raise lane.A3Premise("task execution requires a lifetime owner")
    runner = Runner(ctx)
    started_ts = now()
    try:
        duration = runner.run_process()
    except OSError as exc:
        if runner.process is not None:
            owner.infrastructure_failure(exc)
            lane.a3_render(owner.journal, ctx["format"], ctx["report_words"])
            return 3
        failed = {
            "ts": now(), "run": ctx["run"], "lane": ctx["lane"], "event": "lane-closed",
            "harness": HARNESS, "class": ctx["cls"], "session_id": ctx.get("session_id"),
            "exit_class": "spawn-failed", "exit_code": 3, "error": str(exc),
            "total_cost_usd": None, "cost_src": "codex-plan", "wrapper_pid": os.getpid()}
        if ctx.get("controls_pending"):
            # The pass's report controls get their verdict at this close as at every other (review
            # CR-B4L finding 9): a process that never started returned no report, so unverified.
            failed["controls_deferred"] = lane.deferred_verdicts(
                ctx["controls_pending"], ctx["report"], "", False, False, "spawn-failed")
        owner.start_failed()
        owner.capture({"refusal_count": 0, "refusal_evidence": [], "source": "child never started"}, settled=True)
        failed = owner.finish(failed, allow_move=False)
        sys.stderr.write("codex-lane.py: could not start the lane process: %s\n" % exc)
        if failed.get("controls_deferred"):
            sys.stderr.write("codex-lane.py: lane %s/%s%s\n"
                             % (ctx["run"], ctx["lane"], lane.deferred_text(failed["controls_deferred"])))
        return 3
    with runner._lock:
        captured_lines = list(runner.lines)
    parsed = parse_close_events(captured_lines)
    parsed["source"] = ctx["events"]
    parsed["process_exit"] = runner.process.returncode
    parsed["native_stderr"] = "".join(runner.stderr_chunks)
    parsed["native_exit_class"] = classify(runner.killed_by, parsed, runner.process.returncode,
                                           parsed.get("report_text") or parsed["last_message"])[0]
    _, boundary_error = lane.a3_suffix(owner.refresh().get("boundary"))
    if boundary_error and boundary_error.startswith("final-message, boundary unknown"):
        # Captured stdout still proves this process's refusal. A damaged persisted boundary
        # cannot certify report controls or support later reconstruction of its pass.
        parsed["uncertainty"] = boundary_error
    if not runner.streams_complete:
        parsed["uncertainty"] = "incomplete streams: " + "; ".join(runner.reader_errors or ["EOF not observed"])
    parsed["streams_complete"] = runner.streams_complete
    parsed.update(owner.capture(parsed, settled=runner.streams_complete))
    session_id = runner.session_id or parsed["session_id"] or ctx.get("session_id")

    # The current JSONL response is the evidence. A pre-existing or concurrently planted
    # output file cannot supply a response, even when the CLI leaves -o untouched (critic F1).
    report_text = parsed.get("report_text") or parsed["last_message"]
    response_text = report_text
    exit_class, error = classify(runner.killed_by, parsed, runner.process.returncode, report_text)
    if exit_class in ("failed", "limit", "network"):
        # The close leads with the decisive error, the last one, never the first retries
        # (register 2026-09-26 00:16); the beat keeps classify's own text (parse_events).
        error = decisive_error(parsed, exit_class) or error
    if not report_text:
        report_text = "(no report text: %s)" % (error or "exit %s" % runner.process.returncode)
    elif exit_class in ("failed", "limit", "network") and error:
        # The saved report says why the pass failed before the lane's last message, which stays
        # whole and identifiable below the wrapper's line.
        report_text = ("(codex-lane.py: this pass closed %s — %s. The lane's last message follows, "
                       "unfinished.)\n\n%s" % (exit_class, error, report_text))
    try:
        lane.write_atomic(ctx["report"], report_text.rstrip() + "\n")
        report_written = ctx["report"]
    except OSError as exc:
        report_written = None
        sys.stderr.write("codex-lane.py: report not written (%s)\n" % exc)
    shown, n_shown, n_total, cut = lane.cut_words(report_text, ctx["report_words"])
    stderr_text = "".join(runner.stderr_chunks)
    usage_state, usage_complete, usage_reasons = close_usage(parsed, runner.killed_by,
                                                             runner.process.returncode)
    close = {
        "ts": now(), "run": ctx["run"], "lane": ctx["lane"], "event": "lane-closed",
        "harness": HARNESS, "session_id": session_id, "class": ctx["cls"],
        "model": ctx["model"], "effort": ctx["effort"], "exit_class": exit_class,
        "exit_code": EXIT_CODES.get(exit_class, 3), "process_exit": runner.process.returncode,
        "duration_s": duration, "num_turns": parsed["turns_completed"],
        "turns_started": parsed["turns_started"],
        "turns_failed": parsed["turns_failed"], "total_cost_usd": None, "cost_src": "codex-plan",
        # The completed turns' numeric subtotal, always kept, with its accounting state beside it
        # (close_usage): Codex reports usage only on turn.completed, so a lane stopped mid-turn,
        # a failed or unfinished turn, a failed process or a turn without a measured usage object
        # leaves the sum a subtotal, and no readable count at all leaves it unknown, never a
        # measured zero (register 2026-09-30 10:56).
        "usage": dict(parsed["usage"], calls=parsed["turns_completed"]),
        "usage_complete": usage_complete, "usage_state": usage_state,
        "usage_incomplete": usage_reasons if usage_state in ("missing", "incomplete") else [],
        "items": parsed["items"], "commands": parsed["commands"],
        "sandbox_denials": parsed["sandbox_denials"],
        "denials": {"tool": 0, "fence": 0, "sandbox": parsed["sandbox_denials"]},
        "events": ctx["events"], "events_records": parsed["records"],
        "events_unparseable": parsed["unparseable"],
        "report": report_written, "report_words": n_total, "report_shown": n_shown,
        "report_cut": cut, "error": error, "errors": parsed["errors"][-ERRORS_KEEP:],
        "errors_total": len(parsed["errors"]), "turns_failed_blank": parsed["failures_blank"],
        "limit_signal": (error if exit_class == "limit" else None),
        "killed_by": runner.killed_by, "silence_s": ctx["silence"], "deadline_s": ctx["deadline"],
        "stderr_tail": stderr_text.strip()[-400:] or None, "wrapper_pid": os.getpid(),
        "started": started_ts}
    close.update(ctx.get("close_extra") or {})
    if ctx.get("controls_pending"):
        # The controls this pass declared on its own report, checked against the response this
        # pass returned — never the -o file, an earlier pass's report or the wrapper's own text
        # (register 2026-09-20 01:58).
        close["controls_deferred"] = lane.deferred_verdicts(
            ctx["controls_pending"], ctx["report"], response_text,
            bool(response_text) and not parsed.get("uncertainty"),
            report_written is not None, exit_class)
    if parsed.get("uncertainty"):
        close["report_scope"] = "final-message, boundary unknown"
    close = owner.finish(close)
    exit_class = close["exit_class"]
    if any(v["result"] != "checked" for v in close.get("controls_deferred") or []):
        sys.stderr.write("codex-lane.py: lane %s/%s%s\n"
                         % (ctx["run"], ctx["lane"], lane.deferred_text(close["controls_deferred"])))
    emit_summary(ctx, close, report_text)
    lane.reap_awake(runner.awake)
    return lane.a3_exit_code(owner.journal)


# ----------------------------------------------------------------------- spawn -------------

def store_paths(run, lane_id, record_override=None):
    paths = lane.store_paths(run, lane_id, record_override)
    store = paths["store"]
    # `.log`, not `.jsonl`: the readers that glob the records directory for `*.jsonl` (lane.py's
    # cost fold, deep-lint's spawn-record review) must never take an event stream for a record.
    paths["events"] = os.path.join(store, "%s-events-%s.log" % (run, lane_id))
    paths["stderr"] = os.path.join(store, "%s-stderr-%s.log" % (run, lane_id))
    paths["prompt"] = os.path.join(store, "%s-prompt-%s.md" % (run, lane_id))
    return paths


def compose_prompt(definition_body, core, cwd, writes, search, brief):
    write_clause = ("you may write only under %s (Codex `workspace-write`); everything else is read-only."
                    % ", ".join(writes)) if writes else "this lane is read-only; you write nothing anywhere."
    search_clause = ("granted (`web_search = live`): verify every literature claim by opening its source"
                     if search else "disabled: work closed-book from the files your brief names")
    parts = ["ROLE DEFINITION\n" + definition_body.strip()]
    if core.strip():
        parts.append("LANE CORE (shared by every headless lane of this system)\n" + core.strip())
    parts.append(ADDENDUM.format(cwd=cwd, write_clause=write_clause, search_clause=search_clause).strip())
    parts.append("BRIEF\n" + brief.strip())
    return "\n\n".join(parts) + "\n"


def resume_paths(args):
    """Plan and check both per-pass paths before any resume write (critic F1/F3)."""
    paths = store_paths(args.run, args.lane, args.record)
    # First pass plus this resume plus every earlier recorded resume, including failed starts.
    pass_n = 2 + sum(1 for event in lane.load_record(paths["record"])
                     if event.get("lane") == args.lane and event.get("event") == "lane-resumed")
    for key in ("report", "prompt"):
        paths[key] = lane.pass_report_path(paths[key], pass_n)
    lane.require_absent_paths((paths["report"], paths["prompt"]))
    return paths


def config_hash(command):
    return lane.config_sha256(command, drop_pairs=CONFIG_DROP_PAIRS, drop_tail=1)


def stage_mapped(declared, sources, vault):
    """The READ+ and RUBRIC+ declarations with every path that lies inside a source of the copy
    rewritten to its place in the copy (`<<STAGED_COPY>>/<rel>`), and the rewrites the brief the lane
    receives takes (delivered_brief). `sources` are the directories the copy mirrors, oldest first: a
    spawn's own --stage-from, or for a resumed pass the lane-open's and every recorded refresh's
    (staged_sources). A path inside several is placed by the latest that holds it, the one the
    copy's file there mirrors now (review CR-B4L2 finding 2: a resume mapped against the spawn's
    source alone, so a refreshed source's excluded file was checked in that source). One resolution
    serves the check, the record and the delivered brief (review CR-B4L finding 2):
    lane.resolve_declared's, with `~` expanded, a relative path read against the vault as a grant
    is, and symlinks resolved. A vault-relative path inside a source therefore names the copy's file
    as an absolute one does. The brief the lane reads names the copy that was checked, never the
    source beside it. What the lane reads is the copy, so the copy's version is the one checked: a
    file the copy lacks (an excluded one among them) refuses, and is never checked through its
    original. A CONTROL+ naming a source path stays an ordinary control on the source; a control on
    the copy is written with the token. Returns (declarations, rewrites); a rewrite is (the entry as
    parsed, the entry as mapped)."""
    if isinstance(sources, str):
        sources = [sources]
    latest_first = list(reversed([s for s in sources if isinstance(s, str) and s]))

    def mapped(text, line, what):
        if not text or lane.STAGED_TOKEN in text or lane.REPORT_TOKEN in text:
            return text
        _given, real, _staged = lane.resolve_declared(text, vault, line, what)
        src = next((s for s in latest_first if inside(real, s)), None)
        if src is None:
            return text
        rel = os.path.relpath(real, src)
        token = lane.STAGED_TOKEN + ("" if rel == os.curdir else "/" + rel)
        return token + "/" if text.endswith("/") else token     # a directory written with its slash keeps it
    reads, rubrics, rewrites = [], [], []
    for entry in declared.get("reads") or []:
        new = dict(entry, path=mapped(entry["path"], entry["line"], "declared input"))
        reads.append(new)
        if new != entry:
            rewrites.append(("READ+", entry, new))
    for entry in declared.get("rubrics") or []:
        new = dict(entry, rubric=mapped(entry["rubric"], entry["line"], "rubric"),
                   tree=mapped(entry["tree"], entry["line"], "reviewers' tree"))
        rubrics.append(new)
        if new != entry:
            rewrites.append(("RUBRIC+", entry, new))
    return {"reads": reads, "rubrics": rubrics}, rewrites


def declaration_span(line, marker, accepts):
    """(start, end) of the body `marker` declares on `line`, read as lane.parse_declarations reads it
    (an unquoted marker runs to the line's end, a quoted one to its closing quote), for the first such
    body `accepts`; None where no marker on the line yields one."""
    for match in lane.MARKER_ANY_RE.finditer(line):
        if match.group(0)[:-1] != marker:
            continue
        end = len(line)
        opener = lane.quote_opener(line, match.start())
        if opener is not None:
            close = line.find(lane.QUOTE_PAIRS[opener], match.end())
            end = close if close != -1 else len(line)
        if accepts(line[match.end():end].strip()):
            return match.end(), end
    return None


def swap_in(line, start, end, old, new):
    """`line` with the first `old` inside [start, end) replaced by `new`; unchanged where absent."""
    at = line.find(old, start, end)
    return line if at == -1 else line[:at] + new + line[at + len(old):]


def delivered_brief(brief, rewrites):
    """The brief the lane receives, each rewritten declaration naming its place in the copy on the
    line it stands on, inside the span it declares (`<<STAGED_COPY>>` for now, substituted with the
    copy's path by the caller), so the reading list the lane is handed is the one that was checked.
    Returns (brief, the declarations as written and as delivered, for the record)."""
    lines = brief.splitlines(True)
    done = []
    for marker, old, new in rewrites:
        index = old["line"] - 1
        if not 0 <= index < len(lines):
            continue
        raw = lines[index]
        text = (raw.splitlines() or [""])[0]
        ending = raw[len(text):]
        if marker == "READ+":
            span = declaration_span(text, marker, lambda body: lane.unwrap(body) == old["path"])
            if span:
                text = swap_in(text, span[0], span[1], old["path"], new["path"])
        else:
            span = declaration_span(text, marker,
                                    lambda body: lane.split_in(body) == (old["rubric"], old["tree"]))
            if span:
                cut = text.rfind(" in ", span[0], span[1])
                if new["tree"] != old["tree"]:
                    text = swap_in(text, cut + 4, span[1], old["tree"], new["tree"])
                if new["rubric"] != old["rubric"]:
                    text = swap_in(text, span[0], cut, old["rubric"], new["rubric"])
        if span:
            lines[index] = text + ending
            done.append({"line": old["line"], "marker": marker,
                         "declared": (raw[:len(raw) - len(ending)]).strip(), "delivered": text.strip()})
    return "".join(lines), done


def uses_token(declared):
    """(declarations the staged copy decides, the others), by whether a path carries the token."""
    staged = {"controls": [], "reads": [], "rubrics": []}
    plain = {"controls": [], "reads": [], "rubrics": []}
    for kind, keys in (("controls", ("file",)), ("reads", ("path",)), ("rubrics", ("rubric", "tree"))):
        for entry in declared.get(kind) or []:
            side = staged if any(lane.STAGED_TOKEN in entry[key] for key in keys) else plain
            side[kind].append(entry)
    return staged, plain


def prepare(args, resume_id=None, beat=False):
    """Everything spawn and resume share before the process: checks, paths, command, record.
    A beat (resume --beat) reads no brief, takes no per-pass path and names no report.

    Two phases (critic finding 1 of the 2026-10-10 design review). First every check that does not
    depend on a staged copy: the reason, the pick, the class's write scope, the brief and its
    declarations — controls on files that exist now, declared inputs outside the stage source, web
    work against `--search` — the delegation pair, the executable and the definition. Then, for a
    spawn with `--stage-from`, the copy, and the checks only the finished, exclusion-filtered copy
    can answer: a control or an input written with `<<STAGED_COPY>>`, an input inside the stage
    source (its staged version), a rubric's folders in the reviewers' tree. A refusal in that second
    phase removes the attempt's copy before it exits (Stage.release), so the retry under the same
    lane id is never refused for a leftover; the caller of the spawn decides what happens to a copy
    that passed (cmd_spawn)."""
    lane.require_reason_letter(args.reason or "")
    if not (args.choice_reason or "").strip():
        die("--choice-reason is required: no routing row anchors a Codex model, so every pick "
            "records why this model and effort")
    if args.effort not in EFFORTS:
        die("--effort must be one of %s" % ", ".join(EFFORTS))
    if args.model not in KNOWN_MODELS and not args.any_model:
        die("--model %s is not in the known Codex catalogue %s; pass --any-model to override"
            % (args.model, ", ".join(KNOWN_MODELS)))
    if not args.cls:
        die("--class is required")
    spawning = resume_id is None
    staging = bool(args.stage_from) and spawning
    read_only = bool(getattr(args, "read_only", False))
    if args.stage_writable and not args.stage_from:
        die("--stage-writable goes with --stage-from")
    if read_only and (args.write or args.stage_writable):
        die("--read-only states a lane with no write scope, and this call also names %s: drop "
            "one of them" % ("--write" if args.write else "--stage-writable"))
    if spawning and args.cls in WRITE_CLASSES and not (args.write or args.stage_writable) \
            and not read_only:
        die("class `%s` does its work by writing (fixtures, clones, records), and this spawn gives "
            "it no write scope, so its sandbox would be read-only: pass --stage-writable with "
            "--stage-from, or --write <dir>, or --read-only to run it read-only on purpose "
            "(register 2026-09-23 18:0x)" % args.cls)
    if not args.cwd and not staging:
        die("--cwd is required (or --stage-from)")
    vault = lane.vault_root()
    paths = (resume_paths(args) if resume_id is not None and not beat
             else store_paths(args.run, args.lane, args.record))
    report = None if beat else paths["report"]
    stage_src = real_dir(args.stage_from, "--stage-from") if staging else None
    recorded_stage = None if spawning else getattr(args, "staged_copy", None)
    # The sources whose paths the copy stands for: this spawn's --stage-from, or for a resumed staged
    # pass every source its copy mirrors, oldest first (cmd_resume: the lane-open's, each recorded
    # refresh's, and this call's own refresh).
    map_src = [stage_src] if staging else (list(getattr(args, "staged_sources", None) or [])
                                           if recorded_stage else [])
    rewrites = []
    if beat:
        brief, declared = None, None
        checked, pending, inputs, later = None, [], [], None
    else:
        if not args.brief:
            die("--brief is required (the no-work form is resume --beat)")
        if not os.path.isfile(args.brief):
            die("brief file not found: %s" % args.brief)
        brief = lane.read_text(args.brief, "the brief")
        if not brief.strip():
            die("brief file is empty: %s" % args.brief)
        lane.refuse_doubled_root(args.brief, brief, vault)
        declared = lane.parse_declarations(brief, vault)
        lane.refuse_web(declared, None if args.search else
                        "this spawn has no web search: pass --search (web_search live); the shell's "
                        "--network is a different grant and does not serve it")
        if map_src:
            mapped, rewrites = stage_mapped(declared, map_src, vault)
            declared = dict(declared, **mapped)
        later, now_side = uses_token(declared)
        # Codex reads are unrestricted (the brief's reading list is the grant), so no read root is
        # tested here; a resumed staged pass resolves the token to its recorded copy.
        checked, pending = lane.check_controls(now_side["controls"], vault, report=report,
                                               stage=recorded_stage)
        inputs = lane.check_inputs(now_side, vault, stage=recorded_stage)
        if not staging:
            # No copy is made by this call: a token resolves to a resumed pass's recorded copy, and
            # with none to resolve to, resolve_declared refuses it here, before anything is staged.
            more, more_pending = lane.check_controls(later["controls"], vault, report=report,
                                                     stage=recorded_stage)
            checked, pending = checked + more, pending + more_pending
            inputs = inputs + lane.check_inputs(later, vault, stage=recorded_stage)
            later = None
    mode, mode_src, mode_from = lane.resolve_delegation(args)
    codex, version = resolve_codex(args.codex)
    definition_path, definition_sha, definition_body = definition_of(vault, args.cls)
    core_path, core = core_text(vault, args.append_core)
    if not args.append_core and not args.as_worker:
        drift = lane.core_drift_note(lane.default_home(), vault)
        if drift:
            sys.stderr.write(drift + "\n")

    # The attempt's Stage exists before its copy starts, so the handler below can release whatever
    # the attempt holds whenever it is stopped: its own directory mid-copy, or the copy in place
    # (review CR-B4L finding 8).
    stage = Stage(stage_path(args)) if staging else None
    try:
        if stage is not None:
            stage_copy(args, stage)
            args.cwd = stage.dest
            if args.stage_writable:
                args.write = list(args.write or []) + [stage.dest]
            if later is not None:
                more, more_pending = lane.check_controls(later["controls"], vault, report=report,
                                                         stage=stage.dest)
                checked, pending = checked + more, pending + more_pending
                inputs = inputs + lane.check_inputs(later, vault, stage=stage.dest)
        cwd = real_dir(args.cwd, "--cwd")
        writes = [real_dir(w, "--write") for w in (args.write or [])]
        if writes and not any(inside(cwd, w) for w in writes):
            die("with --write the cwd must lie inside a write directory: under workspace-write the "
                "cwd itself becomes writable (cwd %s; writes %s)" % (cwd, ", ".join(writes)))
        sandbox = "workspace-write" if writes else "read-only"
        add_dirs = [w for w in writes if not inside(w, cwd)]
        if args.network and not writes:
            die("--network needs --write: shell network is a workspace-write setting")
        overrides = config_overrides(args, args.network)
        command = build_command(codex, args, cwd, sandbox, add_dirs, overrides, report, resume_id)
        # `<<STAGED_COPY>>` in the brief becomes the copy's path (register 2026-09-25 04:3x): the
        # actual stage after staging, or a resumed pass's recorded copy. With no copy the text stays
        # as written and one line says so; a declaration using it has already been refused.
        token_at = (stage.dest if stage is not None else recorded_stage)
        token_count = brief.count(lane.STAGED_TOKEN) if brief else 0   # the brief's own, before any rewrite
        staged_declarations = []
        if brief and rewrites and token_at:
            # A declaration of a source path is delivered as the copy's path, the one checked above.
            brief, staged_declarations = delivered_brief(brief, rewrites)
            missed = sorted({old["line"] for _m, old, _n in rewrites} -
                            {done["line"] for done in staged_declarations})
            if missed:
                die("brief line(s) %s: a declaration naming the stage source could not be rewritten "
                    "to the staged copy, so the lane would be handed the source it was not checked "
                    "on: write it with %s" % (", ".join(str(n) for n in missed), lane.STAGED_TOKEN))
            for done in staged_declarations:
                done["delivered"] = done["delivered"].replace(lane.STAGED_TOKEN, token_at)
        if brief and token_at and (token_count or staged_declarations):
            brief = brief.replace(lane.STAGED_TOKEN, token_at)
        elif token_count:
            sys.stderr.write("codex-lane.py: the brief mentions %s %d time(s) and no staged copy "
                             "applies; left as written\n" % (lane.STAGED_TOKEN, token_count))
        prompt = (lane.BEAT_PROMPT + "\n" if beat
                  else compose_prompt(definition_body, core, cwd, writes, args.search, brief))
        env = dict(os.environ)
        env.update({"LLM_WIKI_LANE": "1", "LLM_WIKI_LANE_RUN": args.run, "LLM_WIKI_LANE_ID": args.lane,
                    "LLM_WIKI_LANE_HARNESS": HARNESS})
        global_path, global_bytes = global_instructions_bytes()
    except BaseException:
        release_or_say(stage)         # a refusal, an interrupt or a crash: the attempt's copy goes
        raise
    if global_bytes:
        sys.stderr.write("codex-lane.py: %s is %d bytes and Codex loads it into every lane; "
                         "--ignore-user-config does not cover it\n" % (global_path, global_bytes))
    return {"vault": vault, "brief": brief, "controls": checked, "controls_pending": pending,
            "inputs": inputs, "cwd": cwd, "writes": writes, "read_only": read_only,
            "staged_copy_token": token_count if (token_count and token_at) else 0,
            "staged_declarations": staged_declarations,
            "global_instructions": {"path": global_path, "bytes": global_bytes},
            "stage": getattr(args, "stage_report", None), "stage_owner": stage,
            "sandbox": sandbox, "add_dirs": add_dirs, "mode": (mode, mode_src, mode_from),
            "codex": codex, "version": version, "definition": (definition_path, definition_sha),
            "core_path": core_path, "paths": paths, "overrides": overrides, "command": command,
            "prompt": prompt, "env": env}


def open_line(args, prep, event="lane-open", extra=None):
    vault = prep["vault"]
    mode, mode_src, mode_from = prep["mode"]
    line = {
        "ts": now(), "run": args.run, "lane": args.lane, "event": event, "harness": HARNESS,
        # the process that writes this line and the close: a detached caller's acknowledgement
        # matches its own worker's pid here (lane.await_ack)
        "wrapper_pid": os.getpid(),
        "class": args.cls, "definition": os.path.relpath(prep["definition"][0], vault),
        "definition_sha256": prep["definition"][1],
        "model": args.model, "effort": args.effort, "throttle": "n/a (codex)",
        "row_default": None, "model_src": "explicit",
        "effort_src": getattr(args, "effort_src", "explicit"),
        "choice_reason": args.choice_reason, "reason": args.reason,
        "mode": mode, "mode_src": mode_src, "mode_from": mode_from,
        "cwd": prep["cwd"], "sandbox": prep["sandbox"], "writes": prep["writes"],
        "add_dirs": prep["add_dirs"],
        "grants": [lane.a3_canonical(path) for path in (args.grant or [])] if args.grant else None,
        "expect_usd": lane.require_estimate(args.expect_usd) if args.expect_usd is not None else None,
        "routing_path": os.path.abspath(args.routing) if args.routing else None,
        "reads": "unrestricted (codex sandbox; the brief's reading list is the grant)",
        "stage": prep.get("stage"), "global_instructions": prep.get("global_instructions"),
        "search": bool(args.search), "network": bool(args.network),
        "config_overrides": prep["overrides"], "config_extra": list(args.config or []),
        "ignore_user_config": True,
        "executable": prep["codex"], "codex_version": prep["version"],
        "core": (lane.display_path(prep["core_path"], vault) if prep["core_path"] else None),
        "prompt_file": prep["paths"]["prompt"], "prompt_bytes": len(prep["prompt"].encode("utf-8")),
        "brief": os.path.abspath(args.brief) if args.brief else None,
        "controls_checked": prep["controls"],
        "controls_pending": prep.get("controls_pending") or [],
        "inputs_checked": prep.get("inputs") or [],
        "read_only": bool(prep.get("read_only")),
        "staged_copy_token": prep.get("staged_copy_token") or 0,
        "config_sha256": config_hash(prep["command"]),   # what a resume or a beat must carry byte for byte
        "schema": (os.path.abspath(args.schema) if args.schema else None),
        "events": prep["paths"]["events"], "report": prep["paths"]["report"],
        "deadline_s": args.deadline_s, "silence_s": args.silence_s,
        "report_words_cap": args.report_words, "plant": args.plant,
        "reading_list": args.reading_list, "breadth": lane.customisation_value("breadth", "standard"),
        "budget_usd": None, "total_cost_usd": None, "cost_src": "codex-plan",
        "mechanism": "codex-lane.py headless (codex exec --json, --ignore-user-config, "
                     "sandbox %s, -a never, silence watch on the event stream)" % prep["sandbox"]}
    if prep.get("staged_declarations"):
        # each declaration of a source path, as written and as delivered: the copy's path (review
        # CR-B4L finding 2)
        line["staged_declarations"] = prep["staged_declarations"]
    if getattr(args, "item", None) and event == "lane-open":
        line["item"] = args.item
    if extra:
        line.update(extra)
    return line


def detach(args):
    """Re-run this command as a worker that survives the caller; `--no-wait` returns once the
    worker has acknowledged this call, or says why it could not tell (lane.await_ack). The
    caller opens the run's console first, in its own context, and the worker runs under `--viewer
    none`, appended so it wins over any --viewer the command carried.
    (register 2026-09-09 11:21, update
    2026-09-12). The opener itself is handsoff.py's, reached through lane.open_console_for_spawn."""
    paths = store_paths(args.run, args.lane, args.record)
    os.makedirs(paths["store"], exist_ok=True)
    # The acknowledgement (register 2026-09-29 16:57): this call's own lane-open for a spawn or
    # lane-resumed for a resume, written by the worker with its pid as wrapper_pid, after the
    # record's length now, so neither an older line nor another call's line can stand for it.
    event = "lane-resumed" if args.command == "resume" else "lane-open"
    rows, _ = lane.record_snapshot(paths["record"])
    since = len(rows or [])
    lane.open_console_for_spawn(args.run, args.viewer)
    argv = [sys.executable, os.path.abspath(__file__)] + [a for a in sys.argv[1:]
                                                          if a not in ("--detach", "--no-wait")]
    argv += ["--viewer", "none", "--as-worker"]
    with open(paths["detach_log"], "a", encoding="utf-8") as log:
        worker = subprocess.Popen(argv, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                  start_new_session=True)
    code = lane.await_ack(
        worker, paths["record"], since,
        lambda row, pid: (row.get("lane") == args.lane and row.get("event") == event
                          and row.get("wrapper_pid") == pid),
        args.ack_wait_s, paths["detach_log"],
        "detached pid %d (log %s)" % (worker.pid, paths["detach_log"]),
        "this call's %s (its wrapper_pid the worker's)" % event, who="codex-lane.py")
    if args.no_wait or code not in (0, lane.EXIT_UNCONFIRMED):
        return code          # --no-wait's outcome, or a worker that exited before acknowledging
    return worker.wait()     # the waiting form stays with its worker and takes its exit code


def print_dry_run(prep, line):
    # The class and the sandbox first (register 2026-09-23 18:0x: a read-only sandbox sat unseen
    # among forty dry-run lines while a verifier needed to write).
    print("class: %s · sandbox: %s%s" % (line["class"], prep["sandbox"],
                                          " (--read-only)" if prep.get("read_only") else ""))
    print("command:")
    print("  " + " ".join(shlex.quote(part) for part in prep["command"]))
    print("cwd: %s · sandbox: %s · writes: %s · add-dirs: %s"
          % (prep["cwd"], prep["sandbox"], prep["writes"] or "none", prep["add_dirs"] or "none"))
    print("prompt: %d bytes (definition + core + addendum + brief) on stdin" % line["prompt_bytes"])
    print("controls checked: %s" % json.dumps(prep["controls"]))
    if prep.get("controls_pending"):
        print("controls pending (checked at the close, on this pass's report): %s"
              % json.dumps(prep["controls_pending"]))
    if prep.get("inputs"):
        print("inputs checked: %s" % json.dumps(prep["inputs"]))
    if prep.get("staged_copy_token"):
        print("%s substituted %d time(s) with %s" % (lane.STAGED_TOKEN, prep["staged_copy_token"],
                                                     prep["cwd"]))
    if prep.get("staged_declarations"):
        print("declarations delivered as the staged copy: %s" % json.dumps(prep["staged_declarations"]))
    print("record line (%s):" % prep["paths"]["record"])
    print("  " + json.dumps(line))


def a3_begin(args, prep, line, session=None):
    ctx = context_for(args, prep, {"session_id": session, "open_line": line})
    owner = lane.a3_current(ctx["record"], args.run, args.lane)
    if owner is None:
        raise lane.A3Premise("publication requires a lifetime owner")
    transformations = ["universal newline decoding", "strip surrounding whitespace", "append final newline"]
    if prep.get("staged_declarations") or prep.get("staged_copy_token"):
        transformations.append({"path_substitutions": prep.get("staged_declarations"),
                                "staged_copy_token": prep.get("staged_copy_token")})
    owner.begin(ctx, line, owner.source_bytes, prep["brief"].strip() + "\n", transformations)


def context_for(args, prep, extra=None):
    paths = prep["paths"]
    ctx = {"record": paths["record"], "run": args.run, "lane": args.lane, "cls": args.cls,
           "model": args.model, "effort": args.effort, "command": prep["command"],
           "cwd": prep["cwd"], "env": prep["env"], "prompt": prep["prompt"],
           "events": paths["events"], "stderr": paths["stderr"], "report": paths["report"],
           "deadline": args.deadline_s, "silence": args.silence_s,
           "report_words": args.report_words, "format": args.format, "viewer": args.viewer,
           "detached": bool(args.as_worker), "controls_pending": prep.get("controls_pending") or []}
    if extra:
        ctx.update(extra)
    return ctx


@lane.a3_entry("codex")
def cmd_spawn(args):
    lane.require_lane_id(args.lane)
    paths = store_paths(args.run, args.lane, args.record)
    lane.require_new_lane_id(args.lane, paths["record"])
    if not args.as_worker and not getattr(args, "source_pass", None):   # as lane.py's cmd_spawn
        lane.decisions_spawn_check(paths["record"], args.run, args.lane, who="codex-lane.py",
                                   dry_run=args.dry_run)
    destinations = [paths[key] for key in ("report", "prompt", "input_dir", "events", "stderr")]
    empty_stages = []
    # The detached caller owns its log and stage; the worker rechecks its other destinations.
    if not args.as_worker:
        if args.detach:
            destinations.append(paths["detach_log"])
        if args.stage_from:
            stage = os.path.join(paths["store"], "%s-cwd-%s" % (args.run, args.lane))
            destinations.append(stage)
            empty_stages.append(stage)
    lane.require_absent_paths(destinations, empty_dirs=empty_stages)
    args.model = args.model or DEFAULT_MODEL
    args.effort = resolve_spawn_effort(args)
    if not args.as_worker:
        lane.closed_run_warning(store_paths(args.run, args.lane, args.record)["record"],
                                who="codex-lane.py")
    prep = prepare(args)             # a refusal removes the attempt's staged copy before it exits
    stage = prep.get("stage_owner")
    # Until its lane-open is written the copy is this attempt's, so a stop anywhere before that line
    # (an interrupt, a crash) releases it, as prepare's own handler does (review CR-B4L finding 8).
    # `settled` marks the paths that release it themselves, or hand it to the recorded lane.
    settled = False
    try:
        if not args.as_worker and not getattr(args, "source_pass", None):
            lane.item_warning(paths["record"], args.item, who="codex-lane.py")
        if args.detach and not args.dry_run:
            # Every premise ran in the caller's terminal, the staged copy's included, on a real copy.
            # That copy is the caller's: it goes before the worker starts, and the worker makes and
            # checks its own, so no copy is ever owned by two processes.
            settled = True
            left = stage.release() if stage is not None else None
            if left:
                die("before the worker starts, %s" % leftover_text(stage, left))
            return detach(args)
        paths = prep["paths"]
        line = open_line(args, prep)
        if args.dry_run:
            print_dry_run(prep, line)
            # The dry run checked the real copy; it leaves nothing behind it. An emptied stage whose
            # directory will not go is the named premise it has been since the stage guard (critic
            # fold, 2026-09-16): exit 2, no record, the empty stage reusable.
            settled = True
            left = stage.release() if stage is not None else None
            if left:
                if stage.left_empty() and not stage.lock_refused:
                    die("cannot remove empty dry-run stage %s: %s — the stage stays empty, and a spawn "
                        "under this lane id reuses it" % (stage.dest, left))
                die("the dry run's %s" % leftover_text(stage, left))
            return 0
        a3_begin(args, prep, line)
        lane.append_record(paths["record"], line)   # from here the staged copy is the recorded lane's
        settled = True
    except BaseException:
        if not settled:
            release_or_say(stage)
        raise
    try:
        lane.write_atomic(paths["prompt"], prep["prompt"])
        os.makedirs(paths["input_dir"], exist_ok=True)
        brief_abs = os.path.abspath(args.brief)
        copy = os.path.join(paths["input_dir"], "%s-brief-%s.md" % (args.run, args.lane))
        if os.path.realpath(brief_abs) != os.path.realpath(copy):
            shutil.copyfile(brief_abs, copy)
    except OSError as exc:
        die("the run store is not writable (%s)" % exc)
    return run_lane(context_for(args, prep))


def latest_session(record_path, lane_id):
    if not os.path.isfile(record_path):
        die("no run record at %s" % record_path)
    session, opened = None, None
    for event in lane.load_record(record_path):
        if event.get("lane") != lane_id:
            continue
        if event.get("event") == "lane-open":
            opened = event
        if event.get("event") in ("lane-session", "lane-closed") and event.get("session_id"):
            session = event["session_id"]
    return session, opened


def recorded_stage_sources(record_path, lane_id, stage_dir):
    """The sources a lane's staged copy mirrors by its record, oldest first (review CR-B4L2 finding
    2): the lane-open's --stage-from, then the source of each later lane-resumed whose refresh copied
    into that same copy (`stage.refreshed.copied`). A refresh that only counted (a dry run, a
    detached caller) changed nothing and is passed over, as is a line naming another stage
    directory; a source met again moves to its latest place. What the record never saw is not among
    them: a refresh whose resume was refused after it copied leaves no line."""
    want = os.path.realpath(stage_dir)
    sources = []

    def same_stage(stage):
        return isinstance(stage.get("stage_dir"), str) and os.path.realpath(stage["stage_dir"]) == want

    for event in lane.load_record(record_path):
        if event.get("lane") != lane_id:
            continue
        stage = event.get("stage") if isinstance(event.get("stage"), dict) else None
        kind = event.get("event")
        if kind == "lane-open":
            del sources[:]
        elif kind != "lane-resumed" or not stage:
            continue
        elif not (isinstance(stage.get("refreshed"), dict) and stage["refreshed"].get("copied") is True):
            continue
        if stage and same_stage(stage) and isinstance(stage.get("staged_from"), str) and stage["staged_from"]:
            real = os.path.realpath(stage["staged_from"])
            sources[:] = [s for s in sources if s != real] + [real]
    return sources


def beat_premises(args, records):
    """What a beat refuses beyond a resume's own premises, each exit 2 and nothing written: a
    brief, a stage refresh or a worker beside --beat; a lane still running; a close outside
    lane.py's BEAT_EXITS; a window past lane.py's RESUME_WINDOW_S from the lane's last call
    (its close, or a later successful beat). Returns (age_s, age_src, the close)."""
    if args.brief:
        die("--beat takes no --brief: the beat's prompt is the fixed line %r" % lane.BEAT_PROMPT)
    if args.stage_from or args.detach:
        die("--beat takes no --stage-from and no --detach: one bounded call under the spawn's "
            "own configuration")
    opened, start, spawned, close = lane_watch_state(records, args.lane)
    if start is None:
        die("lane %s/%s is unknown in the record" % (args.run, args.lane))
    if close is None:
        die("lane %s/%s has no lane-closed after its latest start: a beat re-enters a finished "
            "lane; `watch` it first" % (args.run, args.lane))
    cls = close.get("exit_class")
    if cls not in lane.BEAT_EXITS:
        die("lane %s/%s closed %s: a beat re-enters only a close in %s"
            % (args.run, args.lane, cls or "unstated", "/".join(lane.BEAT_EXITS)))
    last = lane.parse_ts(close.get("ts"))
    if last is None:
        die("lane %s/%s: lane-closed carries no parseable ts (%r)"
            % (args.run, args.lane, close.get("ts")))
    age_src = "lane-closed ts"
    close_index = next((i for i, r in enumerate(records) if r is close), len(records))
    for r in records[close_index + 1:]:
        if r.get("lane") != args.lane or r.get("event") != "hold-beat" or r.get("ok") is not True:
            continue
        t = lane.parse_ts(r.get("ts"))
        if t is not None and t > last:
            last, age_src = t, "hold-beat ts"
    age = time.time() - last
    if age > lane.RESUME_WINDOW_S:
        die("lane %s/%s: last call %.0f min ago (%s), over the %d-minute resume window: nothing "
            "is warm to beat" % (args.run, args.lane, age / 60.0, age_src,
                                 lane.RESUME_WINDOW_S // 60))
    return round(age, 1), age_src, close


@lane.a3_entry("codex")
def cmd_resume(args):
    record = store_paths(args.run, args.lane, args.record)["record"]
    session, opened = latest_session(record, args.lane)
    if opened is None:
        die("lane %s/%s has no lane-open line" % (args.run, args.lane))
    if not session:
        die("lane %s/%s has no recorded Codex session id to resume" % (args.run, args.lane))
    # A beat in flight owns the thread until it returns (critic F4, 2026-09-17): the session
    # claim is lane.py's advisory lock, shared by both wrappers, so a Claude beat and a Codex
    # resume cannot cross either. This is the early reading; the claim is taken below.
    beat_marker = lane.beat_marker_path(record, args.run, args.lane)
    holder, holder_kind = lane.session_holder(beat_marker)
    if holder is not None:
        die("lane %s/%s: a held-lane %s is in flight (%s, lock %s): a second call on one "
            "thread is the two-processes-on-one-session fault — wait for the call (bounded by %d s) or, if "
            "that process is wedged, end it and the kernel releases its lock"
            % (args.run, args.lane, holder_kind, lane.holder_text(holder),
               lane.session_lock_path(beat_marker), lane.BEAT_TIMEOUT_S))
    beat = bool(getattr(args, "beat", False))
    if beat:
        age_s, age_src, close = beat_premises(args, lane.load_record(record))
        if args.codex is None:
            recorded = opened.get("executable")   # the spawn's own runtime, as recorded
            if isinstance(recorded, str) and os.access(recorded, os.X_OK):
                args.codex = recorded
    elif not args.brief:
        die("--brief is required (the no-work form is resume --beat)")
    else:
        if not args.as_worker:
            lane.decisions_spawn_check(record, args.run, args.lane, who="codex-lane.py", verb="resume",
                                       dry_run=args.dry_run)
        resume_paths(args)  # before refresh_stage can modify the staged copy, or detach can write a log
    if not beat and args.expect_usd is None:
        previous = lane.a3_latest(record, args.run, args.lane)
        if previous:
            args.expect_usd = previous.get("input", {}).get("estimate")
            args.a3_estimate_source = previous["pass_id"]
    if not args.grant:
        args.grant = list(opened.get("grants") or [])
    if args.routing is None:
        args.routing = opened.get("routing_path")
    if args.reason is None:
        args.reason = opened.get("reason")
    if not (args.choice_reason or "").strip():
        args.choice_reason = opened.get("choice_reason")
    # Re-declare what the spawn chose unless this resume passes its own: the model, the effort and
    # the --config overrides, read back from the lane-open (register 2026-09-13 04:11).
    carried = {}
    if args.model is None:
        args.model = opened.get("model") or DEFAULT_MODEL
        carried["model"] = args.model
        if args.model not in KNOWN_MODELS:
            args.any_model = True        # the spawn was allowed it; a resume re-declares, never re-judges
    if args.effort is None:
        args.effort = opened.get("effort") or LEGACY_RESUME_EFFORT
        if not opened.get("effort"):
            sys.stderr.write("codex-lane.py: lane-open has no effort; using the historical resume "
                             "fallback %s\n" % LEGACY_RESUME_EFFORT)
        carried["effort"] = args.effort
    if args.config is None:
        extra, source = recorded_config_extra(opened)
        args.config = extra
        carried["config"], carried["config_src"] = extra, source
        if source.startswith("none:"):
            sys.stderr.write("codex-lane.py: %s; no --config carried onto the resume\n"
                             % source[len("none:"):].strip())
    # The delegation pair is re-declared like the model and the effort (register 2026-09-30 18:22;
    # the beat's carry of 2026-09-17, now every resume's): with neither flag, the lane-open's regime
    # and its source travel together, so an old source is never joined to a new regime; a complete
    # explicit pair wins, and one flag alone is refused by the resolver, which wants both.
    pair_carried = False
    if not args.delegation and not args.delegation_src:
        mode, mode_src = opened.get("mode"), opened.get("mode_src")
        if mode in lane.REGIMES and mode_src in ("head", "owner"):
            args.delegation, args.delegation_src = mode, mode_src
            carried["delegation"] = "%s (%s)" % (mode, mode_src)
            pair_carried = True
    # Resolved here, before the stage refresh and any write or process: a partial pair, or no
    # usable recorded pair while the Settings line is unresolved, refuses with nothing started.
    lane.resolve_delegation(args)
    if opened.get("read_only") and (args.write or args.stage_writable):
        die("lane %s/%s was spawned --read-only, and a resume adds no write scope to it: spawn a "
            "fresh lane for a writable pass" % (args.run, args.lane))
    if args.stage_from:
        # the lane's own staged copy, refreshed in place (register 2026-09-11 23:37)
        args.cwd = refresh_stage(args, opened, copy=not (args.detach or args.dry_run))
    # A resumed staged pass resolves `<<STAGED_COPY>>` to its recorded copy: the stage the
    # lane-open names, where that stage is the lane's recorded cwd.
    stage_rec = opened.get("stage") if isinstance(opened.get("stage"), dict) else {}
    recorded_dir, recorded_cwd = stage_rec.get("stage_dir"), opened.get("cwd")
    if isinstance(recorded_dir, str) and isinstance(recorded_cwd, str) and os.path.isdir(recorded_dir) \
            and os.path.realpath(recorded_dir) == os.path.realpath(recorded_cwd):
        args.staged_copy = os.path.realpath(recorded_dir)
        # The sources the copy mirrors, whose paths a follow-up brief's declarations are read as the
        # copy's (review CR-B4L finding 2): the lane-open's and every recorded refresh's, oldest
        # first, then this resume's own refresh (review CR-B4L2 finding 2: the lane-open's alone
        # forgot a later refresh's source). A refresh this call does not perform (a detached
        # caller's, whose worker refreshes, or a dry run's) leaves the copy behind its source, so
        # that call checks the source as written and the worker, on the refreshed copy, maps.
        current = not (args.stage_from and (args.detach or args.dry_run))
        if current:
            sources = recorded_stage_sources(record, args.lane, recorded_dir)
            own = (getattr(args, "stage_report", None) or {}).get("staged_from") if args.stage_from else None
            if isinstance(own, str) and own:
                own = os.path.realpath(own)
                sources = [s for s in sources if s != own] + [own]
            args.staged_sources = sources
    if not args.cwd:
        args.cwd = opened.get("cwd")
    if not args.write and opened.get("writes"):
        args.write = list(opened["writes"])
    if args.stage_from and args.stage_writable and args.cwd not in (args.write or []):
        args.write = list(args.write or []) + [args.cwd]
    if args.cls is None:
        args.cls = opened.get("class")
    prep = prepare(args, resume_id=session, beat=beat)
    if pair_carried:
        # lane-resumed records the pair this call used and where it came from
        prep["mode"] = (args.delegation, args.delegation_src, "the lane-open's recorded pair (carried)")
    # The configuration this call runs under against the spawn's (the held-lane beat): a beat
    # that differs is refused before any process starts; a resume records the comparison.
    config_sha = config_hash(prep["command"])
    recorded_sha = opened.get("config_sha256")
    config_src = "lane-open" if isinstance(recorded_sha, str) and recorded_sha else \
        "unrecorded (a lane-open from before config_sha256)"
    config_match = (config_sha == recorded_sha) if isinstance(recorded_sha, str) and recorded_sha \
        else None
    if beat:
        if config_match is False:
            die("lane %s/%s: the resolved configuration differs from the lane-open's (config_sha256 "
                "%s against the recorded %s): a beat carries the spawn's configuration byte for "
                "byte or it is a rewrite, not a beat — nothing started"
                % (args.run, args.lane, config_sha[:12], str(recorded_sha)[:12]))
        if args.dry_run:
            print("command:")
            print("  " + " ".join(shlex.quote(part) for part in prep["command"]))
            print("prompt: %r on stdin · config_sha256 %s (%s) · no report, no pass file"
                  % (lane.BEAT_PROMPT, config_sha, config_src))
            return 0
        with lane.hold_beat_marker(beat_marker):
            return run_beat(context_for(args, prep, {
                "session_id": session, "config_sha256": config_sha, "config_src": config_src,
                "config_match": config_match, "age_s": age_s, "age_src": age_src,
                "carried_from_open": carried,
                "beat_n": 1 + sum(1 for r in lane.load_record(record)
                                  if r.get("lane") == args.lane and r.get("event") == "hold-beat")}))
    if args.detach and not args.dry_run:
        return detach(args)
    paths = prep["paths"]
    line = open_line(args, prep, event="lane-resumed",
                     extra={"session_id": session, "resumed_from": session,
                            "carried_from_open": carried, "report": paths["report"],
                            "config_match": config_match, "config_src": config_src,
                            "read_only": bool(opened.get("read_only"))})
    if args.dry_run:
        print_dry_run(prep, line)
        return 0
    # The thread is claimed HERE, immediately before the first line this resume writes, and not
    # only checked before the preparation above (critic finding 2 of review): a beat that took
    # the session while this call was preparing must turn it back at the door, whichever of the
    # two arrived first. The advisory lock is lane.py's, so a Claude beat and a Codex resume
    # cannot cross either.
    with lane.hold_session(beat_marker, "resume",
                           "a beat holds the lane's session; wait for it (bounded by %d s) and "
                           "resume again" % lane.BEAT_TIMEOUT_S):
        a3_begin(args, prep, line, session)
        lane.append_record(paths["record"], line)
        lane.write_atomic(paths["prompt"], prep["prompt"])
        return run_lane(context_for(args, prep,
                                    {"session_id": session, "spawn_event": "lane-respawned",
                                     "close_extra": {"resumed_from": session}}))


def run_beat(ctx):
    """The held-lane beat (handsoff.py hold, 2026-09-17): the thread resumed and asked for one
    word under the spawn's own configuration. No report, no pass file, no lane-resumed or
    lane-closed line; the beat's events append to the lane's events log and its one record
    line is `hold-beat`, carrying the turn's usage. Bounded by lane.py's BEAT_TIMEOUT_S; a
    non-zero exit, a limit or a failed turn is recorded with ok false, never retried here. The
    keep-awake process starts beside the codex process (lane.start_awake) and its state rides on
    the hold-beat line (lane.beat_awake_fields)."""
    record, run, lane_id = ctx["record"], ctx["run"], ctx["lane"]
    started = time.time()
    owner = lane.a3_begin_beat(ctx, "codex")
    by = os.environ.get(lane.BEAT_BY_ENV) or "hand"
    base = {"run": run, "lane": lane_id, "event": "hold-beat", "harness": HARNESS,
            "session_id": ctx.get("session_id"), "class": ctx["cls"], "model": ctx["model"],
            "effort": ctx["effort"], "n": ctx["beat_n"], "by": by, "prompt": lane.BEAT_PROMPT,
            "config_sha256": ctx["config_sha256"], "config_src": ctx["config_src"],
            "config_match": ctx["config_match"], "last_call_age_s": ctx["age_s"],
            "last_call_src": ctx["age_src"], "carried_from_open": ctx.get("carried_from_open"),
            "total_cost_usd": None, "cost_src": "codex-plan", "wrapper_pid": os.getpid()}
    try:
        owner.process = process = subprocess.Popen(ctx["command"], cwd=ctx["cwd"], env=ctx["env"], text=True,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
    except OSError as exc:
        owner.start_failed()
        owner.capture({"refusal_count": 0, "refusal_evidence": []}, settled=True)
        owner.finish_beat(dict(base, ts=now(), ok=False, exit_class="spawn-failed",
                               exit_code=3, process_exit=None, duration_s=0.0,
                               usage=None, error=str(exc)))
        sys.stderr.write("codex-lane.py: the beat could not start the lane process: %s\n" % exc)
        return 3
    owner.record_child(process)
    # The keep-awake process beside the beat's codex process (owner decision of 2026-10-09: each
    # helper keeps the host awake while it runs, a beat included; lane.start_awake), its state on
    # the one hold-beat line below.
    awake, awake_fields = lane.start_awake(process.pid)
    killed_by = None
    try:
        stdout, stderr = process.communicate(input=ctx["prompt"], timeout=lane.BEAT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        stdout, stderr = lane.kill_group(process)
        killed_by = "deadline"
    duration = round(time.time() - started, 1)
    lines = (stdout or "").splitlines(keepends=True)
    try:
        with open(ctx["events"], "a", encoding="utf-8") as handle:   # the lane's own event stream
            handle.writelines(lines)
    except OSError as exc:
        sys.stderr.write("codex-lane.py: the beat's events were not appended to %s (%s)\n"
                         % (ctx["events"], exc))
    parsed = parse_events(lines)
    evidence = lane.a3_native_evidence("".join(lines), "codex")
    evidence["source"] = ctx["events"]
    evidence["process_exit"] = process.returncode
    evidence["streams_complete"] = not getattr(process, "_a3_stream_incomplete", False)
    evidence = owner.capture(evidence, settled=evidence["streams_complete"])
    parsed.update(evidence)
    decision = parse_close_events(lines)
    exit_class, error = classify(killed_by, decision, process.returncode, parsed["last_message"])
    ok = exit_class == "completed"
    usage = dict(parsed["usage"], calls=parsed["turns_completed"])
    # cached_input_tokens is part of input_tokens. Sum each completed turn's own
    # usage rather than treating a resumed invocation as a cumulative thread total.
    # Retain the per-turn figures beside the sum. A beat's cached share measures
    # that invocation; cache retention at a future beat interval is unmeasured.
    prompt = usage["input_tokens"]
    usage["cache_read_share"] = round(usage["cached_input_tokens"] / prompt, 2) if prompt else None
    usage["turns"] = parsed["turn_usage"]
    usage_basis = ("summed over this invocation's %d turn.completed event(s); that is this "
                   "invocation's own turn and not a running total over the thread, so the cached "
                   "share is this call's own. The prompt cache's RETENTION at a beat's interval "
                   "stays unmeasured: a rewrite on a Codex beat measures that retention"
                   % parsed["turns_completed"])
    line = dict(base, ts=now(), session_id=parsed["session_id"] or ctx.get("session_id"), ok=ok,
                exit_class=exit_class, exit_code=0 if ok else EXIT_CODES.get(exit_class, 3),
                process_exit=process.returncode, duration_s=duration,
                num_turns=parsed["turns_completed"], usage=usage,
                usage_src="turn.completed usage (this invocation's own turns)",
                usage_basis=usage_basis,
                usage_complete=(not killed_by) and parsed["turns_completed"] > 0,
                reply=parsed["last_message"][:80], error=error, errors=parsed["errors"][:5],
                events=ctx["events"], events_records=parsed["records"],
                limit_signal=(error if exit_class == "limit" else None), killed_by=killed_by,
                stderr_tail=(stderr or "").strip()[-400:] or None)
    line.update(lane.beat_awake_fields(awake_fields))
    line = owner.finish_beat(line)
    ok, exit_class = line["ok"], line["exit_class"]
    summary = ("beat %s/%s: codex %s·%s · %s · %.1f s · cached %s · write %s · input %s · "
               "output %s · config %s · %s"
               % (run, lane_id, ctx["model"], ctx["effort"],
                  "ok" if ok else "FAILED (%s)" % exit_class, duration,
                  usage["cached_input_tokens"], usage["cache_write_input_tokens"],
                  usage["input_tokens"], usage["output_tokens"],
                  {True: "match", False: "MISMATCH", None: "unrecorded"}[ctx["config_match"]], by))
    if ctx["format"] == "json":
        print(json.dumps({"summary": summary, "beat": line}))
    else:
        print(summary)
        if line.get("notice"):
            print(lane.a3_notice_text(line["notice"]))
    lane.reap_awake(awake)
    return line["exit_code"]


def lane_watch_state(records, lane_id):
    """(opened, start, spawned, close) for one lane, in record order: `start` is its latest
    lane-open or lane-resumed, `spawned` the latest lane-spawned or lane-respawned after it, and
    `close` the first lane-closed after it (None while that call runs)."""
    opened = start = spawned = close = None
    for event in records:
        if event.get("lane") != lane_id:
            continue
        kind = event.get("event")
        if kind == "lane-open":
            opened = event
        if kind in ("lane-open", "lane-resumed"):
            start, spawned, close = event, None, None
        elif kind in ("lane-spawned", "lane-respawned") and start is not None:
            spawned = event
        elif kind == "lane-closed" and start is not None and close is None:
            close = event
    return opened, start, spawned, close


def print_close(args, opened, start, close):
    """The close's summary line and report, with a preview only on explicit request."""
    report_text = ""
    path = close.get("report")
    if isinstance(path, str) and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                report_text = handle.read().strip()
        except OSError:
            report_text = ""
    ctx = {"run": args.run, "lane": args.lane, "format": args.format,
           "report_words": args.report_words,
           "model": close.get("model") or start.get("model") or (opened or {}).get("model"),
           "effort": close.get("effort") or start.get("effort") or (opened or {}).get("effort")}
    emit_summary(ctx, close, report_text)
    code = close.get("exit_code")
    return code if isinstance(code, int) and not isinstance(code, bool) else \
        EXIT_CODES.get(close.get("exit_class"), 3)


def cmd_wait(args):
    """Background wait: the watch loop, without its still-running time bound."""
    args.max_wait_s = 0
    return cmd_watch(args)


def cmd_watch(args):
    """Block until the lane's next close: the first lane-closed after its latest lane-open or
    lane-resumed. A3 publishes a deduplicated orphan observation; it never claims close authority."""
    record = store_paths(args.run, args.lane, args.record)["record"]
    result = lane.a3_watch(record, args.run, args.lane, args.format, args.report_words,
                           args.max_wait_s, args.poll_s, args.appear_s,
                           silence=args.silence_s,
                           renderer=lambda journal: print_close(
                               args, journal["start"], journal["start"], lane.a3_visible_close(journal)))
    if result is not None:
        return result
    began, running_seen, orphan_since = time.time(), False, None
    while True:
        waited = time.time() - began
        records = lane.load_record(record) if os.path.isfile(record) else []
        opened, start, spawned, close = lane_watch_state(records, args.lane)
        if start is None:
            if waited < args.appear_s:
                time.sleep(0.5)
                continue
            if not os.path.isfile(record):
                die("no run record at %s" % record)
            die("lane %s/%s is unknown in %s (no lane-open or lane-resumed)"
                % (args.run, args.lane, record))
        if close is not None:
            if running_seen:
                return print_close(args, opened, start, close)
            if waited < args.appear_s:
                time.sleep(0.5)          # a just-detached resume may not have written its line yet
                continue
            print_close(args, opened, start, close)
            die("lane %s/%s is already closed (%s at %s): a watch returns on the close after the "
                "latest open or resume, and none has followed it"
                % (args.run, args.lane, close.get("exit_class"), close.get("ts")))
        running_seen = True
        wrapper = (spawned or {}).get("wrapper_pid") or start.get("wrapper_pid")
        if wrapper and lane.pid_alive(wrapper) is False:
            orphan_since = orphan_since or time.time()
            # the wrapper writes its close as it exits: two ticks and the kill grace before orphaned
            if time.time() - orphan_since > 2 * args.poll_s + KILL_GRACE_S:
                print("orphaned: lane %s/%s's wrapper pid %s has gone and no lane-closed follows its "
                      "%s; legacy pass has no A3 ownership; explicit head reconciliation required"
                      % (args.run, args.lane, wrapper, start.get("event")))
                return 3
        else:
            orphan_since = None
        if args.max_wait_s and waited > args.max_wait_s:
            print("still-running: lane %s/%s after %.0f s" % (args.run, args.lane, waited))
            return lane.EXIT_STILL_RUNNING
        time.sleep(args.poll_s if spawned is not None else min(args.poll_s, 0.5))


def cmd_kill(args):
    return lane.a3_kill(args, "codex")


# ---------------------------------------------------------------------- parser -------------

def add_common(parser, spawn=True):
    parser.add_argument("--expect-usd", type=float)
    parser.add_argument("--no-swap", action="store_true")
    parser.add_argument("--source-pass", help=argparse.SUPPRESS)
    parser.add_argument("--source-disposition", help=argparse.SUPPRESS)
    parser.add_argument("--grant", action="append", default=[])
    parser.add_argument("--routing", help="routing table for omitted spawn effort and Claude family "
                        "movement (default: routing.json beside this script)")
    parser.add_argument("--run", required=True)
    parser.add_argument("--lane", required=True, help="lane id; spawn needs a fresh casefold identity and unused destinations; only -pass<n> endings are reserved, in any letter case")
    parser.add_argument("--class", dest="cls", required=spawn, default=None,
                        help="the role definition in .claude/agents/<class>.md")
    parser.add_argument("--brief", required=spawn, default=None,
                        help="the brief file; on resume REQUIRED unless --beat")
    if not spawn:
        parser.add_argument("--beat", action="store_true",
                            help="the held-lane beat (handsoff.py hold): the lane-open's "
                                 "configuration byte for byte, the fixed no-work line on stdin, "
                                 "no report, no pass file, one hold-beat record line")
    parser.add_argument("--cwd", default=None, help="Codex's working root (-C); required on spawn "
                        "unless --stage-from is given")
    parser.add_argument("--stage-from", default=None, help="copy this directory (minus --stage-exclude "
                        "names and .git) into the run store and use the copy as the cwd: a blind copy")
    parser.add_argument("--stage-exclude", action="append", help="a name or glob to leave out of the "
                        "staged copy (repeatable)")
    parser.add_argument("--stage-writable", action="store_true", help="make the staged copy a write "
                        "directory (workspace-write on the copy alone)")
    if spawn:
        parser.add_argument("--item", default=None, metavar="ITEM", type=lane.item_name,
                            help="the run item this lane works on, recorded on lane-open: it starts "
                                 "the item's bar and the console files the lane there")
        parser.add_argument("--read-only", action="store_true",
                            help="run the lane read-only on purpose: a %s class is refused without "
                                 "--stage-writable or --write unless this says so; refused beside "
                                 "either, and recorded so a resume adds no write scope"
                                 % " or ".join(WRITE_CLASSES))
    parser.add_argument("--write", action="append", help="a directory the lane may write (repeatable); "
                        "the cwd must lie inside one of them")
    parser.add_argument("--reason", default=None, help="REQUIRED on spawn: why a lane rather than the "
                        "head, opening with the instrument-rule letter (a)–(d)")
    parser.add_argument("--choice-reason", default=None, help="REQUIRED on spawn: why this model and effort")
    parser.add_argument("--model", default=None, help="default %s on spawn; on resume the "
                        "lane-open's model" % DEFAULT_MODEL)
    parser.add_argument("--any-model", action="store_true", help="allow a model outside the known catalogue")
    parser.add_argument("--effort", default=None, help="%s (on spawn, the class's anchor in "
                        "routing.json; on resume, the lane-open's effort)" % "|".join(EFFORTS))
    parser.add_argument("--search", action="store_true", help="web_search = live (default disabled)")
    parser.add_argument("--network", action="store_true", help="shell network inside workspace-write")
    parser.add_argument("--schema", help="a JSON Schema file for the final message (--output-schema)")
    parser.add_argument("--config", action="append", help="an extra -c key=value override "
                        "(repeatable); on resume the lane-open's extras unless any is given")
    parser.add_argument("--context-window", type=int, default=CONTEXT_WINDOW)
    parser.add_argument("--compact-limit", type=int, default=COMPACT_LIMIT)
    parser.add_argument("--codex", help="the codex executable (default: `codex` on PATH)")
    parser.add_argument("--append-core", help="a lane core file instead of the home's copy")
    parser.add_argument("--deadline-s", type=float, default=DEFAULT_DEADLINE_S)
    parser.add_argument("--silence-s", type=float, default=DEFAULT_SILENCE_S,
                        help="stall bound on the event stream; 0 disables")
    parser.add_argument("--report-words", type=int, default=REPORT_WORDS)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--viewer", choices=("terminal", "none"), default=None)
    parser.add_argument("--record", help="spawn record path (default: the run store)")
    parser.add_argument("--plant", default=None,
                        help="a test device the owner has explicitly permitted, recorded on the lane's record; "
                             "leave empty otherwise (CLAUDE.md section 12)")
    parser.add_argument("--reading-list", default=None)
    parser.add_argument("--delegation", choices=lane.REGIMES, default=None,
                        help="the run's regime, with --delegation-src (the pair together)%s"
                             % ("" if spawn else "; on resume, with neither flag, the lane-open's "
                                "recorded pair is carried and recorded on lane-resumed"))
    parser.add_argument("--delegation-src", choices=("head", "owner"), default=None)
    parser.add_argument("--detach", action="store_true",
                        help="run the call in a worker that survives the caller, once every premise "
                             "has passed in the caller (a refusal exits 2 and starts no worker)")
    parser.add_argument("--no-wait", action="store_true",
                        help="with --detach: wait up to --ack-wait-s for THIS call's own %s (its "
                             "wrapper_pid the worker's), then: acknowledged, print `detached pid N "
                             "(log L)` and exit 0; the worker exits first, print its log tail and "
                             "exit non-zero; the worker lives but no acknowledgement arrives in time, "
                             "or the record cannot be read, print `detached pid N, unconfirmed after "
                             "S s` and exit %d, the worker left running"
                             % ("lane-open" if spawn else "lane-resumed", lane.EXIT_UNCONFIRMED))
    parser.add_argument("--ack-wait-s", type=float, default=lane.ACK_WAIT_S,
                        help="with --detach: the acknowledgement bound in seconds (default %d, "
                             "lane.py's; a waiting limit, not a stall controller)" % lane.ACK_WAIT_S)
    parser.add_argument("--as-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")


def build_parser():
    parser = argparse.ArgumentParser(description="spawn a headless Codex (GPT-6 Astra) lane")
    sub = parser.add_subparsers(dest="command", required=True)
    add_common(sub.add_parser("spawn"), spawn=True)
    add_common(sub.add_parser("resume", description="resume a long write cut short by a usage limit, "
                              "with work on disk and checked, or the multi-expert panel's round 2; "
                              "a second pass goes to a fresh helper with a compact hand-off. Reports use "
                              "<run>-report-<lane>-pass<n>.md and prompts use the same suffix, starting at n=2; "
                              "existing report or prompt paths refuse before writes"), spawn=False)
    for command in ("watch", "wait"):
        watch = sub.add_parser(command, help=("wait for the lane's next close (the close after its "
                               "latest open or resume), bounded: still-running (exit %d, not a close) "
                               "after --max-wait-s, %d s by default, and --max-wait-s 0 waits without "
                               "bound; reads the record, writes nothing"
                               % (lane.EXIT_STILL_RUNNING, lane.WATCH_MAX_WAIT_S)
                               if command == "watch" else
                               "background wait without a time bound; return on the latest close or a watcher error"))
        watch.add_argument("--run", required=True)
        watch.add_argument("--lane", required=True)
        watch.add_argument("--record", help="spawn record path (default: the run store)")
        if command == "watch":
            watch.add_argument("--max-wait-s", type=float, default=lane.WATCH_MAX_WAIT_S,
                               help="return still-running (exit %d) after this many seconds (default %d, "
                                    "lane.py's bound; 0 waits without bound)"
                                    % (lane.EXIT_STILL_RUNNING, lane.WATCH_MAX_WAIT_S))
        else:
            watch.set_defaults(max_wait_s=0)
        watch.add_argument("--appear-s", type=float, default=lane.WATCH_APPEAR_S,
                           help="seconds to wait for a just-detached lane's line before calling it "
                                "unknown or closed (default %d)" % lane.WATCH_APPEAR_S)
        watch.add_argument("--poll-s", type=float, default=WATCH_POLL_S,
                           help="seconds between record reads (default %d)" % WATCH_POLL_S)
        watch.add_argument("--report-words", type=int, default=REPORT_WORDS)
        watch.add_argument("--silence-s", type=float, default=0,
                           help="request an owner-consumed silence stop; never interrupt finalisation")
        watch.add_argument("--format", choices=("text", "json"), default="text")
    kill = sub.add_parser("kill")
    kill.add_argument("--run", required=True)
    kill.add_argument("--lane", required=True)
    kill.add_argument("--reason", required=True)
    kill.add_argument("--escalate", action="store_true")
    kill.add_argument("--record")
    lane.a3_add_recover_parser(sub, "codex")
    return parser


@lane.a3_public
def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command in ("spawn", "resume") and args.no_wait and not args.detach:
        die("--no-wait goes with --detach")
    if args.command in ("spawn", "resume") and args.detach:
        lane.require_ack_wait(args.ack_wait_s)
    if args.command == "spawn":
        return cmd_spawn(args)
    if args.command == "resume":
        return cmd_resume(args)
    if args.command == "watch":
        return cmd_watch(args)
    if args.command == "wait":
        return cmd_wait(args)
    if args.command == "recover":
        return args.func(args)
    return cmd_kill(args)


if __name__ == "__main__":
    sys.exit(main())
