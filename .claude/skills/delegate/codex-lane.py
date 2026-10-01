#!/usr/bin/env python3
"""codex-lane.py — spawn a headless Codex lane (GPT-6 Astra by default) that writes the same
run-record lines as a Claude lane, so the console, the hand-off, the supervisor and the meter
read it unchanged. An installed, authenticated Codex CLI is required.

    codex-lane.py spawn  --run ID --lane ID --class CLASS --brief FILE --cwd DIR --reason "(a) WHY" --choice-reason "WHY" [options]
    codex-lane.py resume --run ID --lane ID --brief FILE [--stage-from DIR] [--detach [--no-wait]] [options]
    codex-lane.py resume --run ID --lane ID --beat                (the held-lane beat: no brief, no report)
    codex-lane.py watch  --run ID --lane ID [--max-wait-s N] [--appear-s N] [--poll-s N]
    codex-lane.py kill   --run ID --lane ID --reason WHY

What a spawn does, in order
---------------------------
1. Premise checks, before any record line: `--reason` opens with the instrument-rule letter
   (`lane.require_reason_letter`, shared with lane.py); `--choice-reason` is non-empty (no
   routing row anchors a Codex pick, so every pick carries its reason); the class has a
   definition in `.claude/agents/<class>.md`; the brief exists, is non-empty and its CONTROL+
   lines hit and no line carries a doubled root (`lane.refuse_doubled_root`: a root path embedding
   a second absolute path, or the vault root twice in one path; register 2026-09-09 19:03);
   the cwd is a directory; with `--write`, the cwd lies inside one of the write
   directories (under Codex's `workspace-write` the cwd itself becomes writable, so a cwd outside
   the write set would widen the grant silently); the `codex` executable resolves and answers
   `--version`.
2. The prompt: the class definition's body (Codex has no `--agents`), the lane core the Claude
   lanes carry, a Codex addendum naming what differs (the sandbox is the fence, the final message
   is the report, no progress file, no web search unless granted), then the brief. It goes to
   Codex on stdin (`codex exec -`) and a copy sits in the run store.
3. The `lane-open` line, then the process (`start_new_session`, so a kill reaches the whole
   group), then `lane-spawned` with the pid; a `lane-session` line when `thread.started` names
   the Codex thread; `lane-closed` at the end with the exit class, the token usage summed over
   turns, `total_cost_usd: null` and `cost_src: codex-plan` (usage sits on the ChatGPT plan,
   outside fable-share.py; a null cost is unpriced, never zero).
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
`--ephemeral` (resume needs the session); `ultra` is an accepted wrapper argument; the installed CLI and selected backend must also support it.

Exit classes and codes (aligned with lane.py's EXIT_CODES): `completed` 0 · `stall` 5 ·
`limit` 6 · everything else 3 (`empty`: a turn completed with no report text, the round's
"returns nothing" case; `failed`, `deadline`, `killed`, `spawn-failed`); a premise failure
exits 2 before any record line.

A spawn onto a closed run (the record holds a `run-close` with no later `run-open` or
`run-resume`, whatever else follows it) prints one warning naming the close and proceeds
(`lane.closed_run_warning`; register 2026-09-03).

Resume
------
`resume` continues the recorded Codex thread and re-declares what the spawn chose unless the resume
passes its own: the model, the effort and the `--config` overrides, read back from the lane's
`lane-open` (`model`, `effort`, `config_extra`, which every lane-open records since 2026-09-13; for
an older record the extras are the `config_overrides` entries after the default block, and a list
that does not start with that block carries none, with one line saying so). `lane-resumed` names
what it carried in `carried_from_open` (register 2026-09-13 04:11), so an `ultra` lane spawned with
`--config features.multi_agent=true` is never resumed at the default `max` without it.
`--stage-from DIR` on a resume refreshes the lane's existing staged copy in place (register
2026-09-11 23:37): the cwd path the thread knows is kept, a file present in DIR replaces its copy,
a file only in the copy (the lane's own output) stays, and `lane-resumed` records the counts under
`stage.refreshed`. It is refused, naming the cwd, for a lane whose recorded cwd was never a staged
copy and for a `--cwd` naming another directory. With `--detach` the caller validates and its
worker copies.
Each resumed pass writes `<run>-report-<lane>-pass<n>.md`, n=2 for the first
resume and increasing per recorded resume. The first pass keeps its unsuffixed filename;
`lane-closed.report` and watch name the latest pass's report, preserving earlier reports.
The prompt uses the same per-pass suffix and `prompt_file` retains that pass's bytes. Spawn
reserves only numeric `-pass<n>` lane-id endings in any letter case, and refuses
case-equivalent lane ids in the run record. Historical `-r<n>` and `-resume-<n>` endings are legal. Spawn and resume check destination directory
listings case-insensitively before any write, stage refresh or detached worker, including
directories and dangling symlinks (critic fold, 2026-09-16). Only the lane's exactly spelt,
empty stage directory may be reused; dry runs remove their empty stage before returning. Classification uses the current JSONL response alone; an existing output file
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
names another.
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
`watch --run --lane` blocks until the next close after the latest start or resume, never an old close.
It returns on a `lane-closed`
# References: register 2026-09-10.
that follows the latest `lane-open` or `lane-resumed` for the lane in record order, never on an
earlier close; prints the close's summary line and its whole report by default; and exits
with the close's exit code. A lane already closed when the watch starts waits up to `--appear-s`
for a newer open or resume (a resume issued with `--detach --no-wait` writes its lane-resumed a
moment after it returns), then prints that close and exits 2, as lane.py watch does.
`still-running` exits 8 after `--max-wait-s`; a lane whose recorded wrapper has gone with no close
after it exits 3 and names `kill` as the way to close the record. The watch reads the record and
writes nothing.

Console: with `--detach` the caller opens the run's console before the worker starts, and the
worker runs under `--viewer none` (register 2026-09-09 11:21; the opener itself is handsoff.py's).

Blind reviews: `--stage-from SRC [--stage-exclude PATTERN]...` copies SRC into
`<store>/<run>-cwd-<lane>/` without the excluded names (`.git` always) and makes the copy the
cwd, so a reviewer never has the other reviewers' reports or the head's verdict within reach of
its working tree (critic CR1, finding 3). Reads elsewhere on the disk stay technically possible
under Codex's sandbox and are recorded as `reads: unrestricted`.
"""

import argparse
import filecmp
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True   # importing lane.py must leave no __pycache__ in the skill home (its suite checks)
import lane  # noqa: E402  (the Claude wrapper: shared store, record and premise helpers)

HARNESS = "codex"
DEFAULT_MODEL = "gpt-6-astra"
DEFAULT_EFFORT = "max"
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")   # Codex's ladder for Astra; `ultra` admitted 2026-09-12 (config.toml enabled-reasoning-efforts lists it; the owner's instruction of 22:2x)
KNOWN_MODELS = ("gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")   # the catalogue of 2026-09-08
CONTEXT_WINDOW = 872000          # the catalogue maximum for gpt-6-astra (models_cache.json, 2026-09-08)
COMPACT_LIMIT = 800000           # compact below the window, not at the 272K default
DEFAULT_DEADLINE_S = 14400       # four hours; set by judgement, unmeasured for a new workload; --deadline-s overrides it
DEFAULT_SILENCE_S = 1800         # set by judgement, unmeasured: reasoning at max is quiet for long stretches
POLL_S = 15
KILL_GRACE_S = 5
REPORT_WORDS = None             # The default report is complete; previews require an explicit request.
WATCH_POLL_S = 5                 # set by judgement, unmeasured: one record read per tick; five seconds bounds how late a close is reported
EXIT_CODES = {"completed": 0, "stall": 5, "limit": 6}   # every other class exits 3; premise 2
LIMIT_RE = re.compile(r"usage limit|rate limit|too many requests|quota|\b429\b|limit reached", re.I)
DENIAL_RE = re.compile(r"operation not permitted|permission denied|not permitted by the sandbox|sandbox denied", re.I)
CORE_NAME = "lane-core.md"
# The configuration hash (the held-lane beat, 2026-09-17): the command line less the report path
# pair, the `resume <thread>` pair and the trailing prompt marker, so a spawn, its resumes and
# its beats hash alike when they run the model under one configuration.
CONFIG_DROP_PAIRS = ("-o", "resume")
TURN_USAGE_KEEP = 8             # per-turn usage figures kept on a record line (critic F7, 2026-09-17): a beat is one turn and a resume a handful, so eight entries hold every case seen while bounding the line; set by judgement, unmeasured

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


def resolve_codex(explicit):
    """The executable and its version, recorded on lane-open so one runtime is named per run."""
    path = explicit or shutil.which("codex")
    if not path:
        die("no `codex` executable on PATH and no --codex given")
    path = os.path.realpath(os.path.expanduser(path))
    if not os.access(path, os.X_OK):
        die("codex executable is not runnable: %s" % path)
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30)
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
    """The lane core the Claude lanes carry: the lane home's copy, else the template."""
    if explicit:
        if not os.path.isfile(explicit):
            die("--append-core file not found: %s" % explicit)
        return explicit, lane.read_text(explicit, "the lane core")
    home = lane.default_home()
    for candidate in (os.path.join(home, CORE_NAME), lane.core_source(vault)):
        if os.path.isfile(candidate):
            return candidate, lane.read_text(candidate, "the lane core")
    return None, ""


def in_git_repo(cwd):
    git = shutil.which("git") or "/usr/bin/git"
    try:
        out = subprocess.run([git, "-C", cwd, "rev-parse", "--is-inside-work-tree"],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def stage_copy(args):
    """A blind working copy: SRC minus the excluded names, under the run store, as the cwd."""
    src = real_dir(args.stage_from, "--stage-from")
    paths = store_paths(args.run, args.lane, args.record)
    dest = os.path.join(paths["store"], "%s-cwd-%s" % (args.run, args.lane))
    excludes = [".git"] + list(args.stage_exclude or [])
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    try:
        shutil.copytree(src, dest, symlinks=True, ignore=shutil.ignore_patterns(*excludes))
    except OSError as exc:
        die("staging %s into %s failed: %s" % (src, dest, exc))
    count = sum(len(files) for _, _, files in os.walk(dest))
    args.stage_report = {"staged_from": src, "stage_excludes": excludes, "stage_files": count,
                         "stage_dir": dest}
    if args.dry_run:
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)     # prepare validates this path; cmd_spawn removes it before returning
    return dest


def refresh_stage(args, opened, copy=True):
    """`resume --stage-from`: refresh the lane's existing staged copy in place (register 2026-09-11
    23:37), so a resume reads the source the head repaired rather than its original copy. The path the
    Codex thread knows is kept; a file present in the source replaces its copy; a file only in the
    copy (the lane's own output under --stage-writable) stays. Refused, naming the cwd, for a lane
    whose recorded cwd was never a staged copy and for a --cwd naming another directory; a type
    clash (a directory in the copy where the source has a file) refuses before anything is copied.
    `copy=False` counts without copying (a dry run, or a detached caller whose worker copies)."""
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
    probe = argparse.Namespace(effort=opened.get("effort") or DEFAULT_EFFORT,
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
    """Everything the close line reports, from the JSONL events Codex printed. Every line is
    parsed with json.loads; an unparseable one is counted, never grepped for meaning."""
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


def classify(killed_by, parsed, returncode, report_text):
    """The execution outcome. A task outcome (complete, partial, blocked) is the report's and
    the head verifies it on disk."""
    joined = " ".join(parsed["errors"])
    if killed_by == "deadline":
        return "deadline", "deadline reached"
    if killed_by == "stall":
        return "stall", "silence past the bound"
    if killed_by == "signal":
        return "killed", "wrapper signalled"
    if joined and LIMIT_RE.search(joined):
        return "limit", joined[:300]
    if parsed["turns_failed"] or (parsed["errors"] and not parsed["turns_completed"]):
        return "failed", joined[:300] or "turn failed"
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
        self._lock = threading.Lock()

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
                if self.session_id is None:
                    try:
                        event = json.loads(raw)
                    except ValueError:
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

    def _kill(self, why):
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
        self.process = subprocess.Popen(self.ctx["command"], cwd=self.ctx["cwd"], env=self.ctx["env"],
                                        text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
        self._record({"event": self.ctx.get("spawn_event", "lane-spawned"),
                      "session_id": self.ctx.get("session_id"), "pid": self.process.pid,
                      "wrapper_pid": os.getpid(), "class": self.ctx["cls"],
                      "detached": bool(self.ctx.get("detached")),
                      "mechanism": "codex-lane.py headless, model %s, effort %s"
                                   % (self.ctx["model"], self.ctx["effort"])})
        threads = [threading.Thread(target=self._read_stdout, daemon=True),
                   threading.Thread(target=self._read_stderr, daemon=True),
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
    usage = close.get("usage") or {}
    print("lane %s/%s · codex %s·%s · %s · %ss · %s turns · in %s (cached %s) · out %s · report %s (%s words)%s"
          % (ctx["run"], ctx["lane"], ctx["model"], ctx["effort"], close.get("exit_class"),
             close.get("duration_s"), close.get("num_turns"), usage.get("input_tokens"),
             usage.get("cached_input_tokens"), usage.get("output_tokens"), close.get("report"),
             close.get("report_words"),
             (" · error: %s" % close.get("error")) if close.get("error") else ""))
    shown, n_shown, n_total, cut = lane.cut_words(report_text, ctx["report_words"])
    if shown:
        print(shown)
    if cut:
        print("(%d of %d words shown; full text: %s)" % (n_shown, n_total, close.get("report")))


def run_lane(ctx):
    """Shared by spawn and resume: the process, the events, the close line, the summary."""
    lane.open_console_for_spawn(ctx["run"], ctx.get("viewer"))
    runner = Runner(ctx)
    started_ts = now()
    try:
        duration = runner.run_process()
    except OSError as exc:
        lane.append_record(ctx["record"], {
            "ts": now(), "run": ctx["run"], "lane": ctx["lane"], "event": "lane-closed",
            "harness": HARNESS, "class": ctx["cls"], "session_id": ctx.get("session_id"),
            "exit_class": "spawn-failed", "exit_code": 3, "error": str(exc),
            "total_cost_usd": None, "cost_src": "codex-plan", "wrapper_pid": os.getpid()})
        sys.stderr.write("codex-lane.py: could not start the lane process: %s\n" % exc)
        return 3
    parsed = parse_events(runner.lines)
    session_id = runner.session_id or parsed["session_id"] or ctx.get("session_id")

    # The current JSONL response is the evidence. A pre-existing or concurrently planted
    # output file cannot supply a response, even when the CLI leaves -o untouched (critic F1).
    report_text = parsed["last_message"]
    exit_class, error = classify(runner.killed_by, parsed, runner.process.returncode, report_text)
    if not report_text:
        report_text = "(no report text: %s)" % (error or "exit %s" % runner.process.returncode)
    try:
        lane.write_atomic(ctx["report"], report_text.rstrip() + "\n")
        report_written = ctx["report"]
    except OSError as exc:
        report_written = None
        sys.stderr.write("codex-lane.py: report not written (%s)\n" % exc)
    shown, n_shown, n_total, cut = lane.cut_words(report_text, ctx["report_words"])
    stderr_text = "".join(runner.stderr_chunks)
    close = {
        "ts": now(), "run": ctx["run"], "lane": ctx["lane"], "event": "lane-closed",
        "harness": HARNESS, "session_id": session_id, "class": ctx["cls"],
        "model": ctx["model"], "effort": ctx["effort"], "exit_class": exit_class,
        "exit_code": EXIT_CODES.get(exit_class, 3), "process_exit": runner.process.returncode,
        "duration_s": duration, "num_turns": parsed["turns_completed"],
        "turns_failed": parsed["turns_failed"], "total_cost_usd": None, "cost_src": "codex-plan",
        "usage": dict(parsed["usage"], calls=parsed["turns_completed"]),
        # False when the wrapper killed the lane or no turn completed: Codex reports usage only
        # on turn.completed, so the zeros above are then unreported, not measured (a lane killed
        # mid-turn reads as 0 tokens however long it worked)
        "usage_complete": (not runner.killed_by) and parsed["turns_completed"] > 0,
        "items": parsed["items"], "commands": parsed["commands"],
        "sandbox_denials": parsed["sandbox_denials"],
        "denials": {"tool": 0, "fence": 0, "sandbox": parsed["sandbox_denials"]},
        "events": ctx["events"], "events_records": parsed["records"],
        "events_unparseable": parsed["unparseable"],
        "report": report_written, "report_words": n_total, "report_shown": n_shown,
        "report_cut": cut, "error": error, "errors": parsed["errors"][:5],
        "limit_signal": (error if exit_class == "limit" else None),
        "killed_by": runner.killed_by, "silence_s": ctx["silence"], "deadline_s": ctx["deadline"],
        "stderr_tail": stderr_text.strip()[-400:] or None, "wrapper_pid": os.getpid(),
        "started": started_ts}
    close.update(ctx.get("close_extra") or {})
    lane.append_record(ctx["record"], close)
    emit_summary(ctx, close, report_text)
    return EXIT_CODES.get(exit_class, 3)


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


def prepare(args, resume_id=None, beat=False):
    """Everything spawn and resume share before the process: checks, paths, command, record.
    A beat (resume --beat) reads no brief, takes no per-pass path and names no report."""
    lane.require_reason_letter(args.reason or "")
    if not (args.choice_reason or "").strip():
        die("--choice-reason is required: no routing row anchors a Codex pick, so every pick "
            "records why this model and effort")
    if args.effort not in EFFORTS:
        die("--effort must be one of %s" % ", ".join(EFFORTS))
    if args.model not in KNOWN_MODELS and not args.any_model:
        die("--model %s is not in the known Codex catalogue %s; pass --any-model to override"
            % (args.model, ", ".join(KNOWN_MODELS)))
    if not args.cls:
        die("--class is required")
    if args.stage_from and resume_id is None:
        args.cwd = stage_copy(args)
        if args.stage_writable:
            args.write = list(args.write or []) + [args.cwd]
    elif args.stage_writable and not args.stage_from:
        die("--stage-writable goes with --stage-from")
    if not args.cwd:
        die("--cwd is required (or --stage-from)")
    vault = lane.vault_root()
    if beat:
        brief, controls = None, None
    else:
        if not args.brief:
            die("--brief is required (the no-work form is resume --beat)")
        if not os.path.isfile(args.brief):
            die("brief file not found: %s" % args.brief)
        brief = lane.read_text(args.brief, "the brief")
        if not brief.strip():
            die("brief file is empty: %s" % args.brief)
        lane.refuse_doubled_root(args.brief, brief, vault)
        controls = lane.check_controls(lane.parse_controls(brief), vault)
    cwd = real_dir(args.cwd, "--cwd")
    writes = [real_dir(w, "--write") for w in (args.write or [])]
    if writes and not any(inside(cwd, w) for w in writes):
        die("with --write the cwd must lie inside a write directory: under workspace-write the "
            "cwd itself becomes writable (cwd %s; writes %s)" % (cwd, ", ".join(writes)))
    sandbox = "workspace-write" if writes else "read-only"
    add_dirs = [w for w in writes if not inside(w, cwd)]
    if args.network and not writes:
        die("--network needs --write: shell network is a workspace-write setting")
    mode, mode_src, mode_from = lane.resolve_delegation(args)
    codex, version = resolve_codex(args.codex)
    definition_path, definition_sha, definition_body = definition_of(vault, args.cls)
    core_path, core = core_text(vault, args.append_core)
    paths = (resume_paths(args) if resume_id is not None and not beat
             else store_paths(args.run, args.lane, args.record))
    overrides = config_overrides(args, args.network)
    command = build_command(codex, args, cwd, sandbox, add_dirs, overrides,
                            None if beat else paths["report"], resume_id)
    prompt = (lane.BEAT_PROMPT + "\n" if beat
              else compose_prompt(definition_body, core, cwd, writes, args.search, brief))
    env = dict(os.environ)
    env.update({"LLM_WIKI_LANE": "1", "LLM_WIKI_LANE_RUN": args.run, "LLM_WIKI_LANE_ID": args.lane,
                "LLM_WIKI_LANE_HARNESS": HARNESS})
    global_path, global_bytes = global_instructions_bytes()
    if global_bytes:
        sys.stderr.write("codex-lane.py: %s is %d bytes and Codex loads it into every lane; "
                         "--ignore-user-config does not cover it\n" % (global_path, global_bytes))
    return {"vault": vault, "brief": brief, "controls": controls, "cwd": cwd, "writes": writes,
            "global_instructions": {"path": global_path, "bytes": global_bytes},
            "stage": getattr(args, "stage_report", None),
            "sandbox": sandbox, "add_dirs": add_dirs, "mode": (mode, mode_src, mode_from),
            "codex": codex, "version": version, "definition": (definition_path, definition_sha),
            "core_path": core_path, "paths": paths, "overrides": overrides, "command": command,
            "prompt": prompt, "env": env}


def open_line(args, prep, event="lane-open", extra=None):
    vault = prep["vault"]
    mode, mode_src, mode_from = prep["mode"]
    line = {
        "ts": now(), "run": args.run, "lane": args.lane, "event": event, "harness": HARNESS,
        "class": args.cls, "definition": os.path.relpath(prep["definition"][0], vault),
        "definition_sha256": prep["definition"][1],
        "model": args.model, "effort": args.effort, "throttle": "n/a (codex)",
        "row_default": None, "model_src": "explicit", "effort_src": "explicit",
        "choice_reason": args.choice_reason, "reason": args.reason,
        "mode": mode, "mode_src": mode_src, "mode_from": mode_from,
        "cwd": prep["cwd"], "sandbox": prep["sandbox"], "writes": prep["writes"],
        "add_dirs": prep["add_dirs"],
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
        "config_sha256": config_hash(prep["command"]),   # what a resume or a beat must carry byte for byte
        "schema": (os.path.abspath(args.schema) if args.schema else None),
        "events": prep["paths"]["events"], "report": prep["paths"]["report"],
        "deadline_s": args.deadline_s, "silence_s": args.silence_s,
        "report_words_cap": args.report_words, "plant": args.plant,
        "reading_list": args.reading_list, "breadth": lane.customisation_value("breadth", "standard"),
        "budget_usd": None, "total_cost_usd": None, "cost_src": "codex-plan",
        "mechanism": "codex-lane.py headless (codex exec --json, --ignore-user-config, "
                     "sandbox %s, -a never, silence watch on the event stream)" % prep["sandbox"]}
    if extra:
        line.update(extra)
    return line


def detach(args):
    """Re-run this command as a worker that survives the caller; `--no-wait` returns at once. The
    caller opens the run's console first, in its own context, and the worker runs under `--viewer
    none`, appended so it wins over any --viewer the command carried.
    (register 2026-09-09 11:21, update
    2026-09-12). The opener itself is handsoff.py's, reached through lane.open_console_for_spawn."""
    paths = store_paths(args.run, args.lane, args.record)
    os.makedirs(paths["store"], exist_ok=True)
    lane.open_console_for_spawn(args.run, args.viewer)
    argv = [sys.executable, os.path.abspath(__file__)] + [a for a in sys.argv[1:]
                                                          if a not in ("--detach", "--no-wait")]
    argv += ["--viewer", "none", "--as-worker"]
    with open(paths["detach_log"], "a", encoding="utf-8") as log:
        worker = subprocess.Popen(argv, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                  start_new_session=True)
    print("detached pid %d (log %s)" % (worker.pid, paths["detach_log"]))
    if args.no_wait:
        return 0
    return worker.wait()


def print_dry_run(prep, line):
    print("command:")
    print("  " + " ".join(shlex.quote(part) for part in prep["command"]))
    print("cwd: %s · sandbox: %s · writes: %s · add-dirs: %s"
          % (prep["cwd"], prep["sandbox"], prep["writes"] or "none", prep["add_dirs"] or "none"))
    print("prompt: %d bytes (definition + core + addendum + brief) on stdin" % line["prompt_bytes"])
    print("controls checked: %s" % json.dumps(prep["controls"]))
    print("record line (%s):" % prep["paths"]["record"])
    print("  " + json.dumps(line))


def context_for(args, prep, extra=None):
    paths = prep["paths"]
    ctx = {"record": paths["record"], "run": args.run, "lane": args.lane, "cls": args.cls,
           "model": args.model, "effort": args.effort, "command": prep["command"],
           "cwd": prep["cwd"], "env": prep["env"], "prompt": prep["prompt"],
           "events": paths["events"], "stderr": paths["stderr"], "report": paths["report"],
           "deadline": args.deadline_s, "silence": args.silence_s,
           "report_words": args.report_words, "format": args.format, "viewer": args.viewer,
           "detached": bool(args.as_worker)}
    if extra:
        ctx.update(extra)
    return ctx


def cmd_spawn(args):
    lane.require_lane_id(args.lane)
    paths = store_paths(args.run, args.lane, args.record)
    lane.require_new_lane_id(args.lane, paths["record"])
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
    args.effort = args.effort or DEFAULT_EFFORT
    if not args.as_worker:
        lane.closed_run_warning(store_paths(args.run, args.lane, args.record)["record"],
                                who="codex-lane.py")
    try:
        prep = prepare(args)
    finally:
        # Even a failed preflight must release its empty stage. rmdir cannot remove contents.
        if args.dry_run and args.stage_from and getattr(args, "stage_report", None):
            stage = args.stage_report["stage_dir"]
            try:
                os.rmdir(stage)
            except OSError as exc:
                die("cannot remove empty dry-run stage %s: %s" % (stage, exc))
    if args.detach and not args.dry_run:
        return detach(args)          # the premise checks above ran in the caller's terminal
    paths = prep["paths"]
    line = open_line(args, prep)
    if args.dry_run:
        print_dry_run(prep, line)
        return 0
    lane.append_record(paths["record"], line)
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
        resume_paths(args)  # before refresh_stage can modify the staged copy, or detach can write a log
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
        args.effort = opened.get("effort") or DEFAULT_EFFORT
        carried["effort"] = args.effort
    if args.config is None:
        extra, source = recorded_config_extra(opened)
        args.config = extra
        carried["config"], carried["config_src"] = extra, source
        if source.startswith("none:"):
            sys.stderr.write("codex-lane.py: %s; no --config carried onto the resume\n"
                             % source[len("none:"):].strip())
    if args.stage_from:
        # the lane's own staged copy, refreshed in place (register 2026-09-11 23:37)
        args.cwd = refresh_stage(args, opened, copy=not (args.detach or args.dry_run))
    if not args.cwd:
        args.cwd = opened.get("cwd")
    if not args.write and opened.get("writes"):
        args.write = list(opened["writes"])
    if args.stage_from and args.stage_writable and args.cwd not in (args.write or []):
        args.write = list(args.write or []) + [args.cwd]
    if args.cls is None:
        args.cls = opened.get("class")
    if beat and not args.delegation and not args.delegation_src:
        # A beat re-declares the regime its spawn recorded, as it does the model and the effort:
        # the supervisor passes no flag, and under a Settings line reading `auto` an unflagged
        # call is refused (lane.resolve_delegation), which would refuse every beat.
        mode, mode_src = opened.get("mode"), opened.get("mode_src")
        if mode in lane.REGIMES and mode_src in ("head", "owner"):
            args.delegation, args.delegation_src = mode, mode_src
            carried["delegation"] = "%s (%s)" % (mode, mode_src)
    prep = prepare(args, resume_id=session, beat=beat)
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
                            "config_match": config_match, "config_src": config_src})
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
    non-zero exit, a limit or a failed turn is recorded with ok false, never retried here."""
    record, run, lane_id = ctx["record"], ctx["run"], ctx["lane"]
    started = time.time()
    by = os.environ.get(lane.BEAT_BY_ENV) or "hand"
    base = {"run": run, "lane": lane_id, "event": "hold-beat", "harness": HARNESS,
            "session_id": ctx.get("session_id"), "class": ctx["cls"], "model": ctx["model"],
            "effort": ctx["effort"], "n": ctx["beat_n"], "by": by, "prompt": lane.BEAT_PROMPT,
            "config_sha256": ctx["config_sha256"], "config_src": ctx["config_src"],
            "config_match": ctx["config_match"], "last_call_age_s": ctx["age_s"],
            "last_call_src": ctx["age_src"], "carried_from_open": ctx.get("carried_from_open"),
            "total_cost_usd": None, "cost_src": "codex-plan", "wrapper_pid": os.getpid()}
    try:
        process = subprocess.Popen(ctx["command"], cwd=ctx["cwd"], env=ctx["env"], text=True,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
    except OSError as exc:
        lane.append_record(record, dict(base, ts=now(), ok=False, exit_class="spawn-failed",
                                        exit_code=3, process_exit=None, duration_s=0.0,
                                        usage=None, error=str(exc)))
        sys.stderr.write("codex-lane.py: the beat could not start the lane process: %s\n" % exc)
        return 3
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
    exit_class, error = classify(killed_by, parsed, process.returncode, parsed["last_message"])
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
    lane.append_record(record, line)
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


def cmd_watch(args):
    """Block until the lane's next close: the first lane-closed after its latest lane-open or
    lane-resumed (register 2026-09-10 07:31). Reads the record; writes nothing."""
    record = store_paths(args.run, args.lane, args.record)["record"]
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
                      "%s; close the record with codex-lane.py kill"
                      % (args.run, args.lane, wrapper, start.get("event")))
                return 3
        else:
            orphan_since = None
        if args.max_wait_s and waited > args.max_wait_s:
            print("still-running: lane %s/%s after %.0f s" % (args.run, args.lane, waited))
            return lane.EXIT_STILL_RUNNING
        time.sleep(args.poll_s if spawned is not None else min(args.poll_s, 0.5))


def cmd_kill(args):
    paths = store_paths(args.run, args.lane, args.record)
    if not os.path.isfile(paths["record"]):
        die("no run record at %s" % paths["record"])

    def state():
        pid, wrapper, closed = None, None, False
        for event in lane.load_record(paths["record"]):
            if event.get("lane") != args.lane:
                continue
            if event.get("event") in ("lane-spawned", "lane-respawned"):
                pid, wrapper, closed = event.get("pid"), event.get("wrapper_pid"), False
            if event.get("event") == "lane-closed":
                closed = True
        return pid, wrapper, closed

    pid, wrapper, closed = state()
    if closed:
        print("lane %s/%s is already closed" % (args.run, args.lane))
        return 0
    if wrapper and lane.pid_alive(wrapper):
        lane.signal_pid(wrapper, signal.SIGTERM)     # the wrapper kills its lane and writes the close
    waited = 0.0
    while waited < KILL_GRACE_S * 2 + 2 and not state()[2]:
        time.sleep(0.5)
        waited += 0.5
    if not state()[2]:
        if pid and lane.pid_alive(pid):
            lane.kill_pid_group(pid, group=True)
        lane.append_record(paths["record"], {
            "ts": now(), "run": args.run, "lane": args.lane, "event": "lane-closed",
            "harness": HARNESS, "exit_class": "killed", "exit_code": 3, "reason": args.reason,
            "total_cost_usd": None, "cost_src": "codex-plan", "session_id": None,
            "killed_by": "kill", "wrapper_pid": os.getpid()})
    print("killed lane %s/%s (%s)" % (args.run, args.lane, args.reason))
    return 0


# ---------------------------------------------------------------------- parser -------------

def add_common(parser, spawn=True):
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
    parser.add_argument("--write", action="append", help="a directory the lane may write (repeatable); "
                        "the cwd must lie inside one of them")
    parser.add_argument("--reason", default=None, help="REQUIRED on spawn: why a lane rather than the "
                        "head, opening with the instrument-rule letter (a)–(d)")
    parser.add_argument("--choice-reason", default=None, help="REQUIRED on spawn: why this model and effort")
    parser.add_argument("--model", default=None, help="default %s on spawn; on resume the "
                        "lane-open's model" % DEFAULT_MODEL)
    parser.add_argument("--any-model", action="store_true", help="allow a model outside the known catalogue")
    parser.add_argument("--effort", default=None, help="%s (default %s on spawn; on resume the "
                        "lane-open's effort)" % ("|".join(EFFORTS), DEFAULT_EFFORT))
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
    parser.add_argument("--plant", default=None)
    parser.add_argument("--reading-list", default=None)
    parser.add_argument("--delegation", choices=lane.REGIMES, default=None)
    parser.add_argument("--delegation-src", choices=("head", "owner"), default=None)
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--as-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")


def build_parser():
    parser = argparse.ArgumentParser(description="spawn a headless Codex (GPT-6 Astra) lane")
    sub = parser.add_subparsers(dest="command", required=True)
    add_common(sub.add_parser("spawn"), spawn=True)
    add_common(sub.add_parser("resume", description="resume a recorded lane; reports use "
                              "<run>-report-<lane>-pass<n>.md and prompts use the same suffix, starting at n=2; "
                              "existing report or prompt paths refuse before writes"), spawn=False)
    watch = sub.add_parser("watch", help="block until the lane's next close (the close after its "
                           "latest open or resume); reads the record, writes nothing")
    watch.add_argument("--run", required=True)
    watch.add_argument("--lane", required=True)
    watch.add_argument("--record", help="spawn record path (default: the run store)")
    watch.add_argument("--max-wait-s", type=float, default=lane.WATCH_MAX_WAIT_S,
                       help="return still-running (exit %d) after this many seconds (default %d, "
                            "lane.py's bound; 0 waits without bound)"
                            % (lane.EXIT_STILL_RUNNING, lane.WATCH_MAX_WAIT_S))
    watch.add_argument("--appear-s", type=float, default=lane.WATCH_APPEAR_S,
                       help="seconds to wait for a just-detached lane's line before calling it "
                            "unknown or closed (default %d)" % lane.WATCH_APPEAR_S)
    watch.add_argument("--poll-s", type=float, default=WATCH_POLL_S,
                       help="seconds between record reads (default %d)" % WATCH_POLL_S)
    watch.add_argument("--report-words", type=int, default=REPORT_WORDS)
    watch.add_argument("--format", choices=("text", "json"), default="text")
    kill = sub.add_parser("kill")
    kill.add_argument("--run", required=True)
    kill.add_argument("--lane", required=True)
    kill.add_argument("--reason", required=True)
    kill.add_argument("--record")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command in ("spawn", "resume") and args.no_wait and not args.detach:
        die("--no-wait goes with --detach")
    if args.command == "spawn":
        return cmd_spawn(args)
    if args.command == "resume":
        return cmd_resume(args)
    if args.command == "watch":
        return cmd_watch(args)
    return cmd_kill(args)


if __name__ == "__main__":
    sys.exit(main())
