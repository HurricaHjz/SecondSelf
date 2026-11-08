#!/bin/sh
# test_watch.sh — the suite for watch.py.   Run:  sh <this skill directory>/test_watch.sh
#
# Every leg runs the real console against fixtures under one mktemp root: a synthetic run record
# carrying every event kind the record can hold, a synthetic hand-off pack naming its items in both
# accepted shapes, a synthetic head transcript and a synthetic lane transcript. Each guard is
# attacked as well as exercised — a planted case that must be caught beside a clean case that must
# not be — and the closing legs prove the console wrote nothing: a checksum manifest of the fixture
# record, pack and transcripts before and after every run (including one run against a read-only
# copy), plus a source sweep for write patterns and for owner paths whose own positive controls hit
# a planted fixture file. No notification is ever raised: AIMYTH_WATCH_NOTIFY=0 is exported below.
# The fixture root is removed at the end. Last line: PASS n/n, or FAIL k/n.
set -u

HERE=$(cd -- "$(dirname -- "$0")" && pwd)
WATCH="$HERE/watch.py"
if [ ! -f "$WATCH" ]; then
  printf 'PROBE FAILED: no watch.py beside this suite at %s\n' "$WATCH"
  exit 2
fi

# The locale. A bracket expression carrying a multibyte glyph — `[✓✗●]` — is a set of single
# BYTES outside a UTF-8 locale, so under `LANG` and `LC_ALL` unset every such leg would read 0
# rows and fail through no fault of the console. The suite therefore fixes its own
# locale rather than the caller's shell: the first UTF-8 locale this host lists wins, and a
# host that lists none is still covered, because every multibyte class in a leg below is
# written as an alternation of whole glyphs (`(✓|✗|●)`), which matches the same byte sequences
# under any locale. Leg LC01 is the must-still-pass case: the console run with the locale
# emptied.
for _loc in C.UTF-8 en_GB.UTF-8 en_US.UTF-8; do
  if locale -a | grep -qx "$_loc"; then
    LC_ALL="$_loc"
    export LC_ALL
    break
  fi
done
unset _loc

AIMYTH_WATCH_NOTIFY=0
export AIMYTH_WATCH_NOTIFY
T=$(mktemp -d)
trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT INT TERM

pass=0
fail=0
ok() { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
no() { fail=$((fail + 1)); printf 'FAIL %s\n' "$1"; }

# Every concrete file cited by the module header resolves from the skill or vault root.
# Runtime templates such as <store>/<run>-timeline.txt are not documentation locators.
python3 -B - "$WATCH" > "$T/header-paths.txt" 2>&1 <<'PY_HEADER_PATHS'
import ast
from pathlib import Path
import re
import sys
import uuid

script = Path(sys.argv[1]).resolve()
header = ast.get_docstring(ast.parse(script.read_text(encoding="utf-8")))
if not header:
    print("PROBE FAILED: watch.py has no module header")
    raise SystemExit(2)


def references(text):
    tokens = re.findall(r"[\w./<>-]+\.(?:py|sh|md|txt)\b", text)
    return {p for p in tokens if "<" not in p and ">" not in p}


def missing(text):
    # <vault>/.claude/skills/delegate/watch.py: parents[3] is the vault root.
    return sorted(p for p in references(text)
                  if not ((script.parents[3] if "/" in p else script.parent) / p).is_file())


refs = references(header)
if not {"watch.py", "test_watch.sh"} <= refs:
    print("PROBE FAILED: the header path scan missed its known script and suite controls")
    raise SystemExit(2)
absent = missing(header)
planted = "absent-" + uuid.uuid4().hex + ".md"
if (script.parent / planted).exists():
    print("PROBE FAILED: the planted missing path exists")
    raise SystemExit(2)
assert missing(header + "\n" + planted) == sorted(absent + [planted])
print("header paths: %d checked, %d missing; planted missing-path control: 1" % (len(refs), len(absent)))
if absent:
    print("missing: " + ", ".join(absent))
    raise SystemExit(1)
PY_HEADER_PATHS
header_rc=$?
if [ "$header_rc" -eq 2 ]; then cat "$T/header-paths.txt"; exit 2; fi
if [ "$header_rc" -eq 0 ]; then
  ok "HP1 every header file path exists; known-file and planted missing-path controls pass"
else
  no "HP1 header file paths: $(cat "$T/header-paths.txt")"
fi

# Every leg runs the console with the store, the projects root and the vault given as fixture
# paths: nothing in watch.py may point at a real machine for these to resolve. COLUMNS and LINES
# are fixed so the rendering the assertions read is the same on every terminal.
run_watch() {
  env LLM_WIKI_STORE="$T/store" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 \
      COLUMNS=150 LINES=60 python3 -B "$WATCH" --vault "$T/vault" "$@"
}

SYNTH_VAULT_NAME=synthetic-vault-name-for-the-grep

# ---------------------------------------------------------------- fixtures
mkdir -p "$T/store/spawn-records" "$T/handoffs" "$T/vault" "$T/projects" "$T/planted" "$T/bin"

# The planted control file: the owner-path, session-id and write-pattern sweeps must each hit it.
cat > "$T/planted/planted-strays.py" <<'PLANTED'
# A planted fixture: every sweep the ship-safety legs run must hit this file, or the sweep is
# broken and its clean result over watch.py means nothing.
VAULT = "/" + "Users/example-owner/Vaults/synthetic-vault-name-for-the-grep"   # assembled: no home-path literal in a shipped file
ALSO = "/" + "home/example-owner/synthetic-vault-name-for-the-grep/notes"
SESSION = "00000000-0000-4000-8000-000000000003"


def stray_writes(path):
    with open(path, "w") as fh:
        fh.write("a write outside any report function")
    os.remove(path)
PLANTED

# The stub the `r` key runs instead of handsoff.py resume-head: it records its arguments only.
cat > "$T/bin/stub-resume.sh" <<'STUB'
#!/bin/sh
printf '%s\n' "$*" >> "$STUB_ARGS"
printf 'stub resume-head: %s\n' "$*"
STUB
chmod +x "$T/bin/stub-resume.sh"

# The pack. Both item-name shapes sit under ## Resume prompt; three decoys must not be parsed:
# one outside that section, one with no em dash, one whose index is not a number.
cat > "$T/handoffs/pack.md" <<'PACK'
# hand-off pack (synthetic fixture)

## Morning report

nothing to report: this pack is a fixture.

## Resume prompt

Continue the run in this order.
item1 N137 · build — the phase shape, a TODO and a phase
item2 N137 · verify+close — the phase shape, second
item3 N137-INSTALL — the older bare-name shape
item4 close-out — the phase shape without a TODO
item8 no-em-dash-here so this line is not an item
itemX NOT-A-NUMBER — the index is not a number

## Trace

item9 DECOY-OUTSIDE-RESUME — named outside the Resume prompt section
PACK

printf '# an empty pack (no item lines at all)\n\n## Resume prompt\n\nnothing here.\n' \
  > "$T/handoffs/empty-pack.md"

# Pointer-shaped packs: run-ptr names an existing decoy pre-flight in its Resume prompt.
# with NO item line, so the sibling <run>-preflight.md must supply the rows, in the backtick shape
# (`item0 open` — …) a pre-flight writes. run-ptr2: the named pre-flight HAS items, so it wins
# over the sibling (the order test).
printf '# decoy pre-flight (no item line)\n\n## Items\n\nnothing here either.\n' \
  > "$T/handoffs/decoy-preflight.md"
cat > "$T/handoffs/run-ptr-handoff.md" <<'PTR'
# hand-off (pointer-shaped fixture)

## Resume prompt
```
Resume run run-ptr from this file, then the contract T_HANDOFFS/decoy-preflight.md, and continue.
```

## Items
The pre-flight's `## Items` (item0 open · item1 capture) is the list; this file records progress in `## Trace`.

## Trace
PTR
sed -i '' "s#T_HANDOFFS#$T/handoffs#" "$T/handoffs/run-ptr-handoff.md"
cat > "$T/handoffs/run-ptr-preflight.md" <<'PTRPF'
# pre-flight (fixture)

## Items
- `item0 open` — resume pre-flight; the boundary.
- `item1 capture` — the sources; the boundary.
- `item2 partition and briefs` — the briefs; the boundary.
- `itemX not-a-number` — a decoy: the index is not a number.

## Lanes
| Lane | Class |
PTRPF
sed "s#decoy-preflight.md#named-preflight.md#; s#run-ptr #run-ptr2 #" "$T/handoffs/run-ptr-handoff.md" \
  > "$T/handoffs/run-ptr2-handoff.md"
printf '# named pre-flight (fixture)\n\n## Items\n- `item0 alpha` — the named file wins.\n' \
  > "$T/handoffs/named-preflight.md"
cp "$T/handoffs/run-ptr-preflight.md" "$T/handoffs/run-ptr2-preflight.md"

# Two pids the liveness legs need, and the fixture record needs with them, since the console
# now probes the pid of every open lane. LIVE_PID is this suite's own shell: certainly alive
# for as long as the suite runs, so a lane carrying it must still read `running`. REAPED_PID is
# a child started, exited and reaped here: certainly gone, and reaped, so nothing is waiting on
# it. Its one risk is pid recycling, and the premise guard below is the answer to it — the
# probe must already read the pid as gone before any fixture is written.
LIVE_PID=$$
sh -c 'exit 0' &
REAPED_PID=$!
wait "$REAPED_PID"
if kill -0 "$REAPED_PID" 2>"$T/reaped-probe.err"; then
  printf 'PROBE FAILED: the reaped pid %s still answers kill -0 (recycled?)\n' "$REAPED_PID"
  exit 2
fi
if ! kill -0 "$LIVE_PID" 2>"$T/live-probe.err"; then
  printf 'PROBE FAILED: this shell (pid %s) does not answer its own kill -0\n' "$LIVE_PID"
  exit 2
fi

python3 -B - "$T" "$WATCH" "$LIVE_PID" "$REAPED_PID" <<'PY_FIX'
"""Write the fixture record, the head transcript and the lane transcript.

The record carries every event kind handsoff.py and lane.py write, plus the schema kinds no
writer emits today (decision, correction, hold), with the field names copied from real records and
their values replaced by synthetic ones. Stamps are relative to now so the elapsed times, the
timeline and the states are the same on every run; the record's stamps carry the local offset (as
handsoff.py writes them) and the transcripts' stamps are UTC with a Z (as the harness writes them),
so the console's conversion is exercised.
"""
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

T, WATCH = sys.argv[1], sys.argv[2]
# The console probes the recorded pid of every open lane, so an open fixture lane must carry a
# pid that is really alive or it renders `✗ dead`: LIVE_PID is the suite shell's own, REAPED_PID
# a child of it that has exited and been reaped.
LIVE_PID, REAPED_PID = int(sys.argv[3]), int(sys.argv[4])
spec = importlib.util.spec_from_file_location("watch_under_test", WATCH)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

t0 = time.time() - 120 * 60
PACK = os.path.join(T, "handoffs", "pack.md")
HOMES = {"B-ONE": os.path.join(T, "lane-home", "B-ONE"),
         "C-TWO": os.path.join(T, "lane-home", "C-TWO"),
         "V-THREE": os.path.join(T, "lane-home", "V-THREE")}
for home in HOMES.values():
    os.makedirs(home, exist_ok=True)
PROJECTS = os.path.join(T, "projects")
METER = ("billed (list, prices 0000-00-00): head $1.00 · lanes $2.00 · session $3.00 · "
         "rewrites 0 ($0.00)")


def ts(mins):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0 + mins * 60))


def utc(mins):
    return datetime.fromtimestamp(t0 + mins * 60, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z")


def ev(mins, kind, **fields):
    payload = {"ts": ts(mins), "run": "run-vocab", "event": kind}
    payload.update(fields)
    return payload


events = [
    ev(0, "run-open", session="head-sid-1", head="seed: the fixture launcher", regime="multi",
       regime_src="head", handoff=PACK, detail="a synthetic run for the console suite",
       envelope_usd=40.0, pid=1001, pid_src="arg", on_limit="stop", on_limit_src="--on-limit",
       grants_file=os.path.join(T, "store", "spawn-records", "run-vocab-grants.json")),
    ev(1, "grants", session="head-sid-1", grants=2, writes=1, on_limit="stop",
       on_limit_src="--on-limit"),
    ev(2, "heartbeat", minutes=30, pid=1001, action="armed"),
    ev(3, "gate", item="item1", context=70000, percent=7, band=0, armed=True, decision="allow",
       metered=True, orientation_tokens=6000),
    ev(4, "lane-open", lane="B-ONE", **{"class": "builder"}, model="fable", effort="max",
       cwd=HOMES["B-ONE"], session_id="lane-sid-1", budget_usd=8.0, projects_root=PROJECTS,
       reason="(a) independence: a synthetic builder", mode="multi", deadline_s=3600,
       silence_s=900.0, silence_src="--silence-s"),
    ev(4, "lane-spawned", lane="B-ONE", session_id="lane-sid-1", pid=2001, wrapper_pid=2000,
       **{"class": "builder"}),
    ev(4, "lane-awake", lane="B-ONE", session_id="lane-sid-1", wrapper_pid=2000,
       **{"class": "builder"}, detached=False, awake="started", caffeinate_pid=2004,
       watched_pid=2001, command=["/usr/bin/caffeinate", "-i", "-w", "2001"],
       note="caffeinate pid 2004 holds an idle-sleep assertion until pid 2001 exits"),
    ev(5, "observation", phase="build", what="a plain note that carries no alerting word",
       note="evidence: the fixture"),
    ev(6, "observation", phase="build", what="warning: the planted alert word",
       note="evidence: the fixture"),
    ev(7, "decision", phase="build", what="a schema kind no writer emits today",
       grant="none needed"),
    ev(20, "lane-closed", lane="B-ONE", exit_class="completed", total_cost_usd=1.23, num_turns=17,
       **{"class": "builder"}, duration_s=960, exit_code=0, is_error=False,
       cost_src="transcript-estimate", report_words=700, session_id="lane-sid-1"),
    # A synthetic lane hold opens, beats once and is released: the three
    # kinds reach the vocabulary leg, and B-ONE reads completed again once the hold has ended
    ev(20.2, "hold", lane="B-ONE", harness="claude", cap=1, beat_after_s=3000,
       session_id="lane-sid-1", exit_class="completed", last_call=ts(20), last_call_src="fixture"),
    ev(20.4, "hold-beat", lane="B-ONE", harness="claude", ok=True, by="supervisor", n=1,
       usage={"input_tokens": 5, "output_tokens": 1, "cache_read_input_tokens": 90000,
              "cache_creation_input_tokens": 0}, total_cost_usd=0.03, config_match=True),
    ev(20.6, "hold-ended", lane="B-ONE", reason="released", by="release", cap=1, beats=1,
       beats_ok=1, beats_failed=0),
    ev(21, "phase-boundary", **{"from": "item1", "to": "item2"},
       disposition="the synthetic builder closed green", meter=METER,
       context="100,000 tokens (10 %)", next="item2", idle_min=1.0, denials=0,
       over_cap_reports=0, respawn_cost_usd=0.0, rewrites=0, commit="0000000",
       waste="real: none · arguable: none · avoided: none"),
    ev(22, "gate", item="item2", context=110000, percent=18, band=0, armed=True,
       decision="allow", metered=True),
    ev(23, "lane-open", lane="C-TWO", **{"class": "critic"}, model="opus", effort="max",
       cwd=HOMES["C-TWO"], session_id="lane-sid-2", budget_usd=8.0, projects_root=PROJECTS,
       reason="(a) independence: a synthetic critic"),
    ev(23, "lane-spawned", lane="C-TWO", session_id="lane-sid-2", pid=2002, wrapper_pid=2003,
       **{"class": "critic"}),
    ev(30, "stall", lane="C-TWO", silent_s=901, threshold_s=900,
       action="SIGTERM the process group"),
    ev(31, "lane-closed", lane="C-TWO", exit_class="stall", total_cost_usd=0.50, num_turns=5,
       **{"class": "critic"}, stall=True, session_id="lane-sid-2"),
    # The resumed lane is left running to the end of the fixture, so its pid must be alive or
    # the console's liveness probe would rightly draw it dead: the suite's own shell it is.
    ev(35, "lane-resumed", lane="C-TWO", session_id="lane-sid-2r", pid=LIVE_PID,
       wrapper_pid=LIVE_PID,
       **{"class": "critic"}, resume_n=1, after_limit=True, age_s=240.0, budget_usd=8.0,
       mechanism="lane.py headless, model opus, effort max"),
    ev(40, "stop-condition", which="limit", lane="head", action="wait until the reset",
       note="synthetic limit text · resets at the fixture hour", on_limit="stop",
       on_limit_src="grants"),
    ev(41, "supervisor-stood-down", reason="limit-stop", on_limit="stop", on_limit_src="grants",
       waited_s=60, note="the fixture supervisor stood down"),
    ev(42, "head-exit", band="limit", context="unmetered (fixture)", handoff=PACK, pack=True,
       spent_usd=None, pid=1001),
    ev(43, "successor-aborted", reason="resume-unsized"),
    ev(44, "head-successor", session_id="head-sid-2", pid=1002, config_dir=None, budget=30.0,
       started_after_s=0, out=os.path.join(T, "store", "spawn-records", "run-vocab-head-1.out")),
    # the wait runs from the limit stop at 40 to the resume at 75: the marks of 41-44 sit inside
    # it, and the free columns between them and the resume are the hatching the suite looks for
    ev(75, "head-resumed", session_id="head-sid-2", pid=1002, context=120000, waited_s=0,
       reset_source="resume-head (by hand, after the reset)", resume_n=1, budget=30.0),
    ev(76, "run-resume", session="head-sid-2", head="the resumed fixture head", on_limit="stop",
       on_limit_src="grants", pid=1002, pid_src="arg"),
    ev(76, "supervise", mode="launched", pid=1002, session_id="head-sid-2", supervisor_pid=1003),
    ev(77, "correction", target="a fixture claim", change="corrected", reason="the fixture"),
    ev(77, "hold", **{"class": "fixture"}, what="a held item", route="no action"),
    ev(78, "unwatched", lane="C-TWO", note="the watcher could not find the transcript"),
    ev(78, "reflect-inputs", session="head-sid-2", counts="0 rows", out="none"),
    ev(79, "phase-boundary", **{"from": "item2", "to": "item3"},
       disposition="the synthetic critic was resumed and left running", meter=METER,
       context="130,000 tokens (13 %)", next="item3", idle_min=2.0, denials=0,
       over_cap_reports=0, respawn_cost_usd=0.0, rewrites=0, commit="0000000",
       waste="real: none · arguable: none · avoided: none"),
    ev(80, "gate", item="item3", context=130000, percent=30, band=0, armed=True,
       decision="allow", metered=True),
    ev(81, "lane-open", lane="V-THREE", **{"class": "verifier"}, model="fable", effort="high",
       cwd=HOMES["V-THREE"], session_id="lane-sid-3", budget_usd=6.0, projects_root=PROJECTS,
       reason="(b) breadth: a synthetic verifier"),
    # V-THREE never closes in this fixture: the same reason as C-TWO's resume above.
    ev(81, "lane-spawned", lane="V-THREE", session_id="lane-sid-3", pid=LIVE_PID,
       wrapper_pid=LIVE_PID, **{"class": "verifier"}),
    ev(85, "observation", phase="verify", what="PROBE FAILED: a planted premise failure",
       note="evidence: the fixture"),
    ev(86, "observation", phase="verify", what="a late plain note with no alerting word in it",
       note="evidence: the fixture"),
]

records = os.path.join(T, "store", "spawn-records")


def write_jsonl(name, rows):
    with open(os.path.join(records, name), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


write_jsonl("run-vocab.jsonl", events)
# the same run, closed: the close ends the item in hand and triggers the timeline report
write_jsonl("run-vocab-closed.jsonl", [dict(e, run="run-vocab-closed") for e in events] + [
    dict(ev(90, "run-close", items="3", lanes="3", meter=METER, reason_tally="(a)x2 (b)x1",
            trace="3 rows", commit="0000000", push="ok"), run="run-vocab-closed")])
# the same run closed with every item done: item4 starts at a boundary just before the close, is
# WORKED (a ledger observation carrying its phase) and ends on an explicit item-done, so the verdict
# reads 4/4 · all done (the green case for the close's tone). Without that record item4 reads
# unresolved, and without the observation its only start is the boundary's `to`, which the close
# reads as skipped since 2026-09-17 (register 12:51; the F4 legs below).
write_jsonl("run-vocab-alldone.jsonl", [dict(e, run="run-vocab-alldone") for e in events] + [
    dict(ev(89, "phase-boundary", **{"from": "item3", "to": "item4"},
            disposition="the synthetic verifier closed green", meter=METER), run="run-vocab-alldone"),
    dict(ev(89, "observation", phase="item4", what="the close-out report written",
            note="evidence: the fixture"), run="run-vocab-alldone"),
    dict(ev(89, "item-done", items=["item4"], note="the close-out report written"), run="run-vocab-alldone"),
    dict(ev(90, "run-close", items="4", lanes="3", meter=METER, reason_tally="(a)x2 (b)x1",
            trace="4 rows", commit="0000000", push="ok"), run="run-vocab-alldone")])
# the head stopped: one more stop after the last head start, so the `r` key may fire
write_jsonl("run-stopped.jsonl", [dict(e, run="run-stopped") for e in events] + [
    dict(ev(88, "stop-condition", which="limit", lane="head", action="wait until the reset",
            note="synthetic limit text"), run="run-stopped")])
# no limit wait anywhere: the negative for the hatched wait
write_jsonl("run-nowait.jsonl", [dict(e, run="run-nowait") for e in events
                                 if e["event"] not in ("stop-condition", "head-resumed")])
# a limit wait ended by a successor head with no head-resumed (2026-09-09): the wait must close
# at the successor, never run to the end of the record
write_jsonl("run-succwait.jsonl", [dict(e, run="run-succwait") for e in events
                                   if e["event"] != "head-resumed"])
# a model-scoped limit (which limit-model, 2026-09-16): the wait must open exactly as for a
# plain limit, and close at the successor
write_jsonl("run-modelwait.jsonl", [dict(e, run="run-modelwait", which="limit-model")
                                    if e["event"] == "stop-condition" else dict(e, run="run-modelwait")
                                    for e in events if e["event"] != "head-resumed"])
# a record whose pack yields no items and which carries no gate event
write_jsonl("run-noitems.jsonl", [
    dict(ev(0, "run-open", session="head-sid-1", handoff=os.path.join(T, "handoffs",
                                                                     "empty-pack.md"),
            head="the fixture", regime="multi"), run="run-noitems"),
    dict(ev(1, "observation", phase="none", what="no gate here"), run="run-noitems")])
# pointer-shaped packs: the rows come from a pre-flight (run-ptr: the sibling; run-ptr2: the named)
for rp in ("run-ptr", "run-ptr2"):
    write_jsonl(rp + ".jsonl", [
        dict(ev(0, "run-open", session="head-sid-1", handoff=os.path.join(T, "handoffs",
                                                                         rp + "-handoff.md"),
                head="the fixture", regime="single"), run=rp),
        dict(ev(1, "observation", phase="none", what="no gate here"), run=rp)])
# no item line anywhere, but the run-open carries expect_items: its keys are the rows, unnamed;
# a key that is not item<k> is refused
write_jsonl("run-expect.jsonl", [
    dict(ev(0, "run-open", session="head-sid-1", handoff=os.path.join(T, "handoffs",
                                                                     "empty-pack.md"),
            head="the fixture", regime="single",
            expect_items={"item0": 40000, "item1": 80000, "junk": 5}), run="run-expect"),
    dict(ev(1, "observation", phase="none", what="no gate here"), run="run-expect")])
# The plain-lane-run shape: lane events and NO run-open, as the lane wrapper alone writes a record
# when an attended session spawns lanes. Two lanes, one completed and one error, and a third left
# open, so the close's counts by exit class have something to count.
plain_events = [
    ev(0, "lane-open", lane="P-ONE", **{"class": "builder"}, model="fable", effort="max",
       cwd=HOMES["B-ONE"], session_id="plain-sid-1", budget_usd=8.0, projects_root=PROJECTS,
       reason="(a) independence: a synthetic plain-run builder"),
    ev(0, "lane-spawned", lane="P-ONE", session_id="plain-sid-1", pid=3001, wrapper_pid=3000,
       **{"class": "builder"}),
    ev(18, "lane-closed", lane="P-ONE", exit_class="completed", total_cost_usd=2.50, num_turns=11,
       **{"class": "builder"}, duration_s=1080, exit_code=0, is_error=False,
       session_id="plain-sid-1"),
    ev(20, "lane-open", lane="P-TWO", **{"class": "critic"}, model="opus", effort="max",
       cwd=HOMES["C-TWO"], session_id="plain-sid-2", budget_usd=6.0, projects_root=PROJECTS,
       reason="(b) breadth: a synthetic plain-run critic"),
    ev(30, "lane-closed", lane="P-TWO", exit_class="error", total_cost_usd=1.25, num_turns=4,
       **{"class": "critic"}, duration_s=600, exit_code=1, is_error=True,
       session_id="plain-sid-2"),
    ev(31, "lane-open", lane="P-THREE", **{"class": "verifier"}, model="fable", effort="high",
       cwd=HOMES["V-THREE"], session_id="plain-sid-3", budget_usd=4.0, projects_root=PROJECTS,
       reason="(c) load: a synthetic plain-run verifier, still running"),
]
write_jsonl("run-plain.jsonl", [dict(e, run="run-plain") for e in plain_events])
write_jsonl("run-plain-closed.jsonl", [dict(e, run="run-plain-closed") for e in plain_events] + [
    dict(ev(40, "run-close", shape="plain-lane-run", lanes=3,
            lanes_by_exit={"completed": 1, "error": 1, "open": 1}, spend_usd=3.75,
            spend_src="sum of 2 lane-closed total_cost_usd",
            meter="none: a plain lane run names no head session to meter"),
         run="run-plain-closed")])
# The liveness shape: four open lanes, no close event on any of them, differing only in the pids
# their spawn recorded. L-DEAD carries a pid that has exited and been reaped, with no close
# event; it must not appear as running. L-LIVE carries
# this suite's own shell. L-MIXED carries one gone pid and one live one: a wrapper that died with
# its lane still working is NOT dead. L-NOPID's spawn names no pid at all, which is an absence and
# never a death. The closed variant adds a run-close so the banner's counts by exit class can be
# read.
liveness_events = [
    ev(0, "lane-open", lane="L-DEAD", **{"class": "builder"}, model="fable", effort="max",
       cwd=HOMES["B-ONE"], session_id="live-sid-1", budget_usd=8.0, projects_root=PROJECTS,
       reason="(a) independence: the lane killed by hand"),
    ev(0, "lane-spawned", lane="L-DEAD", session_id="live-sid-1", pid=REAPED_PID,
       wrapper_pid=REAPED_PID, **{"class": "builder"}),
    ev(1, "lane-open", lane="L-LIVE", **{"class": "critic"}, model="opus", effort="max",
       cwd=HOMES["C-TWO"], session_id="live-sid-2", budget_usd=6.0, projects_root=PROJECTS,
       reason="(b) breadth: the lane still working"),
    ev(1, "lane-spawned", lane="L-LIVE", session_id="live-sid-2", pid=LIVE_PID,
       wrapper_pid=LIVE_PID, **{"class": "critic"}),
    ev(2, "lane-open", lane="L-MIXED", **{"class": "verifier"}, model="fable", effort="high",
       cwd=HOMES["V-THREE"], session_id="live-sid-3", budget_usd=4.0, projects_root=PROJECTS,
       reason="(c) load: the wrapper gone, the lane working"),
    ev(2, "lane-spawned", lane="L-MIXED", session_id="live-sid-3", pid=LIVE_PID,
       wrapper_pid=REAPED_PID, **{"class": "verifier"}),
    ev(3, "lane-open", lane="L-NOPID", **{"class": "builder"}, model="sonnet", effort="medium",
       cwd=HOMES["B-ONE"], session_id="live-sid-4", budget_usd=2.0, projects_root=PROJECTS,
       reason="(a) independence: a spawn line with no pid in it"),
    ev(3, "lane-spawned", lane="L-NOPID", session_id="live-sid-4", **{"class": "builder"}),
]
write_jsonl("run-liveness.jsonl", [dict(e, run="run-liveness") for e in liveness_events])
write_jsonl("run-liveness-closed.jsonl",
            [dict(e, run="run-liveness-closed") for e in liveness_events]
            + [dict(ev(9, "run-close", shape="plain-lane-run", lanes=4,
                       meter="none: a plain lane run names no head session to meter"),
                    run="run-liveness-closed")])
# MC: the lanes-now model cell. Four open lanes on this suite's own live pid, differing only in
# the model and effort their spawn recorded: a long vendor name with a short effort, a recorded
# effort carrying its reason in the same string, a plain pair as the control that must not move,
# and a name too long to fit even shortened. An 11-character cut would print `gpt-6-astr…` and
# drop the effort the owner reads the row for.
modelcell_events = []
for _n, _c, _m, _e in (("M-ASTRA", "writer", "gpt-6-astra", "ultra"),
                       ("M-REASON", "critic", "opus", "max (definition, throttle default)"),
                       ("M-PLAIN", "builder", "fable", "max"),
                       ("M-LONG", "verifier", "claude-opus-4-5", "xhigh")):
    modelcell_events += [
        ev(0, "lane-open", lane=_n, **{"class": _c}, model=_m, effort=_e, cwd=HOMES["B-ONE"],
           session_id="mc-sid-" + _n, budget_usd=8.0, projects_root=PROJECTS,
           reason="(a) independence: a model-cell fixture lane"),
        ev(0, "lane-spawned", lane=_n, session_id="mc-sid-" + _n, pid=LIVE_PID,
           wrapper_pid=LIVE_PID, **{"class": _c})]
write_jsonl("run-modelcell.jsonl", [dict(e, run="run-modelcell") for e in modelcell_events])
# the plain record's own broken premise: no run-open AND no lane event
write_jsonl("run-plain-empty.jsonl", [
    dict(ev(0, "observation", phase="", what="a record with neither a run-open nor a lane"),
         run="run-plain-empty")])
# gate events but no pack items: the gate item ids are the item list
write_jsonl("run-gateonly.jsonl", [
    dict(ev(0, "run-open", session="head-sid-1", handoff=os.path.join(T, "handoffs",
                                                                     "empty-pack.md"),
            head="the fixture", regime="multi"), run="run-gateonly"),
    dict(ev(3, "gate", item="item1", percent=7, decision="allow", metered=True),
         run="run-gateonly"),
    dict(ev(9, "gate", item="item2", percent=9, decision="allow", metered=True),
         run="run-gateonly")])
# The held lanes (2026-09-17): four finished lanes under item1 — H-ONE held with one beat of a cap
# of two, H-TWO held with a beat that failed, H-THREE whose hold ended at the cap, H-FOUR held
# and then resumed for real (running again, on this suite's own live pid) — plus a decision hold
# of the older schema shape (class, what, route, no lane), which holds no lane.


def held_lane(name, cls, model):
    return [ev(2, "lane-open", lane=name, **{"class": cls}, model=model, effort="max",
               cwd=HOMES["B-ONE"], session_id="held-sid-" + name, budget_usd=8.0,
               projects_root=PROJECTS, reason="(a) independence: a held fixture lane"),
            ev(2, "lane-spawned", lane=name, session_id="held-sid-" + name, pid=REAPED_PID,
               wrapper_pid=REAPED_PID, **{"class": cls}),
            ev(10, "lane-closed", lane=name, exit_class="completed", total_cost_usd=2.0,
               num_turns=9, **{"class": cls}, session_id="held-sid-" + name),
            ev(11, "hold", lane=name, harness="claude", cap=2 if name == "H-ONE" else 1,
               beat_after_s=3000, session_id="held-sid-" + name, exit_class="completed",
               last_call=ts(10), last_call_src="fixture", renew=False, beats_before=0)]


held_events = ([ev(0, "run-open", session="head-sid-1", head="the held fixture", regime="multi",
                   handoff=PACK, pid=1001, pid_src="arg"),
                ev(1, "gate", item="item1", context=70000, percent=7, band=0, armed=True,
                   decision="allow", metered=True)]
               + held_lane("H-ONE", "builder", "fable") + held_lane("H-TWO", "critic", "opus")
               + held_lane("H-THREE", "verifier", "sonnet") + held_lane("H-FOUR", "builder", "opus")
               # H-ONE's beat is one minute old (its next beat lies ahead); H-TWO's failed one
               # is 108 minutes old, past the interval, so its row reads beat due
               + [ev(119, "hold-beat", lane="H-ONE", harness="claude", ok=True, by="supervisor", n=1,
                     usage={"input_tokens": 5, "output_tokens": 1, "cache_read_input_tokens": 90000,
                            "cache_creation_input_tokens": 0}, total_cost_usd=0.03),
                  ev(12, "hold-beat", lane="H-TWO", harness="claude", ok=False, by="supervisor", n=1,
                     exit_class="error", error="the fixture beat failed"),
                  ev(13, "hold-ended", lane="H-THREE", reason="cap", by="supervisor", cap=1,
                     beats=1, beats_ok=1, beats_failed=0),
                  ev(14, "lane-resumed", lane="H-FOUR", session_id="held-sid-H-FOUR", pid=LIVE_PID,
                     wrapper_pid=LIVE_PID, **{"class": "builder"}, resume_n=1),
                  ev(15, "hold", **{"class": "fixture"}, what="a decision held for the owner",
                     route="no action"),
                  # H-FIVE: its last call is an hour old and its hold two minutes old, so its beat
                  # is due by the supervisor's reference (the last call), never by the hold's stamp
                  ev(50, "lane-open", lane="H-FIVE", **{"class": "builder"}, model="fable",
                     effort="max", cwd=HOMES["B-ONE"], session_id="held-sid-H-FIVE", budget_usd=8.0,
                     projects_root=PROJECTS, reason="(a) independence: a held fixture lane"),
                  ev(50, "lane-spawned", lane="H-FIVE", session_id="held-sid-H-FIVE",
                     pid=REAPED_PID, wrapper_pid=REAPED_PID, **{"class": "builder"}),
                  ev(60, "lane-closed", lane="H-FIVE", exit_class="completed", total_cost_usd=2.0,
                     num_turns=9, **{"class": "builder"}, session_id="held-sid-H-FIVE"),
                  ev(118, "hold", lane="H-FIVE", harness="claude", cap=1, beat_after_s=3000,
                     session_id="held-sid-H-FIVE", exit_class="completed", last_call=ts(60),
                     last_call_src="fixture", renew=False, beats_before=0),
                  # H-SIX: a reason longer than the row, and a hold that was released
                  ev(51, "lane-open", lane="H-SIX", **{"class": "critic"}, model="opus",
                     effort="max", cwd=HOMES["C-TWO"], session_id="held-sid-H-SIX", budget_usd=8.0,
                     projects_root=PROJECTS,
                     reason="(a) independence: a held fixture lane whose reason runs well past "
                            "the width of the lanes panel, as a real spawn's reason often does, "
                            "so that whatever follows it on the row is cut away"),
                  ev(51, "lane-spawned", lane="H-SIX", session_id="held-sid-H-SIX",
                     pid=REAPED_PID, wrapper_pid=REAPED_PID, **{"class": "critic"}),
                  ev(61, "lane-closed", lane="H-SIX", exit_class="completed", total_cost_usd=2.0,
                     num_turns=9, **{"class": "critic"}, session_id="held-sid-H-SIX"),
                  ev(62, "hold", lane="H-SIX", harness="claude", cap=1, beat_after_s=3000,
                     session_id="held-sid-H-SIX", exit_class="completed", last_call=ts(61),
                     last_call_src="fixture", renew=False, beats_before=0),
                  ev(63, "hold-ended", lane="H-SIX", reason="released", by="release", cap=1,
                     beats=0, beats_ok=0, beats_failed=0),
                  # H-SEVEN (critic F6, 2026-09-17): held, then resumed for real and closed again
                  # five minutes ago. The supervisor's next beat falls due an interval after THAT
                  # close, so the row must read `next due`, not `beat due` for the best part of
                  # an hour. Its hold is still open (no hold-ended), and it is not running.
                  ev(52, "lane-open", lane="H-SEVEN", **{"class": "builder"}, model="fable",
                     effort="max", cwd=HOMES["B-ONE"], session_id="held-sid-H-SEVEN",
                     budget_usd=8.0, projects_root=PROJECTS,
                     reason="(a) independence: a held fixture lane resumed for real"),
                  ev(52, "lane-spawned", lane="H-SEVEN", session_id="held-sid-H-SEVEN",
                     pid=REAPED_PID, wrapper_pid=REAPED_PID, **{"class": "builder"}),
                  ev(58, "lane-closed", lane="H-SEVEN", exit_class="completed",
                     total_cost_usd=2.0, num_turns=9, **{"class": "builder"},
                     session_id="held-sid-H-SEVEN"),
                  ev(59, "hold", lane="H-SEVEN", harness="claude", cap=2, beat_after_s=3000,
                     session_id="held-sid-H-SEVEN", exit_class="completed", last_call=ts(58),
                     last_call_src="fixture", renew=False, beats_before=0),
                  ev(100, "lane-resumed", lane="H-SEVEN", session_id="held-sid-H-SEVEN",
                     pid=REAPED_PID, wrapper_pid=REAPED_PID, **{"class": "builder"}, resume_n=1),
                  ev(115, "lane-closed", lane="H-SEVEN", exit_class="completed",
                     total_cost_usd=3.0, num_turns=4, **{"class": "builder"},
                     session_id="held-sid-H-SEVEN")])
held_events.sort(key=lambda e: e["ts"])      # a record is written in time order; the sort is stable
write_jsonl("run-held.jsonl", [dict(e, run="run-held") for e in held_events])


def assistant(mins, text=None, tool=None, target=None, model="claude-fixture"):
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if tool:
        content.append({"type": "tool_use", "name": tool, "id": "toolu_fixture",
                        "input": {"command": target} if tool == "Bash" else {"file_path": target}})
    return {"type": "assistant", "timestamp": utc(mins), "sessionId": "fixture",
            "message": {"role": "assistant", "model": model, "content": content}}


def write_transcript(directory, name, rows):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


vault_dir = os.path.join(PROJECTS, watch.dashed(os.path.join(T, "vault")))
write_transcript(vault_dir, "head-sid-1.jsonl", [
    assistant(2, text="the first head speaks"),
    assistant(3, tool="Bash", target="a fixture command from head one")])
write_transcript(vault_dir, "head-sid-2.jsonl", [
    assistant(76, text="the resumed head speaks in its own prose"),
    assistant(77, tool="Bash", target="a fixture command from the resumed head",
              model="<synthetic-model-record>"),
    assistant(78, text="the resumed head speaks again")])
write_transcript(os.path.join(PROJECTS, watch.dashed(HOMES["V-THREE"])), "lane-sid-3.jsonl", [
    assistant(82, text="the verifier lane speaks"),
    assistant(83, tool="Bash", target="the last tool call of the lane")])
print("fixtures written")
PY_FIX
[ $? -eq 0 ] || { printf 'PROBE FAILED: the fixture generator did not run\n'; exit 2; }

# The manifest of every file the console reads: it must be byte-identical at the end.
# ---------------------------------------------------------------- fixtures: the session view (A4)
# A fixture job root (AIMYTH_TASKS_ROOT) and four fixture transcripts under the fixture projects
# root. The session view reads those two observables and nothing else, so every leg below runs
# against a machine that has no harness on it. The job directory is keyed by the DASHED working
# directory the transcript itself records, so the suite computes it with the same rule the console
# does rather than spelling one.
SESS_CWD="$T/vault"
DASHED_CWD=$(python3 -B - "$SESS_CWD" <<'DASH_END'
import os, re, sys
print(re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(sys.argv[1])))
DASH_END
)
TASKS="$T/tasks-root/$DASHED_CWD"
mkdir -p "$T/projects/session-project" "$T/projects/session-project/subagents" "$T/state" \
         "$TASKS/jobs-one-aaa/tasks" "$TASKS/mtime-three-ccc/tasks"

python3 -B - "$T" "$SESS_CWD" "$T/projects/session-project" "$TASKS" <<'JOBFIX_END'
"""Build the session-view fixtures: four transcripts and their job directories.

Plant every supported start shape: background Bash, a foreground call moved to the background
after timeout, Monitor, and Agent. Plant the notification carriers too: user message.content,
queue-operation content, and attachment.prompt.
"""
import json, os, sys

T, CWD, PROJ, TASKS = sys.argv[1:5]
TS = "2026-09-08T01:%02d:%02d.000Z"


def rec(**kw):
    kw.setdefault("cwd", CWD)
    return json.dumps(kw)


def assistant(i, blocks):
    return rec(type="assistant", timestamp=TS % (i, 0), message={"role": "assistant", "content": blocks})


def result(i, use_id, text):
    return rec(type="user", timestamp=TS % (i, 30),
               message={"role": "user", "content": [{"type": "tool_result",
                                                     "tool_use_id": use_id, "content": text}]})


def use(use_id, name, inp):
    return {"type": "tool_use", "id": use_id, "name": name, "input": inp}


def notif(i, carrier, task_id, status):
    body = ("<task-notification>\n<task-id>%s</task-id>\n<tool-use-id>tu-x</tool-use-id>\n"
            "<status>%s</status>\n<summary>a fixture summary</summary>\n</task-notification>"
            % (task_id, status))
    if carrier == "user":
        return rec(type="user", timestamp=TS % (i, 40), message={"role": "user", "content": body})
    if carrier == "queue":
        return rec(type="queue-operation", timestamp=TS % (i, 40), content=body)
    return rec(type="attachment", timestamp=TS % (i, 40), attachment={"prompt": body})


# ---- session one: every kind, every state, every notification carrier
lines = []
jobs = [
    # (use id, tool, input, result text, job id)
    ("tu-1", "Bash", {"command": "sh /fixture/test_beta.sh", "run_in_background": True},
     "Command running in background with ID: jsuiteb. Output is being written to: /x/jsuiteb.output.",
     "jsuiteb"),
    ("tu-2", "Bash", {"command": "sh /fixture/test_alpha.sh", "run_in_background": True},
     "Command running in background with ID: jsuitea. Output is being written to: /x/jsuitea.output.",
     "jsuitea"),
    # a lane job started by the MOVED shape: no run_in_background anywhere on the tool call
    ("tu-3", "Bash", {"command": "python3 -B lane.py watch --run run-jobs --lane L1"},
     "Command did not complete within its 120s timeout and was moved to the background "
     "(ID: jlane). Output is being written to: /x/jlane.output.", "jlane"),
    ("tu-4", "Monitor", {"command": "until test -f /x/done; do sleep 5; done", "persistent": True},
     "Monitor started (task jwaiter, persistent — runs until TaskStop or session end).", "jwaiter"),
    ("tu-5", "Agent", {"description": "a fixture agent", "subagent_type": "critic",
                       "run_in_background": True, "prompt": "a fixture prompt"},
     [{"type": "text", "text": "Async agent launched successfully.\nagentId: abcdef0123456789a\n"
                               "The agent is working in the background."}], "abcdef0123456789a"),
    # an `other` command whose output file is a symlink into a subagent transcript: the file
    # decides the kind, not the command
    ("tu-6", "Bash", {"command": "python3 -c 'print(1)'", "run_in_background": True},
     "Command running in background with ID: jlink. Output is being written to: /x/jlink.output.",
     "jlink"),
    ("tu-7", "Bash", {"command": "python3 -c 'print(2)'", "run_in_background": True},
     "Command running in background with ID: jother. Output is being written to: /x/jother.output.",
     "jother"),
    ("tu-8", "Bash", {"command": "echo hi", "run_in_background": True},
     "Command running in background with ID: jlost. Output is being written to: /x/jlost.output.",
     "jlost"),
]
for i, (uid, tool, inp, text, _ident) in enumerate(jobs, start=1):
    lines.append(assistant(i, [use(uid, tool, inp)]))
    lines.append(result(i, uid, text))
# the three carriers, one each
lines.append(notif(20, "queue", "jsuiteb", "completed"))
lines.append(notif(21, "attachment", "jsuitea", "completed"))
lines.append(notif(22, "user", "jother", "failed"))
open(os.path.join(PROJ, "jobs-one-aaa.jsonl"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

# ---- session two: a prefix rival for `jobs-`, and no background record at all
open(os.path.join(PROJ, "jobs-two-bbb.jsonl"), "w", encoding="utf-8").write(
    assistant(1, [{"type": "text", "text": "a turn with no tool call"}]) + "\n")

# ---- session three: a torn record after the start records — the by-mtime fallback
three = [assistant(1, [use("tu-a", "Bash", {"command": "echo one", "run_in_background": True})]),
         result(1, "tu-a", "Command running in background with ID: mrun. Output is being "
                           "written to: /x/mrun.output."),
         assistant(2, [use("tu-b", "Bash", {"command": "echo two", "run_in_background": True})]),
         result(2, "tu-b", "Command running in background with ID: mdone. Output is being "
                           "written to: /x/mdone.output."),
         '{"type":"user","timestamp":"2026-09-08T01:30:00.000Z", TORN']
open(os.path.join(PROJ, "mtime-three-ccc.jsonl"), "w", encoding="utf-8").write("\n".join(three) + "\n")

# ---- session four: the start sentence where it is NOT a start, and quoted script paths
# Every decoy here is a live shape: a grep over another session's transcript can put a phantom row
# on the operator's own board, and a lane watch whose command quotes the script's path can read
# `other`. The true start is the control on the same session.
four = [
    assistant(1, [use("tu-d1", "Bash", {"command": "python3 -c 'print(1)'",
                                        "run_in_background": True})]),
    result(1, "tu-d1", "Command running in background with ID: dtrue. Output is being written "
                       "to: /x/dtrue.output."),
    # a decoy in assistant prose: the sentence quoted back inside a turn
    assistant(2, [{"type": "text", "text": "The harness answered: Command running in background "
                                           "with ID: dphantom1. That was another session."}]),
    # a decoy inside another tool's output: a grep whose hits carry the sentence
    assistant(3, [use("tu-d2", "Bash", {"command": "grep -n background /x/other-session.jsonl"})]),
    result(3, "tu-d2", "---transcripts with background records---\n/x/other-session.jsonl:12: "
                       "Command running in background with ID: dphantom2. Output is being "
                       "written to: /x/dphantom2.output."),
    # a decoy with no tool_use of its own: a result whose tool_use_id resolves to nothing
    result(4, "tu-missing", "Command running in background with ID: dorphan. Output is being "
                            "written to: /x/dorphan.output."),
    # the three quoted commands: a lane watch, the run console, the console through handsoff.py
    assistant(5, [use("tu-d3", "Bash",
                      {"command": "cd /tmp && python3 -B \"/fixture/delegate/lane.py\" watch "
                                  "--run run-jobs --lane L1 --max-wait-s 570",
                       "run_in_background": True})]),
    result(5, "tu-d3", "Command running in background with ID: dqlane. Output is being written "
                       "to: /x/dqlane.output."),
    assistant(6, [use("tu-d4", "Bash",
                      {"command": "python3 -B \"/fixture/delegate/watch.py\" --run r --once",
                       "run_in_background": True})]),
    result(6, "tu-d4", "Command running in background with ID: dqwatch. Output is being written "
                       "to: /x/dqwatch.output."),
    assistant(7, [use("tu-d5", "Bash",
                      {"command": "python3 -B \"/fixture/delegate/handsoff.py\" watch --run r",
                       "run_in_background": True})]),
    result(7, "tu-d5", "Command running in background with ID: dqhandsoff. Output is being "
                       "written to: /x/dqhandsoff.output."),
]
open(os.path.join(PROJ, "decoy-four-ddd.jsonl"), "w", encoding="utf-8").write("\n".join(four) + "\n")

# ---- the lane the `jlane` job watches, and its run record
lane_lines = [assistant(i, [use("tu-l%d" % i, "Read", {"file_path": "/x/a"})]) for i in range(1, 5)]
open(os.path.join(PROJ, "lane-sess-1.jsonl"), "w", encoding="utf-8").write("\n".join(lane_lines) + "\n")
open(os.path.join(T, "store", "spawn-records", "run-jobs.jsonl"), "w", encoding="utf-8").write(
    json.dumps({"ts": "2026-09-08T01:00:00+0100", "run": "run-jobs", "event": "run-open"}) + "\n" +
    json.dumps({"ts": "2026-09-08T01:01:00+0100", "run": "run-jobs", "event": "lane-open",
                "lane": "L1", "class": "builder", "model": "fable", "effort": "max",
                "max_turns": 10, "hard_usd": 8.0, "cwd": CWD, "session_id": "lane-sess-1"}) + "\n")

# ---- the job directories
one = os.path.join(TASKS, "jobs-one-aaa", "tasks")


def out(ident, text):
    open(os.path.join(one, ident + ".output"), "w", encoding="utf-8").write(text)


out("jsuiteb", "\n".join("ok   leg %d" % i for i in range(1, 13)) + "\nPASS 12/12\n")
out("jsuitea", "ok   leg 1\nok   leg 2\nok   leg 3\n")
out("jlane", "lane watch running\n")
out("jwaiter", "waiting\n")
out("jother", "a failure line\n")
# the agent's output is a symbolic link into a subagent transcript, as the harness writes it
sub = os.path.join(PROJ, "subagents", "agent-abcdef0123456789a.jsonl")
open(sub, "w", encoding="utf-8").write('{"type":"assistant"}\n')
os.symlink(sub, os.path.join(one, "abcdef0123456789a.output"))
sub2 = os.path.join(PROJ, "subagents", "agent-jlink.jsonl")
open(sub2, "w", encoding="utf-8").write('{"type":"assistant"}\n')
os.symlink(sub2, os.path.join(one, "jlink.output"))
# the decoy: an output file with no start record anywhere in the transcript. Not a job.
out("norecord1", "a persisted capture with no start record\n")
# `jlost` deliberately has NO output file

four_dir = os.path.join(TASKS, "decoy-four-ddd", "tasks")
os.makedirs(four_dir, exist_ok=True)
for ident in ("dtrue", "dqlane", "dqwatch", "dqhandsoff"):
    open(os.path.join(four_dir, ident + ".output"), "w", encoding="utf-8").write("still writing\n")

three_dir = os.path.join(TASKS, "mtime-three-ccc", "tasks")
open(os.path.join(three_dir, "mrun.output"), "w", encoding="utf-8").write("still writing\n")
open(os.path.join(three_dir, "mdone.output"), "w", encoding="utf-8").write("finished\n")
# Both mtimes are set RELATIVE to the transcript's last parsed record, never to the clock: the
# fallback compares those two numbers, so a fixture pinned to `now` would decide differently
# depending on the hour the suite ran (it would read `done` for both with the fixture stamps an hour
# ahead of the wall clock).
from datetime import datetime
cut = datetime.fromisoformat((TS % (2, 30)).replace("Z", "+00:00")).timestamp()
os.utime(os.path.join(three_dir, "mrun.output"), (cut + 3600, cut + 3600))
os.utime(os.path.join(three_dir, "mdone.output"), (cut - 3600, cut - 3600))
JOBFIX_END

# The session view is run with every root pointed at the fixture tree, and its state directory
# separate from $T/handoffs so the manifest legs below measure the console, not the cache.
run_jobs() {
  env LLM_WIKI_STORE="$T/store" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_TASKS_ROOT="$T/tasks-root" \
      AIMYTH_STATE_DIR="$T/state" AIMYTH_WATCH_NOTIFY=0 COLUMNS=150 LINES=60 \
      python3 -B "$WATCH" --vault "$T/vault" "$@"
}

manifest() {
  find "$T/store" "$T/handoffs" "$T/projects" "$T/tasks-root" -type f -print0 | sort -z |
    xargs -0 shasum | sort
}
manifest > "$T/manifest-before.txt"

# ---------------------------------------------------------------- leg 1: item shapes
run_watch --run run-vocab --once --plain > "$T/vocab.txt" 2>"$T/vocab.err"
rc=$?
if [ "$rc" -eq 0 ] && [ -s "$T/vocab.txt" ]; then
  ok "the console renders a snapshot of the vocabulary record (exit 0)"
else
  no "the vocabulary snapshot exited $rc: $(head -2 "$T/vocab.err")"
fi

if grep -q 'item1  *N137 · build' "$T/vocab.txt" && grep -q 'item2  *N137 · verify+close' "$T/vocab.txt" &&
   grep -q 'item4  *close-out' "$T/vocab.txt"; then
  ok "the phase shape parses (item1 N137 · build, item2 N137 · verify+close, item4 close-out)"
else
  no "the phase shape did not parse: $(grep -c 'item' "$T/vocab.txt") item lines seen"
fi

if grep -q 'item3  *N137-INSTALL' "$T/vocab.txt"; then
  ok "the older bare-name shape parses (item3 N137-INSTALL)"
else
  no "the bare-name shape did not parse"
fi

if grep -q 'DECOY-OUTSIDE-RESUME' "$T/vocab.txt" || grep -q 'NOT-A-NUMBER' "$T/vocab.txt" ||
   grep -q 'no-em-dash-here' "$T/vocab.txt"; then
  no "a planted decoy line was parsed as an item"
else
  ok "the three planted decoys (outside the section, no em dash, a non-numeric index) are refused"
fi

# ---------------------------------------------------------------- leg 2: the no-items premise
# A run-open with no item row anywhere is a live run with nothing to draw yet: a warning on
# stderr and on the board, exit 0, never a refusal (2026-09-20). The refusal stays for a record
# with no run-open and no lane (the plain-empty leg below) and for a missing record.
run_watch --run run-noitems --once --plain > "$T/noitems.out" 2> "$T/noitems.err"
rc=$?
if [ "$rc" -eq 0 ] && grep -q 'watch.py: warning: no item line in .*empty-pack.md, none in a pre-flight beside it' "$T/noitems.err" &&
   grep -q 'no item row yet · none in the pack' "$T/noitems.out" && ! grep -q 'PROBE FAILED' "$T/noitems.err" &&
   ! grep -q '0/1 items done' "$T/noitems.out"; then
  ok "a pack with no items and a record with no gate renders with a warning (exit 0, the board says no item row yet)"
else
  no "the no-items record gave exit $rc; err: $(head -1 "$T/noitems.err"); rows: $(grep -E 'overall|PROBE' "$T/noitems.out" | head -2 | tr '\n' '|')"
fi

out=$(run_watch --run run-ptr --once --plain 2>&1)
rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -qE '^│ item0 +open ' && printf '%s' "$out" | grep -qE '^│ item1 +capture ' &&
   printf '%s' "$out" | grep -qE '^│ item2 +partition and briefs ' && ! printf '%s' "$out" | grep -q 'not-a-number' &&
   printf '%s' "$out" | grep -q '0/3 items done'; then
  ok "a pointer-shaped pack takes its rows from the sibling pre-flight (backtick item lines; the named decoy with no line is passed over; the non-numeric index refused)"
else
  no "run-ptr gave exit $rc: $(printf '%s' "$out" | grep -E '^│ item|overall|warning|PROBE' | head -4 | tr '\n' '|')"
fi

out=$(run_watch --run run-ptr2 --once --plain 2>&1)
rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -qE '^│ item0 +alpha ' && ! printf '%s' "$out" | grep -qE '^│ item1 ' &&
   printf '%s' "$out" | grep -q '0/1 items done'; then
  ok "a pre-flight the pack names by path wins over the sibling (the order test)"
else
  no "run-ptr2 gave exit $rc: $(printf '%s' "$out" | grep -E '^│ item|overall|warning|PROBE' | head -3 | tr '\n' '|')"
fi

out=$(run_watch --run run-expect --once --plain 2>&1)
rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -qE '^│ item0 ' && printf '%s' "$out" | grep -qE '^│ item1 ' &&
   ! printf '%s' "$out" | grep -q 'junk' && printf '%s' "$out" | grep -q '0/2 items done'; then
  ok "with no item line anywhere the run-open's expect_items keys are the rows (unnamed; a non-item key refused)"
else
  no "run-expect gave exit $rc: $(printf '%s' "$out" | grep -E '^│ item|overall|warning|PROBE' | head -3 | tr '\n' '|')"
fi

out=$(run_watch --run run-gateonly --once --plain 2>&1)
rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q 'item1' && printf '%s' "$out" | grep -q 'item2'; then
  ok "gate events without pack items give the gate item ids (the clean case, exit 0)"
else
  no "the gate-only record gave exit $rc"
fi

# ---------------------------------------------------------------- leg 3: rows and states
if grep -qE '^\│ item1 .*done' "$T/vocab.txt" && grep -qE '^\│ item3 .*running' "$T/vocab.txt" &&
   grep -qE '^\│ item4 .*pending' "$T/vocab.txt"; then
  ok "--once --plain shows item1 done, item3 running and item4 pending"
else
  no "the item states are wrong: $(grep -E '^\│ item' "$T/vocab.txt" | tr '\n' '|')"
fi

if grep -q 'turn 3' "$T/vocab.txt"; then
  ok "the header counts the head's turns from the followed transcript (3 assistant records)"
else
  no "the head turn count is wrong: $(grep -m1 'head head-sid' "$T/vocab.txt")"
fi

if grep -q 'context 30 %' "$T/vocab.txt" && grep -q 'session \$3.00' "$T/vocab.txt"; then
  ok "the header carries the last gate's context percent and the metered spend"
else
  no "the header lacks the gate percent or the meter"
fi

if grep -qE '● V-THREE .*2 turns' "$T/vocab.txt" &&
   grep -qE '● V-THREE .*the last tool call of the lane' "$T/vocab.txt"; then
  ok "lanes now shows the running lane's live turn count and last tool call from its transcript"
else
  no "the lanes panel misses the live turns or the last call: $(grep -m1 'V-THREE' "$T/vocab.txt")"
fi

# ---------------------------------------------------------------- leg 4: a resumed lane
item2row=$(grep -E '^\│ item2 ' "$T/vocab.txt")
case $item2row in
  *"●C-TWO"*) resumed=1 ;;
  *) resumed=0 ;;
esac
case $item2row in
  *"✗C-TWO"*) stale=1 ;;
  *) stale=0 ;;
esac
if [ "$resumed" -eq 1 ] && [ "$stale" -eq 0 ]; then
  ok "a lane-resumed lane is drawn running (●), not closed (✗)"
else
  no "the resumed lane is drawn wrong: $item2row"
fi

if grep -qE '^\│ B-ONE .*✓' "$T/vocab.txt" || grep -q '✓B-ONE' "$T/vocab.txt"; then
  ok "a completed lane keeps its ✓ (the clean case beside the resumed one)"
else
  no "the completed lane lost its mark"
fi

# ---------------------------------------------------------------- leg 5: the limit wait
headrow=$(grep -E '^\│ head {3,}' "$T/vocab.txt")
case $headrow in *"░"*) wait_hit=1 ;; *) wait_hit=0 ;; esac
case $headrow in *"↻"*) res_hit=1 ;; *) res_hit=0 ;; esac
case $headrow in *"✖"*) stop_hit=1 ;; *) stop_hit=0 ;; esac
case $headrow in *"│"*) gate_hit=1 ;; *) gate_hit=0 ;; esac
case $headrow in *"▲"*) bnd_hit=1 ;; *) bnd_hit=0 ;; esac
if [ "$wait_hit" -eq 1 ] && [ "$res_hit" -eq 1 ] && [ "$stop_hit" -eq 1 ]; then
  ok "the head row draws the limit wait (░), the stop (✖) and the resume that closes it (↻)"
else
  no "the head row lacks a mark (wait=$wait_hit stop=$stop_hit resume=$res_hit): $headrow"
fi
if [ "$gate_hit" -eq 1 ] && [ "$bnd_hit" -eq 1 ]; then
  ok "the head row draws the gate (│) and the boundary (▲) marks"
else
  no "the head row lacks the gate or the boundary mark: $headrow"
fi

run_watch --run run-nowait --once --plain > "$T/nowait.txt" 2>&1
nowaitrow=$(grep -E '^\│ head {3,}' "$T/nowait.txt")
case $nowaitrow in
  *"░"*) no "a record with no limit stop still drew a wait: $nowaitrow" ;;
  *) ok "a record with no limit stop draws no wait (the negative control)" ;;
esac

# ---------------------------------------------------------------- leg 5b: a wait ended by a successor (2026-09-09)
run_watch --run run-succwait --once --plain > "$T/succwait.txt" 2>&1
succrow=$(grep -E '^\│ head {3,}' "$T/succwait.txt")
case $succrow in *"░"*) sw_wait=1 ;; *) sw_wait=0 ;; esac
case $succrow in *"↻"*) sw_res=1 ;; *) sw_res=0 ;; esac
case ${succrow##*↻} in *"░"*) sw_tail=1 ;; *) sw_tail=0 ;; esac
if [ "$sw_wait" -eq 1 ] && [ "$sw_res" -eq 1 ] && [ "$sw_tail" -eq 0 ]; then
  ok "a limit wait that ends with a successor head closes at the successor: no hatching after the last ↻"
else
  no "the wait ended by a successor runs to the end (wait=$sw_wait resume=$sw_res tail-hatch=$sw_tail): $succrow"
fi

# ---------------------------------------------------------------- leg 5c: a model-scoped limit (2026-09-16)
run_watch --run run-modelwait --once --plain > "$T/modelwait.txt" 2>&1
modelrow=$(grep -E '^\│ head {3,}' "$T/modelwait.txt")
case $modelrow in *"░"*) mw_wait=1 ;; *) mw_wait=0 ;; esac
case ${modelrow##*↻} in *"░"*) mw_tail=1 ;; *) mw_tail=0 ;; esac
if [ "$mw_wait" -eq 1 ] && [ "$mw_tail" -eq 0 ]; then
  ok "a limit-model stop opens the wait like a plain limit and closes it at the successor"
else
  no "a limit-model stop drew no wait or ran it past the successor (wait=$mw_wait tail-hatch=$mw_tail): $modelrow"
fi

# ------------------------------------------------ leg FBW: the owner is told of a fallback (r29)
# The owner's ruling of 2026-09-29: a refused or re-routed task falls back to GPT-6 Astra at the same
# effort rung, and he is told. A re-routed lane closes `completed`, so the console must alert on the
# close's fallback verdict and on the `lane-swapped` line, and the feed must name the verdict, the
# ids and the carried effort. Controls: a clean close (detected false), a close with no usage
# (detected null, no verdict) and a close with no fallback block at all must not alert.
python3 -B - "$WATCH" > "$T/fbw.txt" 2>&1 <<'PY_FBW'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("watch_under_test", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
fb = lambda verdict, ids: {"detected": verdict != "clean", "non_helper": ids, "expected": "claude-opus-5-5",
                           "verdict": None if verdict == "clean" else verdict}
positives = [
    {"event": "lane-closed", "lane": "F1", "exit_class": "completed", "fallback": fb("fallback", ["claude-opus-4-8"])},
    {"event": "lane-closed", "lane": "F2", "exit_class": "completed", "fallback": fb("unconfirmed", ["claude-opus-4-8"])},
    {"event": "lane-closed", "lane": "F3", "exit_class": "completed", "fallback": fb("stale-map", ["claude-opus-5-6"])},
    {"event": "lane-swapped", "lane": "F1", "to": "F1-astra", "ok": True, "effort": "max"},
    {"event": "lane-swapped", "lane": "F4", "to": "F4-astra", "ok": False, "effort": "xhigh", "error": "no codex binary"},
]
negatives = [
    {"event": "lane-closed", "lane": "N1", "exit_class": "completed",
     "fallback": {"detected": False, "non_helper": ["claude-opus-5-5"], "expected": "claude-opus-5-5"}},
    {"event": "lane-closed", "lane": "N2", "exit_class": "completed",
     "fallback": {"detected": None, "non_helper": [], "expected": "claude-opus-5-5", "reason": "no modelUsage on the result"}},
    {"event": "lane-closed", "lane": "N3", "exit_class": "completed"},
]
missed = [e for e in positives if not watch.is_alert(e)]
wrong = [e for e in negatives if watch.is_alert(e)]
print("fbw positives %d missed %d" % (len(positives), len(missed)))
print("fbw negatives %d wrong %d" % (len(negatives), len(wrong)))
print("fbw treated: %s" % ("lane-swapped" in watch.TREATMENT))
print("fbw feed close: %s" % watch.fmt_event(positives[0]))
print("fbw feed swap: %s" % watch.fmt_event(positives[3]))
print("fbw feed failed swap: %s" % watch.fmt_event(positives[4]))
print("fbw feed clean: %s" % watch.fmt_event(negatives[0]))
PY_FBW
if grep -q 'fbw positives 5 missed 0' "$T/fbw.txt" && grep -q 'fbw negatives 3 wrong 0' "$T/fbw.txt" &&
   grep -q 'fbw treated: True' "$T/fbw.txt"; then
  ok "FBW1 a fallback, unconfirmed or stale-map close and every lane-swapped line alert; a clean, an unread and a plain close do not"
else
  no "FBW1 the fallback alert rule is wrong: $(tr '\n' '|' < "$T/fbw.txt")"
fi
if grep -q 'fbw feed close: .*fallback=fallback ran-on=claude-opus-4-8 expected=claude-opus-5-5' "$T/fbw.txt" &&
   grep -q 'fbw feed swap: .*lane-swapped F1 to=F1-astra ok=True effort=max' "$T/fbw.txt" &&
   grep -q 'fbw feed failed swap: .*effort=xhigh error=no codex binary' "$T/fbw.txt"; then
  ok "FBW2 the feed names the verdict, the ids, the successor and the effort carried across the swap"
else
  no "FBW2 the fallback feed line is wrong: $(grep 'fbw feed' "$T/fbw.txt" | tr '\n' '|')"
fi
if grep 'fbw feed clean:' "$T/fbw.txt" | grep -q 'fallback='; then
  no "FBW3 control: a clean close printed a fallback clause"
else
  ok "FBW3 control: a clean close prints no fallback clause"
fi

# ---------------------------------------------------------------- leg 6: alerts
python3 -B - "$WATCH" > "$T/alerts.txt" 2>&1 <<'PY_ALERT'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("watch_under_test", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

positives = [
    {"event": "stop-condition", "which": "limit"},
    {"event": "supervisor-stood-down", "reason": "limit-stop"},
    {"event": "successor-aborted", "reason": "resume-unsized"},
    {"event": "head-exit", "band": "limit"},
    {"event": "run-close", "lanes": "3"},
    {"event": "lane-closed", "lane": "C-TWO", "exit_class": "stall"},
    {"event": "lane-closed", "lane": "C-TWO", "exit_class": "limit"},
]
for word in ("warning: x", "a refusal here", "parked for later", "held back", "reverted the edit",
             "PROBE FAILED: x", "FAIL 3/10"):
    positives.append({"event": "observation", "what": word})
negatives = [
    {"event": "lane-closed", "lane": "B-ONE", "exit_class": "completed"},
    {"event": "observation", "what": "a plain note that carries no alerting word"},
    {"event": "gate", "item": "item1"},
    {"event": "heartbeat", "action": "beat"},
    {"event": "phase-boundary", "from": "item1", "to": "item2"},
]
missed = [e for e in positives if not watch.is_alert(e)]
wrong = [e for e in negatives if watch.is_alert(e)]
print("positives %d missed %d" % (len(positives), len(missed)))
print("negatives %d wrong %d" % (len(negatives), len(wrong)))
# the notification guard, both ways: the suite's environment refuses, and so does --no-notify
print("notify with the environment refusing: %s" % watch.notify("t", "x", True))
print("notify with --no-notify: %s" % watch.notify("t", "x", False))
if missed:
    print("MISSED", missed)
if wrong:
    print("WRONG", wrong)
PY_ALERT
if grep -q 'positives 14 missed 0' "$T/alerts.txt" && grep -q 'negatives 5 wrong 0' "$T/alerts.txt"; then
  ok "every alert kind classifies (14 positives, 0 missed) and 5 non-alerts do not (0 wrong)"
else
  no "the alert classifier is wrong: $(cat "$T/alerts.txt" | tr '\n' '|')"
fi

env LLM_WIKI_STORE="$T/store" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_COLOUR=1 \
    AIMYTH_WATCH_NOTIFY=0 COLUMNS=150 LINES=60 python3 -B "$WATCH" --vault "$T/vault" \
    --run run-vocab --once > "$T/colour.txt" 2>&1
red=$(printf '\033[38;5;196m')
if grep -F "$red" "$T/colour.txt" | grep -q 'a planted premise failure' &&
   ! grep -F "$red" "$T/colour.txt" | grep -q 'no alerting word in it'; then
  ok "the alerting observation is red in the feed and the plain one beside it is not"
else
  no "the feed colouring is wrong: $(grep -c . "$T/colour.txt") lines rendered"
fi

if grep -q 'osascript' "$T/vocab.txt" "$T/colour.txt"; then
  no "an osascript call leaked into a suite run"
else
  ok "no notification path ran in the suite (AIMYTH_WATCH_NOTIFY=0 on every leg)"
fi

if grep -q 'notify with the environment refusing: False' "$T/alerts.txt" &&
   grep -q 'notify with --no-notify: False' "$T/alerts.txt"; then
  ok "the notification is refused by AIMYTH_WATCH_NOTIFY=0 and by --no-notify (no osascript ran)"
else
  no "the notification guard did not hold: $(grep -c notify "$T/alerts.txt") lines"
fi

# ---------------------------------------------------------------- the event vocabulary
python3 -B - "$WATCH" "$T/store/spawn-records/run-vocab-closed.jsonl" > "$T/kinds.txt" 2>&1 <<'PY_VOCAB'
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("watch_under_test", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

kinds = sorted({json.loads(line)["event"] for line in open(sys.argv[2], encoding="utf-8")
                if line.strip()})
missing = [k for k in kinds if k not in watch.TREATMENT]
print("kinds %d missing %d %s" % (len(kinds), len(missing), missing))
print("an invented kind is missing: %s" % ("not-a-real-event" not in watch.TREATMENT))
print("marked %d of them, every mark has a glyph: %s" % (
    len([k for k in kinds if k in watch.MARKS]),
    all(v in watch.MARK_GLYPH for v in watch.MARKS.values())))
PY_VOCAB
kinds=$(sed -n 's/^kinds \([0-9]*\) .*/\1/p' "$T/kinds.txt")
if grep -q ' missing 0 \[\]' "$T/kinds.txt" && [ "${kinds:-0}" -ge 20 ] &&
   grep -q 'an invented kind is missing: True' "$T/kinds.txt"; then
  ok "all $kinds event kinds in the record have a treatment; an invented kind does not (control)"
else
  no "the vocabulary table misses a kind: $(cat "$T/kinds.txt" | tr '\n' '|')"
fi
if grep -qE '^marked [0-9]+ of them, every mark has a glyph: True' "$T/kinds.txt" &&
   ! grep -q '^marked 0 ' "$T/kinds.txt"; then
  ok "$(sed -n 's/^marked \([0-9]*\) .*/\1/p' "$T/kinds.txt") kinds mark the head row and each mark has a glyph"
else
  no "the mark table is inconsistent"
fi

# ---------------------------------------------------------------- terminal size
for w in 90 200; do
  env LLM_WIKI_STORE="$T/store" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 \
      COLUMNS=$w LINES=45 python3 -B "$WATCH" --vault "$T/vault" --run run-vocab --once --plain \
      > "$T/w$w.txt" 2>&1
done
python3 -B -c "
import sys
w90 = max(len(l.rstrip(chr(10))) for l in open(sys.argv[1], encoding='utf-8'))
w200 = max(len(l.rstrip(chr(10))) for l in open(sys.argv[2], encoding='utf-8'))
print('widest at 90: %d · widest at 200: %d' % (w90, w200))
print('within bounds: %s · adaptive: %s' % (w90 <= 90 and w200 <= 200, w90 < w200))
" "$T/w90.txt" "$T/w200.txt" > "$T/widths.txt" 2>&1
if grep -q 'within bounds: True · adaptive: True' "$T/widths.txt"; then
  ok "no line is wider than the terminal and the board follows its width ($(head -1 "$T/widths.txt"))"
else
  no "the width discipline broke: $(cat "$T/widths.txt" | tr '\n' '|')"
fi

run_watch --run run-vocab --once > "$T/notty.txt" 2>&1
if ! grep -q "$(printf '\033')" "$T/notty.txt" && grep -q 'item1' "$T/notty.txt"; then
  ok "--once with a piped stdout prints plain (no escape sequences) without --plain"
else
  no "colour leaked into a piped snapshot"
fi

# ---------------------------------------------------------------- leg 7: the keys
STUB_ARGS="$T/stub-args.txt"
: > "$STUB_ARGS"
env LLM_WIKI_STORE="$T/store" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 \
    STUB_ARGS="$STUB_ARGS" AIMYTH_WATCH_RESUME_CMD="sh $T/bin/stub-resume.sh" \
    python3 -B - "$WATCH" "$T" > "$T/keys.txt" 2>&1 <<'PY_KEYS'
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location("watch_under_test", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
T = sys.argv[2]
vault = os.path.join(T, "vault")
records = os.path.join(T, "store", "spawn-records")

running = watch.Run("run-vocab", os.path.join(records, "run-vocab.jsonl"), vault)
stopped = watch.Run("run-stopped", os.path.join(records, "run-stopped.jsonl"), vault)
print("running head_stopped=%s" % running.head_stopped())
print("stopped head_stopped=%s" % stopped.head_stopped())
quit_r, said = watch.handle_key("r", running)
print("refused quit=%s msg=%s" % (quit_r, " ".join(said)))
quit_r, said = watch.handle_key("r", stopped)
print("fired quit=%s msg=%s" % (quit_r, " ".join(said)))
quit_q, said = watch.handle_key("q", running)
print("quit quit=%s msg=%s" % (quit_q, " ".join(said)))
print("model from a field: %s" % watch.head_model({"event": "head-successor", "model": "fable-x"}))
os.environ.pop("AIMYTH_WATCH_RESUME_CMD", None)          # the unstubbed default, for the next line
print("command: %s" % " ".join(watch.resume_command("run-stopped", "fable")))
PY_KEYS
if grep -q 'refused quit=False msg=head is running' "$T/keys.txt" &&
   grep -q 'running head_stopped=False' "$T/keys.txt"; then
  ok "\`r\` is refused while a head runs and says so"
else
  no "\`r\` was not refused while a head runs: $(grep -m1 refused "$T/keys.txt")"
fi
if grep -q 'fired quit=False msg=resume-head: exit 0' "$T/keys.txt"; then
  ok "\`r\` runs the resume command once the last head event is a stop"
else
  no "\`r\` did not fire after a stop: $(grep -m1 fired "$T/keys.txt")"
fi
if grep -q -- '--run run-stopped --model opus --effort max' "$STUB_ARGS"; then
  ok "the stub was invoked with --run, the fallback model (opus: the record names no head model) and --effort max (AIMYTH_WATCH_RESUME_CMD)"
else
  no "the stub arguments are wrong: $(cat "$STUB_ARGS")"
fi
if [ "$(wc -l < "$STUB_ARGS" | tr -d ' ')" -eq 1 ]; then
  ok "the refused key ran no command (the stub was invoked exactly once)"
else
  no "the stub ran $(wc -l < "$STUB_ARGS") times, wanted 1"
fi
if grep -q 'quit quit=True' "$T/keys.txt" && grep -q 'model from a field: fable-x' "$T/keys.txt"; then
  ok "\`q\` quits and the head model comes from the record when a head event names one"
else
  no "the q key or the model rule is wrong"
fi
if grep -q 'command: .*handsoff.py resume-head --run run-stopped --model fable --effort max' "$T/keys.txt"; then
  ok "the unstubbed command line is handsoff.py resume-head beside this script"
else
  no "the default resume command is wrong: $(grep -m1 command: "$T/keys.txt")"
fi

# ---------------------------------------------------------------- leg 8: the close report
REPORT="$T/store/spawn-records/run-vocab-closed-timeline.txt"
run_watch --run run-vocab-closed --plain --refresh 0.2 < /dev/null > "$T/closed.txt" 2>&1
rc=$?
if [ "$rc" -eq 0 ] && grep -q '■ RUN CLOSED' "$T/closed.txt"; then
  ok "a closed run prints its final board with RUN CLOSED and exits 0"
else
  no "the closed run exited $rc without a RUN CLOSED header"
fi
# the printed path is the store's real path, which under a symlinked temporary root is spelled
# differently from $T: the file name is what the assertion can compare
if grep -q 'timeline report written to .*run-vocab-closed-timeline.txt' "$T/closed.txt" &&
   [ -f "$REPORT" ]; then
  ok "the timeline report is written to the store and its path is printed"
else
  no "no timeline report at $REPORT"
fi
if [ -f "$REPORT" ] &&
   grep -q 'lane · class · model·effort · opened · closed · duration · turns · cost · exit' "$REPORT" &&
   grep -q '^B-ONE · builder · fable·max · ' "$REPORT" && grep -q '^V-THREE · verifier · fable·high · ' "$REPORT"; then
  ok "the report carries the per-lane table with a row per lane"
else
  no "the per-lane table is missing or malformed"
fi
if [ -f "$REPORT" ] && grep -q 'legend: █ item or lane' "$REPORT" && grep -q 'item1' "$REPORT" &&
   ! grep -q "$(printf '\033')" "$REPORT"; then
  ok "the report holds the board and the timeline as plain text (no escape sequences)"
else
  no "the report is not plain text or lacks the board"
fi
if [ -f "$T/store/spawn-records/run-vocab-timeline.txt" ]; then
  no "a snapshot of an open run wrote a report (it must not)"
else
  ok "an open run writes no report (the negative case)"
fi

# ---------------------------------------------------------------- leg 8b: the close's item states and notice
# the close converts nothing: a started item with no completion record reads unresolved and a
# never-started item skipped, the overall line carries the verdict, and a boxed notice follows the
# final board; the open run keeps item4 pending (the control), so the rule fires only at a close
run_watch --run run-vocab-closed --once --plain < /dev/null > "$T/closed-once.txt" 2>&1
if grep -qE '^│ item3 .*unresolved' "$T/closed-once.txt" && grep -qE '^│ item4 .*skipped' "$T/closed-once.txt" &&
   ! grep -qE '^│ item[0-9]+ .*pending' "$T/closed-once.txt"; then
  ok "at the close the item in hand reads unresolved and the item never started reads skipped, none pending"
else
  no "the closed run's item states are wrong: $(grep -E '^│ item' "$T/closed-once.txt" | tr '\n' ' ')"
fi
if grep -q '2/4 items done · 1 unresolved · 1 skipped ■ RUN CLOSED' "$T/closed-once.txt"; then
  ok "the overall line of a closed run counts done and skipped and carries the close mark"
else
  no "the overall line is wrong: $(grep -m1 overall "$T/closed-once.txt")"
fi
if grep -q '■ RUN CLOSED · run-vocab-closed' "$T/closed-once.txt" && grep -q 'lanes 3: ' "$T/closed-once.txt" &&
   grep -q 'timeline report: not written (--once)' "$T/closed-once.txt"; then
  ok "a closed snapshot ends with the boxed RUN CLOSED notice, its lane count and no report claim"
else
  no "the closing notice is missing from the snapshot"
fi
if grep -q '■ RUN CLOSED · run-vocab-closed' "$T/closed.txt" && grep -q 'lanes 3: ' "$T/closed.txt" &&
   ! grep -q "$(printf '\033')" "$T/closed.txt"; then
  ok "the live close prints the boxed notice after the final board, plain under --plain"
else
  no "the live close lacks the boxed notice or carries escapes"
fi
if grep -qE '^│ item4 .*pending' "$T/vocab.txt" && ! grep -q 'RUN CLOSED' "$T/vocab.txt"; then
  ok "the open run still reads item4 pending and shows no close notice (the negative case)"
else
  no "the open run reads a close it never had"
fi

# ---------------------------------------------------------------- PL: the plain-lane-run shape
# A record with lane events and no run-open (the shape lane.py alone writes). Every leg here has
# run-vocab as its control: the same console, the same fixtures, a record that HAS a run-open.
run_watch --run run-plain --once --plain > "$T/plain.txt" 2>"$T/plain.err"
plrc=$?
if [ "$plrc" -eq 0 ] && ! grep -q 'PROBE FAILED' "$T/plain.err"; then
  ok "PL01 a record with no run-open renders (exit 0, no PROBE FAILED); run-vocab is the control"
else
  no "PL01 the plain record exited $plrc: $(head -2 "$T/plain.err")"
fi
if grep -q 'plain lane run · no run-open' "$T/plain.txt"; then
  ok "PL02 the header names the shape: plain lane run · no run-open"
else
  no "PL02 the header reads: $(sed -n 2p "$T/plain.txt")"
fi
if grep -q 'plain lane run · no run-open · lanes 3 · lanes \$3.75 (2 of 3 priced)' "$T/plain.txt"; then
  ok "PL03 the header counts the lanes and sums the spend from the lanes' own costs (2 of 3 priced)"
else
  no "PL03 the header's lanes and spend read: $(sed -n 2p "$T/plain.txt")"
fi
# The mark is matched as an alternation of whole glyphs, never a bracket class: see the locale
# note at the top of this file.
if [ "$(grep -cE '^│ (✓|✗|●) P-(ONE|TWO|THREE) ' "$T/plain.txt")" = "3" ]; then
  ok "PL04 the lanes panel draws one row per lane of the plain record"
else
  no "PL04 the lanes panel drew $(grep -cE '^│ (✓|✗|●) P-' "$T/plain.txt") of 3 rows"
fi
if ! grep -q '├ items ' "$T/plain.txt" && ! grep -qE '^│ item[0-9]' "$T/plain.txt" &&
   grep -q '├ items ' "$T/vocab.txt"; then
  ok "PL05 no items panel on a plain record (the control run-vocab still draws one)"
else
  no "PL05 the plain record drew an items panel or the control drew none"
fi
if grep -q '├ timeline ' "$T/plain.txt" && grep -qE '^│ P-ONE +(█|✓)' "$T/plain.txt" &&
   ! grep -qE '^│ head +' "$T/plain.txt" && grep -qE '^│ head +' "$T/vocab.txt"; then
  ok "PL06 the timeline has the lane rows and no head row (the control has one)"
else
  no "PL06 the plain timeline is wrong: $(grep -cE '^│ head ' "$T/plain.txt") head rows"
fi
if grep -q '├ feed ' "$T/plain.txt" && grep -q 'RECORD  lane-closed P-TWO' "$T/plain.txt"; then
  ok "PL07 the feed carries the record's lane events"
else
  no "PL07 the feed is missing the plain record's lane events"
fi

# ------------------------------------------------- LV: an open lane whose processes have gone
# The console probes the recorded pid of every open lane, so a lane killed by hand — which
# writes no lane-closed at all — is drawn dead instead of running for ever. Each leg's control
# is another lane of the SAME record, rendered by the same run of the same console: only the
# pids differ between them, so a wrong verdict cannot be blamed on the fixture's shape.
run_watch --run run-liveness --once --plain > "$T/liveness.txt" 2>"$T/liveness.err"
lvrc=$?
if [ "$lvrc" -eq 0 ] && ! grep -q 'PROBE FAILED' "$T/liveness.err"; then
  ok "LV00 the liveness record renders (exit 0, no PROBE FAILED)"
else
  no "LV00 the liveness record exited $lvrc: $(head -2 "$T/liveness.err")"
fi
if [ "$(grep -cE '^│ ✗ L-DEAD .* dead · no close event' "$T/liveness.txt")" = "1" ]; then
  ok "LV01 an open lane whose recorded processes have gone is drawn ✗ dead · no close event"
else
  no "LV01 the killed lane's row reads: $(grep -E '^│ . L-DEAD ' "$T/liveness.txt" | head -1)"
fi
if [ "$(grep -cE '^│ ● L-DEAD ' "$T/liveness.txt")" = "0" ]; then
  ok "LV02 and it is not drawn ● running (the state the defect showed for ever)"
else
  no "LV02 the killed lane is still drawn running"
fi
if [ "$(grep -cE '^│ ● L-LIVE ' "$T/liveness.txt")" = "1" ]; then
  ok "LV03 the clean case: a lane whose recorded pid is this suite's own shell still reads ● running"
else
  no "LV03 the live lane's row reads: $(grep -E '^│ . L-LIVE ' "$T/liveness.txt" | head -1)"
fi
if [ "$(grep -cE '^│ ● L-MIXED ' "$T/liveness.txt")" = "1" ]; then
  ok "LV04 a lane with one gone pid and one live one still reads running (only all-gone is dead)"
else
  no "LV04 the mixed lane's row reads: $(grep -E '^│ . L-MIXED ' "$T/liveness.txt" | head -1)"
fi
if [ "$(grep -cE '^│ ● L-NOPID ' "$T/liveness.txt")" = "1" ]; then
  ok "LV05 an open lane whose spawn recorded no pid stays running (an absence is not a death)"
else
  no "LV05 the pid-less lane's row reads: $(grep -E '^│ . L-NOPID ' "$T/liveness.txt" | head -1)"
fi
# ------------------------------------------------- MC: the lanes-now model cell
run_watch --run run-modelcell --once --plain > "$T/modelcell.txt" 2>"$T/modelcell.err"
mcrc=$?
if [ "$mcrc" -eq 0 ] && ! grep -q 'PROBE FAILED' "$T/modelcell.err"; then
  ok "MC00 the model-cell record renders (exit 0, no PROBE FAILED)"
else
  no "MC00 the model-cell record exited $mcrc: $(head -2 "$T/modelcell.err")"
fi
if grep -qE '^. . M-ASTRA .* astra·ultra ' "$T/modelcell.txt" &&
   ! grep -q 'gpt-6-astr…' "$T/modelcell.txt"; then
  ok "MC01 a long vendor name is shortened to its own last segment: astra·ultra, never gpt-6-astr…"
else
  no "MC01 the astra row reads: $(grep -E '^. . M-ASTRA ' "$T/modelcell.txt" | head -1)"
fi
if grep -qE '^. . M-REASON .* opus·max ' "$T/modelcell.txt" &&
   ! grep -q 'max (definition' "$T/modelcell.txt"; then
  ok "MC02 an effort recorded with its reason shows the value alone: opus·max"
else
  no "MC02 the reason-carrying row reads: $(grep -E '^. . M-REASON ' "$T/modelcell.txt" | head -1)"
fi
if grep -qE '^. . M-PLAIN .* fable·max ' "$T/modelcell.txt"; then
  ok "MC03 the control: a pair that already fitted is printed unchanged (fable·max)"
else
  no "MC03 the control row reads: $(grep -E '^. . M-PLAIN ' "$T/modelcell.txt" | head -1)"
fi
if grep -qE '^. . M-LONG .* opus[^ ]*·xhigh ' "$T/modelcell.txt"; then
  ok "MC04 a name too long even shortened is cut, and the effort still survives whole (…·xhigh)"
else
  no "MC04 the over-long row reads: $(grep -E '^. . M-LONG ' "$T/modelcell.txt" | head -1)"
fi
if [ "$(grep -cE '·(ultr|xhig|ma|hig)…' "$T/modelcell.txt")" = "0" ] &&
   [ "$(printf 'x·ma…\n' | grep -cE '·(ultr|xhig|ma|hig)…')" = "1" ]; then
  ok "MC05 no row anywhere carries a cut effort; the probe hits its planted control"
else
  no "MC05 a cut effort is on screen, or the probe matched nothing: $(grep -oE '·[a-z]*…' "$T/modelcell.txt" | head -1)"
fi

run_watch --run run-liveness-closed --once --plain > "$T/liveness-closed.txt" 2>&1
if grep -q 'lanes 4: ' "$T/liveness-closed.txt" && grep -q '1 dead' "$T/liveness-closed.txt" &&
   grep -q '3 running' "$T/liveness-closed.txt"; then
  ok "LV06 the close banner counts the dead lane as dead: lanes 4, 3 running, 1 dead"
else
  no "LV06 the banner's counts read: $(grep -o 'lanes 4: .*' "$T/liveness-closed.txt" | head -1)"
fi

# LC01: the same snapshot with the locale emptied — LANG, LC_ALL and LC_CTYPE all unset, the
# shell the defect shows under. The console must render the same three lane rows, and the
# probe must still read them: both halves of the locale fix are under test here, the exported
# LC_ALL above (which `env -u` removes for this leg) and the glyph alternation in the pattern.
# The control is PL04 above: the same assertion on the same fixture under the suite's locale.
env -u LANG -u LC_ALL -u LC_CTYPE LLM_WIKI_STORE="$T/store" AIMYTH_PROJECTS_DIR="$T/projects" \
    AIMYTH_WATCH_NOTIFY=0 COLUMNS=150 LINES=60 \
    python3 -B "$WATCH" --vault "$T/vault" --run run-plain --once --plain \
    > "$T/plain-nolocale.txt" 2>"$T/plain-nolocale.err"
lcrc=$?
lcrows=$(grep -cE '^│ (✓|✗|●) P-(ONE|TWO|THREE) ' "$T/plain-nolocale.txt")
if [ "$lcrc" -eq 0 ] && [ "$lcrows" = "3" ] && ! grep -q 'PROBE FAILED' "$T/plain-nolocale.err"; then
  ok "LC01 the console renders its three lane rows with LANG, LC_ALL and LC_CTYPE unset (PL04 is the control)"
else
  no "LC01 under an emptied locale the console exited $lcrc and drew $lcrows of 3 lane rows"
fi
# LC02: the negative control for LC01's probe — the pattern is not matching everything. The
# same grep over the same file with a lane name that is not in the record must read 0.
if [ "$(grep -cE '^│ (✓|✗|●) P-(FOUR|FIVE) ' "$T/plain-nolocale.txt")" = "0" ]; then
  ok "LC02 the same glyph-alternation probe reads 0 for a lane the record does not carry"
else
  no "LC02 the glyph-alternation probe matched a lane that is not in the record"
fi
PLREPORT="$T/store/spawn-records/run-plain-closed-timeline.txt"
run_watch --run run-plain-closed --plain --refresh 0.2 < /dev/null > "$T/plain-closed.txt" 2>&1
plcrc=$?
if [ "$plcrc" -eq 0 ] && grep -q '■ RUN CLOSED · run-plain-closed' "$T/plain-closed.txt" &&
   grep -q 'lanes 3: ' "$T/plain-closed.txt"; then
  ok "PL08 a closed plain record prints the boxed notice with its lane counts and exits 0"
else
  no "PL08 the closed plain run exited $plcrc without its boxed notice"
fi
if [ -f "$PLREPORT" ] && grep -q 'timeline report written to .*run-plain-closed-timeline.txt' "$T/plain-closed.txt" &&
   grep -q '^P-ONE · builder · fable·max · ' "$PLREPORT"; then
  ok "PL09 the close writes the timeline report for a plain record too, with its per-lane table"
else
  no "PL09 no timeline report at $PLREPORT"
fi
if grep -q 'plain lane run · no run-open' "$T/plain-closed.txt" &&
   ! grep -q '0/0 items done' "$T/plain-closed.txt"; then
  ok "PL10 the close's notice says the shape rather than claiming 0/0 items done"
else
  no "PL10 the closing notice reads: $(grep -m1 'closed ' "$T/plain-closed.txt")"
fi
run_watch --run run-plain-empty --once --plain > "$T/plain-empty.txt" 2>&1
plerc=$?
if [ "$plerc" -eq 2 ] && grep -q 'PROBE FAILED' "$T/plain-empty.txt" &&
   grep -q 'no run-open, no lane-open and no lane-closed event' "$T/plain-empty.txt"; then
  ok "PL11 a record with neither a run-open nor a lane event is still a premise failure (exit 2)"
else
  no "PL11 the empty plain record exited $plerc: $(head -1 "$T/plain-empty.txt")"
fi
# PL12 would repeat leg 2 (the no-items premise on a record that HAS a run-open): that leg is the
# narrowing's own control and runs above, unchanged.

# ---------------------------------------------------------------- JB: the session view (A4)
# One row per background job of an attended session, from the transcript and the job directory.
# Each kind, each state, each notification carrier and each premise failure is a separate plant of
# the same probe, so a view that emitted one constant could not pass them all.
JB="$T/jobs-one.txt"
run_jobs --session jobs-one-aaa --once --plain > "$JB" 2>"$T/jobs-one.err"
jbrc=$?
jbrow() { grep -E "^│ $1 +$2 " "$JB"; }   # the row for kind $1 and job id $2

if [ "$jbrc" -eq 0 ] && [ -s "$JB" ]; then
  ok "JB01a the session view renders a snapshot from the transcript and the job directory (exit 0)"
else
  no "JB01a the session snapshot exited $jbrc: $(head -3 "$T/jobs-one.err")"
fi
if grep -q '^│ session jobs-one-aaa · jobs 8 ' "$JB"; then
  ok "JB01b the header names the session and counts its eight jobs"
else
  no "JB01b the header reads: $(grep -m1 '│ session' "$JB")"
fi
if grep -qE '^│ session .* · suite 2 · lane 1 · waiter 1 · agent 2 · other 2' "$JB"; then
  ok "JB01c the header counts by kind, in the fixed kind order"
else
  no "JB01c the kind counts read: $(grep -m1 '│ session' "$JB")"
fi
if grep -q '^│ state: notifications' "$JB"; then
  ok "JB01d the header names notifications as the source of the state"
else
  no "JB01d the state source reads: $(grep -m1 'state:' "$JB")"
fi

# JB02 the kinds. Each is decided by a different observable: the command for the suites, the lane
# and the waiter-by-sleep, the tool for the Monitor and Agent jobs, the file for the symlink.
if [ -n "$(jbrow suite jsuiteb)" ] && [ -n "$(jbrow suite jsuitea)" ]; then
  ok "JB02a a command naming a test_*.sh file is kind suite"
else
  no "JB02a the suite rows are missing: $(grep -c '^│ suite' "$JB") found"
fi
if [ -n "$(jbrow lane jlane)" ]; then
  ok "JB02b a lane.py watch command is kind lane — and it was started by the MOVED shape, with no run_in_background on the tool call"
else
  no "JB02b the lane row is missing (the moved-to-background start was not read)"
fi
if [ -n "$(jbrow waiter jwaiter)" ]; then
  ok "JB02c the Monitor tool is kind waiter, decided by the tool and not by its command"
else
  no "JB02c the waiter row is missing"
fi
if [ -n "$(jbrow agent abcdef0123456789a)" ]; then
  ok "JB02d the Agent tool is kind agent, its id read from the agentId line"
else
  no "JB02d the agent row is missing"
fi
if [ -n "$(jbrow agent jlink)" ]; then
  ok "JB02e a symlinked .output makes a job kind agent whatever its command said (the file decides)"
else
  no "JB02e the symlinked job did not read as an agent: $(jbrow other jlink)"
fi
if [ -n "$(jbrow other jother)" ] && [ -n "$(jbrow other jlost)" ]; then
  ok "JB02f a command matching no rule is kind other"
else
  no "JB02f the other rows are missing"
fi

# JB03 the states, one per notification carrier and one per absence
if jbrow suite jsuiteb | grep -q ' done '; then
  ok "JB03a a completed notification in a queue-operation record reads done"
else
  no "JB03a jsuiteb reads: $(jbrow suite jsuiteb)"
fi
if jbrow suite jsuitea | grep -q ' done '; then
  ok "JB03b a completed notification in an attachment record reads done (the carrier a user-record scan misses)"
else
  no "JB03b jsuitea reads: $(jbrow suite jsuitea)"
fi
if jbrow other jother | grep -q ' stopped '; then
  ok "JB03c a notified status that is not completed reads stopped (carried by a user record)"
else
  no "JB03c jother reads: $(jbrow other jother)"
fi
if jbrow waiter jwaiter | grep -q ' running '; then
  ok "JB03d no notification and an output file reads running"
else
  no "JB03d jwaiter reads: $(jbrow waiter jwaiter)"
fi
if jbrow other jlost | grep -q ' lost '; then
  ok "JB03e no notification and no output file reads lost"
else
  no "JB03e jlost reads: $(jbrow other jlost)"
fi

# JB04 the decoy: an output file with no start record is not a job
if ! grep -q 'norecord1' "$JB"; then
  ok "JB04a the .output with no start record is not a row (the no-record decoy)"
else
  no "JB04a the decoy was drawn as a job: $(grep norecord1 "$JB")"
fi
if grep -q '· 1 no record' "$JB"; then
  ok "JB04b the header counts that file as one no record, so it is reported rather than hidden"
else
  no "JB04b the no-record count is missing from the header"
fi

# JB05 the denominators
if jbrow suite jsuiteb | grep -qE '█+.* 12/12'; then
  ok "JB05a a suite whose output announced PASS 12/12 draws a bar against that total"
else
  no "JB05a jsuiteb's bar reads: $(jbrow suite jsuiteb)"
fi
if jbrow suite jsuitea | grep -q 'no denominator'; then
  ok "JB05b a suite with no announced total and nothing cached says no denominator"
else
  no "JB05b jsuitea's bar reads: $(jbrow suite jsuitea)"
fi
if jbrow lane jlane | grep -qE '█+.* 4/10 turns'; then
  ok "JB05c a lane job counts its lane's live turns against the max_turns its lane-open recorded"
else
  no "JB05c the lane bar reads: $(jbrow lane jlane)"
fi
for k in waiter:jwaiter agent:abcdef0123456789a other:jother; do
  kk=${k%%:*}; ii=${k##*:}
  if jbrow "$kk" "$ii" | grep -q 'no denominator'; then
    ok "JB05d a $kk has no observable denominator and says so"
  else
    no "JB05d the $kk row claims a denominator: $(jbrow "$kk" "$ii")"
  fi
done

# JB06 the cache: the view's one write, and the bar it buys on the next run
if [ -f "$T/state/watch-suite-totals.json" ] &&
   grep -q '"test_beta.sh": 12' "$T/state/watch-suite-totals.json"; then
  ok "JB06a the run cached test_beta.sh's total under the state directory (the view's only write)"
else
  no "JB06a the totals cache reads: $(cat "$T/state/watch-suite-totals.json" 2>&1 | tr '\n' ' ')"
fi
python3 -B - "$T/state/watch-suite-totals.json" <<'SEED_END'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["test_alpha.sh"] = 9
json.dump(d, open(sys.argv[1], "w", encoding="utf-8"), indent=1, sort_keys=True)
SEED_END
run_jobs --session jobs-one-aaa --once --plain > "$T/jobs-cached.txt" 2>&1
if grep -E '^│ suite +jsuitea ' "$T/jobs-cached.txt" | grep -qE '█+.* 3/9'; then
  ok "JB06b with a cached total the same suite draws 3/9 from its ok lines (the cache is the denominator)"
else
  no "JB06b the cached suite row reads: $(grep -E '^│ suite +jsuitea ' "$T/jobs-cached.txt")"
fi

# JB07 the by-mtime fallback: a torn record after the start records
run_jobs --session mtime-three-ccc --once --plain > "$T/jobs-mtime.txt" 2>&1
if grep -q '^│ state: by mtime' "$T/jobs-mtime.txt"; then
  ok "JB07a a record that will not parse after a start record moves the state source to by mtime"
else
  no "JB07a the state source reads: $(grep -m1 'state:' "$T/jobs-mtime.txt")"
fi
if grep -E '^│ other +mrun ' "$T/jobs-mtime.txt" | grep -q ' running ' &&
   grep -E '^│ other +mdone ' "$T/jobs-mtime.txt" | grep -q ' done '; then
  ok "JB07b under the fallback the file written since the transcript's last record reads running, the older one done"
else
  no "JB07b the by-mtime states read: $(grep -E '^│ other ' "$T/jobs-mtime.txt" | tr '\n' '|')"
fi

# JB08 the prefix resolution, exactly as fable-share.py resolves one
run_jobs --session jobs-one --once --plain > "$T/jobs-prefix.txt" 2>&1
if grep -q '^│ session jobs-one-aaa ' "$T/jobs-prefix.txt"; then
  ok "JB08a a prefix naming exactly one transcript resolves to its full stem"
else
  no "JB08a the prefix resolved to: $(grep -m1 'session' "$T/jobs-prefix.txt")"
fi
run_jobs --session jobs- --once --plain > "$T/jobs-two.txt" 2>&1
if [ $? -eq 2 ] && grep -q 'PROBE FAILED: 2 sessions match jobs-' "$T/jobs-two.txt"; then
  ok "JB08b a prefix matching two transcripts fails with the count, never a guess between them"
else
  no "JB08b the ambiguous prefix said: $(head -1 "$T/jobs-two.txt")"
fi
run_jobs --session zzznosuch --once --plain > "$T/jobs-zero.txt" 2>&1
if [ $? -eq 2 ] && grep -q 'PROBE FAILED: no transcript for zzznosuch' "$T/jobs-zero.txt"; then
  ok "JB08c a prefix matching no transcript is a premise failure with exit 2"
else
  no "JB08c the missing prefix said: $(head -1 "$T/jobs-zero.txt")"
fi

# JB09 the premise cases
run_jobs --session jobs-two-bbb --once --plain > "$T/jobs-none.txt" 2>&1
if [ $? -eq 0 ] && grep -q '^no background jobs$' "$T/jobs-none.txt"; then
  ok "JB09a a transcript with no background record is a legitimate state: no background jobs, exit 0"
else
  no "JB09a the empty session said: $(head -2 "$T/jobs-none.txt")"
fi
chmod 000 "$TASKS/jobs-one-aaa/tasks"
run_jobs --session jobs-one-aaa --once --plain > "$T/jobs-noroot.txt" 2>&1
noroot=$?
chmod 755 "$TASKS/jobs-one-aaa/tasks"
if [ "$noroot" -eq 0 ] && grep -q 'output: unreadable' "$T/jobs-noroot.txt" &&
   [ "$(grep -c 'output: unreadable' "$T/jobs-noroot.txt")" -ge 8 ]; then
  ok "JB09b an unreadable job root still draws every row from the transcript, each marked output: unreadable (exit 0)"
else
  no "JB09b the unreadable root gave exit $noroot and $(grep -c 'output: unreadable' "$T/jobs-noroot.txt") marked rows"
fi
if run_jobs --once --plain > "$T/jobs-neither.txt" 2>&1; then
  no "JB09c the console ran with neither --run nor --session"
else
  ok "JB09c --run and --session are mutually exclusive and one is required"
fi
if run_jobs --run run-vocab --session jobs-one-aaa --once --plain > "$T/jobs-both.txt" 2>&1; then
  no "JB09d the console accepted --run and --session together"
else
  ok "JB09d passing both --run and --session is refused"
fi

# JB10 the run console is untouched by the session view: an existing snapshot re-asserted after
# every session run above. The header carries a wall clock, so the assertion is leg 8b's own —
# the item rows and the absence of a close — rather than a byte comparison that time would break.
run_watch --run run-vocab --once --plain > "$T/vocab-again.txt" 2>&1
jb10rc=$?
if [ "$jb10rc" -eq 0 ] && grep -qE '^│ item4 .*pending' "$T/vocab-again.txt" &&
   ! grep -q 'RUN CLOSED' "$T/vocab-again.txt" &&
   [ "$(grep -cE '^│ item[0-9]' "$T/vocab-again.txt")" = "$(grep -cE '^│ item[0-9]' "$T/vocab.txt")" ]; then
  ok "JB10 the --run path still renders leg 8b's snapshot after every session run (same item rows, still open)"
else
  no "JB10 the run console changed: exit $jb10rc, $(grep -cE '^│ item[0-9]' "$T/vocab-again.txt") item rows"
fi

# JB11 the start rule and the quoted script paths (session four). A start is a tool_result whose
# text BEGINS with a start sentence and whose tool_use_id resolves to a tool_use of this
# transcript; the same sentence anywhere else is a mention. `dtrue` is the control on the same
# session: if the reader stopped seeing starts altogether, it would fail with the decoys.
JB4="$T/jobs-four.txt"
run_jobs --session decoy-four-ddd --once --plain > "$JB4" 2>&1
jb4rc=$?
jb4row() { grep -E "^│ $1 +$2 " "$JB4"; }
if [ "$jb4rc" -eq 0 ] && jb4row other dtrue > /dev/null; then
  ok "JB11a the control: a true start on this session is a row (exit 0)"
else
  no "JB11a the control start is missing: exit $jb4rc, $(grep -c '^│' "$JB4") rows"
fi
if ! grep -q 'dphantom1' "$JB4"; then
  ok "JB11b the start sentence inside assistant prose is not a start (no row)"
else
  no "JB11b prose put a phantom row on the board: $(grep dphantom1 "$JB4")"
fi
if ! grep -q 'dphantom2' "$JB4"; then
  ok "JB11c the start sentence inside another tool's output is not a start (the live phantom's shape)"
else
  no "JB11c another tool's output put a phantom row on the board: $(grep dphantom2 "$JB4")"
fi
if ! grep -q 'dorphan' "$JB4"; then
  ok "JB11d a result whose tool_use_id resolves to no tool_use is not a start"
else
  no "JB11d an unresolved tool_result became a row: $(grep dorphan "$JB4")"
fi
if [ "$(grep -cE '^│ (suite|lane|waiter|agent|other) +d' "$JB4")" = "4" ]; then
  ok "JB11e session four has exactly its four true starts, the three decoys counted out"
else
  no "JB11e session four drew $(grep -cE '^│ (suite|lane|waiter|agent|other) +d' "$JB4") rows, wanted 4"
fi
if jb4row lane dqlane > /dev/null; then
  ok "JB11f a lane.py command whose script path is QUOTED is kind lane"
else
  no "JB11f the quoted lane command reads: $(grep dqlane "$JB4")"
fi
if jb4row waiter dqwatch > /dev/null; then
  ok "JB11g a quoted watch.py --run command is kind waiter"
else
  no "JB11g the quoted run console reads: $(grep dqwatch "$JB4")"
fi
if jb4row waiter dqhandsoff > /dev/null; then
  ok "JB11h a quoted handsoff.py watch command is kind waiter"
else
  no "JB11h the quoted handsoff console reads: $(grep dqhandsoff "$JB4")"
fi

# ---------------------------------------------------------------- leg 8c: the close's tone
# under colour the close mark on the head row, the header's RUN CLOSED, the overall line and the
# banner take the close's tone: bold green when every item is done, bold yellow when the close
# skipped an item (the planted contrast: run-vocab-closed's item4); leg 8 holds the plain control.
# The contrast negates only the close's own spans (a mark, a RUN CLOSED), since a completed lane's
# ✓ in the lanes panel is bold green by right. Fixed-string greps: the sequences carry `[`, which a
# regex would read as a bracket expression.
G=$(printf '\033[1m\033[38;5;40m')
Y=$(printf '\033[1m\033[38;5;220m')
R0=$(printf '\033[0m')
( export AIMYTH_WATCH_COLOUR=1; run_watch --run run-vocab-alldone --once < /dev/null > "$T/alldone-colour.txt" 2>&1 )
( export AIMYTH_WATCH_COLOUR=1; run_watch --run run-vocab-closed --once < /dev/null > "$T/skipped-colour.txt" 2>&1 )
if grep -q '4/4 items done · all done' "$T/alldone-colour.txt" && grep -qF "${G}  ■ RUN CLOSED${R0}" "$T/alldone-colour.txt" &&
   grep head "$T/alldone-colour.txt" | grep -qF "${G}■${R0}" && grep -qF "${G} ■ RUN CLOSED · run-vocab-alldone" "$T/alldone-colour.txt" &&
   grep -qF "${G} 4/4 items done · all done ■ RUN CLOSED${R0}" "$T/alldone-colour.txt"; then
  ok "an all-done close paints the head row's mark, the header, the overall line and the banner bold green"
else
  no "the all-done close is not bold green throughout: $(grep -cF "$G" "$T/alldone-colour.txt") bold-green spans"
fi
if grep -qF "${Y}  ■ RUN CLOSED${R0}" "$T/skipped-colour.txt" && grep head "$T/skipped-colour.txt" | grep -qF "${Y}■${R0}" &&
   grep -qF "${Y} ■ RUN CLOSED · run-vocab-closed" "$T/skipped-colour.txt" &&
   ! grep -F "$G" "$T/skipped-colour.txt" | grep -q '■'; then
  ok "a close that skipped an item paints them bold yellow and no close span bold green (the contrast)"
else
  no "the skipped close's tone is wrong: bold green $(grep -cF "$G" "$T/skipped-colour.txt") · bold yellow $(grep -cF "$Y" "$T/skipped-colour.txt")"
fi

# ---------------------------------------------------------------- leg 8d: the title names the run's shape
if grep -q 'run console · run-plain-closed' "$T/plain-closed.txt" && grep -q 'hands-off console · run-vocab-closed' "$T/closed.txt" &&
   ! grep -q 'hands-off console · run-plain-closed' "$T/plain-closed.txt"; then
  ok "a plain lane run is titled run console, a hands-off run hands-off console (the contrast)"
else
  no "the console title does not follow the run's shape: $(grep -o '[a-z-]* console · run-[a-z-]*' "$T/plain-closed.txt" "$T/closed.txt" | sort -u | tr '\n' ' ')"
fi

# ---------------------------------------------------------------- KF: the recovery legs
# Their fixtures live in a store of their own ($T/kstore), outside the manifest the write-proof legs
# compare, so the two sanctioned timeline reports stay the only files that appear in $T/store.
KS="$T/kstore"
mkdir -p "$KS/spawn-records" "$T/khandoffs"
python3 -B - "$T" "$LIVE_PID" "$REAPED_PID" <<'PY_KIFIX'
import json
import os
import sys
import time

T, LIVE, REAPED = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
REC = os.path.join(T, "kstore", "spawn-records")
HANDOFFS = os.path.join(T, "khandoffs")
t0 = time.time() - 90 * 60


def ts(mins):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0 + mins * 60))


def ev(mins, kind, **fields):
    payload = {"ts": ts(mins), "event": kind}
    payload.update(fields)
    return payload


def write(run, rows):
    with open(os.path.join(REC, run + ".jsonl"), "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row, run=run), ensure_ascii=False) + "\n")


def lane(mins, name, pid):
    return [ev(mins, "lane-open", lane=name, model="opus", effort="xhigh", session_id="sid-" + name,
               reason="(a) a kifix fixture lane", **{"class": "builder"}),
            ev(mins, "lane-spawned", lane=name, session_id="sid-" + name, pid=pid, wrapper_pid=pid,
               **{"class": "builder"})]


nine = os.path.join(HANDOFFS, "nine.md")
names = ["N148 · build+install", "N145 · build+critic+install", "N146 · repair+gather",
         "N144 · build+critic+install", "N149 · build", "N150 · verify", "N151 · build",
         "N152 · verify+close", "close-out"]
with open(nine, "w", encoding="utf-8") as fh:
    fh.write("# a nine-item pack (fixture)\n\n## Resume prompt\n\n")
    for k, name in enumerate(names, 1):
        fh.write("item%d %s — fixture item %d\n" % (k, name, k))
two = os.path.join(HANDOFFS, "two.md")
with open(two, "w", encoding="utf-8") as fh:
    fh.write("# a two-item pack (fixture)\n\n## Resume prompt\n\n"
             "item1 N1 · build — the first\nitem2 N1 · verify — the second\n")

# IK: the pack's long grammar in the gate and the boundary (register 2026-09-09 11:21)
opener = ev(0, "run-open", session="k-head-1", handoff=nine, regime="multi")
write("run-ik-gate", [opener, ev(1, "gate", item="item1 N148 · build+install", percent=5)]
      + lane(2, "IK-A", LIVE))
write("run-ik-bnd", [opener, ev(1, "gate", item="item1 N148 · build+install", percent=5),
                     ev(20, "phase-boundary", **{"from": "item1 N148 · build+install",
                                                 "to": "item2 N145 · build+critic+install"}),
                     ev(21, "gate", item="item2 N145 · build+critic+install", percent=9)])

# RS: a lane resumed under a later item is in the running set (register 2026-09-13 03:44)
rs = ([ev(0, "run-open", session="k-head-1", handoff=two, regime="multi"),
       ev(1, "gate", item="item1", percent=5)] + lane(2, "RS-A", LIVE)
      + [ev(10, "lane-closed", lane="RS-A", exit_class="completed", total_cost_usd=1.0,
            session_id="sid-RS-A"),
         ev(11, "phase-boundary", **{"from": "item1", "to": "item2"}),
         ev(12, "gate", item="item2", percent=9)] + lane(13, "RS-B", LIVE)
      + [ev(20, "lane-closed", lane="RS-B", exit_class="completed", total_cost_usd=1.0,
            session_id="sid-RS-B")])
resumed = ev(30, "lane-resumed", lane="RS-A", session_id="sid-RS-A", wrapper_pid=LIVE, resume_n=1)
write("run-rs", rs + [resumed])
write("run-rs-closed-again", rs + [resumed, ev(40, "lane-closed", lane="RS-A", exit_class="completed",
                                               total_cost_usd=0.5, session_id="sid-RS-A")])
# the respawn shape: a pid-less lane-resumed, then a lane-respawned naming a pid that has gone
write("run-rs-respawn", rs + [ev(30, "lane-resumed", lane="RS-A", session_id="sid-RS-A", resume_n=1),
                              ev(30, "lane-respawned", lane="RS-A", session_id="sid-RS-A",
                                 pid=REAPED, wrapper_pid=REAPED)])

# HM: the header's model and effort come from the latest head start alone (register 2026-09-10 20:29)
hm = [ev(0, "run-open", session="k-head-1", handoff=two, regime="multi"),
      ev(0, "head-successor", session_id="k-head-2", pid=REAPED, model="opus", effort="max"),
      ev(1, "gate", item="item1", percent=5)]
write("run-hm", hm)
write("run-hm-later", hm + [ev(5, "head-resumed", session_id="k-head-2", pid=REAPED)])
write("run-hm-none", [e for e in hm if e["event"] != "head-successor"])

# F4: the console marks a never-run item done at the close (register 2026-09-17 12:51). A
# six-item pack; items 0 to 2 gated and worked; the closing boundary names item3 as the bare
# next item and the run-close says which items opened. item3's only start is that boundary,
# item4 and item5 never started: all three read skipped, never done, and draw no elapsed time.
six = os.path.join(HANDOFFS, "six.md")
with open(six, "w", encoding="utf-8") as fh:
    fh.write("# a six-item pack (fixture)\n\n## Resume prompt\n\n")
    for k in range(6):
        fh.write("item%d N%d · build — fixture item %d\n" % (k, k, k))
CLOSE_ITEMS = ("3 of 6 opened (items 0 to 2); items 3 and 5 never opened; the two reports of "
               "item4 written at the close-out")
f4 = ([ev(0, "run-open", session="k-head-1", handoff=six, regime="multi"),
       ev(1, "gate", item="item0", percent=3),
       ev(10, "phase-boundary", **{"from": "item0", "to": "item1"}),
       ev(11, "gate", item="item1", percent=8)] + lane(12, "F4-A", REAPED)
      + [ev(20, "lane-closed", lane="F4-A", exit_class="completed", total_cost_usd=1.0,
            session_id="sid-F4-A"),
         ev(21, "phase-boundary", **{"from": "item1", "to": "item2"}),
         ev(22, "gate", item="item2", percent=12),
         ev(23, "observation", phase="item2", what="a finding of item2", note="evidence: fixture"),
         ev(30, "phase-boundary", **{"from": "item2", "to": "item3"})])
write("run-f4-open", f4)                                   # still open: item3 reads running
write("run-f4-close", f4 + [ev(31, "run-close", items=CLOSE_ITEMS, lanes=1)])
# must not fire: the boundary's target then worked — a gate, a lane, or a ledger event with
# its phase — still reads done at the close
write("run-f4-gated", f4 + [ev(31, "gate", item="item3", percent=13),
                            ev(40, "run-close", items="4 of 6 opened", lanes=1)])
write("run-f4-laned", f4 + lane(31, "F4-B", REAPED)
      + [ev(35, "lane-closed", lane="F4-B", exit_class="completed", total_cost_usd=1.0,
            session_id="sid-F4-B"),
         ev(40, "run-close", items="4 of 6 opened", lanes=2)])
write("run-f4-phased", f4 + [ev(31, "observation", phase="item3", what="the abstract drafted",
                               note="evidence: fixture"),
                             ev(40, "run-close", items="4 of 6 opened", lanes=1)])
# premise cases: a run-close with no items field; a record with no boundary at all; the
# boundary's item strings in the pack grammar
write("run-f4-noitems", f4 + [ev(31, "run-close", lanes=1)])
write("run-f4-nobnd", [ev(0, "run-open", session="k-head-1", handoff=six, regime="multi"),
                       ev(1, "gate", item="item0", percent=3),
                       ev(5, "run-close", items="1 of 6 opened", lanes=0)])
write("run-f4-long", f4[:-1] + [ev(30, "phase-boundary", **{"from": "item2 N2 · build",
                                                            "to": "item3 N3 · build"}),
                                ev(31, "run-close", items=CLOSE_ITEMS, lanes=1)])
# Fold (critic 2026-09-17): work recorded AFTER the run-close changes no verdict — a phase
# event, a late gate and a late lane after the close leave the historical 3/6 intact.
write("run-f4-late", f4 + [ev(31, "run-close", items=CLOSE_ITEMS, lanes=1),
                           ev(32, "observation", phase="item3", what="a late note",
                              note="evidence: fixture"),
                           ev(33, "gate", item="item3", percent=14)]
      + lane(34, "F4-C", REAPED)
      + [ev(35, "lane-closed", lane="F4-C", exit_class="completed", total_cost_usd=1.0,
            session_id="sid-F4-C")])
print("kifix fixtures written")
PY_KIFIX
[ $? -eq 0 ] || { printf 'PROBE FAILED: the kifix fixture generator did not run\n'; exit 2; }
kwatch() {
  env LLM_WIKI_STORE="$KS" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 \
      COLUMNS=150 LINES=60 python3 -B "$WATCH" --vault "$T/vault" "$@"
}

# IK01-IK03: a record item string keys by its leading item<k> (register 2026-09-09 11:21)
kwatch --run run-ik-gate --once --plain > "$T/ik-gate.txt" 2>&1
ikrows=$(grep -cE '^│ item[0-9]+ ' "$T/ik-gate.txt")
if [ "$ikrows" = "9" ] && grep -q ' 0/9 items done' "$T/ik-gate.txt" &&
   grep -qE '^│ item1 +N148 · build\+install .*running' "$T/ik-gate.txt" && ! grep -qE '^│ item1 N148' "$T/ik-gate.txt"; then
  ok "IK01 a gate keyed with the long grammar lands on the planned row: nine item rows, item1 running, overall 0/9 (no tenth row)"
else
  no "IK01 the long-keyed gate drew $ikrows item rows: $(grep -o ' [0-9]*/[0-9]* items done' "$T/ik-gate.txt")"
fi
kwatch --run run-ik-bnd --once --plain > "$T/ik-bnd.txt" 2>&1
if [ "$(grep -cE '^│ item[0-9]+ ' "$T/ik-bnd.txt")" = "9" ] && grep -q ' 1/9 items done' "$T/ik-bnd.txt" &&
   grep -qE '^│ item1 +.* done ' "$T/ik-bnd.txt" && grep -qE '^│ item2 +.* running ' "$T/ik-bnd.txt"; then
  ok "IK02 a boundary keyed the long way ends item1 and starts item2 on their planned rows: 1/9 items done"
else
  no "IK02 the long-keyed boundary drew $(grep -cE '^│ item[0-9]+ ' "$T/ik-bnd.txt") rows: $(grep -o ' [0-9]*/[0-9]* items done' "$T/ik-bnd.txt")"
fi
# F4-01..F4-08: a boundary's never-worked target at the close (register 2026-09-17 12:51)
F4_ITEMS='3 of 6 opened (items 0 to 2); items 3 and 5 never opened; the two reports of item4 written at the close-out'
kwatch --run run-f4-close --once --plain < /dev/null > "$T/f4-close.txt" 2>&1
if grep -qE '^│ item0 .* done ' "$T/f4-close.txt" && grep -qE '^│ item1 .* done ' "$T/f4-close.txt" &&
   grep -qE '^│ item2 .* done ' "$T/f4-close.txt" && grep -qE '^│ item3 .* skipped ' "$T/f4-close.txt" &&
   grep -qE '^│ item4 .* skipped ' "$T/f4-close.txt" && grep -qE '^│ item5 .* skipped ' "$T/f4-close.txt" &&
   grep -q '3/6 items done · 3 skipped ■ RUN CLOSED' "$T/f4-close.txt"; then
  ok "F4-01 (must fire) at the close a boundary's never-worked target reads skipped: items 0 to 2 done, 3 to 5 skipped, 3/6 items done · 3 skipped"
else
  no "F4-01 the closed board reads: $(grep -E '^│ item|items done' "$T/f4-close.txt" | tr '\n' '|')"
fi
if ! grep -qE '^│ item3 .* skipped +[0-9]+:[0-9][0-9]' "$T/f4-close.txt" &&
   grep -qE '^│ item2 .* done +[0-9]+:[0-9][0-9]' "$T/f4-close.txt"; then
  ok "F4-02 the skipped target draws no elapsed time (control: the done item2 row carries its clock)"
else
  no "F4-02 the item rows read: $(grep -E '^│ item[23] ' "$T/f4-close.txt" | tr '\n' '|')"
fi
if grep -qF "run-close says: $F4_ITEMS" "$T/f4-close.txt" && grep -q 'items done · 3 skipped' "$T/f4-close.txt"; then
  ok "F4-03 the closing box quotes the run-close event's items text beside the board's own count"
else
  no "F4-03 the closing box lacks the run-close items text: $(grep -c 'run-close says' "$T/f4-close.txt") line(s)"
fi
for v in gated laned phased; do
  kwatch --run "run-f4-$v" --once --plain < /dev/null > "$T/f4-$v.txt" 2>&1
  if grep -qE '^│ item3 .* unresolved ' "$T/f4-$v.txt" && grep -q '3/6 items done · 1 unresolved · 2 skipped ■ RUN CLOSED' "$T/f4-$v.txt"; then
    ok "F4-04 (must not fire, $v) the boundary's target then worked (a $v event of its own) reads unresolved at the close, never skipped: 3/6 items done"
  else
    no "F4-04 ($v) the worked target reads: $(grep -E '^│ item3 |items done' "$T/f4-$v.txt" | tr '\n' '|')"
  fi
done
kwatch --run run-f4-open --once --plain < /dev/null > "$T/f4-open.txt" 2>&1
if grep -qE '^│ item3 .* running ' "$T/f4-open.txt" && ! grep -q 'RUN CLOSED' "$T/f4-open.txt" &&
   grep -qE '^│ item4 .* pending ' "$T/f4-open.txt"; then
  ok "F4-05 (must not fire) a run still open reads the boundary's target as running, as before"
else
  no "F4-05 the open run reads: $(grep -E '^│ item[34] ' "$T/f4-open.txt" | tr '\n' '|')"
fi
kwatch --run run-f4-noitems --once --plain < /dev/null > "$T/f4-noitems.txt" 2>&1
if ! grep -q 'run-close says' "$T/f4-noitems.txt" && grep -q '3/6 items done · 3 skipped' "$T/f4-noitems.txt" &&
   grep -q '■ RUN CLOSED · run-f4-noitems' "$T/f4-noitems.txt"; then
  ok "F4-06 (premise) a run-close with no items field: the box prints the board's count alone"
else
  no "F4-06 the no-items close reads: $(grep -E 'run-close says|items done' "$T/f4-noitems.txt" | tr '\n' '|')"
fi
kwatch --run run-f4-nobnd --once --plain < /dev/null > "$T/f4-nobnd.txt" 2>&1
if grep -qE '^│ item0 .* unresolved ' "$T/f4-nobnd.txt" && grep -q '0/6 items done · 1 unresolved · 5 skipped ■ RUN CLOSED' "$T/f4-nobnd.txt"; then
  ok "F4-07 (premise) a record with no boundary at all: the gated item reads unresolved, the rest skipped"
else
  no "F4-07 the boundary-less close reads: $(grep -E '^│ item0 |items done' "$T/f4-nobnd.txt" | tr '\n' '|')"
fi
kwatch --run run-f4-late --once --plain < /dev/null > "$T/f4-late.txt" 2>&1
if grep -qE '^│ item3 .* skipped ' "$T/f4-late.txt" && grep -q '3/6 items done · 3 skipped ■ RUN CLOSED' "$T/f4-late.txt" &&
   grep -qF "run-close says: $F4_ITEMS" "$T/f4-late.txt" && grep -q 'F4-C' "$T/f4-late.txt"; then
  ok "F4-09 (fold, must fire) a phase event, a gate and a lane recorded after the run-close change no verdict: item3 stays skipped, 3/6 items done, the run-close text quoted (the late lane still listed)"
else
  no "F4-09 post-close evidence changed the verdict: $(grep -E '^│ item3 |items done|run-close says' "$T/f4-late.txt" | tr '\n' '|')"
fi
kwatch --run run-f4-long --once --plain < /dev/null > "$T/f4-long.txt" 2>&1
if grep -qE '^│ item3 .* skipped ' "$T/f4-long.txt" && grep -qE '^│ item2 .* done ' "$T/f4-long.txt" &&
   grep -q '3/6 items done · 3 skipped ■ RUN CLOSED' "$T/f4-long.txt"; then
  ok "F4-08 (premise) a boundary in the pack grammar (item3 N3 · build) keys through item_key and its target reads skipped"
else
  no "F4-08 the long-keyed close reads: $(grep -E '^│ item[23] |items done' "$T/f4-long.txt" | tr '\n' '|')"
fi
python3 -B - "$WATCH" > "$T/ik-unit.txt" 2>&1 <<'PY_ITEMKEY'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("watch_under_test", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
cases = [("item1 N148 · build+install", "item1"), ("**item12** close-out", "item12"),
         ("item3", "item3"), ("  item4 — the phase", "item4"), ("Item5 N1 · build", "item5"),
         ("close-out", "close-out"), ("items", "items"), ("", None), ("   ", None), (None, None)]
bad = [(value, want, watch.item_key(value)) for value, want in cases if watch.item_key(value) != want]
print("cases %d bad %d %s" % (len(cases), len(bad), bad))
PY_ITEMKEY
if grep -q '^cases 10 bad 0 ' "$T/ik-unit.txt"; then
  ok "IK03 item_key reduces a long item string to its item<k>, keeps a string with no such token as itself and reads empty or missing as no item (10 cases)"
else
  no "IK03 item_key: $(tr '\n' '|' < "$T/ik-unit.txt")"
fi

# RS01-RS03: a resumed lane is in the running set until its next close (register 2026-09-13 03:44)
kwatch --run run-rs --once --plain > "$T/rs.txt" 2>&1
rsnow=$(sed -n '/lanes now/,/timeline/p' "$T/rs.txt")
if printf '%s\n' "$rsnow" | grep -qE '^│ ● RS-A ' && printf '%s\n' "$rsnow" | grep -qE '^│ ✓ RS-B ' &&
   grep -qE '^│ item1 .*●RS-A' "$T/rs.txt"; then
  ok "RS01 a lane resumed under a later item is drawn ● running in lanes now, beside the item in hand's own ✓ RS-B (the control)"
else
  no "RS01 lanes now reads: $(printf '%s' "$rsnow" | tr '\n' '|')"
fi
kwatch --run run-rs-closed-again --once --plain > "$T/rs2.txt" 2>&1
rsnow2=$(sed -n '/lanes now/,/timeline/p' "$T/rs2.txt")
if ! printf '%s\n' "$rsnow2" | grep -qE '^│ ● RS-A ' && printf '%s\n' "$rsnow2" | grep -qE '^│ ✓ RS-B ' &&
   grep -qE '^│ item1 .*✓RS-A' "$T/rs2.txt"; then
  ok "RS02 the resumed lane leaves the running set at its next lane-closed: no ● RS-A in lanes now, ✓RS-A on its item row"
else
  no "RS02 after the second close lanes now reads: $(printf '%s' "$rsnow2" | tr '\n' '|')"
fi
kwatch --run run-rs-respawn --once --plain > "$T/rs3.txt" 2>&1
if grep -qE '^│ item1 .*✗RS-A' "$T/rs3.txt" && ! grep -qE '^│ item1 .*●RS-A' "$T/rs3.txt"; then
  ok "RS03 lane-respawned names the resumed call's processes: its gone pid reads ✗ on the item row, where the pid-less lane-resumed alone would read ●"
else
  no "RS03 the respawned lane's item row reads: $(grep -E '^│ item1 ' "$T/rs3.txt")"
fi

# HM01-HM03: the header's model and effort from the latest head start (register 2026-09-10 20:29)
kwatch --run run-hm --once --plain > "$T/hm.txt" 2>&1
kwatch --run run-hm-later --once --plain > "$T/hm2.txt" 2>&1
kwatch --run run-hm-none --once --plain > "$T/hm3.txt" 2>&1
if grep -q '^│ head k-head-2 · opus·max · turn ' "$T/hm.txt"; then
  ok "HM01 the header prints head <sid8> · opus·max from the latest head start's own model and effort keys"
else
  no "HM01 the header reads: $(grep -m1 '^│ head k' "$T/hm.txt")"
fi
if grep -q '^│ head k-head-2 · model unrecorded · turn ' "$T/hm2.txt" && ! grep -q 'opus·max' "$T/hm2.txt"; then
  ok "HM02 a later head start without the keys reads model unrecorded, never the earlier start's opus·max"
else
  no "HM02 the header after a keyless head start reads: $(grep -m1 '^│ head k' "$T/hm2.txt")"
fi
if grep -q '^│ head k-head-1 · model unrecorded · turn ' "$T/hm3.txt"; then
  ok "HM03 a record whose only head start (run-open) carries no keys reads model unrecorded"
else
  no "HM03 the header reads: $(grep -m1 '^│ head k' "$T/hm3.txt")"
fi

# RW01-RW03: a live console waits for a record its detached lane has not written yet
# (register 2026-09-09 11:21: the caller now opens the console before the worker exists)
RWS="$T/rwstore"
mkdir -p "$RWS/spawn-records"
( sleep 2
  python3 -B -c '
import json, os, sys, time
path = sys.argv[1]
now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
rows = [{"ts": now, "run": "run-late", "event": "lane-open", "lane": "LATE", "class": "builder",
         "model": "opus", "effort": "xhigh", "session_id": "sid-late"},
        {"ts": now, "run": "run-late", "event": "lane-closed", "lane": "LATE",
         "exit_class": "completed", "total_cost_usd": 0.1},
        {"ts": now, "run": "run-late", "event": "run-close", "shape": "plain-lane-run", "lanes": 1}]
with open(path + ".part", "w", encoding="utf-8") as fh:
    fh.write("".join(json.dumps(r) + "\n" for r in rows))
os.replace(path + ".part", path)
' "$RWS/spawn-records/run-late.jsonl" ) &
latepid=$!
env LLM_WIKI_STORE="$RWS" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 COLUMNS=150 LINES=60 \
    python3 -B "$WATCH" --vault "$T/vault" --run run-late --plain --refresh 0.2 --wait-record 30 \
    < /dev/null > "$T/late.txt" 2>&1
lrc=$?
wait "$latepid"
if [ "$lrc" -eq 0 ] && grep -q 'waiting up to 30 s for the run record' "$T/late.txt" &&
   grep -q '■ RUN CLOSED · run-late' "$T/late.txt"; then
  ok "RW01 a live console started before its record exists waits for it, then renders and closes the run (exit 0)"
else
  no "RW01 the late record: exit $lrc, $(head -3 "$T/late.txt" | tr '\n' '|')"
fi
env LLM_WIKI_STORE="$RWS" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 COLUMNS=150 LINES=60 \
    python3 -B "$WATCH" --vault "$T/vault" --run run-never --plain --wait-record 1 \
    < /dev/null > "$T/never.txt" 2>&1
nrc=$?
if [ "$nrc" -eq 2 ] && grep -q 'waiting up to 1 s' "$T/never.txt" && grep -q 'PROBE FAILED' "$T/never.txt" &&
   grep -q 'no run record' "$T/never.txt"; then
  ok "RW02 a record that never appears is still the premise failure once the wait is over (exit 2)"
else
  no "RW02 the missing record after the wait: exit $nrc, $(tr '\n' '|' < "$T/never.txt")"
fi
env LLM_WIKI_STORE="$RWS" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 COLUMNS=150 LINES=60 \
    python3 -B "$WATCH" --vault "$T/vault" --run run-never --once --plain --wait-record 30 \
    < /dev/null > "$T/never-once.txt" 2>&1
orc=$?
if [ "$orc" -eq 2 ] && ! grep -q 'waiting up to' "$T/never-once.txt" && grep -q 'no run record' "$T/never-once.txt"; then
  ok "RW03 --once never waits: a missing record fails at once (the control for RW01)"
else
  no "RW03 --once on a missing record: exit $orc, $(tr '\n' '|' < "$T/never-once.txt")"
fi

# ---------------------------------------------------------------- leg 9: derived paths
strays=$(grep -c -E '/Us''ers/|/ho''me/|/Vol''umes/|Cloud''Storage|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-' "$WATCH")
control=$(grep -c -E '/Us''ers/|/ho''me/|/Vol''umes/|Cloud''Storage|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-' "$T/planted/planted-strays.py")
if [ "$strays" -eq 0 ] && [ "$control" -gt 0 ]; then
  ok "no owner path or session id in watch.py (0 hits; the same sweep hits the planted file $control times)"
else
  no "the owner-path sweep found $strays hits in watch.py and $control in the planted control"
fi

vname=$(grep -c "$SYNTH_VAULT_NAME" "$WATCH")
vcontrol=$(grep -c "$SYNTH_VAULT_NAME" "$T/planted/planted-strays.py")
if [ "$vname" -eq 0 ] && [ "$vcontrol" -gt 0 ]; then
  ok "no vault name in watch.py (the name sweep hits the planted file $vcontrol times)"
else
  no "the vault-name sweep found $vname hits in watch.py"
fi

python3 -B - "$WATCH" "$T/planted/planted-strays.py" > "$T/literals.txt" 2>&1 <<'PY_LIT'
"""Every string literal in the file that looks like a path, minus the ones a derivation needs.
An owner path can only enter the source as such a literal, so a clean list is the ship-safe claim;
the planted file must show strays or the check proves nothing."""
import ast
import sys

ALLOWED = {"~/.llm-wiki", "~/.claude", "handsoff.py", "%s.jsonl", "spawn-records",
           "%s-timeline.txt", "watch.py",
           # the harness's job root, composed with this process's own uid in tasks_root(): a
           # system directory every account shares, never an owner path (A4, 2026-09-08)
           "/tmp"}


def path_shaped(v):
    """A literal that could be a path: it starts at a root or a home, or it is one unbroken
    token holding a separator. Prose and format strings hold spaces and are not paths."""
    if v in ALLOWED or len(v) <= 3:
        return False
    return v.startswith(("/", "~/", "./")) or ("/" in v and " " not in v and "\n" not in v)


def patterns(tree):
    """Every string literal that is an argument of `re.compile`. A regular expression holding a
    `/` (`.../tasks/...`, an alternation) is a pattern, not a path, and counting it as a stray
    would either fail this leg on correct source or push the sweep towards an allow-list long
    enough to hide a real owner path."""
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "compile" and \
                isinstance(fn.value, ast.Name) and fn.value.id == "re":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out.add(arg.value)
    return out


def strays(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    skip = patterns(tree)
    out = [node.value for node in ast.walk(tree)
           if isinstance(node, ast.Constant) and isinstance(node.value, str)
           and node.value not in skip and path_shaped(node.value)]
    return sorted(set(out))


for arg in sys.argv[1:]:
    found = strays(arg)
    print("%s: %d %s" % (arg.rsplit("/", 1)[-1], len(found), found[:4]))
PY_LIT
if grep -q '^watch.py: 0 ' "$T/literals.txt" &&
   grep -qE '^planted-strays.py: [1-9]' "$T/literals.txt"; then
  ok "watch.py holds no path-shaped string literal outside its derivation allow-list (control hits)"
else
  no "path literals in watch.py: $(cat "$T/literals.txt" | tr '\n' '|')"
fi

if grep -q "$T/store/spawn-records/run-vocab.jsonl" "$T/vocab.err" 2>/dev/null; then
  no "the console printed the record path as an error"
else
  ok "the store, the projects root and the vault were taken from the environment and --vault"
fi

# ---------------------------------------------------------------- leg 9b: the live head meter
# A synthetic transcript: message A written as two records with one id (a multi-block turn, the
# duplicate the live meter must fold), message B once, both fable at 1,000 output tokens, and a
# message C on an unpriced model. Expected $0.10 (two priced messages at $50/MTok), not the naive
# $0.15; messages 3; unpriced 1; and a missing path is an error, never a zero.
python3 -B - "$HERE" "$T" <<'LIVE' > "$T/live-meter.txt" 2>&1
import json, os, sys
sys.path.insert(0, sys.argv[1])
import watch
p = os.path.join(sys.argv[2], "live-meter-fixture.jsonl")
def rec(mid, model, out):
    return json.dumps({"type": "assistant", "uuid": mid + "-u", "message": {"id": mid, "model": model,
                       "usage": {"input_tokens": 0, "output_tokens": out, "cache_read_input_tokens": 0,
                                 "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0}}}})
with open(p, "w") as fh:
    fh.write("\n".join([rec("A", "claude-fable-5-1", 1000), rec("A", "claude-fable-5-1", 1000),
                        rec("B", "claude-fable-5-1", 1000), rec("C", "claude-fixture", 1000)]) + "\n")
print("RESULT", json.dumps(watch.head_live_spend(p)))
print("MISSING", json.dumps(watch.head_live_spend(os.path.join(sys.argv[2], "no-such.jsonl"))))
LIVE
if grep -q '"usd": 0.1[0]*[,}]' "$T/live-meter.txt" && grep -q '"messages": 3' "$T/live-meter.txt" &&
   grep -q '"unpriced": 1' "$T/live-meter.txt" && grep -q 'MISSING {"error": "no transcript"}' "$T/live-meter.txt"; then
  ok "LM01 the live head meter folds a duplicated message id (0.10, not 0.15), counts the unpriced model, and errors on a missing transcript"
else
  no "LM01 the live head meter read: $(tr '\n' ' ' < "$T/live-meter.txt" | cut -c1-300)"
fi

# ---------------------------------------------------------------- HL: the held lanes (2026-09-17)
# A held lane is drawn ◐ held on the lanes panel and the items panel while its hold is open and it
# is not running again; a beat that failed alerts; a hold that ended reads closed with its reason;
# the older decision hold (no lane) holds nothing.
run_watch --run run-held --once --plain > "$T/held.txt" 2>"$T/held.err"
hlrc=$?
if [ "$hlrc" -eq 0 ] && ! grep -q 'PROBE FAILED' "$T/held.err"; then
  ok "HL00 the held-lanes record renders (exit 0, no PROBE FAILED)"
else
  no "HL00 the held-lanes record exited $hlrc: $(head -2 "$T/held.err")"
fi
if grep -qE '^│ ◐ H-ONE .*held · beats 1/2 · last beat [0-9]{2}:[0-9]{2} ok · next due [0-9]{2}:[0-9]{2}' "$T/held.txt"; then
  ok "HL01 a held lane with one beat of two reads ◐ held with its beat count, its last beat's time and the next beat's due time"
else
  no "HL01 the held row is wrong: $(grep -E 'H-ONE' "$T/held.txt" | head -1)"
fi
if grep -qE '^│ ◐ H-TWO .*held · beats 1/1 · last beat [0-9]{2}:[0-9]{2} FAILED · beat due' "$T/held.txt"; then
  ok "HL02 a held lane whose beat failed 108 minutes ago reads ◐ held with the failure on its row and the beat due"
else
  no "HL02 the failed-beat row is wrong: $(grep -E 'H-TWO' "$T/held.txt" | head -1)"
fi
if grep -qE '^│ ✓ H-THREE .*completed .*hold ended \(cap\)' "$T/held.txt" && ! grep -qE '^│ ◐ H-THREE' "$T/held.txt"; then
  ok "HL03 a lane whose hold ended at the cap reads ✓ completed again, naming the reason (the control: not ◐)"
else
  no "HL03 the ended-hold row is wrong: $(grep -E 'H-THREE' "$T/held.txt" | head -1)"
fi
if grep -qE '^│ ● H-FOUR .*' "$T/held.txt" && ! grep -qE '^│ ◐ H-FOUR' "$T/held.txt"; then
  ok "HL04 a held lane resumed for real reads ● running, never ◐ (no beat while it runs again)"
else
  no "HL04 the resumed held lane is wrong: $(grep -E 'H-FOUR' "$T/held.txt" | head -1)"
fi
item1held=$(grep -E '^│ item1 ' "$T/held.txt")
case $item1held in
  *"◐H-ONE"*"◐H-TWO"*"✓H-THREE"*"●H-FOUR"*) ok "HL05 the items panel marks the two held lanes ◐, the ended one ✓ and the resumed one ●" ;;
  *) no "HL05 the items row is wrong: $item1held" ;;
esac
if grep -q '◐ held' "$T/held.txt"; then
  ok "HL06 the timeline legend names ◐ held"
else
  no "HL06 the legend lacks ◐ held"
fi
python3 -B - "$WATCH" > "$T/held-alerts.txt" 2>&1 <<'PY_HELD'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("watch_under_test", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
print("failed beat alerts: %s" % watch.is_alert({"event": "hold-beat", "lane": "X", "ok": False}))
print("ok beat alerts: %s" % watch.is_alert({"event": "hold-beat", "lane": "X", "ok": True}))
print("hold alerts: %s" % watch.is_alert({"event": "hold", "lane": "X", "cap": 1}))
print("ended alerts: %s" % watch.is_alert({"event": "hold-ended", "lane": "X", "reason": "cap"}))
print("kinds treated: %s" % all(k in watch.TREATMENT for k in ("hold", "hold-beat", "hold-ended")))
PY_HELD
if grep -q 'failed beat alerts: True' "$T/held-alerts.txt" && grep -q 'ok beat alerts: False' "$T/held-alerts.txt" &&
   grep -q 'hold alerts: False' "$T/held-alerts.txt" && grep -q 'ended alerts: False' "$T/held-alerts.txt" &&
   grep -q 'kinds treated: True' "$T/held-alerts.txt"; then
  ok "HL07 a failed beat is an alert, a successful one, a hold and a hold-ended are not, and the three kinds are treated"
else
  no "HL07 the alert rule is wrong: $(tr '\n' '|' < "$T/held-alerts.txt")"
fi
if grep -qE '^│ ◐ H-FIVE .*held · beats 0/1 · last beat none yet · beat due' "$T/held.txt"; then
  ok "HL09 a lane held two minutes ago whose last call is an hour old reads beat due: the row's reference is the lane's last call as the hold recorded it, never the hold's own stamp (must fire; HL01's next due is the control)"
else
  no "HL09 the due time is not taken from the last call: $(grep -E '^│ . H-FIVE' "$T/held.txt" | head -1)"
fi
if grep -qE '^│ ✓ H-SIX .*completed · hold ended \(released\)' "$T/held.txt"; then
  ok "HL10 a lane whose reason runs past the row still names how its hold ended: the note precedes the reason, which the width cuts (must fire)"
else
  no "HL10 the hold note was cut off the row: $(grep -E '^│ . H-SIX' "$T/held.txt" | head -1)"
fi
# HL12 (the re-base, 2026-09-17): the console's state fold carries BOTH changes that met in it —
# the afternoon's rule that a boundary's never-worked target shows no clock, and the held lanes'
# ◐ on the items panel. One record, one Run, one render_items call answers for both.
mkdir -p "$T/bothfold"
python3 -B - "$WATCH" "$T/bothfold/run-both.jsonl" > "$T/both-fold.txt" 2>&1 <<'PY_BOTH'
import importlib.util
import json
import sys
import time

spec = importlib.util.spec_from_file_location("watch_both", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
t0 = time.time() - 60 * 60


def ts(mins):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0 + mins * 60))


rows = [
    {"ts": ts(0), "run": "run-both", "event": "run-open", "session": "s", "head": "both"},
    {"ts": ts(1), "run": "run-both", "event": "gate", "item": "item1", "percent": 5,
     "decision": "allow", "metered": True},
    {"ts": ts(2), "run": "run-both", "event": "lane-open", "lane": "BL", "class": "builder",
     "model": "fable", "effort": "max", "session_id": "both-sid"},
    {"ts": ts(3), "run": "run-both", "event": "lane-closed", "lane": "BL",
     "exit_class": "completed", "session_id": "both-sid", "total_cost_usd": 1.0},
    {"ts": ts(4), "run": "run-both", "event": "hold", "lane": "BL", "harness": "claude",
     "cap": 1, "beat_after_s": 3000, "last_call": ts(3), "session_id": "both-sid"},
    # the boundary's target is never worked: item3 keeps a start and no work, and the gate that
    # follows makes item2 the current one, so item3 is the pending-with-a-start case
    {"ts": ts(5), "run": "run-both", "event": "phase-boundary", "from": "item1", "to": "item3"},
    {"ts": ts(6), "run": "run-both", "event": "gate", "item": "item2", "percent": 6,
     "decision": "allow", "metered": True},
]
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    for row in rows:
        handle.write(json.dumps(row) + "\n")
run = watch.Run("run-both", sys.argv[2], sys.argv[1])
print("held: %s" % run.lanes["BL"].is_held())
print("boundary_only: %s" % ("item3" in run.boundary_only))
print("item3 state: %s" % run.state("item3"))
for line in watch.render_items(run, 100):
    print("row| " + line)
PY_BOTH
BOTH_ITEM3=$(grep '^row| ' "$T/both-fold.txt" | grep -c 'item3.*pending')
BOTH_CLOCK=$(grep '^row| ' "$T/both-fold.txt" | grep 'item3' | grep -cE '[0-9]+:[0-9]{2}')
if grep -q 'held: True' "$T/both-fold.txt" && grep -q 'boundary_only: True' "$T/both-fold.txt" &&
   grep -q '^row| .*◐BL' "$T/both-fold.txt" && [ "$BOTH_ITEM3" = "1" ] && [ "$BOTH_CLOCK" = "0" ]; then
  ok "HL12 the state fold holds both changes that met in it: the held lane is folded to ◐ on the items panel AND a boundary's never-worked target is marked boundary_only and drawn with no clock (the re-base of 2026-09-17)"
else
  no "HL12 one of the two behaviours is missing: $(tr '\n' '|' < "$T/both-fold.txt" | cut -c1-400)"
fi
if grep -qE '^│ ◐ H-SEVEN .*held · beats 0/2 · last beat none yet · next due [0-9]{2}:[0-9]{2}' "$T/held.txt"; then
  ok "HL11 a held lane resumed for real and closed again five minutes ago reads ◐ held with its NEXT due time, since the close that followed the hold is the lane's last call (critic F6; HL02's 'beat due' is the control)"
else
  no "HL11 the due time ignores the close that followed the hold: $(grep -E '^│ . H-SEVEN' "$T/held.txt" | head -1)"
fi
if ! grep -qE '^│ ◐ |◐B-ONE|◐C-TWO|◐V-THREE' "$T/vocab.txt" && grep -q '✓B-ONE' "$T/vocab.txt"; then
  ok "HL08 a hold that was released and the older decision hold (no lane) leave no lane ◐ on the vocabulary record (the control for the lane-keyed reading)"
else
  no "HL08 a lane reads held on the vocabulary record: $(grep -E '^│ ◐ |◐B-ONE|◐C-TWO|◐V-THREE' "$T/vocab.txt" | head -1)"
fi
# HL13 (review finding 1, 2026-09-18): what an open hold's row may PROMISE depends on the run's
# hold service, because a beat comes from the supervisor's tick and from nowhere else. Five
# records, one state each, all with the same lane, the same cap and the same due beat, rendered
# through render_lanes with the colour off: only a live service says `beat due`.
mkdir -p "$T/holdsvc"
python3 -B - "$WATCH" "$T/holdsvc" > "$T/hold-service.txt" 2>&1 <<'PY_HOLDSVC'
import importlib.util
import json
import os
import sys
import time

spec = importlib.util.spec_from_file_location("watch_holdsvc", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
watch.USE_COLOUR = False
t0 = time.time() - 3 * 60 * 60


def ts(mins):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0 + mins * 60))


# the common prefix: a run, a supervisor that ticks, a lane closed 80 minutes ago and held, so
# the beat is due under the recorded 3,000 s interval in every one of the five records
def base(name):
    return [
        {"ts": ts(0), "run": name, "event": "run-open", "session": "s", "head": "svc"},
        {"ts": ts(1), "run": name, "event": "gate", "item": "item1", "percent": 5,
         "decision": "allow", "metered": True},
        {"ts": ts(2), "run": name, "event": "supervise", "mode": "attached", "pid": 1,
         "services_holds": True},
        {"ts": ts(3), "run": name, "event": "lane-open", "lane": "SV", "class": "builder",
         "model": "fable", "effort": "max", "session_id": "svc-sid"},
        {"ts": ts(100), "run": name, "event": "lane-closed", "lane": "SV",
         "exit_class": "completed", "session_id": "svc-sid", "total_cost_usd": 1.0},
        {"ts": ts(101), "run": name, "event": "hold", "lane": "SV", "harness": "claude",
         "cap": 1, "beat_after_s": 3000, "last_call": ts(100), "session_id": "svc-sid"},
    ]


cases = {
    # the live control: the supervisor is ticking and the beat really is due
    "run-svc-live": [],
    # a requested stop: the supervisor stands down at the head's exit and beats nothing meanwhile
    "run-svc-stop": [{"ts": ts(102), "event": "supervise", "mode": "stop-requested"}],
    # the crash residue: a stand-down or a close with the hold still open (the supervisor died
    # between ending the holds and writing its own last event)
    "run-svc-down": [{"ts": ts(102), "event": "supervisor-stood-down", "reason": "stopped"}],
    "run-svc-closed": [{"ts": ts(102), "event": "run-close", "items": "1"}],
    # a stop cleared by a head that came back: the row promises a beat again
    "run-svc-back": [{"ts": ts(102), "event": "supervise", "mode": "stop-requested"},
                     {"ts": ts(103), "event": "supervise", "mode": "attached", "pid": 2,
                      "services_holds": True}],
}
for name, extra in cases.items():
    path = os.path.join(sys.argv[2], name + ".jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        for row in base(name) + [dict(e, run=name) for e in extra]:
            handle.write(json.dumps(row) + "\n")
    run = watch.Run(name, path, sys.argv[1])
    lane = run.lanes["SV"]
    print("%s service=%s held=%s" % (name, run.hold_service, lane.is_held()))
    for line in watch.render_lanes(run, 160):
        if " SV " in line:
            print("%s row|%s" % (name, line))
PY_HOLDSVC
HS_LIVE=$(grep '^run-svc-live row|' "$T/hold-service.txt")
HS_STOP=$(grep '^run-svc-stop row|' "$T/hold-service.txt")
HS_DOWN=$(grep '^run-svc-down row|' "$T/hold-service.txt")
HS_CLOSED=$(grep '^run-svc-closed row|' "$T/hold-service.txt")
HS_BACK=$(grep '^run-svc-back row|' "$T/hold-service.txt")
if printf '%s' "$HS_STOP" | grep -q '◐ SV .*held · stop requested · no beat until the supervisor is back' &&
   ! printf '%s' "$HS_STOP" | grep -q 'beat due' &&
   grep -q '^run-svc-stop service=stop-requested held=True' "$T/hold-service.txt"; then
  ok "HL13 an open hold under a REQUESTED supervisor stop reads ◐ held · stop requested · no beat until the supervisor is back, never beat due (review finding 1, must fire)"
else
  no "HL13 the requested stop still promises a beat: $HS_STOP"
fi
if printf '%s' "$HS_DOWN" | grep -q '◐ SV .*held · unserviced (the supervisor stood down (stopped) at ' &&
   printf '%s' "$HS_CLOSED" | grep -q '◐ SV .*held · unserviced (the run closed at ' &&
   ! printf '%s%s' "$HS_DOWN" "$HS_CLOSED" | grep -q 'beat due'; then
  ok "HL14 an open hold left behind by a stood-down supervisor or a closed run — the residue of a crash between the hold-ended and the event itself — reads ◐ held · unserviced with the reason, never beat due (must fire)"
else
  no "HL14 the unserviced residue is wrong: $HS_DOWN || $HS_CLOSED"
fi
if printf '%s' "$HS_LIVE" | grep -q '◐ SV .*held · beats 0/1 · last beat none yet · beat due' &&
   printf '%s' "$HS_BACK" | grep -q '◐ SV .*held · beats 0/1 · last beat none yet · beat due' &&
   grep -q '^run-svc-back service=live' "$T/hold-service.txt"; then
  ok "HL15 the live-due controls still read beat due: a ticking supervisor, and one that attached again after a requested stop (the stop is cleared by the later supervise, as the supervisor itself reads it)"
else
  no "HL15 a live hold service lost its due time: $HS_LIVE || $HS_BACK"
fi

# ---------------------------------------------------------------- FS: the live screen fits the window (2026-09-22)
# A frame taller than the window scrolls its top away. This synthetic fixture
# checks that item and lane counts cannot hide the header on a short window.
# The live, non-plain screen folds to the window; a snapshot, --plain and the final board
# stay whole. The fixtures live in a store of their own ($T/fstore), outside the write-proof manifest.
mkdir -p "$T/fstore/spawn-records"
python3 -B - "$T/fstore/spawn-records" <<'PY_CROWD'
import json, os, sys, time
out = sys.argv[1]
t0 = time.time() - 200 * 60


def ev(run, mins, kind, **fields):
    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0 + mins * 60)),
               "run": run, "event": kind}
    payload.update(fields)
    return payload


def lanes(run, n):
    rows = []
    for i in range(n):
        name, cls = "L%02d" % (i + 1), ("builder", "critic", "verifier")[i % 3]
        rows.append(ev(run, 2 + 5 * i, "lane-open", lane=name, **{"class": cls}, model="opus",
                       effort="max", reason="(b) breadth: a synthetic crowded-run lane"))
        rows.append(ev(run, 5 + 5 * i, "lane-closed", lane=name, **{"class": cls},
                       exit_class="completed" if i != 3 else "error", total_cost_usd=0.5,
                       num_turns=3, duration_s=180))
    return rows


run = "run-crowd-closed"
rows = [ev(run, 0, "run-open", session="head-sid-crowd", head="the fixture", regime="multi",
           expect_items={"item%d" % k: 40000 for k in range(18)})]
for k in range(7):
    rows.append(ev(run, 1 + 20 * k, "gate", item="item%d" % k, context=1000, percent=1))
    rows.append(ev(run, 19 + 20 * k, "phase-boundary", **{"from": "item%d" % k,
                                                          "to": "item%d" % (k + 1)}))
rows += lanes(run, 28)
rows.append(ev(run, 190, "run-close", items="7", lanes="28"))
rows.sort(key=lambda r: r["ts"])
with open(os.path.join(out, run + ".jsonl"), "w", encoding="utf-8") as fh:
    fh.writelines(json.dumps(r) + "\n" for r in rows)

run = "run-crowd-plain"
rows = lanes(run, 28) + [ev(run, 190, "run-close", shape="plain-lane-run", lanes=28)]
with open(os.path.join(out, run + ".jsonl"), "w", encoding="utf-8") as fh:
    fh.writelines(json.dumps(r) + "\n" for r in rows)
print("crowd fixtures written")
PY_CROWD

crowd() {   # crowd <lines> <run> [args…]: the console against the crowded store at a fixed window
  _l=$1; _r=$2; shift 2
  env LLM_WIKI_STORE="$T/fstore" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 \
      COLUMNS=150 LINES="$_l" python3 -B "$WATCH" --vault "$T/vault" --run "$_r" --refresh 0.2 \
      "$@" < /dev/null 2>/dev/null
}

# split one live run's output into the screen frame and the final board after the screen
cat > "$T/fs-split.py" <<'PY_SPLIT'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
height = int(sys.argv[2])
if "\x1b[2J\x1b[H" not in text or "\x1b[?1049l" not in text:
    print("frame=absent")
    sys.exit(0)
frame = text.split("\x1b[2J\x1b[H", 1)[1].split("\x1b[?25h", 1)[0]
final = text.split("\x1b[?1049l", 1)[1]
rows = frame.rstrip("\n").split("\n")
items = lambda s: len(set(re.findall(r"^│ (item\d+) ", s, re.M)))
lanes = lambda s: len(set(re.findall(r"^│ (L\d\d) ", s, re.M)))
print("frame_rows=%d budget=%d fits=%s" % (len(rows), height - 1, len(rows) <= height - 1))
print("title=%s" % ("console · " in rows[0]))
print("frame_items=%d frame_lanes=%d item_fold=%d lane_fold=%d overall=%s"
      % (items(frame), lanes(frame), len(re.findall(r"^│ ⋯ .*folded to fit the window", frame, re.M)),
         len(re.findall(r"^│ \+\d+ lanes .*folded to fit the window", frame, re.M)),
         bool(re.search(r"^│ overall ", frame, re.M))))
print("now_fold=%d" % len(re.findall(r"^│   \+\d+ lanes .*folded to fit the window", frame, re.M)))
print("final_items=%d final_lanes=%d final_fold=%s"
      % (items(final), lanes(final), "folded to fit" in final))
PY_SPLIT

crowd 40 run-crowd-closed > "$T/fs40.txt"; python3 -B "$T/fs-split.py" "$T/fs40.txt" 40 > "$T/fs40.res"
if grep -q 'fits=True' "$T/fs40.res" && grep -q 'title=True' "$T/fs40.res" &&
   grep -qE 'item_fold=[12] lane_fold=1 overall=True' "$T/fs40.res"; then
  ok "FS01 a crowded run (18 items, 28 lanes) on a 40-row window: the live frame fits, the title shows, lanes and items fold, the overall line stays"
else
  no "FS01 the crowded live frame: $(tr '\n' '|' < "$T/fs40.res")"
fi
if grep -q 'final_items=18 final_lanes=28 final_fold=False' "$T/fs40.res"; then
  ok "FS02 the final board after the live screen is whole (18 items, 28 lanes, no fold line)"
else
  no "FS02 the final board: $(tr '\n' '|' < "$T/fs40.res")"
fi
crowd 200 run-crowd-closed > "$T/fs200.txt"; python3 -B "$T/fs-split.py" "$T/fs200.txt" 200 > "$T/fs200.res"
if grep -q 'fits=True' "$T/fs200.res" &&
   grep -q 'frame_items=18 frame_lanes=28 item_fold=0 lane_fold=0' "$T/fs200.res" &&
   grep -q 'now_fold=0' "$T/fs200.res"; then
  ok "FS03 the must-not-fire case: on a 200-row window the same run folds nothing"
else
  no "FS03 a tall window folded: $(tr '\n' '|' < "$T/fs200.res")"
fi
crowd 6 run-crowd-closed > "$T/fs6.txt"; python3 -B "$T/fs-split.py" "$T/fs6.txt" 6 > "$T/fs6.res"
if grep -q 'frame_rows=[1-5] budget=5 fits=True' "$T/fs6.res" && grep -q 'title=True' "$T/fs6.res"; then
  ok "FS04 a 6-row window: the frame is clipped from the bottom to fit, the title row first"
else
  no "FS04 the tiny window: $(tr '\n' '|' < "$T/fs6.res")"
fi
crowd 20 run-crowd-plain > "$T/fsp.txt"; python3 -B "$T/fs-split.py" "$T/fsp.txt" 20 > "$T/fsp.res"
if grep -q 'fits=True' "$T/fsp.res" && grep -q 'lane_fold=1' "$T/fsp.res" && grep -q 'now_fold=1' "$T/fsp.res" &&
   grep -q 'final_lanes=28 final_fold=False' "$T/fsp.res"; then
  ok "FS05 a plain record (no head row, every lane in hand) folds its timeline and lanes now to a 20-row window and keeps the final board whole"
else
  no "FS05 the plain crowded record: $(tr '\n' '|' < "$T/fsp.res")"
fi
crowd 40 run-crowd-closed --once > "$T/fsonce.txt"
crowd 40 run-crowd-closed --plain > "$T/fsplain.txt"
fo_items=$(grep -cE '^│ item[0-9]+ ' "$T/fsonce.txt")
fp_items=$(grep -cE '^│ item[0-9]+ ' "$T/fsplain.txt")
if [ "$fo_items" -ge 18 ] && [ "$fp_items" -ge 18 ] &&
   ! grep -q 'folded to fit' "$T/fsonce.txt" && ! grep -q 'folded to fit' "$T/fsplain.txt"; then
  ok "FS06 --once and --plain stay whole on a 40-row window ($fo_items and $fp_items item rows, no fold line)"
else
  no "FS06 a snapshot or --plain folded: $fo_items and $fp_items item rows"
fi

# ---------------------------------------------------------------- PN/OR: names arriving after run-open and orientation
# Exercise the real main loop on one Run: each key read follows a rendered frame, so the
# fixture edit happens after the unnamed frame and the assertion sees the next refresh.
# No sleeps or live console are needed. This mutable fixture tree is outside manifest().
python3 -B - "$WATCH" "$T" > "$T/item-refresh.txt" 2>&1 <<'PY_ITEM_REFRESH'
import contextlib
from datetime import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("watch_item_refresh", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
watch.USE_COLOUR = False
root = Path(sys.argv[2]) / "item-refresh"
root.mkdir()
stamp = datetime.now().astimezone().isoformat()


def event(kind, **fields):
    return dict(ts=stamp, run="run-items", event=kind, **fields)


def pack_text(names):
    return "## Resume prompt\n" + "".join(
        "- %s %s — fixture work.\n" % pair for pair in names.items())


def fixture(label, names, planned=True):
    base = root / label
    base.mkdir()
    pack = base / "pack.md"
    pack.write_text(pack_text(names), encoding="utf-8")
    record = base / "run-items.jsonl"
    opened = event("run-open", handoff=str(pack))
    if planned:
        opened["expect_items"] = {"item0": 1, "item1": 1, "item2": 1}
    rows = [opened]
    save(record, rows)
    return pack, record, rows


def save(record, rows):
    record.write_text("".join(json.dumps(e) + "\n" for e in rows), encoding="utf-8")


def panel(run):
    return "\n".join(watch.render_items(run, 150))


def row(text, key):
    found = next((line for line in text.splitlines() if line.startswith("│ " + key + " ")), "")
    assert found, "missing %s row: %s" % (key, text)
    return found


def check(label, test):
    try:
        test()
    except AssertionError as exc:
        print("FAIL %s: %s" % (label, str(exc).replace("\n", " | ") or "assertion failed"))
    else:
        print("ok   " + label)


def live_names(label, initial, final, append=False, preflight=False):
    pack, record, rows = fixture(label, initial)
    target = pack
    if preflight:
        target = pack.with_name("run-items-preflight.md")
        target.write_text(pack_text(initial), encoding="utf-8")
        pack.write_text("## Resume prompt\nSee the sibling pre-flight.\n", encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    step = 0
    # One unchanged refresh discovers the selected pre-flight path in the source cache;
    # the subsequent edit must be noticed through that source's metadata, not its discovery.
    edit_step = 1 if preflight else 0
    before = record.read_bytes()
    inputs = None

    def manifest():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in pack.parent.iterdir() if p.is_file()}

    def key(_timeout):
        nonlocal step, inputs
        text = out.getvalue()
        if step <= edit_step:
            for item, name in initial.items():
                assert name in row(text, item), text
            if not initial:
                assert text.count(" pending ") == 3, text
                assert all(name not in text for name in final.values()), text
            if step == edit_step:
                target.write_text(pack_text(final), encoding="utf-8")
                if append:
                    with record.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(event("observation", note="names ready")) + "\n")
                inputs = manifest()  # after the fixture edit, before the console reads it
            out.seek(0)
            out.truncate()
            step += 1
            return ""
        for item, name in final.items():
            assert name in row(text, item), text
        assert len([line for line in text.splitlines() if line.startswith("│ item")]) == 3, text
        if not append:
            assert record.read_bytes() == before, "record changed without an append"
        step += 1
        return "q"

    env = {"LLM_WIKI_STORE": str(root), "AIMYTH_PROJECTS_DIR": str(root),
           "AIMYTH_WATCH_NOTIFY": "0", "COLUMNS": "150", "LINES": "60"}
    with patch.dict(os.environ, env), patch.object(watch, "record_path", return_value=str(record)), \
            patch.object(watch, "read_key", side_effect=key), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        assert watch.main(["--run", "run-items", "--vault", str(root), "--plain",
                           "--no-notify", "--wait-record", "0"]) == 0
    assert step == edit_step + 2, "the live loop did not render every expected frame"
    assert not err.getvalue(), err.getvalue()
    assert inputs and inputs == manifest(), "the console changed its fixture inputs"


names = {"item0": "orientation", "item1": "capture", "item2": "review"}
check("PN01 blank names fill after a pack edit and record append; planned rows survive",
      lambda: live_names("append", {}, {"item1": "capture", "item2": "review"}, append=True))
check("PN02 blank names fill after a pack edit alone; record bytes stay unchanged",
      lambda: live_names("pack-only", {}, {"item1": "capture", "item2": "review"}))
check("PN03 a fully named pack is renamed without a record append",
      lambda: live_names("rename", names, dict(names, item1="collect")))
check("PN04 a fully named pre-flight is refreshed without a record append",
      lambda: live_names("preflight", names, dict(names, item1="collect"), preflight=True))


def planned_rows():
    pack, record, rows = fixture("partial", {"item1": "capture"})
    run = watch.Run("run-items", str(record), str(root))
    assert run.names == {"item0": "", "item1": "capture", "item2": ""}, run.names
    text = panel(run)
    assert text.count(" pending ") == 3 and "0/3 items done" in text, text
    assert "capture" in row(text, "item1"), text


check("PN05 a partial pack retains every expect_items row with zero items done and a named control",
      planned_rows)
check("PN06 blank names retry the pre-flight while the pack and record stay unchanged",
      lambda: live_names("blank-retry", {}, names, preflight=True))


def orientation(label, named=False, evidence=True, decision="allow", later=False,
                closed=False, phase=False, null=False, target="item1", prior_allowed=False):
    pack, record, rows = fixture(label, names if named else {"item1": "capture"})
    run = watch.Run("run-items", str(record), str(root))
    assert "pending" in row(panel(run), "item0"), panel(run)
    if prior_allowed:
        rows.extend([event("gate", item="item1", decision="allow"), event("head-successor")])
    if phase:
        rows.append(event("ledger", phase="item0", note="orientation read"))
    gate = event("gate", item=target, decision=decision)
    if evidence:
        gate["orientation_tokens"] = None if null else 0  # zero is measured, not absent
    rows.append(gate)
    if closed:
        rows.insert(-1, event("run-close"))
    if later:
        rows.append(event("gate", item="item1", decision="allow"))
    save(record, rows)
    run.rebuild(watch.read_events(str(record)))
    wanted = "done" if not closed and not prior_allowed and target == "item1" and (phase or evidence and not null) \
        and (decision == "allow" or later) else "skipped" if closed else "pending"
    text = panel(run)
    assert wanted in row(text, "item0"), text
    assert len(run.item_order) == 3, run.item_order
    if wanted == "done":
        assert "running" in row(text, "item1") and "1/3 items done" in text, text
    elif wanted == "pending":
        assert "0/3 items done" in text and "capture" in row(text, "item1"), text


check("OR01 measured orientation and an allowed first-item gate complete named item0",
      lambda: orientation("named", named=True))
check("OR02 the same allowed gate completes item0 when the pack never names it",
      lambda: orientation("unnamed"))
check("OR03 a refused gate leaves orientation pending despite measured evidence (negative control)",
      lambda: orientation("refused", decision="refuse"))
check("OR04 evidence on a refused gate survives until the later allowed gate",
      lambda: orientation("retry", decision="refuse", later=True))
check("OR05 an allowed gate without orientation evidence leaves item0 pending",
      lambda: orientation("no-evidence", evidence=False))
check("OR06 null orientation is unmeasured and leaves item0 pending",
      lambda: orientation("null", null=True))
check("OR07 explicit work on phase item0 followed by an allowed gate completes orientation",
      lambda: orientation("phase", evidence=False, phase=True))
check("OR08 a gate after run-close does not change the orientation verdict",
      lambda: orientation("post-close", closed=True))
check("OR09 an allowed gate skipping the first work item does not complete orientation",
      lambda: orientation("skip-first", target="item2"))
check("OR10 a later head's measured orientation cannot complete item0 retrospectively",
      lambda: orientation("later-head", prior_allowed=True))


def late_orientation(label, decision="allow", evidence=True):
    pack, record, rows = fixture(label, {"item1": "capture", "item2": "review"}, planned=False)
    gate = event("gate", item="item1", decision=decision)
    if evidence:
        gate["orientation_tokens"] = 0  # measured zero is evidence
    rows.append(gate)
    save(record, rows)
    before = record.read_bytes()
    out, err = io.StringIO(), io.StringIO()
    step = 0

    def key(_timeout):
        nonlocal step
        text = out.getvalue()
        if step == 0:
            assert not any(line.startswith("│ item0 ") for line in text.splitlines()), text
            assert "capture" in row(text, "item1") and "0/2 items done" in text, text
            # The gate is already in the record; only the pack changes from here onwards.
            pack.write_text(pack_text(names), encoding="utf-8")
            out.seek(0)
            out.truncate()
            step += 1
            return ""
        wanted = "done" if decision == "allow" and evidence else "pending"
        assert "orientation" in row(text, "item0") and wanted in row(text, "item0"), text
        assert "running" in row(text, "item1") and "pending" in row(text, "item2"), text
        assert ("1/3" if wanted == "done" else "0/3") + " items done" in text, text
        assert record.read_bytes() == before, "the late row depended on a record append"
        step += 1
        return "q"

    env = {"LLM_WIKI_STORE": str(root), "AIMYTH_PROJECTS_DIR": str(root),
           "AIMYTH_WATCH_NOTIFY": "0", "COLUMNS": "150", "LINES": "60"}
    with patch.dict(os.environ, env), patch.object(watch, "record_path", return_value=str(record)), \
            patch.object(watch, "read_key", side_effect=key), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        assert watch.main(["--run", "run-items", "--vault", str(root), "--plain",
                           "--no-notify", "--wait-record", "0"]) == 0
    assert step == 2, "the live loop did not render the frame before and after name discovery"
    assert not err.getvalue(), err.getvalue()
    assert {p.name for p in pack.parent.iterdir()} == {pack.name, record.name}
    assert pack.read_text(encoding="utf-8") == pack_text(names), "the console changed the pack"
    assert record.read_bytes() == before, "the console changed the record"


def orientation_admission(label, decision="allow", evidence=True):
    pack, record, rows = fixture(label, names)
    admission = event("gate", item="item0", decision="allow")
    if evidence:
        admission["orientation_tokens"] = 0  # only the admission carries the measurement
    rows.append(admission)
    save(record, rows)
    run = watch.Run("run-items", str(record), str(root))
    text = panel(run)
    assert "running" in row(text, "item0") and "pending" in row(text, "item1"), text
    assert "0/3 items done" in text, text
    # There is no boundary event; departure alone must settle orientation.
    rows.append(event("gate", item="item1", decision=decision))
    save(record, rows)
    before = record.read_bytes()
    run.rebuild(watch.read_events(str(record)))
    wanted = "done" if decision == "allow" and evidence else "pending"
    text = panel(run)
    assert wanted in row(text, "item0") and "running" in row(text, "item1"), text
    assert "review" in row(text, "item2") and "pending" in row(text, "item2"), text
    assert ("1/3" if wanted == "done" else "0/3") + " items done" in text, text
    assert record.read_bytes() == before, "the console changed the record"


check("OR11 item0 first named after an allowed gate is done on a pack-only refresh without expect_items",
      lambda: late_orientation("late-name"))
check("OR12 admission to item0 then an allowed item1 gate completes orientation without a boundary",
      lambda: orientation_admission("admission"))
check("OR13 a late orientation row stays pending for a refused gate or absent evidence",
      lambda: (late_orientation("late-refused", decision="refuse"),
               late_orientation("late-no-evidence", evidence=False)))
check("OR14 after item0 admission, refusal or absent evidence leaves orientation pending",
      lambda: (orientation_admission("admission-refused", decision="refuse"),
               orientation_admission("admission-no-evidence", evidence=False)))
PY_ITEM_REFRESH
[ $? -eq 0 ] || { cat "$T/item-refresh.txt"; printf 'PROBE FAILED: item refresh fixtures did not finish\n'; exit 2; }
while IFS= read -r result; do
  case "$result" in
    'ok   '*) ok "${result#ok   }" ;;
    'FAIL '*) no "${result#FAIL }" ;;
    *) printf 'PROBE FAILED: unexpected item refresh output: %s\n' "$result"; exit 2 ;;
  esac
done < "$T/item-refresh.txt"

# ---------------------------------------------------------------- B10: the console repairs of Batch 10
# Their fixtures live in a store of their own ($T/b10store), outside the manifest the write-proof
# legs compare, as the KF legs' do; the one sanctioned report a close writes there stays there.
BS="$T/b10store"
mkdir -p "$BS/spawn-records" "$T/b10handoffs"
python3 -B - "$T" "$LIVE_PID" <<'PY_B10FIX'
import json
import os
import sys
import time

T, LIVE = sys.argv[1], int(sys.argv[2])
REC = os.path.join(T, "b10store", "spawn-records")
t0 = time.time() - 90 * 60


def ts(mins):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0 + mins * 60))


def ev(mins, kind, **fields):
    payload = {"ts": ts(mins), "event": kind}
    payload.update(fields)
    return payload


def write(run, rows):
    with open(os.path.join(REC, run + ".jsonl"), "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row, run=run), ensure_ascii=False) + "\n")


four = os.path.join(T, "b10handoffs", "four.md")
with open(four, "w", encoding="utf-8") as fh:
    fh.write("# a four-item pack (fixture)\n\n## Resume prompt\n\n")
    for k in range(1, 5):
        fh.write("item%d N%d · build — fixture item %d\n" % (k, k, k))

# WR: a record with no run-open and no lane event yet (register 2026-10-01 13:34): the spawner's
# pre-registered controls line (`ledger --phase controls-LANE` writes an observation) and an early
# peer-name observation, both written before the wrapper's lane-open.
controls = [ev(0, "observation", phase="controls-XR", what="controls: a fixture phrase in a truth file",
               note="pre-registered by the spawner"),
            ev(0.1, "observation", phase="peer", what="peer name: fixture-peer", note="fixture")]
write("run-wr-ctl", controls)              # stays event-less: the premise failure after the grace
write("run-wr-ctl-late", controls)         # gains its lane-open inside the grace (the leg appends it)

# RE: a resume at another effort (register 2026-09-21 18:5x). codex-lane.py's lane-resumed carries
# model and effort; lane.py's carries neither key, so its resume keeps the open's.
opened = [ev(0, "lane-open", lane="RE-A", model="gpt-6-astra", effort="max", session_id="sid-RE-A",
             reason="(a) a fixture lane", **{"class": "builder"}),
          ev(0, "lane-spawned", lane="RE-A", session_id="sid-RE-A", pid=LIVE, wrapper_pid=LIVE),
          ev(10, "lane-closed", lane="RE-A", exit_class="completed", total_cost_usd=1.0,
             session_id="sid-RE-A")]
write("run-re-ultra", opened + [ev(20, "lane-resumed", lane="RE-A", session_id="sid-RE-A2",
                                   wrapper_pid=LIVE, resume_n=1, model="gpt-6-astra", effort="ultra")])
write("run-re-keyless", opened + [ev(20, "lane-resumed", lane="RE-A", session_id="sid-RE-A2",
                                     wrapper_pid=LIVE, resume_n=1)])

# ST: the head row after a stand-down (register 2026-09-25 14:5x): the head exits, the supervisor
# stands down (the ✖), then a heartbeat line and the supervisor's own exit observation arrive.
head = [ev(0, "run-open", session="st-head-1", handoff=four, regime="multi"),
        ev(1, "gate", item="item1", percent=5)]
write("run-st-down", head + [ev(30, "head-exit", band="ok", handoff=four, pack=True),
                             ev(35, "supervisor-stood-down", reason="stopped"),
                             ev(50, "heartbeat", minutes=30, action="beat"),
                             ev(60, "observation", what="the supervisor exited after the stand-down",
                                note="fixture")])
write("run-st-live", head + [ev(50, "heartbeat", minutes=30, action="beat")])
write("run-st-resumed", head + [ev(30, "stop-condition", which="limit", action="wait"),
                                ev(40, "head-resumed", session_id="st-head-1", resume_n=1)])

# PR: items worked in parallel (register 2026-09-20 20:0x, the recurrence of 22 September):
# item1 and item2 are gated, item2's boundary ends it and hands on to item3; item1 has no end.
write("run-pr", [ev(0, "run-open", session="pr-head-1", handoff=four, regime="multi"),
                 ev(1, "gate", item="item1", percent=5),
                 ev(10, "gate", item="item2", percent=8),
                 ev(20, "phase-boundary", **{"from": "item2", "to": "item3"})])
print("b10 fixtures written")
PY_B10FIX
[ $? -eq 0 ] || { printf 'PROBE FAILED: the B10 fixture generator did not run\n'; exit 2; }
bwatch() {
  env LLM_WIKI_STORE="$BS" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 \
      COLUMNS=150 LINES=60 python3 -B "$WATCH" --vault "$T/vault" "$@"
}

# WR01-WR03: a record holding no run-open and no lane event gets the missing record's grace
# (register 2026-10-01 13:34); RW01-RW03 above stay the missing-record legs, unchanged.
( sleep 2
  python3 -B -c '
import json, sys, time
path = sys.argv[1]
now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
rows = [{"ts": now, "run": "run-wr-ctl-late", "event": "lane-open", "lane": "WR-A", "class": "critic",
         "model": "opus", "effort": "max", "session_id": "sid-WR-A"},
        {"ts": now, "run": "run-wr-ctl-late", "event": "lane-closed", "lane": "WR-A",
         "exit_class": "completed", "total_cost_usd": 0.1},
        {"ts": now, "run": "run-wr-ctl-late", "event": "run-close", "shape": "plain-lane-run", "lanes": 1}]
with open(path, "a", encoding="utf-8") as fh:
    fh.write("".join(json.dumps(r) + "\n" for r in rows))
' "$BS/spawn-records/run-wr-ctl-late.jsonl" ) &
wrpid=$!
bwatch --run run-wr-ctl-late --plain --refresh 0.2 --wait-record 30 < /dev/null > "$T/wr-late.txt" 2>&1
wrrc=$?
wait "$wrpid"
if [ "$wrrc" -eq 0 ] && grep -q 'waiting up to 30 s for a run-open or lane event' "$T/wr-late.txt" &&
   grep -q '■ RUN CLOSED · run-wr-ctl-late' "$T/wr-late.txt" && ! grep -q 'PROBE FAILED' "$T/wr-late.txt"; then
  ok "WR01 (must fire) a controls-only record that gains its lane-open inside the grace draws the console and closes the run (exit 0)"
else
  no "WR01 the controls-only record: exit $wrrc, $(head -3 "$T/wr-late.txt" | tr '\n' '|')"
fi
bwatch --run run-wr-ctl --plain --wait-record 1 < /dev/null > "$T/wr-never.txt" 2>&1
wnrc=$?
if [ "$wnrc" -eq 2 ] && grep -q 'waiting up to 1 s for a run-open or lane event' "$T/wr-never.txt" &&
   grep -q 'PROBE FAILED: no run-open, no lane-open and no lane-closed event' "$T/wr-never.txt"; then
  ok "WR02 a record that stays event-less past the grace waits first, then ends with its probe message (exit 2)"
else
  no "WR02 the event-less record after the wait: exit $wnrc, $(tr '\n' '|' < "$T/wr-never.txt")"
fi
bwatch --run run-wr-ctl --once --plain --wait-record 30 < /dev/null > "$T/wr-once.txt" 2>&1
wonrc=$?
if [ "$wonrc" -eq 2 ] && ! grep -q 'waiting up to' "$T/wr-once.txt" &&
   grep -q 'no run-open, no lane-open and no lane-closed event' "$T/wr-once.txt"; then
  ok "WR03 --once still never waits: the controls-only record fails at once (the control for WR01)"
else
  no "WR03 --once on the controls-only record: exit $wonrc, $(tr '\n' '|' < "$T/wr-once.txt")"
fi

# RE01-RE02: a resumed lane's row takes the resume's model and effort (register 2026-09-21 18:5x)
bwatch --run run-re-ultra --once --plain > "$T/re-ultra.txt" 2>&1
if grep -qE '^. ● RE-A .* astra·ultra ' "$T/re-ultra.txt" && ! grep -qE '^. . RE-A .* astra·max ' "$T/re-ultra.txt"; then
  ok "RE01 (must fire) a resume from max to ultra draws the lane at astra·ultra in lanes now, never the open's astra·max"
else
  no "RE01 the resumed lane reads: $(grep -E '^. . RE-A ' "$T/re-ultra.txt" | head -1)"
fi
bwatch --run run-re-keyless --once --plain > "$T/re-keyless.txt" 2>&1
if grep -qE '^. ● RE-A .* astra·max ' "$T/re-keyless.txt"; then
  ok "RE02 (must not fire) a resume whose event carries no model or effort key keeps the open's astra·max"
else
  no "RE02 the keyless resume reads: $(grep -E '^. . RE-A ' "$T/re-keyless.txt" | head -1)"
fi

# ST01-ST03: the head row's fill ends at the stop of a stood-down head (register 2026-09-25 14:5x)
for v in down live resumed; do
  bwatch --run "run-st-$v" --once --plain > "$T/st-$v.txt" 2>&1
done
python3 -B - "$WATCH" "$T/st-down.txt" "$T/st-live.txt" "$T/st-resumed.txt" > "$T/st-cells.txt" 2>&1 <<'PY_HEADCELLS'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("watch_under_test", sys.argv[1])
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
cut = len("│ ") + watch.LANE_NAME_W + 1                  # the box edge and the label column
for path in sys.argv[2:]:
    rows = [line.rstrip("\n") for line in open(path, encoding="utf-8")
            if line.startswith("│ head ") and line[7:8] == " "]
    if len(rows) != 1:
        print("%s rows=%d" % (path.rsplit("/", 1)[-1], len(rows)))
        continue
    cells = rows[0][cut:-2]
    stop = cells.rfind("✖")
    before = cells[:stop].count("█") if stop >= 0 else 0
    after = cells[stop + 1:].count("█") if stop >= 0 else -1
    print("%s stop=%s before=%d after=%d last=%s" % (path.rsplit("/", 1)[-1][:-4],
          "yes" if stop >= 0 else "no", before, after, cells.rstrip()[-1:] or "-"))
PY_HEADCELLS
stdown=$(grep '^st-down ' "$T/st-cells.txt")
case $stdown in
  "st-down stop=yes before="[1-9]*" after=0 last="*) ok "ST01 (must fire) after a head exit and a stand-down, the heartbeat and the supervisor's exit observation draw no head fill past the ✖ ($stdown)" ;;
  *) no "ST01 the stood-down head row: $stdown" ;;
esac
stlive=$(grep '^st-live ' "$T/st-cells.txt")
case $stlive in
  "st-live stop=no "*" last=█") ok "ST02 (must not fire) a live head with a later heartbeat still fills its row to now ($stlive)" ;;
  *) no "ST02 the live head row: $stlive" ;;
esac
stres=$(grep '^st-resumed ' "$T/st-cells.txt")
case $stres in
  "st-resumed stop=yes "*" last=█") ok "ST03 (must not fire) a stop followed by a head start fills on to now ($stres)" ;;
  *) no "ST03 the resumed head row: $stres" ;;
esac

# PR01-PR02: running is every gated item with no end boundary, not only the item in hand
# (register 2026-09-20 20:0x); OR11-OR14 above keep item0's own rule, and leg 3, IK and F4 the
# item in hand's.
bwatch --run run-pr --once --plain > "$T/pr.txt" 2>&1
if grep -qE '^│ item1 .* running ' "$T/pr.txt" && grep -qE '^│ item3 .* running ' "$T/pr.txt"; then
  ok "PR01 (must fire) two items gated and one ended: the other gated item reads running beside the item in hand"
else
  no "PR01 the parallel items read: $(grep -E '^│ item[13] ' "$T/pr.txt" | tr '\n' '|')"
fi
if grep -qE '^│ item2 .* done ' "$T/pr.txt" && grep -qE '^│ item4 .* pending ' "$T/pr.txt" &&
   grep -q ' 1/4 items done' "$T/pr.txt"; then
  ok "PR02 (must not fire) the ended item reads done and the never-gated one pending: 1/4 items done"
else
  no "PR02 the other rows read: $(grep -E '^│ item[24] |items done' "$T/pr.txt" | tr '\n' '|')"
fi

# ---------------------------------------------------------------- IX: suffixed items, re-declared maps, summary bullets, the billed label
# Four causes of one miscount (register 2026-10-12 15:54), each with a planted case and a control:
# a suffixed item keyed as its parent, planned rows read from the run-open's map alone, a
# hand-off's summary bullet read as an item's name, and a boundary's billed figures shown
# unlabelled beside a later head. The fixtures live under $T/ixstore, outside manifest(); only
# --once snapshots and in-process renders run. An `expect-items` event is written in the shape
# handsoff.py's `expect` writes it (its map under `items`, `src` "expect"); IX09 and IX10 hold the
# panel to the map the gate reads, IX10 against handsoff.py's own declared_items beside this suite.
mkdir -p "$T/ixstore/spawn-records" "$T/ixstore/projects" "$T/ixstore/vault" "$T/ixstore/state"
python3 -B - "$WATCH" "$T/ixstore" "$HERE/handsoff.py" > "$T/ix.txt" 2>&1 <<'PY_IX'
import importlib.util
import json
import os
import subprocess
import sys
import time

WATCH, ROOT, HANDSOFF = sys.argv[1], sys.argv[2], sys.argv[3]
RECS = os.path.join(ROOT, "spawn-records")
os.environ.update(LLM_WIKI_STORE=ROOT, AIMYTH_PROJECTS_DIR=os.path.join(ROOT, "projects"),
                  AIMYTH_STATE_DIR=os.path.join(ROOT, "state"), AIMYTH_WATCH_NOTIFY="0")
spec = importlib.util.spec_from_file_location("watch_ix", WATCH)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
watch.USE_COLOUR = False
t0 = time.time() - 3 * 3600
METER = "billed (list, prices 0000-00-00): head $1.00 · lanes $2.00 · session $3.00 · rewrites 0 ($0.00)"


def ts(mins):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0 + mins * 60))


def hhmm(mins):
    return time.strftime("%H:%M", time.localtime(t0 + mins * 60))


def shown(mins):
    """The board's label for that moment: the time alone on the day the suite runs, and its date as well
    across midnight, since t0 is three hours back."""
    moment = watch.parse_ts(ts(mins))
    return hhmm(mins) if moment.date() == watch.datetime.now(moment.tzinfo).date() else watch.dated(moment)


def room(width):
    return width + len(shown(20)) - len(hhmm(20))    # a dated label is wider, and these legs pin the header's fit


def ev(mins, kind, run, **fields):
    out = {"ts": ts(mins), "run": run, "event": kind}
    out.update(fields)
    return out


def save(name, events):
    path = os.path.join(RECS, name + ".jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(json.dumps(e) + "\n" for e in events))
    return path


def check(label, test):
    try:
        test()
    except AssertionError as exc:
        print("FAIL %s: %s" % (label, str(exc).replace("\n", " | ") or "assertion failed"))
    except Exception as exc:                       # a missing function is a failed leg, not a crash
        print("FAIL %s: %s: %s" % (label, type(exc).__name__, str(exc).replace("\n", " | ")))
    else:
        print("ok   " + label)


def ix01():
    cases = [("item14b", "item14b"), ("item14b N214 · build", "item14b"), ("**item12b** close-out", "item12b"),
             ("itemR3", "itemR3"), ("itemB4f · verify", "itemB4f"), ("Item4b N1 · build", "item4b"),
             ("item14 N214 · build", "item14"), ("item14-verify", "item14"), ("item1 N148 · build+install", "item1"),
             ("items", "items"), ("itemization", "itemization")]
    bad = [(v, want, watch.item_key(v)) for v, want in cases if watch.item_key(v) != want]
    assert not bad, bad


def ix02():
    text = ("## In flight\n- item0 to item13b, itemB4f — done\n- item2 and item3 — open\n"
            "- item14b N214 · build — the work\n- itemC1 C1 · close-out — the work\n"
            "- item5 verify item4's build — the work\n- item0 orientation — read the pack\n")
    got = watch.parse_items(text)
    want = {"item14b": "N214 · build", "itemC1": "C1 · close-out", "item5": "verify item4's build",
            "item0": "orientation"}
    assert got == want, got


def ix03():
    keys = ["itemR1", "item12b", "item2", "itemC1", "item10", "item12", "item0", "itemB4f", "zz"]
    got = sorted(keys, key=watch.item_sort_key)
    assert got == ["item0", "item2", "item10", "item12", "item12b", "itemB4f", "itemC1", "itemR1", "zz"], got


PACK = os.path.join(ROOT, "ix-handoff.md")
with open(PACK, "w", encoding="utf-8") as fh:
    fh.write("# Hand-off\n\n## In flight\n- item0 to item1b — done\n\n## Items\n- item0 orientation — read\n"
             "- item1 N1 · build — go\n- item1b N1 · install — go\n- itemC1 C1 · close-out — go\n\n"
             "## Resume prompt\nResume from the record.\n")
board_events = [
    ev(0, "run-open", "run-ix", session="ix-head-1", handoff=PACK,
       expect_items={"item0": 1, "item1": 1, "item2": 1, "item3": 1}),
    ev(1, "gate", "run-ix", item="item1", percent=10, decision="allow", orientation_tokens=10),
    ev(20, "phase-boundary", "run-ix", meter=METER, **{"from": "item1", "to": "item1b"}),
    ev(21, "gate", "run-ix", item="item1b", percent=20, decision="allow"),
    ev(30, "expect-items", "run-ix",
       items={"item0": 1, "item1": 1, "item1b": 1, "item2": 1, "item3": 1, "itemC1": 1}, src="expect"),
    ev(40, "head-successor", "run-ix", session_id="ix-head-2"),
]
REC = save("run-ix", board_events)


def snapshot(run, columns):
    env = dict(os.environ, COLUMNS=str(columns), LINES="60")
    r = subprocess.run([sys.executable, "-B", WATCH, "--vault", os.path.join(ROOT, "vault"), "--run", run,
                        "--once", "--plain"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, "exit %d: %s" % (r.returncode, r.stderr[-300:])
    return r.stdout


def rows(text):
    out = {}
    for line in text.splitlines():
        if line.startswith("│ item"):
            key = line[2:].split(" ", 1)[0]
            state = next((w for w in ("done", "running", "pending", "skipped") if " %s " % w in line), "?")
            out[key] = (state, line)
    return out


def ix04():
    text = snapshot("run-ix", 150)
    got = rows(text)
    states = {k: v[0] for k, v in got.items()}
    assert states == {"item0": "done", "item1": "done", "item1b": "running", "item2": "pending",
                      "item3": "pending", "itemC1": "pending"}, states
    assert " 2/6 items done" in text, [l for l in text.splitlines() if "items done" in l]
    assert "orientation" in got["item0"][1] and "to item1b" not in text, got["item0"][1]


def ix05():
    kinds = sorted({e["event"] for e in board_events})
    missing = [k for k in kinds if k not in watch.TREATMENT]
    assert "expect-items" in kinds and not missing, missing
    assert "an-invented-kind" not in watch.TREATMENT


def ix06():
    launch = {"item0": 1, "item1": 1}
    events = [ev(0, "run-open", "run-x", expect_items=launch),
              ev(1, "expect-items", "run-x", items=["item9"], src="expect"),
              ev(2, "expect-items", "run-x", expect_items={"item7": 1}),
              ev(3, "observation", "run-x", items={"item7": 1}, expect_items={"item7": 1}),
              ev(4, "run-resume", "run-x", expect_items={"item0": 1, "item2": 1})]
    got = watch.latest_expect(events)
    assert got == launch, got
    later = events + [ev(5, "expect-items", "run-x", items={"item2b": 80000}, src="expect")]
    assert watch.latest_expect(later) == {"item2b": 80000}, watch.latest_expect(later)
    emptied = later + [ev(6, "expect-items", "run-x", items={}, src="expect")]
    assert watch.latest_expect(emptied) == {}, watch.latest_expect(emptied)


def ix07():
    pack2 = os.path.join(ROOT, "ix-refresh-handoff.md")
    with open(pack2, "w", encoding="utf-8") as fh:
        fh.write("## Resume prompt\n- item0 orientation — read\n- item1 N1 · build — go\n")
    rec = save("run-ix-refresh", [ev(0, "run-open", "run-ix-refresh", session="ix-r", handoff=pack2,
                                     expect_items={"item0": 1, "item1": 1})])
    run = watch.Run("run-ix-refresh", rec, os.path.join(ROOT, "vault"))
    before = list(run.item_order)
    with open(rec, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev(1, "expect-items", "run-ix-refresh",
                               items={"item0": 1, "item1": 1, "item1b": 1}, src="expect")) + "\n")
    run.rebuild(watch.read_events(rec))
    assert before == ["item0", "item1"] and list(run.item_order) == ["item0", "item1", "item1b"], (before, run.item_order)


def ix08():
    run = watch.Run("run-ix", REC, os.path.join(ROOT, "vault"))
    wide = "\n".join(watch.render_header(run, room(240), "0"))
    full = "billed ▲%s item1→item1b, before this head: head $1.00 · lanes $2.00 · session $3.00" % shown(20)
    assert full in wide and "supervisor" in wide, wide
    narrow = "\n".join(watch.render_header(run, room(150), "0"))
    assert ("▲%s head $1.00 · lanes $2.00 · session $3.00 · elapsed " % shown(20)) in narrow and "supervisor" in narrow, narrow
    # control: a boundary inside the current head's tenure says which boundary, never "before this head"
    own = save("run-ix-own", board_events[:4])
    mine = watch.Run("run-ix-own", own, os.path.join(ROOT, "vault")).spend()
    assert mine.startswith("billed ▲%s item1→item1b: head $1.00" % shown(20)), mine
    closed = save("run-ix-closed", board_events + [ev(50, "run-close", "run-ix", meter=METER, items="fixture")])
    shut = watch.Run("run-ix-closed", closed, os.path.join(ROOT, "vault")).spend()
    assert shut.startswith("billed ■%s: head $1.00" % hhmm(50)), shut


# A real record's shape: the run-open declares item0 to item10; after launch the head's `expect` declares
# one item, and the record carries `"items": {"item2b": 80000}, "src": "expect"`. The gate takes
# that map whole (handsoff.py declared_items: a replacement, never a merge), so the panel does too.
PARTIAL_LAUNCH = {"item0": 40000, "item1": 160000, "item2": 90000, "item3": 90000, "item4": 140000,
                  "item5": 60000, "item6": 90000, "item7": 150000, "item8": 50000, "item9": 120000,
                  "item10": 150000}
PACK_T = os.path.join(ROOT, "ix-partial-handoff.md")
with open(PACK_T, "w", encoding="utf-8") as fh:
    fh.write("# Hand-off\n\n## Resume prompt\nResume from the record.\n")
partial_events = [
    ev(0, "run-open", "run-ix-partial", session="ix-t-seed", handoff=PACK_T, regime="multi",
       expect_items=PARTIAL_LAUNCH),
    ev(1, "head-exit", "run-ix-partial"),
    ev(1, "head-successor", "run-ix-partial", session_id="ix-t-head"),
    ev(2, "run-resume", "run-ix-partial", session="ix-t-head", head="the fixture", detail="item0"),
    ev(3, "phase-boundary", "run-ix-partial", **{"from": "item0", "to": "item1"}),
    ev(3, "gate", "run-ix-partial", item="item1", percent=5, decision="allow"),
    ev(10, "phase-boundary", "run-ix-partial", **{"from": "item1", "to": "item3"}),
    ev(10, "gate", "run-ix-partial", item="item3", percent=9, decision="allow"),
    ev(11, "expect-items", "run-ix-partial", items={"item2b": 80000}, src="expect"),
    ev(17, "phase-boundary", "run-ix-partial", **{"from": "item3", "to": "item4"}),
    ev(17, "gate", "run-ix-partial", item="item4", percent=12, decision="allow"),
]
save("run-ix-partial", partial_events)


def ix09():
    text = snapshot("run-ix-partial", 150)
    got = rows(text)
    states = {k: v[0] for k, v in got.items()}
    want = {"item1": "done", "item2b": "pending", "item3": "done", "item4": "running"}
    assert all(states.get(k) == s for k, s in want.items()), states
    stale = sorted(k for k in ("item2", "item5", "item6", "item7", "item8", "item9", "item10") if k in got)
    assert not stale, "rows from the replaced launch map: %s" % stale
    done = sum(1 for s in states.values() if s == "done")
    assert (" %d/%d items done" % (done, len(states))) in text, [l for l in text.splitlines() if "items done" in l]
    assert watch.latest_expect(partial_events) == {"item2b": 80000}, watch.latest_expect(partial_events)


def ix10():
    import ast
    with open(HANDSOFF, encoding="utf-8") as fh:          # read only; the function's own source runs alone
        tree = ast.parse(fh.read())
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "declared_items"]
    assert len(fn) == 1, "%d top-level declared_items definitions in %s, wanted 1" % (len(fn), HANDSOFF)
    ns = {}
    exec(compile(ast.Module(body=fn, type_ignores=[]), HANDSOFF, "exec"), ns)
    gate = ns["declared_items"]
    a, b, c = {"item0": 1, "item1": 1}, {"item0": 2, "item2b": 3}, {"item4": 5}
    cases = {
        "a real record's shape": partial_events,
        "the launch map alone": [ev(0, "run-open", "r", expect_items=a), ev(1, "gate", "r", item="item0")],
        "two re-declarations": [ev(0, "run-open", "r", expect_items=a), ev(1, "expect-items", "r", items=b),
                                ev(2, "expect-items", "r", items=c)],
        "a list-valued items": [ev(0, "run-open", "r", expect_items=a), ev(1, "expect-items", "r", items=b),
                                ev(2, "expect-items", "r", items=["item9"])],
        "the run-open's key on an expect-items event": [ev(0, "run-open", "r", expect_items=a),
                                                         ev(1, "expect-items", "r", expect_items=b)],
        "a map on a run-resume": [ev(0, "run-open", "r", expect_items=a),
                                  ev(1, "run-resume", "r", expect_items=b)],
        "a map on another kind": [ev(0, "run-open", "r", expect_items=a),
                                  ev(1, "observation", "r", items=b, expect_items=b)],
        "an empty items map": [ev(0, "run-open", "r", expect_items=a), ev(1, "expect-items", "r", items={})],
        "two run-opens": [ev(0, "run-open", "r", expect_items=a), ev(1, "run-open", "r", expect_items=b)],
        "a first run-open without a map": [ev(0, "run-open", "r"), ev(1, "run-open", "r", expect_items=b)],
        "no run-open": [ev(0, "gate", "r", item="item1")],
        "an empty record": [],
    }
    bad = [(name, watch.latest_expect(evs), gate(evs)) for name, evs in cases.items()
           if watch.latest_expect(evs) != gate(evs)]
    assert not bad, bad

    def misread(evs):                                    # control: `expect_items` read on every kind
        got = {}
        for e in evs:
            if e.get("event") in ("run-open", "run-resume", "expect-items") \
                    and isinstance(e.get("expect_items"), dict) and e["expect_items"]:
                got = e["expect_items"]
        return got
    assert misread(partial_events) != gate(partial_events), "control: the misreading reader agreed with the gate"


if not os.path.isfile(HANDSOFF):
    print("PROBE FAILED: no handsoff.py beside this suite at %s; IX10 compares the panel's map with "
          "its declared_items" % HANDSOFF)
check("IX01 item_key keys a suffixed or lettered item as itself (item14b, itemR3, itemB4f, Item4b) and still reduces a long string to its id (11 cases)", ix01)
check("IX02 parse_items skips a summary bullet (to / and lists) and names suffixed and lettered items; a name that only mentions another item is kept", ix02)
check("IX03 item_sort_key orders numbered items by number with a suffix after its parent, then lettered series, then any other key", ix03)
check("IX04 (must fire) an open item1b reads running on its own row beside a done item1, the latest expect-items map adds itemC1, the summary bullet names nothing: 2/6 items done", ix04)
check("IX05 every kind in the IX record has a treatment, expect-items included; an invented kind has none (control)", ix05)
check("IX06 (must not fire) a list-valued items, the run-open's key on an expect-items event, a map on another kind and a map on a run-resume leave the launch map the plan; the last expect-items event's items map replaces it whole, a partial map and an empty one alike", ix06)
check("IX07 a map appended to the record reaches the rows on the next rebuild when every name is already filled", ix07)
check("IX08 the header labels the billed figures with their boundary (full when it fits, mark and time alone when not, elapsed and supervisor kept); before this head only when a head started after it (control); a close's meter reads ■", ix08)


# The item bars (register 2026-11-05 12:41; the critic's model): a start records activity, only an
# explicit completion record ends an item, and a close reports what is left without converting it.
def ib_run(name, rows):
    opening = ev(0, "run-open", name, session="sid-ib", head="fixture head",
                 expect_items={"item1": 1000, "item2": 1000, "item3": 1000})
    return watch.Run(name, save(name, [opening] + rows), os.path.join(ROOT, "vault"))


def ib01():
    n = "run-ib1"
    run = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"), ev(5, "run-close", n, items="three done")])
    assert (run.state("item1"), run.state("item2")) == ("unresolved", "skipped"), run.state("item1")
    assert watch.items_summary(run) == "0/3 items done · 1 unresolved · 2 skipped", watch.items_summary(run)
    n = "run-ib1b"
    ended = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"),
                       ev(2, "phase-boundary", n, **{"from": "item1", "to": "item2"}),
                       ev(3, "gate", n, item="item2", decision="allow"), ev(4, "item-done", n, items=["item2"]),
                       ev(5, "run-close", n, items="two")])
    assert (ended.state("item1"), ended.state("item2")) == ("done", "done"), ended.state("item2")
    assert watch.items_summary(ended) == "2/3 items done · 1 skipped", watch.items_summary(ended)


def ib02():
    n = "run-ib2"
    run = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"), ev(2, "gate", n, item="item2", decision="allow"),
                     ev(3, "item-done", n, items=["item1", "item2 N2 · build", "item3"]), ev(5, "run-close", n, items="all")])
    assert [run.state(i) for i in ("item1", "item2", "item3")] == ["done"] * 3, run.item_end
    assert watch.items_summary(run) == "3/3 items done · all done" and watch.close_tone(run) == watch.GREEN
    assert not run.meters, run.meters
    assert "items=item1,item2 N2 · build,item3" in watch.fmt_event(run.events[3]), watch.fmt_event(run.events[3])


def ib03():
    n = "run-ib3"
    run = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"),
                     ev(2, "lane-open", n, lane="LA", item="item2"), ev(2, "lane-open", n, lane="LB", item="item3 N3 · read"),
                     ev(3, "lane-open", n, lane="LC")])
    assert (run.lanes["LA"].item, run.lanes["LB"].item, run.lanes["LC"].item) == ("item2", "item3", "item1"), run.lanes
    assert run.current == "item1", run.current
    assert [run.state(i) for i in ("item1", "item2", "item3")] == ["running"] * 3, run.gated
    assert (run.lanes["LA"].item_inferred, run.lanes["LC"].item_inferred) == (False, True)
    text = "\n".join(watch.render_items(run, 160))
    assert "●LA " in text and "●LB " in text and "●LC~" in text, text


def ib04():
    n = "run-ib4"
    run = ib_run(n, [ev(1, "lane-open", n, lane="LA", item="item2"),
                     ev(2, "lane-closed", n, lane="LA", exit_class="completed", total_cost_usd=1.0),
                     ev(5, "run-close", n, items="none")])
    assert run.state("item2") == "unresolved", run.state("item2")
    assert "✓LA" in "\n".join(watch.render_items(run, 160))


def ib05():
    n = "run-ib5"
    run = ib_run(n, [ev(30, "gate", n, item="item1", decision="allow")])
    text = "\n".join(watch.render_items(run, 170))
    assert "last item record %s" % watch.dated(watch.parse_ts(ts(30))) in text and " ago" in text, text
    idle = ib_run("run-ib5b", [])
    assert "last item record" not in "\n".join(watch.render_items(idle, 170))


def ib06():
    n = "run-ib6"
    old = ev(-2880, "phase-boundary", n, meter=METER, **{"from": "item1", "to": "item2"})
    run = ib_run(n, [old])
    when = watch.dated(watch.parse_ts(old["ts"]))
    assert run.spend().startswith("billed ▲%s item1→item2" % when), run.spend()
    assert run.spend(short=True).startswith("▲%s" % when), run.spend(short=True)
    same = ib_run("run-ib6b", [ev(20, "phase-boundary", "run-ib6b", meter=METER, **{"from": "item1", "to": "item2"})])
    assert same.spend().startswith("billed ▲%s item1→item2" % shown(20)), same.spend()


def ib07():
    n = "run-ib7"
    run = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"), ev(5, "run-close", n, items="one"),
                     ev(6, "item-done", n, items=["item1"])])
    assert run.state("item1") == "unresolved", run.state("item1")


def ib08():
    n = "run-ib8"
    run = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"),
                     ev(2, "phase-boundary", n, **{"from": "item1", "to": "item2"}), ev(5, "run-close", n, items="one")])
    assert run.state("item2") == "skipped", run.state("item2")
    n = "run-ib8b"
    done = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"),
                      ev(2, "phase-boundary", n, **{"from": "item1", "to": "item2"}),
                      ev(3, "item-done", n, items=["item2"]), ev(5, "run-close", n, items="two")])
    assert done.state("item2") == "done", done.state("item2")


def ib10():
    n = "run-ib10"
    run = ib_run(n, [ev(1, "gate", n, item="item1", decision="allow"),
                     ev(2, "decision", n, phase="item2", what="a decision on item2"),
                     ev(3, "observation", n, phase="not an item", what="a stray phase")])
    assert run.state("item2") == "running" and "not an item" not in run.item_order, run.item_order
    n = "run-ib10b"
    closed = ib_run(n, [ev(2, "observation", n, phase="item2", what="work on item2"), ev(5, "run-close", n, items="x")])
    assert closed.state("item2") == "unresolved", closed.state("item2")
    assert closed.state("item3") == "skipped", closed.state("item3")


def ib09():
    run = watch.Run("run-ix", REC, os.path.join(ROOT, "vault"))
    middle = "\n".join(watch.render_header(run, room(172), "0"))
    assert "▲%s, before this head: head $1.00" % shown(20) in middle and "supervisor" in middle, middle


check("IB01 (fails on old) a start is activity: a close reads a gated item with no completion unresolved, and a boundary from it or item-done reads done (the control)", ib01)
check("IB02 (fails on old) item-done ends the items it names, long keys included, with no meter, and the feed names them; all done reads green", ib02)
check("IB03 (fails on old) lanes run side by side file under their own --item and start it, the item in hand stands, and a lane with none sits under it marked ~", ib03)
check("IB04 (fails on old) a lane's completed close is no item's completion: its item reads unresolved at the close", ib04)
check("IB05 (fails on old) the overall line gives the date and age of the last item record (control: a run with none)", ib05)
check("IB06 (fails on old) a billed label from another day carries its date in both forms (control: today's carries the time alone)", ib06)
check("IB07 an item-done after the close changes no verdict: the board stays as the close left it", ib07)
check("IB08 a boundary's never-worked target stays skipped, and an explicit item-done on it reads done (the control)", ib08)
check("IB09 (fails on old) a header too narrow for the span keeps before this head while elapsed and the supervisor still fit", ib09)
check("IB10 (fails on old) an event whose phase names a planned item starts it, as activity: running, then unresolved at the close, never skipped (control: a phase naming no row adds none)", ib10)
check("IX09 (must fire) a real record's shape: a later expect-items event whose items map declares item2b alone gives item2b a pending row, and the launch-map items no gate or boundary named (item2, item5 to item10) keep none, as the gate reads the map", ix09)
check("IX10 the panel's map is the gate's: latest_expect equals handsoff.py's own declared_items (its source beside this suite, the function alone) on 12 records, a real record's partial map among them; a reader of expect_items on every kind disagrees on that one (control)", ix10)
PY_IX
[ $? -eq 0 ] || { cat "$T/ix.txt"; printf 'PROBE FAILED: the IX fixtures did not finish\n'; exit 2; }
ix_n=0
while IFS= read -r result; do
  case "$result" in
    'ok   '*) ok "${result#ok   }"; ix_n=$((ix_n + 1)) ;;
    'FAIL '*) no "${result#FAIL }"; ix_n=$((ix_n + 1)) ;;
    *) printf 'PROBE FAILED: unexpected IX output: %s\n' "$result"; exit 2 ;;
  esac
done < "$T/ix.txt"
[ "$ix_n" -eq 20 ] || { printf 'PROBE FAILED: the IX block reported %s legs, wanted 20\n' "$ix_n"; exit 2; }

# ---------------------------------------------------------------- leg 10: the write proof
cp -R "$T/store" "$T/ro-store"
chmod -R a-w "$T/ro-store"
robefore=$(find "$T/ro-store" -type f | wc -l | tr -d ' ')
find "$T/ro-store" -type f -print0 | sort -z | xargs -0 shasum | sort > "$T/ro-before.txt"
env LLM_WIKI_STORE="$T/ro-store" AIMYTH_PROJECTS_DIR="$T/projects" AIMYTH_WATCH_NOTIFY=0 \
    COLUMNS=150 LINES=60 python3 -B "$WATCH" --vault "$T/vault" --run run-vocab --once --plain \
    > "$T/ro.txt" 2>&1
rc=$?
roafter=$(find "$T/ro-store" -type f | wc -l | tr -d ' ')
find "$T/ro-store" -type f -print0 | sort -z | xargs -0 shasum | sort > "$T/ro-after.txt"
chmod -R u+w "$T/ro-store"
if [ "$rc" -eq 0 ] && [ "$robefore" -eq "$roafter" ] && [ "$robefore" -gt 0 ] &&
   [ -s "$T/ro-before.txt" ] && cmp -s "$T/ro-before.txt" "$T/ro-after.txt"; then
  ok "a snapshot against a read-only store runs (exit 0); its checksum manifest is unchanged ($robefore files)"
else
  no "the read-only run exited $rc and left $roafter files, wanted $robefore"
fi

manifest > "$T/manifest-after.txt"
grep -v -- '-timeline.txt' "$T/manifest-after.txt" > "$T/manifest-after-inputs.txt"
if cmp -s "$T/manifest-before.txt" "$T/manifest-after-inputs.txt"; then
  ok "the record, the pack and both transcripts are byte-identical after every run"
else
  ok_diff=$(diff "$T/manifest-before.txt" "$T/manifest-after-inputs.txt" | head -3 | tr '\n' '|')
  no "a file the console read changed: $ok_diff"
fi
mb=$(wc -l < "$T/manifest-before.txt" | tr -d ' ')
if [ "$mb" -ge 8 ]; then
  ok "the manifest control covers $mb files (nonzero, so the comparison means something)"
else
  no "the manifest covered $mb files — it proves nothing"
fi
added=$(comm -13 "$T/manifest-before.txt" "$T/manifest-after.txt" | wc -l | tr -d ' ')
# Two closes ran: the hands-off run's and the plain lane run's, one sanctioned report each.
if [ "$added" -eq 2 ] && grep -q -- 'run-vocab-closed-timeline.txt' "$T/manifest-after.txt" &&
   grep -q -- 'run-plain-closed-timeline.txt' "$T/manifest-after.txt"; then
  ok "exactly two files appeared in the fixture store: the two closes' sanctioned timeline reports"
else
  no "$added files appeared in the store, wanted 2 (the two timeline reports)"
fi

python3 -B - "$WATCH" "$T/planted/planted-strays.py" > "$T/writes.txt" 2>&1 <<'PY_WRITE'
"""Every file-mutating call in the file, and whether it sits inside one of the console's two
sanctioned write sites: `write_report` (the close's timeline report) and `save_suite_totals` (the
session view's per-suite denominator cache). A stray is any such call anywhere else."""
import ast
import re
import sys

SANCTIONED = ("write_report", "save_suite_totals")
PATTERN = re.compile(r"""open\([^)]*["'][wax]|os\.(remove|unlink|rename|replace|mkdir|makedirs|"""
                     r"""truncate)|shutil\.(rmtree|move|copy)""")


def scan(path):
    text = open(path, encoding="utf-8").read()
    spans = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name in SANCTIONED:
            spans.append((node.lineno, node.end_lineno))
    inside = stray = 0
    for i, line in enumerate(text.splitlines(), 1):
        if PATTERN.search(line):
            if any(lo <= i <= hi for lo, hi in spans):
                inside += 1
            else:
                stray += 1
    return inside, stray


for arg in sys.argv[1:]:
    inside, stray = scan(arg)
    print("%s: inside=%d stray=%d" % (arg.rsplit("/", 1)[-1], inside, stray))
PY_WRITE
if grep -q '^watch.py: inside=4 stray=0' "$T/writes.txt" &&
   grep -qE '^planted-strays.py: inside=0 stray=[1-9]' "$T/writes.txt"; then
  ok "watch.py's only write calls are the report's two and the totals cache's two; the sweep hits the control"
else
  no "the write sweep says: $(cat "$T/writes.txt" | tr '\n' '|')"
fi

# ---------------------------------------------------------------- result
total=$((pass + fail))
if [ "$fail" -eq 0 ]; then printf 'PASS %s/%s\n' "$pass" "$total"; else printf 'FAIL %s/%s\n' "$fail" "$total"; fi
if [ "$fail" -eq 0 ]; then exit 0; else exit 1; fi
