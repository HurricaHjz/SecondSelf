#!/bin/sh
# test_handsoff.sh — the suite for handsoff.py (delegate skill, hands-off mode).
#
# Run:  sh test_handsoff.sh                       (from beside handsoff.py)
#       HANDSOFF=<path to handsoff.py> sh test_handsoff.sh
#
# Every fixture lives in a fresh directory under AIMYTH_TEST_SCRATCH_ROOT (default /tmp),
# explicitly set to a granted directory in a restricted lane, and is removed on
# exit; HANDSOFF_KEEP=1 keeps it for a post-mortem. The suite writes nothing anywhere else,
# and the last three legs are the proof: a checksum manifest of the shipped skill directory
# and of the hooks directory taken before the legs and again after, that manifest's own
# positive control (a modified copy must show a difference), and a scan of this file for a
# write verb aimed at an absolute path outside /tmp, with a planted control that must hit.
#
# Every leg that reports a clean result carries its positive control on the same run: each
# refusal leg plants the case that must be caught (a second run-open, an append-only key, a
# missing table, an armed band crossing, a second unmetered gate, a duplicate successor).
#
# The last line is PASS n/n or FAIL k/n; the exit code is 0 only when every leg passed.
#
# `sh test_handsoff.sh --leg TEXT` runs only the sections whose banner or verdict line holds TEXT,
# as a fixed string, then the write proof (register entry 2026-10-13 14:13, the filter third). A
# section may lean on one above it, so a filtered run is for iterating on a change and the whole
# suite stays the verdict on it. A TEXT no section holds is PROBE FAILED, exit 2, never clean.
set -u

ONLY_LEG=""
if [ $# -gt 0 ]; then
  if [ "$1" != "--leg" ] || [ $# -ne 2 ] || [ -z "$2" ]; then
    printf 'PROBE FAILED: the only argument is --leg TEXT, a fixed string of a leg name\n' >&2
    exit 2
  fi
  ONLY_LEG=$2
fi

PY=${PYTHON:-python3}
SRC=$0
H=${HANDSOFF:-$(dirname "$SRC")/handsoff.py}

die() { printf 'PROBE FAILED: %s\n' "$1" >&2; exit 2; }

command -v "$PY" >/dev/null || die "no python3 on PATH"
command -v git >/dev/null || die "no git on PATH: the checkpoint-commit legs cannot run"
[ -f "$H" ] || die "no handsoff.py at $H (pass HANDSOFF=<path>)"
SKILL_DIR=$(cd "$(dirname "$H")" && pwd) || die "cannot resolve the directory of $H"
# The handsoff path, resolved once to an absolute one: a stub head calls it from a fixture's own
# working directory, so a path given relative (the suite started from beside the file, where $H
# is ./handsoff.py) must never reach a leg.
H="$SKILL_DIR/$(basename "$H")"
# A staged copy names the shipped modules: HOOKS_DIR (context-watermark.py) and LANE_PY (the
# lane wrapper, imported for its classifier); beside the vault's script tree both default.
HOOKS_DIR=${HOOKS_DIR:-$(cd "$SKILL_DIR/../../hooks" 2>&1 && pwd)}
LANE_PY=${LANE_PY:-$SKILL_DIR/lane.py}
[ -f "$HOOKS_DIR/context-watermark.py" ] || die "no context-watermark.py under $HOOKS_DIR (set HOOKS_DIR)"
[ -f "$LANE_PY" ] || die "no lane.py at $LANE_PY (set LANE_PY)"
export AIMYTH_HOOKS_DIR="$HOOKS_DIR"
export AIMYTH_LANE_PY="$LANE_PY"

# Retain the /tmp default while allowing an explicitly granted scratch root. Keep that root
# outside SKILL_DIR and HOOKS_DIR so the source manifests do not include changing fixtures.
case ${AIMYTH_TEST_SCRATCH_ROOT:-/tmp} in
  /*) : ;;
  *) die "AIMYTH_TEST_SCRATCH_ROOT must be absolute" ;;
esac
WORK=$(mktemp -d "${AIMYTH_TEST_SCRATCH_ROOT:-/tmp}/handsoff-suite.XXXXXX") || die "cannot make a temp directory under the scratch root"
case $WORK in
  "${AIMYTH_TEST_SCRATCH_ROOT:-/tmp}"/handsoff-suite.*) : ;;
  *) die "the temp directory $WORK is not under the scratch root" ;;
esac
cleanup() { [ "${HANDSOFF_KEEP:-0}" = "1" ] || rm -rf "$WORK"; }
# EXIT runs the cleanup; INT and TERM end the run there, non-zero (128 + the signal), so a stopped
# run never carries on without its temp folder.
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# The target must import before anything else is claimed about it; the byte-code file goes to
# the temp directory, because py_compile ignores -B and the vault takes no __pycache__.
"$PY" -c 'import py_compile, sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)' \
      "$H" "$WORK/handsoff.pyc" || die "handsoff.py does not compile"
# The interpreter as handsoff.py names it in every command it hands on (register entry 2026-09-30
# 17:36): its own sys.executable, an absolute path, which the suite's legs expect by value.
PYABS=$("$PY" -c 'import sys; sys.stdout.write(sys.executable)')
case $PYABS in /*) : ;; *) die "the interpreter's own path is not absolute: '$PYABS'" ;; esac

STORE="$WORK/store"
PROJECTS="$WORK/projects"
STATE="$WORK/state"
VAULT="$WORK/vault"
REMOTE="$WORK/remote.git"
MK="$WORK/mk.py"
mkdir -p "$STORE/spawn-records" "$PROJECTS" "$STATE" "$VAULT" "$WORK/handoffs" "$WORK/starter" \
         "$WORK/psclaude" "$WORK/psnone" "$WORK/bin" "$WORK/openbin" "$WORK/openfail" \
         "$WORK/pgrepslow" "$WORK/psslow" "$WORK/pssplit" "$WORK/pgrepexit" "$WORK/gitfail" \
         "$WORK/home" "$WORK/codex-home" "$WORK/claude-config" "$WORK/guard" "$WORK/pstable"

# The real home directory, kept for the read guard below before HOME points at a fixture: the
# home-directory stores (the Codex home, the harness's projects and configuration, the run store
# and the hand-off directory) are fixtures for every call, and a read that still reaches a real
# one is blocked and charged to the last leg (register entry 2026-10-04 10:45: the suites read
# ~/.codex/sessions, ~/.claude/projects and ~/.claude.json).
REALHOME=$("$PY" -c 'import os, sys; sys.stdout.write(os.path.realpath(os.path.expanduser("~")))')
[ -n "$REALHOME" ] || die "the real home directory cannot be read"
export HOME="$WORK/home"
export CODEX_HOME="$WORK/codex-home"
export CLAUDE_CONFIG_DIR="$WORK/claude-config"
# The read guard: a sitecustomize.py on PYTHONPATH that every python process of the suite loads.
# Its audit hook blocks (PermissionError) and logs an open, a directory listing or a glob under a
# real home-directory store; the suite's own tree and the code under test are never under one.
READ_GUARD_LOG="$WORK/read-guard.log"
cat > "$WORK/guard/sitecustomize.py" <<'READGUARD'
"""The suite's read guard (test_handsoff.sh): reads of the real home-directory stores are
blocked before access and logged, one line each, to READ_GUARD_LOG."""
import os
import sys

_ROOTS = [r for r in os.environ.get("READ_GUARD_ROOTS", "").split(os.pathsep) if r]
_LOG = os.environ.get("READ_GUARD_LOG")


def _guard(event, args):
    if event not in ("open", "os.listdir", "os.scandir", "glob.glob", "os.open"):
        return
    target = args[0] if args else None
    if isinstance(target, bytes):
        target = target.decode("utf-8", "replace")
    if not isinstance(target, str) or not target:
        return
    full = os.path.abspath(target)
    for root in _ROOTS:
        if full == root or full.startswith(root + os.sep):
            if _LOG:
                with open(_LOG, "a", encoding="utf-8") as handle:
                    handle.write("%s %s %s\n" % (event, full, " ".join(sys.argv[:3])[:160]))
            raise PermissionError("the suite's read guard blocked %s on %s" % (event, full))


if _ROOTS and _LOG:
    sys.addaudithook(_guard)
READGUARD
READ_GUARD_ROOTS="$REALHOME/.codex:$REALHOME/.claude:$REALHOME/.claude.json"
for store_name in .llm-wiki .aimyth; do
  for sub in spawn-records handoffs; do
    READ_GUARD_ROOTS="$READ_GUARD_ROOTS:$REALHOME/$store_name/$sub"
  done
done
export READ_GUARD_ROOTS READ_GUARD_LOG
export PYTHONPATH="$WORK/guard${PYTHONPATH:+:$PYTHONPATH}"

# The suite's own suffix, from its temporary directory's name: the run ids of every leg that
# plants a console process carry it, so two copies of this suite running at once never see each
# other's consoles (register entry 2026-09-22 20:28: fixed ids made sibling copies fail each
# other's console legs).
SFX=$(basename "$WORK" | sed 's/^handsoff-suite\.//; s/[^A-Za-z0-9]//g')
[ -n "$SFX" ] || die "no suffix in the temp directory's name $WORK"

# One environment for every call: the run store, the projects root, the arming marker root and
# the vault are all fixtures, so no call can reach the real store, transcripts or work tree.
export LLM_WIKI_STORE="$STORE"
export AIMYTH_PROJECTS_DIR="$PROJECTS"
export AIMYTH_STATE_DIR="$STATE"
export CLAUDE_PROJECT_DIR="$VAULT"
export AIMYTH_BANDS="60,80,90"
export AIMYTH_CONTEXT_WINDOW="1000000"
export PYTHONDONTWRITEBYTECODE=1
export LLM_WIKI_LANE_HOME="$WORK/lane-home"
unset AIMYTH_HANDSOFF
unset AIMYTH_WATERMARK_LOG
unset AIMYTH_HANDSOFF_RUN
# A caller's own settings never decide a leg (register entry 2026-10-04 10:45, the environment's
# half): every knob handsoff.py reads that the suite does not set above is cleared here, and a leg
# that wants one passes it on its own call. A run's wrapper exports AIMYTH_MAX_SUCCESSORS, and the
# successor-cap control then read the caller's cap instead of the default.
unset AIMYTH_MAX_SUCCESSORS AIMYTH_VIEWER AIMYTH_OPEN_BIN AIMYTH_BEAT_BY AIMYTH_BEAT_WRAPPER_DIR
# The stub head reads these: it is started by the supervisor with the suite's environment.
SUITE_WORK="$WORK"; SUITE_PY="$PY"; SUITE_MK="$MK"; SUITE_STORE="$STORE"
export SUITE_WORK SUITE_PY SUITE_MK SUITE_STORE

# Synthetic billed line: head 12.34 + lanes 4.22 = session 16.56.
# Three synthetic rewrites at 0.10 each give 0.30; tool rates are independent fixture inputs.
# No captured usage or cost reading is reused.
METER='billed (list 2001-01-01) · head $12.34 · lanes $4.22 · session $16.56 · rewrites 3 ($0.30) · tool uses/call head 2.00 lanes 4.00 · delegation multi (owner) · lanes 1 (reasons: (a)×1 (b)×0 (c)×0 (d)×0, none×0) · metered 1 of 1'

# ------------------------------------------------------------------ the fixture toolkit ----
cat > "$MK" <<'MKPY'
#!/usr/bin/env python3
"""Fixtures and an independent oracle for test_handsoff.sh.

Writes only under the suite's temp directory (every path it is given comes from there); every
query command prints to standard output and writes nothing. The document and record parsers
here are written from the schema, not imported from handsoff.py, so a leg that passes agrees
with an independent reading rather than with the code under test.
"""
import hashlib
import json
import os
import re
import sys
import time

BLOCKS = [
    ("morning", "## Morning report (rewritten at every boundary)", [
        "- **What shipped:** nothing yet.",
        "- **Waits for you:** nothing yet.",
        "- **Register delta:** none.",
        "- **Spend against the envelope:** unmetered.",
        "- **Measured head-load saving:** n/a until the parity run.",
        "- **Warnings raised and handling:** see `## Findings ledger` (9 lines; a wrong figure "
        "on purpose, so a refresh is observable).",
        "- **Resume prompt:** below.",
    ]),
    ("resume", "## Resume prompt (paste into a new conversation if this session is gone)", [
        "Resume the fixture run: read this hand-off in full, then continue at the next item.",
    ]),
    ("inflight", "## In flight", ["- nothing in flight."]),
    ("grants", "## Grants", ["- fixture grants."]),
    ("ledger", "## Findings ledger (one line per warning · issue · finding · lesson)", [
        "| Time | Phase | What | Evidence | Routing |",
        "|---|---|---|---|---|",
        "| 01:00 | 0 | fixture finding one | fixture evidence | no action |",
        "| 01:01 | 0 | fixture finding two | fixture evidence | no action |",
    ]),
    ("trace", "## Trace (one row per decision and boundary)", [
        "| Time | Item | Decision and its rule | Billed line | Waste so far |",
        "|---|---|---|---|---|",
        "| 01:02 | open → 1 | fixture decision | fixture billed line | fixture waste |",
    ]),
    ("decoy", "## Trace archive (a decoy: the row must land in the FIRST trace table)", [
        "| Time | Item | Decision and its rule | Billed line | Waste so far |",
        "|---|---|---|---|---|",
        "| 00:01 | archived | decoy row | decoy | decoy |",
    ]),
    ("plan", "## Plan of record", ["- fixture plan."]),
    ("pointers", "## Pointers", ["- fixture pointers."]),
]


def out(text):
    sys.stdout.write(str(text) + "\n")


def stamp(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(epoch))


def dashed(path):
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(path))


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def read_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().split("\n")


def events_of(path):
    found = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                found.append(json.loads(line))
    return found


def heading_index(lines, name):
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower().startswith(name.lower()):
            return i
    return -1


def section_end(lines, start):
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("# "):
            return i
    return len(lines)


def table(lines, name):
    i = heading_index(lines, name)
    if i < 0:
        return []
    end = section_end(lines, i)
    rows = []
    started = False
    for j in range(i + 1, end):
        if lines[j].lstrip().startswith("|"):
            started = True
            rows.append(lines[j])
        elif started:
            break
    return rows[2:] if len(rows) > 2 else []


LEDGER_PROSE = "The findings ledger is seeded by the first head (a launcher placeholder)."


def cmd_handoff(argv):
    """The fixture hand-off; the second argument drops named blocks, and four ledger variants
    stand in for a launcher's seed: `ledger-prose` (the heading over one prose line, no table),
    `ledger-broken` (a header line with no separator: pipe-led, yet no table), `ledger-two`
    (the prose form, then a second heading with the table) and `ledger-two-table` (the table
    under the first heading AND a second heading with a table)."""
    path = argv[0]
    drop = [x for x in (argv[1] if len(argv) > 1 else "").split(",") if x]
    body = ["# Fixture hand-off (a suite fixture, not a vault page)", ""]
    for key, heading, lines in BLOCKS:
        if key in drop:
            continue
        if key == "ledger" and ("ledger-prose" in drop or "ledger-two" in drop):
            lines = [LEDGER_PROSE]
        elif key == "ledger" and "ledger-broken" in drop:
            lines = [BLOCKS[4][2][0], LEDGER_PROSE]
        body.append(heading)
        body.extend(lines)
        body.append("")
        if key == "ledger" and ("ledger-two" in drop or "ledger-two-table" in drop):
            body.append("## Findings ledger (archive: a second heading carrying the table)")
            body.extend(BLOCKS[4][2])
            body.append("")
    write(path, "\n".join(body))
    out(path)


def cmd_record(argv):
    path, run, session, handoff, envelope = argv[:5]
    base = time.time() - 7200
    ev = {"ts": stamp(base), "run": run, "event": "run-open", "session": session,
          "head": "fixture head", "regime": "multi", "regime_src": "owner",
          "handoff": os.path.realpath(handoff), "detail": "fixture run", "pid_src": "none"}
    # The run's head model as a structured field (run-open --model), which a successor or a
    # resume that names no --model inherits; `nomodel` plants a record that names none.
    if "nomodel" not in argv[5:]:
        ev["model"], ev["model_src"] = "fixture-model", "arg"
    if envelope != "none":
        ev["envelope_usd"] = float(envelope)
    if len(argv) > 5 and argv[5] == "seed":
        ev["session_kind"] = "seed"      # a launcher's placeholder session, which never ran
    write(path, json.dumps(ev, ensure_ascii=False) + "\n")
    out(path)


def append(path, ev):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev, ensure_ascii=False) + "\n")


def cmd_append(argv):
    path, payload = argv[0], argv[1]
    ev = json.loads(payload)
    first = events_of(path)[0]
    ev.setdefault("run", first.get("run"))
    ev.setdefault("ts", stamp(time.time()))
    append(path, ev)
    out(ev["event"])


def cmd_waste(argv):
    """The planted close-outs behind the five waste fields.

    Offsets from a base two hours old, so every figure is fixed whatever the wall clock says:
    closes at +60 s, +120 s and +150 s, and the head's next act (an observation) at +300 s.
    Idle = (300-60 + 300-120 + 300-150) / 60 = 9.5 min; denials 2 (a wrapper count) + 1 (a
    denial list) = 3; one report over the 800-word cap (971 words, the figure this run's own
    record carries); re-spawn cost $5.00 from the one close that did not complete; one report
    that cannot be word-counted (the path does not exist).
    """
    path, run, missing = argv[0], argv[1], argv[2]
    base = time.time() - 7200
    append(path, {"ts": stamp(base + 60), "run": run, "event": "lane-closed", "lane": "L1",
                  "exit_class": "budget", "total_cost_usd": 5.0,
                  "denials": {"tool": 2, "fence": 1}, "permission_denials": [],
                  "report_words": 971})
    append(path, {"ts": stamp(base + 120), "run": run, "event": "lane-closed", "lane": "L2",
                  "exit_class": "completed", "total_cost_usd": 1.25,
                  "permission_denials": [{"tool": "Edit"}], "report_words": 12})
    append(path, {"ts": stamp(base + 150), "run": run, "event": "lane-closed", "lane": "L3",
                  "exit_class": "watch-closed", "total_cost_usd": 0.0, "report": missing})
    append(path, {"ts": stamp(base + 300), "run": run, "event": "observation", "phase": "2",
                  "what": "the head's next act", "note": "closes the idle windows"})
    out("waste fixtures planted")


def cmd_transcript(argv):
    """A transcript the watermark hook's measure() will meter: one assistant usage record
    whose three stock keys sum to the tokens asked for."""
    sid, tokens = argv[0], int(argv[1])
    first = int(argv[2]) if len(argv) > 2 else None   # an optional earlier record (orientation)
    path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"],
                        dashed(os.environ["CLAUDE_PROJECT_DIR"]), "%s.jsonl" % sid)

    def rec(n):
        return {"type": "assistant", "isSidechain": False,
                "message": {"role": "assistant", "model": "claude-fixture-1",
                            "usage": {"input_tokens": n - 2, "cache_read_input_tokens": 1,
                                      "cache_creation_input_tokens": 1}}}
    recs = ([rec(first)] if first is not None else []) + [rec(tokens)]
    write(path, "".join(json.dumps(r) + "\n" for r in recs))
    out(path)


def cmd_untranscript(argv):
    path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"],
                        dashed(os.environ["CLAUDE_PROJECT_DIR"]), "%s.jsonl" % argv[0])
    if os.path.isfile(path):
        os.remove(path)
    out("removed" if not os.path.exists(path) else "still there")


def cmd_pricedscript(argv):
    """A transcript the real meter beside the script prices: N assistant calls of one million
    input tokens each, the model id naming the opus family, one minute apart. Each call costs
    the family's input rate per MTok (prices.json), so a figure is N times that rate. The file
    goes under the vault's dashed directory (a head), or under the directory named as the
    third argument (a lane's own project directory)."""
    sid, n = argv[0], int(argv[1])
    folder = argv[2] if len(argv) > 2 else dashed(os.environ["CLAUDE_PROJECT_DIR"])
    tokens = int(argv[3]) if len(argv) > 3 else 1000000   # input tokens per call
    path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], folder, "%s.jsonl" % sid)
    start = time.time() - 3600
    recs = []
    for i in range(n):
        recs.append({"type": "assistant", "isSidechain": False,
                     "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(start + 60 * i))
                     + ".000Z",
                     "message": {"id": "msg-%s-%d" % (sid, i), "role": "assistant",
                                 "model": "claude-fixture-opus-1",
                                 "content": [{"type": "text", "text": "fixture call"}],
                                 "usage": {"input_tokens": tokens,
                                           "cache_creation_input_tokens": 0,
                                           "cache_read_input_tokens": 0, "output_tokens": 0}}})
    write(path, "".join(json.dumps(r) + "\n" for r in recs))
    out(path)


def transcript_path(sid, root=None):
    return os.path.join(root or os.environ["AIMYTH_PROJECTS_DIR"],
                        dashed(os.environ["CLAUDE_PROJECT_DIR"]), "%s.jsonl" % sid)


def cmd_xscript(argv):
    """One transcript record of every class the extractor must tell apart: a human turn, an
    assistant turn carrying prose and a tool call, a tool-result record, a Skill-tool
    injection (isMeta), a harness injection (a record that is nothing but a system reminder),
    an assistant record of tool calls only, and a torn line."""
    sid = argv[0]
    root = argv[1] if len(argv) > 1 else None
    recs = [
        {"type": "user", "timestamp": "2026-09-05T20:00:00Z",
         "message": {"role": "user",
                     "content": [{"type": "text", "text": "the human turn asks"}]}},
        {"type": "assistant", "timestamp": "2026-09-05T20:00:10Z",
         "message": {"role": "assistant", "model": "claude-fixture-1",
                     "content": [{"type": "text", "text": "the assistant answers in prose"},
                                 {"type": "tool_use", "name": "Bash", "input": {}}]}},
        {"type": "user", "timestamp": "2026-09-05T20:00:20Z",
         "message": {"role": "user", "content": [{"type": "tool_result",
                                                  "content": "tool output text"}]}},
        {"type": "user", "isMeta": True, "timestamp": "2026-09-05T20:00:30Z",
         "message": {"role": "user",
                     "content": [{"type": "text",
                                  "text": "Base directory for this skill: fixture"}]}},
        {"type": "user", "timestamp": "2026-09-05T20:00:40Z",
         "message": {"role": "user",
                     "content": [{"type": "text",
                                  "text": "<system-reminder>injected</system-reminder>"}]}},
        {"type": "assistant", "timestamp": "2026-09-05T20:00:50Z",
         "message": {"role": "assistant",
                     "content": [{"type": "tool_use", "name": "Read", "input": {}}]}},
    ]
    path = transcript_path(sid, root)
    write(path, "".join(json.dumps(r) + "\n" for r in recs) + "{a torn line\n")
    out(path)


def cmd_toolscript(argv):
    """A transcript for the tool-call extraction (register entry 2026-09-07): an assistant
    record of tool calls alone, one carrying prose AND a call, one whose command runs past the
    300-character cut, a tool result that must stay out, and a harness injection. Six records:
    2 extracted + 2 tool-call + 2 excluded, so a leg can check the arithmetic."""
    recs = [
        {"type": "user", "timestamp": "2026-09-07T10:00:00Z",
         "message": {"role": "user",
                     "content": [{"type": "text", "text": "the human turn asks"}]}},
        {"type": "assistant", "timestamp": "2026-09-07T10:00:10Z",
         "message": {"role": "assistant", "model": "claude-fixture-1", "content": [
             {"type": "tool_use", "name": "Bash",
              "input": {"command": "git status --porcelain", "description": "status"}},
             {"type": "tool_use", "name": "Read", "input": {"file_path": "/fixture/page.md"}},
             {"type": "tool_use", "name": "Grep",
              "input": {"pattern": "needle", "output_mode": "content"}},
             {"type": "tool_use", "name": "TodoWrite", "input": {"todos": []}}]}},
        {"type": "assistant", "timestamp": "2026-09-07T10:00:20Z",
         "message": {"role": "assistant", "model": "claude-fixture-1", "content": [
             {"type": "text", "text": "the assistant answers in prose and edits"},
             {"type": "tool_use", "name": "Edit",
              "input": {"file_path": "/fixture/other.md", "old_string": "a", "new_string": "b"}}]}},
        {"type": "user", "timestamp": "2026-09-07T10:00:30Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result",
              "content": "the tool result never reaches the extraction"}]}},
        {"type": "assistant", "timestamp": "2026-09-07T10:00:40Z",
         "message": {"role": "assistant", "model": "claude-fixture-1", "content": [
             {"type": "tool_use", "name": "Bash", "input": {"command": "y" * 400}}]}},
        {"type": "user", "timestamp": "2026-09-07T10:00:50Z",
         "message": {"role": "user",
                     "content": [{"type": "text",
                                  "text": "<system-reminder>injected</system-reminder>"}]}},
    ]
    path = transcript_path(argv[0])
    write(path, "".join(json.dumps(r) + "\n" for r in recs))
    out(path)


def cmd_metascript(argv):
    """A transcript of injected user records only: nothing to extract, and not a failure."""
    recs = [
        {"type": "user", "isMeta": True, "timestamp": "2026-09-05T20:00:00Z",
         "message": {"role": "user", "content": [{"type": "text", "text": "skill injection"}]}},
        {"type": "user", "isMeta": True, "timestamp": "2026-09-05T20:00:10Z",
         "message": {"role": "user",
                     "content": [{"type": "text",
                                  "text": "Base directory for this skill: fixture"}]}},
        {"type": "user", "timestamp": "2026-09-05T20:00:20Z",
         "message": {"role": "user",
                     "content": [{"type": "text",
                                  "text": "<system-reminder>injected</system-reminder>"}]}},
    ]
    path = transcript_path(argv[0])
    write(path, "".join(json.dumps(r) + "\n" for r in recs))
    out(path)


def cmd_replayscript(argv):
    """The two harness shapes that read as the head's own words unless they are handled: a
    resume replay (a whole prior conversation re-sent as ONE user record, ending with the
    message the owner typed), a replay carrying no human marker at all, a synthetic assistant
    record (the harness's stop text), and — as the control for that skip — an ordinary
    assistant record whose text is the same stop words. Two ordinary turns open the file."""
    recs = [
        {"type": "user", "timestamp": "2026-09-06T09:00:00Z",
         "message": {"role": "user",
                     "content": [{"type": "text", "text": "the plain human turn"}]}},
        {"type": "assistant", "timestamp": "2026-09-06T09:00:10Z",
         "message": {"role": "assistant", "model": "claude-fixture-1",
                     "content": [{"type": "text",
                                  "text": "the assistant answers in prose"}]}},
        {"type": "user", "timestamp": "2026-09-06T09:00:20Z",
         "message": {"role": "user", "content": [{"type": "text", "text":
                     "User: an earlier replayed turn\n"
                     "Assistant: an earlier replayed answer\n"
                     "User: the owner's real message"}]}},
        {"type": "assistant", "timestamp": "2026-09-06T09:00:30Z",
         "message": {"role": "assistant", "model": "<synthetic>",
                     "content": [{"type": "text", "text": "No response requested."}]}},
        {"type": "user", "timestamp": "2026-09-06T09:00:40Z",
         "message": {"role": "user", "content": [{"type": "text", "text":
                     "Assistant: a replay with no human marker\n"
                     "Assistant: and a second replayed answer"}]}},
        {"type": "assistant", "timestamp": "2026-09-06T09:00:50Z",
         "message": {"role": "assistant", "model": "claude-fixture-1",
                     "content": [{"type": "text", "text": "No response requested."}]}},
        # The residue: a prompt the owner typed that OPENS by quoting a conversation reads as a
        # replay. Trimming keeps everything after its last human marker, so the owner's own
        # trailing question survives (over-inclusive and visible, never dropped).
        {"type": "user", "timestamp": "2026-09-06T09:01:00Z",
         "message": {"role": "user", "content": [{"type": "text", "text":
                     "User: what did I say here\n"
                     "Assistant: you said that\n"
                     "what do you make of it"}]}},
    ]
    path = transcript_path(argv[0])
    write(path, "".join(json.dumps(r) + "\n" for r in recs))
    out(path)


def cmd_json(argv):
    """One dotted key from a JSON file, so a leg compares a value rather than a substring."""
    with open(argv[0], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    for key in argv[1].split("."):
        if not isinstance(data, dict) or key not in data:
            out("<no key %s>" % argv[1])
            return
        data = data[key]
    out(data if isinstance(data, str) else json.dumps(data))


def cmd_field(argv):
    path, kind, key = argv[0], argv[1], argv[2]
    found = [e for e in events_of(path) if e.get("event") == kind]
    if not found:
        out("<no %s event>" % kind)
        return
    value = found[-1].get(key, "<no key %s>" % key)
    out(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))


def cmd_count(argv):
    path, kind = argv[0], argv[1]
    out(sum(1 for e in events_of(path) if e.get("event") == kind))


def cmd_lines(argv):
    out(len(events_of(argv[0])) if os.path.isfile(argv[0]) else 0)


def cmd_rows(argv):
    out(len(table(read_lines(argv[0]), argv[1])))


def cmd_row(argv):
    rows = table(read_lines(argv[0]), argv[1])
    idx = int(argv[2])
    out(rows[idx] if -len(rows) <= idx < len(rows) else "<no row %s>" % idx)


def cmd_section(argv):
    lines = read_lines(argv[0])
    i = heading_index(lines, argv[1])
    if i < 0:
        out("<no section %s>" % argv[1])
        return
    out(" ".join(x.strip() for x in lines[i + 1:section_end(lines, i)] if x.strip()))


def cmd_bullet(argv):
    lines = read_lines(argv[0])
    i = heading_index(lines, "Morning report")
    if i < 0:
        out("<no morning report>")
        return
    pat = re.compile(r"^\s*[-*]\s+\*\*%s:?\*\*:?\s*(.*)$" % re.escape(argv[1]))
    for j in range(i + 1, section_end(lines, i)):
        m = pat.match(lines[j])
        if m:
            out(m.group(1))
            return
    out("<no bullet %s>" % argv[1])


def cmd_manifest(argv):
    """sha256, size and path for every file under the directories given: the write-proof's
    before-and-after comparison, and the only thing that can show a stray __pycache__."""
    for root in argv:
        for base, dirs, files in os.walk(root):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(base, name)
                try:
                    with open(full, "rb") as handle:
                        digest = hashlib.sha256(handle.read()).hexdigest()
                    size = os.path.getsize(full)
                except OSError as exc:
                    digest, size = "unreadable", str(exc)
                out("%s %s %s" % (digest, size, full))


ALLOWED = ("/tmp", "/private/tmp", "/dev/null", "/dev/stdout", "/dev/stderr")
VERB = re.compile(r"(?:(?<![0-9&])>>?|\b(?:cp|mv|rm|tee|touch|mkdir|install|truncate|dd|ln)\b"
                  r"|sed\s+-i)")
ABS = re.compile(r"(?:^|[\s\"'=(:,])(/[A-Za-z0-9_.@%+-][^\s\"';|)]*)")


def cmd_srcscan(argv):
    """Every line carrying a write verb is checked for an absolute path outside the temp root:
    the suite's own source must score zero, and the planted control file must not."""
    hits = 0
    with open(argv[0], "r", encoding="utf-8", errors="replace") as handle:
        for i, line in enumerate(handle, 1):
            text = line.rstrip("\n")
            if not VERB.search(text):
                continue
            for m in ABS.finditer(text):
                token = m.group(1)
                if token.startswith(ALLOWED):
                    continue
                hits += 1
                out("hit line %d: %s" % (i, text.strip()[:110]))
    out("hits %d" % hits)


def cmd_legs(argv):
    """`--leg TEXT` as shell text: every function the legs define, then every section whose banner
    or verdict line holds TEXT, then the write proof and the summary, which always run. A section
    runs from one `# ---` banner to the next, the first being the one below the manifest; what
    stands above it has run by then. Prints nothing and exits 2 when no section holds TEXT."""
    lines, text = read_lines(argv[0]), argv[1]
    start = next(i for i, line in enumerate(lines)
                 if line.startswith("mk manifest") and "MANIFEST_BEFORE" in line)
    banners = [i for i in range(start, len(lines)) if re.match(r"# -{3,}", lines[i])]
    sections = [lines[a:b] for a, b in zip(banners, banners[1:] + [len(lines)])]
    always = ("write proof", "summary")

    def named(section):
        return section[:1] + [x for x in section[1:] if x.lstrip().startswith("verdict ")]

    picked = [s for s in sections if any(text in line for line in named(s))]
    if not picked:
        sys.stderr.write("PROBE FAILED: no leg's name holds %r\n" % text)
        sys.exit(2)
    functions = []
    for section in sections:
        i, heredoc = 0, None
        while i < len(section):
            line = section[i]
            opens = re.search(r"<<-?\s*['\"]?([A-Za-z0-9_]+)", line)
            if heredoc is not None:
                heredoc = None if line == heredoc else heredoc
            elif re.match(r"[A-Za-z_][A-Za-z0-9_]*\(\) *\{", line):
                end, inner = i, None
                if not line.rstrip().endswith("; }"):
                    while inner is not None or section[end] != "}":
                        starts = re.search(r"<<-?\s*['\"]?([A-Za-z0-9_]+)", section[end])
                        if inner is not None:
                            inner = None if section[end] == inner else inner
                        elif starts:
                            inner = starts.group(1)
                        end += 1
                functions.extend(section[i:end + 1])
                i = end
            elif opens:
                heredoc = opens.group(1)
            i += 1
    kept = [s for s in sections if s in picked
            or any(word in s[0] for word in always)]
    out("printf 'leg filter: %d of %d section(s) hold the text, and the write proof runs\\n'"
        % (len(picked), len(sections)))
    out("\n".join(functions))
    out("\n".join("\n".join(s) for s in kept))


COMMANDS = {"handoff": cmd_handoff, "record": cmd_record, "append": cmd_append,
            "waste": cmd_waste, "transcript": cmd_transcript, "untranscript": cmd_untranscript,
            "pricedscript": cmd_pricedscript,
            "field": cmd_field, "count": cmd_count, "lines": cmd_lines, "rows": cmd_rows,
            "row": cmd_row, "section": cmd_section, "bullet": cmd_bullet,
            "manifest": cmd_manifest, "srcscan": cmd_srcscan, "xscript": cmd_xscript,
            "metascript": cmd_metascript, "replayscript": cmd_replayscript,
            "toolscript": cmd_toolscript, "json": cmd_json, "legs": cmd_legs}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.stderr.write("mk.py: unknown command %r\n" % (sys.argv[1:2],))
        sys.exit(2)
    COMMANDS[sys.argv[1]](sys.argv[2:])
MKPY

# The parent-walk stub: every ps row answers `claude`, so the walk stops at the first parent.
cat > "$WORK/psclaude/ps" <<'PSC'
#!/bin/sh
# ps -o pid=,ppid=,comm= -p PID  →  "<pid> 1 claude"
printf '%s 1 claude\n' "$4"
PSC
# The no-ancestor stub: no row at all, so the walk gives up and the pid source is `none`.
cat > "$WORK/psnone/ps" <<'PSN'
#!/bin/sh
exit 1
PSN
# The process-table stub (the background-task check of `successor`, 2026-10-30): a table built
# around the real caller. The caller is the stub's parent (handsoff.py) and the caller's parent S
# is read with the real /bin/ps; the stub answers S's parent as a planted harness pid PSTABLE_H
# (default 4194301, above any pid this platform issues) named `claude`, and its -A read lists S as
# a session-leading zsh under that pid, plus, with PSTABLE_TASK=1, one session-leading zsh task
# running `sleep 600`. It answers the parent walk (-o pid=,ppid=,comm= -p PID) and the table read
# (-A -o pid=,ppid=,stat=,etime=,args=), nothing else, and logs every call to PSTABLE_LOG.
cat > "$WORK/pstable/ps" <<'PSTABLE'
#!/bin/sh
printf '%s\n' "$*" >> "${PSTABLE_LOG:-/dev/null}"
me=$PPID
s=$(/bin/ps -o ppid= -p "$me" | tr -d ' ')
h=${PSTABLE_H:-4194301}
if [ "$1" = "-A" ]; then
  printf '%s 1 Ss 01:00:00 /fixture/bin/claude --print\n' "$h"
  printf '%s %s Ss 00:01 /bin/zsh -c the call and more\n' "$s" "$h"
  printf '%s %s S 00:01 python3 handsoff.py successor\n' "$me" "$s"
  if [ "${PSTABLE_TASK:-0}" = "1" ]; then
    printf '4194302 %s Ss 12:34 /bin/zsh -c sleep 600; true\n' "$h"
    printf '4194303 4194302 S 12:34 sleep 600\n'
  fi
  exit 0
fi
[ "$2" = "pid=,ppid=,comm=" ] || exit 1
case $4 in
  "$me") printf '%s %s python3\n' "$me" "$s" ;;
  "$s") printf '%s %s /bin/zsh\n' "$s" "$h" ;;
  "$h") printf '%s 1 /fixture/bin/claude\n' "$h" ;;
  *) exit 1 ;;
esac
PSTABLE
# The harness stub: reads the resume instruction from standard input, as the real starter feeds it.
cat > "$WORK/bin/harness" <<STUB
#!/bin/sh
cat > "$WORK/harness-stdin.txt"
printf 'stub harness: args %s\n' "\$*"
STUB
# The stub head for the supervisor legs, driven by its environment: STUB_MODE (limit, nolimit,
# budget, error, complete, nojson, handonly) applies to the first STUB_N invocations; every
# later one hands over as a real head does (head-exit, then its own head-successor) and prints
# a success result. STUB_TOKENS makes it write the transcript the harness would for a fresh
# --session-id. A probe call (--model haiku) fails once, then succeeds. Every invocation
# appends its argv, keeps its stdin and records AIMYTH_HANDSOFF_RUN, keyed by the run.
cat > "$WORK/bin/stubhead" <<'STUBHEAD'
#!/bin/sh
RUN=${AIMYTH_HANDSOFF_RUN:-none}
REC="$SUITE_STORE/spawn-records/$RUN.jsonl"
case " $* " in
  *" --model haiku "*)
    PC="$SUITE_WORK/stub-probe.count"; n=0; [ -f "$PC" ] && n=$(cat "$PC"); n=$((n + 1)); echo "$n" > "$PC"
    if [ "$n" -le 1 ]; then
      printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"You have hit your session limit"}'; exit 1
    fi
    printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"OK","total_cost_usd":0.01}'; exit 0 ;;
esac
CF="$SUITE_WORK/stub-$RUN.count"; n=0; [ -f "$CF" ] && n=$(cat "$CF"); n=$((n + 1)); echo "$n" > "$CF"
printf '%s\n' "$*" >> "$SUITE_WORK/stub-$RUN.args"
printf '%s\n' "${AIMYTH_HANDSOFF_RUN:-unset}" > "$SUITE_WORK/stub-$RUN.env"
cat > "$SUITE_WORK/stub-$RUN.stdin.$n"
sid=""; prev=""
for arg in "$@"; do [ "$prev" = "--session-id" ] && sid=$arg; prev=$arg; done
[ -n "$sid" ] && [ -n "${STUB_TOKENS:-}" ] && "$SUITE_PY" "$SUITE_MK" transcript "$sid" "$STUB_TOKENS" >/dev/null
# STUB_RESUME=1: the head's own first act, as every head the starter starts runs it — its
# run-resume naming its own session (the bootstrap of the resume instruction).
[ -n "$sid" ] && [ "${STUB_RESUME:-0}" = "1" ] && "$SUITE_PY" "$SUITE_MK" append "$REC" "{\"event\":\"run-resume\",\"session\":\"$sid\",\"head\":\"stub head\",\"detail\":\"the head's own run-resume\",\"pid_src\":\"none\"}" >/dev/null
if [ "$n" -le "${STUB_N:-1}" ]; then
  # The repeat-stop legs (2026-10-11): STUB_MODES (comma-separated) gives invocation n the nth
  # word as its mode, else STUB_MODE applies. STUB_PROGRESS (comma-separated) is what invocation
  # n records before it stops: `self`, a boundary whose caller_pid is this process; `selfresume`,
  # that boundary and then a run-resume naming this same process; `foreign`, a boundary naming
  # the supervisor's pid (another live process); `null`, a boundary with no caller_pid; `walk`,
  # the real `boundary` command under the psclaude stub, so the parent walk names this process;
  # `bad`, an unparseable record line; `none` or an empty word, nothing. The hand-over checks
  # (2026-10-30): `refusedhandover`, a gate allowing item2, then the real `handoff --final --band
  # 90`, `successor` and `handoff --final --band 90` again under the psclaude stub (each refused at
  # the cap, exit 10); `oldhandover`, the shape before the call-time cap — a band-50 head-exit and
  # the refusal observation appended by hand; `abortedstarter`, a packed head-exit and then the
  # head's own starter's successor-aborted (timeout), appended by hand.
  mode=${STUB_MODE:-complete}
  [ -n "${STUB_MODES:-}" ] && mode=$(printf '%s\n' "$STUB_MODES" | awk -F, -v n="$n" '{print $n}')
  prog=$(printf '%s\n' "${STUB_PROGRESS:-}" | awk -F, -v n="$n" '{print $n}')
  cp=""
  case $prog in
    self|selfresume) cp=$$; cs=parent-walk ;;
    foreign) cp=$PPID; cs=parent-walk ;;
    null) cp=null; cs=none ;;
  esac
  [ -n "$cp" ] && "$SUITE_PY" "$SUITE_MK" append "$REC" "{\"event\":\"phase-boundary\",\"from\":\"s$n\",\"to\":\"s$n-next\",\"caller_pid\":$cp,\"caller_pid_src\":\"$cs\"}" >/dev/null
  [ "$prog" = "selfresume" ] && "$SUITE_PY" "$SUITE_MK" append "$REC" "{\"event\":\"run-resume\",\"session\":\"${sid:-stub}\",\"head\":\"stub head\",\"detail\":\"the same process again\",\"pid\":$$,\"pid_src\":\"parent-walk\"}" >/dev/null
  [ "$prog" = "walk" ] && env PATH="$SUITE_WORK/psclaude:$PATH" "$SUITE_PY" -B "$SUITE_H" boundary --run "$RUN" --from "s$n" --to "s$n-next" --disposition "a stub boundary" --waste none --next n --meter-line "$SUITE_METER" >>"$SUITE_WORK/stub-$RUN.boundary" 2>&1
  [ "$prog" = "bad" ] && printf '%s\n' '{"event":"phase-boundary","from":"torn' >> "$REC"
  if [ "$prog" = "refusedhandover" ]; then
    "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"gate","item":"item2","decision":"allow","context":100000,"percent":10,"band":0,"armed":true,"metered":true}' >/dev/null
    printf -- '- Next: item2, its next step\n- Needs: nothing\n- Decided: nothing\n' > "$SUITE_WORK/stub-$RUN.pack"
    for c in final successor final; do
      if [ "$c" = final ]; then
        env PATH="$SUITE_WORK/psclaude:$PATH" "$SUITE_PY" -B "${SUITE_HABS:-$SUITE_H}" handoff --run "$RUN" --final --band 90 --inflight-file "$SUITE_WORK/stub-$RUN.pack" --meter-line "$SUITE_METER" >>"$SUITE_WORK/stub-$RUN.refused" 2>&1
      else
        env PATH="$SUITE_WORK/psclaude:$PATH" "$SUITE_PY" -B "${SUITE_HABS:-$SUITE_H}" successor --run "$RUN" --band 90 --meter-line "$SUITE_METER" --harness-bin "$SUITE_WORK/bin/stubhead" --wait-s 1 --max-wait-s 1 --tick-s 1 >>"$SUITE_WORK/stub-$RUN.refused" 2>&1
      fi
      printf 'rc %s %s\n' "$c" "$?" >> "$SUITE_WORK/stub-$RUN.refused"
    done
  fi
  if [ "$prog" = "oldhandover" ]; then
    "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-exit","band":50,"context":"stub","spent_usd":1.0,"pack":true}' >/dev/null
    "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"observation","phase":"","what":"successor refused: no successor left","note":"planted: the shape before the call-time cap"}' >/dev/null
  fi
  if [ "$prog" = "abortedstarter" ]; then
    "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-exit","band":60,"context":"stub","spent_usd":1.0,"pack":true}' >/dev/null
    "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"successor-aborted","reason":"timeout","note":"planted: the starter this head called timed out"}' >/dev/null
  fi
  case $mode in
    limit) printf '%s\n' "{\"type\":\"result\",\"subtype\":\"error_during_execution\",\"is_error\":true,\"result\":\"You've hit your session limit · resets 8:50am (Europe/London)\"}"; exit 1 ;;
    nolimit) printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"Usage limit reached for this session"}'; exit 1 ;;
    fablelimit) printf '%s\n' "{\"type\":\"result\",\"subtype\":\"error_during_execution\",\"is_error\":true,\"result\":\"You've reached your Fable limit. Switch to another model, or manage usage credits at claude.ai/settings/usage, to continue.\"}"; exit 1 ;;
    budget) printf '%s\n' '{"type":"result","subtype":"error_max_budget_usd","is_error":true,"result":"the budget cap was reached"}'; exit 1 ;;
    error) printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"the stub failed"}'; exit 1 ;;
    complete) printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"done without a hand-off"}'; exit 0 ;;
    nojson) printf 'stub: no result line at all\n'; exit 0 ;;
    handonly) "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-exit","band":60,"context":"stub","spent_usd":1.0,"pack":true}' >/dev/null
      printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"handed off, died before successor"}'; exit 0 ;;
    handunpacked) "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-exit","band":60,"context":"stub","spent_usd":1.0,"pack":false}' >/dev/null
      printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"exit recorded without a pack"}'; exit 0 ;;
  esac
fi
"$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-exit","band":60,"context":"stub","spent_usd":1.0,"pack":true}' >/dev/null
"$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-successor","session_id":"sid-by-the-head","pid":1,"budget":1.0}' >/dev/null
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"handed over"}'
exit 0
STUBHEAD
cat > "$WORK/bin/harness2" <<STUB2
#!/bin/sh
cat > "$WORK/harness2-stdin.txt"
printf 'stub harness 2 started\n'
STUB2

# The viewer stubs (the console window). AIMYTH_VIEWER_CMD replaces the whole
# opener command, so with it set NO LEG OF THIS SUITE EVER REACHES THE REAL `open` AND NO REAL
# TERMINAL WINDOW IS EVER OPENED. It is exported for every call below; the legs that test a
# failure point it at the failing stub or unset it with an empty PATH, and the legs on the
# shipped `open` route itself unset it and point AIMYTH_OPEN_BIN — the override of
# the absolute /usr/bin/open the route runs — at the stub `open` below.
# The recording stub appends its whole argv, one argument per line, to the file the current leg
# named in AIMYTH_VIEWER_ARGV: a per-leg file, so a detached starter that opens late can never
# land in a later leg's count.
cat > "$WORK/bin/viewer-stub.sh" <<'VSTUB'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; done
exit 0
VSTUB
cat > "$WORK/bin/viewer-fail.sh" <<'VFAIL'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; done
printf 'stub viewer: this window refuses to open\n' >&2
exit 1
VFAIL
# The stub `open` (the shipped route: `/usr/bin/open <run>-console.command`;
# the legs reach this stub through AIMYTH_OPEN_BIN, never through PATH, which the route does not
# consult). It records its argv as the stub above does and, when STUB_OPEN_CONSOLE=1,
# starts a planted console for the run the command file names — a process carrying
# `watch.py --run R` on its command line, its stdio detached so the opener's captured pipe
# closes when this stub exits — and writes that pid to "$AIMYTH_VIEWER_ARGV.pid" so the leg can
# end it. Without the variable it starts nothing: the empty-window class the opener must report.
cat > "$WORK/openbin/open" <<'OPENSTUB'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; last=$a; done
printf '%s\n' "$*" >> "$AIMYTH_VIEWER_ARGV.calls"   # one line per call
if [ "${STUB_OPEN_CONSOLE:-0}" = "1" ]; then
  run=$(basename "$last" -console.command)   # the command file is the LAST argument (after -g)
  # STUB_CONSOLE_LIFE_S: how long the planted console lives (60 s by default; a console that
  # exits at its own start-up probe lives about a second).
  "$SUITE_PY" -c 'import sys, time; time.sleep(float(sys.argv[1]))' "${STUB_CONSOLE_LIFE_S:-60}" watch.py --run "$run" </dev/null >/dev/null 2>&1 &
  printf '%s\n' "$!" > "$AIMYTH_VIEWER_ARGV.pid"
fi
exit 0
OPENSTUB
# An `open` that fails outright (Launch Services refusing the file): the retry-once shape.
cat > "$WORK/openfail/open" <<'OPENFAIL'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; done
printf '%s\n' "$*" >> "$AIMYTH_VIEWER_ARGV.calls"   # one line per call
printf 'stub open: LSOpenURLsWithRole() failed with error -600\n' >&2
exit 1
OPENFAIL
# The sleeping head for the launch-check legs: a harness that reads its prompt, then lives for
# a few seconds before printing a success result, so a check can find its pid alive.
cat > "$WORK/bin/sleephead" <<'SLEEPHEAD'
#!/bin/sh
cat > /dev/null
sleep "${SLEEPHEAD_S:-8}"
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"done without a hand-off"}'
exit 0
SLEEPHEAD
# A slow `pgrep` for the confirmation-wait legs (critic review finding 3): it sleeps
# PGREP_SLEEP_S, then prints PGREP_PID once more than PGREP_EMPTY_CALLS calls have been made (a
# counter in PGREP_STATE), else nothing. The sleep's own stdio is detached, so a probe the opener
# times out does not hold the opener's pipe open until the sleep ends.
cat > "$WORK/pgrepslow/pgrep" <<'PGREPSLOW'
#!/bin/sh
n=0; [ -f "$PGREP_STATE" ] && n=$(cat "$PGREP_STATE"); n=$((n + 1)); printf '%s' "$n" > "$PGREP_STATE"
sleep "${PGREP_SLEEP_S:-0}" </dev/null >/dev/null 2>&1
if [ "$n" -gt "${PGREP_EMPTY_CALLS:-0}" ] && [ -n "${PGREP_PID:-}" ]; then printf '%s\n' "$PGREP_PID"; fi
exit 0
PGREPSLOW
# A slow `ps` for the launch-check legs (critic review finding 3): every row arrives only after
# PS_SLEEP_S seconds — an etime of 00:05 for `-o etime=`, a `sleep` row otherwise.
cat > "$WORK/psslow/ps" <<'PSSLOW'
#!/bin/sh
sleep "${PS_SLEEP_S:-3}" </dev/null >/dev/null 2>&1
case $2 in etime=) printf '00:05\n' ;; *) printf '%s 1 sleep\n' "$4" ;; esac
exit 0
PSSLOW
# A `ps` that costs a different, compliant amount per query (critic review pass 2 finding 3: a
# check giving the age query and the command query each the whole remaining wait would run two
# probes of 0.75 s and 1 s for 1.75 s against a 1 s deadline). Each query answers after its own sleep, so a
# leg can price the two probes apart.
cat > "$WORK/pssplit/ps" <<'PSSPLIT'
#!/bin/sh
case $2 in
  etime=) sleep "${PS_ETIME_SLEEP_S:-0.75}" </dev/null >/dev/null 2>&1; printf '00:05\n' ;;
  *)      sleep "${PS_ROW_SLEEP_S:-1}" </dev/null >/dev/null 2>&1; printf '%s 1 sleep\n' "$4" ;;
esac
exit 0
PSSPLIT
# A `pgrep` whose every call is scripted (critic finding 8 of the batch's design review: output
# from a failed probe was taken for a sighting): call n prints PGREP_OUT_<n> and exits
# PGREP_RC_<n>, else the last scripted call's pair; the calls are counted in PGREP_STATE.
cat > "$WORK/pgrepexit/pgrep" <<'PGREPEXIT'
#!/bin/sh
n=0; [ -f "$PGREP_STATE" ] && n=$(cat "$PGREP_STATE"); n=$((n + 1)); printf '%s' "$n" > "$PGREP_STATE"
i=$n
while [ "$i" -gt 0 ]; do
  eval "rc=\${PGREP_RC_$i:-}"
  if [ -n "$rc" ]; then eval "out=\${PGREP_OUT_$i:-}"; break; fi
  i=$((i - 1))
done
[ -n "${out:-}" ] && printf '%s\n' "$out"
exit "${rc:-1}"
PGREPEXIT
# A `git` that fails the untracked listing and hands every other call to the real git.
REALGIT=$(command -v git)
cat > "$WORK/gitfail/git" <<GITFAIL
#!/bin/sh
case " \$* " in *" ls-files "*) echo "fatal: the listing fails on purpose" >&2; exit 128 ;; esac
exec "$REALGIT" "\$@"
GITFAIL
mkdir -p "$WORK/nopath"          # an empty directory: no `open` on PATH, and no file for AIMYTH_OPEN_BIN to name
chmod +x "$WORK/psclaude/ps" "$WORK/psnone/ps" "$WORK/pstable/ps" "$WORK/bin/harness" "$WORK/bin/harness2" \
         "$WORK/bin/stubhead" "$WORK/bin/viewer-stub.sh" "$WORK/bin/viewer-fail.sh" \
         "$WORK/openbin/open" "$WORK/openfail/open" "$WORK/bin/sleephead" \
         "$WORK/pgrepslow/pgrep" "$WORK/psslow/ps" "$WORK/pssplit/ps" "$WORK/pgrepexit/pgrep" \
         "$WORK/gitfail/git"
export AIMYTH_VIEWER_CMD="$WORK/bin/viewer-stub.sh"
export AIMYTH_VIEWER_ARGV="$WORK/viewer-default.argv"

# The planted control for the source scan: two write lines aimed outside the temp root, which
# the scan must catch. The target is assembled here rather than written out, so that this
# file's own source carries no absolute write target for the scan to trip over.
CTRL_DIR="/Users""/example/vault/wiki"
{ printf 'cp "$f" %s/index.md\n' "$CTRL_DIR"
  printf 'printf x > %s/log.md\n' "$CTRL_DIR"; } > "$WORK/planted-writer.sh"

# The fixture work tree and its bare remote: every commit leg runs here, never in the vault.
git -c init.defaultBranch=main init -q "$VAULT" || die "cannot init the fixture work tree"
git -C "$VAULT" config user.name "Fixture Owner" || die "cannot set the fixture author name"
git -C "$VAULT" config user.email "owner@example.invalid" || die "cannot set the fixture email"
git -C "$VAULT" config commit.gpgsign false || die "cannot disable signing in the fixture"
git -c init.defaultBranch=main init -q --bare "$REMOTE" || die "cannot init the bare remote"
git -C "$VAULT" remote add origin "$REMOTE" || die "cannot add the fixture remote"
printf 'fixture work tree\n' > "$VAULT/README.md"
git -C "$VAULT" add -A || die "cannot stage the fixture tree"
git -C "$VAULT" commit -q -m "fixture: initial" || die "cannot make the fixture commit"
git -C "$VAULT" push -q -u origin HEAD || die "cannot set the fixture upstream"

# ------------------------------------------------------------------------ leg plumbing -----
N=0; PASSED=0; FAILED=0; why=""; RUNENV=""

# RUNENV holds a leg's environment as NAME=value words separated by spaces. A value may itself hold
# a space (this platform's PATH can carry an entry such as "Application Support"), so the words are
# cut only where a space starts a new NAME= word, one per line, and env takes them with IFS a
# newline and globbing off: a value with no space in it reaches env exactly as before.
runenv() { # a command, run under env with RUNENV's assignments
  set -f; runenv_ifs=$IFS; IFS='
'
  env $(printf '%s\n' "$RUNENV" | sed 's/ \{1,\}\([A-Za-z_][A-Za-z0-9_]*=\)/\
\1/g') "$@"
  runenv_rc=$?
  IFS=$runenv_ifs; set +f
  return "$runenv_rc"
}

run() {
  RC=0
  runenv "$PY" -B "$H" "$@" >"$WORK/out" 2>"$WORK/err" || RC=$?
  cat "$WORK/out" "$WORK/err" >"$WORK/both"
  RUNENV=""
}

mk() { "$PY" "$MK" "$@"; }
real() { "$PY" -c 'import os, sys; sys.stdout.write(os.path.realpath(sys.argv[1]))' "$1"; }
sha_file() { "$PY" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
# handsoff.py resolves the store to its real path (a symlinked /tmp on this platform), so the
# paths it prints and records are compared against this spelling.
REALSTORE=$(real "$STORE")

need_rc() { [ "$RC" = "$1" ] || why="$why; exit $RC, wanted $1"; }
need_out() { grep -q -- "$1" "$WORK/both" || why="$why; output lacks '$1'"; }
need_absent() { if grep -q -- "$1" "$WORK/both"; then why="$why; output carries '$1'"; fi; }
need_eq() { [ "$1" = "$2" ] || why="$why; $3: '$1' != '$2'"; }
need_file() { [ -f "$1" ] || why="$why; no file $1"; }
need_nofile() { [ ! -e "$1" ] || why="$why; file $1 exists"; }
need_lines() { # one line only, for a refusal
  n=$(grep -c 'PROBE FAILED' "$WORK/err")
  [ "$n" = "1" ] || why="$why; $n PROBE FAILED lines, wanted 1"
}
clock_f() { "$PY" -c 'import time; print("%.3f" % time.time())'; }
span_ok() { # $1 start, $2 end, $3 bound in seconds: 'ok', else the span, for a sub-second leg
  "$PY" -c 'import sys
start, end, bound = (float(v) for v in sys.argv[1:4])
print("ok" if end - start <= bound else "%.2f s" % (end - start))' "$1" "$2" "$3"
}
under() { # $1 figure, $2 bound: 'ok', else the figure — a number read off an outcome line
  "$PY" -c 'import sys
print("ok" if float(sys.argv[1]) <= float(sys.argv[2]) else sys.argv[1])' "$1" "$2"
}
wait_field() { # $1 record, $2 kind, $3 key, $4 value, $5 tries of 0.5 s: a detached process
  i=0
  while [ "$i" -lt "$5" ]; do
    [ "$(mk field "$1" "$2" "$3")" = "$4" ] && return 0
    sleep 0.5; i=$((i + 1))
  done
  why="$why; no $2.$3 = '$4' within $5 half-seconds"; return 1
}
starter() { # a foreground starter run: the stubs exit at once, so the loop ends by itself
  RC=0
  runenv "$PY" -B "$H" _starter "$@" >"$WORK/out" 2>"$WORK/err" || RC=$?
  cat "$WORK/out" "$WORK/err" >"$WORK/both"
  RUNENV=""
}
verdict() {
  N=$((N + 1))
  if [ -z "$why" ]; then
    PASSED=$((PASSED + 1)); printf 'ok   %2d  %s\n' "$N" "$1"
  else
    FAILED=$((FAILED + 1)); printf 'FAIL %2d  %s —%s\n' "$N" "$1" "$why"
  fi
  why=""
}

fixture() { # $1 tag, $2 envelope, $3 optional dropped section
  HO="$WORK/handoffs/$1-handoff.md"
  REC="$STORE/spawn-records/$1.jsonl"
  rm -f "$REC"
  mk handoff "$HO" "${3:-}" >/dev/null
  mk record "$REC" "$1" "sid-$1" "$HO" "$2" >/dev/null
}
seed_fixture() { # $1 tag, $2 envelope: a run-open whose session is a launcher's seed (session_kind seed)
  HO="$WORK/handoffs/$1-handoff.md"
  REC="$STORE/spawn-records/$1.jsonl"
  rm -f "$REC"
  mk handoff "$HO" >/dev/null
  mk record "$REC" "$1" "sid-$1" "$HO" "$2" seed >/dev/null
}
plain_fixture() { # $1 tag: the plain-lane-run shape — lane events, NO run-open, no hand-off
  REC="$STORE/spawn-records/$1.jsonl"
  rm -f "$REC"
  "$PY" - "$REC" "$1" <<'PLAINREC'
import json, os, sys, time

path, run = sys.argv[1], sys.argv[2]
base = time.time() - 3600


def stamp(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))


rows = [
    {"event": "lane-open", "lane": "L1", "class": "builder", "model": "fable", "effort": "max"},
    {"event": "lane-spawned", "lane": "L1", "session_id": "sid-plain-l1", "pid": 3001},
    {"event": "lane-closed", "lane": "L1", "exit_class": "completed", "total_cost_usd": 2.50},
    {"event": "lane-open", "lane": "L2", "class": "critic", "model": "opus", "effort": "max"},
    {"event": "lane-closed", "lane": "L2", "exit_class": "error", "total_cost_usd": 1.25},
    {"event": "lane-open", "lane": "L3", "class": "verifier", "model": "fable", "effort": "high"},
]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as fh:
    for i, row in enumerate(rows):
        row.update(ts=stamp(base + i * 60), run=run)
        fh.write(json.dumps(row) + "\n")
PLAINREC
}
arm_resume() { # $1 run: the pre-flight's limit-off (D42) — the grants file carries on_limit resume
  run grants --run "$1" --on-limit resume
  [ "$RC" = 0 ] || die "cannot arm on_limit resume for $1: $(cat "$WORK/both")"
}
gval() { "$PY" -c 'import json, sys; print(json.load(open(sys.argv[1])).get("on_limit"))' "$1"; }
vval() { "$PY" -c 'import json, sys; print(json.load(open(sys.argv[1])).get("viewer"))' "$1"; }
# The viewer stub's recording file, one per leg (see the stub above).
VIEWER_ARGV="$WORK/viewer-default.argv"
viewer_use() { VIEWER_ARGV="$WORK/viewer-$1.argv"; rm -f "$VIEWER_ARGV" "$VIEWER_ARGV.calls"
               export AIMYTH_VIEWER_ARGV="$VIEWER_ARGV"; }
viewer_calls() { if [ -f "$VIEWER_ARGV" ]; then grep -c . "$VIEWER_ARGV"; else echo 0; fi; }
viewer_has() { [ -f "$VIEWER_ARGV" ] || return 1; grep -q -F -- "$1" "$VIEWER_ARGV"; }
need_viewer_arg() { viewer_has "$1" || why="$why; the viewer stub was not called with '$1'"; }
need_no_viewer() { n=$(viewer_calls)
                   [ "$n" = "0" ] || why="$why; the viewer stub was called ($n arguments)"; }
console_cmd() { printf '%s/spawn-records/%s-console.command\n' "$REALSTORE" "$1"; }
# A live console to plant: a process whose command line carries the marker in one of the two
# spellings, so console_alive() finds it exactly as it finds a real console.
PLANTED=""
plant_console() { # $1 run, $2 spelling (watch.py | handsoff.py)
  case $2 in
    handsoff.py) "$PY" -c 'import time; time.sleep(90)' handsoff.py watch --run "$1" & ;;
    *)           "$PY" -c 'import time; time.sleep(90)' watch.py --run "$1" & ;;
  esac
  PLANTED=$!
  sleep 1   # the process must be in the table before any probe reads it
  kill -0 "$PLANTED" || die "the planted console for $1 died before the leg could probe it"
}
kill_console() {
  if [ -n "$PLANTED" ]; then kill "$PLANTED"; wait "$PLANTED" || :; PLANTED=""; fi
  return 0
}

printf 'handsoff.py suite · target %s\n' "$H"
printf 'fixtures %s · vault fixture %s\n\n' "$WORK" "$VAULT"

MANIFEST_BEFORE="$WORK/manifest-before.txt"
mk manifest "$SKILL_DIR" "$HOOKS_DIR" > "$MANIFEST_BEFORE"

# The filter's section list, sourced here so every fixture and function above stands; its summary
# section ends the run.
if [ -n "$ONLY_LEG" ]; then
  mk legs "$SRC" "$ONLY_LEG" > "$WORK/legs.sh" || exit 2
  sh -n "$WORK/legs.sh" || die "the filter's section list does not parse"
  . "$WORK/legs.sh"
  die "the filter's section list ended before its summary"
fi

# ------------------------------------------------------------------------- run-open --------
HO="$WORK/handoffs/open-handoff.md"; mk handoff "$HO" >/dev/null
REC="$STORE/spawn-records/ropen.jsonl"; rm -f "$REC"
run run-open --run ropen --session sid-open --head "fixture head" --regime multi \
    --regime-src owner --handoff "$HO" --detail "opening leg" --pid 4242 --envelope-usd 200
need_rc 0
need_out "pid 4242 (arg)"
need_eq "$(mk field "$REC" run-open pid_src)" "arg" "pid_src"
need_eq "$(mk field "$REC" run-open pid)" "4242" "pid"
need_eq "$(mk lines "$REC")" "1" "record lines"
verdict "run-open: --pid N recorded with pid_src arg"

REC2="$STORE/spawn-records/ropen2.jsonl"; rm -f "$REC2"
RUNENV="PATH=$WORK/psclaude:$PATH"
run run-open --run ropen2 --session sid-open2 --head "fixture head" --regime single \
    --regime-src head --handoff "$HO" --detail "parent walk"
need_rc 0
need_out "(parent-walk)"
need_eq "$(mk field "$REC2" run-open pid_src)" "parent-walk" "pid_src"
case $(mk field "$REC2" run-open pid) in
  ''|*[!0-9]*) why="$why; the parent-walk pid is not a number" ;;
esac
verdict "run-open: the parent walk finds the harness ancestor (pid_src parent-walk)"

REC3="$STORE/spawn-records/ropen3.jsonl"; rm -f "$REC3"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-open --run ropen3 --session sid-open3 --head "fixture head" --regime multi \
    --regime-src owner --handoff "$HO" --detail "no ancestor"
need_rc 0
need_out "pid none (none)"
need_eq "$(mk field "$REC3" run-open pid_src)" "none" "pid_src"
need_eq "$(mk field "$REC3" run-open pid)" "<no key pid>" "pid absent"
verdict "run-open: no harness ancestor gives pid_src none and no pid key"

run run-open --run ropen --session sid-again --head "fixture head" --regime multi \
    --regime-src owner --handoff "$HO" --detail "a second opening"
need_rc 2
need_out "already has a run-open"
need_lines
need_eq "$(mk lines "$REC")" "1" "record lines after the refusal"
verdict "run-open: a second run-open is refused (exit 2, one line, nothing appended)"

REC4="$STORE/spawn-records/ropen4.jsonl"; rm -f "$REC4"
run run-open --run ropen4 --session sid-open4 --head "h" --regime multi --regime-src owner \
    --handoff "$WORK/handoffs/not-there.md" --detail "missing document"
need_rc 2
need_out "hand-off document not found"
need_lines
need_nofile "$REC4"
verdict "run-open: a missing hand-off document is refused (exit 2, no record written)"

REC5="$STORE/spawn-records/ropen5.jsonl"; rm -f "$REC5"
run run-open --run ropen5 --session sid-open5 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "dry run" --dry-run
need_rc 0
need_out "dry run"
need_nofile "$REC5"
verdict "run-open: --dry-run prints the event and writes no record"

# SL-2 (register 2026-09-20 20:0x): a runbook that never names the boundary command. The planted
# case is the entry's own, the bare word on a hand-off row; the controls are a runbook naming the
# command, in each spelling, and a stage with no runbook at all, which opens and says so.
RBOOK="$WORK/runbook-none.md"
printf '# RUNBOOK\n- Items: item0, item1\n- The hand-off row is written at each boundary.\n' > "$RBOOK"
REC6="$STORE/spawn-records/ropen6.jsonl"; rm -f "$REC6"
run run-open --run ropen6 --session sid-open6 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "no boundary line" --runbook "$RBOOK"
need_rc 2
need_out "never names .handsoff.py boundary."
need_out "nothing written"
need_lines
need_nofile "$REC6"
run run-open --run ropen6 --session sid-open6 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "no boundary line" --runbook "$RBOOK" --dry-run
need_rc 2
need_nofile "$REC6"
mkdir -p "$STORE/stages/ropen7"
cp "$RBOOK" "$STORE/stages/ropen7/RUNBOOK.md"
REC7="$STORE/spawn-records/ropen7.jsonl"; rm -f "$REC7"
run run-open --run ropen7 --session sid-open7 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "the stage's own runbook"
need_rc 2
need_out "stages/ropen7/RUNBOOK.md never names"
need_nofile "$REC7"
printf -- '- Each item ends with `handsoff.py boundary --run R`.\n' >> "$STORE/stages/ropen7/RUNBOOK.md"
run run-open --run ropen7 --session sid-open7 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "the stage's own runbook"
need_rc 0
need_out "names the boundary command"
need_file "$REC7"
printf -- '- `boundary` and `close` run without --commit.\n' > "$WORK/runbook-tick.md"
REC8="$STORE/spawn-records/ropen8.jsonl"; rm -f "$REC8"
run run-open --run ropen8 --session sid-open8 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "the command in backticks" --runbook "$WORK/runbook-tick.md"
need_rc 0
need_file "$REC8"
run run-open --run ropen9 --session sid-open9 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "no such file" --runbook "$WORK/no-such-runbook.md"
need_rc 2
need_out "is not a file"
REC10="$STORE/spawn-records/ropen10.jsonl"; rm -f "$REC10"
run run-open --run ropen10 --session sid-open10 --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "no runbook anywhere"
need_rc 0
need_out "so no boundary line was checked"
need_file "$REC10"
verdict "SL-2 (fails on old): run-open refuses a runbook, named or the stage's own, that never names the boundary command, writing nothing, and opens on one that names it or where there is none, saying which"

# ------------------------------------------------------------------------ run-resume -------
fixture rres 200
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rres --session sid-second --head "successor head" --detail "resumed" \
    --pid 5150
need_rc 0
need_out "session sid-seco (arg)"
need_eq "$(mk field "$REC" run-resume session)" "sid-second" "session"
need_eq "$(mk field "$REC" run-resume pid)" "5150" "pid"
verdict "run-resume: an explicit session and --pid are recorded"

fixture rres2 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)"}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-fromstarter","pid":999901,"budget":3.5}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rres2 --session auto --head "successor head" --detail "auto session"
need_rc 0
need_out "(head-successor)"
need_eq "$(mk field "$REC" run-resume session)" "sid-fromstarter" "session from the starter"
verdict "run-resume: --session auto takes the last head-successor's session id"

fixture rres3 200
run run-resume --run rres3 --session auto --head "h" --detail "no successor to read"
need_rc 2
need_out "needs a head-successor event"
need_lines
need_eq "$(mk count "$REC" run-resume)" "0" "run-resume events"
verdict "run-resume: --session auto without a head-successor is refused (exit 2)"

# -------------------------------------------------------------------------- boundary -------
fixture rbnd 200
mk waste "$REC" rbnd "$WORK/handoffs/no-such-report.md" >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rbnd --from 2 --to 3 --disposition "phase 2 closed" \
    --waste "real \$0 · arguable \$0.3 · structural \$1.5" --next "phase 3" \
    --meter-line "$METER" --shipped "the suite" --waits "nothing" --saving "n/a"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary idle_min)" "9.5" "idle_min"
need_eq "$(mk field "$REC" phase-boundary denials)" "3" "denials"
need_eq "$(mk field "$REC" phase-boundary over_cap_reports)" "1" "over_cap_reports"
need_eq "$(mk field "$REC" phase-boundary respawn_cost_usd)" "5.0" "respawn_cost_usd"
need_eq "$(mk field "$REC" phase-boundary rewrites)" "3" "rewrites"
need_out "idle 9.5 min · denials 3 · over-cap 1 · re-spawn \$5.00 · rewrites 3"
need_out "1 report(s) not word-counted"
verdict "boundary: the five waste fields come from the planted close-outs"

need_eq "$(mk rows "$HO" "Trace")" "2" "rows in the first trace table"
need_eq "$(mk rows "$HO" "Trace archive")" "1" "rows in the decoy table"
case $(mk row "$HO" "Trace" -1) in
  *"2 → 3"*"phase 2 closed"*) : ;;
  *) why="$why; the new trace row is not the last row of the first table" ;;
esac
verdict "boundary: the trace row lands in the FIRST trace table, the decoy untouched"

need_eq "$(mk bullet "$HO" "Warnings raised and handling")" \
        "see \`## Findings ledger\` (2 lines; a wrong figure on purpose, so a refresh is observable)." \
        "warnings bullet"
case $(mk bullet "$HO" "Spend against the envelope") in
  *"session \$16.56"*"envelope \$200.0"*) : ;;
  *) why="$why; the spend bullet does not carry the billed line and the envelope" ;;
esac
need_eq "$(mk bullet "$HO" "What shipped")" "the suite" "shipped bullet"
verdict "boundary: the morning report's figures are refreshed from the meter and the ledger"

printf 'a checkpoint change %s\n' "$N" > "$VAULT/notes.txt"
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rbnd --from 3 --to 4 --disposition "checkpoint" --waste "none" \
    --next "phase 4" --meter-line "$METER" --commit "fixture: a checkpoint commit"
need_rc 0
SHA=$(mk field "$REC" phase-boundary commit)
case $SHA in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) : ;;
  *) why="$why; the commit field is '$SHA', not a short sha" ;;
esac
IDENTS=$(git -C "$VAULT" log -1 --format='%an|%ae|%cn|%ce')
need_eq "$IDENTS" "Fixture Owner|owner@example.invalid|Fixture Owner|owner@example.invalid" \
        "author and committer"
if git -C "$VAULT" log -1 --format='%B' | grep -q -E 'Co-Authored|Generated'; then
  why="$why; the commit body carries an attribution line"
fi
verdict "boundary --commit: a real commit, author equal to committer, no attribution"

RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rbnd --from 4 --to 5 --disposition "nothing changed" --waste "none" \
    --next "phase 5" --meter-line "$METER" --commit "fixture: nothing to commit"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary commit)" "none (nothing to commit)" "commit field"
need_out "commit none (nothing to commit)"
verdict "boundary --commit: a clean tree gives 'none (nothing to commit)'"

printf 'another change %s\n' "$N" > "$VAULT/notes.txt"
BEFORE_COMMITS=$(git -C "$VAULT" rev-list --count HEAD)
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rbnd --from 5 --to 6 --disposition "attributed message" --waste "none" \
    --next "phase 6" --meter-line "$METER" \
    --commit "fixture: a message with Co-Authored-By in it"
need_rc 0
case $(mk field "$REC" phase-boundary commit) in
  failed*Co-Authored*) : ;;
  *) why="$why; the attributed message was not refused" ;;
esac
need_eq "$(git -C "$VAULT" rev-list --count HEAD)" "$BEFORE_COMMITS" "commit count"
verdict "boundary --commit: a message carrying an attribution line is refused (failed <reason>)"

RUNENV="PATH=$WORK/psnone:$PATH GIT_COMMITTER_NAME=Someone GIT_COMMITTER_EMAIL=someone@example.invalid"
run boundary --run rbnd --from 6 --to 7 --disposition "split identity" --waste "none" \
    --next "phase 7" --meter-line "$METER" --commit "fixture: split identity"
need_rc 0
case $(mk field "$REC" phase-boundary commit) in
  failed*"differs from committer ident"*) : ;;
  *) why="$why; a committer differing from the author was not refused" ;;
esac
need_eq "$(git -C "$VAULT" rev-list --count HEAD)" "$BEFORE_COMMITS" "commit count"
verdict "boundary --commit: author unequal to committer is refused, nothing committed"

fixture rbnd2 200 "trace,decoy"
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rbnd2 --from 1 --to 2 --disposition "no trace table" --waste "none" \
    --next "next" --meter-line "$METER"
need_rc 3
need_out "NOT refreshed"
need_out "no table under a '## Trace' heading"
need_eq "$(mk count "$REC" phase-boundary)" "1" "phase-boundary events"
verdict "boundary: a hand-off without a trace table exits 3 with the event still written"

fixture rbnd3 200
SUM_BEFORE=$(mk manifest "$WORK/handoffs" | grep rbnd3)
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rbnd3 --from 1 --to 2 --disposition "dry" --waste "none" --next "n" \
    --meter-line "$METER" --dry-run
need_rc 0
need_out "boundary: dry run"
need_eq "$(mk count "$REC" phase-boundary)" "0" "phase-boundary events"
need_eq "$(mk manifest "$WORK/handoffs" | grep rbnd3)" "$SUM_BEFORE" "hand-off checksum"
verdict "boundary --dry-run: no event, no hand-off change"

# ---------------------------------------------------------------------------- ledger -------
fixture rled 200
run ledger --run rled --phase 2 --what "a planted finding" \
    --evidence "the suite's own fixture" --routing "no action"
need_rc 0
need_out "row 3 appended"
need_eq "$(mk rows "$HO" "Findings ledger")" "3" "ledger rows"
case $(mk row "$HO" "Findings ledger" -1) in
  *"a planted finding"*"no action"*) : ;;
  *) why="$why; the ledger row is not the last row" ;;
esac
need_eq "$(mk field "$REC" observation what)" "a planted finding" "observation"
verdict "ledger: the row is appended and an observation recorded"

fixture rled2 200 ledger
run ledger --run rled2 --phase 2 --what "no table to take it" --evidence "e" --routing "r"
need_rc 2
need_out "no table under a '## Findings ledger' heading"
need_lines
need_eq "$(mk count "$REC" observation)" "0" "observation events"
verdict "ledger: a hand-off without the ledger table is refused (exit 2)"

fixture rled3 200
SUM_BEFORE=$(mk manifest "$WORK/handoffs" | grep rled3)
run ledger --run rled3 --phase 2 --what "dry" --evidence "e" --routing "r" --dry-run
need_rc 0
need_out "ledger: dry run"
need_eq "$(mk rows "$HO" "Findings ledger")" "2" "ledger rows"
need_eq "$(mk manifest "$WORK/handoffs" | grep rled3)" "$SUM_BEFORE" "hand-off checksum"
verdict "ledger --dry-run: no row, no observation, no file change"

# ------------------------------------ the seeded ledger (register 2026-09-14 19:35; F2) -------
# A Findings ledger section may contain only a prose placeholder. Its first append must
# create the table before recording the event.
# Must fire: the first call creates the table directly under the heading, keeps the prose below
# it, appends the row and says so; the next call finds one table.
fixture rledp 200 ledger-prose
run ledger --run rledp --phase 2 --what "the first finding" --evidence "e" --routing "r" --dry-run
need_rc 0
need_out "the table would be created under the heading first"
need_eq "$(mk rows "$HO" "Findings ledger")" "0" "dry run: no table yet"
run ledger --run rledp --phase 2 --what "the first finding" --evidence "e" --routing "r"
need_rc 0
need_out "ledger: the '## Findings ledger' section held prose and no table — the five-column header was created directly under the heading, the prose kept below it"
need_out "row 1 appended"
need_eq "$(mk rows "$HO" "Findings ledger")" "1" "one row under the created table"
need_eq "$(grep -c '^| Time | Item | Finding | Evidence | Routing |$' "$HO")" "1" "the header exists once"
need_eq "$(grep -c 'seeded by the first head (a launcher placeholder)' "$HO")" "1" "the prose line survives"
case $(mk section "$HO" "Findings ledger") in
  "| Time | Item | Finding | Evidence | Routing | |---|---|---|---|---| |"*"the first finding"*"The findings ledger is seeded by the first head"*) : ;;
  *) why="$why; the section is not header, separator, row, prose: $(mk section "$HO" "Findings ledger")" ;;
esac
need_eq "$(mk field "$REC" observation what)" "the first finding" "the observation"
run ledger --run rledp --phase 2 --what "the second finding" --evidence "e" --routing "r"
need_rc 0
need_absent "was created"
need_eq "$(mk rows "$HO" "Findings ledger")" "2" "the second call appends to the same table"
need_eq "$(grep -c '^| Time | Item | Finding | Evidence | Routing |$' "$HO")" "1" "still one header"
verdict "ledger on a seeded hand-off (register 2026-09-14 19:35, must fire): a Findings ledger section with a prose line and no table gets the table created under its heading, the prose kept below, the row appended and one line saying so; the next call finds one table"

fixture rdecp 200 ledger-prose
run decision --run rdecp --phase 2 --what "a decision on a seeded hand-off" --grant "owner"
need_rc 0
need_out "decision: the '## Findings ledger' section held prose and no table"
need_eq "$(mk rows "$HO" "Findings ledger")" "1" "one row"
need_eq "$(grep -c '^| Time | Item | Finding | Evidence | Routing |$' "$HO")" "1" "the header exists once"
need_eq "$(grep -c 'seeded by the first head (a launcher placeholder)' "$HO")" "1" "the prose line survives"
need_eq "$(mk count "$REC" decision)" "1" "the decision event"
verdict "decision on a seeded hand-off (must fire): the same repair, the row and the decision event written"

# run-open does the same check once at the open, so the seed is repaired before the first head.
HO="$WORK/handoffs/ropenled-handoff.md"; mk handoff "$HO" ledger-prose >/dev/null
REC="$STORE/spawn-records/ropenled.jsonl"; rm -f "$REC"
run run-open --run ropenled --session sid-openled --head "fixture head" --regime multi \
    --regime-src owner --handoff "$HO" --detail "a seeded ledger" --pid 1 --dry-run
need_rc 0
need_out "run-open: warn: the hand-off's '## Findings ledger' section held no table — the five-column header would be seeded"
need_eq "$(grep -c '^| Time | Item | Finding | Evidence | Routing |$' "$HO")" "0" "dry run: nothing seeded"
run run-open --run ropenled --session sid-openled --head "fixture head" --regime multi \
    --regime-src owner --handoff "$HO" --detail "a seeded ledger" --pid 1
need_rc 0
need_out "run-open: warn: the hand-off's '## Findings ledger' section held no table — the five-column header was seeded"
need_eq "$(mk field "$REC" run-open ledger_table)" "seeded" "the run-open event says so"
need_eq "$(grep -c '^| Time | Item | Finding | Evidence | Routing |$' "$HO")" "1" "the header seeded once"
need_eq "$(grep -c 'seeded by the first head (a launcher placeholder)' "$HO")" "1" "the prose kept"
run ledger --run ropenled --phase 0 --what "the head's first finding" --evidence "e" --routing "r"
need_rc 0
need_absent "was created"
need_eq "$(mk rows "$HO" "Findings ledger")" "1" "the first ledger call appends to the seeded table"
verdict "run-open on a seeded hand-off: the ledger table is seeded at the open (the event carries ledger_table seeded; the dry run only warns) and the head's first ledger call needs no repair"

# Must not fire: a hand-off WITH the table changes nowhere but the new row (the control that
# the repair never runs there: no 'was created' line, and the record of a fixture run-open
# reads ledger_table table); no heading at all still fails as before (the rled2 leg above); two
# headings and no table under the first refuse naming both lines; pipe-led lines that make no
# table refuse, nothing seeded over them.
fixture rledok 200
BEFORE=$(grep -v 'a planted finding' "$HO" | shasum)
run ledger --run rledok --phase 2 --what "a planted finding" --evidence "e" --routing "r"
need_rc 0
need_absent "was created"
need_eq "$(grep -v 'a planted finding' "$HO" | shasum)" "$BEFORE" "every byte outside the new row unchanged"
HO2="$WORK/handoffs/ropenok-handoff.md"; mk handoff "$HO2" >/dev/null
REC2="$STORE/spawn-records/ropenok.jsonl"; rm -f "$REC2"
run run-open --run ropenok --session sid-openok --head "fixture head" --regime multi \
    --regime-src owner --handoff "$HO2" --detail "a ledger with its table" --pid 1
need_rc 0
need_absent "Findings ledger"
need_eq "$(mk field "$REC2" run-open ledger_table)" "table" "run-open records the table it found"
verdict "ledger on a hand-off with the table (must not fire): only the new row changes, nothing is created, and run-open neither warns nor seeds (ledger_table table)"

fixture rledtwo 200 ledger-two
L1=$(grep -n '^## Findings ledger' "$HO" | sed -n 1p | cut -d: -f1)
L2=$(grep -n '^## Findings ledger' "$HO" | sed -n 2p | cut -d: -f1)
run ledger --run rledtwo --phase 2 --what "two headings" --evidence "e" --routing "r"
need_rc 2
need_out "two '## Findings ledger' headings in"
need_out "(lines $L1 and $L2): nothing written — keep one heading"
need_lines
need_eq "$(grep -c '^| Time | Item | Finding | Evidence | Routing |$' "$HO")" "0" "nothing seeded"
need_eq "$(mk count "$REC" observation)" "0" "no observation"
run decision --run rledtwo --phase 2 --what "two headings" --grant "owner"
need_rc 2
need_out "(lines $L1 and $L2): nothing written — keep one heading"
need_eq "$(mk count "$REC" decision)" "0" "no decision event"
verdict "ledger and decision with two Findings ledger headings and no table under the first (must not fire): refused, both heading lines named ($L1 and $L2), nothing written"

# Fold (critic 2026-09-17, medium): two headings refuse whether or not the FIRST holds a table —
# the headings are counted before any other decision; the table under the first is left as it
# was (no row appended). The single-heading controls are the two legs above: a table appends
# the row alone, prose seeds the table.
fixture rledtt 200 ledger-two-table
L1=$(grep -n '^## Findings ledger' "$HO" | sed -n 1p | cut -d: -f1)
L2=$(grep -n '^## Findings ledger' "$HO" | sed -n 2p | cut -d: -f1)
SUM_TT=$(shasum "$HO")
run ledger --run rledtt --phase 2 --what "two headings, a table under the first" --evidence "e" --routing "r"
need_rc 2
need_out "two '## Findings ledger' headings in"
need_out "(lines $L1 and $L2): nothing written — keep one heading"
need_lines
need_eq "$(shasum "$HO")" "$SUM_TT" "the hand-off is untouched (no row under the first table)"
need_eq "$(mk count "$REC" observation)" "0" "no observation"
run decision --run rledtt --phase 2 --what "two headings, a table under the first" --grant "owner"
need_rc 2
need_out "(lines $L1 and $L2): nothing written — keep one heading"
need_eq "$(shasum "$HO")" "$SUM_TT" "the hand-off is untouched after decision too"
need_eq "$(mk count "$REC" decision)" "0" "no decision event"
HO2="$WORK/handoffs/ropentt-handoff.md"; mk handoff "$HO2" ledger-two-table >/dev/null
REC2="$STORE/spawn-records/ropentt.jsonl"; rm -f "$REC2"
run run-open --run ropentt --session sid-opentt --head "fixture head" --regime multi \
    --regime-src owner --handoff "$HO2" --detail "two ledger headings" --pid 1
need_rc 0
need_out "run-open: warn: the hand-off has two '## Findings ledger' headings: ledger and decision will refuse until one heading remains"
need_eq "$(mk field "$REC2" run-open ledger_table)" "two headings" "run-open records the state"
verdict "ledger and decision with two Findings ledger headings and a table under the first (fold, must not fire): refused all the same, both heading lines named ($L1 and $L2), the hand-off untouched; run-open warns and records two headings"

fixture rledbrk 200 ledger-broken
run ledger --run rledbrk --phase 2 --what "a broken table" --evidence "e" --routing "r"
need_rc 2
need_out "no table under a '## Findings ledger' heading"
need_lines
need_eq "$(grep -c '^| Time | Item | Finding | Evidence | Routing |$' "$HO")" "0" "nothing seeded over the broken table"
verdict "ledger on a section whose pipe-led lines make no table (must not fire): refused as before, nothing seeded over it"

# ------------------------------------------------- ledger --observation and the plain shape --
# The plain-lane-run shape: a record lane.py opened, with lane events and no run-open. The legs
# above are the control throughout — the same commands on a record that HAS a run-open.
plain_fixture pled
LINES_BEFORE=$(mk lines "$REC")
HO_SUM_BEFORE=$(mk manifest "$WORK/handoffs")
run ledger --run pled --observation "the head's peer name for this run"
need_rc 0
need_out "observation recorded"
need_out "plain lane run (no run-open)"
need_out "no hand-off row"
need_eq "$(mk count "$REC" observation)" "1" "observation events"
need_eq "$(mk field "$REC" observation what)" "the head's peer name for this run" "what"
need_eq "$(mk field "$REC" observation phase)" "" "phase (empty without --phase)"
need_eq "$(mk lines "$REC")" "$((LINES_BEFORE + 1))" "record lines"
need_eq "$(mk manifest "$WORK/handoffs")" "$HO_SUM_BEFORE" "the hand-off directory's checksums"
verdict "ledger --observation: one observation on a record with no run-open, phase empty, no hand-off row, exit 0"

run ledger --run pled --observation "an observation with a phase" --phase 3
need_rc 0
need_eq "$(mk field "$REC" observation phase)" "3" "phase (given)"
need_eq "$(mk count "$REC" observation)" "2" "observation events"
verdict "ledger --observation --phase: the phase is carried when it is given"

LINES_BEFORE=$(mk lines "$REC")
run ledger --run pled --observation "a dry observation" --dry-run
need_rc 0
need_out "ledger --observation: dry run"
need_out "plain lane run (no run-open)"
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines (dry run appends nothing)"
need_eq "$(mk count "$REC" observation)" "2" "observation events after the dry run"
verdict "ledger --observation --dry-run: the event is printed and nothing is appended"

LINES_BEFORE=$(mk lines "$REC")
run ledger --run pled --phase 2 --what "a finding with nowhere to go" --evidence "e" --routing "r"
need_rc 2
need_out "no run-open event"
need_out "--observation"
need_lines
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines (nothing appended)"
verdict "ledger (the row form) on a plain record: refused as before, exit 2, and the message names --observation as the form that works there"

run ledger --run pled --phase 2 --what "no evidence given"
need_rc 2
need_out "--evidence"
need_out "--observation"
verdict "ledger: a partial row form names the flags it lacks and the observation form (exit 2)"

# ---- SL-1 (register 2026-10-15 01:33 d): a typed clock placeholder in the head's own text ----
# Each writer is planted with a token and must refuse, naming the flag, with nothing written. The
# controls are a register heading in its brackets, a whole time, and two shapes that are no token.
fixture rclock 200
CLOCKN=$(mk lines "$REC")
CLOCKH=$(sha_file "$HO")
run ledger --run rclock --phase 1 --what "the owner's go at 14:3x" --evidence "the prompt" --routing "none"
need_rc 2
need_out "ledger: --what carries the typed clock placeholder 14:3x"
need_out "nothing written"
need_lines
run ledger --run rclock --observation "scored at 00:5x"
need_rc 2
need_out "--observation carries the typed clock placeholder 00:5x"
run ledger --run rclock --phase 1 --what "fine" --evidence "read at 19:1x" --routing "none" --dry-run
need_rc 2
need_out "--evidence carries the typed clock placeholder 19:1x"
run decision --run rclock --phase 1 --what "go on" --grant "owner message 13:1x"
need_rc 2
need_out "decision: --grant carries the typed clock placeholder 13:1x"
run boundary --run rclock --from 1 --to 2 --disposition "closed at 23:2X" --waste "none" --next "n" --meter-line "$METER"
need_rc 2
need_out "boundary: --disposition carries the typed clock placeholder 23:2X"
run boundary --run rclock --from 1 --to 2 --disposition "closed" --waste "wait from 05:0x" --next "n" --meter-line "$METER"
need_rc 2
need_out "boundary: --waste carries"
run handoff --run rclock --inflight "$(printf -- '- Next: at 01:1x\n- Needs: nothing\n- Decided: nothing')"
need_rc 2
need_out "handoff: --inflight carries the typed clock placeholder 01:1x"
run handoff --run rclock --set "shipped=the build, at 02:2x"
need_rc 2
need_out "handoff: --set shipped carries"
printf 'the bullet, at 22:4x\n' > "$WORK/clock-bullet.txt"
run handoff --run rclock --set-file "shipped=$WORK/clock-bullet.txt"
need_rc 2
need_out "handoff: --set-file shipped carries"
need_eq "$(mk lines "$REC")" "$CLOCKN" "no refusal wrote a record line"
need_eq "$(sha_file "$HO")" "$CLOCKH" "no refusal touched the hand-off"
run ledger --run rclock --observation "entry [2026-09-20 20:0x] and [2026-09-23 20:3x b] stand"
need_rc 0
run ledger --run rclock --phase 1 --what "at 12:30:05, a 1:5x zoom and the label 12:3xy" --evidence "e" --routing "r"
need_rc 0
need_eq "$(mk lines "$REC")" "$((CLOCKN + 2))" "the controls wrote their lines"
verdict "SL-1 (fails on old): ledger, decision, boundary and handoff refuse a typed clock placeholder in the head's text, dry run or not, naming the flag and writing nothing, while a bracketed register stamp, a whole time and a longer token pass"

mkdir -p "$STORE/stages/rclock2"
fixture rclock2 200
printf 'the head typed 19:5x here\n' > "$STORE/stages/rclock2/notes.md"
printf 'no token, a whole 19:53:02\n' > "$STORE/stages/rclock2/clean.md"
printf 'an older 20:1x\n' > "$STORE/stages/rclock2/older.md"
"$PY" -c 'import os, sys, time; t = time.time() - 100000; os.utime(sys.argv[1], (t, t))' "$STORE/stages/rclock2/older.md"
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rclock2 --from 1 --to 2 --disposition "closed" --waste "none" --next "n" --meter-line "$METER"
need_rc 0
need_out "boundary: warn: the stage document .*notes.md carries the typed clock placeholder 19:5x"
need_absent "clean.md"
need_absent "older.md"
verdict "SL-1 (fails on old): a boundary warns of a stage document changed since the last boundary that carries a placeholder, and stays quiet on a clean one and on one older than that boundary"

# the clean control: the same --observation on a record that HAS a run-open appends the
# observation and NO ledger row (the head's aside that is not a finding)
fixture rledobs 200
ROWS_BEFORE=$(mk rows "$HO" "Findings ledger")
run ledger --run rledobs --observation "an aside that is not a finding"
need_rc 0
need_out "run-open present"
need_eq "$(mk count "$REC" observation)" "1" "observation events"
need_eq "$(mk rows "$HO" "Findings ledger")" "$ROWS_BEFORE" "ledger rows (unchanged)"
verdict "ledger --observation on a run-open record: the observation alone, the findings ledger untouched (the control for the plain leg)"


# ------------------------------------------------------------- fit (2026-09-14) -------------
# Fit-based continuation: the gate asks whether the NEXT item fits
# under the belt (the third edge, 90 %) instead of comparing the total with the 80 % mark. The
# window here is the default 1M; the prior item is 12.5 % of it, the pack allowance 2 %.
fixture rfit1 200
SID=sid-rfit1
mk transcript "$SID" 700000 >/dev/null
# The billed line in hand keeps the spend measured: these legs claim the fit, and two armed
# gates with an unmeterable spend would be two consecutive unmetered gates (the fold of
# 2026-09-17), which is another leg's claim.
run gate --run rfit1 --to "item one" --meter-line "$METER"
need_rc 0
need_out "fit yes"
need_eq "$(mk field "$REC" gate fit)" "true" "fit"
need_eq "$(mk field "$REC" gate cost_src)" "prior" "cost source"
verdict "fit: at 70 % with nothing declared and nothing measured, the prior item (12.5 %) fits under the belt: allow, fit true, source prior"

RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rfit1 --to "item one" --meter-line "$METER"
need_rc 0
need_out "allow"
need_absent "REFUSED"
RUNENV=""
verdict "fit: armed at 70 % with the prior fitting, the gate allows (the control for the refusal legs below and for the rgate fixture's refusal after its 750k item)"

fixture rfit2 200
SID=sid-rfit2
run expect --run rfit2 --items "item one=250k"
need_rc 0
need_eq "$(mk count "$REC" expect-items)" "1" "expect-items event"
mk transcript "$SID" 700000 >/dev/null
run gate --run rfit2 --to "item one"
need_rc 0
need_out "fit no"
need_eq "$(mk field "$REC" gate fit)" "false" "fit"
need_eq "$(mk field "$REC" gate decision)" "allow" "unarmed: allow"
verdict "fit: the same 70 % with a declared 250k item does not fit (970k over the 900k belt): fit false, source declared; unarmed still allows (the control for the armed leg below)"

RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rfit2 --to "item one"
need_rc 4
need_out "REFUSED (stop-condition band)"
RUNENV=""
verdict "fit: armed, the unfitting item is refused (exit 4, stop-condition band) although the memory sits below the old 80 % mark (must fire)"

fixture rfit3 200
SID=sid-rfit3
mk transcript "$SID" 100000 >/dev/null
run gate --run rfit3 --to "item one"
mk transcript "$SID" 300000 >/dev/null
run gate --run rfit3 --to "item two"
need_rc 0
need_out "largest-measured×1.25"
verdict "fit: after one measured item (200k) the estimate is the largest measured item times the margin, no longer the prior"

fixture rfit4 200
run expect --run rfit4 --items "item one=abc"
need_rc 2
need_out "not a token count"
need_eq "$(mk count "$REC" expect-items)" "0" "nothing recorded on a bad token"
verdict "expect: a bad token dies by name and records nothing (premise failure)"

# The stop decision: resume in place only when the rest of the item fits and the resume is cheap.
fixture rfitres1 200
arm_resume rfitres1
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=140000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rfitres1 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rfitres1-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +2s --tick-s 1
need_rc 0
need_eq "$(mk field "$REC" head-resumed context)" "140000" "resumed in place at 70 % of a 200k window (25k prior + 4k pack under the 180k belt, cache warm)"
verdict "resume in place: a head at 70 % resumes after the reset, where the old 60 % rule would have started a successor (must fire)"

fixture rfitres2 200
arm_resume rfitres2
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=170000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rfitres2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rfitres2-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +2s --tick-s 1
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume at 85 %: the prior item would pass the belt"
need_eq "$(mk count "$REC" head-successor)" "3" "the successor path ran (the first start, the stub head's own hand-over row, and the successor)"
verdict "resume in place refused: a head at 85 % of the window takes a successor, never a resume (fit false; the control for the leg above)"

fixture rfitcold 200
RES=$(env AIMYTH_CONTEXT_WINDOW=200000 "$PY" - "$H" "$REC" <<'FITCOLD_END'
import importlib.util, json, sys, time
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
events = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
warm = hs.resume_in_place(events, {"context": 140000, "percent": 70}, time.time() - 60)
cold = hs.resume_in_place(events, {"context": 140000, "percent": 70}, time.time() - 4000)
small_cold = hs.resume_in_place(events, {"context": 10000, "percent": 5}, time.time() - 4000)
print("warm", warm, "cold", cold, "small_cold", small_cold)
FITCOLD_END
)
need_eq "$RES" "warm True cold False small_cold True" "the cache rule"
verdict "resume in place: a warm cache resumes, a cold cache with a large memory takes a successor, a cold cache with a small memory resumes (the orientation cost bounds it)"

fixture rguard 200
RES=$(env AIMYTH_CONTEXT_WINDOW=200000 "$PY" - "$H" "$REC" <<'FITGUARD_END'
import importlib.util, json, sys, time
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
base = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
def stop(cls, age):
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - age))
    return base + [{"event": "observation", "what": "head exited", "exit_class": cls, "ts": ts}]
out = []
for label, cls, age, ctx in (("refusal", "refusal", 60, 50000), ("error", "error", 60, 50000), ("cold-large", "limit", 4000, 140000), ("warm-small", "limit", 60, 50000)):
    v = hs.resume_guard(stop(cls, age), {"context": ctx, "percent": ctx // 2000}, 0)[0]
    out.append("%s=%s" % (label, v))
print(" ".join(out))
FITGUARD_END
)
need_eq "$RES" "refusal=resume-refused error=resume-refused cold-large=resume-unfit warm-small=ok" "the hand-run resume guard"
verdict "resume-head guard: a refusal or an error stop is refused, a cold large resume is unfit, a warm small limit stop is ok (review finding 4, must fire and must not)"

# G71 (register 2026-09-23 20:3x): the planted case is the entry's own: an item measured at 480,959
# tokens at its gate, most of it done, with the hand-off saying what is left. On the estimate the
# resume does not fit; the control runs the same record with no `Remaining:` line and stays unfit.
fixture rfitrem 200
arm_resume rfitrem
mk append "$REC" '{"event":"gate","item":"one","context":100000,"percent":10,"band":0,"decision":"allow","metered":true}' >/dev/null
mk append "$REC" '{"event":"gate","item":"two","context":580959,"percent":58,"band":0,"decision":"allow","metered":true}' >/dev/null
mk transcript sid-rfitrem 600000 >/dev/null
sleep 1
run handoff --run rfitrem --inflight "$(printf -- '- Next: two\n- Needs: nothing\n- Decided: nothing\n- Remaining: 20k')"
need_rc 0
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"limit"}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0 AIMYTH_CONTEXT_WINDOW=1000000"
run _resume-head --run rfitrem --session sid-rfitrem --out "$WORK/starter/rfitrem-head-1.out" \
    --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --wait-s 5 --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" head-resumed)" "1" "the resume sized on the pack's figure fits"
RES=$(env AIMYTH_CONTEXT_WINDOW=1000000 "$PY" - "$H" "$REC" "$HO" "$WORK/handoffs/rfitrem-plain.md" <<'FITREM_END'
import importlib.util, json, sys, time
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
events = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
events = events[:[e.get("event") for e in events].index("head-resumed")]
m, ho, plain = {"context": 600000, "percent": 60}, sys.argv[3], sys.argv[4]
pack = hs.pack_remaining(events, ho)
text = open(ho, encoding="utf-8").read()
open(plain, "w", encoding="utf-8").write(text.replace("- Remaining: 20k\n", ""))
later = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + 3600))
print(pack, hs.pack_remaining(events, plain), hs.pack_remaining(events, "/no/such/hand-off"),
      hs.pack_remaining(events + [{"event": "gate", "ts": later}], ho),
      hs.resume_guard(events, m, 0, pack)[0], hs.resume_guard(events, m, 0, None)[0])
FITREM_END
)
need_eq "$RES" "20000 None None None ok resume-unfit" "the figure, no line, no file, an older pack, the fit with it and without it"
verdict "G71 (fails on old): an in-place resume is sized on the pack's Remaining line when the pack is no older than the last gate, and with no line, no hand-off or an older pack on the estimate, which stays unfit"

# G71, the review's F1: a figure in a notation the line does not hold must read as no figure, so the
# estimate stands: read as a number prefix, `1.2M` was 1 token and `20 000` was 20, either of which
# admits an oversized resume. The planted cases are those two; the controls keep their value.
RES=$(env AIMYTH_CONTEXT_WINDOW=1000000 "$PY" - "$H" "$REC" "$HO" "$WORK/handoffs/rfitrem-form.md" <<'FITFORM_END'
import importlib.util, json, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
events = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
events = events[:[e.get("event") for e in events].index("head-resumed")]
text = open(sys.argv[3], encoding="utf-8").read()
out = []
for form in ("1.2M", "20 000", "about 20k", "1,2", "20k", "20,000", "20000 tokens", "20 k tokens"):
    open(sys.argv[4], "w", encoding="utf-8").write(text.replace("- Remaining: 20k\n", "- Remaining: %s\n" % form))
    out.append(str(hs.pack_remaining(events, sys.argv[4])))
print(" ".join(out))
FITFORM_END
)
need_eq "$RES" "None None None None 20000 20000 20000 20000" "four unsupported notations, then four valid ones"
verdict "G71 F1 (fails on old): a Remaining figure in unsupported notation reads as no figure, so the estimate stands, while 20k, 20,000 and a figure followed by tokens keep their value"

# Hard stops (owner ruling 2026-09-14): the close's third warnings bullet names every non-limit stop.
fixture rhard 200
mk append "$REC" '{"event":"stop-condition","which":"band","lane":"head","action":"gate refused item item3 at 91 %"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"B-X","exit_class":"deadline"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"B-Y","exit_class":"completed"}' >/dev/null
RES=$("$PY" - "$H" "$REC" <<'FITHARD_END'
import importlib.util, json, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
events = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
print(hs.report_hardstops_text(events))
FITHARD_END
)
case $RES in
  "1 hard stop(s) on the head other than a limit: band at "*"1 lane(s) closed other than completed or limit: B-X at "*"(deadline)"*) : ;;
  *) why="$why; hard stops text: $RES" ;;
esac
verdict "hard stops: the close's bullet names the band stop and the deadline close and skips the completed lane (must fire, with the completed lane as its control)"

# INV-1 (register 2026-10-31 01:57): a completed lane that met denials is no stop. The planted case
# is one such lane beside one real stop; the control is the real stop, which stays counted.
fixture rhard2 200
mk append "$REC" '{"event":"lane-closed","lane":"B-Z","exit_class":"killed"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"B-W","exit_class":"completed","denials":{"sandbox":3}}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"B-V","exit_class":"completed"}' >/dev/null
RES=$("$PY" - "$H" "$REC" <<'FITHARD2_END'
import importlib.util, json, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
events = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
print(hs.report_hardstops_text(events))
FITHARD2_END
)
case $RES in
  *"1 lane(s) closed other than completed or limit: B-Z at "*"(killed) · 1 completed lane(s) met denials, none a stop: B-W at "*"(sandbox 3) · read from"*) : ;;
  *) why="$why; hard stops text: $RES" ;;
esac
verdict "INV-1 (fails on old): the close's bullet counts only exit classes other than completed or limit as stops, and gives a completed lane with denials a count of its own"

# ------------------------------------------------------------------------------ gate -------
fixture rgate 200
SID=sid-rgate
mk transcript "$SID" 100000 >/dev/null
run gate --run rgate --to "item one"
need_rc 0
need_out "band 0 · armed no"
need_out "allow"
need_eq "$(mk field "$REC" gate decision)" "allow" "decision"
need_eq "$(mk field "$REC" gate metered)" "true" "metered"
verdict "gate: unarmed below the first edge allows (band 0)"

mk transcript "$SID" 850000 >/dev/null
run gate --run rgate --to "item two"
need_rc 0
need_out "band 80"
need_out "warn: at or above the second edge"
need_eq "$(mk field "$REC" gate decision)" "allow" "decision"
verdict "gate: unarmed at 85 % warns and allows (soft band, D2)"

RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rgate --to "item three"
need_rc 4
need_out "REFUSED (stop-condition band)"
need_eq "$(mk field "$REC" stop-condition which)" "band" "stop-condition"
need_eq "$(mk field "$REC" gate decision)" "refuse" "decision"
verdict "gate: armed above the second edge exits 4 with stop-condition band"

mk transcript "$SID" 800000 >/dev/null
touch "$STATE/armed-$SID"
run gate --run rgate --to "item four"
need_rc 4
need_out "armed marker"
need_out "band 80"
verdict "gate: armed by the marker file, exactly at the edge, exits 4 (lower edge inclusive)"

mk transcript "$SID" 100000 >/dev/null
# The billed line in hand keeps this gate's spend measured, so the unmetered gate after it is
# the FIRST miss (a spend miss counts on the same rule since 2026-09-17).
run gate --run rgate --to "item five" --meter-line "$METER"
need_rc 4
need_out "REFUSED (stop-condition band)"
need_out "largest-measured"
verdict "gate: armed at 10 % after this fixture's measured 750k item refuses, since the next item would pass the belt (fit-based continuation, 2026-09-14; the old edge rule allowed here; the armed allow at 70 % in the fit block is the control)"

rm -f "$STATE/armed-$SID"
mk untranscript "$SID" >/dev/null
run gate --run rgate --to "item six"
need_rc 0
need_out "gate: unmetered"
need_out "first miss"
need_eq "$(mk field "$REC" gate metered)" "false" "metered"
need_eq "$(mk field "$REC" observation what)" "gate unmetered" "observation"
verdict "gate: the first unmetered gate allows with an observation (N1)"

RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rgate --to "item seven"
need_rc 7
need_out "second consecutive"
need_out "REFUSED"
need_eq "$(mk field "$REC" stop-condition which)" "unmetered" "stop-condition"
verdict "gate: the second consecutive unmetered gate, armed, exits 7 (never 4)"

run gate --run rgate --to "item eight"
need_rc 0
need_out "second consecutive"
need_out "allowed"
need_out "soft: fix the metering"
verdict "gate: the second consecutive unmetered gate, unarmed, warns and allows (D2)"

RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rgate --session "$SID" --head "successor" --detail "scope reset"
need_rc 0
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rgate --to "item nine"
need_rc 0
need_out "first miss"
need_absent "second consecutive"
verdict "gate: the unmetered count is scoped to the last session event (a run-resume resets it)"

# PAT-2 (critic F4 of the design round): a head told how to see a rule file changed since the run
# began. The planted cases are the two start messages on this run, with its run-open's own time;
# the control is a record with no run-open, which has no time to name and gets no sentence.
fixture rpat2 200
arm_resume rpat2
mk append "$REC" '{"event":"gate","item":"one","context":100000,"percent":10,"band":0,"decision":"allow","metered":true}' >/dev/null
mk transcript sid-rpat2 120000 >/dev/null
sleep 1
run handoff --run rpat2 --inflight "$(printf -- '- Next: two\n- Needs: nothing\n- Decided: nothing')"
need_rc 0
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"limit"}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0 AIMYTH_CONTEXT_WINDOW=1000000"
run _resume-head --run rpat2 --session sid-rpat2 --out "$WORK/starter/rpat2-head-1.out" \
    --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --wait-s 5 --tick-s 1
need_rc 0
RTS=$(mk field "$REC" run-open ts)
RULES="git log --oneline --since=$RTS -- CLAUDE.md CUSTOMISATION.md CUSTOMISATION-definitions.md .claude/skills/delegate/SKILL.md. A line there, or one of those files in the status, means a rule file changed since the run began"
grep -q -F "$RULES" "$WORK/stub-rpat2.stdin.1" || why="$why; a head resumed in place was not told how to read a rule-file change"
RES=$(env LLM_WIKI_STORE="$STORE" "$PY" - "$H" rpat2 "$HO" "$WORK/pat2-plain.jsonl" <<'PAT2_END'
import importlib.util, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
print(hs.resume_instruction(sys.argv[2], sys.argv[3]))
open(sys.argv[4], "w").write('{"event":"lane-open","lane":"L"}\n')
print("plain[%s]" % hs.rule_files_note(sys.argv[4]))
PAT2_END
)
case $RES in *"$RULES"*) : ;; *) why="$why; a fresh head's first message does not carry the sentence" ;; esac
case $RES in *"plain[]"*) : ;; *) why="$why; control: a record with no run-open still named a time" ;; esac
verdict "PAT-2 (fails on old): both start messages name git log since the run-open's time, and a record with no run-open gets no sentence"

# ------------------------------------------------------------------ gate: the envelope -------
# Register entry 2026-09-07: an envelope the pre-flight states is measured at every gate, or its
# stop condition cannot fire. Register entries 2026-09-14 19:35 and 00:06 (the run figure): the
# spend compared with it is the RUN's — every head session metered alone plus every lane on the
# record — never the head session's partition. Fixture envelope $100; the billed line in hand
# carries head $12.34 (its lanes $4.22 are the partition's, which the run figure never reads:
# the record's lanes are), so a record with no lane at all spends $14.49.
fixture renv 100
SID=sid-renv
mk transcript "$SID" 100000 >/dev/null
run gate --run renv --to "item one" --meter-line "$METER"
need_rc 0
need_out 'envelope: $12.34 of $100.00, remainder $87.66 · run: heads $12.34 (1 metered) · lanes: none on the record'
need_absent "at least"
need_eq "$(mk field "$REC" gate decision)" "allow" "decision"
need_eq "$(mk field "$REC" gate run_spend_usd)" "12.34" "run_spend_usd on the gate event"
need_eq "$(mk field "$REC" gate run_spend_floor)" "false" "run_spend_floor on the gate event"
verdict "gate: the line carries the run's spend, the envelope and the remainder (100.00 - 12.34 = 87.66) with its derivation, the event carries run_spend_usd and run_spend_floor, and the item is allowed (a record with no lane: the premise case)"

# Two earlier heads — head-successor sessions whose transcripts the meter beside the script
# prices at thirteen and ten calls of one million input tokens at the opus input rate (23 calls:
# over $100 when the input rate exceeds (100 - 12.34) / 23). The rate is read from prices.json.
# The generated transcripts and their costs keep this boundary executable rather than assumed.
# session's $12.34 put the run over $100: the remainder is at or below zero, the gate refuses
# with exit 5, unarmed, and the record gains the gate event and the stop-condition, nothing
# else. Each head is metered ALONE from its transcript: a head-exit's spent_usd (planted here
# at $1.00 each, a figure that would read $2.00) is never what is summed, since it carries the
# partition's lanes too.
OPUS_IN=$("$PY" -c 'import json, sys; print(json.load(open(sys.argv[1]))["families"]["opus"]["input"])' "$SKILL_DIR/prices.json")
TEN=$("$PY" -c 'import sys; print("%.2f" % (13 * float(sys.argv[1])))' "$OPUS_IN")
EIGHT=$("$PY" -c 'import sys; print("%.2f" % (10 * float(sys.argv[1])))' "$OPUS_IN")
OVER=$("$PY" -c 'import sys; print("%.2f" % (23 * float(sys.argv[1]) + 12.34))' "$OPUS_IN")
LEFT=$("$PY" -c 'import sys; print("-$%.2f" % (23 * float(sys.argv[1]) + 12.34 - 100))' "$OPUS_IN")
mk pricedscript sid-renv-h1 13 >/dev/null
mk pricedscript sid-renv-h2 10 >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-renv-h1"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"spent_usd":1.0}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-renv-h2"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"spent_usd":1.0}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run renv --session "$SID" --head "successor" --detail "after two exits"
need_rc 0
LINES_BEFORE=$(mk lines "$REC")
run gate --run renv --to "item two" --meter-line "$METER"
need_rc 5
need_out "envelope: \$$OVER of \$100.00, remainder $LEFT"
need_out "heads \$$OVER (3 metered)"
need_out "REFUSED (stop-condition envelope"
need_eq "$(mk field "$REC" stop-condition which)" "envelope" "stop-condition which"
need_eq "$(mk field "$REC" stop-condition lane)" "head" "stop-condition lane"
need_eq "$(mk field "$REC" gate decision)" "refuse" "decision"
need_eq "$(mk lines "$REC")" "$((LINES_BEFORE + 2))" "record lines (the gate and the stop-condition)"
verdict "gate: a spent envelope (remainder at or below zero) records stop-condition envelope, lane head, and exits 5; the earlier heads are metered alone from their transcripts (\$$TEN + \$$EIGHT), never read off head-exit.spent_usd"

fixture rnoenv none
SID=sid-rnoenv
mk transcript "$SID" 100000 >/dev/null
run gate --run rnoenv --to "item one" --meter-line "$METER"
need_rc 0
need_out "envelope: none · run: \$12.34 · heads \$12.34 (1 metered)"
need_absent "REFUSED"
need_eq "$(mk lines "$REC")" "2" "record lines (run-open and the gate)"
verdict "gate: a record whose run-open carries no envelope_usd prints envelope: none (the run figure beside it) and allows"

# A billed line with no head figure, and a transcript the meter cannot price (the fixture
# model matches no price family: the meter's own `unbilled` premise stands): nothing is
# metered, nothing is recorded, and the line says unmeasured — never $0.00 — and allows.
fixture runm 100
SID=sid-runm
mk transcript "$SID" 100000 >/dev/null
run gate --run runm --to "item one" --meter-line "failed: the fixture meter gave nothing"
need_rc 0
need_out "envelope: unmeasured (nothing metered or recorded (1 head(s); 0 lane(s)) · unmetered: head sid-runm ("
need_out "billed: unbilled (model id matches no price family"
need_absent '$0.00'
need_absent "REFUSED"
need_out "unmetered spend (first miss)"
need_eq "$(mk field "$REC" gate run_spend_usd)" "null" "run_spend_usd null when nothing is measured"
need_eq "$(mk field "$REC" observation what)" "gate unmetered" "the spend miss is an observation (the fold of 2026-09-17)"
need_eq "$(mk lines "$REC")" "3" "record lines (run-open, the gate and the miss's observation)"
verdict "gate: an envelope nothing can be metered against prints unmeasured with the meter's own refusal, never a zero, and allows as a first miss with its observation, never a refusal (the price-table premise: unbilled stands)"

# ---------------------------------------------- the run figure (register entries 2026-09-14) --
# Must fire. Two heads, the second started by head-successor with NO run-resume (the shape
# whose partition the per-session meter cannot see), three lanes: L1 closed with a cost under
# the first head; L2 closed under the first head and resumed and closed again under the second
# (two passes, two recorded costs, one session id); L3 closed `deadline` with a null cost and a
# transcript the meter prices at one call. Hand sum of the five sessions: head 1 two calls +
# head 2 four calls + L1 $2.50 + L2 $1.00 + $1.50 + L3 one call. The old figure on the same
# record — every head-exit's spent_usd plus this session's `session $` — is lower, and both
# are printed. Nothing here depends on a run-resume marker.
H1=$("$PY" -c 'import sys; print("%.2f" % (2 * float(sys.argv[1])))' "$OPUS_IN")
H2=$("$PY" -c 'import sys; print("%.2f" % (4 * float(sys.argv[1])))' "$OPUS_IN")
HEADS=$("$PY" -c 'import sys; print("%.2f" % (6 * float(sys.argv[1])))' "$OPUS_IN")
L3=$("$PY" -c 'import sys; print("%.2f" % (1 * float(sys.argv[1])))' "$OPUS_IN")
SUM=$("$PY" -c 'import sys; print("%.2f" % (7 * float(sys.argv[1]) + 5.0))' "$OPUS_IN")
LANES=$("$PY" -c 'import sys; print("%.2f" % (1 * float(sys.argv[1]) + 5.0))' "$OPUS_IN")
REMAIN=$("$PY" -c 'import sys; print("%.2f" % (100 - 7 * float(sys.argv[1]) - 5.0))' "$OPUS_IN")
seed_fixture rrun 100      # the run-open session is the launcher's seed: skipped and named
mk pricedscript sid-rrun-h1 2 >/dev/null
mk pricedscript sid-rrun-h2 4 >/dev/null
mk pricedscript sid-rrun-l3 1 lane-home-dir >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rrun-h1"}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L1","session_id":"sid-rrun-l1"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L1","session_id":"sid-rrun-l1","exit_class":"completed","total_cost_usd":2.5}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L2","session_id":"sid-rrun-l2"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L2","session_id":"sid-rrun-l2","exit_class":"limit","total_cost_usd":1.0}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":"limit","spent_usd":12.5}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rrun-h2"}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L2","session_id":"sid-rrun-l2"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L2","session_id":"sid-rrun-l2","exit_class":"completed","total_cost_usd":1.5}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L3","session_id":"sid-rrun-l3"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L3","session_id":"sid-rrun-l3","exit_class":"deadline","total_cost_usd":null}' >/dev/null
run run-spend --run rrun
need_rc 0
need_out "head sid-rrun-h1: \$$H1 · metered (transcript)"
need_out "head sid-rrun-h2: \$$H2 · metered (transcript)"
need_out "lane L1: \$2.50 · 1 close cost(s) as recorded"
need_out "lane L2: \$2.50 · 2 close cost(s) as recorded"
need_out "lane L3: \$$L3 · the larger of the transcript's \$$L3 (close(s) without a cost: deadline; sid-rrun: \$$L3 (metered (transcript)"
need_out "head sid-rrun: unmetered · skipped: run-open marks the session a seed"
need_out "run-spend: rrun · \$$SUM of \$100.00, remainder \$$REMAIN · heads \$$HEADS (2 metered; 1 seed skipped) · lanes \$$LANES (3 of 3 with a figure) · 3 meter call(s) · complete"
verdict "run figure (must fire, register 2026-09-14): two heads with no run-resume between them and three lanes (one resumed under the second head, one closed deadline with a null cost) sum to the hand total of the five sessions, \$$SUM, the deadline lane taken from its transcript and the seed skipped"

# The same record through the gate, this session's figure read off the billed line in hand,
# against the OLD arithmetic computed here independently: every head-exit's spent_usd plus
# the line's `session $` — lower, because the second head's partition holds no lane the line
# can see and the deadline lane's null cost was never a number.
METER_H2="billed (list 2026-09-03) · head \$$H2 · lanes \$0.00 · session \$$H2 · rewrites 0 (\$0.00) · lanes 0 (reasons: (a)×0 (b)×0 (c)×0 (d)×0, none×0) · metered 0 of 0 recorded under no partition"
OLD=$("$PY" - "$REC" "$METER_H2" <<'OLD_FIGURE_END'
import json, re, sys
spent = sum(float(e["spent_usd"]) for e in (json.loads(l) for l in open(sys.argv[1]) if l.strip())
            if e.get("event") == "head-exit" and isinstance(e.get("spent_usd"), (int, float)))
print("%.2f" % (spent + float(re.search(r"session \$([0-9.]+)", sys.argv[2]).group(1))))
OLD_FIGURE_END
)
run gate --run rrun --to "item one" --meter-line "$METER_H2"
need_rc 0
need_out "envelope: \$$SUM of \$100.00, remainder \$$REMAIN"
need_absent "at least"
need_eq "$("$PY" -c 'import sys; print("%.2f" % float(sys.argv[1]))' "$(mk field "$REC" gate run_spend_usd)")" "$SUM" "run_spend_usd"
need_eq "$("$PY" -c 'import sys; print(int(float(sys.argv[1]) < float(sys.argv[2])))' "$OLD" "$SUM")" "1" "the old figure ($OLD) is lower than the run figure ($SUM)"
verdict "run figure at the gate (must fire): the envelope line carries \$$SUM where the old arithmetic (head-exit spent_usd + this session's session \$) gives \$$OLD, lower (both shown)"

# Must not fire: a single-head run whose every lane closed with a cost spends the same before
# and after — the old arithmetic's `session $` (head + the lane the meter saw) equals the run
# figure's head $ plus the record's lane cost, and the line reads that figure with no `at least`.
fixture rrun1 100
mk append "$REC" '{"event":"lane-open","lane":"L1","session_id":"sid-rrun1-l1"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L1","session_id":"sid-rrun1-l1","exit_class":"completed","total_cost_usd":2.5}' >/dev/null
run gate --run rrun1 --to "item one" --meter-line 'billed (list 2026-09-03) · head $10.00 · lanes $2.50 · session $12.50 · rewrites 0 ($0.00) · lanes 1 (reasons: (a)×1 (b)×0 (c)×0 (d)×0, none×0) · metered 1 of 1 recorded'
need_rc 0
need_out 'envelope: $12.50 of $100.00, remainder $87.50 · run: heads $10.00 (1 metered) · lanes $2.50 (1 of 1 with a figure)'
need_absent "at least"
need_absent "unmetered:"
verdict "run figure (must not fire): a single-head run with every lane closed with a cost reads the same \$12.50 the session line's session \$ gave, complete, no floor"

# Premise: a lane with a null cost and NO transcript is named, the figure is a floor (`at
# least`), the gate still allows under the envelope — and refuses when the floor alone is
# already over it (envelope $10 against a head of $12.34): a floor is the floor it is.
fixture rflo 100
mk append "$REC" '{"event":"lane-open","lane":"LX","session_id":"sid-rflo-nowhere"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LX","session_id":"sid-rflo-nowhere","exit_class":"deadline","total_cost_usd":null}' >/dev/null
run gate --run rflo --to "item one" --meter-line "$METER"
need_rc 0
need_out 'envelope: at least $12.34 of $100.00, remainder at most $87.66'
need_out "unmetered: lane LX (close(s) without a cost: deadline; sid-rflo: no transcript for lane session sid-rflo-nowhere under"
need_eq "$(mk field "$REC" gate run_spend_floor)" "true" "run_spend_floor"
need_eq "$(mk field "$REC" gate run_spend_usd)" "12.34" "run_spend_usd is the floor"
verdict "run figure premise: a lane closed with a null cost and no transcript is named, the figure reads at least, and the gate allows under the envelope"

fixture rflo2 10
mk append "$REC" '{"event":"lane-open","lane":"LX","session_id":"sid-rflo2-nowhere"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LX","session_id":"sid-rflo2-nowhere","exit_class":"deadline","total_cost_usd":null}' >/dev/null
run gate --run rflo2 --to "item one" --meter-line "$METER"
need_rc 5
need_out 'envelope: at least $12.34 of $10.00, remainder at most -$2.34'
need_out "REFUSED (stop-condition envelope"
need_eq "$(mk field "$REC" stop-condition which)" "envelope" "stop-condition which"
verdict "run figure premise: a floor already over the envelope refuses (exit 5, stop-condition envelope) — the floor is treated as the floor it is"

# Premise: a malformed record line is skipped and counted, and makes the figure a floor.
fixture rmal 100
printf '{"event": "lane-closed", torn\n' >> "$REC"
run gate --run rmal --to "item one" --meter-line "$METER"
need_rc 0
need_out 'envelope: at least $12.34 of $100.00, remainder at most $87.66'
need_out "1 malformed record line(s) skipped"
verdict "run figure premise: a malformed record line is skipped, counted on the line, and the figure reads at least"

# Premise: a lane with two session ids is listed unmetered (no one transcript to meter) and its
# recorded part is kept; the figure is a floor.
fixture rtwo 100
mk append "$REC" '{"event":"lane-open","lane":"LT","session_id":"sid-rtwo-a"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LT","session_id":"sid-rtwo-a","exit_class":"limit","total_cost_usd":3.0}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"LT","session_id":"sid-rtwo-b"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LT","session_id":"sid-rtwo-b","exit_class":"deadline","total_cost_usd":null}' >/dev/null
run run-spend --run rtwo --meter-line "$METER"
need_rc 1
need_out "lane LT: \$3.00 · 1 close cost(s) as recorded · unmetered: close(s) without a cost: deadline; 2 session ids: the passes across ids cannot be reconciled exactly (sid-rtwo: no transcript for lane session sid-rtwo-a under"
need_out "at least \$15.34 of \$100.00"
need_out "AT LEAST"
verdict "run figure premise: a lane with two session ids and no transcripts is listed unmetered with its recorded \$3.00 kept, and run-spend exits 1 on the floor"

# Fold (critic 2026-09-17, high): a two-session-id lane whose closes are ALL priced is metered per
# transcript, the larger of the recorded sum and the transcripts' sum taken, and still listed
# under the floor: the passes across ids cannot be reconciled exactly. Closes $3 + $4 = $7 over
# ids a and b; each transcript one call.
fixture rtwop 100
mk pricedscript sid-rtwop-a 1 lane-home-dir >/dev/null
mk pricedscript sid-rtwop-b 1 lane-home-dir >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"LT","session_id":"sid-rtwop-a"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LT","session_id":"sid-rtwop-a","exit_class":"limit","total_cost_usd":3.0}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"LT","session_id":"sid-rtwop-b"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LT","session_id":"sid-rtwop-b","exit_class":"completed","total_cost_usd":4.0}' >/dev/null
ONE_LANE=$("$PY" -c 'import sys; print("%.2f" % float(sys.argv[1]))' "$OPUS_IN")
TWOTX=$("$PY" -c 'import sys; print("%.2f" % (2 * float(sys.argv[1])))' "$OPUS_IN")
TWOMAX=$("$PY" -c 'import sys; print("%.2f" % max(2 * float(sys.argv[1]), 7.0))' "$OPUS_IN")
TWOSUM=$("$PY" -c 'import sys; print("%.2f" % (max(2 * float(sys.argv[1]), 7.0) + 12.34))' "$OPUS_IN")
run run-spend --run rtwop --meter-line "$METER"
need_rc 1
need_out "lane LT: \$$TWOMAX · the larger of the transcripts' \$$TWOTX (2 session ids: the passes across ids cannot be reconciled exactly; sid-rtwo: \$$ONE_LANE (metered (transcript)"
need_out "and the recorded \$7.00 (2 close cost(s) as recorded)"
need_out "at least \$$TWOSUM of \$100.00"
need_out "unmetered: lane LT (2 session ids: the passes across ids cannot be reconciled exactly;"
need_out "AT LEAST"
verdict "two-session-id lane with priced closes (fold): metered per transcript (\$$ONE_LANE + \$$ONE_LANE), the larger of that sum and the recorded \$7.00 taken, and the total still carries the floor warning"

# Premise: the price table missing beside the script — the meter's own `unbilled` premise: no
# zero is printed. A copy of the script with the meter and no prices.json.
NOPRICE="$WORK/noprice"
rm -rf "$NOPRICE"
mkdir -p "$NOPRICE"
cp "$H" "$NOPRICE/handsoff.py"
# CR-A3-1 H1 (spec), E1: the copied supervisor still needs its shared record-lock module.
cp "$LANE_PY" "$NOPRICE/lane.py"
cp "$SKILL_DIR/fable-share.py" "$NOPRICE/fable-share.py"
fixture rnop 100
mk pricedscript sid-rnop-h1 2 >/dev/null
mk pricedscript sid-rnop-l 1 lane-home-dir >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rnop-h1"}' >/dev/null
# Fold (critic 2026-09-17, medium): a lane with no priced close and a transcript the meter
# cannot bill prints `unmeasured`, never $0.00 (never `lane NULL: $0.00`).
mk append "$REC" '{"event":"lane-open","lane":"NULL","session_id":"sid-rnop-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"NULL","session_id":"sid-rnop-l","exit_class":"deadline","total_cost_usd":null}' >/dev/null
RC=0
"$PY" -B "$NOPRICE/handsoff.py" run-spend --run rnop >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 1
need_nofile "$NOPRICE/prices.json"
need_out "billed: unbilled ("
need_out "lane NULL: unmeasured · 0 close cost(s) as recorded · unmetered: close(s) without a cost: deadline (sid-rnop: the transcript meter gave no figure (exit 2: billed: unbilled ("
need_out "unmeasured · nothing metered or recorded (2 head(s); 1 lane(s))"
need_absent '$0.00'
verdict "run figure premise (price table missing): every meter call says unbilled, the unbillable lane prints unmeasured, the figure reads unmeasured and no dollar zero is printed (fold)"

# The distinguishable case: a lane whose recorded close is a genuine zero prints $0.00 beside the
# word recorded, and the figure is measured.
fixture rzero 100
mk append "$REC" '{"event":"lane-open","lane":"Z","session_id":"sid-rzero-z"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"Z","session_id":"sid-rzero-z","exit_class":"completed","total_cost_usd":0.0}' >/dev/null
run run-spend --run rzero --meter-line "$METER"
need_rc 0
need_out "lane Z: \$0.00 · 1 close cost(s) as recorded"
need_out "\$12.34 of \$100.00, remainder \$87.66 · heads \$12.34 (1 metered) · lanes \$0.00 (1 of 1 with a figure) · 0 meter call(s) · complete"
verdict "a recorded zero (fold, the control): a lane closed at a genuine \$0.00 prints \$0.00 beside the word recorded, distinguishable from an unmeasured lane, and the figure is complete"

# Premise: the meter slow — the calls share a wall-clock budget, so a gate stays bounded. A copy
# whose meter sleeps past a 2 s budget (the call's own bound is the budget's whole seconds
# left, 1 s): the session is left unmetered and named, the figure a floor; and a zero budget
# skips every call before it starts.
SLOWRUN="$WORK/slowrun"
rm -rf "$SLOWRUN"
mkdir -p "$SLOWRUN"
cp "$H" "$SLOWRUN/handsoff.py"
# CR-A3-1 H1 (spec), E1: the copied supervisor still needs its shared record-lock module.
cp "$LANE_PY" "$SLOWRUN/lane.py"
printf '%s\n' 'import time' 'time.sleep(4)' "print('$METER')" > "$SLOWRUN/fable-share.py"
RC=0
"$PY" -B "$SLOWRUN/handsoff.py" run-spend --run rnop --budget-s 2 --no-cache >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 1
need_out "the transcript meter did not finish in 1 s"
need_out "AT LEAST"
run run-spend --run rnop --budget-s 0 --no-cache
need_rc 1
need_out "the run meter's 0 s budget was spent before"
need_out "0 meter call(s)"
verdict "run figure premise (a slow meter): the meter calls share a wall-clock budget — a call past it is cut and named, a spent budget makes no call — and the figure is a floor, never a zero"

# The cache: a metered session is cached by transcript size and mtime, so a second call makes
# no meter call; a transcript that changed is metered again (its figure changes); --no-cache
# meters everything again; a dry run reads the cache and writes none.
fixture rcache 100
mk pricedscript sid-rcache 2 >/dev/null     # the run-open session is the head, metered from its transcript
H3=$("$PY" -c 'import sys; print("%.2f" % (3 * float(sys.argv[1])))' "$OPUS_IN")
CACHE="$STORE/spawn-records/rcache-spend-cache.json"
rm -f "$CACHE"
run gate --run rcache --to "item one" --dry-run
need_rc 0
need_out "envelope: \$$H1 of \$100.00"
need_nofile "$CACHE"
run run-spend --run rcache
need_rc 0
need_out "head sid-rcache: \$$H1 · metered (transcript)"
need_out "1 meter call(s)"
need_file "$CACHE"
run run-spend --run rcache
need_rc 0
need_out "head sid-rcache: \$$H1 · cached:"
need_out "0 meter call(s)"
sleep 1
mk pricedscript sid-rcache 3 >/dev/null
run run-spend --run rcache
need_rc 0
need_out "head sid-rcache: \$$H3 · metered (transcript)"
need_out "1 meter call(s)"
run run-spend --run rcache --no-cache
need_rc 0
need_out "1 meter call(s)"
verdict "run figure cache: a dry run writes no cache, the first call meters and caches, the second is served from the cache (0 meter calls), a changed transcript is metered again with its new figure, and --no-cache meters again"

# Fold (critic 2026-09-17, high): a resumed lane's active pass after a priced close is metered
# from the whole transcript and the larger figure taken. The critic's replay: head $10 (the line
# in hand), an earlier close $7, the lane resumed and running with a transcript worth $12 (two
# calls of 1.5 million input tokens at the opus rate: over the $10 the envelope leaves at any
# rate above $3.34), envelope $20: the run spends $22 and the
# gate refuses with exit 5. A lane still running — here the open pass — makes the figure a floor
# (register entry 2026-09-30 03:21): `at least`, the remainder `at most`, and the gate refuses on
# the floor as it would on the figure.
TWELVE=$("$PY" -c 'import sys; print("%.2f" % (2 * 1.5 * float(sys.argv[1])))' "$OPUS_IN")
RESUMED=$("$PY" -c 'import sys; print("%.2f" % (10 + max(7.0, 2 * 1.5 * float(sys.argv[1]))))' "$OPUS_IN")
RESLEFT=$("$PY" -c 'import sys; v = 20 - (10 + max(7.0, 2 * 1.5 * float(sys.argv[1]))); print(("-$%.2f" % -v) if v < 0 else ("$%.2f" % v))' "$OPUS_IN")
METER10='billed (list 2026-09-03) · head $10.00 · lanes $0.00 · session $10.00 · rewrites 0 ($0.00) · lanes 0 (reasons: (a)×0 (b)×0 (c)×0 (d)×0, none×0) · metered 0 of 0 recorded'
fixture rres 20
mk pricedscript sid-rres-l 2 lane-home-dir 1500000 >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L","session_id":"sid-rres-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rres-l","exit_class":"limit","total_cost_usd":7.0}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L","session_id":"sid-rres-l"}' >/dev/null
run run-spend --run rres --meter-line "$METER10"
need_rc 1
need_out "lane L: \$$TWELVE · the larger of the transcript's \$$TWELVE (an open pass after the last close (latest event lane-resumed); sid-rres: \$$TWELVE (metered (transcript)"
need_out "and the recorded \$7.00 (1 close cost(s) as recorded)"
need_out "at least \$$RESUMED of \$20.00, remainder at most $RESLEFT"
need_out "still running: L (the figure is a floor while a lane spends)"
run gate --run rres --to "item one" --meter-line "$METER10"
need_rc 5
need_out "envelope: at least \$$RESUMED of \$20.00, remainder at most $RESLEFT"
need_eq "$(mk field "$REC" stop-condition which)" "envelope" "stop-condition envelope"
verdict "resumed lane (fold, must fire): an active pass after a priced close is metered from the whole transcript — head \$10.00 + max(\$7.00, \$$TWELVE) = \$$RESUMED over \$20.00 — and, the lane still running, the figure is a floor (Kd9717c6c) on which the gate refuses with exit 5"

# The control: the lane closed again (its latest event a lane-closed) is no floor — $7 + $5 = $12
# recorded, its transcript, unchanged and so served from the cache with no meter call, taken only
# where larger (Kd9717c6c) — and a transcript shared by several passes counts once: closes $3 +
# $4 = $7 with the lane resumed again take max($7, $12) = $12, never $19, a floor while it runs.
LARGER=$("$PY" -c 'import sys; print("%.2f" % max(12.0, float(sys.argv[1])))' "$TWELVE")
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rres-l","exit_class":"completed","total_cost_usd":5.0}' >/dev/null
run run-spend --run rres --meter-line "$METER10"
need_rc 0
need_out "lane L: \$$LARGER · "
need_out "2 close cost(s) as recorded"
need_out "0 meter call(s)"
need_absent "at least"
fixture rres2 100
mk pricedscript sid-rres2-l 2 lane-home-dir 1500000 >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L","session_id":"sid-rres2-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rres2-l","exit_class":"limit","total_cost_usd":3.0}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L","session_id":"sid-rres2-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rres2-l","exit_class":"limit","total_cost_usd":4.0}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L","session_id":"sid-rres2-l"}' >/dev/null
run run-spend --run rres2 --meter-line "$METER10"
need_rc 1
need_out "still running: L (the figure is a floor while a lane spends)"
need_out "lane L: \$$TWELVE · the larger of the transcript's \$$TWELVE (an open pass after the last close (latest event lane-resumed)"
need_out "and the recorded \$7.00 (2 close cost(s) as recorded)"
need_absent "\$19.00"
verdict "resumed lane (fold, must not fire): a lane whose latest event is a close is no floor, its recorded \$12.00 set against its cached transcript (no meter call), and a transcript shared by several passes counts once — max(\$7.00, \$$TWELVE), never \$19.00 — the resumed lane a floor while it runs (Kd9717c6c)"

# Fold (critic 2026-09-17, high): a gate whose run-spend figure cannot be computed is an unmetered
# gate for the two-unmetered-gates rule. Valid context (a transcript the watermark hook measures),
# a spend meter that fails (the fixture model matches no price family, no billed line in hand, no
# lane): armed, the first gate allows with `unmetered spend (first miss)` and its event says so,
# the second consecutive gate refuses with exit 7 and stop-condition unmetered.
fixture rspm 100
SID=sid-rspm
mk transcript "$SID" 100000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rspm --to "item one"
need_rc 0
need_out "unmetered spend (first miss) · item item one allowed"
need_out "envelope: unmeasured ("
need_eq "$(mk field "$REC" gate metered)" "true" "the context is measured (metered true)"
need_eq "$(mk field "$REC" gate run_spend_usd)" "null" "run_spend_usd null on the first miss"
need_eq "$(mk field "$REC" gate decision)" "allow" "the first miss allows"
need_eq "$(mk field "$REC" observation what)" "gate unmetered" "the miss is an observation"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rspm --to "item two"
need_rc 7
need_out "unmetered spend (second consecutive) · armed (env) · REFUSED item item two → handoff --final --band unmetered, then successor"
need_eq "$(mk field "$REC" stop-condition which)" "unmetered" "stop-condition which"
need_eq "$(mk field "$REC" gate decision)" "refuse" "the second gate refuses"
verdict "unmetered spend (fold, must fire): valid context and a failing spend meter read 0 then 7 — the first miss allowed and said on the event (run_spend_usd null, an observation), the second consecutive miss armed refuses with stop-condition unmetered"

# Must not fire: a measured gate resets the count (a miss, a measured gate, a miss, a measured
# gate read 0, 0, 0, 0), and two measured gates in a row read 0 and 0.
fixture rspm2 100
SID=sid-rspm2
mk transcript "$SID" 100000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rspm2 --to "item one"
need_rc 0
need_out "unmetered spend (first miss)"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rspm2 --to "item two" --meter-line "$METER"
need_rc 0
need_absent "unmetered spend"
need_eq "$(mk field "$REC" gate run_spend_usd)" "12.34" "the measured gate carries a figure"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rspm2 --to "item three"
need_rc 0
need_out "unmetered spend (first miss)"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rspm2 --to "item four" --meter-line "$METER"
need_rc 0
need_absent "unmetered spend"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rspm2 --to "item five" --meter-line "$METER"
need_rc 0
need_absent "unmetered spend"
need_eq "$(mk count "$REC" stop-condition)" "0" "no stop-condition in the sequence"
verdict "unmetered spend (fold, must not fire): a measured gate resets the count (0, 0, 0, 0) and two measured gates read 0 and 0; the missing-context control keeps its own 0-then-7 leg above"

# ---- G57 (register 2026-10-16 10:04): a helper's closes repeat its session's running total ----
# Each case is a lane whose true spend differs from the sum of its closes, or must not. The reading
# is the weekly reader's own, so the suite needs it beside this tree (WEEKLY_WASTE names a copy).
# run: a one-off model carried unchanged, so $3 then $5 is $5. beat: the same, with a later beat.
# pass: a model dropped, so costs per pass and the sum. plain: neither, the sum and a note.
# nosid, damaged and absent are the three cases no reading can place, each the sum and a note.
WEEKLY_WASTE=${WEEKLY_WASTE:-$SKILL_DIR/../weekly-audit/weekly-waste.py}
need_file "$WEEKLY_WASTE"
fixture rspend 200
RSP=$(env AIMYTH_WEEKLY_WASTE="$WEEKLY_WASTE" "$PY" - "$H" "$REC" "$WORK/rspend-damaged.jsonl" <<'RSPEND_END'
import importlib.util, json, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
base = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
def usage(**models):
    return {"modelUsage": {name: {"costUSD": cost, "inputTokens": tokens, "outputTokens": 1, "cacheReadInputTokens": 0,
                                  "cacheCreationInputTokens": 0} for name, (cost, tokens) in models.items()}}
def close(lane, sid, total, models):
    ev = {"event": "lane-closed", "lane": lane, "exit_class": "completed", "cost_src": "result",
          "total_cost_usd": total, "usage": usage(**models)}
    if sid:
        ev["session_id"] = sid
    return ev
def beat(lane, sid, total):
    return {"event": "hold-beat", "lane": lane, "session_id": sid, "cost_src": "result", "total_cost_usd": total, "ok": True,
            "usage": {"models": ["big", "tiny"], "input_tokens": 900, "output_tokens": 9, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0}}
one_off = (0.5, 10)
cases = {
    "run": [close("L", "s1", 3.0, {"big": (2.5, 100), "tiny": one_off}), close("L", "s1", 5.0, {"big": (4.5, 200), "tiny": one_off})],
    "beat": [close("L", "s1", 3.0, {"big": (2.5, 100), "tiny": one_off}), close("L", "s1", 5.0, {"big": (4.5, 200), "tiny": one_off}), beat("L", "s1", 6.0)],
    "pass": [close("L", "s1", 3.0, {"big": (2.5, 100), "tiny": one_off}), close("L", "s1", 2.0, {"big": (2.0, 50)})],
    "plain": [close("L", "s1", 3.0, {"big": (3.0, 100)}), close("L", "s1", 5.0, {"big": (5.0, 200)})],
    "nosid": [close("L", "s1", 3.0, {"big": (2.5, 100), "tiny": one_off}), close("L", None, 5.0, {"big": (4.5, 200), "tiny": one_off})],
    "two": [close("L", "s1", 3.0, {"big": (2.5, 100), "tiny": one_off}), close("L", "s1", 5.0, {"big": (4.5, 200), "tiny": one_off}),
            close("L", "s2", 1.0, {"big": (1.0, 20)})],
}
out = []
for name in ("run", "beat", "pass", "plain", "nosid", "two"):
    spend = hs.run_spend(base + cases[name], "rspend", None, use_cache=False)
    row = spend["lanes"][0]
    out.append("%s %.2f %s" % (name, spend["lanes_usd"], "note" if "·" in row[2] else "bare"))
damaged = sys.argv[3]
with open(damaged, "w", encoding="utf-8") as handle:
    handle.write("".join(json.dumps(ev) + "\n" for ev in base + cases["run"]) + "{torn\n")
spend = hs.run_spend(base + cases["run"], "rspend", damaged, use_cache=False)
out.append("damaged %.2f %s %s" % (spend["lanes_usd"], "floor" if spend["floor"] else "exact", "note" if "damaged" in spend["lanes"][0][2] else "bare"))
hs._WEEKLY = None
os.environ["AIMYTH_WEEKLY_WASTE"] = "/no/such/reader.py"
spend = hs.run_spend(base + cases["run"], "rspend", None, use_cache=False)
out.append("absent %.2f %s" % (spend["lanes_usd"], "note" if "no weekly reader" in spend["lanes"][0][2] else "bare"))
print("; ".join(out))
RSPEND_END
)
need_eq "$RSP" "run 5.00 note; beat 6.00 note; pass 5.00 bare; plain 8.00 note; nosid 8.00 note; two 6.00 note; damaged 8.00 floor note; absent 8.00 note" "each lane's recorded figure, and whether it says how"
verdict "G57 (fails on old): a session whose costs read as running totals counts its last, never the sum, a beat included, and per-pass costs sum; a session that reads as neither, a line naming no session, a damaged record line or a missing reader keep the sum and say so"

# --------------------------------------------------------------------------- handoff -------
fixture rho 200
run handoff --run rho --inflight "- lane B2b: the suite, running."
need_rc 0
need_out "inflight rewritten"
case $(mk section "$HO" "In flight") in
  *"lane B2b: the suite, running."*) : ;;
  *) why="$why; the in-flight section was not rewritten" ;;
esac
verdict "handoff --inflight: the in-flight section is rewritten"

run handoff --run rho --set "shipped=the suite and its controls" \
    --set "waits=one confirmation"
need_rc 0
need_eq "$(mk bullet "$HO" "What shipped")" "the suite and its controls" "shipped bullet"
need_eq "$(mk bullet "$HO" "Waits for you")" "one confirmation" "waits bullet"
verdict "handoff --set: named morning-report bullets are rewritten"

SUM_BEFORE=$(mk manifest "$WORK/handoffs" | grep rho)
run handoff --run rho --set "ledger=a row by the back door"
need_rc 2
need_out "append-only"
need_lines
need_eq "$(mk manifest "$WORK/handoffs" | grep rho)" "$SUM_BEFORE" "hand-off checksum"
verdict "handoff --set ledger: refused as append-only (exit 2, file untouched)"

run handoff --run rho --set "trace=a row by the back door"
need_rc 2
need_out "append-only"
need_lines
verdict "handoff --set trace: refused as append-only (exit 2)"

run handoff --run rho --set "nonesuch=x"
need_rc 2
need_out "unknown key"
need_lines
verdict "handoff --set: an unknown key is refused (exit 2)"

printf -- '- Next: item 4 (gate: 4)\n- Needs: wiki/a.md:1-9\n- Decided: D1 because x\n' > "$WORK/pack-rho.md"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rho --final --band 80 --meter-line "$METER" --inflight-file "$WORK/pack-rho.md"
need_rc 0
need_out "head-exit recorded (band 80"
need_eq "$(mk field "$REC" head-exit band)" "80" "head-exit band"
REALHO=$("$PY" -c 'import os, sys; sys.stdout.write(os.path.realpath(sys.argv[1]))' "$HO")
need_eq "$(mk field "$REC" head-exit handoff)" "$REALHO" "head-exit hand-off path"
verdict "handoff --final --band: a head-exit event with the band and the hand-off path"

# ---- R1-9 (register 2026-11-05 12:41): an item the hand-off calls done with no boundary ----
# The planted case is the entry's own line, in a lead's form. The controls are an item whose
# boundary stands, one still running, one negated and a line that opens on no declared item.
fixture ritem 200
mk append "$REC" '{"event":"expect-items","items":{"item1":1000,"item2":1000,"item3":1000,"item4":1000}}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"item1","to":"item2","next":"n"}' >/dev/null
run handoff --run ritem --inflight "$(printf -- '- Next: item5\n- Needs: nothing\n- Decided: nothing\nitem1 map · done, all of it\nitem2 build · done, the suite green\nitem3 reading · still running\nitem4 install · not yet done\nitem9 stray · done')"
need_rc 0
need_out "handoff: warn: the hand-off names item2 done with no completion on the record"
need_absent "names item1"
need_absent "item3"
need_absent "item4 done"
need_absent "item9"
run handoff --run ritem --dry-run --inflight "$(printf -- '- Next: item5\n- Needs: nothing\n- Decided: nothing\nitem2 build · done')"
need_rc 0
need_absent "warn: the hand-off names"
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run ritem --from item3 --to item4 --disposition "item3 closed" --waste "none" --next "n" --meter-line "$METER"
need_rc 0
need_out "boundary: warn: the hand-off names item2 done with no completion on the record"
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run ritem --from item2 --to item3 --disposition "the late record" --waste "none" --next "n" --meter-line "$METER"
need_rc 0
need_absent "warn: the hand-off names"
verdict "R1-9 (fails on old): handoff and boundary warn when the hand-off names an item done with no boundary from it on the record, while a bounded, running, negated or undeclared line stays quiet, and the late boundary clears it"

# ------------------------------------------------------------------------- successor -------
fixture rsuc 200
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rsuc --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$187.66"
need_out "minus the run's spend \$12.34 (run_spend: heads \$12.34 (1 metered)"
need_eq "$(mk count "$REC" head-exit)" "0" "head-exit events"
need_eq "$(mk lines "$REC")" "1" "record lines"
verdict "successor --dry-run: the budget is the envelope minus the run's spend as the gate reads it (200 − the head's \$12.34 in the billed line in hand, K22da6bf5), nothing written"

fixture rsuc2 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)"}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-running","pid":9002,"budget":3.5}' >/dev/null
LINES_BEFORE=$(mk lines "$REC")
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rsuc2 --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "head-successor"
need_lines
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines"
verdict "successor: refused when a head-successor already follows the last head-exit (exit 2)"

fixture rsuc3 10
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rsuc3 --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "the envelope is spent"
need_lines
verdict "successor: a spent envelope is refused rather than a negative budget (exit 2)"

# --------------------------------------------------------------------------- _starter ------
# The pid path: a real process the starter must outlive. The suite reaps it as soon as it
# exits, so pid_alive() sees the process gone rather than a zombie of this shell.
fixture rst 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)"}' >/dev/null
sleep 2 &
PRED=$!
(
  RCF=0
  env STUB_MODE=complete STUB_N=1 "$PY" -B "$H" _starter --run rst --handoff "$HO" --budget 3.50 \
        --out "$WORK/starter/rst-head-1.out" --wait-s 20 --harness-bin "$WORK/bin/stubhead" \
        --meter-line "$METER" --predecessor-pid "$PRED" >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait "$PRED"
wait "$STARTER"
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 0
need_out "head-successor pid"
need_eq "$(mk field "$REC" head-successor budget)" "1.0" "the last head-successor is the stub's own hand-over"
need_file "$WORK/starter/rst-head-1.out"
# What reaches the head is the fixed resume instruction naming the run, never the hand-off's
# `## Resume prompt` (register entry 2026-10-08 23:12; the P1 legs below test the exclusion).
if ! grep -q -F "hands-off run rst," "$WORK/stub-rst.stdin.1"; then
  why="$why; the resume instruction did not reach the head on standard input"
fi
need_eq "$(cat "$WORK/stub-rst.env")" "rst" "AIMYTH_HANDSOFF_RUN seen by the head"
need_eq "$(mk field "$REC" supervise mode)" "launched" "supervise event"
verdict "_starter: waits for the predecessor pid, starts the head on stdin under AIMYTH_HANDSOFF_RUN, supervises it"

# The chain the record must show: head 1 completed without a hand-off → the supervisor's own
# head-exit (band unmetered: no transcript, exit_class completed, pack false, spent from the
# meter line) → one successor at the remainder → head 2 hands over → handed-over, ended.
need_eq "$(mk count "$REC" head-successor)" "3" "head-successors (starter, supervisor, the stub's own)"
need_eq "$(cat "$WORK/stub-rst.count")" "2" "stub invocations"
need_eq "$(mk count "$REC" successor-aborted)" "0" "successor-aborted events"
case $(mk field "$REC" observation note) in
  handed-over*) : ;;
  *) why="$why; the supervisor did not end handed-over: $(mk field "$REC" observation note)" ;;
esac
"$PY" - "$REC" <<'CHAIN' > "$WORK/chain.txt"
import json, sys
evs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
ex = [e for e in evs if e.get("event") == "head-exit" and e.get("exit_class")]
print("%s %s %s %s" % (ex[0]["band"], ex[0]["exit_class"], ex[0]["pack"], ex[0].get("spent_usd")) if ex else "none")
CHAIN
need_eq "$(cat "$WORK/chain.txt")" "unmetered completed False 16.56" "the supervisor's head-exit"
verdict "supervisor: a completed head with no hand-off gets one successor, then the hand-over ends the loop"

fixture rst2 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)"}' >/dev/null
rm -f "$WORK/harness2-stdin.txt"
TR=$(mk transcript sid-rst2 500000)
touch "$TR"
# --wait-s 2 against the 120 s silence proxy: the transcript cannot be quiet long enough, so
# the bound must expire and the starter must abort rather than start a second head.
run _starter --run rst2 --handoff "$HO" --budget 1.00 --out "$WORK/starter/rst2-head-1.out" \
    --wait-s 2 --harness-bin "$WORK/bin/harness2" --transcript "$TR"
need_rc 1
need_out "aborted"
need_eq "$(mk field "$REC" successor-aborted reason)" "timeout" "abort reason"
need_nofile "$WORK/harness2-stdin.txt"
verdict "_starter: the silence proxy times out and aborts (successor-aborted timeout)"

fixture rst3 200
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"unmetered (no transcript)"}' >/dev/null
mk append "$REC" '{"event":"observation","phase":"2","what":"a restart happened","note":"n"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"unmetered (no transcript)"}' >/dev/null
rm -f "$WORK/harness2-stdin.txt"
run _starter --run rst3 --handoff "$HO" --budget 1.00 --out "$WORK/starter/rst3-head-1.out" \
    --wait-s 5 --harness-bin "$WORK/bin/harness2" --transcript ""
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "unmetered-loop" "abort reason"
need_nofile "$WORK/harness2-stdin.txt"
verdict "_starter: two unmetered head-exits abort the restart (unmetered-loop, at most one)"

fixture rst4 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)"}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-already","pid":9003,"budget":2.0}' >/dev/null
rm -f "$WORK/harness2-stdin.txt"
run _starter --run rst4 --handoff "$HO" --budget 1.00 --out "$WORK/starter/rst4-head-1.out" \
    --wait-s 5 --harness-bin "$WORK/bin/harness2" --transcript ""
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "duplicate" "abort reason"
need_nofile "$WORK/harness2-stdin.txt"
verdict "_starter: a head-successor already following the head-exit aborts (duplicate)"

# ------------------------------ the head's first message (register entry 2026-10-08 23:12) ---
# Every head handsoff.py starts fresh receives a fixed resume instruction composed from the run id
# and the hand-off's real path. The hand-off's `## Resume prompt` is the owner's prompt for the
# next attended session and reaches no head: a launcher writes it through the shipped
# `resume-prompt` key, as each plant below is written, and the head that starts must not see it.
PLANT_ID="PLANTED-OWNER-PROMPT-4417"
PLANT_OWNER="$PLANT_ID walk me through the report"
first_ok() { # $1 captured first message, $2 run, $3 hand-off path: the fixed instruction's content
  [ -f "$1" ] || { why="$why; no first message captured at $1"; return 0; }
  if grep -q -F "$PLANT_ID" "$1"; then why="$why; the owner's planted prompt reached the head ($1)"; fi
  grep -q -F "hands-off run $2," "$1" || why="$why; the first message does not name the run $2 ($1)"
  grep -q -F "Hand-off: $3" "$1" || why="$why; the first message does not name the hand-off $3 ($1)"
  grep -q -F 'starting with its `## In flight` section' "$1" || why="$why; the first message does not send the head to In flight ($1)"
  grep -q -F 'the RUNBOOK and the decisions file' "$1" || why="$why; the first message does not name the RUNBOOK and the decisions file ($1)"
  grep -q -F 'is not an instruction to you' "$1" || why="$why; the first message does not set the owner's prompt aside ($1)"
  # The bootstrap (the delegate skill's section 4; the fix's review of 2026-10-09): EVERY head,
  # the run's first included (the fix's second review: the session meter partitions a run's
  # lanes by run-open and run-resume alone), reads the record's tail and `git status`, then runs
  # run-resume through the script under test, before any item work; the record then decides
  # only where the head starts (the first head's gate, else on from In flight).
  grep -q -F "Before any item work, whether you are the run's first head or a later one: read the tail of the run record $REALSTORE/spawn-records/$2.jsonl and \`git status\`, then run \`$PYABS -B " "$1" || why="$why; the first message does not send every head, the first included, to the record's tail, git status and the command, through the absolute interpreter ($1)"
  grep -q -F " run-resume --run $2 --session auto --head '<your model and effort>' --detail '<the item you start or resume>'\`. That registers your session on the record, which the session meter needs to count your helpers as yours." "$1" || why="$why; the first message does not carry the run-resume command for $2 with its reason ($1)"
  grep -q -F "Then, if that record shows no \`gate\` event written by an earlier head of this run, begin, as the run's first head does, at the gate In flight names; otherwise continue the run from In flight." "$1" || why="$why; the first message does not say where a first and a later head start ($1)"
  # The command is never inside a condition: no line that carries run-resume opens a branch
  # (scanned with its backtick spans and absolute paths cut, so a path can never decide it).
  fo_words=$(grep -F 'run-resume' "$1" | sed -e 's/`[^`]*`//g' -e 's|/[^ ]*||g')
  [ -n "$fo_words" ] || why="$why; no line of the first message carries run-resume ($1)"
  if printf '%s\n' "$fo_words" | grep -q -i -E '(^|[^a-z])(if|otherwise|unless|where)([^a-z]|$)'; then
    why="$why; the run-resume step sits under a condition: $(printf '%s' "$fo_words" | cut -c1-160) ($1)"
  fi
  fo_script=$(sed -n 's/.*`[^ `]* -B \([^ `]*\) run-resume .*/\1/p' "$1")
  if [ -z "$fo_script" ] || [ "$(real "$fo_script")" != "$(real "$H")" ]; then
    why="$why; the run-resume command names '$fo_script', not the script under test ($1)"
  fi
  return 0
}
plant_owner() { # $1 run: the owner's next-session prompt, written through the shipped key; the control
  run handoff --run "$1" --set "resume-prompt=$PLANT_OWNER"
  need_rc 0
  need_eq "$(grep -c -F "$PLANT_ID" "$HO")" "1" "control: the plant sits in the hand-off once"
  need_eq "$(mk section "$HO" "Resume prompt")" "$PLANT_OWNER" "control: the plant is the hand-off's whole Resume prompt"
}
first_wait() { # $1 file, $2 fixed string, $3 tries of 0.5 s: a detached supervisor ends late
  i=0
  while [ "$i" -lt "$3" ]; do
    if [ -f "$1" ] && grep -q -F -- "$2" "$1"; then return 0; fi
    sleep 0.5; i=$((i + 1))
  done
  why="$why; no '$2' in $1 within $3 half-seconds"; return 0
}

# P1-a: the successor command (the launch kit's path: `handoff --set resume-prompt=…`, then
# `successor`), its head captured by the stub harness through the starter it detaches.
fixture rfirst 200
viewer_use rfirst
plant_owner rfirst
sh -c 'exit 0' &
FIRSTDEAD=$!
wait "$FIRSTDEAD" || :
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run rfirst --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --predecessor-pid "$FIRSTDEAD" --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "the fixed resume instruction"
wait_field "$REC" head-successor session_id sid-by-the-head 40
first_wait "$REALSTORE/spawn-records/rfirst-head-1.out.starter.log" "— ended" 60
first_ok "$WORK/stub-rfirst.stdin.1" rfirst "$(real "$HO")"
need_eq "$(cat "$WORK/stub-rfirst.count")" "1" "heads started"
# The watermark hook reads a successor's first prompt for the hand-off it names: it must still
# find the hand-off in the composed instruction.
HOOKNAMED=$("$PY" - "$HOOKS_DIR/context-watermark.py" "$WORK/stub-rfirst.stdin.1" <<'HOOKFIRST'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("cw_first", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    with open(sys.argv[2], encoding="utf-8") as handle:
        print(mod.named_handoff(handle.read()) or "none")
except OSError as exc:
    print("unreadable: %s" % exc)
HOOKFIRST
)
need_eq "$HOOKNAMED" "$(real "$HO")" "the hand-off the watermark hook reads off the first message"
verdict "P1-a (register entry 2026-10-08 23:12): the head the successor command starts receives the fixed resume instruction — the run id, the hand-off's real path, In flight as the authority, the RUNBOOK and the decisions file, the bootstrap every head runs, the run's first included (the named record's tail and git status, then run-resume through the script under test, before any item work, under no condition; the record then decides only where the head starts: the first head's gate, else on from In flight), the owner's prompt set aside — and never the hand-off's Resume prompt, whose planted owner prompt is absent (control: the plant is that section, once); the watermark hook still names the hand-off from it"

# P1-b: the supervisor's own start path. The starter starts head 1, which completes with no
# hand-off; the supervisor records its head-exit and starts head 2 through succeed_exit and
# start_head. Both first messages are the fixed instruction.
fixture rfirst2 200
plant_owner rfirst2
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)"}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=1"
starter --run rfirst2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rfirst2-head-1.out" \
        --wait-s 5 --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_eq "$(cat "$WORK/stub-rfirst2.count")" "2" "heads started (the starter's, then the supervisor's own)"
SUPCHAIN=$("$PY" - "$REC" <<'SUPCHAIN'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    evs = [json.loads(line) for line in handle if line.strip()]
kinds = [e.get("event") for e in evs]
own = [i for i, e in enumerate(evs) if e.get("event") == "head-exit" and e.get("exit_class") == "completed"]
print("%d %s" % (len(own), bool(own) and "head-successor" in kinds[own[0] + 1:]))
SUPCHAIN
)
need_eq "$SUPCHAIN" "1 True" "the supervisor's own head-exit, then its head-successor"
first_ok "$WORK/stub-rfirst2.stdin.1" rfirst2 "$(real "$HO")"
first_ok "$WORK/stub-rfirst2.stdin.2" rfirst2 "$(real "$HO")"
verdict "P1-b (register entry 2026-10-08 23:12): on the supervisor's start path — the starter's head and the head the supervisor itself starts after a completed head with no hand-off (its head-exit, then its head-successor) — each first message is the fixed resume instruction with the run id, the hand-off path and the run-resume bootstrap, never the planted owner prompt (control: the plant is the hand-off's Resume prompt)"

# P1-c: the console's item names from a hand-off in the section shape a real night run's hand-off
# has (Resume prompt holding the owner's prompt, then In flight, Plan of record, Grants, Pointers,
# Trace, Findings ledger, Morning report). watch.py reads the Resume prompt's item lines first and
# the whole pack when that section names none, so the owner's prompt there must leave the item
# names the hand-off carries elsewhere readable. The control moves one item line under the Resume
# prompt, which must then win: the night shape's result is the fall-through, not a missed read.
NIGHT="$WORK/handoffs/rnight-handoff.md"
NIGHTOLD="$WORK/handoffs/rnight-old-handoff.md"
cat > "$NIGHT" <<'NIGHTHO'
# Hand-off: rnight (hands-off; a suite fixture in a night run's section shape)

Written by the attended launcher. From the launch on, this file is the run's hand-off.

## Resume prompt
PLANTED-OWNER-PROMPT-4417 walk me through the report

## In flight
- pack written: 2001-01-01T07:55:30+0100
Next: the run is closed; the owner's next session walks through the report.

Needs: the owner's decisions on the held fixes.

Decided: every item done or held; nothing pushed.

## Plan of record
The RUNBOOK beside the run's stage: items item0 to item2, each opening with a gate.
- item0 orientation — the RUNBOOK, the pre-flight and the decisions file
- item1 the compile — one compile lane over the inbox
- item2 close — the reflection, the report and the closing commit

## Grants
Those of the pre-flight, as confirmed by the owner's go.

## Pointers
- The close report: the run's report in the vault's output directory

## Trace
| Time | Item | Decision and its rule | Billed line | Waste so far |
|---|---|---|---|---|
| 23:15 | item0 → item1 | orientation done | billed (fixture) | none |

## Findings ledger
| Time | Item | Finding | Evidence | Routing |
|---|---|---|---|---|
| 23:15 | item0 | the fixture's one finding | fixture | none |

## Morning report
- **Spend against the envelope:** fixture
- **Warnings raised and handling:** see `## Findings ledger` (1 line)
NIGHTHO
"$PY" - "$NIGHT" "$NIGHTOLD" <<'NIGHTOLDPY'
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    text = handle.read()
line = "- item7 DECOY-IN-RESUME — an item line under the Resume prompt\n"
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    handle.write(text.replace("## Resume prompt\n", "## Resume prompt\n" + line, 1))
NIGHTOLDPY
NIGHTP=$("$PY" - "$SKILL_DIR/watch.py" "$NIGHT" "$NIGHTOLD" <<'NIGHTPY'
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("w_night", sys.argv[1])
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
for tag, path in (("NIGHT", sys.argv[2]), ("OLD", sys.argv[3])):
    items, src = w.pack_items([{"event": "run-open", "run": "rnight", "handoff": path}])
    print("%sITEMS %s %s" % (tag, json.dumps(items, sort_keys=True), src == path))
NIGHTPY
)
need_eq "$(printf '%s\n' "$NIGHTP" | grep '^NIGHTITEMS')" 'NIGHTITEMS {"item0": "orientation", "item1": "the compile", "item2": "close"} True' "the night shape's item names, read from the hand-off itself"
need_eq "$(printf '%s\n' "$NIGHTP" | grep '^OLDITEMS')" 'OLDITEMS {"item7": "DECOY-IN-RESUME"} True' "control: an item line under the Resume prompt is read first"
verdict "P1-c (register entry 2026-10-08 23:12): the console's item names still parse from a hand-off in a night run's section shape whose Resume prompt holds the owner's prompt — item0 to item2 from the Plan of record, the owner's prompt never an item — and the control's item line under the Resume prompt wins, so the result is the parser's fall-through"

# P1-c2: the item-name inputs a real night run's hand-off gives the console (the fix's second
# review, 2026-10-09, finding 4), as a literal fixture of that shape: the hand-off names no item
# rows of its own — its Plan of record points to a RUNBOOK, its Trace and ledger rows open with
# a pipe — and the pre-flight it names under Grants lists the items as colon rows
# (`- item0 orientation: …`), which the console's grammar (`item<k> <name> —`) does not read;
# the run-open carries expect_items for item0 to item9, as the launch writes them. What the
# console shows today, asserted rather than assumed: ten rows, item0 to item9, every name blank
# (the colon rows stay unnamed), the owner's prompt in Resume prompt never an item, and the
# source the hand-off itself. watch.py is unchanged by the fix, so this is what is preserved.
# The control proves the pre-flight is read and that a row in the grammar still parses: the
# same fixture with item3's row alone in the em-dash form names item3, its source the pre-flight.
cat > "$WORK/rnightreal-handoff.tmpl" <<'RNHO'
# Hand-off: @RUN@ (hands-off, a night run; head at max; a suite fixture in a real night hand-off's shape)

Written by the attended launcher. From the launch on, this file is the run's hand-off. Vault root V = @W@/vault.

## Resume prompt
researcher, shortest. Walk me through V/output/reports/night-report.md and the lessons note V/output/notes/lessons.md, highlights first, each with your recommendation, and take my decisions on whatever the night held. The run's hand-off is @W@/handoffs/@RUN@-handoff.md.

## In flight
- pack written: 2001-01-01T07:55:30+0100
Next: the run is closed. The owner's morning session walks through V/output/reports/night-report.md and the lessons note, highlights first, each with its recommendation, and takes his decisions (the Resume prompt above is his prompt for it).

Needs: the owner's decisions on the held fixes, each with options and a recommendation in the report.

Decided: (decisions.md D1 to D5; findings ledger rows 1 to 2) the compile, check and lessons note done; two fixes held with their staged builds kept in the stage; nothing pushed.

## Plan of record
@W@/stage/RUNBOOK.md: items item0 to item9. Each item opens with `handsoff.py gate` and ends with `handsoff.py boundary` in the direct form (RUNBOOK rule 10).

## Grants
Those of the pre-flight @W@/handoffs/@RUN@-preflight.md, revision 1 (the Grants table and the Stop conditions), as confirmed by the owner's go in @W@/stage/decisions.md.

## Pointers
- The fix plan, final version, with its review rounds and dispositions: @W@/stage/fix-plan.md
- Helper reports of this run: @W@/store/spawn-records/@RUN@-report-<lane>.md
- The close report: V/output/reports/night-report.md

## Trace
| Time | Item | Decision and its rule | Billed line | Waste so far |
|---|---|---|---|---|
| 23:15 | item0 → item1 | orientation done: RUNBOOK, pre-flight, decisions.md, the fix plan read; usage at start recorded | billed (fixture) · head $2.05 · lanes $0.00 · session $2.05 | none beyond orientation |
| 23:51 | item1 → item2 | the compile helper completed: five source pages, four concept pages | billed (fixture) · head $7.34 · lanes $0.00 · session $7.34 | none |


## Findings ledger
| Time | Item | Finding | Evidence | Routing |
|---|---|---|---|---|
| 23:15 | item0 | the head started with the owner's morning prompt as its first message and proceeded on In flight | the head's first message | register entry; morning report |
| 00:53 | item6 | decision: the hold rule judged not met, so the fix proceeds | grant G3 | morning report |


## Morning report
- **Spend against the envelope:** billed (fixture) · head $49.10 · lanes $0.00 · session $49.10 · envelope $500.0
- **Warnings raised and handling:** see `## Findings ledger` (2 lines)
RNHO
cat > "$WORK/rnightreal-preflight.tmpl" <<'RNPF'
# Pre-flight: @RUN@ (hands-off, a night run; head at max; a suite fixture in a real pre-flight's shape)

Status: revision 2, written by the attended session on the owner's ask. Fix plan: @W@/stage/fix-plan.md, version 3, after two independent review rounds.

## What the run does, in order
- item0 orientation: the RUNBOOK, this pre-flight, decisions.md, the fix plan with its review reports; both usage windows read.
- item1 the compile: a one-word probe of the open-work model, then one compile helper over the five sources in the raw inbox.
- item2 the check: the verify helper under the ingest Verify step (M0 file, raw slices, plant); the head settles every non-zero score.
- item3 the lessons: the head writes a lessons note for the morning walk-through, each lesson with its source page and confidence tier.
- item4 fixes F1 and F2 (both helper launchers): one builder in one combined staged copy, a review, folds as needed, then both installed together.
- item5 fix F3 (the stray tool-tag check): a design review first, then a builder, a review and the install.
- item6 fix F5 (the compile source budget): the bound derived from item2's verify scores, a review, the install.
- item7 fix F6: two register entries closed after their grep is re-run with a control.
- item8 declined (D2 no: no spine exists yet): skipped.
- item9 close: the cross-reflection over the run's transcript, the head's single reflect --yes, the morning report, the final hand-off and the closing commit.

## Lanes
| Lane | Task | Model | Effort | Ultra |
|---|---|---|---|---|
| C5 | compile the five sources | the open-work model after a one-word probe | xhigh | no |
| V1 | verify C5's pages | the closed-work model | xhigh | no |

## Parameters
- Head: at max, launched by handsoff.py successor.
- Envelope: soft USD 100; hard stop USD 500.

## Grants
| # | Value on go |
|---|---|
| G1 | items in order, item0 to item9 (item8 only on D2); each opens with gate and ends with boundary |
| G9 | soft USD 100, hard stop USD 500 |

## Stop conditions
- A suite still red after one fix cycle at an install: restore the backup and hold that fix.

## Decisions for the owner's go
- D1 · go for items 0 to 7 and 9. Recommended: yes.
- D2 · item8, the two first drafts. Recommended: yes.

## Close report
V/output/reports/night-report.md, walked through with the owner in the morning.
RNPF
RNREAL=$("$PY" - "$SKILL_DIR/watch.py" "$WORK" "$VAULT" <<'RNREALPY'
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location("w_nightreal", sys.argv[1])
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
work, vault = sys.argv[2], sys.argv[3]
expect = {"item%d" % k: 40000 for k in range(10)}   # the launch's expect_items keys, item0 to item9


def fill(tmpl, run, dst, swap=None):
    with open(os.path.join(work, tmpl), encoding="utf-8") as handle:
        text = handle.read().replace("@W@", work).replace("@RUN@", run)
    if swap:
        assert text.count(swap[0]) == 1, "the control's row is not in the fixture once"
        text = text.replace(swap[0], swap[1])
    with open(dst, "w", encoding="utf-8") as handle:
        handle.write(text)
    return text


def record(run, handoff):
    path = os.path.join(work, "%s.jsonl" % run)
    rows = [{"ts": "2001-01-01T23:12:27+0100", "run": run, "event": "run-open", "session": run + "-seed",
             "session_kind": "seed", "handoff": handoff, "expect_items": expect},
            {"ts": "2001-01-01T23:15:38+0100", "run": run, "event": "gate", "item": "item0",
             "decision": "allow"}]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(json.dumps(r) + "\n" for r in rows))
    return path, rows


row3 = "- item3 the lessons: the head writes"
for tag, run, swap in (("REAL", "rnightreal", None),
                       ("CTRL", "rnightrealc", (row3, "- item3 the lessons — the head writes"))):
    ho = os.path.join(work, "handoffs", "%s-handoff.md" % run)
    pf = os.path.join(work, "handoffs", "%s-preflight.md" % run)
    hotext = fill("rnightreal-handoff.tmpl", run, ho)
    pftext = fill("rnightreal-preflight.tmpl", run, pf, swap)
    rec, rows = record(run, ho)
    items, src = w.pack_items(rows)
    shown = w.Run(run, rec, vault)
    print("%sHO %s" % (tag, json.dumps(w.parse_items(hotext), sort_keys=True)))
    print("%sPF %s" % (tag, json.dumps(w.parse_items(pftext), sort_keys=True)))
    print("%sPACK %s %s" % (tag, json.dumps(items, sort_keys=True),
                            "handoff" if src == ho else "preflight" if src == pf else src))
    print("%sCONSOLE %s | %s" % (tag, " ".join(shown.item_order),
                                 " ".join("%s=%s" % (k, shown.names.get(k, "") or "-")
                                          for k in shown.item_order)))
    print("%sCANDIDATES %s" % (tag, json.dumps([c == pf for c in w.preflight_candidates(hotext, ho, run)])))
RNREALPY
)
rnr() { printf '%s\n' "$RNREAL" | grep "^$1 " | cut -d' ' -f2-; }
BLANK10='{"item0": "", "item1": "", "item2": "", "item3": "", "item4": "", "item5": "", "item6": "", "item7": "", "item8": "", "item9": ""}'
ORDER10="item0 item1 item2 item3 item4 item5 item6 item7 item8 item9"
need_eq "$(rnr REALHO)" "{}" "the real shape's hand-off names no item row of its own (Resume prompt, Plan of record, Trace and ledger alike)"
need_eq "$(rnr REALCANDIDATES)" "[true]" "control: the console finds the pre-flight the hand-off names"
need_eq "$(rnr REALPF)" "{}" "the pre-flight's colon rows are outside the console's grammar"
need_eq "$(rnr REALPACK)" "$BLANK10 handoff" "the console's items: item0 to item9 from expect_items, every name blank, the source the hand-off"
need_eq "$(rnr REALCONSOLE)" "$ORDER10 | item0=- item1=- item2=- item3=- item4=- item5=- item6=- item7=- item8=- item9=-" "the console's item rows as its model holds them"
need_eq "$(rnr CTRLPF)" '{"item3": "the lessons"}' "control: one em-dash row in the same pre-flight parses"
need_eq "$(rnr CTRLPACK)" '{"item0": "", "item1": "", "item2": "", "item3": "the lessons", "item4": "", "item5": "", "item6": "", "item7": "", "item8": "", "item9": ""} preflight' "control: that name reaches the console from the pre-flight, the colon rows still blank"
need_eq "$(rnr CTRLCONSOLE)" "$ORDER10 | item0=- item1=- item2=- item3=the lessons item4=- item5=- item6=- item7=- item8=- item9=-" "control: the console's rows with the one parsed name"
need_eq "$(printf '%s\n' "$RNREAL" | grep -c .)" "10" "every probe answered"
verdict "P1-c2 (the fix's second review, 2026-10-09, finding 4): on a literal fixture of a real night hand-off's item-name inputs — a hand-off whose Plan of record points to a RUNBOOK, a pre-flight it names under Grants whose item rows use colons, expect_items for item0 to item9 — the console shows today ten rows, item0 to item9, every name blank, from the hand-off, and the owner's Resume prompt is never an item: what the fix preserves is exactly this (names that parse still parse; unnamed rows stay unnamed), since watch.py is unchanged (control: one em-dash row in the same pre-flight is read and named, so the pre-flight is consulted and the blanks are the grammar's)"

# P1-d: the seed launch (the launch kit's own path: a seeded run-open, the owner's next-session
# prompt written through the shipped key, then `successor --pack-fresh`). The run's first head
# starts on the fixed instruction and never on the plant. The record holds no gate, so the
# message's branch for this head is the first head's, and the text is the same as every start's.
seed_fixture rfirstseed 200
viewer_use rfirstseed
plant_owner rfirstseed
need_eq "$(mk field "$REC" run-open session_kind)" "seed" "control: the run-open is a launcher's seed"
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run rfirstseed --pack-fresh --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "successor: pid none (run-open, seed: no pid)"
need_out "the fixed resume instruction"
wait_field "$REC" head-successor session_id sid-by-the-head 40
SEEDLOG="$REALSTORE/spawn-records/rfirstseed-head-1.out.starter.log"
first_wait "$SEEDLOG" "— ended" 60
need_eq "$(grep -c '"what": "pack-fresh"' "$REC")" "1" "control: the --pack-fresh observation"
if ! grep -q -F "pack: fresh — --pack-fresh recorded at" "$SEEDLOG"; then
  why="$why; control: the starter did not take the --pack-fresh word: $(grep -F 'pack:' "$SEEDLOG")"
fi
need_eq "$(mk count "$REC" gate)" "0" "control: no gate on the record before the first head"
need_eq "$(cat "$WORK/stub-rfirstseed.count")" "1" "heads started"
first_ok "$WORK/stub-rfirstseed.stdin.1" rfirstseed "$(real "$HO")"
verdict "P1-d (register entry 2026-10-08 23:12): on the seed launch's path — a seeded run-open, the owner's prompt planted through the shipped resume-prompt key, then successor --pack-fresh — the run's first head receives the fixed resume instruction with its bootstrap, which sends this first head too to run-resume before any item work, and never the planted owner prompt (controls: the plant is the hand-off's whole Resume prompt, the record is seeded, the starter took the --pack-fresh word, no gate precedes the head)"

# P1-e: the meter partition on the seed launch (the fix's second review, 2026-10-09, finding 1).
# fable-share.py places a lane in the partition the latest run-open or run-resume opened and reads
# no head-successor, so the run's first head owns its helpers only once its own run-resume is on
# the record. The seed launch runs for real (`successor --pack-fresh` on a seeded record); its head
# is the bootstrap stub below, which does mechanically what the first message's bootstrap says
# before any item work: it takes the one run-resume command the message carries, fills its two
# placeholders, waits for its own head-successor, runs the command as written, then spawns one
# helper (the lane events the wrapper writes) and hands over as the stub head does. The record is
# then the seed launch's (run-open, the seed's head-exit, head-successor, the first head's
# run-resume, one helper's lane events), and the session meter's own reader and matcher
# (read_spawn_record, session_matches, partition_label: the selection main() applies) give the
# helper to the started head. Control, the review's: the same record with the run-resume dropped
# gives that head no helper and the billed line's `recorded under no partition` label.
cat > "$WORK/bin/boothead" <<'BOOTHEAD'
#!/bin/sh
RUN=${AIMYTH_HANDSOFF_RUN:-none}
REC="$SUITE_STORE/spawn-records/$RUN.jsonl"
CF="$SUITE_WORK/boot-$RUN.count"; n=0; [ -f "$CF" ] && n=$(cat "$CF"); n=$((n + 1)); echo "$n" > "$CF"
cat > "$SUITE_WORK/boot-$RUN.stdin.$n"
sid=""; prev=""
for arg in "$@"; do [ "$prev" = "--session-id" ] && sid=$arg; prev=$arg; done
if [ "$n" = "1" ]; then
  i=0
  while [ "$i" -lt 40 ] && ! grep -q -F -- "$sid" "$REC"; do sleep 0.25; i=$((i + 1)); done
  sed -n 's/.*`\([^ `]* -B [^`]* run-resume [^`]*\)`.*/\1/p' "$SUITE_WORK/boot-$RUN.stdin.$n" \
    | sed -e 's/<your model and effort>/stub-model stub-effort/' -e 's/<the item you start or resume>/item0/' \
    > "$SUITE_WORK/boot-$RUN.cmd"
  rc=0
  sh "$SUITE_WORK/boot-$RUN.cmd" > "$SUITE_WORK/boot-$RUN.resume.out" 2>&1 || rc=$?
  echo "$rc" > "$SUITE_WORK/boot-$RUN.resume.rc"
  "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"lane-open","lane":"H1","reason":"(a) the first head'"'"'s helper"}' >/dev/null
  "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"lane-spawned","lane":"H1","session_id":"sid-boot-helper"}' >/dev/null
  "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"lane-closed","lane":"H1","exit_class":"completed","total_cost_usd":0.5}' >/dev/null
fi
"$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-exit","band":60,"context":"stub","spent_usd":1.0,"pack":true}' >/dev/null
"$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-successor","session_id":"sid-by-the-head","pid":1,"budget":1.0}' >/dev/null
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"handed over"}'
exit 0
BOOTHEAD
chmod +x "$WORK/bin/boothead"
seed_fixture rmeter 200
viewer_use rmeter
need_eq "$(mk field "$REC" run-open session_kind)" "seed" "control: the run-open is a launcher's seed"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rmeter --pack-fresh --meter-line "$METER" --harness-bin "$WORK/bin/boothead" \
    --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
wait_field "$REC" head-successor session_id sid-by-the-head 40
first_wait "$REALSTORE/spawn-records/rmeter-head-1.out.starter.log" "— ended" 60
need_eq "$(cat "$WORK/boot-rmeter.count")" "1" "heads started"
first_ok "$WORK/boot-rmeter.stdin.1" rmeter "$(real "$HO")"
need_eq "$(grep -c . "$WORK/boot-rmeter.cmd")" "1" "one run-resume command in the first message"
need_eq "$(cat "$WORK/boot-rmeter.resume.rc")" "0" "the run-resume the message carries, run as written ($(tail -c 300 "$WORK/boot-rmeter.resume.out"))"
METERP=$("$PY" - "$SKILL_DIR/fable-share.py" "$REC" "$WORK/rmeter-without-resume.jsonl" <<'METERPY'
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("fs_meter", sys.argv[1])
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)
rec, without = sys.argv[2], sys.argv[3]
with open(rec, encoding="utf-8") as handle:
    lines = [line for line in handle if line.strip()]
evs = [json.loads(line) for line in lines]
kinds = [e.get("event") for e in evs]
head = next(e["session_id"] for e in evs if e.get("event") == "head-successor")   # the started head
resumes = [e for e in evs if e.get("event") == "run-resume"]
first = lambda kind: kinds.index(kind) if kind in kinds else -1
print("SHAPE %s" % (0 <= first("run-open") < first("head-exit") < first("head-successor")
                    < first("run-resume") < first("lane-open")))
print("RESUMES %d %s" % (len(resumes), all(e.get("session") == head for e in resumes)))
with open(without, "w", encoding="utf-8") as handle:   # the control: the run-resume dropped
    handle.write("".join(line for line, e in zip(lines, evs) if e.get("event") != "run-resume"))


def meter(path):
    lanes, _, parts, marked, _, _, _ = fs.read_spawn_record(path)
    mine = set(i for i, part in enumerate(parts) if fs.session_matches(part["session"], head))
    picked = [lane["name"] for lane in lanes
              if (not marked) or any(span["partition"] in mine for span in lane["spans"])]
    chosen = sorted(set(span["partition"] for lane in lanes for span in lane["spans"]
                        if span["partition"] in mine))
    label = fs.partition_label(parts, chosen, head) if marked else "no markers"
    return picked, label.replace(head[:8], "HEAD"), len(lanes)


for tag, path in (("WITH", rec), ("WITHOUT", without)):
    picked, label, total = meter(path)
    print("%s %d of %d %s · %s" % (tag, len(picked), total, ",".join(picked) or "-", label))
METERPY
)
mtr() { printf '%s\n' "$METERP" | grep "^$1 " | cut -d' ' -f2-; }
need_eq "$(mtr SHAPE)" "True" "control: run-open, the seed's head-exit, head-successor, the first head's run-resume, then the helper"
need_eq "$(mtr RESUMES)" "1 True" "one run-resume, naming the started head's session"
need_eq "$(mtr WITH)" "1 of 1 H1 · recorded under run-resume HEAD" "the session meter's partition with the first head's run-resume"
need_eq "$(mtr WITHOUT)" "0 of 1 - · recorded under no partition for HEAD" "control: the same record without the run-resume"
verdict "P1-e (the fix's second review, 2026-10-09, finding 1): on the seed launch (successor --pack-fresh on a seeded record), the first head, doing what its first message's bootstrap says before any item work, runs the run-resume command the message carries through the script under test; on the record that leaves (run-open, the seed's head-exit, head-successor, the first head's run-resume, one helper's lane events) the session meter's reader gives the helper to the started head, 1 of 1 recorded under its run-resume (control, the review's: the same record without the run-resume gives that head 0 of 1, recorded under no partition)"

# ------------------------- the repeat-exit guard and a refused gate (register 2026-09-23 12:4x) ---
# start_guards' item_before reads only the head's latest start window. A refusal on an item
# never allowed in that window names no attempt, whatever the gate order. Allowed items less
# completed boundaries must leave exactly one unfinished item. The must-fire controls are
# two exits after allowed gates on one item and a head that also refused that same item.
# A completed boundary (`phase-boundary`, which cmd_boundary writes with `from` and `to`) ends the
# backward read with no item (the fix's review, 2026-10-09): a head that completed item15 and was
# refused at item16 made no attempt on item15. P2-c and P2-d are that case at 80 and at 90; their
# no-boundary variants also name no item because item16 was never allowed. A boundary BEFORE
# the allowed gate on a different item must not hide a repeat (P2-b).
REX=$("$PY" - "$H" <<'REXPY'
import ast
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("h_rex", sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
# Exercise the nested attribution directly for the first-head projection, without changing
# production visibility or running a starter. Both baseline and current source use this name.
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
guard = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "start_guards")
item_fn = next(n for n in guard.body if isinstance(n, ast.FunctionDef) and n.name == "item_before")
item_code = compile(ast.Module(body=[item_fn], type_ignores=[]), sys.argv[1], "exec")


def item_at_exit(evs):
    scope = dict(vars(h), events=evs)
    exec(item_code, scope)
    return scope["item_before"](len(evs) - 1)


def gate(item, decision):
    return {"event": "gate", "item": item, "decision": decision, "metered": True,
            "fit": decision == "allow"}


def chain(first, second, first_band=80, second_band=90, before=()):
    evs = [{"event": "run-open", "session": "sid-a"}] + list(before)
    evs += [first, {"event": "head-exit", "band": first_band, "pack": True},
            {"event": "head-successor", "session_id": "sid-b", "pid": 1, "budget": 1.0}]
    evs += list(second) if isinstance(second, (list, tuple)) else [second]
    evs += [{"event": "head-exit", "band": second_band, "pack": True}]
    return evs


def boundary(src, dst):
    # the fields cmd_boundary writes: from, to, disposition, next
    return {"event": "phase-boundary", "from": src, "to": dst, "disposition": "done",
            "next": dst}


def reason(evs):
    hi = max(i for i, e in enumerate(evs) if e.get("event") == "head-exit")
    return h.start_guards(evs, hi)[0]


refused, allowed = gate("item15", "refuse"), gate("item15", "allow")
completed = [allowed, boundary("item15", "item16"), gate("item16", "refuse")]
for name, evs in (("REFUSED80", chain(refused, allowed)),
                  ("REFUSED90", chain(refused, allowed, 90, 80)),
                  ("OTHERITEM", chain(refused, allowed, before=(gate("item14", "allow"),))),
                  ("ALLOWED", chain(allowed, allowed)),
                  ("WORKED", chain(refused, allowed, before=(gate("item15", "allow"),))),
                  ("BAND60", chain(allowed, allowed, 80, 60)),
                  ("COMPLETED80", chain(allowed, completed, 80, 80)),
                  ("COMPLETED90", chain(allowed, completed, 80, 90)),
                  ("NOBOUNDARY", chain(allowed, [allowed, gate("item16", "refuse")], 80, 80)),
                  ("NOBOUNDARY90", chain(allowed, [allowed, gate("item16", "refuse")], 80, 90)),
                  ("BOUNDARYFIRST", chain(allowed, allowed, 80, 90,
                                          before=(boundary("item14", "item15"),)))):
    print("%s %s" % (name, reason(evs)))
# T1 projects the incident onto the fields the guards read: seed, two starts per head,
# gates and exits. Its 17 events are synthetic; no record session or run identifiers ship.
t1 = [{"event": "run-open", "session": "seed"}, {"event": "head-exit", "band": 0},
      {"event": "head-successor", "session_id": "sid-a"},
      {"event": "run-resume", "session": "sid-a"}, gate("item0", "allow"),
      boundary("item0", "item1"), gate("item1", "refuse"), gate("item6", "refuse"),
      gate("item7", "allow"), {"event": "head-exit", "band": 80},
      {"event": "head-successor", "session_id": "sid-b"},
      {"event": "run-resume", "session": "sid-b"}, gate("item1", "allow"),
      gate("item6", "allow"), gate("item7", "allow"), gate("item8", "refuse"),
      {"event": "head-exit", "band": 80}]
l1 = [{"event": "run-open", "session": "sid-a"}, gate("item1", "refuse"),
      gate("item6", "refuse"), gate("item7", "allow"), {"event": "head-exit", "band": 80}]
x, y = gate("X", "allow"), gate("Y", "allow")
for name, evs in (("T1", t1),
                  ("T3b", chain(x, x, 80, 80, before=(gate("Y", "refuse"),))),
                  ("T4", chain(y, [x, y], 80, 80, before=(x,))),
                  ("T5", chain(gate("Y", "refuse"), [x, gate("Y", "refuse")],
                               80, 80, before=(x,))),
                  ("T2r", [{"event": "run-open", "session": "older"}, y,
                            {"event": "head-exit", "band": 0}] + chain(x, x, 80, 80)),
                  ("SUBTRACT", chain(x, [x, y, boundary("Y", "Z"), x], 80, 80)),
                  ("MALFORMED", chain(x, [x, {"event": "gate", "item": "X"}], 80, 80)),
                  ("BADITEM", chain(x, [gate([], "allow"), x], 80, 80)),
                  ("BADBOUNDARY", chain(x, [{"event": "phase-boundary"}, x], 80, 80)),
                  ("NOSTART", [x, {"event": "head-exit", "band": 80}, x,
                               {"event": "head-exit", "band": 80}])):
    print("%s %s" % (name, reason(evs)))
print("L1 %s" % item_at_exit(l1))
REXPY
) || die "repeat-exit in-memory premises failed"
rex() { printf '%s\n' "$REX" | grep "^$1 " | cut -d' ' -f2; }
need_eq "$(rex REFUSED80)" "None" "a refused gate before the 80 exit, an allowed one before the 90 exit"
need_eq "$(rex REFUSED90)" "None" "the same at 90 then 80"
need_eq "$(rex OTHERITEM)" "None" "the first head's allowed gate on another item, then a refused one"
# 11 existing cases, 5 requested projections, one residual loop and 5 premise/set controls.
need_eq "$(printf '%s\n' "$REX" | grep -c .)" "22" "every case answered"
verdict "P2-a (register entry 2026-09-23 12:4x, must not fire): a refused item never allowed in that head's window names no attempt, including when another item was allowed"
need_eq "$(rex ALLOWED)" "repeat-exit" "two exits at 80 and 90, each after an allowed gate on item15"
need_eq "$(rex WORKED)" "repeat-exit" "an allowed gate on item15, then a refused one, before the first exit"
need_eq "$(rex BOUNDARYFIRST)" "repeat-exit" "a boundary into item15 before head A's allowed gate on it, then head B's allowed gate"
need_eq "$(rex BAND60)" "None" "control: the band rule is unchanged (a 60 exit never counts)"
verdict "P2-b (register entry 2026-09-23 12:4x, must fire): two band exits at 80 and 90, each after an ALLOWED gate on the same unfinished item, fire repeat-exit, as does a head that worked the item before its refused gate, and a boundary into the item before the first head's allowed gate hides nothing; the band rule is unchanged (control: a 60 exit does not fire)"
need_eq "$(rex COMPLETED80)" "None" "head A allowed item15 and exited at 80; head B allowed item15, completed item15 → item16, was refused at item16 and exited at 80"
need_eq "$(rex NOBOUNDARY)" "None" "the same at 80 without the completed boundary names no item: item16 was never allowed"
need_eq "$(rex ALLOWED)" "repeat-exit" "control: one unfinished allowed item per head still fires"
verdict "P2-c (must not fire): the completed boundary ends the backward read; without it, the refusal on item16, never allowed in this window, also names no item (control: ALLOWED fires)"
need_eq "$(rex COMPLETED90)" "None" "the same with head B's exit at 90"
need_eq "$(rex NOBOUNDARY90)" "None" "the same at 90 without the completed boundary names no item: item16 was never allowed"
need_eq "$(rex WORKED)" "repeat-exit" "control: refusing the same item after allowing it still fires"
verdict "P2-d (must not fire): the boundary and no-boundary cases also name no item at band 90 (control: WORKED fires)"
for name in T1 T3b T4 T5 L1; do
  need_eq "$(rex "$name")" "None" "$name: no attributable single-item attempt"
done
need_eq "$(rex T2r)" "repeat-exit" "T2r: another head's earlier unfinished item cannot hide a loop"
verdict "repeat-exit window projections: T1, L1 and T3b clear; T4 and T5 pin the accepted residual (multiple unfinished items, or re-allowed work and a never-allowed refusal); T2r still catches the single-item loop (control)"
for name in MALFORMED BADITEM BADBOUNDARY NOSTART; do
  need_eq "$(rex "$name")" "None" "$name: an unreadable premise names no item"
done
need_eq "$(rex SUBTRACT)" "repeat-exit" "control: completing Y leaves X as the sole unfinished item"
verdict "repeat-exit window premises: malformed gates and boundaries or no start cannot fire; completed items are subtracted (control)"

# P2-c through the starter: the completed-boundary record starts its successor; the boundary is
# written in cmd_boundary's own shape (from, to, disposition, next).
fixture rrexc 200
mk append "$REC" '{"event":"gate","item":"item15","decision":"allow","metered":true,"fit":true}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)","pack":true}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rrexc-2","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"gate","item":"item15","decision":"allow","metered":true,"fit":true}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"item15","to":"item16","disposition":"done","next":"item16: the next item"}' >/dev/null
mk append "$REC" '{"event":"gate","item":"item16","decision":"refuse","metered":true,"fit":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"810,000 tokens (81 %)","pack":true}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rrexc --handoff "$HO" --budget 3.50 --out "$WORK/starter/rrexc-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" successor-aborted)" "0" "successor-aborted events"
need_absent "repeat-exit"
need_file "$WORK/stub-rrexc.stdin.1"
verdict "P2-c through the starter: head A's band-80 exit after an allowed gate on item15, then head B's band-80 exit after completing item15 → item16 and a refused gate on item16, starts the successor (no successor-aborted)"

# The same two cases through the starter: the refused-gate record starts its head, the allowed one
# aborts before any head with successor-aborted repeat-exit.
fixture rrexa 200
mk append "$REC" '{"event":"gate","item":"item15","decision":"refuse","metered":true,"fit":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"560,000 tokens (56 %)","pack":true}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rrexa-2","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"gate","item":"item15","decision":"allow","metered":true,"fit":true}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":90,"context":"900,000 tokens (90 %)","pack":true}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rrexa --handoff "$HO" --budget 3.50 --out "$WORK/starter/rrexa-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" successor-aborted)" "0" "successor-aborted events"
need_file "$WORK/stub-rrexa.stdin.1"
verdict "P2-a through the starter: a band exit after a refused gate, then a band exit after an allowed gate on the same item, starts the successor (no successor-aborted)"

fixture rrexb 200
mk append "$REC" '{"event":"gate","item":"item15","decision":"allow","metered":true,"fit":true}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"800,000 tokens (80 %)","pack":true}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rrexb-2","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"gate","item":"item15","decision":"allow","metered":true,"fit":true}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":90,"context":"900,000 tokens (90 %)","pack":true}' >/dev/null
rm -f "$WORK/harness2-stdin.txt"
run _starter --run rrexb --handoff "$HO" --budget 1.00 --out "$WORK/starter/rrexb-head-1.out" \
    --wait-s 5 --harness-bin "$WORK/bin/harness2" --transcript ""
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "repeat-exit" "abort reason"
need_out "the last two head-exits followed a gate on the same item (item15)"
need_nofile "$WORK/harness2-stdin.txt"
verdict "P2-b through the starter: two band exits after allowed gates on the same item abort with successor-aborted repeat-exit and start no head"

# P2-e: the no-progress rule (the fix's second review, 2026-10-09, finding 2). A refused gate is
# no attempt on its item, so the attempt comparison skips it; two heads in turn that are each
# refused at the same pending item have still made no progress, and a third start would only be
# refused again. start_guards' second repeat-exit rule stops such a chain: the last two exits by
# two different heads (the sessions their latest run-open, run-resume or head-successor name),
# each at band 80 or 90, each after a refused gate on the same item, with no allowed gate and no
# completed boundary between the two refusals. All four band pairings must stop; the controls
# must not (an allowed gate or a completed boundary between the refusals, another item, a band-60
# exit, one head resumed in place, unreadable sessions, one refusal answered by two exits of one
# head). P2-a (refused, then allowed: proceeds), P2-b (two allowed attempts: stops), P2-c and
# P2-d (a completed boundary, then a refusal: proceeds) above are unchanged and still hold.
REXE=$("$PY" - "$H" <<'REXEPY'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("h_rexe", sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def gate(item, decision):
    return {"event": "gate", "item": item, "decision": decision, "metered": True,
            "fit": decision == "allow"}


def boundary(src, dst):
    return {"event": "phase-boundary", "from": src, "to": dst, "disposition": "done", "next": dst}


def chain(first, second, first_band, second_band, start=None, opener=None):
    evs = [opener or {"event": "run-open", "session": "sid-a"}] + list(first)
    evs += [{"event": "head-exit", "band": first_band, "pack": True}]
    evs += [start or {"event": "head-successor", "session_id": "sid-b", "pid": 1, "budget": 1.0}]
    evs += list(second) + [{"event": "head-exit", "band": second_band, "pack": True}]
    return evs


def answer(evs):
    hi = max(i for i, e in enumerate(evs) if e.get("event") == "head-exit")
    reason, detail = h.start_guards(evs, hi)
    return "%s%s" % (reason, " no-progress" if detail and "no progress" in detail else "")


refused = gate("item15", "refuse")
cases = [("NP%d%d" % (a, b), chain([refused], [refused], a, b)) for a in (80, 90) for b in (80, 90)]
cases += [
    ("NPTWICE", chain([refused], [refused, refused], 80, 90)),
    ("NPALLOWED", chain([refused], [gate("item15", "allow"), refused], 80, 90)),
    ("NPBOUNDARY", chain([refused], [boundary("item14", "item15"), refused], 80, 90)),
    ("NPOTHER", chain([refused], [gate("item16", "refuse")], 80, 90)),
    ("NPBAND60", chain([refused], [refused], 60, 80)),
    ("NPBAND60B", chain([refused], [refused], 90, 60)),
    ("NPRESUMED", chain([refused], [refused], 80, 90,
                        start={"event": "head-resumed", "session_id": "sid-a", "pid": 1})),
    ("NPNOSESSION", chain([refused], [refused], 80, 90, start={"event": "head-successor", "pid": 1},
                          opener={"event": "run-open"})),
    ("NPONEHEAD", [{"event": "run-open", "session": "sid-a"},
                   {"event": "head-successor", "session_id": "sid-b", "pid": 1},
                   refused, {"event": "head-exit", "band": 80, "pack": True},
                   {"event": "head-exit", "band": 90, "pack": True}]),
    ("NPEMPTYITEM", chain([gate("", "refuse")], [gate("", "refuse")], 80, 90)),
    ("NPLISTITEM", chain([gate([], "refuse")], [gate([], "refuse")], 80, 90)),
]
for name, evs in cases:
    print("%s %s" % (name, answer(evs)))
REXEPY
) || die "no-progress in-memory premises failed"
rexe() { printf '%s\n' "$REXE" | grep "^$1 " | cut -d' ' -f2-; }
need_eq "$(rexe NP8080)" "repeat-exit no-progress" "two heads in turn refused at item15, exits at 80 and 80"
need_eq "$(rexe NP8090)" "repeat-exit no-progress" "the same at 80 and 90"
need_eq "$(rexe NP9080)" "repeat-exit no-progress" "the same at 90 and 80"
need_eq "$(rexe NP9090)" "repeat-exit no-progress" "the same at 90 and 90"
need_eq "$(rexe NPTWICE)" "repeat-exit no-progress" "the second head refused twice at item15, nothing allowed between"
need_eq "$(rexe NPALLOWED)" "None" "control: an allowed gate on item15 between the two refusals"
need_eq "$(rexe NPBOUNDARY)" "None" "control: a completed boundary between the two refusals"
need_eq "$(rexe NPOTHER)" "None" "control: the second head refused at another item"
need_eq "$(rexe NPBAND60)" "None" "control: the first exit at band 60"
need_eq "$(rexe NPBAND60B)" "None" "control: the second exit at band 60"
need_eq "$(rexe NPRESUMED)" "None" "control: one head resumed in place (one session) is not two heads"
need_eq "$(rexe NPNOSESSION)" "None" "control: no session readable on the record, so two heads cannot be shown"
need_eq "$(rexe NPONEHEAD)" "None" "control: one head's one refusal answered by two exits"
need_eq "$(rexe NPEMPTYITEM)" "None" "an empty refused item cannot prove no progress"
need_eq "$(rexe NPLISTITEM)" "None" "a non-string refused item cannot prove no progress"
# 13 existing no-progress cases plus two unreadable-item cases.
need_eq "$(printf '%s\n' "$REXE" | grep -c .)" "15" "every case answered"
verdict "P2-e (the fix's second review, 2026-10-09, must fire): two heads in turn, each exiting at band 80 or 90 after a refused gate on the same item with no allowed gate and no completed boundary between the two refusals, stop with repeat-exit in all four band pairings (80/80, 80/90, 90/80, 90/90; and a second head refused twice) — no progress; none of the controls fires: an allowed gate or a completed boundary between the refusals, another item, a band-60 exit on either side, one head resumed in place, unreadable sessions, one refusal answered by two exits of one head"

# P2-e through the starter: the 80/90 pairing on a real record aborts before any head.
fixture rrexe 200
mk append "$REC" '{"event":"gate","item":"item15","decision":"refuse","metered":true,"fit":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"420,000 tokens (42 %)","pack":true}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-2-rrexe","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"run-resume","session":"sid-2-rrexe","head":"fixture head 2","detail":"item15"}' >/dev/null
mk append "$REC" '{"event":"gate","item":"item15","decision":"refuse","metered":true,"fit":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":90,"context":"430,000 tokens (43 %)","pack":true}' >/dev/null
rm -f "$WORK/harness2-stdin.txt"
run _starter --run rrexe --handoff "$HO" --budget 1.00 --out "$WORK/starter/rrexe-head-1.out" \
    --wait-s 5 --harness-bin "$WORK/bin/harness2" --transcript ""
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "repeat-exit" "abort reason"
need_out "each followed a refused gate on the same item (item15) with no allowed gate and no completed boundary between the two refusals: no progress"
need_nofile "$WORK/harness2-stdin.txt"
need_eq "$(mk count "$REC" head-successor)" "1" "no head-successor written after the abort"
verdict "P2-e through the starter: head A refused at item15 and exiting at band 80, then head B (its own session, run-resumed) refused at item15 and exiting at band 90, abort with successor-aborted repeat-exit, the no-progress detail, and no head started"

# P2-f: one session in two spellings is one head (the fix's third review, 2026-10-09, finding 1).
# A head writes run-open with the eight-character id the status hook shows; the wrapper and an
# explicit `run-resume --session` carry the full id, which cmd_run_resume records as given. The
# session convention (fable-share.py's session_matches) takes an id and a prefix of it at least
# eight characters long for one session, and no_progress now reads sessions the same way: a head
# resumed in place, named short at one exit and full at the other, is one head, and its two
# refusals are no chain of heads. Short then full and full then short, each at 80/80, 80/90, 90/80
# and 90/90, must proceed, as must the review's own counterexample (run-open short, a refused gate
# and an exit at 80, head-resumed, run-resume full, a refused gate and an exit at 90), which also
# runs through the starter on a real record. Two distinct heads refused in turn must still stop:
# a short id beside another session's full id, two full ids, the short-then-full record with the
# full id of another session, and a shared prefix under eight characters (not the short id). The
# full ids are assembled from parts, so this file's own source carries no session-id literal (the
# pattern the ship-safe leg sweeps for).
SHORTSID=12345678
FULLSID="$SHORTSID-1234-1234-1234-123456789abc"
REXF=$("$PY" - "$H" "$SHORTSID" "$FULLSID" <<'REXFPY'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("h_rexf", sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
SHORT, FULL = sys.argv[2], sys.argv[3]
OTHER = "87654321" + FULL[len(SHORT):]   # another session's full id: no prefix shared with FULL


def gate(item, decision):
    return {"event": "gate", "item": item, "decision": decision, "metered": True,
            "fit": decision == "allow"}


def exit_at(band):
    return {"event": "head-exit", "band": band, "pack": True}


def resumed(opened, named, first_band, second_band):
    # one head resumed in place: run-open as `opened`, refused at item15, exit; head-resumed (the
    # supervisor's event, which names no new session); run-resume as `named`, refused again, exit
    refused = gate("item15", "refuse")
    return [{"event": "run-open", "session": opened}, refused, exit_at(first_band),
            {"event": "head-resumed", "session_id": opened, "pid": 1, "resume_n": 1},
            {"event": "run-resume", "session": named}, refused, exit_at(second_band)]


def two_heads(first, second):
    # two heads in turn: head A opens as `first`, head B starts and run-resumes as `second`; each
    # is refused at item15 and exits, at 80 and then 90
    refused = gate("item15", "refuse")
    return [{"event": "run-open", "session": first}, refused, exit_at(80),
            {"event": "head-successor", "session_id": second, "pid": 1, "budget": 1.0},
            {"event": "run-resume", "session": second}, refused, exit_at(90)]


def answer(evs):
    hi = max(i for i, e in enumerate(evs) if e.get("event") == "head-exit")
    reason, detail = h.start_guards(evs, hi)
    return "%s%s" % (reason, " no-progress" if detail and "no progress" in detail else "")


# the review's counterexample, event for event
REVIEW = [{"event": "run-open", "session": SHORT}, gate("item15", "refuse"), exit_at(80),
          {"event": "head-resumed", "session_id": SHORT, "pid": 1},
          {"event": "run-resume", "session": FULL}, gate("item15", "refuse"), exit_at(90)]
cases = [("SF%d%d" % (a, b), resumed(SHORT, FULL, a, b)) for a in (80, 90) for b in (80, 90)]
cases += [("FS%d%d" % (a, b), resumed(FULL, SHORT, a, b)) for a in (80, 90) for b in (80, 90)]
cases += [
    ("REVIEW", REVIEW),
    ("DISTINCT", two_heads(SHORT, OTHER)),
    ("DISTINCTFULL", two_heads(FULL, OTHER)),
    ("SFOTHER", resumed(SHORT, OTHER, 80, 90)),
    ("UNDER8", two_heads(SHORT[:7], FULL)),
]
for name, evs in cases:
    print("%s %s" % (name, answer(evs)))
REXFPY
)
rexf() { printf '%s\n' "$REXF" | grep "^$1 " | cut -d' ' -f2-; }
for c in SF8080 SF8090 SF9080 SF9090; do
  need_eq "$(rexf "$c")" "None" "$c: one session, run-open short then run-resume full"
done
for c in FS8080 FS8090 FS9080 FS9090; do
  need_eq "$(rexf "$c")" "None" "$c: one session, run-open full then run-resume short"
done
need_eq "$(rexf REVIEW)" "None" "the review's counterexample"
need_eq "$(rexf DISTINCT)" "repeat-exit no-progress" "control: head A by its short id, head B by another session's full id"
need_eq "$(rexf DISTINCTFULL)" "repeat-exit no-progress" "control: two heads by two different full ids"
need_eq "$(rexf SFOTHER)" "repeat-exit no-progress" "control: the short-then-full record with the full id of another session"
need_eq "$(rexf UNDER8)" "repeat-exit no-progress" "control: a shared prefix of seven characters is not the short id"
need_eq "$(printf '%s\n' "$REXF" | grep -c .)" "13" "every case answered"
# The review's counterexample through the starter: the record on disk, the stub head as P2-c's.
HO="$WORK/handoffs/rrexsid-handoff.md"
REC="$STORE/spawn-records/rrexsid.jsonl"
rm -f "$REC"
mk handoff "$HO" >/dev/null
mk record "$REC" rrexsid "$SHORTSID" "$HO" 200 >/dev/null
mk append "$REC" '{"event":"gate","item":"item15","decision":"refuse","metered":true,"fit":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"420,000 tokens (42 %)","pack":true}' >/dev/null
mk append "$REC" '{"event":"head-resumed","session_id":"'"$SHORTSID"'","pid":1,"context":90000,"waited_s":1,"reset_source":"x","resume_n":1}' >/dev/null
mk append "$REC" '{"event":"run-resume","session":"'"$FULLSID"'","head":"fixture head","detail":"item15"}' >/dev/null
mk append "$REC" '{"event":"gate","item":"item15","decision":"refuse","metered":true,"fit":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":90,"context":"430,000 tokens (43 %)","pack":true}' >/dev/null
need_eq "$(mk field "$REC" run-open session)" "$SHORTSID" "control: run-open names the short id"
need_eq "$(mk field "$REC" run-resume session)" "$FULLSID" "control: run-resume names the full id"
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rrexsid --handoff "$HO" --budget 3.50 --out "$WORK/starter/rrexsid-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" successor-aborted)" "0" "successor-aborted events"
need_absent "repeat-exit"
need_file "$WORK/stub-rrexsid.stdin.1"
verdict "P2-f (the fix's third review, 2026-10-09, finding 1, must not fire): one session written short then full and full then short, across 80/80, 80/90, 90/80 and 90/90, is one head and no repeat-exit; the review's counterexample (run-open short, refused at item15, exit at 80, head-resumed, run-resume full, refused at item15, exit at 90) proceeds, and through the starter on a real record starts its head (no successor-aborted); two distinct heads refused in turn still stop with the no-progress detail (a short id beside another session's full id, two full ids, the short-then-full record with another session's full id, a seven-character shared prefix)"

# ------------------------------------------------------------------------- wait-reset ------
fixture rwait 200
# +5 s against a 2 s block bound: the call must give the window back, not the reset.
T0=$(date +%s)
run wait-reset --run rwait --reset-at "+5s" --max-block-s 2 --lane B9
T1=$(date +%s)
need_rc 8
need_out "still-running"
need_eq "$(mk field "$REC" stop-condition which)" "limit" "stop-condition"
if [ "$((T1 - T0))" -gt 4 ]; then why="$why; the call blocked $((T1 - T0)) s past its 2 s bound"; fi
verdict "wait-reset: --reset-at +5s under a 2 s block bound returns still-running (exit 8)"

fixture rwait2 200
run wait-reset --run rwait2 --stop-text "You've hit your session limit · resets 3:50am (Europe/London)" \
    --dry-run
need_rc 0
need_out "stop text 'resets 3:50am'"
need_out "wait-reset: dry run"
need_eq "$(mk count "$REC" stop-condition)" "0" "stop-condition events"
verdict "wait-reset: the am/pm reset time is parsed out of the stop text"

fixture rwait3 200
run wait-reset --run rwait3 --stop-text "limit reached; the window resets at 2030-01-02T03:04:05+0100" \
    --dry-run
need_rc 0
need_out "stop text ISO 2030-01-02T03:04:05+0100"
verdict "wait-reset: an ISO reset time in the stop text is parsed"

# A reset time of day across a clock change (Europe/London, 25 October 2026, a 25-hour day):
# next_clock builds each day's candidate from that day's date, never today's plus 86,400 s.
# Must hold: Saturday 23:00 BST waiting for 03:00 lands on Sunday 03:00 GMT, not 02:00; Sunday
# 23:30 GMT waiting for 00:30 lands on Monday 00:30 GMT, never at or before now; the repeated hour
# (01:30 on the change night) takes its later instant; an ordinary day is unchanged.
why=""
NC_OUT=$(TZ=Europe/London "$PY" -B - "$H" 2>&1 <<'NCPY'
import ast, sys, time
src = open(sys.argv[1]).read()
fn = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "next_clock"][0]
ns = {"time": time}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "next_clock", "exec"), ns)
nc = ns["next_clock"]
def ts(y, mo, d, h, mi, dst):
    return time.mktime((y, mo, d, h, mi, 0, 0, 0, dst))
cases = [
    ("sat-2300-to-0300", ts(2026, 10, 24, 23, 0, 1), 3, 0, "2026-10-25 03:00 GMT"),
    ("sun-2330-to-0030", ts(2026, 10, 25, 23, 30, 0), 0, 30, "2026-10-26 00:30 GMT"),
    ("repeated-hour", ts(2026, 10, 25, 0, 30, 1), 1, 30, "2026-10-25 01:30 GMT"),
    ("ordinary-day", ts(2026, 10, 23, 13, 0, 1), 9, 0, "2026-10-24 09:00 BST"),
]
for name, now, h, m, want in cases:
    got = time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(nc(h, m, now)))
    print("%s %s" % (name, "ok" if got == want else "got %s, wanted %s" % (got, want)))
NCPY
)
for c in sat-2300-to-0300 sun-2330-to-0030 repeated-hour ordinary-day; do
  grep -q -- "^$c ok$" <<<"$NC_OUT" || why="$why; $c: $(grep -- "^$c" <<<"$NC_OUT" | head -1)"
done
verdict "next_clock: a reset time of day across the 25 October 2026 clock change lands on the right instant (Saturday's 03:00 at 03:00 GMT, Sunday night's 00:30 on Monday, the repeated hour at its later instant, an ordinary day unchanged)"

# The probe is opt-in and off by default (owner ruling 2026-09-06): with no reset time to sleep
# to and no --probe, the wait is not entered at all — the stop condition is recorded and the
# hand-off is the recovery. The planted input is a stop text naming no time.
fixture rwait4 200
run wait-reset --run rwait4 --stop-text "the window is closed, and no time is given"
need_rc 7
need_out "no reset time could be parsed and --probe was not passed"
need_out "the hand-off is the recovery"
need_absent "PROBE FAILED"
need_eq "$(mk count "$REC" stop-condition)" "1" "stop-condition events"
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
need_eq "$(mk field "$REC" stop-condition note)" "the window is closed, and no time is given" "the stop text"
verdict "wait-reset: no reset time and no --probe records stop-condition limit-unparsed and ends with the hand-off as the recovery (exit 7)"

# A limit scoped to ONE model states no reset time and cannot be waited out, so it is its own
# stop condition. Must fire: the harness's own model-limit text. Must not fire: the account-wide
# texts of the leg above and the leg below, which keep limit-unparsed and the ordinary wait.
fixture rwaitmodel 200
run wait-reset --run rwaitmodel --stop-text "You've reached your Fable limit. Switch to another model, or manage usage credits at claude.ai/settings/usage?from=cc_cli_limit_message, to continue."
need_rc 7
need_out "the Fable limit is exhausted"
need_out "the hand-off is the recovery"
need_absent "no reset time could be parsed"
need_eq "$(mk count "$REC" stop-condition)" "1" "stop-condition events"
need_eq "$(mk field "$REC" stop-condition which)" "limit-model" "which"
need_eq "$(mk field "$REC" stop-condition model)" "Fable" "the scope on the event"
verdict "wait-reset: a model-scoped limit records limit-model with the scope named, never limit-unparsed"

fixture rwaitmodel2 200
run wait-reset --run rwaitmodel2 --stop-text "You have reached your usage limit for this session; it resets at 9am." --dry-run
need_rc 0
need_absent "limit-model"
need_out "stop text"
verdict "wait-reset: control — an account-wide limit naming a reset time never takes the model-scoped branch"

fixture rwaitmodel3 200
run wait-reset --run rwaitmodel3 --stop-text "You have reached your weekly limit."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — an account-wide scope word (weekly) is never read as a model"

fixture rwaitmodel4 200
run wait-reset --run rwaitmodel4 --stop-text "You have reached your spending limit."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — an account word matched by stem (spending) is never read as a model (review 2026-09-14 finding 3)"

fixture rwaitmodel5 200
run wait-reset --run rwaitmodel5 --stop-text "You have reached your weekly limit. Switch to another model."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — an account scope word wins over the remedy sentence (review 2026-09-14 finding 3)"

fixture rwaitmodel6 200
run wait-reset --run rwaitmodel6 --stop-text "You have reached your 5-hour limit. Switch to another model."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — a period token (5-hour) is an account window, never a model, even with the remedy sentence (review 2026-09-14 finding 1)"

fixture rwaitmodel7 200
run wait-reset --run rwaitmodel7 --stop-text "You have reached your weekly usage limit. Switch to another model."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — a two-word account scope (weekly usage) is never a model (review 2026-09-14 finding 1)"

fixture rwaitmodel8 200
run wait-reset --run rwaitmodel8 --stop-text "You've hit your hourly limit. Switch to another model."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — an account scope after hit, not reached, is never a model (review 2026-09-14 finding 1)"

fixture rwaitmodel9 200
run wait-reset --run rwaitmodel9 --stop-text "You have reached your 5-hour rolling window limit. Switch to another model."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — an account scope anywhere in the limit sentence (5-hour rolling window) is never a model (review 2026-09-14 residual 1)"

fixture rwaitmodel10 200
run wait-reset --run rwaitmodel10 --stop-text "You have reached your weekly fair use limit. Switch to another model."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — a three-word account scope (weekly fair use) is never a model (review 2026-09-14 residual 1)"

fixture rwaitmodel11 200
run wait-reset --run rwaitmodel11 --stop-text "You've hit your account-wide limit. Switch to another model."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "which"
verdict "wait-reset: control — a hyphenated account compound (account-wide) is never a model (review 2026-09-14 residual 1)"

fixture rwait5 200
run wait-reset --run rwait5 --probe --dry-run
need_rc 0
need_out "probe every 900 s under the same login"
need_absent "PROBE FAILED"
verdict "wait-reset: --probe without --config-dir is accepted under the single account (D28)"

# The help text says the probe is opt-in, and the phrase the owner ruling forbids is absent.
run wait-reset --help
need_rc 0
need_out "OFF by default"
need_absent "auto-probe"
OPTIN=$(grep -c 'opt in to' "$WORK/both")
[ "$OPTIN" -ge 1 ] || why="$why; the help text never says the probe is opted in to ($OPTIN)"
verdict "wait-reset --help: the probe is named as opt-in and off by default (control: the count of 'opt in to' is $OPTIN)"

# ------------------------------------------------------------------------------ close ------
fixture rclose 200
mk append "$REC" '{"event":"lane-open","lane":"L1"}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L2"}' >/dev/null
mk append "$REC" '{"event":"decision","phase":"2","what":"one","grant":"owner"}' >/dev/null
mk append "$REC" '{"event":"decision","phase":"2","what":"two","grant":"owner"}' >/dev/null
mk append "$REC" '{"event":"gate","item":"a","context":100000,"percent":10,"band":0,"armed":false,"decision":"allow","metered":true}' >/dev/null
mk append "$REC" '{"event":"gate","item":"b","context":300000,"percent":30,"band":0,"armed":false,"decision":"allow","metered":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run close --run rclose --meter-line "$METER" --items "9 of 9" --register "one entry" \
    --log "one line" --lint "clean" --parity "not yet"
need_rc 0
need_out "lanes 2 · decisions 2 · gates 2"
need_eq "$(mk field "$REC" run-close lanes)" "2" "lanes"
need_eq "$(mk field "$REC" run-close decisions_on_owner_behalf)" "2" "decisions"
need_eq "$(mk field "$REC" run-close reason_tally)" "(a)×1 (b)×0 (c)×0 (d)×0, none×0" "tally"
case $(mk field "$REC" run-close head_context_per_item) in
  *'"delta": 200000'*) : ;;
  *) why="$why; the per-item context deltas are missing" ;;
esac
case $(mk field "$REC" run-close trace) in
  "1 rows under '## Trace'"*) : ;;
  *) why="$why; the trace count is not the first table's row count" ;;
esac
# The run figure at the close (register entries 2026-09-14): its own fields on the run-close
# event and the spend bullet's `run …` after the session line and the envelope; the two lanes
# opened here without a session id or a close make it a floor, named.
need_eq "$(mk bullet "$HO" "Spend against the envelope")" \
        "$METER · envelope \$200.0 · run at least \$12.34 of \$200.00" "spend bullet"
need_eq "$(mk field "$REC" run-close run_spend_usd)" "12.34" "run_spend_usd on the run-close event"
need_eq "$(mk field "$REC" run-close run_spend_floor)" "true" "run_spend_floor on the run-close event"
need_out "run spend: at least \$12.34 of \$200.00, remainder at most \$187.66 · heads \$12.34 (1 metered) · lanes: none with a figure (2 on the record; 2 unmeasured) · unmetered: lane L1 (no close yet (still open); the record names no session id for the lane; no priced close); lane L2 ("
need_file "$STORE/spawn-records/rclose-heartbeat.stop"
verdict "close: run-close carries lanes, decisions, the tally, per-item context, the trace and the run figure (its fields, its line and the spend bullet); the heartbeat stop marker is written"

# ---------------------------------------------------------- close on the plain-lane-run shape
plain_fixture pclose
COMMITS_BEFORE=$(git -C "$VAULT" rev-list --count HEAD)
run close --run pclose --items "not applicable"
need_rc 0
need_out "plain lane run (no run-open)"
need_out "lanes 3 (completed 1 · error 1 · open 1)"
need_out "spend \$3.75"
need_out "no hand-off row, no commit, no push"
need_eq "$(mk field "$REC" run-close shape)" "plain-lane-run" "the shape field"
need_eq "$(mk field "$REC" run-close lanes)" "3" "lanes"
need_eq "$(mk field "$REC" run-close lanes_by_exit)" '{"completed": 1, "error": 1, "open": 1}' "lanes by exit class"
need_eq "$(mk field "$REC" run-close spend_usd)" "3.75" "spend summed from the lane-closed costs"
need_eq "$(mk field "$REC" run-close spend_src)" "sum of 2 lane-closed total_cost_usd" "the spend's source"
need_eq "$(mk field "$REC" run-close trace)" "<no key trace>" "no trace field (there is no hand-off)"
need_eq "$(mk field "$REC" run-close commit)" "<no key commit>" "no commit field"
need_eq "$(git -C "$VAULT" rev-list --count HEAD)" "$COMMITS_BEFORE" "commit count"
need_nofile "$STORE/spawn-records/pclose-heartbeat.stop"
need_nofile "$STORE/spawn-records/pclose-supervisor.stop"
verdict "close on a plain record: run-close carries shape plain-lane-run, the lanes by exit class and the lane-summed spend; no hand-off row, no commit, no meter, no markers (exit 0)"

# the clean control: a run-open record still closes as today, and its run-close carries NO shape
need_eq "$(mk field "$STORE/spawn-records/rclose.jsonl" run-close shape)" "<no key shape>" "the hands-off close carries no shape field"
need_eq "$(mk field "$STORE/spawn-records/rclose.jsonl" run-close lanes)" "2" "the hands-off close's lanes"
verdict "close: the hands-off close of the rclose leg is unchanged and carries no shape field, so the two shapes are told apart by the record"

plain_fixture pclose2
LINES_BEFORE=$(mk lines "$REC")
COMMITS_BEFORE=$(git -C "$VAULT" rev-list --count HEAD)
run close --run pclose2 --items "fixture items" --commit "fixture: a commit a plain run may not make"
need_rc 2
need_out "never commits and never pushes"
need_lines
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines (nothing written)"
need_eq "$(mk count "$REC" run-close)" "0" "run-close events"
need_eq "$(git -C "$VAULT" rev-list --count HEAD)" "$COMMITS_BEFORE" "commit count"
run close --run pclose2 --items "fixture items" --push
need_rc 2
need_out "never commits and never pushes"
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines after --push"
need_eq "$(mk count "$REC" run-close)" "0" "run-close events after --push"
verdict "close --commit and --push on a plain record: refused with the reason (exit 2), nothing written and nothing committed"

plain_fixture pclose3
LINES_BEFORE=$(mk lines "$REC")
run close --run pclose3 --dry-run
need_rc 0
need_out "close: dry run · plain lane run"
need_out '"shape": "plain-lane-run"'
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines (dry run writes nothing)"
verdict "close --dry-run on a plain record: the run-close it would write is printed and the record is untouched"

# ------------------------------------------------------------- grants file and pointer ----
mkdir -p "$WORK/real-grant"
ln -s "$WORK/real-grant" "$WORK/link-grant"
HO="$WORK/handoffs/rgrant-handoff.md"; mk handoff "$HO" >/dev/null
REC="$STORE/spawn-records/rgrant.jsonl"; rm -f "$REC"
GF="$REALSTORE/spawn-records/rgrant-grants.json"
run run-open --run rgrant --session sid-rgrant --head "h" --regime multi --regime-src owner \
    --handoff "$HO" --detail "grants" --pid 1 --envelope-usd 100 --grant "$WORK/link-grant" \
    --write "$WORK/link-grant/out"
need_rc 0
need_file "$GF"
need_eq "$(mk field "$REC" run-open grants_file)" "$GF" "grants_file on the event"
need_eq "$(cat "$STATE/run-sid-rgrant")" "rgrant" "the run-<sid> pointer"
REAL_GRANT=$("$PY" -c 'import os, sys; sys.stdout.write(os.path.realpath(sys.argv[1]))' "$WORK/link-grant")
"$PY" - "$GF" "$WORK/link-grant" "$REAL_GRANT" "$VAULT" "$STORE" "$STATE" "$PROJECTS" "$WORK/lane-home" <<'GRANTS' > "$WORK/grants-check.txt"
import json, os, sys
g = json.load(open(sys.argv[1]))
link, real, vault, store, state, projects, lane_home = sys.argv[2:9]
want = [link, real, os.path.realpath(vault), os.path.realpath(store), os.path.realpath(state),
        os.path.realpath(projects), os.path.realpath(lane_home), "/tmp"]
missing = [p for p in want if p not in g["grants"]]
wmissing = [p for p in (os.path.realpath(store), os.path.realpath(state), real + "/out", link + "/out") if p not in g["writes"]]
print("grants-missing %d writes-missing %d source %s run %s" % (len(missing), len(wmissing), g.get("source"), g.get("run")))
for p in missing + wmissing: print("missing " + p)
GRANTS
need_eq "$(head -1 "$WORK/grants-check.txt")" "grants-missing 0 writes-missing 0 source run-open run rgrant" "grants file content"
verdict "run-open: the grants file holds the given path in both spellings, the defaults (vault, store, state, projects, lane-home, /tmp), the writes; the pointer names the run"

rm -f "$GF"
run grants --run rgrant --add-grant "$WORK/link-grant" --add-write "$WORK/real-grant/more"
need_rc 0
need_file "$GF"
need_out "grants: $GF"
need_eq "$(mk field "$REC" grants grants_file)" "$GF" "grants event"
need_eq "$(cat "$STATE/run-sid-rgrant")" "rgrant" "the pointer after grants"
if ! grep -q "real-grant/more" "$GF"; then why="$why; the new write is not in the rewritten file"; fi
if ! grep -q "link-grant/out" "$GF"; then why="$why; the recorded write was lost (the record's lists are the baseline)"; fi
verdict "grants: a missing grants file is rewritten with the pointer (N7), the add forms merging into the record's lists (K64bc6c8c: a missing file restores nothing by itself)"

fixture rgrant2 200
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rgrant2 --session sid-second --head "h" --detail "d" --grants-file "$WORK/custom-grants.json"
need_rc 2
need_out "grants-file is retired"
need_out "$REALSTORE/spawn-records/rgrant2-grants.json"
need_lines
need_nofile "$WORK/custom-grants.json"
need_eq "$(mk count "$REC" run-resume)" "0" "no run-resume from the refusal"
GF2="$REALSTORE/spawn-records/rgrant2-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rgrant2 --session sid-second --head "h" --detail "d" --write "$WORK/real-grant/rgrant2"
need_rc 0
need_file "$GF2"
need_eq "$(mk field "$REC" run-resume grants_file)" "$GF2" "the default path"
need_eq "$(cat "$STATE/run-sid-second")" "rgrant2" "the pointer for the resumed session"
if ! grep -q '"source": "run-resume"' "$GF2"; then why="$why; source is not run-resume"; fi
verdict "run-resume: --grants-file is retired and refused naming the default path, nothing written (register 2026-09-06); an explicit --write writes the default path with source run-resume and the pointer"

fixture rkeep 200
GFK="$REALSTORE/spawn-records/rkeep-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run grants --run rkeep --write "$WORK/real-grant/keepme"
need_rc 0
need_file "$GFK"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rkeep --session sid-keep --head "h" --detail "no flags"
need_rc 0
need_out "grants $GFK (kept)"
need_eq "$(mk field "$REC" run-resume grants)" "kept" "grants kept on the event"
if ! grep -q "real-grant/keepme" "$GFK"; then why="$why; the seeded write was lost"; fi
if grep -q '"source": "run-resume"' "$GFK"; then why="$why; the file was rewritten"; fi
RKL=$(mk lines "$REC")
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rkeep --session sid-keep2 --head "h" --detail "explicit write" --write "$WORK/real-grant/other"
need_rc 2
need_out "would shrink the run's grants and passes no --replace"
need_eq "$(mk lines "$REC")" "$RKL" "the refused call wrote no event"
if ! grep -q "real-grant/keepme" "$GFK"; then why="$why; the refused call changed the file"; fi
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rkeep --session sid-keep2 --head "h" --detail "explicit write" --write "$WORK/real-grant/other" --replace
need_rc 0
need_absent "(kept)"
if grep -q "real-grant/keepme" "$GFK"; then why="$why; an explicit --write did not replace the file"; fi
if ! grep -q "real-grant/other" "$GFK"; then why="$why; the explicit write is absent"; fi
verdict "run-resume: with no --grant or --write an existing grants file is kept (register 2026-09-06); an explicit --write that drops a path is refused without --replace, nothing written, and with --replace rewrites the file (control, K64bc6c8c)"

fixture rwarn 200
mk transcript sid-rwarn 100000 >/dev/null
# The billed line in hand keeps the spend measured: this leg claims the warning, and two armed
# gates with an unmeterable spend would be two consecutive unmetered gates (2026-09-17).
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rwarn --to "item" --meter-line "$METER"
need_rc 0
need_out "warn: armed with no grants file at $REALSTORE/spawn-records/rwarn-grants.json: the head fence is fail-open"
RUNENV="AIMYTH_HANDSOFF=1 PATH=$WORK/psnone:$PATH"
run boundary --run rwarn --from 1 --to 2 --disposition d --waste w --next n --meter-line "$METER"
need_rc 0
need_out "warn: armed with no grants file"
run grants --run rwarn
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run rwarn --to "item two" --meter-line "$METER"
need_rc 0
need_absent "warn: armed"
verdict "gate and boundary: armed with no grants file warns (exit unchanged); the control after grants is silent"

# ---------------------------------------------------------------- the next-task pack ------
fixture rpack 200
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rpack --final --band 80 --meter-line "$METER"
need_rc 2
need_out "needs the next-task pack"
need_lines
need_eq "$(mk count "$REC" head-exit)" "0" "head-exit events"
verdict "handoff --final without the pack is refused (exit 2, nothing written)"

for MISSING in Next Needs Decided; do
  printf -- '- Next: item 4 (gate: 4)\n- Needs: wiki/a.md:1-9\n- Decided: D1 because x\n' | grep -v "$MISSING" > "$WORK/pack-$MISSING.md"
  RUNENV="PATH=$WORK/psnone:$PATH"
  run handoff --run rpack --final --band 80 --meter-line "$METER" --inflight-file "$WORK/pack-$MISSING.md"
  need_rc 2
  need_out "lacks $MISSING:"
  need_lines
done
need_eq "$(mk count "$REC" head-exit)" "0" "head-exit events after three refusals"
verdict "handoff --final: a pack lacking Next:, Needs: or Decided: is refused naming the label"

run handoff --run rpack --inflight "- Next: item 4
- Needs: wiki/a.md:1-9"
need_rc 0
need_out "warn: the in-flight pack lacks Decided:"
need_out "inflight rewritten"
verdict "handoff --inflight (not final): a missing label warns and writes"

printf -- '- Next: item 4 (gate: 4)\n- Needs: wiki/a.md:1-9\n- Decided: D1 because x\n' > "$WORK/pack-full.md"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rpack --final --band 80 --meter-line "$METER" --inflight-file "$WORK/pack-full.md"
need_rc 0
need_eq "$(mk field "$REC" head-exit pack)" "true" "pack"
need_eq "$(mk field "$REC" head-exit spent_usd)" "16.56" "spent_usd from the meter line (N5)"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rpack --final --band limit --meter-line "$METER" --inflight-file "$WORK/pack-full.md"
need_rc 0
need_eq "$(mk field "$REC" head-exit band)" "limit" "band limit accepted"
verdict "handoff --final: the full pack writes head-exit with pack true and spent_usd; band limit is accepted"

# ----------------------------------------------------------------- the pack-age guard -----
# The stamp handoff --inflight writes, and the guard that compares it with the record's last
# phase-boundary or head-exit. A head-exit carrying pack true is not the anchor: handoff --final
# writes the pack and that exit in one call, so the pack cannot be older than it.
fixture rage 200
mk append "$REC" '{"event":"phase-boundary","ts":"2020-01-02T03:04:05+0100","from":"1","to":"2","next":"item 5: older than the pack"}' >/dev/null
run handoff --run rage --inflight "- Next: item 5 (gate: 5)
- Needs: wiki/b.md:1-4
- Decided: D2 because y"
need_rc 0
case $(mk section "$HO" "In flight") in
  "- pack written: 20"*) : ;;
  *) why="$why; no pack-written stamp on the section: $(mk section "$HO" "In flight")" ;;
esac
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rage --handoff "$HO" --budget 3.50 --out "$WORK/starter/rage-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_out "pack: fresh"
need_absent "re-derived"
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations"
case $(mk section "$HO" "In flight") in
  *"item 5 (gate: 5)"*) : ;;
  *) why="$why; the fresh pack was rewritten: $(mk section "$HO" "In flight")" ;;
esac
verdict "the pack-age guard: handoff --inflight stamps the pack, and a pack newer than the last boundary is accepted unchanged by the starter"

# The planted stale case: a phase-boundary, a decision and a lane opened AFTER the pack was
# written, so the record knows more than the pack does.
fixture rage2 200
mk append "$REC" '{"event":"lane-open","lane":"B7","class":"builder","model":"opus","reason":"opened before the boundary"}' >/dev/null
run handoff --run rage2 --inflight "- Next: the stale item
- Needs: wiki/c.md:1-2
- Decided: D3 because z"
need_rc 0
mk append "$REC" '{"event":"phase-boundary","ts":"2030-01-02T03:04:05+0100","from":"2","to":"3","next":"item 9: the record knows better"}' >/dev/null
mk append "$REC" '{"event":"decision","ts":"2030-01-02T04:00:00+0100","phase":"3","what":"ship the guard","grant":"owner"}' >/dev/null
mk append "$REC" '{"event":"lane-open","ts":"2030-01-02T04:05:00+0100","lane":"B8","class":"verifier","model":"sonnet","reason":"open since the boundary"}' >/dev/null
mk append "$REC" '{"event":"head-exit","ts":"2030-01-02T04:10:00+0100","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rage2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rage2-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_out "pack: STALE"
need_out "re-derived from the record"
G=$(grep -c 'stale-pack' "$REC"); [ "$G" -ge 1 ] || why="$why; no stale-pack observation ($G)"
SEC=$(mk section "$HO" "In flight")
case $SEC in *"pack re-derived from the record at "*) : ;; *) why="$why; no re-derivation header: $SEC" ;; esac
case $SEC in *"item 9: the record knows better"*) : ;; *) why="$why; the boundary's next is missing" ;; esac
case $SEC in *"lane B8 open since"*) : ;; *) why="$why; the lane open since the boundary is missing" ;; esac
case $SEC in *"ship the guard"*) : ;; *) why="$why; the decision since the boundary is missing" ;; esac
case $SEC in *"the stale item"*) why="$why; the stale pack survived the re-derivation" ;; *) : ;; esac
case $SEC in *"lane B7 open since"*) : ;; *) why="$why; a lane opened before the boundary and never closed is missing from the re-derived pack (K615a63df: open lanes over the whole record)" ;; esac
verdict "the pack-age guard: a pack older than the last phase-boundary is STALE, and the starter re-derives the in-flight section from the record before the successor starts (observation stale-pack), every lane still open listed, the one opened before the boundary included (K615a63df)"

# No boundary at all: nothing for the pack to be older than.
fixture rage3 200
run handoff --run rage3 --inflight "- Next: the first item
- Needs: wiki/d.md:1
- Decided: D4 because w"
need_rc 0
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rage3 --session sid-noboundary --head "h" --detail "no boundary yet"
need_rc 0
need_absent "stale"
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations"
verdict "the pack-age guard: a record with no phase-boundary and no head-exit leaves the pack fresh by definition (run-resume is silent)"

# The same command over a pack older than a head-exit: one warning line, nothing rewritten.
fixture rage4 200
run handoff --run rage4 --inflight "- Next: written before the exit
- Needs: wiki/e.md:2
- Decided: D5 because v"
need_rc 0
# The head acted after its pack (a gate in 2030) and a `pack: false` head-exit was then written
# for it: the guard keys on the head's last activity, never on that head-exit's own timestamp
# (register 2026-09-12 21:2x), and the pack predates the activity.
mk append "$REC" '{"event":"gate","ts":"2030-01-02T03:04:00+0100","item":"item 9","context":null,"percent":null,"band":"unmetered","armed":false,"decision":"allow","metered":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","ts":"2030-01-02T03:04:05+0100","band":80,"context":"c","spent_usd":5,"pack":false}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rage4 --session sid-stalepack --head "h" --detail "resumed onto a stale pack"
need_rc 0
need_out "in-flight pack is stale"
need_eq "$(grep -c 'in-flight pack is stale' "$WORK/both")" "1" "warning lines"
need_eq "$(mk field "$REC" observation what)" "stale-pack" "the observation"
case $(mk section "$HO" "In flight") in
  *"written before the exit"*) : ;;
  *) why="$why; run-resume rewrote the pack, which is the starter's job" ;;
esac
verdict "run-resume: a pack older than the last head-exit warns once and records observation stale-pack, rewriting nothing (control: the no-boundary leg above is silent)"

# The derivation as a command, and its shape: header, next, open lanes, decisions.
fixture rage5 200
mk append "$REC" '{"event":"phase-boundary","ts":"2026-01-02T03:04:05+0100","from":"3","to":"4","next":"item 7: the derived next"}' >/dev/null
mk append "$REC" '{"event":"lane-open","ts":"2026-01-02T04:00:00+0100","lane":"B9","class":"builder","model":"opus","reason":"still open"}' >/dev/null
mk append "$REC" '{"event":"lane-open","ts":"2026-01-02T04:01:00+0100","lane":"B10","class":"verifier","model":"sonnet","reason":"closed again"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","ts":"2026-01-02T04:02:00+0100","lane":"B10","exit_class":"completed"}' >/dev/null
mk append "$REC" '{"event":"decision","ts":"2026-01-02T04:03:00+0100","phase":"4","what":"the derived decision","grant":"owner"}' >/dev/null
run handoff --run rage5 --inflight-from-record --dry-run
need_rc 0
need_out "pack re-derived from the record at"
need_out "Next: item 7: the derived next"
need_out "Needs: lane B9 open since"
need_out "class builder"
need_out "Decided: the derived decision"
need_absent "lane B10"
need_eq "$(mk section "$HO" "In flight")" "- nothing in flight." "the dry run wrote nothing"
verdict "handoff --inflight-from-record --dry-run: the header, the boundary's next, the open lane with its spawn line and the decision are printed; the lane closed again is absent and nothing is written"

run handoff --run rage5 --inflight-from-record
need_rc 0
need_out "inflight rewritten"
case $(mk section "$HO" "In flight") in
  "- pack re-derived from the record at "*) : ;;
  *) why="$why; the written section does not open with the re-derivation header" ;;
esac
need_eq "$(mk count "$REC" observation)" "0" "observations recorded by the subcommand"
run handoff --run rage5 --inflight-from-record --inflight "a second source"
need_rc 2
need_out "two sources for one section"
need_lines
verdict "handoff --inflight-from-record: writes the derived pack and records nothing; with --inflight as well it is refused (exit 2)"

# The pack handed in as a file, and the stamp's replacement: an earlier stamp is dropped, so the
# section carries exactly one age and it is the age of this write.
fixture rage6 200
cat > "$WORK/pack6.md" <<'PACK6'
- pack written: 2020-01-02T03:04:05+0100
- Next: item 6 handed in by file
- Needs: wiki/f.md:1
- Decided: D6 because u
PACK6
run handoff --run rage6 --inflight-file "$WORK/pack6.md"
need_rc 0
SEC=$(mk section "$HO" "In flight")
case $SEC in "- pack written: 20"*) : ;; *) why="$why; the pack from the file was not stamped: $SEC" ;; esac
need_eq "$(printf '%s\n' "$SEC" | grep -c 'pack written:')" "1" "stamp lines on the section"
case $SEC in *"2020-01-02T03:04:05"*) why="$why; the file's earlier stamp survived the write" ;; *) : ;; esac
case $SEC in *"item 6 handed in by file"*) : ;; *) why="$why; the file's pack body is missing: $SEC" ;; esac
verdict "handoff --inflight-file: the pack is stamped with the time of this write, and the earlier stamp planted in the file is replaced rather than doubled"

# The head writing its own pack over a re-derived one: the guard's header carries the age, so it
# is dropped by the same rule, and one fresh stamp replaces it.
run handoff --run rage6 --inflight "- pack re-derived from the record at 2020-03-04T05:06:07+0100 (the head's pack was stale)
- Next: the head's own pack over a derived one
- Needs: wiki/g.md:2
- Decided: D7 because t"
need_rc 0
SEC=$(mk section "$HO" "In flight")
case $SEC in "- pack written: 20"*) : ;; *) why="$why; the head's own pack was not stamped: $SEC" ;; esac
need_eq "$(printf '%s\n' "$SEC" | grep -c 'pack re-derived from the record')" "0" "re-derivation headers left"
need_eq "$(printf '%s\n' "$SEC" | grep -c 'pack written:')" "1" "stamp lines on the section"
case $SEC in *"the head's own pack over a derived one"*) : ;; *) why="$why; the pack body is missing: $SEC" ;; esac
verdict "handoff --inflight over a re-derived pack: the planted 2020 re-derivation header is dropped and one fresh stamp replaces it"

# A pack written before this guard existed, or by hand: no stamp, so no age. The guard leaves it
# alone rather than re-deriving over the head's own judgement, and says which.
fixture rage7 200
run handoff --run rage7 --set "inflight=- Next: the hand-written pack
- Needs: wiki/h.md:3
- Decided: D8 because s"
need_rc 0
mk append "$REC" '{"event":"phase-boundary","ts":"2030-01-02T03:04:05+0100","from":"4","to":"5","next":"item 11: later than any stamp"}' >/dev/null
mk append "$REC" '{"event":"head-exit","ts":"2030-01-02T03:05:00+0100","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rage7 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rage7-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_out "pack: unstamped"
need_out "carries no"
need_absent "re-derived"
need_out "head-successor"
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations"
case $(mk section "$HO" "In flight") in
  *"the hand-written pack"*) : ;;
  *) why="$why; the unstamped pack was rewritten" ;;
esac
verdict "the pack-age guard: an unstamped pack (planted with --set, against a 2030 boundary) is left alone and the successor still starts (control: the same 2030 boundary re-derived a stamped pack two legs above)"

# The comparison's edge, both sides planted with --set, which writes no stamp of its own.
fixture rage8 200
mk append "$REC" '{"event":"phase-boundary","ts":"2030-01-02T03:04:05+0100","from":"5","to":"6","next":"item 12: the edge"}' >/dev/null
run handoff --run rage8 --set "inflight=- pack written: 2030-01-02T03:04:05+0100
- Next: stamped at the boundary
- Needs: wiki/i.md:4
- Decided: D9 because r"
need_rc 0
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rage8 --session sid-edge-equal --head "h" --detail "stamped at the boundary"
need_rc 0
need_absent "in-flight pack is stale"
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations at the edge"
run handoff --run rage8 --set "inflight=- pack written: 2030-01-02T03:04:04+0100
- Next: stamped one second before the boundary
- Needs: wiki/i.md:4
- Decided: D9 because r"
need_rc 0
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rage8 --session sid-edge-before --head "h" --detail "stamped a second early"
need_rc 0
need_out "in-flight pack is stale"
need_eq "$(grep -c 'stale-pack' "$REC")" "1" "stale-pack observations one second earlier"
verdict "the pack-age guard's edge: a pack stamped at the boundary's own timestamp is fresh, and the same pack stamped one second earlier is stale (the control on the same fixture)"

# The head-exit `handoff --final` writes carries the pack, so it is not the anchor; the exit the
# supervisor writes for a head that wrote none is.
fixture rage9 200
run handoff --run rage9 --inflight "- Next: written with the final hand-off
- Needs: wiki/j.md:5
- Decided: D10 because q"
need_rc 0
mk append "$REC" '{"event":"head-exit","ts":"2030-01-02T03:04:05+0100","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rage9 --session sid-packtrue --head "h" --detail "after a final hand-off"
need_rc 0
need_absent "in-flight pack is stale"
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations after a pack-true exit"
# The new head (sid-packtrue) acted in 2030 before this pack-false exit: the guard keys on that last
# activity, not on the exit's own timestamp (register 2026-09-12 21:2x), so a same-second tie
# between the pack's stamp and the new head's start cannot decide the leg.
mk append "$REC" '{"event":"gate","ts":"2030-01-02T03:04:06+0100","item":"item 10","context":null,"percent":null,"band":"unmetered","armed":false,"decision":"allow","metered":false}' >/dev/null
mk append "$REC" '{"event":"head-exit","ts":"2030-01-02T03:04:06+0100","band":80,"context":"c","spent_usd":5,"pack":false}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rage9 --session sid-packfalse --head "h" --detail "after an exit with no pack"
need_rc 0
need_out "in-flight pack is stale"
need_eq "$(grep -c 'stale-pack' "$REC")" "1" "stale-pack observations after a pack-false exit"
verdict "the pack-age guard: a head-exit carrying pack true is skipped as the anchor (a 2030 exit leaves a 2026 pack fresh), and a pack-false exit after the new head's 2030 activity makes it stale (the control on the same fixture; register 2026-09-12 21:2x)"

# An anchor whose timestamp this script cannot parse: unmeasured, not stale — a comparison that
# cannot be made is not evidence of age.
fixture rageA 200
run handoff --run rageA --inflight "- Next: against an unparsable boundary
- Needs: wiki/k.md:6
- Decided: D11 because p"
need_rc 0
mk append "$REC" '{"event":"phase-boundary","ts":"the third of never","from":"6","to":"7","next":"item 13: unparsable"}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rageA --session sid-unmeasured --head "h" --detail "an unparsable boundary"
need_rc 0
need_absent "in-flight pack is stale"
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations against an unparsable anchor"
mk append "$REC" '{"event":"phase-boundary","ts":"2030-01-02T03:04:05+0100","from":"7","to":"8","next":"item 14: parsable again"}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rageA --session sid-measured --head "h" --detail "a parsable boundary"
need_rc 0
need_out "in-flight pack is stale"
verdict "the pack-age guard: a boundary whose timestamp does not parse leaves the pack unmeasured rather than stale, and a parsable later boundary on the same fixture is the control"

# A hand-off with no '## In flight' section at all: nothing to age, nothing re-derived, and the
# start is not blocked by the guard.
fixture rageB 200 inflight
mk append "$REC" '{"event":"phase-boundary","ts":"2030-01-02T03:04:05+0100","from":"8","to":"9","next":"item 15: no section to compare"}' >/dev/null
mk append "$REC" '{"event":"head-exit","ts":"2030-01-02T03:05:00+0100","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rageB --handoff "$HO" --budget 3.50 --out "$WORK/starter/rageB-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_out "no '## In flight' section"
need_absent "re-derived"
need_out "head-successor"
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations with no section"
verdict "the pack-age guard: a hand-off with no '## In flight' section (the section dropped from the fixture) is reported and left alone, and the successor still starts"

# The derived pack against the D41 label gate: what the guard writes must pass the check a head's
# own pack must pass, or a re-derivation would leave a hand-off --final would refuse.
fixture rageC 200
mk append "$REC" '{"event":"phase-boundary","ts":"2026-01-02T03:04:05+0100","from":"9","to":"10","next":"item 16: the final derived next"}' >/dev/null
mk append "$REC" '{"event":"lane-open","ts":"2026-01-02T04:00:00+0100","lane":"B11","class":"builder","model":"opus","reason":"open at the final"}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rageC --inflight-from-record --final --band 80 --meter-line "$METER"
need_rc 0
need_out "head-exit recorded"
need_eq "$(mk field "$REC" head-exit pack)" "true" "the head-exit's pack flag"
case $(mk section "$HO" "In flight") in
  "- pack re-derived from the record at "*) : ;;
  *) why="$why; the final hand-off does not carry the derived pack" ;;
esac
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rageC --final --band 80 --meter-line "$METER" --inflight "- Next: one label only"
need_rc 2
need_out "the next-task pack lacks"
need_lines
verdict "handoff --inflight-from-record --final: the derived pack passes the same D41 label gate a head's own pack must pass, and a one-label pack on the same fixture is still refused (exit 2)"

# The supervisor's own successor start, not the starter's: the head it launched stops at a limit
# above the first edge, the supervisor writes the head-exit the head owed (pack false) and starts
# a successor — and that pack, fresh when the run began, is older than the exit just written.
fixture rageD 200
arm_resume rageD
mk append "$REC" '{"event":"head-exit","ts":"2020-01-02T03:04:05+0100","band":80,"context":"c","spent_usd":5,"pack":false}' >/dev/null
run handoff --run rageD --inflight "- Next: fresh when the first head started
- Needs: wiki/l.md:7
- Decided: D12 because o"
need_rc 0
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=170000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rageD --handoff "$HO" --budget 3.50 --out "$WORK/starter/rageD-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_out "pack: fresh"
need_out "pack: STALE"
need_out "re-derived from the record"
S=$(mk count "$REC" head-successor); [ "$S" -ge 2 ] || why="$why; head-successor events $S, wanted 2 or more"
G=$(grep -c 'stale-pack' "$REC"); [ "$G" -ge 1 ] || why="$why; no stale-pack observation from the supervisor's successor start ($G)"
SEC=$(mk section "$HO" "In flight")
case $SEC in "- pack re-derived from the record at "*) : ;; *) why="$why; no re-derivation header after the supervisor's start: $SEC" ;; esac
case $SEC in *"- Next: fresh when the first head started (from the head's own pack written "*) : ;; *) why="$why; the head's own Next, newer than any boundary, is not carried with its source (K615a63df): $SEC" ;; esac
case $SEC in *"newer than any phase-boundary (the record carries none)"*) : ;; *) why="$why; the derivation does not say the record holds no boundary: $SEC" ;; esac
verdict "the pack-age guard on the supervisor's own successor path: the first start reports the pack fresh, the head-exit the supervisor writes for a limit stop makes it stale, and the second start re-derives the section before briefing the successor, the head's own Next carried with its source since no boundary is newer (K615a63df)"

# ------------------------------------------------------------------ orientation (D41) -----
fixture rorient 200
mk transcript sid-rorient 100000 60000 >/dev/null
run gate --run rorient --to "item one"
need_rc 0
need_out "orientation 40,000"
need_eq "$(mk field "$REC" gate orientation_tokens)" "40000" "orientation_tokens"
run gate --run rorient --to "item two"
need_rc 0
need_absent "orientation"
need_eq "$(mk field "$REC" gate orientation_tokens)" "<no key orientation_tokens>" "no orientation on a later gate"
verdict "gate: the first gate of a session records orientation_tokens = context minus the first-call context; later gates do not"

# INV-3 (register 2026-10-30 21:40 b): a helper's reference copy that fell behind its source. The
# planted cases are a stale rule file and a stale decisions file; the controls are an equal copy
# and one with no source, which both stay quiet, and a run with no refs folder.
fixture rrefs 200
mkdir -p "$STORE/stages/rrefs/refs"
printf 'the rule as it stands\n' > "$VAULT/INV3-RULES.md"
printf 'the older rule\n' > "$STORE/stages/rrefs/refs/INV3-RULES.md"
printf 'the same text\n' > "$VAULT/INV3-SAME.md"
cp "$VAULT/INV3-SAME.md" "$STORE/stages/rrefs/refs/INV3-SAME.md"
printf 'no source for this\n' > "$STORE/stages/rrefs/refs/inv3-orphan.md"
printf 'a newer ruling\n' > "$WORK/inv3-decisions.md"
printf 'an older ruling\n' > "$STORE/stages/rrefs/refs/inv3-decisions.md"
run gate --run rrefs --to "item one" --decisions-file "$WORK/inv3-decisions.md" \
    --ack "the newer ruling read" --ack-digest "$(sha_file "$WORK/inv3-decisions.md")"
need_out "gate: warn: the staged reference copy .*refs/INV3-RULES.md differs from its source"
need_out "gate: warn: the staged reference copy .*refs/inv3-decisions.md differs from its source"
need_absent "INV3-SAME"
need_absent "inv3-orphan"
need_eq "$(mk count "$REC" gate)" "1" "a warning, and the gate still written"
rm -f "$VAULT/INV3-RULES.md" "$VAULT/INV3-SAME.md"
fixture rrefs2 200
run gate --run rrefs2 --to "item one"
need_absent "staged reference copy"
verdict "INV-3 (fails on old): the gate warns of each staged reference copy that differs from its source, the rule file and the decisions file alike, while an equal copy, one with no source and a run with no refs folder stay quiet"

# INV-3, the review's F2: a run stage keeps its decisions file beside refs/, and a gate that names no
# file must still compare them. The planted case is a stale copy of that file with no flag given;
# the control is the same pair made equal, which stays quiet.
fixture rrefs3 200
mkdir -p "$STORE/stages/rrefs3/refs"
printf 'a newer ruling\n' > "$STORE/stages/rrefs3/decisions.md"
printf 'an older ruling\n' > "$STORE/stages/rrefs3/refs/decisions.md"
run gate --run rrefs3 --to "item one"
need_out "gate: warn: the staged reference copy .*rrefs3/refs/decisions.md differs from its source .*rrefs3/decisions.md"
cp "$STORE/stages/rrefs3/decisions.md" "$STORE/stages/rrefs3/refs/decisions.md"
run gate --run rrefs3 --to "item two"
need_absent "staged reference copy"
verdict "INV-3 F2 (fails on old): with no --decisions-file the gate compares a run's refs/decisions.md with the stage's own decisions.md, and an equal pair stays quiet"

fixture rorient2 200
mk transcript sid-rorient2 100000 60000 >/dev/null
mk append "$REC" '{"event":"head-resumed","session_id":"sid-rorient2","pid":1,"context":90000,"waited_s":1,"reset_source":"x","resume_n":1}' >/dev/null
run gate --run rorient2 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "null" "null after a resume"
need_eq "$(mk field "$REC" gate orientation_note)" "unmeasured after a resume" "the note"
fixture rorient3 200
run gate --run rorient3 --to "item one"
need_eq "$(mk field "$REC" gate orientation_tokens)" "null" "null when unmetered"
case $(mk field "$REC" gate orientation_note) in
  "unmetered gate"*) : ;;
  *) why="$why; the unmetered note is wrong: $(mk field "$REC" gate orientation_note)" ;;
esac
verdict "gate: orientation is null with its reason after a head-resumed event and on an unmetered gate"

# A run-resume naming the session the head event before it named: the process kept its context,
# so its first call after the resume carries the whole session, and the difference is not an
# orientation cost.
fixture rorient6 200
mk transcript sid-rorient6b 100000 60000 >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rorient6b","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"gate","item":"an earlier item","context":61000,"percent":6,"band":0,"armed":false,"decision":"allow","metered":true,"orientation_tokens":1240}' >/dev/null
mk append "$REC" '{"event":"run-resume","session":"sid-rorient6b","head":"fixture head","detail":"resumed in place","pid_src":"none"}' >/dev/null
run gate --run rorient6 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "null" "null after a same-session resume"
need_eq "$(mk field "$REC" gate orientation_note)" "unmeasured after a same-session resume" "the note"
need_absent "orientation 40,000"
verdict "gate: the first gate after a run-resume naming the previous head event's own session records orientation_tokens null with the same-session note"

fixture rorient7 200
mk transcript sid-rorient7b 100000 60000 >/dev/null
mk append "$REC" '{"event":"run-resume","session":"sid-rorient7b","head":"fixture head","detail":"a fresh session","pid_src":"none"}' >/dev/null
run gate --run rorient7 --to "item one"
need_rc 0
need_out "orientation 40,000"
need_eq "$(mk field "$REC" gate orientation_tokens)" "40000" "orientation still measured"
need_eq "$(mk field "$REC" gate orientation_note)" "<no key orientation_note>" "no note when it is measured"
verdict "gate: a run-resume naming a session the record has not seen still measures orientation (the control for the leg above)"

# A head-successor and the run-resume its successor writes share a session id BY DESIGN, so the
# shared id alone must not null the successor's own first gate. The shape is the run record of
# 2026-09-06 (a seeded head-exit with no transcript, a head-successor, then the run-resume, with
# no gate of that session in between): HANDSOFF_REAL_RECORD points the legs at that record — its
# session ids rewritten to this suite's own — and without it the same eight events are built here.
REALREC=${HANDSOFF_REAL_RECORD:-}
shape_record() { # $1 destination record, $2 the session id to give the resumed head
  if [ -f "$REALREC" ]; then
    "$PY" - "$REALREC" "$1" "$2" <<'SHAPE'
import json, sys
evs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()][:8]
last = [e.get("session") or e.get("session_id") for e in evs
        if e.get("event") in ("run-open", "run-resume", "head-successor")][-1]
for e in evs:
    for key in ("session", "session_id"):
        if e.get(key):
            e[key] = sys.argv[3] if e[key] == last else "sid-seeded-head"
open(sys.argv[2], "w", encoding="utf-8").write("".join(json.dumps(e) + "\n" for e in evs))
SHAPE
    SHAPE_SRC="the run record of 2026-09-06"
  else
    mk append "$1" '{"event":"observation","phase":"","what":"head exited","exit_class":"error","note":"the seeded head never ran"}' >/dev/null
    mk append "$1" '{"event":"head-exit","band":"unmetered","context":"unmetered (transcript missing: a path that is not there)","exit_class":"error","pack":false}' >/dev/null
    mk append "$1" "{\"event\":\"head-successor\",\"session_id\":\"$2\",\"pid\":1,\"budget\":1.0}" >/dev/null
    mk append "$1" "{\"event\":\"run-resume\",\"session\":\"$2\",\"head\":\"fixture head\",\"detail\":\"the successor records itself\",\"pid_src\":\"none\"}" >/dev/null
    SHAPE_SRC="the same eight events built here"
  fi
}

fixture rorient8 200
shape_record "$REC" sid-rorient8b
mk transcript sid-rorient8b 72167 59763 >/dev/null
run gate --run rorient8 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "12404" "the successor's own first gate stays measured"
need_eq "$(mk field "$REC" gate orientation_note)" "<no key orientation_note>" "no note on a measured gate"
need_out "orientation 12,404"
verdict "gate: a run-resume naming the head-successor's own session, with no gate of that session before it, still measures orientation ($SHAPE_SRC)"

fixture rorient9 200
shape_record "$REC" sid-rorient9b
mk transcript sid-rorient9b 72167 59763 >/dev/null
"$PY" - "$REC" <<'INSERT'
import json, sys
path = sys.argv[1]
evs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
cut = max(i for i, e in enumerate(evs) if e.get("event") == "run-resume")
gate = {"ts": evs[cut]["ts"], "run": evs[cut].get("run"), "event": "gate", "item": "an earlier item",
        "context": 61000, "percent": 6, "band": 0, "armed": False, "decision": "allow",
        "metered": True, "orientation_tokens": 1240}
evs.insert(cut, gate)
open(path, "w", encoding="utf-8").write("".join(json.dumps(e) + "\n" for e in evs))
INSERT
run gate --run rorient9 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "null" "null once that session has gated before the resume"
need_eq "$(mk field "$REC" gate orientation_note)" "unmeasured after a same-session resume" "the note"
verdict "gate: the same shape with one gate of that session BEFORE the run-resume nulls the first gate after it (the control for the leg above)"

# G58 (register 2026-10-16 03:30): a fresh head that finishes the item in flight before its first
# gate. The planted case is a successor's spawn before that gate; the two controls are the same
# shape with no item action, measured above (rorient8), and a run's opening head, measured here.
fixture rorient10 200
shape_record "$REC" sid-rorient10b
mk transcript sid-rorient10b 72167 59763 >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L-work","class":"builder"}' >/dev/null
run gate --run rorient10 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "null" "null after resumed item work"
need_eq "$(mk field "$REC" gate orientation_note)" "unmeasured: resumed item work (lane-open) before the first gate" "the note"
need_absent "orientation 12,404"
fixture rorient11 200
mk transcript sid-rorient11 100000 60000 >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L-open","class":"builder"}' >/dev/null
run gate --run rorient11 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "40000" "the opening head's first gate stays measured"
verdict "G58 (fails on old): a successor's first gate after a decision, spawn or boundary of its own records orientation unmeasured with the reason, while the opening head's first gate stays measured"

# G58, the review's F4: resuming a helper is the same continuation as spawning one. The planted case
# is a successor's lane-resumed before its first gate; the control is the opening head's own.
fixture rorient12 200
shape_record "$REC" sid-rorient12b
mk transcript sid-rorient12b 72167 59763 >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L-work"}' >/dev/null
run gate --run rorient12 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "null" "null after a resumed helper"
need_eq "$(mk field "$REC" gate orientation_note)" "unmeasured: resumed item work (lane-resumed) before the first gate" "the note"
fixture rorient13 200
mk transcript sid-rorient13 100000 60000 >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L-open"}' >/dev/null
run gate --run rorient13 --to "item one"
need_rc 0
need_eq "$(mk field "$REC" gate orientation_tokens)" "40000" "the opening head's first gate stays measured"
verdict "G58 F4 (fails on old): a successor's first gate after resuming a helper records orientation unmeasured, while the opening head's first gate stays measured"

# ----------------------------------------------------------- N5: the envelope remainder ----
# K22da6bf5 (register entry 2026-09-26 02:2x): the remainder is the envelope minus the run's spend
# as the gate and the close read it, never the sum of the head-exits' session totals, which
# counted a resumed or repaired head twice and each head's lanes with it. The record's head
# spends $12.34 (the billed line in hand) while its head-exits carry $50 and $40: 100 − 12.34.
fixture rspent 100
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":50}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":40}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rspent --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$87.66"
need_absent "budget \$10.00"
# A billed line whose head figure is over the envelope leaves it spent.
METER120=$(printf '%s' "$METER" | sed 's/head \$12\.34 · lanes \$4\.22 · session \$16\.56/head $120.00 · lanes $0.00 · session $120.00/')
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rspent --meter-line "$METER120" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "the envelope is spent"
need_lines
need_eq "$(mk field "$REC" successor-aborted reason)" "budget" "successor-aborted budget"
verdict "successor (K22da6bf5): the remainder is the envelope minus the run's spend (100 − \$12.34, the head-exits' \$50 and \$40 not summed); a spend over the envelope → successor-aborted budget"

# ------------------------------------------------- the limit gate (D42): the grants file's key ---
HO="$WORK/handoffs/onl-handoff.md"; mk handoff "$HO" >/dev/null
REC="$STORE/spawn-records/ronl.jsonl"; rm -f "$REC"
GF="$STORE/spawn-records/ronl-grants.json"; rm -f "$GF"
run run-open --run ronl --session sid-onl --head "fixture head" --regime single --regime-src owner \
    --handoff "$HO" --detail "gate" --pid 1
need_rc 0
need_eq "$(gval "$GF")" "stop" "run-open default"
need_eq "$(mk field "$REC" run-open on_limit)" "stop" "the run-open event"
need_eq "$(mk field "$REC" run-open on_limit_src)" "default (no grants file)" "the source"
need_out "on_limit stop (default (no grants file))"
run grants --run ronl --on-limit resume
need_rc 0
need_eq "$(gval "$GF")" "resume" "grants --on-limit resume"
need_out "on_limit resume (--on-limit)"
run grants --run ronl --grant "$WORK/handoffs"
need_rc 0
need_eq "$(gval "$GF")" "resume" "a rebuild with --grant carries resume forward"
need_eq "$(mk field "$REC" grants on_limit_src)" "grants" "carried from the file"
run run-resume --run ronl --session sid-onl2 --head "fixture head" --detail "flag-less" --pid 1
need_rc 0
need_eq "$(gval "$GF")" "resume" "a flag-less run-resume keeps the file"
need_eq "$(mk field "$REC" run-resume on_limit)" "resume" "the run-resume event"
run run-resume --run ronl --session sid-onl3 --head "fixture head" --detail "rebuild" --pid 1 --grant "$WORK/handoffs"
need_rc 0
need_eq "$(gval "$GF")" "resume" "a run-resume rebuild with --grant carries resume forward"
run run-resume --run ronl --session sid-onl4 --head "fixture head" --detail "set stop" --pid 1 --on-limit stop
need_rc 0
need_eq "$(gval "$GF")" "stop" "run-resume --on-limit stop rewrites"
need_eq "$(mk field "$REC" run-resume on_limit_src)" "--on-limit" "the source"
REC2="$STORE/spawn-records/ronl2.jsonl"; rm -f "$REC2"
run run-open --run ronl2 --session sid-onl5 --head "fixture head" --regime single --regime-src owner \
    --handoff "$HO" --detail "gate" --pid 1 --on-limit resume
need_rc 0
need_eq "$(gval "$STORE/spawn-records/ronl2-grants.json")" "resume" "run-open --on-limit resume"
verdict "limit gate (D42): run-open writes on_limit stop by default and resume under the flag; grants --on-limit sets it; every rebuild (grants --grant, run-resume --grant) and a flag-less run-resume carry it forward; --on-limit stop rewrites"

run grants --run ronl --grants-file "$WORK/elsewhere-grants.json" --on-limit resume
need_rc 2
need_out "grants-file is retired"
need_nofile "$WORK/elsewhere-grants.json"
need_eq "$(gval "$GF")" "stop" "the default path's file is untouched by the refusal"
verdict "limit gate (D42): --grants-file is retired and refused (register 2026-09-06), so no on_limit can land outside the default path the supervisor and the status hook read (C2 H2)"

# The oracle for a stop's head-exits (register entry 2026-09-14 05:13), independent of
# handsoff.py: for the FIRST head started on the record (its head-successor or head-resumed, up to
# the next head start) it prints the number of head-exit events, then the order of that stop's
# 'head exited' observation, stop-condition, head-exit and successor-aborted events.
hx_shape() { # $1 record
  "$PY" - "$1" <<'HXSHAPE'
import json, sys
evs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
starts = [i for i, e in enumerate(evs) if e.get("event") in ("head-successor", "head-resumed")]
if not starts:
    print("no head start")
    sys.exit(0)
end = starts[1] if len(starts) > 1 else len(evs)
seq = []
for e in evs[starts[0] + 1:end]:
    kind = e.get("event")
    if kind == "observation" and e.get("what") == "head exited":
        seq.append("exited")
    elif kind in ("stop-condition", "head-exit", "successor-aborted"):
        seq.append(kind)
print("%d %s" % (seq.count("head-exit"), ",".join(seq)))
HXSHAPE
}

# --------------------------------------------------------- the supervisor: limit, resume ---
fixture rlim 200
arm_resume rlim
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
OUT="$WORK/starter/rlim-head-1.out"
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rlim --handoff "$HO" --budget 3.50 --out "$OUT" --wait-s 5 --harness-bin "$WORK/bin/stubhead" \
        --meter-line "$METER" --reset-at +2s --tick-s 1
need_rc 0
need_eq "$(mk field "$REC" stop-condition which)" "limit" "stop-condition"
case $(mk field "$REC" stop-condition action) in
  "wait until "*"(--reset-at +2s)") : ;;
  *) why="$why; --reset-at did not win over the stop text: $(mk field "$REC" stop-condition action)" ;;
esac
need_eq "$(mk field "$REC" stop-condition note)" "You've hit your session limit · resets 8:50am (Europe/London)" "the stop text"
need_eq "$(mk field "$REC" stop-condition on_limit_src)" "grants" "the gate read from the grants file"
case $(mk field "$REC" stop-condition watch) in "transcript "*) : ;; *) why="$why; the stop-condition names no watched transcript: $(mk field "$REC" stop-condition watch)" ;; esac
need_eq "$(mk field "$REC" head-resumed context)" "50000" "head-resumed context"
need_eq "$(mk field "$REC" head-resumed resume_n)" "1" "resume_n"
need_eq "$(mk field "$REC" head-resumed reset_source)" "--reset-at +2s" "reset_source"
need_eq "$(mk field "$REC" head-resumed out)" "$OUT" "out"
W=$(mk field "$REC" head-resumed waited_s); [ "$W" -ge 2 ] || why="$why; waited_s $W under 2"
case $(sed -n 2p "$WORK/stub-rlim.args") in
  *"--resume "*) : ;;
  *) why="$why; the second invocation is not a --resume: $(sed -n 2p "$WORK/stub-rlim.args")" ;;
esac
case $(sed -n 2p "$WORK/stub-rlim.args") in *"--session-id"*) why="$why; the resume carries --session-id" ;; esac
grep -q "RESUMED after the account window reset" "$WORK/stub-rlim.stdin.2" || why="$why; the resume note is missing"
grep -q "Lanes closed with exit class limit: resume each with lane.py resume" "$WORK/stub-rlim.stdin.2" || why="$why; the note's last sentence is missing"
need_eq "$(grep -c '"type":"result"' "$OUT")" "2" "both results appended to the same .out"
case $(mk field "$REC" observation note) in handed-over*) : ;; *) why="$why; not ended handed-over" ;; esac
verdict "supervisor: a limit stop waits (--reset-at wins over the text), resumes under the edge with the note on stdin, then the hand-over ends it"

fixture rlim2 200
arm_resume rlim2
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=170000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rlim2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rlim2-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume at 85 % (fit false: 170k + 25k + 4k over the 180k belt)"
"$PY" - "$REC" <<'CHAIN' > "$WORK/chain.txt"
import json, sys
evs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
ex = [e for e in evs if e.get("event") == "head-exit" and e.get("exit_class")]
print("%s %s %s" % (ex[0]["band"], ex[0]["exit_class"], ex[0].get("spent_usd")) if ex else "none")
CHAIN
need_eq "$(cat "$WORK/chain.txt")" "limit limit 16.56" "head-exit band limit with spent_usd"
need_eq "$(mk count "$REC" head-successor)" "3" "the successor path ran"
need_eq "$(hx_shape "$REC")" "1 exited,stop-condition,head-exit" "the limit stop's head-exits (one, from the successor path alone)"
case $(sed -n 2p "$WORK/stub-rlim2.args") in *"--session-id"*) : ;; *) why="$why; the successor is not a fresh session" ;; esac
verdict "supervisor: a limit stop at or above the first edge writes head-exit band limit and starts the successor"

# ------------------------------------------- the limit gate (D42, D43): stop and stand down ---
# t2: the default. No grants file at all → on_limit stop, source "default (no grants file)": the
# supervisor writes the stop-condition and stands down at once — no wait, no resume, exit 0.
fixture rstop 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rstop --handoff "$HO" --budget 3.50 --out "$WORK/starter/rstop-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_out "stood down (limit-stop)"
need_eq "$(mk field "$REC" stop-condition which)" "limit" "stop-condition"
need_eq "$(mk field "$REC" stop-condition action)" "stand-down: on_limit stop" "the action"
need_eq "$(mk field "$REC" stop-condition on_limit_src)" "default (no grants file)" "the source"
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "limit-stop" "stood-down reason"
need_eq "$(mk field "$REC" supervisor-stood-down on_limit)" "stop" "on_limit"
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume"
need_eq "$(mk count "$REC" successor-aborted)" "0" "not an abort"
need_eq "$(cat "$WORK/stub-rstop.count")" "1" "one start, no second"
verdict "limit gate (D42): with no grants file the default on_limit stop stands the supervisor down at once — stop-condition, supervisor-stood-down limit-stop, exit 0, no wait, no resume"

# resume-head (D42's recovery, C2 M4): after the stand-down above, the owner's command resumes the
# head in place — armed (AIMYTH_HANDSOFF_RUN), with the head-resumed event, supervised to its hand-over.
RSID=$(mk field "$REC" head-successor session_id)
run resume-head --run rstop --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --dry-run
need_rc 0
need_out "would detach"
need_out "_resume-head --run rstop --session $RSID"
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
run _resume-head --run rstop --session "$RSID" --out "$WORK/starter/rstop-head-1.out" \
    --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --wait-s 5 --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" head-resumed)" "1" "head-resumed"
need_eq "$(mk field "$REC" head-resumed reset_source)" "resume-head (by hand, after the reset)" "the source"
case $(sed -n 2p "$WORK/stub-rstop.args") in *"--resume $RSID"*) : ;; *) why="$why; the second invocation is not a --resume of the session: $(sed -n 2p "$WORK/stub-rstop.args")" ;; esac
need_eq "$(cat "$WORK/stub-rstop.env")" "rstop" "AIMYTH_HANDSOFF_RUN seen by the resumed head (armed)"
case $(mk field "$REC" observation note) in handed-over*) : ;; *) why="$why; not ended handed-over: $(mk field "$REC" observation note)" ;; esac
verdict "resume-head (D42, C2 M4): after a stand-down the owner's command resumes the last head in place — armed, head-resumed recorded, supervised to the hand-over"

# t7: a grants file written before the gate existed (no on_limit key) reads stop, source "default (key absent)".
fixture rstop2 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
printf '{"run":"rstop2","grants":[],"writes":[]}\n' > "$STORE/spawn-records/rstop2-grants.json"
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rstop2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rstop2-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_eq "$(mk field "$REC" stop-condition on_limit_src)" "default (key absent)" "the source"
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "limit-stop" "stood-down"
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume"
verdict "limit gate (D42): a grants file without the key reads stop, source default (key absent)"

# t3: under resume, the transcript changes during the wait (the owner continued the session by
# hand) → supervisor-stood-down resumed-by-hand, no resume call. The starter runs in the
# background with a 6 s reset; the leg appends one record to the head's transcript once the
# stop-condition is written. The rlim leg above is the control: unchanged → head-resumed.
fixture rhand 200
arm_resume rhand
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
(
  RCF=0
  env STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$H" _starter \
      --run rhand --handoff "$HO" --budget 3.50 --out "$WORK/starter/rhand-head-1.out" --wait-s 5 \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +6s --tick-s 1 \
      >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait_field "$REC" stop-condition which limit 20
HSID=$(mk field "$REC" head-successor session_id)
HTR=$(find "$PROJECTS" -name "$HSID.jsonl" | head -1)
[ -n "$HTR" ] || why="$why; no transcript for the head session $HSID under $PROJECTS"
printf '{"type":"user","message":{"role":"user","content":"continue"}}\n' >> "$HTR"
wait "$STARTER"
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 0
need_out "stood down (resumed-by-hand)"
case $(mk field "$REC" stop-condition watch) in "transcript "*) : ;; *) why="$why; the stop-condition names no watched transcript: $(mk field "$REC" stop-condition watch)" ;; esac
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "resumed-by-hand" "stood-down reason"
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume"
need_eq "$(mk count "$REC" successor-aborted)" "0" "not an abort"
need_eq "$(cat "$WORK/stub-rhand.count")" "1" "one start, no second"
verdict "limit gate (D43): under resume, a transcript that changes during the wait stands the supervisor down (resumed-by-hand) with no resume call — the rlim leg is its control (unchanged transcript → head-resumed)"

# t4: supervise --stop needs no harness ancestor (it precedes pid resolution), writes the marker,
# and the sleeping supervisor stands down (stopped) at its next tick.
fixture rmark 200
arm_resume rmark
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
(
  RCF=0
  env STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$H" _starter \
      --run rmark --handoff "$HO" --budget 3.50 --out "$WORK/starter/rmark-head-1.out" --wait-s 5 \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +6s --tick-s 1 \
      >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait_field "$REC" stop-condition which limit 20
RUNENV="PATH=$WORK/psnone:$PATH"
run supervise --run rmark --stop
need_rc 0
need_out "stop marker written"
need_file "$STORE/spawn-records/rmark-supervisor.stop"
need_eq "$(mk field "$REC" supervise mode)" "stop-requested" "the supervise event"
wait "$STARTER"
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 0
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "stopped" "stood-down reason"
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume"
verdict "limit gate (D43): supervise --stop under the no-ancestor stub writes the marker, and the sleeping supervisor stands down (stopped) at its next tick"

# a fresh arming removes a stale marker: the rmark marker is still on disk; a new starter for the
# same run must not stand down on it.
fixture rmark2 200
arm_resume rmark2
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
printf 'stale\n' > "$STORE/spawn-records/rmark2-supervisor.stop"
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rmark2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rmark2-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_out "stale stop marker removed"
need_eq "$(mk count "$REC" supervisor-stood-down)" "0" "no stand-down on a stale marker"
need_eq "$(mk count "$REC" head-resumed)" "1" "the resume ran"
verdict "limit gate (D43): a fresh arming removes a stale stop marker and the wait proceeds to the resume"

# t4c: a stop marker present AT THE HEAD'S EXIT stands the supervisor down before any successor
# decision, on the successor fork of a head that did not stop on a limit — the shape of the
# 2026-09-07 register entry: a marker written before a successor started after a SIGTERM must
# stop it. The supervisor is attached to a pid that is already gone, so the
# classification runs at once off the head's own .out; t4d below is the same fixture with no
# marker, and it starts the successor.
fixture rexit 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"terminated by a signal"}' > "$WORK/rexit.out"
printf 'stopped by the owner\n' > "$STORE/spawn-records/rexit-supervisor.stop"
RC=0
env "$PY" -B "$H" _supervise --run rexit --pid 999999 --session sid-rexit \
    --out "$WORK/rexit.out" --harness-bin "$WORK/bin/stubhead" --handoff "$HO" \
    --meter-line "$METER" --tick-s 1 --wait-s 2 >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 0
need_out "stood down (stopped)"
need_out "a stop marker was on disk at the head's exit"
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "stopped" "stood-down reason"
need_eq "$(mk count "$REC" head-successor)" "0" "no successor start"
need_eq "$(mk count "$REC" successor-aborted)" "0" "not an abort"
[ -f "$WORK/stub-rexit.count" ] && why="$why; the stub head was started"
need_file "$STORE/spawn-records/rexit-supervisor.stop"
verdict "stop marker (2026-09-07): a marker on disk at a head's exit stands the supervisor down (stopped) before the successor decision, on a non-limit exit class; the marker is left for the record"

# t4c2: the other fork — a head that left NO head-exit, classified from its own .out (the shape a
# signalled head takes). The marker stands the supervisor down there too.
fixture rexit4 200
printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"terminated by a signal"}' > "$WORK/rexit4.out"
printf 'stopped by the owner\n' > "$STORE/spawn-records/rexit4-supervisor.stop"
RC=0
env "$PY" -B "$H" _supervise --run rexit4 --pid 999999 --session sid-rexit4 \
    --out "$WORK/rexit4.out" --harness-bin "$WORK/bin/stubhead" --handoff "$HO" \
    --meter-line "$METER" --tick-s 1 --wait-s 2 >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 0
need_out "stood down (stopped)"
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "stopped" "stood-down reason"
need_eq "$(mk count "$REC" head-exit)" "0" "no head-exit written by the supervisor"
need_eq "$(mk count "$REC" head-successor)" "0" "no successor start"
[ -f "$WORK/stub-rexit4.count" ] && why="$why; the stub head was started"
verdict "stop marker: on the classifier's own fork too (a head that left no head-exit, the signalled shape) the marker stands the supervisor down before the successor decision"

# t4d: the control — the same fixture and the same exit, with no marker: the successor starts.
fixture rexit2 200
printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"terminated by a signal"}' > "$WORK/rexit2.out"
need_nofile "$STORE/spawn-records/rexit2-supervisor.stop"
RC=0
env STUB_MODE=complete STUB_N=0 "$PY" -B "$H" _supervise --run rexit2 --pid 999999 \
    --session sid-rexit2 --out "$WORK/rexit2.out" --harness-bin "$WORK/bin/stubhead" \
    --handoff "$HO" --meter-line "$METER" --tick-s 1 --wait-s 2 >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_eq "$(mk count "$REC" supervisor-stood-down)" "0" "no stand-down without a marker"
need_eq "$(cat "$WORK/stub-rexit2.count")" "1" "the stub head was started once (the successor)"
need_out "successor path"
verdict "stop marker: the control — the same exit with no marker takes the successor path and starts one head"

# t4e: arming a supervisor does not clear the marker (the three clearing sites are resume-head, a
# successor called by a head, and close). The marker planted here survives the attach, so the
# supervisor stands down at the head's exit rather than succeeding it.
fixture rexit3 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"terminated by a signal"}' > "$WORK/rexit3.out"
printf 'stopped by the owner\n' > "$STORE/spawn-records/rexit3-supervisor.stop"
RC=0
env "$PY" -B "$H" _supervise --run rexit3 --pid 999999 --session sid-rexit3 \
    --out "$WORK/rexit3.out" --harness-bin "$WORK/bin/stubhead" --handoff "$HO" \
    --meter-line "$METER" --tick-s 1 --wait-s 2 >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_absent "stale stop marker removed"
need_file "$STORE/spawn-records/rexit3-supervisor.stop"
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "stopped" "stood-down reason"
verdict "stop marker: attaching a supervisor never clears the marker (no 'stale stop marker removed' line), so a stopped run stays stopped across a re-arming"

# t8: the ≥60 % fork under resume with the transcript changed during the wait → stood down, no
# successor start (the last-act check before successor_path is the same check the tick runs).
fixture rhand2 200
arm_resume rhand2
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
(
  RCF=0
  env STUB_MODE=limit STUB_N=1 STUB_TOKENS=150000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$H" _starter \
      --run rhand2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rhand2-head-1.out" --wait-s 5 \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +6s --tick-s 1 \
      >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait_field "$REC" stop-condition which limit 20
HSID=$(mk field "$REC" head-successor session_id)
HTR=$(find "$PROJECTS" -name "$HSID.jsonl" | head -1)
[ -n "$HTR" ] || why="$why; no transcript for the head session $HSID under $PROJECTS"
printf '{"type":"user","message":{"role":"user","content":"continue"}}\n' >> "$HTR"
wait "$STARTER"
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 0
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "resumed-by-hand" "stood-down reason"
need_eq "$(mk count "$REC" head-successor)" "1" "no successor start after the stand-down (the starter's own only)"
need_eq "$(cat "$WORK/stub-rhand2.count")" "1" "one start, no second"
verdict "limit gate (D43): at 75 % (the successor fork) a transcript that changes during the wait stands the supervisor down before any successor start"

# t6: no transcript file (no STUB_TOKENS) → the wait is unwatched, recorded as such, and proceeds.
fixture runw 200
arm_resume runw
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=1 AIMYTH_CONTEXT_WINDOW=200000"
starter --run runw --handoff "$HO" --budget 3.50 --out "$WORK/starter/runw-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_eq "$(mk field "$REC" stop-condition watch)" "unwatched (no transcript file)" "the watch label"
need_eq "$(mk count "$REC" supervisor-stood-down)" "0" "no stand-down"
verdict "limit gate (D43): with no transcript file the wait is recorded unwatched and proceeds"

# t3d / t8b (C2 M3): the LAST-ACT check. The change lands after the wait's last tick and before
# the start: --reset-at +8s with --tick-s 5 checks at 0 s and 5 s, then sleeps to 8 s; the leg
# appends at ≈6.5 s. A per-tick-only implementation resumes; the last-act check stands down.
# Timing-dependent by construction (margins of 1.5 s each side: the append at 6.5 s against the
# 5 s tick and the 8 s start).
fixture rlast 200
arm_resume rlast
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
(
  RCF=0
  env STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$H" _starter \
      --run rlast --handoff "$HO" --budget 3.50 --out "$WORK/starter/rlast-head-1.out" --wait-s 5 \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +8s --tick-s 5 \
      >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait_field "$REC" stop-condition which limit 20
sleep 6
HSID=$(mk field "$REC" head-successor session_id)
HTR=$(find "$PROJECTS" -name "$HSID.jsonl" | head -1)
printf '{"type":"user","message":{"role":"user","content":"continue"}}\n' >> "$HTR"
wait "$STARTER"
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 0
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "resumed-by-hand" "stood-down reason"
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume"
verdict "limit gate (D43, C2 M3): the resume fork's last-act check catches a change after the wait's last tick (timing leg)"

fixture rlast2 200
arm_resume rlast2
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
(
  RCF=0
  env STUB_MODE=limit STUB_N=1 STUB_TOKENS=150000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$H" _starter \
      --run rlast2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rlast2-head-1.out" --wait-s 5 \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +8s --tick-s 5 \
      >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait_field "$REC" stop-condition which limit 20
sleep 6
HSID=$(mk field "$REC" head-successor session_id)
HTR=$(find "$PROJECTS" -name "$HSID.jsonl" | head -1)
printf '{"type":"user","message":{"role":"user","content":"continue"}}\n' >> "$HTR"
wait "$STARTER"
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 0
need_eq "$(mk field "$REC" supervisor-stood-down reason)" "resumed-by-hand" "stood-down reason"
need_eq "$(mk count "$REC" head-successor)" "1" "no successor start (the starter's own only)"
need_eq "$(cat "$WORK/stub-rlast2.count")" "1" "one start, no second"
verdict "limit gate (D43, C2 H1): the successor fork's last-act check, inside start_head after the meter, catches a change after the wait's last tick (timing leg)"

fixture rbud 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=budget STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rbud --handoff "$HO" --budget 3.50 --out "$WORK/starter/rbud-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" stop-condition)" "0" "no wait after a budget stop"
need_eq "$(mk field "$REC" head-resumed budget)" "187.66" "the resume's cap is the remainder (200 - 12.34, the run's spend: the head's figure in the billed line, the earlier head-exit's 5 not summed; K22da6bf5)"
case $(sed -n 2p "$WORK/stub-rbud.args") in *"--resume "*"--max-budget-usd 187.66"*) : ;; *) why="$why; the resume's argv lacks the remainder cap" ;; esac
grep -q "RESUMED after a budget stop" "$WORK/stub-rbud.stdin.2" || why="$why; the budget note is missing"
fixture rbud2 10      # 10 − 12.34 (the run's spend): spent
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=budget STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rbud2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rbud2-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "budget" "successor-aborted budget"
need_eq "$(mk count "$REC" head-resumed)" "0" "no resume on a spent envelope"
verdict "supervisor: a budget stop resumes at once at the remainder; a spent envelope aborts (budget)"

fixture rn4 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=handonly STUB_N=1"
starter --run rn4 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rn4-head-1.out" --wait-s 2 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_out "has no successor after 2 s"
need_eq "$(mk count "$REC" head-successor)" "3" "starter, the N4 start, the stub's own"
need_eq "$(mk count "$REC" successor-aborted)" "0" "no abort"
need_eq "$(cat "$WORK/stub-rn4.count")" "2" "stub invocations"
case $(mk field "$REC" observation note) in handed-over*) : ;; *) why="$why; the control did not end handed-over" ;; esac
verdict "supervisor (N4): a head-exit with no head-successor after the wait gets the successor path; with one present, handed-over ends it"

fixture rcap 200
arm_resume rcap
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=3 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rcap --handoff "$HO" --budget 3.50 --out "$WORK/starter/rcap-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_eq "$(mk count "$REC" head-resumed)" "2" "resumes capped at 2 (N6)"
need_eq "$(mk field "$REC" head-resumed resume_n)" "2" "resume_n"
need_eq "$(mk count "$REC" head-successor)" "3" "the third limit took the successor path"
verdict "supervisor (N6): resume_n is capped at 2 per session; the third limit takes the successor path"

fixture rrep 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=error STUB_N=2"
starter --run rrep --handoff "$HO" --budget 3.50 --out "$WORK/starter/rrep-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 1
need_eq "$(mk field "$REC" head-exit band)" "error" "an error exit's band (N6)"
need_eq "$(mk field "$REC" successor-aborted reason)" "repeat-stop" "repeat-stop"
need_eq "$(cat "$WORK/stub-rrep.count")" "2" "two starts, no third"
need_eq "$(hx_shape "$REC")" "1 exited,head-exit" "the first error stop's head-exits (one)"
verdict "supervisor (N6): an error exit writes band error; two consecutive error stops with no progress (no boundary by either head) abort (repeat-stop)"

# The completed-without-close loop: a head that exits completed with neither a head-exit nor a
# run-close gets its one successor, and a successor doing the same is a loop rather than
# progress. The first stop's successor is this leg's own positive control: the abort is on the
# second stop, not the first, and the head really started twice.
fixture rcomp 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=2"
starter --run rcomp --handoff "$HO" --budget 3.50 --out "$WORK/starter/rcomp-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "repeat-stop" "repeat-stop"
need_eq "$(cat "$WORK/stub-rcomp.count")" "2" "two starts, no third"
need_eq "$(mk count "$REC" head-successor)" "2" "the starter's start and the one successor (the control: the first completed stop was succeeded)"
verdict "supervisor: two consecutive completed-without-close exits with no progress (no boundary by either head: the R7 loop) abort (repeat-stop) after the first has had its successor"

# ------------------------ repeat-stop keyed on progress (the design of 2026-10-11, Revision 2) ---
# RS-BEGIN. These legs need only the plumbing above the run-open legs, so a run against an older
# handsoff.py can take them alone (the fail-on-old run). A stop counts toward repeat-stop only
# when its own head made no progress — no phase-boundary whose caller_pid is that head's process
# — and a stop pairs when the supervisor follows it with an automatic start (error, budget,
# completed, unsucceeded without an own packed exit, in any mix). A leg marked (fails on old) fails against the build before
# the change; every continuation leg counts the stub's real starts, never only an absent abort.
SUITE_H="$H"; SUITE_METER="$METER"; export SUITE_H SUITE_METER
# A transcript per head (STUB_TOKENS), so a completed or budget stop's head-exit carries a band
# edge, not `unmetered`: two unmetered head-exits in a row end the run unmetered-loop at the
# start guards, before the repeat-stop guard is ever reached.
RS_ENV="STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
rs_obs() { # $1 record: every `head exited` observation as class:progress, in order (- for none)
  "$PY" -c 'import json, sys
seen = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict) and e.get("event") == "observation" and e.get("what") == "head exited":
        seen.append("%s:%s" % (e.get("exit_class"), e.get("progress", "-")))
print(" ".join(seen))' "$1"
}
rs_get() { # $1 record, $2 kind, $3 key, $4 occurrence (1-based, 0 the last); unparseable lines skipped
  "$PY" -c 'import json, sys
found = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict) and e.get("event") == sys.argv[2]:
        found.append(e)
k = int(sys.argv[4])
if not found or k > len(found):
    print("<no %s #%d>" % (sys.argv[2], k))
else:
    v = found[k - 1 if k else -1].get(sys.argv[3], "<no key %s>" % sys.argv[3])
    print(v if isinstance(v, str) else json.dumps(v))' "$1" "$2" "$3" "$4"
}
rs_count() { # $1 record, $2 kind: that kind's events, unparseable lines skipped
  "$PY" -c 'import json, sys
n = 0
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    n += isinstance(e, dict) and e.get("event") == sys.argv[2]
print(n)' "$1" "$2"
}
rs_stubs() { # $1 run: how many times the stub head was really started
  if [ -f "$WORK/stub-$1.count" ]; then cat "$WORK/stub-$1.count"; else echo 0; fi
}
rs_fixture() { # $1 run: a run-open and the head-exit the starter succeeds
  fixture "$1" 200
  mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
}
rs_go() { # $1 run, $2 modes, $3 progress words, $4 stub stops (STUB_N), $5 extra env words: one
          # starter run, its exit code in $WORK/<run>.rc and its output in $WORK/<run>.log
  RSRC=0
  env $RS_ENV $5 STUB_MODES="$2" STUB_PROGRESS="$3" STUB_N="$4" \
      AIMYTH_VIEWER_ARGV="$WORK/viewer-$1.argv" "$PY" -B "$H" _starter --run "$1" \
      --handoff "$WORK/handoffs/$1-handoff.md" --budget 3.50 --out "$WORK/starter/$1-head-1.out" \
      --wait-s 2 --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 \
      >"$WORK/$1.log" 2>&1 || RSRC=$?
  printf '%s\n' "$RSRC" > "$WORK/$1.rc"
}
rs_attach() { # $1 run, $2 extra env words: a supervisor attached to pid 999999, already gone, whose
              # stop is classified off a completed .out — a head no start event on the record names
  printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"done without a hand-off"}' > "$WORK/$1.out"
  RSRC=0
  env $RS_ENV $2 AIMYTH_VIEWER_ARGV="$WORK/viewer-$1.argv" "$PY" -B "$H" _supervise --run "$1" \
      --pid 999999 --session "sid-$1" --out "$WORK/$1.out" --harness-bin "$WORK/bin/stubhead" \
      --handoff "$WORK/handoffs/$1-handoff.md" --meter-line "$METER" --tick-s 1 --wait-s 2 \
      >"$WORK/$1.log" 2>&1 || RSRC=$?
  printf '%s\n' "$RSRC" > "$WORK/$1.rc"
}
# The matrix's unsucceeded stops have no pack; packed hand-overs are covered separately below.
rs_mode() { case $1 in completed) echo complete ;; unsucceeded) echo handunpacked ;; *) echo "$1" ;; esac; }
rs_word() { case $1 in yes) echo self ;; *) echo none ;; esac; }
rs_cell() { # $1 run, $2 first class, $3 its progress, $4 second class, $5 its progress: the
            # outcome against the rule, empty when it holds
  R="$STORE/spawn-records/$1.jsonl"
  if [ "$3" = no ] && [ "$5" = no ]; then
    want="rc 1 · repeat-stop · starts 2 · $2:no $4:no"
  else
    want="rc 0 · <no successor-aborted #0> · starts 3 · $2:$3 $4:$5 handed-over:no"
  fi
  have="rc $(cat "$WORK/$1.rc") · $(rs_get "$R" successor-aborted reason 0) · starts $(rs_stubs "$1") · $(rs_obs "$R")"
  # behaviour: the exit, the abort and the starts alone, without the recorded verdicts
  [ "${6:-}" = "behaviour" ] && { have=${have% · *}; want=${want% · *}; }
  [ "$have" = "$want" ] || printf '%s:%s then %s:%s got [%s] wanted [%s]' "$2" "$3" "$4" "$5" "$have" "$want"
}

# The matrix: every ordered pair of completed, error, budget and unsucceeded, each side with and
# without its own boundary — 64 two-stop runs, both stops real, eight at a time (each run has its
# own record, stub counter and viewer file). The rule: repeat-stop exactly when both read no.
RS_I=0; RS_PIDS=""; RS_CELLS=""
for rx in completed error budget unsucceeded; do
  for rp in yes no; do
    for ry in completed error budget unsucceeded; do
      for rq in yes no; do
        RS_I=$((RS_I + 1))
        RS_CELLS="$RS_CELLS rsm$RS_I:$rx:$rp:$ry:$rq"
        rs_fixture "rsm$RS_I"
        rs_go "rsm$RS_I" "$(rs_mode $rx),$(rs_mode $ry)" "$(rs_word $rp),$(rs_word $rq)" 2 "" &
        RS_PIDS="$RS_PIDS $!"
        if [ $((RS_I % 8)) -eq 0 ]; then
          for rs_pid in $RS_PIDS; do wait "$rs_pid"; done
          RS_PIDS=""
        fi
      done
    done
  done
done
for rs_pid in $RS_PIDS; do wait "$rs_pid"; done
rs_named() { # $1 x, $2 p, $3 y, $4 q, $5 optional `behaviour`: that cell's matrix run against the rule
  id=$(printf '%s\n' $RS_CELLS | grep ":$1:$2:$3:$4\$" | cut -d: -f1)
  [ -n "$id" ] || { why="$why; no matrix run for $1:$2:$3:$4"; return; }
  miss=$(rs_cell "$id" "$1" "$2" "$3" "$4" "${5:-}")
  [ -z "$miss" ] || why="$why; $miss"
}
rs_named completed yes completed yes
verdict "repeat-stop (fails on old): two completed stops, each head with its own boundary, do not abort — a real successor starts (three stub starts)"
rs_named completed no completed no behaviour
verdict "repeat-stop: two completed stops, neither head with a boundary, abort at the second stop (the R7 case; the behaviour alone, which passes on old and new)"
rs_named completed yes completed no
rs_named completed no completed yes
verdict "repeat-stop (fails on old): completed with a boundary, then completed without (and the reverse) does not abort; a real successor starts"
rs_named error yes error yes
verdict "repeat-stop (fails on old): two error stops, each head with its own boundary, do not abort; a real successor starts"
rs_named error no error no behaviour
verdict "repeat-stop: two error stops, neither head with a boundary, abort (the behaviour alone, which passes on old and new)"
rs_named completed no error no
verdict "repeat-stop (fails on old; choice 1 B): completed without a boundary, then error without, abort — the classes pair in any mix"
RS_MISS=0; RS_HELD=0
for cell in $RS_CELLS; do
  miss=$(rs_cell $(printf '%s' "$cell" | tr ':' ' '))
  if [ -n "$miss" ]; then RS_MISS=$((RS_MISS + 1)); why="$why; $miss"; else RS_HELD=$((RS_HELD + 1)); fi
done
need_eq "$RS_HELD of $((RS_HELD + RS_MISS))" "64 of 64" "matrix cells holding the rule"
verdict "repeat-stop (Revision 2 matrix): 4 first-stop classes × 4 second-stop classes × 2 first-head boundary states × 2 second-head boundary states = 64 cells; completed, error, budget and unsucceeded with pack false, with and without each head's own boundary — repeat-stop exactly when both read progress no, otherwise a real successor; packed unsucceeded hand-overs are covered separately"

# The barrier: no, yes, no, no — mixed classes, the third a budget stop resumed in place (a new
# process with a window of its own) — aborts at the fourth stop and not before.
rs_fixture rsbar
rs_go rsbar "error,complete,budget,complete" "none,self,none,none" 4 ""
R="$STORE/spawn-records/rsbar.jsonl"
need_eq "$(cat "$WORK/rsbar.rc")" "1" "exit"
need_eq "$(rs_get "$R" successor-aborted reason 0)" "repeat-stop" "reason"
need_eq "$(rs_stubs rsbar)" "4" "four real starts, no fifth"
need_eq "$(rs_obs "$R")" "error:no completed:yes budget:no completed:no" "the recorded verdicts"
need_eq "$(rs_count "$R" head-resumed)" "1" "the budget stop resumed in place"
verdict "repeat-stop (fails on old; Revision 2): the barrier no, yes, no, no aborts only at the fourth stop — a head's own boundary breaks the pair"

# A boundary another process wrote never counts: its caller_pid names the supervisor, not the head.
rs_fixture rsfor
rs_go rsfor "complete,error" "foreign,foreign" 2 ""
R="$STORE/spawn-records/rsfor.jsonl"
need_eq "$(cat "$WORK/rsfor.rc")" "1" "exit"
need_eq "$(rs_get "$R" successor-aborted reason 0)" "repeat-stop" "reason"
need_eq "$(rs_obs "$R")" "completed:no error:no" "the recorded verdicts"
case $(rs_get "$R" observation progress_note 1) in *"(1 by another process)"*) : ;; *) why="$why; the note does not name the foreign boundary" ;; esac
need_eq "$(rs_get "$R" phase-boundary caller_pid 1)" "$(rs_get "$R" supervise supervisor_pid 1)" "the planted boundary names the supervisor's process"
verdict "repeat-stop (fails on old; Revision 2): a boundary whose caller_pid is another process never counts as the head's progress"

# A boundary with no caller_pid reads unknown, and unknown never fires.
rs_fixture rsnul
rs_go rsnul "error,error" "null,null" 2 ""
R="$STORE/spawn-records/rsnul.jsonl"
need_eq "$(cat "$WORK/rsnul.rc")" "0" "exit"
need_eq "$(rs_count "$R" successor-aborted)" "0" "no abort"
need_eq "$(rs_stubs rsnul)" "3" "a real third start"
need_eq "$(rs_obs "$R")" "error:unknown error:unknown handed-over:no" "the recorded verdicts"
verdict "repeat-stop (fails on old; Revision 2): a boundary with no caller_pid reads unknown and never fires; a real successor starts"

# A run-resume by the same process inside its window is the same invocation: the boundary it
# recorded before that marker still counts.
rs_fixture rsrr
rs_go rsrr "complete,complete" "selfresume,none" 2 ""
R="$STORE/spawn-records/rsrr.jsonl"
need_eq "$(rs_get "$R" run-resume pid 0)" "$(rs_get "$R" head-successor pid 1)" "the run-resume names the first head's own process"
need_eq "$(cat "$WORK/rsrr.rc")" "0" "exit"
need_eq "$(rs_stubs rsrr)" "3" "a real third start"
need_eq "$(rs_obs "$R")" "completed:yes completed:no handed-over:no" "the recorded verdicts"
verdict "repeat-stop (fails on old; Revision 2): a run-resume by the same process inside the window keeps the boundary written before it"

# A head-resumed is a new process: it does not borrow the boundary its predecessor wrote.
rs_fixture rshr
rs_go rshr "budget,complete,error" "self,none,none" 3 ""
R="$STORE/spawn-records/rshr.jsonl"
need_eq "$(rs_count "$R" head-resumed)" "1" "the budget stop resumed in place"
need_eq "$(rs_obs "$R")" "budget:yes completed:no error:no" "the recorded verdicts"
need_eq "$(cat "$WORK/rshr.rc")" "1" "exit"
need_eq "$(rs_get "$R" successor-aborted reason 0)" "repeat-stop" "reason"
need_eq "$(rs_stubs rshr)" "3" "three real starts, no fourth"
verdict "repeat-stop (fails on old; Revision 2): a head-resumed invocation does not borrow its predecessor's boundary"

# Malformed lines: one written inside the stopped head's window reads unknown (it may hold the
# boundary); one from before the window never disables the guard. The second head writes the
# torn line, so its stop reads unknown and the third start goes ahead; the third and fourth heads
# then stop with no progress, the torn line now before their windows, and the fourth stop fires.
# (Every head here stops by its mode: the stub's own hand-over appends through mk.py, which
# cannot read a record holding a torn line.)
rs_fixture rsbad1
rs_go rsbad1 "error,error,complete,complete" "none,bad,none,none" 4 ""
R="$STORE/spawn-records/rsbad1.jsonl"
need_eq "$(cat "$WORK/rsbad1.rc")" "1" "exit (inside)"
need_eq "$(rs_stubs rsbad1)" "4" "a real third and fourth start (inside)"
need_eq "$(rs_obs "$R")" "error:no error:unknown completed:no completed:no" "the recorded verdicts (inside)"
need_eq "$(rs_get "$R" successor-aborted reason 0)" "repeat-stop" "reason at the fourth stop (inside)"
rs_fixture rsbad2
printf '%s\n' '{"event":"phase-boundary","from":"torn before the window' >> "$STORE/spawn-records/rsbad2.jsonl"
rs_go rsbad2 "complete,error" "none,none" 2 ""
R="$STORE/spawn-records/rsbad2.jsonl"
need_eq "$(cat "$WORK/rsbad2.rc")" "1" "exit (before)"
need_eq "$(rs_get "$R" successor-aborted reason 0)" "repeat-stop" "reason (before)"
need_eq "$(rs_obs "$R")" "completed:no error:no" "the recorded verdicts (before)"
verdict "repeat-stop (fails on old; Revision 2): an unparseable line inside the head's window reads unknown and never fires; one from before the window leaves the guard in force"

# Choice 2: a head whose pid no start event on the record names (a supervisor attached to it)
# reads unknown, so the next stop with no progress does not pair with it. The control plants a
# start event naming that pid: the same stop then reads no, and the pair fires.
fixture rsatt 200
rs_attach rsatt "STUB_MODES=complete STUB_PROGRESS=none STUB_N=1"
R="$STORE/spawn-records/rsatt.jsonl"
need_eq "$(cat "$WORK/rsatt.rc")" "0" "exit"
need_eq "$(rs_count "$R" successor-aborted)" "0" "no abort"
need_eq "$(rs_stubs rsatt)" "2" "two real starts after the attached head"
need_eq "$(rs_obs "$R")" "completed:unknown completed:no handed-over:no" "the recorded verdicts"
case $(rs_get "$R" observation progress_note 1) in *"no start event names pid 999999"*) : ;; *) why="$why; the unknown does not name the missing start" ;; esac
fixture rsatt2 200
mk append "$STORE/spawn-records/rsatt2.jsonl" '{"event":"run-resume","session":"sid-rsatt2","head":"fixture head","detail":"the attached head","pid":999999,"pid_src":"arg"}' >/dev/null
rs_attach rsatt2 "STUB_MODES=complete STUB_PROGRESS=none STUB_N=1"
R="$STORE/spawn-records/rsatt2.jsonl"
need_eq "$(cat "$WORK/rsatt2.rc")" "1" "exit (control)"
need_eq "$(rs_get "$R" successor-aborted reason 0)" "repeat-stop" "reason (control)"
need_eq "$(rs_obs "$R")" "completed:no completed:no" "the recorded verdicts (control)"
verdict "repeat-stop (fails on old; choice 2): a previous stop with no readable start event reads unknown and does not pair; with the start on the record it reads no and pairs (the control)"

# Choice 3, dropped by Revision 2: an abort and a restart between two stops with no progress reset
# nothing. Case one plants a completed stop with no progress and its repeat-stop abort, then the
# owner's restart; case two is the review's shape (a budget stop, resume-failed, an automatic
# successor); the control's restarted head records a boundary and breaks the pair by itself.
fixture rsnr 200
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"completed","pid":4242,"progress":"no","progress_note":"no boundary event by pid 4242","note":"session sid-rsnr-old exit 0 → completed"}' >/dev/null
mk append "$REC" '{"event":"successor-aborted","reason":"repeat-stop","note":"planted: the earlier abort"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
rs_go rsnr "error" "none" 1 ""
need_eq "$(cat "$WORK/rsnr.rc")" "1" "exit (restart)"
need_eq "$(rs_count "$REC" successor-aborted)" "2" "a second abort"
need_eq "$(rs_get "$REC" successor-aborted reason 0)" "repeat-stop" "reason (restart)"
need_eq "$(rs_stubs rsnr)" "1" "one start, no successor"
fixture rsnr2 200
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"budget","pid":4243,"progress":"no","progress_note":"no boundary event by pid 4243","note":"session sid-rsnr2-old exit 1 → budget"}' >/dev/null
mk append "$REC" '{"event":"successor-aborted","reason":"resume-failed","note":"planted: the resume could not start"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":"error","context":"c","spent_usd":5}' >/dev/null
rs_go rsnr2 "error" "none" 1 ""
need_eq "$(cat "$WORK/rsnr2.rc")" "1" "exit (resume-failed)"
need_eq "$(rs_get "$REC" successor-aborted reason 0)" "repeat-stop" "reason (resume-failed)"
fixture rsnr3 200
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"completed","pid":4244,"progress":"no","progress_note":"no boundary event by pid 4244","note":"session sid-rsnr3-old exit 0 → completed"}' >/dev/null
mk append "$REC" '{"event":"successor-aborted","reason":"repeat-stop","note":"planted: the earlier abort"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
rs_go rsnr3 "error" "self" 1 ""
need_eq "$(cat "$WORK/rsnr3.rc")" "0" "exit (control)"
need_eq "$(rs_count "$REC" successor-aborted)" "1" "no new abort (control)"
need_eq "$(rs_stubs rsnr3)" "2" "a real successor (control)"
verdict "repeat-stop (fails on old; choice 3 dropped): stops pair across a successor-aborted and a restart — completed then error, and budget, resume-failed, then error — while a restarted head with its own boundary breaks the pair (the control)"

# A seed exit is still skipped, in both observation orders, with a real-stop control: a seeded
# record's `head exited` beside a head-exit whose session left no transcript is no previous stop.
SEEDX='{"event":"head-exit","band":"unmetered","context":"unmetered (transcript missing for the seed session)","pack":false}'
SEEDO='{"event":"observation","phase":"","what":"head exited","exit_class":"error","pid":4245,"progress":"no","progress_note":"planted","note":"the seeded head never ran"}'
REALX='{"event":"head-exit","band":"error","context":"500,000 tokens (50 %)","exit_class":"error","spent_usd":3.0,"pack":false}'
fixture rsseeda 200; mk append "$REC" "$SEEDO" >/dev/null; mk append "$REC" "$SEEDX" >/dev/null
rs_go rsseeda "error" "none" 1 ""
fixture rsseedb 200; mk append "$REC" "$SEEDX" >/dev/null; mk append "$REC" "$SEEDO" >/dev/null
rs_go rsseedb "error" "none" 1 ""
fixture rsseedc 200; mk append "$REC" "$SEEDO" >/dev/null; mk append "$REC" "$REALX" >/dev/null
rs_go rsseedc "error" "none" 1 ""
need_eq "$(cat "$WORK/rsseeda.rc") $(rs_stubs rsseeda) $(rs_count "$STORE/spawn-records/rsseeda.jsonl" successor-aborted)" "0 2 0" "observation then seed head-exit: no abort, a real successor"
need_eq "$(cat "$WORK/rsseedb.rc") $(rs_stubs rsseedb) $(rs_count "$STORE/spawn-records/rsseedb.jsonl" successor-aborted)" "0 2 0" "seed head-exit then observation: no abort, a real successor"
need_eq "$(cat "$WORK/rsseedc.rc") $(rs_stubs rsseedc) $(rs_get "$STORE/spawn-records/rsseedc.jsonl" successor-aborted reason 0)" "1 1 repeat-stop" "the real-stop control"
verdict "repeat-stop: a seed exit is still skipped as a previous stop in both observation orders, while a metered stop beside the same observation pairs (the control; passes on old and new)"

# The hard bounds stay when the verdict is unknown: the stop marker stands the supervisor down,
# and the successor cap ends the run.
fixture rsmk 200
printf 'stopped by the owner\n' > "$STORE/spawn-records/rsmk-supervisor.stop"
rs_attach rsmk ""
R="$STORE/spawn-records/rsmk.jsonl"
need_eq "$(cat "$WORK/rsmk.rc")" "0" "exit (marker)"
need_eq "$(rs_obs "$R")" "completed:unknown" "the recorded verdict (marker)"
need_eq "$(rs_get "$R" supervisor-stood-down reason 0)" "stopped" "stood down (marker)"
need_eq "$(rs_count "$R" head-successor)" "0" "no successor (marker)"
need_eq "$(rs_stubs rsmk)" "0" "no start (marker)"
rs_fixture rscap
rs_go rscap "error,error,error,error,error,error" "null,null,null,null,null,null" 6 "AIMYTH_MAX_SUCCESSORS=3"
R="$STORE/spawn-records/rscap.jsonl"
need_eq "$(cat "$WORK/rscap.rc")" "1" "exit (cap)"
need_eq "$(rs_get "$R" successor-aborted reason 0)" "successor-cap" "reason (cap)"
need_eq "$(rs_stubs rscap)" "3" "three starts at a cap of three"
need_eq "$(rs_obs "$R")" "error:unknown error:unknown error:unknown" "the recorded verdicts (cap)"
verdict "repeat-stop (fails on old; Revision 2): with the verdict unknown the stop marker still stands the supervisor down and the successor cap still ends the run"

# End to end: the stub runs the real `boundary` command, under the psclaude stub so the parent
# walk stops at the stub's own process — the head process the supervisor started and waits on.
rs_fixture rswalk
rs_go rswalk "complete,complete" "walk,walk" 2 ""
R="$STORE/spawn-records/rswalk.jsonl"
need_eq "$(rs_get "$R" phase-boundary caller_pid 1)" "$(rs_get "$R" head-successor pid 1)" "the first boundary names the first head's process"
need_eq "$(rs_get "$R" phase-boundary caller_pid 2)" "$(rs_get "$R" head-successor pid 2)" "the second boundary names the second head's process"
need_eq "$(rs_get "$R" phase-boundary caller_pid_src 1)" "head-command" "caller_pid_src"
need_eq "$(cat "$WORK/rswalk.rc")" "0" "exit"
need_eq "$(rs_stubs rswalk)" "3" "a real third start"
need_eq "$(rs_obs "$R")" "completed:yes completed:yes handed-over:no" "the recorded verdicts"
verdict "repeat-stop (fails on old; Revision 2): end to end, the boundary command records the head's own process as caller_pid by the parent walk, and the supervisor credits it"

# `boundary` itself: the parent walk's harness ancestor as caller_pid (the psclaude stub answers
# for the suite's own shell, this boundary's parent), and null with source none where the walk
# reaches no harness (the psnone stub).
fixture rsbcp 200
RUNENV="PATH=$WORK/psclaude:$PATH"
run boundary --run rsbcp --from 1 --to 2 --disposition "walked" --waste "none" --next "n" --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary caller_pid)" "$$" "caller_pid by the walk"
need_eq "$(mk field "$REC" phase-boundary caller_pid_src)" "head-command" "caller_pid_src from the head command"
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rsbcp --from 2 --to 3 --disposition "no harness" --waste "none" --next "n" --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary caller_pid)" "null" "caller_pid with no harness"
need_eq "$(mk field "$REC" phase-boundary caller_pid_src)" "none" "caller_pid_src with no harness"
verdict "boundary (fails on old; Revision 2): records caller_pid and caller_pid_src from the parent walk, null and none when the walk reaches no harness"

# The verdict and the pairing as functions, on planted records: the windows the integration legs
# above cannot plant — a hand-over whose own observation lands after its successor's start (the
# order a live record shows), a pid reused across an earlier stop — and the class lists.
RSU=$("$PY" - "$H" <<'RSUNIT'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def ev(kind, **kw):
    kw["event"] = kind
    return kw
def stop(cls="completed"):
    return ev("observation", what="head exited", exit_class=cls)
def bnd(pid):
    return ev("phase-boundary", caller_pid=pid)
fails = []
def check(name, got, want):
    if got != want:
        fails.append("%s: %r != %r" % (name, got, want))
P, Q = 4301, 4302
base = [ev("run-open", session="s0", pid_src="none")]
own = base + [ev("head-successor", session_id="s1", pid=P), bnd(P)]
check("own", mod.head_progress(own, P, 1, 0, 0)[0], "yes")
check("foreign", mod.head_progress(base + [ev("head-successor", session_id="s1", pid=P), bnd(Q)], P, 1, 0, 0)[0], "no")
check("null", mod.head_progress(base + [ev("head-successor", session_id="s1", pid=P), bnd(None)], P, 1, 0, 0)[0], "unknown")
check("absent caller", mod.head_progress(base + [ev("head-successor", session_id="s1", pid=P), ev("phase-boundary")], P, 1, 0, 0)[0], "unknown")
check("no start", mod.head_progress(base + [bnd(P)], P, 0, 0, 0)[0], "unknown")
check("no pid", mod.head_progress(own, None, 1, 0, 0)[0], "unknown")
check("bool pid", mod.head_progress(own, True, 1, 0, 0)[0], "unknown")
same = base + [ev("head-successor", session_id="s1", pid=P), bnd(P), ev("run-resume", session="s1", pid=P)]
check("same-pid run-resume", mod.head_progress(same, P, 3, 0, 0)[0], "yes")
resumed = base + [ev("head-successor", session_id="s1", pid=P), bnd(P), stop("budget"),
                  ev("head-resumed", session_id="s1", pid=Q)]
check("head-resumed borrows nothing", mod.head_progress(resumed, Q, 4, 0, 0)[0], "no")
late = base + [ev("head-successor", session_id="s1", pid=P), ev("head-exit"),
               ev("head-successor", session_id="s2", pid=Q), stop("handed-over"), bnd(Q)]
check("hand-over observation after the successor's start", mod.head_progress(late, Q, 3, 0, 0)[0], "yes")
reused = base + [ev("head-successor", session_id="s1", pid=P), bnd(P), stop("error"),
                 ev("head-successor", session_id="s2", pid=P)]
check("a reused pid's earlier boundary", mod.head_progress(reused, P, 4, 0, 0)[0], "no")
plain = base + [ev("head-successor", session_id="s1", pid=P)]
check("malformed rise", mod.head_progress(plain, P, 1, 1, 2)[0], "unknown")
check("malformed before", mod.head_progress(plain, P, 1, 1, 1)[0], "no")
check("own boundary with a rise", mod.head_progress(own, P, 1, 0, 1)[0], "yes")
for cls in ("error", "budget", "completed", "unsucceeded", "a-future-class"):
    check("pairs " + cls, mod.stop_pairs(cls), True)
for cls in ("limit", "closed", "handed-over", "classifier-missing", "waiting", None, ""):
    check("never pairs %r" % cls, mod.stop_pairs(cls), False)
check("stood down", mod.stood_down_after([stop(), ev("supervisor-stood-down")], 0), True)
check("not stood down", mod.stood_down_after([stop(), ev("head-successor")], 0), False)
check("previous_stop unchanged", mod.previous_stop([stop("error")]), "error")
print("ok" if not fails else "; ".join(fails))
RSUNIT
)
need_eq "$RSU" "ok" "the planted windows and classes"
verdict "repeat-stop (fails on old; Revision 2): the verdict's windows on planted records — own, foreign, null and absent caller_pid, no start, no pid, a same-process run-resume, a head-resumed, a hand-over observed after its successor's start, a reused pid, malformed lines — and the pairing classes"

# The module docstring states the rule that now holds, and the retired one is gone.
RSDOC=$("$PY" -c 'import ast, sys
d = ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read()))
new = ("caller_pid_src", "progress_note", "unknown never fires", "resets nothing", "both read no")
print("%d %d" % (sum(1 for s in new if s in d), d.count("two consecutive\nerror or budget stops, in any mix")))' "$H")
need_eq "$RSDOC" "5 0" "the new rule's phrases in the docstring, and the retired pairing gone"
verdict "repeat-stop (fails on old): the module docstring's supervisor paragraph states the progress rule, and the retired class-only pairing is gone"
# RS-END

# Packed hand-overs: evaluate the production repeat-stop condition in memory, never a starter.
# Reading the condition from each target also lets these same cases show the baseline result.
RSPACK=$("$PY" - "$H" <<'RSPACKPY'
import ast
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("h_rspack", sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
checks = [n.test for n in ast.walk(tree) if isinstance(n, ast.If)
          and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                  and c.func.id == "stop_pairs" for c in ast.walk(n.test))]
if len(checks) != 1:
    print("PROBE FAILED: cannot locate the repeat-stop condition")
    raise SystemExit(2)
condition = compile(ast.Expression(body=checks[0]), sys.argv[1], "eval")


def ev(kind, **kw):
    return dict(kw, event=kind)


def stop(cls, pid):
    return ev("observation", what="head exited", exit_class=cls, pid=pid, progress="no")


def pair(first="unsucceeded", second="unsucceeded", first_exits=(), second_exits=()):
    return [ev("run-open", session="sid-a", pid=101)] + list(first_exits) + [stop(first, 101),
            ev("head-successor", session_id="sid-b", pid=102)] + list(second_exits) + [stop(second, 102)]


def reason(record):
    current, events = record[-1], record[:-1]
    before_i, before_ev = h.previous_stop_event(events)
    scope = dict(vars(h), events=events, before_i=before_i, before_ev=before_ev,
                 before=(before_ev or {}).get("exit_class"), cls=current.get("exit_class"),
                 progress=current.get("progress"), pid=current.get("pid"))
    return "repeat-stop" if eval(condition, scope) else None


packed = ev("head-exit", band=80, pack=True)
unpacked = ev("head-exit", band=80, pack=False)
foreign = ev("head-exit", band=80, pack=True, pid=103)
stale = pair(first_exits=(packed, ev("run-resume", session="sid-a", pid=101)))
unknown = pair("error", "error")
unknown[-1]["progress"] = "unknown"
progress = pair("error", "error")
progress[-3]["progress"] = "yes"
mismatch = pair("error", "unsucceeded")
mismatch[-1]["pid"] = 103
seed = ev("run-open", session="seed", session_kind="seed", pid=555, pid_src="arg")
assert h.final_pid([seed], None)[0] == 555   # the live writer's premise, not a hand-set pid
bad_stop_pid = pair("error", "unsucceeded")
bad_stop_pid[-1]["pid"] = "unreadable"
bad_owner = pair("error", "unsucceeded")
bad_owner[-2]["pid"] = None
no_owner = pair("error", "unsucceeded", second_exits=(packed,))
no_owner[-3]["pid"] = None
no_owner[-1]["pid"] = None
for name, record in (
        ("S1", pair(first_exits=(packed,), second_exits=(packed,))),
        ("S2", pair("error", "error")),
        ("S3", pair("unsucceeded", "error", first_exits=(foreign,))),
        ("S4", pair("unsucceeded", "error")),
        ("S5", pair("unsucceeded", "error", first_exits=(packed,))),
        ("S6", pair("error", "unsucceeded", second_exits=(packed,))),
        ("S7", pair(first_exits=(unpacked,), second_exits=(unpacked,))),
        ("S8", pair("budget", "completed", first_exits=(packed,), second_exits=(packed,))),
        ("S9", stale),
        ("S10", pair(second_exits=(foreign,))),
        ("S11", [stop("error", 101), stop("unsucceeded", 102)]),
        ("S12", unknown),
        ("S13", pair("error", None)),
        ("S14", mismatch),
        ("S15", pair("error", "unsucceeded", second_exits=(dict(packed, pid=102),))),
        ("S16", pair("error", "unsucceeded", second_exits=(dict(packed, pid=None),))),
        ("S17", pair(second_exits=(dict(packed, pack="true"),))),
        ("S18", pair(first_exits=(ev("supervisor-stood-down"),))),
        ("S19", progress),
        ("S20", [seed] + pair(first_exits=(dict(packed, pid=555),), second_exits=(dict(packed, pid=555),))),
        ("S21", [seed] + pair(first_exits=(dict(packed, pid=556),), second_exits=(dict(packed, pid=556),))),
        ("S22", bad_stop_pid),
        ("S23", bad_owner),
        ("S24", pair(second_exits=(ev("head-exit", band=80),))),
        ("S25", pair(second_exits=(dict(packed, pack=None),))),
        ("S26", pair(second_exits=(dict(packed, pack=1),))),
        ("S27", pair(second_exits=(dict(packed, pid="unreadable"),))),
        ("S28", no_owner)):
    # S18's stand-down belongs after its first stop, as it does in the supervisor record.
    if name == "S18":
        record[1], record[2] = record[2], record[1]
    print("%s %s" % (name, reason(record)))
RSPACKPY
) || die "repeat-stop in-memory premises failed"
rspack() { printf '%s\n' "$RSPACK" | grep "^$1 " | cut -d' ' -f2; }
# S1-S19 cover the original pairing cases; S20-S21 exercise the seed writer's pid;
# S22-S28 distinguish absent fields from unreadable stop, pack and exit identities.
need_eq "$(printf '%s\n' "$RSPACK" | grep -c .)" "28" "every packed-stop case answered"
for name in S1 S5 S6 S11 S12 S13 S14 S15 S16 S17 S18 S19 S20 S22 S23 S25 S26 S27 S28; do
  need_eq "$(rspack "$name")" "None" "$name: no repeat-stop"
done
for name in S2 S3 S4 S7 S8 S9 S10 S21 S24; do
  need_eq "$(rspack "$name")" "repeat-stop" "$name: the pairing control still fires"
done
verdict "repeat-stop packed exits: S1 and S20's seed-pid hand-overs clear; S2 errors and S3/S21 foreign exits still pair; both stop positions, boolean or absent pack, latest start, foreign and unreadable identity, progress and stand-down controls; S17's unreadable pack now leaves the stop unpaired"

rs_fixture rspacked
rs_go rspacked "handonly,handonly" "none,none" 2 ""
need_eq "$(cat "$WORK/rspacked.rc")" "0" "two packed unsucceeded stops continue"
need_eq "$(rs_stubs rspacked)" "3" "the successor really started"
need_eq "$(rs_count "$STORE/spawn-records/rspacked.jsonl" successor-aborted)" "0" "no repeat-stop abort"
need_eq "$(rs_obs "$STORE/spawn-records/rspacked.jsonl")" "unsucceeded:no unsucceeded:no handed-over:no" "the packed stops and successor"
verdict "repeat-stop S1 through the supervisor: two packed hand-overs without boundaries start their successor (three stub starts; S2's matrix pair still aborts)"

# The seed guard (register 2026-09-06): a head-exit recording a session that left no transcript
# is not a stop, so it can never be the first of two. The same record's head count leaves that
# session out and the orientation rows carry one row per session id.
fixture rseed 200
shape_record "$REC" sid-rseedb
"$PY" - "$H" "$REC" <<'PREV' > "$WORK/prev.txt"
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
evs = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
print(mod.previous_stop(evs))
PREV
need_eq "$(cat "$WORK/prev.txt")" "None" "a seeded head-exit is not a previous stop"
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"error","note":"a head that really ran"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":"error","context":"500,000 tokens (50 %)","exit_class":"error","spent_usd":3.0,"pack":false}' >/dev/null
"$PY" - "$H" "$REC" <<'PREV2' > "$WORK/prev2.txt"
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
evs = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
print(mod.previous_stop(evs))
PREV2
need_eq "$(cat "$WORK/prev2.txt")" "error" "positive control: a metered error head-exit is still a stop"
verdict "supervisor: a head-exit whose session left no transcript is skipped by the repeat-stop guard, while a metered error exit still counts ($SHAPE_SRC)"

WTS="$WORK/rseed-waste.md"
run waste-table --run rseed --out "$WTS" --no-meter
need_rc 0
# One id, not two spans: the head-successor and the run-resume that follows it name the SAME
# session, so counting spans would count one head twice (register entry 2026-09-06, fixed
# 2026-09-07). The distinct-id count is asserted in its own leg further down with a control.
need_eq "$(grep -c '1 head session(s)' "$WTS")" "1" "the head count leaves the session with no transcript out"
need_eq "$(grep -c '^| orientation cost · head sid-rseedb' "$WTS")" "1" "one row per session id"
need_eq "$(grep -c 'orientation cost · head sid-seeded-head' "$WTS")" "0" "the session that left no transcript is not a head"
need_eq "$(grep -c '^| orientation cost' "$WTS")" "1" "orientation rows in all"
verdict "waste-table: a session that left no transcript is out of the head count, and the head-successor and run-resume of one session render a single orientation row"

fixture rnojson 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=nojson STUB_N=1"
starter --run rnojson --handoff "$HO" --budget 3.50 --out "$WORK/starter/rnojson-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_out "no JSON result line"
need_eq "$(mk field "$REC" head-exit band)" "60" "the last head-exit is the stub's hand-over"
need_eq "$(mk count "$REC" head-successor)" "3" "an error class start, then the hand-over"
verdict "supervisor: a .out with no JSON result line classifies as error (one successor), never as a limit"

fixture rdup 200
arm_resume rdup
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
(
  RCF=0
  env STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$H" _starter \
      --run rdup --handoff "$HO" --budget 3.50 --out "$WORK/starter/rdup-head-1.out" --wait-s 5 \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +3s --tick-s 1 \
      >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait_field "$REC" stop-condition which limit 20
mk append "$REC" '{"event":"head-resumed","session_id":"sid-other-supervisor","pid":1,"context":1,"waited_s":1,"reset_source":"x","resume_n":1}' >/dev/null
wait "$STARTER"
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "duplicate-resume" "duplicate-resume"
need_eq "$(cat "$WORK/stub-rdup.count")" "1" "no second start"
verdict "supervisor: a head-resumed written by another supervisor during the wait refuses the resume (duplicate-resume)"

# The planted input for both legs below is STUB_MODE=nolimit: a limit result whose text names
# no reset time. Without --probe the supervisor sends nothing and hands off; with it, it probes.
fixture rnoprobe 200
arm_resume rnoprobe
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
rm -f "$WORK/stub-probe.count"
RUNENV="STUB_MODE=nolimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rnoprobe --handoff "$HO" --budget 3.50 --out "$WORK/starter/rnoprobe-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1
need_rc 1
need_out "no reset time could be parsed and --probe was not passed"
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "the unparsed stop-condition"
need_eq "$(mk field "$REC" successor-aborted reason)" "limit-unparsed" "successor-aborted"
need_eq "$(mk count "$REC" head-resumed)" "0" "resumes without a probe"
need_eq "$(cat "$WORK/stub-rnoprobe.count")" "1" "one start, no second"
PROBES=0; [ -f "$WORK/stub-probe.count" ] && PROBES=$(cat "$WORK/stub-probe.count")
need_eq "$PROBES" "0" "probe calls without --probe"
verdict "supervisor: without --probe an unparsed limit sends no probe (0 calls to the stub) and ends limit-unparsed with the hand-off as the recovery"

fixture rprobe 200
arm_resume rprobe
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
rm -f "$WORK/stub-probe.count"
RUNENV="STUB_MODE=nolimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rprobe --handoff "$HO" --budget 3.50 --out "$WORK/starter/rprobe-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1 --probe
need_rc 0
need_eq "$(mk field "$REC" stop-condition action)" "probe every 1 s under the same login" "the probe plan"
need_eq "$(cat "$WORK/stub-probe.count")" "2" "one failed probe, one success"
[ "$(cat "$WORK/stub-probe.count")" -ge 1 ] || why="$why; --probe sent no probe at all"
case $(mk field "$REC" head-resumed reset_source) in probe*) : ;; *) why="$why; reset_source is not the probe" ;; esac
verdict "supervisor: with --probe and no reset time it probes under the same login until one succeeds, then resumes (2 calls ≥ 1: the positive control for the zero above)"

# A limit scoped to ONE model (the harness's own text: "reached your Fable limit … switch to another
# model") can be waited out by nobody and probed by nobody: a probe on another model answers for the
# wrong model. The supervisor records which=limit-model with the scope, aborts limit-model-fable, and
# sends no probe even with --probe (the rprobe leg above is the positive control with 2 calls).
fixture rmscope 200
arm_resume rmscope
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
rm -f "$WORK/stub-probe.count"
RUNENV="STUB_MODE=fablelimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rmscope --handoff "$HO" --budget 3.50 --out "$WORK/starter/rmscope-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1
need_rc 1
need_out "the Fable limit is exhausted"
need_eq "$(mk field "$REC" stop-condition which)" "limit-model" "the model-scoped stop-condition"
need_eq "$(mk field "$REC" stop-condition model)" "Fable" "the scope on the event"
need_eq "$(mk field "$REC" successor-aborted reason)" "limit-model-fable" "the abort reason"
need_eq "$(mk count "$REC" head-resumed)" "0" "resumes"
PROBES=0; [ -f "$WORK/stub-probe.count" ] && PROBES=$(cat "$WORK/stub-probe.count")
need_eq "$PROBES" "0" "probe calls without --probe"
verdict "supervisor: a model-scoped limit records limit-model with the scope and aborts limit-model-fable, no probe, no resume"

fixture rmscopeprobe 200
arm_resume rmscopeprobe
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
rm -f "$WORK/stub-probe.count"
RUNENV="STUB_MODE=fablelimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rmscopeprobe --handoff "$HO" --budget 3.50 --out "$WORK/starter/rmscopeprobe-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1 --probe
need_rc 1
need_eq "$(mk field "$REC" stop-condition which)" "limit-model" "which with --probe"
need_eq "$(mk count "$REC" head-resumed)" "0" "resumes with --probe"
PROBES=0; [ -f "$WORK/stub-probe.count" ] && PROBES=$(cat "$WORK/stub-probe.count")
need_eq "$PROBES" "0" "probe calls with --probe on a model-scoped limit"
verdict "supervisor: --probe is skipped for a model-scoped limit (0 calls to the stub against the 2 of the rprobe control): a probe on another model would resume the head on the exhausted one"

# ------------------------- the limit stop's head-exit (register entry 2026-09-14 05:13) -------
# A limit stop no wait can clear (limit-unparsed, limit-model) ends in successor-aborted, and a
# successor started by hand needs a head-exit after the head's start: the supervisor's 'head
# exited' observation is not one, so the supervisor writes the stop's head-exit before
# successor-aborted; hx_shape is the oracle.
printf -- '- Next: item 4 (gate: 4)\n- Needs: wiki/a.md:1-9\n- Decided: D1 because x\n' > "$WORK/pack-hx.md"
fixture rhxunp 200
arm_resume rhxunp
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=nolimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rhxunp --handoff "$HO" --budget 3.50 --out "$WORK/starter/rhxunp-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1
need_rc 1
need_out "head-exit recorded (band limit, 50,000 tokens (25 %), pid "
need_eq "$(hx_shape "$REC")" "1 exited,stop-condition,head-exit,successor-aborted" "the stop's head-exits and their order"
need_eq "$(mk count "$REC" head-exit)" "2" "head-exit events (the planted earlier one and the stop's)"
need_eq "$(mk field "$REC" successor-aborted reason)" "limit-unparsed" "the abort still follows"
need_eq "$(mk field "$REC" head-exit band)" "limit" "band"
need_eq "$(mk field "$REC" head-exit pack)" "false" "pack"
need_eq "$(mk field "$REC" head-exit pack_src)" "supervisor: the last head-written pack stands" "pack_src"
need_eq "$(mk field "$REC" head-exit which)" "limit-unparsed" "which"
need_eq "$(mk field "$REC" head-exit pid)" "$(mk field "$REC" head-successor pid)" "the pid is the stopped head's"
need_eq "$(mk field "$REC" head-exit context)" "50,000 tokens (25 %)" "context from the transcript"
need_eq "$(mk field "$REC" head-exit spent_usd)" "16.56" "spent_usd from the billed line"
need_eq "$(mk field "$REC" head-exit context_src)" "<no key context_src>" "no _src beside a figure that is there"
LINES_BEFORE=$(mk lines "$REC")
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rhxunp --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$187.66"
need_out "(head-exit)"
need_absent "PROBE FAILED"
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "the dry run wrote nothing"
verdict "limit-stop head-exit (must fire, register 2026-09-14 05:13): an unparsed limit stop leaves exactly one head-exit after the head's start, after its stop-condition and before successor-aborted, with band limit, pack false beside pack_src, the head's pid, context and spend; successor --dry-run then passes its premise at the envelope's remainder"

RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxunp --final --band limit --pid 7302 --meter-line "$METER" --inflight-file "$WORK/pack-hx.md" --dry-run
need_rc 0
need_out "head-exit already recorded (the supervisor's at "
need_absent '"event": "head-exit"'
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxunp --final --band limit --pid 7302 --meter-line "$METER" --inflight-file "$WORK/pack-hx.md"
need_rc 0
need_out "inflight rewritten"
need_out "head-exit already recorded (the supervisor's at "
need_absent "handoff: pid 7302"
need_eq "$(mk count "$REC" head-exit)" "2" "head-exit events after handoff --final (no second one for the stop)"
need_eq "$(mk field "$REC" head-exit pack_src)" "supervisor: the last head-written pack stands" "the last head-exit is still the supervisor's"
case $(mk section "$HO" "In flight") in *"D1 because x"*) : ;; *) why="$why; the pack was not written: $(mk section "$HO" "In flight")" ;; esac
# The control: the guard keys on a stop the supervisor observed ('head exited' after the head's
# start), never on any head-exit. With no observation after the start (a live head's own hand-off
# after a head-exit a head, successor or the successor path wrote) the call records its own.
fixture rhxctl 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-hxctl","pid":7303,"budget":3.5}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":"limit","context":"c","exit_class":"limit","pack":false,"pid":7303}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxctl --final --band limit --pid 7303 --meter-line "$METER" --inflight-file "$WORK/pack-hx.md"
need_rc 0
need_out "head-exit recorded (band limit"
need_absent "head-exit already recorded"
need_eq "$(mk count "$REC" head-exit)" "2" "the control records its head-exit"
verdict "limit-stop head-exit (must not fire twice): handoff --final --band limit after the supervisor's own head-exit writes the pack and no second head-exit, printing head-exit already recorded in the dry run and the real one, while with no observed stop after the head's start it records one (the control)"

fixture rhxmodel 200
arm_resume rhxmodel
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=fablelimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rhxmodel --handoff "$HO" --budget 3.50 --out "$WORK/starter/rhxmodel-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1
need_rc 1
need_out "head-exit recorded (band limit"
need_eq "$(hx_shape "$REC")" "1 exited,stop-condition,head-exit,successor-aborted" "the stop's head-exits and their order"
need_eq "$(mk count "$REC" head-exit)" "2" "head-exit events (the planted earlier one and the stop's)"
need_eq "$(mk field "$REC" stop-condition which)" "limit-model" "the stop-condition's which"
need_eq "$(mk field "$REC" head-exit which)" "limit-model" "the head-exit's which"
need_eq "$(mk field "$REC" successor-aborted reason)" "limit-model-fable" "the abort reason"
need_eq "$(mk field "$REC" head-exit band)" "limit" "band"
need_eq "$(mk field "$REC" head-exit pack)" "false" "pack"
need_eq "$(mk field "$REC" head-exit pid)" "$(mk field "$REC" head-successor pid)" "the pid is the stopped head's"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rhxmodel --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$187.66"
verdict "limit-stop head-exit (must fire, model-scoped): the Fable-limit stop text leaves the same shape, the stop-condition and the head-exit carrying which limit-model before successor-aborted limit-model-fable, and successor --dry-run passes its premise"

# An older record: the supervisor's 'head exited' observation after the head-successor, and no
# head-exit after it. The refusal names the missing head-exit and the repair; the repair then lets
# the premise pass; a head-successor with no observation after it keeps the old refusal.
fixture rhxold 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-hxold","pid":7301,"budget":3.5}' >/dev/null
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"limit","note":"a record written before the supervisor recorded the head-exit"}' >/dev/null
mk append "$REC" '{"event":"stop-condition","which":"limit-unparsed","lane":"head","action":"no reset time","note":"Usage limit reached for this session"}' >/dev/null
mk append "$REC" '{"event":"successor-aborted","reason":"limit-unparsed","note":"no reset time"}' >/dev/null
LINES_BEFORE=$(mk lines "$REC")
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rhxold --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_lines
need_out "the head-exit is missing"
need_out "no head-exit follows the supervisor's \`head exited\` observation"
need_out "handoff --final --band limit --run rhxold --pid 7301 --inflight-file"
need_absent "already follows the last head-exit"
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "the refusal wrote nothing"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --final --band limit --run rhxold --pid 7301 --meter-line "$METER" --inflight-file "$WORK/pack-hx.md"
need_rc 0
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rhxold --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "for pid 7301 (head-exit)"
fixture rhxold2 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-hxold2","pid":7304,"budget":3.5}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rhxold2 --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "already follows the last head-exit"
need_absent "the head-exit is missing"
verdict "successor on an older record: a 'head exited' observation with no head-exit after it is refused naming the missing head-exit and the repair handoff --final --band limit with the head's pid; that repair then lets the premise pass, and a head-successor with no observation after it keeps the old refusal (the control)"

# The premises of the change itself: no pid on the stop, no run-open (so no meter) and no head
# session, called on the helper directly, since both supervisor entries always hold a pid (the
# starter its own process, _supervise its required --pid).
fixture rhxpid 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-hxpid","pid":7305,"budget":3.5}' >/dev/null
RC=0
"$PY" - "$H" "$REC" "$METER" <<'HXPID' >"$WORK/hxpid.txt" 2>&1 || RC=$?
import importlib.util, json, sys, types
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
evs = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
a = types.SimpleNamespace(run="rhxpid", meter_line=sys.argv[3], handoff=None)
ev = mod.limit_exit_event(a, evs, "sid-hxpid", len(evs) - 1, None, 0.0, "limit-unparsed")
print("pid=%s | %s | spent=%s" % (json.dumps(ev["pid"]), ev.get("pid_src"), ev["spent_usd"]))
bare = [e for e in evs if e.get("event") != "run-open"]
a2 = types.SimpleNamespace(run="rhxpid", meter_line=None, handoff=None)
ev2 = mod.limit_exit_event(a2, bare, None, len(bare) - 1, None, 0.0, "limit-model")
print("spent=%s | %s | context=%s | %s | handoff=%s" % (
    json.dumps(ev2["spent_usd"]), ev2.get("spent_src"), json.dumps(ev2["context"]),
    ev2.get("context_src"), ev2.get("handoff", "absent")))
HXPID
cp "$WORK/hxpid.txt" "$WORK/both"
need_rc 0
need_eq "$(sed -n 1p "$WORK/hxpid.txt")" "pid=null | none: this supervisor holds no pid for the head | spent=16.56" "no pid on the stop"
need_eq "$(sed -n 2p "$WORK/hxpid.txt")" "spent=null | none: the record carries no run-open, so the meter has no run to read | context=null | none: no head session in the record | handoff=absent" "no run-open and no head session"
need_absent "Traceback"
verdict "limit-stop head-exit premise (no pid, no run-open, no head session): the helper writes pid null with pid_src, and on a record with no run-open spent_usd and context null each with its _src and no hand-off path, without raising"

NOMETER="$WORK/nometer"
rm -rf "$NOMETER"
mkdir -p "$NOMETER"
cp "$H" "$NOMETER/handsoff.py"
# CR-A3-1 H1 (spec), E1: the copied supervisor still needs its shared record-lock module.
cp "$LANE_PY" "$NOMETER/lane.py"
fixture rhxmeter 200
arm_resume rhxmeter
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RC=0
env STUB_MODE=nolimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$NOMETER/handsoff.py" _starter \
    --run rhxmeter --handoff "$HO" --budget 3.50 --out "$WORK/starter/rhxmeter-head-1.out" --wait-s 5 \
    --harness-bin "$WORK/bin/stubhead" --probe-interval-s 1 --tick-s 1 >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 1
need_nofile "$NOMETER/fable-share.py"
need_eq "$(hx_shape "$REC")" "1 exited,stop-condition,head-exit,successor-aborted" "the stop's head-exits and their order"
need_eq "$(mk field "$REC" head-exit spent_usd)" "null" "no spend without a billed line"
need_eq "$(mk field "$REC" head-exit spent_src)" "none: failed: fable-share.py not found beside handsoff.py" "spent_src names why"
need_eq "$(mk field "$REC" head-exit context)" "50,000 tokens (25 %)" "the context is still measured (the control)"
need_eq "$(mk field "$REC" successor-aborted reason)" "limit-unparsed" "the abort still follows"
need_absent "Traceback"
verdict "limit-stop head-exit premise (no meter): a supervisor with no fable-share.py beside it and no --meter-line writes spent_usd null with spent_src naming the meter's failure, measures the context all the same, and still aborts limit-unparsed"

fixture rhxnotx 200
arm_resume rhxnotx
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=nolimit STUB_N=1 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rhxnotx --handoff "$HO" --budget 3.50 --out "$WORK/starter/rhxnotx-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1
need_rc 1
need_eq "$(hx_shape "$REC")" "1 exited,stop-condition,head-exit,successor-aborted" "the stop's head-exits and their order"
need_eq "$(mk field "$REC" head-exit context)" "null" "no context without a transcript"
case $(mk field "$REC" head-exit context_src) in
  "none: transcript missing: "*) : ;;
  *) why="$why; context_src does not name the missing transcript: $(mk field "$REC" head-exit context_src)" ;;
esac
need_eq "$(mk field "$REC" head-exit spent_usd)" "16.56" "the spend is still there (the control)"
need_eq "$(mk field "$REC" successor-aborted reason)" "limit-unparsed" "the abort still follows"
need_absent "Traceback"
verdict "limit-stop head-exit premise (no transcript): a head that left no transcript gets context null with context_src naming the missing transcript, the spend from the billed line, and the abort still follows"

# The hand-run wait-reset shares the two outcomes but not the code, and holds no head's pid while
# its --lane may name any lane: it records the stop-condition and writes no head-exit.
fixture rhxwait 200
run wait-reset --run rhxwait --lane head --stop-text "Usage limit reached for this session"
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "the unparsed branch ran (the control)"
need_eq "$(mk count "$REC" head-exit)" "0" "head-exit events after the unparsed wait"
run wait-reset --run rhxwait --lane head --stop-text "You've reached your Fable limit. Switch to another model, or manage usage credits at claude.ai/settings/usage, to continue."
need_rc 7
need_eq "$(mk field "$REC" stop-condition which)" "limit-model" "the model-scoped branch ran (the control)"
need_eq "$(mk count "$REC" head-exit)" "0" "head-exit events after the model-scoped wait"
verdict "wait-reset (must not fire): a hand-run wait records the limit-unparsed and limit-model stop-conditions and exits 7 but writes no head-exit, since it holds no head's pid and its --lane may name any lane"

# review finding 2, the stop's identity: a head-resumed after the supervisor's head-exit starts a
# new head, so that head's own successor call and final hand-off record its own exit (the old pid
# is never reused), and a repeated repair after that head's observed stop writes none.
fixture rhxres 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-hxres","pid":7310,"budget":3.5}' >/dev/null
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"limit","note":"planted: the stop"}' >/dev/null
mk append "$REC" '{"event":"stop-condition","which":"limit-unparsed","lane":"head","action":"planted","note":"planted"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":"limit","which":"limit-unparsed","exit_class":"limit","context":null,"context_src":"none: planted","pack":false,"pack_src":"supervisor: the last head-written pack stands","spent_usd":5,"pid":7310}' >/dev/null
mk append "$REC" '{"event":"successor-aborted","reason":"limit-unparsed","note":"planted"}' >/dev/null
mk append "$REC" '{"event":"head-resumed","session_id":"sid-hxres","pid":7311,"context":1,"waited_s":1,"reset_source":"resume-head (by hand, after the reset)","resume_n":1}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rhxres --dry-run --pid 7311 --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "successor: pid 7311 (arg)"
need_out "for pid 7311 (head-exit)"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxres --final --band 80 --pid 7311 --meter-line "$METER" --inflight-file "$WORK/pack-hx.md" --dry-run
need_rc 0
need_out '"pid": 7311'
need_absent "head-exit already recorded"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxres --final --band 80 --pid 7311 --meter-line "$METER" --inflight-file "$WORK/pack-hx.md"
need_rc 0
need_out "head-exit recorded (band 80"
need_eq "$(mk count "$REC" head-exit)" "2" "the resumed head's own head-exit beside the supervisor's"
need_eq "$(mk field "$REC" head-exit pid)" "7311" "the resumed head's pid"
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"completed","note":"planted: the resumed head stopped"}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxres --final --band 80 --pid 7311 --meter-line "$METER" --inflight-file "$WORK/pack-hx.md"
need_rc 0
need_out "head-exit already recorded (the one at "
need_eq "$(mk count "$REC" head-exit)" "2" "head-exit events after a repeated repair of the resumed head's observed stop"
verdict "limit-stop head-exit, the stop's identity (review finding 2): after the supervisor's head-exit a head-resumed starts a new head, whose successor call and final hand-off record its own exit with its own pid 7311 (dry run and real), and a repeated repair after that head's observed stop writes none"

# review finding 2, the overlap: a hand repair that lands while the supervisor's meter runs. The
# meter is a stand-in beside a copy of handsoff.py that sleeps 6 s before its billed line (set by
# judgement, unmeasured: the repair below takes about a second), and the repair runs as soon as
# the stop-condition is on the record, so it lands inside that sleep. Timing-dependent by design.
SLOW="$WORK/slowmeter"
rm -rf "$SLOW"
mkdir -p "$SLOW"
cp "$H" "$SLOW/handsoff.py"
# CR-A3-1 H1 (spec), E1: the copied supervisor still needs its shared record-lock module.
cp "$LANE_PY" "$SLOW/lane.py"
printf '%s\n' 'import time' 'time.sleep(6)' "print('$METER')" > "$SLOW/fable-share.py"
fixture rhxrace 200
arm_resume rhxrace
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
(
  RCF=0
  env STUB_MODE=nolimit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$SLOW/handsoff.py" _starter \
      --run rhxrace --handoff "$HO" --budget 3.50 --out "$WORK/starter/rhxrace-head-1.out" --wait-s 5 \
      --harness-bin "$WORK/bin/stubhead" --probe-interval-s 1 --tick-s 1 >"$WORK/starter-out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/starter-rc"
) &
STARTER=$!
wait_field "$REC" stop-condition which limit-unparsed 20
RACEPID=$(mk field "$REC" head-successor pid)
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxrace --final --band limit --pid "$RACEPID" --meter-line "$METER" --inflight-file "$WORK/pack-hx.md"
need_rc 0
need_out "head-exit recorded (band limit"
REPAIR_WHY=$why; why=""
wait "$STARTER"
why=$REPAIR_WHY
RC=$(cat "$WORK/starter-rc")
cp "$WORK/starter-out" "$WORK/both"
need_rc 1
need_out "while the meter ran: none written"
need_eq "$(hx_shape "$REC")" "1 exited,stop-condition,head-exit,successor-aborted" "one head-exit for the stop with the repair inside the meter"
need_eq "$(mk field "$REC" head-exit pack)" "true" "the one head-exit is the repair's"
need_eq "$(mk field "$REC" successor-aborted reason)" "limit-unparsed" "the abort still follows"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rhxrace --final --band limit --pid "$RACEPID" --meter-line "$METER" --inflight-file "$WORK/pack-hx.md"
need_rc 0
need_out "head-exit already recorded (the one at "
need_eq "$(hx_shape "$REC")" "1 exited,stop-condition,head-exit,successor-aborted" "still one head-exit after a repeated repair"
verdict "limit-stop head-exit, the overlap (review finding 2): a repair landing while the supervisor's meter runs is the stop's one head-exit, the supervisor re-checking under the record lock and writing none, its abort exit 1 unchanged, and a repeated repair after it writes none"

# ------------------------------------------------------------------------ supervise -------
fixture rsup 200
run supervise --run rsup --pid 999999 --dry-run
need_rc 2
need_out "is not alive"
verdict "supervise: an explicit --pid that is not alive is refused — a stopped run has no head to attach to (C2 L5)"
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"done"}' > "$WORK/rsup.out"
sleep 3 &
SPID=$!
# The head calls supervise about itself early; its hand-off (head-exit, then its own successor
# call's head-successor) lands later, before its process ends.
run supervise --run rsup --pid "$SPID" --out "$WORK/rsup.out" --harness-bin "$WORK/bin/stubhead" --tick-s 1
need_rc 0
need_out "supervise: pid $SPID session sid-rsup · out $WORK/rsup.out · detached pid"
need_eq "$(mk field "$REC" supervise mode)" "attached" "supervise mode"
need_eq "$(mk field "$REC" supervise pid)" "$SPID" "supervised pid"
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":5}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-next","pid":1,"budget":1.0}' >/dev/null
wait "$SPID"
wait_field "$REC" observation what "supervisor ended" 20
case $(mk field "$REC" observation note) in handed-over*) : ;; *) why="$why; not handed-over: $(mk field "$REC" observation note)" ;; esac
verdict "supervise: attaches to a running pid, detaches at once, and its loop ends handed-over when the pid dies"

RUNENV="PATH=$WORK/psnone:$PATH"
run supervise --run rsup --out "$WORK/rsup.out"
need_rc 2
need_out "no harness ancestor to supervise"
need_lines
verdict "supervise: no claude ancestor and no --pid is refused (exit 2)"

fixture rsup2 200
mk append "$REC" '{"event":"head-exit","band":60,"context":"c"}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-s2","pid":1,"budget":1.0,"out":"/tmp/from-record.out"}' >/dev/null
run supervise --run rsup2 --pid 1 --dry-run
need_rc 0
need_out "out /tmp/from-record.out (head-successor)"
fixture rsup3 200
printf 'x\n' > "$STORE/spawn-records/rsup3-head-1.out"; sleep 1
printf 'x\n' > "$STORE/spawn-records/rsup3-head-2.out"
run supervise --run rsup3 --pid 1 --dry-run
need_out "out $REALSTORE/spawn-records/rsup3-head-2.out (newest .out)"
fixture rsup4 200
run supervise --run rsup4 --pid 1 --dry-run
need_out "out none (transcript-only)"
verdict "supervise: the .out comes from the record's head-successor, else the newest <run>-head-*.out, else none"

# The supervisor never opts into the probe on its own: the detached command carries --probe
# only when this caller passed it (owner ruling 2026-09-06).
fixture rsupprobe 200
run supervise --run rsupprobe --pid 1 --dry-run
need_rc 0
need_out "would detach"
if grep -qE -- '--probe( |$)' "$WORK/both"; then why="$why; the detached command carries --probe with no flag given"; fi
run supervise --run rsupprobe --pid 1 --probe --dry-run
need_rc 0
grep -qE -- '--probe( |$)' "$WORK/both" || why="$why; --probe was not forwarded to the detached supervisor"
verdict "supervise: --probe reaches the detached supervisor only when the caller passes it (control: the same command without the flag carries none)"

# ------------------------------------------------------------------------ heartbeat -------
fixture rhb 200
run heartbeat --run rhb --minutes 0.02
need_rc 0
need_out "heartbeat: rhb · 0.02 min · the cache is refreshed by this re-invocation; re-arm if still idle"
need_eq "$(mk count "$REC" heartbeat)" "2" "armed then beat"
need_eq "$(mk field "$REC" heartbeat action)" "beat" "the last action"
need_nofile "$STORE/spawn-records/rhb-heartbeat.pid"
verdict "heartbeat: arms, sleeps --minutes (a float), prints the beat line and records armed then beat"

fixture rhb2 200
( "$PY" -B "$H" heartbeat --run rhb2 --minutes 1 --tick-s 0.2 >"$WORK/hb-bg.out" 2>&1 ) &
HBW=$!
sleep 1
run heartbeat --run rhb2 --minutes 1
need_rc 0
need_out "heartbeat: already armed (pid "
need_out " min left)"
need_eq "$(mk field "$REC" heartbeat action)" "already-armed" "already-armed"
run heartbeat --run rhb2 --stop
need_rc 0
need_file "$STORE/spawn-records/rhb2-heartbeat.stop"
wait "$HBW"
need_eq "$(cat "$WORK/hb-bg.out")" "" "the stopped timer prints nothing"
need_eq "$(mk field "$REC" heartbeat action)" "stopped" "the timer's stopped event"
need_nofile "$STORE/spawn-records/rhb2-heartbeat.pid"
verdict "heartbeat: a second arming is refused while one is alive; --stop ends the timer quietly"

fixture rhb3 200
sleep 1 &
SP=$!
run heartbeat --run rhb3 --minutes 1 --parent-pid "$SP" --tick-s 0.2
need_rc 0
need_eq "$(cat "$WORK/out")" "" "an orphaned timer prints nothing"
need_eq "$(mk field "$REC" heartbeat action)" "orphaned" "orphaned"
wait "$SP"
verdict "heartbeat: the timer ends quietly (action orphaned) when its parent is gone"

# ------------------------------------------------------------------ waste-table (D36) ------
# Two boundaries (the second without `rewrites`), three gates (the first carrying the
# orientation figure), one lane closed `limit` and one closed `completed`. The expected row
# count is arithmetic, not a memory: 5 waste fields × 2 boundaries + 2 billed lines + 1 heads'
# total + 1 run total + 3 context rows + 1 orientation row + 1 lost-lane row = 19.
fixture rwaste 200
mk append "$REC" '{"event":"gate","item":"one","context":100000,"percent":10,"band":0,"metered":true,"orientation_tokens":40000}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L1","exit_class":"limit","total_cost_usd":2.5}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L2","exit_class":"completed","total_cost_usd":1.0}' >/dev/null
# The billed line is substituted by printf: inside double quotes its `$12.34` would expand to
# nothing and the payload would be written wrong without an error (the shell rule).
B1=$(printf '{"event":"phase-boundary","from":"1","to":"2","meter":"%s","idle_min":9.5,"denials":3,"over_cap_reports":1,"respawn_cost_usd":5.0,"rewrites":3}' "$METER")
mk append "$REC" "$B1" >/dev/null
mk append "$REC" '{"event":"gate","item":"two","context":140000,"percent":14,"band":0,"metered":true}' >/dev/null
B2=$(printf '{"event":"phase-boundary","from":"2","to":"3","meter":"%s","idle_min":0.0,"denials":0,"over_cap_reports":0,"respawn_cost_usd":0.0}' "$METER")
mk append "$REC" "$B2" >/dev/null
mk append "$REC" '{"event":"gate","item":"three","context":300000,"percent":30,"band":0,"metered":true}' >/dev/null
WT="$WORK/rwaste-table.md"
run waste-table --run rwaste --out "$WT"
need_rc 0
need_out "waste-table: 19 rows from 2 boundaries, 3 gates, 2 lanes"
need_eq "$(grep -c . "$WORK/out")" "1" "stdout lines"
need_file "$WT"
need_eq "$(mk rows "$WT" "Waste table")" "19" "rendered rows"
need_eq "$(grep -c 'rewrites after a lapsed cache · 2 → 3.*| field absent |' "$WT")" "1" "the absent rewrites field"
need_eq "$(grep -c 'orientation cost · head sid-rwaste | 40,000 tokens · gate.orientation_tokens' "$WT")" "1" "the orientation row"
need_eq "$(grep -c 'Kinds are mechanical' "$WT")" "1" "the legend"
need_eq "$(grep -c 'lost lane · L1 · exit class limit | \$2.50 · lane-closed.total_cost_usd' "$WT")" "1" "the lost lane"
need_eq "$(grep -c 'lost lane · L2' "$WT")" "0" "a completed lane is not a lost lane"
need_eq "$(grep -c 'no waste found' "$WT")" "0" "no zero-findings row when a figure is positive"
need_eq "$(grep -c 'heads. total (shown sum) | \$16.56 = \$16.56' "$WT")" "1" "the heads' total as a shown sum"
need_eq "$(grep -c 'run total (recorded run spend) | unrecorded · no phase-boundary or run-close on the record carries run_spend_usd' "$WT")" "1" "boundaries planted without the run figure: the run total says so and adds nothing to the heads' total"
need_eq "$(grep -c 'context · item one, to the gate of item two at .* | +40,000 tokens · gate context 100,000 → 140,000' "$WT")" "1" "context per item as a gate delta, on the item that grew"
verdict "waste-table: 19 rows from the record alone — a row per waste field per boundary, the billed lines with the heads' total and the run total, the gate deltas, the orientation figure and the lost lane"

run waste-table --run rwaste
need_rc 0
need_file "$REALSTORE/spawn-records/rwaste-waste-table.md"
WTD="$WORK/rwaste-dry.md"
run waste-table --run rwaste --out "$WTD" --dry-run
need_rc 0
need_out "dry run"
need_out "19 rows from 2 boundaries"
need_nofile "$WTD"
verdict "waste-table: the default path is <store>/spawn-records/<run>-waste-table.md; --dry-run prints the counts and writes nothing"

# The zero-findings control, and a gate series with one gate (no consecutive pair to difference).
fixture rwaste2 200
mk append "$REC" '{"event":"gate","item":"one","context":100000,"percent":10,"band":0,"metered":true}' >/dev/null
WT2="$WORK/rwaste2-table.md"
run waste-table --run rwaste2 --out "$WT2"
need_rc 0
need_out "0 boundaries, 1 gates, 0 lanes"
need_eq "$(mk rows "$WT2" "Waste table")" "4" "rendered rows"
need_eq "$(grep -c 'no waste found' "$WT2")" "1" "the zero-findings row"
need_eq "$(grep -c 'no phase-boundary events' "$WT2")" "2" "the header line and the row"
need_eq "$(grep -c 'one gate event only' "$WT2")" "1" "one gate: no pair to difference"
need_eq "$(grep -c 'field absent' "$WT2")" "1" "the orientation field is absent, not zero"
verdict "waste-table: no boundary events still renders the gate, orientation and lane rows, says 'no phase-boundary events' and ends with the zero-findings row naming what was searched"

# A boundary carrying no waste field at all: five `field absent` rows, never five zeroes.
fixture rwaste3 200
mk append "$REC" '{"event":"phase-boundary","from":"1","to":"2"}' >/dev/null
WT3="$WORK/rwaste3-table.md"
run waste-table --run rwaste3 --out "$WT3"
need_rc 0
need_eq "$(grep -c '| field absent |' "$WT3")" "6" "five waste fields and the billed line"
need_eq "$(grep -c '0 min' "$WT3")" "0" "a missing field never reads as a measured zero"
need_eq "$(grep -c 'no waste found' "$WT3")" "1" "zero findings when every field is absent"
need_eq "$(grep -c 'no boundary billed line carried a .session' "$WT3")" "1" "the total says so rather than summing to zero"
rm -f "$STORE/spawn-records/rwaste9.jsonl"
run waste-table --run rwaste9
need_rc 2
need_out "PROBE FAILED"
need_lines
need_nofile "$REALSTORE/spawn-records/rwaste9-waste-table.md"
verdict "waste-table: a boundary lacking every field renders 'field absent' and no zero; no record is a premise failure (exit 2) that writes nothing"

# ----------------------------------------------------------- extract-transcript (D36) ------
mk xscript sid-extract >/dev/null
EX="$WORK/extract"
run extract-transcript --session sid-extract --out "$EX"
need_rc 0
need_eq "$(grep -c . "$WORK/out")" "1" "stdout lines"
need_out "2 turns (1 human, 1 assistant) of 7 records"
need_eq "$(mk json "$EX/counts.json" session)" "sid-extract" "session"
need_eq "$(mk json "$EX/counts.json" records)" "7" "records"
need_eq "$(mk json "$EX/counts.json" human_turns)" "1" "human turns"
need_eq "$(mk json "$EX/counts.json" assistant_turns)" "1" "assistant turns"
need_eq "$(mk json "$EX/counts.json" extracted)" "2" "extracted"
need_eq "$(mk json "$EX/counts.json" excluded.tool_result)" "1" "tool results excluded"
need_eq "$(mk json "$EX/counts.json" excluded.meta)" "1" "isMeta injections excluded"
need_eq "$(mk json "$EX/counts.json" excluded.notification)" "1" "harness injections excluded"
need_eq "$(mk json "$EX/counts.json" excluded.unparseable)" "1" "the torn line is counted, not fatal"
need_eq "$(grep -c '^## turn 1 · human · 2026-09-05T20:00:00Z' "$EX/turns.md")" "1" "turn 1"
need_eq "$(grep -c '^## turn 2 · assistant · 2026-09-05T20:00:10Z' "$EX/turns.md")" "1" "turn 2"
need_eq "$(grep -c 'the assistant answers in prose' "$EX/turns.md")" "1" "positive control: the assistant prose is there"
need_eq "$(grep -c 'tool output text' "$EX/turns.md")" "0" "the tool result is out"
need_eq "$(grep -c 'Base directory for this skill' "$EX/turns.md")" "0" "the Skill-tool injection is out"
need_eq "$(grep -c 'system-reminder' "$EX/turns.md")" "0" "the harness injection is out"
verdict "extract-transcript: the human turn and the assistant prose are extracted in order; the tool result, the isMeta injection and the harness injection are counted out and a torn line is not fatal"

ALT="$WORK/altprojects"
mk xscript sid-alt "$ALT" >/dev/null
run extract-transcript --session sid-alt --out "$WORK/alt" --projects-root "$ALT"
need_rc 0
need_out "2 turns (1 human, 1 assistant)"
run extract-transcript --session sid-nothere --out "$WORK/none"
need_rc 2
need_out "PROBE FAILED"
need_lines
need_nofile "$WORK/none/turns.md"
mk metascript sid-onlymeta >/dev/null
run extract-transcript --session sid-onlymeta --out "$WORK/onlymeta"
need_rc 0
need_out "0 turns (0 human, 0 assistant) of 3 records"
need_eq "$(mk json "$WORK/onlymeta/counts.json" excluded.meta)" "2" "two isMeta records"
need_eq "$(mk json "$WORK/onlymeta/counts.json" excluded.notification)" "1" "one harness injection"
need_eq "$(mk json "$WORK/onlymeta/counts.json" extracted)" "0" "nothing to extract"
verdict "extract-transcript: --projects-root finds a transcript elsewhere; a missing transcript is a premise failure (exit 2); a transcript of injections only extracts nothing and still exits 0"

# The two harness shapes: a resume replay sent as one user record, and the synthetic stop
# record. Both legs run against the same extraction, so each carries the other's counts.
mk replayscript sid-replay >/dev/null
RP="$WORK/replay"
run extract-transcript --session sid-replay --out "$RP"
need_rc 0
need_eq "$(grep -c . "$WORK/out")" "1" "stdout lines"
need_out "5 turns (3 human, 2 assistant) of 7 records"
need_out "replay 1"
need_eq "$(mk json "$RP/counts.json" excluded.replay)" "1" "the replay with no owner message is the one excluded (register 2026-09-07: one bucket per record)"
need_eq "$(mk json "$RP/counts.json" notes.replay_trimmed)" "2" "the two trimmed replays are human turns, noted and not also excluded"
need_eq "$(mk json "$RP/counts.json" human_turns)" "3" "the plain turn, the replay's own message and the quoted prompt"
need_eq "$(grep -c 'what do you make of it' "$RP/turns.md")" "1" "residue: a typed prompt opening with a quoted conversation keeps the owner's trailing words"
need_eq "$(grep -c "the owner's real message" "$RP/turns.md")" "1" "the trailing owner message is kept"
need_eq "$(grep -c 'an earlier replayed turn' "$RP/turns.md")" "0" "the replayed turns are out"
need_eq "$(grep -c 'an earlier replayed answer' "$RP/turns.md")" "0" "the replayed answers are out"
need_eq "$(grep -c 'a replay with no human marker' "$RP/turns.md")" "0" "a replay with no owner message is dropped whole"
need_eq "$(grep -c 'the plain human turn' "$RP/turns.md")" "1" "positive control: an ordinary human turn is untouched"
need_eq "$(grep -c 'were trimmed to the text after their last' "$RP/turns.md")" "1" "the header states the trimming"
verdict "extract-transcript: a resume replay keeps only its trailing owner message as a human turn (notes.replay_trimmed), and one carrying no owner message is dropped under excluded.replay"

need_eq "$(mk json "$RP/counts.json" excluded.synthetic)" "1" "the synthetic record is counted out"
need_eq "$(mk json "$RP/counts.json" assistant_turns)" "2" "the prose turn and the control record"
need_eq "$(grep -c 'No response requested.' "$RP/turns.md")" "1" "positive control: the same words from a real model are still a turn"
need_eq "$(grep -c 'the assistant answers in prose' "$RP/turns.md")" "1" "positive control: the assistant prose is there"
need_out "synthetic 1"
verdict "extract-transcript: an assistant record whose model opens '<synthetic' is skipped and counted, while the same stop words from a real model stay a turn (the skip keys on the model field)"

# ------------------------------------------------- the reflect skill's proposed amendment ---
# The diff is a build-time artefact: while it is staged the leg dry-runs it against a copy of
# the skill file (never the file itself), and once the head has applied it the same leg reads
# the paragraph in the installed file. Point REFLECT_DIFF at the staged diff until then.
# The reflect skill's directory: beside the target's own skill directory by default, and
# REFLECT_DIR when the target is a staged copy outside the skill tree.
REFLECT_DIR=${REFLECT_DIR:-$SKILL_DIR/../reflect}
REFLECT_SKILL=${REFLECT_SKILL:-$REFLECT_DIR/SKILL.md}
RDIFF=${REFLECT_DIFF:-$SKILL_DIR/reflect-skill.diff}
[ -f "$RDIFF" ] || RDIFF=$(dirname "$SRC")/reflect-skill.diff
PROOT="$WORK/patchroot"
rm -rf "$PROOT"
mkdir -p "$PROOT/.claude/skills/reflect"
if [ -f "$RDIFF" ] && [ -f "$REFLECT_SKILL" ]; then
  command -v patch >/dev/null || why="$why; no patch on PATH: the dry-run legs cannot run"
  cp "$REFLECT_SKILL" "$PROOT/.claude/skills/reflect/SKILL.md"
  RC=0; (cd "$PROOT" && patch -p0 --dry-run < "$RDIFF") >"$WORK/both" 2>&1 || RC=$?
  need_rc 0
  need_out "SKILL.md"
  D1=$(grep -c 'waste-table' "$RDIFF")
  [ "$D1" -ge 1 ] || why="$why; the diff never names waste-table ($D1)"
  D2=$(grep -c 'Hands-off boundaries' "$RDIFF")
  [ "$D2" -ge 1 ] || why="$why; the diff never names the paragraph ($D2)"
  verdict "reflect skill: the staged diff applies to the installed file with patch -p0 --dry-run"
  # The control: the anchored span is cut out of the copy, so the hunk has nothing to match.
  # A one-word edit is not the control, since patch applies with fuzz and would still land it.
  "$PY" -c 'import sys; p = sys.argv[1]; lines = open(p, encoding="utf-8").read().split("\n"); open(p, "w", encoding="utf-8").write("\n".join(lines[:100]) + "\n")' \
        "$PROOT/.claude/skills/reflect/SKILL.md"
  RC=0; (cd "$PROOT" && patch -p0 --dry-run < "$RDIFF") >"$WORK/both" 2>&1 || RC=$?
  [ "$RC" = "0" ] && why="$why; the diff applied to a skill file whose anchored span had gone"
  need_out "hunks failed"
  verdict "reflect skill: the same diff is refused when the span it anchors on has gone from the file (the control for the leg above)"
elif [ -f "$REFLECT_SKILL" ]; then
  P1=0; grep -q 'Hands-off boundaries' "$REFLECT_SKILL" && P1=1
  [ "$P1" = "1" ] || why="$why; no staged diff at $RDIFF and no applied paragraph in $REFLECT_SKILL (pass REFLECT_DIFF=<path>)"
  verdict "reflect skill: the hands-off boundaries paragraph is in the installed file (no staged diff to dry-run)"
  P2=0; grep -q 'never applies to cross runs' "$REFLECT_SKILL" && P2=1
  [ "$P2" = "1" ] || why="$why; positive control: the cross-run sentence is missing from $REFLECT_SKILL"
  verdict "reflect skill: the cross-reflection section is readable (the control for the leg above)"
else
  why="$why; no reflect SKILL.md at $REFLECT_SKILL and no staged diff at $RDIFF"
  verdict "reflect skill: the diff's target is readable"
  why="$why; the control cannot run without the skill file"
  verdict "reflect skill: the control for the leg above"
fi

# ------------------------------------------------------- reflect-inputs (D36, the P4 lane) --
# The blind reflector's whole input set in one directory: the extraction, the waste table and a
# copy of the run record with the spawner's control pre-registration (an observation whose phase
# starts `controls`) dropped and the brief-and-plant keys stripped. The source record carries
# both, which is this leg's positive control.
fixture rrefl 200
mk xscript sid-rrefl >/dev/null
mk waste "$REC" rrefl "$WORK/no-such-report.md" >/dev/null
mk append "$REC" '{"event":"observation","phase":"controls-B1","what":"pre-registered control","note":"the case planted for the lane"}' >/dev/null
mk append "$REC" '{"event":"observation","phase":"reflection-b1","what":"a phase the copy keeps"}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"B1","class":"builder","brief":"the brief text","brief_copy":"/tmp/brief-copy.md","controls_checked":true,"plant":"the case planted for the lane"}' >/dev/null
RD="$WORK/reflect-in"
run reflect-inputs --run rrefl --session sid-rrefl --out "$RD"
need_rc 0
need_eq "$(grep -c . "$WORK/out")" "1" "stdout lines"
need_out "reflect-inputs: 2 turns (1 human, 1 assistant) of 7 records"
need_out "1 controls observation(s) dropped"
need_file "$RD/turns.md"
need_file "$RD/counts.json"
need_file "$RD/waste-table.md"
need_file "$RD/record-filtered.jsonl"
need_eq "$(grep -c '^# Waste table · run rrefl' "$RD/waste-table.md")" "1" "the waste table's own title"
need_eq "$(mk json "$RD/counts.json" extracted)" "2" "the extraction's own counts"
need_eq "$(grep -c 'controls_checked' "$RD/record-filtered.jsonl")" "0" "controls_checked keys in the copy"
need_eq "$(grep -c 'controls-B1' "$RD/record-filtered.jsonl")" "0" "controls-phase observations in the copy"
need_eq "$(grep -c 'controls_checked' "$REC")" "1" "positive control: the source record carries the key"
need_eq "$(grep -c 'controls-B1' "$REC")" "1" "positive control: the source record carries the observation"
need_eq "$(grep -c 'reflection-b1' "$RD/record-filtered.jsonl")" "1" "an observation of another phase is kept"
need_eq "$(grep -c 'the brief text' "$RD/record-filtered.jsonl")" "0" "the brief is stripped"
need_eq "$(grep -c 'brief-copy.md' "$RD/record-filtered.jsonl")" "0" "the brief copy is stripped"
need_eq "$(grep -c 'the case planted for the lane' "$RD/record-filtered.jsonl")" "0" "the plant is stripped"
need_eq "$(grep -c 'the case planted for the lane' "$REC")" "2" "positive control: the source record carries both"
need_eq "$(grep -c '"lane": "B1"' "$RD/record-filtered.jsonl")" "1" "positive control: the stripped event itself is kept"
need_eq "$(mk lines "$RD/record-filtered.jsonl")" "7" "events kept (8 in the record, one controls observation dropped)"
need_eq "$(mk lines "$REC")" "9" "the record after its reflect-inputs event"
need_eq "$(grep -c 'reflect-inputs' "$RD/record-filtered.jsonl")" "0" "the copy is written before the event that records it"
need_eq "$(mk field "$REC" reflect-inputs out)" "$(real "$RD")" "the event names the directory"
need_eq "$(mk field "$REC" reflect-inputs session)" "sid-rrefl" "the event names the session"
verdict "reflect-inputs: the four files land in the granted directory, the filtered copy holds no controls-phase observation and no controls_checked, brief or plant key, and every other event survives"

run reflect-inputs --run rrefl --session sid-rrefl --out "$STORE/spawn-records/blind"
need_rc 2
need_out "is inside the run store"
need_lines
need_nofile "$REALSTORE/spawn-records/blind/turns.md"
run reflect-inputs --run rrefl --session sid-rrefl --out "$PROJECTS/blind"
need_rc 2
need_out "is inside the projects root"
need_lines
need_nofile "$PROJECTS/blind/turns.md"
need_eq "$(mk count "$REC" reflect-inputs)" "1" "no event from either refusal (the control: the granted directory above recorded one)"
verdict "reflect-inputs: an --out inside the run store or the projects root is a premise failure (exit 2) that writes nothing and records nothing"

DRD="$WORK/reflect-dry"
run reflect-inputs --run rrefl --session sid-rrefl --out "$DRD" --dry-run
need_rc 0
need_out "reflect-inputs: dry run"
need_out "would write turns.md, counts.json, waste-table.md and record-filtered.jsonl"
need_out "2 turns (1 human, 1 assistant) of 7 records"
need_nofile "$DRD/turns.md"
need_nofile "$DRD/record-filtered.jsonl"
need_eq "$(mk count "$REC" reflect-inputs)" "1" "no second event from the dry run (the control: the write above recorded one)"
verdict "reflect-inputs --dry-run: the same counts, no file written and no event recorded"

# ---- G13 (register 2026-10-15 01:33 f): a second run into one --out replaced the first's files --
# The two sessions' transcripts differ, so a replaced turns.md changes its bytes; the planted case
# is the repeated output, the control a first run into the same fresh directory, which writes.
fixture rrout 200
mk xscript sid-rrout-a >/dev/null
mk xscript sid-rrout-b >/dev/null
ROD="$WORK/reflect-repeat"
run reflect-inputs --run rrout --session sid-rrout-a --out "$ROD" --no-meter
need_rc 0
need_file "$ROD/turns.md"
ROSHA=$(sha_file "$ROD/turns.md")
need_eq "$(mk count "$REC" reflect-inputs)" "1" "the first run's event (the control: a fresh --out writes)"
run reflect-inputs --run rrout --session sid-rrout-b --out "$ROD" --no-meter
need_rc 2
need_out "is not empty"
need_out "nothing written"
need_lines
need_eq "$(sha_file "$ROD/turns.md")" "$ROSHA" "the first session's extraction, byte for byte"
need_eq "$(mk count "$REC" reflect-inputs)" "1" "no event from the refused second run"
run reflect-inputs --run rrout --session sid-rrout-b --out "$ROD" --no-meter --dry-run
need_rc 2
need_out "is not empty"
run reflect-inputs --run rrout --session sid-rrout-b --out "$WORK/reflect-repeat-b" --no-meter
need_rc 0
need_eq "$(mk count "$REC" reflect-inputs)" "2" "a fresh directory for the second session records its event"
verdict "G13 (fails on old): a second reflect-inputs into a non-empty --out, dry run or not, is a premise failure that leaves the first extraction byte-identical and records nothing; a fresh directory for each session writes"

# ------------------------------------------- the console window ------------
# The viewer key in the grants file, the opener, who opens it, and the failure modes. Every leg
# runs through the recording stub set up above (AIMYTH_VIEWER_CMD), so no window is ever opened
# and the assertions are on the stub's argv, the command file and the primitive's own lines.
PYEXE=$("$PY" -c 'import sys; sys.stdout.write(sys.executable)')
pmode() { "$PY" -c 'import os, stat, sys; print(oct(stat.S_IMODE(os.stat(sys.argv[1]).st_mode))[-3:])' "$1"; }
viewer_last() { tail -1 "$VIEWER_ARGV"; }

VHO="$WORK/handoffs/vw-handoff.md"; mk handoff "$VHO" >/dev/null
REC="$STORE/spawn-records/rvw.jsonl"; rm -f "$REC"
GF="$STORE/spawn-records/rvw-grants.json"; rm -f "$GF"
viewer_use vkey
run run-open --run rvw --session sid-vw --head "fixture head" --regime single --regime-src owner \
    --handoff "$VHO" --detail "the viewer key" --pid 1
need_rc 0
need_eq "$(vval "$GF")" "terminal" "run-open's default with no file at all"
need_eq "$(mk field "$REC" run-open viewer)" "terminal" "the run-open event"
need_eq "$(mk field "$REC" run-open viewer_src)" "default (no grants file)" "the source"
need_out "viewer terminal (default (no grants file))"
run grants --run rvw --viewer none
need_rc 0
need_eq "$(vval "$GF")" "none" "grants --viewer none rewrites the key"
need_eq "$(mk field "$REC" grants viewer_src)" "arg" "the flag is the source"
run grants --run rvw
need_rc 0
need_eq "$(vval "$GF")" "none" "positive control: a file WITH the key carries it forward"
need_eq "$(mk field "$REC" grants viewer_src)" "grants" "positive control: the source reads grants"
"$PY" -c 'import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d.pop("viewer", None)
json.dump(d, open(p, "w", encoding="utf-8"))' "$GF"
need_eq "$(vval "$GF")" "None" "the planted case: the key is gone from the file"
run grants --run rvw
need_rc 0
need_eq "$(vval "$GF")" "terminal" "a file without the key reads terminal"
need_eq "$(mk field "$REC" grants viewer_src)" "default (key absent)" "the source names the absent key"
verdict "the viewer key: a grants file WITHOUT it reads terminal, source 'default (key absent)', and no file at all reads 'default (no grants file)' (control: a file with the key reads 'grants')"

REC="$STORE/spawn-records/rvwn.jsonl"; rm -f "$REC"
GF="$STORE/spawn-records/rvwn-grants.json"; rm -f "$GF"
viewer_use vflag
run run-open --run rvwn --session sid-vwn --head "fixture head" --regime single --regime-src owner \
    --handoff "$VHO" --detail "the flag" --pid 1 --viewer none
need_rc 0
need_eq "$(vval "$GF")" "none" "run-open --viewer none"
need_eq "$(mk field "$REC" run-open viewer)" "none" "the run-open event"
need_eq "$(mk field "$REC" run-open viewer_src)" "arg" "the source"
need_out "viewer: none (grants) · no window"
need_no_viewer
need_nofile "$(console_cmd rvwn)"
verdict "the viewer key: run-open --viewer none writes none, records viewer_src arg, opens nothing and writes no command file"

run grants --run rvwn --grant "$WORK/handoffs"
need_rc 0
need_eq "$(vval "$GF")" "none" "a rebuild with --grant carries none forward"
need_eq "$(mk field "$REC" grants viewer_src)" "grants" "carried from the file"
GRANTED=$("$PY" -c 'import json, sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))["grants"]))' "$GF")
run run-resume --run rvwn --session sid-vwn2 --head "fixture head" --detail "flag-less" --pid 1
need_rc 0
need_eq "$(vval "$GF")" "none" "a flag-less run-resume keeps the file"
need_eq "$(mk field "$REC" run-resume viewer)" "none" "the run-resume event"
need_eq "$("$PY" -c 'import json, sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))["grants"]))' "$GF")" \
        "$GRANTED" "the kept file's paths are unchanged (both spellings kept)"
run run-resume --run rvwn --session sid-vwn3 --head "fixture head" --detail "the flag alone" --pid 1 --viewer terminal
need_rc 0
need_eq "$(vval "$GF")" "terminal" "--viewer alone rewrites, as --on-limit does"
need_eq "$(mk field "$REC" run-resume viewer_src)" "arg" "the source"
verdict "the viewer key: grants --grant and a flag-less run-resume carry it forward untouched, while --viewer alone rewrites it"

REC="$STORE/spawn-records/rvwo.jsonl"; rm -f "$REC"
CF=$(console_cmd rvwo); rm -f "$CF"
viewer_use vopen
run run-open --run rvwo --session sid-vwo --head "fixture head" --regime single --regime-src owner \
    --handoff "$VHO" --detail "the window" --pid 1
need_rc 0
need_eq "$(viewer_calls)" "1" "the opener was called with one argument"
need_eq "$(viewer_last)" "$CF" "the command file is the LAST argument"
need_out "viewer: Terminal window opened on $CF"
need_file "$CF"
need_eq "$(pmode "$CF")" "755" "the command file's mode"
need_eq "$(sed -n 1p "$CF")" "#!/bin/sh" "the command file's first line"
LINE2=$(sed -n 2p "$CF")
case $LINE2 in
  "printf "*"aiMyth hands-off · rvwo"*) : ;;
  *) why="$why; the title line reads '$LINE2'" ;;
esac
LINE3=$(sed -n 3p "$CF")
case $LINE3 in
  "exec env LLM_WIKI_STORE=$REALSTORE CLAUDE_PROJECT_DIR="*" -B "*"handsoff.py watch --run rvwo") : ;;
  *) why="$why; the exec line reads '$LINE3'" ;;
esac
case $LINE3 in *"$PYEXE"*) : ;; *) why="$why; the exec line does not name this interpreter" ;; esac
need_eq "$(grep -c . "$CF")" "3" "the command file's line count (no cd line: every path in it is absolute)"
verdict "the opener: run-open writes <run>-console.command (0755: a title line naming the run, then exec env LLM_WIKI_STORE=<store> CLAUDE_PROJECT_DIR=<vault> <this interpreter> -B <this script> watch --run R, and no cd) and calls the opener with that path as its last argument (the exec pin moved from line 2 to line 3)"

CF=$(console_cmd rvwst)
# The stale content is assembled from parts so that this file's own source carries no absolute
# path beside a write verb (the source scan below), and no owner path anywhere.
STALE_EXE="/nowhere""/python"
STALE_SRC="/nowhere""/handsoff.py"
printf '#!/bin/sh\nexec %s -B %s watch --run rvwst\n' "$STALE_EXE" "$STALE_SRC" > "$CF"
chmod 600 "$CF"
grep -q 'nowhere' "$CF" || why="$why; positive control: the planted stale line is not in the file"
REC="$STORE/spawn-records/rvwst.jsonl"; rm -f "$REC"
viewer_use vstale
run run-open --run rvwst --session sid-vwst --head "fixture head" --regime single --regime-src owner \
    --handoff "$VHO" --detail "a stale command file" --pid 1
need_rc 0
if grep -q 'nowhere' "$CF"; then why="$why; the stale command file was not rewritten"; fi
need_eq "$(pmode "$CF")" "755" "the rewritten file's mode"
need_eq "$(sed -n 3p "$CF" | sed 's/.* watch --run //')" "rvwst" "the rewritten exec line (line 3)"
verdict "the opener: a stale <run>-console.command is rewritten and re-moded 0755 (control: the planted stale line is there before the run)"

fixture rvwsuc 200
viewer_use vsuc
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwsuc --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: Terminal window opened on"
need_viewer_arg "$(console_cmd rvwsuc)"
need_file "$(console_cmd rvwsuc)"
sleep 2   # the detached starter aborts on the missing harness; let it go before the next leg
verdict "successor: with no console alive for the run, one window is opened on it and the primitive still exits 0"

# The grace window (2026-09-08): run-open and successor a second apart can open two windows, since
# Terminal may not yet have started the first console's process when successor probes the table.
# A console opened within CONSOLE_START_GRACE_S counts as alive,
# keyed on the command file's mtime: the opener stamps it at every open and pushes it into the
# past on a failed open. Legs: a fresh stamp blocks the second window; an old stamp does not; a
# failed open leaves no fresh stamp; the helper itself on a fresh, an old and a missing file.
fixture rvwg1 200
CF=$(console_cmd rvwg1)
printf '#!/bin/sh\n' > "$CF"; chmod 755 "$CF"    # a command file stamped now: a console starting
viewer_use vg1
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwg1 --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "may still be starting · no second window"
need_no_viewer
sleep 2
verdict "successor: a console opened within the grace window (a fresh command-file stamp, no process yet) is not doubled — no opener call, the primitive still exits 0"

fixture rvwg2 200
CF=$(console_cmd rvwg2)
printf '#!/bin/sh\n' > "$CF"; chmod 755 "$CF"
"$PY" -c 'import os, sys, time; t = time.time() - 120; os.utime(sys.argv[1], (t, t))' "$CF"
viewer_use vg2
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwg2 --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: Terminal window opened on"
need_viewer_arg "$CF"
AGE=$("$PY" -c 'import os, sys, time; print(int(time.time() - os.path.getmtime(sys.argv[1])))' "$CF")
[ "$AGE" -lt 15 ] || why="$why; the opener did not re-stamp the command file (age ${AGE}s)"
sleep 2
verdict "successor: a command file stamped two minutes ago does not count as a starting console — the window is opened and the file is stamped afresh (the control for the grace leg)"

fixture rvwg3 200
CF=$(console_cmd rvwg3); rm -f "$CF"
viewer_use vg3
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_VIEWER_CMD=$WORK/bin/viewer-fail.sh"
run successor --run rvwg3 --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: no Terminal window"
need_eq "$(viewer_calls)" "2" "positive control: the failing stub was reached, and retried once (register 2026-09-09 11:21)"
AGE=$("$PY" -c 'import os, sys, time; print(int(time.time() - os.path.getmtime(sys.argv[1])))' "$CF")
[ "$AGE" -ge 15 ] || why="$why; a failed open left a fresh stamp (age ${AGE}s), so it would read as a console starting"
sleep 2
verdict "a failed open pushes the command file's stamp past the grace window, so the failure never reads as a console still starting"

CF=$(console_cmd rvwg4)
printf '#!/bin/sh\n' > "$CF"
env LLM_WIKI_STORE="$STORE" "$PY" - "$H" rvwg4 "$CF" <<'CSTART' > "$WORK/cs.txt"
import importlib.util, os, sys, time
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
run, path = sys.argv[2], sys.argv[3]
fresh = mod.console_starting(run)
t = time.time() - 120; os.utime(path, (t, t))
old = mod.console_starting(run)
os.remove(path)
gone = mod.console_starting(run)
print("fresh" if fresh is not None and 0 <= fresh < mod.CONSOLE_START_GRACE_S else "fresh=%r" % fresh,
      old, gone)
CSTART
need_eq "$(cat "$WORK/cs.txt")" "fresh None None" "console_starting: a fresh stamp is an age under the grace window; an old stamp and a missing file are None"
verdict "console_starting: keyed on the command file's stamp alone — fresh counts, old and missing make no claim"

RSUC2="rvwsuc2$SFX"   # a planted console's run id carries the suite's suffix (register 2026-09-22 20:28)
fixture "$RSUC2" 200
plant_console "$RSUC2" watch.py
viewer_use vsuc2
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run "$RSUC2" --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "a console is already alive (pid $PLANTED)"
need_no_viewer
need_nofile "$(console_cmd "$RSUC2")"
sleep 2
kill_console
verdict "successor: a console already alive for the run is never doubled — the pid is named, nothing is opened, no command file is written"

fixture rvwrh 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-rvwrh","pid":1,"budget":5.0}' >/dev/null
viewer_use vrh
run resume-head --run rvwrh --harness-bin "$WORK/bin/no-such-harness" --budget-usd 5 --tick-s 1
need_rc 0
need_out "viewer: Terminal window opened on"
need_viewer_arg "$(console_cmd rvwrh)"
sleep 2   # the detached half aborts: the fixture session has no transcript to size
verdict "resume-head: with no console alive for the run, one window is opened on it and the primitive still exits 0"

RRH2="rvwrh2$SFX"
fixture "$RRH2" 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-rvwrh2","pid":1,"budget":5.0}' >/dev/null
plant_console "$RRH2" handsoff.py
viewer_use vrh2
run resume-head --run "$RRH2" --harness-bin "$WORK/bin/no-such-harness" --budget-usd 5 --tick-s 1
need_rc 0
need_out "a console is already alive (pid $PLANTED)"
need_no_viewer
sleep 2
kill_console
verdict "resume-head: a console already alive for the run is never doubled (the handsoff.py spelling of the marker)"

viewer_use vspell
RSP="rvwsp$SFX"
plant_console "$RSP" watch.py
"$PY" - "$H" "$RSP" <<'CALIVE' > "$WORK/ca-watch.txt"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
print(len(mod.console_alive(sys.argv[2])), len(mod.console_alive("rvwsp-nobody")))
CALIVE
need_eq "$(cat "$WORK/ca-watch.txt")" "1 0" "the watch.py spelling, with the negative control"
kill_console
plant_console "$RSP" handsoff.py
"$PY" - "$H" "$RSP" <<'CALIVE2' > "$WORK/ca-handsoff.txt"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
print(len(mod.console_alive(sys.argv[2])), len(mod.console_alive("rvwsp-nobody")))
CALIVE2
need_eq "$(cat "$WORK/ca-handsoff.txt")" "1 0" "the handsoff.py spelling, with the negative control"
kill_console
sleep 1
"$PY" - "$H" "$RSP" <<'CALIVE3' > "$WORK/ca-none.txt"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
print(len(mod.console_alive(sys.argv[2])))
CALIVE3
need_eq "$(cat "$WORK/ca-none.txt")" "0" "nothing alive once the planted console is gone"
verdict "console_alive: both spellings of the marker are found — 'watch.py --run R' as the console RUNS and 'handsoff.py watch --run R' as it is launched — and a run with no console reads 0 (the negative control on each run)"

fixture rvwnone 200
run grants --run rvwnone --viewer none
need_rc 0
viewer_use vnone
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwnone --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: none (grants)"
need_no_viewer
mk append "$REC" '{"event":"head-successor","session_id":"sid-rvwnone","pid":1,"budget":5.0}' >/dev/null
run resume-head --run rvwnone --harness-bin "$WORK/bin/no-such-harness" --budget-usd 5 --tick-s 1
need_rc 0
need_out "viewer: none (grants)"
need_no_viewer
need_nofile "$(console_cmd rvwnone)"
sleep 2
verdict "viewer none: run-open (above), successor and resume-head each open nothing and write no command file, and each still exits 0"

fixture rvwfail 200
viewer_use vfail
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_VIEWER_CMD=$WORK/bin/viewer-fail.sh"
run successor --run rvwfail --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: no Terminal window"
need_out "exit 1"
need_out "run by hand: $PYABS -B"
need_out "watch --run rvwfail"
need_eq "$(viewer_calls)" "2" "positive control: the failing stub was reached, and retried once (register 2026-09-09 11:21)"
sleep 2
verdict "the failing opener: a stub that exits 1 gives one stderr line naming the reason and the by-hand command, and the primitive still exits 0"

# ------------------------- the opener's route (register 2026-09-17 20:29 and 20:31)
# viewer_argv without AIMYTH_VIEWER_CMD is `/usr/bin/open <command file>` and nothing else — the
# owner's absolute path (the ruling on the fold, critic review finding 7), no script text, no
# osascript, the path the last argument; AIMYTH_OPEN_BIN overrides the executable (a suite's
# stub); with AIMYTH_VIEWER_CMD set it is the custom command plus the path (the control on the
# same helper). The AppleScript's idle-wait constants are gone, and the claim's life covers the
# open bound plus the confirmation bound.
VARGV=$(env -u AIMYTH_VIEWER_CMD -u AIMYTH_OPEN_BIN "$PY" - "$H" <<'VIEWER_ARGV_END'
import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
argv, source = ho.viewer_argv("/fixture/dir/rvw-console.command", "rvw")
os.environ["AIMYTH_OPEN_BIN"] = "/fixture/bin/open-stub"
oargv, osource = ho.viewer_argv("/fixture/dir/rvw-console.command", "rvw")
del os.environ["AIMYTH_OPEN_BIN"]
os.environ["AIMYTH_VIEWER_CMD"] = "/fixture/bin/custom-viewer --flag"
cargv, csource = ho.viewer_argv("/fixture/dir/rvw-console.command", "rvw")
checks = {
    "open_route": argv == ["/usr/bin/open", "-g", "/fixture/dir/rvw-console.command"] and source == "open",
    "absolute_default": ho.OPEN_BIN == "/usr/bin/open" and os.path.isabs(argv[0]),
    "override_bin": oargv == ["/fixture/bin/open-stub", "-g", "/fixture/dir/rvw-console.command"] and osource == "open",
    "no_script": not any("osascript" in w or "tell application" in w for w in argv),
    "custom_route": cargv == ["/fixture/bin/custom-viewer", "--flag", "/fixture/dir/rvw-console.command"]
                    and csource == "AIMYTH_VIEWER_CMD",
    "idle_constants_gone": not any(hasattr(ho, n) for n in ("VIEWER_IDLE_PAUSE_S", "VIEWER_IDLE_POLLS", "VIEWER_IDLE_STEP_S")),
    "confirm_inside_grace": 0 < ho.CONSOLE_CONFIRM_STEP_S <= ho.CONSOLE_START_GRACE_S and ho.VIEWER_TIMEOUT_S > 0,
    "claim_is_a_lock": ho.console_lock_path("rvw").endswith("rvw-console.lock")
                       and ho.fcntl is not None,
    "claim_has_no_life": not any(hasattr(ho, n) for n in ("CONSOLE_CLAIM_LIFE_S", "take_claim", "read_claim")),
}
print(json.dumps(checks))
VIEWER_ARGV_END
)
case $VARGV in *false*) why="$why; viewer_argv: $VARGV" ;; esac
case $VARGV in *'"custom_route": true'*) : ;; *) why="$why; the control did not run: $VARGV" ;; esac
verdict "the opener's route (critic review finding 7): viewer_argv is the owner's absolute /usr/bin/open, then -g (open's background flag, register 2026-09-22), then the command file — no script text, no osascript, the path last — AIMYTH_OPEN_BIN overrides the executable and AIMYTH_VIEWER_CMD still replaces the command whole (the controls); the AppleScript's idle-wait constants are gone, and the one-window claim is the lock beside the record with no life to expire (the №163 ruling: the age-based claim and its takeover are gone with the constant)"

# The route itself, through the stub `open` AIMYTH_OPEN_BIN names (PATH carries no `open`), with
# AIMYTH_VIEWER_CMD empty: the stub is called once, with -g and then the command file, and the window is
# claimed only once a `watch` process for the run is in the table (the stub plants one), its pid
# named on the line.
ROPEN="rvwopen$SFX"
fixture "$ROPEN" 200
viewer_use vopen2
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run successor --run "$ROPEN" --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: Terminal window opened on $(console_cmd "$ROPEN") via $WORK/openbin/open (first attempt) · console pid "
need_eq "$(viewer_calls)" "2" "open was called once, with two arguments: -g and the command file"
need_eq "$(head -1 "$VIEWER_ARGV")" "-g" "the first argument is -g, open's flag for leaving the application in the background (register 2026-09-22)"
need_eq "$(wc -l < "$VIEWER_ARGV.calls" | tr -d ' ')" "1" "one call, counted by the stub's own per-call line"
need_eq "$(cat "$VIEWER_ARGV.calls")" "-g $(console_cmd "$ROPEN")" "that one call's arguments are exactly -g and the command file"
need_eq "$(viewer_last)" "$(console_cmd "$ROPEN")" "the command file is open's last argument"
OPID=$(cat "$VIEWER_ARGV.pid")
need_out "console pid $OPID confirmed after"
need_absent "osascript"
sleep 2
kill "$OPID"
verdict "the opener's open route (must fire): successor runs open on the command file once and reports the window only with the console pid it confirmed in the process table"

# The empty-window class (an attempt that exits clean and shows nothing): `open` exits 0 and
# starts no console, so no window is claimed, the bound is named,
# the stamp is pushed past the grace window (a later opener is not blocked) and the primitive
# still exits 0. One `open` call: an unconfirmed console is not a failed `open`, so no retry.
fixture rvwempty 200
CF=$(console_cmd rvwempty)
viewer_use vempty
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD="
run successor --run rvwempty --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: no Terminal window (command file $CF; $WORK/openbin/open exited 0 but no console process for the run appeared within 15 s; the last probe: "
need_out "the last probe: pgrep exit 1: no match); run by hand: $PYABS -B"
need_absent "Terminal window opened"
need_eq "$(viewer_calls)" "2" "open was called once (-g and the command file)"
AGE=$("$PY" -c 'import os, sys, time; print(int(time.time() - os.path.getmtime(sys.argv[1])))' "$CF")
[ "$AGE" -ge 15 ] || why="$why; the unconfirmed open left a fresh stamp (age ${AGE}s)"
sleep 2
verdict "the opener's open route (must fire on the empty-window class): an open that exits 0 with no console process inside the bound is reported as no window with the bound named, its stamp pushed past the grace window, and the primitive still exits 0"

# An `open` that fails outright is retried once with the same command, its stderr quoted.
fixture rvwopenfail 200
viewer_use vopenfail
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openfail/open AIMYTH_VIEWER_CMD="
run successor --run rvwopenfail --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: no Terminal window (command file $(console_cmd rvwopenfail); first attempt: $WORK/openfail/open exit 1: stub open: LSOpenURLsWithRole() failed with error -600; retry: $WORK/openfail/open exit 1: stub open"
need_out "run by hand: $PYABS -B"
need_eq "$(viewer_calls)" "4" "open was tried twice (first attempt and retry), -g and the command file each time"
need_eq "$(wc -l < "$VIEWER_ARGV.calls" | tr -d ' ')" "2" "two calls, counted by the stub's own per-call line"
need_eq "$(sort -u "$VIEWER_ARGV.calls")" "-g $(console_cmd rvwopenfail)" "both calls carry exactly -g and the command file"
sleep 2
verdict "the opener's open route (a failing open): a non-zero exit is retried once with the same command, both attempts named with open's stderr, and the primitive still exits 0"

# open-console: the opener on demand, and --check as the live check.
ROC="rvwoc$SFX"
fixture "$ROC" 200
viewer_use voc
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run "$ROC"
need_rc 0
need_out "viewer: Terminal window opened on $(console_cmd "$ROC") via $WORK/openbin/open (first attempt) · console pid "
OCPID=$(cat "$VIEWER_ARGV.pid")
run open-console --run "$ROC" --check
need_rc 0
need_out "console: pid $OCPID alive on watch --run $ROC"
run open-console --run "$ROC"
need_rc 0
need_out "a console is already alive (pid $OCPID) · no second window"
need_eq "$(viewer_calls)" "2" "no second open while the console lives (the one call's two arguments)"
kill "$OCPID"; sleep 1
run open-console --run "$ROC" --check
need_rc 1
need_out "NO CONSOLE for $ROC"
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD="
run open-console --run "$ROC" --dry-run
need_rc 0
need_out "would run: $WORK/openbin/open -g $(console_cmd "$ROC")"
need_eq "$(viewer_calls)" "2" "a dry run opens nothing (still the one earlier call)"
verdict "open-console: opens the window on demand through open, --check prints the confirmed pid with exit 0, a second call while it lives opens nothing, --check after the console ends prints NO CONSOLE with exit 1, and --dry-run prints the open line and calls nothing"

# The one-window claim is the advisory lock on <run>-console.lock beside the record (the ruling
# on the №163 fold, 2026-09-18): the claim file of №162 is retired, and the single line here that
# spells it plants a leftover of that retired name to prove nothing reads it. Legs: a leftover
# claim file blocks no window and is not touched; the lock file is where the claim now lives; and
# neither opt-out — --viewer none, --check — takes a claim at all.
RCLAIM="rvwclaim$SFX"
fixture "$RCLAIM" 200
CF=$(console_cmd "$RCLAIM"); rm -f "$CF"
LOCKF="$REALSTORE/spawn-records/$RCLAIM-console.lock"; rm -f "$LOCKF"
: > "$CF.opening"
viewer_use vclaim
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run "$RCLAIM"
need_rc 0
need_out "viewer: Terminal window opened on $CF via $WORK/openbin/open (first attempt) · console pid "
need_eq "$(viewer_calls)" "2" "the retired claim file blocked nothing and open ran once (-g and the command file)"
need_file "$CF.opening"
need_file "$LOCKF"
need_absent "took over"
kill "$(cat "$VIEWER_ARGV.pid")"; sleep 1
rm -f "$CF.opening"
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run "$RCLAIM" --viewer none
need_rc 0
need_out "viewer: none (grants) · no window"
need_eq "$(viewer_calls)" "2" "--viewer none opened nothing more (the earlier call's two arguments)"
LOCKN="$REALSTORE/spawn-records/rvwnoclaim-console.lock"; rm -f "$LOCKN"
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD="
run open-console --run rvwnoclaim --viewer none
need_rc 0
need_nofile "$LOCKN"
run open-console --run rvwnoclaim --check
need_rc 1
need_out "NO CONSOLE for rvwnoclaim"
need_nofile "$LOCKN"
verdict "open-console and the one-window claim on a lock (the №163 ruling): a leftover claim file of the retired name blocks no window and is left untouched, the claim is the <run>-console.lock beside the record, and --viewer none and --check take no claim at all (no lock file) while --viewer none still opens nothing"

# A claim holder in another PROCESS, and what a crash leaves behind. The holder takes the run's
# claim and stops; a second opener names it, opens nothing, exits 0 and takes nothing over (the
# lock file is still there afterwards). Then the holder is killed outright — the shape a crashed
# opener leaves — and the next opener is free AT ONCE, because the kernel released the claim with
# the process. Must fire on a claim file whose fresh file outlives its holder and blocks the
# window for the whole 35 s life it is given (the pre-fold claim).
RKILL="rvwkill$SFX"
fixture "$RKILL" 200
KCF=$(console_cmd "$RKILL"); rm -f "$KCF"
KLOCK="$REALSTORE/spawn-records/$RKILL-console.lock"; rm -f "$KLOCK"
rm -f "$WORK/holder.flag"
cat > "$WORK/holder.py" <<'HOLDER_END'
"""Take the run's console claim in a process of its own, say so, and wait to be killed. It takes
whichever claim the code under test has, so the same leg runs on the pre-fold code."""
import importlib.util
import os
import sys
import time

spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, flag = sys.argv[2], sys.argv[3]
if hasattr(ho, "take_console_lock"):
    held, fd, why = ho.take_console_lock(run)
    if held:
        ho.write_console_claim(fd, ho.CONSOLE_PHASE_OPEN)
else:
    # the claim file of №162, retired by the ruling of 2026-09-18: reached only where this leg
    # runs against the pre-fold code
    held, why = ho.take_claim(ho.console_command_path(run) + ".opening")
with open(flag, "w", encoding="utf-8") as fh:
    fh.write("%s %d %s\n" % (held, os.getpid(), why))
sys.stdout.flush()
time.sleep(120)
HOLDER_END
"$PY" -B "$WORK/holder.py" "$H" "$RKILL" "$WORK/holder.flag" &
HOLDPID=$!
i=0
while [ ! -s "$WORK/holder.flag" ] && [ "$i" -lt 60 ]; do sleep 0.25; i=$((i + 1)); done
case $(cat "$WORK/holder.flag" 2>/dev/null) in
  True*) : ;;
  *) why="$why; the holder process never took the claim: '$(cat "$WORK/holder.flag" 2>/dev/null)'" ;;
esac
viewer_use vkill
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD="
run open-console --run "$RKILL"
need_rc 0
need_out "another opener (pid $HOLDPID"
need_out "no second window"
need_no_viewer
need_file "$KLOCK"
need_nofile "$KCF"
kill -9 "$HOLDPID"; wait "$HOLDPID" 2>/dev/null || :
KT0=$(clock_f)
viewer_use vkill2
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run "$RKILL"
need_rc 0
need_out "viewer: Terminal window opened on $KCF"
need_eq "$(viewer_calls)" "2" "the killed holder's claim was gone, so the window opened once (-g and the command file)"
need_eq "$(span_ok "$KT0" "$(clock_f)" 20)" "ok" "the next opener waited for no claim to expire"
kill "$(cat "$VIEWER_ARGV.pid")" 2>/dev/null; sleep 1
verdict "the console claim across processes (the №163 ruling, must fire): a holder in another process makes a second opener name it, open nothing and exit 0 without taking anything over, and a holder killed outright leaves the next opener free at once — the kernel released the claim with the process"

# The two forced interleavings of critic review pass 2 (finding 2 and the first new finding),
# reproduced with real threads through open_console_if_dark against one fixture directory, the
# opener and both process probes mocked, each plant driven by an event rather than a sleep so the
# interleaving is forced and not raced for. Must fire on a claim file that admits TWO openers
# on each (the pre-fold claim):
#   · the release window — a caller observes no console, pauses, and acts on that observation
#     after another caller has opened, confirmed and released its claim;
#   · the replacement between a read and the act on it — both callers read one stale claim, the
#     first replaces it with its own, and the second then acts on the pathname it read.
# The controls that must NOT fire: two callers at once in either order, and four at once, with
# nothing planted, each make exactly one opener call on both codes. The leftover claim file of
# the retired name is planted in the second case and read by nothing.
cat > "$WORK/claimrace.py" <<'CLAIM_RACE_END'
"""The forced interleavings of critic review pass 2, run against either code. One JSON line."""
import importlib.util
import itertools
import json
import os
import sys
import threading
import time

spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
work = sys.argv[2]
os.makedirs(work, exist_ok=True)
cmd = os.path.join(work, "rrace-console.command")
lock = os.path.join(work, "rrace-console.lock")
old_claim = cmd + ".opening"   # the claim file of №162, retired 2026-09-18, planted to prove it inert
ho.console_command_path = lambda run: cmd
if hasattr(ho, "console_lock_path"):
    ho.console_lock_path = lambda run: lock
ho.console_starting = lambda run: None
ho.viewer_log = lambda log, line: None
ho.say = lambda line: None
ho.note = lambda line: None

calls = []
guard = threading.Lock()
console = []
pause = {}
taken = threading.Event()


def alive(run, timeout=None):
    seen = list(console)                       # the caller's observation, taken here
    wait = pause.pop(threading.current_thread().name, 0.0)
    if wait:
        time.sleep(wait)                       # the plant: it acts on that observation later
    return seen


def fake_open(run, viewer=None, dry_run=False, why="", log=None):
    with guard:
        calls.append(1)
    taken.set()                                # a caller has this run's claim and is opening
    time.sleep(0.3)                            # the open and its confirmation wait
    console.append(4242)                       # the window is visible to any probe from here
    return True


ho.console_alive = alive
ho.open_console = fake_open


def reset():
    del calls[:]
    del console[:]
    pause.clear()
    taken.clear()
    for path in (lock, old_claim):
        if os.path.exists(path):
            os.unlink(path)


def plant_old_claim(age):
    with open(old_claim, "w", encoding="utf-8") as fh:
        fh.write("pid 1\nmonotonic %.3f\n" % (time.monotonic() - age))
    stamp = time.time() - age
    os.utime(old_claim, (stamp, stamp))


def worker():
    ho.open_console_if_dark("rrace", viewer="terminal")


def race(n, names=None, gap=0.0):
    names = names or [chr(ord("A") + i) for i in range(n)]
    threads = [threading.Thread(target=worker, name=name) for name in names]
    for thread in threads:
        thread.start()
        if gap:
            time.sleep(gap)
    for thread in threads:
        thread.join()
    return len(calls)


# 1 · the release window: B observes no console, pauses, and acts on that observation after A has
# opened, confirmed and released its claim.
reset()
pause["B"] = 0.6
release_window = race(2, ["A", "B"], gap=0.05)

# 2 · the replacement between a read of a stale claim and the act on it: both callers read it,
# then the second acts only once the first has replaced it with its own.
reset()
plant_old_claim(120)
if hasattr(ho, "read_claim"):
    real_read, seq = ho.read_claim, itertools.count()
    both_read = threading.Barrier(2, timeout=3)

    def slow_read(claim):
        out = real_read(claim)
        n = next(seq)
        if n < 2:
            try:
                both_read.wait()
            except threading.BrokenBarrierError:
                pass
        if n == 1:
            taken.wait(3)
        return out

    ho.read_claim = slow_read
replacement = race(2, ["A", "B"], gap=0.05)
leftover_kept = os.path.exists(old_claim)

# 3 · the controls: two callers at once in either order, and four at once, nothing planted.
reset()
two_at_once = race(2, ["A", "B"])
reset()
two_reversed = race(2, ["B", "A"])
reset()
four_at_once = race(4)

# 4 · a leftover claim file of the retired name, fresh: it claims nothing and is not rewritten.
reset()
plant_old_claim(0)
with open(old_claim, encoding="utf-8") as fh:
    before = fh.read()
leftover_fresh = race(1, ["A"])
with open(old_claim, encoding="utf-8") as fh:
    leftover_same = fh.read() == before

print(json.dumps({"release_window": release_window, "replacement": replacement,
                  "leftover_kept": leftover_kept, "two_at_once": two_at_once,
                  "two_reversed": two_reversed, "four_at_once": four_at_once,
                  "leftover_fresh": leftover_fresh, "leftover_same": leftover_same},
                 sort_keys=True))
CLAIM_RACE_END
CLAIMRACE=$("$PY" -B "$WORK/claimrace.py" "$H" "$WORK/claimrace")
case $CLAIMRACE in *'"release_window": 1'*) : ;; *) why="$why; the release window: $CLAIMRACE" ;; esac
case $CLAIMRACE in *'"replacement": 1'*) : ;; *) why="$why; the replacement interleaving: $CLAIMRACE" ;; esac
case $CLAIMRACE in *'"two_at_once": 1'*) : ;; *) why="$why; two callers at once: $CLAIMRACE" ;; esac
case $CLAIMRACE in *'"two_reversed": 1'*) : ;; *) why="$why; two callers, the other order: $CLAIMRACE" ;; esac
case $CLAIMRACE in *'"four_at_once": 1'*) : ;; *) why="$why; four callers at once: $CLAIMRACE" ;; esac
case $CLAIMRACE in *'"leftover_fresh": 1'*) : ;; *) why="$why; a leftover claim file blocked the window: $CLAIMRACE" ;; esac
case $CLAIMRACE in *'"leftover_kept": true'*) : ;; *) why="$why; a leftover claim file was taken over: $CLAIMRACE" ;; esac
case $CLAIMRACE in *'"leftover_same": true'*) : ;; *) why="$why; a leftover claim file was rewritten: $CLAIMRACE" ;; esac
verdict "the one-window claim under forced interleavings (critic review pass 2, findings 2 and the release window, must fire): a caller acting on an earlier no-console observation after another has opened and released, and a second caller acting on a claim replaced since it read it, each admit exactly ONE opener; two callers at once in either order and four at once admit one (the controls); and a leftover claim file of the retired name blocks nothing and is neither renamed nor rewritten"

# The claim body's write failure (critic review pass 2, the second new finding, must fire on a
# claim where a fault-injected ENOSPC on the body raises OSError out of `open-console`: the
# process exits 1 and neither the opener nor the claim's release runs). The fault is injected
# at the two ways a body reaches the file — os.write for the folded claim, a file object for the
# pre-fold one — and the whole `open-console` dispatch is run behind it. The unlock's own failure
# is the second half: it is named too, and still opens. The control is the same call without the
# fault, which exits 0 and writes its body.
cat > "$WORK/enospc.py" <<'ENOSPC_END'
"""A fault-injected ENOSPC on the console claim's body, through the whole open-console dispatch,
then an unlock that fails. One JSON line on stdout; the viewer's own lines go to stderr."""
import contextlib
import errno
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run = sys.argv[2]
ho.console_alive = lambda name, timeout=None: []
ho.console_starting = lambda name: None
real_write, real_fdopen = os.write, os.fdopen
body_writes = []


def full_disk(fd, data):
    """ENOSPC on the claim body alone (the folded body opens with this process's pid and a
    space); every other write goes through."""
    if data.startswith(str(os.getpid()).encode("ascii") + b" "):
        body_writes.append(1)
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
    return real_write(fd, data)


class FullDisk(object):
    """The same fault where the body goes through a file object (the pre-fold claim's writer)."""

    def __init__(self, handle):
        self.handle = handle

    def write(self, data):
        body_writes.append(1)
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.handle.close()
        return False


def full_disk_fdopen(fd, *args, **kwargs):
    return FullDisk(real_fdopen(fd, *args, **kwargs))


def call():
    sys.argv = ["handsoff.py", "open-console", "--run", run]
    try:
        with contextlib.redirect_stdout(sys.stderr):
            ho.main()
    except SystemExit as exc:
        return exc.code or 0
    except BaseException as exc:                  # the pre-fold outcome: it raised out
        return "%s: %s" % (type(exc).__name__, exc)
    return 0


os.write, os.fdopen = full_disk, full_disk_fdopen
enospc_exit = call()
os.write, os.fdopen = real_write, real_fdopen
opener_ran = os.path.exists(os.environ["AIMYTH_VIEWER_ARGV"])
unlock_exit = "no lock to unlock"
if ho.fcntl is not None and hasattr(ho, "release_console_lock"):
    real_flock = ho.fcntl.flock

    def flaky(fd, op):
        if op == ho.fcntl.LOCK_UN:
            raise OSError(errno.EIO, os.strerror(errno.EIO))
        return real_flock(fd, op)

    ho.fcntl.flock = flaky
    unlock_exit = call()
    ho.fcntl.flock = real_flock
print(json.dumps({"enospc_exit": enospc_exit, "body_writes_attempted": len(body_writes),
                  "opener_ran": opener_ran, "unlock_exit": unlock_exit}, sort_keys=True))
ENOSPC_END
viewer_use venospc
ENOSPC=$(env AIMYTH_VIEWER_CMD="$WORK/bin/viewer-stub.sh" AIMYTH_VIEWER_ARGV="$VIEWER_ARGV" \
             "$PY" -B "$WORK/enospc.py" "$H" rvwenospc 2>"$WORK/enospc.err")
case $ENOSPC in *'"enospc_exit": 0'*) : ;; *) why="$why; the claim body's ENOSPC: $ENOSPC" ;; esac
case $ENOSPC in *'"unlock_exit": 0'*) : ;; *) why="$why; a failing unlock: $ENOSPC" ;; esac
case $ENOSPC in *'"opener_ran": true'*) : ;; *) why="$why; the opener never ran: $ENOSPC" ;; esac
case $ENOSPC in *'"body_writes_attempted": 1'*) : ;; *) why="$why; the fault was not reached (the control): $ENOSPC" ;; esac
grep -q 'viewer: claim body not written (\[Errno 28\] No space left on device): opening anyway' "$WORK/enospc.err" \
  || why="$why; the body failure was not named on stderr: $(head -2 "$WORK/enospc.err" | tr '\n' ' ')"
grep -q 'viewer: the console claim could not be released' "$WORK/enospc.err" \
  || why="$why; the unlock failure was not named on stderr"
if grep -q 'Traceback' "$WORK/enospc.err"; then why="$why; the fault raised out of the opener"; fi
need_eq "$(grep -c 'Terminal window opened on' "$WORK/enospc.err")" "2" "both faulted calls still opened one window each"
viewer_use venospc2
ENOSPCOK=$(env AIMYTH_VIEWER_CMD="$WORK/bin/viewer-stub.sh" AIMYTH_VIEWER_ARGV="$VIEWER_ARGV" \
               "$PY" -B - "$H" rvwenospc2 <<'ENOSPC_OK_END' 2>"$WORK/enospc-ok.err"
import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
ho.console_alive = lambda name, timeout=None: []
ho.console_starting = lambda name: None
sys.argv = ["handsoff.py", "open-console", "--run", sys.argv[2]]
code = 0
try:
    import contextlib
    with contextlib.redirect_stdout(sys.stderr):
        ho.main()
except SystemExit as exc:
    code = exc.code or 0
body = ""
if hasattr(ho, "console_lock_path"):
    with open(ho.console_lock_path("rvwenospc2"), encoding="utf-8") as fh:
        body = fh.read().strip()
print(json.dumps({"exit": code, "body": body}))
ENOSPC_OK_END
)
case $ENOSPCOK in *'"exit": 0'*) : ;; *) why="$why; the control call did not exit 0: $ENOSPCOK" ;; esac
case $ENOSPCOK in *'"body": "'*' open"'*) : ;; *) why="$why; the control call wrote no claim body naming its phase: $ENOSPCOK" ;; esac
if grep -q 'Traceback' "$WORK/enospc-ok.err"; then why="$why; the control call raised"; fi
need_eq "$(grep -c 'Terminal window opened on' "$WORK/enospc-ok.err")" "1" "the control call opened its window"
verdict "the claim body's write failure (critic review pass 2, the second new finding, must fire): a fault-injected ENOSPC on the body — and, after it, an unlock that fails — each give one named viewer line, still open the window and still exit 0, never raising out of the opener, while the same call without the fault exits 0 and leaves its body naming the holder's pid and phase (the control)"

# open-console honours the environment opt-out too (critic review finding 4): AIMYTH_VIEWER=none
# opens nothing, as --viewer none does above; an unknown value is named and the grants default
# opens (the control).
RENV="rvwenv$SFX"
fixture "$RENV" 200
viewer_use venv
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1 AIMYTH_VIEWER=none"
run open-console --run "$RENV"
need_rc 0
need_out "viewer: none"
need_out "no window"
need_no_viewer
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1 AIMYTH_VIEWER=window"
run open-console --run "$RENV"
need_rc 0
need_out "open-console: AIMYTH_VIEWER='window' is neither terminal nor none · the grants file decides"
need_out "viewer: Terminal window opened on $(console_cmd "$RENV") via $WORK/openbin/open (first attempt) · console pid "
need_eq "$(viewer_calls)" "2" "the control: an unknown value falls back to the grants default and opens once (-g and the command file)"
kill "$(cat "$VIEWER_ARGV.pid")"; sleep 1
verdict "open-console and AIMYTH_VIEWER=none (critic review finding 4, must fire): the environment opt-out opens nothing, as --viewer none does, while an unknown value is named and the grants default opens (the control)"

# The confirmation wait's bound (critic review finding 3, must fire on the pre-fold wait, which
# let a probe run its own 10 s and accepted a pid found after the bound): with every pgrep probe
# sleeping past its bound the wait returns inside the bound with no pid; a pid that shows only
# after the bound is a timeout, never a window; the zero-cost control makes at most 30 probes at
# the defaults; an immediate pid returns at once.
WAITC=$("$PY" - "$H" "$WORK" <<'WAIT_CONSOLE_END'
import importlib.util, json, os, sys, time
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
work = sys.argv[2]
os.environ["PATH"] = os.path.join(work, "pgrepslow") + os.pathsep + os.environ.get("PATH", "")
ho.note = lambda msg: None
def run(sleep_s, empty_calls, pid, bound, step):
    state = os.path.join(work, "pgrep-state-%d-%d" % (os.getpid(), time.monotonic_ns()))
    os.environ.update(PGREP_STATE=state, PGREP_SLEEP_S=str(sleep_s), PGREP_EMPTY_CALLS=str(empty_calls), PGREP_PID=pid)
    t0 = time.monotonic()
    out = ho.wait_console("rvwwait", bound, step)
    wall = time.monotonic() - t0
    probes = int(open(state).read() or 0) if os.path.exists(state) else 0
    return list(out[0]), round(wall, 2), probes
slow = run(6, 0, "", 3, 0.5)
late = run(2, 1, "4321", 3, 0.5)
zero = run(0, 0, "", None, None)
quick = run(0, 0, "4321", None, None)
print("slow_ok=%s late_ok=%s zero_ok=%s quick_ok=%s · slow %s · late %s · zero %s · quick %s" % (
    not slow[0] and slow[1] < 3.6, not late[0] and late[1] < 3.6,
    not zero[0] and zero[2] <= 30 and zero[1] < 15.6, quick[0] == [4321] and quick[1] < 1.0,
    slow, late, zero, quick))
WAIT_CONSOLE_END
)
case $WAITC in *"slow_ok=True"*) : ;; *) why="$why; slow probes ran past the bound: $WAITC" ;; esac
case $WAITC in *"late_ok=True"*) : ;; *) why="$why; a pid found after the bound was accepted: $WAITC" ;; esac
case $WAITC in *"zero_ok=True"*) : ;; *) why="$why; the zero-cost control: $WAITC" ;; esac
case $WAITC in *"quick_ok=True"*) : ;; *) why="$why; an immediate pid: $WAITC" ;; esac
verdict "the confirmation wait's bound (critic review finding 3, must fire): probes that sleep past their bound end the 3 s wait inside 3.6 s with no pid, a pid that shows only after the bound is a timeout and never a window, the zero-cost control makes at most 30 probes inside the 15 s default, and an immediate pid returns at once"

# The AppleScript route is gone from the two opener files — every `osascript` left
# in handsoff.py or lane.py sits on a comment line naming the retired route — with a planted
# copy carrying a live call as the control that must hit.
OSA=$("$PY" - "$H" "$LANE_PY" "$WORK" <<'OSA_END'
import os, sys
def live(path):
    return ["%s:%d" % (os.path.basename(path), i)
            for i, line in enumerate(open(path, encoding="utf-8"), 1)
            if "osascript" in line and not line.lstrip().startswith("#")]
real = live(sys.argv[1]) + live(sys.argv[2])
planted = os.path.join(sys.argv[3], "planted-osascript.py")
with open(planted, "w", encoding="utf-8") as fh:
    fh.write('import subprocess\nsubprocess.run(["osascript", "-e", "tell application \\"Terminal\\" to activate"])\n')
print("%d %d %s" % (len(real), len(live(planted)), " ".join(real)))
OSA_END
)
case $OSA in "0 1"*) : ;; *) why="$why; osascript reachable: $OSA" ;; esac
verdict "no osascript reachable: every osascript left in handsoff.py and lane.py is on a comment line naming the retired route (control: a planted live call hits)"

# The claim of №162 is retired with the №163 ruling: no line of handsoff.py names its helpers or
# its life constant, and the only lines that spell its file name are the dated ones that call it
# retired — with a planted copy carrying live lines as the control that must hit.
RETIRED=$("$PY" - "$H" "$WORK" <<'RETIRED_END'
import os
import sys

NAMES = ("take_claim", "read_claim(", "release_claim", "claim_text", "CONSOLE_CLAIM_LIFE_S",
         "stale claim")


def live(path):
    hits = []
    with open(path, encoding="utf-8") as handle:
        for i, line in enumerate(handle, 1):
            if any(name in line for name in NAMES):
                hits.append("%s:%d" % (os.path.basename(path), i))
            # the claim file of №162, retired 2026-09-18: a line may spell it only where it
            # also says so
            elif ".opening" in line and "retired" not in line:
                hits.append("%s:%d" % (os.path.basename(path), i))
    return hits


real = live(sys.argv[1])
planted = os.path.join(sys.argv[2], "planted-claim.py")
with open(planted, "w", encoding="utf-8") as fh:
    # the planted control: two live lines naming the claim retired 2026-09-18, neither saying so
    fh.write('claim = console_command_path(run) + ".opening"\nheld, why = take_claim(claim)\n')
print("%d %d %s" % (len(real), len(live(planted)), " ".join(real)))
RETIRED_END
)
case $RETIRED in "0 2"*) : ;; *) why="$why; the retired claim is still named in handsoff.py: $RETIRED" ;; esac
verdict "the claim file of №162 is retired (the №163 ruling): no line of handsoff.py names its helpers, its takeover or its life constant, and every line that spells its file name calls it retired (control: a planted pair of live lines hits twice)"

fixture rvwpath 200
viewer_use vpath
RC=0
env PATH="$WORK/nopath" AIMYTH_OPEN_BIN="$WORK/nopath/open" AIMYTH_VIEWER_CMD= AIMYTH_VIEWER_ARGV="$VIEWER_ARGV" \
    LLM_WIKI_STORE="$STORE" AIMYTH_PROJECTS_DIR="$PROJECTS" AIMYTH_STATE_DIR="$STATE" \
    CLAUDE_PROJECT_DIR="$VAULT" "$PYEXE" -B "$H" successor --run rvwpath --meter-line "$METER" \
    --harness-bin "$WORK/bin/no-such-harness" --wait-s 1 --max-wait-s 5 --tick-s 1 \
    >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 0
need_out "viewer: no Terminal window"
need_out "first attempt: $WORK/nopath/open not found (no such file)"
need_out "retry: $WORK/nopath/open not found (no such file)"
need_absent "osascript"
need_out "run by hand: $PYABS -B"
need_no_viewer
sleep 2
# the positive control on the same premise: with the stub back, the same command opens one
fixture rvwpath2 200
viewer_use vpath2
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwpath2 --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: Terminal window opened on"
sleep 2
verdict "no opener at the path AIMYTH_OPEN_BIN names: it is named in one stderr line (first attempt and retry) with the by-hand command, nothing names osascript, and the primitive exits 0 (control: the same call with the opener in place opens one)"

fixture rvwdry 200
CF=$(console_cmd rvwdry); rm -f "$CF"
viewer_use vdry
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwdry --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "viewer: dry run"
need_out "would run:"
need_out "$CF"
need_nofile "$CF"
need_no_viewer
run resume-head --run rvwdry --dry-run --harness-bin "$WORK/bin/stubhead" --meter-line "$METER"
need_rc 0
need_out "viewer: dry run"
need_nofile "$CF"
need_no_viewer
REC="$STORE/spawn-records/rvwdry2.jsonl"; rm -f "$REC"
run run-open --run rvwdry2 --dry-run --session sid-vwdry2 --head "fixture head" --regime single \
    --regime-src owner --handoff "$VHO" --detail "dry" --pid 1
need_rc 0
need_out "viewer: dry run"
need_out "$(console_cmd rvwdry2)"
need_nofile "$(console_cmd rvwdry2)"
need_nofile "$REC"
need_no_viewer
verdict "--dry-run on run-open, successor and resume-head: the opener's command line is printed, nothing is called and no command file is written"

# ------------------------------- launch-check (register entry 2026-09-17 16:32) --
# The planted race: the check starts before the record holds the head-successor line and passes
# once the line appears (a subshell appends it 1.5 s later, as the detached starter did in the
# same second as LAUNCHED); the control is the single read the hand-written check made
# (--wait 0), which says NOT STARTED on the same record a moment earlier.
seed_fixture rlc1 200
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"unmetered (seed)","pack":true}' >/dev/null
run launch-check --run rlc1 --wait 0
need_rc 1
need_out "launch-check: rlc1 NOT STARTED · no live head within the 0 s deadline: the last head event is the head-exit at"
need_out "(no pid on it, so the starter has nothing to wait on: a seed exit, or an exit recorded without a pid); no head start after it (1 read(s))"
sleep 30 &
LC1HEAD=$!
( sleep 1.5; "$PY" "$MK" append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lc1\",\"pid\":$LC1HEAD,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null ) &
run launch-check --run rlc1 --wait 10 --poll-s 0.2
need_rc 0
need_out "launch-check: rlc1 STARTED · head-successor at"
need_out "(session sid-lc1) · pid $LC1HEAD alive ("
need_out "· model fable effort max · seen"
READS=$(sed -n 's/.*(\([0-9]*\) read(s)).*/\1/p' "$WORK/out")
[ "${READS:-0}" -ge 2 ] || why="$why; the check saw the line at its first read ($READS reads): the race was not replayed"
kill "$LC1HEAD"; wait "$LC1HEAD" 2>/dev/null || :
verdict "launch-check (must fire): a single read says NOT STARTED while the polled check started on the same record passes once the head-successor line lands, naming the live pid, the session and the model, after more than one read"

# The same race through a real detached successor: the check issued the moment successor
# returns finds the head the starter started (a harness that lives 8 s), with its real pid.
seed_fixture rlcrace 200
viewer_use vlcrace
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rlcrace --meter-line "$METER" --harness-bin "$WORK/bin/sleephead" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
run launch-check --run rlcrace --wait 20 --poll-s 0.2
need_rc 0
need_out "launch-check: rlcrace STARTED · head-successor at"
RLCPID=$(mk field "$REC" head-successor pid)
need_out "pid $RLCPID alive ("
need_out "model fixture-model effort max"
verdict "launch-check on a real seed launch: issued the moment successor returns, the check finds the head the detached starter started and names its pid from the record"

# The controls: a head that dies, no successor by the deadline (with a live predecessor the
# starter waits on, named with the advice on --wait), a closed run and an aborted starter.
seed_fixture rlcdead 200
sh -c 'exit 0' &
LCDEAD=$!
wait "$LCDEAD" || :
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcdead\",\"pid\":$LCDEAD,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
run launch-check --run rlcdead --wait 5
need_rc 1
need_out "launch-check: rlcdead NOT STARTED · the head-successor at"
need_out "(session sid-lcdead) names pid $LCDEAD, which is not alive · 0 s after the check began (1 read(s))"
verdict "launch-check (a head that died): a head-successor whose pid is gone ends the check at once with exit 1, naming the pid"

seed_fixture rlcwait 200
sleep 30 &
LCPRED=$!
mk append "$REC" "{\"event\":\"head-exit\",\"band\":60,\"context\":\"c\",\"pid\":$LCPRED,\"pack\":true}" >/dev/null
run launch-check --run rlcwait --wait 1 --poll-s 0.2
need_rc 1
need_out "launch-check: rlcwait NOT STARTED · no live head within the 1 s deadline: the last head event is the head-exit at"
need_out "(its pid $LCPRED is alive, so the starter waits for it up to its --wait-s (600 s by default): pass --wait above that bound); no head start after it"
READS=$(sed -n 's/.*(\([0-9]*\) read(s)).*/\1/p' "$WORK/out")
[ "${READS:-0}" -ge 3 ] || why="$why; the check polled only $READS time(s) inside a 1 s deadline at 0.2 s"
kill "$LCPRED"; wait "$LCPRED" 2>/dev/null || :
verdict "launch-check (no successor by the deadline): the check polls to the deadline, exits 1, names the head-exit it is still waiting behind and, since that head's pid is alive, says the starter waits on it and that --wait must exceed the starter's bound"

seed_fixture rlcclosed 200
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","pack":true}' >/dev/null
mk append "$REC" '{"event":"run-close","items":"fixture"}' >/dev/null
run launch-check --run rlcclosed --wait 5
need_rc 1
need_out "launch-check: rlcclosed NOT STARTED · the run is closed (run-close at"
need_out "(1 read(s))"
verdict "launch-check (a closed run): a run-close ends the check at once with exit 1, naming the close"

seed_fixture rlcabort 200
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"c","pack":true}' >/dev/null
mk append "$REC" '{"event":"successor-aborted","reason":"timeout","note":"predecessor pid 1 alive after 1 s"}' >/dev/null
run launch-check --run rlcabort --wait 5
need_rc 1
need_out "launch-check: rlcabort NOT STARTED · the starter aborted after the head-exit at"
need_out "(successor-aborted timeout at"
need_out "predecessor pid 1 alive after 1 s)"
verdict "launch-check (an aborted starter): a successor-aborted after the head-exit ends the check at once with exit 1, quoting the reason and the note"

# A `head exited` observation counts against a start only when it names that start's session:
# after a hand-over the OLD head's supervisor writes its observation after the new head started.
seed_fixture rlcexit 200
sleep 30 &
LCEXIT=$!
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcexit-new\",\"pid\":$LCEXIT,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"handed-over","note":"session sid-lcexit-old exit 0 after 100 s → handed-over"}' >/dev/null
run launch-check --run rlcexit --wait 0
need_rc 0
need_out "launch-check: rlcexit STARTED · head-successor at"
mk append "$REC" '{"event":"observation","phase":"","what":"head exited","exit_class":"error","note":"session sid-lcexit-new exit 1 after 3 s → error"}' >/dev/null
run launch-check --run rlcexit --wait 0
need_rc 1
need_out "launch-check: rlcexit NOT STARTED · the head of the head-successor at"
need_out "(session sid-lcexit-new) exited (head exited at"
need_out "session sid-lcexit-new exit 1 after 3 s → error)"
kill "$LCEXIT"; wait "$LCEXIT" 2>/dev/null || :
verdict "launch-check (a head that exited): the supervisor's head-exited observation naming the start's session ends the check with exit 1, while an older head's observation after a hand-over does not (the control on the same record)"

# The premises: a missing record, a malformed line, a reused pid, and the check run inside the
# run's own head — refused by name (the environment, the head's pid among this shell's
# ancestors, the session marker under a harness process) unless --detach-safe is given.
run launch-check --run rlcnone --wait 0
need_rc 2
need_lines
need_out "no run record at $REALSTORE/spawn-records/rlcnone.jsonl: run-open never ran, so there is no launch to confirm"
plain_fixture rlcplain
run launch-check --run rlcplain --wait 0
need_rc 2
need_out "no run-open event in"
verdict "launch-check (premises): a missing record and a plain lane record (no run-open) are each refused with exit 2 and one line naming the path"

seed_fixture rlcbad 200
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"c","pack":true}' >/dev/null
printf '{"event": "head-successor", "session_id": "sid-torn", "pid": 4\n' >> "$REC"
run launch-check --run rlcbad --wait 0
need_rc 1
need_out "launch-check: rlcbad NOT STARTED · no live head within the 0 s deadline: the last head event is the head-exit at"
need_out "(1 read(s)) · 1 unparseable line(s) skipped"
sleep 30 &
LCBAD=$!
# printf, not mk append: the fixture toolkit's own parser refuses a record holding a torn line.
NOWTS=$("$PY" -c 'import time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z"))')
printf '{"ts":"%s","run":"rlcbad","event":"head-successor","session_id":"sid-lcbad","pid":%s,"model":"fable","effort":"max"}\n' "$NOWTS" "$LCBAD" >> "$REC"
run launch-check --run rlcbad --wait 0
need_rc 0
need_out "launch-check: rlcbad STARTED · head-successor at"
need_out "(1 read(s)) · 1 unparseable line(s) skipped"
kill "$LCBAD"; wait "$LCBAD" 2>/dev/null || :
verdict "launch-check (a malformed line): a torn line is counted on the outcome line and never read as an event — the check still fails on the record around it and still passes on a later good line"

seed_fixture rlcreuse 200
sleep 30 &
LCREUSE=$!
OLDTS=$("$PY" -c 'import time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 120)))')
mk append "$REC" "{\"ts\":\"$OLDTS\",\"event\":\"head-successor\",\"session_id\":\"sid-lcreuse\",\"pid\":$LCREUSE,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
run launch-check --run rlcreuse --wait 0
need_rc 1
need_out "launch-check: rlcreuse NOT STARTED · the head-successor at $OLDTS (session sid-lcreuse) names pid $LCREUSE, which is alive but started"
need_out "s after the event: a reused pid, not that head"
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcreuse2\",\"pid\":$LCREUSE,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
run launch-check --run rlcreuse --wait 0
need_rc 0
need_out "launch-check: rlcreuse STARTED · head-successor at"
need_out "(session sid-lcreuse2) · pid $LCREUSE alive ("
kill "$LCREUSE"; wait "$LCREUSE" 2>/dev/null || :
verdict "launch-check (a reused pid): a live pid whose process started after the event that names it is a reused pid and exits 1 with the gap named, while the same pid on an event stamped at its start passes (the control)"

# Identity evidence that cannot be read never passes (critic review finding 1, must fire on the
# pre-fold check, which said STARTED with "its age could not be read"): under a ps that answers
# nothing the age of a live pid is unreadable, and an event stamped 120 s before that process —
# the critic's plant — is NOT STARTED by name, at a single read and at the deadline of a polled
# check; the control (a readable age on an event stamped at the process's start) passes; a start
# with no timestamp, or an unreadable one, fails by name at once.
seed_fixture rlcunver 200
sleep 30 &
LCUNVER=$!
OLDTS=$("$PY" -c 'import time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 120)))')
mk append "$REC" "{\"ts\":\"$OLDTS\",\"event\":\"head-successor\",\"session_id\":\"sid-lcunver\",\"pid\":$LCUNVER,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run launch-check --run rlcunver --wait 0
need_rc 1
need_out "launch-check: rlcunver NOT STARTED · pid identity unverifiable: the head-successor at $OLDTS (session sid-lcunver) names pid $LCUNVER, which is alive, but its age could not be read"
need_out "so a reused pid cannot be excluded"
need_absent "STARTED · head-successor"
RUNENV="PATH=$WORK/psnone:$PATH"
run launch-check --run rlcunver --wait 1 --poll-s 0.2
need_rc 1
need_out "launch-check: rlcunver NOT STARTED · pid identity unverifiable:"
need_out "left of the deadline"
READS=$(sed -n 's/.*(\([0-9]*\) read(s)).*/\1/p' "$WORK/out")
[ "${READS:-0}" -ge 2 ] || why="$why; the polled check gave up after $READS read(s) inside a 1 s deadline"
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcunver2\",\"pid\":$LCUNVER,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
run launch-check --run rlcunver --wait 0
need_rc 0
need_out "launch-check: rlcunver STARTED · head-successor at"
need_out "(session sid-lcunver2) · pid $LCUNVER alive ("
need_absent "unverifiable"
printf '{"run":"rlcunver","event":"head-successor","session_id":"sid-lcunver3","pid":%s,"model":"fable","effort":"max"}\n' "$LCUNVER" >> "$REC"
run launch-check --run rlcunver --wait 5
need_rc 1
need_out "launch-check: rlcunver NOT STARTED · pid identity unverifiable: the head-successor at no ts (session sid-lcunver3) carries no timestamp, so when pid $LCUNVER started cannot be checked against it"
need_out "(1 read(s))"
printf '{"ts":"yesterday","run":"rlcunver","event":"head-successor","session_id":"sid-lcunver4","pid":%s,"model":"fable","effort":"max"}\n' "$LCUNVER" >> "$REC"
run launch-check --run rlcunver --wait 5
need_rc 1
need_out "launch-check: rlcunver NOT STARTED · pid identity unverifiable: the head-successor at yesterday (session sid-lcunver4) carries an unreadable timestamp ('yesterday')"
need_out "(1 read(s))"
kill "$LCUNVER"; wait "$LCUNVER" 2>/dev/null || :
verdict "launch-check (critic review finding 1, must fire): a live pid whose age cannot be read, on an event stamped 120 s before the process, is NOT STARTED · pid identity unverifiable — at a single read and at the deadline of a polled check — while the same pid with a readable age on an event stamped at its start passes (the control), and a start with no timestamp or an unreadable one fails by name at once"

# The deadline governs every probe (critic review finding 3, must fire on a check that returns
# STARTED 3 s after a 1 s deadline): under a ps that answers only after 3 s the
# age probe is cut at the time left, so `--wait 1` ends at its deadline with the start unverified
# — exit 1 by name — and the same record under the real ps passes (the control). The stub slows
# every ps call, the refusal walk's included, so --detach-safe skips that walk: the leg measures
# the check's own deadline.
seed_fixture rlcslow 200
sleep 30 &
LCSLOW=$!
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcslow\",\"pid\":$LCSLOW,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
RUNENV="PATH=$WORK/psslow:$PATH PS_SLEEP_S=3"
T0=$(date +%s)
run launch-check --run rlcslow --wait 1 --poll-s 0.2 --detach-safe
T1=$(date +%s)
need_rc 1
need_out "launch-check: rlcslow NOT STARTED · pid identity unverifiable: the head-successor at"
need_out "(session sid-lcslow) names pid $LCSLOW, which is alive, but its age could not be read (\`ps -o etime=\` gave nothing within the 1.0 s left of the deadline)"
need_absent "STARTED · head-successor"
[ $((T1 - T0)) -le 2 ] || why="$why; the check took $((T1 - T0)) s against a 1 s deadline"
run launch-check --run rlcslow --wait 0
need_rc 0
need_out "launch-check: rlcslow STARTED · head-successor at"
kill "$LCSLOW"; wait "$LCSLOW" 2>/dev/null || :
verdict "launch-check (critic review finding 3, must fire): with a ps that answers only after 3 s, --wait 1 ends at its deadline within 2 s with exit 1 and names the unread age, never STARTED after the deadline; the same record under the real ps passes (the control)"

# The deadline is ONE budget that successive probes share (critic review pass 2 finding 3, must
# fire on a check that gives the command query the same bound the age query has already spent:
# two compliant probes of 0.75 s and 1 s would run 1.75 s against a 1 s deadline). The
# same two probes here: the check must end within its deadline plus one poll, still exit 1 (a
# start confirmed after the deadline is no start), and say so with the elapsed figure on its own
# line. --detach-safe skips the refusal walk, whose probes the stub would slow too.
seed_fixture rlcshare 200
sleep 30 &
LCSHARE=$!
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcshare\",\"pid\":$LCSHARE,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
RUNENV="PATH=$WORK/pssplit:$PATH PS_ETIME_SLEEP_S=1 PS_ROW_SLEEP_S=4"
SHT0=$(clock_f)
run launch-check --run rlcshare --wait 3 --poll-s 0.2 --detach-safe
SHT1=$(clock_f)
need_rc 1
need_out "launch-check: rlcshare NOT STARTED"
need_out "past the 3 s deadline"
CONF=$(sed -n 's/.*confirmed only \([0-9.]*\) s after the check began.*/\1/p' "$WORK/out")
need_eq "$(under "${CONF:-99}" 3.5)" "ok" "the check's own elapsed against its 3 s deadline (4 s before the fold: the age probe's second, then the whole deadline again for the command probe)"
need_eq "$(span_ok "$SHT0" "$SHT1" 5.0)" "ok" "the whole call, interpreter start included"
# The timely control: the same two probes at no cost at all return a start inside the deadline.
RUNENV="PATH=$WORK/pssplit:$PATH PS_ETIME_SLEEP_S=0 PS_ROW_SLEEP_S=0"
TMT0=$(clock_f)
run launch-check --run rlcshare --wait 3 --poll-s 0.2 --detach-safe
TMT1=$(clock_f)
need_rc 0
need_out "launch-check: rlcshare STARTED · head-successor at"
need_out "· seen 0 s after the check began (1 read(s))"
need_eq "$(span_ok "$TMT0" "$TMT1" 2.0)" "ok" "the timely control's whole call"
kill "$LCSHARE"; wait "$LCSHARE" 2>/dev/null || :
verdict "launch-check's shared deadline (critic review pass 2 finding 3, must fire): with an age probe of 1 s and a command probe that never answers, against --wait 3, the check ends AT its deadline — its own elapsed at most 3.5 s, where before the fold the command probe was handed the whole 3 s again and the check ran 4 s — still exits 1 on the late start, and the same probes at no cost return STARTED at the first read (the control)"

# A series of zero-cost probes neither exhausts the budget early nor overruns it: a record with no
# head start polls to the deadline, makes its reads, and ends inside it.
seed_fixture rlcfree 200
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"unmetered (seed)","pack":true}' >/dev/null
RUNENV="PATH=$WORK/pssplit:$PATH PS_ETIME_SLEEP_S=0 PS_ROW_SLEEP_S=0"
FRT0=$(clock_f)
run launch-check --run rlcfree --wait 1 --poll-s 0.2 --detach-safe
FRT1=$(clock_f)
need_rc 1
need_out "launch-check: rlcfree NOT STARTED · no live head within the 1 s deadline"
FREEREADS=$(sed -n 's/.*(\([0-9]*\) read(s)).*/\1/p' "$WORK/out")
[ "${FREEREADS:-0}" -ge 4 ] || why="$why; the zero-cost series made $FREEREADS read(s) inside a 1 s deadline at a 0.2 s poll"
need_eq "$(span_ok "$FRT0" "$FRT1" 2.5)" "ok" "the zero-cost series' whole call"
verdict "launch-check's shared deadline (the zero-cost control): probes that cost nothing leave the budget to the poll — a 1 s deadline at a 0.2 s poll makes at least four reads and still ends inside its deadline"

# The bound each probe is HANDED, read off the call itself (critic review pass 2 finding 3's
# second half: a helper must never be forwarded timeout=60 when its own stated bound is 10 s). A
# recording double for subprocess.run prices each probe and reports the timeout it was given.
BUDGET=$("$PY" -B - "$H" <<'BUDGET_END'
import importlib.util
import json
import os
import sys
import time

spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
seen, cost = [], [0.0]


class Done(object):
    def __init__(self, out):
        self.stdout, self.stderr, self.returncode = out, "", 0


def fake_run(argv, **kwargs):
    seen.append(round(float(kwargs.get("timeout", -1)), 2))
    if cost[0]:
        time.sleep(cost[0])
    return Done("00:05\n" if "etime=" in argv else "%s 1 sleep\n" % argv[-1])


ho.subprocess.run = fake_run
ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
events = [{"event": "run-open", "ts": ts, "run": "r", "session": "s", "session_kind": "seed"},
          {"event": "head-successor", "ts": ts, "run": "r", "session_id": "s", "pid": os.getpid()}]


def bounds(wait, per_probe):
    del seen[:]
    cost[0] = per_probe
    try:
        ho.head_start_verdict(events, budget=ho.probe_budget(wait))
    except (AttributeError, TypeError):        # the pre-fold shape: one figure for every probe
        ho.head_start_verdict(events, probe_s=(wait or None))
    return list(seen)


wide, tight, free = bounds(60, 0.0), bounds(1, 0.4), bounds(0, 0.0)
print(json.dumps({"cap_kept": wide == [10.0, 10.0],
                  "budget_shared": len(tight) == 2 and 0.9 <= tight[0] <= 1.0 and 0.4 <= tight[1] <= 0.65,
                  "no_deadline_keeps_cap": free == [10.0, 10.0],
                  "wide": wide, "tight": tight, "free": free}, sort_keys=True))
BUDGET_END
)
case $BUDGET in *'"cap_kept": true'*) : ;; *) why="$why; a 60 s deadline overran the probe's own 10 s cap: $BUDGET" ;; esac
case $BUDGET in *'"budget_shared": true'*) : ;; *) why="$why; the second probe did not draw on what the first left: $BUDGET" ;; esac
case $BUDGET in *'"no_deadline_keeps_cap": true'*) : ;; *) why="$why; a single read lost the probe's own cap (the control): $BUDGET" ;; esac
verdict "launch-check's probe bounds (critic review pass 2 finding 3, must fire): against a 60 s deadline each ps call is still handed its own 10 s cap and never the whole remainder, against a 1 s deadline the second probe is handed only what the first left, and with no deadline at all both keep the cap (the control)"

# A malformed pid on any event is named, never raised (critic review finding 5, must fire on the
# pre-fold check, which crashed with OverflowError and no outcome line): 10**40 on a head-exit,
# 10**40 on a head-successor, and a non-integer on a head-exit.
seed_fixture rlcbig 200
BIGTS=$("$PY" -c 'import time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z"))')
printf '{"ts":"%s","run":"rlcbig","event":"head-exit","band":60,"context":"c","pid":10000000000000000000000000000000000000000,"pack":true}\n' "$BIGTS" >> "$REC"
run launch-check --run rlcbig --wait 0
need_rc 1
need_out "launch-check: rlcbig NOT STARTED · no live head within the 0 s deadline: the last head event is the head-exit at"
need_out "(its pid 10000000000000000000000000000000000000000 is not a usable pid (an integer from 2 to 2147483647), so the starter has nothing to wait on); no head start after it"
need_absent "Traceback"
need_absent "OverflowError"
printf '{"ts":"%s","run":"rlcbig","event":"head-successor","session_id":"sid-lcbig","pid":10000000000000000000000000000000000000000,"model":"fable","effort":"max"}\n' "$BIGTS" >> "$REC"
run launch-check --run rlcbig --wait 0
need_rc 1
need_out "launch-check: rlcbig NOT STARTED · the head-successor at"
need_out "(session sid-lcbig) names no usable pid (10000000000000000000000000000000000000000): a live head cannot be confirmed from it"
need_absent "Traceback"
printf '{"ts":"%s","run":"rlcbig","event":"head-exit","band":60,"context":"c","pid":"abc","pack":true}\n' "$BIGTS" >> "$REC"
run launch-check --run rlcbig --wait 0
need_rc 1
need_out "(its pid 'abc' is not a usable pid (an integer from 2 to 2147483647), so the starter has nothing to wait on); no head start after it"
need_absent "Traceback"
verdict "launch-check (critic review finding 5, must fire): a pid of 10**40 on a head-exit or a head-successor, or a non-integer pid on a head-exit, is named on the outcome line with exit 1 and never raises"

seed_fixture rlcarm 200
sleep 30 &
LCARM=$!
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcarm\",\"pid\":$LCARM,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run launch-check --run rlcarm --wait 0
need_rc 2
need_lines
need_out "launch-check REFUSED inside the run's own head (AIMYTH_HANDSOFF=1 is set in this shell's environment): a head that called successor about itself must never wait on its own replacement"
need_out "or pass --detach-safe when this shell is not that head"
RUNENV="AIMYTH_HANDSOFF=1"
run launch-check --run rlcarm --wait 0 --detach-safe
need_rc 0
need_out "launch-check: rlcarm STARTED"
kill "$LCARM"; wait "$LCARM" 2>/dev/null || :
verdict "launch-check (refused inside an armed head, the environment form): AIMYTH_HANDSOFF=1 refuses with exit 2 and one line naming the variable and the remedy, and --detach-safe lets the same call run"

seed_fixture rlcanc 200
mk append "$REC" "{\"event\":\"head-exit\",\"band\":60,\"context\":\"c\",\"pid\":$$,\"pack\":true}" >/dev/null
run launch-check --run rlcanc --wait 0
need_rc 2
need_lines
need_out "launch-check REFUSED inside the run's own head (pid $$, named by the head-exit at"
need_out "is an ancestor of this shell)"
run launch-check --run rlcanc --wait 0 --detach-safe
need_rc 1
need_out "launch-check: rlcanc NOT STARTED · no live head within the 0 s deadline"
verdict "launch-check (refused inside the head, the ancestor form): a head-exit naming this shell's own ancestor pid — the process the starter waits for — refuses with exit 2, and --detach-safe runs the check (which then reports honestly)"

seed_fixture rlcmark 200
touch "$STATE/armed-sid-rlcmark"
RUNENV="PATH=$WORK/psclaude:$PATH"
run launch-check --run rlcmark --wait 0
need_rc 2
need_lines
need_out "launch-check REFUSED inside the run's own head (the session marker armed-sid-rlcmark is on disk and this shell runs under a claude process)"
rm -f "$STATE/armed-sid-rlcmark"
RUNENV="PATH=$WORK/psclaude:$PATH"
run launch-check --run rlcmark --wait 0
need_rc 1
need_out "launch-check: rlcmark NOT STARTED · no live head within the 0 s deadline: only the seed run-open at"
verdict "launch-check (refused inside the head, the marker form): the session marker for the record's head session under a harness ancestor refuses with exit 2, and without the marker the same call runs (the control)"

run launch-check --help
need_rc 0
need_out "--wait"
need_out "--poll-s"
need_out "--detach-safe"
run open-console --help
need_rc 0
need_out "--check"
need_out "--viewer"
verdict "help: launch-check names --wait, --poll-s and --detach-safe; open-console names --check and --viewer"

# ------------------------------------------ the seed pid (register entry 2026-09-07) -------
SHO="$WORK/handoffs/vseed-handoff.md"; mk handoff "$SHO" >/dev/null
PACK=$(printf 'Next: the next item\nNeeds: nothing\nDecided: the pid')
REC="$STORE/spawn-records/rseedpid.jsonl"; rm -f "$REC"
viewer_use vseed
run run-open --run rseedpid --session sid-seedpid --head "the launcher" --regime multi \
    --regime-src head --handoff "$SHO" --detail "a seeded record" --pid 93910 \
    --session-kind seed --envelope-usd 200
need_rc 0
need_eq "$(mk field "$REC" run-open pid)" "93910" "the seed's recorded pid"
# No --pid, and every ps row answers `claude`: the parent walk would take THIS shell's pid,
# which is the fault the register entry names. The seed's own recorded pid must win.
RUNENV="PATH=$WORK/psclaude:$PATH"
run handoff --run rseedpid --final --band 80 --inflight "$PACK"
need_rc 0
need_out "handoff: pid 93910 (run-open, seed)"
need_eq "$(mk field "$REC" head-exit pid)" "93910" "the head-exit takes the seed's pid"
need_absent "(parent-walk)"
verdict "handoff --final on a SEEDED record without --pid takes the seed run-open's pid and says so ('pid 93910 (run-open, seed)'), never the parent walk to the calling session"

REC="$STORE/spawn-records/rheadpid.jsonl"; rm -f "$REC"
run run-open --run rheadpid --session sid-headpid --head "a head" --regime multi \
    --regime-src head --handoff "$SHO" --detail "a head record" --pid 55555 --envelope-usd 200
need_rc 0
need_eq "$(mk field "$REC" run-open session_kind)" "head" "not a seed"
RUNENV="PATH=$WORK/psclaude:$PATH"
run handoff --run rheadpid --final --band 80 --inflight "$PACK"
need_rc 0
need_out "(parent-walk)"
need_absent "(run-open, seed)"
if [ "$(mk field "$REC" head-exit pid)" = "55555" ]; then
  why="$why; the head record's head-exit took the run-open pid instead of the walk"
fi
REC="$STORE/spawn-records/rheadpid2.jsonl"; rm -f "$REC"
run run-open --run rheadpid2 --session sid-headpid2 --head "a head" --regime multi \
    --regime-src head --handoff "$SHO" --detail "no ancestor" --pid 55555 --envelope-usd 200
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run rheadpid2 --final --band 80 --inflight "$PACK"
need_rc 0
need_out "handoff: pid none (none)"
need_eq "$(mk field "$REC" head-exit pid)" "<no key pid>" "no pid on the head-exit"
verdict "handoff --final on a HEAD record is unchanged: the parent walk still decides (parent-walk under the claude ps stub, none under the empty one), and the run-open pid is never taken"

# The same rule where `successor` writes the FIRST head-exit itself (register entry 2026-09-08):
# the head never wrote one, so the pid on it — and the predecessor pid the starter then waits
# on, which reads that event — came from the parent walk. Under the psclaude stub every ps row
# answers `claude`, so the walk would take THIS shell's pid and the starter would wait on the
# suite instead of the launcher shell: the fault the seed pid closes.
REC="$STORE/spawn-records/rsucseed.jsonl"; rm -f "$REC"
run run-open --run rsucseed --session sid-sucseed --head "the launcher" --regime multi \
    --regime-src head --handoff "$SHO" --detail "a seeded record" --pid 93911 \
    --session-kind seed --envelope-usd 200 --model fixture-model
need_rc 0
need_eq "$(mk field "$REC" run-open pid)" "93911" "the seed's recorded pid"
RUNENV="PATH=$WORK/psclaude:$PATH"
run successor --run rsucseed --dry-run --budget-usd 5 --meter-line "$METER" \
    --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "successor: pid 93911 (run-open, seed)"
need_absent "(parent-walk)"
need_eq "$(mk field "$REC" head-exit pid)" "<no head-exit event>" "the dry run wrote no head-exit"
# The real run, which appends the head-exit before it detaches its starter. --budget-usd is any
# cap at all (it only keeps the meter out of the leg, as the seed skip already would); the
# harness name does not exist and the three waits are 1/5/1 s, so the detached starter finds
# nothing to start and gives up at once — the pattern the viewer successor legs above use.
RUNENV="PATH=$WORK/psclaude:$PATH"
run successor --run rsucseed --budget-usd 5 --meter-line "$METER" \
    --harness-bin "$WORK/bin/no-such-harness" --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "successor: pid 93911 (run-open, seed)"
need_eq "$(mk field "$REC" head-exit pid)" "$(mk field "$REC" run-open pid)" "the head-exit's pid is the run-open's"
verdict "successor on a SEEDED record without --pid takes the seed run-open's pid for the first head-exit it writes ('successor: pid 93911 (run-open, seed)'), never the parent walk to the calling session"

REC="$STORE/spawn-records/rsuchead.jsonl"; rm -f "$REC"
run run-open --run rsuchead --session sid-suchead --head "a head" --regime multi \
    --regime-src head --handoff "$SHO" --detail "a head record" --pid 55556 --envelope-usd 200 \
    --model fixture-model
need_rc 0
need_eq "$(mk field "$REC" run-open session_kind)" "head" "not a seed"
RUNENV="PATH=$WORK/psclaude:$PATH"
run successor --run rsuchead --budget-usd 5 --meter-line "$METER" \
    --harness-bin "$WORK/bin/no-such-harness" --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "(parent-walk)"
need_absent "(run-open, seed)"
XPID=$(mk field "$REC" head-exit pid)
if [ "$XPID" = "$(mk field "$REC" run-open pid)" ]; then
  why="$why; the head record's head-exit took the run-open pid (55556) instead of the walk"
fi
case $XPID in
  ''|*[!0-9]*) why="$why; positive control: the walk recorded no pid on the head-exit ('$XPID')" ;;
esac
verdict "successor on a HEAD record is unchanged: the parent walk decides the first head-exit's pid (a live pid under the claude ps stub, never the run-open's 55556)"

REC="$STORE/spawn-records/rsucarg.jsonl"; rm -f "$REC"
run run-open --run rsucarg --session sid-sucarg --head "the launcher" --regime multi \
    --regime-src head --handoff "$SHO" --detail "a seeded record" --pid 93911 \
    --session-kind seed --envelope-usd 200 --model fixture-model
need_rc 0
RUNENV="PATH=$WORK/psclaude:$PATH"
run successor --run rsucarg --dry-run --pid 41414 --budget-usd 5 --meter-line "$METER" \
    --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "successor: pid 41414 (arg)"
need_absent "(run-open, seed)"
# A seed run-open with no pid yields no pid and runs no walk (register 2026-09-12 20:0x): under the
# claude ps stub the walk would take this shell's pid, so any pid here would be the fault.
REC="$STORE/spawn-records/rsucnopid.jsonl"; rm -f "$REC"
RUNENV="PATH=$WORK/psclaude:$PATH"
run run-open --run rsucnopid --session sid-sucnopid --head "the launcher" --regime multi \
    --regime-src head --handoff "$SHO" --detail "a seed with no pid" --session-kind seed \
    --envelope-usd 200 --model fixture-model
need_rc 0
need_eq "$(mk field "$REC" run-open session_kind)" "seed" "a seeded record"
need_eq "$(mk field "$REC" run-open pid)" "<no key pid>" "no pid of its own, a live claude parent notwithstanding"
RUNENV="PATH=$WORK/psclaude:$PATH"
run successor --run rsucnopid --dry-run --budget-usd 5 --meter-line "$METER" \
    --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "successor: pid none (run-open, seed: no pid)"
need_absent "(parent-walk)"
need_out "so no wait"
verdict "successor: --pid wins on a seeded record ('pid 41414 (arg)'), and a seed run-open with no pid yields no pid, no walk and no wait ('pid none (run-open, seed: no pid)', register 2026-09-12 20:0x)"

# --------------------------------------------------------------------- controls ------------
"$PY" - "$H" > "$WORK/shipsafe.txt" <<'SHIPSAFE'
import re, sys
PATTERNS = (("owner path", r"/(?:Users|home)/[A-Za-z0-9._-]+"),
            # a user or store name is the payload gate's derived needle, never a literal here
            ("session id", r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
            ("uid", r"\buid=\d+\b"),
            ("run id", r"\brun-20\d{6}[A-Za-z0-9-]*"))
src = open(sys.argv[1], encoding="utf-8").read()
total = 0
for name, pattern in PATTERNS:
    hits = re.findall(pattern, src)
    total += len(hits)
    if hits:
        print("%s: %s" % (name, ", ".join(sorted(set(hits))[:4])))
print("hits %d" % total)
SHIPSAFE
SHIP=$(tail -1 "$WORK/shipsafe.txt")
need_eq "$SHIP" "hits 0" "ship-safe sweep of handsoff.py"
# Assembled from parts, so this file's own source carries no owner path, session id or run id.
{ printf 'HOME_DIR = "%s%s"\n' "/Users" "/example-owner/vault"
  printf 'SESSION = "%s-1111-2222-3333-444455556666"\n' "0a0a0a0a"
  printf 'RUN = "%s%s"\n' "run-2026" "0101-example"; } > "$WORK/planted-owner.py"
SHIPCTRL=$("$PY" - "$WORK/planted-owner.py" <<'SHIPSAFE2' | tail -1
import re, sys
PATTERNS = (("owner path", r"/(?:Users|home)/[A-Za-z0-9._-]+"),
            # a user or store name is the payload gate's derived needle, never a literal here
            ("session id", r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
            ("uid", r"\buid=\d+\b"),
            ("run id", r"\brun-20\d{6}[A-Za-z0-9-]*"))
src = open(sys.argv[1], encoding="utf-8").read()
total = sum(len(re.findall(p, src)) for _, p in PATTERNS)
print("hits %d" % total)
SHIPSAFE2
)
need_eq "$SHIPCTRL" "hits 3" "positive control: the planted file's three literals"
verdict "ship-safe: no owner path, session id, uid or run id is a literal in handsoff.py ($SHIP; control: 3 planted hits; names are the payload gate's derived needles)"

NEG=$(grep -c 'tests the wrong' "$H")
need_eq "$NEG" "0" "negative control: the lifted refusal's phrase"
POS=$(grep -c 'unmetered-loop' "$H")
[ "$POS" -ge 1 ] || why="$why; positive control: 'unmetered-loop' count $POS"
verdict "controls: 'tests the wrong' absent from handsoff.py ($NEG); 'unmetered-loop' present ($POS)"

fixture rclose2 200
printf 'a change to close over %s\n' "$N" > "$VAULT/notes.txt"
RUNENV="PATH=$WORK/psnone:$PATH"
run close --run rclose2 --items "fixture items" --meter-line "$METER" --commit "fixture: the closing commit" --push
need_rc 0
need_out "push ok"
need_eq "$(mk field "$REC" run-close push)" "ok" "push"
need_eq "$(git -C "$VAULT" rev-parse HEAD)" "$(git -C "$REMOTE" rev-parse HEAD)" "remote head"
verdict "close --commit --push: the commit is made and pushed to the fixture remote"

# The write proof's three legs stand at the END of the suite (moved there 2026-10-10: legs added
# after them for a month ran outside the manifest's window, against the header's own claim).

# ------------------------------------------ waste fields (register, 2026-09-05) ------------
# The three boundary fields whose labels said more than they measured: idle_min is head
# idleness (time in the span when no lane was running and the head made no call, a head gap
# counting only above 60 s) read from the head's transcript, with the record-only measure
# kept as a labelled fallback; respawn_cost_usd leaves out a cut lane that a later
# lane-resumed picked up; rewrites is the change since the same head's previous boundary.
# Every timestamp is placed relative to N, the clock at fixture time, so each figure is
# arithmetic. Span: a planted boundary at N-1000 to the boundary under test (about N). Lane
# L1 runs N-900..N-600; the head calls at N-1000, N-900, N-870, N-300 and N. Gaps above 60 s:
# N-1000..N-900 = 100 s (no lane); N-870..N-300 = 570 s, of which N-870..N-600 = 270 s under
# L1, so 300 s; N-300..N = 300 s; the last gap, to the boundary itself, is seconds. Idle =
# 700 s = 11.7 min. The record-only measure on the same events is L1's close (N-600) to the
# head's next recorded act (the observation at N-300) = 5.0 min, which the transcript-less
# control reads and labels idle_src record.
cat > "$WORK/idle-fixture.py" <<'BH2_IDLE_FIXTURE_END'
import json, os, re, sys, time
rec, sid, mode = sys.argv[1], sys.argv[2], sys.argv[3]
now = time.time()
stamp = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))
zulu = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"
with open(rec, encoding="utf-8") as fh:
    run = json.loads(fh.readline())["run"]
events = [
    {"event": "phase-boundary", "from": "0", "to": "1", "ts": stamp(now - 1000),
     "next": "the planted span start"},
    {"event": "lane-open", "lane": "L1", "ts": stamp(now - 900), "class": "builder"},
    {"event": "lane-closed", "lane": "L1", "ts": stamp(now - 600), "exit_class": "completed",
     "total_cost_usd": 1.0, "report_words": 10},
    {"event": "observation", "ts": stamp(now - 300), "what": "the head's next recorded act"},
]
with open(rec, "a", encoding="utf-8") as fh:
    for ev in events:
        ev["run"] = run
        fh.write(json.dumps(ev) + "\n")
if mode == "transcript":
    slug = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"]))
    path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], slug, sid + ".jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for t in (now - 1000, now - 900, now - 870, now - 300, now):
            # What the head was waiting on lands just as it answers, so each gap ends in a wait.
            fh.write(json.dumps({"type": "user", "isSidechain": False, "timestamp": zulu(t),
                                 "message": {"role": "user", "content": "the wait's end"}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "isSidechain": False, "timestamp": zulu(t),
                                 "message": {"role": "assistant", "model": "claude-fixture-1",
                                             "usage": {"input_tokens": 100,
                                                       "cache_read_input_tokens": 1,
                                                       "cache_creation_input_tokens": 1}}}) + "\n")
print("planted")
BH2_IDLE_FIXTURE_END

fixture ridle 200
"$PY" "$WORK/idle-fixture.py" "$REC" sid-ridle transcript >/dev/null
run boundary --run ridle --from 1 --to 2 --disposition "head idle" --waste "none" --next "n" \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary idle_min)" "11.7" "idle_min from the transcript"
need_eq "$(mk field "$REC" phase-boundary idle_src)" "transcript" "idle_src"
need_out "idle 11.7 min"
need_out "idle src transcript"
verdict "waste fields: idle_min is head idleness from the head's transcript — 700 s of gaps above 60 s outside the lane's running time = 11.7 min, labelled idle_src transcript"

# G53 (register 2026-10-15 01:33 e), its idle third: the same span with every gap ending in the
# head's own record is its generation, so it reads 0.0, where the old rule read the 700 s; the
# leg above, with each gap ending in a wait, is the control. A real transcript's request record
# opens the generation, so it lands a second after the head's last record and the gap is after it.
fixture rgen 200
"$PY" "$WORK/idle-fixture.py" "$REC" sid-rgen transcript >/dev/null
"$PY" - "$PROJECTS" "$VAULT" sid-rgen <<'GENSCRIPT'
import calendar, json, os, re, sys, time
path = os.path.join(sys.argv[1], re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(sys.argv[2])), sys.argv[3] + ".jsonl")
heads = [r for r in (json.loads(line) for line in open(path, encoding="utf-8")) if r["type"] == "assistant"]
out = []
for rec in heads:
    out.append(json.dumps(rec))
    at = calendar.timegm(time.strptime(rec["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")) + 1
    out.append(json.dumps({"type": "api-request", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(at)) + ".000Z"}))
open(path, "w", encoding="utf-8").write("\n".join(out[:-1]) + "\n")
GENSCRIPT
run boundary --run rgen --from 1 --to 2 --disposition "head generating" --waste "none" --next "n" \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary idle_min)" "0.0" "the head's own generation is no idle"
need_eq "$(mk field "$REC" phase-boundary idle_src)" "transcript" "idle_src"
need_eq "$(mk field "$REC" phase-boundary idle_rule)" "waits" "the rule the figure was measured on"
verdict "G53 (fails on old): a transcript gap that ends in the head's own record is its generation and no idle minute, and the boundary names the rule it was measured on"

# G53, its other two thirds. An empty preview the head asked for is no cut: the planted case is
# report_shown 0, the control a real cut of the same report. The context rows name the item that
# grew and never difference two heads: the planted case is a gate each side of a hand-over.
fixture rgen2 200
mk append "$REC" '{"event":"lane-closed","lane":"LE","exit_class":"completed","total_cost_usd":1.0,"report_words":2000,"report_cut":true,"report_shown":0}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LC","exit_class":"completed","total_cost_usd":1.0,"report_words":2000,"report_cut":true,"report_shown":800}' >/dev/null
run boundary --run rgen2 --from 1 --to 2 --disposition "previews" --waste "none" --next "n" --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary over_cap_reports)" "1" "the real cut alone"
mk append "$REC" '{"event":"gate","item":"one","context":100000,"percent":10,"band":0,"metered":true}' >/dev/null
mk append "$REC" '{"event":"gate","item":"two","context":140000,"percent":14,"band":0,"metered":true}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rgen2b","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"run-resume","session":"sid-rgen2b","head":"fixture head","detail":"the successor records itself","pid_src":"none"}' >/dev/null
mk append "$REC" '{"event":"gate","item":"three","context":60000,"percent":6,"band":0,"metered":true}' >/dev/null
mk append "$REC" '{"event":"gate","item":"four","context":90000,"percent":9,"band":0,"metered":true}' >/dev/null
WTG="$WORK/rgen2-table.md"
run waste-table --run rgen2 --out "$WTG"
need_rc 0
need_eq "$(grep -c 'context · item one, to the gate of item two at .* | +40,000 tokens' "$WTG")" "1" "item one's growth, on item one"
need_eq "$(grep -c 'context · item three at .* | 60,000 tokens · no comparable preceding gate' "$WTG")" "1" "the hand-over, differenced with nothing"
need_eq "$(grep -c 'context · item three, to the gate of item four at .* | +30,000 tokens' "$WTG")" "1" "the second head's own growth"
need_eq "$(grep -c '| -80,000 tokens' "$WTG")" "0" "no delta across the hand-over"
need_eq "$(grep -c 'context · item two at .* | +40,000' "$WTG")" "0" "the growth is not on the later item"
verdict "G53 (fails on old): an empty preview the head asked for counts as no cut beside a real one, and the context rows name the item that grew and never difference one head's gate with the next head's"

# G53, the review's F5: an unmetered gate between two metered ones. The interval spans two items, so
# no single-item delta exists; the planted case is the +200 that used to land on item one, and the
# control is the ordinary adjacent pair after it.
fixture rgen3 200
mk append "$REC" '{"event":"gate","item":"one","context":100,"percent":1,"band":0,"metered":true}' >/dev/null
mk append "$REC" '{"event":"gate","item":"two","percent":2,"band":0,"metered":false}' >/dev/null
mk append "$REC" '{"event":"gate","item":"three","context":300,"percent":3,"band":0,"metered":true}' >/dev/null
mk append "$REC" '{"event":"gate","item":"four","context":450,"percent":4,"band":0,"metered":true}' >/dev/null
WTG="$WORK/rgen3-table.md"
run waste-table --run rgen3 --out "$WTG"
need_rc 0
need_eq "$(grep -c '| +200 tokens' "$WTG")" "0" "no delta across the unmetered gate"
need_eq "$(grep -c 'context · item two at .* | unmeasured · the gate is unmetered' "$WTG")" "1" "the unmetered gate named"
need_eq "$(grep -c 'context · item three at .* | 300 tokens · no comparable preceding gate' "$WTG")" "1" "the gate after it, differenced with nothing"
need_eq "$(grep -c 'context · item three, to the gate of item four at .* | +150 tokens' "$WTG")" "1" "control: the adjacent pair after it"
verdict "G53 F5 (fails on old): a gate after an unmetered gate takes no single-item delta, while ordinary adjacent gates still do"

fixture ridle2 200
"$PY" "$WORK/idle-fixture.py" "$REC" sid-ridle2 none >/dev/null
run boundary --run ridle2 --from 1 --to 2 --disposition "no transcript" --waste "none" --next "n" \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary idle_min)" "5.0" "idle_min from the record"
need_eq "$(mk field "$REC" phase-boundary idle_src)" "record" "idle_src"
need_out "idle src record"
verdict "waste fields: the same events without a head transcript fall back to the record-only measure (5.0 min, each close to the head's next act) and say so with idle_src record (the control: the two figures differ)"

fixture rresp 200
mk append "$REC" '{"event":"lane-open","lane":"C1","class":"builder"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"C1","session_id":"lane-c1","exit_class":"limit","total_cost_usd":4.0,"report_words":5}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"C1","session_id":"lane-c1","resume_n":1}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"C1","session_id":"lane-c1","exit_class":"completed","total_cost_usd":1.0,"report_words":5,"resumed":true}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"C2","exit_class":"budget","total_cost_usd":2.5,"report_words":5}' >/dev/null
run boundary --run rresp --from 1 --to 2 --disposition "a resumed cut" --waste "none" --next "n" \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary respawn_cost_usd)" "2.5" "respawn_cost_usd"
need_eq "$(mk field "$REC" phase-boundary respawn_excluded)" "1" "respawn_excluded"
need_out "re-spawn \$2.50"
need_out "1 resumed lane(s) excluded from re-spawn"
verdict "waste fields: respawn_cost_usd leaves out the cut lane a later lane-resumed picked up (C1, \$4.00) and keeps the one nobody resumed (C2, \$2.50)"

fixture rresp2 200
mk append "$REC" '{"event":"lane-closed","lane":"C1","exit_class":"limit","total_cost_usd":4.0,"report_words":5}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"C2","exit_class":"budget","total_cost_usd":2.5,"report_words":5}' >/dev/null
run boundary --run rresp2 --from 1 --to 2 --disposition "no resume" --waste "none" --next "n" \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary respawn_cost_usd)" "6.5" "respawn_cost_usd"
need_eq "$(mk field "$REC" phase-boundary respawn_excluded)" "0" "respawn_excluded"
need_out "re-spawn \$6.50"
need_absent "excluded from re-spawn"
verdict "waste fields: the same two cuts with no lane-resumed both count (\$6.50, none excluded) — the control for the leg above"

fixture rrew 200
run boundary --run rrew --from 1 --to 2 --disposition "first" --waste "none" --next "n" \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary rewrites)" "3" "the first boundary keeps the billed figure"
need_eq "$(mk field "$REC" phase-boundary rewrites_total)" "3" "rewrites_total"
need_eq "$(mk field "$REC" phase-boundary rewrites_since)" "head start" "rewrites_since"
METER5=$(printf '%s' "$METER" | sed 's/rewrites 3 (/rewrites 5 (/')
run boundary --run rrew --from 2 --to 3 --disposition "second" --waste "none" --next "n" \
    --meter-line "$METER5"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary rewrites)" "2" "the change since the previous boundary"
need_eq "$(mk field "$REC" phase-boundary rewrites_total)" "5" "rewrites_total"
case $(mk field "$REC" phase-boundary rewrites_since) in
  "1 → 2 at "*) : ;;
  *) why="$why; rewrites_since does not name the previous boundary: $(mk field "$REC" phase-boundary rewrites_since)" ;;
esac
need_out "rewrites 2 "
verdict "waste fields: rewrites is the change since this head's previous boundary (billed 3 then 5: fields 3, then 2), the first boundary keeping the figure and the second naming its base"

RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rrew --session sid-rrew-2 --head "successor" --detail "a second head"
need_rc 0
METER7=$(printf '%s' "$METER" | sed 's/rewrites 3 (/rewrites 7 (/')
run boundary --run rrew --from 3 --to 4 --disposition "the successor's first" --waste "none" \
    --next "n" --meter-line "$METER7"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary rewrites)" "7" "a new head's first boundary keeps its figure"
need_eq "$(mk field "$REC" phase-boundary rewrites_since)" "head start" "rewrites_since"
verdict "waste fields: a successor head's first boundary keeps its own billed figure (7, not 7 - 5): the change never crosses heads (the control for the leg above)"

WTR="$WORK/rresp-table.md"
run waste-table --run rresp --out "$WTR"
need_rc 0
need_eq "$(grep -c 'cut lane · C1 · exit class limit · resumed | \$4.00 · lane-closed.total_cost_usd · C1 at .* · resumed at .*, so not lost (excluded from respawn_cost_usd) | real | no fix' "$WTR")" "1" "the resumed cut lane's row"
need_eq "$(grep -c 'lost lane · C2 · exit class budget | \$2.50' "$WTR")" "1" "the lost lane's row"
need_eq "$(grep -c '(1 resumed lane(s) excluded)' "$WTR")" "1" "the respawn field's source"
need_eq "$(grep -c '(idle_src record)' "$WTR")" "1" "the idle field's source (the record fallback)"
need_eq "$(grep -c 'change since head start (this head' "$WTR")" "1" "the rewrites field's source"
need_eq "$(grep -c 'Field meanings (2026-09-06)' "$WTR")" "1" "the legend"
WTI="$WORK/ridle-table.md"
run waste-table --run ridle --out "$WTI"
need_rc 0
need_eq "$(grep -c '| 11.7 min · phase-boundary.idle_min · head idle: no lane running and the head waiting, gaps above 60 s that end in something other than the head.s own record, read from its transcript (idle_src transcript)' "$WTI")" "1" "the transcript-sourced idle row"
verdict "waste-table: the rows say the new meanings and their source — the resumed cut lane is not lost, the lost-lane cost names its exclusion, idle names transcript or record, rewrites names its base — and the legend carries them"

# This table is the reader of the soft cap the wrapper logs at every close (critic finding
# F4, 2026-09-07): a completed lane over its class's soft threshold gets a row of its own, a
# lost one carries the note on the row it already had, and a close without the flag gets none.
fixture rsoft 200
mk append "$REC" '{"event":"lane-closed","lane":"S1","exit_class":"completed","total_cost_usd":12.0,"soft_usd":9.67,"soft_exceeded":true,"report_words":5}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"S2","exit_class":"completed","total_cost_usd":1.0,"soft_usd":9.67,"soft_exceeded":false,"report_words":5}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"S3","exit_class":"budget","total_cost_usd":3.0,"soft_usd":2.14,"soft_exceeded":true,"report_words":5}' >/dev/null
WSC="$WORK/rsoft-table.md"
run waste-table --run rsoft --out "$WSC" --no-meter
need_rc 0
need_eq "$(grep -c 'soft-cap lane · S1 · exit class completed | soft-cap: \$12.00 over \$9.67 (class) · lane-closed.soft_exceeded · logged at the close, never a stop | arguable | unrouted' "$WSC")" "1" "the completed lane's soft-cap row"
need_eq "$(grep -c 'S2' "$WSC")" "0" "a close whose soft_exceeded is false gets no row (the control)"
verdict "waste-table (F4): a completed lane billed over its class's soft threshold gets a row of its own, arguable in kind and routed like any other finding, while a close carrying soft_exceeded false gets none"

need_eq "$(grep -c 'lost lane · S3 · exit class budget | \$3.00 · lane-closed.total_cost_usd · S3 at .* · soft-cap: \$3.00 over \$2.14 (class) | real | unrouted' "$WSC")" "1" "the lost lane's row carries the note"
need_eq "$(grep -c 'soft-cap' "$WSC")" "3" "the two rows and the legend sentence, and nothing else"
need_eq "$(grep -c 'the line is logged, never a stop, and the head ledgers it at the lane.s close' "$WSC")" "1" "the legend sentence"
verdict "waste-table (F4): a lost lane that also crossed its soft threshold carries the note on the row it already had, and the legend says the threshold is logged rather than enforced and where the head puts it"

fixture rold 200
B0=$(printf '{"event":"phase-boundary","from":"1","to":"2","meter":"%s","idle_min":2.0,"denials":0,"over_cap_reports":0,"respawn_cost_usd":1.0,"rewrites":3}' "$METER")
mk append "$REC" "$B0" >/dev/null
WTO="$WORK/rold-table.md"
run waste-table --run rold --out "$WTO"
need_rc 0
need_eq "$(grep -c 'a boundary written before the head-idle rule (no idle_src)' "$WTO")" "1" "the old idle row"
need_eq "$(grep -c 'a boundary written before the resume exclusion' "$WTO")" "1" "the old respawn row"
need_eq "$(grep -c 'a boundary written before the delta rule' "$WTO")" "1" "the old rewrites row"
need_eq "$(grep -c 'idle_src transcript' "$WTO")" "1" "the transcript source named by the legend only"
verdict "waste-table: a boundary written before the 2026-09-06 meanings is quoted as recorded, each of the three rows naming the rule it predates (the control: the new-meaning strings appear in the legend alone)"

# ------------------------------- the five fixes of 2026-09-07 (T6, T7, T8 and two entries) --
# (a) T7: run-open --session-kind, written as session_kind, and the seed session skipped by the
# waste table's head rows and named once in its legend line.
HO="$WORK/handoffs/rskind-handoff.md"; mk handoff "$HO" >/dev/null
REC="$STORE/spawn-records/rskind.jsonl"; rm -f "$REC"
run run-open --run rskind --session sid-seedplace --head "launcher" --regime multi \
    --regime-src owner --handoff "$HO" --detail "a seeded launch" --pid 4242 \
    --envelope-usd 400 --session-kind seed
need_rc 0
need_out "session_kind seed"
need_eq "$(mk field "$REC" run-open session_kind)" "seed" "session_kind on the run-open event"
HO2="$WORK/handoffs/rhkind-handoff.md"; mk handoff "$HO2" >/dev/null
rm -f "$STORE/spawn-records/rhkind.jsonl"
run run-open --run rhkind --session sid-realhead --head "head" --regime multi \
    --regime-src owner --handoff "$HO2" --detail "an ordinary launch" --pid 4242
need_rc 0
need_eq "$(mk field "$STORE/spawn-records/rhkind.jsonl" run-open session_kind)" "head" \
        "positive control: the default is head, never absent"
verdict "run-open: --session-kind seed is written as session_kind on the run-open event and named on the line, and the flag defaults to head (T7)"

mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"unmetered (transcript missing: a path that is not there)","exit_class":"error","pack":false}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-realsucc","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"run-resume","session":"sid-realsucc","head":"h","detail":"the successor records itself","pid_src":"none"}' >/dev/null
mk append "$REC" '{"event":"gate","item":"one","context":100000,"percent":10,"band":0,"metered":true,"orientation_tokens":4000}' >/dev/null
WSK="$WORK/rskind-table.md"
run waste-table --run rskind --out "$WSK" --no-meter
need_rc 0
need_eq "$(grep -c '1 head session(s)' "$WSK")" "1" "the seed session is not a head session"
need_eq "$(grep -c 'seed (skipped): sid-seedplace' "$WSK")" "1" "one seed line in the legend"
need_eq "$(grep -c '^| orientation cost · head sid-realsucc' "$WSK")" "1" "positive control: the real head still has its row"
need_eq "$(grep -c '^| orientation cost · head sid-seedplace' "$WSK")" "0" "the seed session renders no head row"
need_eq "$(grep -c 'Head sessions are counted by DISTINCT session id (sid-realsucc)' "$WSK")" "1" "the head named is the real one"
WSK2="$WORK/rwaste-noseed.md"
run waste-table --run rwaste --out "$WSK2" --no-meter
need_eq "$(grep -c 'seed (skipped): none' "$WSK2")" "1" "control: a record marking no seed says so rather than dropping the line"
verdict "waste-table: a session run-open marks seed is skipped by the head rows and named once as 'seed (skipped)', while a record with no seed says none (T7)"

# (b) T6: the run's own window, and the --start/--end pair passed to the meter.
fixture rwin 200
mk append "$REC" '{"event":"phase-boundary","from":"1","to":"2","idle_min":0.0}' >/dev/null
mk append "$REC" '{"event":"run-close","items":"1","register":"none"}' >/dev/null
"$PY" - "$H" "$REC" <<'WINDOW' > "$WORK/window.txt"
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
evs = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
start, end, src = mod.run_window(evs)
cmd = mod.meter_cmd("/nowhere/fable-share.py", "rwin", "sid-rwin", mod.run_open(evs), "auto",
                    start, end)
print(start)
print(end)
print(src)
print(" ".join(cmd))
WINDOW
need_eq "$(sed -n 1p "$WORK/window.txt")" "$(mk field "$REC" run-open ts)" "the window opens at run-open"
need_eq "$(sed -n 2p "$WORK/window.txt")" "$(mk field "$REC" run-close ts)" "the window closes at run-close"
case $(sed -n 4p "$WORK/window.txt") in
  *"--start $(mk field "$REC" run-open ts) --end $(mk field "$REC" run-close ts)"*) : ;;
  *) why="$why; the meter command carries no --start/--end pair: $(sed -n 4p "$WORK/window.txt")" ;;
esac
fixture rwin2 200
mk append "$REC" '{"event":"phase-boundary","from":"1","to":"2","idle_min":0.0}' >/dev/null
"$PY" - "$H" "$REC" <<'WINDOW2' > "$WORK/window2.txt"
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
evs = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
start, end, src = mod.run_window(evs)
print(end)
print(src)
WINDOW2
need_eq "$(sed -n 1p "$WORK/window2.txt")" "$(mk field "$REC" phase-boundary ts)" "control: no run-close ends the window at the record's last event"
case $(sed -n 2p "$WORK/window2.txt") in
  *"no run-close"*) : ;;
  *) why="$why; the window source does not say the run-close is missing: $(sed -n 2p "$WORK/window2.txt")" ;;
esac
verdict "waste-table (T6): the run's own window is run-open to run-close, else the record's last event, and the meter command carries it as --start/--end"

fixture rwinrow 200
BW=$(printf '{"event":"phase-boundary","from":"1","to":"2","meter":"%s","idle_min":0.0,"denials":0,"over_cap_reports":0,"respawn_cost_usd":0.0}' "$METER")
mk append "$REC" "$BW" >/dev/null
WWR="$WORK/rwinrow-table.md"
WINLINE='billed (list 2026-09-03) · head $5.00 · lanes $2.00 · session $7.00 · rewrites 0 ($0.00) · metered 1 of 1'
run waste-table --run rwinrow --out "$WWR" --meter-line "sid-rwinrow=$WINLINE"
need_rc 0
need_eq "$(grep -c 'heads. total (shown sum) | \$7.00 = \$7.00' "$WWR")" "1" "the window figure wins over the session-wide billed line"
need_eq "$(grep -c "metered over the run's window: \$7.00 (the record gives the last boundary billed line" "$WWR")" "1" "the row says which figure it took and what the record gave"
need_eq "$(grep -c 'envelope base \$200.00 (run-open.envelope_usd)' "$WWR")" "1" "the envelope base beside the total"
WWR2="$WORK/rwinrow-norow.md"
run waste-table --run rwinrow --out "$WWR2" --no-meter
need_eq "$(grep -c 'heads. total (shown sum) | \$16.56 = \$16.56' "$WWR2")" "1" "control: without a window figure the row falls back to the record's own"
verdict "waste-table (T6): the whole-run row takes the head's window meter figure over the session-wide billed line, names both and prints the envelope base"

# (b) the register entry of 2026-09-06: the under-read, the head count and the limit wait.
fixture rlater 100
BL=$(printf '{"event":"phase-boundary","from":"1","to":"2","meter":"%s","idle_min":0.0,"denials":0,"over_cap_reports":0,"respawn_cost_usd":0.0}' "$METER")
mk append "$REC" "$BL" >/dev/null
mk append "$REC" '{"event":"head-exit","band":0,"context":"362,843 tokens (36 %)","spent_usd":56.26,"pack":true}' >/dev/null
WLA="$WORK/rlater-table.md"
run waste-table --run rlater --out "$WLA" --no-meter
need_rc 0
need_eq "$(grep -c 'heads. total (shown sum) | \$56.26 = \$56.26' "$WLA")" "1" "the later head-exit spend, not the earlier billed line"
need_eq "$(grep -c 'head-exit.spent_usd \$56.26, later in the record than the last boundary billed line \$16.56' "$WLA")" "1" "the row names both figures and which is later"
fixture rearlier 100
mk append "$REC" '{"event":"head-exit","band":0,"context":"c","spent_usd":5.0,"pack":true}' >/dev/null
mk append "$REC" "$BL" >/dev/null
WEA="$WORK/rearlier-table.md"
run waste-table --run rearlier --out "$WEA" --no-meter
need_eq "$(grep -c 'heads. total (shown sum) | \$16.56 = \$16.56' "$WEA")" "1" "control: a boundary later than the head-exit keeps the billed line"
verdict "waste-table (register 2026-09-06): per head the run total takes the LATER of the last boundary billed line and head-exit.spent_usd, so a head that exits without a boundary loses no spend"

fixture rids 100
mk append "$REC" '{"event":"head-successor","session_id":"sid-two","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"run-resume","session":"sid-two","head":"h","detail":"the successor records itself","pid_src":"none"}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-two","pid":1,"budget":1.0}' >/dev/null
WID="$WORK/rids-table.md"
run waste-table --run rids --out "$WID" --no-meter
need_rc 0
need_eq "$(grep -c '2 head session(s)' "$WID")" "1" "four spans over two distinct ids read as two heads"
need_eq "$(grep -c 'Head sessions are counted by DISTINCT session id (sid-rids, sid-two)' "$WID")" "1" "the ids are named"
mk append "$REC" '{"event":"head-successor","session_id":"sid-three","pid":1,"budget":1.0}' >/dev/null
WID2="$WORK/rids2-table.md"
run waste-table --run rids --out "$WID2" --no-meter
need_eq "$(grep -c '3 head session(s)' "$WID2")" "1" "positive control: a third id moves the count to three"
verdict "waste-table (register 2026-09-06): head sessions are counted by distinct session id, four spans of two ids reading as two heads"

# The record's own run-open sits two hours back, so the planted wait is stamped inside that
# span (a stop 60 minutes back, its resume 30 minutes back) rather than on a fixed date. Both
# stamps come from ONE clock reading: read by two interpreter calls that straddled a second, the
# wait was 1801 s, the row read 30.02 min and the 30.0 min check below failed (2026-10-11).
fixture rlimit 100
LIM_TS=$("$PY" -c 'import time; t = int(time.time()); print(" ".join(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t - s)) for s in (3600, 1800)))')
STOP_TS=${LIM_TS% *}; RES_TS=${LIM_TS#* }
mk append "$REC" "{\"event\":\"stop-condition\",\"which\":\"limit\",\"lane\":\"head\",\"action\":\"wait until the reset\",\"ts\":\"$STOP_TS\"}" >/dev/null
mk append "$REC" "{\"event\":\"head-resumed\",\"session_id\":\"sid-rlimit\",\"pid\":1,\"context\":136346,\"waited_s\":1800,\"ts\":\"$RES_TS\"}" >/dev/null
BLIM=$(printf '{"event":"phase-boundary","from":"2","to":"3","meter":"%s","idle_min":40.0,"idle_src":"transcript","denials":0,"over_cap_reports":0,"respawn_cost_usd":0.0}' "$METER")
mk append "$REC" "$BLIM" >/dev/null
WLI="$WORK/rlimit-table.md"
run waste-table --run rlimit --out "$WLI" --no-meter
need_rc 0
need_eq "$(grep -c "^| limit wait · limit → head-resumed at $RES_TS | 30.0 min" "$WLI")" "1" "the structural row for the recorded limit wait"
need_eq "$(grep -c 'not head idleness: a boundary whose span covers it counts the same minutes under idle_min | structural' "$WLI")" "1" "the row's kind and its reason"
need_eq "$(grep -c 'of which 30.0 min is a recorded limit wait' "$WLI")" "1" "the idle row says how much of it is the wait"
need_eq "$(grep -c '^| limit wait' "$WTR")" "0" "control: a record with no stop-condition renders no limit-wait row"
verdict "waste-table (register 2026-09-06): a stop-condition and its head-resumed take a structural row of their own and the idle row that covers them says how many of its minutes they hold"

# (c) T8: the over-cap row carries the cut tail's price, never the lane's whole cost.
fixture rtail 200
mk append "$REC" '{"event":"lane-open","lane":"L9","class":"builder","model":"claude-opus-5","budget_usd":15.0}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L9","exit_class":"completed","total_cost_usd":14.57,"report_words":1000,"report_cut":true}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L8","class":"verifier","model":"claude-sonnet-5","budget_usd":2.0}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L8","exit_class":"completed","total_cost_usd":0.39,"report_words":800,"report_cut":false}' >/dev/null
BT=$(printf '{"event":"phase-boundary","from":"1","to":"2","meter":"%s","idle_min":0.0,"denials":0,"over_cap_reports":1,"respawn_cost_usd":0.0}' "$METER")
mk append "$REC" "$BT" >/dev/null
WTT="$WORK/rtail-table.md"
run waste-table --run rtail --out "$WTT" --no-meter
need_rc 0
need_eq "$(grep -c 'cut tail \$0.01 · the tail alone (the words cut), never the lane.s whole cost: L9 200 words over = \$0.0052 (opus output \$20.00/MTok)' "$WTT")" "1" "the cut tail priced at the lane's model's output rate"
need_eq "$(grep -c '1.3 tokens per word, set by judgement, unmeasured' "$WTT")" "2" "the ratio and its standing, in the row and in the legend"
need_eq "$(grep -c 'L8' "$WTT")" "0" "a lane at the cap contributes nothing to the row"
need_eq "$(grep -c '14.57' "$WTT")" "0" "the lane's whole cost is not the figure"
verdict "waste-table (T8): the over-cap row carries the cut tail (report_words − 800 at the model's output rate), a lane at the cap contributing nothing and the lane's whole cost nowhere in it"

fixture rtail2 200
mk append "$REC" '{"event":"lane-closed","lane":"L7","exit_class":"completed","total_cost_usd":1.0,"report_words":900}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L6","class":"builder","model":"fable-1","budget_usd":15.0}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L6","exit_class":"completed","total_cost_usd":1.0,"report_words":900}' >/dev/null
BT2=$(printf '{"event":"phase-boundary","from":"1","to":"2","meter":"%s","idle_min":0.0,"denials":0,"over_cap_reports":2,"respawn_cost_usd":0.0}' "$METER")
mk append "$REC" "$BT2" >/dev/null
WT7="$WORK/rtail2-table.md"
run waste-table --run rtail2 --out "$WT7" --no-meter
need_rc 0
need_eq "$(grep -c 'L7 100 words over (unpriced: the record names no model for this lane)' "$WT7")" "1" "a lane whose model the record does not name is counted in words and left unpriced"
need_eq "$(grep -c 'L6 100 words over = \$0.0065 (fable output \$50.00/MTok)' "$WT7")" "1" "positive control: the priced lane in the same span"
need_eq "$(grep -c 'over the priced tail(s)' "$WT7")" "1" "the total says it covers the priced tails alone"
verdict "waste-table (T8): a lane whose model the record does not name is counted in words and never guessed at a price, beside a priced lane in the same span"

# (d) the extraction carries an assistant record's tool calls, never their results.
mk toolscript sid-tools >/dev/null
TX="$WORK/tools"
run extract-transcript --session sid-tools --out "$TX"
need_rc 0
need_out "2 turns (1 human, 1 assistant) of 6 records"
need_out "2 tool-call turn(s)"
need_eq "$(grep -c '^## turn 2 · assistant · tool calls · 2026-09-07T10:00:10Z' "$TX/turns.md")" "1" "the tool-call turn's heading"
need_eq "$(grep -c '^- Bash: git status --porcelain' "$TX/turns.md")" "1" "the Bash call carries its command"
need_eq "$(grep -c '^- Read: /fixture/page.md' "$TX/turns.md")" "1" "the Read call carries its file path"
need_eq "$(grep -c '^- Grep: needle' "$TX/turns.md")" "1" "the Grep call carries its pattern"
need_eq "$(grep -c '^- TodoWrite$' "$TX/turns.md")" "1" "a tool outside the table prints its name alone"
need_eq "$(grep -c 'the tool result never reaches the extraction' "$TX/turns.md")" "0" "the tool result is out, as before"
# A repetition count above 255 is outside POSIX grep, so the long line is matched by its head
# and its cut marker and measured in Python.
need_eq "$(grep -c ' …\[cut\]$' "$TX/turns.md")" "1" "one line carries the cut marker"
need_eq "$(grep -c '^- Bash: yyyyyyyyyy' "$TX/turns.md")" "1" "the long command's own line"
CUTLEN=$("$PY" -c 'import sys; print(max(len(x.rstrip(chr(10))) for x in open(sys.argv[1], encoding="utf-8") if x.startswith("- Bash: y")))' "$TX/turns.md")
need_eq "$CUTLEN" "300" "the cut line is exactly 300 characters"
verdict "extract-transcript: an assistant record of tool calls alone is a tool-call turn, one line per call with the tool's name and its command, path or pattern, cut at 300 characters (register 2026-09-07)"

need_eq "$(mk json "$TX/counts.json" tool_call_turns)" "2" "tool_call_turns in counts.json"
need_eq "$(mk json "$TX/counts.json" extracted)" "2" "extracted counts the prose turns alone"
"$PY" -c 'import json,sys; c=json.load(open(sys.argv[1])); print(c["records"], c["extracted"] + c["tool_call_turns"] + sum(c["excluded"].values()))' \
      "$TX/counts.json" > "$WORK/sum.txt"
need_eq "$(cut -d" " -f1 "$WORK/sum.txt")" "$(cut -d" " -f2 "$WORK/sum.txt")" "records = extracted + tool_call_turns + excluded"
need_eq "$(grep -c 'Records = 2 extracted + 2 tool-call + 2 excluded = 6' "$TX/turns.md")" "1" "the extraction states the arithmetic"
need_eq "$(grep -c '^## turn 3 · assistant · 2026-09-07T10:00:20Z' "$TX/turns.md")" "1" "a record with prose AND calls keeps its prose turn"
need_eq "$(grep -c '^- Edit: /fixture/other.md' "$TX/turns.md")" "1" "and its tool calls go under that turn"
need_eq "$(mk json "$EX/counts.json" tool_call_turns)" "1" "positive control: the first extraction's own tool-call record"
verdict "extract-transcript: counts.json carries tool_call_turns and records = extracted + tool_call_turns + excluded holds, a record with prose and calls keeping one turn"

RTD="$WORK/rrefl-tools"
run reflect-inputs --run rrefl --session sid-tools --out "$RTD" --no-meter
need_rc 0
need_out "2 tool-call turn(s)"
need_eq "$(mk field "$STORE/spawn-records/rrefl.jsonl" reflect-inputs counts | grep -c 'tool_call_turns')" "1" "the event's counts carry the figure"
verdict "reflect-inputs: the tool-call turns reach the reflector's input set and the count is on the event"

# (e) the successor sizes its cap from the envelope when the last head-exit is a seed exit.
fixture rseedsucc 400
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"unmetered (transcript missing: a path that is not there)","exit_class":"error","pack":false}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rseedsucc --dry-run --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget_src: envelope (seed)"
need_out "budget \$400.00"
need_absent "pass --budget-usd"
fixture rmetsucc 400
mk append "$REC" '{"event":"head-exit","band":0,"context":"500,000 tokens (50 %)","spent_usd":40.0,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rmetsucc --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$387.66"
need_absent "envelope (seed)"
verdict "successor: a seed head-exit sizes the cap at the envelope minus recorded spend (budget_src: envelope (seed)), while a metered head-exit takes the ordinary remainder, the envelope minus the run's spend (400 − \$12.34, K22da6bf5; register 2026-09-07)"

# ------------------------------ run-lifecycle register entries (grants, pack, seed, heads) ----
glist() { # $1 grants file, $2 key, $3 path: 1 when that list holds the path, else 0
  "$PY" -c 'import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); print(1 if sys.argv[3] in d.get(sys.argv[2], []) else 0)' "$1" "$2" "$3"
}
gcount() { "$PY" -c 'import json, sys; print(len(json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2], [])))' "$1" "$2"; }

# (H1) grants and run-resume carry the lists a call does not name (register 2026-09-12 21:3x and
# 2026-09-11 04:17). The planted file is shaped like a launcher's: literal paths in its own order.
fixture rcarry 200
GFC="$REALSTORE/spawn-records/rcarry-grants.json"
"$PY" - "$GFC" "$WORK/carry" <<'PLANTGRANTS'
import json, os, sys
path, base = sys.argv[1], sys.argv[2]
lit = [os.path.join(base, n) for n in ("worktree", "clone.git", "review", "packs", "handoff-a", "handoff-b")]
json.dump({"run": "fixture", "grants": lit + [os.path.join(base, "experiments")], "writes": lit[:5],
           "on_limit": "stop", "viewer": "terminal", "source": "a launcher (planted)"},
          open(path, "w", encoding="utf-8"), indent=1)
PLANTGRANTS
GC_BEFORE=$(gcount "$GFC" grants); WC_BEFORE=$(gcount "$GFC" writes)
run grants --run rcarry --on-limit resume
need_rc 0
need_eq "$(gval "$GFC")" "resume" "on_limit, the key the call named"
for n in worktree clone.git review packs handoff-a; do
  need_eq "$(glist "$GFC" writes "$WORK/carry/$n")" "1" "the literal write $n after grants --on-limit resume"
done
for n in worktree clone.git review packs handoff-a handoff-b experiments; do
  need_eq "$(glist "$GFC" grants "$WORK/carry/$n")" "1" "the literal read grant $n"
done
need_eq "$(mk field "$REC" grants writes_src)" "carried (file)" "the event names the carry"
need_out "writes (carried (file))"
verdict "grants --on-limit resume (register 2026-09-12 21:3x, the call as run): the file's literal read grants and writes are carried forward and only on_limit changes (planted: $GC_BEFORE grants, $WC_BEFORE writes)"

GSHA=$(sha_file "$GFC")
run grants --run rcarry --write "$WORK/carry/worktree"
need_rc 2
need_out "would shrink the run's grants and passes no --replace"
need_out "carry/review"
need_eq "$(sha_file "$GFC")" "$GSHA" "a narrowing without --replace leaves the file byte-identical"
run grants --run rcarry --write "$WORK/carry/worktree" --replace
need_rc 0
need_out "loses"
need_out "(--replace: the lists named replace the run's, so it is written)"
need_eq "$(glist "$GFC" writes "$WORK/carry/review")" "0" "an explicit --write --replace replaces the write list"
need_eq "$(glist "$GFC" writes "$WORK/carry/worktree")" "1" "the named write is written"
need_eq "$(glist "$GFC" grants "$WORK/carry/experiments")" "1" "the read list the call does not name is still carried"
verdict "grants --write (register 2026-09-29 20:49): a named list that would lose paths is refused without --replace, the file untouched; with --replace it replaces the file's list, its lost paths printed on stderr, while the unnamed read list is carried"

fixture rcarry2 200
GFV="$REALSTORE/spawn-records/rcarry2-grants.json"
"$PY" - "$GFV" "$WORK/carry" <<'PLANTGRANTS2'
import json, os, sys
path, base = sys.argv[1], sys.argv[2]
lit = [os.path.join(base, n) for n in ("repo", "vault-a", "vault-b", "vault-c", "vault-d")]
json.dump({"run": "fixture", "grants": lit, "writes": lit, "on_limit": "stop", "viewer": "terminal",
           "source": "a launcher (planted)"}, open(path, "w", encoding="utf-8"), indent=1)
PLANTGRANTS2
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rcarry2 --session sid-carry2 --head "fixture head" --detail "the head's first act" --viewer none
need_rc 0
need_out "(lists carried)"
need_eq "$(vval "$GFV")" "none" "viewer, the key the call named"
for n in repo vault-a vault-b vault-c vault-d; do
  need_eq "$(glist "$GFV" writes "$WORK/carry/$n")" "1" "the literal write $n after run-resume --viewer none"
  need_eq "$(glist "$GFV" grants "$WORK/carry/$n")" "1" "the literal read grant $n"
done
need_eq "$(mk field "$REC" run-resume writes_src)" "carried (file)" "the event names the carried write list"
need_eq "$(mk field "$REC" run-resume grants_src)" "carried (file)" "the event names the carried read list"
verdict "run-resume --viewer none (register 2026-09-11 04:17): the launcher's literal grants and writes survive and only the viewer key changes"

# The shrink guard: the file gone or unreadable, the record's grants event still holds the lists.
fixture rshrink 200
GFS="$REALSTORE/spawn-records/rshrink-grants.json"
run grants --run rshrink --grant "$WORK/carry/keep-r" --write "$WORK/carry/keep-w"
need_rc 0
rm -f "$GFS"
LINES_BEFORE=$(mk lines "$REC")
run grants --run rshrink --on-limit resume
need_rc 2
need_out "would shrink the run's grants"
need_out "the write list loses"
need_out "carry/keep-w"
need_lines
need_nofile "$GFS"
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines after the refusal"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rshrink --session sid-shrink --head "fixture head" --detail "no lists" --viewer none
need_rc 2
need_out "carry/keep-w"
need_nofile "$GFS"
need_eq "$(mk count "$REC" run-resume)" "0" "no run-resume from the refusal"
printf 'not json\n' > "$GFS"
run grants --run rshrink --on-limit resume
need_rc 2
need_out "would shrink"
need_eq "$(cat "$GFS")" "not json" "the unreadable file is left as it was"
run grants --run rshrink --on-limit resume --grant "$WORK/carry/keep-r" --write "$WORK/carry/keep-w"
need_rc 0
need_eq "$(glist "$GFS" writes "$WORK/carry/keep-w")" "1" "the explicit re-issue is written"
verdict "the shrink guard: with the file gone or unreadable, a call naming no list that would lose a recorded write path prints the delta and refuses (exit 2, nothing written), for grants and run-resume alike; the same call re-issuing the lists is written (control)"

# (H8) --grants-file is retired (register 2026-09-06): run-open refuses it, naming the default path.
HOG="$WORK/handoffs/rgf-handoff.md"; mk handoff "$HOG" >/dev/null
REC="$STORE/spawn-records/rgf.jsonl"; rm -f "$REC"
run run-open --run rgf --session sid-rgf --head "fixture head" --regime multi --regime-src owner \
    --handoff "$HOG" --detail "a retired option" --pid 1 --grants-file "$WORK/elsewhere-rgf.json"
need_rc 2
need_out "grants-file is retired"
need_out "$REALSTORE/spawn-records/rgf-grants.json"
need_lines
need_nofile "$REC"
need_nofile "$WORK/elsewhere-rgf.json"
need_nofile "$REALSTORE/spawn-records/rgf-grants.json"
run run-open --run rgf --session sid-rgf --head "fixture head" --regime multi --regime-src owner \
    --handoff "$HOG" --detail "the bare flag" --pid 1 --grants-file
need_rc 2
need_out "grants-file is retired"
need_nofile "$REC"
viewer_use rgf
run run-open --run rgf --session sid-rgf --head "fixture head" --regime multi --regime-src owner \
    --handoff "$HOG" --detail "no option" --pid 1
need_rc 0
need_file "$REALSTORE/spawn-records/rgf-grants.json"
verdict "run-open --grants-file (register 2026-09-06): refused with the default path named, with or without a path, and nothing written; without the option the default path is written (control)"

tsago() { "$PY" -c 'import sys, time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - float(sys.argv[1]))))' "$1"; }
setmtime() { "$PY" -c 'import os, sys, time; t = time.time() - float(sys.argv[2]); os.utime(sys.argv[1], (t, t))' "$1" "$2"; }
plant_pack() { # $1 hand-off, $2 stamp, $3 Next text: a hand edit of '## In flight' that kept an old stamp
  "$PY" - "$1" "$2" "$3" <<'PLANTPACK'
import sys
path, stamp, nxt = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
new = ("## In flight\n- pack written: %s\n- Next: %s\n- Needs: wiki/h.md:1\n"
       "- Decided: D8 because the author said so\n" % (stamp, nxt))
if "## In flight\n- nothing in flight.\n" not in text:
    sys.exit("plant_pack: the fixture's in-flight section is not where it was expected")
open(path, "w", encoding="utf-8").write(text.replace("## In flight\n- nothing in flight.\n", new, 1))
PLANTPACK
}
wait_log() { # $1 file, $2 fixed string, $3 tries of 0.5 s: a detached starter writes its log late
  i=0
  while [ "$i" -lt "$3" ]; do
    if [ -f "$1" ] && grep -q -F -- "$2" "$1"; then return 0; fi
    sleep 0.5; i=$((i + 1))
  done
  why="$why; no '$2' in $1 within $3 half-seconds"; return 1
}
act_events() { # $1 record: the head's gate 600 s ago and the supervisor's `head exited` 300 s ago
  mk append "$1" "$(printf '{"event":"gate","ts":"%s","item":"item2","context":null,"percent":null,"band":"unmetered","armed":false,"decision":"allow","metered":false}' "$(tsago 600)")" >/dev/null
  mk append "$1" "$(printf '{"event":"observation","ts":"%s","phase":"","what":"head exited","exit_class":"error","note":"stopped by the launcher"}' "$(tsago 300)")" >/dev/null
}

# (H2) The pack-age guard keys on the head's last activity, never on the head-exit `successor`
# writes at its own call (register 2026-09-12 21:2x). The pack's stamp is 900 s old in every leg.
fixture rpfresh 200
plant_pack "$HO" "$(tsago 900)" "the launcher's amended shape"
act_events "$REC"
setmtime "$HO" 120      # the launcher's rewrite, three minutes after the head stopped
viewer_use rpfresh
RUNENV="STUB_MODE=complete STUB_N=0 PATH=$WORK/psnone:$PATH"
run successor --run rpfresh --budget-usd 5 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 5 --max-wait-s 10 --tick-s 1
need_rc 0
SLOG="$REALSTORE/spawn-records/rpfresh-head-1.out.starter.log"
wait_log "$SLOG" "— ended" 60
if ! grep -q -F "pack: fresh — the hand-off was rewritten at" "$SLOG"; then
  why="$why; the starter did not judge the rewrite fresh: $(grep -F 'pack:' "$SLOG")"
fi
case $(mk section "$HO" "In flight") in
  *"the launcher's amended shape"*) : ;;
  *) why="$why; the amended pack was re-derived: $(mk section "$HO" "In flight")" ;;
esac
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations"
verdict "the pack-age guard (register 2026-09-12 21:2x): a hand-off rewritten after the head's last activity is fresh at the successor's start, though its stamp is older and the head-exit successor wrote is newer"

fixture rpstale 200
plant_pack "$HO" "$(tsago 900)" "the superseded shape"
mk append "$REC" "$(printf '{"event":"phase-boundary","ts":"%s","from":"1","to":"2","next":"item 2: the shape at the boundary"}' "$(tsago 800)")" >/dev/null
act_events "$REC"
setmtime "$HO" 400      # the hand-off's last write came before the head stopped
mk append "$REC" '{"event":"head-exit","band":0,"context":"c","pack":false}' >/dev/null
RUNENV="STUB_MODE=complete STUB_N=0 PATH=$WORK/psnone:$PATH"
starter --run rpstale --handoff "$HO" --budget 3.50 --out "$WORK/starter/rpstale-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_out "pack: STALE — the pack was written"
need_out "before the head's last activity (the \`head exited\` observation"
SEC=$(mk section "$HO" "In flight")
case $SEC in *'a copy of the `next` field of the phase-boundary'*) : ;; *) why="$why; the re-derived Next line does not say it is a copy: $SEC" ;; esac
case $SEC in *"item 2: the shape at the boundary"*) : ;; *) why="$why; the boundary's next is missing" ;; esac
case $SEC in *"the superseded shape"*) why="$why; the stale pack survived" ;; *) : ;; esac
verdict "the pack-age guard: a hand-off whose stamp and mtime both predate the head's last activity is STALE and re-derived, and the Next line says it is a copy of the boundary's next field (control for the fresh leg above)"

fixture rpword 200
plant_pack "$HO" "$(tsago 900)" "the launcher's word"
act_events "$REC"
setmtime "$HO" 400      # the stale shape of the leg above
viewer_use rpword
RUNENV="STUB_MODE=complete STUB_N=0 PATH=$WORK/psnone:$PATH"
run successor --run rpword --pack-fresh --budget-usd 5 --meter-line "$METER" \
    --harness-bin "$WORK/bin/stubhead" --wait-s 5 --max-wait-s 10 --tick-s 1
need_rc 0
SLOG="$REALSTORE/spawn-records/rpword-head-1.out.starter.log"
wait_log "$SLOG" "— ended" 60
if ! grep -q -F "pack: fresh — --pack-fresh recorded at" "$SLOG"; then
  why="$why; the starter did not take the launcher's word: $(grep -F 'pack:' "$SLOG")"
fi
need_eq "$(grep -c '"what": "pack-fresh"' "$REC")" "1" "the pack-fresh observation"
case $(mk section "$HO" "In flight") in
  *"the launcher's word"*) : ;;
  *) why="$why; --pack-fresh did not keep the pack" ;;
esac
need_eq "$(grep -c 'stale-pack' "$REC")" "0" "stale-pack observations"
verdict "successor --pack-fresh: the pack the leg above re-derives is kept, the starter naming the recorded pack-fresh observation"

# (H3) A seed records no pid and its starter does not wait (register 2026-09-12 20:0x), under a
# live claude parent: the psclaude stub answers `claude` for every row, so a walk would find one.
SHO3="$WORK/handoffs/rseednone-handoff.md"; mk handoff "$SHO3" >/dev/null
REC="$STORE/spawn-records/rseednone.jsonl"; rm -f "$REC"
viewer_use rseednone
RUNENV="PATH=$WORK/psclaude:$PATH"
run run-open --run rseednone --session sid-seednone --head "the launcher" --regime multi \
    --regime-src owner --handoff "$SHO3" --detail "a seed under a live claude parent" \
    --session-kind seed --envelope-usd 200 --model fixture-model
need_rc 0
need_out "pid none (none (seed: no pid unless --pid))"
need_eq "$(mk field "$REC" run-open pid)" "<no key pid>" "a seed records no pid under a live claude parent"
RUNENV="PATH=$WORK/psclaude:$PATH"
run successor --run rseednone --dry-run --budget-usd 5 --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "successor: pid none (run-open, seed: no pid)"
need_out "so no wait"
need_absent "(parent-walk)"
mk append "$REC" '{"event":"head-exit","band":"unmetered","context":"unmetered (transcript missing: a seed)","pack":false}' >/dev/null
# A transcript written a moment ago would hold a silence wait for its whole 30 s bound, so a start
# well inside that bound shows the wait was skipped rather than satisfied.
TXLIVE=$(mk transcript sid-seednone 1000)
T_START=$(date +%s)
RUNENV="STUB_MODE=complete STUB_N=0 PATH=$WORK/psclaude:$PATH"
starter --run rseednone --handoff "$SHO3" --budget 3.50 --out "$WORK/starter/rseednone-head-1.out" \
        --wait-s 30 --transcript "$TXLIVE" --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
T_END=$(date +%s)
need_rc 0
need_out "starts at once: the predecessor is a seed session with no pid"
need_absent "waits for"
[ "$(mk count "$REC" head-successor)" -ge 1 ] || why="$why; no head-successor was recorded"
[ $((T_END - T_START)) -lt 25 ] || why="$why; the starter took $((T_END - T_START)) s of a 30 s bound"
verdict "seed (register 2026-09-12 20:0x): run-open --session-kind seed under a live claude parent records no pid, successor takes none and runs no walk, and the starter starts the head at once instead of waiting"

# A --pid naming this suite's own shell — the parent of every call here, and older than the 60 s
# bound by now (the leg waits out any shortfall) — is refused (register 2026-09-10 10:51).
AGE_NOW=$("$PY" -c 'import re, subprocess, sys
out = subprocess.run(["ps", "-o", "etime=", "-p", sys.argv[1]], capture_output=True, text=True).stdout.strip()
m = re.fullmatch(r"(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)", out)
print(0 if not m else ((int(m.group(1) or 0) * 24 + int(m.group(2) or 0)) * 60 + int(m.group(3))) * 60 + int(m.group(4)))' "$$")
[ "$AGE_NOW" -gt 61 ] || sleep $((62 - AGE_NOW))
fixture ranc 200
LINES_BEFORE=$(mk lines "$REC")
run successor --run ranc --dry-run --pid "$$" --budget-usd 5 --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "pid $$ is this caller's own ancestor"
need_out "over the 60 s bound"
need_lines
run successor --run ranc --pid "$$" --budget-usd 5 --meter-line "$METER" \
    --harness-bin "$WORK/bin/no-such-harness" --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 2
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines: no head-exit written"
need_nofile "$REALSTORE/spawn-records/ranc-head-1.out.starter.log"
run successor --run ranc --dry-run --predecessor-pid "$$" --budget-usd 5 --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "predecessor-pid $$ is this caller's own ancestor"
verdict "successor (register 2026-09-10 10:51): a --pid or --predecessor-pid naming the caller's own long-lived ancestor (this suite's shell) is refused with the reason named, dry run or not, and nothing is written or detached"

sh -c '"$1" -B "$2" successor --run ranc --dry-run --pid "$$" --budget-usd 5 --meter-line "$3" --harness-bin "$4"; exit $?' young "$PY" "$H" "$METER" "$WORK/bin/harness" >"$WORK/out" 2>"$WORK/err"
RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 0
need_out "successor: dry run"
sleep 1 &
DEADPID=$!
wait "$DEADPID"
run successor --run ranc --dry-run --pid "$DEADPID" --budget-usd 5 --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "successor: pid $DEADPID (arg)"
verdict "successor (controls): a --pid naming an ancestor shell seconds old, and one naming a process already gone, are accepted"

sleep 60 &
LIVEPID=$!
fixture rtimeout 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":1,"pack":true}' >/dev/null
starter --run rtimeout --handoff "$HO" --budget 3.50 --out "$WORK/starter/rtimeout-head-1.out" --wait-s 2 \
        --predecessor-pid "$LIVEPID" --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
kill "$LIVEPID"; wait "$LIVEPID" || :
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "timeout" "the abort reason"
case $(mk field "$REC" successor-aborted note) in
  *"sleep, running "*"a seed pid must belong to a process that exits within seconds"*) : ;;
  *) why="$why; the timeout does not name the process: $(mk field "$REC" successor-aborted note)" ;;
esac
verdict "the starter (register 2026-09-10 10:51): a predecessor still alive at the bound ends successor-aborted timeout, the note naming the process's command and age"

# (H4) raise-envelope (register 2026-09-10 20:02): a gate's envelope stop at $40.16 of $40.00.
# The line carries the spend as its head figure too: the gate reads the RUN figure (this head's
# `head $` plus the record's lanes, none here), raise-envelope its own recorded-plus-session
# check, and on a consistent line the two agree at $40.16.
METER40=$(printf '%s' "$METER" | sed 's/head \$12\.34 · lanes \$4\.22 · session \$16\.56/head $40.16 · lanes $0.00 · session $40.16/')
fixture rraise 40
mk transcript sid-rraise 100000 >/dev/null
run gate --run rraise --to item3 --meter-line "$METER40"
need_rc 5
need_out 'envelope: $40.16 of $40.00, remainder -$0.16'
need_out "raise-envelope --run rraise --to USD"
run raise-envelope --run rraise --to 40.10 --reason "a top-up below the spend" --meter-line "$METER40"
need_rc 2
need_out "at or below the run's spend \$40.16"
need_lines
need_eq "$(mk count "$REC" envelope)" "0" "no envelope event from the refusal"
run raise-envelope --run rraise --to 60 --reason "the owner's top-up" --meter-line "$METER40"
need_rc 0
need_out "envelope \$40.00 → \$60.00"
need_eq "$(mk field "$REC" envelope envelope_usd)" "60.0" "the envelope event's figure"
need_eq "$(mk field "$REC" envelope previous_usd)" "40.0" "the figure it replaces"
run gate --run rraise --to item3 --meter-line "$METER40"
need_rc 0
need_out 'envelope: $40.16 of $60.00, remainder $19.84'
run raise-envelope --run rraise --to 50 --reason "not a raise" --meter-line "$METER40"
need_rc 2
need_out "not above the current envelope"
verdict "raise-envelope (register 2026-09-10 20:02): the gate's envelope stop names the command; a top-up at or below the spend is refused; a raise to \$60 appends an envelope event the gate reads at once (remainder \$19.84); a figure not above the current envelope is refused"

plain_fixture pnoenv
run raise-envelope --run pnoenv --to 50 --reason "no run-open"
need_rc 2
need_out "no run-open"
need_lines
run raise-envelope --run no-such-run-record --to 50 --reason "no record"
need_rc 2
need_out "no run record"
fixture rraiseclosed 40
mk append "$REC" '{"event":"run-close","items":"1 of 1"}' >/dev/null
run raise-envelope --run rraiseclosed --to 50 --reason "a closed run" --meter-line "$METER40"
need_rc 2
need_out "is closed"
need_eq "$(mk count "$REC" envelope)" "0" "no envelope event on a closed run"
run raise-envelope --run rraise --to 70 --reason "   " --meter-line "$METER40"
need_rc 2
need_out "reason is empty"
verdict "raise-envelope premises: no run-open, no record, a closed run and an empty reason are each refused (exit 2) with nothing written"

# (H5) The decision subcommand, and close counting both forms (register 2026-09-06).
fixture rdec 200
run decision --run rdec --phase 2 --what "item2 runs three builders in parallel" --grant "G2 and G13"
need_rc 0
need_out "ledger row 3 appended"
need_eq "$(mk count "$REC" decision)" "1" "decision events"
need_eq "$(mk count "$REC" observation)" "0" "no observation beside the decision"
need_eq "$(mk rows "$HO" "Findings ledger")" "3" "the ledger's rows (two fixture rows and the decision)"
case $(mk row "$HO" "Findings ledger" -1) in
  *"| decision: item2 runs three builders in parallel | grant: G2 and G13 | no action |") : ;;
  *) why="$why; the decision's ledger row: $(mk row "$HO" "Findings ledger" -1)" ;;
esac
run ledger --run rdec --phase 2 --what "decision (head 2, within G2): item2 extends to two entries" --evidence "the head's reading" --routing "no action"
need_rc 0
run ledger --run rdec --phase 2 --what "decisions channel read at the gate" --evidence "a control" --routing "no action"
need_rc 0
run close --run rdec --meter-line "$METER" --dry-run
need_rc 0
need_out '"decisions_on_owner_behalf": 2'
need_out '"decisions_src": "1 decision event(s) + 1 ledger observation(s)"'
run close --run rdec --items "fixture items" --meter-line "$METER"
need_rc 0
need_out "decisions 2"
need_eq "$(mk field "$REC" run-close decisions_on_owner_behalf)" "2" "the close's count"
verdict "decision + close (register 2026-09-06): one decision call (event and ledger row, no observation) and one ledger row whose what opens with the word decision count 2, while a row opening 'decisions channel' is not counted (control)"

fixture rdec2 200 ledger
run decision --run rdec2 --phase 1 --what "a decision" --grant "G1"
need_rc 2
need_out "no table under a '## Findings ledger' heading"
need_eq "$(mk count "$REC" decision)" "0" "no decision event without its row"
plain_fixture pdec
run decision --run pdec --phase 1 --what "a decision" --grant "G1"
need_rc 2
need_out "ledger --observation"
verdict "decision premises: a hand-off with no ledger table and a plain record are refused (exit 2) with nothing written"

# (H6) Two heads on one run (register 2026-09-03): a live head start that is not the caller's.
fixture rtwo 200
mk transcript sid-rtwo-peer 100000 >/dev/null
sleep 120 &
PEER=$!
sleep 1
mk append "$REC" "$(printf '{"event":"head-successor","session_id":"sid-rtwo-peer","pid":%d,"budget":1.0}' "$PEER")" >/dev/null
LINES_BEFORE=$(mk lines "$REC")
run gate --run rtwo --to "item one" --meter-line "$METER"
need_rc 9
need_out "TWO HEADS"
need_eq "$(mk count "$REC" gate)" "0" "no gate event from the refusal"
need_eq "$(mk lines "$REC")" "$((LINES_BEFORE + 1))" "one observation and nothing else"
need_eq "$(mk field "$REC" observation what)" "two heads" "the observation"
# ps readable: the refusal stands on positive evidence (with no readable ps it is a warning, below)
run run-resume --run rtwo --session sid-rtwo-second --head "a second head" --detail "resumed onto a live session"
need_rc 9
need_eq "$(mk count "$REC" run-resume)" "0" "no run-resume from the refusal"
run gate --run rtwo --to "item one" --meter-line "$METER" --i-am-pid "$PEER"
need_rc 0
need_absent "TWO HEADS"
kill "$PEER"; wait "$PEER" || :
run gate --run rtwo --to "item two" --meter-line "$METER"
need_rc 0
need_absent "TWO HEADS"
verdict "two heads (register 2026-09-03): gate and run-resume refuse with exit 9 while the last head start names a live pid outside the caller's process chain (one observation, no gate or run-resume event); --i-am-pid naming it clears, and so does its death"

fixture rtwo2 200
sleep 120 &
LATE=$!
sleep 1
mk append "$REC" "$(printf '{"event":"head-successor","ts":"2020-01-02T03:04:05+0000","session_id":"sid-old","pid":%d,"budget":1.0}' "$LATE")" >/dev/null
run gate --run rtwo2 --to "item one" --meter-line "$METER"
need_rc 0
need_absent "TWO HEADS"
mk append "$REC" "$(printf '{"event":"head-successor","session_id":"sid-mine","pid":%d,"budget":1.0}' "$$")" >/dev/null
run gate --run rtwo2 --to "item two" --meter-line "$METER"
need_rc 0
need_absent "TWO HEADS"
mk append "$REC" "$(printf '{"event":"head-successor","session_id":"sid-peer2","pid":%d,"budget":1.0}' "$LATE")" >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","pack":true}' >/dev/null
run gate --run rtwo2 --to "item three" --meter-line "$METER"
need_rc 0
need_absent "TWO HEADS"
kill "$LATE"; wait "$LATE" || :
verdict "two heads (controls): a live pid whose process started after the head start recording it (a reused pid), the caller's own shell, and a live head start with a head-exit after it each clear the check"

# (H7) run-open seeds the Trace table a prose section lacks (register 2026-09-11 04:20).
PHO="$WORK/handoffs/rtrace-handoff.md"; mk handoff "$PHO" "trace,decoy" >/dev/null
"$PY" - "$PHO" <<'PROSETRACE'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
if "## Plan of record" not in text:
    sys.exit("the fixture hand-off has no plan section to put the prose trace before")
text = text.replace("## Plan of record", "## Trace\nOne row per decision and boundary is kept here once the run starts.\n\n## Plan of record", 1)
open(path, "w", encoding="utf-8").write(text)
PROSETRACE
REC="$STORE/spawn-records/rtrace.jsonl"; rm -f "$REC"
viewer_use rtrace
run run-open --run rtrace --session sid-rtrace --head "fixture head" --regime multi --regime-src owner \
    --handoff "$PHO" --detail "a prose trace" --pid 1 --dry-run
need_rc 0
need_out "would be seeded"
need_eq "$(grep -c '^| Time | Item |' "$PHO")" "0" "the dry run writes no header"
run run-open --run rtrace --session sid-rtrace --head "fixture head" --regime multi --regime-src owner \
    --handoff "$PHO" --detail "a prose trace" --pid 1
need_rc 0
need_out "held no table"
need_eq "$(mk field "$REC" run-open trace_table)" "seeded" "trace_table on the event"
need_eq "$(grep -c '^| Time | Item | Decision and its rule | Billed line | Waste so far |$' "$PHO")" "1" "the five-column header"
case $(mk section "$PHO" "Trace") in *"One row per decision and boundary is kept here"*) : ;; *) why="$why; the section's prose was lost" ;; esac
RUNENV="PATH=$WORK/psnone:$PATH"
run boundary --run rtrace --from 0 --to 1 --disposition "the seeded table" --waste "none" --next "item 1" --meter-line "$METER"
need_rc 0
need_absent "NOT refreshed"
need_eq "$(mk rows "$PHO" "Trace")" "1" "the boundary's row under the seeded header"
verdict "run-open (register 2026-09-11 04:20): a Trace section of prose gets the five-column header under its heading with a warning (a dry run warns and writes nothing), and the next boundary appends its row there instead of exiting 3"

THO="$WORK/handoffs/rtrace2-handoff.md"; mk handoff "$THO" >/dev/null
REC="$STORE/spawn-records/rtrace2.jsonl"; rm -f "$REC"
SUM_BEFORE=$(mk manifest "$WORK/handoffs" | grep rtrace2-handoff)
run run-open --run rtrace2 --session sid-rtrace2 --head "fixture head" --regime multi --regime-src owner \
    --handoff "$THO" --detail "a table" --pid 1
need_rc 0
need_absent "warn: the hand-off"
need_eq "$(mk field "$REC" run-open trace_table)" "table" "trace_table on the event"
need_eq "$(mk manifest "$WORK/handoffs" | grep rtrace2-handoff)" "$SUM_BEFORE" "a hand-off with its table is untouched"
NHO="$WORK/handoffs/rtrace3-handoff.md"; mk handoff "$NHO" "trace,decoy" >/dev/null
REC="$STORE/spawn-records/rtrace3.jsonl"; rm -f "$REC"
run run-open --run rtrace3 --session sid-rtrace3 --head "fixture head" --regime multi --regime-src owner \
    --handoff "$NHO" --detail "no trace section" --pid 1
need_rc 0
need_out "has no '## Trace' section"
need_eq "$(mk field "$REC" run-open trace_table)" "no section" "trace_table on the event"
verdict "run-open (controls): a hand-off whose Trace opens with its table is left byte-identical and silent; one with no Trace section is warned about and not seeded"

run reflect-inputs --run rrefl --session sid-rrefl --out "$STORE/spawn-records/blind-roots"
need_rc 2
need_out "allowed: any directory outside the run store ($REALSTORE)"
need_out "and the projects root ("
need_lines
need_nofile "$REALSTORE/spawn-records/blind-roots/turns.md"
verdict "reflect-inputs (register 2026-09-11 04:20): the refusal of an --out inside the run store names the allowed roots (control: the granted-directory leg above writes its four files)"

# (H9) The decisions channel (register 2026-09-13 03:53): gate and close hold (exit 6) on an unread
# AUTHOR observation or a changed decisions file until --ack records what was read.
fixture rhold 200
mk transcript sid-rhold 100000 >/dev/null
run gate --run rhold --to item1 --meter-line "$METER"
need_rc 0
need_absent "HOLD"
mk append "$REC" '{"event":"observation","phase":"","what":"AUTHOR INSTRUCTION (relayed by the launcher): run the second writer pass","note":"also in the decisions file"}' >/dev/null
LINES_BEFORE=$(mk lines "$REC")
run gate --run rhold --to item2 --meter-line "$METER"
need_rc 6
need_out "HOLD (decisions channel, exit 6)"
need_out "AUTHOR INSTRUCTION (relayed by the launcher): run the second writer pass"
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "the hold writes nothing"
run gate --run rhold --to item2 --meter-line "$METER" --ack "read the AUTHOR instruction: the second writer pass runs next"
need_rc 0
need_out "ack recorded"
need_eq "$(mk count "$REC" gate)" "2" "the acked gate is recorded"
need_eq "$(grep -c '"what": "ack: read the AUTHOR instruction' "$REC")" "1" "the ack observation"
run gate --run rhold --to item3 --meter-line "$METER"
need_rc 0
need_absent "HOLD"
verdict "the decisions channel (register 2026-09-13 03:53): an AUTHOR observation after the last gate holds the next gate (exit 6, lines printed, nothing written); --ack records what was read and proceeds; the next gate clears (control: the first gate cleared)"

DFILE="$WORK/author-decisions.md"
printf '# decisions\n- the checklist stays\n' > "$DFILE"
setmtime "$DFILE" -30
run gate --run rhold --to item4 --meter-line "$METER" --decisions-file "$DFILE"
need_rc 6
need_out "the decisions file"
run gate --run rhold --to item4 --meter-line "$METER" --decisions-file "$DFILE" --ack "read the decisions file: the checklist stays" --ack-digest "$(sha_file "$DFILE")"
need_rc 0
setmtime "$DFILE" 3600
run gate --run rhold --to item5 --meter-line "$METER" --decisions-file "$DFILE"
need_rc 0
need_absent "HOLD"
run gate --run rhold --to item5 --meter-line "$METER" --decisions-file "$WORK/no-such-decisions.md"
need_rc 2
need_out "is not a file"
verdict "the decisions channel: unacknowledged file content holds (exit 6) until its digest is acked; the same content clears independently of mtime; a named file that does not exist is refused (exit 2)"

mk append "$REC" '{"event":"observation","phase":"","what":"AUTHOR DECISION NOT YET APPLIED: the checklist justification","note":"relayed before the close"}' >/dev/null
run run-is-closed --run rhold
need_rc 1
need_out "open"
run close --run rhold --items "fixture items" --meter-line "$METER"
need_rc 6
need_out "AUTHOR DECISION NOT YET APPLIED"
need_eq "$(mk count "$REC" run-close)" "0" "the held close writes no run-close"
# The earlier gates bound this run's file, so the close finds it there and its ack names the digest.
run close --run rhold --items "fixture items" --meter-line "$METER" --ack "read the AUTHOR decision: the justification is applied" --ack-digest "$(sha_file "$DFILE")"
need_rc 0
need_eq "$(mk count "$REC" run-close)" "1" "the acked close"
run run-is-closed --run rhold
need_rc 0
need_out "closed"
run run-is-closed --run no-such-run-record
need_rc 2
verdict "close and run-is-closed: an AUTHOR observation after the last gate holds the close (exit 6, no run-close) until acked; run-is-closed exits 1 before the close, 0 after it and 2 with no record"

# Event order and unresolved ownership, including the read-only command's write proof.
"$PY" -B "$(dirname "$SRC")/test_run_is_closed.py" --handsoff "$H" --fixture-root "$WORK" \
  > "$WORK/run-is-closed.log" 2>&1
CLOSED_RC=$?
cat "$WORK/run-is-closed.log"
need_eq "$CLOSED_RC" "0" "run-is-closed regression suite"
verdict "run-is-closed: event order, explicit premise failures and read-only proof"

# The scratch root the patch above opened: an absolute one holds the suite's fixtures, which a
# restricted lane needs, and a relative one is a failed premise before any fixture is made.
RC=0
RUNENV="HANDSOFF=$H HOOKS_DIR=$HOOKS_DIR LANE_PY=$LANE_PY AIMYTH_TEST_SCRATCH_ROOT=relative/root"
runenv sh "$SRC" --leg "no leg is named this" >"$WORK/both" 2>&1 || RC=$?
RUNENV=""
need_rc 2
need_out "AIMYTH_TEST_SCRATCH_ROOT must be absolute"
mkdir -p "$WORK/granted-root"
RC=0
RUNENV="HANDSOFF=$H HOOKS_DIR=$HOOKS_DIR LANE_PY=$LANE_PY AIMYTH_TEST_SCRATCH_ROOT=$WORK/granted-root"
runenv sh "$SRC" --leg "run-resume: --session auto without a head-successor" >"$WORK/both" 2>&1 || RC=$?
RUNENV=""
need_rc 0
need_out "granted-root/handsoff-suite"
need_out "^PASS "
verdict "T2-B1 (fails on old): the suite's fixtures sit under any absolute AIMYTH_TEST_SCRATCH_ROOT, and a relative one is a failed premise"

# ------------------------------------------ folds of the critic round on these entries ----
# The decisions channel keys on the whole word AUTHOR: a non-letter or the end follows it.
fixture rword 200
mk transcript sid-rword 100000 >/dev/null
run gate --run rword --to item1 --meter-line "$METER"
need_rc 0
mk append "$REC" '{"event":"observation","phase":"","what":"AUTHORED the page for the index: a lane wrote it"}' >/dev/null
mk append "$REC" '{"event":"observation","phase":"","what":"AUTHORITY check: none needed"}' >/dev/null
run gate --run rword --to item2 --meter-line "$METER"
need_rc 0
need_absent "HOLD"
need_eq "$(mk count "$REC" gate)" "2" "the gate after the AUTHORED and AUTHORITY observations"
verdict "the decisions channel (whole word, must not fire): observations whose what opens AUTHORED or AUTHORITY, a longer word than AUTHOR, do not hold the gate"

for W in "AUTHOR-side note from the launcher: item1 is complete" "AUTHOR ruling: the tie-breaker order" "AUTHOR: run the second writer pass" "AUTHOR"; do
  mk append "$REC" "$("$PY" -c 'import json, sys; print(json.dumps({"event": "observation", "phase": "", "what": sys.argv[1]}))' "$W")" >/dev/null
  run gate --run rword --to "item held" --meter-line "$METER"
  need_rc 6
  need_out "HOLD (decisions channel, exit 6)"
  need_out "1 AUTHOR observation(s)"
  run gate --run rword --to "item held" --meter-line "$METER" --ack "read the relayed line: $W"
  need_rc 0
done
verdict "the decisions channel (whole word, must fire): observations opening AUTHOR-side, AUTHOR ruling, AUTHOR: and a bare AUTHOR each hold the next gate (exit 6) until acked"

# The two-heads check refuses only on positive evidence: a live head start it cannot place,
# because ps or the process's age cannot be read, is one warning line and the call proceeds.
REALPS=$(command -v ps) || die "no ps on PATH: the two-heads legs cannot run"
mkdir -p "$WORK/psnoage"
printf '#!/bin/sh\ncase "$*" in *etime=*) exit 1 ;; esac\nexec %s "$@"\n' "$REALPS" > "$WORK/psnoage/ps"
chmod +x "$WORK/psnoage/ps"
fixture rblind 200
sleep 120 &
PEERB=$!
sleep 1
mk transcript sid-rblind-peer 100000 >/dev/null
mk append "$REC" "$(printf '{"event":"head-successor","session_id":"sid-rblind-peer","pid":%d,"budget":1.0}' "$PEERB")" >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run gate --run rblind --to "item one" --meter-line "$METER"
need_rc 0
need_absent "TWO HEADS"
need_out "warn: gate: the two-heads check cannot verify"
need_out "process chain"
need_eq "$(grep -c '"what": "two heads"' "$REC")" "0" "no two-heads observation from a warning"
need_eq "$(mk count "$REC" gate)" "1" "the gate proceeded"
mk transcript sid-rblind-old 100000 >/dev/null
mk append "$REC" "$(printf '{"event":"head-successor","ts":"%s","session_id":"sid-rblind-old","pid":%d,"budget":1.0}' "$(tsago 3600)" "$PEERB")" >/dev/null
RUNENV="PATH=$WORK/psnoage:$PATH"
run gate --run rblind --to "item two" --meter-line "$METER"
need_rc 0
need_absent "TWO HEADS"
need_out "the process's age"
mk transcript sid-rblind-own 100000 >/dev/null
mk append "$REC" "$(printf '{"event":"head-successor","session_id":"sid-rblind-own","pid":%d,"budget":1.0}' "$PPID")" >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rblind --session sid-rblind-own --head "the caller's own head" --detail "ps unreadable"
need_rc 0
need_absent "TWO HEADS"
need_out "warn: run-resume: the two-heads check cannot verify"
need_eq "$(mk count "$REC" run-resume)" "1" "the run-resume proceeded"
verdict "two heads (broken premise, must not fire): with no readable ps a live foreign head start, and one naming the caller's own grandparent, give one warning line and the call proceeds (exit 0, no observation); with no readable process age a reused pid is a warning, not a refusal"

mk transcript sid-rblind-peer2 100000 >/dev/null
mk append "$REC" "$(printf '{"event":"head-successor","session_id":"sid-rblind-peer2","pid":%d,"budget":1.0}' "$PEERB")" >/dev/null
run run-resume --run rblind --session sid-rblind-third --head "a second head" --detail "resumed onto a live session"
need_rc 9
need_out "TWO HEADS"
run gate --run rblind --to "item three" --meter-line "$METER"
need_rc 9
need_eq "$(grep -c '"what": "two heads"' "$REC")" "2" "one observation per refusal"
kill "$PEERB"; wait "$PEERB" || :
mk transcript sid-rblind-big 100000 >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-rblind-big","pid":1099511627776,"budget":1.0}' >/dev/null
run gate --run rblind --to "item four" --meter-line "$METER"
need_rc 0
need_absent "Traceback"
need_absent "TWO HEADS"
verdict "two heads (positive evidence, must fire): with ps readable the same live foreign head start still refuses run-resume and gate (exit 9, one observation each); a recorded pid past the platform's pid range names no process and clears with no traceback"

# The shrink guard's baseline is the record's lists whenever it holds them: a grants file already
# narrowed by hand is never the contract a rewrite is checked against.
fixture rnarrow 200
GFN="$REALSTORE/spawn-records/rnarrow-grants.json"
run grants --run rnarrow --grant "$WORK/carry/nar-r" --write "$WORK/carry/nar-w1" --write "$WORK/carry/nar-w2"
need_rc 0
"$PY" - "$GFN" <<'NARROWEDFILE'
import json, sys
path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
d["writes"] = []
json.dump(d, open(path, "w", encoding="utf-8"), indent=1)
NARROWEDFILE
LINES_BEFORE=$(mk lines "$REC")
run grants --run rnarrow --on-limit resume
need_rc 2
need_out "would shrink the run's grants"
need_out "the write list loses"
need_out "carry/nar-w1"
need_out "against the grants event at"
need_lines
need_eq "$(gcount "$GFN" writes)" "0" "the narrowed file is left as it was"
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines after the refusal"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rnarrow --session sid-narrow --head "fixture head" --detail "no lists" --viewer none
need_rc 2
need_out "carry/nar-w2"
need_eq "$(mk count "$REC" run-resume)" "0" "no run-resume from the refusal"
verdict "the shrink guard (narrowed file, must fire): a grants file narrowed to an empty write list while the record's grants event holds the wider list refuses grants --on-limit and run-resume --viewer alike (exit 2), the delta printed against the recorded lists and nothing written"

run grants --run rnarrow --on-limit resume --write "$WORK/carry/nar-w1" --replace
need_rc 0
need_out "loses"
need_eq "$(glist "$GFN" writes "$WORK/carry/nar-w1")" "1" "the explicit re-issue is written"
run grants --run rnarrow --on-limit stop
need_rc 0
need_absent "would shrink"
need_eq "$(glist "$GFN" writes "$WORK/carry/nar-w1")" "1" "the carried write after the explicit call"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rnarrow --session sid-narrow2 --head "fixture head" --detail "narrowed on purpose" --write "$WORK/carry/nar-w3" --replace
need_rc 0
need_eq "$(mk field "$REC" run-resume writes_src)" "--write" "the run-resume event names its list source"
need_eq "$("$PY" -c 'import json, sys; e = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]; r = [x for x in e if x.get("event") == "run-resume"][-1]; print(1 if isinstance(r.get("writes"), list) and sys.argv[2] in r["writes"] else 0)' "$REC" "$WORK/carry/nar-w3")" "1" "the rewriting run-resume records its write list"
run grants --run rnarrow --viewer none
need_rc 0
need_absent "would shrink"
need_eq "$(glist "$GFN" writes "$WORK/carry/nar-w3")" "1" "the run-resume's list is carried"
verdict "the shrink guard (recorded baseline, must not fire): an explicit --write --replace re-issue is written with its delta noted and becomes the recorded baseline, so the next flag-less call proceeds; a rewriting run-resume records its lists, so its explicit narrowing (--replace) is not later read as a shrink"

# The network key: run-open and grants write it from --network (none when absent); every other
# rewrite carries it; a grants file written before the key reads as none.
nval() { "$PY" -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")).get("network", "<no key>")))' "$1"; }
NHO4="$WORK/handoffs/rnet-handoff.md"; mk handoff "$NHO4" >/dev/null
REC="$STORE/spawn-records/rnet.jsonl"; rm -f "$REC"
GFNET="$REALSTORE/spawn-records/rnet-grants.json"
viewer_use rnet
run run-open --run rnet --session sid-rnet --head "fixture head" --regime multi --regime-src owner \
    --handoff "$NHO4" --detail "no network flag" --pid 1
need_rc 0
need_eq "$(nval "$GFNET")" "[]" "run-open without --network writes none"
need_out "network none (default (no grants file))"
need_eq "$(mk field "$REC" run-open network_src)" "default (no grants file)" "network_src on the run-open event"
run grants --run rnet --network "API.OpenAlex.org, export.arxiv.org,api.openalex.org"
need_rc 0
need_eq "$(nval "$GFNET")" '["api.openalex.org", "export.arxiv.org"]' "grants --network writes the hosts lower-cased and de-duplicated"
need_out "network api.openalex.org,export.arxiv.org (arg)"
run grants --run rnet --on-limit resume
need_rc 0
need_eq "$(nval "$GFNET")" '["api.openalex.org", "export.arxiv.org"]' "grants without --network carries the hosts"
need_eq "$(mk field "$REC" grants network_src)" "grants" "the carried source on the grants event"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rnet --session sid-rnet2 --head "fixture head" --detail "viewer only" --viewer none
need_rc 0
need_eq "$(nval "$GFNET")" '["api.openalex.org", "export.arxiv.org"]' "a rewriting run-resume carries the hosts"
need_out "network api.openalex.org,export.arxiv.org"
run grants --run rnet --network none
need_rc 0
need_eq "$(nval "$GFNET")" "[]" "grants --network none writes none"
NHO5="$WORK/handoffs/rnet2-handoff.md"; mk handoff "$NHO5" >/dev/null
REC="$STORE/spawn-records/rnet2.jsonl"; rm -f "$REC"
run run-open --run rnet2 --session sid-rnet2x --head "fixture head" --regime multi --regime-src owner \
    --handoff "$NHO5" --detail "a named host" --pid 1 --network export.arxiv.org
need_rc 0
need_eq "$(nval "$REALSTORE/spawn-records/rnet2-grants.json")" '["export.arxiv.org"]' "run-open --network writes the host"
need_eq "$(mk field "$REC" run-open network)" '["export.arxiv.org"]' "the run-open event records the hosts"
need_out "network export.arxiv.org (arg)"
verdict "the network key (must write): run-open writes none without --network and the hosts with it; grants --network writes bare hosts lower-cased and de-duplicated; grants without the flag and a rewriting run-resume carry the value; --network none clears it"

SUM_NET=$(mk manifest "$REALSTORE/spawn-records" | grep rnet-grants)
for BAD in "" "https://api.openalex.org" "api.openalex.org:443" "none,api.openalex.org" "api.openalex.org,,export.arxiv.org" "*.openalex.org" "user@api.openalex.org" "api.openalex.org/x"; do
  run grants --run rnet --network "$BAD"
  need_rc 2
  need_out "network"
  need_lines
done
need_eq "$(mk manifest "$REALSTORE/spawn-records" | grep rnet-grants)" "$SUM_NET" "the grants file after the refusals"
REC="$STORE/spawn-records/rnet3.jsonl"; rm -f "$REC"
run run-open --run rnet3 --session sid-rnet3 --head "fixture head" --regime multi --regime-src owner \
    --handoff "$NHO5" --detail "a bad host" --pid 1 --network "https://export.arxiv.org"
need_rc 2
need_nofile "$REC"
need_nofile "$REALSTORE/spawn-records/rnet3-grants.json"
verdict "the network key (refusals): an empty value, a URL, a port, none inside a list, an empty item, a wildcard, a user@host and a path are each refused (exit 2, one PROBE FAILED line) with the grants file unchanged, and run-open refuses one before writing the record or the file"

fixture rnetold 200
GFO="$REALSTORE/spawn-records/rnetold-grants.json"
"$PY" - "$GFO" "$WORK/carry" <<'PREKEYGRANTS'
import json, os, sys
path, base = sys.argv[1], sys.argv[2]
json.dump({"run": "fixture", "grants": [os.path.join(base, "old-r")], "writes": [os.path.join(base, "old-w")],
           "on_limit": "stop", "viewer": "terminal", "source": "a grants file written before the network key"},
          open(path, "w", encoding="utf-8"), indent=1)
PREKEYGRANTS
run grants --run rnetold --viewer none
need_rc 0
need_out "network none (default (key absent))"
need_absent "Traceback"
need_eq "$(nval "$GFO")" "[]" "a file written before the key is rewritten with none"
need_eq "$(glist "$GFO" writes "$WORK/carry/old-w")" "1" "its write list is carried"
verdict "the network key (a grants file written before it): read as none (default (key absent)), never an error, and rewritten with an empty list while its lists are carried"

run grants --help
need_rc 0
need_out "--network"
run run-open --help
need_rc 0
need_out "--network"
DOCNET=$("$PY" -c 'import ast, sys
d = ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read()))
print(sum(1 for s in ("The network key.", "run-open --network none|HOST", "a file written before the key", "grants --network") if s in d))' "$H")
need_eq "$DOCNET" "4" "the network key's four phrases in the module docstring"
verdict "the network key (documented): run-open --help and grants --help name --network, and the module docstring documents the key, its default, its carry and a file written before it"

# The module docstring's seed pattern states the current rule, not the launcher's own pid.
DOCSEED=$("$PY" -c 'import ast, sys
d = ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read()))
old = sum(d.count(s) for s in ("passes ITS OWN pid", "a subshell, never the launcher"))
new = sum(1 for s in ("with NO --pid", "records no pid, and on a SEEDED record", "inside a `( … )` subshell it", "The seed pattern (register entries") if s in d)
print("%d %d" % (old, new))' "$H")
need_eq "$DOCSEED" "0 4" "the retired seed wording (0 hits) and the current rule (4 phrases)"
run successor --dry-run --run no-such-seed-run --budget-usd 1
need_absent "a subshell, never the launcher"
verdict "the seed pattern (docstring): the text that told a launcher to pass its own pid now says a launcher passes no --pid, a seed records none, and \$\$ names the launcher's shell even inside a subshell"

run --help
need_rc 0
need_out "raise-envelope"
need_out "run-is-closed"
DOCN=$("$PY" -c 'import ast, sys; d = ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read())); print(sum(1 for c in ("raise-envelope --run", "decision --run", "run-is-closed --run", "--pack-fresh", "--i-am-pid", "--decisions-file") if c in d))' "$H")
need_eq "$DOCN" "6" "the new subcommands and flags named in the module docstring"
run gate --help
need_rc 0
need_out "decisions-file"
need_out "i-am-pid"
verdict "help and docstring: raise-envelope and run-is-closed are listed by --help, the module docstring names raise-envelope, decision and run-is-closed with --pack-fresh, --i-am-pid and --decisions-file, and gate --help names its new flags"

# ------------------------- meters, waste fields, extraction, close and viewer (2026-09-13) ---
# A priced transcript for the real meter beside the script: N assistant calls of one million
# input tokens each, the model id naming the opus family, one minute apart from START (epoch
# seconds). Each call costs the family's input rate per MTok (prices.json), so every dollar
# figure below is arithmetic on that one rate.
cat > "$WORK/b2tx.py" <<'B2TX_END'
import json, os, re, sys, time
sid, n, start = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
slug = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"]))
path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], slug, sid + ".jsonl")
os.makedirs(os.path.dirname(path), exist_ok=True)
zulu = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"
with open(path, "w", encoding="utf-8") as fh:
    for i in range(n):
        fh.write(json.dumps({"type": "assistant", "isSidechain": False, "timestamp": zulu(start + 60 * i),
                             "message": {"id": "msg-%s-%d" % (sid, i), "role": "assistant",
                                         "model": "claude-fixture-opus-1",
                                         "content": [{"type": "text", "text": "fixture call"}],
                                         "usage": {"input_tokens": 1000000,
                                                   "cache_creation_input_tokens": 0,
                                                   "cache_read_input_tokens": 0,
                                                   "output_tokens": 0}}}) + "\n")
print(path)
B2TX_END
NOW=$("$PY" -c 'import time; print(int(time.time()))')
ONE=$("$PY" -c 'import json, sys; print("%.2f" % json.load(open(sys.argv[1]))["families"]["opus"]["input"])' "$SKILL_DIR/prices.json")
TWO=$("$PY" -c 'import sys; print("%.2f" % (2 * float(sys.argv[1])))' "$ONE")
THREE=$("$PY" -c 'import sys; print("%.2f" % (3 * float(sys.argv[1])))' "$ONE")
TWOJ=$("$PY" -c 'import json, sys; print(json.dumps(round(2 * float(sys.argv[1]), 2)))' "$ONE")

# Register entries 2026-09-09 15:27 and 2026-09-10 02:49: the meter prints its refusal on
# standard output, so a fallback reading standard error alone would never fire.
fixture rmtr 200
"$PY" "$WORK/b2tx.py" sid-rmtr 2 "$((NOW - 3000))" >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L1","class":"builder","reason":"(a)"}' >/dev/null
mk append "$REC" '{"event":"lane-spawned","lane":"L1","session_id":"sid-rmtr-lane-unwritten"}' >/dev/null
run boundary --run rmtr --from 1 --to 2 --disposition "a lane with no transcript yet" --waste none \
    --next n --dry-run
need_rc 0
need_out "head alone (--lanes none): the meter found no readable lane transcript under --lanes auto"
need_out "head \$$TWO · lanes not scanned · session \$$TWO"
need_absent "failed: exit"
need_out "meter invoked as "
need_out "--lanes auto"
need_out "--session sid-rmtr "
verdict "boundary meter (register 2026-09-09 15:27 and 2026-09-10 02:49, must fire): the meter's no-lane-transcript refusal is on standard output, the fallback reads it there and meters the head alone, the billed line says so, and --dry-run prints the meter invocation"

fixture rmtr2 200
mk append "$REC" '{"event":"lane-open","lane":"L1","class":"builder","reason":"(a)"}' >/dev/null
run boundary --run rmtr2 --from 1 --to 2 --disposition "a different refusal" --waste none \
    --next n --dry-run
need_rc 0
need_out "failed: exit 2 · fable share: unmetered ("
need_absent "head alone"
need_absent "no readable lane transcript found"
verdict "boundary meter (must not fire): a refusal other than the missing lane transcript (here the head has no transcript at all) is never retried under --lanes none, and the failure quotes the meter's own words rather than a bare exit 2"

fixture rmtr3 200
"$PY" "$WORK/b2tx.py" sid-rmtr3 2 "$((NOW - 3000))" >/dev/null
"$PY" "$WORK/b2tx.py" sid-rmtr3-lane 1 "$((NOW - 2970))" >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L1","class":"builder","reason":"(a)"}' >/dev/null
mk append "$REC" '{"event":"lane-spawned","lane":"L1","session_id":"sid-rmtr3-lane"}' >/dev/null
run boundary --run rmtr3 --from 1 --to 2 --disposition "a lane with its transcript" --waste none \
    --next n --dry-run
need_rc 0
need_out "head \$$TWO · lanes \$$ONE · session \$$THREE"
need_absent "head alone"
need_absent "failed:"
verdict "boundary meter (control): with the lane's transcript in place --lanes auto meters the head and the lane (two calls and one at \$$ONE) and takes no fallback"

fixture rmtr4 200
"$PY" "$WORK/b2tx.py" sid-rmtr4 1 "$((NOW - 3000))" >/dev/null
run boundary --run rmtr4 --from 0 --to 1 --disposition "no lane opened yet" --waste none \
    --next n --dry-run
need_rc 0
need_out "session \$$ONE"
need_absent "failed: exit"
need_absent "head alone"
verdict "boundary meter (a record before its first lane-open): a record with no lane-open yet is metered under --lanes auto with lanes 0 by the meter beside this script, so the first boundary carries a billed line"

# Register entry 2026-09-07: a lane killed with its head closes with total_cost_usd null.
fixture rkill 200
mk append "$REC" '{"event":"lane-open","lane":"K1","class":"builder"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"K1","session_id":"sid-rkill-lane","exit_class":"error","total_cost_usd":null,"cost_src":"result","report_words":5}' >/dev/null
"$PY" "$WORK/b2tx.py" sid-rkill-lane 2 "$((NOW - 3000))" >/dev/null
run boundary --run rkill --from 1 --to 2 --disposition "a killed lane" --waste none --next n \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary respawn_cost_usd)" "$TWOJ" "the killed lane billed from its transcript (the field as JSON)"
case $(mk field "$REC" phase-boundary respawn_src) in
  *"1 metered (transcript): K1 \$$TWO"*) : ;;
  *) why="$why; respawn_src: $(mk field "$REC" phase-boundary respawn_src)" ;;
esac
need_out "re-spawn \$$TWO · "
need_out "re-spawn: 0 close cost(s) as recorded · 1 metered (transcript)"
WTK="$WORK/rkill-table.md"
run waste-table --run rkill --out "$WTK"
need_rc 0
need_eq "$(grep -c "lost lane · K1 · exit class error | metered (transcript) \\\$$TWO" "$WTK")" "1" "the lost-lane row billed from the transcript"
verdict "killed lane (register 2026-09-07, must fire): a lane-closed with total_cost_usd null is billed from its surviving transcript by the meter, the boundary field and the waste-table row both saying metered (transcript)"

fixture rkill2 200
mk append "$REC" '{"event":"lane-closed","lane":"K2","session_id":"sid-rkill-none","exit_class":"error","total_cost_usd":null,"report_words":5}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"C2","exit_class":"budget","total_cost_usd":2.5,"report_words":5}' >/dev/null
run boundary --run rkill2 --from 1 --to 2 --disposition "a killed lane, no transcript" \
    --waste none --next n --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary respawn_cost_usd)" "null" "no cost and no transcript: null, never 0"
case $(mk field "$REC" phase-boundary respawn_src) in
  *"unmeasured: 1 lane(s) with no cost and no metered transcript (K2: no transcript for lane session sid-rkill-none"*"beside a priced part of \$2.50"*) : ;;
  *) why="$why; respawn_src: $(mk field "$REC" phase-boundary respawn_src)" ;;
esac
need_out "re-spawn unmeasured"
need_absent "re-spawn \$"
WTK2="$WORK/rkill2-table.md"
run waste-table --run rkill2 --out "$WTK2"
need_rc 0
need_eq "$(grep -c 'lost-lane cost re-spawned · 1 → 2 at .* | unmeasured (the field is null)' "$WTK2")" "1" "the span figure reads unmeasured"
need_eq "$(grep -c 'lost lane · K2 · exit class error | unmeasured (the field is null) .*no transcript for lane session sid-rkill-none' "$WTK2")" "1" "the lane row names why"
WTK3="$WORK/rkill-nometer-table.md"
run waste-table --run rkill --out "$WTK3" --no-meter
need_rc 0
need_eq "$(grep -c 'lost lane · K1 · exit class error | unmeasured (the field is null)' "$WTK3")" "1" "--no-meter runs no transcript meter"
verdict "killed lane (must not fire): with no transcript to meter the span's figure is null and renders unmeasured beside the priced part (\$2.50), never \$0.00, and --no-meter bills no transcript (control: the leg above billed K1)"

# Register entry 2026-09-10 03:05: a wave cut by the limit and resumed priced at $0.00.
fixture rcut 200
for pair in R1:3.32 R3:2.81 R4:3.36; do
  lane=${pair%%:*}; cost=${pair#*:}
  mk append "$REC" "$(printf '{"event":"lane-open","lane":"%s","class":"reflector"}' "$lane")" >/dev/null
  mk append "$REC" "$(printf '{"event":"lane-closed","lane":"%s","exit_class":"limit","total_cost_usd":%s,"report_words":5}' "$lane" "$cost")" >/dev/null
done
for lane in R1 R3 R4; do
  mk append "$REC" "$(printf '{"event":"lane-resumed","lane":"%s","after_limit":true}' "$lane")" >/dev/null
  mk append "$REC" "$(printf '{"event":"lane-closed","lane":"%s","exit_class":"completed","total_cost_usd":5.0,"report_words":5}' "$lane")" >/dev/null
done
run boundary --run rcut --from 2 --to 3 --disposition "a limit-cut wave, resumed" --waste none \
    --next n --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary respawn_cost_usd)" "0.0" "re-spawn keeps its meaning: every cut lane was resumed"
need_eq "$(mk field "$REC" phase-boundary respawn_excluded)" "3" "respawn_excluded"
need_eq "$(mk field "$REC" phase-boundary limit_cut_resumed)" "3" "limit_cut_resumed"
need_eq "$(mk field "$REC" phase-boundary limit_cut_resumed_usd)" "9.49" "3.32 + 2.81 + 3.36"
need_out "re-spawn \$0.00 · "
need_out "limit-cut resumed \$9.49 (3 lane(s): first attempts, excluded from re-spawn)"
WTC="$WORK/rcut-table.md"
run waste-table --run rcut --out "$WTC"
need_rc 0
need_eq "$(grep -c 'first attempts of limit-cut lanes later resumed · 2 → 3 at .* | \$9.49 · phase-boundary.limit_cut_resumed_usd .*| structural |' "$WTC")" "1" "the separate structural row"
verdict "limit-cut wave (register 2026-09-10 03:05, must fire): three lanes closed limit and resumed keep re-spawn at \$0.00 and put their first attempts' \$9.49 on a separate figure of the boundary line and a structural row of the table"

fixture rcut2 200
mk append "$REC" '{"event":"lane-closed","lane":"B1","exit_class":"budget","total_cost_usd":4.0,"report_words":5}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"B1"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"B1","exit_class":"completed","total_cost_usd":1.0,"report_words":5}' >/dev/null
run boundary --run rcut2 --from 1 --to 2 --disposition "a budget cut, resumed" --waste none \
    --next n --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary respawn_excluded)" "1" "the resumed cut is still excluded"
need_eq "$(mk field "$REC" phase-boundary limit_cut_resumed)" "0" "a budget cut is no limit cut"
need_eq "$(mk field "$REC" phase-boundary limit_cut_resumed_usd)" "0.0" "no limit-cut cost"
need_absent "limit-cut resumed"
verdict "limit-cut wave (must not fire): a lane cut by its budget and resumed is excluded from re-spawn as before and adds nothing to the limit-cut figure, which the line then omits"

# Register entry 2026-09-06: the head fence's denies, beside the lanes' tool denials.
fixture rden 200
DEN="$WORK/state-den"
mkdir -p "$DEN"
"$PY" - "$DEN/events.log" <<'B2DEN_END'
import sys, time
now = time.time()
st = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))
rows = [(st(now - 60), "sid-rden", "head-fence", "deny", "a compound the fence refused"),
        (st(now - 50), "sid-rden", "head-fence", "deny", "a second refused compound"),
        (st(now - 40), "sid-rden", "head-fence", "deny-no-grants", "a command with no grants file"),
        (st(now - 30), "sid-other", "head-fence", "deny", "another head's deny"),
        (st(now - 9000), "sid-rden", "head-fence", "deny", "a deny before the span"),
        (st(now - 20), "sid-rden", "head-fence", "allow-unarmed", "not a deny"),
        (st(now - 10), "sid-rden", "handsoff-gate", "deny", "the band hook, not the fence")]
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    fh.write("".join("\t".join(row) + "\n" for row in rows))
B2DEN_END
RUNENV="AIMYTH_STATE_DIR=$DEN"
run boundary --run rden --from 1 --to 2 --disposition "head denies" --waste none --next n \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary head_denials)" "3" "two denies and one deny-no-grants of this head in the span"
case $(mk field "$REC" phase-boundary head_denials_src) in
  *"3 head-fence deny line(s) for session(s) sid-rden in the span, of 6 head-fence line(s) among 7 read"*) : ;;
  *) why="$why; head_denials_src: $(mk field "$REC" phase-boundary head_denials_src)" ;;
esac
need_out "denials 0 · over-cap"
need_out "head fence denials 3"
WTN="$WORK/rden-table.md"
run waste-table --run rden --out "$WTN"
need_rc 0
need_eq "$(grep -c 'head fence denials · 1 → 2 at .* | 3 · phase-boundary.head_denials' "$WTN")" "1" "the head's row"
need_eq "$(grep -c 'lane tool denials · 1 → 2 at ' "$WTN")" "1" "the lanes' row names its scope"
need_eq "$(grep -c 'the tool denials row counts the LANES' "$WTN")" "1" "the legend names the scope"
verdict "denials scope (register 2026-09-06, must fire): the head fence's deny lines for this head inside the span are counted from events.log (another head's, one before the span, an allow and the band hook's deny left out), beside the lanes' tool denials, and the table's legend and labels name both scopes"

fixture rden2 200
RUNENV="AIMYTH_STATE_DIR=$WORK/state-den-none"
run boundary --run rden2 --from 1 --to 2 --disposition "no fence log" --waste none --next n \
    --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary head_denials)" "null" "no events.log: unmeasured, never 0"
case $(mk field "$REC" phase-boundary head_denials_src) in
  "unmeasured: no events.log at "*) : ;;
  *) why="$why; head_denials_src: $(mk field "$REC" phase-boundary head_denials_src)" ;;
esac
need_out "head fence denials unmeasured"
fixture rden3 200
RUNENV="AIMYTH_STATE_DIR=$DEN"
run boundary --run rden3 --from 1 --to 2 --disposition "a head with no deny" --waste none \
    --next n --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary head_denials)" "0" "a measured zero for a head the log never names"
case $(mk field "$REC" phase-boundary head_denials_src) in
  *"of 6 head-fence line(s) among 7 read"*) : ;;
  *) why="$why; the zero carries no control: $(mk field "$REC" phase-boundary head_denials_src)" ;;
esac
verdict "denials scope (must not fire): with no events.log the head's figure is null and the line reads unmeasured, and a head the log never names reads 0 beside the 6 head-fence lines read (its control)"

# Register entry 2026-09-09 15:43: the run total reads a billed line carried by hand as well as the
# meter's literal `session $`.
fixture rtot 200
mk append "$REC" '{"event":"phase-boundary","from":"1","to":"2","meter":"failed: exit 2"}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"2","to":"3","meter":"billed (list, prices 2026-09-03): head $11.24 · lanes $14.34 · session $25.58 (the meter run by hand)"}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"3","to":"4","meter":"head USD 18.58 (the harness line) · lanes 14.34 · session ≈ 32.92"}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"4","to":"5","meter":"head USD 24.83 (the harness line) · lanes 20.89 · session ≈ 45.72"}' >/dev/null
WTO="$WORK/rtot-table.md"
run waste-table --run rtot --out "$WTO" --no-meter
need_rc 0
need_eq "$(grep -c 'heads. total (shown sum) | \$45.72 = \$45.72 · per head: sid-rtot the last boundary billed line.s .session ≈. \$45.72 (a figure carried by hand)' "$WTO")" "1" "the hand-carried approximate form is read"
need_eq "$(grep -c '1 boundary line(s) carried no session figure' "$WTO")" "1" "only the failed line carries no figure"
fixture rtot2 200
mk append "$REC" '{"event":"phase-boundary","from":"4","to":"5","meter":"head USD 52.34 · lanes USD 20.22 · session USD 72.56"}' >/dev/null
WTO2="$WORK/rtot2-table.md"
run waste-table --run rtot2 --out "$WTO2" --no-meter
need_rc 0
need_eq "$(grep -c 'heads. total (shown sum) | \$72.56 = \$72.56 · per head: sid-rtot2 the last boundary billed line.s .session USD. \$72.56 (a figure carried by hand)' "$WTO2")" "1" "the USD form is read"
verdict "run total (register 2026-09-09 15:43, must fire): a billed line carried by hand as 'session ≈ <n>' or 'session USD <n>' is read into the run total and the row names the form, while a failed line still carries no figure"

fixture rtot3 200
mk append "$REC" '{"event":"phase-boundary","from":"1","to":"2","meter":"billed (list, prices 2026-09-03): head $5.00 · lanes $0.00 · session $5.00"}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"2","to":"3","meter":"head USD 6.10 (the harness line) · session ≈ n/a (the meter failed) · sessions $9.99 · session 0a1b2c3d"}' >/dev/null
WTO3="$WORK/rtot3-table.md"
run waste-table --run rtot3 --out "$WTO3" --no-meter
need_rc 0
need_eq "$(grep -c 'heads. total (shown sum) | \$5.00 = \$5.00 · per head: sid-rtot3 the last boundary billed line.s .session \$. \$5.00' "$WTO3")" "1" "the earlier literal figure stands"
need_eq "$(grep -c '1 boundary line(s) carried no session figure' "$WTO3")" "1" "the n/a line is quoted, not read"
need_eq "$(grep -c 'a figure carried by hand' "$WTO3")" "0" "no hand-carried form was read"
verdict "run total (must not fire): 'session ≈ n/a', 'sessions \$9.99' and a session id are no figure, so the last line carrying one (the meter's \$5.00) stands and the n/a line is quoted"

# Register entries 2026-09-07 (the reflect-inputs counts) and 2026-09-13 03:53 (owner messages
# delivered mid-turn): one transcript holding every record class this suite knows, 26 records,
# each expected bucket named beside it.
cat > "$WORK/b2every.py" <<'B2EVERY_END'
import json, os, re, sys
sid = sys.argv[1]
slug = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"]))
path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], slug, sid + ".jsonl")
os.makedirs(os.path.dirname(path), exist_ok=True)
NOTE = "<task-notification><task-id>b1</task-id><status>completed</status></task-notification>"
def user(content, **extra):
    rec = {"type": "user", "timestamp": "2026-09-12T23:50:00Z",
           "message": {"role": "user", "content": content}}
    rec.update(extra)
    return rec
def asst(content, model="claude-fixture-1"):
    return {"type": "assistant", "timestamp": "2026-09-12T23:50:10Z",
            "message": {"role": "assistant", "model": model, "content": content}}
def text(t):
    return [{"type": "text", "text": t}]
records = [
    user(text("the owner's first message")),                                        # human
    asst(text("the assistant answers in prose")),                                   # assistant
    asst([{"type": "tool_use", "name": "Read", "input": {"file_path": "/fixture/a.md"}}]),  # tool-call turn
    asst([{"type": "thinking", "thinking": "a thought"}]),                         # other
    asst([]),                                                                       # other
    user([{"type": "tool_result", "content": "tool output text"}]),                 # tool_result
    user(text("Base directory for this skill: fixture"), isMeta=True),              # meta
    user(text("<system-reminder>injected</system-reminder>")),                      # notification
    user(text(NOTE)),                                                               # notification
    user(text(NOTE + "\nthe owner's mid-turn ruling MIDTURN-MARK-2350")),           # human (cut)
    user([{"type": "text", "text": NOTE},
          {"type": "text", "text": "a second mid-turn message MIDTURN-MARK-BLOCK"}]),  # human (cut)
    user(text("<task-notification>an unclosed notification UNCLOSED-NOTE")),         # notification
    user(text("[Request interrupted by user]")),                                    # interrupt
    user(text("[Request interrupted by user for tool use]")),                       # interrupt
    user(text("User: an earlier turn\nAssistant: an earlier answer\nUser: the replayed owner message")),  # human (trimmed)
    user(text("Assistant: a replay with no human marker\nAssistant: and another")),  # replay
    asst(text("No response requested."), model="<synthetic>"),                      # synthetic
    {"type": "progress", "data": {}},                                               # other
    {"type": "summary", "summary": "a summary"},                                    # other
    {"type": "system", "content": "a system record"},                               # other
    {"type": "file-history-snapshot", "snapshot": {}},                              # other
    {"type": "queue-operation", "operation": "enqueue", "content": "queued"},        # other
    {"message": {"role": "user"}},                                                  # other
    user([{"type": "tool_result", "content": "output"},
          {"type": "text", "text": "a message beside a tool result MIDTURN-MARK-RESULT"}]),  # human
]
with open(path, "w", encoding="utf-8") as fh:
    fh.write("".join(json.dumps(r) + "\n" for r in records) + "{a torn line\n[1, 2]\n")    # unparseable x2
print(path)
B2EVERY_END
"$PY" "$WORK/b2every.py" sid-every >/dev/null
EVX="$WORK/every"
run extract-transcript --session sid-every --out "$EVX"
need_rc 0
need_out "6 turns (5 human, 1 assistant) of 26 records"
need_out "interrupt 2, replay 1, synthetic 1, unparseable 2, other 8, compaction 0, cross_session 0 · reconciles"
"$PY" -c 'import json, sys; c = json.load(open(sys.argv[1])); print(c["records"], c["extracted"] + c["tool_call_turns"] + sum(c["excluded"].values()), c["in_no_bucket"], c["reconciles"], c["excluded"]["other"], len(c["other_types"]))' "$EVX/counts.json" > "$WORK/every.txt"
need_eq "$(cat "$WORK/every.txt")" "26 26 0 True 8 8" "records = extracted + tool_call_turns + every exclusion, other holding 8 records of 8 named types"
need_eq "$(mk json "$EVX/counts.json" other_types.queue-operation)" "1" "a queue-operation record is named under other_types"
need_eq "$(grep -c 'Records = 6 extracted + 1 tool-call + 19 excluded = 26, against 26 records read: reconciles' "$EVX/turns.md")" "1" "the header prints the reconciliation as an equation"
env LLM_WIKI_STORE="$STORE" "$PY" - "$H" <<'B2RECON_END' > "$WORK/recon.txt"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
whole = {"records": 5, "extracted": 2, "tool_call_turns": 1, "excluded": {"tool_result": 1, "other": 1}}
short = {"records": 8, "extracted": 2, "tool_call_turns": 1, "excluded": {"tool_result": 1, "other": 1}}
print("%s | %s" % (mod.reconciliation_text(whole), mod.reconciliation_text(short)))
B2RECON_END
need_eq "$(cat "$WORK/recon.txt")" "reconciles | DOES NOT RECONCILE: 3 record(s) in no bucket" "the verdict fires on a planted shortfall of 3 and not on a whole sum"
fixture rrefl2 200
run reflect-inputs --run rrefl2 --session sid-every --out "$WORK/refl-every" --no-meter
need_rc 0
need_eq "$(mk field "$STORE/spawn-records/rrefl2.jsonl" reflect-inputs counts | grep -c '"in_no_bucket": 0')" "1" "the reflect-inputs event carries the reconciliation"
verdict "extraction counts (register 2026-09-07, must fire and must not): a transcript of every record class reconciles, 26 = 6 extracted + 1 tool-call + 19 excluded with other 8 by type, the header prints the equation, the verdict reads DOES NOT RECONCILE on a planted shortfall, and reflect-inputs carries it"

need_eq "$(grep -c 'MIDTURN-MARK-2350' "$EVX/turns.md")" "1" "an owner message after a notification in one text block"
need_eq "$(grep -c 'MIDTURN-MARK-BLOCK' "$EVX/turns.md")" "1" "an owner message in a text block beside a notification block"
need_eq "$(grep -c 'MIDTURN-MARK-RESULT' "$EVX/turns.md")" "1" "an owner message beside a tool result"
need_eq "$(mk json "$EVX/counts.json" notes.injections_cut)" "2" "two records kept after a span was cut"
need_eq "$(mk json "$EVX/counts.json" notes.tool_result_with_text)" "1" "one tool-result record carrying owner text"
need_eq "$(mk json "$EVX/counts.json" excluded.interrupt)" "2" "both interrupt markers excluded"
need_eq "$(grep -c 'Request interrupted by user' "$EVX/turns.md")" "0" "no interrupt marker reads as a human turn"
need_eq "$(grep -c '<task-notification' "$EVX/turns.md")" "0" "the notification spans are cut out of the kept turns"
verdict "mid-turn owner messages (register 2026-09-13 03:53, must fire): a known owner message delivered with a task notification, in a block beside one and beside a tool result each appears as a human turn, and the two interrupt markers are excluded rather than counted as human turns"

need_eq "$(mk json "$EVX/counts.json" excluded.notification)" "3" "a reminder alone, a notification alone and an unclosed notification stay excluded"
need_eq "$(grep -c 'UNCLOSED-NOTE' "$EVX/turns.md")" "0" "the unclosed notification stays out"
mk metascript sid-prose >/dev/null
"$PY" - "$PROJECTS" "$VAULT" <<'B2PROSE_END' >/dev/null
import json, os, re, sys
slug = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(sys.argv[2]))
path = os.path.join(sys.argv[1], slug, "sid-prose.jsonl")
rows = [{"type": "user", "timestamp": "2026-09-12T23:51:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "please check how a <task-notification> tag is handled PROSE-MARK"}]}},
        {"type": "user", "timestamp": "2026-09-12T23:52:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user] and then I typed this TYPED-MARK"}]}}]
with open(path, "w", encoding="utf-8") as fh:
    fh.write("".join(json.dumps(r) + "\n" for r in rows))
B2PROSE_END
run extract-transcript --session sid-prose --out "$WORK/prose"
need_rc 0
need_out "2 turns (2 human, 0 assistant) of 2 records"
need_eq "$(grep -c 'PROSE-MARK' "$WORK/prose/turns.md")" "1" "a prose mention of the tag is the owner's"
need_eq "$(grep -c 'TYPED-MARK' "$WORK/prose/turns.md")" "1" "words typed after a marker are the owner's"
verdict "mid-turn owner messages (must not fire): a record that is nothing but notifications, a reminder alone and an unclosed notification stay excluded (3), while a prose mention of the tag and a line typed after the interrupt marker stay human turns"

# Register entry 2026-09-10 17:43: the close re-reads the record after the report was written.
sha_of() { "$PY" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
report_fixture() { # $1 path, $2 the warnings heading
  printf '%s\n' '# Run report (a suite fixture, not a vault page)' '' '## Spend against the envelope' '' \
    'The head wrote this at item 5: session $72.56, resumed once.' '' "$2" '' \
    '- the first stop, as the head wrote it.' '' '## Related' '- a fixture link' > "$1"
}
STAMPS=$("$PY" -c 'import time; f = lambda s: time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - s)); print(f(3000), f(2700), f(1200), f(600))')
T1=$(echo "$STAMPS" | cut -d' ' -f1); T2=$(echo "$STAMPS" | cut -d' ' -f2)
T3=$(echo "$STAMPS" | cut -d' ' -f3); T4=$(echo "$STAMPS" | cut -d' ' -f4)
CLOSE_METER='billed (list, prices 2026-09-03): head $74.51 · lanes $23.20 · session $97.71'
fixture rrep 200
mk append "$REC" "$(printf '{"event":"lane-closed","lane":"B-registry","exit_class":"limit","total_cost_usd":0.78,"ts":"%s"}' "$T1")" >/dev/null
mk append "$REC" "$(printf '{"event":"stop-condition","which":"limit","lane":"head","ts":"%s"}' "$T1")" >/dev/null
mk append "$REC" "$(printf '{"event":"head-resumed","session_id":"sid-rrep","ts":"%s"}' "$T2")" >/dev/null
RPT="$WORK/rrep-report.md"
report_fixture "$RPT" '## Warnings and handling'
# the second stop and its resume come after the report was written, and the close meters last
mk append "$REC" "$(printf '{"event":"stop-condition","which":"limit","lane":"head","ts":"%s"}' "$T3")" >/dev/null
mk append "$REC" "$(printf '{"event":"head-resumed","session_id":"sid-rrep","ts":"%s"}' "$T4")" >/dev/null
run close --run rrep --items "fixture items" --report "$RPT" --meter-line "$CLOSE_METER"
need_rc 0
need_out "patched Closing meter (handsoff.py close), Limit stops on the record (handsoff.py close)"
need_eq "$(grep -c '^- \*\*Closing meter (handsoff.py close):\*\* billed (list, prices 2026-09-03): head \$74.51 · lanes \$23.20 · session \$97.71$' "$RPT")" "1" "the spend section carries the closing meter"
need_eq "$(grep -c '^- \*\*Limit stops on the record (handsoff.py close):\*\* 2 limit stop(s): head at .* → head-resumed .*, 5.0 min; head at .* → head-resumed .*, 10.0 min · 1 lane(s) closed limit: B-registry' "$RPT")" "1" "the warnings section names both stops and the lane"
need_eq "$(grep -c 'The head wrote this at item 5: session \$72.56, resumed once.' "$RPT")" "1" "the head's own prose is untouched"
need_eq "$(mk field "$REC" run-close report_patched)" '["Closing meter (handsoff.py close)", "Limit stops on the record (handsoff.py close)", "Hard stops on the record (handsoff.py close)"]' "the run-close records what was patched"
need_eq "$(grep -c '^- \*\*Hard stops on the record (handsoff.py close):\*\* 0 hard stop(s) on the head other than a limit · 0 lane(s) closed other than completed or limit · 0 completed lane(s) met denials, none a stop · read from the record at the close' "$RPT")" "1" "the hard-stops bullet states its counts (this fixture has limit stops only)"
"$PY" - "$RPT" <<'B2ORDER_END' > "$WORK/order.txt"
import sys
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
at = lambda p: next(i for i, l in enumerate(lines) if l.startswith(p))
print(at("## Spend") < at("- **Closing meter") < at("## Warnings") < at("- **Limit stops") < at("## Related"))
B2ORDER_END
need_eq "$(cat "$WORK/order.txt")" "True" "each bullet sits inside its own section"
verdict "close re-read (register 2026-09-10 17:43, must fire): a report written before the run's second limit stop and its closing meter gets one bullet under Spend (the close's billed line) and one under Warnings (both stops with their minutes, and the lane closed limit), the head's prose untouched"

H1=$(sha_of "$RPT")
run close --run rrep --items "fixture items" --report "$RPT" --meter-line "$CLOSE_METER"
need_rc 0
need_out "already current, not rewritten"
need_eq "$(sha_of "$RPT")" "$H1" "an already-current report is left byte for byte"
fixture rrep2 200
RPT2="$WORK/rrep2-report.md"
report_fixture "$RPT2" '## Warnings and handling'
H2=$(sha_of "$RPT2")
run close --run rrep2 --items "fixture items" --meter-line "$CLOSE_METER"
need_rc 0
need_absent "report:"
need_eq "$(sha_of "$RPT2")" "$H2" "a close without --report leaves the page alone"
need_eq "$(mk field "$STORE/spawn-records/rrep2.jsonl" run-close report)" "<no key report>" "no report key on its run-close"
verdict "close re-read (must not fire): an already-current report is not rewritten, and a close without --report neither reads nor writes one"

fixture rrep3 200
run close --run rrep3 --items "fixture items" --report "$WORK/no-such-report.md" --meter-line "$CLOSE_METER"
need_rc 2
need_out "PROBE FAILED: --report"
need_lines
need_eq "$(mk count "$REC" run-close)" "0" "a refused close writes nothing"
fixture rrep4 200
RPT4="$WORK/rrep4-report.md"
report_fixture "$RPT4" '## Notes'
run close --run rrep4 --items "fixture items" --report "$RPT4" --meter-line "$CLOSE_METER"
need_rc 3
need_out "NOT patched: no '## Warnings…' section"
need_eq "$(mk count "$REC" run-close)" "1" "the close itself is written"
need_eq "$(grep -c 'Closing meter (handsoff.py close)' "$RPT4")" "1" "the section that exists is still patched"
plain_fixture rrep5
run close --run rrep5 --items "fixture items" --report "$RPT"
need_rc 2
need_out "patches no run report"
need_eq "$(mk count "$REC" run-close)" "0" "the plain close writes nothing"
verdict "close re-read (premises): a --report that is not a file is refused (exit 2) before any write, a report lacking its warnings section keeps its spend bullet and the close exits 3 naming the section, and a plain lane run's close refuses --report (exit 2)"

# Register entry 2026-09-09 11:21: the opener retries once through the same command, names the
# path and the attempt, and a detaching caller opens first and writes the lines to its log.
cat > "$WORK/bin/viewer-once.sh" <<'VONCE'
#!/bin/sh
for a in "$@"; do printf '%s\n' "$a" >> "$AIMYTH_VIEWER_ARGV"; done
n=0; [ -f "$AIMYTH_VIEWER_ARGV.count" ] && n=$(cat "$AIMYTH_VIEWER_ARGV.count"); n=$((n + 1))
printf '%s\n' "$n" > "$AIMYTH_VIEWER_ARGV.count"
if [ "$n" -le 1 ]; then printf 'stub viewer: the first window refuses\n' >&2; exit 1; fi
exit 0
VONCE
chmod +x "$WORK/bin/viewer-once.sh"
VHO1="$WORK/handoffs/vonce-handoff.md"; mk handoff "$VHO1" >/dev/null
REC="$STORE/spawn-records/rvonce.jsonl"; rm -f "$REC"
viewer_use vonce
RUNENV="AIMYTH_VIEWER_CMD=$WORK/bin/viewer-once.sh"
run run-open --run rvonce --session sid-vonce --head "fixture head" --regime single --regime-src owner \
    --handoff "$VHO1" --detail "an opener that refuses once" --pid 1
need_rc 0
need_out "viewer: Terminal window opened on $(console_cmd rvonce) via $WORK/bin/viewer-once.sh (retry, after first attempt: "
need_out "the first window refuses"
need_eq "$(viewer_calls)" "2" "the first attempt and one retry"
fixture rvonced 200     # a record with no recorded pid: rvonce's run-open --pid 1 names every process's ancestor
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvonced --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "retry: the same command 1 time(s) on a failure"
verdict "viewer retry (register 2026-09-09 11:21, must fire): an opener that refuses its first call is retried once through the same command and the window line names the command file, the opener's path and that the retry opened it"

fixture rvwlog 200
viewer_use vlog
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwlog --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "(first attempt)"
need_eq "$(viewer_calls)" "1" "an opener that opens is not retried"
SLOG=$(sed -n 's/.*detached (log \([^)]*\)).*/\1/p' "$WORK/out" | head -1)
need_file "$SLOG"
sleep 2   # the detached starter aborts on the missing harness
"$PY" - "$SLOG" <<'B2SLOG_END' > "$WORK/slog.txt"
import sys
lines = open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines()
first = next((i for i, l in enumerate(lines) if "viewer: first attempt via " in l and "rvwlog-console.command · opened" in l), None)
window = next((i for i, l in enumerate(lines) if "viewer: Terminal window opened on " in l and "rvwlog-console.command via " in l), None)
starter = next((i for i, l in enumerate(lines) if l.startswith("starter: ")), None)
print(first is not None and window is not None and (starter is None or window < starter))
B2SLOG_END
need_eq "$(cat "$WORK/slog.txt")" "True" "the opener's path, outcome and window line are in the starter log before the starter's own first line"
verdict "viewer before the detach (must not fire twice): successor opens the window before it detaches the starter, an opener that opens is called once, and the starter's log carries the opener's path, outcome and window line ahead of the starter's own lines"

run close --help
need_rc 0
need_out "--report"
run _starter --help
need_rc 0
need_out "--viewer-opened"
run _resume-head --help
need_rc 0
need_out "--viewer-opened"
DOCB2=$("$PY" -c 'import ast, sys
d = ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read()))
new = ("meter invoked as", "--viewer-opened", "close --report PATH", "notes.replay_trimmed", "limit_cut_resumed_usd", "head fence denials", "session USD <n>", "model_src", "metered (transcript)", "DOES NOT RECONCILE")
old = ("which needs no Automation permission", "marker and counted\nunder `excluded.replay`")
print("%d %d" % (sum(1 for s in new if s in d), sum(d.count(s) for s in old)))' "$H")
need_eq "$DOCB2" "10 0" "the ten new phrases in the module docstring and the two retired ones gone"
verdict "help and docstring (the 2026-09-13 amendments): close --help names --report, _starter and _resume-head name --viewer-opened, and the module docstring carries the meter, waste-field, extraction, close and viewer amendments with the retired fallback wording gone"

# Register entry 2026-09-10 20:29: the head-start events carry the model and effort the head's
# command line runs under, and (2026-09-09 11:21) a starter handed --viewer-opened opens nothing.
own_start() { # $1 record, $2 event kind: the model, effort and model_src of the last such event the harness stub did not write
  "$PY" - "$1" "$2" <<'B2OWN_END'
import json, sys
evs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
own = [e for e in evs if e.get("event") == sys.argv[2] and e.get("session_id") != "sid-by-the-head"]
print(" ".join(json.dumps(own[-1].get(k)) for k in ("model", "effort", "model_src")) if own else "none")
B2OWN_END
}
fixture rmodel 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
viewer_use vmodel
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rmodel --handoff "$HO" --budget 3.50 --out "$WORK/starter/rmodel-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --model opus --effort high \
        --viewer-opened
need_rc 0
need_eq "$(own_start "$REC" head-successor)" '"opus" "high" "arg"' "the starter's head-successor carries its command line's model and effort"
case $(sed -n 1p "$WORK/stub-rmodel.args") in *"--model opus --effort high"*) : ;; *) why="$why; the stub was not started with --model opus --effort high: $(sed -n 1p "$WORK/stub-rmodel.args")" ;; esac
need_out "viewer: the caller ran the opener before the detach"
need_no_viewer
verdict "head-start events (register 2026-09-10 20:29, must fire): the starter's head-successor records model opus and effort high, the values its harness command line carried, and a starter handed --viewer-opened opens no window for that start"

fixture rmodel2 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
viewer_use vmodel2
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rmodel2 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rmodel2-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_eq "$(own_start "$REC" head-successor | cut -d' ' -f1-2)" '"fixture-model" "max"' "no --model: the record's own model is inherited, beside effort max"
case $(own_start "$REC" head-successor) in
  *'"record: the run-open at '*) : ;;
  *) why="$why; model_src does not name the run-open it came from: $(own_start "$REC" head-successor)" ;;
esac
case $(sed -n 1p "$WORK/stub-rmodel2.args") in *"--model fixture-model"*) : ;; *) why="$why; the stub was not started on the inherited model: $(sed -n 1p "$WORK/stub-rmodel2.args")" ;; esac
need_absent "the caller ran the opener"
need_eq "$(viewer_calls)" "1" "without --viewer-opened the start opens its window (the control)"
verdict "head-start events (register 2026-09-23 12:5x, must not fire): a starter given no --model starts its head on the record's structured model, model_src naming the run-open it came from, beside effort max — never on the harness default — and without --viewer-opened the starter opens its own window"

fixture rmodel3 200
arm_resume rmodel3
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rmodel3 --handoff "$HO" --budget 3.50 --out "$WORK/starter/rmodel3-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +2s --tick-s 1 \
        --model sonnet --effort medium
need_rc 0
need_eq "$(mk count "$REC" head-resumed)" "1" "one in-place resume"
need_eq "$(own_start "$REC" head-resumed)" '"sonnet" "medium" "arg"' "the head-resumed event carries the resumed command line's model and effort"
verdict "head-start events (must fire): an in-place resume after a limit writes head-resumed with the model and effort its --resume command line carried"

# ---- G26 (register 2026-10-04 22:58, the owner's A4): the launch's effort survives a resume ------
# The planted case is a head launched at high with no flag on the next call; the controls are the
# flag, which still overrides, and a record that names none, where max stands.
fixture reff 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-reff","pid":999903,"model":"fixture-model","effort":"high"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run reff --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "effort high (effort_src: record: the head-successor at "
need_out "--effort high"
need_absent "--effort max"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run reff --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness" --effort low
need_rc 0
need_out "effort low (effort_src: arg)"
need_out "--effort low"
need_absent "--effort high"
RUNENV="PATH=$WORK/psnone:$PATH"
run resume-head --run reff --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "--effort high --effort-src"
need_absent "--effort max"
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run reff --handoff "$HO" --budget 3.50 --out "$WORK/starter/reff-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
case $(sed -n 1p "$WORK/stub-reff.args") in *"--effort high"*) : ;; *) why="$why; the stub did not start at the recorded effort: $(sed -n 1p "$WORK/stub-reff.args")" ;; esac
need_eq "$(own_start "$REC" head-successor | cut -d' ' -f2)" '"high"' "the new head-successor records the inherited effort"
need_eq "$(grep -c '"effort_src": "record: the head-successor at ' "$REC")" "1" "the new event's source names the record"
fixture reff2 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run reff2 --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "effort max (effort_src: default"
need_out "--effort max"
verdict "G26 (fails on old): successor, resume-head and the starter keep the effort recorded at launch, a flag overriding only when given, and max stands only where the record names none"

REFF3="$STORE/spawn-records/reff3.jsonl"; rm -f "$REFF3"
HOEFF="$WORK/handoffs/reff3-handoff.md"; mk handoff "$HOEFF" >/dev/null
run run-open --run reff3 --session sid-reff3 --head "fixture head" --regime multi --regime-src owner \
    --handoff "$HOEFF" --detail "effort on the record" --pid 4243 --envelope-usd 200 --model opus --effort xhigh
need_rc 0
need_eq "$(mk field "$REFF3" run-open effort)" "xhigh" "run-open's structured effort"
mk append "$REFF3" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run reff3 --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "effort xhigh (effort_src: record: the run-open at "
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run reff3 --session sid-reff3b --head "successor head" --detail "resumed" --pid 5151 --effort medium
need_rc 0
need_eq "$(mk field "$REFF3" run-resume effort)" "medium" "run-resume's structured effort"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run reff3 --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "effort medium (effort_src: record: the run-resume at "
verdict "G26 (fails on old): run-open and run-resume record --effort as a structured field, and the newest head start's effort is the one a successor inherits"

fixture rvwflag 200
viewer_use vflag
sh -c 'exit 0' &
FLAGDEAD=$!
wait "$FLAGDEAD" || :
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run rvwflag --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --predecessor-pid "$FLAGDEAD" --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
FLOG=$(sed -n 's/.*detached (log \([^)]*\)).*/\1/p' "$WORK/out" | head -1)
wait_field "$REC" head-successor session_id sid-by-the-head 40
sleep 1
need_eq "$(grep -c 'viewer: the caller ran the opener before the detach' "$FLOG")" "1" "the detached starter was handed --viewer-opened"
need_eq "$(viewer_calls)" "1" "one window in all: the caller's, none from the starter"
verdict "viewer before the detach (must fire): a real detached successor start opens the window in the caller, the starter it detaches is handed --viewer-opened and says so in its log, and no second window is opened"

# Register entry 2026-09-10 17:43, the table's half: a plan-usage (Codex) lane is counted in words
# and never priced, on the over-cap row and on its own lane row, while a Claude lane beside it is.
fixture rplan 200
mk append "$REC" '{"event":"lane-open","lane":"CX","harness":"codex","model":"gpt-fixture-1","class":"critic"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"CX","harness":"codex","exit_class":"error","total_cost_usd":null,"report_words":1000}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"OP","model":"claude-fixture-opus-1","class":"builder"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"OP","exit_class":"completed","total_cost_usd":1.0,"report_words":1000}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"1","to":"2","idle_min":0.0,"denials":0,"over_cap_reports":2,"respawn_cost_usd":0.0,"rewrites":0}' >/dev/null
WTP="$WORK/rplan-table.md"
run waste-table --run rplan --out "$WTP"
need_rc 0
need_eq "$(grep -c 'CX 200 words over (plan usage: a Codex lane is counted in words, never priced)' "$WTP")" "1" "the Codex lane's cut tail is counted, never priced"
need_eq "$(grep -c 'OP 200 words over = \$0.0052 (opus output \$20.00/MTok)' "$WTP")" "1" "the Claude lane's tail is priced (the control)"
need_eq "$(grep -c 'lost lane · CX · exit class error | plan usage (a Codex lane): counted, never priced · lane-closed.total_cost_usd null' "$WTP")" "1" "the Codex lane's row is never metered or unmeasured"
need_eq "$(grep -c 'matches no price family' "$WTP")" "0" "no Codex lane reads as an unknown price family"
verdict "plan-usage lanes in the table (register 2026-09-10 17:43): a Codex lane's over-cap tail and lost-lane row say counted, never priced, beside a Claude lane whose tail is priced at its model's rate, and neither reads as an unknown price family"

# -------------------------------------------------------------- held lanes -----
# The record is the whole state: a `hold` event opens it, the supervisor's tick services it
# through the lane's OWN wrapper (stubbed below: AIMYTH_BEAT_WRAPPER_DIR names a directory whose
# lane.py and codex-lane.py record their argv and write the hold-beat a real wrapper writes, or
# fail as the leg asks), and a `hold-ended` closes it. The clock is the record's own: a lane whose
# last call is 51 minutes old is due under the real HOLD_BEAT_S, one 5 minutes old is not, so no
# leg shortens the interval. Every clean leg has its must-fire twin beside it.
BEATWRAP="$WORK/beatwrap"; mkdir -p "$BEATWRAP"
cat > "$BEATWRAP/lane.py" <<'BEATSTUB'
"""The stub wrapper for the held-lane legs: records its argv (one line per call, keyed by the run)
and writes the hold-beat a real wrapper writes. AIMYTH_BEAT_STUB_FAIL_LANES names lanes whose
beat is refused (exit 2, no record line); AIMYTH_BEAT_STUB_SILENT_LANES lanes whose call exits 0
having written nothing. The harness is read from this file's own name."""
import json, os, sys, time
argv = sys.argv[1:]
lane = argv[argv.index("--lane") + 1]
run = argv[argv.index("--run") + 1]
with open(os.path.join(os.environ["SUITE_WORK"], "beat-%s.args" % run), "a") as handle:
    handle.write(os.path.basename(sys.argv[0]) + " " + " ".join(argv) + "\n")
if lane in os.environ.get("AIMYTH_BEAT_STUB_FAIL_LANES", "").split(","):
    sys.stderr.write("stub wrapper: PROBE FAILED: the beat is refused for this leg\n")
    sys.exit(2)
if lane in os.environ.get("AIMYTH_BEAT_STUB_SILENT_LANES", "").split(","):
    sys.exit(0)
harness = "codex" if "codex" in os.path.basename(sys.argv[0]) else "claude"
stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
line = {"ts": stamp, "run": run, "lane": lane, "event": "hold-beat",
        "harness": harness, "ok": True, "by": os.environ.get("AIMYTH_BEAT_BY", "hand"),
        "usage": {"input_tokens": 5, "output_tokens": 1, "cache_read_input_tokens": 90000,
                  "cache_creation_input_tokens": 0},
        "total_cost_usd": 0.03 if harness == "claude" else None, "config_match": True, "stub": True}
record = os.path.join(os.environ["SUITE_STORE"], "spawn-records", run + ".jsonl")
with open(record, "a") as handle:
    handle.write(json.dumps(line) + "\n")
    # AIMYTH_BEAT_STUB_RELEASES=A:B — while lane A's beat runs, a release of lane B lands on the
    # record (another writer inside the supervisor's pass), as `handsoff.py release` writes it
    for pair in os.environ.get("AIMYTH_BEAT_STUB_RELEASES", "").split(","):
        if ":" in pair and pair.split(":")[0] == lane:
            handle.write(json.dumps({"ts": stamp, "run": run, "lane": pair.split(":")[1],
                                     "event": "hold-ended", "reason": "released", "by": "release",
                                     "stub": True}) + "\n")
    # AIMYTH_BEAT_STUB_RESUMES=A:B — while lane A's beat runs, a REAL resume of lane B lands, as
    # lane.py writes it: B is running again from that line on, and no beat may follow (critic F3)
    for pair in os.environ.get("AIMYTH_BEAT_STUB_RESUMES", "").split(","):
        if ":" in pair and pair.split(":")[0] == lane:
            handle.write(json.dumps({"ts": stamp, "run": run, "lane": pair.split(":")[1],
                                     "event": "lane-resumed", "session_id": "sid-resumed",
                                     "stub": True}) + "\n")
print(json.dumps({"summary": "stub beat ok", "beat": line}))
BEATSTUB
cp "$BEATWRAP/lane.py" "$BEATWRAP/codex-lane.py"

# The fixture lanes: `hold_lane REC RUN NAME KIND CLOSED_AGO_S [EXIT] [LAST_CALL_AGO_S] [notranscript]`
# appends a lane's open, spawn (or Codex session) and close, stamped in the past; a Claude lane
# gets a transcript whose last assistant record carries the last-call stamp (the harness's own
# UTC `Z` shape), a Codex lane an events log whose mtime is that stamp.
HF="$WORK/holdfix.py"
cat > "$HF" <<'HOLDFIX'
import json, os, sys, time
rec, run, name, kind, closed_ago = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
exit_class = sys.argv[6] if len(sys.argv) > 6 else "completed"
last_ago = float(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7] != "-" else closed_ago + 5
transcript = not (len(sys.argv) > 8 and sys.argv[8] == "notranscript")
now = time.time()
work, projects = os.environ["SUITE_WORK"], os.environ["AIMYTH_PROJECTS_DIR"]


def stamp(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))


def utc(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))


def add(ev):
    with open(rec, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(ev, run=run)) + "\n")


if kind == "codex":
    sid = "01a0-%s-%s" % (run, name)
    log = os.path.join(work, "events-%s-%s.log" % (run, name))
    with open(log, "w", encoding="utf-8") as handle:
        handle.write('{"type":"turn.completed","usage":{"input_tokens":1}}\n')
    os.utime(log, (now - last_ago, now - last_ago))
    add({"ts": stamp(now - closed_ago - 600), "event": "lane-open", "lane": name, "harness": "codex",
         "class": "critic", "model": "gpt-fixture-1", "effort": "max", "events": log, "cwd": work})
    add({"ts": stamp(now - closed_ago - 599), "event": "lane-session", "lane": name, "harness": "codex",
         "session_id": sid, "pid": 1})
    add({"ts": stamp(now - closed_ago), "event": "lane-closed", "lane": name, "harness": "codex",
         "session_id": sid, "exit_class": exit_class, "total_cost_usd": None})
else:
    sid = "sid-%s-%s" % (run, name)
    tdir = os.path.join(projects, "held-lanes")
    os.makedirs(tdir, exist_ok=True)
    path = os.path.join(tdir, sid + ".jsonl")
    if transcript:
        with open(path, "w", encoding="utf-8") as handle:
            for t in (now - last_ago - 60, now - last_ago):
                handle.write(json.dumps({"type": "assistant", "timestamp": utc(t), "message": {
                    "role": "assistant", "model": "claude-fixture-1", "usage": {"input_tokens": 10}}}) + "\n")
    add({"ts": stamp(now - closed_ago - 600), "event": "lane-open", "lane": name, "class": "builder",
         "model": "fable", "effort": "max", "session_id": sid, "cwd": work, "projects_root": projects})
    add({"ts": stamp(now - closed_ago - 599), "event": "lane-spawned", "lane": name, "session_id": sid, "pid": 1})
    add({"ts": stamp(now - closed_ago), "event": "lane-closed", "lane": name, "session_id": sid,
         "exit_class": exit_class, "transcript": path if transcript else None, "total_cost_usd": 1.0})
print(sid)
HOLDFIX
hold_lane() { "$PY" "$HF" "$@" >/dev/null; }
tier_close() { # $1 record, $2 lane, $3 tier JSON list: the tier the lane's close recorded
  "$PY" - "$1" "$2" "$3" <<'TIERFIX'
import json, sys
path, lane, tier = sys.argv[1:4]
rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
for row in rows:
    if row.get("lane") == lane and row.get("event") == "lane-closed":
        row["cache_write_tier"] = json.loads(tier)
with open(path, "w", encoding="utf-8") as handle:
    for row in rows:
        handle.write(json.dumps(row) + "\n")
TIERFIX
}
past() { "$PY" -c 'import sys, time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - float(sys.argv[1]))))' "$1"; }
lc() { # $1 record, $2 lane, $3 kind -> the count of that lane's events of the kind
  "$PY" -c 'import json, sys
n = sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l).get("lane") == sys.argv[2] and json.loads(l).get("event") == sys.argv[3])
print(n)' "$1" "$2" "$3"
}
lf() { # $1 record, $2 lane, $3 kind, $4 key -> the key of the LAST such event, as JSON
  "$PY" -c 'import json, sys
evs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
found = [e for e in evs if e.get("lane") == sys.argv[2] and e.get("event") == sys.argv[3]]
print(json.dumps(found[-1].get(sys.argv[4])) if found else "<none>")' "$1" "$2" "$3" "$4"
}

# H1: a hold on a Claude lane whose transcript's last call is 51 minutes old, then the same hold
# again (must fire: already held, nothing written).
# The decisions-channel legs earlier in this suite use the same run name and CLOSE that run, which
# leaves a supervisor stop marker and a heartbeat marker on disk; `fixture` resets the record but
# not the markers, and from 2026-09-17 a stop marker stops the hold service (review finding 1),
# so the held-lane block starts from no marker. The premise is the run's, not this fold's.
fixture rhold 200
rm -f "$STORE/spawn-records/rhold-supervisor.stop" "$STORE/spawn-records/rhold-heartbeat.stop"
hold_lane "$REC" rhold LA claude 3060
run hold --run rhold --lane LA
need_rc 0
need_out "hold: rhold/LA held · claude lane · cap 1 beat(s)"
need_eq "$(lc "$REC" LA hold)" "1" "one hold event"
need_eq "$(lf "$REC" LA hold harness)" '"claude"' "harness"
need_eq "$(lf "$REC" LA hold cap)" "1" "the default cap"
need_eq "$(lf "$REC" LA hold beat_after_s)" "3000" "the interval recorded on the hold"
case $(lf "$REC" LA hold last_call_src) in '"transcript last assistant record '*) : ;; *) why="$why; last_call_src is not the transcript: $(lf "$REC" LA hold last_call_src)" ;; esac
LAGE=$(lf "$REC" LA hold last_call_age_s); [ "$LAGE" -ge 3060 ] && [ "$LAGE" -le 3120 ] || why="$why; last_call_age_s $LAGE outside 3060..3120"
run hold --run rhold --lane LA
need_rc 2
need_out "already held"
need_lines
need_eq "$(lc "$REC" LA hold)" "1" "the second hold wrote nothing"
verdict "held lanes: hold records a Claude lane's hold with the transcript's last assistant record as its last call, the default cap and the interval; a second hold on it is refused (must fire), nothing written"

# H2: a Codex lane's last call: the session file's last event under CODEX_HOME when one exists,
# else the wrapper's events log mtime (both legs on one run; the missing-session-file case is the
# control for the session-file reading).
hold_lane "$REC" rhold LC codex 3060
run hold --run rhold --lane LC
need_rc 0
case $(lf "$REC" LC hold last_call_src) in '"codex events log mtime '*) : ;; *) why="$why; last_call_src is not the events log: $(lf "$REC" LC hold last_call_src)" ;; esac
need_eq "$(lf "$REC" LC hold harness)" '"codex"' "harness"
hold_lane "$REC" rhold LC2 codex 3060
CXH="$WORK/codexhome"; mkdir -p "$CXH/sessions/2026/09/17"
printf '%s\n' '{"timestamp":"'"$(past 3120 | sed 's/+0100$/+01:00/;s/+0000$/Z/')"'","type":"session_meta"}' \
  '{"timestamp":"'"$(past 3090 | sed 's/+0100$/+01:00/;s/+0000$/Z/')"'","type":"response_item"}' \
  > "$CXH/sessions/2026/09/17/rollout-2026-09-17T00-00-00-01a0-rhold-LC2.jsonl"
RUNENV="CODEX_HOME=$CXH"
run hold --run rhold --lane LC2
need_rc 0
case $(lf "$REC" LC2 hold last_call_src) in '"codex session file (timestamp) '*) : ;; *) why="$why; last_call_src is not the session file: $(lf "$REC" LC2 hold last_call_src)" ;; esac
LAGE=$(lf "$REC" LC2 hold last_call_age_s); [ "$LAGE" -ge 3090 ] && [ "$LAGE" -le 3150 ] || why="$why; the session file's last event was not the reference: age $LAGE"
verdict "held lanes: a Codex lane's last call is its session file's last event under CODEX_HOME, else the wrapper's events log mtime (the control on the same run)"

# H3: the premise cases, each exit 2 with nothing written: an unknown lane, no record, a plain
# record, a closed run, a lane still running, a limit close, a lapsed window, a cap under 1, a
# renew with no hold, a dry run.
HOLDS_BEFORE=$(mk count "$REC" hold)
run hold --run rhold --lane NOPE
need_rc 2; need_out "unknown"; need_lines
run hold --run nosuchrun --lane LA
need_rc 2; need_out "no run record"; need_lines
plain_fixture rholdplain
run hold --run rholdplain --lane L1
need_rc 2; need_out "no run-open event"; need_out "lane.py resume --beat"; need_lines
REC="$STORE/spawn-records/rhold.jsonl"
hold_lane "$REC" rhold LR claude 60
mk append "$REC" '{"event":"lane-resumed","lane":"LR","session_id":"sid-rhold-LR"}' >/dev/null
run hold --run rhold --lane LR
need_rc 2; need_out "no lane-closed after its latest start"; need_lines
hold_lane "$REC" rhold LL claude 600 limit
run hold --run rhold --lane LL
need_rc 2; need_out "closed limit"; need_lines
hold_lane "$REC" rhold LO claude 7200
run hold --run rhold --lane LO
need_rc 2; need_out "past the 55-minute window"; need_lines
hold_lane "$REC" rhold LF claude 300
run hold --run rhold --lane LF --cap 0
need_rc 2; need_out "--cap takes 1 to 24"; need_lines
run hold --run rhold --lane LF --renew
need_rc 2; need_out "no open hold to renew"; need_lines
run hold --run rhold --lane LF --dry-run
need_rc 0; need_out "hold: dry run"
need_eq "$(mk count "$REC" hold)" "$HOLDS_BEFORE" "no refusal and no dry run wrote a hold"
fixture rholdclosed 200
hold_lane "$REC" rholdclosed LA claude 300
mk append "$REC" '{"event":"run-close","items":"1"}' >/dev/null
run hold --run rholdclosed --lane LA
need_rc 2; need_out "is closed"; need_lines
need_eq "$(mk count "$REC" hold)" "0" "nothing written on a closed run"
REC="$STORE/spawn-records/rhold.jsonl"
verdict "held lanes (premises, must fire): an unknown lane, a missing record, a plain record, a closed run, a running lane, a limit close, a lapsed window, a cap under 1, a renew with no hold and a dry run each write nothing"

# H4: release ends the hold (released, 0 beats); a second release is refused (must fire).
run release --run rhold --lane LA
need_rc 0
need_out "hold-ended: rhold/LA (released)"
need_eq "$(lc "$REC" LA hold-ended)" "1" "one hold-ended"
need_eq "$(lf "$REC" LA hold-ended reason)" '"released"' "the reason"
need_eq "$(lf "$REC" LA hold-ended beats)" "0" "no beats"
run release --run rhold --lane LA
need_rc 2; need_out "no open hold to release"; need_lines
need_eq "$(lc "$REC" LA hold-ended)" "1" "the second release wrote nothing"
verdict "held lanes: release writes hold-ended released with the beat count, and a second release is refused (must fire), nothing written"

# H5: the tick. Every hold below is written BEFORE the supervisor attaches (the re-attach premise),
# the head is a live sleep, and the stub wrappers stand in for lane.py and codex-lane.py:
#   LA  Claude, last call 51 min ago, held now              → one beat through lane.py, ok
#   LC  Codex, events log 51 min old, held now              → one beat through codex-lane.py, ok
#   LF  closed 5 min ago, held now                          → no beat (not due: the control)
#   LX  held 60 min ago, one beat 51 min ago, cap 1         → hold-ended cap, no beat
#   LY  as LX, then renewed with cap 2 one minute ago       → a second beat (the renew's fresh count)
#   LZ  Claude, due, the stub refuses                        → one failed hold-beat by the supervisor, never a second
#   LW  held 60 min ago, resumed and closed limit after it   → hold-ended lane-closed, no beat
#   LV  held 60 min ago, resumed and still running           → nothing (no second process on one session)
run hold --run rhold --lane LA
need_rc 0
run hold --run rhold --lane LF
need_rc 0
for L in LX LY LZ LW LV; do hold_lane "$REC" rhold "$L" claude 3660; done
for L in LX LY; do
  mk append "$REC" "{\"event\":\"hold\",\"lane\":\"$L\",\"cap\":1,\"harness\":\"claude\",\"beat_after_s\":3000,\"ts\":\"$(past 3600)\"}" >/dev/null
  mk append "$REC" "{\"event\":\"hold-beat\",\"lane\":\"$L\",\"harness\":\"claude\",\"ok\":true,\"by\":\"supervisor\",\"ts\":\"$(past 3060)\"}" >/dev/null
done
mk append "$REC" "{\"event\":\"hold\",\"lane\":\"LY\",\"cap\":2,\"renew\":true,\"harness\":\"claude\",\"beat_after_s\":3000,\"ts\":\"$(past 60)\"}" >/dev/null
mk append "$REC" "{\"event\":\"hold\",\"lane\":\"LZ\",\"cap\":1,\"harness\":\"claude\",\"beat_after_s\":3000,\"ts\":\"$(past 600)\"}" >/dev/null
mk append "$REC" "{\"event\":\"hold\",\"lane\":\"LW\",\"cap\":1,\"harness\":\"claude\",\"beat_after_s\":3000,\"ts\":\"$(past 3600)\"}" >/dev/null
mk append "$REC" "{\"event\":\"lane-resumed\",\"lane\":\"LW\",\"session_id\":\"sid-rhold-LW\",\"ts\":\"$(past 1800)\"}" >/dev/null
mk append "$REC" "{\"event\":\"lane-closed\",\"lane\":\"LW\",\"session_id\":\"sid-rhold-LW\",\"exit_class\":\"limit\",\"ts\":\"$(past 900)\"}" >/dev/null
mk append "$REC" "{\"event\":\"hold\",\"lane\":\"LV\",\"cap\":1,\"harness\":\"claude\",\"beat_after_s\":3000,\"ts\":\"$(past 3600)\"}" >/dev/null
mk append "$REC" "{\"event\":\"lane-resumed\",\"lane\":\"LV\",\"session_id\":\"sid-rhold-LV\",\"ts\":\"$(past 60)\"}" >/dev/null
rm -f "$WORK/beat-rhold.args"
sleep 120 & HEADPID=$!
(
  RCF=0
  env AIMYTH_BEAT_WRAPPER_DIR="$BEATWRAP" AIMYTH_BEAT_STUB_FAIL_LANES=LZ "$PY" -B "$H" _supervise \
      --run rhold --pid "$HEADPID" --session sid-rhold --out none --handoff "$HO" \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --wait-s 2 \
      >"$WORK/hold-sup.out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/hold-sup.rc"
) &
SUP=$!
i=0
while [ "$i" -lt 40 ]; do
  [ "$(lc "$REC" LZ hold-beat)" = "1" ] && [ "$(lc "$REC" LY hold-beat)" = "2" ] && [ "$(lc "$REC" LC hold-beat)" = "1" ] && break
  sleep 0.5; i=$((i + 1))
done
sleep 4   # at least three more ticks: a failed beat must not be retried
kill "$HEADPID" 2>"$WORK/kill.err" || :
wait "$HEADPID" 2>"$WORK/kill.err" || :
wait "$SUP"
cat "$WORK/hold-sup.out" > "$WORK/both"
need_eq "$(lc "$REC" LA hold-beat)" "1" "LA: one beat"
need_eq "$(lf "$REC" LA hold-beat ok)" "true" "LA: ok"
need_eq "$(lf "$REC" LA hold-beat by)" '"supervisor"' "LA: issued by the supervisor (the wrapper saw AIMYTH_BEAT_BY)"
grep -q '^lane.py resume --run rhold --lane LA --beat --format json$' "$WORK/beat-rhold.args" || why="$why; LA's beat did not go through lane.py resume --beat: $(cat "$WORK/beat-rhold.args" 2>/dev/null | tr '\n' '|')"
grep -q '^codex-lane.py resume --run rhold --lane LC --beat --format json$' "$WORK/beat-rhold.args" || why="$why; LC's beat did not go through codex-lane.py resume --beat"
need_eq "$(lc "$REC" LC hold-beat)" "1" "LC: one beat"
need_eq "$(lc "$REC" LF hold-beat)" "0" "LF: not due, no beat (the control)"
case $(lf "$REC" LF hold-ended reason) in "<none>"|'"stood-down"') : ;; *) why="$why; LF: its hold ended for a reason a lane not yet due cannot have: $(lf "$REC" LF hold-ended reason)" ;; esac
need_eq "$(lc "$REC" LX hold-ended)" "1" "LX: the hold ended"
need_eq "$(lf "$REC" LX hold-ended reason)" '"cap"' "LX: at the cap"
need_eq "$(lf "$REC" LX hold-ended beats)" "1" "LX: one beat counted"
need_eq "$(lc "$REC" LX hold-beat)" "1" "LX: no beat past the cap"
need_eq "$(lc "$REC" LY hold-beat)" "2" "LY: the renew's fresh count allowed a second beat"
case $(lf "$REC" LY hold-ended reason) in "<none>"|'"stood-down"') : ;; *) why="$why; LY: the renewed hold ended at $(lf "$REC" LY hold-ended reason), not at the supervisor's stand-down" ;; esac
need_eq "$(lc "$REC" LZ hold-beat)" "1" "LZ: exactly one failed beat across the ticks"
need_eq "$(lf "$REC" LZ hold-beat ok)" "false" "LZ: ok false"
need_eq "$(lf "$REC" LZ hold-beat by)" '"supervisor"' "LZ: written by the supervisor"
need_eq "$(lf "$REC" LZ hold-beat process_exit)" "2" "LZ: the wrapper's exit recorded"
case $(lf "$REC" LZ hold-beat error) in *"the beat is refused for this leg"*) : ;; *) why="$why; LZ's error lacks the wrapper's stderr: $(lf "$REC" LZ hold-beat error)" ;; esac
need_eq "$(grep -c '^lane.py resume --run rhold --lane LZ --beat' "$WORK/beat-rhold.args")" "1" "LZ: the wrapper was called once, never retried"
need_eq "$(lc "$REC" LW hold-ended)" "1" "LW: the hold ended"
need_eq "$(lf "$REC" LW hold-ended reason)" '"lane-closed"' "LW: on the limit close after the hold"
need_eq "$(lc "$REC" LW hold-beat)" "0" "LW: no beat"
need_eq "$(lc "$REC" LV hold-beat)" "0" "LV: no beat while it runs again"
case $(lf "$REC" LV hold-ended reason) in "<none>"|'"stood-down"') : ;; *) why="$why; LV: the hold of a lane running again ended at $(lf "$REC" LV hold-ended reason)" ;; esac
need_eq "$(grep -c 'hold rhold/LA · beat 1/1 through lane.py' "$WORK/both")" "1" "the supervisor's log names LA's beat"
verdict "held lanes (the tick, on holds written before the attach): a due Claude lane and a due Codex lane each get one beat through their own wrapper, a lane not yet due none; the cap ends a hold when the next beat falls due, a renew's fresh count allows another; a refused beat is recorded once by the supervisor and never retried across three further ticks; a limit close after the hold ends it; a lane running again is left alone"

# H5b (must fire): a wrapper that exits 0 having written no hold-beat still leaves one line,
# ok false, so no attempt goes unrecorded.
fixture rholdq 200
hold_lane "$REC" rholdq LQ claude 3060
run hold --run rholdq --lane LQ
need_rc 0
rm -f "$WORK/beat-rholdq.args"
sleep 120 & HEADPID=$!
(
  RCF=0
  env AIMYTH_BEAT_WRAPPER_DIR="$BEATWRAP" AIMYTH_BEAT_STUB_SILENT_LANES=LQ "$PY" -B "$H" _supervise \
      --run rholdq --pid "$HEADPID" --session sid-rholdq --out none --handoff "$HO" \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --wait-s 2 \
      >"$WORK/hold-sup2.out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/hold-sup2.rc"
) &
SUP=$!
i=0
while [ "$i" -lt 40 ] && [ "$(lc "$REC" LQ hold-beat)" != "1" ]; do sleep 0.5; i=$((i + 1)); done
sleep 2
kill "$HEADPID" 2>"$WORK/kill.err" || :
wait "$HEADPID" 2>"$WORK/kill.err" || :
wait "$SUP"
need_eq "$(lc "$REC" LQ hold-beat)" "1" "one failed beat stands for the silent attempt"
need_eq "$(lf "$REC" LQ hold-beat ok)" "false" "ok false"
need_eq "$(lf "$REC" LQ hold-beat process_exit)" "0" "the wrapper's exit 0 recorded"
case $(lf "$REC" LQ hold-beat note) in *"recorded no hold-beat"*) : ;; *) why="$why; the note does not say the wrapper wrote nothing" ;; esac
verdict "held lanes (must fire): a wrapper that returns without a hold-beat still leaves exactly one failed hold-beat, and no second attempt follows within the interval"

# H5c: the last act before a beat is a re-read of the record. Two due lanes, RA then RB in the
# pass's lane order; while RA's beat runs, a release of RB lands on the record (the stub writes it).
# RB must get no beat in that pass (must fire); the control is the same pair with no release
# planted, where RB is beaten.
hold_pass() { # $1 run, $2 extra environment for the stub (may be empty)
  sleep 120 & HEADPID=$!
  (
    RCF=0
    env AIMYTH_BEAT_WRAPPER_DIR="$BEATWRAP" $2 "$PY" -B "$H" _supervise \
        --run "$1" --pid "$HEADPID" --session "sid-$1" --out none --handoff "$HO" \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --wait-s 2 \
        >"$WORK/hold-pass-$1.out" 2>&1 || RCF=$?
    printf '%s\n' "$RCF" > "$WORK/hold-pass-$1.rc"
  ) &
  SUP=$!
  i=0
  while [ "$i" -lt 40 ] && [ "$(lc "$REC" RA hold-beat)" != "1" ]; do sleep 0.5; i=$((i + 1)); done
  sleep 3   # further ticks: whatever the pass was going to do to RB has happened
  kill "$HEADPID" 2>"$WORK/kill.err" || :
  wait "$HEADPID" 2>"$WORK/kill.err" || :
  wait "$SUP"
}
fixture rholdr 200
hold_lane "$REC" rholdr RA claude 3060
hold_lane "$REC" rholdr RB claude 3060
run hold --run rholdr --lane RA; need_rc 0
run hold --run rholdr --lane RB; need_rc 0
hold_pass rholdr "AIMYTH_BEAT_STUB_RELEASES=RA:RB"
need_eq "$(lc "$REC" RA hold-beat)" "1" "RA: beaten"
need_eq "$(lc "$REC" RB hold-ended)" "1" "RB: the release landed during RA's beat"
need_eq "$(lc "$REC" RB hold-beat)" "0" "RB: no beat after its hold ended mid-pass"
fixture rholdr2 200
hold_lane "$REC" rholdr2 RA claude 3060
hold_lane "$REC" rholdr2 RB claude 3060
run hold --run rholdr2 --lane RA; need_rc 0
run hold --run rholdr2 --lane RB; need_rc 0
hold_pass rholdr2 ""
need_eq "$(lc "$REC" RA hold-beat)" "1" "control: RA beaten"
need_eq "$(lc "$REC" RB hold-beat)" "1" "control: RB beaten where no release lands"
verdict "held lanes (must fire): a release that lands on the record while an earlier lane's beat runs is seen by the re-read before the next beat, so the released lane is not beaten; with no release planted the same second lane is beaten (the control)"

# H6: run-close ends every open hold before the run-close, and the close event counts them.
fixture rholdc 200
hold_lane "$REC" rholdc LA claude 300
hold_lane "$REC" rholdc LB codex 300
run hold --run rholdc --lane LA; need_rc 0
run hold --run rholdc --lane LB --cap 3; need_rc 0
run close --run rholdc --meter-line "$CLOSE_METER" --items 1 --dry-run
need_rc 0
need_eq "$(mk count "$REC" hold-ended)" "0" "a dry run ends nothing"
run close --run rholdc --meter-line "$CLOSE_METER" --items 1
need_rc 0
need_eq "$(mk count "$REC" hold-ended)" "2" "both holds ended"
need_eq "$(lf "$REC" LA hold-ended reason)" '"run-close"' "LA's reason"
need_eq "$(lf "$REC" LB hold-ended reason)" '"run-close"' "LB's reason"
need_eq "$(lf "$REC" LB hold-ended cap)" "3" "LB's cap on its hold-ended"
need_eq "$(mk field "$REC" run-close holds_ended)" "2" "the run-close counts them"
"$PY" - "$REC" <<'ORDER' > "$WORK/hold-order.txt"
import json, sys
kinds = [json.loads(l)["event"] for l in open(sys.argv[1]) if l.strip()]
print("before" if kinds.index("run-close") > max(i for i, k in enumerate(kinds) if k == "hold-ended") else "after")
ORDER
need_eq "$(cat "$WORK/hold-order.txt")" "before" "the hold-ended lines precede the run-close"
run hold --run rholdc --lane LA
need_rc 2; need_out "is closed"
verdict "held lanes: close ends every open hold (reason run-close, each with its cap) before the run-close, counts them on the event, a dry run ends nothing, and no hold opens on the closed run"

# H6b (the re-base, 2026-09-17): `close` carries BOTH the afternoon's run-spend fields and the
# held lanes' holds_ended, since the two changes meet in one function. The close above is the
# subject: one run-close event answers for both behaviours.
need_eq "$(mk field "$REC" run-close holds_ended)" "2" "the held-lane field"
case $(mk field "$REC" run-close run_spend_src) in "<no key"*|"null"|"") why="$why; the run-close carries no run_spend_src: the afternoon's spend fields did not survive the re-base" ;; *) : ;; esac
need_eq "$(grep -c '^run spend: ' "$WORK/both")" "0" "the closed-run refusal above printed none (the control for the line below)"
fixture rholdcs 200
hold_lane "$REC" rholdcs LA claude 300
run hold --run rholdcs --lane LA; need_rc 0
run close --run rholdcs --meter-line "$CLOSE_METER" --items 1
need_rc 0
need_out "run spend: "
need_eq "$(mk field "$REC" run-close holds_ended)" "1" "the same close ended the hold"
case $(mk field "$REC" run-close run_spend_floor) in "<no key"*|"") why="$why; run_spend_floor missing from the run-close" ;; *) : ;; esac
verdict "the re-base (both behaviours in one function): one close writes the afternoon's run-spend fields and line AND ends every open hold, counting them on the run-close"

# H7: the two wrappers and the supervisor agree on the close classes a beat re-enters, and the
# help names the verbs and the supervisor's bound.
CONST=$("$PY" - "$H" "$LANE_PY" <<'CONSTS'
import importlib.util, sys
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
h, l = load("h_under_test", sys.argv[1]), load("l_under_test", sys.argv[2])
print("%s %s %d %d" % (h.HOLDABLE_EXITS == l.BEAT_EXITS, h.HOLD_ENDED_REASONS == ("released", "cap", "lane-closed", "run-close", "stood-down"), h.HOLD_BEAT_S, h.HOLD_CAP_DEFAULT))
CONSTS
)
need_eq "$CONST" "True True 3000 1" "HOLDABLE_EXITS equals lane.py's BEAT_EXITS; the five reasons; 50 min; cap 1"
run hold --help
need_rc 0; need_out "--renew"; need_out "--beat-after-s"
run release --help
need_rc 0
run _supervise --help
need_rc 0; need_out "--beat-timeout-s"
verdict "held lanes: handsoff.py and lane.py carry one tuple of beatable close classes, the five hold-ended reasons stand, the 50-minute interval and the cap of 1 are the constants, and the help names hold, release and --beat-timeout-s"

# H8 (critic F2): the supervisor's bound on a beat must sit ABOVE the wrapper's own, or
# subprocess.run kills the wrapper before the wrapper's own kill_group runs and the harness —
# started with start_new_session — survives on the lane's session, which is the
# two-processes-on-one-session fault. The constants carry the ordering and the grace.
BOUNDS=$("$PY" - "$H" "$LANE_PY" <<'BOUNDS_END'
import importlib.util, sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h, l = load("h_bounds", sys.argv[1]), load("l_bounds", sys.argv[2])
print("%s %s %s %d" % (h.HOLD_BEAT_WRAPPER_BOUND_S == l.BEAT_TIMEOUT_S,
                       h.HOLD_BEAT_TIMEOUT_S > l.BEAT_TIMEOUT_S,
                       h.HOLD_BEAT_TIMEOUT_S == l.BEAT_TIMEOUT_S + h.HOLD_BEAT_GRACE_S,
                       h.HOLD_BEAT_GRACE_S))
BOUNDS_END
) || BOUNDS="the constants could not be read"
need_eq "$BOUNDS" "True True True 120" "the supervisor's bound is the wrapper's plus the stated grace"
run _supervise --help
need_rc 0; need_out "plus a 120 s grace"
verdict "held lanes (critic F2): the supervisor's beat bound is lane.py's own wrapper bound plus a stated 120 s grace, never equal to it, and the help names the derivation"

# H8b: the two orderings, each against a wrapper that hangs with a grandchild of its own in a
# fresh session (what the real wrappers start). Inner bound below the outer: the wrapper kills its
# own group and records the failure, and nothing survives. Outer below the inner (the must-fire
# twin: the ordering the equal bounds gave): the supervisor times out, records the attempt itself,
# and the grandchild is still alive — the orphan the grace exists to prevent.
HANGWRAP="$WORK/hangwrap"; mkdir -p "$HANGWRAP"
cat > "$HANGWRAP/lane.py" <<'HANGSTUB'
"""A stub wrapper for the beat-timeout legs: it starts a grandchild in its OWN session, as the
real wrappers do, then waits STUB_INNER_S before killing that group and recording the failed
hold-beat its own bound would record. The leg sets the two bounds and reads what survived."""
import json, os, signal, subprocess, sys, time
argv = sys.argv[1:]
lane = argv[argv.index("--lane") + 1]
run = argv[argv.index("--run") + 1]
work = os.environ["SUITE_WORK"]
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                         start_new_session=True)
with open(os.path.join(work, "hang-%s.pid" % lane), "w") as handle:
    handle.write("%d\n" % child.pid)
time.sleep(float(os.environ.get("STUB_INNER_S", "3")))
try:
    os.killpg(os.getpgid(child.pid), signal.SIGKILL)
except OSError:
    pass
child.wait()
record = os.path.join(os.environ["SUITE_STORE"], "spawn-records", run + ".jsonl")
with open(record, "a") as handle:
    handle.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "run": run,
                             "lane": lane, "event": "hold-beat", "harness": "claude",
                             "ok": False, "by": os.environ.get("AIMYTH_BEAT_BY", "hand"),
                             "exit_class": "deadline", "timed_out": True,
                             "error": "the stub wrapper's own bound fired first",
                             "stub": True}) + "\n")
sys.exit(3)
HANGSTUB
cp "$HANGWRAP/lane.py" "$HANGWRAP/codex-lane.py"
hang_pass() { # $1 run, $2 inner bound, $3 the supervisor's outer bound
  sleep 120 & HEADPID=$!
  (
    RCF=0
    env AIMYTH_BEAT_WRAPPER_DIR="$HANGWRAP" STUB_INNER_S="$2" "$PY" -B "$H" _supervise \
        --run "$1" --pid "$HEADPID" --session "sid-$1" --out none --handoff "$HO" \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --wait-s 2 \
        --beat-timeout-s "$3" >"$WORK/hang-$1.out" 2>&1 || RCF=$?
    printf '%s\n' "$RCF" > "$WORK/hang-$1.rc"
  ) &
  SUP=$!
  i=0
  while [ "$i" -lt 60 ] && [ "$(lc "$REC" HG hold-beat)" != "1" ]; do sleep 0.5; i=$((i + 1)); done
  HGPID=$(cat "$WORK/hang-HG.pid" 2>/dev/null || printf '0')
  if kill -0 "$HGPID" 2>/dev/null; then HGALIVE=yes; else HGALIVE=no; fi
  kill "$HEADPID" 2>"$WORK/kill.err" || :
  wait "$HEADPID" 2>"$WORK/kill.err" || :
  wait "$SUP"
}
fixture rhang 200
hold_lane "$REC" rhang HG claude 3060
run hold --run rhang --lane HG; need_rc 0
rm -f "$WORK/hang-HG.pid"
hang_pass rhang 2 8
need_eq "$(lc "$REC" HG hold-beat)" "1" "one attempt recorded"
need_eq "$(lf "$REC" HG hold-beat timed_out)" "true" "the WRAPPER recorded the timeout, not the supervisor"
need_eq "$(lf "$REC" HG hold-beat stub)" "true" "the wrapper's own line"
need_eq "$HGALIVE" "no" "the wrapper killed its own grandchild: nothing survives on the lane's session"
fixture rhang2 200
hold_lane "$REC" rhang2 HG claude 3060
run hold --run rhang2 --lane HG; need_rc 0
rm -f "$WORK/hang-HG.pid"
hang_pass rhang2 9 1
need_eq "$(lc "$REC" HG hold-beat)" "1" "one attempt recorded"
need_eq "$(lf "$REC" HG hold-beat by)" '"supervisor"' "the SUPERVISOR recorded it: its bound fired first"
case $(lf "$REC" HG hold-beat error) in *"did not finish"*"stray process"*) : ;; *) why="$why; the supervisor's error does not name the stray process: $(lf "$REC" HG hold-beat error)" ;; esac
need_eq "$HGALIVE" "yes" "must fire: with the outer bound below the wrapper's own, the harness the wrapper started was still alive"
kill -9 "$(cat "$WORK/hang-HG.pid" 2>/dev/null || printf '0')" 2>/dev/null || :
verdict "held lanes (critic F2, must fire): with the supervisor's bound above the wrapper's the wrapper times out first, kills its own process group and records the beat, and no process survives; with it below, the supervisor records the attempt, says a stray process may be on the lane's session, and the grandchild is indeed still alive"

# H9 (critic F1): a record the hold service cannot read makes read_record call die(), which is
# sys.exit(2). Catch SystemExit as well as Exception. The same-run control verifies that ticks
# write nothing while the record cannot be read;
# fails, and once the record is readable again the same hold is beaten — the error path left it
# serviceable.
fixture rholdd 200
hold_lane "$REC" rholdd LD claude 3060
run hold --run rholdd --lane LD; need_rc 0
rm -f "$WORK/beat-rholdd.args"
sleep 120 & HEADPID=$!
(
  RCF=0
  env AIMYTH_BEAT_WRAPPER_DIR="$BEATWRAP" "$PY" -B "$H" _supervise \
      --run rholdd --pid "$HEADPID" --session sid-rholdd --out none --handoff "$HO" \
      --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --wait-s 2 \
      >"$WORK/hold-die.out" 2>&1 || RCF=$?
  printf '%s\n' "$RCF" > "$WORK/hold-die.rc"
) &
SUP=$!
i=0
while [ "$i" -lt 40 ] && [ "$(lc "$REC" LD hold-beat)" != "1" ]; do sleep 0.5; i=$((i + 1)); done
chmod 000 "$REC"
sleep 3
if kill -0 "$SUP" 2>/dev/null; then SUPALIVE=yes; else SUPALIVE=no; fi
chmod 644 "$REC"
sleep 2
kill "$HEADPID" 2>"$WORK/kill.err" || :
wait "$HEADPID" 2>"$WORK/kill.err" || :
wait "$SUP"
cp "$WORK/hold-die.out" "$WORK/both"
need_eq "$SUPALIVE" "yes" "the supervisor outlived the dying reader"
need_eq "$(cat "$WORK/hold-die.rc")" "0" "and ended on the head's exit, exit 0, not on the die"
need_out "hold service raised SystemExit"
need_eq "$(lc "$REC" LD hold-beat)" "1" "the failed ticks wrote nothing: one beat in all (the control)"
case $(lf "$REC" LD hold-ended reason) in "<none>"|'"stood-down"') : ;; *) why="$why; the raised error ended the hold: $(lf "$REC" LD hold-ended reason)" ;; esac
verdict "held lanes (critic F1, must fire): a record the hold service cannot read raises SystemExit inside the service, which is caught and logged — the supervisor keeps waiting on its head and exits 0 at the head's stop — and the failed ticks write nothing, the hold staying open and serviceable (the control: its one beat before the fault)"

# H10 (critic F3): the re-read before a beat re-checks the LANE, not only its hold. While RA's
# beat runs, a real resume of RB lands; RB must get no beat and no failed hold-beat (a refusal
# recorded as a failure would end its hold at the cap having beaten nothing). Control: the same
# pair with no resume planted, where RB is beaten.
fixture rholdre 200
hold_lane "$REC" rholdre RA claude 3060
hold_lane "$REC" rholdre RB claude 3060
run hold --run rholdre --lane RA; need_rc 0
run hold --run rholdre --lane RB; need_rc 0
hold_pass rholdre "AIMYTH_BEAT_STUB_RESUMES=RA:RB"
need_eq "$(lc "$REC" RA hold-beat)" "1" "RA: beaten"
need_eq "$(lc "$REC" RB lane-resumed)" "1" "RB: the real resume landed during RA's beat"
need_eq "$(lc "$REC" RB hold-beat)" "0" "RB: no beat while it runs again"
case $(lf "$REC" RB hold-ended reason) in "<none>"|'"stood-down"') : ;; *) why="$why; RB: its hold ended at $(lf "$REC" RB hold-ended reason), so the resumed lane was marked by the beat path" ;; esac
need_eq "$(grep -c 'the lane started again during this pass' "$WORK/hold-pass-rholdre.out")" "1" "the supervisor says why"
verdict "held lanes (critic F3, must fire): a real resume that lands while an earlier lane's beat runs is seen by the re-read, so the resumed lane gets no beat and no failed hold-beat, and its hold stands (control: H5c's pair, beaten where nothing lands)"

# H11 (critic F5a): the window a hold is measured against counts a SUCCESSFUL beat only. A close
# 70 min ago with a FAILED beat 20 min ago is cold — nothing kept it warm — and --renew is
# refused; the control is the same lane with a SUCCESSFUL beat 20 min ago, which is warm.
fixture rholdw 200
hold_lane "$REC" rholdw WF claude 4200
mk append "$REC" "{\"event\":\"hold\",\"lane\":\"WF\",\"cap\":1,\"harness\":\"claude\",\"beat_after_s\":3000,\"ts\":\"$(past 4100)\"}" >/dev/null
mk append "$REC" "{\"event\":\"hold-beat\",\"lane\":\"WF\",\"harness\":\"claude\",\"ok\":false,\"by\":\"supervisor\",\"ts\":\"$(past 1200)\"}" >/dev/null
HOLDS_BEFORE=$(mk count "$REC" hold)
run hold --run rholdw --lane WF --renew
need_rc 2; need_out "past the 55-minute window"; need_lines
need_eq "$(mk count "$REC" hold)" "$HOLDS_BEFORE" "nothing written on the failed beat's reference"
hold_lane "$REC" rholdw WO claude 4200
mk append "$REC" "{\"event\":\"hold\",\"lane\":\"WO\",\"cap\":1,\"harness\":\"claude\",\"beat_after_s\":3000,\"ts\":\"$(past 4100)\"}" >/dev/null
mk append "$REC" "{\"event\":\"hold-beat\",\"lane\":\"WO\",\"harness\":\"claude\",\"ok\":true,\"by\":\"supervisor\",\"ts\":\"$(past 1200)\"}" >/dev/null
run hold --run rholdw --lane WO --renew
need_rc 0
case $(lf "$REC" WO hold last_call_src) in *"hold-beat ts (ok)"*) : ;; *) why="$why; the successful beat is not the reference: $(lf "$REC" WO hold last_call_src)" ;; esac
verdict "held lanes (critic F5a, must fire): a lane whose only beat FAILED is measured from its own last call, so a renew 70 minutes after the close is refused with nothing written, while the same lane with a successful beat 20 minutes ago renews on that beat's stamp (the control)"

# H12 (critic F5b): what services a hold is a supervisor, so that is what the guard tests. A run
# whose supervisor has stood down, or has been asked to stop, refuses a hold; the control is the
# same record with a supervisor attached after the stand-down, which is accepted and marked
# `ticking`; a record with no supervise event at all is still accepted (the re-attach premise,
# H5) with a warning naming it.
fixture rholds 200
hold_lane "$REC" rholds SA claude 3060
mk append "$REC" '{"event":"supervisor-stood-down","reason":"limit-stop","on_limit":"stop"}' >/dev/null
HOLDS_BEFORE=$(mk count "$REC" hold)
run hold --run rholds --lane SA
need_rc 2; need_out "no supervisor to service a hold"; need_out "supervisor-stood-down (limit-stop)"; need_lines
need_eq "$(mk count "$REC" hold)" "$HOLDS_BEFORE" "nothing written after a stand-down"
mk append "$REC" '{"event":"supervise","mode":"stop-requested","marker":"x"}' >/dev/null
run hold --run rholds --lane SA
need_rc 2; need_out "stop was requested"; need_lines
mk append "$REC" '{"event":"supervise","mode":"attached","pid":1,"supervisor_pid":2,"services_holds":true}' >/dev/null
run hold --run rholds --lane SA
need_rc 0
need_eq "$(lf "$REC" SA hold supervision)" '"ticking"' "the control: a hold-servicing supervisor is on the record"
fixture rholdu 200
hold_lane "$REC" rholdu SU claude 3060
run hold --run rholdu --lane SU
need_rc 0
need_eq "$(lf "$REC" SU hold supervision)" '"none"' "no supervise event yet: the re-attach case"
need_out "hold: warning"
need_out "no supervise event"
verdict "held lanes (critic F5b, must fire): a hold on a run whose supervisor stood down or was asked to stop is refused with nothing written, one attached afterwards is accepted and recorded ticking (the control), and a record with no supervise event yet is accepted with a warning (the re-attach premise)"

# H13 (critic F5c): the cache tier the lane's own close recorded is read, never assumed. A lane
# whose last call wrote the 5-minute tier is warned about at the 50-minute default; the control is
# the same fixture at the 1-hour tier, which warns about nothing.
fixture rholdt 200
hold_lane "$REC" rholdt TA claude 3060
tier_close "$REC" TA '["5m"]'
run hold --run rholdt --lane TA
need_rc 0
need_out "wrote the cache at tier 5m"
need_out "expect a cold re-send"
case $(lf "$REC" TA hold tier_warning) in *"5m"*) : ;; *) why="$why; the warning is not on the hold event: $(lf "$REC" TA hold tier_warning)" ;; esac
hold_lane "$REC" rholdt TB claude 3060
tier_close "$REC" TB '["1h"]'
run hold --run rholdt --lane TB
need_rc 0
need_eq "$(lf "$REC" TB hold tier_warning)" "null" "the control: a 1-hour tier warns about nothing"
need_eq "$(grep -c 'wrote the cache at tier' "$WORK/both")" "0" "and prints no tier warning"
verdict "held lanes (critic F5c, must fire): a hold on a lane whose close recorded the 5-minute cache tier is accepted with a warning that a 50-minute beat re-sends the whole context, recorded on the hold; a close at the 1-hour tier warns about nothing (the control)"

# H14 (critic F6): a stand-down ends every open hold. Without it the lane stays ◐ held with
# nobody ticking, since the stood-down supervisor is the only process that services holds.
fixture rholdsd 200
hold_lane "$REC" rholdsd SD claude 3060
run hold --run rholdsd --lane SD; need_rc 0
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=limit STUB_N=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 AIMYTH_BEAT_WRAPPER_DIR=$BEATWRAP"
rm -f "$WORK/beat-rholdsd.args"
starter --run rholdsd --handoff "$HO" --budget 3.50 --out "$WORK/starter/rholdsd-head-1.out" \
        --wait-s 5 --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_rc 0
need_out "stood down (limit-stop)"
# review finding 1, the first planted case: the head had already stopped when the tick came, so
# the hold gets NO beat — the order inside a tick is the head, the stop state, then the holds.
need_eq "$(lc "$REC" SD hold-beat)" "0" "a head that has stopped gains no further beat"
need_nofile "$WORK/beat-rholdsd.args"
need_eq "$(lc "$REC" SD hold-ended)" "1" "the hold ended at the stand-down"
need_eq "$(lf "$REC" SD hold-ended reason)" '"stood-down"' "the reason"
need_eq "$(lf "$REC" SD hold-ended by)" '"supervisor"' "by the supervisor"
need_eq "$(mk field "$REC" supervisor-stood-down holds_ended)" "1" "the stand-down counts the holds it ended"
HOLDS_OPEN=$("$PY" - "$H" "$REC" <<'OPENHOLDS'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("h_holds", sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
print(len(h.open_holds(h.read_record(sys.argv[2])[0])))
OPENHOLDS
)
need_eq "$HOLDS_OPEN" "0" "no hold is left open for a supervisor that has gone"
verdict "held lanes (critic F6 and review finding 1, must fire): a supervisor that stands down ends every open hold first (reason stood-down, counted on the stand-down event), so no lane is left reading held with nobody ticking, and the stopped head's due hold is never beaten on the way out"

# H15 (critic F8): --cap and --beat-after-s carry stated bounds. A cap of 100000 and an interval
# past the resume window are refused; the ceiling itself and the window itself are accepted (the
# controls).
fixture rholdb 200
hold_lane "$REC" rholdb BA claude 300
HOLDS_BEFORE=$(mk count "$REC" hold)
run hold --run rholdb --lane BA --cap 100000
need_rc 2; need_out "--cap takes 1 to 24"; need_lines
run hold --run rholdb --lane BA --beat-after-s 999999
need_rc 2; need_out "--beat-after-s takes 1 to 3300"; need_lines
run hold --run rholdb --lane BA --beat-after-s 0
need_rc 2; need_out "--beat-after-s takes 1 to 3300"; need_lines
need_eq "$(mk count "$REC" hold)" "$HOLDS_BEFORE" "no refusal wrote a hold"
run hold --run rholdb --lane BA --cap 24 --beat-after-s 3300
need_rc 0
need_eq "$(lf "$REC" BA hold cap)" "24" "the ceiling itself is accepted (the control)"
need_eq "$(lf "$REC" BA hold beat_after_s)" "3300" "as is the window itself"
run hold --help
need_rc 0; need_out "most 24"; need_out "1 to 3300"
verdict "held lanes (critic F8, must fire): --cap above the ceiling of 24 and --beat-after-s outside 1 s to the 3,300 s resume window are refused with nothing written, the ceiling and the window themselves are accepted, and the help states both bounds"

# H16 (the re-base, 2026-09-17; re-based again 2026-09-18 onto the launch check): the verb table is
# where verbs built apart meet — `run-spend`, the held lanes' `hold` and `release`, the launch
# check's `launch-check` and `open-console` — and a hand-resolved merge there is what drops a verb
# silently.
# TWO claims, because they fail apart: argparse registers a subparser, and `main`'s handlers dict
# dispatches it, so a verb can parse, print its help and still raise KeyError when it is run.
# Every verb of all three changes is parsed AND dispatched to its own command.
VERBS=""
for v in hold release run-spend launch-check open-console; do
  run "$v" --help
  [ "$RC" = 0 ] || VERBS="$VERBS $v(exit $RC)"
done
run --help
need_rc 0
for v in hold release run-spend launch-check open-console; do
  grep -q -- "$v" "$WORK/both" || VERBS="$VERBS $v(absent from the usage)"
done
# The dispatch itself, on a run that has no record: each verb must end in its OWN command's
# refusal, never in a KeyError from a verb the merge left out of the handlers dict.
for v in hold release run-spend launch-check; do
  case $v in
    hold|release) run "$v" --run rnoverb --lane VB ;;
    *) run "$v" --run rnoverb ;;
  esac
  [ "$RC" = 2 ] || VERBS="$VERBS $v(dispatch exit $RC)"
  grep -q 'no run record' "$WORK/both" || VERBS="$VERBS $v(not its own refusal)"
  if grep -q 'Traceback' "$WORK/both"; then VERBS="$VERBS $v(raised)"; fi
done
# open-console's own dispatch is its --check reading, which needs no record and writes nothing.
run open-console --run rnoverb --check
[ "$RC" = 1 ] || VERBS="$VERBS open-console(dispatch exit $RC)"
grep -q 'NO CONSOLE' "$WORK/both" || VERBS="$VERBS open-console(not its own line)"
if grep -q 'Traceback' "$WORK/both"; then VERBS="$VERBS open-console(raised)"; fi
need_eq "$VERBS" "" "every verb of all three changes is registered, named in the usage and dispatched"
verdict "the re-base (all three changes in the verb table): hold, release, run-spend, launch-check and open-console are registered subparsers AND registered handlers — each dispatches to its own command's refusal rather than raising — and all five are named in the top-level usage, so no change's verbs were lost in either merge"

# H17 (review finding 1): `service_holds` itself refuses to beat once the run has stopped — a
# requested supervisor stop (its marker or its `supervise` event), a run-close, or a stand-down —
# and a terminal stop ends the open holds instead of leaving them on the board. The service is
# called directly, with the stub wrappers standing in for lane.py and codex-lane.py, so each
# planted case is one pass over one record; the fourth run is the live, due control.
svc_pass() { # $1 run: one service_holds pass over that run's record
  env AIMYTH_BEAT_WRAPPER_DIR="$BEATWRAP" "$PY" - "$H" "$STORE/spawn-records/$1.jsonl" "$1" \
      >"$WORK/svc-$1.out" 2>&1 <<'SVCEOF'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("h_svc", sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class Args(object):
    pass


a = Args()
a.run = sys.argv[3]
a.tick_s = 1
a.beat_timeout_s = 20
h.service_holds(a, sys.argv[2])
SVCEOF
}
for R in svcstop svcclose svcdown svclive; do
  fixture "$R" 200
  hold_lane "$REC" "$R" SV claude 3060
  run hold --run "$R" --lane SV
  need_rc 0
done
REC="$STORE/spawn-records/svcstop.jsonl"
mk append "$REC" '{"event":"supervise","mode":"stop-requested","marker":"x"}' >/dev/null
REC="$STORE/spawn-records/svcclose.jsonl"
mk append "$REC" '{"event":"run-close","items":"1"}' >/dev/null
REC="$STORE/spawn-records/svcdown.jsonl"
mk append "$REC" '{"event":"supervisor-stood-down","reason":"stopped","on_limit":"stop"}' >/dev/null
for R in svcstop svcclose svcdown svclive; do svc_pass "$R"; done
for R in svcstop svcclose svcdown; do
  need_eq "$(lc "$STORE/spawn-records/$R.jsonl" SV hold-beat)" "0" "$R: no beat after the stop"
done
need_eq "$(lc "$STORE/spawn-records/svclive.jsonl" SV hold-beat)" "1" "the control: the live, due hold is beaten"
need_eq "$(lf "$STORE/spawn-records/svclive.jsonl" SV hold-beat ok)" "true" "the control's beat is ok"
need_eq "$(lc "$STORE/spawn-records/svcclose.jsonl" SV hold-ended)" "1" "a closed run's hold is ended, not left held"
need_eq "$(lf "$STORE/spawn-records/svcclose.jsonl" SV hold-ended reason)" '"stood-down"' "with the head's token"
need_eq "$(lc "$STORE/spawn-records/svcdown.jsonl" SV hold-ended)" "1" "a stood-down run's hold is ended"
need_eq "$(lc "$STORE/spawn-records/svcstop.jsonl" SV hold-ended)" "0" "a REQUESTED stop is not terminal: the hold stands (resume-head can clear the marker) and the line says why"
case $(cat "$WORK/svc-svcstop.out") in *"not serviced and not ended"*) : ;; *) why="$why; the requested stop's pass says nothing: $(head -2 "$WORK/svc-svcstop.out" | tr '\n' '|')" ;; esac
MARKRUN="$STORE/spawn-records/svclive.jsonl"
printf 'stop\n' > "$STORE/spawn-records/svclive-supervisor.stop"
svc_pass svclive
need_eq "$(lc "$MARKRUN" SV hold-beat)" "1" "the stop MARKER alone stops the service: no second beat"
rm -f "$STORE/spawn-records/svclive-supervisor.stop"
REC="$STORE/spawn-records/rhold.jsonl"
verdict "held lanes (review finding 1, must fire): a stop-requested event, a run-close, a stand-down and a stop marker each stop the hold service before any beat — the terminal two ending the open holds with reason stood-down, the requested stop leaving them with a line that says why — while the live, due control is beaten"

# H23 (review finding 1, 2026-09-18 — the timing H17 does NOT cover): the stop lands DURING the
# pass, between the opening check and the final re-read before the beat. That is the real window:
# an earlier lane's beat is bounded by HOLD_BEAT_TIMEOUT_S, so the opening check can be twelve
# minutes old when the beat is issued, and the critic's replay got one beat out of each of these
# three timings. The driver plants at exactly that point by wrapping beat_reference, which
# service_holds calls after the opening check and before the re-read.
svc_plant() { # $1 run, $2 the JSON line planted mid-pass, or the word marker for the stop file
  env AIMYTH_BEAT_WRAPPER_DIR="$BEATWRAP" "$PY" - "$H" "$STORE/spawn-records/$1.jsonl" "$1" "$2" \
      >"$WORK/svcp-$1.out" 2>&1 <<'SVCPEOF'
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("h_svcp", sys.argv[1])
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

record, run, plant = sys.argv[2], sys.argv[3], sys.argv[4]
original, planted = h.beat_reference, []


def planting(*args, **kwargs):
    if not planted:
        planted.append(True)
        if plant == "marker":
            with open(h.supervisor_stop_file(run), "w", encoding="utf-8") as handle:
                handle.write("stop\n")
        else:
            with open(record, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(dict(json.loads(plant), run=run, ts=h.now())) + "\n")
    return original(*args, **kwargs)


h.beat_reference = planting


class Args(object):
    pass


a = Args()
a.run, a.tick_s, a.beat_timeout_s = run, 1, 20
h.service_holds(a, record)
print("PLANTED %s" % bool(planted))
SVCPEOF
}
for R in svcpstop svcpclose svcpdown svcplive svcpmark; do
  fixture "$R" 200
  rm -f "$STORE/spawn-records/$R-supervisor.stop" "$STORE/spawn-records/$R-heartbeat.stop"
  hold_lane "$REC" "$R" SP claude 3060
  run hold --run "$R" --lane SP
  need_rc 0
done
svc_plant svcpstop '{"event":"supervise","mode":"stop-requested"}'
svc_plant svcpclose '{"event":"run-close","items":"1"}'
svc_plant svcpdown '{"event":"supervisor-stood-down","reason":"stopped","on_limit":"stop"}'
svc_plant svcpmark marker
svc_plant svcplive '{"event":"observation","phase":"","what":"a line that blocks no hold"}'
for R in svcpstop svcpclose svcpdown svcpmark svcplive; do
  need_eq "$(grep -c '^PLANTED True' "$WORK/svcp-$R.out")" "1" "$R: the plant landed inside the pass"
done
for R in svcpstop svcpclose svcpdown svcpmark; do
  need_eq "$(lc "$STORE/spawn-records/$R.jsonl" SP hold-beat)" "0" "$R: a stop that landed during the pass still stopped the beat"
done
need_eq "$(lc "$STORE/spawn-records/svcplive.jsonl" SP hold-beat)" "1" "the live-due control: a line that blocks nothing leaves the beat alone"
need_eq "$(lf "$STORE/spawn-records/svcplive.jsonl" SP hold-beat ok)" "true" "and that beat is ok"
need_eq "$(lf "$STORE/spawn-records/svcpclose.jsonl" SP hold-ended reason)" '"stood-down"' "the run closed mid-pass: its hold is ended, not left held"
need_eq "$(lf "$STORE/spawn-records/svcpdown.jsonl" SP hold-ended reason)" '"stood-down"' "the supervisor stood down mid-pass: its hold is ended"
need_eq "$(lc "$STORE/spawn-records/svcpstop.jsonl" SP hold-ended)" "0" "a REQUESTED stop mid-pass is not terminal: the hold stands for a supervisor that comes back"
need_eq "$(lc "$STORE/spawn-records/svcpmark.jsonl" SP hold-ended)" "0" "nor is the stop marker alone"
case $(cat "$WORK/svcp-svcpstop.out") in *"not serviced and not ended"*) : ;; *) why="$why; the requested stop's pass says nothing: $(head -2 "$WORK/svcp-svcpstop.out" | tr '\n' '|')" ;; esac
case $(lf "$STORE/spawn-records/svcpclose.jsonl" SP hold-ended note) in *"during the pass"*) : ;; *) why="$why; the hold-ended note does not say where the block was seen: $(lf "$STORE/spawn-records/svcpclose.jsonl" SP hold-ended note)" ;; esac
case $(lf "$STORE/spawn-records/svcclose.jsonl" SV hold-ended note) in *"before the pass"*) : ;; *) why="$why; H17's note no longer says the block was seen before the pass: $(lf "$STORE/spawn-records/svcclose.jsonl" SV hold-ended note)" ;; esac
rm -f "$STORE/spawn-records/svcpmark-supervisor.stop"
verdict "held lanes (review finding 1, 2026-09-18, must fire): a stop-requested event, a run-close, a stand-down and a stop marker that land DURING the pass — after the opening check, before the final re-read — each stop the beat, the terminal two ending the open holds with reason stood-down and a note saying the block was seen during the pass, the requested stop and the bare marker leaving them with a line that says why, while the live-due control is still beaten once"

# H24 (review finding 1, part iii): the stand-down on a REQUESTED stop ends every open hold, as
# the stand-down on a limit does (H14). Asserted rather than assumed: stand_down is called
# directly with the reason the marker-at-the-head's-exit path writes, and the board is then read
# from the same record — no lane may be left ◐ held once the supervisor has gone.
fixture rholdrq 200
rm -f "$STORE/spawn-records/rholdrq-supervisor.stop"
hold_lane "$REC" rholdrq RQ claude 3060
run hold --run rholdrq --lane RQ
need_rc 0
STANDRQ=$("$PY" - "$H" "$SKILL_DIR/watch.py" "$REC" <<'STANDEOF'
import importlib.util
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h, w = load("h_stand", sys.argv[1]), load("w_stand", sys.argv[2])
rc = h.stand_down(sys.argv[3], "rholdrq", "stopped",
                  "the stop marker was on disk when the head exited", "stop", "marker", 0)
events = h.read_record(sys.argv[3])[0]
run = w.Run("rholdrq", sys.argv[3], sys.argv[2])
lane = run.lanes.get("RQ")
print("STANDLEG %s %s %s %s %s"
      % (rc, len(h.open_holds(events)), lane.is_held(), run.hold_service, lane.hold_note))
STANDEOF
)
need_eq "$(printf '%s\n' "$STANDRQ" | grep '^STANDLEG' | head -1)" "STANDLEG 0 0 False stood-down hold ended (stood-down)" "the stand-down exits 0, leaves no open hold, and the board draws the lane closed with the reason"
need_eq "$(lc "$REC" RQ hold-ended)" "1" "one hold-ended"
need_eq "$(lf "$REC" RQ hold-ended by)" '"supervisor"' "by the supervisor"
need_eq "$(mk field "$REC" supervisor-stood-down holds_ended)" "1" "the stand-down event counts the hold it ended"
need_eq "$(mk field "$REC" supervisor-stood-down reason)" 'stopped' "on the requested stop's own reason, not a limit's"
verdict "held lanes (review finding 1 part iii, must fire): the supervisor's stand-down on a REQUESTED stop ends every open hold with reason stood-down and counts it on the supervisor-stood-down event, so the board reads the lane closed rather than held with nobody ticking"

# H18 (review finding 1): an abort is the supervisor's last act, so it ends every open hold. The
# record and the console are both read: the board must not draw the lane held afterwards.
fixture rabort 200
hold_lane "$REC" rabort AB claude 3060
run hold --run rabort --lane AB
need_rc 0
ABORT=$("$PY" - "$H" "$SKILL_DIR/watch.py" "$REC" <<'ABORTEOF'
import importlib.util
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h, w = load("h_abort", sys.argv[1]), load("w_abort", sys.argv[2])
rc = h.abort(sys.argv[3], "rabort", "budget", "the fixture's abort")
events = h.read_record(sys.argv[3])[0]
run = w.Run("rabort", sys.argv[3], sys.argv[2])
lane = run.lanes.get("AB")
print("ABORTLEG %s %s %s %s" % (rc, len(h.open_holds(events)), lane.is_held(), lane.hold_note))
ABORTEOF
)
need_eq "$(printf '%s\n' "$ABORT" | grep '^ABORTLEG' | head -1)" "ABORTLEG 1 0 False hold ended (stood-down)" "the abort exits 1, leaves no open hold, and the console draws the lane closed with the reason, never held"
need_eq "$(lc "$REC" AB hold-ended)" "1" "one hold-ended"
need_eq "$(lf "$REC" AB hold-ended reason)" '"stood-down"' "the reason"
need_eq "$(mk field "$REC" successor-aborted holds_ended)" "1" "the abort event counts the holds it ended"
verdict "held lanes (review finding 1, must fire): an abort ends every open hold with reason stood-down and counts them on the successor-aborted event, so the board draws the lane closed with its reason and no unqualified held state survives the supervisor"

# H19 (review finding 3): a beat's cost enters the run figure. The lane's beats are billable
# calls inside the pass it already closed, so they are added to its recorded figure, they open no
# pass of their own, and a beat with no cost makes the figure a floor and names the lane.
fixture rbeat 100
mk transcript sid-rbeat 1000 >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L","session_id":"sid-rbeat-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rbeat-l","exit_class":"completed","total_cost_usd":1.0}' >/dev/null
mk append "$REC" '{"event":"hold-beat","lane":"L","session_id":"sid-rbeat-l","ok":true,"n":1,"by":"supervisor","total_cost_usd":0.25}' >/dev/null
run run-spend --run rbeat --meter-line "$METER10"
need_rc 0
need_out "lane L: \$1.25 · 1 close cost(s) as recorded + 1 beat cost(s) (\$0.25)"
need_out "\$11.25 of \$100.00"
need_out "0 meter call(s)"
need_absent "at least"
need_absent "latest event hold-beat"
mk transcript sid-rbeat 100000 >/dev/null
run gate --run rbeat --to "item one" --meter-line "$METER10"
need_rc 0
need_eq "$(mk field "$REC" gate run_spend_usd)" "11.25" "the gate reads the same figure, the beat included"
verdict "held lanes (review finding 3, must fire): a \$1.00 close and a \$0.25 beat read \$1.25 for the lane and \$11.25 for the run, with no meter call, no floor and no pass opened by the beat, and the gate carries that figure"

# The twin: a beat with no cost is a gap — the lane's figure is a floor and it is named among the
# unmeasured, never silently understated.
fixture rbeatf 100
mk append "$REC" '{"event":"lane-open","lane":"L","session_id":"sid-rbeatf-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rbeatf-l","exit_class":"completed","total_cost_usd":1.0}' >/dev/null
mk append "$REC" '{"event":"hold-beat","lane":"L","session_id":"sid-rbeatf-l","ok":false,"n":1,"by":"supervisor"}' >/dev/null
run run-spend --run rbeatf --meter-line "$METER10"
need_rc 1
need_out "1 beat(s) without a cost"
need_out "unmetered: lane L"
need_out "at least \$11.00"
verdict "held lanes (review finding 3, must fire): a beat that recorded no cost makes the lane's figure a floor and names the lane among the unmeasured (exit 1), rather than reading as a complete \$11.00"

# The third case: a lane with an unpriced close, a priced beat and a meterable transcript is
# counted ONCE — the larger of the transcript and the recorded sum — so the beat neither doubles
# the figure nor adds a pass.
fixture rbeatm 100
mk pricedscript sid-rbeatm-l 2 lane-home-dir 1500000 >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L","session_id":"sid-rbeatm-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rbeatm-l","exit_class":"completed"}' >/dev/null
mk append "$REC" '{"event":"hold-beat","lane":"L","session_id":"sid-rbeatm-l","ok":true,"n":1,"by":"supervisor","total_cost_usd":0.25}' >/dev/null
run run-spend --run rbeatm --meter-line "$METER10"
need_rc 0
need_absent "at least"
need_out "lane L: \$$TWELVE · the larger of the transcript's \$$TWELVE"
need_out "and the recorded \$0.25 (0 close cost(s) as recorded + 1 beat cost(s) (\$0.25))"
need_absent "latest event hold-beat"
verdict "held lanes (review finding 3, must not fire): a lane whose close carries no cost and whose beat does takes the larger of its transcript and its recorded \$0.25 — counted once, with no pass opened by the beat"

# H20 (review finding 5): no shipped message advises the retired operational route — a shortened
# rehearsal interval or a re-attach of a live run's supervisor. The controls are the new wordings.
need_eq "$(grep -c 'a rehearsal shortens it' "$H")" "0" "the retired help clause is gone"
need_eq "$(grep -c 'shortens the interval for a rehearsal' "$H")" "0" "and its twin in the usage text"
need_eq "$(grep -c 'rehearsal of the next hands-off' "$H")" "1" "control: the help now says which rehearsal uses the default"
need_eq "$(grep -c 'an install is attended and between runs' "$H")" "1" "control: the diagnostic names the attended install"
run hold --help
need_rc 0
need_absent "a rehearsal shortens it"
need_out "uses the default"
fixture rword 200
hold_lane "$REC" rword WD claude 3060
mk append "$REC" '{"event":"supervisor-stood-down","reason":"stopped","on_limit":"stop"}' >/dev/null
run hold --run rword --lane WD
need_rc 2
need_out "hold a lane only under a run whose own supervisor is running"
need_out "opens the next run under that run's own fresh supervisor"
need_absent "supervise --run"
need_absent "--pid <head pid>"
verdict "held lanes (review finding 5, must fire): no shipped help or diagnostic advises a shortened rehearsal interval or a re-attach of a live run's supervisor — the refusal names the attended install and the next run's own fresh supervisor instead (controls: both new wordings present)"

# H25 (review finding 4): `hold-verdict` reads what each beat did to the cache from the record
# alone. Six planted beats — a hit, a rewrite and an open of each family — with the three exit
# codes; a record with no beat at all; a beat whose usage cannot be read; and the mirrored
# fraction asserted equal to the closing meter's own by a grep of both files.
beat_line() { # $1 record, $2 lane, $3 harness, $4 n, $5 usage JSON, $6 extra JSON fields
  mk append "$1" "{\"event\":\"hold-beat\",\"lane\":\"$2\",\"harness\":\"$3\",\"n\":$4,\"ok\":true,\"by\":\"supervisor\",\"config_match\":true,\"usage\":$5${6:+,$6}}" >/dev/null
}
fixture rhvhit 200
beat_line "$REC" HA claude 1 '{"cache_read_input_tokens":95000,"cache_creation_input_tokens":0,"input_tokens":1000}'
beat_line "$REC" HB codex 1 '{"input_tokens":96000,"cached_input_tokens":95000,"cache_write_input_tokens":0}'
run hold-verdict --run rhvhit
need_rc 0
need_out "HA · claude · beat 1 · ok true · config match · cached 95000 of 96000 (share 0.990) · uncached 1000 · hit"
need_out "HB · codex · beat 1 · ok true · config match · cached 95000 of 96000 (share 0.990) · uncached 1000 · hit"
need_out "hold-verdict: rhvhit · 2 beat(s) · hit 2 · rewrite 0 · open 0 · exit 0"
fixture rhvrw 200
beat_line "$REC" RA claude 1 '{"cache_read_input_tokens":1000,"cache_creation_input_tokens":95000,"input_tokens":1000}'
beat_line "$REC" RB codex 1 '{"input_tokens":96000,"cached_input_tokens":1000,"cache_write_input_tokens":0}'
run hold-verdict --run rhvrw
need_rc 1
need_eq "$(grep -c ' · rewrite$' "$WORK/both")" "2" "both families read rewrite"
need_out "hold-verdict: rhvrw · 2 beat(s) · hit 0 · rewrite 2 · open 0 · exit 1"
fixture rhvopen 200
beat_line "$REC" OA claude 1 '{"cache_read_input_tokens":50000,"cache_creation_input_tokens":40000,"input_tokens":6000}'
beat_line "$REC" OB codex 1 '{"input_tokens":96000,"cached_input_tokens":50000,"cache_write_input_tokens":0}'
run hold-verdict --run rhvopen
need_rc 2
need_eq "$(grep -c 'open (neither side reaches 0.90 of the whole input)' "$WORK/both")" "2" "both families read open with the figures"
need_out "hold-verdict: rhvopen · 2 beat(s) · hit 0 · rewrite 0 · open 2 · exit 2"
run hold-verdict --run rhvopen --lane OB
need_rc 2
need_eq "$(grep -c '^hold-verdict: O' "$WORK/both")" "1" "--lane reads one lane's beats"
run hold-verdict --run rhvhit --format json
need_rc 0
need_out '"verdict": "hit"'
need_out '"rewrite_fraction": 0.9'
need_out '"cached_share": 0.99'
fixture rhvnone 200
hold_lane "$REC" rhvnone NB claude 3060
run hold-verdict --run rhvnone
need_rc 2
need_out "hold-verdict: rhvnone · no hold-beat on the record: nothing to read"
need_eq "$(grep -c 'PROBE FAILED' "$WORK/err")" "0" "an empty reading is a reading, not a refusal"
fixture rhvbad 200
beat_line "$REC" BA claude 1 '{"cache_creation_input_tokens":0,"input_tokens":1000}'
beat_line "$REC" BB codex 2 '{"input_tokens":96000,"cached_input_tokens":99000}'
mk append "$REC" '{"event":"hold-beat","lane":"BC","harness":"claude","n":1,"ok":false,"by":"supervisor","error":"the wrapper recorded no hold-beat","usage":null}' >/dev/null
beat_line "$REC" BD codex 1 '{"input_tokens":96000,"cached_input_tokens":95000}' '"usage_complete":false'
run hold-verdict --run rhvbad
need_rc 2
need_out "open (unmeasured: usage.cache_read_input_tokens is None)"
need_out "open (unmeasured: usage.cached_input_tokens (99000) is larger than usage.input_tokens (96000))"
need_out "open (unmeasured: the beat did not succeed (the wrapper recorded no hold-beat))"
need_out "open (unmeasured: the wrapper recorded usage_complete false)"
need_out "hold-verdict: rhvbad · 4 beat(s) · hit 0 · rewrite 0 · open 4 · exit 2"
# the mirrored constant is the closing meter's own, asserted by reading BOTH files
FRACTIONS=$("$PY" - "$H" "$SKILL_DIR/fable-share.py" <<'FRACEOF'
import re
import sys

values = []
for path, name in ((sys.argv[1], "HOLD_VERDICT_FRACTION"), (sys.argv[2], "REWRITE_FRACTION")):
    with open(path, encoding="utf-8") as handle:
        found = re.findall(r"^%s = ([0-9.]+)$" % name, handle.read(), re.M)
    values.append(found[0] if len(found) == 1 else "x%d" % len(found))
print("%s %s %s" % (values[0], values[1], values[0] == values[1]))
FRACEOF
)
need_eq "$FRACTIONS" "0.9 0.9 True" "the mirrored fraction equals the closing meter's, each defined exactly once"
need_eq "$(grep -c 'REWRITE_FRACTION' "$H")" "1" "handsoff.py names the meter's constant once, in the citation beside its mirror"
need_eq "$(grep -c 'aggregate' "$H")" "1" "and names the meter's classifier function once, in that same citation"
verdict "held lanes (review finding 4, must fire): hold-verdict reads six planted beats — a hit, a rewrite and an open of each family — with the three exit codes and the figures behind each, --lane narrows it, --format json carries the same rows, a record with no beat prints one line and exits 2 without a refusal, four unreadable premises each read open (unmeasured: what is missing), and the mirrored fraction is asserted equal to the closing meter's REWRITE_FRACTION by reading both files"

# H21 (the re-base of 2026-09-18): item 162's launch check and the held-lane mechanism write into
# ONE record, so the check must read a hold, a beat and a hold-ended as none of its business: they
# are neither a head start nor a head exit. Both behaviours in one leg, with the same record
# read again after the head's pid has gone as the control.
seed_fixture rlchold 200
sleep 30 &
LCHOLD=$!
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lchold\",\"pid\":$LCHOLD,\"model\":\"fable\",\"effort\":\"max\"}" >/dev/null
hold_lane "$REC" rlchold HK claude 3060
run hold --run rlchold --lane HK
need_rc 0
mk append "$REC" '{"event":"hold-beat","lane":"HK","harness":"claude","ok":true,"n":1,"by":"supervisor"}' >/dev/null
mk append "$REC" '{"event":"hold-ended","lane":"HK","reason":"cap","by":"supervisor"}' >/dev/null
run launch-check --run rlchold --wait 0
need_rc 0
need_out "launch-check: rlchold STARTED · head-successor at"
need_absent "hold-beat"
need_absent "hold-ended"
kill "$LCHOLD"; wait "$LCHOLD" 2>/dev/null || :
run launch-check --run rlchold --wait 0
need_rc 1
need_out "launch-check: rlchold NOT STARTED"
verdict "the re-base (the launch check meeting the held lanes): a hold, a hold-beat and a hold-ended on the record are invisible to launch-check — the live head still reads STARTED and the outcome line names no hold — and the same record once that head's pid has gone reads NOT STARTED (the control)"

# H22 (the re-base of 2026-09-18): item 162 rebuilt the console opener (open_console,
# open_console_if_dark, console_alive and the one-window claim, on a lock since №163) and the held-lane fold draws
# the held row inside the window that opener starts, so the two meet at the command file. One leg
# for both: what the opener would run is the board, and that board, built from the same record,
# reads the lane held. The control is a released hold on the same record, which is not held.
fixture rmeet 200
rm -f "$STORE/spawn-records/rmeet-supervisor.stop" "$STORE/spawn-records/rmeet-heartbeat.stop"
hold_lane "$REC" rmeet MT claude 3060
hold_lane "$REC" rmeet MR claude 3060
run hold --run rmeet --lane MT
need_rc 0
run hold --run rmeet --lane MR
need_rc 0
run release --run rmeet --lane MR
need_rc 0
MEET=$("$PY" - "$H" "$SKILL_DIR/watch.py" "$REC" <<'MEETEOF'
import importlib.util
import os
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h, w = load("h_meet", sys.argv[1]), load("w_meet", sys.argv[2])
text = h.console_command_text("rmeet")
claim = h.console_lock_path("rmeet")
run = w.Run("rmeet", sys.argv[3], sys.argv[2])
print("MEETCMD %s" % ("watch --run rmeet" in text))
print("MEETCLAIM %s" % (claim.endswith("rmeet-console.lock")
                        and os.path.dirname(claim) == os.path.dirname(h.console_command_path("rmeet"))))
print("MEETHELD %s %s" % (run.lanes["MT"].is_held(), run.lanes["MR"].is_held()))
MEETEOF
)
need_eq "$(printf '%s\n' "$MEET" | grep '^MEETCMD')" "MEETCMD True" "the opener's command file runs the board for this run"
need_eq "$(printf '%s\n' "$MEET" | grep '^MEETCLAIM')" "MEETCLAIM True" "the one-window claim's lock sits beside that command file"
need_eq "$(printf '%s\n' "$MEET" | grep '^MEETHELD')" "MEETHELD True False" "that board draws the open hold held and the released one not (the control)"
verdict "the re-base (the console opener meeting the held lanes): the window the rebuilt opener starts is the board that draws the hold — the command file runs watch --run R, the lock its one-window claim is taken on sits beside it, and the same record read through watch.py reads the open hold held and the released one closed (the control)"

# ================================================ Batch 4, the handsoff.py half (2026-10-10) =====
# One block of legs, each built to fail on the code before the batch and pass on it (the batch's
# fail-on-old runs record both), named by the register entry it closes. Run ids that plant a
# console carry the suite's suffix ($SFX); every other fixture is this suite's own.

# ---- K4a701287: the successor cap from the run's grants file; resume-unsized names its path ----
plant_successors() { # $1 record, $2 count: that many head-exit and head-successor pairs, then the last exit
  "$PY" - "$1" "$2" <<'PLANTSUCC'
import json, sys, time
path, n = sys.argv[1], int(sys.argv[2])
run = json.loads(open(path, encoding="utf-8").readline())["run"]
stamp = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))
base = time.time() - 3600
with open(path, "a", encoding="utf-8") as fh:
    for i in range(n):
        for ev in ({"event": "head-exit", "band": 60, "context": "c", "spent_usd": 1.0, "pack": True},
                   {"event": "head-successor", "session_id": "sid-cap-%d" % i, "pid": 1, "budget": 1.0,
                    "model": "fixture-model"}):
            ev.update(ts=stamp(base + 10 * i), run=run)
            fh.write(json.dumps(ev) + "\n")
    fh.write(json.dumps({"ts": stamp(base + 10 * n), "run": run, "event": "head-exit", "band": 60,
                         "context": "c", "spent_usd": 1.0, "pack": True}) + "\n")
PLANTSUCC
}
# The default cap is 20 since the owner's amendment of 2026-10-30 (it was 6): each case plants 20.
fixture rcap 200
plant_successors "$REC" 20
run grants --run rcap --max-successors 30
need_rc 0
need_eq "$("$PY" -c 'import json, sys; print(json.load(open(sys.argv[1])).get("max_successors"))' "$REALSTORE/spawn-records/rcap-grants.json")" "30" "the grants file carries the run's cap"
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rcap --handoff "$HO" --budget 3.50 --out "$WORK/starter/rcap-head-1.out" --wait-s 1 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --model fixture-model
need_rc 0
need_eq "$(mk count "$REC" successor-aborted)" "0" "no abort under the grants file's cap of 30"
need_eq "$("$PY" -c 'import json, sys; e = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]; print(sum(1 for x in e if x.get("event") == "head-successor" and x.get("session_id") not in ("sid-by-the-head",) and not str(x.get("session_id")).startswith("sid-cap-")))' "$REC")" "1" "the twenty-first successor started"
fixture rcapctl 200
plant_successors "$REC" 20
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rcapctl --handoff "$HO" --budget 3.50 --out "$WORK/starter/rcapctl-head-1.out" --wait-s 1 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --model fixture-model
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "successor-cap" "the control: no grants key, the default cap of 20"
case $(mk field "$REC" successor-aborted note) in
  *"at its cap of 20 (the default"*) : ;;
  *) why="$why; the cap's source is not named: $(mk field "$REC" successor-aborted note)" ;;
esac
fixture rcapenv 200
plant_successors "$REC" 20
RUNENV="STUB_MODE=complete STUB_N=0 AIMYTH_MAX_SUCCESSORS=22"
starter --run rcapenv --handoff "$HO" --budget 3.50 --out "$WORK/starter/rcapenv-head-1.out" --wait-s 1 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --model fixture-model
need_rc 0
need_eq "$(mk count "$REC" successor-aborted)" "0" "with no grants key the environment's cap of 22 is the fallback"
verdict "K4a701287 (must fire): a grants file carrying max_successors 30 lets the starter start a twenty-first successor, the cap read from the run's own grants file, while the same record with no key aborts successor-cap at the default 20 naming the source (the control) and AIMYTH_MAX_SUCCESSORS stays the fallback"

fixture runsized 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-unsized","pid":1,"budget":5.0,"model":"fixture-model"}' >/dev/null
SOUGHT=$("$PY" -c 'import os, re, sys; print(os.path.join(os.path.realpath(os.environ["AIMYTH_PROJECTS_DIR"]), re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])), "sid-unsized.jsonl"))')
run _resume-head --run runsized --session sid-unsized --out none --harness-bin "$WORK/bin/harness" \
    --budget-usd 5 --tick-s 1 --model fixture-model
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "resume-unsized" "the abort"
case $(mk field "$REC" successor-aborted note) in
  *"sought $SOUGHT"*) : ;;
  *) why="$why; the abort does not name the transcript path it sought ($SOUGHT): $(mk field "$REC" successor-aborted note)" ;;
esac
verdict "K4a701287 (must fire): resume-head's resume-unsized abort names the transcript path it sought and why, beside the missing gate event"

# ---- Kcfcdadd1: a detached lane outlives a successor; the starter's first line names it ----
fixture rlanes 200
LANEPID=$("$PY" -c 'import subprocess, sys
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(p.pid)')
mk append "$REC" "{\"event\":\"lane-open\",\"lane\":\"LDET\",\"class\":\"verifier\",\"model\":\"opus\",\"session_id\":\"sid-ldet\"}" >/dev/null
mk append "$REC" "{\"event\":\"lane-spawned\",\"lane\":\"LDET\",\"session_id\":\"sid-ldet\",\"pid\":$LANEPID,\"wrapper_pid\":$LANEPID,\"detached\":true}" >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"LBAD","class":"critic","model":"opus"}' >/dev/null
mk append "$REC" '{"event":"lane-spawned","lane":"LBAD","pid":"not-a-pid"}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"LDONE","class":"builder","model":"opus"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LDONE","exit_class":"completed","total_cost_usd":1.0}' >/dev/null
viewer_use vlanes
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run rlanes --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 \
    --max-wait-s 5 --tick-s 1
need_rc 0
LOGL="$REALSTORE/spawn-records/rlanes-head-1.out.starter.log"
wait_log "$LOGL" "supervisor: head-successor pid" 30
wait_log "$LOGL" "starter: open lanes at the start (2): " 4
kill -0 "$LANEPID" 2>/dev/null || why="$why; the planted detached lane died across the successor"
grep -q -F "LDET open since " "$LOGL" || why="$why; the starter's line does not name LDET"
grep -q -F "wrapper pid $LANEPID alive, lane pid $LANEPID alive" "$LOGL" || why="$why; LDET's liveness is not read: $(grep 'open lanes' "$LOGL" | cut -c1-200)"
grep -q -F "LBAD open since" "$LOGL" || why="$why; the lane with an unusable pid is not listed"
grep -q -F "lane pid 'not-a-pid' unusable: unknown" "$LOGL" || why="$why; an unusable pid is not named unknown"
if grep -q -F "LDONE" "$LOGL"; then why="$why; a closed lane is listed as open"; fi
kill "$LANEPID" 2>/dev/null || :
sleep 1
verdict "Kcfcdadd1 (must fire): a planted detached lane in a session of its own is alive after successor started the next head (the successor path signals nothing), and the starter's first line lists the open lanes across the whole record with their liveness — alive, an unusable pid named unknown — and leaves a closed lane out"

# ---- Kd9717c6c: the run figure never falls at a lane's close; a floor while a lane runs ----
fixture rfall 400
mk pricedscript sid-lfall 2 lane-fall >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"LFALL","class":"builder","model":"opus","session_id":"sid-lfall"}' >/dev/null
mk append "$REC" '{"event":"lane-spawned","lane":"LFALL","session_id":"sid-lfall","pid":1}' >/dev/null
FALL_X=$("$PY" -c 'import sys; print("%.2f" % (2 * float(sys.argv[1])))' "$OPUS_IN")
FALL_RUN=$("$PY" -c 'import sys; print("%.2f" % (12.34 + 2 * float(sys.argv[1])))' "$OPUS_IN")
run run-spend --run rfall --meter-line "$METER" --no-cache
need_rc 1
need_out "lane LFALL: \$$FALL_X"
need_out "still running: LFALL"
need_out "AT LEAST"
mk append "$REC" '{"event":"lane-closed","lane":"LFALL","session_id":"sid-lfall","exit_class":"completed","total_cost_usd":1.0}' >/dev/null
run run-spend --run rfall --meter-line "$METER" --no-cache
need_rc 0
need_out "lane LFALL: \$$FALL_X · the larger of the transcript's \$$FALL_X"
need_out "run-spend: rfall · \$$FALL_RUN of \$400.00"
need_out "complete"
verdict "Kd9717c6c (must fire): a lane still running makes the run figure a floor (AT LEAST, the lane named), and at its close the lane keeps the larger of its transcript's figure (\$$FALL_X) and its lower recorded cost (\$1.00), so the run figure does not fall"

# ---- K22da6bf5: the successor's remainder is the close's ----
fixture rsame 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":50.0,"pack":true}' >/dev/null
mk append "$REC" '{"event":"head-resumed","session_id":"sid-rsame","pid":1,"model":"fixture-model"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":"limit","context":"c","spent_usd":60.0,"pack":false,"pid":1}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"LS","class":"builder","model":"opus"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LS","exit_class":"completed","total_cost_usd":10.0}' >/dev/null
run close --run rsame --items "fixture items" --meter-line "$METER" --dry-run
need_rc 0
need_out '"run_spend_usd": 22.34'
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rsame --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$177.66"
need_out "minus the run's spend \$22.34"
need_absent "spent over every head-exit"
verdict "K22da6bf5 (must fire): on a record with a resumed and a repaired head-exit (session totals 50 and 60) and a 10-dollar lane, the successor sizes the next head at the envelope minus the run's spend (22.34: the head's own 12.34 and the lane), the remainder the close meters (177.66), never the head-exits' summed session totals"

# ---- K615a63df: the stale-pack derivation lists every open lane and prefers the newer pack ----
fixture rstale 200
mk append "$REC" "$(printf '{"event":"phase-boundary","ts":"%s","from":"item6","to":"item7","next":"OLD NEXT: the seventh kit pass","disposition":"d","meter":"m","waste":"w"}' "$(tsago 86400)")" >/dev/null
mk append "$REC" "$(printf '{"event":"lane-open","ts":"%s","lane":"LP9","class":"builder","model":"opus","reason":"open before the anchor"}' "$(tsago 3000)")" >/dev/null
mk append "$REC" "$(printf '{"event":"lane-spawned","ts":"%s","lane":"LP9","pid":999999,"wrapper_pid":999998}' "$(tsago 3000)")" >/dev/null
plant_pack "$HO" "$(tsago 1800)" "HEAD PACK NEXT: item 9, the analysis gates"
mk append "$REC" "$(printf '{"event":"gate","ts":"%s","item":"item9","context":null,"percent":null,"band":"unmetered","armed":false,"decision":"allow","metered":false}' "$(tsago 600)")" >/dev/null
mk append "$REC" '{"event":"head-exit","band":"limit","context":"c","pack":false,"pid":1}' >/dev/null
run handoff --run rstale --inflight-from-record
need_rc 0
SEC=$(mk section "$HO" "In flight")
case $SEC in *"Needs: lane LP9 open since"*) : ;; *) why="$why; the lane opened before the anchor is not listed: $SEC" ;; esac
case $SEC in *"Next: HEAD PACK NEXT: item 9, the analysis gates (from the head's own pack written"*) : ;; *) why="$why; the newer head pack's Next is not taken: $SEC" ;; esac
case $SEC in *"OLD NEXT"*) why="$why; the day-old boundary's next stands in for the newer pack" ;; esac
case $SEC in *"Kept from the pack this rewrite replaced"*"Needs: wiki/h.md:1"*) : ;; *) why="$why; the head pack's other lines are not kept: $SEC" ;; esac
need_eq "$(grep -c '^## In flight (re-derived from the record at ' "$HO")" "1" "the derived section's own heading"
verdict "K615a63df (must fire): the re-derivation lists a lane opened before the anchor with no close (the whole record, not the span since the boundary), takes Next from the head's own pack where that is newer than the last phase-boundary, keeps the pack's other lines, and writes under its own heading"

# ---- K3a0b95c3: successor --seed-pid from an attended head ----
fixture rseedpid 200
sleep 60 &
ATTPID=$!
viewer_use vseedpid
T0=$(date +%s)
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run rseedpid --pid "$ATTPID" --seed-pid --meter-line "$METER" \
    --harness-bin "$WORK/bin/stubhead" --wait-s 30 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "--seed-pid: a seed process that exits 2 s after this call"
need_eq "$(mk field "$REC" head-exit pid)" "$ATTPID" "the head-exit names the attended head's own pid"
LOGS="$REALSTORE/spawn-records/rseedpid-head-1.out.starter.log"
wait_log "$LOGS" "supervisor: head-successor pid" 30
T1=$(date +%s)
[ $((T1 - T0)) -le 12 ] || why="$why; the successor started $((T1 - T0)) s after the call, not at once"
kill -0 "$ATTPID" 2>/dev/null || why="$why; the attended head's process is gone (it must stay alive throughout)"
grep -q -F "waits for pid" "$LOGS" || why="$why; the starter did not wait on the seed"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rseedpid --seed-pid --predecessor-pid "$ATTPID" --dry-run --meter-line "$METER" \
    --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "--seed-pid and --predecessor-pid each name the process the starter waits for"
fixture rseedctl 200
viewer_use vseedctl
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run rseedctl --pid "$ATTPID" --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 3 --max-wait-s 5 --tick-s 1
need_rc 0
wait_field "$REC" successor-aborted reason "timeout" 20
kill "$ATTPID" 2>/dev/null || :
verdict "K3a0b95c3 (must fire): with the attended head's pid alive, successor --seed-pid starts the successor within seconds on a seed process that exits on its own, the head-exit still naming the attended pid; --seed-pid beside --predecessor-pid is refused; without it the starter waits on the attended process and aborts on timeout (the control)"

# ---- Kae7bc546: boundary re-derives In flight, keeping the owner's relays and hand-written lines ----
fixture rbinf 200
printf -- '- Next: item3, the old pack\n- note: the owner relayed at 15:28 that the checklist stays (hand-written)\n- Needs: wiki/a.md:1\n- Decided: D1 because x\n' > "$WORK/pack-binf.md"
run handoff --run rbinf --inflight-file "$WORK/pack-binf.md"
need_rc 0
mk append "$REC" '{"event":"observation","phase":"","what":"AUTHOR ruling: the second writer pass runs next","note":"relayed by the watch"}' >/dev/null
run boundary --run rbinf --from item3 --to item4 --disposition "item3 done" --waste "none" \
    --next "item4: the new item" --meter-line "$METER"
need_rc 0
need_out "in flight: re-derived from the record"
SEC=$(mk section "$HO" "In flight")
case $SEC in *"Next: item4: the new item (the \`next\` of this boundary, item3 → item4)"*) : ;; *) why="$why; Next does not name the new item: $SEC" ;; esac
case $SEC in *"Next: item3, the old pack"*) why="$why; the old pack's Next survived beside the new one" ;; esac
case $SEC in *"Owner (an AUTHOR observation on the record at "*"AUTHOR ruling: the second writer pass runs next"*) : ;; *) why="$why; the relayed owner line is dropped: $SEC" ;; esac
case $SEC in *"note: the owner relayed at 15:28 that the checklist stays (hand-written)"*) : ;; *) why="$why; the hand-written line is dropped: $SEC" ;; esac
need_eq "$(grep -c '^## In flight (re-derived from the record at ' "$HO")" "1" "the derived section's own heading"
run handoff --run rbinf --inflight-file "$WORK/pack-binf.md"
need_rc 0
need_eq "$(grep -c '^## In flight$' "$HO")" "1" "a head's own pack restores the plain heading"
fixture rbinf2 200 inflight
run boundary --run rbinf2 --from item1 --to item2 --disposition "d" --waste "w" --next "item2" --meter-line "$METER"
need_rc 0
need_out "nothing re-derived"
verdict "Kae7bc546 (must fire): a boundary re-derives In flight after its trace row — Next names the boundary's new item, a relayed AUTHOR observation and a hand-written line of the replaced pack survive, the old Next does not, the section carries its own heading and a head's next pack restores the plain one; a hand-off with no In flight section is said and is no failure (the control)"

# ---- K782d71bb: the extraction reads queued owner messages and drops the harness's own records ----
TQ=$("$PY" - <<'QSCRIPT'
import json, os, re
sid = "sid-queued"
root = os.environ["AIMYTH_PROJECTS_DIR"]
path = os.path.join(root, re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])), sid + ".jsonl")
os.makedirs(os.path.dirname(path), exist_ok=True)
recs = [
    {"type": "user", "timestamp": "2026-10-01T10:00:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "the first owner turn"}]}},
    {"type": "assistant", "timestamp": "2026-10-01T10:00:05Z", "message": {"role": "assistant", "model": "claude-fixture-1", "content": [{"type": "text", "text": "the head works"}]}},
    {"type": "queue-operation", "operation": "enqueue", "timestamp": "2026-10-01T10:00:06Z", "content": "MIDTURN-OWNER-SENTINEL approve both"},
    {"type": "attachment", "timestamp": "2026-10-01T10:00:06Z", "attachment": {"type": "queued_command", "prompt": "MIDTURN-OWNER-SENTINEL approve both"}},
    {"type": "attachment", "timestamp": "2026-10-01T10:00:07Z", "attachment": {"type": "queued_command", "prompt": "<cross-session-message from=\"peer\">RELAY-SENTINEL the owner said go</cross-session-message>"}},
    {"type": "attachment", "timestamp": "2026-10-01T10:00:08Z", "attachment": {"type": "queued_command", "prompt": [{"type": "text", "text": "<task-notification>job 7 completed</task-notification>"}]}},
    {"type": "user", "timestamp": "2026-10-01T10:00:09Z", "message": {"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
    {"type": "user", "isCompactSummary": True, "timestamp": "2026-10-01T10:00:10Z", "message": {"role": "user", "content": [{"type": "text", "text": "This session is being continued from a previous conversation that ran out of context. COMPACT-SENTINEL the summary"}]}},
    {"type": "attachment", "timestamp": "2026-10-01T10:00:11Z", "attachment": {"type": "file", "filename": "x"}},
]
open(path, "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in recs))
print(path)
QSCRIPT
)
EXQ="$WORK/extract-queued"
run extract-transcript --session sid-queued --out "$EXQ"
need_rc 0
need_eq "$(grep -c 'MIDTURN-OWNER-SENTINEL approve both' "$EXQ/turns.md")" "1" "the queued owner message is a turn, once (not doubled by its queue-operation)"
need_eq "$(grep -B2 'MIDTURN-OWNER-SENTINEL' "$EXQ/turns.md" | grep -c '· human ·')" "1" "and it is a human turn"
need_eq "$(grep -c 'RELAY-SENTINEL' "$EXQ/turns.md")" "0" "a relay from another session is never a human turn"
need_eq "$(grep -c 'COMPACT-SENTINEL' "$EXQ/turns.md")" "0" "the compaction summary is never a human turn"
need_eq "$(grep -c 'Request interrupted' "$EXQ/turns.md")" "0" "the interrupt marker is never a human turn"
need_eq "$(mk json "$EXQ/counts.json" human_turns)" "2" "two human turns: the first and the queued one"
need_eq "$(mk json "$EXQ/counts.json" excluded.cross_session)" "1" "the relay"
need_eq "$(mk json "$EXQ/counts.json" excluded.compaction)" "1" "the compaction summary"
need_eq "$(mk json "$EXQ/counts.json" excluded.notification)" "1" "the queued notification"
need_eq "$(mk json "$EXQ/counts.json" excluded.interrupt)" "1" "the interrupt marker"
need_eq "$(mk json "$EXQ/counts.json" notes.queued_commands)" "1" "the note"
need_eq "$(mk json "$EXQ/counts.json" reconciles)" "true" "every record in one bucket"
verdict "K782d71bb (must fire): a message the owner sent mid-turn, carried by a queued_command attachment, is extracted as a human turn once, while a relay from another session, a queued task notification, an interrupt marker and a compaction summary are each excluded under their own count, and the records reconcile"

# ---- BC5-15b (register 2026-10-25 17:23): the session tool's relay, with its reply note ----
# The shape is a real record's: the wrapper, a CDATA body, the close, then the tool's one line. A
# relay beside the owner's words loses the relay and keeps the words; the words naming the wrapper
# mid-sentence stay the owner's, the control.
RELAY=$("$PY" - <<'RELAYSCRIPT'
import json, os, re
folder = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])))
os.makedirs(folder, exist_ok=True)
path = os.path.join(folder, "sid-relay.jsonl")
note = "\nReplying is optional. If a response is needed, call claudian_send_message with this session_id."
wrapped = '<session_message from="peer session" session_id="conv-1">\n<![CDATA[RELAY-BODY-SENTINEL the owner said go]]>\n</session_message>' + note
def user(text, stamp):
    return {"type": "user", "timestamp": "2026-10-01T10:00:%02dZ" % stamp, "message": {"role": "user", "content": text}}
recs = [user("the first owner turn", 0), user(wrapped, 1),
        user(wrapped + "\nOWNER-BESIDE-SENTINEL and my own words", 2),
        user("OWNER-NAMES-SENTINEL what does <session_message> mean here", 3),
        user('<session_messages from="x">NOT-A-RELAY-SENTINEL</session_messages>', 4)]
open(path, "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in recs))
print(path)
RELAYSCRIPT
)
need_file "$RELAY"
EXR="$WORK/extract-relay"
run extract-transcript --session sid-relay --out "$EXR"
need_rc 0
need_eq "$(mk json "$EXR/counts.json" excluded.cross_session)" "1" "the wrapped relay and its reply note, one record"
need_eq "$(grep -c 'RELAY-BODY-SENTINEL' "$EXR/turns.md")" "0" "a relay is never a human turn"
need_eq "$(grep -c 'Replying is optional' "$EXR/turns.md")" "0" "the tool's reply note is never a human turn"
need_eq "$(grep -c 'OWNER-BESIDE-SENTINEL and my own words' "$EXR/turns.md")" "1" "the owner's words beside a relay survive"
need_eq "$(grep -c 'OWNER-NAMES-SENTINEL' "$EXR/turns.md")" "1" "an owner naming the wrapper mid-sentence stays a turn"
need_eq "$(grep -c 'NOT-A-RELAY-SENTINEL' "$EXR/turns.md")" "1" "a longer tag name is no relay"
need_eq "$(mk json "$EXR/counts.json" human_turns)" "4" "the first, the words beside a relay, the naming turn and the longer tag"
need_eq "$(mk json "$EXR/counts.json" reconciles)" "true" "every record in one bucket"
verdict "BC5-15b (fails on old): a <session_message> record with the tool's reply note is a relay from another session, never an owner turn, while the owner's words beside one and an owner naming the wrapper stay human turns"

# ---- K9dd0b7fb: close and disarm remove the arming markers the run still owns ----
DSTATE="$WORK/state-disarm"
rm -rf "$DSTATE"; mkdir -p "$DSTATE"
fixture rdis 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-dis2","pid":1,"budget":1.0}' >/dev/null
mk append "$REC" '{"event":"head-successor","session_id":"sid-dis3","pid":1,"budget":1.0}' >/dev/null
: > "$DSTATE/armed-sid-rdis"; printf 'rdis\n' > "$DSTATE/run-sid-rdis"
: > "$DSTATE/armed-sid-dis2"; printf 'rother\n' > "$DSTATE/run-sid-dis2"
: > "$DSTATE/armed-sid-dis3"
: > "$DSTATE/armed-sid-unrelated"; printf 'rdis\n' > "$DSTATE/run-sid-unrelated"
DLINES=$(mk lines "$REC")
RUNENV="AIMYTH_STATE_DIR=$DSTATE"
run close --run rdis --items "fixture items" --meter-line "$METER" --dry-run
need_rc 0
need_out "would remove"
need_file "$DSTATE/armed-sid-rdis"
printf 'decisions\n' > "$WORK/dis-decisions.md"
RUNENV="AIMYTH_STATE_DIR=$DSTATE"
run close --run rdis --items "fixture items" --meter-line "$METER" --decisions-file "$WORK/dis-decisions.md"
need_rc 6
need_file "$DSTATE/armed-sid-rdis"
need_eq "$(mk lines "$REC")" "$DLINES" "a held close writes nothing"
RUNENV="AIMYTH_STATE_DIR=$DSTATE"
run disarm --run rdis
need_rc 2
need_out "carries no run-close"
RUNENV="AIMYTH_STATE_DIR=$DSTATE"
run close --run rdis --items "fixture items" --meter-line "$METER"
need_rc 0
need_out "disarm: rdis · "
need_nofile "$DSTATE/armed-sid-rdis"
need_file "$DSTATE/armed-sid-dis2"
need_file "$DSTATE/armed-sid-dis3"
need_file "$DSTATE/armed-sid-unrelated"
need_out "sid-dis2 kept (its pointer names run rother"
need_out "sid-dis3 unresolved (no pointer"
: > "$DSTATE/armed-sid-rdis"
chmod 555 "$DSTATE"
RUNENV="AIMYTH_STATE_DIR=$DSTATE"
run disarm --run rdis
need_rc 1
need_out "sid-rdis failed ("
chmod 755 "$DSTATE"
need_file "$DSTATE/armed-sid-rdis"
RUNENV="AIMYTH_STATE_DIR=$DSTATE"
run disarm --run rdis
need_rc 1
need_out "sid-rdis removed"
need_nofile "$DSTATE/armed-sid-rdis"
verdict "K9dd0b7fb (must fire): once run-close is on the record, close removes the arming marker of a head session whose pointer still names the run, keeps one whose pointer names another run, leaves one with no pointer unresolved and touches no unrelated marker; a dry run and a held close remove nothing; disarm refuses an open run, reports an unlink the system refuses (exit 1) and removes the marker on the retry"

# ---- K64bc6c8c: grant additions merge; any shrink needs --replace ----
fixture rgadd 200
GFA="$REALSTORE/spawn-records/rgadd-grants.json"
run grants --run rgadd --grant "$WORK/carry/r1" --write "$WORK/carry/w1" --write "$WORK/carry/w2" \
    --write "$WORK/carry/w3" --write "$WORK/carry/w4" --write "$WORK/carry/w5" --write "$WORK/carry/w6" \
    --write "$WORK/carry/w7" --write "$WORK/carry/w8" --write "$WORK/carry/w9" --write "$WORK/carry/w10" \
    --write "$WORK/carry/w11" --write "$WORK/carry/w12" --network api.example.org --viewer none \
    --on-limit resume --max-successors 12
need_rc 0
"$PY" - "$GFA" <<'FUTUREKEY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["future_setting"] = {"kept": True}
json.dump(d, open(sys.argv[1], "w", encoding="utf-8"), indent=1)
FUTUREKEY
WBEFORE=$(gcount "$GFA" writes)
GASHA=$(sha_file "$GFA")
run grants --run rgadd --write "$WORK/carry/clone" --grant "$WORK/carry/clone"
need_rc 2
need_out "would shrink the run's grants and passes no --replace"
need_eq "$(sha_file "$GFA")" "$GASHA" "the 14-write regression refuses, the file untouched"
run grants --run rgadd --add-write "$WORK/carry/clone" --add-grant "$WORK/carry/clone"
need_rc 0
NSPELL=$("$PY" -c 'import os, sys; p = os.path.abspath(sys.argv[1]); print(1 if os.path.realpath(p) == p else 2)' "$WORK/carry/clone")
need_eq "$(gcount "$GFA" writes)" "$((WBEFORE + NSPELL))" "every write kept and the clone added (in each of its $NSPELL spelling(s))"
need_eq "$(glist "$GFA" writes "$WORK/carry/w12")" "1" "an earlier write survives"
need_eq "$(glist "$GFA" grants "$WORK/carry/r1")" "1" "an earlier read grant survives"
need_eq "$(glist "$GFA" grants "$WORK/carry/clone")" "1" "the read grant added"
need_eq "$(gval "$GFA") $(vval "$GFA") $(nval "$GFA")" 'resume none ["api.example.org"]' "on_limit, viewer and network kept"
need_eq "$("$PY" -c 'import json, sys; d = json.load(open(sys.argv[1])); print(d.get("max_successors"), json.dumps(d.get("future_setting")))' "$GFA")" '12 {"kept": true}' "the successor cap and a newer setting kept"
run grants --run rgadd --write "$WORK/carry/clone" --grant "$WORK/carry/clone" --replace
need_rc 0
need_out "(--replace: the lists named replace the run's, so it is written)"
need_eq "$(glist "$GFA" writes "$WORK/carry/w12")" "0" "--replace narrows on purpose"
run grants --run rgadd --add-write "$WORK/carry/after"
need_rc 0
need_absent "would shrink"
need_eq "$(glist "$GFA" writes "$WORK/carry/after")" "1" "the replacement is the next call's baseline"
run grants --run rgadd --grant "$WORK/carry/a" --add-grant "$WORK/carry/b"
need_rc 2
need_out "pass one form for the read list"
run grants --run rgadd --replace
need_rc 2
need_out "--replace names no list"
run grants --run rgadd --replace --add-write "$WORK/carry/x"
need_rc 2
need_out "pass one form"
REC_RO="$STORE/spawn-records/rgaddopen.jsonl"; rm -f "$REC_RO"
run run-open --run rgaddopen --session sid-rgaddopen --head "fixture head" --regime multi --regime-src owner \
    --handoff "$HO" --detail "add on open" --pid 1 --add-write "$WORK/carry/x"
need_rc 2
need_out "writes the run's first grants file"
need_nofile "$REC_RO"
fixture rgnobase 200
run grants --run rgnobase --add-write "$WORK/carry/x"
need_rc 2
need_out "no trustworthy baseline"
need_nofile "$REALSTORE/spawn-records/rgnobase-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rgadd --session sid-rgadd2 --head "fixture head" --detail "an addition" --add-write "$WORK/carry/viaresume"
need_rc 0
need_out "(paths added)"
need_eq "$(glist "$GFA" writes "$WORK/carry/after")" "1" "run-resume's addition keeps the list"
need_eq "$(glist "$GFA" writes "$WORK/carry/viaresume")" "1" "and adds its path"
( env "$PY" -B "$H" grants --run rgadd --add-write "$WORK/carry/conc-a" >"$WORK/conc-a.out" 2>&1 ) &
CA=$!
( env "$PY" -B "$H" grants --run rgadd --add-write "$WORK/carry/conc-b" >"$WORK/conc-b.out" 2>&1 ) &
CB=$!
wait "$CA"; RCA=$?
wait "$CB"; RCB=$?
need_eq "$RCA $RCB" "0 0" "both concurrent additions succeed"
need_eq "$(glist "$GFA" writes "$WORK/carry/conc-a") $(glist "$GFA" writes "$WORK/carry/conc-b")" "1 1" "neither concurrent addition is lost"
verdict "K64bc6c8c (must fire): on a 14-write run, grants --write X --grant X refuses and leaves the file byte-identical; --add-write/--add-grant keep both lists, on_limit, viewer, network, the successor cap and a newer setting; --replace rewrites and becomes the baseline; conflicting forms and an add with no trustworthy baseline are refused; run-resume adds the same way; two additions at once both land"

# ---- G8 (register 2026-10-23 03:48): a reading-list check is no control of the reflector's ----
# The planted cases are the entry's: a verifier's CONTROL+ "NOT READY" and a path on it, both of
# which withheld every line naming them. The controls are a reflector's own phrase and whole path,
# its resumed lane, and a class-less legacy plant, each of which must stay withheld.
LONGROOT="/fixture/a/root/of/more/than/forty/characters/shared/by/every/path"
fixture rneedle 200
mk append "$REC" "{\"event\":\"lane-open\",\"lane\":\"V1\",\"class\":\"verifier\",\"controls_checked\":[{\"phrase\":\"NOT READY\",\"file\":\"$LONGROOT/verifier-brief.md\",\"matches\":1}]}" >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"V1","controls_checked":[{"phrase":"RESUMED-VERIFIER-PHRASE","file":"","matches":1}]}' >/dev/null
mk append "$REC" "{\"event\":\"lane-open\",\"lane\":\"R1\",\"class\":\"reflector\",\"controls_checked\":[{\"phrase\":\"REFLECTOR-ONLY-PHRASE\",\"file\":\"$LONGROOT/reflector-control.md\",\"matches\":1}]}" >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"R1","controls_checked":[{"phrase":"RESUMED-REFLECTOR-PHRASE","file":"","matches":1}]}' >/dev/null
mk append "$REC" '{"event":"plant-recorded","plant":"LEGACY-PLANT-PHRASE"}' >/dev/null
TNEED=$("$PY" - "$LONGROOT" <<'NEEDSCRIPT'
import json, os, re, sys
root = sys.argv[1]
folder = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])))
os.makedirs(folder, exist_ok=True)
path = os.path.join(folder, "sid-needle.jsonl")
lines = ["the verdict read NOT READY at item 2", "RESUMED-VERIFIER-PHRASE stands", "reading %s/some-other-page.md now" % root,
         "reading %s/verifier-brief.md now" % root, "REFLECTOR-ONLY-PHRASE stands", "RESUMED-REFLECTOR-PHRASE stands",
         "LEGACY-PLANT-PHRASE stands", "reading %s/reflector-control.md now" % root, "an ordinary line"]
recs = [{"type": "user", "timestamp": "2026-10-02T10:00:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "the owner asks"}]}},
        {"type": "assistant", "timestamp": "2026-10-02T10:00:05Z", "message": {"role": "assistant", "model": "claude-fixture-1", "content": [{"type": "text", "text": "\n".join(lines)}]}}]
open(path, "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in recs))
print(path)
NEEDSCRIPT
)
OUTN="$WORK/refl-needle"
run reflect-inputs --run rneedle --session sid-needle --out "$OUTN" --no-meter
need_rc 0
need_eq "$(grep -c 'the verdict read NOT READY at item 2' "$OUTN/turns.md")" "1" "a verifier's check phrase stays"
need_eq "$(grep -c 'RESUMED-VERIFIER-PHRASE stands' "$OUTN/turns.md")" "1" "a resumed verifier lane's phrase stays"
need_eq "$(grep -c 'some-other-page.md now' "$OUTN/turns.md")" "1" "a path under the same root stays"
need_eq "$(grep -c 'verifier-brief.md now' "$OUTN/turns.md")" "1" "a verifier's own file stays"
need_eq "$(grep -c 'REFLECTOR-ONLY-PHRASE' "$OUTN/turns.md")" "0" "a reflector's control is withheld"
need_eq "$(grep -c 'RESUMED-REFLECTOR-PHRASE' "$OUTN/turns.md")" "0" "a resumed reflector lane's control is withheld"
need_eq "$(grep -c 'LEGACY-PLANT-PHRASE' "$OUTN/turns.md")" "0" "a class-less plant is withheld"
need_eq "$(grep -c 'reflector-control.md' "$OUTN/turns.md")" "0" "a reflector's whole path is withheld"
need_eq "$(grep -c 'an ordinary line' "$OUTN/turns.md")" "1" "the ordinary line stays"
need_eq "$(mk json "$OUTN/counts.json" notes.controls_redacted)" "4" "four lines withheld, counted"
verdict "G8 (fails on old): reflect-inputs keeps a lane's reading-list check phrase and a path that shares only its root, while a reflector's control, its resumed lane's, its whole path and a class-less plant stay withheld"

# ---- K0fe7df69: reflect-inputs on an attended record; the controls withheld from the extraction ----
plain_fixture rratt
mk append "$REC" '{"event":"observation","phase":"controls-XRATT","what":"ATT-CONTROL-SENTINEL the reflector must find the missed gate","note":"planted"}' >/dev/null
mk xscript sid-att >/dev/null
OUTATT="$WORK/refl-attended"
run reflect-inputs --run rratt --session sid-att --out "$OUTATT" --no-meter
need_rc 0
need_out "attended record (no run-open)"
for f in turns.md counts.json waste-table.md record-filtered.jsonl; do need_file "$OUTATT/$f"; done
need_eq "$(grep -c 'Head figures: unavailable' "$OUTATT/waste-table.md")" "1" "the head figures are said to be unavailable"
need_eq "$(grep -c '^| heads. total\|^| run total' "$OUTATT/waste-table.md")" "0" "no total row: the record holds no billed line and no recorded run spend"
need_eq "$(grep -c 'ATT-CONTROL-SENTINEL' "$OUTATT/record-filtered.jsonl")" "0" "the controls observation is dropped from the copy"
need_eq "$(mk field "$REC" reflect-inputs shape)" "attended" "the event names the shape"
fixture rrhands 200
mk xscript sid-hands >/dev/null
run reflect-inputs --run rrhands --session sid-hands --out "$WORK/refl-hands" --no-meter
need_rc 0
need_absent "attended record"
need_eq "$(grep -c 'Head figures: unavailable' "$WORK/refl-hands/waste-table.md")" "0" "a hands-off record keeps its head rows (the control)"
need_eq "$(mk field "$REC" reflect-inputs shape)" "hands-off" "the event names the shape"
plain_fixture rratt2
printf '{"event": "run-open", "run": "rratt2", torn\n' >> "$REC"
run reflect-inputs --run rratt2 --session sid-att --out "$WORK/refl-torn" --no-meter
need_rc 2
need_out "an attended record must read whole"
need_nofile "$WORK/refl-torn/turns.md"
verdict "K0fe7df69 (must fire): reflect-inputs takes a record with no run-open as an attended record — the extraction, a waste table rendered from the lane events with the head figures said to be unavailable, and the blinded copy — while a hands-off record renders as before and a record with a torn line is refused rather than read as attended"

fixture rrsent 200
mk append "$REC" '{"event":"observation","phase":"controls-XRS","what":"CTRL-SENTINEL-B4H the reflector must name the ledger gap at item 3","note":"pre-registered"}' >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"XRS","class":"reflector","model":"opus","plant":"PLANT-SENTINEL-B4H a planted stale pack in the fixture"}' >/dev/null
TSENT=$("$PY" - <<'SENTSCRIPT'
import json, os, re
sid = "sid-sent"
root = os.environ["AIMYTH_PROJECTS_DIR"]
path = os.path.join(root, re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])), sid + ".jsonl")
os.makedirs(os.path.dirname(path), exist_ok=True)
ctl = "CTRL-SENTINEL-B4H the reflector must name the ledger gap at item 3"
recs = [
    {"type": "user", "timestamp": "2026-10-02T10:00:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "the owner asks for the reflection"}]}},
    {"type": "assistant", "timestamp": "2026-10-02T10:00:05Z", "message": {"role": "assistant", "model": "claude-fixture-1", "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "git status --porcelain"}}]}},
    {"type": "assistant", "timestamp": "2026-10-02T10:00:10Z", "message": {"role": "assistant", "model": "claude-fixture-1", "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "python3 handsoff.py ledger --run rrsent --phase controls-XRS --observation \"%s\"" % ctl}}]}},
    {"type": "assistant", "timestamp": "2026-10-02T10:00:15Z", "message": {"role": "assistant", "model": "claude-fixture-1", "content": [{"type": "text", "text": "Registered the control.\nI expect: %s.\nNow the spawn." % ctl}]}},
    {"type": "assistant", "timestamp": "2026-10-02T10:00:20Z", "message": {"role": "assistant", "model": "claude-fixture-1", "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "echo \"PLANT-SENTINEL-B4H a planted stale pack in the fixture\" > /tmp/plant.txt"}}]}},
]
open(path, "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in recs))
print(path)
SENTSCRIPT
)
OUTS="$WORK/refl-sentinel"
run reflect-inputs --run rrsent --session sid-sent --out "$OUTS" --no-meter
need_rc 0
need_eq "$(grep -r -c 'SENTINEL-B4H' "$OUTS" | awk -F: '{s += $2} END {print s + 0}')" "0" "no control or plant text in any of the four outputs"
need_eq "$(grep -c '^- Bash: git status --porcelain' "$OUTS/turns.md")" "1" "an ordinary tool call stays"
need_eq "$(grep -c 'Registered the control.' "$OUTS/turns.md")" "1" "an ordinary line of the same turn stays"
need_eq "$(mk json "$OUTS/counts.json" notes.controls_redacted)" "3" "three lines withheld, counted"
need_eq "$(grep -c 'SENTINEL-B4H' "$TSENT")" "3" "the control: the source transcript carries the texts"
need_eq "$(grep -c 'SENTINEL-B4H' "$REC")" "2" "the control: the source record carries them"
verdict "K0fe7df69 (critic finding 2, must fire): a control text present in both the record and the head's transcript — in the Bash command that registered it, in the head's own prose and in a planted case's echo — appears in none of the four blinded outputs, the three lines withheld and counted, while an ordinary tool call and the turn's other lines stay"

cp "$TSENT" "$WORK/frozen-sent.jsonl"
"$PY" - "$TSENT" <<'GROWSENT'
import json, sys
with open(sys.argv[1], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": "2026-10-02T10:01:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "AFTER-FREEZE a later owner turn"}]}}) + "\n")
GROWSENT
run reflect-inputs --run rrsent --session sid-sent --out "$WORK/refl-frozen" --transcript "$WORK/frozen-sent.jsonl" --no-meter
need_rc 0
need_eq "$(mk json "$WORK/refl-frozen/counts.json" records)" "5" "the frozen copy's records, not the live transcript's six"
need_eq "$(grep -c 'AFTER-FREEZE' "$WORK/refl-frozen/turns.md")" "0" "nothing after the freeze"
run reflect-inputs --run rrsent --session sid-sent --out "$WORK/refl-frozen2" --transcript "$WORK/no-such-copy.jsonl" --no-meter
need_rc 2
need_out "is not a file"
verdict "K0fe7df69 (the frozen-transcript remedy): --transcript reads a frozen copy of the session instead of the live transcript, which has grown since, and a copy that is not there is refused"

# ---- K235cae8f: the stage root's reflect/ directory, carved out of the store check ----
fixture rcarve 200
mk xscript sid-carve >/dev/null
SROOT="$REALSTORE/stages/rcarve"
mkdir -p "$SROOT/reflect" "$REALSTORE/stages/rcarve2/reflect"
run reflect-inputs --run rcarve --session sid-carve --out "$SROOT/reflect/xr" --no-meter
need_rc 0
need_file "$SROOT/reflect/xr/turns.md"
for bad in "$SROOT/other" "$REALSTORE/stages/rcarve2/reflect" "$SROOT/reflect2" "$REALSTORE/spawn-records/rcarve-xr"; do
  run reflect-inputs --run rcarve --session sid-carve --out "$bad" --no-meter
  need_rc 2
  need_out "inside the run store"
done
ln -s "$REALSTORE/spawn-records" "$SROOT/reflect/esc"
run reflect-inputs --run rcarve --session sid-carve --out "$SROOT/reflect/esc/xr" --no-meter
need_rc 2
need_out "inside the run store"
need_nofile "$REALSTORE/spawn-records/xr/turns.md"
run reflect-inputs --run rcarve --session sid-carve --out "$PROJECTS/xr" --no-meter
need_rc 2
need_out "inside the projects root"
verdict "K235cae8f (must fire): reflect-inputs writes into the run's own <store>/stages/<run>/reflect/, while a sibling of it, another run's reflect directory, a prefix lookalike, the spawn records, a symlink leading out of reflect/ into the store and the projects root are each refused"

# ---- K6149a3b5: a hands-off head's heartbeat is refused ----
fixture rhbref 200
HBPID_FILE="$REALSTORE/spawn-records/rhbref-heartbeat.pid"
sleep 60 &
HBLIVE=$!
printf '%s %s\n' "$HBLIVE" "$(( $(date +%s) + 3000 ))" > "$HBPID_FILE"
HBSHA=$(sha_file "$HBPID_FILE")
HBLINES=$(mk lines "$REC")
RUNENV="AIMYTH_HANDSOFF=1"
run heartbeat --run rhbref --minutes 1
need_rc 2
need_lines
need_out "heartbeat refused: this caller runs under AIMYTH_HANDSOFF=1"
need_eq "$(sha_file "$HBPID_FILE")" "$HBSHA" "the attended heartbeat's pid file is untouched"
need_eq "$(mk lines "$REC")" "$HBLINES" "no heartbeat event"
RUNENV="AIMYTH_HANDSOFF=1"
run heartbeat --run rhbref --stop
need_rc 2
need_nofile "$REALSTORE/spawn-records/rhbref-heartbeat.stop"
kill "$HBLIVE" 2>/dev/null || :
rm -f "$HBPID_FILE"
run heartbeat --run rhbref --minutes 1 --dry-run
need_rc 0
need_out "heartbeat: dry run · would arm"
verdict "K6149a3b5 (must fire): heartbeat under AIMYTH_HANDSOFF=1 exits 2 with one line before the record, the pid file or the stop marker is touched — an attended heartbeat's pid file stays byte-identical and --stop writes no marker — while without the variable the attended path arms (the control)"

# ---- K94e80827: a limit wait ends at the first head start after the stop ----
fixture rlwait 200
LW0=$(tsago 3700)
mk append "$REC" "$(printf '{"event":"stop-condition","ts":"%s","which":"limit","lane":"head","action":"wait","note":"limit"}' "$LW0")" >/dev/null
LWS=$("$PY" -c 'import sys, time
from datetime import datetime
t = datetime.strptime(sys.argv[1], "%Y-%m-%dT%H:%M:%S%z").timestamp() + 45
print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t)))' "$LW0")
mk append "$REC" "$(printf '{"event":"head-successor","ts":"%s","session_id":"sid-lw2","pid":1,"budget":1.0}' "$LWS")" >/dev/null
mk append "$REC" "$(printf '{"event":"head-resumed","ts":"%s","session_id":"sid-lw2","pid":1}' "$(tsago 100)")" >/dev/null
mk append "$REC" "$(printf '{"event":"stop-condition","ts":"%s","which":"band","lane":"head","action":"refused","note":"band"}' "$(tsago 90)")" >/dev/null
mk append "$REC" "$(printf '{"event":"head-successor","ts":"%s","session_id":"sid-lw3","pid":1,"budget":1.0}' "$(tsago 80)")" >/dev/null
WLW="$WORK/wt-lwait.md"
run waste-table --run rlwait --no-meter --out "$WLW"
need_rc 0
need_eq "$(grep -c "^| limit wait · limit → head-successor at $LWS | 0.75 min" "$WLW")" "1" "the wait ends at the successor 0.75 min after the stop"
need_eq "$(grep -c '^| limit wait' "$WLW")" "1" "one row: a band stop is no limit wait (the control)"
verdict "K94e80827 (must fire): a limit stop followed by a successor 45 s later and a head-resumed an hour on reads a 0.75-minute wait ending at the head-successor, and a band stop-condition takes no limit-wait row"

# ---- K3dbf76d5: the next head's model is the record's, or the call is refused ----
HONM="$WORK/handoffs/rnomodel-handoff.md"; mk handoff "$HONM" >/dev/null
REC="$STORE/spawn-records/rnomodel.jsonl"; rm -f "$REC"
mk record "$REC" rnomodel sid-rnomodel "$HONM" 200 nomodel >/dev/null
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
NMLINES=$(mk lines "$REC")
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rnomodel --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "successor needs a model for the next head"
need_lines
RUNENV="PATH=$WORK/psnone:$PATH"
run resume-head --run rnomodel --dry-run --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "resume-head needs a model"
need_eq "$(mk lines "$REC")" "$NMLINES" "neither refusal wrote a line"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rnomodel --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness" --model opus-x
need_rc 0
need_out "model opus-x (model_src: arg)"
rm -f "$WORK/stub-rnomodel.count"
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run rnomodel --handoff "$HONM" --budget 3.50 --out "$WORK/starter/rnomodel-head-1.out" --wait-s 1 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "model-unknown" "the supervisor's own start with no model aborts"
need_nofile "$WORK/stub-rnomodel.count"
fixture rinherit 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-inh1","pid":1,"budget":1.0,"model":"opus-x","model_src":"arg"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rinherit --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "model opus-x (model_src: record: the head-successor at "
need_out "--model opus-x"
mk append "$REC" '{"event":"head-resumed","session_id":"sid-inh1","pid":1,"model":"sonnet-y"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rinherit --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "model sonnet-y (model_src: record: the head-resumed at "
RUNENV="PATH=$WORK/psnone:$PATH"
run resume-head --run rinherit --dry-run --harness-bin "$WORK/bin/harness" --model fable-z
need_rc 0
need_out "model fable-z (arg)"
fixture rauto 200
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5,"pack":true}' >/dev/null
RUNENV="STUB_MODE=error STUB_N=1"
starter --run rauto --handoff "$HO" --budget 3.50 --out "$WORK/starter/rauto-head-1.out" --wait-s 1 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 0
need_eq "$("$PY" -c 'import json, sys; e = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]; print(" ".join(str(x.get("model")) for x in e if x.get("event") == "head-successor" and x.get("session_id") != "sid-by-the-head"))' "$REC")" "fixture-model fixture-model" "both starts — the starter's and the supervisor's own successor after the error — carry the record's model"
verdict "K3dbf76d5 (must fire): with no model anywhere successor and resume-head refuse before writing and the supervisor's own start aborts model-unknown with no harness started; a by-hand successor inherits the newest head start's structured model (a later head-resumed's wins), an explicit --model wins, and the supervisor's automatic successor after an error inherits the record's model (this run's 13:36 recurrence)"

LCM=$("$PY" -c 'import subprocess, sys
p = subprocess.Popen(["sleep", "30"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(p.pid)')
fixture rlcmodel 200
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcm\",\"pid\":$LCM,\"model\":null,\"model_src\":\"harness default (no --model)\",\"effort\":\"max\"}" >/dev/null
run launch-check --run rlcmodel --wait 0 --detach-safe
need_rc 1
need_out "launch-check: rlcmodel NOT CERTIFIED · the head started"
need_out "carries no readable model (model_src harness default (no --model))"
need_absent "rlcmodel STARTED"
fixture rlcmodel2 200
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcm2\",\"pid\":$LCM,\"model\":\"fixture-model\",\"effort\":\"max\"}" >/dev/null
run launch-check --run rlcmodel2 --wait 0 --detach-safe
need_rc 0
need_absent "carries no readable model"
verdict "G14x (fails on old): launch-check refuses to certify a start whose head-successor carries no model, exit 1, since it may run on the harness default; a start with a model certifies (the control)"

# G14x, the run-resume half (register 2026-10-15 01:33 c, status of 28 October): a head's first act
# is a run-resume whose model sits in free text. The controls are the head-successor naming its
# session, read as the model, and `run-resume --model`; the planted case is a session no start names
# a model for, which certified before.
fixture rlcmodel3 200
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-lcm3\",\"pid\":$LCM,\"model\":\"fixture-model\",\"effort\":\"high\"}" >/dev/null
mk append "$REC" "{\"event\":\"run-resume\",\"session\":\"sid-lcm3\",\"head\":\"opus at max in free text\",\"detail\":\"its first act\",\"pid\":$LCM}" >/dev/null
run launch-check --run rlcmodel3 --wait 0 --detach-safe
need_rc 0
need_out "model fixture-model effort high"
fixture rlcmodel4 200
mk append "$REC" "{\"event\":\"run-resume\",\"session\":\"sid-other-head\",\"head\":\"opus at max in free text\",\"detail\":\"an attended head\",\"pid\":$LCM}" >/dev/null
run launch-check --run rlcmodel4 --wait 0 --detach-safe
need_rc 1
need_out "launch-check: rlcmodel4 NOT CERTIFIED"
need_out "the run-resume at .* carries no readable model"
need_out "model none effort none"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rlcmodel4 --session sid-named-head --head "named head" --detail "names its model" --pid "$LCM" --model fixture-model --effort high
need_rc 0
run launch-check --run rlcmodel4 --wait 0 --detach-safe
need_rc 0
need_out "model fixture-model effort high"
kill "$LCM" 2>/dev/null || :
verdict "G14x (fails on old): a run-resume reads the model of the head start naming its session, a session none names one for is refused, and run-resume --model names it"

# ---- K0bef4fc6: the replay — an unparsed limit stop writes its head-exit when the head ran run-resume ----
fixture rreplay 200
arm_resume rreplay
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":5}' >/dev/null
RUNENV="STUB_MODE=nolimit STUB_N=1 STUB_TOKENS=50000 STUB_RESUME=1 AIMYTH_CONTEXT_WINDOW=200000"
starter --run rreplay --handoff "$HO" --budget 3.50 --out "$WORK/starter/rreplay-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --probe-interval-s 1 --tick-s 1 --model fixture-model
need_rc 1
need_eq "$(mk count "$REC" run-resume)" "1" "the head ran its own run-resume (the premise of the replay)"
need_eq "$(mk field "$REC" stop-condition which)" "limit-unparsed" "the unparsed stop"
need_eq "$(mk count "$REC" head-exit)" "2" "the planted exit and the stop's own"
need_eq "$(mk field "$REC" head-exit which)" "limit-unparsed" "the last head-exit is the stop's"
need_out "head-exit recorded (band limit"
need_absent "already follows this head's start: none written"
verdict "K0bef4fc6 (the replay of the 2026-09-22 batch run's record, must fire): a head that ran its own run-resume, then stopped on a limit with no parseable reset, gets its head-exit from the supervisor before successor-aborted — the head's own run-resume no longer reads as a later head that supersedes the stop"

# ---- Keefdb609: a console counts whatever order its arguments take ----
probe_alive() { # $1 run to probe, $2 control run: prints "<count> <control count>"
  "$PY" - "$H" "$1" "$2" <<'CALIVE_ORDER'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod.note = lambda msg: None
print(len(mod.console_alive(sys.argv[2])), len(mod.console_alive(sys.argv[3])))
CALIVE_ORDER
}
ROR="rvwor$SFX"
"$PY" -c 'import time; time.sleep(60)' watch.py --vault /fixture/vault --run "$ROR" &
ORP=$!; sleep 1
need_eq "$(probe_alive "$ROR" "$ROR-nobody")" "1 0" "another argument before --run (a console started with --vault first), with the negative control"
kill "$ORP"; wait "$ORP" 2>/dev/null || :
"$PY" -c 'import time; time.sleep(60)' watch.py "--run=$ROR" &
ORP=$!; sleep 1
need_eq "$(probe_alive "$ROR" "$ROR-nobody")" "1 0" "the --run=R form"
kill "$ORP"; wait "$ORP" 2>/dev/null || :
"$PY" -c 'import time; time.sleep(60)' handsoff.py watch --vault /fixture/vault --run "$ROR" &
ORP=$!; sleep 1
need_eq "$(probe_alive "$ROR" "$ROR-nobody")" "1 0" "handsoff.py watch with --vault first"
kill "$ORP"; wait "$ORP" 2>/dev/null || :
"$PY" -c 'import time; time.sleep(60)' watch.py --run "$ROR-longer" &
ORP=$!; sleep 1
need_eq "$(probe_alive "$ROR" "$ROR-longer")" "0 1" "a console for a longer run id never counts for its prefix (the control finds it)"
kill "$ORP"; wait "$ORP" 2>/dev/null || :
"$PY" -c 'import time; time.sleep(60)' lanewatch.py --run "$ROR" &
ORP=$!; sleep 1
need_eq "$(probe_alive "$ROR" "$ROR-nobody")" "0 0" "lanewatch.py is not watch.py (the left boundary)"
kill "$ORP"; wait "$ORP" 2>/dev/null || :
"$PY" -c 'import time; time.sleep(60)' lane.py watch --run "$ROR" --lane X &
ORP=$!; sleep 1
need_eq "$(probe_alive "$ROR" "$ROR-nobody")" "0 0" "a lane.py watch process (a helper's own wait) is not a console"
kill "$ORP"; wait "$ORP" 2>/dev/null || :
verdict "Keefdb609 (must fire): a console counts with --vault before --run, with --run=R and as handsoff.py watch with other arguments first, while a longer run id, lanewatch.py --run R and a lane.py watch never count"

# ---- Kd5d7ad73: close needs --items, before anything is written ----
fixture ritems 200
ILINES=$(mk lines "$REC")
run close --run ritems --meter-line "$METER" --ack "read nothing new"
need_rc 2
need_out "close needs --items"
need_lines
need_eq "$(mk lines "$REC")" "$ILINES" "refused before the ack or any other write"
run close --run ritems --meter-line "$METER" --dry-run
need_rc 0
need_out "close: --items absent: a real close refuses that"
need_eq "$(mk lines "$REC")" "$ILINES" "a dry run writes nothing"
run close --run ritems --items "item1 done; item2 held: the owner's call" --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" run-close items)" "item1 done; item2 held: the owner's call" "the stated items"
need_out "close: --register absent: written as unstated"
need_out "close: --log absent: written as unstated"
need_out "close: --lint absent: written as unstated"
plain_fixture pitems
run close --run pitems
need_rc 2
need_out "close needs --items"
run close --run pitems --items "the lanes' work, verified"
need_rc 0
need_eq "$(mk field "$REC" run-close shape)" "plain-lane-run" "the plain shape closes with stated items"
verdict "Kd5d7ad73 (must fire): close with --items absent is refused (exit 2) before its ack or any other write, a dry run reads it as unstated and writes nothing, stated items close both record shapes, and an absent --register, --log or --lint is noted on stderr"

# ---- K06dde25c: the waste table's run total is the run's spend, heads and lanes ----
# The boundary below records the run figure its line prints: the head's $12.34 from the billed
# line in hand plus the lanes mk waste plants ($5.00 + $1.25 + $0.00 = $6.25), the Codex lane
# counted and never priced and the lane closed with no cost unmeasured, so a floor: at least
# 12.34 + 6.25 = $18.59. The heads' total keeps the session figure under its own label.
fixture rtotl 200
mk waste "$REC" rtotl "$WORK/no-such-report.md" >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"LC","harness":"codex","class":"critic","model":"gpt-fixture-1"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LC","harness":"codex","exit_class":"completed","total_cost_usd":null,"cost_src":"codex-plan"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LN","exit_class":"killed","total_cost_usd":null}' >/dev/null
run boundary --run rtotl --from item1 --to item2 --disposition "d" --waste "w" --next "item2" --meter-line "$METER"
need_rc 0
need_out "run spend: at least \$18.59 of \$200.00"
WTL="$WORK/wt-totl.md"
run waste-table --run rtotl --no-meter --out "$WTL"
need_rc 0
need_eq "$(grep -c 'heads. total (shown sum) | \$16.56 = \$16.56' "$WTL")" "1" "the heads' total, relabelled"
need_eq "$(grep -c 'run total (recorded run spend) | at least \$18.59 · run_spend_usd of the phase-boundary at .*heads \$12.34 (1 metered) · lanes \$6.25' "$WTL")" "1" "the run total is the boundary's run spend, heads plus lanes"
need_eq "$(grep -c 'run total (recorded run spend).*predates' "$WTL")" "0" "nothing recorded after the boundary"
mk append "$REC" '{"event":"lane-closed","lane":"LZ","exit_class":"completed","total_cost_usd":2.0}' >/dev/null
run waste-table --run rtotl --no-meter --out "$WTL"
need_rc 0
need_eq "$(grep -c 'run total (recorded run spend) | at least \$18.59 .* it predates the lane close(s) or beat(s) recorded after it: LZ' "$WTL")" "1" "a lane closed after the boundary is named as outside the figure"
verdict "K06dde25c (must fire): the waste table's run total is the run spend the boundary recorded — the head's \$12.34 plus the lanes' \$6.25, a floor at \$18.59 — never the heads' session total, which keeps its \$16.56 under its own label; a lane closed after that boundary is named as outside the figure"

# ---- Kde41f01c: ledger --observation creates a missing record ----
RLED="$STORE/spawn-records/rledgernew.jsonl"; rm -f "$RLED"
run ledger --run rledgernew --observation "peer: fixture-peer" --dry-run
need_rc 0
need_nofile "$RLED"
run ledger --run rledgernew --observation "peer: fixture-peer"
need_rc 0
need_out "new record (created by this observation"
need_eq "$(mk lines "$RLED")" "1" "the record holds the one observation"
need_eq "$(mk field "$RLED" observation what)" "peer: fixture-peer" "the observation"
verdict "Kde41f01c (must fire): ledger --observation on a run with no record creates it with that one observation and says so, and a dry run writes nothing"

# ---- Kdcac6b59: a lock that cannot be worked opens anyway; contention still refuses ----
viewer_use vlockerr
LOCKERR=$(env AIMYTH_VIEWER_CMD="$WORK/bin/viewer-stub.sh" AIMYTH_VIEWER_ARGV="$VIEWER_ARGV" "$PY" - "$H" "rvwlockerr$SFX" <<'LOCKERR_END' 2>"$WORK/lockerr.err"
import errno, importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run = sys.argv[2]
ho.console_alive = lambda name, timeout=None: []
ho.console_starting = lambda name: None
ho.say = lambda line: sys.stderr.write(str(line) + "\n")
real = ho.fcntl.flock
out = {}
for name, code in (("enolck", errno.ENOLCK), ("ewouldblock", errno.EWOULDBLOCK)):
    def failing(fd, op, code=code):
        if op & ho.fcntl.LOCK_EX:
            raise OSError(code, "planted")
        return real(fd, op)
    ho.fcntl.flock = failing
    out[name] = ho.open_console_if_dark(run, viewer="terminal")
    ho.fcntl.flock = real
print(json.dumps(out, sort_keys=True))
LOCKERR_END
)
need_eq "$LOCKERR" '{"enolck": true, "ewouldblock": false}' "ENOLCK opens, EWOULDBLOCK refuses"
[ "$(grep -c 'cannot be locked (ENOLCK' "$WORK/lockerr.err")" -ge 1 ] || why="$why; the unworkable lock is not named on stderr"
need_eq "$(grep -c 'holds this run.s console claim' "$WORK/lockerr.err")" "1" "contention is named as contention"
need_eq "$(viewer_calls)" "1" "one window opened, by the ENOLCK call (the custom viewer stub is handed the command file alone)"
verdict "Kdcac6b59 (must fire): a planted ENOLCK from the console claim's lock is read as a lock that cannot be worked — said on stderr and the window opened anyway — while EWOULDBLOCK is still another opener's claim and opens nothing"

# ---- K6cf0c658: raise-envelope checks the top-up against the run's spend ----
fixture rraise 20
mk append "$REC" '{"event":"lane-open","lane":"LR","class":"builder","model":"opus"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"LR","exit_class":"completed","total_cost_usd":30.0}' >/dev/null
RLINES=$(mk lines "$REC")
run raise-envelope --run rraise --to 30 --reason "the owner's top-up" --meter-line "$METER"
need_rc 2
need_out "is at or below the run's spend \$42.34"
need_eq "$(mk lines "$REC")" "$RLINES" "nothing written"
run raise-envelope --run rraise --to 50 --reason "the owner's top-up" --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$REC" envelope envelope_usd)" "50.0" "the top-up above the run figure"
verdict "K6cf0c658 (must fire): a top-up between the head's own figure (12.34) and the run's spend with its lanes (42.34) is refused, and one above the run figure is written"

# ---- K5c5ab931: the tool lines carry the skill, subagent, url and query, and show line breaks ----
TTOOL=$("$PY" - <<'TOOLSCRIPT'
import json, os, re
sid = "sid-tools2"
path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])), sid + ".jsonl")
os.makedirs(os.path.dirname(path), exist_ok=True)
calls = [{"type": "tool_use", "name": "Skill", "input": {"skill": "reflect", "args": "--cross"}},
         {"type": "tool_use", "name": "Agent", "input": {"subagent_type": "critic", "description": "review the guard", "prompt": "a long prompt"}},
         {"type": "tool_use", "name": "WebFetch", "input": {"url": "https://example.org/a", "prompt": "summarise"}},
         {"type": "tool_use", "name": "WebSearch", "input": {"query": "hands-off supervisor"}},
         {"type": "tool_use", "name": "Bash", "input": {"command": "cd /tmp\necho two statements"}}]
recs = [{"type": "user", "timestamp": "2026-10-02T10:00:00Z", "message": {"role": "user", "content": [{"type": "text", "text": "go"}]}},
        {"type": "assistant", "timestamp": "2026-10-02T10:00:05Z", "message": {"role": "assistant", "model": "claude-fixture-1", "content": calls}}]
open(path, "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in recs))
print(path)
TOOLSCRIPT
)
EXT="$WORK/extract-tools2"
run extract-transcript --session sid-tools2 --out "$EXT"
need_rc 0
need_eq "$(grep -c '^- Skill: reflect$' "$EXT/turns.md")" "1" "the skill's name"
need_eq "$(grep -c '^- Agent: critic · review the guard$' "$EXT/turns.md")" "1" "the subagent type and its description"
need_eq "$(grep -c '^- WebFetch: https://example.org/a$' "$EXT/turns.md")" "1" "the url"
need_eq "$(grep -c '^- WebSearch: hands-off supervisor$' "$EXT/turns.md")" "1" "the query"
need_eq "$(grep -c '^- Bash: cd /tmp ⏎ echo two statements$' "$EXT/turns.md")" "1" "a line break shown as a separator"
verdict "K5c5ab931 (must fire): the extraction's tool lines carry a Skill call's skill, an Agent call's subagent type and description, WebFetch's url and WebSearch's query, and a two-line command shows its line break as a visible separator"

# ---- Kb65afcbe: the lanes' sandbox and fence denials reach the boundary ----
fixture rsandbox 200
mk append "$REC" '{"event":"lane-open","lane":"CXS","harness":"codex","class":"critic","model":"gpt-fixture-1"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"CXS","harness":"codex","exit_class":"completed","total_cost_usd":null,"cost_src":"codex-plan","denials":{"tool":0,"fence":1,"sandbox":2}}' >/dev/null
run boundary --run rsandbox --from item1 --to item2 --disposition "d" --waste "w" --next "item2" --meter-line "$METER"
need_rc 0
need_out "denials 0 · "
need_out "lane fence denials 1 · lane sandbox denials 2"
need_eq "$(mk field "$REC" phase-boundary sandbox_denials)" "2" "the field on the event"
need_eq "$(mk field "$REC" phase-boundary fence_denials)" "1" "the fence field on the event"
WSB="$WORK/wt-sandbox.md"
run waste-table --run rsandbox --no-meter --out "$WSB"
need_rc 0
need_eq "$(grep -c '^| lane sandbox denials · item1 → item2 .* | 2 · ' "$WSB")" "1" "the waste table's labelled row"
verdict "Kb65afcbe (must fire): a Codex lane's close carrying sandbox 2 and fence 1 makes the boundary report lane sandbox denials 2 and lane fence denials 1, each in its own labelled field and waste-table row beside the tool denials (0)"

# ---- Kbc9896e6: rendering a closed run's table leaves its stored copy alone ----
fixture rclosedwt 200
mk append "$REC" '{"event":"run-close","items":"done"}' >/dev/null
STOREDWT="$REALSTORE/spawn-records/rclosedwt-waste-table.md"
printf 'the stored table as the run wrote it\n' > "$STOREDWT"
WTSHA=$(sha_file "$STOREDWT")
run waste-table --run rclosedwt --no-meter
need_rc 0
need_eq "$(sha_file "$STOREDWT")" "$WTSHA" "the closed run's stored table is byte-identical"
need_out "# Waste table · run rclosedwt"
need_out "printed to standard output; the stored table"
fixture ropenwt 200
run waste-table --run ropenwt --no-meter
need_rc 0
need_file "$REALSTORE/spawn-records/ropenwt-waste-table.md"
verdict "Kbc9896e6 (must fire): waste-table without --out on a closed run prints the table and leaves the run's stored table byte-identical, while an open run's table is still written to the store (the control)"

# ---- K4b390bb7: no double-quoted verdict title carries a backtick ----
TITLES=$(grep -c '^verdict "[^"]*`' "$SRC")
need_eq "$TITLES" "0" "double-quoted verdict titles with a backtick in this suite"
printf 'verdict "a planted title with a `close` inside"\n' > "$WORK/planted-title.sh"
need_eq "$(grep -c '^verdict "[^"]*`' "$WORK/planted-title.sh")" "1" "the control: the planted title is found"
verdict "K4b390bb7 (must fire): no verdict title in this suite is double-quoted around a backtick, which the shell would run as a command (control: a planted one is found)"

# ---- K50271794: the console legs' run ids are this copy's own ----
need_eq "$(printf '%s' "$RSP" | grep -c "^rvwsp$SFX\$")" "1" "a console leg's run id carries the suffix"
"$PY" -c 'import time; time.sleep(30)' watch.py --run rvwsp &
SIBP=$!; sleep 1
need_eq "$(probe_alive "$RSP" rvwsp)" "0 1" "a sibling copy's console under the bare id is invisible to this copy's id (the control finds it)"
kill "$SIBP"; wait "$SIBP" 2>/dev/null || :
SFX2=$(printf '%s' "/tmp/handsoff-suite.AbC123" | sed 's|.*/||; s/^handsoff-suite\.//; s/[^A-Za-z0-9]//g')
need_eq "$SFX2" "AbC123" "the suffix is the temp directory's own random part"
verdict "K50271794 (must fire): the run ids of the legs that plant a console carry the suite's own suffix, so a console a sibling copy plants under the bare id is invisible to this copy's probe (the control sees it)"

# ---- K4443c15f: the by-hand line names the absolute interpreter ----
BYHAND=$("$PY" - "$H" <<'BYHAND_END'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
print(ho.by_hand_line("rbyhand"))
BYHAND_END
)
case $BYHAND in "$PYABS -B "*" watch --run rbyhand") : ;; *) why="$why; the by-hand line is not on the absolute interpreter: $BYHAND" ;; esac
case $BYHAND in python3\ *) why="$why; the by-hand line starts with a bare python3" ;; esac
verdict "K4443c15f (must fire): the by-hand console line starts with the absolute path of the interpreter running handsoff.py, never a bare python3"

# ---- D21 (c) and K86a774ca: the launch check waits for the whole first batch, open and progressing ----
LCH=$("$PY" -c 'import subprocess, sys
p = subprocess.Popen(["sleep", "120"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
print(p.pid)')
LCL=$("$PY" -c 'import subprocess, sys
p = subprocess.Popen(["sleep", "120"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
print(p.pid)')
batch_fixture() { # $1 run: a head start with a live pid, then helpers planted by the leg
  fixture "$1" 200
  mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-$1\",\"pid\":$LCH,\"model\":\"fixture-model\",\"effort\":\"max\"}" >/dev/null
}
lane_open() { # $1 lane, $2 seconds ago (the open), $3 harness word (claude|codex), $4 pid
  mk append "$REC" "$(printf '{"event":"lane-open","ts":"%s","lane":"%s","class":"builder","model":"opus","session_id":"sid-%s"%s}' "$(tsago "$2")" "$1" "$1" "$([ "$3" = codex ] && printf ',"harness":"codex"')")" >/dev/null
  mk append "$REC" "$(printf '{"event":"lane-spawned","ts":"%s","lane":"%s","session_id":"sid-%s","pid":%s,"wrapper_pid":%s}' "$(tsago "$2")" "$1" "$1" "$4" "$4")" >/dev/null
}
lane_transcript() { # $1 lane, $2 seconds ago of its last record, $3 'Z' to stamp in UTC
  "$PY" - "$1" "$2" "${3:-local}" <<'LANETX'
import json, os, sys, time
lane, ago, form = sys.argv[1], float(sys.argv[2]), sys.argv[3]
t = time.time() - ago
stamp = (time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t)) if form == "Z"
         else time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t)))
path = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], "lane-%s" % lane, "sid-%s.jsonl" % lane)
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w", encoding="utf-8").write(json.dumps({"type": "assistant", "timestamp": stamp, "message": {"role": "assistant", "content": [{"type": "text", "text": "working"}]}}) + "\n")
LANETX
}
batch_fixture rlb
lane_open T1 60 claude "$LCL"; lane_transcript T1 30
lane_open T2 60 codex "$LCL"
mk append "$REC" "$(printf '{"event":"lane-session","ts":"%s","lane":"T2","harness":"codex","session_id":"thread-t2","pid":%s}' "$(tsago 50)" "$LCL")" >/dev/null
lane_open T3 120 claude "$LCL"
mk append "$REC" '{"event":"lane-closed","lane":"T3","exit_class":"completed","total_cost_usd":1.0}' >/dev/null
lane_open X1 60 claude "$LCL"; lane_transcript X1 20
run launch-check --run rlb --lanes T1,T2,T3 --wait 0 --detach-safe
need_rc 0
need_out "launch-check: rlb STARTED CLEAN"
need_out "T1 progressing (transcript (timestamp) at "
need_out "T2 progressing (record lane-session at "
need_out "T3 done (closed completed at "
need_absent "X1"
batch_fixture rlbres
mk append "$REC" "{\"event\":\"run-resume\",\"session\":\"sid-rlbres\",\"pid\":$LCH,\"model\":\"fixture-model\"}" >/dev/null
lane_open T1 60 claude "$LCL"; lane_transcript T1 30
run launch-check --run rlbres --lanes T1 --wait 1 --poll-s 0.5 --detach-safe
need_rc 0
need_out "launch-check: rlbres STARTED CLEAN · run-resume at "
batch_fixture rlbsilent
lane_open T1 60 claude "$LCL"; lane_transcript T1 30
lane_open T2 60 claude "$LCL"
run launch-check --run rlbsilent --lanes T1,T2 --wait 2 --poll-s 0.5 --detach-safe
need_rc 1
need_out "launch-check: rlbsilent NOT CLEAN"
need_out "T2 silent (opened at "
need_out "not every planned helper is open and making progress within the 2 s deadline"
batch_fixture rlbmiss
lane_open T1 60 claude "$LCL"; lane_transcript T1 30
lane_open X1 60 claude "$LCL"; lane_transcript X1 30
run launch-check --run rlbmiss --lanes T1,T4 --wait 1 --poll-s 0.5 --detach-safe
need_rc 1
need_out "T4 missing (no attempt since the head started)"
fixture rlbstale 200
lane_open T1 600 claude "$LCL"; lane_transcript T1 30
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-rlbstale\",\"pid\":$LCH,\"model\":\"fixture-model\"}" >/dev/null
run launch-check --run rlbstale --lanes T1 --wait 1 --poll-s 0.5 --detach-safe
need_rc 1
need_out "T1 missing (no attempt since the head started; an attempt before that head is not this launch's)"
batch_fixture rlbbad
lane_open T1 60 claude "$LCL"; lane_transcript T1 30
printf '{"event": "lane-open", "lane": "T9", torn\n' >> "$REC"
run launch-check --run rlbbad --lanes T1 --wait 1 --poll-s 0.5 --detach-safe
need_rc 1
need_out "the record has 1 unparseable line(s), and a malformed record never certifies a clean start"
batch_fixture rlbnull
lane_open T1 60 claude "$LCL"; lane_transcript T1 30
printf 'null\n' >> "$REC"
run launch-check --run rlbnull --lanes T1 --wait 1 --poll-s 0.5 --detach-safe
need_rc 1
need_absent "Traceback"
need_out "NOT CLEAN"
batch_fixture rlbfail
lane_open T1 60 claude "$LCL"; lane_transcript T1 30
lane_open T2 60 claude "$LCL"
mk append "$REC" '{"event":"lane-closed","lane":"T2","exit_class":"error","total_cost_usd":0.5}' >/dev/null
LT0=$(clock_f)
run launch-check --run rlbfail --lanes T1,T2 --wait 30 --poll-s 0.5 --detach-safe
need_rc 1
need_out "T2 failed (closed error at "
need_eq "$(span_ok "$LT0" "$(clock_f)" 10)" "ok" "a failed helper ends the check at once, never at the deadline"
run launch-check --run rlbfail --lanes "," --wait 0 --detach-safe
need_rc 2
need_out "--lanes names no helper"
run launch-check --run rlbfail --lanes T1,T1 --wait 0 --detach-safe
need_rc 2
need_out "--lanes names T1 twice"
batch_fixture rlbpid
lane_open T1 60 claude '"not-a-pid"'; lane_transcript T1 30
lane_open T2 60 claude '"not-a-pid"'
run launch-check --run rlbpid --lanes T1,T2 --wait 1 --poll-s 0.5 --detach-safe
need_rc 1
need_out "T1 progressing (transcript (timestamp) at "
need_out "liveness unverifiable"
need_out "T2 unverified (no activity since its open"
batch_fixture rlbtz
lane_open T1 60 claude "$LCL"; lane_transcript T1 30 Z
lane_open T2 60 claude "$LCL"; lane_transcript T2 90 Z
run launch-check --run rlbtz --lanes T1,T2 --wait 1 --poll-s 0.5 --detach-safe
need_rc 1
need_out "T1 progressing"
need_out "T2 silent"
verdict "D21 (c) and K86a774ca (must fire): launch-check --lanes certifies STARTED CLEAN only when every planned helper's latest attempt since the head started is progressing (a transcript record or a record event after its open) or done, unrelated helpers ignored; a silent or missing helper is NOT CLEAN at the deadline, a stale attempt is missing, a malformed or null record line never certifies, a failed helper ends the check at once, an empty or repeated list is refused (exit 2), an unusable pid relies on activity alone, timestamps in another offset are compared as instants, and the head's own run-resume (its first act) moves the anchor rather than failing the batch"

# G14x on the certificate itself (register 2026-10-15 01:33 c, the 28 October gap): the same first
# batch, ready and progressing, is NOT CLEAN on a start with no readable model; the controls are
# the certificate above, and the run-resume that reads its model from the head-successor.
fixture rlbmodel 200
mk append "$REC" "{\"event\":\"run-resume\",\"session\":\"sid-unnamed-head\",\"head\":\"opus at max in free text\",\"detail\":\"its first act\",\"pid\":$LCH}" >/dev/null
lane_open T4 60 claude "$LCL"; lane_transcript T4 30
run launch-check --run rlbmodel --lanes T4 --wait 0 --detach-safe
need_rc 1
need_out "launch-check: rlbmodel NOT CLEAN"
need_out "carries no readable model"
need_absent "STARTED CLEAN"
batch_fixture rlbmodel2
mk append "$REC" "{\"event\":\"run-resume\",\"session\":\"sid-rlbmodel2\",\"head\":\"opus at max in free text\",\"detail\":\"its first act\",\"pid\":$LCH}" >/dev/null
lane_open T5 60 claude "$LCL"; lane_transcript T5 30
run launch-check --run rlbmodel2 --lanes T5 --wait 0 --detach-safe
need_rc 0
need_out "launch-check: rlbmodel2 STARTED CLEAN"
need_out "model fixture-model effort max"
verdict "G14x (fails on old): launch-check --lanes never certifies STARTED CLEAN on a start with no readable model, and a head's first run-resume reads the model of the head-successor that started it"

# ---- K8f4055c6 with Kbf3c2f75 (G1): the ack digest, and the close's final recheck ----
fixture rdig 200
DIGF="$WORK/digest-decisions.md"
printf '# decisions\n- line one\n' > "$DIGF"
run decisions-read --run rdig --decisions-file "$DIGF"
need_rc 0
need_out "decisions-read: "
need_out "the whole file: the record carries no accepted ack with a digest"
need_out "digest: $(sha_file "$DIGF")"
D1=$(sha_file "$DIGF")
DLINES0=$(mk lines "$REC")
run gate --run rdig --to item1 --meter-line "$METER" --decisions-file "$DIGF" --ack "read line one"
need_rc 6
need_out "the ack carries no --ack-digest"
need_eq "$(mk lines "$REC")" "$DLINES0" "a digest-less ack records nothing"
printf -- '- line two, appended after the read\n' >> "$DIGF"
run gate --run rdig --to item1 --meter-line "$METER" --decisions-file "$DIGF" --ack "read line one" --ack-digest "$D1"
need_rc 6
need_out "the lines appended since that read"
need_out "| - line two, appended after the read"
need_eq "$(mk lines "$REC")" "$DLINES0" "a stale ack records nothing"
D2=$(sha_file "$DIGF")
run gate --run rdig --to item1 --meter-line "$METER" --decisions-file "$DIGF" --ack "read lines one and two" --ack-digest "$D2"
need_rc 0
need_eq "$("$PY" -c 'import json, sys; e = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]; a = [x for x in e if x.get("event") == "observation" and str(x.get("what", "")).startswith("ack: ")]; print(a[-1].get("digest") if a else "<no ack>")' "$REC")" "$D2" "the accepted ack records the digest"
run gate --run rdig --to item2 --meter-line "$METER" --decisions-file "$DIGF" --ack-digest "$D2"
need_rc 2
need_out "--ack-digest was given without --ack"
run gate --run rdig --to item2 --meter-line "$METER" --decisions-file "$DIGF" --ack "x" --ack-digest "$(printf '%s' "$D2" | cut -c1-12)"
need_rc 2
need_out "is not a whole sha256"
# rdig's gates bound its file, so "no decisions file" takes a run that names none.
fixture rdigu 200
run gate --run rdigu --to item2 --meter-line "$METER" --ack "x" --ack-digest "$D2"
need_rc 2
need_out "--ack-digest was given without --decisions-file"
verdict "K8f4055c6 and Kbf3c2f75 (G1, must fire): decisions-read prints the unacknowledged lines and the file's digest; an ack with no digest, or with a digest the file has grown past since its read (the appended line printed), holds the gate (exit 6) and records nothing; the fresh digest passes and is recorded; a digest with no ack, with no decisions file, or cut to a prefix is refused (exit 2)"

GCOPY="$WORK/g1copy"
rm -rf "$GCOPY"; mkdir -p "$GCOPY"
cp "$H" "$GCOPY/handsoff.py"
# CR-A3-1 H1 (spec), E1: the copied supervisor still needs its shared record-lock module.
cp "$LANE_PY" "$GCOPY/lane.py"
cat > "$GCOPY/fable-share.py" <<'APPENDMETER'
"""A stand-in meter for the close's final recheck: on its first run it appends one line to the
decisions file G1_APPEND names (an owner writing while the close meters), then prints a billed
line, as the real meter does."""
import os, sys
marker = os.environ.get("G1_APPEND")
if marker and not os.path.exists(marker + ".done"):
    with open(marker, "a", encoding="utf-8") as handle:
        handle.write("- an owner line written while the close was metering\n")
    open(marker + ".done", "w").close()
print("billed (list 2001-01-01) · head $1.00 · lanes $0.00 · session $1.00 · rewrites 0 ($0.00) · tool uses/call head 1.00 lanes 0.00 · delegation multi (owner) · lanes 0 (reasons: (a)×0 (b)×0 (c)×0 (d)×0, none×0) · metered 1 of 1")
APPENDMETER
fixture rfinal 200
FINF="$WORK/final-decisions.md"
printf '# decisions\n- the checklist stays\n' > "$FINF"
F1=$(sha_file "$FINF")
FLINES=$(mk lines "$REC")
RC=0
env G1_APPEND="$FINF" "$PY" -B "$GCOPY/handsoff.py" close --run rfinal --items "fixture items" --decisions-file "$FINF" \
    --ack "read the checklist line" --ack-digest "$F1" >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" > "$WORK/both"
need_rc 6
need_out "arrived while the close was preparing"
need_out "| - an owner line written while the close was metering"
need_eq "$(mk count "$REC" run-close)" "0" "no run-close: the same call held"
need_eq "$(mk lines "$REC")" "$((FLINES + 1))" "only the call's own ack is on the record"
F2=$(sha_file "$FINF")
RC=0
env G1_APPEND="$FINF" "$PY" -B "$GCOPY/handsoff.py" close --run rfinal --items "fixture items" --decisions-file "$FINF" \
    --ack "read both lines" --ack-digest "$F2" >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" > "$WORK/both"
need_rc 0
need_eq "$(mk field "$REC" run-close decisions_digest)" "$F2" "the run-close records the content it acknowledged"
case $(mk field "$REC" run-close decisions_cutoff) in 20*) : ;; *) why="$why; no cutoff on the run-close" ;; esac
need_out "unchanged at the cutoff"
rm -rf "$GCOPY"
verdict "K8f4055c6 (G1 final recheck, the owner's provisional choice of 2026-10-10, must fire): an owner line appended to the decisions file while the close meters holds that same close (exit 6, no run-close, the line printed); with the content unchanged the close goes through and its run-close records the digest it acknowledged and the cutoff after which nothing is covered"

# ---- Ked83406c (G3): the console confirm hold, on a probe whose exit status is read ----
RHOLD="rvwhold$SFX"
fixture "$RHOLD" 200
viewer_use vhold
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1 STUB_CONSOLE_LIFE_S=1"
run open-console --run "$RHOLD"
need_rc 0
need_out "viewer: console started (pid "
need_out "but exited within"
need_out "run by hand: $PYABS -B"
need_absent "Terminal window opened"
need_eq "$(viewer_calls)" "2" "not retried: one open call (-g and the command file)"
RHOLD2="rvwhold2$SFX"
fixture "$RHOLD2" 200
viewer_use vhold2
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run "$RHOLD2"
need_rc 0
need_out "(first seen at "
need_out "still alive after the 3 s hold)"
kill "$(cat "$VIEWER_ARGV.pid")" 2>/dev/null || :
G3P=$("$PY" - "$H" "$WORK" <<'G3PROBE'
import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
work = sys.argv[2]
os.environ["PATH"] = os.path.join(work, "pgrepexit") + os.pathsep + os.environ.get("PATH", "")
out = {}
def scripted(name, *calls):
    state = os.path.join(work, "pgrep-g3-%s" % name)
    if os.path.exists(state):
        os.remove(state)
    for key in list(os.environ):
        if key.startswith(("PGREP_OUT_", "PGREP_RC_")):
            del os.environ[key]
    os.environ["PGREP_STATE"] = state
    for i, (text, rc) in enumerate(calls, 1):
        os.environ["PGREP_OUT_%d" % i] = text
        os.environ["PGREP_RC_%d" % i] = str(rc)
scripted("exit3", ("4242", 3))
out["probe_exit3"] = ho.console_probe("rg3")[0]
scripted("hold3", ("4242", 3))
out["hold_exit3"] = ho.hold_console("rg3", [4242], hold=0)[0]
scripted("gone", ("", 1))
out["hold_gone"] = ho.hold_console("rg3", [4242], hold=0)[0]
scripted("swap", ("5151", 0))
out["hold_swap"] = ho.hold_console("rg3", [4242], hold=0)[0]
scripted("same", ("4242", 0))
out["hold_same"] = ho.hold_console("rg3", [4242], hold=0)[0]
scripted("wait3", ("4242", 3))
pids = ho.wait_console("rg3", 1.0, 0.25)[0]
out["wait_exit3"] = list(pids)
print(json.dumps(out, sort_keys=True))
G3PROBE
)
need_eq "$G3P" '{"hold_exit3": "unverified", "hold_gone": "exited", "hold_same": "confirmed", "hold_swap": "exited", "probe_exit3": "unverified", "wait_exit3": []}' "the probe's status read at every step"
verdict "Ked83406c (G3 with critic finding 8, must fire): a console that exits within the 3 s hold after its first sighting is reported started-then-exited with the by-hand line and not retried, a live one is confirmed with both times; a pgrep that exits 3 with a pid on its output never confirms or sights, a console gone or replaced after the hold is no confirmation, and the same pid seen by a successful probe is"

# ---- Kd748b2f0: a disposition's head decisions must be on the record ----
fixture rdref 200
run decision --run rdref --phase 1 --what "item1 runs three builders" --grant "G2"
need_rc 0
need_out "decision: recorded HD-1"
run decision --run rdref --phase 1 --what "an unrelated decision" --grant "G3"
need_rc 0
need_out "recorded HD-2"
run boundary --run rdref --from item1 --to item2 --disposition "item1 done under HD-1 and HD-7; the owner's D19" \
    --waste "w" --next "item2" --meter-line "$METER"
need_rc 0
need_out "warn: the disposition names head decision(s) with no decision event on the record: HD-7"
need_eq "$(mk field "$REC" phase-boundary decision_refs)" '{"named": ["HD-1", "HD-7"], "missing": ["HD-7"], "ambiguous": [], "unverifiable": null}' "the references on the event"
run boundary --run rdref --from item2 --to item3 --disposition "item2 done under HD-1" --waste "w" --next "item3" --meter-line "$METER"
need_rc 0
need_absent "warn: the disposition"
run boundary --run rdref --from item3 --to item4 --disposition "item3 done on the owner's D19 and D21 (c)" --waste "w" --next "item4" --meter-line "$METER"
need_rc 0
need_absent "warn: the disposition"
need_eq "$(mk field "$REC" phase-boundary decision_refs)" "<no key decision_refs>" "a disposition naming no head decision carries no references"
verdict "Kd748b2f0 (must fire, the owner's provisional choice of explicit references): decision assigns HD-<n>; a boundary whose disposition names HD-7 with no decision event warns despite an unrelated decision on the record, its exit unchanged and the references on its event; a named decision that is recorded and an owner-only disposition warn of nothing"

# ---- K594ef68f: the vault root's untracked entries are listed before a checkpoint commit ----
fixture rroot 200
mkdir -p "$VAULT/docs-b4h"
printf 'tracked\n' > "$VAULT/docs-b4h/a.md"
git -C "$VAULT" add docs-b4h/a.md
git -C "$VAULT" commit -q -m "fixture: a tracked folder"
printf 'a stray download\n' > "$VAULT/stray-b4h.txt"
mkdir -p "$VAULT/junkdir-b4h"
printf 'x\n' > "$VAULT/junkdir-b4h/x.txt"
printf 'nested\n' > "$VAULT/docs-b4h/new.md"
printf 'a tracked change\n' >> "$VAULT/README.md"
RUNENV="PATH=$WORK/gitfail:$PATH"
run boundary --run rroot --from item1 --to item2 --disposition "d" --waste "w" --next "item2" --meter-line "$METER" \
    --commit "fixture: the root listing, unverified"
need_rc 0
need_out "untracked at the vault root: unverified (git ls-files exit 128"
run boundary --run rroot --from item2 --to item3 --disposition "d" --waste "w" --next "item3" --meter-line "$METER" \
    --commit "fixture: the root listing"
need_rc 0
need_eq "$(mk field "$REC" phase-boundary root_untracked)" "[]" "everything was committed by the first boundary (the listing came first)"
printf 'another stray\n' > "$VAULT/stray2-b4h.txt"
mkdir -p "$VAULT/junk2-b4h"; printf 'y\n' > "$VAULT/junk2-b4h/y.txt"
printf 'nested two\n' > "$VAULT/docs-b4h/new2.md"
run boundary --run rroot --from item3 --to item4 --disposition "d" --waste "w" --next "item4" --meter-line "$METER" \
    --commit "fixture: the root listing again"
need_rc 0
need_out "untracked at the vault root (advisory: the commit takes them with the rest): junk2-b4h/, stray2-b4h.txt"
need_eq "$(mk field "$REC" phase-boundary root_untracked)" '["junk2-b4h/", "stray2-b4h.txt"]' "the listing on the event"
need_absent "docs-b4h/new2.md"
verdict "K594ef68f (must fire): before a checkpoint commit the boundary lists the untracked entries at the vault root — a stray file and an untracked folder — and not a new file inside a tracked folder or a tracked file's change, records the list on its event, and says unverified when git cannot list them, the commit going ahead either way"

# ---- Kcdbad8e4: one hand-off directory default in handsoff.py and the hooks ----
mkdir -p "$WORK/home-nosym"
STATEDEF=$(env -u AIMYTH_STATE_DIR HOME="$WORK/home-nosym" "$PY" - "$H" "$HOOKS_DIR" <<'STATEDEF_END'
import importlib.util, os, sys
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
ho = load("ho", sys.argv[1])
found = {"handsoff.py": ho.state_dir()}
for hook in ("precompact-checkpoint.py", "handsoff-gate.py", "head-fence.py"):
    found[hook] = load(hook.replace("-", "_").replace(".py", ""), os.path.join(sys.argv[2], hook)).state_dir()
first = found["handsoff.py"]
print("same" if all(v == first for v in found.values()) else "split: " + "; ".join("%s %s" % kv for kv in sorted(found.items())))
os.environ["AIMYTH_STATE_DIR"] = "/tmp/fixture-state-override"
found = [ho.state_dir()] + [load(h + "2", os.path.join(sys.argv[2], h)).state_dir() for h in ("precompact-checkpoint.py", "handsoff-gate.py", "head-fence.py")]
print("override same" if len(set(found)) == 1 and found[0] == "/tmp/fixture-state-override" else "override split: %s" % found)
STATEDEF_END
)
need_eq "$(printf '%s\n' "$STATEDEF" | sed -n 1p)" "same" "with no alias symlink and no override every component resolves one hand-off directory"
need_eq "$(printf '%s\n' "$STATEDEF" | sed -n 2p)" "override same" "an explicit AIMYTH_STATE_DIR is read alike (the paired control)"
verdict "Kcdbad8e4 (must fire against the hooks before their diff): handsoff.py and the checkpoint, gate and fence hooks resolve one default hand-off directory in a home with no alias symlink and no override, and an explicit AIMYTH_STATE_DIR alike"
kill "$LCH" "$LCL" 2>/dev/null || :
# ---- help and docstring (2026-10-10): the new verbs and flags are parsed and documented ----
run disarm --help
need_rc 0
need_out "--dry-run"
run decisions-read --help
need_rc 0
need_out "--decisions-file"
run launch-check --help
need_rc 0
need_out "--lanes"
run grants --help
need_rc 0
need_out "--add-grant"
need_out "--add-write"
need_out "--replace"
need_out "--max-successors"
run successor --help
need_rc 0
need_out "--seed-pid"
run reflect-inputs --help
need_rc 0
need_out "--transcript"
run gate --help
need_rc 0
need_out "--ack-digest"
DOCB4=$("$PY" -c 'import ast, sys
d = ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read()))
new = ("decisions-read", "--ack-digest", "--seed-pid", "--add-grant", "--add-write", "--replace", "max_successors", "disarm", "--lanes", "HD-<n>", "--transcript", "stages/<run>/reflect", "STARTED CLEAN", "CONSOLE_CONFIRM_HOLD_S")
old = ("has an mtime later than that reference", "A call naming\nneither --grant nor --write")
print("%d %d" % (sum(1 for s in new if s in d), sum(d.count(s) for s in old)))' "$H")
need_eq "$DOCB4" "14 0" "the fourteen new phrases in the module docstring and the two retired ones gone"
verdict "help and docstring (2026-10-10, must fire): disarm, decisions-read, launch-check --lanes, the grant forms with --max-successors, successor --seed-pid, reflect-inputs --transcript and gate --ack-digest are parsed, and the module docstring names them, the retired mtime rule and the old shrink-guard wording gone"

# -------------------------- the fold of the review of the held build (2026-10-11) ---------
# HF-BEGIN. These legs need only the plumbing above the run-open legs, so a run against an older
# handsoff.py can take them alone (the fail-on-old run). One leg per finding of the review of the
# held build that this fold owns (finding 8, the install README, is not a code finding); every leg
# fails against the build before the fold, while the controls inside each — an unchanged close,
# the head's own run-resume, a verified replacement, a line before the start, a positive
# remainder, a real call — hold on both.
hf_tsago() { "$PY" -c 'import sys, time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - float(sys.argv[1]))))' "$1"; }
hf_wait_log() { # $1 file, $2 fixed string, $3 tries of 0.5 s: a detached starter writes late
  i=0
  while [ "$i" -lt "$3" ]; do
    if [ -f "$1" ] && grep -q -F -- "$2" "$1"; then return 0; fi
    sleep 0.5; i=$((i + 1))
  done
  why="$why; no '$2' in $1 within $3 half-seconds"; return 1
}
hf_raw() { # $1 record, $2 run, $3 JSON event: appended as given with ts and run, whatever the record holds (mk append cannot read past a torn line)
  "$PY" -c 'import json, sys, time
ev = json.loads(sys.argv[3])
ev.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
ev.setdefault("run", sys.argv[2])
with open(sys.argv[1], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(ev) + "\n")' "$1" "$2" "$3"
}
hf_get() { # $1 record, $2 kind, $3 key, $4 occurrence (1-based, 0 the last); unparseable lines skipped
  "$PY" -c 'import json, sys
found = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict) and e.get("event") == sys.argv[2]:
        found.append(e)
k = int(sys.argv[4])
if not found or k > len(found):
    print("<no %s #%d>" % (sys.argv[2], k))
else:
    v = found[k - 1 if k else -1].get(sys.argv[3], "<no key %s>" % sys.argv[3])
    print(v if isinstance(v, str) else json.dumps(v))' "$1" "$2" "$3" "$4"
}
hf_obs() { # $1 record: every head-exited observation as class:progress, in order; unparseable lines skipped
  "$PY" -c 'import json, sys
seen = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict) and e.get("event") == "observation" and e.get("what") == "head exited":
        seen.append("%s:%s" % (e.get("exit_class"), e.get("progress", "-")))
print(" ".join(seen))' "$1"
}
hf_stubs() { if [ -f "$WORK/stub-$1.count" ]; then cat "$WORK/stub-$1.count"; else echo 0; fi; }
hf_sum() { # $1 directory, $2 fixed string: its hits summed over every file under the directory
  grep -r -c -F -- "$2" "$1" | awk -F: '{s += $NF} END {print s + 0}'
}

# Finding 1 (HIGH; G1, K8f4055c6): the close's recheck cursor is the snapshot its decisions
# channel checked. The owner's relay lands after the call's read, before its ack or after it, and
# must hold that same close; with nothing appended the close goes through, its own ack left out
# of the recheck (the control).
hf_close() { # $1 run, $2 where the relay lands (none, before-ack, after-ack): one close in process, `rc N` last
  "$PY" - "$H" "$1" "$2" "$METER" <<'HFCLOSE'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, race, meter = sys.argv[2], sys.argv[3], sys.argv[4]
path = ho.record_path(run)


def relay():
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": ho.now(), "run": run, "event": "observation", "phase": "",
                                 "what": "AUTHOR ruling: HF-RELAY the checklist changes before the close"}) + "\n")


real_pending, real_hold = ho.decisions_pending, ho.decisions_hold


def pending(*args, **kwargs):
    if race == "before-ack":
        relay()
    return real_pending(*args, **kwargs)


def hold(*args, **kwargs):
    result = real_hold(*args, **kwargs)
    if race == "after-ack":
        relay()
    return result


ho.decisions_pending, ho.decisions_hold = pending, hold
sys.argv = ["handsoff.py", "close", "--run", run, "--items", "fixture items", "--meter-line", meter,
            "--ack", "read the relays on the record"]
try:
    ho.main()
    code = 0
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
sys.stdout.flush()
print("rc %d" % code)
HFCLOSE
}
for hf_case in none before-ack after-ack; do
  fixture "hfclose-$hf_case" 200
  hf_close "hfclose-$hf_case" "$hf_case" >"$WORK/hfclose-$hf_case.out" 2>&1
done
R="$STORE/spawn-records/hfclose-none.jsonl"
need_eq "$(grep '^rc ' "$WORK/hfclose-none.out")" "rc 0" "the unchanged close"
need_eq "$(mk count "$R" run-close)" "1" "the unchanged close writes its run-close"
for hf_case in before-ack after-ack; do
  R="$STORE/spawn-records/hfclose-$hf_case.jsonl"
  need_eq "$(grep '^rc ' "$WORK/hfclose-$hf_case.out")" "rc 6" "exit with the relay $hf_case"
  need_eq "$(mk count "$R" run-close)" "0" "no run-close with the relay $hf_case"
  grep -q -F "arrived while the close was preparing" "$WORK/hfclose-$hf_case.out" || why="$why; no hold line with the relay $hf_case"
  grep -q -F "HF-RELAY the checklist changes" "$WORK/hfclose-$hf_case.out" || why="$why; the held close does not print the relay ($hf_case)"
done
verdict "close (fails on old; the review of 2026-10-11, finding 1, G1): an AUTHOR relay appended after the call's read, before its ack or after it, holds that same close (exit 6, no run-close, the relay printed), the recheck's cursor being the snapshot the decisions channel checked; an unchanged record closes (the control)"

# Finding 2 (MEDIUM; D21 (c), K86a774ca): the first batch's wait keeps the head start's terminal
# states and holds to one head process. Each case confirms a live head with one silent helper; at
# the check's first re-read the record gains the case's events and the helper's activity: a
# run-close; a replacement start whose identity cannot be verified (an unreadable timestamp, no
# pid, a reused pid, an age the probe cannot read); and the two controls, the head's own
# run-resume (the same process) and a replacement whose identity is verified.
hf_launch() { # $1 run, $2 case, $3 the --wait: one launch-check --lanes T1 in process, `planted …` and `rc N` last
  "$PY" - "$H" "$1" "$2" "$3" <<'HFLAUNCH'
import importlib.util, json, os, subprocess, sys, time
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, case, wait = sys.argv[2], sys.argv[3], sys.argv[4]
path = ho.record_path(run)


def sleeper():
    return subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)


def stamp(ago=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - ago))


def add(ev):
    ev.setdefault("ts", stamp())
    ev["run"] = run
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev) + "\n")


def helper(ago):
    sid = "sid-%s-T1" % run
    add({"event": "lane-open", "ts": stamp(ago), "lane": "T1", "class": "builder", "model": "opus",
         "session_id": sid})
    add({"event": "lane-spawned", "ts": stamp(ago), "lane": "T1", "session_id": sid,
         "pid": lane.pid, "wrapper_pid": lane.pid})


def activity():
    folder = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], "lane-%s" % run)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "sid-%s-T1.jsonl" % run), "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": stamp(),
                                 "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": "working"}]}}) + "\n")


def plant():
    sid = "sid-%s" % run
    if case == "close":
        add({"event": "run-close", "items": "closed while the check waited"})
    elif case == "badts":
        add({"event": "head-resumed", "ts": "not a time", "session_id": sid, "pid": other.pid,
             "model": "fixture-model"})
    elif case == "nopid":
        add({"event": "head-resumed", "session_id": sid, "pid": None, "model": "fixture-model"})
    elif case == "reused":
        add({"event": "head-successor", "ts": stamp(3600), "session_id": sid + "-b",
             "pid": other.pid, "model": "fixture-model"})
    elif case in ("noage", "verified"):
        add({"event": "head-resumed", "session_id": sid, "pid": other.pid, "model": "fixture-model"})
    elif case == "sameproc":
        add({"event": "run-resume", "session": sid, "head": "fixture head", "detail": "its first act",
             "pid": head.pid, "pid_src": "parent-walk"})
    if case != "close":
        helper(3)   # the helper's attempt after the newer start, which is that start's batch
    activity()


head, other, lane = sleeper(), sleeper(), sleeper()
state = {"lanes": False, "planted": False}
code = None
try:
    add({"event": "head-successor", "session_id": "sid-%s" % run, "pid": head.pid,
         "model": "fixture-model", "effort": "max"})
    helper(5)
    real_read, real_lanes, real_age = ho.read_record, ho.launch_lanes, ho.process_age_s

    def lanes_entered(*args, **kwargs):
        state["lanes"] = True
        return real_lanes(*args, **kwargs)

    def read(p, *args, **kwargs):
        if state["lanes"] and not state["planted"] and p == path:
            state["planted"] = True
            plant()
        return real_read(p, *args, **kwargs)

    def age(pid, *args, **kwargs):
        if case == "noage" and pid == other.pid:
            return None
        return real_age(pid, *args, **kwargs)

    ho.read_record, ho.launch_lanes, ho.process_age_s = read, lanes_entered, age
    sys.argv = ["handsoff.py", "launch-check", "--run", run, "--lanes", "T1", "--wait", wait,
                "--poll-s", "0.3", "--detach-safe"]
    try:
        ho.main()
        code = 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
finally:
    for proc in (head, other, lane):
        proc.kill()
        proc.wait()
sys.stdout.flush()
print("planted %s" % state["planted"])
print("rc %s" % code)
HFLAUNCH
}
for hf_case in close badts nopid reused sameproc verified; do
  fixture "hflaunch-$hf_case" 200
  hf_launch "hflaunch-$hf_case" "$hf_case" 8 >"$WORK/hflaunch-$hf_case.out" 2>&1
done
fixture hflaunch-noage 200
hf_launch hflaunch-noage noage 3 >"$WORK/hflaunch-noage.out" 2>&1
for hf_case in close badts nopid reused noage sameproc verified; do
  grep -q -F "planted True" "$WORK/hflaunch-$hf_case.out" || why="$why; the $hf_case events never arrived during the wait (the leg's premise)"
done
for hf_case in close badts nopid reused noage; do
  need_eq "$(grep '^rc ' "$WORK/hflaunch-$hf_case.out")" "rc 1" "exit ($hf_case)"
  grep -q -F "NOT CLEAN" "$WORK/hflaunch-$hf_case.out" || why="$why; no NOT CLEAN line ($hf_case)"
  if grep -q -F "STARTED CLEAN" "$WORK/hflaunch-$hf_case.out"; then why="$why; certified ($hf_case)"; fi
done
grep -q -F "but the run closed (run-close at " "$WORK/hflaunch-close.out" || why="$why; the close during the wait is not named"
grep -q -F "could not be confirmed: pid identity unverifiable: " "$WORK/hflaunch-badts.out" || why="$why; the unreadable timestamp is not named"
grep -q -F "names no usable pid" "$WORK/hflaunch-nopid.out" || why="$why; the pid-less replacement is not named"
grep -q -F "a reused pid, not that head" "$WORK/hflaunch-reused.out" || why="$why; the reused pid is not named"
grep -q -F "its identity was not verified within the 3 s deadline" "$WORK/hflaunch-noage.out" || why="$why; the unverified replacement is not named at the deadline"
for hf_case in sameproc verified; do
  need_eq "$(grep '^rc ' "$WORK/hflaunch-$hf_case.out")" "rc 0" "exit ($hf_case, a control)"
  grep -q -F "STARTED CLEAN" "$WORK/hflaunch-$hf_case.out" || why="$why; the control $hf_case is not certified"
  grep -q -F "T1 progressing" "$WORK/hflaunch-$hf_case.out" || why="$why; the control $hf_case does not read the helper's activity"
done
verdict "launch-check --lanes (fails on old; the review of 2026-10-11, finding 2, D21 (c)): a run-close arriving during the first batch's wait is NOT CLEAN; a replacement head start with an unreadable timestamp, no pid, a reused pid or an age that cannot be read never certifies; the head's own run-resume by the same process and a replacement whose identity is verified still certify (the controls)"

# Finding 3 (MEDIUM; the repeat-stop guard's malformed-line evidence, D32 (4)): a line that cannot
# be read, written after the head's start and before a supervisor attached, lies inside that
# head's window, so its stop reads unknown and cannot fire, while the later heads' windows open
# after it and their pair still fires. The control puts the line before the start: the guard
# stays in force and the first pair fires. A unit part places lines on planted records.
hf_attach() { # $1 run, $2 extra env words: a supervisor attached to pid 999999, already gone, its stop classified off a completed .out
  printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"done without a hand-off"}' > "$WORK/$1.out"
  HFRC=0
  env STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000 $2 AIMYTH_VIEWER_ARGV="$WORK/viewer-$1.argv" "$PY" -B "$H" _supervise --run "$1" \
      --pid 999999 --session "sid-$1" --out "$WORK/$1.out" --harness-bin "$WORK/bin/stubhead" \
      --handoff "$WORK/handoffs/$1-handoff.md" --meter-line "$METER" --tick-s 1 --wait-s 2 \
      >"$WORK/$1.log" 2>&1 || HFRC=$?
  printf '%s\n' "$HFRC" > "$WORK/$1.rc"
}
HF_ATTACHED='{"event":"run-resume","session":"sid-%s","head":"fixture head","detail":"the attached head","pid":999999,"pid_src":"arg"}'
fixture hfmal 200
hf_raw "$REC" hfmal "$(printf "$HF_ATTACHED" hfmal)"
printf '%s\n' '{"event":"phase-boundary","from":"torn after the start' >> "$REC"
hf_attach hfmal "STUB_MODES=complete,error STUB_PROGRESS=none,none STUB_N=2"
R="$STORE/spawn-records/hfmal.jsonl"
need_eq "$(hf_obs "$R")" "completed:unknown completed:no error:no" "the recorded verdicts (after the start)"
case $(hf_get "$R" observation progress_note 1) in *"unparseable record line(s) lie inside this head's window"*) : ;; *) why="$why; the unknown does not name the line inside the window: $(hf_get "$R" observation progress_note 1)" ;; esac
need_eq "$(hf_stubs hfmal)" "2" "two real starts after the attached head"
need_eq "$(cat "$WORK/hfmal.rc") $(hf_get "$R" successor-aborted reason 0)" "1 repeat-stop" "the later pair still fires"
fixture hfmal2 200
printf '%s\n' '{"event":"phase-boundary","from":"torn before the start' >> "$REC"
hf_raw "$REC" hfmal2 "$(printf "$HF_ATTACHED" hfmal2)"
hf_attach hfmal2 "STUB_MODES=complete STUB_PROGRESS=none STUB_N=1"
R="$STORE/spawn-records/hfmal2.jsonl"
need_eq "$(hf_obs "$R")" "completed:no completed:no" "the recorded verdicts (before the start, the control)"
need_eq "$(hf_stubs hfmal2)" "1" "one real start (the control)"
need_eq "$(cat "$WORK/hfmal2.rc") $(hf_get "$R" successor-aborted reason 0)" "1 repeat-stop" "the first pair fires (the control)"
HFU=$("$PY" - "$H" "$WORK/hf-marks.jsonl" <<'HFUNIT'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
fails = []


def check(name, got, want):
    if got != want:
        fails.append("%s: %r != %r" % (name, got, want))


def ev(kind, **kw):
    kw["event"] = kind
    return kw


try:
    path = sys.argv[2]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": "run-open"}) + "\n")
        handle.write('{"event": "torn\n')
        handle.write(json.dumps({"event": "head-successor", "pid": 4301}) + "\n")
        handle.write("null\n")
        handle.write(json.dumps({"event": "phase-boundary", "caller_pid": 4302}) + "\n")
    marks = []
    got = ho.read_record(path, marks)
    check("placeholders", marks, [1, 2])
    check("the default reader unchanged", ho.read_record(path), got)
    check("the default reader's shape", (len(got), len(got[0]), got[1]), (2, 3, 2))
    P = 4301
    base = [ev("run-open", session="s0", pid_src="none"), ev("head-successor", session_id="s1", pid=P)]
    check("inside the window", ho.head_progress(base, P, 1, 1, 1, [2])[0], "unknown")
    check("just before the start", ho.head_progress(base, P, 1, 1, 1, [1])[0], "no")
    check("before the run-open", ho.head_progress(base, P, 1, 1, 1, [0])[0], "no")
    check("its own boundary beside one inside",
          ho.head_progress(base + [ev("phase-boundary", caller_pid=P)], P, 1, 1, 1, [3])[0], "yes")
    check("no placeholders: the counts alone", ho.head_progress(base, P, 1, 1, 1)[0], "no")
    later = base + [ev("observation", what="head exited"), ev("head-successor", session_id="s2", pid=4303)]
    check("a later head's window", ho.head_progress(later, 4303, 3, 1, 1, [2])[0], "no")
except Exception as exc:
    fails.append("raised %s: %s" % (type(exc).__name__, exc))
print("ok" if not fails else "; ".join(fails))
HFUNIT
)
need_eq "$HFU" "ok" "the reader's placeholders and the window on planted records"
verdict "repeat-stop (fails on old; the review of 2026-10-11, finding 3, D32 (4)): an unparseable line written after the attached head's start and before the attach reads unknown and does not pair, the later heads' pair still firing; one written before that start leaves the guard in force (the control); the reader places each skipped line among the events for the guard alone, every other call unchanged"

# Finding 4 (MEDIUM; K615a63df): successive re-derivations keep the newer head-written Next with
# its own pack stamp, and a genuinely newer boundary supersedes it.
hf_plant_pack() { # $1 hand-off, $2 stamp, $3 Next text: a head's own pack, written at the stamp
  "$PY" - "$1" "$2" "$3" <<'HFPACK'
import sys
path, stamp, nxt = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
new = ("## In flight\n- pack written: %s\n- Next: %s\n- Needs: wiki/h.md:1\n"
       "- Decided: D8 because the author said so\n" % (stamp, nxt))
if "## In flight\n- nothing in flight.\n" not in text:
    sys.exit("hf_plant_pack: the fixture's in-flight section is not where it was expected")
with open(path, "w", encoding="utf-8") as handle:
    handle.write(text.replace("## In flight\n- nothing in flight.\n", new, 1))
HFPACK
}
fixture hfnext 200
mk append "$REC" "$(printf '{"event":"phase-boundary","ts":"%s","from":"item6","to":"item7","next":"HF OLD NEXT: the seventh pass","disposition":"d","meter":"m","waste":"w"}' "$(hf_tsago 86400)")" >/dev/null
HF_PSTAMP=$(hf_tsago 1800)
hf_plant_pack "$HO" "$HF_PSTAMP" "HF HEAD NEXT: item 9, the analysis gates"
mk append "$REC" '{"event":"head-exit","band":"limit","context":"c","pack":false,"pid":1}' >/dev/null
HF_WANT="Next: HF HEAD NEXT: item 9, the analysis gates (from the head's own pack written $HF_PSTAMP, newer than "
for hf_pass in 1 2 3; do
  run handoff --run hfnext --inflight-from-record
  need_rc 0
  SEC=$(mk section "$HO" "In flight")
  case $SEC in *"$HF_WANT"*) : ;; *) why="$why; derivation $hf_pass lost the head's Next or its stamp: $SEC" ;; esac
  case $SEC in *"HF OLD NEXT"*) why="$why; derivation $hf_pass restored the older boundary's next" ;; esac
done
need_eq "$(grep -c '^- Next: ' "$HO")" "1" "one Next line after three derivations"
mk append "$REC" '{"event":"phase-boundary","from":"item9","to":"item10","next":"HF NEWER NEXT: item 10, the report","disposition":"d","meter":"m","waste":"w"}' >/dev/null
run handoff --run hfnext --inflight-from-record
need_rc 0
SEC=$(mk section "$HO" "In flight")
case $SEC in *"Next: HF NEWER NEXT: item 10, the report (a copy of the "*) : ;; *) why="$why; the newer boundary's next does not supersede: $SEC" ;; esac
case $SEC in *"HF HEAD NEXT"*) why="$why; the superseded head Next survives a newer boundary" ;; esac
case $SEC in *"Needs: wiki/h.md:1"*) : ;; *) why="$why; the pack's hand-written lines are not kept" ;; esac
verdict "handoff --inflight-from-record (fails on old; the review of 2026-10-11, finding 4, K615a63df): three successive re-derivations with no newer boundary keep the head's newer Next with its own pack stamp and never restore the day-old boundary's next, while a genuinely newer phase-boundary supersedes it; the pack's hand-written lines stay"

# Finding 5 (MEDIUM; K0fe7df69): a registered control is withheld before the extraction splits a
# turn into lines or cuts a tool line, so its wrapped and unwrapped copies are all gone while the
# unrelated prose around them stays. The copies: one on a line of its own, one wrapped after its
# first word, one wrapped after its head, one in the owner's words, one wrapped inside a command,
# and one a tool line's cut would leave fourteen characters of.
fixture hfred 200
mk append "$REC" '{"event":"observation","phase":"controls-XHF","what":"HF-CTRL-SENTINEL the reflector must find the gap at item four","note":"pre-registered"}' >/dev/null
THF=$("$PY" - <<'HFSCRIPT'
import json, os, re
sid = "sid-hfred"
root = os.environ["AIMYTH_PROJECTS_DIR"]
path = os.path.join(root, re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])),
                    sid + ".jsonl")
os.makedirs(os.path.dirname(path), exist_ok=True)
ctl = "HF-CTRL-SENTINEL the reflector must find the gap at item four"


def prose(text, at):
    return {"type": "assistant", "timestamp": "2026-10-11T10:00:%02dZ" % at,
            "message": {"role": "assistant", "model": "claude-fixture-1",
                        "content": [{"type": "text", "text": text}]}}


def call(command, at):
    return {"type": "assistant", "timestamp": "2026-10-11T10:00:%02dZ" % at,
            "message": {"role": "assistant", "model": "claude-fixture-1",
                        "content": [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}


recs = [
    {"type": "user", "timestamp": "2026-10-11T10:00:00Z",
     "message": {"role": "user", "content": [{"type": "text", "text": "the owner asks for the reflection"}]}},
    prose("Unrelated prose line one stays.\nI expect: %s.\nUnrelated prose line three stays." % ctl, 5),
    prose("Unrelated opening stays.\nI expect: HF-CTRL-SENTINEL\nthe reflector must find the gap at item four.\n"
          "Unrelated closing stays.", 10),
    prose("Wrapped late: HF-CTRL-SENTINEL the reflector must find\nthe gap at item four, said twice.\n"
          "Unrelated tail stays.", 15),
    {"type": "user", "timestamp": "2026-10-11T10:00:20Z",
     "message": {"role": "user", "content": [{"type": "text",
                                              "text": "please check HF-CTRL-SENTINEL the\nreflector must find the gap at item four"}]}},
    call("echo 'HF-CTRL-SENTINEL the reflector\nmust find the gap at item four'", 25),
    call("x" * 270 + " " + ctl, 30),
    call("git status --porcelain", 35),
]
with open(path, "w", encoding="utf-8") as handle:
    handle.write("".join(json.dumps(r) + "\n" for r in recs))
print(path)
HFSCRIPT
)
OUTHF="$WORK/refl-hfred"
run reflect-inputs --run hfred --session sid-hfred --out "$OUTHF" --no-meter
need_rc 0
need_eq "$(hf_sum "$OUTHF" "HF-CTRL-SENTIN")" "0" "no copy of the control, nor the head a cut leaves, in the four outputs"
need_eq "$(hf_sum "$OUTHF" "gap at item four")" "0" "no wrapped tail of the control in the four outputs"
for hf_line in "Unrelated prose line one stays." "Unrelated prose line three stays." "Unrelated opening stays." \
    "Unrelated closing stays." "Unrelated tail stays." "- Bash: git status --porcelain" "the owner asks for the reflection"; do
  need_eq "$(grep -c -F -- "$hf_line" "$OUTHF/turns.md")" "1" "unrelated text stays: $hf_line"
done
need_eq "$(mk json "$OUTHF/counts.json" notes.controls_redacted)" "9" "nine lines withheld, counted"
need_eq "$(grep -c -F "HF-CTRL-SENTINEL" "$THF")" "6" "the control: the source transcript carries six copies"
verdict "reflect-inputs (fails on old; the review of 2026-10-11, finding 5, K0fe7df69): a registered control wrapped across lines — in prose after its first word or after its head, in the owner's words, inside a command — and one a tool line's cut would shorten appear in none of the four blinded outputs, every line they touch withheld and counted, while the unrelated prose around them and an ordinary tool call stay"

# Finding 6 (MEDIUM; K22da6bf5): one refusal for every budget the successor computes. A seeded
# record whose run spend is at or above its envelope refuses before any head-exit, detach or
# start, its dry run too; a positive remainder launches the head with that remainder.
HF_SEEDX='{"event":"head-exit","band":"unmetered","context":"unmetered (transcript missing for the seed session)","pack":false}'
hf_seeded() { # $1 run, $2 envelope, $3 the one lane's recorded cost: a seeded record whose last head-exit is the seed's
  seed_fixture "$1" "$2"
  mk append "$REC" "$HF_SEEDX" >/dev/null
  mk append "$REC" '{"event":"lane-open","lane":"LSEED","class":"builder","model":"opus"}' >/dev/null
  mk append "$REC" "{\"event\":\"lane-closed\",\"lane\":\"LSEED\",\"exit_class\":\"completed\",\"total_cost_usd\":$3}" >/dev/null
}
for hf_case in at:100 above:120; do
  hf_tag=${hf_case%%:*}; hf_cost=${hf_case#*:}
  hf_seeded "hfseed-$hf_tag" 100 "$hf_cost"
  HFL=$(mk lines "$REC")
  RUNENV="PATH=$WORK/psnone:$PATH"
  run successor --run "hfseed-$hf_tag" --dry-run --harness-bin "$WORK/bin/stubhead"
  need_rc 2
  need_out "the envelope is spent (envelope (seed)"
  need_eq "$(mk lines "$REC")" "$HFL" "a refused dry run writes nothing ($hf_tag)"
  viewer_use "hfseed-$hf_tag"
  RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
  run successor --run "hfseed-$hf_tag" --harness-bin "$WORK/bin/stubhead" --wait-s 1 --max-wait-s 5 --tick-s 1
  need_rc 2
  need_out "the envelope is spent"
  need_eq "$(mk count "$REC" successor-aborted) $(hf_get "$REC" successor-aborted reason 0)" "1 budget" "the refusal is on the record ($hf_tag)"
  need_eq "$(mk count "$REC" head-exit)" "1" "no head-exit written ($hf_tag)"
  need_nofile "$REALSTORE/spawn-records/hfseed-$hf_tag-head-1.out.starter.log"
  need_no_viewer
done
sleep 2   # a starter detached by the old code would have started its head by now
need_eq "$(hf_stubs hfseed-at) $(hf_stubs hfseed-above)" "0 0" "no head started"
hf_seeded hfseed-below 100 40
viewer_use hfseed-below
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run hfseed-below --harness-bin "$WORK/bin/stubhead" --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "budget \$60.00 (budget_src: envelope (seed)"
hf_wait_log "$WORK/stub-hfseed-below.args" "--max-budget-usd 60.00" 30
hf_wait_log "$REALSTORE/spawn-records/hfseed-below-head-1.out.starter.log" "supervisor: handed-over" 30
verdict "successor (fails on old; the review of 2026-10-11, finding 6, K22da6bf5): a seeded record whose run spend reaches its envelope (\$100 of \$100) or passes it (\$120) refuses, its dry run writing nothing and its real call recording successor-aborted budget before any head-exit, starter, window or head; a positive remainder (\$60) launches the head with that remainder (the control)"

# Finding 7 (MEDIUM; K4a701287): run-resume --max-successors rewrites the cap, the run's lists
# carried, and a cap below 1 is refused with nothing written; a resume naming nothing keeps the
# file and the cap it now holds (the control).
fixture hfcap 200
GFC="$REALSTORE/spawn-records/hfcap-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run grants --run hfcap --write "$WORK/real-grant/hfcap" --max-successors 4
need_rc 0
need_eq "$(mk json "$GFC" max_successors)" "4" "the cap before the resume"
HFW=$(grep -c -F "real-grant/hfcap" "$GFC")
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run hfcap --session sid-hfcap --head "h" --detail "the cap alone" --max-successors 9
need_rc 0
need_out "max_successors 9 (arg)"
need_eq "$(mk json "$GFC" max_successors)" "9" "the cap written to the grants file"
need_eq "$(mk field "$REC" run-resume max_successors)" "9" "the cap on the run-resume"
need_eq "$(grep -c -F "real-grant/hfcap" "$GFC")" "$HFW" "the write list carried"
[ "$HFW" -ge 1 ] || why="$why; the planted write grant was never in the file (the control)"
HFL=$(mk lines "$REC")
HFS=$(sha_file "$GFC")
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run hfcap --session sid-hfcap --head "h" --detail "a zero cap" --max-successors 0
need_rc 2
need_out "--max-successors must be a whole number of at least 1, got 0"
need_eq "$(mk lines "$REC")" "$HFL" "a refused cap writes no event"
need_eq "$(sha_file "$GFC")" "$HFS" "a refused cap leaves the file as it was"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run hfcap --session sid-hfcap --head "h" --detail "no flags"
need_rc 0
need_out "(kept)"
need_eq "$(mk json "$GFC" max_successors)" "9" "a kept file keeps its cap"
verdict "run-resume --max-successors (fails on old; the review of 2026-10-11, finding 7, K4a701287): a cap-only resume rewrites the grants file's cap (4 to 9) with the lists carried and records it on its event; a zero cap is refused (exit 2) with nothing written; a resume naming nothing keeps the file and its cap (the control)"

# Finding 9 (LOW; K22da6bf5, K6cf0c658): the dry runs of successor, in both budget branches, and
# of raise-envelope leave the run's meter cache as they find it — an absent one absent, an
# existing one byte-identical — although each meters a lane; a real call still fills it (the
# controls).
hf_cached() { # $1 run, $2 seed or plain: a record whose one lane the meter prices from its transcript; HFC names its cache
  if [ "$2" = seed ]; then seed_fixture "$1" 400; mk append "$REC" "$HF_SEEDX" >/dev/null; else fixture "$1" 400; fi
  mk pricedscript "sid-$1-l" 2 "lane-$1" >/dev/null
  mk append "$REC" "{\"event\":\"lane-open\",\"lane\":\"LC\",\"class\":\"builder\",\"model\":\"opus\",\"session_id\":\"sid-$1-l\"}" >/dev/null
  mk append "$REC" "{\"event\":\"lane-closed\",\"lane\":\"LC\",\"session_id\":\"sid-$1-l\",\"exit_class\":\"completed\",\"total_cost_usd\":1.0}" >/dev/null
  HFC="$REALSTORE/spawn-records/$1-spend-cache.json"
}
hf_stale() { printf '%s\n' '{"sid-elsewhere": {"path": "none", "size": 0, "mtime": 0, "usd": 9.99}}' > "$1"; }
hf_cache_has() { # $1 cache, $2 session id: yes when the cache holds a metered entry for the session
  "$PY" -c 'import json, sys
try:
    entry = json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2])
except (OSError, ValueError) as exc:
    entry = None
print("yes" if isinstance(entry, dict) and isinstance(entry.get("usd"), (int, float)) else "no")' "$1" "$2"
}
# The premise of every dry run below: the meter really priced the lane's transcript (two calls of a
# million opus input tokens each, so twice the family's input rate, above the $1.00 recorded), the
# figure a cache entry would hold.
HF_LANE=$("$PY" -c 'import json, sys; print("%.2f" % max(1.0, 2 * float(json.load(open(sys.argv[1]))["families"]["opus"]["input"])))' "$SKILL_DIR/prices.json")
hf_cached hfcache-succ plain
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hfcache-succ --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "lanes \$$HF_LANE (1 of 1 with a figure"
need_nofile "$HFC"
hf_stale "$HFC"; HFS=$(sha_file "$HFC")
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hfcache-succ --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_eq "$(sha_file "$HFC")" "$HFS" "successor --dry-run leaves an existing cache as it was"
hf_cached hfcache-seed seed
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hfcache-seed --dry-run --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget_src: envelope (seed)"
need_out "lanes \$$HF_LANE (1 of 1 with a figure"
need_nofile "$HFC"
hf_cached hfcache-env plain
run raise-envelope --run hfcache-env --to 500 --reason "a top-up" --meter-line "$METER" --dry-run
need_rc 0
need_out "lanes \$$HF_LANE (1 of 1 with a figure"
need_nofile "$HFC"
hf_stale "$HFC"; HFS=$(sha_file "$HFC")
run raise-envelope --run hfcache-env --to 500 --reason "a top-up" --meter-line "$METER" --dry-run
need_rc 0
need_eq "$(sha_file "$HFC")" "$HFS" "raise-envelope --dry-run leaves an existing cache as it was"
rm -f "$HFC"
run raise-envelope --run hfcache-env --to 500 --reason "a top-up" --meter-line "$METER"
need_rc 0
need_eq "$(hf_cache_has "$HFC" sid-hfcache-env-l)" "yes" "a real raise-envelope fills the cache (a control)"
hf_cached hfcache-real plain
viewer_use hfcache-real
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run hfcache-real --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_eq "$(hf_cache_has "$HFC" sid-hfcache-real-l)" "yes" "a real successor fills the cache (a control)"
hf_wait_log "$REALSTORE/spawn-records/hfcache-real-head-1.out.starter.log" "supervisor: handed-over" 30
verdict "meter cache (fails on old; the review of 2026-10-11, finding 9, K22da6bf5 and K6cf0c658): successor --dry-run, on a record that meters a lane and on a seeded one, and raise-envelope --dry-run leave an absent cache absent and an existing one byte-identical, while a real raise-envelope and a real successor fill it (the controls)"
# HF-END

# ---------------- the fold of the second review of the held build (2026-10-11) ---------------
# HF2-BEGIN. Like the block above, these legs need only the plumbing above the run-open legs, so a
# run against an older handsoff.py can take them alone (the fail-on-old run); they define their
# own helpers. One leg per finding of the second review, and a second leg for the gate under F1;
# every leg fails against the build before this fold, while the controls inside each — a relay
# after the ack, a gate no relay raced, a replacement verified in time, a single read under
# --wait 0, a resume no call raced — hold on both.

# Finding F1 (HIGH; G1, the decisions channel): an ack covers the record its call read, and no
# more. A close whose final recheck holds it has already recorded its ack, behind the owner's
# relay that raced its read (the before-ack case of the first fold's leg); the next close without
# an ack still holds on that relay, writing nothing, and a fresh ack then lets the close through.
# The control: a relay landing after the ack is held the same way by both builds.
hf2_close() { # $1 run, $2 where the relay lands (before-ack, after-ack): one close with --ack in process, `rc N` last
  "$PY" - "$H" "$1" "$2" "$METER" <<'HF2CLOSE'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, race, meter = sys.argv[2], sys.argv[3], sys.argv[4]
path = ho.record_path(run)


def relay():
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": ho.now(), "run": run, "event": "observation", "phase": "",
                                 "what": "AUTHOR ruling: HF2-RELAY the close waits for the checklist"}) + "\n")


real_pending, real_hold = ho.decisions_pending, ho.decisions_hold


def pending(*args, **kwargs):
    if race == "before-ack":
        relay()
    return real_pending(*args, **kwargs)


def hold(*args, **kwargs):
    result = real_hold(*args, **kwargs)
    if race == "after-ack":
        relay()
    return result


ho.decisions_pending, ho.decisions_hold = pending, hold
sys.argv = ["handsoff.py", "close", "--run", run, "--items", "fixture items", "--meter-line", meter,
            "--ack", "read the relays on the record"]
try:
    ho.main()
    code = 0
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
sys.stdout.flush()
print("rc %d" % code)
HF2CLOSE
}
for hf2_case in before-ack after-ack; do
  fixture "hf2close-$hf2_case" 200
  hf2_close "hf2close-$hf2_case" "$hf2_case" >"$WORK/hf2close-$hf2_case.out" 2>&1
  R="$STORE/spawn-records/hf2close-$hf2_case.jsonl"
  need_eq "$(grep '^rc ' "$WORK/hf2close-$hf2_case.out") $(mk count "$R" run-close)" "rc 6 0" "the raced close holds and writes no run-close ($hf2_case, the premise)"
  need_eq "$(grep -c -F '"what": "ack: read the relays on the record"' "$R")" "1" "the held close's ack is on the record ($hf2_case, the premise)"
  run close --run "hf2close-$hf2_case" --items "fixture items" --meter-line "$METER"
  need_rc 6
  need_out "HOLD (decisions channel, exit 6)"
  need_out "HF2-RELAY the close waits for the checklist"
  need_eq "$(mk count "$R" run-close)" "0" "no run-close from the next close without an ack ($hf2_case)"
  if [ "$hf2_case" = before-ack ]; then need_out "as the ack observation at "; fi
  run close --run "hf2close-$hf2_case" --items "fixture items" --meter-line "$METER" --ack "read the relay: the close waits for the checklist"
  need_rc 0
  need_eq "$(mk count "$R" run-close)" "1" "a fresh ack lets the close through ($hf2_case)"
done
verdict "close (fails on old; the second review of 2026-10-11, finding F1, G1): after a close held by its final recheck, the owner's relay having raced its read and landed before its ack, the next close without an ack still holds on that relay (exit 6, the relay printed, no run-close), the ack covering only the record its call read, and a fresh ack then lets the close through; a relay after the ack holds the same way on both builds (the control)"

# Finding F1, the gate's half: a gate has no final recheck, so an owner's relay landing while it
# runs is the next call's to hold, yet the reference was the gate's own event, or its ack, both
# written after that relay. The relay lands before the gate's ack, or after its decisions check and
# before its event: the next gate without an ack holds on it (exit 6, the relay printed, nothing
# written) and a fresh ack lets it through. The control: a gate with an ack that no relay raced
# leaves the next gate clear.
hf2_gate() { # $1 run, $2 where the relay lands (none, before-ack, after-check), $3 yes for --ack: one gate in process, `rc N` last
  "$PY" - "$H" "$1" "$2" "$3" "$METER" <<'HF2GATE'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, race, ack, meter = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
path = ho.record_path(run)


def relay():
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": ho.now(), "run": run, "event": "observation", "phase": "",
                                 "what": "AUTHOR ruling: HF2-GATE-RELAY item two waits for the owner"}) + "\n")


real_pending, real_hold = ho.decisions_pending, ho.decisions_hold


def pending(*args, **kwargs):
    if race == "before-ack":
        relay()
    return real_pending(*args, **kwargs)


def hold(*args, **kwargs):
    result = real_hold(*args, **kwargs)
    if race == "after-check":
        relay()
    return result


ho.decisions_pending, ho.decisions_hold = pending, hold
sys.argv = ["handsoff.py", "gate", "--run", run, "--to", "item1", "--meter-line", meter]
if ack == "yes":
    sys.argv += ["--ack", "read the record before item one"]
try:
    ho.main()
    code = 0
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
sys.stdout.flush()
print("rc %d" % code)
HF2GATE
}
for hf2_case in none:yes before-ack:yes after-check:no; do
  hf2_race=${hf2_case%%:*}; hf2_ack=${hf2_case#*:}
  fixture "hf2gate-$hf2_race" 200
  mk transcript "sid-hf2gate-$hf2_race" 100000 >/dev/null
  hf2_gate "hf2gate-$hf2_race" "$hf2_race" "$hf2_ack" >"$WORK/hf2gate-$hf2_race.out" 2>&1
  R="$STORE/spawn-records/hf2gate-$hf2_race.jsonl"
  need_eq "$(grep '^rc ' "$WORK/hf2gate-$hf2_race.out") $(mk count "$R" gate)" "rc 0 1" "the raced gate proceeds and records its gate ($hf2_race, the premise)"
  HF2L=$(mk lines "$R")
  run gate --run "hf2gate-$hf2_race" --to item2 --meter-line "$METER"
  if [ "$hf2_race" = none ]; then
    need_rc 0
    need_absent "HOLD"
    need_eq "$(mk count "$R" gate)" "2" "the next gate is recorded (the control)"
  else
    need_rc 6
    need_out "HOLD (decisions channel, exit 6)"
    need_out "HF2-GATE-RELAY item two waits for the owner"
    need_out "as the gate at "
    need_eq "$(mk lines "$R")" "$HF2L" "the held gate writes nothing ($hf2_race)"
    run gate --run "hf2gate-$hf2_race" --to item2 --meter-line "$METER" --ack "read the relay: item two waits for the owner"
    need_rc 0
    need_eq "$(mk count "$R" gate)" "2" "a fresh ack lets the gate through ($hf2_race)"
  fi
done
verdict "gate (fails on old; the second review of 2026-10-11, finding F1, the gate's half): an owner's relay landing while a gate runs, before its ack or after its decisions check and before its event, holds the next gate without an ack (exit 6, the relay printed, nothing written), the gate's event and its ack covering only the record its check read, and a fresh ack lets it through; a gate with an ack that no relay raced leaves the next gate clear (the control)"

# Finding F2 (MEDIUM; D21 (c), made by the first fold): a replacement head start whose
# verification ends past the deadline never certifies. Each case confirms a live head with one
# silent helper; at the check's first re-read the record gains a replacement start naming another
# live process, then the helper's attempt and its activity after that start, so the helper is
# ready. In the late case the replacement's command probe times out at its bound, the deadline,
# and returns 0.2 s past it (the margin set by judgement, so the leg rests on no sub-millisecond
# timing). The controls: the timely case's probe is 0.5 s slow inside an 8 s deadline, and under
# --wait 0 (a single read, no deadline) the head's own probe is 1 s slow.
hf2_launch() { # $1 run, $2 case (late, timely, wait0), $3 the --wait: one launch-check --lanes T1 in process, `planted …` and `rc N` last
  "$PY" - "$H" "$1" "$2" "$3" <<'HF2LAUNCH'
import importlib.util, json, os, subprocess, sys, time
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, case, wait = sys.argv[2], sys.argv[3], sys.argv[4]
path = ho.record_path(run)


def sleeper():
    return subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)


def stamp(ago=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - ago))


def add(ev):
    ev.setdefault("ts", stamp())
    ev["run"] = run
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev) + "\n")


def helper(ago):
    sid = "sid-%s-T1" % run
    add({"event": "lane-open", "ts": stamp(ago), "lane": "T1", "class": "builder", "model": "opus",
         "session_id": sid})
    add({"event": "lane-spawned", "ts": stamp(ago), "lane": "T1", "session_id": sid,
         "pid": lane.pid, "wrapper_pid": lane.pid})


def activity():
    folder = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], "lane-%s" % run)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "sid-%s-T1.jsonl" % run), "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": stamp(),
                                 "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": "working"}]}}) + "\n")


head, other, lane = sleeper(), sleeper(), sleeper()
state = {"lanes": False, "planted": False, "slow": 0}
code = None
try:
    add({"event": "head-successor", "session_id": "sid-%s" % run, "pid": head.pid,
         "model": "fixture-model", "effort": "max"})
    helper(5)
    if case == "wait0":
        activity()   # a single read: the helper is ready before the check begins
    real_read, real_lanes, real_row = ho.read_record, ho.launch_lanes, ho.ps_row

    def lanes_entered(*args, **kwargs):
        state["lanes"] = True
        return real_lanes(*args, **kwargs)

    def read(p, *args, **kwargs):
        if case != "wait0" and state["lanes"] and not state["planted"] and p == path:
            state["planted"] = True
            add({"event": "head-resumed", "session_id": "sid-%s" % run, "pid": other.pid,
                 "model": "fixture-model"})
            helper(3)   # the helper's attempt after the replacement start: that start's batch
            activity()
        return real_read(p, *args, **kwargs)

    def row(pid, *args, **kwargs):
        bound = kwargs.get("timeout", args[0] if args else None)
        if case == "late" and pid == other.pid:
            state["slow"] += 1
            time.sleep((bound or 0.0) + 0.2)   # timed out at its bound, the deadline, then torn down
            return None
        if (case == "timely" and pid == other.pid) or (case == "wait0" and pid == head.pid):
            state["slow"] += 1
            time.sleep(0.5 if case == "timely" else 1.0)
        return real_row(pid, *args, **kwargs)

    ho.read_record, ho.launch_lanes, ho.ps_row = read, lanes_entered, row
    sys.argv = ["handsoff.py", "launch-check", "--run", run, "--lanes", "T1", "--wait", wait,
                "--poll-s", "0.3", "--detach-safe"]
    try:
        ho.main()
        code = 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
finally:
    for proc in (head, other, lane):
        proc.kill()
        proc.wait()
sys.stdout.flush()
print("planted %s · slow probes %d" % (state["planted"], state["slow"]))
print("rc %s" % code)
HF2LAUNCH
}
for hf2_case in late:3 timely:8 wait0:0; do
  hf2_tag=${hf2_case%%:*}; hf2_wait=${hf2_case#*:}
  fixture "hf2launch-$hf2_tag" 200
  hf2_launch "hf2launch-$hf2_tag" "$hf2_tag" "$hf2_wait" >"$WORK/hf2launch-$hf2_tag.out" 2>&1
done
O="$WORK/hf2launch-late.out"
grep -q -F "planted True · slow probes 1" "$O" || why="$why; the replacement or its slow probe never came during the wait (late, the premise)"
need_eq "$(grep '^rc ' "$O")" "rc 1" "exit (late)"
grep -q -F "NOT CLEAN" "$O" || why="$why; no NOT CLEAN line (late)"
grep -q -F "past the 3 s deadline" "$O" || why="$why; the replacement confirmed past the deadline is not named"
if grep -q -F "STARTED CLEAN" "$O"; then why="$why; certified (late)"; fi
O="$WORK/hf2launch-timely.out"
grep -q -F "planted True · slow probes 1" "$O" || why="$why; the replacement or its slow probe never came during the wait (timely, the premise)"
need_eq "$(grep '^rc ' "$O")" "rc 0" "exit (timely, a control)"
grep -q -F "STARTED CLEAN" "$O" || why="$why; the timely replacement is not certified"
grep -q -F "(a replacement start, its identity verified)" "$O" || why="$why; the timely certification does not name the replacement"
grep -q -F "T1 progressing" "$O" || why="$why; the timely control does not read the helper's activity"
O="$WORK/hf2launch-wait0.out"
grep -q -F "planted False · slow probes 1" "$O" || why="$why; the head's slow probe never ran (wait0, the premise)"
need_eq "$(grep '^rc ' "$O")" "rc 0" "exit (--wait 0, a control)"
grep -q -F "STARTED CLEAN" "$O" || why="$why; the single read is not certified"
grep -q -F "T1 progressing" "$O" || why="$why; the single read does not read the helper's activity"
verdict "launch-check --lanes (fails on old; the second review of 2026-10-11, finding F2, D21 (c)): a replacement head start whose verification ends past the deadline is NOT CLEAN (exit 1, the late confirmation named) though its helper is ready; a replacement verified inside the deadline and a single read under --wait 0 with a slow probe still certify (the controls)"

# Finding F3 (LOW; made by the first fold): a rewriting run-resume records the grants keys it
# writes. Each case plants the run's lists (one read path, one write path) and the cap 4 through
# the real grants verb, then runs one run-resume naming --viewer alone, so the cap and the limit
# gate are carried from the file. In the raced case a real `grants --max-successors 9 --on-limit
# resume` completes after the resume began and before it takes the record's lock: the file, the
# run-resume event and stdout then agree on 9 and resume, with both lists kept. The control: the
# same resume with no call between keeps 4 and stop everywhere.
hf2_resume() { # $1 run, $2 race (none, cap): one rewriting run-resume (--viewer none) in process under the stub ps, `raced …` and `rc N` last
  env PATH="$WORK/psnone:$PATH" "$PY" - "$H" "$1" "$2" <<'HF2RESUME'
import importlib.util, subprocess, sys
target, run, race = sys.argv[1], sys.argv[2], sys.argv[3]
spec = importlib.util.spec_from_file_location("ho", target)
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
real_lock = ho.record_lock
state = {"raced": "no"}


def lock(path):
    if race == "cap" and state["raced"] == "no":
        # The other call takes and releases the record's lock itself, before this resume takes it.
        done = subprocess.run([sys.executable, "-B", target, "grants", "--run", run,
                               "--max-successors", "9", "--on-limit", "resume"],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True)
        state["raced"] = "rc %d" % done.returncode
    return real_lock(path)


ho.record_lock = lock
sys.argv = ["handsoff.py", "run-resume", "--run", run, "--session", "sid-%s" % run, "--head", "h",
            "--detail", "the viewer alone", "--viewer", "none"]
try:
    ho.main()
    code = 0
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
sys.stdout.flush()
print("raced %s" % state["raced"])
print("rc %d" % code)
HF2RESUME
}
hf2_lists() { # $1 grants file, $2 record, $3 read-path tail, $4 write-path tail: the entries ending so in the file's lists and in the last run-resume's (-1: no such list)
  "$PY" -c 'import json, sys
grants = json.load(open(sys.argv[1], encoding="utf-8"))
resume = {}
for line in open(sys.argv[2], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict) and e.get("event") == "run-resume":
        resume = e


def n(value, tail):
    return sum(1 for p in value if isinstance(p, str) and p.endswith(tail)) if isinstance(value, list) else -1


print("file %d %d event %d %d" % (n(grants.get("grants"), sys.argv[3]), n(grants.get("writes"), sys.argv[4]),
                                  n(resume.get("grants"), sys.argv[3]), n(resume.get("writes"), sys.argv[4])))' "$1" "$2" "$3" "$4"
}
hf2_order() { # $1 record: where the last grants event stands against the last run-resume, and its cap
  "$PY" -c 'import json, sys
events = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        events.append(json.loads(line))
    except ValueError:
        continue
last = {}
for i, e in enumerate(events):
    if isinstance(e, dict):
        last[e.get("event")] = (i, e)
g, r = last.get("grants"), last.get("run-resume")
if g is None or r is None:
    print("<no grants or no run-resume>")
else:
    print("grants %s %s run-resume" % (g[1].get("max_successors"), "before" if g[0] < r[0] else "after"))' "$1"
}
for hf2_case in none cap; do
  fixture "hf2res-$hf2_case" 200
  R="$STORE/spawn-records/hf2res-$hf2_case.jsonl"
  GF2="$REALSTORE/spawn-records/hf2res-$hf2_case-grants.json"
  RUNENV="PATH=$WORK/psnone:$PATH"
  run grants --run "hf2res-$hf2_case" --grant "$WORK/real-grant/hf2res-$hf2_case-read" --write "$WORK/real-grant/hf2res-$hf2_case-write" --max-successors 4
  need_rc 0
  need_eq "$(mk json "$GF2" max_successors) $(mk json "$GF2" on_limit)" "4 stop" "the file before the resume ($hf2_case, the premise)"
  HF2B=$(hf2_lists "$GF2" "$R" "/real-grant/hf2res-$hf2_case-read" "/real-grant/hf2res-$hf2_case-write")
  HF2F=${HF2B% event *}; HF2C=${HF2F#file }
  case " $HF2C " in *" 0 "*|*" -1 "*) why="$why; the planted lists are not in the file before the resume ($hf2_case, the premise): $HF2B" ;; esac
  hf2_resume "hf2res-$hf2_case" "$hf2_case" >"$WORK/hf2res-$hf2_case.out" 2>&1
  O="$WORK/hf2res-$hf2_case.out"
  if [ "$hf2_case" = cap ]; then HF2CAP=9; HF2LIM=resume; HF2RACED="raced rc 0"; else HF2CAP=4; HF2LIM=stop; HF2RACED="raced no"; fi
  need_eq "$(grep '^raced ' "$O") $(grep '^rc ' "$O")" "$HF2RACED rc 0" "the resume, and the call before its lock ($hf2_case)"
  need_eq "$(mk json "$GF2" max_successors) $(mk json "$GF2" on_limit) $(mk json "$GF2" viewer)" "$HF2CAP $HF2LIM none" "the file ($hf2_case)"
  need_eq "$(mk field "$R" run-resume max_successors) $(mk field "$R" run-resume on_limit) $(mk field "$R" run-resume viewer)" "$HF2CAP $HF2LIM none" "the run-resume event ($hf2_case)"
  need_eq "$(mk field "$R" run-resume max_successors_src) $(mk field "$R" run-resume on_limit_src)" "grants grants" "the event's sources ($hf2_case)"
  need_eq "$(grep -c -F "on_limit $HF2LIM · viewer none" "$O") $(grep -c -F "max_successors $HF2CAP (grants)" "$O")" "1 1" "stdout ($hf2_case)"
  need_eq "$(hf2_lists "$GF2" "$R" "/real-grant/hf2res-$hf2_case-read" "/real-grant/hf2res-$hf2_case-write")" "$HF2F event $HF2C" "both lists kept, in the file and on the event ($hf2_case)"
done
need_eq "$(hf2_order "$STORE/spawn-records/hf2res-cap.jsonl")" "grants 9 before run-resume" "the raced cap was recorded before the resume (the premise)"
need_eq "$(hf2_order "$STORE/spawn-records/hf2res-none.jsonl")" "grants 4 before run-resume" "the control's one grants call"
verdict "run-resume (fails on old; the second review of 2026-10-11, finding F3): a rewriting resume takes every grants key it records from the one plan it writes under the record's lock, so a grants call raising the cap to 9 and setting on_limit resume between the resume's start and its lock leaves the file, the run-resume event and stdout agreeing on 9 and resume, both lists kept; a resume no call raced keeps 4 and stop everywhere (the control)"
# HF2-END

# ---------------- the fold of the third review of the held build (2026-10-11) ----------------
# HF3-BEGIN. Like the blocks above, these legs need only the plumbing above the run-open legs, so a
# run against an older handsoff.py can take them alone (the fail-on-old run); they define their
# own helpers. One leg for the coverage rule that replaced the stopped design (N1) and one for the
# launch check's deadline (N2); each fails against the build before this fold, while the controls
# inside each (a valid coverage, a coverage short of the relay, records written before the field,
# two overlapping calls, a timely re-read, a timely probe and a single read under --wait 0) hold
# on both.

# Finding N1 (HIGH; the decisions channel, its coverage rule replaced): a gate event's or an ack's
# decisions_seen covers the record only when it is a whole number from 0 to the count of the
# events before it; any other present value covers nothing, so the relay it would have hidden
# holds the gate and the close and stays on the pending list alike, until a fresh, valid ack.
# Each case plants an AUTHOR relay behind the run-open, then one or two gate events or acks
# carrying the case's value (the critic's example: an ack carrying the string "1"). The controls
# keep their present reading on both builds: a valid value that covers the relay (nothing
# pending) or falls short of it (pending), events written before the field (read by their place),
# and two overlapping calls, the furthest valid coverage winning over a slower call's shorter one.
hf3_plant() { # $1 record, $2 run, $3 case: the relay and the case's gate events or acks, appended
  "$PY" - "$1" "$2" "$3" <<'HF3PLANT'
import json, sys, time
path, run, case = sys.argv[1], sys.argv[2], sys.argv[3]
# Per case, after the relay (index 1, behind the run-open): each event's kind and its
# decisions_seen as JSON text, None for no field. The first planted event sits at index 2.
CASES = {
    "str1": [("ack", '"1"')], "str2": [("ack", '"2"')], "true": [("ack", "true")],
    "null": [("ack", "null")], "neg": [("ack", "-1")], "big": [("ack", "99")],
    "past": [("ack", "3")], "float": [("ack", "2.0")], "gatestr": [("gate", '"2"')],
    "overmal": [("ack", '"2"'), ("ack", "1")],
    "valid": [("ack", "2")], "short": [("ack", "1")], "legacy": [("ack", None)],
    "gatevalid": [("gate", "2")], "gatelegacy": [("gate", None)],
    "overlap": [("ack", "2"), ("ack", "1")],
}


def add(ev):
    ev.update(ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"), run=run)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev) + "\n")


add({"event": "observation", "phase": "",
     "what": "AUTHOR ruling: HF3-RELAY the next item waits for the owner's list"})
for kind, value in CASES[case]:
    if kind == "ack":
        ev = {"event": "observation", "phase": "", "what": "ack: read the record"}
    else:
        ev = {"event": "gate", "item": "item1", "context": 100000, "percent": 10, "band": 0,
              "armed": False, "decision": "allow", "metered": True}
    if value is not None:
        ev["decisions_seen"] = json.loads(value)
    add(ev)
HF3PLANT
}
hf3_pending() { # $1 records directory, $2 the cases (one string): `<case>:<pending count>` per case's gate record, from decisions_pending in process (it reads, never writes)
  "$PY" - "$H" "$1" "$2" <<'HF3PENDING'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
found = []
for case in sys.argv[3].split():
    events, _ = ho.read_record(os.path.join(sys.argv[2], "hf3g-%s.jsonl" % case))
    found.append("%s:%d" % (case, len(ho.decisions_pending(events, None)[0])))
print(" ".join(found))
HF3PENDING
}
HF3_CASES="str1 str2 true null neg big past float gatestr overmal valid short legacy gatevalid gatelegacy overlap"
HF3_HELD="str1 str2 true null neg big past float gatestr overmal short"
for hf3_c in $HF3_CASES; do
  fixture "hf3g-$hf3_c" 200
  hf3_plant "$REC" "hf3g-$hf3_c" "$hf3_c"
  fixture "hf3c-$hf3_c" 200
  hf3_plant "$REC" "hf3c-$hf3_c" "$hf3_c"
done
need_eq "$(hf3_pending "$STORE/spawn-records" "$HF3_CASES")" "str1:1 str2:1 true:1 null:1 neg:1 big:1 past:1 float:1 gatestr:1 overmal:1 valid:0 short:1 legacy:0 gatevalid:0 gatelegacy:0 overlap:0" "the pending list (decisions_pending), case by case"
for hf3_c in $HF3_CASES; do
  case " $HF3_HELD " in *" $hf3_c "*) hf3_rc=6 ;; *) hf3_rc=0 ;; esac
  R="$STORE/spawn-records/hf3g-$hf3_c.jsonl"
  HF3L=$(mk lines "$R")
  run gate --run "hf3g-$hf3_c" --to item2 --meter-line "$METER"
  [ "$RC" = "$hf3_rc" ] || why="$why; gate exit $RC, wanted $hf3_rc ($hf3_c)"
  if [ "$hf3_rc" = 6 ]; then
    grep -q -F "HF3-RELAY the next item waits" "$WORK/both" || why="$why; the held gate does not print the relay ($hf3_c)"
    need_eq "$(mk lines "$R")" "$HF3L" "the held gate writes nothing ($hf3_c)"
  else
    need_eq "$(mk field "$R" gate item)" "item2" "the gate is recorded ($hf3_c)"
  fi
  if [ "$hf3_c" = str1 ]; then
    grep -q -F 'carries decisions_seen "1", not a whole number from 0 to 2 (the events before it) and so covers nothing' "$WORK/both" || why="$why; the held gate does not name the refused value (str1)"
  fi
  R="$STORE/spawn-records/hf3c-$hf3_c.jsonl"
  run close --run "hf3c-$hf3_c" --items "fixture items" --meter-line "$METER"
  [ "$RC" = "$hf3_rc" ] || why="$why; close exit $RC, wanted $hf3_rc ($hf3_c)"
  if [ "$hf3_rc" = 6 ]; then hf3_n=0; else hf3_n=1; fi
  need_eq "$(mk count "$R" run-close)" "$hf3_n" "the close's run-close ($hf3_c)"
done
# A fresh, valid ack covers what the malformed one could not: that gate, the next gate with no
# ack, and the close.
run gate --run hf3g-str1 --to item2 --meter-line "$METER" --ack "read the relay: the next item waits for the owner's list"
need_rc 0
run gate --run hf3g-str1 --to item3 --meter-line "$METER"
need_rc 0
need_eq "$(mk field "$STORE/spawn-records/hf3g-str1.jsonl" gate item)" "item3" "the fresh ack lets the next gate through with no ack (str1)"
run close --run hf3c-str1 --items "fixture items" --meter-line "$METER" --ack "read the relay: the next item waits for the owner's list"
need_rc 0
need_eq "$(mk count "$STORE/spawn-records/hf3c-str1.jsonl" run-close)" "1" "a fresh ack lets the close through (str1)"
verdict "decisions coverage (fails on old; the third review of 2026-10-11, finding N1, the stopped part replaced by fail-closed coverage): a gate event or ack whose decisions_seen is a string, a boolean, null, a negative number, a number above the count of the events before it or a float covers nothing, so the AUTHOR relay it stood behind holds the gate and the close (exit 6, nothing written) and stays on the pending list until a fresh, valid ack lets both through; a valid value, records written before the field and two overlapping calls, the furthest valid coverage winning, keep their present reading (the controls)"

# Finding N2 (MEDIUM; D21 (c), older than the build): every path that certifies a start reads the
# clock after its last read or probe, so a first batch first seen ready past the deadline is NOT
# CLEAN. Each case confirms a live head with one helper whose process is alive. In the late
# re-read the helper is silent until the check's first re-read inside the first batch's wait,
# which returns past the 2 s deadline carrying the helper's first activity; in the late probe the
# activity is there from the start, but the helper's activity probe returns past that deadline.
# Both land 0.5 s past it (set by judgement, unmeasured: the leg rests on no sub-second timing).
# The controls: the same re-read and probe 0.5 s slow inside an 8 s deadline, and under --wait 0
# (a single read, no deadline) a probe 1 s slow, each still STARTED CLEAN.
hf3_launch() { # $1 run, $2 case (reread-late, probe-late, reread-timely, probe-timely, wait0), $3 the --wait: one launch-check --lanes T1 in process, `slowed N` and `rc N` last
  "$PY" - "$H" "$1" "$2" "$3" <<'HF3LAUNCH'
import importlib.util, json, os, subprocess, sys, time
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, case, wait_text = sys.argv[2], sys.argv[3], sys.argv[4]
wait = float(wait_text)
path = ho.record_path(run)
LATE_S, TIMELY_S, WAIT0_S = 0.5, 0.5, 1.0   # set by judgement, unmeasured (see the leg's comment)


def sleeper():
    return subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)


def stamp(ago=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - ago))


def add(ev):
    ev.setdefault("ts", stamp())
    ev["run"] = run
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev) + "\n")


def activity():
    folder = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], "lane-%s" % run)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "sid-%s-T1.jsonl" % run), "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": stamp(),
                                 "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": "working"}]}}) + "\n")


head, lane = sleeper(), sleeper()
state = {"t_lanes": None, "slowed": 0}
code = None
try:
    add({"event": "head-successor", "session_id": "sid-%s" % run, "pid": head.pid,
         "model": "fixture-model", "effort": "max"})
    sid = "sid-%s-T1" % run
    add({"event": "lane-open", "ts": stamp(5), "lane": "T1", "class": "builder", "model": "opus",
         "session_id": sid})
    add({"event": "lane-spawned", "ts": stamp(5), "lane": "T1", "session_id": sid,
         "pid": lane.pid, "wrapper_pid": lane.pid})
    if not case.startswith("reread"):
        activity()   # ready before the check begins: only the probe's own time decides
    real_read, real_lanes, real_probe = ho.read_record, ho.launch_lanes, ho.lane_activity_stamp

    def until(offset):   # sleep until `offset` seconds after the first batch's wait began
        time.sleep(max(0.0, state["t_lanes"] + offset - time.monotonic()))

    def lanes_entered(*args, **kwargs):
        state["t_lanes"] = time.monotonic()
        return real_lanes(*args, **kwargs)

    def read(p, *args, **kwargs):
        if case.startswith("reread") and state["t_lanes"] is not None and not state["slowed"] \
                and p == path:
            state["slowed"] += 1
            until(wait + LATE_S if case == "reread-late" else TIMELY_S)
            activity()   # the helper's first activity, first seen by this re-read
        return real_read(p, *args, **kwargs)

    def probe(*args, **kwargs):
        if not case.startswith("reread") and state["t_lanes"] is not None and not state["slowed"]:
            state["slowed"] += 1
            until(wait + LATE_S if case == "probe-late" else WAIT0_S if case == "wait0"
                  else TIMELY_S)
        return real_probe(*args, **kwargs)

    ho.read_record, ho.launch_lanes, ho.lane_activity_stamp = read, lanes_entered, probe
    sys.argv = ["handsoff.py", "launch-check", "--run", run, "--lanes", "T1", "--wait", wait_text,
                "--poll-s", "0.3", "--detach-safe"]
    try:
        ho.main()
        code = 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
finally:
    for proc in (head, lane):
        proc.kill()
        proc.wait()
sys.stdout.flush()
print("slowed %d" % state["slowed"])
print("rc %s" % code)
HF3LAUNCH
}
for hf3_case in reread-late:2 probe-late:2 reread-timely:8 probe-timely:8 wait0:0; do
  hf3_tag=${hf3_case%%:*}; hf3_wait=${hf3_case#*:}
  fixture "hf3launch-$hf3_tag" 200
  hf3_launch "hf3launch-$hf3_tag" "$hf3_tag" "$hf3_wait" >"$WORK/hf3launch-$hf3_tag.out" 2>&1
done
for hf3_tag in reread-late probe-late; do
  O="$WORK/hf3launch-$hf3_tag.out"
  grep -q -F "slowed 1" "$O" || why="$why; the late re-read or probe never came during the wait ($hf3_tag, the premise)"
  grep -q -F "T1 progressing" "$O" || why="$why; the helper's late readiness was never read ($hf3_tag, the premise)"
  need_eq "$(grep '^rc ' "$O")" "rc 1" "exit ($hf3_tag)"
  grep -q -F "NOT CLEAN" "$O" || why="$why; no NOT CLEAN line ($hf3_tag)"
  grep -q -F "past the 2 s deadline" "$O" || why="$why; the late first batch is not named ($hf3_tag)"
  if grep -q -F "STARTED CLEAN" "$O"; then why="$why; certified ($hf3_tag)"; fi
done
for hf3_tag in reread-timely probe-timely wait0; do
  O="$WORK/hf3launch-$hf3_tag.out"
  grep -q -F "slowed 1" "$O" || why="$why; the slow re-read or probe never came ($hf3_tag, the premise)"
  need_eq "$(grep '^rc ' "$O")" "rc 0" "exit ($hf3_tag, a control)"
  grep -q -F "STARTED CLEAN" "$O" || why="$why; the control $hf3_tag is not certified"
  grep -q -F "T1 progressing" "$O" || why="$why; the control $hf3_tag does not read the helper's activity"
done
verdict "launch-check --lanes (fails on old; the third review of 2026-10-11, finding N2, D21 (c)): a first batch first seen ready past the deadline, through a re-read or a helper probe that returns late, is NOT CLEAN (exit 1, the late batch named), every certification reading the clock after its last read or probe; the same re-read or probe inside the deadline and a single read under --wait 0 with a slow probe still certify (the controls)"
# HF3-END


# HF4-BEGIN
# Finding R1: every new acknowledgement-shaped observation carries the size of the snapshot
# its writer read, including the two ledger forms. The relay is appended after that first
# read returns its snapshot and before the ledger sees the return, so the interleaving is
# deterministic. The absent-record case instead relays immediately before the ledger append:
# the ledger checked an empty snapshot and cannot cover the new relay. One leg includes the
# ordinary, already-read, legacy, plain-record and dry-run controls.
hf4_ledger() { # $1 run, $2 observation|row, $3 after|before|none|creation, $4 ack|ordinary
  "$PY" - "$H" "$1" "$2" "$3" "$4" <<'HF4LEDGER'
import importlib.util, json, os, sys


def failed(reason):
    print("PROBE FAILED: " + reason, file=sys.stderr)
    raise SystemExit(2)


spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, form, timing, kind = sys.argv[2:]
if form not in ("observation", "row") or timing not in ("after", "before", "none", "creation") \
        or kind not in ("ack", "ordinary"):
    failed("the ledger fixture has an unknown form, timing or kind")
path = ho.record_path(run)
relay_text = "AUTHOR ruling: HF4-RELAY the next item waits for review"
text = "ack: read the current record" if kind == "ack" else "ordinary finding mentioning ack: later"


def rows():
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            result = [json.loads(line) for line in handle if line.strip()]
    except (OSError, ValueError) as exc:
        failed("cannot read the ledger fixture: %s" % exc)
    if any(not isinstance(row, dict) for row in result):
        failed("the ledger fixture contains a non-object record")
    return result


initial = rows()
if timing in ("none", "creation"):
    if os.path.exists(path) or form != "observation":
        failed("the new-record control needs an absent observation record")
elif not initial:
    failed("the existing-record control has no record events")
if any(row.get("what") == relay_text or row.get("what") == text for row in initial):
    failed("the ledger fixture already contains this leg's relay or entry")
state = {"reads": 0, "relays": 0, "appends": 0, "snapshot": None}


def relay():
    if state["relays"]:
        failed("the relay would be planted more than once")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": ho.now(), "run": run, "event": "observation",
                                 "phase": "", "what": relay_text}) + "\n")
    state["relays"] += 1


if timing == "before":
    relay()
checked = rows()
real_read, real_append = ho.read_record, ho.append_record


def read(target, *args, **kwargs):
    result = real_read(target, *args, **kwargs)
    if os.path.realpath(target) == os.path.realpath(path):
        state["reads"] += 1
        if state["snapshot"] is None:
            if result[1] or result[0] != checked:
                failed("the first read did not return the planted snapshot")
            state["snapshot"] = len(result[0])
            if timing == "after":
                relay()
    return result


def append(target, payload):
    if os.path.realpath(target) == os.path.realpath(path) and payload.get("what") == text:
        state["appends"] += 1
        if timing == "creation":
            if state["reads"] or os.path.exists(path):
                failed("the creation race did not reach the first append on an absent record")
            relay()
    return real_append(target, payload)


ho.read_record, ho.append_record = read, append
sys.argv = ["handsoff.py", "ledger", "--run", run]
if form == "observation":
    sys.argv += ["--observation", text]
else:
    sys.argv += ["--phase", "review", "--what", text, "--evidence", "fixture", "--routing", "review"]
try:
    ho.main()
    code = 0
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
ho.read_record, ho.append_record = real_read, real_append
if timing in ("before", "after") and state["snapshot"] is None:
    failed("the existing ledger call never reached the record read")
if timing in ("before", "after", "creation") and state["relays"] != 1:
    failed("the planted relay did not land exactly once")
if state["appends"] != 1:
    failed("the ledger call did not reach its single observation append")
events = rows()
entries = [row for row in events if row.get("event") == "observation" and row.get("what") == text]
if len(entries) != 1:
    failed("the record does not contain the single ledger entry")
if timing == "after" and events[len(checked)].get("what") != relay_text:
    failed("the relay did not occupy the first place after the snapshot")
if timing in ("after", "creation") and events[-1].get("what") != text:
    failed("the raced ledger entry did not land after the relay")
entry = entries[0]
covered = json.dumps(entry["decisions_seen"]) if "decisions_seen" in entry else "absent"
print("rc %d" % code)
print("snapshot %d" % (state["snapshot"] if state["snapshot"] is not None else 0))
print("coverage " + covered)
print("pending %d" % len(ho.decisions_pending(events, None)[0]))
print("relays %d" % state["relays"])
print("reads %d" % state["reads"])
HF4LEDGER
}
hf4_pending() { # $1 run: pending AUTHOR count; read-only, malformed input is a failed premise
  "$PY" - "$H" "$1" <<'HF4PENDING'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
events, bad = ho.read_record(ho.record_path(sys.argv[2]))
if bad:
    print("PROBE FAILED: the pending probe read a malformed fixture", file=sys.stderr)
    raise SystemExit(2)
print(len(ho.decisions_pending(events, None)[0]))
HF4PENDING
}

for hf4_form in observation row; do
  hf4_run="hf4-ledger-$hf4_form"
  fixture "$hf4_run" 200
  mk transcript "sid-$hf4_run" 100000 >/dev/null || die "cannot make the ledger race's head transcript"
  HF4_SEEN=$(mk lines "$REC")
  HF4_ROWS=$(mk rows "$HO" "Findings ledger")
  HF4_BEFORE=$(sha_file "$REC")
  hf4_ledger "$hf4_run" "$hf4_form" after ack >"$WORK/hf4-ledger.out" 2>&1 \
      || die "the ledger race failed: $(cat "$WORK/hf4-ledger.out")"
  need_eq "$(grep '^rc ' "$WORK/hf4-ledger.out")" "rc 0" "the raced ledger succeeds ($hf4_form)"
  need_eq "$(grep '^snapshot ' "$WORK/hf4-ledger.out")" "snapshot $HF4_SEEN" "the first read's snapshot ($hf4_form)"
  need_eq "$(grep '^coverage ' "$WORK/hf4-ledger.out")" "coverage $HF4_SEEN" "explicit coverage stops before the relay ($hf4_form)"
  need_eq "$(grep '^pending ' "$WORK/hf4-ledger.out")" "pending 1" "the pending list keeps the raced relay ($hf4_form)"
  need_eq "$(grep '^relays ' "$WORK/hf4-ledger.out")" "relays 1" "the race's positive control ($hf4_form)"
  need_eq "$(mk lines "$REC")" "$((HF4_SEEN + 2))" "one relay and one ledger observation were appended ($hf4_form)"
  [ "$(sha_file "$REC")" != "$HF4_BEFORE" ] || why="$why; the checksum missed the planted record writes ($hf4_form)"
  if [ "$hf4_form" = row ]; then HF4_ROWS=$((HF4_ROWS + 1)); fi
  need_eq "$(mk rows "$HO" "Findings ledger")" "$HF4_ROWS" "the row form alone adds a ledger row ($hf4_form)"
  HF4_HELD_SUM="$(sha_file "$REC") $(sha_file "$HO")"
  # The second pass proves the first held call cannot itself clear or consume the relay.
  for hf4_again in first second; do
    run gate --run "$hf4_run" --to item2 --meter-line "$METER"
    need_rc 6
    need_out "HF4-RELAY the next item waits for review"
    need_eq "$(sha_file "$REC") $(sha_file "$HO")" "$HF4_HELD_SUM" "held gate changes no record or hand-off bytes ($hf4_form, $hf4_again)"
    run close --run "$hf4_run" --items "fixture items" --meter-line "$METER"
    need_rc 6
    need_out "HF4-RELAY the next item waits for review"
    need_eq "$(sha_file "$REC") $(sha_file "$HO")" "$HF4_HELD_SUM" "held close changes no record or hand-off bytes ($hf4_form, $hf4_again)"
  done
  HF4_ACK_SEEN=$(mk lines "$REC")
  run gate --run "$hf4_run" --to item2 --meter-line "$METER" --ack "read the relay: the next item waits for review"
  need_rc 0
  need_eq "$(mk field "$REC" observation decisions_seen)" "$HF4_ACK_SEEN" "the valid ack covers its own checked snapshot ($hf4_form)"
  HF4_PENDING=$(hf4_pending "$hf4_run") || die "cannot read the pending count after the fresh ack"
  need_eq "$HF4_PENDING" "0" "the fresh ack clears the planted relay ($hf4_form)"
  run gate --run "$hf4_run" --to item3 --meter-line "$METER"
  need_rc 0
  run close --run "$hf4_run" --items "fixture items" --meter-line "$METER"
  need_rc 0
  need_eq "$(mk count "$REC" run-close)" "1" "a valid acknowledgement lets the close through ($hf4_form)"
done

# Controls for both forms: a relay already inside the read snapshot remains covered, while an
# ordinary entry mentioning ack: away from its start leaves that same relay pending.
for hf4_form in observation row; do
  for hf4_kind in ack ordinary; do
    hf4_run="hf4-ledger-before-$hf4_form-$hf4_kind"
    fixture "$hf4_run" 200
    mk transcript "sid-$hf4_run" 100000 >/dev/null || die "cannot make the ledger control's head transcript"
    HF4_SEEN=$(mk lines "$REC"); HF4_SEEN=$((HF4_SEEN + 1))
    hf4_ledger "$hf4_run" "$hf4_form" before "$hf4_kind" >"$WORK/hf4-ledger-before.out" 2>&1 \
        || die "the ledger control failed: $(cat "$WORK/hf4-ledger-before.out")"
    need_eq "$(grep '^rc ' "$WORK/hf4-ledger-before.out")" "rc 0" "the ledger control succeeds ($hf4_form, $hf4_kind)"
    need_eq "$(grep '^snapshot ' "$WORK/hf4-ledger-before.out")" "snapshot $HF4_SEEN" "the relay precedes the snapshot ($hf4_form, $hf4_kind)"
    need_eq "$(grep '^relays ' "$WORK/hf4-ledger-before.out")" "relays 1" "the control's AUTHOR relay exists ($hf4_form, $hf4_kind)"
    if [ "$hf4_kind" = ack ]; then
      need_eq "$(grep '^coverage ' "$WORK/hf4-ledger-before.out")" "coverage $HF4_SEEN" "an already-read ledger ack still carries explicit coverage ($hf4_form)"
      need_eq "$(grep '^pending ' "$WORK/hf4-ledger-before.out")" "pending 0" "the already-read relay is covered ($hf4_form)"
      run gate --run "$hf4_run" --to item2 --meter-line "$METER"
      need_rc 0
      run close --run "$hf4_run" --items "fixture items" --meter-line "$METER"
      need_rc 0
    else
      need_eq "$(grep '^coverage ' "$WORK/hf4-ledger-before.out")" "coverage absent" "an ordinary ledger entry keeps its fields ($hf4_form)"
      need_eq "$(grep '^pending ' "$WORK/hf4-ledger-before.out")" "pending 1" "ordinary prose does not acknowledge the relay ($hf4_form)"
      HF4_HELD_SUM="$(sha_file "$REC") $(sha_file "$HO")"
      run gate --run "$hf4_run" --to item2 --meter-line "$METER"
      need_rc 6
      run close --run "$hf4_run" --items "fixture items" --meter-line "$METER"
      need_rc 6
      need_eq "$(sha_file "$REC") $(sha_file "$HO")" "$HF4_HELD_SUM" "the ordinary entry leaves both holds write-free ($hf4_form)"
    fi
  done
done

# No record was read on either creation path, so both new acks have coverage 0; a relay that
# created the file immediately before the ledger's append remains pending on the raced path.
for hf4_timing in none creation; do
  hf4_run="hf4-ledger-new-$hf4_timing"
  REC="$STORE/spawn-records/$hf4_run.jsonl"
  [ ! -e "$REC" ] || die "the new ledger fixture already exists"
  hf4_ledger "$hf4_run" observation "$hf4_timing" ack >"$WORK/hf4-ledger-new.out" 2>&1 \
      || die "the new-record ledger control failed: $(cat "$WORK/hf4-ledger-new.out")"
  need_eq "$(grep '^rc ' "$WORK/hf4-ledger-new.out")" "rc 0" "the new ledger record is created ($hf4_timing)"
  need_eq "$(grep '^snapshot ' "$WORK/hf4-ledger-new.out")" "snapshot 0" "the creation snapshot is empty ($hf4_timing)"
  need_eq "$(grep '^reads ' "$WORK/hf4-ledger-new.out")" "reads 0" "no record read preceded creation ($hf4_timing)"
  need_eq "$(grep '^coverage ' "$WORK/hf4-ledger-new.out")" "coverage 0" "new-record acknowledgements never receive legacy coverage ($hf4_timing)"
  if [ "$hf4_timing" = creation ]; then
    need_eq "$(grep '^pending ' "$WORK/hf4-ledger-new.out")" "pending 1" "the creation race keeps its relay pending"
    HF4_HELD_SUM=$(sha_file "$REC")
    run close --run "$hf4_run" --items "fixture items"
    need_rc 6
    need_out "HF4-RELAY the next item waits for review"
    need_eq "$(sha_file "$REC")" "$HF4_HELD_SUM" "the creation race holds a plain close without writing"
    run close --run "$hf4_run" --items "fixture items" --ack "read the relay: the next item waits for review"
    need_rc 0
  else
    need_eq "$(grep '^pending ' "$WORK/hf4-ledger-new.out")" "pending 0" "the empty creation control has no relay"
    run close --run "$hf4_run" --items "fixture items"
    need_rc 0
  fi
done

plain_fixture hf4-ledger-plain
HF4_SEEN=$(mk lines "$REC")
hf4_ledger hf4-ledger-plain observation after ack >"$WORK/hf4-ledger-plain.out" 2>&1 \
    || die "the plain-record ledger race failed: $(cat "$WORK/hf4-ledger-plain.out")"
need_eq "$(grep '^snapshot ' "$WORK/hf4-ledger-plain.out")" "snapshot $HF4_SEEN" "the plain record has its own checked snapshot"
need_eq "$(grep '^coverage ' "$WORK/hf4-ledger-plain.out")" "coverage $HF4_SEEN" "the plain-record ack carries explicit coverage"
need_eq "$(grep '^pending ' "$WORK/hf4-ledger-plain.out")" "pending 1" "the plain-record relay stays pending"
HF4_HELD_SUM=$(sha_file "$REC")
run close --run hf4-ledger-plain --items "fixture items"
need_rc 6
need_eq "$(sha_file "$REC")" "$HF4_HELD_SUM" "the plain record's held close writes nothing"
run close --run hf4-ledger-plain --items "fixture items" --ack "read the relay: the next item waits for review"
need_rc 0

# Historical records with absent coverage remain historical: the fixture supplies its old ack
# directly, rather than asking a current writer to fabricate one without the new field.
fixture hf4-ledger-legacy 200
mk transcript sid-hf4-ledger-legacy 100000 >/dev/null || die "cannot make the legacy control's head transcript"
mk append "$REC" '{"event":"observation","what":"AUTHOR ruling: HF4-LEGACY relay"}' >/dev/null \
    || die "cannot plant the legacy relay"
mk append "$REC" '{"event":"observation","what":"ack: historical acknowledgement"}' >/dev/null \
    || die "cannot plant the historical acknowledgement"
need_eq "$(mk field "$REC" observation decisions_seen)" "<no key decisions_seen>" "the historical ack has genuinely absent coverage"
HF4_PENDING=$(hf4_pending hf4-ledger-legacy) || die "cannot read the legacy pending count"
need_eq "$HF4_PENDING" "0" "the legacy reader still covers the historical relay"
run gate --run hf4-ledger-legacy --to item2 --meter-line "$METER"
need_rc 0
run close --run hf4-ledger-legacy --items "fixture items" --meter-line "$METER"
need_rc 0

# Dry runs preserve both record and hand-off checksums. The observation form also prints its
# coverage, including the absent-record snapshot; the row form prints only its proposed row.
fixture hf4-ledger-dry 200
mk append "$REC" '{"event":"observation","what":"AUTHOR ruling: HF4-DRY relay"}' >/dev/null \
    || die "cannot plant the dry-run relay"
HF4_SEEN=$(mk lines "$REC")
HF4_DRY_SUM="$(sha_file "$REC") $(sha_file "$HO")"
run ledger --run hf4-ledger-dry --observation "ack: dry read of the record" --dry-run
need_rc 0
need_out "\"decisions_seen\": $HF4_SEEN"
need_eq "$(sha_file "$REC") $(sha_file "$HO")" "$HF4_DRY_SUM" "the dry observation changes no bytes"
run ledger --run hf4-ledger-dry --phase review --what "ack: dry read of the record" --evidence fixture --routing review --dry-run
need_rc 0
need_eq "$(sha_file "$REC") $(sha_file "$HO")" "$HF4_DRY_SUM" "the dry row changes no bytes"
HF4_PENDING=$(hf4_pending hf4-ledger-dry) || die "cannot read the dry-run pending count"
need_eq "$HF4_PENDING" "1" "dry-run acknowledgements never clear the positive-control relay"
need_nofile "$STORE/spawn-records/hf4-ledger-dry-new.jsonl"
run ledger --run hf4-ledger-dry-new --observation "ack: dry read of an absent record" --dry-run
need_rc 0
need_out '"decisions_seen": 0'
need_nofile "$STORE/spawn-records/hf4-ledger-dry-new.jsonl"
verdict "ledger acknowledgement coverage (fails on old; fourth review, R1): both ledger forms bound every new ack to the snapshot they read, so a relay racing either read stays pending and repeatedly holds gate and close with exit 6 and unchanged checksums until a valid ack; empty and plain records also carry bounded coverage, creation races stay pending, and already-read acknowledgements, ordinary entries, genuine legacy records and dry runs keep their behaviour (the controls)"

# R2: the shared launch deadline starts before the first record read and its preceding probes.
# Each case starts a live head; the batch cases complete T1 during the first read. The late
# read, or the file-existence probe before it, sleeps --wait plus 0.5 s. The 0.5 s margin,
# timely delay of 0.5 s, wait-zero delay of 1 s, and 8 s timely budget are set by judgement,
# unmeasured. Each late case must fail; the timely and wait-zero controls still certify on one
# read. The same checks fail against the pre-fold copy, which starts its budget after the delay.
hf4_launch_initial() { # $1 run, $2 head|batch, $3 read-late|probe-late|timely|wait0, $4 wait
  "$PY" - "$H" "$1" "$2" "$3" "$4" <<'HF4LAUNCHINITIAL'
import importlib.util, json, os, subprocess, sys, time
spec = importlib.util.spec_from_file_location("ho", sys.argv[1])
ho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ho)
run, mode, case, wait_text = sys.argv[2:]
path = ho.record_path(run)
wait = float(wait_text)
delay = wait + 0.5 if case.endswith("late") else 1.0 if case == "wait0" else 0.5
# The sleeper's 60 s bound is set by judgement, unmeasured; finally always reaps it.
head = subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, start_new_session=True)
state = {"slowed": 0, "reads": 0, "batch_ready": 0}
real_read, real_isfile = ho.read_record, os.path.isfile
code = None


def add(ev):
    ev.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()))
    ev["run"] = run
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev) + "\n")


def slow():
    state["slowed"] += 1
    time.sleep(delay)


def read(p, *args, **kwargs):
    if p == path:
        state["reads"] += 1
        if state["reads"] == 1:
            if case != "probe-late":
                slow()
            if mode == "batch":
                add({"event": "lane-closed", "lane": "T1", "exit_class": "completed"})
                state["batch_ready"] += 1
    return real_read(p, *args, **kwargs)


def isfile(p):
    if p == path and case == "probe-late" and not state["slowed"]:
        slow()
    return real_isfile(p)


try:
    add({"event": "head-successor", "session_id": "sid-%s" % run, "pid": head.pid,
         "model": "fixture-model", "effort": "max"})
    if mode == "batch":
        add({"event": "lane-open", "lane": "T1", "class": "builder", "model": "fixture-model",
             "session_id": "sid-%s-T1" % run})
    ho.read_record, os.path.isfile = read, isfile
    sys.argv = ["handsoff.py", "launch-check", "--run", run, "--wait", wait_text,
                "--poll-s", "0.3", "--detach-safe"]
    if mode == "batch":
        sys.argv.extend(["--lanes", "T1"])
    try:
        ho.main()
        code = 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
finally:
    ho.read_record, os.path.isfile = real_read, real_isfile
    head.kill()
    head.wait()
if state["slowed"] != 1 or state["reads"] != 1 or state["batch_ready"] != (mode == "batch"):
    print("PROBE FAILED: initial-read delay or ready-batch premise: %r" % state)
    sys.exit(2)
print("slowed %d reads %d batch_ready %d" % (state["slowed"], state["reads"], state["batch_ready"]))
print("rc %s" % code)
HF4LAUNCHINITIAL
}
for hf4_mode in head batch; do
  for hf4_case in read-late:2 probe-late:2 timely:8 wait0:0; do
    hf4_tag=${hf4_case%%:*}; hf4_wait=${hf4_case#*:}
    fixture "hf4initial-$hf4_mode-$hf4_tag" 200
    hf4_launch_initial "hf4initial-$hf4_mode-$hf4_tag" "$hf4_mode" "$hf4_tag" "$hf4_wait" \
      >"$WORK/hf4initial-$hf4_mode-$hf4_tag.out" 2>&1 || die "initial launch-read regression premise failed ($hf4_mode, $hf4_tag): $(cat "$WORK/hf4initial-$hf4_mode-$hf4_tag.out")"
  done
  for hf4_tag in read-late probe-late; do
    O="$WORK/hf4initial-$hf4_mode-$hf4_tag.out"
    need_eq "$(grep '^rc ' "$O")" "rc 1" "exit ($hf4_mode, $hf4_tag)"
    grep -q -F "NOT STARTED" "$O" || why="$why; the late initial read certified ($hf4_mode, $hf4_tag)"
    if grep -q -E '^launch-check: [^ ]+ STARTED( |$)' "$O"; then why="$why; a success line survived ($hf4_mode, $hf4_tag)"; fi
  done
  for hf4_tag in timely wait0; do
    O="$WORK/hf4initial-$hf4_mode-$hf4_tag.out"
    need_eq "$(grep '^rc ' "$O")" "rc 0" "exit ($hf4_mode, $hf4_tag, a control)"
    grep -q -E '^launch-check: [^ ]+ STARTED( |$)' "$O" || why="$why; the single-read control failed ($hf4_mode, $hf4_tag)"
    if [ "$hf4_mode" = batch ]; then
      grep -q -F "STARTED CLEAN" "$O" || why="$why; the ready batch control failed ($hf4_tag)"
      grep -q -F "T1 done" "$O" || why="$why; the control's newly ready helper was not read ($hf4_tag)"
    fi
  done
done
verdict "launch-check (fails on old; fourth review finding R2): the first record read and preceding file probe share the deadline, so late head-only and first-batch checks never certify; timely reads and delayed --wait 0 checks certify with one read (the controls)"
# HF4-END

# ================== the hand-over checks (2026-10-30; register entries 2026-10-30 16:11 and
# 2026-10-25 16:28) ===========================================================================
# One block, before the write proof, so every leg numbered above keeps its number. Each leg is
# built to fail on the code before the change and pass on it (the build's fail-on-old run records
# both). The successor count is successors_left's: the record's head-successor events against the
# run's cap (the grants file, then AIMYTH_MAX_SUCCESSORS, then the default of 20).
hc_plant() { # $1 record, $2 count: that many hand-overs (head-exit, head-successor, the started
             # head's own run-resume), the last head live
  "$PY" - "$1" "$2" <<'HCPLANT'
import json, sys, time
path, n = sys.argv[1], int(sys.argv[2])
run = json.loads(open(path, encoding="utf-8").readline())["run"]
stamp = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))
base = time.time() - 3600
with open(path, "a", encoding="utf-8") as fh:
    for i in range(n):
        sid = "sid-%s-%d" % (run, i)
        for ev in ({"event": "head-exit", "band": 60, "context": "c", "spent_usd": 1.0, "pack": True},
                   {"event": "head-successor", "session_id": sid, "budget": 1.0,
                    "model": "fixture-model"},
                   {"event": "run-resume", "session": sid, "head": "fixture head",
                    "detail": "the head's own first act", "pid_src": "none"}):
            ev.update(ts=stamp(base + 10 * i), run=run)
            fh.write(json.dumps(ev) + "\n")
HCPLANT
}
hc_obs() { # $1 record, $2 an observation's `what`: how many the record holds
  "$PY" -c 'import json, sys
n = 0
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    n += isinstance(e, dict) and e.get("event") == "observation" and e.get("what") == sys.argv[2]
print(n)' "$1" "$2"
}
hc_after_start() { # $1 record, $2 kind: that kind's events after the record's last head start
  "$PY" -c 'import json, sys
ev = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict):
        ev.append(e)
s = max([i for i, e in enumerate(ev) if e.get("event") in ("run-open", "run-resume", "head-successor", "head-resumed")] or [-1])
print(sum(1 for e in ev[s + 1:] if e.get("event") == sys.argv[2]))' "$1" "$2"
}
hc_pack() { printf -- '- Next: item3, the fixture item\n- Needs: nothing\n- Decided: nothing\n' > "$1"; }
# The stub head runs from the starter's working directory (the fixture vault), so the script it
# calls is named by its absolute path: $H is relative when the suite is started from its own folder.
SUITE_HABS="$SKILL_DIR/$(basename "$H")"; export SUITE_HABS
HCPACK="$WORK/hc-pack.md"
hc_pack "$HCPACK"
hc_load='import importlib.util, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs_hc", sys.argv[1])
hs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hs)
'

# ---- DA-1 (must fire): `successor` at the cap refuses (exit 10) before anything is written ----
fixture hcda1 200
hc_plant "$REC" 6
run grants --run hcda1 --max-successors 6
viewer_use hcda1
HCX=$(mk count "$REC" head-exit)
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcda1 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 \
    --max-wait-s 1 --tick-s 1
need_rc 10
need_out "successor: REFUSED (exit 10): no successor left for run hcda1 — 6 of 6 head starts on its cap (the grants file $REALSTORE/spawn-records/hcda1-grants.json)"
need_out "Nothing was written but this refusal's observation"
need_eq "$(mk count "$REC" head-exit)" "$HCX" "head-exits (unchanged)"
need_eq "$(hc_obs "$REC" pack-fresh)" "0" "pack-fresh"
need_eq "$(hc_obs "$REC" "successor refused: no successor left")" "1" "the refusal's observation"
need_nofile "$REALSTORE/spawn-records/hcda1-head-1.out.starter.log"
need_no_viewer
sh -c 'exit 0' &
HCDEAD=$!
wait "$HCDEAD" || :
run grants --run hcda1 --max-successors 7
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run hcda1 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --predecessor-pid "$HCDEAD" --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
need_file "$REALSTORE/spawn-records/hcda1-head-1.out.starter.log"
wait_field "$REC" head-successor session_id sid-by-the-head 40
verdict "DA-1 (must fire; register 2026-10-30 16:11): successor at 6 of 6 exits 10 naming the count and the grants file, with no head-exit, pack-fresh, starter or console and one refusal observation; the control on the same run, the cap raised to 7, exits 0 and its starter starts the head"

# ---- DA-2 (must fire): `handoff --final` at the cap writes the pack and no head-exit ----
fixture hcda2 200
hc_plant "$REC" 6
run grants --run hcda2 --max-successors 6
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcda2 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 10
need_out "handoff: REFUSED (exit 10): no successor left for run hcda2"
need_out "The pack is written to '## In flight'"
grep -q -- "- Next: item3, the fixture item" "$HO" || why="$why; In flight lacks the pack's Next line"
grep -q -- "- pack written: " "$HO" || why="$why; In flight lacks the pack's age stamp"
need_eq "$(hc_after_start "$REC" head-exit)" "0" "head-exits after the head's start"
need_eq "$(hc_obs "$REC" "handoff --final refused: no successor left")" "1" "the refusal's observation"
run grants --run hcda2 --max-successors 7
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcda2 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 0
need_out "head-exit recorded (band 80"
need_eq "$(hc_after_start "$REC" head-exit)" "1" "the control's head-exit"
verdict "DA-2 (must fire): handoff --final at 6 of 6 exits 10, its pack written to In flight with its age stamp, no head-exit after the head's start and one refusal observation; the control at 6 of 7 exits 0 and writes its head-exit"

# ---- DA-3: the dry runs at the cap refuse and write nothing; below it each proceeds ----
fixture hcda3 200
hc_plant "$REC" 6
run grants --run hcda3 --max-successors 6
HCR=$(sha_file "$REC"); HCH=$(sha_file "$HO")
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcda3 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER" --dry-run
need_rc 10
need_out "handoff: dry run · would rewrite"
need_out "REFUSED (exit 10): successors: 6 of 6 started, none left"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcda3 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --dry-run
need_rc 10
need_out "Nothing was written (dry run)"
need_eq "$(sha_file "$REC") $(sha_file "$HO")" "$HCR $HCH" "the record and the hand-off (sha256)"
run grants --run hcda3 --max-successors 7
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcda3 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER" --dry-run
need_rc 0
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcda3 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --dry-run
need_rc 0
verdict "DA-3: handoff --final --dry-run and successor --dry-run at the cap each exit 10 with the record's and the hand-off's sha256 unchanged; below the cap each exits 0 (the control)"

# ---- DA-4 (must fire, wiring; review CR-CAP2 finding 5 a): start_guards reads successors_left ----
fixture hcda4 200
run grants --run hcda4 --max-successors 4
HCW=$("$PY" - "$H" <<HCWIRE
$hc_load
ev = [{"event": "run-open", "run": "hcda4", "session": "s0"}]
for i in range(3):
    ev += [{"event": "head-exit", "band": 60, "run": "hcda4"},
           {"event": "head-successor", "session_id": "s%d" % (i + 1), "run": "hcda4"}]
ev.append({"event": "head-exit", "band": 60, "run": "hcda4"})
hi = len(ev) - 1
below = hs.successors_left(ev, "hcda4")["left"], hs.start_guards(ev, hi, run="hcda4")[0]
at = ev[:hi] + [{"event": "head-successor", "session_id": "s4", "run": "hcda4"}, ev[hi]]
atcap = hs.successors_left(at, "hcda4")["left"], hs.start_guards(at, len(at) - 1, run="hcda4")[0]
hs.successors_left = lambda events, run: {"used": 0, "cap": 0, "src": "planted", "left": 0,
                                          "fault": None, "own": False, "run": run}
wired = hs.start_guards(ev, hi, run="hcda4")[0]
print("below %s %s · at %s %s · wired %s" % (below + atcap + (wired,)))
HCWIRE
)
need_eq "$HCW" "below 1 None · at 0 successor-cap · wired successor-cap" "the count and the guard (wired: a planted count of 0 left refuses)"
verdict "DA-4 (must fire, the wiring case of finding 5 a): at 3 of 4 one is left and start_guards admits; one more head-successor leaves 0 and it refuses successor-cap; a successors_left replaced in the imported copy by one reading 0 left at 0 used makes start_guards refuse, so the starter's guard reads the shared count"

# ---- DA-5: the stated source names the grants file's real state; a faulty file is no decided cap ----
fixture hcda5 200
hc_plant "$REC" 20
printf 'not json at all\n' > "$REALSTORE/spawn-records/hcda5-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcda5 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --dry-run
need_rc 10
need_out "the default (the grants file: unreadable ("
need_out "own successor cap cannot be read"
need_absent "this is the run's last lead"
fixture hcda5b 200
hc_plant "$REC" 20
printf '{}\n' > "$REALSTORE/spawn-records/hcda5b-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcda5b --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --dry-run
need_rc 10
need_out "the default (the grants file: readable, no max_successors key; no AIMYTH_MAX_SUCCESSORS)"
need_out "no successor left for run hcda5b"
fixture hcda5c 200
hc_plant "$REC" 5
run grants --run hcda5c --max-successors 6
run run-resume --run hcda5c --session sid-hcda5c-4 --head "fixture head" --detail "the count"
need_rc 0
need_out "· successors: 5 of 6 started, 1 left"
need_absent "1 left ("
verdict "DA-5 (finding 10 f; CR-CAP2 finding 6): a garbage grants file at 20 used names 'the default (the grants file: unreadable (' and the file fault, never the run's last lead; a readable {} names 'readable, no max_successors key'; the control, a valid key, prints the short form with no source"

# ---- DA-6 (must fire; finding 3 a): band 90 at none left, through what follows ----
fixture hcda6 200
hc_plant "$REC" 6
mk append "$REC" '{"event":"gate","item":"item2","decision":"allow","context":100000,"percent":10,"band":0,"armed":true,"metered":true}' >/dev/null
run grants --run hcda6 --max-successors 6
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcda6 --final --band 90 --inflight-file "$HCPACK" --meter-line "$METER"
HC6="$RC"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcda6 --band 90 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1
HC6="$HC6 $RC"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcda6 --final --band 90 --inflight-file "$HCPACK" --meter-line "$METER"
HC6="$HC6 $RC"
RUNENV="PATH=$WORK/psnone:$PATH"
run close --run hcda6 --meter-line "$METER" --items "1" --register "none" --log "one line" \
    --lint "clean" --parity "not yet"
HC6="$HC6 $RC"
need_eq "$HC6" "10 10 10 0" "the exits of handoff --final, successor, handoff --final and close"
need_eq "$(hc_after_start "$REC" head-exit)" "0" "head-exits after the head's start"
need_eq "$(( $(hc_obs "$REC" "handoff --final refused: no successor left") + $(hc_obs "$REC" "successor refused: no successor left") ))" "3" "refusal observations"
need_eq "$(mk count "$REC" run-close)" "1" "run-close"
# (ii) the head ends instead of closing: the starter's stub head runs the refused calls and completes;
# the supervisor writes the head-exit it owes and aborts successor-cap; the cap raised, an attended
# restart starts a head and no repeat-exit abort follows.
fixture hcda6b 200
hc_plant "$REC" 5
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
run grants --run hcda6b --max-successors 6
RSRC=0
env $RS_ENV STUB_MODES=complete STUB_PROGRESS=refusedhandover STUB_N=1 STUB_RESUME=1 \
    AIMYTH_VIEWER_ARGV="$WORK/viewer-hcda6b.argv" "$PY" -B "$H" _starter --run hcda6b \
    --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcda6b-head-1.out" --wait-s 2 \
    --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 >"$WORK/hcda6b.log" 2>&1 || RSRC=$?
need_eq "$RSRC" "1" "the starter's exit (successor-cap)"
need_eq "$(grep -c '^rc final 10$' "$WORK/stub-hcda6b.refused") $(grep -c '^rc successor 10$' "$WORK/stub-hcda6b.refused")" "2 1" "the stub head's refused calls"
need_eq "$(mk field "$REC" successor-aborted reason)" "successor-cap" "the supervisor's abort"
need_eq "$(hc_after_start "$REC" head-exit)" "1" "head-exits after the head's start (the supervisor's owed one alone)"
run grants --run hcda6b --max-successors 7
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=1"
run successor --run hcda6b --seed-pid --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
wait_field "$REC" head-successor session_id sid-by-the-head 40
need_eq "$(rs_count "$REC" successor-aborted)" "1" "no abort after the restart (no repeat-exit)"
# The control on the same shape before this patch: two band-90 head-exits by one head after the
# gate allowing item2, and the restart's starter aborts repeat-exit.
fixture hcda6c 200
hc_plant "$REC" 6
mk append "$REC" '{"event":"gate","item":"item2","decision":"allow","context":100000,"percent":10,"band":0,"armed":true,"metered":true}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":90,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":90,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
run grants --run hcda6c --max-successors 7
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run hcda6c --seed-pid --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
wait_field "$REC" successor-aborted reason repeat-exit 40
verdict "DA-6 (must fire; finding 3 a): at 6 of 6 after a gate allowing item2, handoff --final --band 90, successor and a second handoff --final --band 90 each exit 10 and close exits 0, with no head-exit after the head's start, three refusal observations and one run-close; a stub head that runs the same refusals and completes leaves only the supervisor's owed head-exit, and the restart after the cap is raised starts a head with no repeat-exit; the control, two band-90 exits planted, aborts repeat-exit"

# ---- DA-7 (must fire; finding 3 c): a refused hand-over, then a limit under on_limit resume ----
fixture hcda7 200
hc_plant "$REC" 2
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
run grants --run hcda7 --max-successors 3
arm_resume hcda7
RUNENV="STUB_MODE=limit STUB_N=1 STUB_PROGRESS=refusedhandover STUB_RESUME=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run hcda7 --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcda7-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
need_eq "$(grep -c '^rc final 10$' "$WORK/stub-hcda7.refused") $(grep -c '^rc successor 10$' "$WORK/stub-hcda7.refused")" "2 1" "the stub head's refused calls (3 of 3)"
need_eq "$(mk count "$REC" head-resumed)" "1" "resumed in place"
need_eq "$(rs_count "$REC" successor-aborted)" "0" "no abort"
fixture hcda7c 200
hc_plant "$REC" 2
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
run grants --run hcda7c --max-successors 3
arm_resume hcda7c
RUNENV="STUB_MODE=limit STUB_N=1 STUB_PROGRESS=oldhandover STUB_RESUME=1 STUB_TOKENS=50000 AIMYTH_CONTEXT_WINDOW=200000"
starter --run hcda7c --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcda7c-head-1.out" --wait-s 5 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --reset-at +1s --tick-s 1
case $(rs_obs "$REC") in
  unsucceeded:*) : ;;
  *) why="$why; the control's stop class: $(rs_obs "$REC")" ;;
esac
need_eq "$(mk count "$REC" head-resumed)" "0" "the control: no resume"
verdict "DA-7 (must fire; finding 3 c): a head refused at 3 of 3 that then stops on a limit under on_limit resume is resumed in place with no abort; the control, the shape before this patch (a head-exit then the refusal observation), stops unsucceeded and is not resumed"

# ---- DA-8: the seeded first launch is never refused, and the count is printed from the start ----
seed_fixture hcda8 200
run grants --run hcda8 --max-successors 1
RUNENV="PATH=$WORK/psnone:$PATH"
run gate --run hcda8 --to item1 --meter-line "$METER" --dry-run
need_rc 0
need_out "successors: 0 of 1 started, 1 left"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcda8 --final --band 60 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 0
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
run successor --run hcda8 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 5 \
    --max-wait-s 5 --tick-s 1
need_rc 0
wait_field "$REC" head-successor session_id sid-by-the-head 40
verdict "DA-8: on a seeded record at 0 of 1 the gate prints 'successors: 0 of 1 started, 1 left', and handoff --final and successor both proceed (a refusal at the cap is never the seed's)"

# ---- DA-9 (the count, warn): gate, the band refusal, the envelope stop and run-resume ----
fixture hcda9 200
hc_plant "$REC" 3
run grants --run hcda9 --max-successors 14
mk transcript sid-hcda9-2 100000 >/dev/null
run gate --run hcda9 --to "item one" --meter-line "$METER"
need_rc 0
need_out "· successors: 3 of 14 started, 11 left"
need_eq "$(mk field "$REC" gate successors_used) $(mk field "$REC" gate successors_cap) $(mk field "$REC" gate successors_left)" "3 14 11" "the gate event's count"
need_eq "$(mk field "$REC" gate successors_src)" "the grants file $REALSTORE/spawn-records/hcda9-grants.json" "the gate event's source"
run run-resume --run hcda9 --session sid-hcda9-2 --head "fixture head" --detail "the count"
need_rc 0
need_out "· successors: 3 of 14 started, 11 left"
fixture hcda9b 200
hc_plant "$REC" 14
run grants --run hcda9b --max-successors 14
mk transcript sid-hcda9b-13 850000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcda9b --to "item two" --meter-line "$METER"
need_rc 4
need_out "→ no successor is left (successors: 14 of 14 started): watch in-flight lanes to their close while the room lasts, then close the run with its morning report"
need_absent "then successor"
case $(mk field "$REC" stop-condition note) in
  *"then close the run with its morning report"*) : ;;
  *) why="$why; the stop-condition note does not say close: $(mk field "$REC" stop-condition note)" ;;
esac
fixture hcda9c 200
hc_plant "$REC" 13
run grants --run hcda9c --max-successors 14
mk transcript sid-hcda9c-12 850000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcda9c --to "item two" --meter-line "$METER"
need_rc 4
need_out "→ handoff --final --band 80, watch in-flight lanes, then successor"
need_out "successors: 13 of 14 started, 1 left"
fixture hcda9d 10
hc_plant "$REC" 14
run grants --run hcda9d --max-successors 14
run gate --run hcda9d --to "item two" --meter-line "$METER"
need_rc 5
need_out "the owner tops the envelope up before any successor"
need_out "· successors: 14 of 14 started, none left"
verdict "DA-9 (warn): the gate line and event carry 'successors: 3 of 14 started, 11 left' and run-resume's line the same; at 14 of 14 the armed band refusal (exit 4) and its stop-condition note say close the run and never 'then successor', while at 13 of 14 the hand-over text stands (the control); the envelope stop (exit 5) keeps the owner's top-up text and carries the count"

# ---- DB-1 (the classifier, on planted tables) ----
HCB=$("$PY" - "$H" <<HCTABLE
$hc_load
H, S, X = 300, 200, 100
BASE = {H: (1, "Ss", "01:00:00", "/fixture/bin/claude --print"),
        S: (H, "Ss", "00:01", "/bin/zsh -c the call; more"),
        X: (S, "S", "00:01", "python3 handsoff.py successor")}
TASK = {400: (H, "Ss", "12:34", "/bin/zsh -c sleep 600; true"), 401: (400, "S", "12:34", "sleep 600")}
HARN = {H: (H, 1, "/fixture/bin/claude")}
def go(table, chain=([X, S, H], True), rows=HARN, pred=H, seed=False):
    hs.process_chain_read = lambda: (list(chain[0]), chain[1])
    hs.ps_row = lambda pid, timeout=None: rows.get(pid)
    hs.process_table = ((lambda timeout=None: (dict(table), "")) if table is not None
                        else (lambda timeout=None: (None, "a planted unreadable table")))
    kind, lines = hs.background_tasks(seed, pred, 600)
    return kind, "\n".join(lines)
out = []
k, t = go({**BASE, **TASK})
out.append("found:%s:%d" % (k, ("pid 400 (running 12:34): sleep 600" in t) + ("TaskStop" in t)))
k, t = go(dict(BASE))
out.append("none:%s:%d" % (k, "control: this call's own shell, pid 200" in t))
k, _ = go({**BASE, 500: (H, "Ss", "00:10", "node mcp-server")})
out.append("nonshell:%s" % k)
k, _ = go({**BASE, 600: (H, "Zs", "00:10", "/bin/zsh")})
out.append("zombie:%s" % k)
k, _ = go({**BASE, S: (H, "S", "00:01", "/bin/zsh -c x")})
out.append("notleader:%s" % k)
k, _ = go({**BASE, S: (H, "Ss", "00:01", "python3 x")})
out.append("notshell:%s" % k)
k, t = go(None)
out.append("unreadable:%s:%d" % (k, "a planted unreadable table" in t))
k, _ = go(dict(BASE), chain=([X, S], True), pred=H)
out.append("outside:%s" % k)
k, _ = go(dict(BASE), chain=([X, S], False), pred=H)
out.append("notwhole:%s" % k)
k, t = go(dict(BASE), chain=([X, S, H], False), pred=H)
out.append("notwholein:%s:%d" % (k, "pid 300 is in the part read" in t))
k, _ = go(dict(BASE), rows={H: (H, 1, "/sbin/launchd")})
out.append("notharness:%s" % k)
k, _ = go(dict(BASE), seed=True)
out.append("seed:%s" % k)
print(" ".join(out))
HCTABLE
)
need_eq "$HCB" "found:found:2 none:none:1 nonshell:none zombie:none notleader:undecided notshell:undecided unreadable:undecided:1 outside:not-checked notwhole:undecided notwholein:undecided:1 notharness:not-checked seed:not-checked" "the planted cases"
verdict "DB-1 (the background-task classifier, planted tables): a session-leading zsh child of the harness beside the call's own shell is found and its sleep named; without it none, with the control named; a non-shell child and a zombie shell are not counted; the call's own shell not a session leader or not a shell, and an unreadable table, are undecided, never none; a chain walk that is not whole is undecided in both shapes, the predecessor missing from the part read or found in it (build review RV-CAP finding F7); a pid outside the chain, a pid that is not the harness and a seed are not checked"

# ---- DB-2 (must warn, end to end) and DB-3 (not checked): through the process-table stub ----
fixture hcdb2 200
viewer_use hcdb2
RUNENV="PATH=$WORK/pstable:$PATH PSTABLE_TASK=1 PSTABLE_LOG=$WORK/pstable-hcdb2.log STUB_MODE=complete STUB_N=0"
run successor --run hcdb2 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 5 \
    --max-wait-s 5 --tick-s 1
need_rc 0
need_out "successor: warn: head pid 4194301 still runs 1 background task(s) beside this call:"
need_out "pid 4194302 (running 12:34): sleep 600"
HCL=$(grep -n 'starter pid .* detached' "$WORK/out" | head -1 | cut -d: -f1)
HCW2=$(grep -n 'still runs 1 background task' "$WORK/out" | head -1 | cut -d: -f1)
[ -n "$HCL" ] && [ -n "$HCW2" ] && [ "$HCW2" -gt "$HCL" ] || why="$why; the warning is not after the starter line ($HCL, $HCW2)"
need_file "$REALSTORE/spawn-records/hcdb2-head-1.out.starter.log"
wait_field "$REC" head-successor session_id sid-by-the-head 40
fixture hcdb2c 200
viewer_use hcdb2c
RUNENV="PATH=$WORK/pstable:$PATH PSTABLE_TASK=0 PSTABLE_LOG=$WORK/pstable-hcdb2c.log STUB_MODE=complete STUB_N=0"
run successor --run hcdb2c --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 5 \
    --max-wait-s 5 --tick-s 1
need_rc 0
need_out "successor: background tasks: none seen beside this call under head pid 4194301 (control: this call's own shell, pid "
need_absent "warn: head pid"
wait_field "$REC" head-successor session_id sid-by-the-head 40
verdict "DB-2 (must warn, end to end): under the process-table stub a session-leading shell child of the head's own process is named, pid, age and command, after the starter line, and the starter still detaches and starts the head; the control on the same stub without the task prints the none line with its control"

fixture hcdb3 200
viewer_use hcdb3
rm -f "$WORK/pstable-hcdb3.log"
RUNENV="PATH=$WORK/pstable:$PATH PSTABLE_TASK=1 PSTABLE_LOG=$WORK/pstable-hcdb3.log STUB_MODE=complete STUB_N=0"
run successor --run hcdb3 --seed-pid --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 5 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "successor: background tasks: not checked — the starter waits on the seed process"
need_eq "$(grep -c -- '^-A' "$WORK/pstable-hcdb3.log")" "0" "table reads with --seed-pid"
[ "$(grep -c -- '^-A' "$WORK/pstable-hcdb2.log")" -ge 1 ] || why="$why; the control: the DB-2 call read no table"
wait_field "$REC" head-successor session_id sid-by-the-head 40
verdict "DB-3 (not checked): with --seed-pid the call prints 'not checked — the starter waits on the seed process' and reads no table (the stub's call log), while the DB-2 call read it once (the control)"

# ---- DB-4 (could not run): the psclaude stub's table has no parseable row ----
fixture hcdb4 200
viewer_use hcdb4
RUNENV="PATH=$WORK/psclaude:$PATH STUB_MODE=complete STUB_N=0"
run successor --run hcdb4 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 \
    --max-wait-s 1 --tick-s 1
need_rc 0
need_out "successor: warn: the background-task check could not run (the process table read gave no parseable row): no task is counted"
need_absent "background tasks: none seen"
need_file "$REALSTORE/spawn-records/hcdb4-head-1.out.starter.log"
wait_field "$REC" successor-aborted reason timeout 40
verdict "DB-4 (could not run): under the psclaude stub the table read gives no row, so the call warns that the check could not run, never none, exits 0 and its starter still detaches"

# ---- DB-5 (live, the one leg on the real process table) is not a leg of this suite ----
# It needs a process the real `ps` reads as the harness, and a lane's fence refuses any command that
# names the harness, so it is its own script, run at install against the installed copy and the
# base copy, never skipped by a switch here (build review RV-CAP finding F2).

# ---- DB-6 (S-7; finding 6): the supervisor's wait once the head's own starter has gone ----
HCG=$("$PY" - "$H" <<HCGONE
$hc_load
def e(kind, **f):
    d = {"event": kind, "run": "r"}
    d.update(f)
    return d
ab = e("successor-aborted", reason="timeout", ts="2026-10-30T03:56:19+0000")
pid = [e("run-open", session="s0"), e("head-successor", session_id="s1", pid=4321),
       e("head-exit", band=60, pack=True), ab]
nopid = [e("run-open", session="s0"), e("head-successor", session_id="s1"),
         e("head-exit", band=60, pack=True), ab]
seed = [e("run-open", session="s0", session_kind="seed"), e("head-exit", band="unmetered", pack=False), ab]
after = pid + [e("head-successor", session_id="s2", pid=4322)]
noab = pid[:3]
b1, line = hs.starter_gone(pid, 1, 60, 600)
b2, _ = hs.starter_gone(nopid, 1, 60, 600)
b3, _ = hs.starter_gone(nopid, 1, 60, 100)
b4, _ = hs.starter_gone(seed, 0, 60, 600)
b5, _ = hs.starter_gone(after, 1, 60, 600)
b6, _ = hs.starter_gone(noab, 1, 60, 600)
print("pid %s silence %s capped %s seed %s after %s noabort %s · %s · %s %s" % (
    b1, b2, b3, b4, b5, b6, hs.SILENCE_PROXY_S + hs.SILENCE_POLL_S + 60,
    "timeout at 03:56:19" in line, "waiting 180 s for a re-called starter, not 600 s" in line))
HCGONE
)
need_eq "$HCG" "pid 180 silence 185 capped 100 seed 180 after None noabort None · 185 · True True" "the bounds"
rs_fixture hcgone
env $RS_ENV STUB_MODES=complete STUB_PROGRESS=abortedstarter STUB_N=1 \
    AIMYTH_VIEWER_ARGV="$WORK/viewer-hcgone.argv" "$PY" -B "$H" _starter --run hcgone \
    --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcgone-head-1.out" --wait-s 6 \
    --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 >"$WORK/hcgone.log" 2>&1
HCRC=$?
need_eq "$HCRC" "0" "the starter's exit"
grep -q "supervisor: the head's own starter already aborted (timeout at " "$WORK/hcgone.log" || why="$why; the shortened wait is not named"
grep -q "waiting 3 s for a re-called starter, not 6 s" "$WORK/hcgone.log" || why="$why; the bound is not 3 ticks"
grep -q "the head-exit has no successor after 3 s" "$WORK/hcgone.log" || why="$why; the start line misstates the wait (finding 9)"
HCGAP=$("$PY" -c 'import json, sys, datetime
ev = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
t = lambda s: datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
xi = min(i for i, e in enumerate(ev) if e.get("event") == "head-exit" and e.get("context") == "stub")
si = [i for i, e in enumerate(ev) if e.get("event") == "head-successor" and i > xi and e.get("session_id") != "sid-by-the-head"]
print(int((t(ev[si[0]]["ts"]) - t(ev[xi]["ts"])).total_seconds()) if si else "none")' "$STORE/spawn-records/hcgone.jsonl")
need_eq "$(under "$HCGAP" 6)" "ok" "seconds from the head's exit to its successor's start (3 ticks plus 3 s of slack)"
rs_fixture hcgonectl
HCT2=$(clock_f)
env $RS_ENV STUB_MODES=handonly STUB_N=1 \
    AIMYTH_VIEWER_ARGV="$WORK/viewer-hcgonectl.argv" "$PY" -B "$H" _starter --run hcgonectl \
    --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcgonectl-head-1.out" --wait-s 6 \
    --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 >"$WORK/hcgonectl.log" 2>&1
HCT3=$(clock_f)
need_eq "$("$PY" -c 'import sys; d = float(sys.argv[2]) - float(sys.argv[1]); print("ok" if d >= 6 else "%.2f s" % d)' "$HCT2" "$HCT3")" "ok" "the control waits at least the full 6 s"
if grep -q "already aborted" "$WORK/hcgonectl.log"; then why="$why; the control shortened its wait"; fi
verdict "DB-6 (S-7; finding 6): starter_gone gives three ticks when a re-called starter would wait on a pid or on a seed, SILENCE_PROXY_S + SILENCE_POLL_S + a tick for silence, capped at --wait-s, and none once a head-successor follows or with no abort; timed, a head whose own starter aborted is succeeded within 3 ticks plus 3 s of slack and the start line names the 3 s waited, while the control with no abort waits the full 6 s"

# ---- DB-7 (S-8; finding 8 b, CR-CAP2 finding 9): the starter's timeout note on the head's own pid ----
sleep 30 &
HCS8=$!
fixture hcs8 200
mk append "$REC" "{\"event\":\"head-successor\",\"session_id\":\"sid-hcs8\",\"pid\":$HCS8,\"budget\":1.0,\"model\":\"fixture-model\"}" >/dev/null
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psclaude:$PATH"
starter --run hcs8 --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcs8-head-1.out" \
        --predecessor-pid "$HCS8" --wait-s 1 --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 1
need_eq "$(mk field "$REC" successor-aborted reason)" "timeout" "the reason stays timeout"
case $(mk field "$REC" successor-aborted note) in
  *"the head's own process, still alive after its hand-over — a print-mode head stays alive while a background task it started runs"*"its shell children could not be read ("*"its supervisor starts the successor once it exits"*) : ;;
  *) why="$why; the note does not name the cause: $(mk field "$REC" successor-aborted note)" ;;
esac
fixture hcs8c 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-hcs8c","pid":4194305,"budget":1.0,"model":"fixture-model"}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":60,"context":"c","spent_usd":1.0,"pack":true}' >/dev/null
RUNENV="PATH=$WORK/psclaude:$PATH"
starter --run hcs8c --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcs8c-head-1.out" \
        --predecessor-pid "$HCS8" --wait-s 1 --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1
need_rc 1
case $(mk field "$REC" successor-aborted note) in
  *"a long-lived process — a launcher's own, or an attended conversation's"*) : ;;
  *) why="$why; the control's note changed: $(mk field "$REC" successor-aborted note)" ;;
esac
kill "$HCS8" 2>/dev/null; wait "$HCS8" 2>/dev/null || :
verdict "DB-7 (S-8): a starter that times out on the record's last head start's own pid names the head's own process kept alive by a background task, says its shell children could not be read when the table gives no row (never none), and that its supervisor starts the successor once it exits, the reason still timeout; the control, an attended pid that is not the last start's, keeps the existing text"

# ---- AM-1 (the owner's amendment of 2026-10-30): the default is 20, and the grants file still wins ----
HCAM=$("$PY" - "$H" <<HCAMEND
$hc_load
print(hs.MAX_SUCCESSORS_DEFAULT)
HCAMEND
)
need_eq "$HCAM" "20" "MAX_SUCCESSORS_DEFAULT"
fixture hcam 200
plant_successors "$REC" 6
run grants --run hcam --max-successors 6
RUNENV="STUB_MODE=complete STUB_N=0"
starter --run hcam --handoff "$HO" --budget 3.50 --out "$WORK/starter/hcam-head-1.out" --wait-s 1 \
        --harness-bin "$WORK/bin/stubhead" --meter-line "$METER" --tick-s 1 --model fixture-model
need_rc 1
case $(mk field "$REC" successor-aborted note) in
  *"at its cap of 6 (the grants file "*) : ;;
  *) why="$why; the grants file's cap did not win: $(mk field "$REC" successor-aborted note)" ;;
esac
verdict "AM-1 (the amendment of 2026-10-30): the default successor cap is 20, and a grants file carrying max_successors 6 still aborts the starter at 6 of 6 naming the grants file, below the default"

# ================== the build review's folds (review RV-CAP, findings F3 to F7) ==================
# The interleaving driver (F3): it runs one handsoff.py command with a planted change landing
# between the command's first read of the record and its locked recheck. The change is made on the
# command's first entry to record_lock, the lock both hand-over commands take for that recheck,
# before the lock is held: the first read saw one successor left, and the locked re-read sees none.
# stderr names what landed and whether the lock was reached at all (each leg's premise).
cat > "$WORK/hc-race.py" <<'HCRACE'
import contextlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
target, what, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
spec = importlib.util.spec_from_file_location("hs_race", target)
hs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hs)
run = rest[rest.index("--run") + 1]
real_lock = hs.record_lock
reached = []


@contextlib.contextmanager
def racing_lock(path):
    if not reached:
        reached.append(what)
        if what == "successor":
            hs.append_record(path, hs.event(run, "head-successor", session_id="sid-raced-head",
                                            budget=1.0, model="fixture-model"))
        elif what.startswith("cap="):
            grants = hs.grants_path(run)
            with open(grants, encoding="utf-8") as handle:
                payload = json.load(handle)
            payload["max_successors"] = int(what[4:])
            with open(grants, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
        if what != "none":
            sys.stderr.write("race: %s landed before the lock\n" % what)
    with real_lock(path):
        yield


hs.record_lock = racing_lock
sys.argv = [target] + rest
code = 0
try:
    hs.main()
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
sys.stderr.write("race: the lock was %s\n" % ("reached" if reached else "never reached"))
sys.exit(code)
HCRACE
race() { # $1 what lands before the lock (successor, cap=N or none), then the handsoff.py arguments:
         # run() with the driver in handsoff.py's place, so RUNENV reaches it the way run() passes it
  hc_what=$1; shift
  hc_h=$H; H="$WORK/hc-race.py"
  run "$hc_h" "$hc_what" "$@"
  H=$hc_h
}
hc_starters() { # $1 run: the starter logs its successor calls left in the store
  "$PY" -c 'import glob, os, sys; print(len(glob.glob(os.path.join(sys.argv[1], sys.argv[2] + "-head-*.out.starter.log"))))' "$REALSTORE/spawn-records" "$1"
}
hc_cap() { # $1 run: the max_successors its grants file carries, or `absent`
  "$PY" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("max_successors", "absent"))' "$REALSTORE/spawn-records/$1-grants.json"
}

# ---- RC-1 (must fire; F3): handoff --final, a head-successor landing before the lock ----
fixture hcrc1 200
hc_plant "$REC" 5
run grants --run hcrc1 --max-successors 6
HCX=$(mk count "$REC" head-exit)
RUNENV="PATH=$WORK/psnone:$PATH"
race successor handoff --run hcrc1 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 10
need_out "race: successor landed before the lock"
need_out "race: the lock was reached"
need_out "handoff: REFUSED (exit 10): a head-successor (session sid-raced-head, at "
need_out "another head has started, the duplicate the starter's own guard refuses, so this head is no longer the run's lead"
need_absent "so this head stays the run's lead"
need_eq "$(mk count "$REC" head-exit)" "$HCX" "head-exits (none appended)"
need_eq "$(hc_obs "$REC" "handoff --final refused: no successor left")" "1" "the refusal's observation"
need_eq "$(hc_obs "$REC" pack-fresh)" "0" "pack-fresh"
grep -q -- "- Next: item3, the fixture item" "$HO" || why="$why; In flight lacks the pack's Next line"
fixture hcrc1c 200
hc_plant "$REC" 5
run grants --run hcrc1c --max-successors 6
HCX=$(mk count "$REC" head-exit)
RUNENV="PATH=$WORK/psnone:$PATH"
race none handoff --run hcrc1c --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 0
need_out "race: the lock was reached"
need_out "head-exit recorded (band 80"
need_eq "$(mk count "$REC" head-exit)" "$((HCX + 1))" "the control's head-exit"
verdict "RC-1 (must fire; build review RV-CAP finding F3): a head-successor landing between handoff --final's first read and its locked recheck leaves none on the cap of 6, so the call exits 10 with no head-exit appended, one refusal observation, the pack written to In flight and no pack-fresh, and says another head has started and this head is no longer the run's lead; the control, the same driver with nothing landing at one left, records its head-exit"

# ---- RC-2 (must fire; F3): handoff --final, the cap lowered before the lock ----
fixture hcrc2 200
hc_plant "$REC" 5
run grants --run hcrc2 --max-successors 6
HCX=$(mk count "$REC" head-exit)
RUNENV="PATH=$WORK/psnone:$PATH"
race cap=5 handoff --run hcrc2 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 10
need_out "race: cap=5 landed before the lock"
need_out "race: the lock was reached"
need_out "handoff: REFUSED (exit 10): no successor left for run hcrc2 — 5 of 5 head starts on its cap (the grants file $REALSTORE/spawn-records/hcrc2-grants.json)"
need_out "and no head-exit was recorded, so this head stays the run's lead"
need_absent "no longer the run's lead"
need_eq "$(hc_cap hcrc2)" "5" "the cap the change wrote"
need_eq "$(mk count "$REC" head-exit)" "$HCX" "head-exits (none appended)"
need_eq "$(hc_obs "$REC" "handoff --final refused: no successor left")" "1" "the refusal's observation"
need_eq "$(hc_obs "$REC" pack-fresh)" "0" "pack-fresh"
grep -q -- "- Next: item3, the fixture item" "$HO" || why="$why; In flight lacks the pack's Next line"
verdict "RC-2 (must fire; F3): the cap lowered from 6 to 5 between handoff --final's first read and its locked recheck leaves none at 5 used, so the call exits 10 with no head-exit appended, one refusal observation, the pack written and no pack-fresh, and keeps this head the run's lead, since no other head started (RC-1's control is this driver's)"

# ---- RC-3 (must fire; F3): successor, a head-successor landing before the lock ----
fixture hcrc3 200
hc_plant "$REC" 5
run grants --run hcrc3 --max-successors 6
viewer_use hcrc3
HCX=$(mk count "$REC" head-exit)
RUNENV="PATH=$WORK/psnone:$PATH"
race successor successor --run hcrc3 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 1 --max-wait-s 1 --tick-s 1 --pack-fresh
need_rc 10
need_out "race: successor landed before the lock"
need_out "race: the lock was reached"
need_out "successor: REFUSED (exit 10): a head-successor (session sid-raced-head, at "
need_out "another head has started, the duplicate the starter's own guard refuses, so this head is no longer the run's lead"
need_absent "so this head stays the run's lead"
need_eq "$(mk count "$REC" head-exit)" "$HCX" "head-exits (none appended)"
need_eq "$(hc_obs "$REC" "successor refused: no successor left")" "1" "the refusal's observation"
need_eq "$(hc_obs "$REC" pack-fresh)" "0" "pack-fresh (--pack-fresh given)"
need_eq "$(hc_starters hcrc3)" "0" "starter logs"
need_no_viewer
# The control on the same driver: nothing landing at one left, the call launches, and each launch
# probe above sees its effect (the starter log, the console stub's call).
fixture hcrc3c 200
hc_plant "$REC" 5
run grants --run hcrc3c --max-successors 6
viewer_use hcrc3c
sh -c 'exit 0' &
HCDEAD=$!
wait "$HCDEAD" || :
RUNENV="PATH=$WORK/psnone:$PATH STUB_MODE=complete STUB_N=0"
race none successor --run hcrc3c --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --predecessor-pid "$HCDEAD" --wait-s 5 --max-wait-s 5 --tick-s 1 --pack-fresh
need_rc 0
need_out "race: the lock was reached"
need_eq "$(hc_obs "$REC" pack-fresh)" "1" "the control's pack-fresh"
need_eq "$(hc_starters hcrc3c)" "1" "the control's starter log"
need_viewer_arg "$(console_cmd hcrc3c)"
wait_field "$REC" head-successor session_id sid-by-the-head 40
verdict "RC-3 (must fire; F3): a head-successor landing between successor's first read and its locked recheck leaves none on the cap of 6, so the call exits 10 with no head-exit appended, one refusal observation, no pack-fresh, no starter and no console, and says another head has started and this head is no longer the run's lead; the control, nothing landing at one left, records pack-fresh, detaches its starter and opens the console"

# ---- RC-4 (must fire; F3): successor, the cap lowered before the lock ----
fixture hcrc4 200
hc_plant "$REC" 5
run grants --run hcrc4 --max-successors 6
viewer_use hcrc4
HCX=$(mk count "$REC" head-exit)
RUNENV="PATH=$WORK/psnone:$PATH"
race cap=5 successor --run hcrc4 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" \
    --wait-s 1 --max-wait-s 1 --tick-s 1 --pack-fresh
need_rc 10
need_out "race: cap=5 landed before the lock"
need_out "race: the lock was reached"
need_out "successor: REFUSED (exit 10): no successor left for run hcrc4 — 5 of 5 head starts on its cap (the grants file $REALSTORE/spawn-records/hcrc4-grants.json)"
need_out "Nothing was written but this refusal's observation, so this head stays the run's lead"
need_absent "no longer the run's lead"
need_eq "$(hc_cap hcrc4)" "5" "the cap the change wrote"
need_eq "$(mk count "$REC" head-exit)" "$HCX" "head-exits (none appended)"
need_eq "$(hc_obs "$REC" "successor refused: no successor left")" "1" "the refusal's observation"
need_eq "$(hc_obs "$REC" pack-fresh)" "0" "pack-fresh (--pack-fresh given)"
need_eq "$(hc_starters hcrc4)" "0" "starter logs"
need_no_viewer
verdict "RC-4 (must fire; F3): the cap lowered from 6 to 5 between successor's first read and its locked recheck leaves none at 5 used, so the call exits 10 with no head-exit appended, one refusal observation, no pack-fresh, no starter and no console, and keeps this head the run's lead (RC-3's control is this driver's)"

# ---- UM-1 (F3): the second consecutive unmetered gate at none left says close the run ----
# The context-unmetered refusal (no transcript for the head, armed): its arrow, its clause and its
# event's count, each changed by this package; the control at one left keeps the hand-over text.
fixture hcum1 200
hc_plant "$REC" 14
run grants --run hcum1 --max-successors 14
run gate --run hcum1 --to "item one" --meter-line "$METER"
need_rc 0
need_out "first miss"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcum1 --to "item two" --meter-line "$METER"
need_rc 7
need_out "second consecutive · armed (env) · REFUSED item item two → no successor is left (successors: 14 of 14 started): watch in-flight lanes to their close while the room lasts, then close the run with its morning report (handoff --set bullets, then close)"
need_out "· successors: 14 of 14 started, none left — this is the run's last lead"
need_absent "then successor"
need_eq "$(mk field "$REC" gate band) $(mk field "$REC" gate decision) $(mk field "$REC" gate successors_used) $(mk field "$REC" gate successors_cap) $(mk field "$REC" gate successors_left)" "unmetered refuse 14 14 0" "the refused gate's event"
need_eq "$(mk field "$REC" stop-condition which)" "unmetered" "the stop-condition"
fixture hcum1c 200
hc_plant "$REC" 13
run grants --run hcum1c --max-successors 14
run gate --run hcum1c --to "item one" --meter-line "$METER"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcum1c --to "item two" --meter-line "$METER"
need_rc 7
need_out "REFUSED item item two → handoff --final --band unmetered, then successor"
need_out "· successors: 13 of 14 started, 1 left"
verdict "UM-1 (F3): the second consecutive unmetered gate, armed, at 14 of 14 exits 7 saying close the run with its morning report and never 'then successor', carries the count, and its event records 14 used of 14 and 0 left; the control at 13 of 14 keeps 'handoff --final --band unmetered, then successor'"

# ---- UM-2 (F3): the unmetered-spend refusal at none left says close the run ----
# A measured context and a failing spend meter (the fixture model matches no price family, no
# billed line in hand): the second consecutive miss, armed, is the spend refusal.
fixture hcum2 200
hc_plant "$REC" 14
run grants --run hcum2 --max-successors 14
mk transcript sid-hcum2-13 100000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcum2 --to "item one"
need_rc 0
need_out "unmetered spend (first miss)"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcum2 --to "item two"
need_rc 7
need_out "unmetered spend (second consecutive) · armed (env) · REFUSED item item two → no successor is left (successors: 14 of 14 started): watch in-flight lanes to their close while the room lasts, then close the run with its morning report (handoff --set bullets, then close)"
need_out "· successors: 14 of 14 started, none left — this is the run's last lead"
need_absent "then successor"
need_eq "$(mk field "$REC" gate metered) $(mk field "$REC" gate decision) $(mk field "$REC" gate successors_left)" "true refuse 0" "the refused gate's event"
fixture hcum2c 200
hc_plant "$REC" 13
run grants --run hcum2c --max-successors 14
mk transcript sid-hcum2c-12 100000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcum2c --to "item one"
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcum2c --to "item two"
need_rc 7
need_out "REFUSED item item two → handoff --final --band unmetered, then successor"
need_out "· successors: 13 of 14 started, 1 left"
verdict "UM-2 (F3): the unmetered-spend refusal (a measured context, a failing spend meter), armed, at 14 of 14 exits 7 saying close the run with its morning report and never 'then successor', with the count on its line and 0 left on its event; the control at 13 of 14 keeps the hand-over text"

# ---- FC-1 (F4): a faulty cap at none left is undecided — how to recover it, never close ----
# A grants file whose cap cannot be read (an unusable value, or bytes that are not JSON) falls back
# to the default of 20, at which 20 used leave none: both hand-over commands and the gate's band
# refusal name the fault, say the last-lead question is undecided and give the recovery, and none
# says close the run. The control, a keyless file (a run that set no cap) at 20, does say close.
fixture hcfc1 200
hc_plant "$REC" 20
printf '{"run": "hcfc1", "grants": [], "writes": [], "max_successors": "six"}\n' > "$REALSTORE/spawn-records/hcfc1-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcfc1 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 \
    --max-wait-s 1 --tick-s 1
need_rc 10
need_out "successor: REFUSED (exit 10): run hcfc1's own successor cap cannot be read — its grants file is readable, unusable max_successors value 'six'"
need_out "so whether this head is the run's last lead is undecided"
need_out "Recover the cap: "
need_out "handsoff.py grants --run hcfc1 --max-successors N"
need_absent "close the run"
need_eq "$(hc_obs "$REC" "successor refused: no successor left")" "1" "the refusal's observation"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcfc1 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 10
need_out "handoff: REFUSED (exit 10): run hcfc1's own successor cap cannot be read"
need_out "so whether this head is the run's last lead is undecided"
need_absent "close the run"
mk transcript sid-hcfc1-19 850000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hcfc1 --to "item two" --meter-line "$METER"
need_rc 4
need_out "→ no successor is left on a fallback cap, and the run's own cap cannot be read (the grants file is readable, unusable max_successors value 'six'), so whether this head is the run's last lead is undecided"
need_absent "close the run"
fixture hcfc2 200
hc_plant "$REC" 20
printf 'not json at all\n' > "$REALSTORE/spawn-records/hcfc2-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hcfc2 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 10
need_out "own successor cap cannot be read — its grants file is unreadable ("
need_out "so whether this head is the run's last lead is undecided"
need_absent "close the run"
fixture hcfc1c 200
hc_plant "$REC" 20
printf '{"run": "hcfc1c", "grants": [], "writes": []}\n' > "$REALSTORE/spawn-records/hcfc1c-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hcfc1c --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 \
    --max-wait-s 1 --tick-s 1
need_rc 10
need_out "close the run with its morning report"
need_absent "undecided"
verdict "FC-1 (must not say close; build review RV-CAP finding F4): at a faulty cap with none left — an unusable max_successors value, or a grants file that is not JSON — successor and handoff --final exit 10 and, with the gate's band refusal, name the fault, say whether this is the run's last lead is undecided, give the recovery (grants --max-successors N) and never say close the run; the control, a keyless grants file at 20 of 20, does say close the run"

# ---- KL-1 (F5): a keyless grants file is a decided cap, the default of 20 applies ----
# grants_payload writes max_successors only when a cap is set, so `grants` with no cap writes a
# file without the key: a run that set no cap, whose fallback is its decided cap. At 20 of 20 both
# hand-over commands refuse as the run's last lead and the gate says close the run; the control,
# an unusable value at 20 of 20, is a fault and undecided.
fixture hckl1 200
hc_plant "$REC" 20
run grants --run hckl1 --viewer none
need_rc 0
need_eq "$(hc_cap hckl1)" "absent" "the grants file's max_successors (grants with no cap writes no key)"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hckl1 --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 \
    --max-wait-s 1 --tick-s 1
need_rc 10
need_out "successor: REFUSED (exit 10): no successor left for run hckl1 — 20 of 20 head starts on its cap (the default (the grants file: readable, no max_successors key; no AIMYTH_MAX_SUCCESSORS))"
need_out "so this head stays the run's lead"
need_out "close the run with its morning report"
need_absent "cannot be read"
need_absent "undecided"
RUNENV="PATH=$WORK/psnone:$PATH"
run handoff --run hckl1 --final --band 80 --inflight-file "$HCPACK" --meter-line "$METER"
need_rc 10
need_out "handoff: REFUSED (exit 10): no successor left for run hckl1 — 20 of 20 head starts on its cap (the default (the grants file: readable, no max_successors key"
need_absent "undecided"
mk transcript sid-hckl1-19 850000 >/dev/null
RUNENV="AIMYTH_HANDSOFF=1"
run gate --run hckl1 --to "item two" --meter-line "$METER"
need_rc 4
need_out "→ no successor is left (successors: 20 of 20 started): watch in-flight lanes to their close while the room lasts, then close the run with its morning report"
need_absent "undecided"
fixture hckl1c 200
hc_plant "$REC" 20
printf '{"run": "hckl1c", "grants": [], "writes": [], "max_successors": 0}\n' > "$REALSTORE/spawn-records/hckl1c-grants.json"
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run hckl1c --meter-line "$METER" --harness-bin "$WORK/bin/stubhead" --wait-s 1 \
    --max-wait-s 1 --tick-s 1
need_rc 10
need_out "its grants file is readable, unusable max_successors value 0"
need_out "undecided"
verdict "KL-1 (build review RV-CAP finding F5): a grants file written with no cap carries no max_successors key, and at 20 of 20 it is a decided cap at the default of 20: successor and handoff --final refuse as the run's last lead (stays the lead, close the run) and the gate's band refusal says close the run, none of them naming a fault or undecided; the control, an unusable value (0) at 20 of 20, is a fault and undecided"

# ---- RR-1 (F6): both run-resume dry runs print the count ----
fixture hcrr1 200
hc_plant "$REC" 3
run grants --run hcrr1 --max-successors 14
HCR=$(sha_file "$REC"); HCG=$(sha_file "$REALSTORE/spawn-records/hcrr1-grants.json")
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run hcrr1 --session sid-hcrr1-2 --head "fixture head" --detail "the count" --dry-run
need_rc 0
need_out "run-resume: dry run · {"
need_out "\"grants\": \"kept\""
need_out "· successors: 3 of 14 started, 11 left"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run hcrr1 --session sid-hcrr1-2 --head "fixture head" --detail "the count" \
    --max-successors 20 --dry-run
need_rc 0
need_out "run-resume: dry run · {"
need_out "· successors: 3 of 20 started, 17 left"
need_eq "$(sha_file "$REC") $(sha_file "$REALSTORE/spawn-records/hcrr1-grants.json")" "$HCR $HCG" "the record and the grants file (sha256): the dry runs wrote nothing"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run hcrr1 --session sid-hcrr1-2 --head "fixture head" --detail "the count"
need_rc 0
need_out "· successors: 3 of 14 started, 11 left"
verdict "RR-1 (build review RV-CAP finding F6): run-resume's dry run with the grants file kept prints 'successors: 3 of 14 started, 11 left', and its dry run planning a cap of 20 prints the count that cap would give, '3 of 20 started, 17 left', neither writing the record or the grants file; the control, the real call, prints the same count as the kept dry run"

# ---- G22f (register 2026-10-13 14:13, the filter third): --leg runs chosen sections alone ----
# A nested run of this suite on a short section. The planted cases are a name no leg carries, which
# must fail its premise rather than read clean, and a stray argument; the control is the name that
# selects, whose section runs while a leg of another section stays out.
LEGENV="HANDSOFF=$H HOOKS_DIR=$HOOKS_DIR LANE_PY=$LANE_PY"
RC=0
RUNENV="$LEGENV"; runenv sh "$SRC" --leg "run-resume: --session auto without a head-successor" >"$WORK/both" 2>&1 || RC=$?
RUNENV=""
need_rc 0
need_out "leg filter: 1 of "
need_out "run-resume: an explicit session and --pid are recorded"
need_out "write proof: the shipped skill and hooks directories are byte-identical"
need_out "^PASS 7/7$"
need_absent "run-open: --dry-run prints the event"
RC=0
RUNENV="$LEGENV"; runenv sh "$SRC" --leg "no leg is named this" >"$WORK/both" 2>&1 || RC=$?
RUNENV=""
need_rc 2
need_out "PROBE FAILED: no leg's name holds"
need_absent "^PASS"
need_absent "^ok "
RC=0
RUNENV="$LEGENV"; runenv sh "$SRC" --unknown >"$WORK/both" 2>&1 || RC=$?
RUNENV=""
need_rc 2
need_out "PROBE FAILED: the only argument is --leg TEXT"
need_absent "^ok "
verdict "G22f (fails on old): --leg TEXT runs the sections naming it and the write proof, a name no leg carries or a stray argument is a premise failure, and no run is mistaken for the whole suite"

# ------------------------------------------------------------------------ write proof ------
# The last legs, so they cover every leg above (moved here 2026-10-10).
MANIFEST_AFTER="$WORK/manifest-after.txt"
mk manifest "$SKILL_DIR" "$HOOKS_DIR" > "$MANIFEST_AFTER"
# A difference here is either a write by the suite (the fault this leg looks for) or a sibling
# process writing to the same directory while the suite ran; the reason line names the paths,
# so the two can be told apart rather than guessed at.
DIFF=$(diff "$MANIFEST_BEFORE" "$MANIFEST_AFTER" | grep '^[<>]' | cut -c1-90)
need_eq "$DIFF" "" "manifest difference"
need_eq "$(grep -c . "$MANIFEST_BEFORE")" "$(grep -c . "$MANIFEST_AFTER")" "manifest length"
NEWCACHE=$(grep '__pycache__' "$MANIFEST_AFTER" | grep -c -v -F -f "$MANIFEST_BEFORE")
need_eq "$NEWCACHE" "0" "byte-code files created under the shipped directories"
verdict "write proof: the shipped skill and hooks directories are byte-identical after the run"

COPY="$WORK/manifest-control"
rm -rf "$COPY"
mkdir -p "$COPY"
cp "$H" "$COPY/handsoff.py"
mk manifest "$COPY" > "$WORK/control-before.txt"
printf '# a planted change\n' >> "$COPY/handsoff.py"
mk manifest "$COPY" > "$WORK/control-after.txt"
if diff "$WORK/control-before.txt" "$WORK/control-after.txt" >/dev/null; then
  why="$why; the manifest did not notice a planted one-line change"
fi
verdict "write proof control: the manifest detects a planted change in a copy"

SCAN=$(mk srcscan "$SRC" | tail -1)
need_eq "$SCAN" "hits 0" "source scan of the suite"
PLANTED=$(mk srcscan "$WORK/planted-writer.sh" | tail -1)
need_eq "$PLANTED" "hits 2" "source scan of the planted control"
verdict "write proof: no write verb in this suite aims outside /tmp (control: 2 planted hits)"

# The read proof (register entry 2026-10-04 10:45, the test_handsoff.sh part): every python
# process of the run loaded the read guard, and no read reached a real home-directory store. The
# control: a planted read of a path under the real Codex home must be blocked and logged — a
# path that does not exist, so a broken guard still reads nothing real.
RG_BEFORE=0; [ -f "$READ_GUARD_LOG" ] && RG_BEFORE=$(grep -c . "$READ_GUARD_LOG")
if [ "$RG_BEFORE" != "0" ]; then
  why="$why; $RG_BEFORE read(s) of a real store were blocked during the run: $(cut -c1-200 "$READ_GUARD_LOG" | head -5 | tr '\n' '|')"
fi
RGCTL=$("$PY" -c 'import os, sys
try:
    open(os.path.join(sys.argv[1], ".codex", "sessions", "suite-read-guard-probe.jsonl"))
    print("read")
except PermissionError:
    print("blocked")
except OSError as exc:
    print("unguarded: %s" % type(exc).__name__)' "$REALHOME")
need_eq "$RGCTL" "blocked" "the planted real-store read (the control)"
RG_AFTER=0; [ -f "$READ_GUARD_LOG" ] && RG_AFTER=$(grep -c . "$READ_GUARD_LOG")
need_eq "$RG_AFTER" "$((RG_BEFORE + 1))" "the guard logged the planted read"
need_eq "$(printf '%s' "$HOME" | grep -c "^$WORK")" "1" "HOME is the fixture's"
verdict "read proof (register 2026-10-04 10:45): no read of a real home-directory store in the whole run (the Codex home, the harness's projects and configuration, the run store and the hand-off directory are fixtures), while a planted read under the real Codex home is blocked and logged (the control)"

# --------------------------------------------- the receipts, fix (c) and the resume shape ------
# A3 receipt interfaces: native helper outcomes, public drain, durable head receipt and acknowledgement.
"$PY" -B "$SKILL_DIR/test_a3.py" --wrappers "$SKILL_DIR" --fixture-root "$WORK" \
  --part handsoff --only A23 --no-mutations > "$WORK/a3-receipts.log" 2>&1
A3_RECEIPT_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) printf '%s\n' "$line" ;;
    'BAD '*) printf '%s\n' "$line" ;;
  esac
done < "$WORK/a3-receipts.log"
if [ "$A3_RECEIPT_RC" != 0 ]; then why="$why receipt matrix failed (exit $A3_RECEIPT_RC)"; fi
verdict "A3 public notice delivery, exact-version receipts and consumer crash matrix"

# The spawn hold's reader, the decisions file's binding, the ack verb and the in-flight ack line. Its
# lane legs run in test_lane.sh and test_codex_lane.sh; this file beside them ships with the launcher.
if [ -f "$SKILL_DIR/test_decisions_spawn.py" ]; then
  "$PY" -B "$SKILL_DIR/test_decisions_spawn.py" --wrappers "$SKILL_DIR" --fixture-root "$WORK" \
    --part handsoff > "$WORK/decisions-spawn.log" 2>&1
  DSPAWN_RC=$?
  while IFS= read -r line; do
    case "$line" in
      'OK '*) why=""; verdict "${line#OK }" ;;
      'BAD '*) why="spawn hold assertion failed"; verdict "${line#BAD }" ;;
      'PROBE FAILED:'*) why="$line"; verdict "spawn hold premise" ;;
    esac
  done < "$WORK/decisions-spawn.log"
  if [ "$DSPAWN_RC" != 0 ] && ! grep -q '^BAD ' "$WORK/decisions-spawn.log"; then
    why="$(tail -3 "$WORK/decisions-spawn.log")"; verdict "spawn hold harness failed"
  fi
else
  printf 'UNRUN the spawn hold: no test_decisions_spawn.py beside this suite\n'
fi

# Fix (c): the real resume constructor with fake process, connectivity and clock boundaries.
"$PY" -B "$SKILL_DIR/test_fix_c.py" --wrappers "$SKILL_DIR" --fixture-root "$WORK" \
  --part handsoff > "$WORK/fix-c.log" 2>&1
FIXC_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) why=""; verdict "${line#OK }" ;;
    'BAD '*) why="fix (c) assertion failed"; verdict "${line#BAD }" ;;
    'PROBE FAILED:'*) why="$line"; verdict "fix (c) premise" ;;
  esac
done < "$WORK/fix-c.log"
if [ "$FIXC_RC" != 0 ] && ! grep -q '^BAD ' "$WORK/fix-c.log"; then
  why="$(tail -3 "$WORK/fix-c.log")"; verdict "fix (c) harness failed"
fi

# The item bars (register 2026-11-05 12:41): item-done and the close's list. Its lane legs run in
# test_lane.sh and test_codex_lane.sh; this file beside them ships with the launcher.
if [ -f "$SKILL_DIR/test_item_bars.py" ]; then
  "$PY" -B "$SKILL_DIR/test_item_bars.py" --wrappers "$SKILL_DIR" --fixture-root "$WORK" \
    --part handsoff > "$WORK/item-bars.log" 2>&1
  IBARS_RC=$?
  while IFS= read -r line; do
    case "$line" in
      'OK '*) why=""; verdict "${line#OK }" ;;
      'BAD '*) why="item bars assertion failed"; verdict "${line#BAD }" ;;
      'PROBE FAILED:'*) why="$line"; verdict "item bars premise" ;;
    esac
  done < "$WORK/item-bars.log"
  if [ "$IBARS_RC" != 0 ] && ! grep -q '^BAD ' "$WORK/item-bars.log"; then
    why="$(tail -3 "$WORK/item-bars.log")"; verdict "item bars harness failed"
  fi
else
  printf 'UNRUN the item bars: no test_item_bars.py beside this suite\n'
fi

# Path A: caps, successor decisions, positive work, D29 and public cold-cache advice.
"$PY" -B "$SKILL_DIR/test_resume_shape.py" --wrappers "$SKILL_DIR" --fixture-root "$WORK" \
  > "$WORK/resume-shape.log" 2>&1
SHAPE_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) why=""; verdict "${line#OK }" ;;
    'BAD '*) why="resume shape assertion failed"; verdict "${line#BAD }" ;;
    'PROBE FAILED:'*) why="$line"; verdict "resume shape premise" ;;
  esac
done < "$WORK/resume-shape.log"
if [ "$SHAPE_RC" != 0 ] && ! grep -q '^BAD ' "$WORK/resume-shape.log"; then
  why="$(tail -3 "$WORK/resume-shape.log")"; verdict "resume shape harness failed"
fi

# ---- INV-2 (register 2026-10-30 21:40 f): a receipt for version n settles the versions below ----
# The planted case is the entry's: v1 and v2 of a notice still printing after v3's receipt. The
# controls are a newer version, which stays owed, and a notice with no receipt at all. A stand-in
# for the journal store keeps the versions exact; A23 above runs the same reading on real journals.
RNOTE=$("$PY" - "$H" <<'NOTICESCRIPT'
import argparse, contextlib, importlib.util, io, json, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("hs", sys.argv[1])
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
def notice(identifier, version):
    return {"notice_id": identifier, "version": version, "payload_sha256": "%s%d" % (identifier, version), "payload": {}}
class Store:
    class A3Premise(Exception):
        pass
    journals = [{"notices": [notice("settled", n) for n in (1, 2, 3)],
                 "acknowledgements": [{"notice_id": "settled", "version": 3, "payload_sha256": "settled3"}]},
                {"notices": [notice("newer", n) for n in (1, 2)],
                 "acknowledgements": [{"notice_id": "newer", "version": 1, "payload_sha256": "newer1"}]},
                {"notices": [notice("bare", 1)], "acknowledgements": []}]
    @staticmethod
    def a3_journals(record, run=None):
        return Store.journals
    @staticmethod
    def a3_pending(record, run=None):
        return [n for j in Store.journals for n in j["notices"]
                if (n["notice_id"], n["version"]) not in {(a["notice_id"], a["version"]) for a in j["acknowledgements"]}]
    @staticmethod
    def a3_json(value):
        return json.dumps(value, sort_keys=True)
    @staticmethod
    def a3_notice_text(item):
        return "printed %s v%d" % (item["notice_id"], item["version"])
hs.a3_shared = lambda: Store
out = io.StringIO()
with contextlib.redirect_stdout(out):
    hs.cmd_notices(argparse.Namespace(run="fixture", record="/no/such/record", ack=False, format="json"))
pending = sorted("%s%d" % (n["notice_id"], n["version"]) for n in json.loads(out.getvalue())["pending"])
out = io.StringIO()
with contextlib.redirect_stdout(out):
    hs.a3_expose_notices(lambda a: 0)(argparse.Namespace(run="fixture", record="/no/such/record"))
print(" ".join(pending), "|", " ".join(sorted(line.split()[1] + line.split()[2] for line in out.getvalue().splitlines() if "printed" in line)))
NOTICESCRIPT
)
need_eq "$RNOTE" "bare1 newer2 | barev1 newerv2" "what stays owed, drained and at a gate"
verdict "INV-2 (fails on old): a receipt for version n settles every lower version of that notice, drained or printed at a gate, while a newer version and a notice with no receipt stay owed"

# ------------------------------------- a3_shared and AIMYTH_LANE_PY (older than the hand-over fix) ---
# The record transaction (a3_shared) loads the lane wrapper AIMYTH_LANE_PY names, as the classifier
# (lane_module) does, so a copy under test with no lane.py beside it uses the one the suite names.
# The wrapper named here is a copy of the suite's lane.py that marks its own import; the control is
# the same copy of handsoff.py with the variable unset, which has no lane.py beside it to load.
A3L="$WORK/a3-lane-py"
rm -rf "$A3L"; mkdir -p "$A3L/code" "$A3L/wrapper"
cp "$H" "$A3L/code/handsoff.py"
{ cat "$LANE_PY"; printf '\nimport os as _a3_mark_os\nwith open(_a3_mark_os.environ["A3_LANE_MARK"], "a", encoding="utf-8") as _a3_mark:\n    _a3_mark.write(__file__ + "\\n")\n'; } > "$A3L/wrapper/lane.py"
plain_fixture a3lanepy
A3N=$(mk lines "$REC")
RC=0
env AIMYTH_LANE_PY="$A3L/wrapper/lane.py" A3_LANE_MARK="$A3L/mark" "$PY" -B "$A3L/code/handsoff.py" \
    ledger --run a3lanepy --observation "through the wrapper AIMYTH_LANE_PY names" >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
need_rc 0
need_out "observation recorded"
need_eq "$(mk lines "$REC")" "$((A3N + 1))" "record lines (the observation appended)"
if [ -f "$A3L/mark" ]; then
  need_eq "$(sort -u "$A3L/mark")" "$(real "$A3L/wrapper/lane.py")" "the wrapper the copy loaded"
else
  why="$why; the wrapper AIMYTH_LANE_PY names was never loaded"
fi
RC=0
env -u AIMYTH_LANE_PY "$PY" -B "$A3L/code/handsoff.py" ledger --run a3lanepy --observation "with no wrapper named" \
    >"$WORK/out" 2>"$WORK/err" || RC=$?
cat "$WORK/out" "$WORK/err" >"$WORK/both"
[ "$RC" != 0 ] || why="$why; the control (AIMYTH_LANE_PY unset, no lane.py beside the copy) exited 0, so the leg would prove nothing"
need_eq "$(mk lines "$REC")" "$((A3N + 1))" "record lines after the control (nothing more appended)"
verdict "a3_shared reads AIMYTH_LANE_PY (older than the hand-over fix): a copy of handsoff.py with no lane.py beside it appends its observation through the wrapper the variable names, which marks its own import; the control, the same copy with the variable unset, fails and appends nothing"

# ----------------------------------------------------------------------------- summary -----
printf '\n'
if [ "$FAILED" -eq 0 ]; then
  printf 'PASS %d/%d\n' "$PASSED" "$N"
  exit 0
fi
printf 'FAIL %d/%d\n' "$FAILED" "$N"
exit 1
