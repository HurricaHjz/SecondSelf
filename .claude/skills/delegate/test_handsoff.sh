#!/bin/sh
# test_handsoff.sh — the suite for handsoff.py (delegate skill, hands-off mode).
#
# Run:  sh test_handsoff.sh                       (from beside handsoff.py)
#       HANDSOFF=<path to handsoff.py> sh test_handsoff.sh
#
# Every fixture lives in a fresh directory under /tmp — never TMPDIR, which on this platform
# points at a per-user root outside the temp directory a lane is granted — and is removed on
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
set -u

PY=${PYTHON:-python3}
SRC=$0
H=${HANDSOFF:-$(dirname "$SRC")/handsoff.py}

die() { printf 'PROBE FAILED: %s\n' "$1" >&2; exit 2; }

command -v "$PY" >/dev/null || die "no python3 on PATH"
command -v git >/dev/null || die "no git on PATH: the checkpoint-commit legs cannot run"
[ -f "$H" ] || die "no handsoff.py at $H (pass HANDSOFF=<path>)"
SKILL_DIR=$(cd "$(dirname "$H")" && pwd) || die "cannot resolve the directory of $H"
# A staged copy names the shipped modules: HOOKS_DIR (context-watermark.py) and LANE_PY (the
# lane wrapper, imported for its classifier); beside the vault's script tree both default.
HOOKS_DIR=${HOOKS_DIR:-$(cd "$SKILL_DIR/../../hooks" 2>&1 && pwd)}
LANE_PY=${LANE_PY:-$SKILL_DIR/lane.py}
[ -f "$HOOKS_DIR/context-watermark.py" ] || die "no context-watermark.py under $HOOKS_DIR (set HOOKS_DIR)"
[ -f "$LANE_PY" ] || die "no lane.py at $LANE_PY (set LANE_PY)"
export AIMYTH_HOOKS_DIR="$HOOKS_DIR"
export AIMYTH_LANE_PY="$LANE_PY"

WORK=$(mktemp -d /tmp/handsoff-suite.XXXXXX) || die "cannot make a temp directory under /tmp"
case $WORK in
  /tmp/*|/private/tmp/*) : ;;
  *) die "the temp directory $WORK is not under /tmp" ;;
esac
cleanup() { [ "${HANDSOFF_KEEP:-0}" = "1" ] || rm -rf "$WORK"; }
trap cleanup EXIT INT TERM

# The target must import before anything else is claimed about it; the byte-code file goes to
# the temp directory, because py_compile ignores -B and the vault takes no __pycache__.
"$PY" -c 'import py_compile, sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)' \
      "$H" "$WORK/handsoff.pyc" || die "handsoff.py does not compile"

STORE="$WORK/store"
PROJECTS="$WORK/projects"
STATE="$WORK/state"
VAULT="$WORK/vault"
REMOTE="$WORK/remote.git"
MK="$WORK/mk.py"
mkdir -p "$STORE/spawn-records" "$PROJECTS" "$STATE" "$VAULT" "$WORK/handoffs" "$WORK/starter" \
         "$WORK/psclaude" "$WORK/psnone" "$WORK/bin" "$WORK/openbin" "$WORK/openfail" \
         "$WORK/pgrepslow" "$WORK/psslow" "$WORK/pssplit"

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


COMMANDS = {"handoff": cmd_handoff, "record": cmd_record, "append": cmd_append,
            "waste": cmd_waste, "transcript": cmd_transcript, "untranscript": cmd_untranscript,
            "pricedscript": cmd_pricedscript,
            "field": cmd_field, "count": cmd_count, "lines": cmd_lines, "rows": cmd_rows,
            "row": cmd_row, "section": cmd_section, "bullet": cmd_bullet,
            "manifest": cmd_manifest, "srcscan": cmd_srcscan, "xscript": cmd_xscript,
            "metascript": cmd_metascript, "replayscript": cmd_replayscript,
            "toolscript": cmd_toolscript, "json": cmd_json}

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
# The harness stub: reads the resume prompt from standard input, as the real starter feeds it.
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
if [ "$n" -le "${STUB_N:-1}" ]; then
  case ${STUB_MODE:-complete} in
    limit) printf '%s\n' "{\"type\":\"result\",\"subtype\":\"error_during_execution\",\"is_error\":true,\"result\":\"You've hit your session limit · resets 8:50am (Europe/London)\"}"; exit 1 ;;
    nolimit) printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"Usage limit reached for this session"}'; exit 1 ;;
    fablelimit) printf '%s\n' "{\"type\":\"result\",\"subtype\":\"error_during_execution\",\"is_error\":true,\"result\":\"You've reached your Fable limit. Switch to another model, or manage usage credits at claude.ai/settings/usage, to continue.\"}"; exit 1 ;;
    budget) printf '%s\n' '{"type":"result","subtype":"error_max_budget_usd","is_error":true,"result":"the budget cap was reached"}'; exit 1 ;;
    error) printf '%s\n' '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"the stub failed"}'; exit 1 ;;
    complete) printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"done without a hand-off"}'; exit 0 ;;
    nojson) printf 'stub: no result line at all\n'; exit 0 ;;
    handonly) "$SUITE_PY" "$SUITE_MK" append "$REC" '{"event":"head-exit","band":60,"context":"stub","spent_usd":1.0,"pack":true}' >/dev/null
      printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"handed off, died before successor"}'; exit 0 ;;
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
  "$SUITE_PY" -c 'import time; time.sleep(60)' watch.py --run "$run" </dev/null >/dev/null 2>&1 &
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
mkdir -p "$WORK/nopath"          # an empty directory: no `open` on PATH, and no file for AIMYTH_OPEN_BIN to name
chmod +x "$WORK/psclaude/ps" "$WORK/psnone/ps" "$WORK/bin/harness" "$WORK/bin/harness2" \
         "$WORK/bin/stubhead" "$WORK/bin/viewer-stub.sh" "$WORK/bin/viewer-fail.sh" \
         "$WORK/openbin/open" "$WORK/openfail/open" "$WORK/bin/sleephead" \
         "$WORK/pgrepslow/pgrep" "$WORK/psslow/ps" "$WORK/pssplit/ps"
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

run() {
  RC=0
  env $RUNENV "$PY" -B "$H" "$@" >"$WORK/out" 2>"$WORK/err" || RC=$?
  cat "$WORK/out" "$WORK/err" >"$WORK/both"
  RUNENV=""
}

mk() { "$PY" "$MK" "$@"; }
real() { "$PY" -c 'import os, sys; sys.stdout.write(os.path.realpath(sys.argv[1]))' "$1"; }
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
  env $RUNENV "$PY" -B "$H" _starter "$@" >"$WORK/out" 2>"$WORK/err" || RC=$?
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
    ts = time.strftime("%Y-%m-%dT%H:%M:%S+0100", time.localtime(time.time() - age))
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
# gate refuses with exit 5, no floor.
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
need_rc 0
need_out "lane L: \$$TWELVE · the larger of the transcript's \$$TWELVE (an open pass after the last close (latest event lane-resumed); sid-rres: \$$TWELVE (metered (transcript)"
need_out "and the recorded \$7.00 (1 close cost(s) as recorded)"
need_out "\$$RESUMED of \$20.00, remainder $RESLEFT"
need_absent "at least"
run gate --run rres --to "item one" --meter-line "$METER10"
need_rc 5
need_out "envelope: \$$RESUMED of \$20.00, remainder $RESLEFT"
need_absent "at least"
need_eq "$(mk field "$REC" stop-condition which)" "envelope" "stop-condition envelope"
verdict "resumed lane (fold, must fire): an active pass after a priced close is metered from the whole transcript — head \$10.00 + max(\$7.00, \$$TWELVE) = \$$RESUMED over \$20.00 — and the gate refuses with exit 5, no floor"

# The control: the lane closed again (its latest event a lane-closed) is read from its recorded
# costs alone — $7 + $5 = $12 — and no transcript is metered; and a transcript shared by several
# passes counts once: closes $3 + $4 = $7 with the lane resumed again take max($7, $12) = $12,
# never $19.
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rres-l","exit_class":"completed","total_cost_usd":5.0}' >/dev/null
run run-spend --run rres --meter-line "$METER10"
need_rc 0
need_out "lane L: \$12.00 · 2 close cost(s) as recorded"
need_out "0 meter call(s)"
fixture rres2 100
mk pricedscript sid-rres2-l 2 lane-home-dir 1500000 >/dev/null
mk append "$REC" '{"event":"lane-open","lane":"L","session_id":"sid-rres2-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rres2-l","exit_class":"limit","total_cost_usd":3.0}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L","session_id":"sid-rres2-l"}' >/dev/null
mk append "$REC" '{"event":"lane-closed","lane":"L","session_id":"sid-rres2-l","exit_class":"limit","total_cost_usd":4.0}' >/dev/null
mk append "$REC" '{"event":"lane-resumed","lane":"L","session_id":"sid-rres2-l"}' >/dev/null
run run-spend --run rres2 --meter-line "$METER10"
need_rc 0
need_out "lane L: \$$TWELVE · the larger of the transcript's \$$TWELVE (an open pass after the last close (latest event lane-resumed)"
need_out "and the recorded \$7.00 (2 close cost(s) as recorded)"
need_absent "\$19.00"
verdict "resumed lane (fold, must not fire): a lane whose latest event is a close reads its recorded costs alone (no meter call), and a transcript shared by several passes counts once — max(\$7.00, \$$TWELVE), never \$19.00"

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

# ------------------------------------------------------------------------- successor -------
fixture rsuc 200
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rsuc --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$183.44"
need_out "minus session \$16.56"
need_eq "$(mk count "$REC" head-exit)" "0" "head-exit events"
need_eq "$(mk lines "$REC")" "1" "record lines"
verdict "successor --dry-run: the budget is the envelope minus the session total, nothing written"

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
if ! grep -q "Resume the fixture run" "$WORK/stub-rst.stdin.1"; then
  why="$why; the resume prompt did not reach the head on standard input"
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
run close --run pclose2 --commit "fixture: a commit a plain run may not make"
need_rc 2
need_out "never commits and never pushes"
need_lines
need_eq "$(mk lines "$REC")" "$LINES_BEFORE" "record lines (nothing written)"
need_eq "$(mk count "$REC" run-close)" "0" "run-close events"
need_eq "$(git -C "$VAULT" rev-list --count HEAD)" "$COMMITS_BEFORE" "commit count"
run close --run pclose2 --push
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
run grants --run rgrant --write "$WORK/real-grant/more"
need_rc 0
need_file "$GF"
need_out "grants: $GF"
need_eq "$(mk field "$REC" grants grants_file)" "$GF" "grants event"
need_eq "$(cat "$STATE/run-sid-rgrant")" "rgrant" "the pointer after grants"
if ! grep -q "real-grant/more" "$GF"; then why="$why; the new write is not in the rewritten file"; fi
verdict "grants: a missing grants file is rewritten with the pointer (N7)"

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
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rkeep --session sid-keep2 --head "h" --detail "explicit write" --write "$WORK/real-grant/other"
need_rc 0
need_absent "(kept)"
if grep -q "real-grant/keepme" "$GFK"; then why="$why; an explicit --write did not replace the file"; fi
if ! grep -q "real-grant/other" "$GFK"; then why="$why; the explicit write is absent"; fi
verdict "run-resume: with no --grant or --write an existing grants file is kept (register 2026-09-06); an explicit --write rewrites it (control)"

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
case $SEC in *"lane B7"*) why="$why; a lane opened before the boundary is in the re-derived pack" ;; *) : ;; esac
verdict "the pack-age guard: a pack older than the last phase-boundary is STALE, and the starter re-derives the in-flight section from the record before the successor starts (observation stale-pack)"

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
case $SEC in *"fresh when the first head started"*) why="$why; the stale pack survived into the successor's brief" ;; *) : ;; esac
case $SEC in *"the record carries no phase-boundary event"*) : ;; *) why="$why; the derivation does not say the record holds no boundary: $SEC" ;; esac
verdict "the pack-age guard on the supervisor's own successor path: the first start reports the pack fresh, the head-exit the supervisor writes for a limit stop makes it stale, and the second start re-derives the section before briefing the successor"

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

# ----------------------------------------------------------- N5: the envelope remainder ----
fixture rspent 100
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":50}' >/dev/null
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":40}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rspent --dry-run --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 0
need_out "budget \$10.00"
mk append "$REC" '{"event":"head-exit","band":80,"context":"c","spent_usd":10}' >/dev/null
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rspent --meter-line "$METER" --harness-bin "$WORK/bin/harness"
need_rc 2
need_out "the envelope is spent"
need_lines
need_eq "$(mk field "$REC" successor-aborted reason)" "budget" "successor-aborted budget"
verdict "successor: the remainder is the envelope minus every head-exit's spent_usd (10 of 100); spent → successor-aborted budget"

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
need_eq "$(mk field "$REC" head-resumed budget)" "178.44" "the resume's cap is the remainder (200 - 5 - 16.56)"
case $(sed -n 2p "$WORK/stub-rbud.args") in *"--resume "*"--max-budget-usd 178.44"*) : ;; *) why="$why; the resume's argv lacks the remainder cap" ;; esac
grep -q "RESUMED after a budget stop" "$WORK/stub-rbud.stdin.2" || why="$why; the budget note is missing"
fixture rbud2 20
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
verdict "supervisor (N6): an error exit writes band error; two consecutive error stops abort (repeat-stop)"

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
verdict "supervisor: two consecutive completed-without-close exits abort (repeat-stop) after the first has had its successor"

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
need_out "budget \$178.44"
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
need_out "budget \$178.44"
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
# count is arithmetic, not a memory: 5 waste fields × 2 boundaries + 2 billed lines + 1 run
# total + 3 context rows + 1 orientation row + 1 lost-lane row = 18.
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
need_out "waste-table: 18 rows from 2 boundaries, 3 gates, 2 lanes"
need_eq "$(grep -c . "$WORK/out")" "1" "stdout lines"
need_file "$WT"
need_eq "$(mk rows "$WT" "Waste table")" "18" "rendered rows"
need_eq "$(grep -c 'rewrites after a lapsed cache · 2 → 3.*| field absent |' "$WT")" "1" "the absent rewrites field"
need_eq "$(grep -c 'orientation cost · head sid-rwaste | 40,000 tokens · gate.orientation_tokens' "$WT")" "1" "the orientation row"
need_eq "$(grep -c 'Kinds are mechanical' "$WT")" "1" "the legend"
need_eq "$(grep -c 'lost lane · L1 · exit class limit | \$2.50 · lane-closed.total_cost_usd' "$WT")" "1" "the lost lane"
need_eq "$(grep -c 'lost lane · L2' "$WT")" "0" "a completed lane is not a lost lane"
need_eq "$(grep -c 'no waste found' "$WT")" "0" "no zero-findings row when a figure is positive"
need_eq "$(grep -c 'run total (shown sum) | \$16.56 = \$16.56' "$WT")" "1" "the run total as a shown sum"
need_eq "$(grep -c 'context · item two at .* | +40,000 tokens · gate context 100,000 → 140,000' "$WT")" "1" "context per item as a gate delta"
verdict "waste-table: 18 rows from the record alone — a row per waste field per boundary, the billed lines with the run total, the gate deltas, the orientation figure and the lost lane"

run waste-table --run rwaste
need_rc 0
need_file "$REALSTORE/spawn-records/rwaste-waste-table.md"
WTD="$WORK/rwaste-dry.md"
run waste-table --run rwaste --out "$WTD" --dry-run
need_rc 0
need_out "dry run"
need_out "18 rows from 2 boundaries"
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

fixture rvwsuc2 200
plant_console rvwsuc2 watch.py
viewer_use vsuc2
RUNENV="PATH=$WORK/psnone:$PATH"
run successor --run rvwsuc2 --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "a console is already alive (pid $PLANTED)"
need_no_viewer
need_nofile "$(console_cmd rvwsuc2)"
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

fixture rvwrh2 200
mk append "$REC" '{"event":"head-successor","session_id":"sid-rvwrh2","pid":1,"budget":5.0}' >/dev/null
plant_console rvwrh2 handsoff.py
viewer_use vrh2
run resume-head --run rvwrh2 --harness-bin "$WORK/bin/no-such-harness" --budget-usd 5 --tick-s 1
need_rc 0
need_out "a console is already alive (pid $PLANTED)"
need_no_viewer
sleep 2
kill_console
verdict "resume-head: a console already alive for the run is never doubled (the handsoff.py spelling of the marker)"

viewer_use vspell
plant_console rvwsp watch.py
"$PY" - "$H" rvwsp <<'CALIVE' > "$WORK/ca-watch.txt"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
print(len(mod.console_alive(sys.argv[2])), len(mod.console_alive("rvwsp-nobody")))
CALIVE
need_eq "$(cat "$WORK/ca-watch.txt")" "1 0" "the watch.py spelling, with the negative control"
kill_console
plant_console rvwsp handsoff.py
"$PY" - "$H" rvwsp <<'CALIVE2' > "$WORK/ca-handsoff.txt"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("target", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
print(len(mod.console_alive(sys.argv[2])), len(mod.console_alive("rvwsp-nobody")))
CALIVE2
need_eq "$(cat "$WORK/ca-handsoff.txt")" "1 0" "the handsoff.py spelling, with the negative control"
kill_console
sleep 1
"$PY" - "$H" rvwsp <<'CALIVE3' > "$WORK/ca-none.txt"
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
need_out "run by hand: python3 -B"
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
fixture rvwopen 200
viewer_use vopen2
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run successor --run rvwopen --meter-line "$METER" --harness-bin "$WORK/bin/no-such-harness" \
    --wait-s 1 --max-wait-s 5 --tick-s 1
need_rc 0
need_out "viewer: Terminal window opened on $(console_cmd rvwopen) via $WORK/openbin/open (first attempt) · console pid "
need_eq "$(viewer_calls)" "2" "open was called once, with two arguments: -g and the command file"
need_eq "$(head -1 "$VIEWER_ARGV")" "-g" "the first argument is -g, open's flag for leaving the application in the background (register 2026-09-22)"
need_eq "$(wc -l < "$VIEWER_ARGV.calls" | tr -d ' ')" "1" "one call, counted by the stub's own per-call line"
need_eq "$(cat "$VIEWER_ARGV.calls")" "-g $(console_cmd rvwopen)" "that one call's arguments are exactly -g and the command file"
need_eq "$(viewer_last)" "$(console_cmd rvwopen)" "the command file is open's last argument"
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
need_out "viewer: no Terminal window (command file $CF; $WORK/openbin/open exited 0 but no console process for the run appeared within 15 s); run by hand: python3 -B"
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
need_out "run by hand: python3 -B"
need_eq "$(viewer_calls)" "4" "open was tried twice (first attempt and retry), -g and the command file each time"
need_eq "$(wc -l < "$VIEWER_ARGV.calls" | tr -d ' ')" "2" "two calls, counted by the stub's own per-call line"
need_eq "$(sort -u "$VIEWER_ARGV.calls")" "-g $(console_cmd rvwopenfail)" "both calls carry exactly -g and the command file"
sleep 2
verdict "the opener's open route (a failing open): a non-zero exit is retried once with the same command, both attempts named with open's stderr, and the primitive still exits 0"

# open-console: the opener on demand, and --check as the live check.
fixture rvwoc 200
viewer_use voc
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run rvwoc
need_rc 0
need_out "viewer: Terminal window opened on $(console_cmd rvwoc) via $WORK/openbin/open (first attempt) · console pid "
OCPID=$(cat "$VIEWER_ARGV.pid")
run open-console --run rvwoc --check
need_rc 0
need_out "console: pid $OCPID alive on watch --run rvwoc"
run open-console --run rvwoc
need_rc 0
need_out "a console is already alive (pid $OCPID) · no second window"
need_eq "$(viewer_calls)" "2" "no second open while the console lives (the one call's two arguments)"
kill "$OCPID"; sleep 1
run open-console --run rvwoc --check
need_rc 1
need_out "NO CONSOLE for rvwoc"
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD="
run open-console --run rvwoc --dry-run
need_rc 0
need_out "would run: $WORK/openbin/open -g $(console_cmd rvwoc)"
need_eq "$(viewer_calls)" "2" "a dry run opens nothing (still the one earlier call)"
verdict "open-console: opens the window on demand through open, --check prints the confirmed pid with exit 0, a second call while it lives opens nothing, --check after the console ends prints NO CONSOLE with exit 1, and --dry-run prints the open line and calls nothing"

# The one-window claim is the advisory lock on <run>-console.lock beside the record (the ruling
# on the №163 fold, 2026-09-18): the claim file of №162 is retired, and the single line here that
# spells it plants a leftover of that retired name to prove nothing reads it. Legs: a leftover
# claim file blocks no window and is not touched; the lock file is where the claim now lives; and
# neither opt-out — --viewer none, --check — takes a claim at all.
fixture rvwclaim 200
CF=$(console_cmd rvwclaim); rm -f "$CF"
LOCKF="$REALSTORE/spawn-records/rvwclaim-console.lock"; rm -f "$LOCKF"
: > "$CF.opening"
viewer_use vclaim
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run rvwclaim
need_rc 0
need_out "viewer: Terminal window opened on $CF via $WORK/openbin/open (first attempt) · console pid "
need_eq "$(viewer_calls)" "2" "the retired claim file blocked nothing and open ran once (-g and the command file)"
need_file "$CF.opening"
need_file "$LOCKF"
need_absent "took over"
kill "$(cat "$VIEWER_ARGV.pid")"; sleep 1
rm -f "$CF.opening"
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1"
run open-console --run rvwclaim --viewer none
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
fixture rvwkill 200
KCF=$(console_cmd rvwkill); rm -f "$KCF"
KLOCK="$REALSTORE/spawn-records/rvwkill-console.lock"; rm -f "$KLOCK"
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
"$PY" -B "$WORK/holder.py" "$H" rvwkill "$WORK/holder.flag" &
HOLDPID=$!
i=0
while [ ! -s "$WORK/holder.flag" ] && [ "$i" -lt 60 ]; do sleep 0.25; i=$((i + 1)); done
case $(cat "$WORK/holder.flag" 2>/dev/null) in
  True*) : ;;
  *) why="$why; the holder process never took the claim: '$(cat "$WORK/holder.flag" 2>/dev/null)'" ;;
esac
viewer_use vkill
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD="
run open-console --run rvwkill
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
run open-console --run rvwkill
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
fixture rvwenv 200
viewer_use venv
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1 AIMYTH_VIEWER=none"
run open-console --run rvwenv
need_rc 0
need_out "viewer: none"
need_out "no window"
need_no_viewer
RUNENV="PATH=$WORK/psnone:$PATH AIMYTH_OPEN_BIN=$WORK/openbin/open AIMYTH_VIEWER_CMD= STUB_OPEN_CONSOLE=1 AIMYTH_VIEWER=window"
run open-console --run rvwenv
need_rc 0
need_out "open-console: AIMYTH_VIEWER='window' is neither terminal nor none · the grants file decides"
need_out "viewer: Terminal window opened on $(console_cmd rvwenv) via $WORK/openbin/open (first attempt) · console pid "
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
need_out "run by hand: python3 -B"
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
need_out "model none effort max"
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
    --session-kind seed --envelope-usd 200
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
    --regime-src head --handoff "$SHO" --detail "a head record" --pid 55556 --envelope-usd 200
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
    --session-kind seed --envelope-usd 200
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
    --envelope-usd 200
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
run close --run rclose2 --meter-line "$METER" --commit "fixture: the closing commit" --push
need_rc 0
need_out "push ok"
need_eq "$(mk field "$REC" run-close push)" "ok" "push"
need_eq "$(git -C "$VAULT" rev-parse HEAD)" "$(git -C "$REMOTE" rev-parse HEAD)" "remote head"
verdict "close --commit --push: the commit is made and pushed to the fixture remote"

# ------------------------------------------------------------------------ write proof ------
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
need_eq "$(grep -c '| 11.7 min · phase-boundary.idle_min · head idle: no lane running and no head call, gaps above 60 s, the head.s calls from its transcript (idle_src transcript)' "$WTI")" "1" "the transcript-sourced idle row"
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
need_eq "$(grep -c 'run total (shown sum) | \$7.00 = \$7.00' "$WWR")" "1" "the window figure wins over the session-wide billed line"
need_eq "$(grep -c "metered over the run's window: \$7.00 (the record gives the last boundary billed line" "$WWR")" "1" "the row says which figure it took and what the record gave"
need_eq "$(grep -c 'envelope base \$200.00 (run-open.envelope_usd)' "$WWR")" "1" "the envelope base beside the total"
WWR2="$WORK/rwinrow-norow.md"
run waste-table --run rwinrow --out "$WWR2" --no-meter
need_eq "$(grep -c 'run total (shown sum) | \$16.56 = \$16.56' "$WWR2")" "1" "control: without a window figure the row falls back to the record's own"
verdict "waste-table (T6): the whole-run row takes the head's window meter figure over the session-wide billed line, names both and prints the envelope base"

# (b) the register entry of 2026-09-06: the under-read, the head count and the limit wait.
fixture rlater 100
BL=$(printf '{"event":"phase-boundary","from":"1","to":"2","meter":"%s","idle_min":0.0,"denials":0,"over_cap_reports":0,"respawn_cost_usd":0.0}' "$METER")
mk append "$REC" "$BL" >/dev/null
mk append "$REC" '{"event":"head-exit","band":0,"context":"362,843 tokens (36 %)","spent_usd":56.26,"pack":true}' >/dev/null
WLA="$WORK/rlater-table.md"
run waste-table --run rlater --out "$WLA" --no-meter
need_rc 0
need_eq "$(grep -c 'run total (shown sum) | \$56.26 = \$56.26' "$WLA")" "1" "the later head-exit spend, not the earlier billed line"
need_eq "$(grep -c 'head-exit.spent_usd \$56.26, later in the record than the last boundary billed line \$16.56' "$WLA")" "1" "the row names both figures and which is later"
fixture rearlier 100
mk append "$REC" '{"event":"head-exit","band":0,"context":"c","spent_usd":5.0,"pack":true}' >/dev/null
mk append "$REC" "$BL" >/dev/null
WEA="$WORK/rearlier-table.md"
run waste-table --run rearlier --out "$WEA" --no-meter
need_eq "$(grep -c 'run total (shown sum) | \$16.56 = \$16.56' "$WEA")" "1" "control: a boundary later than the head-exit keeps the billed line"
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
# span (a stop 60 minutes back, its resume 30 minutes back) rather than on a fixed date.
fixture rlimit 100
STOP_TS=$("$PY" -c 'import time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 3600)))')
RES_TS=$("$PY" -c 'import time; print(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 1800)))')
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
need_out "budget \$360.00"
need_absent "envelope (seed)"
verdict "successor: a seed head-exit sizes the cap at the envelope minus recorded spend (budget_src: envelope (seed)), while a metered head-exit takes the ordinary remainder (register 2026-09-07)"

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

run grants --run rcarry --write "$WORK/carry/worktree"
need_rc 0
need_out "loses"
need_eq "$(glist "$GFC" writes "$WORK/carry/review")" "0" "an explicit --write replaces the write list"
need_eq "$(glist "$GFC" writes "$WORK/carry/worktree")" "1" "the named write is written"
need_eq "$(glist "$GFC" grants "$WORK/carry/experiments")" "1" "the read list the call does not name is still carried"
verdict "grants --write (control): a named list replaces the file's, its lost paths printed on stderr, while the unnamed read list is carried"

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
need_out "would shrink the run's write list"
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
    --session-kind seed --envelope-usd 200
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
run close --run rdec --meter-line "$METER"
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
run gate --run rhold --to item4 --meter-line "$METER" --decisions-file "$DFILE" --ack "read the decisions file: the checklist stays"
need_rc 0
setmtime "$DFILE" 3600
run gate --run rhold --to item5 --meter-line "$METER" --decisions-file "$DFILE"
need_rc 0
need_absent "HOLD"
run gate --run rhold --to item5 --meter-line "$METER" --decisions-file "$WORK/no-such-decisions.md"
need_rc 2
need_out "is not a file"
verdict "the decisions channel: a decisions file changed after the last gate holds (exit 6) until acked; one older than the last gate clears; a named file that does not exist is refused (exit 2)"

mk append "$REC" '{"event":"observation","phase":"","what":"AUTHOR DECISION NOT YET APPLIED: the checklist justification","note":"relayed before the close"}' >/dev/null
run run-is-closed --run rhold
need_rc 1
need_out "open"
run close --run rhold --meter-line "$METER"
need_rc 6
need_out "AUTHOR DECISION NOT YET APPLIED"
need_eq "$(mk count "$REC" run-close)" "0" "the held close writes no run-close"
run close --run rhold --meter-line "$METER" --ack "read the AUTHOR decision: the justification is applied"
need_rc 0
need_eq "$(mk count "$REC" run-close)" "1" "the acked close"
run run-is-closed --run rhold
need_rc 0
need_out "closed"
run run-is-closed --run no-such-run-record
need_rc 2
verdict "close and run-is-closed: an AUTHOR observation after the last gate holds the close (exit 6, no run-close) until acked; run-is-closed exits 1 before the close, 0 after it and 2 with no record"

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
need_out "would shrink the run's write list"
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

run grants --run rnarrow --on-limit resume --write "$WORK/carry/nar-w1"
need_rc 0
need_out "loses"
need_eq "$(glist "$GFN" writes "$WORK/carry/nar-w1")" "1" "the explicit re-issue is written"
run grants --run rnarrow --on-limit stop
need_rc 0
need_absent "would shrink"
need_eq "$(glist "$GFN" writes "$WORK/carry/nar-w1")" "1" "the carried write after the explicit call"
RUNENV="PATH=$WORK/psnone:$PATH"
run run-resume --run rnarrow --session sid-narrow2 --head "fixture head" --detail "narrowed on purpose" --write "$WORK/carry/nar-w3"
need_rc 0
need_eq "$(mk field "$REC" run-resume writes_src)" "--write" "the run-resume event names its list source"
need_eq "$("$PY" -c 'import json, sys; e = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]; r = [x for x in e if x.get("event") == "run-resume"][-1]; print(1 if isinstance(r.get("writes"), list) and sys.argv[2] in r["writes"] else 0)' "$REC" "$WORK/carry/nar-w3")" "1" "the rewriting run-resume records its write list"
run grants --run rnarrow --viewer none
need_rc 0
need_absent "would shrink"
need_eq "$(glist "$GFN" writes "$WORK/carry/nar-w3")" "1" "the run-resume's list is carried"
verdict "the shrink guard (recorded baseline, must not fire): an explicit --write re-issue is written with its delta noted and becomes the recorded baseline, so the next flag-less call proceeds; a rewriting run-resume records its lists, so its explicit narrowing is not later read as a shrink"

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
need_eq "$(grep -c 'run total (shown sum) | \$45.72 = \$45.72 · per head: sid-rtot the last boundary billed line.s .session ≈. \$45.72 (a figure carried by hand)' "$WTO")" "1" "the hand-carried approximate form is read"
need_eq "$(grep -c '1 boundary line(s) carried no session figure' "$WTO")" "1" "only the failed line carries no figure"
fixture rtot2 200
mk append "$REC" '{"event":"phase-boundary","from":"4","to":"5","meter":"head USD 52.34 · lanes USD 20.22 · session USD 72.56"}' >/dev/null
WTO2="$WORK/rtot2-table.md"
run waste-table --run rtot2 --out "$WTO2" --no-meter
need_rc 0
need_eq "$(grep -c 'run total (shown sum) | \$72.56 = \$72.56 · per head: sid-rtot2 the last boundary billed line.s .session USD. \$72.56 (a figure carried by hand)' "$WTO2")" "1" "the USD form is read"
verdict "run total (register 2026-09-09 15:43, must fire): a billed line carried by hand as 'session ≈ <n>' or 'session USD <n>' is read into the run total and the row names the form, while a failed line still carries no figure"

fixture rtot3 200
mk append "$REC" '{"event":"phase-boundary","from":"1","to":"2","meter":"billed (list, prices 2026-09-03): head $5.00 · lanes $0.00 · session $5.00"}' >/dev/null
mk append "$REC" '{"event":"phase-boundary","from":"2","to":"3","meter":"head USD 6.10 (the harness line) · session ≈ n/a (the meter failed) · sessions $9.99 · session 0a1b2c3d"}' >/dev/null
WTO3="$WORK/rtot3-table.md"
run waste-table --run rtot3 --out "$WTO3" --no-meter
need_rc 0
need_eq "$(grep -c 'run total (shown sum) | \$5.00 = \$5.00 · per head: sid-rtot3 the last boundary billed line.s .session \$. \$5.00' "$WTO3")" "1" "the earlier literal figure stands"
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
need_out "interrupt 2, replay 1, synthetic 1, unparseable 2, other 8 · reconciles"
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
run close --run rrep --report "$RPT" --meter-line "$CLOSE_METER"
need_rc 0
need_out "patched Closing meter (handsoff.py close), Limit stops on the record (handsoff.py close)"
need_eq "$(grep -c '^- \*\*Closing meter (handsoff.py close):\*\* billed (list, prices 2026-09-03): head \$74.51 · lanes \$23.20 · session \$97.71$' "$RPT")" "1" "the spend section carries the closing meter"
need_eq "$(grep -c '^- \*\*Limit stops on the record (handsoff.py close):\*\* 2 limit stop(s): head at .* → head-resumed .*, 5.0 min; head at .* → head-resumed .*, 10.0 min · 1 lane(s) closed limit: B-registry' "$RPT")" "1" "the warnings section names both stops and the lane"
need_eq "$(grep -c 'The head wrote this at item 5: session \$72.56, resumed once.' "$RPT")" "1" "the head's own prose is untouched"
need_eq "$(mk field "$REC" run-close report_patched)" '["Closing meter (handsoff.py close)", "Limit stops on the record (handsoff.py close)", "Hard stops on the record (handsoff.py close)"]' "the run-close records what was patched"
need_eq "$(grep -c '^- \*\*Hard stops on the record (handsoff.py close):\*\* 0 hard stop(s) on the head other than a limit · 0 lane(s) closed other than completed or limit · read from the record at the close' "$RPT")" "1" "the hard-stops bullet states its counts (this fixture has limit stops only)"
"$PY" - "$RPT" <<'B2ORDER_END' > "$WORK/order.txt"
import sys
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
at = lambda p: next(i for i, l in enumerate(lines) if l.startswith(p))
print(at("## Spend") < at("- **Closing meter") < at("## Warnings") < at("- **Limit stops") < at("## Related"))
B2ORDER_END
need_eq "$(cat "$WORK/order.txt")" "True" "each bullet sits inside its own section"
verdict "close re-read (register 2026-09-10 17:43, must fire): a report written before the run's second limit stop and its closing meter gets one bullet under Spend (the close's billed line) and one under Warnings (both stops with their minutes, and the lane closed limit), the head's prose untouched"

H1=$(sha_of "$RPT")
run close --run rrep --report "$RPT" --meter-line "$CLOSE_METER"
need_rc 0
need_out "already current, not rewritten"
need_eq "$(sha_of "$RPT")" "$H1" "an already-current report is left byte for byte"
fixture rrep2 200
RPT2="$WORK/rrep2-report.md"
report_fixture "$RPT2" '## Warnings and handling'
H2=$(sha_of "$RPT2")
run close --run rrep2 --meter-line "$CLOSE_METER"
need_rc 0
need_absent "report:"
need_eq "$(sha_of "$RPT2")" "$H2" "a close without --report leaves the page alone"
need_eq "$(mk field "$STORE/spawn-records/rrep2.jsonl" run-close report)" "<no key report>" "no report key on its run-close"
verdict "close re-read (must not fire): an already-current report is not rewritten, and a close without --report neither reads nor writes one"

fixture rrep3 200
run close --run rrep3 --report "$WORK/no-such-report.md" --meter-line "$CLOSE_METER"
need_rc 2
need_out "PROBE FAILED: --report"
need_lines
need_eq "$(mk count "$REC" run-close)" "0" "a refused close writes nothing"
fixture rrep4 200
RPT4="$WORK/rrep4-report.md"
report_fixture "$RPT4" '## Notes'
run close --run rrep4 --report "$RPT4" --meter-line "$CLOSE_METER"
need_rc 3
need_out "NOT patched: no '## Warnings…' section"
need_eq "$(mk count "$REC" run-close)" "1" "the close itself is written"
need_eq "$(grep -c 'Closing meter (handsoff.py close)' "$RPT4")" "1" "the section that exists is still patched"
plain_fixture rrep5
run close --run rrep5 --report "$RPT"
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
need_eq "$(own_start "$REC" head-successor)" 'null "max" "harness default (no --model)"' "no --model: the field is null and model_src says why"
need_absent "the caller ran the opener"
need_eq "$(viewer_calls)" "1" "without --viewer-opened the start opens its window (the control)"
verdict "head-start events (must not fire): a start with no --model records model null with model_src naming the harness default beside effort max, and without --viewer-opened the starter opens its own window"

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
verdict "the re-base (both behaviours in one function): one `close` writes the afternoon's run-spend fields and line AND ends every open hold, counting them on the run-close"

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

# ----------------------------------------------------------------------------- summary -----
printf '\n'
if [ "$FAILED" -eq 0 ]; then
  printf 'PASS %d/%d\n' "$PASSED" "$N"
  exit 0
fi
printf 'FAIL %d/%d\n' "$FAILED" "$N"
exit 1
