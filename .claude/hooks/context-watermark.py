#!/usr/bin/env python3
"""context-watermark.py — UserPromptSubmit hook: one line of context metering per prompt.

Reads only the TAIL of this session's transcript (the last TAIL_BYTES, by seek — never a
whole read, so the cost stays flat as the transcript grows), finds the last QUALIFYING
assistant usage record, and injects one line as additionalContext:

    context: 284,481 tokens (28 % of 1M) · transcript 1.4 MB · ok

A record qualifies when message.role is "assistant", message.usage is an object, the record
is not a sidechain (a lane's turn interleaved in the head's file), message.model does not
start with "<synthetic" and the stock is non-zero: a limit-stop record carries a synthetic
model and all-zero usage and would otherwise read as `context: 0 · ok` at the worst moment.
context = input_tokens + cache_read_input_tokens + cache_creation_input_tokens (missing keys
count 0) — the three quantities the lane close-out meters, so head and lane figures compare
directly. The last field is one of `ok` · `write the hand-off document at the next item
boundary` · `hand-off band: finish what is in flight and open a new item only where the hands-off
gate's fit check allows it (an attended session starts nothing new)` · `hard band: write
the hand-off now and end the session`, chosen by the bands (lower edge inclusive; the fourth text
needs a third edge, which the hands-off default carries). These shared texts serve importers,
armed sessions, other windows and explicit AIMYTH_BANDS settings. With no band
override, an unarmed 1M session uses an attended-only path that shows no band text and names
its thresholds in tokens, never as a percentage (owner decision of 9 October 2026): every
metered prompt below 900k carries the fit sum (context now + the work's estimate + the 50k
close-out < 950k), to be stated before new work, with nothing new started without an estimate;
at 900k start the full close; above 900k close in full if the head's share of the close fits,
else use the short close; at the 950,000-token belt update the hand-off and, if the close is
pending, its calendar line, then stop. The figure is the last request's usage, never a mid-turn
meter or a mechanical fit gate. Where the prompt names an EXISTING
hand-off document (a file ending `-handoff.md` directly inside a `handoffs` directory), the line
appends ` · hand-off named: <path>`, so a successor's first turn shows what it inherited.
Each metered prompt appends `ts<TAB>session_id<TAB>context<TAB>percent`
to the watermark log — the head-session series a maintenance review reads.

Knobs (env):
  AIMYTH_CONTEXT_WINDOW  window in tokens (default 1000000: the contextWindow the harness reports
                         for the 1M model; set it lower for a smaller model)
  AIMYTH_BANDS           "60,80,90" — TWO OR THREE band edges in percent, integers, ascending.
                         Derivation (fit-based-continuation-design, 2026-09-14): in a hands-off run the
                         gate computes whether the NEXT item fits (memory + the item's cost + the pack
                         allowance under the belt, the third edge), and 60 and 80 are only its fallbacks
                         for a missing figure. The legacy advisory marks remain selectable:
                         60 % is the point from which a hand-off should exist
                         (measured item costs run 30k to 125k; the largest single call on record, 369k,
                         predates the armed hook that now bounds a call), 80 % the point past which one
                         more item may reach the window. The third edge, 90 %, is the hands-off hard band
                         (hands-off-mode-design, D1): set by judgement, unmeasured. The attended
                         path above reads no edge. Two edges keep the legacy three-text line; a fourth edge, a
                         descending pair or a bad token falls back to the default, on stderr.
  AIMYTH_WATERMARK_LOG   default ~/.aimyth/logs/context-watermark.log (the hook logs' own folder,
                         apart from the hand-offs; directory created)
  AIMYTH_PROJECTS_DIR    default ~/.claude/projects — the root a transcript must sit under; a
                         path elsewhere is a stale or foreign transcript and is reported as
                         unmetered rather than measured (tests point this at a fixture)
  AIMYTH_HANDSOFF        "1" selects the legacy texts, as does an armed-<session_id> marker
  AIMYTH_STATE_DIR       marker root (default ~/.aimyth/handoffs), as in handsoff-gate.py

Premise failures, declared never silent, exit 0: bad stdin (empty, malformed, or not a JSON
object); no transcript_path; a path outside the projects dir; no qualifying usage record in the
tail — each `context: unmetered (<reason>)`. A missing or empty transcript is turn 1 of a
session rather than a fault (the harness creates the file after the first prompt), so it reads
`context: start (no transcript yet)`; measure() still carries the precise reason, under a
`start` flag, for a caller that wants it. An event that
is not UserPromptSubmit (a mis-registration) is noted on stderr and injects nothing — keyed
on the stdin field, never on which matcher fired. Never blocks: every path exits 0; stdout
carries the JSON line or nothing; diagnostics go to stderr.

Shared by import with precompact-checkpoint.py, handsoff-gate.py and the delegate skill's
handsoff.py: measure(), render(), window(), bands() — extend these, never rename them.
"""
import json
import os
import re
import sys
import time

TAIL_BYTES = 512 * 1024
# Bound, not a threshold. Headroom: the last usage record sits 2–3 kB from the end of a 10 MB
# transcript and the largest single record seen is 143 kB (design page, §Components).
DEFAULT_WINDOW = 1_000_000
DEFAULT_BANDS = (60, 80, 90)   # percent; derivation in the docstring (both design pages)
# Attended policy, 2026-10-05; tokens, since the attended path runs on the 1M window alone.
# The 950k belt is set by judgement, unmeasured as a safe threshold. PreCompact observations:
# 966,186 (24 September), 965,974 (1 October), 1,002,694 (2 September); the belt is 15,974
# below the lowest, not a promised compaction limit.
ATTENDED_BELT = 950_000
# Provisional reserve from one close: 908,206 - 866,568 = 41,638 tokens;
# including following turns: 915,609 - 866,568 = 49,041, rounded up to 50k.
ATTENDED_RESERVE = 50_000
ATTENDED_CLOSE = ATTENDED_BELT - ATTENDED_RESERVE
BAND_TEXT = ("ok",
             "write the hand-off document at the next item boundary",
             "hand-off band: finish what is in flight and open a new item only where the "
             "hands-off gate's fit check allows it (an attended session starts nothing new)",
             "hard band: write the hand-off now and end the session")
MAX_EDGES = len(BAND_TEXT) - 1   # one edge per text after "ok": two edges or three
START_TEXT = "context: start (no transcript yet)"
HANDOFF_DIR = "handoffs"          # a hand-off document sits directly in this directory (design)
HANDOFF_SUFFIX = "-handoff.md"    # ...and its name ends here (hands-off design, §Trace schema)
SPLIT_RE = re.compile(r"""[\s"'`<>()\[\]{},;]+""")   # a prompt into candidate tokens
TRIM = ".,;:!?"                   # sentence punctuation left on a named path
# Bounds on the prompt scan, not thresholds: a prompt can carry a pasted document, and each
# candidate costs a stat. Both set by judgement, unmeasured.
PROMPT_SCAN = 64 * 1024
MATCH_CAP = 8
USAGE_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def window():
    w = _int(os.environ.get("AIMYTH_CONTEXT_WINDOW"))
    return w if w > 0 else DEFAULT_WINDOW


def bands():
    """Two or three ascending edges in percent; three is the default and the third is the hard
    band. Anything else — a bad token, a fourth edge, a descending or out-of-range set — falls
    back to the default and says so on stderr, never to a silent partial parse."""
    raw = os.environ.get("AIMYTH_BANDS")
    if not raw:
        return DEFAULT_BANDS
    parts = [p.strip() for p in raw.split(",")]
    if 2 <= len(parts) <= MAX_EDGES and all(re.fullmatch(r"\d+", p) for p in parts):
        edges = tuple(int(p) for p in parts)
        if edges[0] > 0 and edges[-1] <= 100 and all(
                edges[i] <= edges[i + 1] for i in range(len(edges) - 1)):
            return edges
    sys.stderr.write("[context-watermark] AIMYTH_BANDS=%r invalid; using %s\n"
                     % (raw, ",".join(str(e) for e in DEFAULT_BANDS)))
    return DEFAULT_BANDS


def projects_dir():
    return os.environ.get("AIMYTH_PROJECTS_DIR") or os.path.join("~", ".claude", "projects")


def under_projects(path):
    root = os.path.realpath(os.path.expanduser(projects_dir()))
    p = os.path.realpath(os.path.expanduser(path))
    try:
        return os.path.commonpath([root, p]) == root
    except ValueError:
        return False


def last_usage(path):
    """The stock of the last qualifying assistant usage record in the transcript tail, or
    None. Skipped: sidechain records (a lane's context, never this session's), records whose
    model starts with "<synthetic" and records whose stock is zero (a limit-stop record is
    both, and would otherwise read as a false `ok`)."""
    size = os.path.getsize(path)
    start = max(0, size - TAIL_BYTES)
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read()
    lines = data.split(b"\n")
    if start > 0:
        lines = lines[1:]   # a seek rarely lands on a line start: drop the torn first chunk
    for line in reversed(lines):
        if b'"usage"' not in line:   # cheap pre-filter; the parse below is the decision
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("isSidechain"):
            continue
        msg = rec.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            continue
        if str(msg.get("model", "")).startswith("<synthetic"):
            continue
        stock = sum(_int(usage.get(k)) for k in USAGE_KEYS)
        if stock <= 0:
            continue
        return stock
    return None


def measure(tp):
    """{"context": int, "size": bytes} when metered, else {"reason": str}."""
    if not tp:
        return {"reason": "no transcript_path"}
    if not under_projects(tp):
        return {"reason": "path outside the projects dir"}
    tp = os.path.expanduser(tp)
    if not os.path.isfile(tp):
        return {"reason": "transcript missing", "start": True}   # turn 1: not created yet
    size = os.path.getsize(tp)
    if size == 0:
        return {"reason": "transcript empty", "start": True}     # turn 1: created, nothing flushed
    ctx = last_usage(tp)
    if ctx is None:
        return {"reason": "no qualifying usage record in the tail"}
    return {"context": ctx, "size": size}


def fmt_window(w):
    return "1M" if w == 1_000_000 else "%gk" % (w / 1000.0)


def fmt_size(n):
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.1f kB" % (n / 1024.0)
    return "%.1f MB" % (n / (1024.0 * 1024.0))


def band(context, w, b):
    """Index into BAND_TEXT: how many edges the figure has reached, lower edge inclusive — 0 to 2
    for two edges, 0 to 3 for three. Integer arithmetic, so the band agrees with the floored
    percent that is displayed."""
    return sum(1 for edge in b if context * 100 >= edge * w)


def percent(context, w):
    return context * 100 // w


def render(m, w=None, b=None):
    if m.get("context") is None:
        if m.get("start"):
            return START_TEXT
        return "context: unmetered (%s)" % m.get("reason", "unknown")
    w = w or window()
    b = b or bands()
    return "context: %s tokens (%d %% of %s) · transcript %s · %s" % (
        format(m["context"], ","), percent(m["context"], w), fmt_window(w),
        fmt_size(m["size"]), BAND_TEXT[band(m["context"], w, b)])


def attended(sid, w):
    """Only the unarmed 1M default; marker semantics match handsoff-gate.py's armed()."""
    if (w != DEFAULT_WINDOW or "AIMYTH_BANDS" in os.environ
            or os.environ.get("AIMYTH_HANDSOFF") == "1"):
        return False
    # Same plain-token bound as the gate: an unusable id cannot name a marker.
    if isinstance(sid, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", sid):
        root = os.path.expanduser(os.environ.get("AIMYTH_STATE_DIR")
                                  or os.path.join("~", ".aimyth", "handoffs"))
        if os.path.isfile(os.path.join(root, "armed-" + sid)):
            return False
    return True


def render_attended(m, w=None, b=None):
    """Advisory fit and close text on every metered prompt, with no band text and no band
    trigger; the shared render() keeps its legacy contract."""
    w = w or window()
    line = render(m, w, b)
    ctx = m.get("context")
    if ctx is None:   # unmetered and start lines carry no figure to sum
        return line
    belt, reserve, close = (format(n, ",") for n in
                            (ATTENDED_BELT, ATTENDED_RESERVE, ATTENDED_CLOSE))
    if ctx >= ATTENDED_BELT:
        text = ("%s-token belt reached: update the hand-off document and, if the close is pending, "
                "its calendar line; then stop" % belt)
    elif ctx > ATTENDED_CLOSE:
        text = ("close now: %s tokens remain under the %s-token belt, less than the %s close-out "
                "reserve; if the head's share of the close fits, close here in full; if not, "
                "short close: write the hand-off, the next prompt and a calendar line dated today "
                "naming the pending close; the next session runs the cross-reflection over the "
                "saved transcript and the calendar first, then checks its prompt against both "
                "before any work; the rest of the close it runs follows CUSTOMISATION.md's "
                "closing order, follow-up check included"
                % (format(ATTENDED_BELT - ctx, ","), belt, reserve))
    elif ctx == ATTENDED_CLOSE:
        text = ("full close-out now: %s tokens remain under the %s-token belt; run the "
                "cross-reflection with --yes and record accepted items first, then run the "
                "follow-up check over owner turns after the reflection's copy, then update the "
                "calendar only if a dated item was made or changed, then write the hand-off "
                "and give the next prompt last; stay under the belt" % (reserve, belt))
    else:
        text = ("fit: new work only if %s now + its estimate + %s close-out < %s tokens; "
                "state the sum first; no estimate, nothing new; start the close-out by %s tokens"
                % (format(ctx, ","), reserve, belt, close))
    return line.rsplit(" · ", 1)[0] + " · " + text


def named_handoff(prompt):
    """The first EXISTING hand-off document the prompt names, spelled as the prompt spells it, else
    None. A candidate is a whitespace- or bracket-delimited token whose name ends HANDOFF_SUFFIX
    and whose parent directory is named HANDOFF_DIR. A path that does not resolve is NOT reported:
    the suffix says the document is on disk to be read, and a stale path in a resume prompt must
    not read as a document in hand."""
    if not isinstance(prompt, str) or not prompt:
        return None
    seen = 0
    for tok in SPLIT_RE.split(prompt[:PROMPT_SCAN]):
        tok = tok.strip(TRIM)
        if not tok.endswith(HANDOFF_SUFFIX):
            continue
        if os.path.basename(os.path.dirname(tok)) != HANDOFF_DIR:
            continue
        seen += 1
        if seen > MATCH_CAP:
            break
        if os.path.isfile(os.path.expanduser(tok)):
            return tok
    return None


def sid_safe(sid):
    return re.sub(r"[^A-Za-z0-9._-]", "-", sid or "") or "unknown"


def append_log(sid, context, pct):
    path = os.path.expanduser(os.environ.get("AIMYTH_WATERMARK_LOG")
                              or os.path.join("~", ".aimyth", "logs", "context-watermark.log"))
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%d\t%d\n" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                          sid_safe(sid), context, pct))
    except OSError as e:
        sys.stderr.write("[context-watermark] log append failed at %s: %s\n" % (path, e))


def emit(text):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit", "additionalContext": text}}))


def main():
    raw = sys.stdin.read()
    try:
        ev = json.loads(raw) if raw.strip() else None
    except ValueError:
        ev = None
    if not isinstance(ev, dict):
        emit("context: unmetered (bad stdin)")   # declared, never silent
        return
    name = ev.get("hook_event_name")
    if name is not None and name != "UserPromptSubmit":
        sys.stderr.write("[context-watermark] ignoring event %s (registered for UserPromptSubmit only)\n" % name)
        return
    w, b = window(), bands()
    m = measure(ev.get("transcript_path"))
    if m.get("context") is not None:
        append_log(ev.get("session_id"), m["context"], percent(m["context"], w))
    line = render_attended(m, w, b) if attended(ev.get("session_id"), w) else render(m, w, b)
    named = named_handoff(ev.get("prompt"))
    if named:
        line += " · hand-off named: %s" % named
    emit(line)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # fail-safe: never block a prompt
        sys.stderr.write("[context-watermark] %s: %s\n" % (type(e).__name__, e))
    sys.exit(0)
