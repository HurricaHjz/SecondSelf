#!/usr/bin/env python3
"""handsoff-gate.py — PreToolUse hook: the hands-off hard band, enforced at the tool layer.

Registered for every tool, behind a shell check in .claude/settings.json: with AIMYTH_HANDSOFF not 1,
AIMYTH_STATE_DIR unset and no `armed-*` marker in ~/.aimyth/handoffs, the command exits before Python
starts. Past that check an unarmed session is silent and costs one interpreter start (another
session's marker lets it through); armed it is what stands between a runaway item and the compaction the hands-off design exists to avoid
(hands-off-mode-design.md, D1 and §Context bands).

ARMED when AIMYTH_HANDSOFF=1 is in the environment (the successor starter and the pre-flight start
command set it) OR the state directory holds the marker file `armed-<session_id>`, so a
session already running can be armed, and disarmed, by one file. Unarmed: exit 0, no stdout, no
stderr.

ARMED, the context is measured with context-watermark.py's measure() (imported: one implementation
of the figure) and read against the same bands():
  - at or above the THIRD band (90 % by default, the hard band): every tool call is denied except a
    Bash command whose text contains one of `handsoff.py handoff`, `handsoff.py successor`,
    `handsoff.py boundary`, `handsoff.py ledger` — the four that write the hand-off, hand over to a
    successor, close the boundary and append to the findings ledger. The reason names the figure,
    the band and those four commands. A configuration with only two edges has no hard band: the
    hook says so on stderr and enforces the read bound alone.
  - at the hard band, the run's LAST LEAD may also stop its background tasks (TaskStop) and close
    the run (a Bash command containing `handsoff.py close`): the owner's decision of 30 October
    2026. The last lead is the session handsoff.py's last_lead_state() reads as `last` — no
    successor left on the run's decided cap (the count `gate` prints, successors_left) and the
    calling session the record's current head — so another armed session of the same run is
    denied. Only for such a call, and only at that height, is handsoff.py imported (from the
    delegate skill beside this hooks folder, ../skills/delegate/handsoff.py); every other call
    costs what it did. An allowance is silence, one stderr note and one events.log line.
  - at or above the SECOND band (80 %): a Read with no `limit`, or a limit above READ_CAP, is
    denied — at that height one unbounded read can cross the remaining headroom in a single call
    (C1 F3 on the design page; the 369k single-call jump on record). A bounded Read passes
    untouched, and below the second band a Read is never touched.
  - below both edges: silent.
An allow is SILENCE, never a permissionDecision of "allow": an explicit allow would also skip the
permission prompt the owner still wants for everything this hook has no opinion about.

The deny is advisory in one respect worth stating: it matches the four commands as substrings of
the Bash text, so a command that carries one alongside other work is allowed. The gate is a brake
on a runaway loop, not a sandbox; the head composes the close-out commands itself.

Premise failures — an unreadable payload, no transcript (a fresh session), no usage record, the
watermark module missing, an unusable session id for the marker — ALLOW, with one line on stderr.
Fail-open is the safe direction here: a broken premise must never block an attended session, and
the watermark line, `handsoff.py gate` and the head's own rule each still carry the band.
The last-lead allowance runs the other way: it relaxes the hard band only for a lead SHOWN to have
no successor left, so when that cannot be read — no run, a pointer unreadable, the record missing
or unreadable, a grants file whose cap cannot be read, handsoff.py absent or failing — the deny
stands, its reason naming the premise (an owner's guard stays binding until he retires it).

Every deny appends one tab-separated line — timestamp, session, handsoff-gate, deny, tool, context
— to the state directory's `events.log`, the file and shape precompact-checkpoint.py already
writes, so one series carries compactions, session starts and denials; a last-lead allowance
appends the same line with the action `allow-last-lead`. A failed append is a stderr line, never a
downgraded deny.

Knobs (env):
  AIMYTH_HANDSOFF     "1" arms this session
  AIMYTH_STATE_DIR    marker and events.log root (default ~/.aimyth/handoffs, the hand-off
                      documents' own directory: the real path, of which ~/.llm-wiki is a symlink)
  AIMYTH_READ_CAP     lines a Read may ask for above the second band (default 400)
  (context-watermark.py's own knobs — AIMYTH_CONTEXT_WINDOW, AIMYTH_BANDS, AIMYTH_PROJECTS_DIR —
  decide the figure and the edges.)
  The last-lead allowance reads handsoff.py's knobs: AIMYTH_HANDSOFF_RUN (the run), else the
  pointer file `run-<session_id>` under AIMYTH_STATE_DIR; LLM_WIKI_STORE (the run store holding
  the record and its grants file); AIMYTH_MAX_SUCCESSORS (the cap's fallback when the grants file
  carries none).

Never blocks by exit code: every path exits 0 and the decision travels in the JSON on stdout, which
is what the registration line (`... || true`) preserves.
"""
import sys
sys.dont_write_bytecode = True   # the import below must never leave bytecode beside the hooks
import contextlib
import importlib.util
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_READ_CAP = 400   # lines; set by judgement, unmeasured (critic C1's amendment, 2026-09-05)
HARD_EDGES = 3           # the hard band is the third edge; two edges are the attended shape
ALLOWED = ("handsoff.py handoff", "handsoff.py successor",
           "handsoff.py boundary", "handsoff.py ledger")
# The run's last lead may also run these at the hard band (the owner's decision of 2026-10-30):
# TaskStop, the delegate skill's name for the tool that stops a background task, and the run's
# close, which no other subcommand's name starts with.
STOP_TOOLS = ("TaskStop",)
CLOSE_COMMAND = "handsoff.py close"
LAST_LEAD = ("The run's last lead (no successor left) may also stop its background tasks with "
             "TaskStop and close the run with handsoff.py close.")
SID_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")   # a marker file name is built from this, or not at all


def note(msg):
    sys.stderr.write("[handsoff-gate] %s\n" % msg)


def state_dir():
    return os.path.expanduser(os.environ.get("AIMYTH_STATE_DIR")
                              or os.path.join("~", ".aimyth", "handoffs"))


def read_cap():
    raw = os.environ.get("AIMYTH_READ_CAP")
    if not raw:
        return DEFAULT_READ_CAP
    try:
        v = int(raw)
    except ValueError:
        v = 0
    if v <= 0:
        note("AIMYTH_READ_CAP=%r invalid; using %d" % (raw, DEFAULT_READ_CAP))
        return DEFAULT_READ_CAP
    return v


def armed(sid):
    """Environment first (it needs no disk), then the marker file. A session id that is not a plain
    token cannot name a marker file: say so, and treat the session as unarmed by marker."""
    if os.environ.get("AIMYTH_HANDSOFF") == "1":
        return True
    if not sid:
        return False
    if not SID_RE.fullmatch(sid):
        note("session id %r is not a plain token: marker arming skipped" % sid)
        return False
    return os.path.isfile(os.path.join(state_dir(), "armed-" + sid))


def watermark():
    spec = importlib.util.spec_from_file_location(
        "context_watermark", os.path.join(HERE, "context-watermark.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def field(v):
    return str(v).replace("\t", " ").replace("\n", " ") or "unknown"


def log_event(sid, action, tool, ctx):
    """One events.log line: the deny's, or a last-lead allowance's (`allow-last-lead`)."""
    d = state_dir()
    p = os.path.join(d, "events.log")
    try:
        os.makedirs(d, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("%s\t%s\thandsoff-gate\t%s\t%s\t%d\n"
                    % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), field(sid), action, field(tool), ctx))
    except OSError as e:
        note("events.log append failed at %s: %s" % (p, e))


def log_deny(sid, tool, ctx):
    log_event(sid, "deny", tool, ctx)


def last_lead(sid):
    """handsoff.py's last_lead_state(sid): ("last" | "not-last" | "undecided", text). The module
    is loaded from the delegate skill beside this hooks folder, with stdout sent to stderr so
    nothing but this hook's JSON reaches stdout; no bytecode is written (dont_write_bytecode
    above). Anything raised, a missing module included, is undecided."""
    path = os.path.join(HERE, os.pardir, "skills", "delegate", "handsoff.py")
    try:
        with contextlib.redirect_stdout(sys.stderr):
            spec = importlib.util.spec_from_file_location("handsoff_gate_handsoff", path)
            if spec is None or spec.loader is None:
                return "undecided", "handsoff.py cannot be loaded from %s" % path
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            state, text = mod.last_lead_state(sid)
        return state, text
    except BaseException as e:   # SystemExit, a missing file, anything: the deny stands
        return "undecided", "%s: %s" % (type(e).__name__, e)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))


def read_limit(ti):
    """(bounded, shown) for a Read's `limit`. A missing, non-integer or non-positive limit is not
    bounded: above the second band a caller says how much it is reading, or it does not read."""
    v = ti.get("limit")
    cap = read_cap()
    if isinstance(v, bool) or not isinstance(v, (int, str)):
        return False, "no limit" if v is None else "limit %r" % (v,)
    if isinstance(v, str):
        if not v.strip().isdigit():
            return False, "limit %r" % (v,)
        v = int(v.strip())
    if v <= 0 or v > cap:
        return False, "limit %d" % v
    return True, "limit %d" % v


def main():
    raw = sys.stdin.read()
    try:
        ev = json.loads(raw) if raw.strip() else None
    except ValueError:
        ev = None
    if not isinstance(ev, dict):
        note("premise failure: unreadable payload (%d bytes); allowing the call" % len(raw))
        return
    name = ev.get("hook_event_name")
    if name is not None and name != "PreToolUse":
        note("ignoring event %s (registered for PreToolUse only)" % name)
        return
    sid = ev.get("session_id") or ""
    if not armed(sid):
        return
    tool = field(ev.get("tool_name"))
    ti = ev.get("tool_input")
    if not isinstance(ti, dict):
        ti = {}
    try:
        mod = watermark()
    except Exception as e:
        note("premise failure: watermark module unavailable (%s: %s); allowing %s"
             % (type(e).__name__, e, tool))
        return
    m = mod.measure(ev.get("transcript_path"))
    ctx = m.get("context")
    if ctx is None:
        note("premise failure: %s; allowing %s" % (m.get("reason", "unknown"), tool))
        return
    w, b = mod.window(), mod.bands()
    idx = mod.band(ctx, w, b)
    figure = "context %s tokens (%d %% of %s)" % (
        format(ctx, ","), mod.percent(ctx, w), mod.fmt_window(w))
    if len(b) < HARD_EDGES:
        note("bands %s carry no third edge: the hard band is not enforced (read bound only)"
             % ",".join(str(e) for e in b))
    elif idx >= HARD_EDGES:
        cmd = ti.get("command") if tool == "Bash" else None
        if isinstance(cmd, str) and any(a in cmd for a in ALLOWED):
            return
        why = ""
        asked = ("TaskStop" if tool in STOP_TOOLS else CLOSE_COMMAND
                 if isinstance(cmd, str) and CLOSE_COMMAND in cmd else None)
        if asked is not None:
            state, text = last_lead(sid)
            if state == "last":
                note("hard band: %s allowed for the run's last lead (%s; the owner's decision of "
                     "2026-10-30)" % (asked, text))
                log_event(sid, "allow-last-lead", tool, ctx)
                return
            if state == "not-last":
                why = (" %s passes at the hard band only for the run's last lead, and this lead is "
                       "not (%s)." % (asked, text))
            else:
                why = (" %s: whether this lead is the run's last could not be read (%s), so the "
                       "hard band stands." % (asked, text))
        deny("hands-off hard band: %s, at or above the %d %% edge. Every tool call is denied except "
             "the close-out: %s. %s%s Write the hand-off now and end the session."
             % (figure, b[HARD_EDGES - 1], ", ".join(ALLOWED), LAST_LEAD, why))
        log_deny(sid, tool, ctx)
        return
    if len(b) >= 2 and idx >= 2 and tool == "Read":
        bounded, shown = read_limit(ti)
        if not bounded:
            deny("bounded reads only above %d %% under hands-off: pass limit ≤ %d (this Read: %s; "
                 "%s). One unbounded read can cross the remaining headroom in a single call."
                 % (b[1], read_cap(), shown, figure))
            log_deny(sid, tool, ctx)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # fail-open: a broken guard must never block a session
        sys.stderr.write("[handsoff-gate] %s: %s\n" % (type(e).__name__, e))
    sys.exit(0)
