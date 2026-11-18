"""usage_windows.py — the basic window meter shared by handsoff.py, lane.py and codex-lane.py.

Package A of the window-meter design (revision 3, section 4). Every function here returns data or
text and writes no file; the one process it starts is the sibling usage reader, read-usage.py
`--only both --format json` (package B's JSON form), in its own process group.

- `UsageRead`: one reading of Claude's 5-hour and weekly windows and GPT's week, started beside
  the dollar work and joined against ONE deadline (READ_S to read plus REAP_S to reap).
- `sample_delta`: each window's change in percentage points against the immediately preceding
  reading, or null with its reason.
- `load_preflight_data`: the pre-flight's usage attachment, validated before any write.
- `item_at_open`: a lane's item at lane-open (explicit, inferred from the last boundary, or
  unassigned), the one rule both wrappers use.
- `close_accounting`: the close-only rows (helpers, items, totals, comparisons), per window and
  never summed across windows.
- `render_windows`: the three owned Spend bullets, readings and deltas only.

A percentage is used capacity (100 = the whole window used); a difference between percentages is
in percentage points (pp). The readings' source for a Claude window is the canonical window name
B's reader gives (`claude_5h`, `claude_week`), so a change in the figure alone is a measured change.

Rebuilt alone on the 9 November 2026 delegate folder (decided line DW-20261021-2), with the limit
policy's shared parts beside it, so the package carries one process-group runner, not two:
- `bounded_run`, `usage_check_bounds`, `read_json`: the one runner, also used by handsoff.py's
  limit-policy readings, codex-lane.py's GPT start check and each Codex lane's GPT watch (10 s to
  read plus 5 s to reap; the watch's reading can be cancelled when its lane ends).
- `credits_effective`, `gpt_verdict`, `gpt_stop_action`: the GPT credits rule (owner decision
  N19), the weekly verdict and the stop rule for running GPT work, the one copy both wrappers read.
- `GPT_LIMIT_MODE`, `GPT_STOP_MODE` and `GPT_UNREADABLE_MODE`: the three mode constants, and
  `GPT_WATCH_EVERY_S`, the watch's cadence (below).
A lane-open's inferred item rides as `usage_item`, `usage_item_source` and `usage_item_locator`;
the explicit `item` key stays the launchers' own (`spawn --item`), which the console reads.
"""
import hashlib
import json
import math
import os
import select
import signal
import subprocess
import sys
import threading
import time

SCHEMA = 1
WINDOWS = ("claude_5h", "claude_week", "gpt_week")
LABELS = {"claude_5h": "Claude 5-hour window", "claude_week": "Claude weekly window",
          "gpt_week": "GPT weekly window"}
# A window's length in minutes: 5 x 60 = 300 and 7 x 24 x 60 = 10,080.
WINDOW_MINUTES = {"claude_5h": 300, "claude_week": 10080, "gpt_week": 10080}
READ_S = 90   # the reader's own --timeout-s (read-usage.py TIMEOUT_S); set by judgement, unmeasured
REAP_S = 5    # to end and reap the reader's group after the read bound; set by judgement, unmeasured
UNITS = {"claude": ("usd_list",),
         "gpt": ("fresh_input_mtokens", "cached_input_mtokens", "output_mtokens")}
MTOKENS = 1000000.0   # a million tokens: the raw count divided by 1,000,000
READING_EVENTS = ("run-open", "phase-boundary", "run-close")
JUDGEMENT = "set by judgement, unmeasured"
# The limit policy's version (handsoff.py LIMIT_POLICY_VERSION; a suite leg checks the two agree):
# a grants file without it is a run opened before limit policy 1.
LIMIT_POLICY_VERSION = 1
# One GPT reading for a limit decision (package B's bounds): 10 s to read plus 5 s to reap, one
# outer deadline over both, under lane.py's ACK_WAIT_S of 60 s; each set by judgement, unmeasured.
USAGE_CHECK_READ_S = 10
USAGE_CHECK_REAP_S = 5
USAGE_CHECK_ENV = "AIMYTH_USAGE_CHECK_TIMEOUT_S"   # lowers the read bound within (0, 10] only
# The three mode constants of the GPT blocks (line 2's replacement design splits the earlier single
# guard constant into the last two). Each is "trial" (record what it would refuse or stop, and block
# nothing) or "enforce". All three values are settled by the owner's word of 9 November 2026,
# 23:29:59 GMT ("yes for all as you recommended", to his walk-through's Part 4, item 47 (a): the
# stops live from the install, running GPT work stopped at GPT's weekly limit, the failed-reading
# case left in trial until the trial counts how often a reading fails). No flag, grant or
# environment variable changes any of them, so nothing a head writes lowers one; a suite flips them
# only in a throwaway copy of the folder.
# - GPT_LIMIT_MODE: his decided default itself (N19, "the default for GPT limit should be stop when
#   weekly limit hit, and only proceed if preflight approve with credits"): a GPT start (spawn,
#   resume, beat) refused while a measured weekly figure reads 100 % or more and the pre-flight
#   approved no credits at run-open. "enforce" from the install, by his word above; "trial" undoes it.
# - GPT_STOP_MODE: GPT work already running, stopped at a measured weekly figure of 100 % or more
#   without approved credits: each Codex lane's own watch (codex-lane.py Runner) and the
#   supervisor's stop at a stand-down, both through gpt_stop_action. "enforce" from the install, by
#   his word above (item 84 (a) of the second night report of 9 November 2026); "trial" makes both
#   record would_stop and send nothing.
# - GPT_UNREADABLE_MODE: a GPT start whose reading is unreadable, refused unless credits are
#   approved (question 2's option (b)). It stays in "trial" by his word above until the trial counts
#   how often a reading fails: the start proceeds and records would_refuse. No mode governs an
#   unreadable reading while a lane runs: it never stops a running lane (question R3).
GPT_LIMIT_MODE = "enforce"
GPT_STOP_MODE = "enforce"
GPT_UNREADABLE_MODE = "trial"
MODES = ("trial", "enforce")
# The GPT watch's cadence: one reading of GPT's week every GPT_WATCH_EVERY_S seconds while an
# armed Codex lane runs; 600 s is set by judgement, unmeasured (question R2), and kept by the
# owner's word above until two runs measure how fast GPT's week rises. The watch waits a full
# interval after each reading returns, so a lane that crosses 100 % runs at most
# 15 + 600 + 15 + 1 + 5 = 636 s more before its stop completes (watch_stop_bound_s; review V-T2b2,
# R2): the reading in flight when the line is crossed (it can read below and still take its whole
# 10 s + 5 s bound), one interval, the next reading's 15 s bound, the runner's 1 s tick and
# codex-lane.py's 5 s KILL_GRACE_S. Where the line is crossed during the start check's own reading,
# the lane's start between that reading and its first interval adds its own time (unmeasured).
GPT_WATCH_EVERY_S = 600
# The stop bound's last two parts, mirrored from codex-lane.py so the report's sentence states one
# figure: the runner's tick (Runner._watch_run, "a poll a second") and KILL_GRACE_S (a suite leg
# checks the two files agree).
WATCH_TICK_S = 1
WATCH_GRACE_S = 5
# The wrapper's wait for a cancelled reading's process group at the lane's end: the 5 s reap
# allowance plus 1 s for the cancel to be seen and the thread to return; set by judgement, unmeasured.
GPT_WATCH_JOIN_S = 6


# ------------------------------------------------------------------ one reading -------------

def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) + (".%06d" % int((ts % 1) * 1e6)) \
        + time.strftime("%z", time.localtime(ts))


def bounded_run(cmd, read_s, reap_s, env=None, cancel=None):
    """One child in its own process group under one outer deadline: read_s to read its output
    and exit, then at most reap_s to end and reap it (SIGTERM, then SIGKILL at half the
    allowance). Pipes are read with select against the deadline and closed by this side, so a
    pipe a group member keeps open never extends the read. Never raises for the child. The one
    runner of the package: the meter's readings and the limit policy's readings both use it.
    `cancel`, where given (a threading.Event: a Codex lane's GPT watch, set when its lane ends),
    is checked at each pass of both read loops, at least every 0.25 s: once set it ends the read as
    the bound would, with the whole reap allowance counted from that moment, and the result says
    `cancelled: true`. With cancel None the runner is as before and the result has no such key."""
    t0 = time.monotonic()
    read_end, deadline = t0 + read_s, t0 + read_s + reap_s
    out = {"rc": None, "stdout": "", "stderr": "", "timed_out": False, "reaped": True,
           "kept_pipe": False, "elapsed": 0.0, "error": None}
    if cancel is not None:
        out["cancelled"] = False
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, start_new_session=True)
    except OSError as exc:
        out["error"] = str(exc)
        return out
    fo, fe = proc.stdout.fileno(), proc.stderr.fileno()
    bufs = {fo: bytearray(), fe: bytearray()}
    live = set(bufs)
    while live:
        if cancel is not None and cancel.is_set():
            out["cancelled"] = True
            break
        left = read_end - time.monotonic()
        if left <= 0:
            out["timed_out"] = True
            break
        exited = proc.poll() is not None
        ready, _, _ = select.select(list(live), [], [], 0 if exited else min(left, 0.25))
        if exited and not ready:
            break
        for fd in ready:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                chunk = b""
            if chunk:
                bufs[fd].extend(chunk)
            else:
                live.discard(fd)
    while not out["timed_out"] and not out.get("cancelled") and proc.poll() is None:
        if cancel is not None and cancel.is_set():
            out["cancelled"] = True
            break
        if time.monotonic() >= read_end:
            out["timed_out"] = True
            break
        time.sleep(0.02)
    if out.get("cancelled"):
        # The reap allowance runs from the cancel, not from the read's start (critic CR-T2b2
        # finding 8), so a cancelled group is ended inside reap_s of the lane's end.
        deadline = time.monotonic() + reap_s
    out["kept_pipe"] = bool(live) and not out.get("cancelled")
    if out["timed_out"] or out.get("cancelled") or live:
        for sig, share in ((signal.SIGTERM, 0.5), (signal.SIGKILL, 1.0)):
            try:
                os.killpg(proc.pid, sig)
            except OSError:
                pass
            until = time.monotonic() + max(0.0, deadline - time.monotonic()) * share
            while proc.poll() is None and time.monotonic() < until:
                time.sleep(0.02)
    for pipe in (proc.stdout, proc.stderr):
        try:
            pipe.close()
        except OSError:
            pass
    out["reaped"] = proc.poll() is not None
    out["rc"] = proc.returncode if out["reaped"] else None
    out["stdout"] = bytes(bufs[fo]).decode("utf-8", "replace")
    out["stderr"] = bytes(bufs[fe]).decode("utf-8", "replace")
    out["elapsed"] = round(time.monotonic() - t0, 2)
    return out


def usage_check_bounds(warn=None):
    """(read bound, reap allowance) in seconds for one limit-policy reading: USAGE_CHECK_READ_S,
    lowered by AIMYTH_USAGE_CHECK_TIMEOUT_S only within (0, 10]; any other value is ignored, with
    one line through `warn` where the caller gives one. The reap allowance is fixed."""
    read_s = USAGE_CHECK_READ_S
    raw = os.environ.get(USAGE_CHECK_ENV)
    if raw not in (None, ""):
        try:
            value = float(raw)
        except ValueError:
            value = None
        if value is not None and value == value and 0 < value <= USAGE_CHECK_READ_S:
            read_s = value
        elif warn is not None:
            warn("%s=%r ignored: it is accepted only within (0, %d] s, so the read bound stays "
                 "%d s" % (USAGE_CHECK_ENV, raw, USAGE_CHECK_READ_S, USAGE_CHECK_READ_S))
    return read_s, USAGE_CHECK_REAP_S


def reader_object(run, read_s):
    """(object, reason) from a bounded_run of read-usage.py --format json: the object where the
    reader exited 0 or 1 with one JSON object carrying `windows`, else None and why."""
    if run["error"]:
        return None, "the reader could not start: %s" % run["error"]
    if run.get("cancelled"):
        return None, ("cancelled: the lane ended during the reading (the reader's process group was "
                      "ended%s)" % ("" if run["reaped"] else "; it was not reaped in time"))
    if run["timed_out"]:
        return None, ("timed out after %g s (the reader's process group was ended%s)"
                      % (read_s, "" if run["reaped"] else "; it was not reaped in time"))
    if run["rc"] not in (0, 1):
        return None, "reader exit %s: %s" % (run["rc"], _one_line(run["stderr"] or run["stdout"])
                                             or "no output")
    try:
        obj = json.loads(run["stdout"])
    except ValueError:
        return None, "invalid JSON from the reader: %s" % (_one_line(run["stdout"], 120) or "empty")
    if not isinstance(obj, dict) or not isinstance(obj.get("windows"), dict):
        return None, "invalid JSON from the reader: no windows object"
    return obj, None


def read_json(here, only, warn=None, cancel=None):
    """One limit-policy reading through the sibling read-usage.py --only <only> --format json, in
    its own process group under the 15 s outer bound (usage_check_bounds): (object or None,
    reason, elapsed seconds). Writes nothing; the reader writes nothing. `cancel` is bounded_run's
    (the GPT watch's end); None leaves the reading as before."""
    read_s, reap_s = usage_check_bounds(warn)
    cmd = [sys.executable, "-B", os.path.join(here, "read-usage.py"), "--only", only,
           "--format", "json", "--timeout-s", str(max(1, int(math.ceil(read_s))))]
    run = bounded_run(cmd, read_s, reap_s, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                      cancel=cancel)
    obj, reason = reader_object(run, read_s)
    return obj, reason, run["elapsed"]


def gpt_verdict(obj):
    """(verdict, figure, evidence) for GPT's week from a reader object: `exhausted` where any
    weekly evidence reads 100 or more (raw, never clamped, read before the window, so two
    differing windows with one at 100 still read exhausted), `below` where the week is measured
    under 100, else `unreadable` (no weekly evidence at 100 and no measured week)."""
    evidence = [e for e in ((obj or {}).get("gpt_week_evidence") or []) if isinstance(e, dict)]
    hot = [e for e in evidence if isinstance(e.get("used_pct"), (int, float))
           and not isinstance(e.get("used_pct"), bool) and e["used_pct"] >= 100]
    if hot:
        top = max(hot, key=lambda e: e["used_pct"])
        return "exhausted", top["used_pct"], evidence
    week = ((obj or {}).get("windows") or {}).get("gpt_week")
    figure = (week.get("used_pct") if isinstance(week, dict) and week.get("status") == "measured"
              else None)
    if _figure(figure) is not None:
        return "below", figure, evidence
    return "unreadable", None, evidence


def credits_effective(payload, events):
    """(approved, source): GPT credits count as approved only where the grants file is a limit
    policy 1 file holding JSON true AND the run's run-open event holds `gpt_credits_approved: true`
    (N19; package B's rule N4): run-open is written once, so a file raised by hand after a false
    run-open reads false. A file without limit_policy_version (a run opened before the policy, or
    no file) reads false."""
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("limit_policy_version") != LIMIT_POLICY_VERSION:
        return False, ("default (no grants file)" if not payload
                       else "default (no limit_policy_version: a run opened before limit policy %d)"
                       % LIMIT_POLICY_VERSION)
    value = payload.get("gpt_credits_approved")
    opened = None
    for ev in events or []:
        if isinstance(ev, dict) and ev.get("event") == "run-open":
            opened = ev
    at_open = opened.get("gpt_credits_approved") if isinstance(opened, dict) else None
    if value is True and at_open is True:
        return True, "grants true, run-open true"
    if value is True:
        return False, ("grants true, run-open %s: never raised after run-open (N4)"
                       % ("false" if at_open is False else "absent" if at_open is None
                          else "malformed %r" % (at_open,)))
    if value is False:
        return False, "grants"
    if value is None:
        return False, "default (key absent)"
    return False, "default (malformed value %r)" % (value,)


def gpt_stop_action(verdict, approved, mode):
    """(action, note): the one stop rule for GPT work already running (N19), which each Codex
    lane's own watch (codex-lane.py Runner) and the supervisor's stand-down (handsoff.py
    gpt_stop_decision) both apply, as credits_effective is the one credits rule. `stop` where the
    week reads exhausted (any weekly evidence at 100 % or more) with no approved credits under
    GPT_STOP_MODE "enforce"; `would_stop` for the same in "trial"; else `none` with its note. An
    unreadable verdict, or any other, never stops: the cannot-decide case stops nothing in every
    mode (question R3)."""
    if verdict == "exhausted" and not approved:
        if mode == "enforce":
            return "stop", "stopped: GPT's week at 100 % or more without approved credits (N19)"
        return "would_stop", "would stop (trial state): no stop sent"
    if verdict == "exhausted":
        return "none", "observed continuation on approved credits (no debit claimed)"
    if verdict == "unreadable":
        return "none", "unreadable: nothing stopped"
    if verdict == "below":
        return "none", "below 100 %: nothing stopped"
    return "none", "%s: nothing stopped" % (verdict,)


def _figure(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and 0 <= value <= 100 else None


def _one_line(text, cut=160):
    return " ".join(str(text or "").split())[:cut]


def failed_reading(reason, started, finished):
    """A reading that measured nothing: every window unmeasured with the reason, never zero."""
    return {"schema": SCHEMA, "status": "unmeasured", "reason": reason,
            "started_at": _iso(started), "finished_at": _iso(finished),
            "started_ts": round(started, 6), "finished_ts": round(finished, 6),
            "elapsed_s": round(finished - started, 2), "reader_exit": None,
            "windows": {w: {"used_pct": None, "reset_text": None, "status": "unmeasured",
                            "reason": reason, "source": None} for w in WINDOWS},
            "gpt_week_evidence": []}


def reading_from_object(obj, started, finished, rc=None):
    """The embedded reading from the reader's JSON object: the three windows as the reader gave
    them (a figure outside 0-100 is unmeasured, never clamped), the GPT evidence as read, and
    this side's own start and finish times, which bracket the reader's observation."""
    if not isinstance(obj, dict) or not isinstance(obj.get("windows"), dict):
        return failed_reading("invalid JSON from the reader: no windows object", started, finished)
    windows = {}
    for w in WINDOWS:
        src = obj["windows"].get(w)
        if not isinstance(src, dict):
            windows[w] = {"used_pct": None, "reset_text": None, "status": "unmeasured",
                          "reason": "the reader gave no %s window" % w, "source": None}
            continue
        entry = {"used_pct": src.get("used_pct"), "reset_text": src.get("reset_text"),
                 "status": src.get("status"), "reason": src.get("reason"),
                 "source": src.get("source")}
        if "heading" in src:
            entry["heading"] = src.get("heading")
        if src.get("absent") is True and entry["status"] == "unmeasured":
            entry["absent"] = True   # the account prints no such heading: not a read failure
        if entry["status"] == "measured" and _figure(entry["used_pct"]) is None:
            entry.update(status="unmeasured", used_pct=None,
                         reason="figure %r outside 0-100" % (src.get("used_pct"),))
        elif entry["status"] not in ("measured", "unmeasured", "not_requested"):
            entry.update(status="unmeasured", used_pct=None,
                         reason="status %r is not the reader's" % (src.get("status"),))
        windows[w] = entry
    measured = [w for w in WINDOWS if windows[w]["status"] == "measured"]
    status = "measured" if len(measured) == len(WINDOWS) else "partial" if measured else "unmeasured"
    reasons = ["%s: %s" % (w, windows[w]["reason"]) for w in WINDOWS if w not in measured]
    evidence = obj.get("gpt_week_evidence") if isinstance(obj.get("gpt_week_evidence"), list) else []
    return {"schema": SCHEMA, "status": status, "reason": "; ".join(reasons) or None,
            "started_at": _iso(started), "finished_at": _iso(finished),
            "started_ts": round(started, 6), "finished_ts": round(finished, 6),
            "elapsed_s": round(finished - started, 2), "reader_exit": rc,
            "reader_started_at": obj.get("started_at"), "reader_finished_at": obj.get("finished_at"),
            "windows": windows, "gpt_week_evidence": evidence}


class UsageRead(object):
    """One reading through `read-usage.py --only both --format json --timeout-s 90`, started
    with start() and collected with join(). The reader runs in its own process group on a
    thread, so the caller's dollar work runs meanwhile; the whole call is bounded by one deadline
    of READ_S + REAP_S from its start (plus a poll interval). A failed reading is unmeasured with
    its reason; it never raises and never writes a file."""

    def __init__(self, here, read_s=READ_S, reap_s=REAP_S, env=None):
        self.reader = os.path.join(here, "read-usage.py")
        self.read_s, self.reap_s = read_s, reap_s
        self.env = dict(env if env is not None else os.environ, PYTHONDONTWRITEBYTECODE="1")
        self.cmd = [sys.executable, "-B", self.reader, "--only", "both", "--format", "json",
                    "--timeout-s", str(int(math.ceil(read_s)))]
        self.thread = None
        self.result = None
        self.started = None

    def start(self):
        self.started = time.time()
        self.thread = threading.Thread(target=self._run, name="usage-read")
        self.thread.daemon = True
        self.thread.start()
        return self

    def _run(self):
        self.result = bounded_run(self.cmd, self.read_s, self.reap_s, self.env)

    def join(self):
        if self.thread is None:
            now = time.time()
            return failed_reading("the reading was never started", now, now)
        left = self.started + self.read_s + self.reap_s + 1.0 - time.time()
        self.thread.join(max(0.0, left))
        finished = time.time()
        run = self.result
        if run is None:
            return failed_reading("the reading did not finish inside its %g s deadline"
                                  % (self.read_s + self.reap_s), self.started, finished)
        if run["error"]:
            return failed_reading("the reader could not start: %s" % run["error"],
                                  self.started, finished)
        if run["timed_out"]:
            return failed_reading("timed out after %g s (the reader's process group was ended%s)"
                                  % (self.read_s, "" if run["reaped"] else "; not reaped in time"),
                                  self.started, finished)
        if run["rc"] not in (0, 1):
            return failed_reading("reader exit %s: %s" % (run["rc"], _one_line(
                run["stderr"] or run["stdout"]) or "no output"), self.started, finished)
        try:
            obj = json.loads(run["stdout"])
        except ValueError:
            return failed_reading("invalid JSON from the reader: %s"
                                  % (_one_line(run["stdout"], 120) or "empty"), self.started, finished)
        return reading_from_object(obj, self.started, finished, run["rc"])


def dry_run_reading():
    """What a dry run embeds: no reader is started."""
    return {"usage_reading": None, "usage_reading_reason": "dry-run"}


# ------------------------------------------------------------------ the delta ---------------

def readings_of(events):
    """[(index, event)] for every open, boundary or close carrying a reading, failed ones
    included: a dry run is never recorded, and an event from before the meter has no key."""
    return [(i, e) for i, e in enumerate(events)
            if e.get("event") in READING_EVENTS and "usage_reading" in e]


def previous_reading(events):
    """The immediately preceding reading on the record (a failed one included, never skipped),
    or None where the record holds none."""
    found = readings_of(events)
    return found[-1][1].get("usage_reading") if found else None


def _window_delta(prev, cur, w):
    out = {"delta_pp": None, "reason": None}
    if cur is None:
        out["reason"] = "no reading (dry-run)"
        return out
    c = cur["windows"][w]
    out["to"] = c.get("used_pct") if c.get("status") == "measured" else None
    if prev is None:
        out["reason"] = "first reading"
        return out
    p = (prev.get("windows") or {}).get(w) or {}
    out["from"] = p.get("used_pct") if p.get("status") == "measured" else None
    if p.get("status") != "measured" or _figure(p.get("used_pct")) is None:
        out["reason"] = "unmeasured predecessor"
    elif c.get("status") != "measured" or _figure(c.get("used_pct")) is None:
        out["reason"] = "unmeasured reading"
    elif not p.get("reset_text") or not c.get("reset_text"):
        out["reason"] = "reset unstated"
    elif p.get("reset_text") != c.get("reset_text"):
        out["reason"] = "reset changed"
    elif p.get("source") != c.get("source"):
        out["reason"] = "scope changed"
    elif not (isinstance(prev.get("finished_ts"), (int, float))
              and isinstance(cur.get("started_ts"), (int, float))
              and prev["finished_ts"] <= cur["started_ts"]):
        out["reason"] = "overlapping observations"
    elif cur["finished_ts"] - prev["started_ts"] >= WINDOW_MINUTES[w] * 60:
        out["reason"] = "span at least one window"
    elif c["used_pct"] < p["used_pct"]:
        out["reason"] = "counter decreased"
    else:
        out["delta_pp"] = round(c["used_pct"] - p["used_pct"], 6)
    return out


def sample_delta(prev, cur):
    """Each window's change in pp, current minus previous, only where both are measured, the
    reset texts are identical and stated, the sources agree, the observations are ordered, the
    span is shorter than the window and the counter has not fallen; else null with the reason."""
    return {w: _window_delta(prev, cur, w) for w in WINDOWS}


def coverage(events, w):
    """(subtotal pp, valid segments, gaps) over the record's readings for window w: the sum of
    adjacent valid segments, a subtotal carrying its gap count. A gap or a reset is never bridged
    with zero; the first reading is no gap."""
    total, segments, gaps = 0.0, 0, 0
    for _, e in readings_of(events):
        d = ((e.get("usage_delta") or {}).get(w) or {})
        if d.get("reason") == "first reading":
            continue
        if isinstance(d.get("delta_pp"), (int, float)):
            total += d["delta_pp"]
            segments += 1
        else:
            gaps += 1
    return round(total, 6), segments, gaps


# ------------------------------------------------------------------ the pre-flight ---------

class PreflightError(ValueError):
    pass


def _bounds(value, where):
    if not isinstance(value, dict) or set(value) != {"low", "high"}:
        raise PreflightError("%s must be {low, high}" % where)
    low, high = value["low"], value["high"]
    for name, v in (("low", low), ("high", high)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise PreflightError("%s.%s must be a finite non-negative number" % (where, name))
    if low > high:
        raise PreflightError("%s: low %r above high %r" % (where, low, high))
    return {"low": low, "high": high}


def _text(value, where, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise PreflightError("%s must be a non-empty string" % where)
    return value


def load_preflight_data(path):
    """(normalised plan, sha256 of the file's bytes) from the pre-flight's usage attachment,
    read once; PreflightError names the first fault. Schema 1: {schema: 1, usage: {rates,
    helpers, account_expectations?, explain_gap_pp?}}. No `limits` object: package B's settings
    come from run-open flags."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise PreflightError("cannot read %s: %s" % (path, exc))
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PreflightError("not JSON: %s" % exc)
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise PreflightError("schema must be 1")
    extra = set(data) - {"schema", "usage"}
    if extra:
        raise PreflightError("unknown top-level key(s) %s" % ", ".join(sorted(extra)))
    usage = data.get("usage")
    if not isinstance(usage, dict):
        raise PreflightError("usage must be an object")
    extra = set(usage) - {"rates", "helpers", "account_expectations", "explain_gap_pp"}
    if extra:
        raise PreflightError("unknown usage key(s) %s" % ", ".join(sorted(extra)))
    rates, ids = [], set()
    if not isinstance(usage.get("rates"), list):
        raise PreflightError("usage.rates must be a list")
    for n, r in enumerate(usage["rates"]):
        where = "usage.rates[%d]" % n
        if not isinstance(r, dict):
            raise PreflightError("%s must be an object" % where)
        rid = _text(r.get("id"), where + ".id")
        if rid in ids:
            raise PreflightError("%s: rate id %r declared twice" % (where, rid))
        ids.add(rid)
        family = r.get("family")
        if family not in UNITS:
            raise PreflightError("%s.family must be claude or gpt" % where)
        row = {"id": rid, "family": family}
        for key in ("model", "effort", "class", "workload"):
            row[key] = _text(r.get(key), "%s.%s" % (where, key))
        basis = _text(r.get("basis"), where + ".basis")
        row["basis"] = basis
        per = r.get("pp_per_unit")
        if not isinstance(per, dict) or not per:
            raise PreflightError("%s.pp_per_unit must be a non-empty object" % where)
        row["pp_per_unit"] = {}
        for w, units in per.items():
            if w not in WINDOWS:
                raise PreflightError("%s.pp_per_unit: unknown window %r" % (where, w))
            if not isinstance(units, dict) or not units:
                raise PreflightError("%s.pp_per_unit.%s must be a non-empty object" % (where, w))
            row["pp_per_unit"][w] = {}
            for unit, b in units.items():
                if unit not in UNITS[family]:
                    raise PreflightError("%s.pp_per_unit.%s: unit %r is not a %s unit"
                                         % (where, w, unit, family))
                row["pp_per_unit"][w][unit] = _bounds(b, "%s.pp_per_unit.%s.%s" % (where, w, unit))
        rates.append(row)
    helpers, keys = [], set()
    if not isinstance(usage.get("helpers"), list):
        raise PreflightError("usage.helpers must be a list")
    for n, h in enumerate(usage["helpers"]):
        where = "usage.helpers[%d]" % n
        if not isinstance(h, dict):
            raise PreflightError("%s must be an object" % where)
        row = {"lane": _text(h.get("lane"), where + ".lane")}
        if row["lane"] in keys:
            raise PreflightError("%s: lane %r planned twice" % (where, row["lane"]))
        keys.add(row["lane"])
        row["item"] = _text(h.get("item"), where + ".item")
        if h.get("family") not in UNITS:
            raise PreflightError("%s.family must be claude or gpt" % where)
        row["family"] = h["family"]
        for key in ("model", "effort", "class", "rate_id"):
            row[key] = _text(h.get(key), "%s.%s" % (where, key))
        units = h.get("expected_units")
        if not isinstance(units, dict) or not units:
            raise PreflightError("%s.expected_units must be a non-empty object" % where)
        row["expected_units"] = {}
        for unit, b in units.items():
            if unit not in UNITS[row["family"]]:
                raise PreflightError("%s.expected_units: unit %r is not a %s unit"
                                     % (where, unit, row["family"]))
            row["expected_units"][unit] = _bounds(b, "%s.expected_units.%s" % (where, unit))
        helpers.append(row)
    plan = {"schema": 1, "rates": rates, "helpers": helpers}
    acc = usage.get("account_expectations")
    if acc is not None:
        if not isinstance(acc, dict):
            raise PreflightError("usage.account_expectations must be an object")
        plan["account_expectations"] = {}
        for w, b in acc.items():
            if w not in WINDOWS:
                raise PreflightError("usage.account_expectations: unknown window %r" % w)
            plan["account_expectations"][w] = _bounds(b, "usage.account_expectations.%s" % w)
    gap = usage.get("explain_gap_pp")
    if gap is not None:
        if not isinstance(gap, dict) or set(gap) != {"pp", "provenance"}:
            raise PreflightError("usage.explain_gap_pp must be {pp, provenance}")
        pp = gap["pp"]
        if isinstance(pp, bool) or not isinstance(pp, (int, float)) or not math.isfinite(pp) or pp < 0:
            raise PreflightError("usage.explain_gap_pp.pp must be a finite non-negative number")
        plan["explain_gap_pp"] = {"pp": pp, "provenance": _text(gap["provenance"],
                                                                "usage.explain_gap_pp.provenance")}
    return plan, hashlib.sha256(raw).hexdigest()


# ------------------------------------------------------------------ items -------------------

def record_events(path):
    """The record's JSON objects in order; a missing file is no events and a torn line is
    skipped (the lane-open rule needs only the boundaries). Reads, never writes."""
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except (OSError, IOError):
        return []
    return out


def item_at_open(events, explicit=None, legacy=False, source_pass=None):
    """The lane's item at lane-open: an explicit value; else the latest preceding phase-boundary's
    `to`, inferred, with that event's locator; else unassigned. At close a legacy open (one from
    before the meter) is inferred from the record before it and labelled inferred-legacy. An A3
    successor (a spawn naming its source pass) gets its item at its own open: forwarding the
    source's item stays deferred, and the open says so. The keys are `usage_item`,
    `usage_item_source`, `usage_item_locator` and `usage_item_note`: the lane-open's own `item` is
    the launchers' explicit `--item`, which the console reads as a named item, and stays theirs."""
    out = None
    if explicit not in (None, ""):
        out = {"usage_item": explicit, "usage_item_source": "explicit"}
    else:
        for i in range(len(events) - 1, -1, -1):
            e = events[i]
            if e.get("event") == "phase-boundary":
                out = {"usage_item": e.get("to"),
                       "usage_item_source": "inferred-legacy" if legacy else "inferred",
                       "usage_item_locator": {"event": "phase-boundary", "index": i,
                                              "ts": e.get("ts"), "from": e.get("from"),
                                              "to": e.get("to")}}
                break
    out = out or {"usage_item": None, "usage_item_source": "unassigned"}
    if source_pass:
        out["usage_item_note"] = ("an A3 successor of pass %s: its item is set at its own open, "
                                  "never forwarded from the source pass (forwarding deferred)"
                                  % source_pass)
    return out


# ------------------------------------------------------------------ close accounting ---------

def _family(e):
    return "gpt" if e.get("harness") == "codex" else "claude"


def _pass_key(e):
    for key in ("close_id", "pass_id", "invocation_id"):
        if e.get(key):
            return (e.get("event"), key, e[key])
    return (e.get("event"), "line", json.dumps(e, sort_keys=True))


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def codex_split(usage, state):
    """(fresh, cached, output in million tokens, complete, reason) for one Codex close or beat:
    fresh = input - cached, cached, output; incomplete unless 0 <= cached <= input and every
    count is a number, and a subtotal unless the close's accounting is complete."""
    if not isinstance(usage, dict):
        return None, False, "no usage object (missing)"
    inp, cached, out = (_num(usage.get(k)) for k in ("input_tokens", "cached_input_tokens",
                                                       "output_tokens"))
    if inp is None or cached is None or out is None:
        return None, False, "a count is missing or not a number"
    if not 0 <= cached <= inp or out < 0:
        return None, False, "cached %s outside 0..input %s" % (cached, inp)
    q = {"fresh_input_mtokens": (inp - cached) / MTOKENS, "cached_input_mtokens": cached / MTOKENS,
         "output_mtokens": out / MTOKENS}
    if state not in (None, "complete"):
        return q, False, "usage_state %s: a subtotal" % state
    return q, True, None


def _helpers_from(events):
    """{lane: row} from the record prefix: the lane's first lane-open (resumes and beats keep its
    item), its passes' quantities, deduplicated by close_id / pass_id / invocation_id."""
    rows, seen = {}, set()
    for i, e in enumerate(events):
        kind, lane = e.get("event"), e.get("lane")
        if lane is None:
            continue
        if kind == "lane-open" and lane not in rows:
            item = {k: e.get(k) for k in ("usage_item", "usage_item_source", "usage_item_locator")
                    if k in e}
            if "usage_item_source" not in item:
                item = item_at_open(events[:i], explicit=e.get("item"), legacy=True)
            fam = _family(e)
            rows[lane] = {"lane": lane, "family": fam, "model": e.get("model"),
                          "effort": e.get("effort"), "class": e.get("class"),
                          "item": item.get("usage_item"),
                          "item_source": item.get("usage_item_source"),
                          "quantities": {u: 0.0 for u in UNITS[fam]}, "passes": 0, "open": 0,
                          "incomplete": []}
            if fam == "gpt":
                rows[lane]["split_complete"] = "unverified"
        row = rows.get(lane)
        if row is None:
            continue
        if kind in ("lane-open", "lane-resumed"):
            row["open"] += 1
        if kind not in ("lane-closed", "hold-beat"):
            continue
        if kind == "hold-beat" and e.get("observation_only"):
            continue      # the supervisor's stand-in for a beat: an observation, never a pass
        key = (lane,) + _pass_key(e)
        if key in seen:
            continue
        seen.add(key)
        if kind == "lane-closed":
            row["open"] = max(0, row["open"] - 1)
        row["passes"] += 1
        if row["family"] == "claude":
            cost = _num(e.get("total_cost_usd"))
            if cost is None:
                row["incomplete"].append("%s at %s: cost unknown" % (kind, e.get("ts")))
            else:
                row["quantities"]["usd_list"] += cost
        else:
            q, complete, reason = codex_split(e.get("usage"), e.get("usage_state"))
            if q is None:
                row["incomplete"].append("%s at %s: %s" % (kind, e.get("ts"), reason))
                continue
            for u, v in q.items():
                row["quantities"][u] += v
            if not complete:
                row["incomplete"].append("%s at %s: %s" % (kind, e.get("ts"), reason))
    for row in rows.values():
        if row["open"]:
            row["incomplete"].append("%d pass(es) open at the cutoff (pending)" % row["open"])
        if row["passes"] == 0 and not row["open"]:
            row["incomplete"].append("no close before the cutoff")
        row["complete"] = not row["incomplete"]
        row["quantities"] = {u: round(v, 9) for u, v in row["quantities"].items()}
        del row["open"]
    return rows


def _interval(pairs):
    lows = [a for a, _ in pairs]
    highs = [b for _, b in pairs]
    return {"low": round(sum(lows), 9), "high": round(sum(highs), 9)}


def _shares(plan_row, rate, actual, complete):
    """Per window w over the components j whose rate names w: expected E_w, estimated actual A_w
    and difference D_w, each a {low, high} pp interval; never summed across windows. A_w counts
    every component the rate names, whether or not the plan states its expected quantity, so the
    actual never depends on the expectation (CR-MET-BA2 F3); E_w and D_w count the components that
    have one. A component without an expectation, or an actual unknown because the helper's passes
    are incomplete, is named under `partial`, which the item and run totals carry (_add)."""
    out = {}
    for w in WINDOWS:
        per = rate["pp_per_unit"].get(w)
        if not per:
            continue
        e_pairs, a_pairs, d_pairs, missing = [], [], [], []
        for unit, r in per.items():
            qa = actual.get(unit) if complete else None
            if qa is not None:
                a_pairs.append((qa * r["low"], qa * r["high"]))
            q = plan_row["expected_units"].get(unit)
            if q is None:
                missing.append("no expected %s" % unit)
                continue
            e_pairs.append((q["low"] * r["low"], q["high"] * r["high"]))
            if qa is not None:
                d = qa - q["high"]
                d_pairs.append((min(d * r["low"], d * r["high"]), max(d * r["low"], d * r["high"])))
        if not complete:
            missing.append("actual unknown (the helper's passes are incomplete)")
        out[w] = {"expected": _interval(e_pairs) if e_pairs else None,
                  "actual": _interval(a_pairs) if complete and a_pairs else None,
                  "difference": _interval(d_pairs) if complete and d_pairs else None}
        if missing:
            out[w]["partial"] = missing
    return out


def _add(into, shares, lane):
    """One helper's per-window shares added into an item or run total. A component the share
    lacks is carried under the window's `partial`, naming the helper, never dropped (CR-MET-BA2 F3)."""
    for w, s in shares.items():
        slot = into.setdefault(w, {"expected": None, "actual": None, "difference": None})
        for k in ("expected", "actual", "difference"):
            v = s.get(k)
            if v is None:
                continue
            cur = slot[k] or {"low": 0.0, "high": 0.0}
            slot[k] = {"low": round(cur["low"] + v["low"], 9), "high": round(cur["high"] + v["high"], 9)}
        for gap in s.get("partial") or []:
            slot.setdefault("partial", []).append("%s: %s" % (lane, gap))


def account_comparison(events, close_reading, close_delta, plan):
    """Close-only: each window's final figure against the pre-flight's expected final figure,
    made only where the opening and final resets agree and are stated, every reading between
    supports an unbroken span, and the scope agrees; else unknown with the gap. Account
    movement is never allocated to helpers."""
    chain = [e for _, e in readings_of(events)]
    out = {}
    expectations = (plan or {}).get("account_expectations") or {}
    gap = (plan or {}).get("explain_gap_pp")
    for w in WINDOWS:
        if not chain or chain[0].get("event") != "run-open" or not chain[0].get("usage_reading"):
            out[w] = {"status": "unknown", "reason": "no opening reading"}
            continue
        first = chain[0]["usage_reading"]["windows"][w]
        last = (close_reading or {}).get("windows", {}).get(w) or {}
        deltas = [(e.get("usage_delta") or {}).get(w) or {} for e in chain[1:]] + [close_delta.get(w) or {}]
        broken = [d.get("reason") for d in deltas if not isinstance(d.get("delta_pp"), (int, float))]
        if first.get("status") != "measured" or last.get("status") != "measured":
            out[w] = {"status": "unknown", "reason": "opening or final reading unmeasured"}
        elif not first.get("reset_text") or first.get("reset_text") != last.get("reset_text"):
            out[w] = {"status": "unknown", "reason": "opening and final resets differ or are unstated"}
        elif first.get("source") != last.get("source"):
            out[w] = {"status": "unknown", "reason": "scope changed"}
        elif broken:
            out[w] = {"status": "unknown", "reason": "%d gap(s) in the span: %s"
                      % (len(broken), "; ".join(sorted(set(str(b) for b in broken))))}
        else:
            row = {"status": "compared", "opening_pct": first["used_pct"], "final_pct": last["used_pct"],
                   "change_pp": round(last["used_pct"] - first["used_pct"], 6)}
            exp = expectations.get(w)
            if exp is None:
                row.update(expected_final_pct=None, above_expected=None,
                           reason="the pre-flight states no expected final figure")
            else:
                row.update(expected_final_pct=exp, above_expected=last["used_pct"] > exp["high"],
                           difference_pp=round(last["used_pct"] - exp["high"], 6))
                if gap is not None:
                    row["explain_gap_pp"] = dict(gap)
                    row["explanation_marked"] = row["difference_pp"] > gap["pp"]
            out[w] = row
    return out


def close_accounting(events, plan, close_reading=None, close_delta=None):
    """The run-close rows from the record prefix up to the cutoff: usage_helpers, usage_items,
    usage_totals and usage_comparisons. A helper matches a planned row exactly on the lane and on
    item, family, model, effort and class, never by guessing; an unplanned helper or a missing
    rate makes the estimate partial, never an expected zero. Head use and unrelated account use
    are outside helper coverage, so the run total is a helper subtotal."""
    found = _helpers_from(events)
    rates = {r["id"]: r for r in (plan or {}).get("rates", [])}
    planned = {h["lane"]: h for h in (plan or {}).get("helpers", [])}
    helpers, items, partial = [], {}, []
    totals = {}
    lanes = list(found) + [l for l in planned if l not in found]
    for lane in lanes:
        row = found.get(lane)
        p = planned.get(lane)
        if row is None:
            row = {"lane": lane, "family": p["family"], "model": p["model"], "effort": p["effort"],
                   "class": p["class"], "item": p["item"], "item_source": "planned, never opened",
                   "quantities": {u: None for u in UNITS[p["family"]]}, "passes": 0,
                   "incomplete": ["no lane-open before the cutoff"], "complete": False}
            if p["family"] == "gpt":
                row["split_complete"] = "unverified"   # every Codex row (design line 507; CR-MET-BA2 F4)
        if plan is None:
            row["plan"] = "unestimated"
        elif p is None:
            row["plan"] = "unplanned"
            partial.append("%s unplanned" % lane)
        elif any(row[k] != p[k] for k in ("item", "family", "model", "effort", "class")):
            row["plan"] = "mismatch"
            row["mismatch"] = [k for k in ("item", "family", "model", "effort", "class")
                               if row[k] != p[k]]
            partial.append("%s does not match its planned row (%s)" % (lane, ", ".join(row["mismatch"])))
        elif p["rate_id"] not in rates:
            row["plan"] = "no rate"
            row["rate_id"] = p["rate_id"]
            partial.append("%s: rate %s missing" % (lane, p["rate_id"]))
        else:
            rate = rates[p["rate_id"]]
            if any(rate[k] != p[k] for k in ("family", "model", "effort", "class")):
                row["plan"] = "no rate"
                row["rate_id"] = p["rate_id"]
                partial.append("%s: rate %s names another family, model, effort or class"
                               % (lane, p["rate_id"]))
            else:
                row["plan"], row["rate_id"] = "matched", p["rate_id"]
                units = {}
                for unit, q in p["expected_units"].items():
                    qa = row["quantities"].get(unit)
                    if row["complete"] and qa is not None:
                        units[unit] = {"expected": q, "actual": qa, "overrun": qa > q["high"],
                                       "d": round(qa - q["high"], 9)}
                    else:
                        units[unit] = {"expected": q, "actual": None, "overrun": None, "d": None,
                                       "reason": "; ".join(row["incomplete"]) or "incomplete"}
                row["units"] = units
                row["shares"] = _shares(p, rate, row["quantities"], row["complete"])
                if not row["complete"]:
                    partial.append("%s incomplete" % lane)
                for w, sh in sorted(row["shares"].items()):
                    expectless = [g for g in sh.get("partial") or [] if g.startswith("no expected ")]
                    if expectless:
                        partial.append("%s: %s in %s" % (lane, ", ".join(expectless), w))
                key = row["item"] if row["item"] is not None else "unassigned"
                _add(items.setdefault(key, {"helpers": [], "shares": {}})["shares"], row["shares"], lane)
                _add(totals, row["shares"], lane)
        key = row["item"] if row["item"] is not None else "unassigned"
        items.setdefault(key, {"helpers": [], "shares": {}})["helpers"].append(lane)
        if plan is not None and row["plan"] != "matched":
            # A helper outside the estimate adds no share: its item names it, never silently short.
            items[key].setdefault("partial", []).append("%s: %s" % (lane, row["plan"]))
        helpers.append(row)
    status = "unestimated" if plan is None else ("partial" if partial else "complete")
    rates_row = measured_rates(events, plan, close_reading, helpers)
    comparisons = {
        "units": [{"lane": h["lane"], "unit": u, "overrun": v["overrun"], "d": v["d"]}
                  for h in helpers for u, v in sorted((h.get("units") or {}).items())],
        "account": account_comparison(events, close_reading, close_delta or {}, plan),
        "credits_consumed": "unknown"}
    return {"usage_helpers": helpers, "usage_items": items,
            "usage_totals": {"label": "helper subtotal", "estimate": status, "partial": partial,
                             "shares": totals},
            "usage_comparisons": comparisons, "usage_rates": rates_row}


WINDOW_FAMILY = {"claude_5h": "claude", "claude_week": "claude", "gpt_week": "gpt"}


def measured_rates(events, plan, close_reading, helpers):
    """Close-only (critic CR-T2b finding 11): each window's measured UPPER-BOUND rate beside the
    pre-flight's assumed one. The window's change over the run (run-open's own reading to the
    close's, both measured and naming the same reset) divided by the run's units in that window:
    per helper of the window's family, and per unit of that family's quantities. An upper bound,
    because the change includes every other use of the account in the run's time, and the units
    count only what the record shows. The hand derivation on the register's 2026-10-21 23:35 i
    entry is this figure: 31 points over 42 helpers is 0.738 points each."""
    ro = next((e for e in events if e.get("event") == "run-open"), None)
    first_all = ((ro or {}).get("usage_reading") or {}).get("windows") or {}
    last_all = (close_reading or {}).get("windows") or {}
    out = {}
    for w in WINDOWS:
        fam = WINDOW_FAMILY[w]
        mine = [h for h in helpers if h.get("family") == fam and h.get("passes")]
        assumed = {}
        for r in (plan or {}).get("rates") or []:
            if r.get("family") != fam:
                continue
            for unit, b in (((r.get("pp_per_unit") or {}).get(w)) or {}).items():
                if isinstance(b, dict) and _num(b.get("low")) is not None and _num(b.get("high")) is not None:
                    cur = assumed.get(unit)
                    assumed[unit] = ({"low": b["low"], "high": b["high"]} if cur is None else
                                     {"low": min(cur["low"], b["low"]), "high": max(cur["high"], b["high"])})
        row = {"label": "measured upper bound (the change includes all other account use)",
               "assumed_pp_per_unit": assumed or None, "helpers": len(mine)}
        first, last = first_all.get(w) or {}, last_all.get(w) or {}
        if ro is None or "usage_reading" not in ro:
            row.update(status="unknown", reason="no opening reading")
        elif first.get("status") != "measured" or last.get("status") != "measured":
            row.update(status="unknown", reason="opening or final reading unmeasured")
        elif first.get("reset_text") != last.get("reset_text"):
            row.update(status="unknown", reason="the window's reset moved during the run, so its "
                                                "change does not span the run")
        else:
            change = round(last["used_pct"] - first["used_pct"], 6)
            row.update(status="measured", change_pp=change)
            row["pp_per_helper"] = round(change / len(mine), 6) if mine else None
            per_unit = {}
            for unit in UNITS[fam]:
                q = sum((h.get("quantities") or {}).get(unit) or 0.0 for h in mine
                        if h.get("complete"))
                per_unit[unit] = round(change / q, 6) if q > 0 else None
            row["pp_per_unit"] = per_unit
            incomplete = [h["lane"] for h in mine if not h.get("complete")]
            if incomplete:
                row["units_partial"] = incomplete
        out[w] = row
    return out


def coverage_only(accounting):
    """What a close dry run may show: coverage, never a comparison or an estimate."""
    return {"helpers": len(accounting["usage_helpers"]),
            "complete": sum(1 for h in accounting["usage_helpers"] if h.get("complete")),
            "incomplete": [h["lane"] for h in accounting["usage_helpers"] if not h.get("complete")],
            "unassigned": [h["lane"] for h in accounting["usage_helpers"] if h.get("item") is None]}


# ------------------------------------------------------------------ presentation ------------

NOT_SHOWN = "not shown by the account"   # a window whose heading the account does not print


def _pct(v):
    return ("%g %%" % v) if isinstance(v, (int, float)) and not isinstance(v, bool) else "unmeasured"


def render_windows(events):
    """[(label, text)] for the three owned Spend bullets: the opening figure (run-open's own
    reading) and the latest, the reset text, the latest delta or its reason, and the covered
    subtotal with its gap count. An unknown reads `unmeasured`, never zero. Readings and deltas
    only: no comparison or estimate."""
    chain = [e for _, e in readings_of(events)]
    opening_ev = next((e for e in events if e.get("event") == "run-open"), None)
    out = []
    for w in WINDOWS:
        measured = [e for e in chain if (((e.get("usage_reading") or {}).get("windows") or {})
                                         .get(w) or {}).get("status") == "measured"]
        if not measured:
            # One text while nothing of this window was ever measured, so a later failed reading
            # changes no bullet and an already-current page stays as it is. An account that prints
            # no such window (tonight's prints no "Current session") says so, never a fault.
            latest_w = ((((chain[-1].get("usage_reading") or {}).get("windows") or {}).get(w)
                         or {}) if chain else {})
            out.append((LABELS[w], NOT_SHOWN if latest_w.get("absent") else
                        "unmeasured (no reading of this window measured on the record)"))
            continue
        # The opening figure is run-open's own reading, never a later one (CR-MET-BA2 F2): a run
        # opened before the meter, or whose opening reading failed, shows its opening unmeasured.
        first = (((opening_ev or {}).get("usage_reading") or {}).get("windows") or {}).get(w) or {}
        last_ev = chain[-1]
        last = (last_ev.get("usage_reading") or {}).get("windows", {}).get(w) or {}
        d = (last_ev.get("usage_delta") or {}).get(w) or {}
        total, segments, gaps = coverage(events, w)
        if first.get("status") == "measured":
            opening = _pct(first.get("used_pct"))
        elif opening_ev is None or "usage_reading" not in opening_ev:
            opening = "unmeasured (no opening reading)"
        else:
            opening = "unmeasured"
        latest = _pct(last.get("used_pct")) if last.get("status") == "measured" else "unmeasured"
        change = ("%+g pp" % d["delta_pp"]) if isinstance(d.get("delta_pp"), (int, float)) \
            else "change unknown (%s)" % (d.get("reason") or "no delta")
        out.append((LABELS[w], "opening %s · latest %s (%s) · latest change %s · covered subtotal "
                    "%s over %d segment(s), %d gap(s)"
                    % (opening, latest, "resets %s" % last["reset_text"] if last.get("reset_text")
                       else "reset unstated", change,
                       ("%+g pp" % total) if segments else "none", segments, gaps)))
    return out


UNGUARDED_SENTENCE = ("After a Claude weekly stand-down nothing stops GPT work that crosses the "
                      "line later, so the run's report names that gap and leaves any credit debit "
                      "unknown")   # package B's guidance sentence (SKILL.md.guidance-B.diff, line 8)


def _interval_text(seconds):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0:
        return "an unrecorded interval"
    if seconds % 60 == 0:
        return "%d minute%s" % (seconds // 60, "" if seconds == 60 else "s")
    return "%g s" % seconds


def _seconds(value):
    """A positive number of seconds, or None (a bool, a string or a missing value is no figure)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
        return None
    return value


def watch_stop_bound_s(every_s, read_bound_s):
    """The most a lane armed with this interval and reading bound runs past 100 % before its stop
    completes (review V-T2b2, R2): the reading in flight when the line is crossed, which can read
    below and still take its whole bound, then one interval (the watch waits a full interval after
    each reading returns), the next reading's bound, the runner's tick and the stop's grace. None
    where either figure is not a positive number of seconds."""
    every, bound = _seconds(every_s), _seconds(read_bound_s)
    if every is None or bound is None:
        return None
    return bound + every + bound + WATCH_TICK_S + WATCH_GRACE_S


# A close's watch record shows the time past the line bounded only where it carries every one of
# these with a value of its kind (review V-T2b2, Claim 12 and R7): a missing counter is no evidence
# of zero faults, so an empty or partial record never reads as bounded.
WATCH_COUNTS = ("readings", "unreadable", "errors")
WATCH_FIGURES = ("every_s", "read_bound_s")


def _watch_gaps(summary):
    """The names a close's gpt_watch lacks for the bounded reading, each with why; [] when whole."""
    gaps = []
    if summary.get("armed") is not True:
        gaps.append("armed %s" % ("absent" if "armed" not in summary else json.dumps(summary["armed"])))
    if summary.get("mode") != "enforce":
        gaps.append("mode %s" % ("absent" if "mode" not in summary else json.dumps(summary["mode"])))
    for name in WATCH_COUNTS:
        value = summary.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            gaps.append("%s %s" % (name, "absent" if name not in summary else "not a count"))
    if not isinstance(summary.get("ended_early"), bool):
        gaps.append("ended_early %s" % ("absent" if "ended_early" not in summary else "not true or false"))
    for name in WATCH_FIGURES:
        if _seconds(summary.get(name)) is None:
            gaps.append("%s %s" % (name, "absent" if name not in summary else "not a positive figure"))
    return gaps


def watched_sentence(watch, close):
    """The run report's sentence for one listed lane whose spawn line armed a GPT watch, built
    from that lane's own record (critic CR-T2b2 finding 4): the mode and interval its spawn line
    carries, and its close's watch record. It says the watch stops the lane only where the mode is
    enforce. It says the time past the line is bounded only where the close's record is whole
    (every count and figure of WATCH_COUNTS and WATCH_FIGURES present with a value of its kind,
    armed, mode enforce; review V-T2b2, Claim 12 and R7) and shows no unreadable reading, no error
    and no early end; the bound it states includes the reading time (watch_stop_bound_s; R2).
    Otherwise it names what the close shows or lacks."""
    mode = watch.get("mode")
    if mode == "enforce":
        acts = "to stop it at 100 % without approved credits"
    else:
        # The trial wording claims no would-stop: the close does not count them (review V-T2b2,
        # Claim 12: a trial lane with only below-limit readings recorded none).
        acts = ("set only to record a would-stop at 100 %% without approved credits (mode %s), "
                "stopping nothing" % (mode or "unrecorded"))
    text = ("its own GPT watch read GPT's week every %s while it ran, %s; the spend between two "
            "readings is unknown" % (_interval_text(watch.get("every_s")), acts))
    if mode != "enforce":
        return text + ", and nothing bounds the time it ran past the line"
    summary = (close or {}).get("gpt_watch")
    if close is None or not isinstance(summary, dict):
        return text + ("; %s, so the time it ran past the line is not shown bounded"
                       % ("no close by the run's close" if close is None
                          else "its close carries no watch record"))
    gaps = _watch_gaps(summary)
    if gaps:
        return text + ("; its close's watch record is incomplete (%s), so the time it ran past the "
                       "line is not shown bounded" % ", ".join(gaps))
    faults = []
    if summary["unreadable"]:
        faults.append("%s unreadable reading(s)" % summary["unreadable"])
    if summary["errors"]:
        faults.append("%s reading error(s)" % summary["errors"])
    if summary["ended_early"]:
        faults.append("its watch ended early")
    if faults:
        return text + ("; its close records %s, so the time it ran past the line is not bounded"
                       % ", ".join(faults))
    bound = watch_stop_bound_s(summary["every_s"], summary["read_bound_s"])
    return text + (", so the time it ran past the line is bounded by %g s: the reading in flight "
                   "when it crossed and the next one (%g s each at most), one interval between "
                   "them, the runner's %d s tick and the stop's %d s grace"
                   % (bound, summary["read_bound_s"], WATCH_TICK_S, WATCH_GRACE_S))


def stand_down_bullets(events):
    """[(label, text)]: one run-report Spend bullet for each supervisor-stood-down whose event
    lists Codex lanes still open after its GPT reading and any stop (critic CR-T2b finding 1),
    built at the close from the record (review V-T2b, Claim 13): for each listed lane, the first
    lane-closed after the stand-down names its later fate ("closed later at <ts>, <exit class>",
    with its watch's stop where its close carries one), else "no close by the run's close"; the
    lane's own spawn line decides its sentence (watched_sentence where it armed a GPT watch,
    package B's UNGUARDED_SENTENCE for a lane with no watch). A stand-down whose list is empty
    adds none."""
    out = []
    for i, e in enumerate(events):
        if e.get("event") != "supervisor-stood-down" or not e.get("codex_lanes_open"):
            continue
        g = e.get("gpt_at_stand_down") or {}
        verdict = g.get("verdict") or "not read"
        fig = g.get("figure")
        parts, unguarded = [], False
        for name in [str(x) for x in e["codex_lanes_open"]]:
            spawn = None
            for x in events[:i]:
                if x.get("lane") == name and x.get("event") in ("lane-spawned", "lane-respawned"):
                    spawn = x
            close = next((x for x in events[i + 1:] if x.get("event") == "lane-closed"
                          and x.get("lane") == name), None)
            if close is None:
                fate = "no close by the run's close"
            else:
                fate = "closed later at %s, %s" % (close.get("ts") or "time unrecorded",
                                                   close.get("exit_class") or "class unrecorded")
                stopped = (close.get("gpt_watch") or {}).get("stopped") \
                    if isinstance(close.get("gpt_watch"), dict) else None
                if isinstance(stopped, dict):
                    fate += "; stopped by its GPT watch at %s %%" % stopped.get("figure")
            watch = (spawn or {}).get("gpt_watch")
            if isinstance(watch, dict) and watch.get("armed") is True:
                parts.append("%s: %s; %s" % (name, fate, watched_sentence(watch, close)))
            else:
                unguarded = True
                parts.append("%s: %s; its wrapper ran no GPT watch%s" % (
                    name, fate, " (%s)" % watch.get("reason") if isinstance(watch, dict)
                    and watch.get("reason") else ""))
        out.append(("GPT lanes open at stand-down %d" % (len(out) + 1),
                    "%s (%s) listed %s as open after its GPT reading; GPT week %s%s. %s.%s"
                    % (e.get("reason") or "stand-down", e.get("ts") or "time unrecorded",
                       ", ".join(str(x) for x in e["codex_lanes_open"]), verdict,
                       " at %s %%" % fig if isinstance(fig, (int, float)) else "",
                       ". ".join(parts), " %s." % UNGUARDED_SENTENCE if unguarded else "")))
    return out


def place_bullets(lines, start, end, bullets):
    """Replace or add `- **<label>:** <text>` bullets inside lines[start+1:end] (a section whose
    heading is lines[start]); every other line is kept. Returns the labels changed. In memory only."""
    changed = []
    for label, text in bullets:
        bullet = "- **%s:** %s" % (label, _one_line(text, 2000))
        prefix = "- **%s:**" % label
        found = next((j for j in range(start + 1, end) if lines[j].startswith(prefix)), None)
        if found is not None:
            if lines[found] != bullet:
                lines[found] = bullet
                changed.append(label)
            continue
        j = end
        while j - 1 > start and not lines[j - 1].strip():
            j -= 1
        block = [bullet]
        if not lines[j - 1].lstrip().startswith(("- ", "* ")):
            block = [""] + block
        if j < len(lines) and lines[j].strip():
            block = block + [""]
        lines[j:j] = block
        end += len(block)
        changed.append(label)
    return changed


# ------------------------------------------------------------------ the backstop in points --

def claude_week_rate(events):
    """(rate, source) for showing the run's backstop in points of the Claude week (decision E3):
    the pre-flight's Claude-week rate in points per list-priced dollar, read from run-open's
    usage_plan (the reviewed attachment, pinned by its sha256) as the {low, high} hull over every
    Claude rate row that names claude_week in usd_list. (None, reason) where the record holds no
    such figure: the points then read unmeasured, never a typed constant."""
    ro = next((e for e in events if e.get("event") == "run-open"), None)
    plan = (ro or {}).get("usage_plan")
    if not isinstance(plan, dict):
        return None, "no pre-flight usage attachment on run-open"
    rows = []
    for r in plan.get("rates") or []:
        b = ((r.get("pp_per_unit") or {}).get("claude_week") or {}).get("usd_list")
        if r.get("family") == "claude" and isinstance(b, dict):
            rows.append((r.get("id"), b))
    if not rows:
        return None, "the pre-flight attachment on run-open states no Claude-week rate"
    rate = {"low": min(b["low"] for _, b in rows), "high": max(b["high"] for _, b in rows)}
    # The source names where the rate is read and no unit: the owner's line carries no dollars.
    return rate, ("run-open usage_plan, Claude-week rate%s %s (attachment sha256 %s)"
                  % ("s" if len(rows) > 1 else "", ", ".join(str(i) for i, _ in rows),
                     str(ro.get("usage_plan_sha256") or "unrecorded")[:12]))


def _points_text(iv):
    low, high = ("%.1f" % iv["low"]), ("%.1f" % iv["high"])
    return low if low == high else "%s-%s" % (low, high)


def backstop(events, envelope_usd, spend_usd=None, floor=False):
    """(owner text, machine row) for the run's backstop in points of the Claude week (decision
    E3): the envelope, and the run's spend so far, converted at the rate the record carries
    (claude_week_rate). The text names the rate's source and carries no dollar figure; the dollars
    stay in the machine row. Unmeasured where the rate or the envelope is absent."""
    ok = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    rate, src = claude_week_rate(events)
    row = {"envelope_usd": envelope_usd if ok(envelope_usd) else None,
           "spend_usd": spend_usd if ok(spend_usd) else None, "spend_floor": bool(floor),
           "rate_pp_per_usd": rate, "rate_source": src, "backstop_pp": None, "spend_pp": None}
    if rate is None:
        return "backstop in points of the Claude week: unmeasured (%s)" % src, row
    if not ok(envelope_usd):
        return ("backstop in points of the Claude week: unmeasured (no envelope on the record; "
                "rate: %s)" % src), row
    row["backstop_pp"] = {"low": round(envelope_usd * rate["low"], 6),
                          "high": round(envelope_usd * rate["high"], 6)}
    text = "backstop %s points of the Claude week" % _points_text(row["backstop_pp"])
    if ok(spend_usd):
        row["spend_pp"] = {"low": round(spend_usd * rate["low"], 6), "high": round(spend_usd * rate["high"], 6)}
        text += ", run so far %s%s points" % ("at least " if floor else "", _points_text(row["spend_pp"]))
    else:
        text += ", run so far unmeasured"
    return text + " (rate: %s)" % src, row


def summary_line(reading, delta, backstop_text=None):
    """One line of readings and deltas for a command's stdout, with the run's backstop in points
    where the caller passes it; never a comparison and never a dollar figure."""
    tail = (" · %s" % backstop_text) if backstop_text else ""
    if reading is None:
        return "usage windows: no reading (dry-run)" + tail
    parts = []
    for w in WINDOWS:
        win = reading["windows"][w]
        d = (delta or {}).get(w) or {}
        parts.append("%s %s%s" % (w, _pct(win.get("used_pct")) if win.get("status") == "measured"
                                  else NOT_SHOWN if win.get("absent") else "unmeasured",
                                  " (%+g pp)" % d["delta_pp"] if isinstance(d.get("delta_pp"), (int, float))
                                  else " (%s)" % d.get("reason") if d.get("reason") else ""))
    return "usage windows: %s" % " · ".join(parts) + tail
