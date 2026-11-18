#!/usr/bin/env python3
"""test_limit_defaults.py — the suite for limit policy 1 (the hands-off limit defaults): a new run
waits at Claude's 5-hour limit, stands down at Claude's weekly limit, and starts no GPT work at
GPT's weekly limit unless the pre-flight approved credits at run-open.

Run:  python3 test_limit_defaults.py [--wrappers DIR] [--only ID]... [--fixture-root DIR]
      (--wrappers defaults to this file's directory; --only selects groups: B01-B08, B07r, B10-B15,
      R01-R04, I01, T14, T15, W03, W01)

Line 2's replacement design (each Codex lane's own GPT watch, the mode split into GPT_LIMIT_MODE,
GPT_STOP_MODE and GPT_UNREADABLE_MODE, and the review V-T2b's four fixes) adds B11 (the watch:
must fire, must not, cannot decide), B12 (its bound and its exit with the lane), B13 (the mode
split), B14 (a detached refusal writes nothing), B07r (the wait's GPT check retired; it replaces
B07's wait-kill legs) and W03 (no real `claude` or `codex` reachable), and amends B10. A tree
without a constant a leg asks for (the earlier copy has no GPT_STOP_MODE) gets an unchanged mode
copy, so the leg reports FAIL there rather than stopping the suite. A GPT stand-in sequence is
counted from the start check's own call: call 1 is the start check, call 2 the watch's first
reading. The fold of review V-T2b2 (10 November 2026) adds B10.10e to h (a close's watch record
that is empty, unarmed or partial never reads as bounded; the stated stop bound includes the
reading in flight at the crossing) and B12.7 (that bound held in its planted worst case). The
fold of review V-T8-G2 (10 November 2026) adds B15: a stop ends the lane's whole process group by
the id recorded at its start, after the leader has exited and been reaped too, and never signals a
group it cannot prove the lane's own (a reused id).

It never starts a real model, account reading or helper: `claude -p /usage` and `codex
app-server` are stand-ins (USAGE_CLAUDE_BIN, USAGE_CODEX_BIN), the head harness is a stand-in
(--harness-bin), and a Codex lane runs the real wrapper over a stand-in `codex`. Every fixture
lives under one mktemp -d directory inside --fixture-root (default TMPDIR, else /tmp), removed on
exit. Each group carries a planted case that must be caught, a clean case and a positive control
on the same run. The last group proves the suite and the reader wrote nothing beside the
scripts: a checksum-and-mode manifest of the wrappers directory before and after, with a planted
same-length change as its control, and a scan of the reader's source for write calls whose own
planted control must hit. The last line is PASS n/n or FAIL k/n; a broken premise prints PROBE
FAILED and exits 2. Timing bounds below are ceilings set by judgement, unmeasured.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

# B09 (package B2's strict reset parse) is dropped: that design is retired by the owner's words of
# 24 October 2026, and the installed reset parse stays (declared in the checkpoint's LEGS-GONE.md).
# B07's wait-kill legs are gone with the wait's GPT check (line 2's replacement); B07r replaces them.
GROUPS = ("B01", "B02", "B03", "B04", "B04x", "B05", "B05m", "B06", "B07r", "B08", "B10", "B11",
          "B12", "B13", "B14", "B15", "R01", "R02", "R03", "R04", "I01", "T14", "T15", "W03", "W01")
# The earlier copy's single guard constant, named once here: the legs that run on that copy set it
# in a mode copy, and B13.1 reads it 0 times in the five code files of the staged copy.
LEGACY_GUARD = "GPT_" + "GUARD_MODE"
METER = ("billed (list 2001-01-01) · head $12.34 · lanes $4.22 · session $16.56 · rewrites 3 "
         "($0.30) · tool uses/call head 2.00 lanes 4.00 · delegation multi (owner) · lanes 1 "
         "(reasons: (a)×1 (b)×0 (c)×0 (d)×0, none×0) · metered 1 of 1")
NEW_NOTE = ("Lanes: resume each Claude lane (lane.py) that closed with exit class limit after "
            "this head's last start before the stop")
CODEX_NOTE = "A Codex lane's limit close is not resumed by this note: it follows the GPT weekly rule."
OLD_NOTE = "Lanes closed with exit class limit: resume each with lane.py resume"

HEAD_STUB = r'''#!{py}
import json, os, sys, time
d = os.environ["HEAD_STUB_DIR"]
run = os.environ.get("AIMYTH_HANDSOFF_RUN", "none")
rec = os.path.join(os.environ["LLM_WIKI_STORE"], "spawn-records", run + ".jsonl")
cf = os.path.join(d, "count")
n = (int(open(cf).read()) if os.path.exists(cf) else 0) + 1
open(cf, "w").write(str(n))
open(os.path.join(d, "args.%d" % n), "w").write(" ".join(sys.argv[1:]))
open(os.path.join(d, "stdin.%d" % n), "w").write(sys.stdin.read())
def append(ev):
    ev.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z")); ev.setdefault("run", run)
    with open(rec, "a") as h:
        h.write(json.dumps(ev) + "\n")
if "--session-id" in sys.argv:
    append({"event": "gate", "to": "stub-item", "context": 50000})
    # The head's transcript, one parseable session record, where transcript_for finds it (a
    # unique */<sid>.jsonl under the projects root): today's resume of a limit stop requires it
    # (D29, resume_transcript_error), as a real head's harness writes one.
    sid = sys.argv[sys.argv.index("--session-id") + 1]
    tdir = os.path.join(os.environ["AIMYTH_PROJECTS_DIR"], "fixture-vault")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, sid + ".jsonl"), "w") as h:
        h.write(json.dumps({"type": "user", "sessionId": sid, "message": {"role": "user",
                            "content": "fixture"}}) + "\n")
tf = os.path.join(d, "texts.json")
texts = json.load(open(tf)) if os.path.exists(tf) else []
text = texts[n - 1] if n <= len(texts) else None
if text is not None:
    print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                      "result": text}))
    sys.exit(1)
append({"event": "head-exit", "band": 60, "context": "stub", "spent_usd": 1.0, "pack": True})
append({"event": "head-successor", "session_id": "sid-by-the-head", "pid": 1, "budget": 1.0})
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "handed over"}))
'''

CU_STUB = r'''#!{py}
import os, sys
d = os.environ["CU_STUB_DIR"]
cf = os.path.join(d, "count")
n = (int(open(cf).read()) if os.path.exists(cf) else 0) + 1
open(cf, "w").write(str(n))
mode = open(os.path.join(d, "mode")).read().strip() if os.path.exists(os.path.join(d, "mode")) else "text"
if mode == "fail":
    sys.stderr.write("stand-in: not logged in\n")
    sys.exit(1)
sys.stdout.write(open(os.path.join(d, "text")).read())
'''

GPT_STUB = r'''#!{py}
import json, os, signal, subprocess, sys, time
d = os.environ["GPT_STUB_DIR"]
cf = os.path.join(d, "count")
n = (int(open(cf).read()) if os.path.exists(cf) else 0) + 1
open(cf, "w").write(str(n))
def read(name, default):
    p = os.path.join(d, name)
    return open(p).read().strip() if os.path.exists(p) else default
mode = read("mode", "figure")
planted = None
if mode == "sequence":
    # One step per call, by this call's count (call 1 is the start check's reading); the last step
    # repeats. A number is the weekly figure; "fail" and "silent" are those modes for this call.
    steps = json.load(open(os.path.join(d, "figures.json")))
    step = steps[min(n, len(steps)) - 1]
    mode, planted = (step, None) if isinstance(step, str) else ("figure", step)
with open(os.path.join(d, "pids"), "a") as h:
    h.write("server %d reader %d start %.3f call %d\n" % (os.getpid(), os.getppid(), time.time(), n))
def ended(*_):
    # The end stamp, also when the reader ends this stand-in with SIGTERM after its answer.
    with open(os.path.join(d, "pids"), "a") as h:
        h.write("end %d %.3f\n" % (os.getpid(), time.time()))
    os._exit(0)
signal.signal(signal.SIGTERM, ended)
if mode == "fail":
    sys.exit(1)
if mode == "silent":
    time.sleep(30)
    sys.exit(0)
if mode == "ignoreterm":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen(["sleep", "30"])
    with open(os.path.join(d, "pids"), "a") as h:
        h.write("child %d\n" % child.pid)
    while True:
        time.sleep(1)
if mode == "delay":
    # A reading that takes delay_s seconds (review V-T2b2, R2): the figure is read at the call's
    # start; on the call switch_call names, the figure file is set to 100 right after that sample,
    # the moment stamped, so the line is crossed while this reading, which reads below, is in flight.
    planted = json.loads(read("figure", "50"))
    if read("switch_call", "") == str(n):
        open(os.path.join(d, "figure"), "w").write("100")
        with open(os.path.join(d, "pids"), "a") as h:
            h.write("switched %d %.3f\n" % (n, time.time()))
    time.sleep(float(read("delay_s", "0")))
for line in sys.stdin:
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if msg.get("id") == 1:
        print(json.dumps({"id": 1, "result": {"userAgent": "stand-in"}}))
    elif msg.get("id") == 2:
        if mode == "badjson":
            print("this is not json {")
            print("{\"id\": 2, \"result\": ")
            sys.stdout.flush()
            time.sleep(30)
            sys.exit(0)
        if mode == "closeduring":
            with open(read("close_record", ""), "a") as h:
                h.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "run": read("close_run", ""),
                                    "event": "run-close"}) + "\n")
        if mode == "closelane":
            # A named lane's close appended while this reading answers (review V-T2b, Claim 12).
            with open(read("close_record", ""), "a") as h:
                h.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "run": read("close_run", ""),
                                    "lane": read("close_lane", ""), "harness": "codex",
                                    "event": "lane-closed", "exit_class": "completed"}) + "\n")
        if mode == "result":
            result = json.load(open(os.path.join(d, "result.json")))
        else:
            figure = planted if planted is not None else json.loads(read("figure", "50"))
            result = {"rateLimits": {
                "primary": {"usedPercent": 10, "windowDurationMins": 300, "resetsInSeconds": 3600},
                "secondary": {"usedPercent": figure, "windowDurationMins": 10080,
                              "resetsAt": int(time.time()) + 86400}}}
        print(json.dumps({"id": 2, "result": result}))
    sys.stdout.flush()
ended()
'''

CODEX_STUB = r'''#!{py}
import json, os, signal, sys, time
if sys.argv[1:2] == ["--version"]:
    print("codex-cli 0.0.0-stand-in")
    sys.exit(0)
d = os.environ["CODEX_STUB_DIR"]
if os.path.exists(os.path.join(d, "ignore_term")):
    # A lane that ignores SIGTERM (B12.7), so a stop takes codex-lane.py's whole KILL_GRACE_S.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
mode = open(os.path.join(d, "mode")).read().strip() if os.path.exists(os.path.join(d, "mode")) else "ok"
out = None
for i, a in enumerate(sys.argv):
    if a == "-o" and i + 1 < len(sys.argv):
        out = sys.argv[i + 1]
sys.stdin.read()
cf = os.path.join(d, "count")
n = (int(open(cf).read()) if os.path.exists(cf) else 0) + 1
open(cf, "w").write(str(n))
print(json.dumps({"type": "thread.started", "thread_id": "thread-stand-in"}), flush=True)
if os.path.exists(os.path.join(d, "term_child")):
    # A tool command in the lane's group that ignores SIGTERM (B15.2, review V-T8-G2 point 8); it
    # writes its pid once its handler is set, so a stop never reaches it before then.
    import subprocess
    subprocess.Popen([sys.executable, "-B", "-c", "import os, signal, sys, time; "
                      "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                      "open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(60)",
                      os.path.join(d, "term_child.pid")])
if mode == "slow":
    time.sleep(60)
if os.path.exists(os.path.join(d, "sleep_s")):
    # A lane that runs a set time, silent after thread.started (line 2's replacement legs).
    time.sleep(float(open(os.path.join(d, "sleep_s")).read().strip()))
    open(os.path.join(d, "exited"), "a").write("%d %.3f\n" % (os.getpid(), time.time()))
print(json.dumps({"type": "turn.started"}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 40,
                                                      "cache_write_input_tokens": 0, "output_tokens": 7,
                                                      "reasoning_output_tokens": 3}}), flush=True)
if out:
    open(out, "w").write("OK\n")
'''

# B15 (review V-T8-G2 point 8): a stop through codex-lane.py's Runner._kill, on a runner built by
# hand around a stand-in lane (a leader in its own session, as run_process starts codex, with one
# child), each case in a fresh process so its module load and any spy stay there. Prints one JSON
# object. Every process it starts is killed by its known group id before it ends; `work` is a
# fixture folder for the children's pid files.
STOP_PROBE = r'''
import importlib.util, json, os, signal, subprocess, sys, time
tree, case, work = sys.argv[1], sys.argv[2], sys.argv[3]
sys.dont_write_bytecode = True
sys.path.insert(0, tree)
spec = importlib.util.spec_from_file_location("codex_lane_stop_probe", os.path.join(tree, "codex-lane.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
out = {"case": case}

def group(tag, child_ignores_term):
    ready = os.path.join(work, tag + ".member")
    child = ("import os, signal, time\n"
             + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if child_ignores_term else "")
             + "open(%r, 'w').write(str(os.getpid()))\ntime.sleep(60)\n" % ready)
    lead = "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-B', '-c', %r])\ntime.sleep(60)\n" % child
    p = subprocess.Popen([sys.executable, "-B", "-c", lead], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.monotonic() + 10
    while time.monotonic() < end and not (os.path.exists(ready) and open(ready).read().strip()):
        time.sleep(0.02)
    return p, int(open(ready).read())

def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def gone_within(pid, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end and alive(pid):
        time.sleep(0.05)
    return not alive(pid)

def runner(process):
    r = m.Runner.__new__(m.Runner)
    r.process, r.owner = process, None
    if hasattr(m.Runner, "_group_at_start"):
        r.pgid = m.Runner._group_at_start(r)      # as run_process records it at the start
    return r

def cleanup(*procs):
    for p in procs:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        p.wait(timeout=10)

if case in ("member", "polite"):
    p, member = group(case, case == "member")
    try:
        r = runner(p)
        m.Runner._kill(r, "gpt-watch", explicit=True, reason="suite stop probe")
        p.wait(timeout=10)
        out.update(leader_exit=p.returncode, member_gone=gone_within(member, 3),
                   stop_group=getattr(r, "stop_group", None))
    finally:
        cleanup(p)
elif case == "reused":
    # The lane's leader exited and was reaped before the stop; its pid now stands, by a spy, for
    # a process in another group (987654, a stand-in id no call may name). The spy records every
    # killpg and kill and sends nothing.
    p = subprocess.Popen([sys.executable, "-B", "-c", "pass"], start_new_session=True)
    r = runner(p)
    p.wait(timeout=10)
    calls, real = [], (os.killpg, os.kill, os.getpgid)
    os.killpg = lambda g, s: calls.append(["killpg", g, int(s)])
    os.kill = lambda q, s: calls.append(["kill", q, int(s)])
    os.getpgid = lambda q: 987654 if q == p.pid else real[2](q)
    try:
        m.Runner._kill(r, "gpt-watch", explicit=True, reason="suite stop probe")
    finally:
        os.killpg, os.kill, os.getpgid = real
    out.update(calls=calls, stop_group=getattr(r, "stop_group", None))
elif case == "decoy":
    # The lane's group is seen while its leader is unreaped, then ends whole and its leader is
    # reaped; a live, unrelated group (its member ignoring SIGTERM) then holds the id the runner
    # recorded, as a reused id would. Real signals: the decoy must outlive the stop.
    p, member = group("lane", False)
    r = runner(p)
    if hasattr(m.Runner, "_census_group"):
        m.Runner._census_group(r)
    cleanup(p)
    gone_within(member, 3)
    d, dmember = group("decoy", True)
    try:
        r.pgid = d.pid
        m.Runner._kill(r, "gpt-watch", explicit=True, reason="suite stop probe")
        time.sleep(0.3)
        out.update(decoy_leader_alive=d.poll() is None, decoy_member_alive=alive(dmember),
                   stop_group=getattr(r, "stop_group", None))
    finally:
        cleanup(d)
print(json.dumps(out))
'''

KILL_STUB = r'''#!{py}
import os, sys
with open(os.environ["KILL_STUB_LOG"], "a") as h:
    h.write(" ".join(sys.argv[1:]) + "\n")
sys.exit(3)
'''

DRIVER = r'''
import argparse, importlib.util, json, os, sys, time
path, call = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("module_under_test", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
def shared(mod):
    load = getattr(mod, "import_usage_windows", None) or getattr(mod, "usage_windows_module", None)
    return load() if load else mod
try:
    if call == "policy":
        events = [json.loads(l) for l in open(m.record_path(args[0])) if l.strip()]
        print(json.dumps(m.run_limit_policy(events, args[0])))
    elif call == "credits":
        rows = [json.loads(l) for l in open(args[1]) if l.strip()]
        print(json.dumps(list(m.credits_approval(args[0], rows))))
    elif call == "parse":
        now_ts, text = args
        t, src = m.parse_reset_text(text, now_ts)
        print(json.dumps({"t": t, "src": src,
                          "next_clock_850": m.next_clock(8, 50, now_ts),
                          "next_clock_759": m.next_clock(7, 59, now_ts)}))
    elif call == "parse_many":
        now_ts, texts = args
        rows = []
        for text in texts:
            t, src = m.parse_reset_text(text, now_ts)
            rows.append({"t": t, "src": src, "date_only": m.date_only_reset(text)})
        print(json.dumps(rows))
    elif call == "parse_clock":
        now_ts, cases = args
        rows = []
        for text, hour, minute in cases:
            t, src = m.parse_reset_text(text, now_ts)
            rows.append({"t": t, "src": src, "date_only": m.date_only_reset(text),
                         "want": None if hour is None else m.next_clock(hour, minute, now_ts)})
        print(json.dumps(rows))
    elif call == "reset_at":
        now_ts, value = args
        print(json.dumps({"t": m.parse_reset_at(value, now_ts)}))
    elif call == "sweep":
        spans, = args
        n, bad = 0, []
        for start, end in spans:
            now = start
            while now <= end:
                for hour in range(24):
                    for minute in (0, 30):
                        n += 1
                        t = m.next_clock(hour, minute, now)
                        lt = time.localtime(t) if t is not None else None
                        skipped = lt is not None and hour == 1 and lt.tm_hour == 2 and lt.tm_mon == 3
                        if (t is None or t <= now or t - now > 25 * 3600
                                or ((lt.tm_hour, lt.tm_min) != (hour, minute) and not skipped)):
                            bad.append([now, hour, minute, t])
                now += 1800
        print(json.dumps({"n": n, "bad": len(bad), "first": bad[:3]}))
    elif call == "zone":
        link, tz = args
        if link is not None:
            m.LOCALTIME_LINK = link
        if tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = tz
        zone = m.local_zone()
        print(json.dumps({"zone": None if zone is None else str(getattr(zone, "key", zone))}))
    elif call == "wait_at":
        import contextlib, io, time as clock
        now_ts, argv = args
        clock.time = lambda: now_ts
        clock.sleep = lambda s: None
        sys.argv = ["handsoff.py"] + argv
        out, rc = io.StringIO(), None
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                rc = m.main()
            except SystemExit as exc:
                rc = exc.code
        print(json.dumps({"rc": rc, "out": out.getvalue()[-600:]}))
    elif call == "bounds":
        # The one runner sits in usage_windows.py (DW-20261021-2); each wrapper reaches it through
        # its own loader, so this reads the very module the wrapper would use.
        print(json.dumps(list(shared(m).usage_check_bounds(
            warn=lambda s: sys.stderr.write(s + "\n")))))
    elif call == "bounded":
        cmd, read_s, reap_s = args
        print(json.dumps(shared(m).bounded_run(cmd, read_s, reap_s)))
    elif call == "reader_object":
        run = {"error": None, "timed_out": False, "rc": 0, "stdout": args[0], "stderr": "",
               "reaped": True}
        print(json.dumps(list(shared(m).reader_object(run, 1))))
    elif call == "service_holds":
        m.service_holds(argparse.Namespace(run=args[0], beat_timeout_s=120), m.record_path(args[0]))
        print(json.dumps("serviced"))
    elif call == "gpt":
        print(json.dumps(list(m.parse_gpt_windows(args[0], 1800000000))))
    elif call == "call":
        # A named module function on JSON arguments (DW-20261021-2's added legs).
        print(json.dumps(getattr(m, args[0])(*args[1:]), default=str))
except AttributeError as exc:
    print(json.dumps({"absent": str(exc)}))
'''


FAULT = '''

# A planted fault, in a throwaway mode copy only (test_limit_defaults.py mode_tree).
_planted_gpt_verdict = gpt_verdict


def gpt_verdict(obj):
    out = _planted_gpt_verdict(obj)
    if out[1] == 77:
        raise %s
    return out
'''


def patch_constants(text, constants, tag):
    """(text, absent names): each named constant's one assignment set to its value; a name the
    text does not assign is returned as absent and left out; two or more assignments are a
    broken premise (Probe)."""
    absent = []
    for name, value in constants.items():
        line = re.compile(r'^%s = ("(?:trial|enforce)"|[0-9]+(?:\.[0-9]+)?)$' % re.escape(name), re.M)
        found = len(line.findall(text))
        if found == 0:
            absent.append(name)
            continue
        if found != 1:
            raise Probe("mode copy %s: %s is assigned %d times, not once" % (tag, name, found))
        new = '"%s"' % value if isinstance(value, str) else repr(value)
        text = line.sub(lambda m: "%s = %s" % (name, new), text)
    return text, absent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stamp(epoch=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() if epoch is None else epoch))


class Probe(Exception):
    pass


class Fx(object):
    """One fixture tree: store, homes, vault, hooks (empty: no watermark hook), stand-ins."""

    def __init__(self, suite, tag):
        self.suite, self.tag = suite, tag
        self.root = tempfile.mkdtemp(prefix="%s-" % tag, dir=suite.root)
        j = lambda *p: os.path.join(self.root, *p)
        self.store, self.home, self.vault = j("store"), j("home"), j("vault")
        self.bin, self.work = j("bin"), j("work")
        self.dirs = {k: j("stub-" + k) for k in ("head", "cu", "gpt", "codex")}
        for p in (j("store", "spawn-records"), self.home, j("codex-home"), j("claude-config"),
                  j("projects"), j("state"), j("vault", ".claude", "agents"), j("hooks"),
                  j("lane-home"), self.bin, self.work, j("handoffs")) + tuple(self.dirs.values()):
            os.makedirs(p, exist_ok=True)
        for cls in ("critic", "builder"):
            with open(j("vault", ".claude", "agents", cls + ".md"), "w") as h:
                h.write("---\nname: %s\ndescription: fixture role\ntools: Read, Grep, Bash\n---\n"
                        "Fixture role.\n" % cls)
        for name, body in (("stubhead", HEAD_STUB), ("cu", CU_STUB), ("gpt-server", GPT_STUB),
                           ("codex", CODEX_STUB)):
            path = j("bin", name)
            with open(path, "w") as h:
                h.write(body.replace("{py}", sys.executable))
            os.chmod(path, 0o755)
        with open(j("bin", "viewer-stub"), "w") as h:
            h.write("#!/bin/sh\nexit 0\n")
        os.chmod(j("bin", "viewer-stub"), 0o755)
        with open(j("brief.md"), "w") as h:
            h.write("Reply with the single word OK.\n")
        with open(j("follow.md"), "w") as h:
            h.write("Follow-up: repeat the word.\n")
        self.set("gpt", "figure", "50")
        self.set("cu", "text", "Current session: 20% used · resets 4am\n"
                               "Current week (all models): 30% used · resets Oct 15\n")

    def path(self, *p):
        return os.path.join(self.root, *p)

    def set(self, stub, name, value):
        with open(os.path.join(self.dirs[stub], name), "w") as h:
            h.write(value)

    def count(self, stub):
        p = os.path.join(self.dirs[stub], "count")
        return int(open(p).read()) if os.path.exists(p) else 0

    def env(self, **extra):
        drop = ("AIMYTH_HANDSOFF", "AIMYTH_HANDSOFF_RUN", "AIMYTH_USAGE_CHECK_TIMEOUT_S",
                "AIMYTH_BEAT_WRAPPER_DIR", "AIMYTH_BEAT_BY", "A3_BEAT_INVOCATION", "PYTHONPATH")
        env = {k: v for k, v in os.environ.items() if k not in drop}
        env.update(LLM_WIKI_STORE=self.store, HOME=self.home, CODEX_HOME=self.path("codex-home"),
                   CLAUDE_CONFIG_DIR=self.path("claude-config"),
                   AIMYTH_PROJECTS_DIR=self.path("projects"), AIMYTH_STATE_DIR=self.path("state"),
                   CLAUDE_PROJECT_DIR=self.vault, LLM_WIKI_LANE_HOME=self.path("lane-home"),
                   AIMYTH_HOOKS_DIR=self.path("hooks"), AIMYTH_CONTEXT_WINDOW="1000000",
                   AIMYTH_BANDS="60,80,90", AIMYTH_VIEWER="none",
                   AIMYTH_VIEWER_CMD=self.path("bin", "viewer-stub"), PYTHONDONTWRITEBYTECODE="1",
                   USAGE_CLAUDE_BIN=self.path("bin", "cu"),
                   USAGE_CODEX_BIN=self.path("bin", "gpt-server"),
                   HEAD_STUB_DIR=self.dirs["head"], CU_STUB_DIR=self.dirs["cu"],
                   GPT_STUB_DIR=self.dirs["gpt"], CODEX_STUB_DIR=self.dirs["codex"])
        # W03: shims named `claude` and `codex` first on PATH for every leg; each logs its argv,
        # so a leg that reached a real model or reader by PATH shows in the shim's log.
        env["PATH"] = self.suite.shims + os.pathsep + env.get("PATH", "")
        env.update({k: str(v) for k, v in extra.items() if v is not None})
        for k, v in extra.items():
            if v is None:
                env.pop(k, None)
        return env

    def record(self, run):
        return os.path.join(self.store, "spawn-records", run + ".jsonl")

    def grants(self, run):
        return os.path.join(self.store, "spawn-records", run + "-grants.json")

    def events(self, run):
        p = self.record(run)
        if not os.path.exists(p):
            return []
        out = []
        for line in open(p, encoding="utf-8"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    def append(self, run, ev):
        ev = dict(ev)
        ev.setdefault("ts", stamp())
        ev.setdefault("run", run)
        with open(self.record(run), "a", encoding="utf-8") as h:
            h.write(json.dumps(ev) + "\n")

    def handoff(self, run):
        p = self.path("handoffs", run + "-handoff.md")
        if not os.path.exists(p):
            with open(p, "w") as h:
                h.write("# Fixture hand-off %s (a suite fixture)\n\n"
                        "## Morning report (rewritten at every boundary)\n"
                        "- **What shipped:** nothing yet.\n- **Waits for you:** nothing yet.\n"
                        "- **Spend against the envelope:** unmetered.\n\n"
                        "## In flight\n- nothing in flight.\n\n"
                        "## Findings ledger (one line per warning · issue · finding · lesson)\n"
                        "| Time | Phase | What | Evidence | Routing |\n|---|---|---|---|---|\n"
                        "| 01:00 | 0 | fixture finding | fixture evidence | no action |\n\n"
                        "## Trace (one row per decision and boundary)\n"
                        "| Time | Item | Decision and its rule | Billed line | Waste so far |\n"
                        "|---|---|---|---|---|\n"
                        "| 01:02 | open → 1 | fixture decision | fixture billed line | fixture waste |\n" % run)
        return p

    def h(self, *args, env=None, timeout=60):
        return self.suite.run([sys.executable, "-B", self.suite.H] + list(args),
                              env or self.env(), timeout, cwd=self.root)

    def c(self, *args, env=None, timeout=90):
        return self.suite.run([sys.executable, "-B", self.suite.C] + list(args),
                              env or self.env(), timeout, cwd=self.root)

    def open_run(self, run, *flags, env=None):
        p = self.h("run-open", "--run", run, "--session", "sid-" + run, "--head", "fixture head",
                   "--regime", "single", "--regime-src", "owner", "--handoff", self.handoff(run),
                   "--detail", "fixture", "--pid", "1", "--model", "fixture-model",
                   "--envelope-usd", "100", "--viewer", "none", *flags, env=env)
        return p

    def legacy_run(self, run, on_limit=None):
        """A run opened before limit policy 1: a planted run-open and, where given, a grants
        file with on_limit and none of the new keys."""
        self.append(run, {"event": "run-open", "session": "sid-" + run, "head": "fixture head",
                          "regime": "single", "regime_src": "owner",
                          "handoff": os.path.realpath(self.handoff(run)), "detail": "legacy",
                          "pid_src": "none", "model": "fixture-model", "model_src": "arg",
                          "envelope_usd": 100.0, "ts": stamp(time.time() - 600)})
        if on_limit:
            with open(self.grants(run), "w") as h:
                json.dump({"run": run, "grants": [], "writes": [], "on_limit": on_limit,
                           "viewer": "none", "network": []}, h)

    def starter(self, run, texts, *extra, env=None, background=False, timeout=90):
        """The supervisor over the stand-in head: the stand-in stops with each text in turn (None
        hands over)."""
        self.set("head", "texts.json", json.dumps(texts))
        for f in os.listdir(self.dirs["head"]):
            if f == "count" or f.startswith("args.") or f.startswith("stdin."):
                os.remove(os.path.join(self.dirs["head"], f))
        self.append(run, {"event": "head-exit", "band": 80, "context": "c", "spent_usd": 5})
        cmd = [sys.executable, "-B", self.suite.H, "_starter", "--run", run, "--handoff",
               self.handoff(run), "--budget", "3.50", "--out", self.path("work", run + ".out"),
               "--wait-s", "5", "--harness-bin", self.path("bin", "stubhead"), "--meter-line",
               METER, "--tick-s", "1"] + list(extra)
        if background:
            return subprocess.Popen(cmd, env=env or self.env(), cwd=self.root,
                                    stdout=open(self.path("work", run + ".starter"), "w"),
                                    stderr=subprocess.STDOUT)
        return self.suite.run(cmd, env or self.env(), timeout, cwd=self.root)

    def head_stdin(self, n):
        p = os.path.join(self.dirs["head"], "stdin.%d" % n)
        return open(p).read() if os.path.exists(p) else None

    def driver(self, module, call, args, env=None):
        p = self.suite.run([sys.executable, "-B", "-c", DRIVER, module, call, json.dumps(args)],
                           env or self.env(), 60, cwd=self.root)
        try:
            return json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"crash": (p.stdout + p.stderr)[-600:]}


def kinds(events, kind, **match):
    return [e for e in events if e.get("event") == kind
            and all(e.get(k) == v for k, v in match.items())]


# Package B's unguarded-lane sentence, as the run report carries it (usage_windows UNGUARDED_SENTENCE).
UNGUARDED_TEXT = "After a Claude weekly stand-down nothing stops GPT work that crosses the line later"


def read_jsonl(path):
    """Every JSON object line of a record, a torn last line skipped (it is read while written)."""
    out = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return None


class Suite(object):
    def __init__(self, args):
        self.args = args
        self.base_W = os.path.realpath(args.wrappers)
        self.use(self.base_W)
        for p in (self.H, self.C, self.R, os.path.join(self.W, "lane.py")):
            if not os.path.isfile(p):
                raise Probe("no %s under --wrappers %s" % (os.path.basename(p), self.W))
        root = args.fixture_root or os.environ.get("TMPDIR") or "/tmp"
        if not os.path.isdir(root):
            raise Probe("the fixture root %s is not a directory" % root)
        self.root = tempfile.mkdtemp(prefix="limit-defaults-", dir=root)
        self.passed = self.failed = 0
        self.denied = []
        self.outcomes = {}   # each stop's result in each mode, read back by B13.4
        self.shims = os.path.join(self.root, "shims")
        os.makedirs(self.shims)
        for name in ("claude", "codex"):
            shim = os.path.join(self.shims, name)
            with open(shim, "w") as h:
                h.write("#!/bin/sh\nprintf '%%s\\n' \"$*\" >> \"%s\"\nexit 3\n"
                        % os.path.join(self.shims, name + ".log"))
            os.chmod(shim, 0o755)

    def use(self, tree):
        """Point every leg at the wrappers in `tree` (the folder itself, or a mode copy)."""
        self.W = tree
        self.H = os.path.join(tree, "handsoff.py")
        self.C = os.path.join(tree, "codex-lane.py")
        self.R = os.path.join(tree, "read-usage.py")

    def mode_tree(self, tag, fault=None, **constants):
        """A throwaway copy of the wrappers folder whose usage_windows.py sets the named constants
        (the mode constants, or a number such as GPT_WATCH_EVERY_S for fast fixtures): production
        code carries no test hook, so another value runs only in a copy. A constant the module does
        not assign at all is a tree that lacks the line (the earlier copy has no GPT_STOP_MODE):
        the copy keeps it unchanged and its legs report FAIL. Two or more assignments are a broken
        premise. `fault` ("raise" or "exit") appends a planted fault to the copy's gpt_verdict: at
        the sentinel figure 77 it raises RuntimeError, or SystemExit(2) as lane.load_record's die()
        does (critic CR-T2b2 finding 2)."""
        if not hasattr(self, "_trees"):
            self._trees = {}
        if tag in self._trees:
            return self._trees[tag]
        dest = os.path.join(self.root, "tree-" + tag)
        shutil.copytree(self.base_W, dest, ignore=shutil.ignore_patterns("__pycache__"))
        path = os.path.join(dest, "usage_windows.py")
        if not os.path.isfile(path):
            # A folder without the line (the base): the copy runs unchanged, so its legs fail
            # where the line is absent rather than stopping the suite.
            self._trees[tag] = dest
            return dest
        text, absent = patch_constants(open(path, encoding="utf-8").read(), constants, tag)
        if fault:
            text += FAULT % ("RuntimeError(\"planted fault at the sentinel figure 77\")"
                             if fault == "raise" else "SystemExit(2)")
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        self.absent = getattr(self, "absent", {})
        self.absent[tag] = absent
        self._trees[tag] = dest
        return dest

    def selected(self, gid):
        return not self.args.only or gid in self.args.only

    def check(self, gid, name, ok, detail=""):
        if ok:
            self.passed += 1
            print("ok   %s %s" % (gid, name), flush=True)
        else:
            self.failed += 1
            print("FAIL %s %s — %s" % (gid, name, str(detail)[:900]), flush=True)

    def run(self, cmd, env, timeout, cwd=None, stdin=None):
        try:
            return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout,
                                  cwd=cwd, stdin=subprocess.DEVNULL if stdin is None else stdin)
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or ""      # bytes on a timeout even under text=True: decode it
            out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
            return subprocess.CompletedProcess(cmd, 124, out, "timed out after %s s" % timeout)

    def reader(self, fx, *args, env=None):
        p = self.run([sys.executable, "-B", self.R] + list(args), env or fx.env(), 60)
        try:
            obj = json.loads(p.stdout) if "json" in args else None
        except ValueError:
            obj = None
        return p, obj

    # ------------------------------------------------------------------ B01 -------------------
    def b01(self):
        fx = Fx(self, "b01")
        p = fx.open_run("rb1")
        events, g = fx.events("rb1"), json.load(open(fx.grants("rb1"))) if os.path.exists(fx.grants("rb1")) else {}
        ro = (kinds(events, "run-open") or [{}])[0]
        want = {"on_limit": "resume", "claude_week_limit": "stop", "gpt_credits_approved": False,
                "limit_policy_version": 1}
        self.check("B01", "a flagless run-open writes on_limit resume (default (limit policy 1)), "
                   "claude_week_limit stop, credits false and version 1 to the file and the event",
                   p.returncode == 0 and all(g.get(k) == v and ro.get(k) == v for k, v in want.items())
                   and ro.get("on_limit_src") == "default (limit policy 1)"
                   and "claude_week_limit stop (default (limit policy 1))" in p.stdout,
                   {"rc": p.returncode, "file": {k: g.get(k) for k in want}, "event": {k: ro.get(k) for k in want},
                    "src": ro.get("on_limit_src"), "out": p.stdout[-300:] + p.stderr[-300:]})
        keys = ("on_limit", "claude_week_limit", "gpt_credits_approved", "limit_policy_version")
        snap = lambda: json.dumps({k: json.load(open(fx.grants("rb1"))).get(k) for k in keys}) \
            if os.path.exists(fx.grants("rb1")) else "absent"
        first = snap()
        steps = [fx.h("grants", "--run", "rb1", "--add-grant", fx.work),
                 fx.h("run-resume", "--run", "rb1", "--session", "sid-rb1b", "--head", "h", "--detail",
                      "rewrite", "--pid", "1", "--add-write", fx.work),
                 fx.h("run-resume", "--run", "rb1", "--session", "sid-rb1c", "--head", "h", "--detail",
                      "keep", "--pid", "1")]
        self.check("B01", "grants --add-grant, a rewriting run-resume and a keeping run-resume carry "
                   "the four keys byte for byte",
                   all(s.returncode == 0 for s in steps) and snap() == first
                   and first == json.dumps({"on_limit": "resume", "claude_week_limit": "stop",
                                            "gpt_credits_approved": False, "limit_policy_version": 1}),
                   {"rcs": [s.returncode for s in steps], "before": first, "after": snap(),
                    "err": [s.stderr[-200:] for s in steps]})
        before = open(fx.grants("rb1"), "rb").read() if os.path.exists(fx.grants("rb1")) else b""
        p = fx.h("grants", "--run", "rb1", "--gpt-credits-approved", "yes")
        after = open(fx.grants("rb1"), "rb").read() if os.path.exists(fx.grants("rb1")) else b""
        self.check("B01", "grants --gpt-credits-approved yes is refused (exit 2) and leaves the file's "
                   "bytes unchanged (the flag's only value is no)",
                   p.returncode == 2 and before == after and before != b"" and "invalid choice: 'yes'" in p.stderr,
                   {"rc": p.returncode, "err": p.stderr[-200:]})
        p1 = fx.open_run("rb1y", "--gpt-credits-approved", "yes")
        y1 = json.load(open(fx.grants("rb1y"))).get("gpt_credits_approved") if os.path.exists(fx.grants("rb1y")) else None
        p2 = fx.h("grants", "--run", "rb1y", "--gpt-credits-approved", "no")
        y2 = json.load(open(fx.grants("rb1y"))).get("gpt_credits_approved") if os.path.exists(fx.grants("rb1y")) else None
        ev = (kinds(fx.events("rb1y"), "grants") or [{}])[-1]
        self.check("B01", "--gpt-credits-approved no after a yes run-open writes false and the grants "
                   "event records it", p1.returncode == 0 and y1 is True and p2.returncode == 0
                   and y2 is False and ev.get("gpt_credits_approved") is False,
                   {"rc": [p1.returncode, p2.returncode], "values": [y1, y2], "event": ev.get("gpt_credits_approved")})
        # A file raised to true by hand after a false run-open.
        if os.path.exists(fx.grants("rb1")):
            g = json.load(open(fx.grants("rb1")))
            g["gpt_credits_approved"] = True
            json.dump(g, open(fx.grants("rb1"), "w"))
        pol = fx.driver(self.H, "policy", ["rb1"])
        cred = fx.driver(self.C, "credits", ["rb1", fx.record("rb1")])
        n4 = "grants true, run-open false: never raised after run-open (N4)"
        self.check("B01", "a file raised to true by hand after a false run-open reads false in "
                   "run_limit_policy and in check_gpt_start's reader, both with the N4 source",
                   pol.get("gpt_credits_approved") is False and pol.get("gpt_credits_approved_src") == n4
                   and cred == [False, n4], {"policy": pol, "codex": cred})
        # A true in a file that existed before run-open is not carried.
        with open(fx.grants("rb1pre"), "w") as h:
            json.dump({"run": "rb1pre", "grants": [], "writes": [], "gpt_credits_approved": True,
                       "claude_week_limit": "wait", "limit_policy_version": 1}, h)
        p = fx.open_run("rb1pre")
        g = json.load(open(fx.grants("rb1pre")))
        self.check("B01", "a true (and a wait) in a grants file written before run-open is not carried",
                   p.returncode == 0 and g.get("gpt_credits_approved") is False
                   and g.get("claude_week_limit") == "stop", {"rc": p.returncode, "file": g})
        # Clean and control.
        p = fx.open_run("rb1set", "--on-limit", "stop", "--claude-week-limit", "wait",
                        "--gpt-credits-approved", "yes")
        g = json.load(open(fx.grants("rb1set"))) if os.path.exists(fx.grants("rb1set")) else {}
        pol = fx.driver(self.H, "policy", ["rb1set"])
        cred = fx.driver(self.C, "credits", ["rb1set", fx.record("rb1set")])
        self.check("B01", "control: run-open --on-limit stop --claude-week-limit wait "
                   "--gpt-credits-approved yes records stop, wait and true, both readers agreeing",
                   p.returncode == 0 and (g.get("on_limit"), g.get("claude_week_limit"),
                                          g.get("gpt_credits_approved")) == ("stop", "wait", True)
                   and pol.get("gpt_credits_approved") is True and cred == [True, "grants true, run-open true"],
                   {"rc": p.returncode, "file": g, "policy": pol, "codex": cred, "err": p.stderr[-200:]})
        fx.legacy_run("rb1leg", on_limit="resume")
        pol = fx.driver(self.H, "policy", ["rb1leg"])
        cred = fx.driver(self.C, "credits", ["rb1leg", fx.record("rb1leg")])
        self.check("B01", "control: a legacy-shaped run (no version, on_limit resume, no new keys) reads "
                   "resume, stop and false, both readers agreeing",
                   (pol.get("on_limit"), pol.get("claude_week_limit"), pol.get("gpt_credits_approved"))
                   == ("resume", "stop", False) and isinstance(cred, list) and cred[0] is False
                   and cred[1] == pol.get("gpt_credits_approved_src"), {"policy": pol, "codex": cred})

    # ------------------------------------------------------------------ B02 -------------------
    def b02(self):
        fx = Fx(self, "b02")
        fx.open_run("rb2")
        iso = stamp(time.time() + 4)
        p = fx.starter("rb2", ["You've hit your session limit · resets %s" % iso])
        ev = fx.events("rb2")
        sc = kinds(ev, "stop-condition")
        self.check("B02", "a default run's session stop waits for the ISO reset and resumes: one "
                   "stop-condition window short, one wait, one head-resumed",
                   p.returncode == 0 and len(sc) == 1 and sc[0].get("which") == "limit"
                   and sc[0].get("window") == "short" and str(sc[0].get("action", "")).startswith("wait until")
                   and len(kinds(ev, "head-resumed")) == 1,
                   {"rc": p.returncode, "sc": sc, "resumed": len(kinds(ev, "head-resumed")),
                    "out": (p.stdout + p.stderr)[-500:]})
        # The cannot-decide case under the installed parser: a session text with no reset and no
        # --probe is limit-unparsed, then successor-aborted; no wait, no resume. (Package B's
        # date-only branch, N12, is reset-text parsing of the retired design and is not taken.)
        fx.open_run("rb2n")
        p = fx.starter("rb2n", ["You've hit your session limit · resets soon"], timeout=30)
        ev = fx.events("rb2n")
        sc = kinds(ev, "stop-condition")
        self.check("B02", "cannot decide: a session stop with no reset and no --probe is limit-unparsed, "
                   "then successor-aborted, with no wait and no resume",
                   len(sc) == 1 and sc[0].get("which") == "limit-unparsed"
                   and not kinds(ev, "head-resumed") and fx.count("head") == 1
                   and len(kinds(ev, "successor-aborted", reason="limit-unparsed")) == 1,
                   {"rc": p.returncode, "sc": sc, "heads": fx.count("head"),
                    "out": (p.stdout + p.stderr)[-300:]})
        env = fx.env(TZ="UTC")
        base = 1791028800.0     # 2026-10-03 12:00:00 UTC
        # B03d (critic CR-T2b finding 7): the installed parser and the dated weekly reset form the
        # account's usage display printed on 9 November 2026 ("resets Nov 15 at 7:59am"). AMPM_RE
        # needs a digit straight after "resets", so the dated text does not parse: under
        # --claude-week-limit wait the supervisor records limit-unparsed and the run ends
        # successor-aborted, with no wait and no reset-timeout. It fails safe (it stops).
        dated = "You've hit your weekly limit · resets Nov 15 at 7:59am (Europe/London)"
        fx.open_run("rb3d", "--claude-week-limit", "wait")
        p = fx.starter("rb3d", [dated], timeout=30)
        ev = fx.events("rb3d")
        sc = kinds(ev, "stop-condition")
        self.check("B03d", "under --claude-week-limit wait the dated weekly reset is limit-unparsed, then "
                   "successor-aborted: no wait, no reset-timeout, no resume",
                   [s.get("which") for s in sc] == ["limit-unparsed"]
                   and len(kinds(ev, "successor-aborted", reason="limit-unparsed")) == 1
                   and not kinds(ev, "successor-aborted", reason="reset-timeout")
                   and not kinds(ev, "head-resumed") and fx.count("head") == 1,
                   {"rc": p.returncode, "sc": sc, "out": (p.stdout + p.stderr)[-300:]})
        r = fx.driver(self.H, "parse", [base, "You've hit your weekly limit · resets 7:59am"], env=env)
        self.check("B03d", "control: a time-of-day weekly reset ('resets 7:59am') goes through next_clock",
                   r.get("t") is not None and r.get("t") == r.get("next_clock_759"), r)
        fx.open_run("rb3e", "--on-limit", "resume")
        p = fx.starter("rb3e", [dated.replace("weekly", "session")], timeout=30)
        sc = kinds(fx.events("rb3e"), "stop-condition")
        self.check("B03d", "pin of today's parse: in an --on-limit resume run the same dated reset on a "
                   "session text is limit-unparsed too (the installed parser, unchanged)",
                   [s.get("which") for s in sc] == ["limit-unparsed"],
                   {"rc": p.returncode, "sc": sc, "out": (p.stdout + p.stderr)[-300:]})
        r = fx.driver(self.H, "parse", [base, "You've hit your session limit · resets 8:50am (Europe/London)"], env=env)
        self.check("B02", "control: 'resets 8:50am (Europe/London)' goes through next_clock",
                   r.get("t") is not None and r.get("t") == r.get("next_clock_850"), r)
        r = fx.driver(self.H, "parse", [base, "resets 2026-10-03T13:00:00Z"], env=env)
        self.check("B02", "control: an ISO time stays ISO", str(r.get("src", "")).startswith("stop text ISO"), r)
        fx.open_run("rb2s", "--on-limit", "stop")
        p = fx.starter("rb2s", ["You've hit your session limit · resets %s" % stamp(time.time() + 4)])
        ev = fx.events("rb2s")
        sd = kinds(ev, "supervisor-stood-down")
        self.check("B02", "control: --on-limit stop stands down and starts no further head",
                   p.returncode == 0 and len(sd) == 1 and sd[0].get("reason") == "limit-stop"
                   and fx.count("head") == 1 and not kinds(ev, "head-resumed"),
                   {"rc": p.returncode, "sd": sd, "heads": fx.count("head")})
        fx.open_run("rb2m")
        proc = fx.starter("rb2m", ["You've hit your session limit · resets %s" % stamp(time.time() + 20)],
                          background=True)
        deadline = time.time() + 15
        while time.time() < deadline and not kinds(fx.events("rb2m"), "stop-condition"):
            time.sleep(0.3)
        stopped = fx.h("supervise", "--stop", "--run", "rb2m")
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        ev = fx.events("rb2m")
        sd = kinds(ev, "supervisor-stood-down")
        self.check("B02", "control: a stop marker during the wait stands the supervisor down",
                   stopped.returncode == 0 and len(sd) == 1 and sd[0].get("reason") == "stopped"
                   and not kinds(ev, "head-resumed"), {"stop": stopped.returncode, "sd": sd,
                                                       "err": stopped.stderr[-200:]})

    # ------------------------------------------------------------------ B09 -------------------
    def b09(self):
        # NEVER RUN (DW-20261021-2): package B2's strict reset parse is retired by the owner's
        # words of 24 October 2026; B09 is out of GROUPS and is kept only as the record of what
        # that design tested (declared in the checkpoint's LEGS-GONE.md).
        """HD-14: the reset clause matched whole against the accepted forms (CR-MET-BA3 F1), and
        next_clock on the next local calendar date (F2)."""
        import calendar
        fx = Fx(self, "b9")
        utc, london = fx.env(TZ="UTC"), fx.env(TZ="Europe/London")
        base = 1791028800.0     # 2026-10-03 12:00:00 UTC, B02's reading
        g = lambda *t: float(calendar.timegm(t + (0,) * (6 - len(t))))
        when = lambda ts: time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts))
        # F1: the malformed forms CR-MET-BA3 reproduced (the first three), then those this fold
        # found; build-B read each as a time (a valid prefix, or an invalid meridian hour).
        malformed = ("resets Oct 22 at 8/ 30pm", "resets Oct 22 at 8:30 p . m.", "resets 13am",
                     "resets 8/ 30pm", "resets 0am", "resets 0pm", "resets 13:30pm", "resets 00:30am",
                     "resets 8 - 30pm", "resets 8 / 30pm", "resets 8 ; 30pm", "resets 8 · 30pm",
                     "resets Oct 22 at 8 - 30pm", "resets Oct 22 at 8 · 30pm",
                     "resets Oct 22 at 8:30 P . M .", "resets at 8pm on Oct 22",
                     "resets Oct 5 at 20:30 a week on", "resets 8 (30pm)", "resets 8. (30pm)")
        got = fx.driver(self.H, "parse_many", [base, list(malformed)], env=utc)
        for i, text in enumerate(malformed):
            r = got[i] if isinstance(got, list) and i < len(got) else got
            self.check("B09", "strict parse (F1): %r matches no accepted form whole: unparsed and not "
                       "date-only" % text, isinstance(r, dict) and "t" in r and r.get("t") is None
                       and r.get("date_only") is None, r)
        guards = ("resets 8:30 p . m.", "resets 8:30 a . m .", "resets 8:30 m", "resets 8:30 PMX",
                  "resets Oct 22 at 13:30pm", "resets 24:00", "resets 8:60pm")
        got = fx.driver(self.H, "parse_many", [base, list(guards)], env=utc)
        self.check("B09", "strict parse guard: the %d malformed texts build-B already refused stay "
                   "unparsed" % len(guards), isinstance(got, list) and len(got) == len(guards)
                   and all(r.get("t") is None and r.get("date_only") is None for r in got), got)
        # Valid controls of every accepted form and trailer: their own time and source string.
        oct26 = g(2026, 10, 26)
        dated = (("resets Oct 26 at 5:59pm", 64740, "resets Oct 26 at 5:59pm"),
                 ("resets Oct 26, 5:59pm", 64740, "resets Oct 26, 5:59pm"),
                 ("resets on Oct 26 at 5:59 pm", 64740, "resets on Oct 26 at 5:59 pm"),
                 ("resets Oct. 26 at 17:59", 64740, "resets Oct. 26 at 17:59"),
                 ("resets Oct 26 5pm", 61200, "resets Oct 26 5pm"),
                 ("resets Oct 26 at 5:59pm (Europe/London)", 64740, "resets Oct 26 at 5:59pm"),
                 ("resets Oct 26 at 5:59pm BST (Europe/London)", 64740, "resets Oct 26 at 5:59pm"),
                 ("resets Oct 26 at 5:59pm ∙ /upgrade", 64740, "resets Oct 26 at 5:59pm"))
        got = fx.driver(self.H, "parse_many", [base, [t for t, _, _ in dated]], env=utc)
        for i, (text, offset, src) in enumerate(dated):
            r = got[i] if isinstance(got, list) and i < len(got) else got
            self.check("B09", "accepted dated form %r gives Oct 26 %02d:%02d, source %r"
                       % (text, offset // 3600, offset % 3600 // 60, src),
                       isinstance(r, dict) and r.get("t") == oct26 + offset
                       and r.get("src") == "stop text '%s'" % src, r)
        timed = (("resets 8:30pm", 20, 30, "resets 8:30pm"), ("resets 8 pm", 20, 0, "resets 8 pm"),
                 ("resets 8:30 pm", 20, 30, "resets 8:30 pm"), ("resets at 9am.", 9, 0, "resets at 9am"),
                 ("resets 3:50am (Europe/London)", 3, 50, "resets 3:50am"),
                 ("resets 8:30pm BST", 20, 30, "resets 8:30pm"),
                 ("resets 8pm · /upgrade", 20, 0, "resets 8pm"),
                 ("resets 8pm · 2 lanes open", 20, 0, "resets 8pm"),
                 ("resets 8pm; 2 lanes open", 20, 0, "resets 8pm"), ("resets 00:30", 0, 30, "resets 00:30"),
                 ("resets 12:59am", 0, 59, "resets 12:59am"), ("resets 1am", 1, 0, "resets 1am"),
                 ("resets 08:30pm", 20, 30, "resets 08:30pm"),
                 ("You've hit your session limit · resets 8:50am (Europe/London)", 8, 50, "resets 8:50am"),
                 ("You have reached your usage limit for this session; it resets at 9am.", 9, 0, "resets at 9am"))
        got = fx.driver(self.H, "parse_clock", [base, [[t, h, mi] for t, h, mi, _ in timed]], env=utc)
        for i, (text, hour, minute, src) in enumerate(timed):
            r = got[i] if isinstance(got, list) and i < len(got) else got
            self.check("B09", "accepted time-only form %r gives next_clock(%02d:%02d), source %r"
                       % (text, hour, minute, src), isinstance(r, dict) and r.get("t") is not None
                       and r.get("t") == r.get("want") and r["t"] > base
                       and r.get("src") == "stop text '%s'" % src, r)
        got = fx.driver(self.H, "parse_many", [base, ["resets 15 OCT", "resets Oct 15"]], env=utc)
        self.check("B09", "control: a day before an upper-case month and a date with no time are "
                   "date-only, never 15:00", isinstance(got, list)
                   and [r.get("t") for r in got] == [None, None]
                   and [r.get("date_only") for r in got] == ["resets 15 OCT", "resets Oct 15"], got)
        # F2 (Europe/London: clocks go back at 02:00 BST on Sunday 25 October 2026 and forward at
        # 01:00 GMT on Sunday 28 March 2027).
        clock = ((g(2026, 10, 25, 23, 30), "resets 00:00", g(2026, 10, 26), "F2: at 23:30 GMT on 25 October"),
                 (g(2026, 10, 25, 23, 30), "resets 12am", g(2026, 10, 26), "F2, the meridian form: at 23:30 GMT on 25 October"),
                 (g(2026, 10, 24, 22, 30), "resets 00:00", g(2026, 10, 24, 23), "control, the day before: at 23:30 BST on 24 October"),
                 (g(2026, 10, 26, 23, 30), "resets 00:00", g(2026, 10, 27), "control, the day after: at 23:30 GMT on 26 October"),
                 (g(2026, 10, 24, 11), "resets 11am", g(2026, 10, 25, 11), "across the change back: at 12:00 BST on 24 October"),
                 (g(2027, 3, 27, 12), "resets 11am", g(2027, 3, 28, 10), "across the change forward: at 12:00 GMT on 27 March 2027"),
                 (g(2026, 10, 25, 0, 45), "resets Oct 25 at 1:30am", g(2026, 10, 25, 1, 30),
                  "a wall time that occurs twice is its later instant: at 01:45 BST on 25 October"),
                 (g(2027, 3, 28, 0, 30), "resets 1:30am", g(2027, 3, 28, 1, 30),
                  "a wall time the change skips is placed past the gap: at 00:30 GMT on 28 March 2027"))
        for now_ts, text, want, name in clock:
            r = fx.driver(self.H, "parse", [now_ts, text], env=london)
            t = r.get("t") if isinstance(r, dict) else None
            self.check("B09", "%s, %r gives %s, %d s ahead" % (name, text, when(want), want - now_ts),
                       t == want and t > now_ts, r)
        r = fx.driver(self.H, "reset_at", [g(2026, 10, 25, 23, 30), "00:00"], env=london)
        self.check("B09", "F2, the owner's --reset-at 00:00 at 23:30 GMT on 25 October gives 26 October "
                   "00:00 GMT", isinstance(r, dict) and r.get("t") == g(2026, 10, 26), r)
        spans = [[g(2026, 10, 24, 12), g(2026, 10, 26, 12)], [g(2027, 3, 27, 12), g(2027, 3, 29, 12)]]
        r = fx.driver(self.H, "sweep", [spans], env=london)
        self.check("B09", "F2 sweep over both change weekends (every 30 min, 48 wall times): always ahead, "
                   "at most 25 h on, at its own wall time except in the skipped hour (control: 9312 "
                   "calls counted)", isinstance(r, dict) and r.get("n") == 9312 and r.get("bad") == 0, r)
        posix = fx.env(TZ="GMT0BST,M3.5.0/1,M10.5.0")
        r = fx.driver(self.H, "parse", [g(2026, 10, 25, 23, 30), "resets 00:00"], env=posix)
        self.check("B09", "F2 under a POSIX TZ rule (the time module's zone, on calendar dates): 26 "
                   "October 00:00 GMT", isinstance(r, dict) and r.get("t") == g(2026, 10, 26), r)
        lnk, plain = fx.path("localtime-link"), fx.path("localtime-plain")
        os.symlink("/usr/share/zoneinfo/Europe/London", lnk)
        os.symlink("/no/zone/here", plain)
        rows = [fx.driver(self.H, "zone", [link, tz], env=utc)
                for link, tz in ((lnk, None), (plain, None), (None, ":Europe/London"),
                                 (None, "GMT0BST,M3.5.0/1,M10.5.0"), (None, "Europe/London"))]
        self.check("B09", "the zone: TZ unset reads the system link's zone (a fixture link), an unlinked "
                   "one and a POSIX rule leave it to the time module, TZ ':Europe/London' and "
                   "'Europe/London' name it", [r.get("zone") if isinstance(r, dict) else r for r in rows]
                   == ["Europe/London", None, "Europe/London", None, "Europe/London"], rows)
        # The hand-run wait-reset at the fixture time stays pending; it never reaches a reset placed
        # in the past (CR-MET-BA3: exit 0 and "reset reached ... after 0 s").
        for i, (now_ts, name) in enumerate(((g(2026, 10, 25, 23, 30), "at 23:30 GMT on 25 October"),
                                            (g(2026, 10, 24, 22, 30), "(control) at 23:30 BST on 24 October"),
                                            (g(2026, 10, 26, 23, 30), "(control) at 23:30 GMT on 26 October"))):
            run = "rb9c%d" % i
            fx.open_run(run)
            r = fx.driver(self.H, "wait_at", [now_ts, ["wait-reset", "--run", run, "--stop-text",
                                                       "You've hit your session limit · resets 00:00"]], env=london)
            reached = [e for e in kinds(fx.events(run), "observation", what="wait-reset ended")
                       if "reset reached" in str(e.get("note"))]
            self.check("B09", "the hand-run wait-reset %s on 'resets 00:00' stays pending: exit 8, "
                       "still-running 1800, no reached reset" % name,
                       isinstance(r, dict) and r.get("rc") == 8 and "still-running 1800" in str(r.get("out"))
                       and not reached, {"r": r, "reached": reached})
        # No malformed text produces a reached reset or a resume: CR-MET-BA3's dated forms with
        # yesterday's date, in the supervisor and the hand-run wait-reset, and a time-only 13am.
        lt = time.localtime(time.time() - 86400)
        yday = "%s %d" % (("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                           "Dec")[lt.tm_mon - 1], lt.tm_mday)
        for i, clock_text in enumerate(("8/ 30pm", "8:30 p . m.")):
            text = "You've hit your session limit · resets %s at %s" % (yday, clock_text)
            run, hand = "rb9f%d" % i, "rb9g%d" % i
            fx.open_run(run)
            p = fx.starter(run, [text])
            ev = fx.events(run)
            sc = kinds(ev, "stop-condition")
            reached = [e for e in kinds(ev, "observation", what="wait-reset ended")
                       if "reset reached" in str(e.get("note"))]
            self.check("B09", "no reached reset (F1): the supervisor on %r (yesterday) stands down "
                       "limit-unparsed, no resume" % text[-26:],
                       len(sc) == 1 and sc[0].get("which") == "limit-unparsed" and not reached
                       and not kinds(ev, "head-resumed") and fx.count("head") == 1
                       and len(kinds(ev, "successor-aborted", reason="limit-unparsed")) == 1,
                       {"rc": p.returncode, "sc": sc, "reached": reached, "heads": fx.count("head"),
                        "out": (p.stdout + p.stderr)[-300:]})
            fx.open_run(hand)
            q = fx.h("wait-reset", "--run", hand, "--stop-text", text)
            ev = fx.events(hand)
            sc = kinds(ev, "stop-condition")
            reached = [e for e in kinds(ev, "observation", what="wait-reset ended")
                       if "reset reached" in str(e.get("note"))]
            self.check("B09", "no reached reset (F1): the hand-run wait-reset on %r (yesterday) records "
                       "limit-unparsed, exit 7" % text[-26:],
                       q.returncode == 7 and len(sc) == 1 and sc[0].get("which") == "limit-unparsed"
                       and not reached, {"rc": q.returncode, "sc": sc, "reached": reached,
                                         "out": (q.stdout + q.stderr)[-300:]})
        fx.open_run("rb9t")
        q = fx.h("wait-reset", "--run", "rb9t", "--stop-text", "You've hit your session limit · resets 13am",
                 "--max-block-s", "1", timeout=30)
        sc = kinds(fx.events("rb9t"), "stop-condition")
        self.check("B09", "no wait on an invalid meridian hour (F1): the hand-run wait-reset reads "
                   "'resets 13am' as limit-unparsed, exit 7",
                   q.returncode == 7 and len(sc) == 1 and sc[0].get("which") == "limit-unparsed",
                   {"rc": q.returncode, "sc": sc, "out": (q.stdout + q.stderr)[-300:]})

    # ------------------------------------------------------------------ B03 -------------------
    def b03(self):
        fx = Fx(self, "b03")
        texts = ["You've hit your weekly limit · resets %s", "You've reached your limit for this week · resets %s",
                 "Your 7-day limit is reached · resets %s"]
        for shape in ("legacy", "new"):
            for i, t in enumerate(texts):
                run = "rb3%s%d" % (shape[0], i)
                if shape == "legacy":
                    fx.legacy_run(run, on_limit="resume")
                else:
                    fx.open_run(run)
                p = fx.starter(run, [t % stamp(time.time() + 3)])
                ev = fx.events(run)
                sd, sc = kinds(ev, "supervisor-stood-down"), kinds(ev, "stop-condition")
                self.check("B03", "regression trap (%s, on_limit resume): %r stands down limit-weekly "
                           "with zero wait, probe, resume, successor or model swap" % (shape, t[:40]),
                           p.returncode == 0 and len(sd) == 1 and sd[0].get("reason") == "limit-weekly"
                           and sd[0].get("waited_s") == 0 and len(sc) == 1 and sc[0].get("window") == "week"
                           and sc[0].get("action") == "stand-down: claude_week_limit stop"
                           and not kinds(ev, "head-resumed") and fx.count("head") == 1
                           and len(kinds(ev, "head-successor")) == 1
                           and not kinds(ev, "observation", what="wait-reset probe"),
                           {"rc": p.returncode, "sd": sd, "sc": sc, "heads": fx.count("head"),
                            "out": (p.stdout + p.stderr)[-300:]})
        fx.open_run("rb3s")
        p = fx.starter("rb3s", ["You've hit your session limit · resets %s" % stamp(time.time() + 3)])
        self.check("B03", "control: a session text in a default run resumes",
                   p.returncode == 0 and len(kinds(fx.events("rb3s"), "head-resumed")) == 1,
                   {"rc": p.returncode, "out": (p.stdout + p.stderr)[-300:]})
        fx.open_run("rb3w", "--claude-week-limit", "wait")
        p = fx.starter("rb3w", ["You've hit your weekly limit · resets %s" % stamp(time.time() + 3)])
        ev = fx.events("rb3w")
        self.check("B03", "control: with --claude-week-limit wait a weekly text a few seconds ahead "
                   "waits and resumes", p.returncode == 0 and len(kinds(ev, "head-resumed")) == 1
                   and (kinds(ev, "stop-condition") or [{}])[0].get("window") == "week",
                   {"rc": p.returncode, "sc": kinds(ev, "stop-condition"), "out": (p.stdout + p.stderr)[-300:]})
        fx.open_run("rb3t", "--claude-week-limit", "wait")
        p = fx.starter("rb3t", ["You've hit your weekly limit · resets %s" % stamp(time.time() + 120)],
                       "--max-wait-s", "5")
        ev = fx.events("rb3t")
        ab = kinds(ev, "successor-aborted")
        self.check("B03", "control: a weekly reset past --max-wait-s ends reset-timeout",
                   ab and ab[-1].get("reason") == "reset-timeout" and not kinds(ev, "head-resumed"),
                   {"rc": p.returncode, "aborted": ab})

    # ------------------------------------------------------------------ B04 -------------------
    def b04(self):
        fx = Fx(self, "b04")
        unq = "You've hit your usage limit · resets %s"
        cases = [("week 100", "Current session: 20% used · resets 4am\nCurrent week (all models): 100% used · resets Oct 15\n",
                  "text", "limit-weekly", 0),
                 ("session 100, week 40", "Current session: 100% used · resets 4am\nCurrent week (all models): 40% used · resets Oct 15\n",
                  "text", None, 1),
                 ("both below", "Current session: 30% used · resets 4am\nCurrent week (all models): 40% used · resets Oct 15\n",
                  "text", "limit-unclassified", 0),
                 ("a failing reader", "", "fail", "limit-unclassified", 0)]
        for i, (label, text, mode, reason, resumed) in enumerate(cases):
            run = "rb4%d" % i
            fx.open_run(run)
            fx.set("cu", "text", text)
            fx.set("cu", "mode", mode)
            before = fx.count("cu")
            p = fx.starter(run, [unq % stamp(time.time() + 3)])
            ev = fx.events(run)
            sd, sc = kinds(ev, "supervisor-stood-down"), kinds(ev, "stop-condition")
            ok = p.returncode == 0 and fx.count("cu") - before == 1 and len(kinds(ev, "head-resumed")) == resumed
            if reason:
                ok = ok and len(sd) == 1 and sd[0].get("reason") == reason
            if mode == "fail":
                ok = ok and "not logged in" in json.dumps(sc)
            self.check("B04", "an unqualified stop takes one reading (%s): %s, the stand-in read once"
                       % (label, reason or "wait and resume"), ok,
                       {"rc": p.returncode, "reads": fx.count("cu") - before, "sd": sd, "sc": sc,
                        "out": (p.stdout + p.stderr)[-300:]})
        fx.set("cu", "mode", "text")
        fx.open_run("rb4m")
        before = fx.count("cu")
        p = fx.starter("rb4m", ["You've reached your Fable limit. Switch to another model, or manage usage "
                                "credits at claude.ai/settings/usage, to continue."])
        ev = fx.events("rb4m")
        self.check("B04", "control: a model-scoped text takes no reading and keeps the limit-model path",
                   fx.count("cu") == before and kinds(ev, "stop-condition", which="limit-model"),
                   {"reads": fx.count("cu") - before, "sc": kinds(ev, "stop-condition")})
        fx.open_run("rb4s")
        before = fx.count("cu")
        p = fx.starter("rb4s", ["You've hit your session limit · resets %s" % stamp(time.time() + 3)])
        self.check("B04", "control: a session text takes no reading",
                   fx.count("cu") == before and len(kinds(fx.events("rb4s"), "head-resumed")) == 1,
                   {"reads": fx.count("cu") - before, "rc": p.returncode})

    # ------------------------------------------------------------------ B05 -------------------
    def spawn(self, fx, run, lane, *extra, env=None):
        return fx.c("spawn", "--run", run, "--lane", lane, "--codex", fx.path("bin", "codex"),
                    "--class", "critic", "--brief", fx.path("brief.md"), "--cwd", fx.work,
                    "--reason", "(a) suite", "--choice-reason", "suite pick", "--delegation",
                    "single", "--delegation-src", "head", "--viewer", "none", "--silence-s", "0",
                    "--deadline-s", "60", *extra, env=env)

    def journals(self, fx, run):
        ns = fx.record(run) + ".a3"
        out = []
        for base, _, files in os.walk(ns):
            out += sorted(os.path.join(base, f) for f in files if not f.endswith(".lock"))
        return out

    def b05(self):
        fx = Fx(self, "b05")
        fx.open_run("rb5")
        fx.set("gpt", "figure", "50")
        p = self.spawn(fx, "rb5", "L1")
        self.check("B05", "premise: a spawn at 50 runs and closes (the lane later resumed and beaten)",
                   p.returncode == 0 and kinds(fx.events("rb5"), "lane-closed"),
                   {"rc": p.returncode, "err": p.stderr[-400:]})
        for figure in ("100", "101"):
            fx.set("gpt", "figure", figure)
            for label, args in (("spawn", ("spawn",)), ("detached spawn", ("spawn", "--detach", "--no-wait")),
                                ("staged spawn", ("spawn", "--stage-from")),
                                ("real resume", ("resume",)), ("direct beat", ("beat",))):
                before = open(fx.record("rb5"), "rb").read()
                jbefore = self.journals(fx, "rb5")
                lane = "S%s%d" % (figure, len(label))
                stage = os.path.join(fx.store, "spawn-records", "rb5-cwd-%s" % lane)
                if args[0] == "spawn" and "--stage-from" in args:
                    src = fx.path("src-tree")
                    os.makedirs(src, exist_ok=True)
                    open(os.path.join(src, "f.txt"), "w").write("x")
                    p = fx.c("spawn", "--run", "rb5", "--lane", lane, "--codex", fx.path("bin", "codex"),
                             "--class", "critic", "--brief", fx.path("brief.md"), "--stage-from", src,
                             "--reason", "(a) suite", "--choice-reason", "suite pick", "--delegation",
                             "single", "--delegation-src", "head", "--viewer", "none", "--silence-s", "0",
                             "--deadline-s", "60")
                elif args[0] == "spawn":
                    p = self.spawn(fx, "rb5", lane, *args[1:])
                elif args[0] == "resume":
                    p = fx.c("resume", "--run", "rb5", "--lane", "L1", "--brief", fx.path("follow.md"),
                             "--codex", fx.path("bin", "codex"), "--viewer", "none", "--silence-s", "0",
                             "--deadline-s", "60")
                else:
                    p = fx.c("resume", "--run", "rb5", "--lane", "L1", "--beat", "--viewer", "none")
                after = open(fx.record("rb5"), "rb").read()
                self.check("B05", "%s at %s with credits false exits 2 with the reason, the record's "
                           "bytes and A3 journals unchanged%s" % (label, figure,
                                                                 ", the staged copy released" if "--stage-from" in args else ""),
                           p.returncode == 2 and "approves no credits (N19): no GPT start; nothing written" in p.stderr + p.stdout
                           and ("reads %s %%" % figure) in p.stderr + p.stdout and before == after
                           and self.journals(fx, "rb5") == jbefore and not os.path.exists(stage),
                           {"rc": p.returncode, "err": (p.stderr + p.stdout)[-400:], "same": before == after,
                            "stage": os.path.exists(stage)})
        # N2: a beat issued through service_holds at 100.
        fx.set("gpt", "figure", "100")
        fx.append("rb5", {"event": "hold", "lane": "L1", "cap": 2, "beat_after_s": 1, "by": "head"})
        time.sleep(1.5)
        r = fx.driver(self.H, "service_holds", ["rb5"], env=fx.env())
        beats = kinds(fx.events("rb5"), "hold-beat", lane="L1")
        stand = beats[-1] if beats else {}
        self.check("B05", "N2: a beat through service_holds at 100 leaves the stand-in hold-beat ok false, "
                   "process_exit 2, harness_may_survive false",
                   stand.get("ok") is False and stand.get("process_exit") == 2
                   and stand.get("harness_may_survive") is False, {"driver": r, "beats": beats})
        fx.set("gpt", "figure", "50")
        p = fx.c("resume", "--run", "rb5", "--lane", "L1", "--brief", fx.path("follow.md"),
                 "--codex", fx.path("bin", "codex"), "--viewer", "none", "--silence-s", "0", "--deadline-s", "60")
        resumed = kinds(fx.events("rb5"), "lane-resumed", lane="L1")
        self.check("B05", "N2: at 50 the same lane's resume passes a3_entry and starts",
                   p.returncode == 0 and resumed and resumed[-1].get("usage_start_check", {}).get("figure") == 50,
                   {"rc": p.returncode, "err": p.stderr[-400:]})
        fx.append("rb5", {"event": "hold-beat", "lane": "L1", "harness": "codex", "ok": False, "n": 9,
                          "invocation_id": "planted", "observation_only": True,
                          "harness_may_survive": True, "by": "supervisor"})
        p = fx.c("resume", "--run", "rb5", "--lane", "L1", "--brief", fx.path("follow.md"),
                 "--codex", fx.path("bin", "codex"), "--viewer", "none", "--silence-s", "0", "--deadline-s", "60")
        self.check("B05", "positive control (N2): a planted stand-in with harness_may_survive true makes "
                   "the same resume refuse in a3_entry", p.returncode == 2 and "harness may survive" in p.stderr,
                   {"rc": p.returncode, "err": p.stderr[-300:]})
        # Clean: 99 and 95 proceed with the check on the start.
        for figure in ("99", "95"):
            fx.set("gpt", "figure", figure)
            lane = "P%s" % figure
            p = self.spawn(fx, "rb5", lane)
            opened = (kinds(fx.events("rb5"), "lane-open", lane=lane) or [{}])[0]
            chk = opened.get("usage_start_check") or {}
            self.check("B05", "clean: a reading of %s proceeds and the lane-open carries usage_start_check"
                       % figure, p.returncode == 0 and chk.get("figure") == int(figure)
                       and chk.get("verdict") == "proceed", {"rc": p.returncode, "check": chk, "err": p.stderr[-300:]})
        fx.open_run("rb5y", "--gpt-credits-approved", "yes")
        fx.set("gpt", "figure", "100")
        before = fx.count("gpt")
        p = self.spawn(fx, "rb5y", "Y1")
        chk = ((kinds(fx.events("rb5y"), "lane-open", lane="Y1") or [{}])[0]).get("usage_start_check") or {}
        self.check("B05", "clean: approval at run-open with a reading of 100 proceeds and takes no reading",
                   p.returncode == 0 and fx.count("gpt") == before and chk.get("credits") == "approved at run-open",
                   {"rc": p.returncode, "reads": fx.count("gpt") - before, "check": chk})
        before = fx.count("gpt")
        rec = fx.path("plain.jsonl")
        p = self.spawn(fx, "rplain", "Q1", "--record", rec)
        rows = [json.loads(l) for l in open(rec)] if os.path.exists(rec) else []
        opened = [r for r in rows if r.get("event") == "lane-open"]
        self.check("B05", "clean: a plain lane run (no run-open) takes no reading and gets no field",
                   p.returncode == 0 and fx.count("gpt") == before and opened
                   and "usage_start_check" not in opened[0], {"rc": p.returncode, "reads": fx.count("gpt") - before})

    # ------------------------------------------------------------------ B06 -------------------
    def b06(self):
        fx = Fx(self, "b06")
        fx.open_run("rb6")
        fx.set("gpt", "mode", "silent")
        open(os.path.join(fx.dirs["gpt"], "pids"), "w").close()
        env = fx.env(AIMYTH_USAGE_CHECK_TIMEOUT_S="1")
        t0 = time.time()
        p = self.spawn(fx, "rb6", "T1", env=env)
        took = time.time() - t0
        time.sleep(1.0)
        silent = []
        for line in open(os.path.join(fx.dirs["gpt"], "pids")):
            parts = line.split()
            silent += [int(parts[i + 1]) for i, w in enumerate(parts[:-1]) if w in ("server", "reader")]
        sstates = {pid: alive(pid) for pid in silent}
        chk = ((kinds(fx.events("rb6"), "lane-open", lane="T1") or [{}])[0]).get("usage_start_check") or {}
        self.check("B06", "a silent app-server under the hook at 1 s: the spawn proceeds within 10 s, "
                   "usage_start_check unmeasured with the timeout reason, and the stand-in's pid file "
                   "shows no reader or app-server left alive",
                   p.returncode == 0 and took <= 10 and chk.get("status") == "unmeasured"
                   and "timed out" in str(chk.get("reason")) and silent
                   and all(v is False for v in sstates.values()),
                   {"rc": p.returncode, "took": round(took, 2), "check": chk, "pids": sstates,
                    "err": p.stderr[-300:]})
        # Ignored termination through the real reader.
        fx.set("gpt", "mode", "ignoreterm")
        open(os.path.join(fx.dirs["gpt"], "pids"), "w").close()
        t0 = time.time()
        p = self.spawn(fx, "rb6", "T2", env=env)
        took = time.time() - t0
        time.sleep(1.0)
        pids = []
        for line in open(os.path.join(fx.dirs["gpt"], "pids")):
            parts = line.split()
            pids += [int(parts[i + 1]) for i, w in enumerate(parts[:-1]) if w in ("server", "reader", "child")]
        states = {pid: alive(pid) for pid in pids}
        if any(v is None for v in states.values()):
            self.denied.append("B06 liveness: python3 -c 'import os; os.kill(PID, 0)' for %s" % pids)
        self.check("B06", "N13: an app-server that ignores SIGTERM (and its child) is ended inside the "
                   "one outer deadline: the spawn proceeds within 10 s and no reader, app-server or child "
                   "is left alive", p.returncode == 0 and took <= 10 and pids
                   and all(v is False for v in states.values()),
                   {"rc": p.returncode, "took": round(took, 2), "pids": states, "err": p.stderr[-300:]})
        script = fx.path("keeper.sh")
        with open(script, "w") as h:
            h.write("#!/bin/sh\ntrap '' TERM\nsleep 30 &\necho $! > %s\nsleep 30\n" % fx.path("keeper.pid"))
        os.chmod(script, 0o755)
        for module in (self.H, self.C):
            if os.path.exists(fx.path("keeper.pid")):
                os.remove(fx.path("keeper.pid"))
            t0 = time.time()
            r = fx.driver(module, "bounded", [ ["/bin/sh", script], 1, 2])
            took = time.time() - t0
            time.sleep(0.5)
            kid = int(open(fx.path("keeper.pid")).read()) if os.path.exists(fx.path("keeper.pid")) else None
            self.check("B06", "N13 (%s bounded_run): ignored SIGTERM and a kept pipe end within read 1 s + "
                       "reap 2 s (ceiling 4.5 s with the interpreter's start), the child killed"
                       % os.path.basename(module),
                       r.get("timed_out") is True and r.get("elapsed", 99) <= 3.5 and took <= 4.5
                       and kid is not None and alive(kid) is False, {"r": r, "took": round(took, 2), "kid": kid})
        with open(script, "w") as h:
            h.write("#!/bin/sh\nsleep 30 &\necho $! > %s\necho '{\"windows\": {}}'\nexit 0\n" % fx.path("keeper.pid"))
        r = fx.driver(self.H, "bounded", [ ["/bin/sh", script], 3, 2])
        time.sleep(0.3)
        kid = int(open(fx.path("keeper.pid")).read()) if os.path.exists(fx.path("keeper.pid")) else None
        self.check("B06", "N13: a leader that exits leaving a child on the pipe: its output is read at once, "
                   "the kept pipe named and the child ended", r.get("rc") == 0 and r.get("kept_pipe") is True
                   and r.get("elapsed", 99) < 2.0 and "windows" in r.get("stdout", "") and alive(kid) is False,
                   {"r": r, "kid": kid})
        fx.set("gpt", "mode", "silent")
        t0 = time.time()
        p = self.spawn(fx, "rb6", "T3", "--detach", "--no-wait", env=env)
        took = time.time() - t0
        self.check("B06", "a detached --no-wait spawn is acknowledged with no 60 s wait",
                   p.returncode == 0 and took <= 15, {"rc": p.returncode, "took": round(took, 2), "out": (p.stdout + p.stderr)[-300:]})
        fx.set("gpt", "mode", "badjson")
        p = self.spawn(fx, "rb6", "T4", env=env)
        chk = ((kinds(fx.events("rb6"), "lane-open", lane="T4") or [{}])[0]).get("usage_start_check") or {}
        bad = [fx.driver(m, "reader_object", ["not json {"]) for m in (self.H, self.C)]
        self.check("B06", "invalid JSON from the stand-in reads unmeasured and the start proceeds; both "
                   "modules read garbage reader output as invalid JSON",
                   p.returncode == 0 and chk.get("status") == "unmeasured"
                   and all(isinstance(b, list) and b[0] is None and "invalid JSON" in b[1] for b in bad),
                   {"rc": p.returncode, "check": chk, "bad": bad})
        fx.set("gpt", "mode", "figure")
        fx.set("gpt", "figure", "40")
        time.sleep(2)   # the detached T3 must close before a beat on another lane
        p = fx.c("resume", "--run", "rb6", "--lane", "T1", "--beat", "--viewer", "none", env=env)
        beat = (kinds(fx.events("rb6"), "hold-beat", lane="T1") or [{}])[-1]
        self.check("B06", "an allowed beat's hold-beat carries its check",
                   p.returncode == 0 and (beat.get("usage_start_check") or {}).get("figure") == 40,
                   {"rc": p.returncode, "beat": beat.get("usage_start_check"), "err": p.stderr[-300:]})
        fx.set("gpt", "figure", "100")
        p = self.spawn(fx, "rb6", "T5", env=env)
        self.check("B06", "control: a valid 100 in the same run still refuses", p.returncode == 2,
                   {"rc": p.returncode})
        before = fx.count("gpt")
        p = self.spawn(fx, "rb6", "T6", "--dry-run", env=env)
        self.check("B06", "control: a dry run takes no reading", p.returncode == 0 and fx.count("gpt") == before,
                   {"rc": p.returncode, "reads": fx.count("gpt") - before})
        # B06's "a detached spawn reads once (the worker), never in the parent" is gone: the caller
        # now reads before the detach (review V-T2b, Claim 8), and B14.3 counts both readings.
        b30 = fx.driver(self.C, "bounds", [], env=fx.env(AIMYTH_USAGE_CHECK_TIMEOUT_S="30"))
        b30h = fx.driver(self.H, "bounds", [], env=fx.env(AIMYTH_USAGE_CHECK_TIMEOUT_S="30"))
        p = self.spawn(fx, "rb6", "T8", env=fx.env(AIMYTH_USAGE_CHECK_TIMEOUT_S="30"))
        self.check("B06", "control: the hook at 30 is ignored with its stderr line and the bound stays 10 s",
                   b30 == [10, 5] and b30h == [10, 5] and "AIMYTH_USAGE_CHECK_TIMEOUT_S='30' ignored" in p.stderr,
                   {"bounds": [b30, b30h], "err": p.stderr[-300:]})

    # ------------------------------------------------------------------ B07 -------------------
    def wait_for(self, fx, run, pred, limit):
        deadline = time.time() + limit
        while time.time() < deadline:
            if pred(fx.events(run)):
                return True
            time.sleep(0.3)
        return False

    def gpt_obs(self, ev):
        """The supervisor's GPT observations during a wait (the retired check's own `what`)."""
        return kinds(ev, "observation", what="gpt weekly check during the reset wait")

    def b07r(self):
        """B07r: the wait's per-tick GPT check is retired (line 2's replacement), since each open
        Codex lane's own watch reads instead; it replaces B07's wait-kill legs, declared gone. A
        5-hour wait of several ticks with a Codex lane open at 100 % takes no GPT reading in the
        supervisor; the same wait, ended by a stand-down, reads once (the stand-in is reachable)."""
        fx = Fx(self, "b07r")
        wrapdir = fx.path("killwrap")
        os.makedirs(wrapdir, exist_ok=True)
        with open(os.path.join(wrapdir, "codex-lane.py"), "w") as h:
            h.write(KILL_STUB.replace("{py}", sys.executable))
        log = fx.path("kill.log")
        fx.open_run("rb7r")
        sleeper = subprocess.Popen(["sleep", "60"])
        fx.append("rb7r", {"event": "lane-open", "lane": "C7", "harness": "codex", "class": "critic"})
        fx.append("rb7r", {"event": "lane-spawned", "lane": "C7", "pid": sleeper.pid, "wrapper_pid": sleeper.pid})
        fx.set("gpt", "mode", "figure")
        fx.set("gpt", "figure", "100")
        before = fx.count("gpt")
        session = "You've hit your session limit · resets %s"
        proc = fx.starter("rb7r", [session % stamp(time.time() + 40)], background=True,
                          env=fx.env(AIMYTH_BEAT_WRAPPER_DIR=wrapdir, KILL_STUB_LOG=log))
        waiting = self.wait_for(fx, "rb7r", lambda ev: kinds(ev, "stop-condition", which="limit"), 30)
        time.sleep(4.0)   # at least three ticks of the starter's --tick-s 1 inside the wait
        during = fx.count("gpt") - before
        obs = self.gpt_obs(fx.events("rb7r"))
        calls = open(log).read().splitlines() if os.path.exists(log) else []
        self.check("B07r", "B07r.1 a 5-hour wait of three or more ticks with a Codex lane open at 100 % and no "
                   "credits takes no GPT reading in the supervisor (the stand-in's count unchanged across the "
                   "ticks), sends no kill and writes no GPT observation",
                   waiting and during == 0 and not obs and not calls,
                   {"waiting": waiting, "reads": during, "obs": obs[:2], "calls": calls})
        # The same wait ended by a stand-down: the stop marker, as `supervise --stop` writes it.
        open(os.path.join(fx.store, "spawn-records", "rb7r-supervisor.stop"), "w").close()
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
        sd = (kinds(fx.events("rb7r"), "supervisor-stood-down") or [{}])[-1]
        total = fx.count("gpt") - before
        sleeper.kill()
        sleeper.wait()
        self.check("B07r", "B07r.2 control, same run: the wait then ends in a stand-down with the lane open, which "
                   "reads GPT's week exactly once (the count up by 1 after the ticks: the stand-in is reachable)",
                   sd.get("reason") == "stopped" and total - during == 1
                   and (sd.get("gpt_at_stand_down") or {}).get("verdict") == "exhausted",
                   {"sd": {k: sd.get(k) for k in ("reason", "codex_lanes_open", "gpt_at_stand_down")},
                    "reads": [during, total]})
    # ------------------------------------------- B04x: B04L and B04m (DW-20261021-2's fold) ----
    def b04x(self):
        fx = Fx(self, "b4x")
        neither = "Current session: 20% used · resets 4am\nCurrent week (all models): 30% used · resets Oct 15\n"
        # B04L (critic CR-T2b finding 3, changed outcome (b)): a legacy on_limit resume run at an
        # unqualified text takes one reading and stands down limit-unclassified when it settles nothing.
        fx.set("cu", "text", neither)
        fx.legacy_run("rb4l", on_limit="resume")
        before = fx.count("cu")
        p = fx.starter("rb4l", ["You've hit your usage limit · resets %s" % stamp(time.time() + 4)])
        ev = fx.events("rb4l")
        sc, sd = kinds(ev, "stop-condition"), kinds(ev, "supervisor-stood-down")
        self.check("B04L", "a legacy on_limit resume run at an unqualified text takes one reading and stands "
                   "down limit-unclassified (changed outcome (b))",
                   fx.count("cu") - before == 1 and len(sd) == 1 and sd[0].get("reason") == "limit-unclassified"
                   and any(s.get("action") == "stand-down: limit-unclassified" for s in sc)
                   and not kinds(ev, "head-resumed"),
                   {"rc": p.returncode, "reads": fx.count("cu") - before, "sc": sc, "sd": sd})
        fx.legacy_run("rb4m", on_limit="resume")
        before = fx.count("cu")
        p = fx.starter("rb4m", ["You've hit your session limit · resets %s" % stamp(time.time() + 4)])
        ev = fx.events("rb4m")
        self.check("B04L", "control: the same legacy run at a session text waits and resumes as today, with "
                   "no reading taken",
                   fx.count("cu") == before and len(kinds(ev, "head-resumed")) == 1
                   and not kinds(ev, "supervisor-stood-down"),
                   {"rc": p.returncode, "reads": fx.count("cu") - before, "out": (p.stdout + p.stderr)[-300:]})
        fx.set("cu", "mode", "fail")
        fx.legacy_run("rb4n", on_limit="resume")
        p = fx.starter("rb4n", ["You've hit your usage limit · resets %s" % stamp(time.time() + 4)])
        sd = kinds(fx.events("rb4n"), "supervisor-stood-down")
        self.check("B04L", "cannot decide: the reading unreadable stands the legacy run down limit-unclassified",
                   len(sd) == 1 and sd[0].get("reason") == "limit-unclassified",
                   {"rc": p.returncode, "sd": sd, "out": (p.stdout + p.stderr)[-300:]})
        fx.set("cu", "mode", "text")
        # B04m (finding 10): a model-scoped stop takes no classification and no reading; under the
        # new default it follows wait_for_reset's model branch.
        fable = ("You've reached your Fable limit. Switch to another model, or manage usage credits at "
                 "claude.ai/settings/usage, to continue.")
        fx.open_run("rb4f")
        before = fx.count("cu")
        p = fx.starter("rb4f", [fable], timeout=30)
        ev = fx.events("rb4f")
        sc = kinds(ev, "stop-condition")
        self.check("B04m", "a model-scoped stop in a default run takes no reading: stop-condition limit-model, "
                   "head-exit, successor-aborted",
                   fx.count("cu") == before and [s.get("which") for s in sc] == ["limit-model"]
                   and kinds(ev, "successor-aborted") and not kinds(ev, "supervisor-stood-down"),
                   {"rc": p.returncode, "reads": fx.count("cu") - before, "sc": sc,
                    "out": (p.stdout + p.stderr)[-300:]})
        fx.open_run("rb4g", "--on-limit", "stop")
        p = fx.starter("rb4g", [fable], timeout=30)
        sd = kinds(fx.events("rb4g"), "supervisor-stood-down")
        self.check("B04m", "control: under --on-limit stop the same text stands down limit-stop, as today",
                   len(sd) == 1 and sd[0].get("reason") == "limit-stop", {"rc": p.returncode, "sd": sd})
        fx.open_run("rb4h")
        before = fx.count("cu")
        p = fx.starter("rb4h", ["You've reached your Fable limit · resets 8am"], "--max-wait-s", "1",
                       timeout=30)
        ev = fx.events("rb4h")
        sc = kinds(ev, "stop-condition")
        self.check("B04m", "the model-scoped text with a time-of-day reset enters the wait (no reading), "
                   "bounded: --max-wait-s ends it reset-timeout",
                   fx.count("cu") == before and len(sc) == 1 and sc[0].get("which") == "limit"
                   and str(sc[0].get("action", "")).startswith("wait until")
                   and len(kinds(ev, "successor-aborted", reason="reset-timeout")) == 1,
                   {"rc": p.returncode, "sc": sc, "out": (p.stdout + p.stderr)[-300:]})

    # ------------------------------------------- B05m: the GPT start check in its other modes ---
    def lane_open(self, fx, run, lane):
        found = kinds(fx.events(run), "lane-open", lane=lane)
        return found[-1] if found else {}

    def b05m(self):
        default = self.W
        fx = Fx(self, "b5m")
        fx.open_run("rb5m")
        fx.set("gpt", "figure", "100")
        self.use(self.mode_tree("trial-limit", GPT_LIMIT_MODE="trial"))
        try:
            p = self.spawn(fx, "rb5m", "M1")
        finally:
            self.use(default)
        chk = self.lane_open(fx, "rb5m", "M1").get("usage_start_check") or {}
        self.check("B05m", "trial copy of GPT_LIMIT_MODE: a spawn at a planted 100 % without credits starts, "
                   "records would_refuse with the figure, and prints one would-refuse line",
                   p.returncode == 0 and (chk.get("would_refuse") or {}).get("figure") == 100
                   and chk.get("mode") == "trial" and p.stderr.count("would refuse (trial state)") == 1,
                   {"rc": p.returncode, "check": chk, "err": p.stderr[-300:]})
        fx.set("gpt", "mode", "fail")
        p = self.spawn(fx, "rb5m", "M2")
        chk = self.lane_open(fx, "rb5m", "M2").get("usage_start_check") or {}
        self.check("B05m", "question 2 (provisional option (b)) in its trial state, the shipped "
                   "GPT_UNREADABLE_MODE: an unreadable reading starts the lane and records would_refuse unreadable",
                   p.returncode == 0 and (chk.get("would_refuse") or {}).get("verdict") == "unreadable"
                   and chk.get("mode") == "trial",
                   {"rc": p.returncode, "check": chk, "err": p.stderr[-300:]})
        before = open(fx.record("rb5m"), "rb").read()
        self.use(self.mode_tree("enforce-unreadable", GPT_UNREADABLE_MODE="enforce"))
        try:
            p = self.spawn(fx, "rb5m", "M3")
        finally:
            self.use(default)
        self.check("B05m", "enforce copy of GPT_UNREADABLE_MODE: the unreadable reading refuses the start, exit 2, "
                   "the record byte-identical, the reason named",
                   p.returncode == 2 and open(fx.record("rb5m"), "rb").read() == before
                   and "unreadable" in p.stderr, {"rc": p.returncode, "err": p.stderr[-300:]})
        fx.set("gpt", "mode", "figure")
        fx.set("gpt", "figure", "50")
        p = self.spawn(fx, "rb5m", "M4")
        chk = self.lane_open(fx, "rb5m", "M4").get("usage_start_check") or {}
        self.check("B05m", "control: below 100 the start proceeds with no would_refuse",
                   p.returncode == 0 and chk.get("gpt_verdict") == "below" and "would_refuse" not in chk,
                   {"rc": p.returncode, "check": chk})

    # ------------------------------------------- B10: a stand-down with Codex lanes open --------
    def b10_case(self, fx, run, figure, mode="figure", lane="C9", wrapdir=None, log=None, open_lane=True,
                 flags=()):
        fx.open_run(run, *flags)
        sleeper = None
        if open_lane:
            sleeper = subprocess.Popen(["sleep", "60"])
            fx.append(run, {"event": "lane-open", "lane": lane, "harness": "codex", "class": "critic"})
            fx.append(run, {"event": "lane-spawned", "lane": lane, "pid": sleeper.pid,
                            "wrapper_pid": sleeper.pid})
        fx.set("gpt", "mode", mode)
        fx.set("gpt", "figure", str(figure))
        before = fx.count("gpt")
        t0 = time.monotonic()
        p = fx.starter(run, ["You've hit your weekly limit · resets %s" % stamp(time.time() + 600)],
                       env=fx.env(AIMYTH_BEAT_WRAPPER_DIR=wrapdir, KILL_STUB_LOG=log), timeout=90)
        took = round(time.monotonic() - t0, 2)
        if sleeper is not None:
            sleeper.kill()
            sleeper.wait()
        sd = kinds(fx.events(run), "supervisor-stood-down")
        calls = open(log).read().splitlines() if log and os.path.exists(log) else []
        return p, (sd[-1] if sd else {}), fx.count("gpt") - before, calls, took

    def bullets_of(self, fx, events):
        out = fx.driver(os.path.join(self.W, "usage_windows.py"), "call", ["stand_down_bullets", events])
        return out if isinstance(out, list) else []

    def b10(self):
        """B10: a stand-down with Codex lanes open. Line 2's replacement ships its stop enforcing
        (GPT_STOP_MODE), re-reads the lane list (review V-T2b, Claim 12) and builds the report's
        bullets from the record at the close (Claim 13)."""
        default = self.W
        fx = Fx(self, "b10")
        wrapdir = fx.path("killwrap")
        os.makedirs(wrapdir, exist_ok=True)
        with open(os.path.join(wrapdir, "codex-lane.py"), "w") as h:
            h.write(KILL_STUB.replace("{py}", sys.executable))
        p, sd, reads, calls, _ = self.b10_case(fx, "rb10e", 100, wrapdir=wrapdir, log=fx.path("k-e.log"))
        g = sd.get("gpt_at_stand_down") or {}
        self.check("B10", "B10.1 must fire, the shipped tree: a weekly stand-down with a Codex lane open at 100 % "
                   "without credits sends codex-lane.py kill for the lane (the kill stand-in logs one call) "
                   "and records it, mode enforce",
                   sd.get("reason") == "limit-weekly" and g.get("verdict") == "exhausted"
                   and [k.get("lane") for k in g.get("kills") or []] == ["C9"] and g.get("mode") == "enforce"
                   and len(calls) == 1 and "kill --run rb10e --lane C9" in calls[0],
                   {"rc": p.returncode, "sd": sd, "calls": calls})
        self.outcomes["stand-down enforce"] = bool(len(calls) == 1 and g.get("kills"))
        self.use(self.mode_tree("stop-trial", GPT_STOP_MODE="trial"))
        try:
            p, sd, reads, calls, _ = self.b10_case(fx, "rb10t", 100, wrapdir=wrapdir, log=fx.path("k-t.log"))
        finally:
            self.use(default)
        g = sd.get("gpt_at_stand_down") or {}
        self.check("B10", "B10.1t a trial copy of GPT_STOP_MODE: the same stand-down lists the lane, records "
                   "would_stop and sends no kill",
                   sd.get("reason") == "limit-weekly" and sd.get("codex_lanes_open") == ["C9"]
                   and g.get("verdict") == "exhausted" and g.get("would_stop") == ["C9"]
                   and g.get("kills") == [] and g.get("mode") == "trial" and not calls,
                   {"rc": p.returncode, "sd": sd, "calls": calls})
        self.outcomes["stand-down trial"] = bool(g.get("would_stop") == ["C9"] and not calls)
        p, sd, reads, calls, _ = self.b10_case(fx, "rb10b", 40, wrapdir=wrapdir, log=fx.path("k-b.log"))
        g = sd.get("gpt_at_stand_down") or {}
        self.check("B10", "must not fire: GPT at 40 % sends no kill, and the lane is still listed",
                   sd.get("codex_lanes_open") == ["C9"] and g.get("verdict") == "below" and not calls
                   and not g.get("would_stop"), {"sd": sd, "calls": calls})
        bullets = self.bullets_of(fx, fx.events("rb10b"))
        report = "# Run report\n\n## Spend\n\n- **Billed:** x\n\n## Next\n\nnone\n"
        patched = fx.driver(self.H, "call", ["patch_report", report, fx.events("rb10b"), METER,
                                             bullets or None])
        text = patched[0] if isinstance(patched, list) and patched else ""
        self.check("B10", "the close's run-report Spend bullets carry one unguarded-lanes line naming the lane, "
                   "with package B's sentence",
                   len(bullets) == 1 and "C9" in bullets[0][1]
                   and "leaves any credit debit unknown" in bullets[0][1]
                   and text.count("GPT lanes open at stand-down 1") == 1
                   and text.index("GPT lanes open at stand-down 1") < text.index("## Next"),
                   {"bullets": bullets, "text": text[-400:]})
        p, sd, reads, calls, _ = self.b10_case(fx, "rb10y", 100, wrapdir=wrapdir, log=fx.path("k-y.log"),
                                               flags=("--gpt-credits-approved", "yes"))
        g = sd.get("gpt_at_stand_down") or {}
        self.check("B10", "B10.3 must not fire: credits approved at run-open, GPT at 100 %: no kill, the lane "
                   "listed, \"observed continuation on approved credits (no debit claimed)\"",
                   sd.get("codex_lanes_open") == ["C9"] and g.get("verdict") == "exhausted" and not calls
                   and g.get("note") == "observed continuation on approved credits (no debit claimed)",
                   {"sd": sd, "calls": calls})
        p, sd, reads, calls, _ = self.b10_case(fx, "rb10n", 100, open_lane=False)
        self.check("B10", "control: no Codex lane open: no GPT reading at the stand-down and no field",
                   sd.get("reason") == "limit-weekly" and reads == 0 and "codex_lanes_open" not in sd
                   and "gpt_at_stand_down" not in sd, {"sd": sd, "reads": reads})
        p, sd, reads, calls, _ = self.b10_case(fx, "rb10u", 0, mode="fail", wrapdir=wrapdir,
                                               log=fx.path("k-u.log"))
        g = sd.get("gpt_at_stand_down") or {}
        self.check("B10", "cannot decide: an unreadable reading stops nothing, says unreadable, and the "
                   "stand-down completes",
                   sd.get("reason") == "limit-weekly" and g.get("verdict") == "unreadable" and not calls
                   and sd.get("codex_lanes_open") == ["C9"], {"sd": sd, "calls": calls})
        p, sd, reads, calls, took = self.b10_case(fx, "rb10h", 0, mode="silent", wrapdir=wrapdir,
                                                  log=fx.path("k-h.log"))
        g = sd.get("gpt_at_stand_down") or {}
        # Bound: the reading's 10 s + 5 s (usage_windows USAGE_CHECK_*), plus the supervisor's own
        # start and stop, ceiling 40 s (set by judgement, unmeasured); the measured time is printed.
        self.timing("B10", "hung GPT stand-in at a stand-down", took_s=took, reading_s=g.get("elapsed_s"))
        self.check("B10", "cannot decide: a hung GPT stand-in is ended inside the reading's bound, recorded "
                   "timed out, and the stand-down completes (times on the timing line above)",
                   sd.get("reason") == "limit-weekly" and g.get("verdict") == "unreadable"
                   and "timed out" in str(g.get("reason")) and isinstance(g.get("elapsed_s"), (int, float))
                   and g["elapsed_s"] <= 15.5 and took <= 40, {"sd": sd, "took": took})
        self.b10_lists(fx, wrapdir)

    def b10_lists(self, fx, wrapdir):
        """B10.6 to B10.10: the stand-down's lane list re-read (Claim 12) and the report's bullets
        from the record (Claim 13; critic CR-T2b2 finding 4)."""
        default = self.W
        # B10.6: a real stand-in lane, killed by the stand-down through the real codex-lane.py kill.
        # The earlier copy ships its stop in trial, so both trees run a copy whose legacy guard
        # constant reads enforce (absent from the staged copy, which ships GPT_STOP_MODE enforce).
        self.use(self.mode_tree("b10-enforce", **{LEGACY_GUARD: "enforce"}))
        try:
            fx.open_run("rb10k")
            fx.set("gpt", "mode", "figure")
            fx.set("gpt", "figure", "50")
            fx.set("codex", "sleep_s", "30")
            p = self.lane_bg(fx, "rb10k", "K6")
            spawned = self.wait_for(fx, "rb10k", lambda ev: kinds(ev, "lane-spawned", lane="K6"), 30)
            fx.set("gpt", "figure", "100")
            fx.starter("rb10k", ["You've hit your weekly limit · resets %s" % stamp(time.time() + 600)],
                       timeout=90)
            self.reap(p, 20)
        finally:
            self.use(default)
            self.clear_sleep(fx)
        sd = (kinds(fx.events("rb10k"), "supervisor-stood-down") or [{}])[-1]
        closes = kinds(fx.events("rb10k"), "lane-closed", lane="K6")
        self.check("B10", "B10.6 Claim 12, a killed lane: after the stand-down's real codex-lane.py kill closes "
                   "the lane, codex_lanes_open is [], codex_lanes_stopped names it and codex_lanes_open_before "
                   "is the list read before the reading",
                   spawned and closes and closes[-1].get("exit_class") == "killed"
                   and sd.get("codex_lanes_open") == [] and sd.get("codex_lanes_stopped") == ["K6"]
                   and sd.get("codex_lanes_open_before") == ["K6"],
                   {"sd": {k: sd.get(k) for k in ("codex_lanes_open", "codex_lanes_stopped",
                                                  "codex_lanes_open_before", "gpt_at_stand_down")},
                    "closes": [c.get("exit_class") for c in closes]})
        # B10.7: the lane's close appended while the stand-in answers the stand-down's reading.
        fx.set("gpt", "close_record", fx.record("rb10c"))
        fx.set("gpt", "close_run", "rb10c")
        fx.set("gpt", "close_lane", "C9")
        p, sd, reads, calls, _ = self.b10_case(fx, "rb10c", 100, mode="closelane", wrapdir=wrapdir,
                                               log=fx.path("k-c.log"))
        self.check("B10", "B10.7 Claim 12, a lane closed during the reading: codex_lanes_open is [], "
                   "codex_lanes_open_before names the lane, and no kill is sent",
                   sd.get("codex_lanes_open") == [] and sd.get("codex_lanes_open_before") == ["C9"] and not calls,
                   {"sd": {k: sd.get(k) for k in ("codex_lanes_open", "codex_lanes_open_before")}, "calls": calls})
        # B10.8: the report names no closed lane as running; control: rb10b's lane, never closed.
        named = [b for run in ("rb10k", "rb10c") for b in self.bullets_of(fx, fx.events(run))]
        control = self.bullets_of(fx, fx.events("rb10b"))
        self.check("B10", "B10.8 Claim 13, the report: no Spend bullet names the lanes of B10.6 and B10.7, which "
                   "closed, as running (control: the 40 % stand-down's lane, still open at the close, is named "
                   "\"no close by the run's close\")",
                   not any("K6" in b[1] or "running" in b[1] for b in named)
                   and len(control) == 1 and "C9: no close by the run's close" in control[0][1],
                   {"named": named, "control": control})
        # B10.9: a lane listed at a stand-down that its own watch stops later, at 100.
        self.use(self.mode_tree("watch2", GPT_WATCH_EVERY_S=2))
        try:
            fx.open_run("rb10w")
            fx.set("gpt", "mode", "figure")
            fx.set("gpt", "figure", "50")
            fx.set("codex", "sleep_s", "30")
            p = self.lane_bg(fx, "rb10w", "L9")
            self.wait_for(fx, "rb10w", lambda ev: kinds(ev, "lane-spawned", lane="L9"), 30)
            fx.starter("rb10w", ["You've hit your weekly limit · resets %s" % stamp(time.time() + 600)],
                       timeout=90)
            fx.set("gpt", "figure", "100")
            self.reap(p, 45)
        finally:
            self.use(default)
            self.clear_sleep(fx)
        bullets = self.bullets_of(fx, fx.events("rb10w"))
        self.check("B10", "B10.9 Claim 13, a later close: the bullet names the listed lane \"closed later at "
                   "<ts>, killed; stopped by its GPT watch at 100 %\"",
                   len(bullets) == 1 and "L9: closed later at " in bullets[0][1]
                   and ", killed; stopped by its GPT watch at 100 %" in bullets[0][1],
                   {"bullets": bullets})
        # B10.10: watched and unwatched lanes, the sentence from each lane's own fields (finding 4).
        # The planted close's watch record is whole, as codex-lane.py's watch_summary writes it
        # (read_bound_s included); `summary` replaces it outright (review V-T2b2, Claim 12 and R7).
        def planted(mode, counts, summary=None):
            ts = stamp()
            watch = {"armed": True, "every_s": 600, "mode": mode, "read_bound_s": 15}
            if summary is None:
                summary = dict({"armed": True, "every_s": 600, "mode": mode, "read_bound_s": 15,
                                "readings": 3, "unreadable": 0, "errors": 0, "ended_early": False,
                                "stopped": None}, **counts)
            return [{"ts": ts, "event": "lane-open", "lane": "WW", "harness": "codex"},
                    {"ts": ts, "event": "lane-spawned", "lane": "WW", "pid": 1, "gpt_watch": watch},
                    {"ts": ts, "event": "lane-open", "lane": "UU", "harness": "codex"},
                    {"ts": ts, "event": "lane-spawned", "lane": "UU", "pid": 2},
                    {"ts": ts, "event": "supervisor-stood-down", "reason": "limit-weekly",
                     "codex_lanes_open": ["WW", "UU"], "gpt_at_stand_down": {"verdict": "below", "figure": 40}},
                    {"ts": ts, "event": "lane-closed", "lane": "WW", "exit_class": "completed",
                     "gpt_watch": summary}]
        enforce = self.bullets_of(fx, planted("enforce", {}))
        text = enforce[0][1] if enforce else ""
        ww = text.split("UU:")[0]
        self.check("B10", "B10.10a a watched lane (its spawn line's gpt_watch armed, mode enforce, every_s 600; its "
                   "close's watch record whole, with no unreadable reading, error or early end) gets the "
                   "watched sentence: its watch read every 10 minutes to stop it, the time past the line "
                   "bounded by 636 s, the reading time included (review V-T2b2, R2)",
                   "every 10 minutes while it ran, to stop it at 100 %" in ww
                   and "the time it ran past the line is bounded by 636 s: the reading in flight when it "
                       "crossed and the next one (15 s each at most), one interval between them" in ww
                   and UNGUARDED_TEXT not in ww, {"bullets": enforce})
        self.check("B10", "B10.10b an unwatched lane (no gpt_watch on its spawn line, as a wrapper from before the "
                   "install writes it) is named with package B's sentence",
                   "UU" in text and UNGUARDED_TEXT in text, {"bullets": enforce})
        trial = self.bullets_of(fx, planted("trial", {}))
        tw = (trial[0][1] if trial else "").split("UU:")[0]
        self.check("B10", "B10.10c the same watched lane as a trial copy writes it (mode trial, below-limit "
                   "readings only): the bullet says its watch was set only to record a would-stop and stopped "
                   "nothing, never that it recorded one, that it stops the lane or that the time is bounded "
                   "(review V-T2b2, Claim 12)",
                   "set only to record a would-stop" in tw and "stopping nothing" in tw
                   and "recorded a would-stop" not in tw and "to stop it" not in tw and "bounded by" not in tw,
                   {"bullets": trial})
        blind = self.bullets_of(fx, planted("enforce", {"unreadable": 2}))
        bw = (blind[0][1] if blind else "").split("UU:")[0]
        self.check("B10", "B10.10d a watched lane whose close records unreadable readings: the bullet names the "
                   "count and says the time past the line is not bounded",
                   "its close records 2 unreadable reading(s), so the time it ran past the line is not bounded"
                   in bw and "bounded by one interval" not in bw and "is bounded by" not in bw, {"bullets": blind})
        # B10.10e to h (review V-T2b2, Claim 12 and R7): a close record that is empty, unarmed or
        # missing any count or figure never reads as bounded; B10.10a's whole record is the control.
        def sentence(summary):
            out = self.bullets_of(fx, planted("enforce", {}, summary=summary))
            return (out[0][1] if out else "").split("UU:")[0]
        empty = sentence({})
        self.check("B10", "B10.10e must not read bounded: a watched lane whose close carries an empty gpt_watch "
                   "({}) gets \"not shown bounded\", never \"bounded by\" (control: B10.10a's whole record "
                   "reads bounded on the same run)",
                   "so the time it ran past the line is not shown bounded" in empty and "bounded by" not in empty
                   and "is bounded by 636 s" in ww, {"empty": empty})
        unarmed = sentence({"armed": False, "reason": "no run-open on the record (a plain lane run)"})
        self.check("B10", "B10.10f must not read bounded: a close whose gpt_watch is unarmed reads \"not shown "
                   "bounded\" and names armed false",
                   "not shown bounded" in unarmed and "armed false" in unarmed and "bounded by" not in unarmed,
                   {"unarmed": unarmed})
        whole = {"armed": True, "every_s": 600, "mode": "enforce", "read_bound_s": 15, "readings": 3,
                 "unreadable": 0, "errors": 0, "ended_early": False, "stopped": None}
        partial, wrong = {}, {}
        for name in ("armed", "mode", "readings", "unreadable", "errors", "ended_early", "every_s",
                     "read_bound_s"):
            partial[name] = sentence({k: v for k, v in whole.items() if k != name})
        for name, value in (("unreadable", "0"), ("errors", None), ("readings", True), ("ended_early", None),
                            ("read_bound_s", 0), ("every_s", "600"), ("mode", "trial")):
            wrong["%s=%r" % (name, value)] = sentence(dict(whole, **{name: value}))
        bad = sorted(k for k, s in list(partial.items()) + list(wrong.items())
                     if "not shown bounded" not in s or "bounded by" in s)
        self.check("B10", "B10.10g must not read bounded: a close record missing any one of armed, mode, "
                   "readings, unreadable, errors, ended_early, every_s or read_bound_s, or holding one with a "
                   "value not of its kind (7 planted), reads \"not shown bounded\" every time (15 records; "
                   "control: the whole record, B10.10a)",
                   not bad and len(partial) == 8 and len(wrong) == 7 and "is bounded by 636 s" in ww,
                   {"bad": bad, "sample": partial.get("errors", "")[-200:]})
        bounds = [fx.driver(os.path.join(self.W, "usage_windows.py"), "call", ["watch_stop_bound_s"] + list(a))
                  for a in ((600, 15), (2, 15), (60, 15), (600, 0), (600, None))]
        # A tree without the module (the live base) reads as empty here, so the leg fails, not the suite.
        uw_path = os.path.join(self.W, "usage_windows.py")
        uw_text = open(uw_path, encoding="utf-8").read() if os.path.isfile(uw_path) else ""
        cx_text = open(self.C, encoding="utf-8").read()
        grace = re.findall(r"^KILL_GRACE_S = ([0-9.]+)$", cx_text, re.M)
        mirrored = re.findall(r"^WATCH_GRACE_S = ([0-9.]+)$", uw_text, re.M)
        tick = re.findall(r"^WATCH_TICK_S = ([0-9.]+)$", uw_text, re.M)
        self.check("B10", "B10.10h the stated stop bound includes the reading time (review V-T2b2, R2): "
                   "watch_stop_bound_s gives 15 + 600 + 15 + 1 + 5 = 636 s as shipped, 38 s at a 2 s interval and "
                   "96 s at 60 s, none for a zero or missing figure; its 5 s grace equals codex-lane.py's "
                   "KILL_GRACE_S and its tick is 1 s, as the runner polls",
                   bounds == [636, 38, 96, None, None] and grace == mirrored == ["5"] and tick == ["1"]
                   and re.search(r"^\s+tick = 1\.0\b", cx_text, re.M) is not None,
                   {"bounds": bounds, "grace": grace, "mirrored": mirrored, "tick": tick})
    # ------------------------------------------- R04: tonight's usage shapes -------------------
    def r04(self):
        fx = Fx(self, "r04")
        fx.set("cu", "text", "Current week (all models): 16% used · resets Nov 15 at 7:59am (Europe/London)\n"
                             "Current week (Fable): 0% used · resets Nov 15 at 8am (Europe/London)\n")
        reset = int(time.time()) + 6 * 86400

        def two(a, b):
            fx.set("gpt", "mode", "result")
            fx.set("gpt", "result.json", json.dumps({"rateLimits": {
                "primary": {"usedPercent": a, "windowDurationMins": 10080, "resetsAt": reset},
                "secondary": {"usedPercent": b, "windowDurationMins": 10080, "resetsAt": reset}}}))
        two(37, 37)
        p, obj = self.reader(fx, "--only", "both", "--format", "json")
        w = (obj or {}).get("windows") or {}
        five, week, gpt = w.get("claude_5h") or {}, w.get("claude_week") or {}, w.get("gpt_week") or {}
        self.check("R04", "tonight's shape: claude_week measured 16 with its reset text; claude_5h unmeasured, "
                   "absent, its reason naming the missing heading; gpt_week measured 37 with both paths; exit 1",
                   p.returncode == 1 and week.get("status") == "measured" and week.get("used_pct") == 16
                   and week.get("reset_text") == "resets Nov 15 at 7:59am (Europe/London)"
                   and five.get("status") == "unmeasured" and five.get("absent") is True
                   and "Current session" in str(five.get("reason"))
                   and gpt.get("status") == "measured" and gpt.get("used_pct") == 37
                   and " + " in str(gpt.get("source")) and len(obj.get("gpt_week_evidence") or []) == 2,
                   {"rc": p.returncode, "obj": obj, "err": p.stderr[-200:]})
        uw = os.path.join(self.W, "usage_windows.py")
        reading = fx.driver(uw, "call", ["reading_from_object", obj, 0, 1, 1])
        line = fx.driver(uw, "call", ["summary_line", reading, None])
        self.check("R04", "the meter on that shape: the reading is partial and the owner's line says the "
                   "account shows no 5-hour window",
                   isinstance(reading, dict) and reading.get("status") == "partial"
                   and "claude_5h not shown by the account" in str(line), {"reading": reading, "line": line})
        q = self.run([sys.executable, "-B", self.R, "--only", "claude"], fx.env(), 60)
        self.check("R04", "control: text mode on the same stand-in prints both headings with their figures and "
                   "resets (the shape of the 9 November reading)",
                   q.returncode == 0 and "Current week (all models): 16% used · resets Nov 15 at 7:59am" in q.stdout
                   and "Current week (Fable): 0% used · resets Nov 15 at 8am" in q.stdout,
                   {"rc": q.returncode, "out": q.stdout[-300:]})
        two(37, 41)
        p, obj = self.reader(fx, "--only", "astra", "--format", "json")
        gpt = ((obj or {}).get("windows") or {}).get("gpt_week") or {}
        ev = (obj or {}).get("gpt_week_evidence") or []
        self.check("R04", "cannot decide: two GPT weekly windows at 37 and 41 read unmeasured 'ambiguous weekly "
                   "windows', both evidence entries kept with their figures",
                   gpt.get("status") == "unmeasured" and gpt.get("reason") == "ambiguous weekly windows"
                   and sorted(e.get("used_pct") for e in ev) == [37, 41], {"obj": obj})
        two(37, 100)
        p, obj = self.reader(fx, "--only", "astra", "--format", "json")
        verdict = fx.driver(uw, "call", ["gpt_verdict", obj])
        self.check("R04", "with 100 in either window, gpt_verdict still reads exhausted (evidence before window)",
                   isinstance(verdict, list) and verdict[:2] == ["exhausted", 100], {"verdict": verdict})

    # ------------------------------------------- I01: the lane items ---------------------------
    def i01(self):
        fx = Fx(self, "i01")
        fx.open_run("ri1")
        fx.set("gpt", "figure", "50")
        fx.append("ri1", {"event": "phase-boundary", "from": "item1", "to": "item2"})
        p = self.spawn(fx, "ri1", "I1")
        lo = self.lane_open(fx, "ri1", "I1")
        self.check("I01", "no --item after a boundary: lane-open has usage_item item2, source inferred, a "
                   "locator, and no `item` key",
                   p.returncode == 0 and lo.get("usage_item") == "item2"
                   and lo.get("usage_item_source") == "inferred" and "item" not in lo
                   and (lo.get("usage_item_locator") or {}).get("to") == "item2",
                   {"rc": p.returncode, "open": {k: lo.get(k) for k in lo if "item" in k}, "err": p.stderr[-300:]})
        p = self.spawn(fx, "ri1", "I2", "--item", "item3")
        lo = self.lane_open(fx, "ri1", "I2")
        self.check("I01", "control: with --item the console's `item` is as today and usage_item_source explicit",
                   p.returncode == 0 and lo.get("item") == "item3" and lo.get("usage_item") == "item3"
                   and lo.get("usage_item_source") == "explicit",
                   {"rc": p.returncode, "open": {k: lo.get(k) for k in lo if "item" in k}, "err": p.stderr[-300:]})

    # ------------------------------------------------------------------ B08 -------------------
    def b08(self):
        fx = Fx(self, "b08")
        fx.open_run("rb8")
        fx.append("rb8", {"event": "lane-open", "lane": "CL", "harness": "claude"})
        fx.append("rb8", {"event": "lane-closed", "lane": "CL", "exit_class": "limit",
                          "limit_signal": "result text names a limit"})
        fx.append("rb8", {"event": "lane-open", "lane": "CX", "harness": "codex"})
        fx.append("rb8", {"event": "lane-closed", "lane": "CX", "exit_class": "limit",
                          "limit_signal": "usage limit reached for this plan"})
        p = fx.starter("rb8", ["You've hit your session limit · resets %s" % stamp(time.time() + 3)])
        note = fx.head_stdin(2) or ""
        self.check("B08", "the resumed head's stdin carries the new sentence (Claude lanes resumed, the "
                   "Codex close left to the GPT rule) and not the old one",
                   p.returncode == 0 and NEW_NOTE in note and CODEX_NOTE in note and OLD_NOTE not in note,
                   {"rc": p.returncode, "note": note[-400:]})
        fx.open_run("rb8s", "--on-limit", "stop")
        p = fx.starter("rb8s", ["You've hit your session limit · resets %s" % stamp(time.time() + 3)])
        self.check("B08", "control: under on_limit stop the run stands down and feeds no note",
                   p.returncode == 0 and fx.head_stdin(2) is None
                   and kinds(fx.events("rb8s"), "supervisor-stood-down", reason="limit-stop"),
                   {"rc": p.returncode})

    # ------------------------------------------------------------------ R01 -------------------
    def r01(self):
        fx = Fx(self, "r01")
        live = ("Current session: 34% used · resets Oct 5 at 8pm (Europe/London)\n"
                "Current week (all models): 67% used · resets Oct 8 at 7am (Europe/London)\n"
                "Current week (one model): 5% used · resets Oct 8 at 7am (Europe/London)\n")
        fx.set("cu", "text", live)
        p, obj = self.reader(fx, "--format", "json")
        w = (obj or {}).get("windows") or {}
        self.check("R01", "JSON: the three keys present; session and all-models headings mapped; the "
                   "one-model week ignored; the GPT week found as secondary; exit 0",
                   p.returncode == 0 and set(w) == {"claude_5h", "claude_week", "gpt_week"}
                   and w["claude_5h"].get("used_pct") == 34 and w["claude_week"].get("used_pct") == 67
                   and w["gpt_week"].get("used_pct") == 50 and w["gpt_week"].get("source") == "rateLimits.secondary"
                   and obj.get("schema") == 1 and obj.get("requested") == "both",
                   {"rc": p.returncode, "obj": obj, "err": p.stderr[-300:]})
        fx.set("cu", "text", "Current session\n  0% used · resets 4am (Europe/London)\nCurrent week (all models)\n  17% used\n")
        fx.set("gpt", "figure", "0")
        p, obj = self.reader(fx, "--format", "json")
        w = (obj or {}).get("windows") or {}
        self.check("R01", "JSON: a measured zero stays zero (both families); a missing reset is null while "
                   "measured (the two-line shape)",
                   p.returncode == 0 and w.get("claude_5h", {}).get("used_pct") == 0
                   and w.get("gpt_week", {}).get("used_pct") == 0
                   and w.get("claude_week", {}).get("status") == "measured"
                   and w.get("claude_week", {}).get("reset_text") is None, {"rc": p.returncode, "obj": obj})
        fx.set("cu", "text", "Current session: 4% used · resets 4am\nCurrent session: 9% used · resets 4am\n"
                             "Current week (all models): 17% used · resets Oct 15\n")
        p, obj = self.reader(fx, "--only", "claude", "--format", "json")
        w = (obj or {}).get("windows") or {}
        self.check("R01", "JSON: a duplicate canonical heading is unmeasured (exit 1), the other measured",
                   p.returncode == 1 and w.get("claude_5h", {}).get("status") == "unmeasured"
                   and "appears 2 times" in str(w.get("claude_5h", {}).get("reason"))
                   and w.get("claude_week", {}).get("status") == "measured", {"rc": p.returncode, "obj": obj})
        p, obj = self.reader(fx, "--only", "astra", "--format", "json")
        w = (obj or {}).get("windows") or {}
        self.check("R01", "JSON: --only astra marks the Claude windows not_requested (exit 0)",
                   p.returncode == 0 and w.get("claude_5h", {}).get("status") == "not_requested"
                   and w.get("claude_week", {}).get("status") == "not_requested", {"rc": p.returncode, "obj": obj})
        fx.set("cu", "mode", "fail")
        p, obj = self.reader(fx, "--format", "json")
        w = (obj or {}).get("windows") or {}
        p2, _ = self.reader(fx, "--format", "json", "--timeout-s", "0")
        self.check("R01", "JSON: a failed Claude reading leaves both Claude windows unmeasured with text "
                   "mode's reason (exit 1, three keys); a bad bound exits 2 with PROBE FAILED",
                   p.returncode == 1 and set(w) == {"claude_5h", "claude_week", "gpt_week"}
                   and "not logged in" in str(w.get("claude_week", {}).get("reason"))
                   and p2.returncode == 2 and "PROBE FAILED" in p2.stdout, {"rc": [p.returncode, p2.returncode], "obj": obj})
        fx.set("cu", "mode", "text")
        fx.set("cu", "text", live)
        fx.set("gpt", "figure", "19")
        p, _ = self.reader(fx)
        self.check("R01", "control: text mode's output and exit code are unchanged (two lines, exit 0)",
                   p.returncode == 0 and p.stdout.startswith("claude-usage: Current session: 34% used")
                   and "\nastra-usage: 5 h window 10% used" in p.stdout and "· 7 d window 19% used" in p.stdout
                   and len(p.stdout.splitlines()) == 2,
                   {"rc": p.returncode, "out": p.stdout})

    # ------------------------------------------------------------------ R02 -------------------
    def r02(self):
        fx = Fx(self, "r02")
        wk = lambda used, path="w": {"usedPercent": used, "windowDurationMins": 10080, "resetsAt": 1800000000}
        cases = [
            ("weekly 101: accounting null, evidence 101", {"rateLimits": {"secondary": wk(101)}},
             lambda w, e: w["status"] == "unmeasured" and [x["used_pct"] for x in e] == [101]),
            ("two differing weekly groups, one at 100: ambiguous, evidence holds both",
             {"a": {"secondary": wk(100)}, "b": {"secondary": wk(60)}},
             lambda w, e: w["reason"] == "ambiguous weekly windows" and sorted(x["used_pct"] for x in e) == [60, 100]),
            ("bool, string, NaN and negative figures give no evidence",
             {"a": {"x": wk(True)}, "b": {"x": wk("100")}, "c": {"x": wk(float("nan"))}, "d": {"x": wk(-5)}},
             lambda w, e: e == [] and w["status"] == "unmeasured"),
            ("an exhausted 300-minute window gives no weekly evidence",
             {"rateLimits": {"primary": {"usedPercent": 100, "windowDurationMins": 300}}},
             lambda w, e: e == [] and w["status"] == "unmeasured"),
            ("a missing duration gives none", {"rateLimits": {"primary": {"usedPercent": 100}}},
             lambda w, e: e == []),
            ("a malformed candidate beside a saturated one keeps the saturated evidence",
             {"a": {"x": wk("bad")}, "b": {"x": wk(100)}},
             lambda w, e: [x["used_pct"] for x in e] == [100]),
            ("control: a single numeric weekly 100 is measured 100 with evidence 100",
             {"rateLimits": {"secondary": wk(100)}},
             lambda w, e: w["status"] == "measured" and w["used_pct"] == 100 and [x["used_pct"] for x in e] == [100]),
            ("control: a single 49 is measured 49 with evidence 49", {"rateLimits": {"secondary": wk(49)}},
             lambda w, e: w["used_pct"] == 49 and [x["used_pct"] for x in e] == [49]),
            ("identical duplicates collapse with both paths kept",
             {"a": {"x": wk(30)}, "b": {"x": wk(30)}},
             lambda w, e: w["status"] == "measured" and w["source"] == "a.x + b.x"),
        ]
        for name, result, test in cases:
            r = fx.driver(self.R, "gpt", [result])
            ok = False
            try:
                ok = isinstance(r, list) and test(r[0], r[1])
            except (KeyError, TypeError, IndexError):
                ok = False
            self.check("R02", name, ok, r)
        fx.set("gpt", "mode", "result")
        fx.set("gpt", "result.json", json.dumps({"rateLimits": {"secondary": wk(101)}}))
        p, obj = self.reader(fx, "--only", "astra", "--format", "json")
        p2, _ = self.reader(fx, "--only", "astra")
        self.check("R02", "end to end: weekly 101 through the reader is unmeasured with evidence 101 (exit 1), "
                   "while text mode fails the whole GPT reading as before",
                   p.returncode == 1 and [x.get("used_pct") for x in (obj or {}).get("gpt_week_evidence", [])] == [101]
                   and p2.returncode == 1 and "could not read" in p2.stdout, {"obj": obj, "text": p2.stdout})

    # ------------------------------------------------------------------ R03 -------------------
    def r03(self):
        """N10: a Claude window's source is its canonical name, so two readings differing only in
        the figure give a 1-point delta, never `scope changed`."""
        fx = Fx(self, "r03")
        reads = []
        for pct in (34, 35):
            fx.set("cu", "text", "Current session: %d%% used · resets Oct 5 at 8pm (Europe/London)\n"
                                 "Current week (all models): 67%% used · resets Oct 8 at 7am (Europe/London)\n" % pct)
            p, obj = self.reader(fx, "--only", "claude", "--format", "json")
            reads.append(((obj or {}).get("windows") or {}).get("claude_5h") or {})

        def delta(a, b, key):
            if a.get(key) != b.get(key):
                return "scope changed"
            if a.get("reset_text") != b.get("reset_text") or not a.get("reset_text"):
                return "reset changed"
            if a.get("status") != "measured" or b.get("status") != "measured":
                return "unmeasured"
            return b["used_pct"] - a["used_pct"]

        a, b = reads
        self.check("R03", "N10: two one-line readings differing only in the percentage keep one source "
                   "(claude_5h) and give a 1-point change, never 'scope changed'",
                   a.get("source") == "claude_5h" and b.get("source") == "claude_5h"
                   and delta(a, b, "source") == 1, {"first": a, "second": b})
        self.check("R03", "N10: the literal heading line is kept separately and differs between the two",
                   a.get("heading", "").startswith("Current session: 34%")
                   and b.get("heading", "").startswith("Current session: 35%"), {"first": a, "second": b})
        self.check("R03", "positive control: keyed on the literal heading instead, the same pair reads "
                   "'scope changed' (the failure N10 names)", delta(a, b, "heading") == "scope changed",
                   {"first": a, "second": b})

    # ------------------------------------------------------------------ T14 -------------------
    def t14(self):
        fx = Fx(self, "t14")
        fx.open_run("rt14")
        ho = fx.handoff("rt14")
        snap = lambda: (open(ho, "rb").read(), open(fx.record("rt14"), "rb").read())
        refuse = {
            "ledger": ["ledger", "--run", "rt14", "--phase", "p1", "--what", "at 23:2x the lane closed",
                       "--evidence", "e", "--routing", "r"],
            "decision": ["decision", "--run", "rt14", "--phase", "p1", "--what", "took it at 00:0x",
                         "--grant", "g"],
            "boundary": ["boundary", "--run", "rt14", "--from", "item1", "--to", "item2", "--disposition",
                         "closed at 01:1x", "--waste", "none", "--next", "n", "--meter-line", METER],
            "handoff": ["handoff", "--run", "rt14", "--inflight",
                        "Next: resume at 02:2x\nNeeds: none\nDecided: none"],
        }
        clean = {
            "ledger": ["ledger", "--run", "rt14", "--phase", "p1", "--what",
                       "per [2026-09-12 21:3x], at 23:24 the lane closed", "--evidence", "e", "--routing", "r"],
            "decision": ["decision", "--run", "rt14", "--phase", "p1", "--what",
                         "took it at 00:04 under [2026-10-15 01:33 d]", "--grant", "g"],
            "boundary": ["boundary", "--run", "rt14", "--from", "item1", "--to", "item2", "--disposition",
                         "closed at 01:14", "--waste", "none", "--next", "n", "--meter-line", METER],
            "handoff": ["handoff", "--run", "rt14", "--inflight",
                        "Next: resume at 02:24 ([2026-09-26 03:5x] cited)\nNeeds: none\nDecided: none"],
        }
        for name in ("ledger", "decision", "boundary", "handoff"):
            before = snap()
            p = fx.h(*refuse[name])
            self.check("T14", "must refuse: %s with a typed HH:Mx placeholder exits 2, nothing written" % name,
                       p.returncode == 2 and "typed clock placeholder" in p.stderr and snap() == before,
                       {"rc": p.returncode, "err": p.stderr[-300:], "same": snap() == before})
            p = fx.h(*clean[name])
            self.check("T14", "must pass: %s with a real clock and a bracketed register heading" % name,
                       p.returncode == 0, {"rc": p.returncode, "err": (p.stdout + p.stderr)[-400:]})
        pack = fx.path("pack.md")
        with open(pack, "w") as h:
            h.write("Next: resume at 02:2x\nNeeds: none\nDecided: none\n")
        before = snap()
        p = fx.h("handoff", "--run", "rt14", "--inflight-file", pack)
        self.check("T14", "must refuse: handoff --inflight-file whose text carries HH:Mx",
                   # Today's installed guard (refuse_placeholder) names the value `--inflight`; the
                   # refusal and the unchanged files are the leg (migrated 9 November 2026).
                   p.returncode == 2 and "--inflight" in p.stderr and snap() == before,
                   {"rc": p.returncode, "err": p.stderr[-300:]})

    # ------------------------------------------------------------------ T15 -------------------
    def t15(self):
        fx = Fx(self, "t15")
        fx.open_run("rt15")
        dashed = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(fx.vault))
        tdir = fx.path("projects", dashed)
        os.makedirs(tdir, exist_ok=True)
        for sid in ("sid-one", "sid-two"):
            with open(os.path.join(tdir, sid + ".jsonl"), "w") as h:
                for rec in ({"type": "user", "timestamp": "2026-10-21T20:00:00Z",
                             "message": {"role": "user", "content": [{"type": "text", "text": "ask %s" % sid}]}},
                            {"type": "assistant", "timestamp": "2026-10-21T20:00:10Z",
                             "message": {"role": "assistant", "model": "claude-fixture-1",
                                         "content": [{"type": "text", "text": "answer %s" % sid}]}}):
                    h.write(json.dumps(rec) + "\n")
        out = fx.path("reflect-out")
        p1 = fx.h("reflect-inputs", "--run", "rt15", "--session", "sid-one", "--out", out, "--no-meter")
        first = {f: open(os.path.join(out, f), "rb").read() for f in sorted(os.listdir(out))} if os.path.isdir(out) else {}
        n_ev = len(kinds(fx.events("rt15"), "reflect-inputs"))
        p2 = fx.h("reflect-inputs", "--run", "rt15", "--session", "sid-two", "--out", out, "--no-meter")
        second = {f: open(os.path.join(out, f), "rb").read() for f in sorted(os.listdir(out))} if os.path.isdir(out) else {}
        self.check("T15", "repeated output: a second session into the same non-empty --out is refused "
                   "(exit 2) and the first session's four files stay byte for byte",
                   p1.returncode == 0 and len(first) >= 4 and p2.returncode == 2 and "is not empty" in p2.stderr
                   and first == second and len(kinds(fx.events("rt15"), "reflect-inputs")) == n_ev,
                   {"rc": [p1.returncode, p2.returncode], "files": sorted(first), "err": (p1.stderr + p2.stderr)[-400:]})
        out2 = fx.path("reflect-out-two")
        os.makedirs(out2)
        p3 = fx.h("reflect-inputs", "--run", "rt15", "--session", "sid-two", "--out", out2, "--no-meter")
        self.check("T15", "control: the second session into an existing empty folder is written",
                   p3.returncode == 0 and os.path.exists(os.path.join(out2, "turns.md")),
                   {"rc": p3.returncode, "err": p3.stderr[-300:]})
        p4 = fx.h("reflect-inputs", "--run", "rt15", "--session", "sid-two", "--out", out, "--no-meter", "--dry-run")
        self.check("T15", "a dry run into the non-empty --out is refused the same way",
                   p4.returncode == 2 and "is not empty" in p4.stderr, {"rc": p4.returncode})

    # ------------------------------------------- B11 to B14, W03: line 2's replacement --------
    def timing(self, gid, what, **values):
        """A measured time printed beside its leg, never inside the leg's name (a name holding a
        time moves between runs)."""
        print("     timing %s %s · %s" % (gid, what, " ".join("%s=%s" % kv for kv in sorted(values.items()))),
              flush=True)

    def clear_sleep(self, fx):
        for name in ("sleep_s", "exited"):
            p = os.path.join(fx.dirs["codex"], name)
            if os.path.exists(p):
                os.remove(p)

    def reset_gpt(self, fx, mode="figure", figure="50", steps=None):
        """The GPT stand-in set afresh: its call count and pids file cleared, so a sequence counts
        from the next call (the start check's)."""
        for name in ("count", "pids", "figures.json"):
            p = os.path.join(fx.dirs["gpt"], name)
            if os.path.exists(p):
                os.remove(p)
        open(os.path.join(fx.dirs["gpt"], "pids"), "w").close()
        fx.set("gpt", "mode", mode)
        fx.set("gpt", "figure", str(figure))
        if steps is not None:
            fx.set("gpt", "figures.json", json.dumps(steps))

    def gpt_calls(self, fx):
        """[(call, server pid, reader pid, start, end or None)] from the stand-in's pids file."""
        p = os.path.join(fx.dirs["gpt"], "pids")
        starts, ends = [], {}
        for line in (open(p).read().splitlines() if os.path.exists(p) else []):
            parts = line.split()
            if parts[:1] == ["server"] and len(parts) >= 8:
                starts.append((int(parts[7]), int(parts[1]), int(parts[3]), float(parts[5])))
            elif parts[:1] == ["end"] and len(parts) == 3:
                ends[int(parts[1])] = float(parts[2])
        return [(c, s, r, t, ends.get(s)) for c, s, r, t in starts]

    def reap(self, p, limit):
        """Wait for a background wrapper; past `limit` seconds its process group is killed (fixture
        hygiene) and None is returned."""
        try:
            return p.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            p.wait()
            return None

    def lane_bg(self, fx, run, lane, *extra, env=None, verb="spawn"):
        """A Codex lane in the foreground form, started as a background process in its own group,
        so every tree reads GPT's week in one order: the start check's call, then the watch's."""
        out = open(fx.path("work", "%s-%s-%s.out" % (run, lane, verb)), "w")
        if verb == "spawn":
            cmd = ["spawn", "--run", run, "--lane", lane, "--codex", fx.path("bin", "codex"), "--class",
                   "critic", "--brief", fx.path("brief.md"), "--cwd", fx.work, "--reason", "(a) suite",
                   "--choice-reason", "suite pick", "--delegation", "single", "--delegation-src", "head"]
        else:
            cmd = ["resume", "--run", run, "--lane", lane, "--brief", fx.path("follow.md"),
                   "--codex", fx.path("bin", "codex")]
        cmd += ["--viewer", "none", "--silence-s", "0", "--deadline-s", "120"] + list(extra)
        return subprocess.Popen([sys.executable, "-B", self.C] + cmd, env=env or fx.env(), cwd=fx.root,
                                stdout=out, stderr=subprocess.STDOUT, start_new_session=True)

    def run_watched(self, fx, run, lane, switch=None, extra=(), env=None, verb="spawn", limit=90,
                    sleep_s=15, record=None):
        """One lane over the stand-in codex (silent for sleep_s seconds after thread.started). Once
        its lane-spawned (or lane-respawned) is on the record, `switch()` plants the change; then
        the close is awaited. Returns the lane's close, its spawn line, its watch lines after that
        line, the measured times and the stand-in's calls."""
        rec = record or fx.record(run)
        kind = "lane-spawned" if verb == "spawn" else "lane-respawned"
        fx.set("codex", "sleep_s", str(sleep_s))
        exited = os.path.join(fx.dirs["codex"], "exited")
        if os.path.exists(exited):
            os.remove(exited)
        c0 = len(kinds(read_jsonl(rec), "lane-closed", lane=lane))
        s0 = len(kinds(read_jsonl(rec), kind, lane=lane))
        n0 = fx.count("gpt")
        p = self.lane_bg(fx, run, lane, *extra, env=env, verb=verb)
        deadline = time.time() + 30
        while time.time() < deadline and p.poll() is None \
                and len(kinds(read_jsonl(rec), kind, lane=lane)) <= s0:
            time.sleep(0.1)
        seen = len(kinds(read_jsonl(rec), kind, lane=lane)) > s0
        t_switch, n_switch = time.time(), fx.count("gpt")
        if switch is not None and seen:
            switch()
        closed_at = returned_at = None
        deadline = time.time() + limit
        while time.time() < deadline:
            if closed_at is None and len(kinds(read_jsonl(rec), "lane-closed", lane=lane)) > c0:
                closed_at = time.time()
            if returned_at is None and p.poll() is not None:
                returned_at = time.time()
            if returned_at is not None and (closed_at is not None or time.time() - returned_at > 2):
                break
            time.sleep(0.1)
        rc = self.reap(p, 1)
        ev = read_jsonl(rec)
        idx = max([i for i, e in enumerate(ev) if e.get("event") == kind and e.get("lane") == lane]
                  or [len(ev)])
        after = ev[idx:]
        closes = kinds(ev, "lane-closed", lane=lane)
        exit_at = None
        if os.path.exists(exited):
            try:
                exit_at = float(open(exited).read().split()[-1])
            except (ValueError, IndexError):
                exit_at = None
        watch_lines = [e for e in after if e.get("event") == "observation" and e.get("lane") == lane]
        r = {"rc": rc, "seen": seen, "ev": ev, "spawn": ev[idx] if idx < len(ev) else {},
             "close": closes[-1] if len(closes) > c0 else {}, "closes": len(closes) - c0,
             "lines": [e for e in watch_lines if e.get("watch_line") == "verdict"],
             "config": [e for e in watch_lines if e.get("watch_line") == "config"],
             "to_close": None if closed_at is None else round(closed_at - t_switch, 2),
             "closed_at": closed_at, "t_switch": t_switch,
             "close_after_exit": None if closed_at is None or exit_at is None else round(closed_at - exit_at, 2),
             "return_after_close": None if closed_at is None or returned_at is None
             else round(returned_at - closed_at, 2),
             "reads": fx.count("gpt") - n0, "reads_after_switch": fx.count("gpt") - n_switch,
             "out": open(fx.path("work", "%s-%s-%s.out" % (run, lane, verb))).read()[-400:]}
        r["watch"] = r["close"].get("gpt_watch") or {}
        self.clear_sleep(fx)
        return r

    def detail(self, r):
        return {"rc": r["rc"], "seen": r["seen"],
                "close": {k: r["close"].get(k) for k in ("exit_class", "killed_by", "error", "disposition")},
                "watch": r["watch"], "spawn_watch": r["spawn"].get("gpt_watch"),
                "lines": [(l.get("verdict"), l.get("figure"), l.get("action"), l.get("credits_src"),
                           str(l.get("what"))[:120]) for l in r["lines"]],
                "to_close": r["to_close"], "reads": r["reads"], "out": r["out"]}

    def stopped(self, r, fig):
        """The watch's stop of its own lane, as the record shows it."""
        c, w = r["close"], r["watch"]
        stops = [l for l in r["lines"] if l.get("action") == "stop"]
        disp = c.get("disposition") or {}
        return (c.get("exit_class") == "killed" and c.get("killed_by") == "gpt-watch" and len(stops) == 1
                and stops[0].get("verdict") == "exhausted" and stops[0].get("figure") == fig
                and (w.get("stopped") or {}).get("figure") == fig and disp.get("decision") == "held"
                and "N19" in str(disp.get("reason")) and str(fig) in str(disp.get("reason")))

    def ran_unstopped(self, r):
        c = r["close"]
        # Every A3 close carries stop_cause; it is null where nothing stopped the pass.
        return c.get("exit_class") == "completed" and c.get("killed_by") is None and c.get("stop_cause") is None

    def b11(self):
        """B11: each Codex lane's own GPT watch (line 2's replacement), in a mode copy that reads
        every 2 s: must fire, must not fire, cannot decide."""
        default = self.W
        fx = Fx(self, "b11")
        w2 = self.mode_tree("watch2", GPT_WATCH_EVERY_S=2)
        to = lambda v: (lambda: fx.set("gpt", "figure", str(v)))
        self.use(w2)
        try:
            self.b11_fire(fx, to)
            self.b11_clean(fx, to)
            self.b11_undecided(fx, to)
            self.b11_meet(fx)
        finally:
            self.use(default)

    def b11_fire(self, fx, to):
        fx.open_run("r11a")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r11a", "W1", switch=to(100))
        stop = ([l for l in r["lines"] if l.get("action") == "stop"] or [{}])[0]
        self.timing("B11", "B11.1 switch to close", to_close_s=r["to_close"])
        ok = (self.stopped(r, 100) and r["to_close"] is not None and r["to_close"] <= 11
              and stop.get("mode") == "enforce" and stop.get("credits") == "not approved"
              and r["spawn"].get("gpt_watch", {}).get("armed") is True)
        self.outcomes["watch enforce"] = ok
        self.check("B11", "B11.1 must fire: GPT's week switched from 50 to 100 once lane-spawned is on the record, "
                   "no credits: within 11 s of the switch the lane closes killed by its own watch (killed_by "
                   "gpt-watch), one stop line (exhausted, figure 100, mode enforce, credits not approved), "
                   "gpt_watch.stopped.figure 100 on the close, and the A3 disposition held with a reason naming "
                   "N19 and 100", ok, self.detail(r))
        fx.open_run("r11b")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r11b", "W2", switch=to(101))
        stop = ([l for l in r["lines"] if l.get("action") == "stop"] or [{}])[0]
        self.check("B11", "B11.2 must fire, raw: the same with 101: the same stop, with 101 kept as evidence",
                   self.stopped(r, 101) and any(e.get("used_pct") == 101 for e in stop.get("evidence") or []),
                   self.detail(r))
        fx.open_run("r11e", "--gpt-credits-approved", "yes")
        self.reset_gpt(fx, figure="100")
        r = self.run_watched(fx, "r11e", "W5", switch=lambda: fx.h("grants", "--run", "r11e",
                                                                    "--gpt-credits-approved", "no"))
        stop = ([l for l in r["lines"] if l.get("action") == "stop"] or [{}])[0]
        self.check("B11", "B11.5 credits lowered mid-lane: approved at run-open, GPT at 100, `grants "
                   "--gpt-credits-approved no` after lane-spawned: the next tick reads and stops the lane "
                   "(credits source grants)", self.stopped(r, 100) and stop.get("credits_src") == "grants",
                   self.detail(r))
        fx.open_run("r11f")
        self.reset_gpt(fx)
        g = json.load(open(fx.grants("r11f"))) if os.path.exists(fx.grants("r11f")) else {}
        g["gpt_credits_approved"] = True
        json.dump(g, open(fx.grants("r11f"), "w"))
        r = self.run_watched(fx, "r11f", "W6", switch=to(100))
        stop = ([l for l in r["lines"] if l.get("action") == "stop"] or [{}])[0]
        self.check("B11", "B11.6 raised by hand: a false run-open, the grants file edited to true after it, 50 at "
                   "the start and 100 after lane-spawned: credits read false (\"grants true, run-open false: "
                   "never raised after run-open (N4)\") and the lane is stopped",
                   self.stopped(r, 100) and stop.get("credits_src")
                   == "grants true, run-open false: never raised after run-open (N4)", self.detail(r))
        fx.open_run("r11m", "--gpt-credits-approved", "yes")
        self.reset_gpt(fx, figure="100")
        r = self.run_watched(fx, "r11m", "W15", switch=lambda: os.path.exists(fx.grants("r11m"))
                             and os.remove(fx.grants("r11m")))
        stop = ([l for l in r["lines"] if l.get("action") == "stop"] or [{}])[0]
        self.check("B11", "B11.15 the grants file gone mid-lane after an approved run-open (critic CR-T2b2 "
                   "finding 8), GPT at 100: the approval reads not approved (\"default (no grants file)\") and "
                   "the watch stops the lane", self.stopped(r, 100)
                   and stop.get("credits_src") == "default (no grants file)", self.detail(r))

    def b11_clean(self, fx, to):
        fx.open_run("r11c")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r11c", "W3", sleep_s=8)
        self.check("B11", "B11.3 must not fire: the figure stays 50: the lane closes completed with no stop, "
                   "gpt_watch.readings 2 or more, and exactly one watch line (below)",
                   self.ran_unstopped(r) and r["watch"].get("readings", 0) >= 2 and len(r["lines"]) == 1
                   and r["lines"][0].get("verdict") == "below" and r["lines"][0].get("action") == "none",
                   self.detail(r))
        fx.open_run("r11d", "--gpt-credits-approved", "yes")
        self.reset_gpt(fx, figure="100")
        r = self.run_watched(fx, "r11d", "W4", sleep_s=8)
        self.check("B11", "B11.4 must not fire: credits approved at run-open, GPT at 100 throughout: completed "
                   "with no stop, the stand-in never called during the lane, gpt_watch.readings 0 and "
                   "skipped_credits 2 or more",
                   self.ran_unstopped(r) and r["reads"] == 0 and r["watch"].get("readings") == 0
                   and r["watch"].get("skipped_credits", 0) >= 2 and not r["lines"], self.detail(r))
        self.reset_gpt(fx, figure="100")
        rec = fx.path("plain11.jsonl")
        r = self.run_watched(fx, "r11p", "W11", extra=("--record", rec), record=rec, sleep_s=4)
        sw = r["spawn"].get("gpt_watch") or {}
        self.check("B11", "B11.11 a plain lane run (no run-open on its record), GPT at 100: the spawn line "
                   "carries gpt_watch armed false with its reason, the stand-in is never called, and the lane "
                   "completes", self.ran_unstopped(r) and sw.get("armed") is False
                   and "no run-open" in str(sw.get("reason")) and r["reads"] == 0, self.detail(r))
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r11c", "W3", switch=to(100), verb="resume")
        self.check("B11", "B11.12 resume: B11.3's lane resumed, 50 at the resume's start and 100 after "
                   "lane-respawned: lane-respawned carries gpt_watch armed true and the resumed pass is stopped",
                   (r["spawn"].get("gpt_watch") or {}).get("armed") is True and self.stopped(r, 100),
                   self.detail(r))
        default = self.W
        self.use(self.mode_tree("watch2-trial", GPT_WATCH_EVERY_S=2, GPT_STOP_MODE="trial"))
        try:
            fx.open_run("r11j")
            self.reset_gpt(fx)
            r = self.run_watched(fx, "r11j", "W10", switch=to(100), sleep_s=10)
        finally:
            self.use(default)
        would = [l for l in r["lines"] if l.get("action") == "would_stop"]
        ok = (self.ran_unstopped(r) and len(would) == 1 and r["reads_after_switch"] >= 2
              and (r["watch"].get("last") or {}).get("verdict") == "exhausted" and r["watch"].get("mode") == "trial")
        self.outcomes["watch trial"] = ok
        self.check("B11", "B11.10 trial copy of GPT_STOP_MODE: 100 after the start: the lane completes, exactly "
                   "one would-stop line across two or more exhausted readings, and no stop", ok, self.detail(r))
        fx.open_run("r11n")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r11n", "W16", env=fx.env(AIMYTH_USAGE_CHECK_TIMEOUT_S="1"), sleep_s=4)
        sw = r["spawn"].get("gpt_watch") or {}
        self.check("B11", "B11.16a must fire (critic CR-T2b2 advice 6): the read bound lowered to 1 s and the "
                   "app-server set by USAGE_CODEX_BIN: the spawn line records both, and one warning line names "
                   "them", len(r["config"]) == 1 and str(r["config"][0].get("what")).startswith(
                       "warning: gpt weekly watch for lane W16 reads with a non-default reader")
                   and "read bound 1 s" in str(r["config"][0].get("what")) and sw.get("read_s") == 1
                   and sw.get("reader_bin_src") == "USAGE_CODEX_BIN", self.detail(r))
        fx.open_run("r11o", "--gpt-credits-approved", "yes")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r11o", "W17", env=fx.env(USAGE_CODEX_BIN=None), sleep_s=4)
        sw = r["spawn"].get("gpt_watch") or {}
        self.check("B11", "B11.16b must not fire: the default bound and no USAGE_CODEX_BIN (credits approved, so "
                   "no reading starts): the spawn line says default for both and no warning line is written",
                   self.ran_unstopped(r) and not r["config"] and sw.get("armed") is True
                   and sw.get("reader_bin_src") == "default" and sw.get("read_bound_src") == "default"
                   and r["reads"] == 0, self.detail(r))

    def b11_undecided(self, fx, to):
        fx.open_run("r11g")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r11g", "W7", env=fx.env(USAGE_CODEX_BIN="/usr/bin/false"), sleep_s=8)
        line = (r["lines"] or [{}])[0]
        self.check("B11", "B11.7 cannot decide, unreadable: the reader's app-server fails for the whole lane: the "
                   "lane completes with no stop in the shipped tree, one watch line (unreadable, with the "
                   "reader's reason) whose what raises the console's alert (\"warning: gpt weekly watch "
                   "blind\"), and gpt_watch.unreadable 2 or more",
                   self.ran_unstopped(r) and len(r["lines"]) == 1 and line.get("verdict") == "unreadable"
                   and line.get("reason") and str(line.get("what")).startswith("warning: gpt weekly watch blind")
                   and r["watch"].get("unreadable", 0) >= 2, self.detail(r))
        fx.open_run("r11h")
        self.reset_gpt(fx, mode="silent")
        r = self.run_watched(fx, "r11h", "W8", env=fx.env(AIMYTH_USAGE_CHECK_TIMEOUT_S="1"), sleep_s=8)
        line = (r["lines"] or [{}])[0]
        self.timing("B11", "B11.8 close after the stand-in lane's exit", close_after_exit_s=r["close_after_exit"])
        self.check("B11", "B11.8 cannot decide, late: a silent app-server under the 1 s hook: completed with no "
                   "stop, one watch line unreadable \"timed out\", and the close follows the stand-in lane's exit "
                   "within 1 + 5 s",
                   self.ran_unstopped(r) and len(r["lines"]) == 1 and line.get("verdict") == "unreadable"
                   and "timed out" in str(line.get("reason")) and r["close_after_exit"] is not None
                   and r["close_after_exit"] <= 6, self.detail(r))
        fx.open_run("r11i")
        self.reset_gpt(fx, mode="sequence", steps=[50, "fail", 100])
        r = self.run_watched(fx, "r11i", "W9")
        self.check("B11", "B11.9 unreadable, then 100, counted from the start check's call (50, then fail, then "
                   "100): two watch lines, unreadable then exhausted, and the lane stopped at the watch's second "
                   "reading", [l.get("verdict") for l in r["lines"]] == ["unreadable", "exhausted"]
                   and self.stopped(r, 100) and r["watch"].get("readings") == 2, self.detail(r))
        default = self.W
        for leg, fault, kind in (("B11.14a", "raise", "RuntimeError"), ("B11.14b", "exit", "SystemExit")):
            self.use(self.mode_tree("watch2-" + fault, fault=fault, GPT_WATCH_EVERY_S=2))
            try:
                fx.open_run("r11" + fault)
                self.reset_gpt(fx, mode="sequence", steps=[50, 77, 100])
                r = self.run_watched(fx, "r11" + fault, "WF" + fault[0].upper())
            finally:
                self.use(default)
            self.check("B11", "%s a tick that raises (critic CR-T2b2 finding 2): a planted %s at the sentinel "
                       "figure 77 on the watch's first reading: one watch line verdict error naming %s, the "
                       "watch goes on, and its next tick reads 100 and stops the lane" % (leg, kind, kind),
                       [l.get("verdict") for l in r["lines"]] == ["error", "exhausted"]
                       and kind in str(r["lines"][0].get("reason")) and self.stopped(r, 100)
                       and r["watch"].get("errors") == 1 and not r["watch"].get("ended_early"), self.detail(r))

    def b11_meet(self, fx):
        """B11.13: the stand-down's stop and the lane's own watch meet on one lane."""
        default = self.W
        self.use(self.mode_tree("watch4-enforce", GPT_WATCH_EVERY_S=4, **{LEGACY_GUARD: "enforce"}))
        try:
            fx.open_run("r11k")
            self.reset_gpt(fx)
            weekly = ["You've hit your weekly limit · resets %s" % stamp(time.time() + 600)]
            r = self.run_watched(fx, "r11k", "W13", switch=lambda: (fx.set("gpt", "figure", "100"),
                                                                    fx.starter("r11k", weekly, timeout=90)))
        finally:
            self.use(default)
        sd = (kinds(r["ev"], "supervisor-stood-down") or [{}])[-1]
        kills = [k.get("lane") for k in (sd.get("gpt_at_stand_down") or {}).get("kills") or []]
        stops = [l for l in r["lines"] if l.get("action") == "stop"]
        self.check("B11", "B11.13 two stops, one lane: a stand-down at 100 (enforcing) kills the lane through the "
                   "real codex-lane.py kill while its own watch is due: exactly one lane-closed, killed; at most "
                   "one of the two stops acts (the stand-down's kill or the watch's stop line, never both), and "
                   "no watch error", r["closes"] == 1 and r["close"].get("exit_class") == "killed"
                   and (kills == ["W13"]) != bool(stops) and len(stops) <= 1
                   and not [l for l in r["lines"] if l.get("verdict") == "error"],
                   dict(self.detail(r), kills=kills))

    def b12(self):
        """B12: the watch's own bound, and its exit when the lane ends (a mode copy reading every 2 s)."""
        default = self.W
        fx = Fx(self, "b12")
        self.use(self.mode_tree("watch2", GPT_WATCH_EVERY_S=2))
        try:
            self.b12_legs(fx)
        finally:
            self.use(default)

    def b12_legs(self, fx):
        silent = lambda: fx.set("gpt", "mode", "silent")
        fx.open_run("r12a")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r12a", "X1", switch=silent, sleep_s=3)
        time.sleep(0.5)
        pids = [pid for c, s, rd, t, e in self.gpt_calls(fx) if c >= 2 for pid in (s, rd)]
        states = {pid: alive(pid) for pid in pids}
        self.timing("B12", "B12.1 in flight at the end", close_after_exit_s=r["close_after_exit"],
                    return_after_close_s=r["return_after_close"])
        self.check("B12", "B12.1 a reading in flight at the lane's end (the stand-in silent after lane-spawned, "
                   "the default 10 s bound, a 3 s lane): the close follows the lane's exit within 1 + 5 s, the "
                   "wrapper returns within GPT_WATCH_JOIN_S 6 s after it, gpt_watch.in_flight_at_end true, and "
                   "no reader or app-server of the watch's reading is alive once the wrapper has returned",
                   r["close_after_exit"] is not None and r["close_after_exit"] <= 6
                   and r["return_after_close"] is not None and r["return_after_close"] <= 7
                   and r["watch"].get("in_flight_at_end") is True and pids
                   and all(v is False for v in states.values()), dict(self.detail(r), pids=states))
        fx.open_run("r12b")
        self.reset_gpt(fx)
        when = {}

        def kill_during():
            silent()
            time.sleep(3.0)
            when["kill"] = time.time()
            fx.c("kill", "--run", "r12b", "--lane", "X2", "--reason", "suite kill during a hung reading")
        r = self.run_watched(fx, "r12b", "X2", switch=kill_during)
        took = None if r["closed_at"] is None or "kill" not in when else round(r["closed_at"] - when["kill"], 2)
        self.timing("B12", "B12.2 kill to close", kill_to_close_s=took)
        self.check("B12", "B12.2 an explicit kill during a hung reading: the lane closes killed within "
                   "KILL_GRACE_S + 2 s of the kill, not after the reading",
                   r["close"].get("exit_class") == "killed" and took is not None and took <= 7, self.detail(r))
        fx.open_run("r12c")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r12c", "X3", switch=silent, extra=("--silence-s", "3"))
        self.timing("B12", "B12.3 spawn line to stall close", to_close_s=r["to_close"])
        self.check("B12", "B12.3 silence during a hung reading (--silence-s 3, the stand-in lane silent after "
                   "thread.started): the lane closes stall within 3 + 1 + 5 s of its spawn line",
                   r["close"].get("exit_class") == "stall" and r["to_close"] is not None and r["to_close"] <= 9,
                   self.detail(r))
        fx.open_run("r12d")
        self.reset_gpt(fx)
        r = self.run_watched(fx, "r12d", "X4", sleep_s=8)
        calls = sorted((t, e) for c, s, rd, t, e in self.gpt_calls(fx) if c >= 2)
        overlap = any(calls[i + 1][0] < (calls[i][1] or float("inf")) for i in range(len(calls) - 1))
        self.check("B12", "B12.4 reading count, one at a time (every 2 s, an 8 s lane, GPT at 50): the watch's "
                   "calls number from 1 to ceil(8 / 2) = 4, and no two readings' start-to-end stamps overlap",
                   1 <= len(calls) <= 4 and not overlap and all(e is not None for _, e in calls),
                   dict(self.detail(r), calls=calls))
        self.b12_kill9(fx, silent)
        self.b12_files(fx)
        self.b12_bound(fx)

    def b12_bound(self, fx):
        """B12.7 (review V-T2b2, R2): the stop bound the code states holds with the reading time
        included. The worst case planted in the 2 s copy: each reading takes 8.5 s (inside the 10 s
        read bound), the line is crossed just after the watch's first reading samples 50 (so that
        reading still reads below), and the stand-in lane ignores SIGTERM, so the stop takes the
        whole 5 s grace. The stated bound is usage_windows.watch_stop_bound_s where the tree has it;
        a tree without it states checkpoint 3's bound, one interval + one reading's bound + 1 + 5
        (its usage_windows.py comment: "one interval, one reading's 10 s + 5 s bound, the runner's
        1 s tick and codex-lane.py's 5 s KILL_GRACE_S"). 8.5 s is set by judgement: long enough that
        two readings pass the older bound, short enough to stay inside the read bound."""
        fx.open_run("r12h")
        self.reset_gpt(fx, mode="delay")
        fx.set("gpt", "delay_s", "8.5")
        fx.set("gpt", "switch_call", "2")
        held = os.path.join(fx.dirs["codex"], "ignore_term")
        open(held, "w").close()
        try:
            r = self.run_watched(fx, "r12h", "X8", sleep_s=60, limit=90)
        finally:
            for p in (held, os.path.join(fx.dirs["gpt"], "delay_s"), os.path.join(fx.dirs["gpt"], "switch_call")):
                if os.path.exists(p):
                    os.remove(p)
        pids = os.path.join(fx.dirs["gpt"], "pids")
        switched = [float(l.split()[2]) for l in (open(pids).read().splitlines() if os.path.exists(pids) else [])
                    if l.startswith("switched 2 ")]
        sw = r["spawn"].get("gpt_watch") or {}
        every, bound = sw.get("every_s"), sw.get("read_bound_s")
        stated = fx.driver(os.path.join(self.W, "usage_windows.py"), "call", ["watch_stop_bound_s", every, bound])
        source = "watch_stop_bound_s"
        if not isinstance(stated, (int, float)) and isinstance(every, (int, float)) and isinstance(bound, (int, float)):
            stated, source = every + bound + 1 + 5, "checkpoint 3's stated bound (interval + one reading + 1 + 5)"
        took = None if r["closed_at"] is None or len(switched) != 1 else round(r["closed_at"] - switched[0], 2)
        readings = [round(e - t, 2) for c, s, rd, t, e in self.gpt_calls(fx) if c >= 2 and e is not None]
        self.timing("B12", "B12.7 crossing to close", took_s=took, stated_s=stated, readings_s=readings)
        self.check("B12", "B12.7 the stated stop bound holds with the reading time included (review V-T2b2, R2): "
                   "the line crossed while a reading that reads below is in flight, each reading about 8.5 s, "
                   "the lane ignoring SIGTERM: the lane is stopped (killed by its watch at 100, held) within "
                   "the bound the code states for its interval and read bound",
                   self.stopped(r, 100) and took is not None and isinstance(stated, (int, float))
                   and took <= stated, dict(self.detail(r), took=took, stated=stated, source=source,
                                            readings=readings))

    def b12_kill9(self, fx, silent):
        """B12.5: the wrapper killed outright during a reading."""
        fx.open_run("r12e")
        self.reset_gpt(fx)
        fx.set("codex", "sleep_s", "30")
        p = self.lane_bg(fx, "r12e", "X5")
        spawned = self.wait_for(fx, "r12e", lambda ev: kinds(ev, "lane-spawned", lane="X5"), 30)
        silent()
        deadline, reading = time.time() + 8, []
        while time.time() < deadline and not reading:
            reading = [(s, rd) for c, s, rd, t, e in self.gpt_calls(fx) if c >= 2]
            time.sleep(0.1)
        t_kill, gone_after = time.time(), None
        try:
            os.kill(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.wait()
        pids = [pid for pair in reading for pid in pair]
        while pids and time.time() < t_kill + 20:
            if all(alive(pid) is False for pid in pids):
                gone_after = round(time.time() - t_kill, 2)
                break
            time.sleep(0.2)
        lane_pid = (kinds(fx.events("r12e"), "lane-spawned", lane="X5") or [{}])[-1].get("pid")
        if isinstance(lane_pid, int):   # fixture hygiene: the orphaned stand-in lane and its group
            for kill in (lambda: os.killpg(lane_pid, signal.SIGKILL), lambda: os.kill(lane_pid, signal.SIGKILL)):
                try:
                    kill()
                except OSError:
                    pass
        self.clear_sleep(fx)
        self.timing("B12", "B12.5 SIGKILL to the reading's group gone", gone_after_s=gone_after)
        self.check("B12", "B12.5 the wrapper killed outright (SIGKILL) during a watch reading: the reader and its "
                   "app-server stand-in are gone within 10 + 5 + 1 s of the SIGKILL (the reader's own bound)",
                   spawned and bool(reading) and gone_after is not None and gone_after <= 16,
                   {"spawned": spawned, "reading": reading, "gone_after": gone_after})

    def b12_files(self, fx):
        """B12.6: a lane whose watch read GPT's week leaves the same files as one whose watch took no
        reading (credits approved), run and lane ids aside: the watch writes nothing but record lines."""
        def added(run, lane, *flags):
            before = self.listing(fx.store)
            fx.open_run(run, *flags)
            mid = self.listing(fx.store)
            r = self.run_watched(fx, run, lane, sleep_s=6)
            new = self.listing(fx.store) - mid
            norm = lambda x: re.sub(r"\d+", "#", re.sub(r"[0-9a-f]{8,}", "<id>", x.replace(run, "<run>")
                                                       .replace(lane, "<lane>")))
            return r, set(norm(x) for x in new), mid - before
        self.reset_gpt(fx)
        r1, read_files, _ = added("r12f", "X6")
        self.reset_gpt(fx)
        r2, quiet_files, _ = added("r12g", "X7", "--gpt-credits-approved", "yes")
        self.check("B12", "B12.6 nothing but record lines: the files a lane adds while its watch reads GPT's week "
                   "(2 or more readings) equal, run and lane ids aside, those of a lane whose watch takes no "
                   "reading (control: the reading lane's watch read at least twice)",
                   r1["watch"].get("readings", 0) >= 2 and r2["watch"].get("readings") == 0
                   and read_files == quiet_files and read_files,
                   {"reading": sorted(read_files ^ quiet_files)[:8], "counts": [r1["watch"].get("readings"),
                                                                                 r2["watch"].get("readings")]})

    def listing(self, root):
        out = set()
        for base, dirs, files in os.walk(root):
            for name in dirs + files:
                out.add(os.path.relpath(os.path.join(base, name), root))
        return out

    def b13(self):
        """B13: the mode split (GPT_LIMIT_MODE, GPT_STOP_MODE, GPT_UNREADABLE_MODE)."""
        default = self.W
        code = ("usage_windows.py", "codex-lane.py", "handsoff.py", "lane.py", "read-usage.py")
        texts = {}
        for name in code:
            p = os.path.join(self.W, name)
            texts[name] = open(p, encoding="utf-8").read() if os.path.isfile(p) else ""
        uw = texts["usage_windows.py"]
        assigned = lambda line: len(re.findall(r"^%s$" % re.escape(line), uw, re.M))
        counts = {line: assigned(line) for line in ('GPT_LIMIT_MODE = "enforce"', 'GPT_STOP_MODE = "enforce"',
                                                    'GPT_UNREADABLE_MODE = "trial"', "GPT_WATCH_EVERY_S = 600")}
        legacy = sum(t.count(LEGACY_GUARD) for t in texts.values()) \
            + open(os.path.abspath(__file__), encoding="utf-8").read().count(LEGACY_GUARD)
        control = texts["codex-lane.py"].count("GPT_LIMIT_MODE")
        self.check("B13", "B13.1 shipped constants: one assignment each of GPT_LIMIT_MODE \"enforce\", "
                   "GPT_STOP_MODE \"enforce\", GPT_UNREADABLE_MODE \"trial\" and GPT_WATCH_EVERY_S 600, and the "
                   "earlier single guard constant 0 times in the five code files and this suite (control: "
                   "GPT_LIMIT_MODE found in codex-lane.py)",
                   all(v == 1 for v in counts.values()) and legacy == 0 and control > 0,
                   {"counts": counts, "legacy": legacy, "control": control})
        fx = Fx(self, "b13")
        wrapdir = fx.path("killwrap")
        os.makedirs(wrapdir, exist_ok=True)
        with open(os.path.join(wrapdir, "codex-lane.py"), "w") as h:
            h.write(KILL_STUB.replace("{py}", sys.executable))
        self.use(self.mode_tree("split", GPT_UNREADABLE_MODE="enforce", GPT_STOP_MODE="trial"))
        try:
            fx.open_run("r13a")
            self.reset_gpt(fx, mode="fail")
            before = open(fx.record("r13a"), "rb").read()
            p = self.spawn(fx, "r13a", "U1")
            same = open(fx.record("r13a"), "rb").read() == before
            _, sd, _, calls, _ = self.b10_case(fx, "r13b", 100, wrapdir=wrapdir, log=fx.path("k-13.log"))
        finally:
            self.use(default)
        g = sd.get("gpt_at_stand_down") or {}
        self.check("B13", "B13.2 independence: one copy with GPT_UNREADABLE_MODE \"enforce\" and GPT_STOP_MODE "
                   "\"trial\": an unreadable start refuses (exit 2, the record unchanged), and a stand-down at 100 "
                   "in the same copy records would_stop and sends no kill",
                   p.returncode == 2 and same and g.get("would_stop") == ["C9"] and not calls
                   and g.get("mode") == "trial", {"rc": p.returncode, "same": same, "sd": g, "calls": calls})
        fx.open_run("r13c")
        self.reset_gpt(fx, mode="fail")
        p = self.spawn(fx, "r13c", "U2")
        chk = self.lane_open(fx, "r13c", "U2").get("usage_start_check") or {}
        self.check("B13", "B13.3a the unreadable start, shipped: the lane starts and records would_refuse "
                   "unreadable, mode trial", p.returncode == 0 and chk.get("mode") == "trial"
                   and (chk.get("would_refuse") or {}).get("verdict") == "unreadable", {"rc": p.returncode, "check": chk})
        self.use(self.mode_tree("enforce-unreadable", GPT_UNREADABLE_MODE="enforce"))
        try:
            before = open(fx.record("r13c"), "rb").read()
            p = self.spawn(fx, "r13c", "U3")
            same = open(fx.record("r13c"), "rb").read() == before
        finally:
            self.use(default)
        self.check("B13", "B13.3b the unreadable start, a copy with GPT_UNREADABLE_MODE \"enforce\": it refuses, "
                   "exit 2, nothing written", p.returncode == 2 and same and "nothing written" in p.stderr,
                   {"rc": p.returncode, "same": same, "err": p.stderr[-300:]})
        want = ("watch enforce", "watch trial", "stand-down enforce", "stand-down trial")
        self.check("B13", "B13.4 each stop in both values, from this run's own legs: the watch stops in enforce "
                   "(B11.1) and only records a would-stop in trial (B11.10); the stand-down kills in enforce "
                   "(B10.1) and records would_stop with no kill in trial (B10.1t)",
                   all(self.outcomes.get(k) is True for k in want),
                   {k: self.outcomes.get(k, "not run (B10 and B11 run before B13)") for k in want})
        text = 'X = 1\nGPT_LIMIT_MODE = "enforce"\n'
        absent_text, absent = patch_constants(text, {"GPT_STOP_MODE": "trial"}, "self-test")
        one, none = patch_constants(text, {"GPT_LIMIT_MODE": "trial"}, "self-test")
        try:
            patch_constants(text + 'GPT_LIMIT_MODE = "trial"\n', {"GPT_LIMIT_MODE": "enforce"}, "self-test")
            doubled = False
        except Probe:
            doubled = True
        self.check("B13", "B13.5 a constant absent from a tree: the mode copy is made unchanged and the name is "
                   "returned absent (its legs then report FAIL, the suite does not exit 2); a doubled assignment "
                   "is a broken premise; control: a single assignment is set",
                   absent_text == text and absent == ["GPT_STOP_MODE"] and doubled
                   and 'GPT_LIMIT_MODE = "trial"' in one and none == [],
                   {"absent": absent, "doubled": doubled, "one": one})

    def b14(self):
        """B14: a detached refusal writes nothing (review V-T2b, Claim 8): the caller reads before the
        detach, and the worker's own refusal names what it leaves."""
        fx = Fx(self, "b14")
        fx.open_run("r14a")
        self.reset_gpt(fx, figure="100")
        before = self.listing(fx.store)
        p = self.spawn(fx, "r14a", "D1", "--detach", "--no-wait")
        time.sleep(1.0)
        after = self.listing(fx.store)
        fx.set("gpt", "figure", "40")
        p2 = self.spawn(fx, "r14a", "D2", "--detach", "--no-wait")
        self.wait_for(fx, "r14a", lambda ev: kinds(ev, "lane-closed", lane="D2"), 30)
        made = self.listing(fx.store) - after
        self.check("B14", "B14.1 a detached spawn at 100 without credits: exit 2 in the caller with the refusal on "
                   "its stderr, and a listing of the store and its .a3 namespace unchanged (no detach log, no "
                   "lock, no record line); control, same run: a detached spawn at 40 makes its detach log and "
                   "its lane-open, so the listing sees files when they are made",
                   p.returncode == 2 and "approves no credits (N19): no GPT start; nothing written" in p.stderr
                   and before == after and any("detached-D2" in x for x in made)
                   and kinds(fx.events("r14a"), "lane-open", lane="D2"),
                   {"rc": p.returncode, "err": p.stderr[-300:], "new": sorted(after - before)[:6], "rc2": p2.returncode})
        log = os.path.join(fx.store, "spawn-records", "r14a-detached-D2.log")
        log_before = open(log, "rb").read() if os.path.exists(log) else None
        locks = sorted(x for x in self.listing(fx.store) if x.endswith(".lock"))
        fx.set("gpt", "figure", "100")
        p = fx.c("resume", "--run", "r14a", "--lane", "D2", "--brief", fx.path("follow.md"), "--codex",
                 fx.path("bin", "codex"), "--viewer", "none", "--silence-s", "0", "--deadline-s", "60",
                 "--detach", "--no-wait")
        time.sleep(1.0)
        self.check("B14", "B14.2 a detached resume at 100 of a closed lane: exit 2 in the caller, no lane-resumed, "
                   "nothing appended to the lane's detach log, and no new lock",
                   p.returncode == 2 and not kinds(fx.events("r14a"), "lane-resumed", lane="D2")
                   and log_before is not None and open(log, "rb").read() == log_before
                   and sorted(x for x in self.listing(fx.store) if x.endswith(".lock")) == locks,
                   {"rc": p.returncode, "err": p.stderr[-300:]})
        self.reset_gpt(fx, figure="30")
        p = self.spawn(fx, "r14a", "D3", "--detach", "--no-wait")
        self.wait_for(fx, "r14a", lambda ev: kinds(ev, "lane-closed", lane="D3"), 30)
        self.check("B14", "B14.3 two readings (replaces B06's detached \"reads once\" leg): a detached spawn at 30 "
                   "reads GPT's week exactly twice, the caller and then the worker, and the lane starts",
                   p.returncode == 0 and fx.count("gpt") == 2 and kinds(fx.events("r14a"), "lane-open", lane="D3"),
                   {"rc": p.returncode, "reads": fx.count("gpt")})
        self.reset_gpt(fx, mode="sequence", steps=[50, 100])
        p = self.spawn(fx, "r14a", "D4", "--detach", "--no-wait")
        if p.returncode == 0:   # a tree whose worker starts the lane: let it close (fixture hygiene)
            self.wait_for(fx, "r14a", lambda ev: kinds(ev, "lane-closed", lane="D4"), 20)
        log = os.path.join(fx.store, "spawn-records", "r14a-detached-D4.log")
        text = open(log).read() if os.path.exists(log) else ""
        self.check("B14", "B14.4 the worker's own refusal (50 for the caller's reading, then 100 for the "
                   "worker's): exit 2, no lane-open, and the detach log's line says what remains (\"no lane-open "
                   "written; this worker's detach log ... and the lane's A3 gate lock remain\")",
                   p.returncode == 2 and not kinds(fx.events("r14a"), "lane-open", lane="D4")
                   and "no lane-open written; this worker's detach log (which holds this line) and the lane's A3 "
                       "gate lock remain" in text, {"rc": p.returncode, "log": text[-300:]})
        self.reset_gpt(fx, figure="100")
        before, jbefore, lbefore = open(fx.record("r14a"), "rb").read(), self.journals(fx, "r14a"), self.listing(fx.store)
        p = self.spawn(fx, "r14a", "D5")
        changed = self.listing(fx.store) ^ lbefore
        self.check("B14", "B14.5 a foreground refusal: exit 2, the record and its A3 journals unchanged, and the "
                   "one new path in the store is the lane's empty A3 gate lock (taken by lane.a3_entry before the "
                   "check), which the refusal now names beside \"nothing written\"",
                   p.returncode == 2 and "no GPT start; nothing written (the lane's empty A3 gate lock file aside"
                   in p.stderr and open(fx.record("r14a"), "rb").read() == before
                   and self.journals(fx, "r14a") == jbefore and len(changed) <= 1
                   and all(x.endswith(".lock") and ".a3" in x for x in changed),
                   {"rc": p.returncode, "err": p.stderr[-300:], "record_same": open(fx.record("r14a"), "rb").read() == before,
                    "journals_same": self.journals(fx, "r14a") == jbefore,
                    "listing_changed": sorted(self.listing(fx.store) ^ lbefore)[:8]})

    def stop_probe(self, fx, case):
        """One STOP_PROBE case against this tree's codex-lane.py, in a fresh process."""
        work = fx.path("work", "stop-" + case)
        os.makedirs(work, exist_ok=True)
        p = self.run([sys.executable, "-B", "-c", STOP_PROBE, self.W, case, work], fx.env(), 60)
        try:
            return json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"crash": (p.stdout + p.stderr)[-600:]}

    def b15(self):
        """B15 (review V-T8-G2 point 8): a stop ends the lane's whole process group. The shipped stop
        sent SIGKILL only while the leader lived, and through the leader's pid, so a member that
        ignores SIGTERM outlived a leader that exits on it; and a pid reaped and reused would have
        led it to another group. Now every stop signal goes to the group id recorded at the start,
        the SIGKILL after the leader is gone too, each only once the group is proven the lane's own."""
        fx = Fx(self, "b15")
        r = self.stop_probe(fx, "member")
        kill = [s for s in r.get("stop_group") or [] if s.get("signal") == "SIGKILL"]
        self.check("B15", "B15.1 must fire: a stopped lane whose leader exits on SIGTERM and whose member ignores it "
                   "(a runner around a stand-in group): the member is gone after the stop, the SIGKILL sent to the "
                   "group after the leader was reaped, on the proof of a member seen while it was not",
                   r.get("leader_exit") == -signal.SIGTERM and r.get("member_gone") is True and len(kill) == 1
                   and kill[0].get("sent") is True and kill[0].get("leader_reaped") is True, r)
        r = self.stop_probe(fx, "reused")
        self.check("B15", "B15.2 must not fire, a reused id: the leader reaped before the stop and its pid standing "
                   "(by a spy) for a process in another group: no signal is sent to any group or pid, and the stop "
                   "records that the group could not be proven the lane's",
                   r.get("calls") == [] and r.get("stop_group")
                   and all(s.get("sent") is False and "not signalled" in str(s.get("proof"))
                           for s in r["stop_group"]), r)
        r = self.stop_probe(fx, "decoy")
        self.check("B15", "B15.3 must not fire, a live group under the recorded id: the lane's group seen, then ended "
                   "whole and its leader reaped, and an unrelated live group holding the recorded id: that group's "
                   "leader and its SIGTERM-ignoring member are both alive after the stop",
                   r.get("decoy_leader_alive") is True and r.get("decoy_member_alive") is True, r)
        r = self.stop_probe(fx, "polite")
        term = [s for s in r.get("stop_group") or [] if s.get("signal") == "SIGTERM"]
        self.check("B15", "B15.4 control, an ordinary stop: a lane whose leader and member both exit on SIGTERM is gone "
                   "after the stop (the SIGTERM sent to the group while the leader was unreaped, where the tree "
                   "records it)",
                   r.get("leader_exit") == -signal.SIGTERM and r.get("member_gone") is True
                   and (not term or (term[0].get("sent") is True and term[0].get("leader_reaped") is False)), r)
        self.b15_wrapper(fx)

    def b15_wrapper(self, fx):
        """B15.5: the same through the real wrapper: a Codex lane over the stand-in codex, whose tool
        command ignores SIGTERM, stopped by `codex-lane.py kill`."""
        fx.open_run("r15e")
        self.reset_gpt(fx)
        held = os.path.join(fx.dirs["codex"], "term_child")
        pidfile = os.path.join(fx.dirs["codex"], "term_child.pid")
        open(held, "w").close()

        def kill_after_member():
            end = time.time() + 20
            while time.time() < end and not (os.path.exists(pidfile) and open(pidfile).read().strip()):
                time.sleep(0.05)
            fx.c("kill", "--run", "r15e", "--lane", "K1", "--reason", "suite stop of a member that ignores SIGTERM")
        member = None
        try:
            r = self.run_watched(fx, "r15e", "K1", switch=kill_after_member, sleep_s=60, limit=60)
            member = int(open(pidfile).read()) if os.path.exists(pidfile) else None
            gone = None
            if member is not None:
                end = time.time() + 3
                while time.time() < end and alive(member):
                    time.sleep(0.05)
                gone = alive(member) is False
            spawn, close = r["spawn"], r["close"]
            kill = [s for s in close.get("stop_group") or [] if s.get("signal") == "SIGKILL"]
            self.check("B15", "B15.5 must fire, through the wrapper: a Codex lane whose tool command ignores SIGTERM, "
                       "stopped by codex-lane.py kill: it closes killed, the member is gone once the wrapper has "
                       "returned, its lane-spawned records the group id (pgid, its pid), and its close's stop_group "
                       "shows the SIGKILL sent to that group",
                       close.get("exit_class") == "killed" and gone is True
                       and isinstance(spawn.get("pid"), int) and spawn.get("pgid") == spawn.get("pid")
                       and any(s.get("sent") is True and s.get("pgid") == spawn.get("pid") for s in kill),
                       {"member": member, "gone": gone, "pgid": spawn.get("pgid"), "pid": spawn.get("pid"),
                        "close": {k: close.get(k) for k in ("exit_class", "killed_by", "stop_group")},
                        "out": r["out"]})
        finally:
            if os.path.exists(held):
                os.remove(held)
            if member is not None and alive(member):   # fixture hygiene where the stop left it
                try:
                    os.kill(member, signal.SIGKILL)
                except OSError:
                    pass
            self.clear_sleep(fx)

    def w03(self):
        """W03: no real `claude` or `codex` was reachable (design W03): shims named for both stood first
        on every fixture's PATH, so a leg that reached either by PATH left a line in its log."""
        logs = {n: os.path.join(self.shims, n + ".log") for n in ("claude", "codex")}
        seen = {n: (open(p).read() if os.path.exists(p) else "") for n, p in logs.items()}
        subprocess.run([os.path.join(self.shims, "codex"), "w03-control"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        control = open(logs["codex"]).read() if os.path.exists(logs["codex"]) else ""
        self.check("W03", "no leg reached a `claude` or `codex` on PATH: both shims' logs are empty after every "
                   "other group (control: the codex shim run once directly logs exactly that one line)",
                   seen["claude"] == "" and seen["codex"] == "" and control.splitlines() == ["w03-control"],
                   {"claude": seen["claude"][-200:], "codex": seen["codex"][-200:], "control": control[-100:]})

    # ------------------------------------------------------------------ W01 -------------------
    def manifest(self, root):
        out = []
        for base, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(files):
                p = os.path.join(base, name)
                out.append("%s %o %s" % (sha(open(p, "rb").read()), os.stat(p).st_mode & 0o777,
                                         os.path.relpath(p, root)))
        return out

    def w01(self, before):
        after = self.manifest(self.W)
        copy = os.path.join(self.root, "manifest-control")
        shutil.copytree(self.W, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        target = os.path.join(copy, "read-usage.py")
        data = bytearray(open(target, "rb").read())
        data[0:1] = b"#" if data[0:1] != b"#" else b"!"
        open(target, "wb").write(bytes(data))
        planted = self.manifest(copy)
        self.check("W01", "the wrappers directory's checksum-and-mode manifest is unchanged after every "
                   "group (control: a planted same-length change shows)",
                   before == after and planted != before and len(planted) == len(before),
                   {"changed": sorted(set(before) ^ set(after))[:6]})
        pattern = re.compile(r"open\([^)]*['\"][wax]\+?b?['\"]|write_atomic|os\.(remove|unlink|rename|replace|makedirs|mkdir)\("
                             r"|shutil\.(copy|copy2|copyfile|copytree|move|rmtree)\(")
        src = open(self.R, encoding="utf-8").read()
        hits = [l for l in src.splitlines() if pattern.search(l)]
        control = pattern.search("    open(path, 'w').write(x)") is not None
        self.check("W01", "the reader's source holds no file-write call (control: a planted open(..., 'w') "
                   "line hits)", not hits and control, hits[:4])

    def run_all(self):
        before = self.manifest(self.W) if self.selected("W01") else None
        for gid in GROUPS[:-1]:
            if self.selected(gid):
                print("--- %s" % gid, flush=True)
                try:
                    getattr(self, gid.lower())()
                except Probe:
                    raise
                except Exception as exc:   # a fixture crash is a premise failure, never an expected failure
                    raise Probe("%s fixture crashed: %s: %s" % (gid, type(exc).__name__, exc))
        if self.selected("W01"):
            print("--- W01", flush=True)
            self.w01(before)
        for line in self.denied:
            print("needs process inspection outside this sandbox: %s" % line)
        total = self.passed + self.failed
        print("FAIL %d/%d" % (self.failed, total) if self.failed else "PASS %d/%d" % (self.passed, total))
        return 1 if self.failed else 0


def main():
    ap = argparse.ArgumentParser(description="limit policy 1 suite (package B)")
    ap.add_argument("--wrappers", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--fixture-root", default=None)
    ap.add_argument("--only", action="append", choices=GROUPS, default=[])
    ap.add_argument("--keep", action="store_true", help="keep the fixture tree for a post-mortem")
    args = ap.parse_args()
    suite = None
    try:
        suite = Suite(args)
        return suite.run_all()
    except Probe as exc:
        print("PROBE FAILED: %s" % exc)
        return 2
    finally:
        if suite is not None and not args.keep:
            shutil.rmtree(suite.root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
