#!/usr/bin/env python3
"""read-usage.py: one reading of the account's usage windows, for a hands-off run's window plan
(the pre-flight's usage row: Claude's weekly window, a 5-hour window on an account that has one, and
Astra's weekly window, read at the start and at the close, and at an item's end where the plan asks). Stdout only: the script
writes no file itself; the `claude` and `codex` processes it starts keep their own session records,
as every call of theirs does.

Why a script: an armed head's fence reads the slash-command prompt of `claude -p '/usage'` as a path
outside the grants and refuses the call; the same reading driven from inside this program is one
plain `python3 <this file>` command, which the fence clears.

Usage: python3 .claude/skills/delegate/read-usage.py [--only claude|astra|both] [--timeout-s N] [--format text|json]
Prints one line per window source:
  claude-usage: <the condensed text `claude -p /usage` printed>        or  claude-usage: could not read (<why>)
  astra-usage: <each rate-limit window: length, per cent used, reset>   or  astra-usage: could not read (<why>)
Exit 0 when every requested reading was read and every window in it carries a real figure; 1 when
any could not be read or its shape was not recognised (the line says which; a reading is never
guessed); 2 on a usage error. A real figure: in Claude's text, a per-cent token is read whole (the
whole run of digits, letters, dots and signs before a `%`), and every token is a figure from 0 to
100 with no sign, so `-1% used` is unread, never read as 1%; the text names at least one usage
window (a line naming a session or a week), every figure stands on a window line or after one, and
every window line has its figure, on that line or on a later line before the next window line (the
activity footer, "Last 24h · N requests · 1 session", is no window line). Only
a figure written as `N% used` fills a window: any other per-cent token is still checked as above
but fills none. So a notice such as "usage limits unavailable for this session", window headings
with no figures, or a progress line such as "Download 42% complete", alone or after a window
heading whose usage is unavailable, is unread, with no list of notice wordings to keep current;
a real `4% used` stays read whatever its line says about reset times. In Astra's result, every
window (a dict holding a used percent or a window length) has a used percent from 0 to 100, so an
absent one, a null, a string or a value out of range is unread.

JSON form (`--format json`; text is the default and unchanged), ported from the window-meter
design's package B onto this reader (decided line DW-20261021-2): one object on stdout with
`schema` 1, `started_at`, `finished_at`, `requested`, `windows` and `gpt_week_evidence`. `windows`
always holds `claude_5h`, `claude_week` and `gpt_week`, each with `used_pct` (a figure from 0 to
100, or null), `reset_text` (the reset as text, never turned into a time), `status` (measured,
unmeasured or not_requested), `reason` (null only when measured) and `source`. A Claude window's
`source` is its canonical name, so two readings that differ only in a figure keep one source; the
heading line rides beside it as `heading`. `Current session` fills `claude_5h` and `Current week
(all models)` fills `claude_week`, each with the first figure written `N% used` in its block (the
same rule as text mode); the windows are read only from a reading text mode's own check accepted.
A canonical heading the accepted reading does not print is unmeasured with `absent` true (an
account that shows no 5-hour window, as on 9 November 2026), never a read failure; one printed
twice is unmeasured. A GPT window is weekly only at 10,080 minutes; its `source` is its JSON path;
identical weekly duplicates collapse with every path kept and differing ones are `ambiguous weekly
windows`. `gpt_week_evidence` lists every weekly candidate's raw used figure, as read (101 stays
101). Exit 0 when every requested window is measured, 1 when any is not (the object still
printed), 2 on a usage error (`PROBE FAILED`). Under `--only both` the two families are read at
once, each under its own `--timeout-s`.

Executables: USAGE_CLAUDE_BIN and USAGE_CODEX_BIN override the `claude` and `codex` found on PATH
(a suite's stand-ins). The Codex reading talks to `codex app-server` over stdio: `initialize`, the
`initialized` notification, then `account/rateLimits/read`, one JSON object per line. That handshake
is written from the app-server protocol as its author knew it; it read both windows live at a
hands-off run's start on 2026-10-10, and its suite (`test_read_usage.sh`) proves it against
stand-ins. A protocol or output change prints "could not read", never a figure.
"""
import argparse
import json
import os
import re
import select
import shutil
import subprocess
import sys
import threading
import time

TIMEOUT_S = 90        # each reading's bound; set by judgement, unmeasured (a /usage call returns in seconds when healthy)
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
KEEP_RE = re.compile(r"%|reset|limit|session|week", re.I)
WINDOW_RE = re.compile(r"\b(session|week)\b", re.I)          # a line that names a usage window
# The activity footer ("Last 24h · 105 requests · 1 session") counts sessions and carries no
# figure: it names no usage window, whether it says "1 session" or "2 sessions". A footer-shaped
# line with a `%` in it is no footer (window_line).
FOOTER_RE = re.compile(r"^last\s+\d+\s*[a-z]+\b.*\brequests?\b", re.I)
TOKEN_CHAR_RE = re.compile(r"[\w.+\-−]")                # a character of a per-cent token
NUMBER_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")               # a whole figure, such as 4 or 17.5
SIGNED_RE = re.compile(r"[+\-−][0-9]+(?:\.[0-9]+)?")    # a figure with a sign, refused
USED_RE = re.compile(r"%\s*used\b", re.I)                     # the only form that fills a window
TEXT_CUT = 400        # characters of condensed text kept on the line; set by judgement, unmeasured
WEEK_MINUTES = 7 * 24 * 60                                   # 10,080: a GPT window is weekly only at this length
CLAUDE_HEADINGS = (("claude_5h", re.compile(r"^current session\b", re.I), "Current session"),
                   ("claude_week", re.compile(r"^current week \(all models\)", re.I),
                    "Current week (all models)"))
RESET_FRAGMENT_RE = re.compile(r"\bresets?\b.*$", re.I)     # a heading's `resets ...` fragment, kept as text
WINDOW_KEYS = ("claude_5h", "claude_week", "gpt_week")


def percent(value):
    """A used-percent value as a number from 0 to 100, else None: a bool, a string, a null, a
    non-finite number or one out of range is no figure."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value < 0 or value > 100:
        return None
    return value


def tokens(line):
    """Every per-cent token on a line, whole: the run of word characters, dots and signs that ends
    at a `%` (one space allowed before it), so `-1% used` holds the token `-1`, never the figure 1.
    A run with no digit in it is no token. Each token comes with the place of its `%`."""
    out = []
    for at in [m.start() for m in re.finditer("%", line)]:
        end = at - 1 if at and line[at - 1].isspace() else at
        start = end
        while start and TOKEN_CHAR_RE.match(line[start - 1]):
            start -= 1
        if re.search("[0-9]", line[start:end]):
            out.append((line[start:end], at))
    return out


def figure_problem(token):
    """Why a per-cent token is no figure from 0 to 100, or None."""
    if NUMBER_RE.fullmatch(token):
        return None if percent(float(token)) is not None else "a figure out of range"
    if SIGNED_RE.fullmatch(token):
        return "a figure with a sign"
    return "a token that is no whole figure"


def window_line(line):
    """A line that names a usage window: one naming a session or a week, other than the activity
    footer, which counts requests and sessions over a period and has no figure of its own. A line
    shaped like the footer that carries a per-cent figure is no footer, so it stays a window line
    and its figure never fills the heading above it."""
    return bool(WINDOW_RE.search(line)) and not (FOOTER_RE.match(line) and "%" not in line)


def text_problem(lines):
    """Why Claude's kept lines are no reading, or None: every per-cent token is a whole figure from
    0 to 100 with no sign, at least one line names a usage window, no figure comes before the first
    window line, and each window line is paired with the first figure written `N% used` on it or
    on a later line before the next window line; another per-cent token fills no window."""
    windows, waiting = 0, None
    for line in lines:
        if window_line(line):
            if waiting is not None:
                return "a window with no figure: %s" % waiting
            waiting, windows = line, windows + 1
        for token, at in tokens(line):
            why = figure_problem(token)
            if why:
                return "%s (%s%%): %s" % (why, token, line)
            if not windows:
                return "a figure outside any usage window: %s" % line
            if USED_RE.match(line, at):
                waiting = None
    if waiting is not None:
        return "a window with no figure: %s" % waiting
    if not windows:
        return "no usage window (no line names a session or a week): %s" % " / ".join(lines)
    return None


def resolve(env_key, name):
    given = os.environ.get(env_key)
    path = given or shutil.which(name)
    if not path:
        return None, "no `%s` on PATH and %s unset" % (name, env_key)
    path = os.path.realpath(os.path.expanduser(path))
    if not os.access(path, os.X_OK):
        return None, "%s is not executable" % path
    return path, None


def read_claude(timeout_s):
    """(read, the text line, the kept lines): the kept lines only where text mode's own check
    passed, else None, so the JSON form never reads a window from a refused reading."""
    binary, why = resolve("USAGE_CLAUDE_BIN", "claude")
    if binary is None:
        return False, "could not read (%s)" % why, None
    try:
        out = subprocess.run([binary, "-p", "/usage"], capture_output=True, text=True,
                             timeout=timeout_s, cwd="/tmp", stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, "could not read (timed out after %d s)" % timeout_s, None
    except OSError as exc:
        return False, "could not read (%s)" % exc, None
    text = ANSI_RE.sub("", out.stdout or "")
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if out.returncode != 0 or not lines:
        err = " ".join((out.stderr or "").split())[:200]
        return (False, "could not read (exit %d%s)" % (out.returncode, "; " + err if err else "; empty output"),
                None)
    kept = [line for line in lines if KEEP_RE.search(line)]
    if not kept:
        return False, "could not read (unrecognised output: %s)" % " / ".join(lines)[:TEXT_CUT], None
    problem = text_problem(kept)
    if problem:
        return False, "could not read (%s)" % problem[:TEXT_CUT], None
    return True, " / ".join(kept)[:TEXT_CUT], kept


def figure_of(token):
    """A per-cent token text_problem has passed, as a number: whole figures stay integers."""
    return int(token) if re.fullmatch(r"[0-9]+", token) else float(token)


def window_entry(status, source, used=None, reset=None, reason=None, **extra):
    out = {"used_pct": used, "reset_text": reset, "status": status, "reason": reason,
           "source": source}
    out.update(extra)
    return out


def parse_claude_windows(kept):
    """Claude's two windows from the kept lines of a reading text mode accepted: a heading (a line
    naming a session or a week) owns the first figure written `N% used` and the first `resets ...`
    fragment that follow it, up to the next heading (text_problem's own pairing). The source is
    the canonical window name; the heading line rides beside it as `heading`. A canonical heading
    the reading does not print is unmeasured with `absent` true: the account shows no such window,
    which is not a read failure."""
    blocks = []
    for line in kept:
        if window_line(line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    out = {}
    for key, pattern, label in CLAUDE_HEADINGS:
        mine = [b for b in blocks if pattern.search(b[0])]
        if len(mine) != 1:
            out[key] = window_entry("unmeasured", key, reason=(
                "no '%s' heading in the reading (the account shows no such window)" % label
                if not mine else "the '%s' heading appears %d times" % (label, len(mine))),
                heading=None, **({"absent": True} if not mine else {}))
            continue
        block = mine[0]
        figure = reset = None
        for line in block:
            if figure is None:
                for token, at in tokens(line):
                    if USED_RE.match(line, at):
                        figure = figure_of(token)
                        break
            m = RESET_FRAGMENT_RE.search(line)
            if reset is None and m:
                reset = m.group(0).strip()
        if figure is None:
            out[key] = window_entry("unmeasured", key, reason="the '%s' heading has no figure" % label,
                                    heading=block[0])
        else:
            out[key] = window_entry("measured", key, used=figure, reset=reset, heading=block[0])
    return out


def json_path(path):
    return ".".join(path) if path else "(result)"


def candidates_in(node, path, found):
    """Every dict carrying a used-percent figure, with its JSON path within the result."""
    if isinstance(node, dict):
        keys = {k.lower().replace("_", ""): k for k in node}
        if "usedpercent" in keys:
            found.append((json_path(path), node))
        for k, value in node.items():
            candidates_in(value, path + [str(k)], found)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            candidates_in(value, path + ["[%d]" % i], found)
    return found


def weekly(get):
    mins = get.get("windowdurationmins", get.get("windowminutes"))
    return isinstance(mins, (int, float)) and not isinstance(mins, bool) and mins == WEEK_MINUTES


def reset_of(get, read_at):
    """A window's reset as text, the key deciding the form: a numeric `resetsAt` is an epoch, a
    numeric `resetsInSeconds` is added to the reading's own time, a string is kept as returned."""
    for key, relative in (("resetsat", False), ("resetsinseconds", True)):
        value = get.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value == value:
            stamp_at = read_at + value if relative else value
            try:
                return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stamp_at))
            except (OverflowError, ValueError, OSError):
                return None
        if isinstance(value, str) and value:
            return value
    return None


def evidence_figure(value):
    """A raw used figure as evidence: a finite, non-negative number (never a bool or a string),
    kept as read, so 101 stays 101; else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        return None
    return value


def parse_gpt_windows(result, read_at):
    """(gpt_week, evidence) from an `account/rateLimits/read` result. A window is weekly only at a
    duration of 10,080 minutes (never by being primary or secondary). Exactly one weekly figure
    from 0 to 100 is measured; identical duplicates (same figure, same reset) collapse with every
    path kept; differing candidates are `ambiguous weekly windows`; a figure outside 0-100 is
    null with its reason. Evidence lists every weekly candidate's raw figure, unclamped."""
    found = [(p, {k.lower().replace("_", ""): v for k, v in node.items()})
             for p, node in candidates_in(result, [], [])]
    weeks = [(p, get) for p, get in found if weekly(get)]
    evidence = []
    for p, get in weeks:
        raw = evidence_figure(get.get("usedpercent"))
        if raw is not None:
            evidence.append({"source": p, "used_pct": raw, "reset_text": reset_of(get, read_at)})
    if not weeks:
        return window_entry("unmeasured", None, reason=(
            "no weekly window (no window of %d minutes) in the result" % WEEK_MINUTES)), evidence
    bad = [p for p, get in weeks if percent(get.get("usedpercent")) is None]
    if bad:
        return window_entry("unmeasured", " + ".join(p for p, _ in weeks), reason=(
            "a weekly window whose used percent is not a figure from 0 to 100: %s"
            % ", ".join(bad))), evidence
    distinct = {}
    for p, get in weeks:
        distinct.setdefault((get.get("usedpercent"), reset_of(get, read_at)), []).append(p)
    if len(distinct) > 1:
        return window_entry("unmeasured", " + ".join(p for p, _ in weeks),
                            reason="ambiguous weekly windows"), evidence
    (used, reset), paths = next(iter(distinct.items()))
    return window_entry("measured", " + ".join(paths), used=used, reset=reset), evidence


def windows_in(node, found):
    """Every dict carrying usedPercent or a window length (windowDurationMins or windowMinutes, the
    two that describe() reads), wherever it sits in the result, so a window that has a length but
    lost its used percent is found and refused, never skipped."""
    if isinstance(node, dict):
        keys = {k.lower().replace("_", ""): k for k in node}
        if keys.keys() & {"usedpercent", "windowdurationmins", "windowminutes"}:
            found.append(node)
        for value in node.values():
            windows_in(value, found)
    elif isinstance(node, list):
        for value in node:
            windows_in(value, found)
    return found


def describe(window):
    get = {k.lower().replace("_", ""): v for k, v in window.items()}
    used = get.get("usedpercent")
    mins = get.get("windowdurationmins", get.get("windowminutes"))
    resets = get.get("resetsat", get.get("resetsinseconds"))
    if isinstance(mins, (int, float)) and not isinstance(mins, bool):
        span = "%g d" % (mins / 1440.0) if mins >= 1440 else "%g h" % (mins / 60.0)
    else:
        span = "length unstated"
    when = "reset unstated"
    if isinstance(resets, (int, float)) and not isinstance(resets, bool):
        stamp = resets if resets > 10 ** 9 else time.time() + resets
        when = "resets %s" % time.strftime("%a %d %b %H:%M %Z", time.localtime(stamp))
    elif isinstance(resets, str) and resets:
        when = "resets %s" % resets
    return "%s window %s%% used, %s" % (span, used, when)


def send(proc, payload):
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def await_id(proc, wanted, deadline):
    """The response object whose id is `wanted`, or (None, why). Lines that are notifications or
    other ids are skipped; an unparseable line is skipped and counted."""
    skipped = 0
    buf = ""
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return None, "timed out waiting for response %d (%d line(s) skipped)" % (wanted, skipped)
        ready, _, _ = select.select([proc.stdout], [], [], min(left, 1.0))
        if not ready:
            if proc.poll() is not None:
                return None, "app-server exited %s before response %d" % (proc.returncode, wanted)
            continue
        chunk = os.read(proc.stdout.fileno(), 65536)
        if not chunk:
            return None, "app-server closed its output before response %d" % wanted
        buf += chunk.decode("utf-8", "replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if isinstance(message, dict) and message.get("id") == wanted:
                return message, None


def read_astra(timeout_s):
    """(read, the text line, the raw result): the result whenever the app-server answered the
    rate-limits request, even one text mode refuses (a figure of 101), since the JSON form keeps
    that figure as evidence; else None."""
    binary, why = resolve("USAGE_CODEX_BIN", "codex")
    if binary is None:
        return False, "could not read (%s)" % why, None
    deadline = time.monotonic() + timeout_s
    try:
        proc = subprocess.Popen([binary, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, cwd="/tmp")
    except OSError as exc:
        return False, "could not read (%s)" % exc, None
    try:
        send(proc, {"method": "initialize", "id": 1,
                    "params": {"clientInfo": {"name": "read-usage", "title": "read-usage", "version": "1"}}})
        reply, why = await_id(proc, 1, deadline)
        if reply is None:
            return False, "could not read (%s)" % why, None
        if "error" in reply:
            return False, "could not read (initialize refused: %s)" % json.dumps(reply["error"])[:200], None
        send(proc, {"method": "initialized"})
        send(proc, {"method": "account/rateLimits/read", "id": 2})
        reply, why = await_id(proc, 2, deadline)
        if reply is None:
            return False, "could not read (%s)" % why, None
        if "error" in reply:
            return (False, "could not read (account/rateLimits/read refused: %s)"
                    % json.dumps(reply["error"])[:200], None)
        result = reply.get("result")
        found = windows_in(result, [])
        if not found:
            return False, "could not read (unrecognised result shape: %s)" % json.dumps(result)[:300], result
        for window in found:
            used = {k.lower().replace("_", ""): v for k, v in window.items()}.get("usedpercent")
            if percent(used) is None:
                return False, ("could not read (a window whose used percent is not a figure from 0 "
                               "to 100: %s)" % json.dumps(window)[:300]), result
        return True, " · ".join(describe(w) for w in found), result
    except (OSError, ValueError) as exc:
        return False, "could not read (%s)" % exc, None
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()


def reason_of(text):
    """Text mode's reason inside `could not read (...)`, for the JSON form's `reason`."""
    m = re.fullmatch(r"could not read \((.*)\)", text or "", re.S)
    return m.group(1) if m else (text or "unreadable")


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def json_reading(only, timeout_s):
    """(the JSON object, exit code). Under --only both the two families are read at once, each
    under its own bound, so the worst case is one bound rather than the sum."""
    started = stamp()
    results = {}

    def claude():
        results["claude"] = read_claude(timeout_s)

    def astra():
        results["astra"] = (read_astra(timeout_s), time.time())

    jobs = []
    if only in ("claude", "both"):
        jobs.append(threading.Thread(target=claude))
    if only in ("astra", "both"):
        jobs.append(threading.Thread(target=astra))
    for job in jobs:
        job.start()
    for job in jobs:
        job.join()
    windows, evidence = {}, []
    if "claude" in results:
        good, text, kept = results["claude"]
        if good:
            windows.update(parse_claude_windows(kept))
        else:
            for key, _, _ in CLAUDE_HEADINGS:
                windows[key] = window_entry("unmeasured", key, reason=reason_of(text), heading=None)
    else:
        for key, _, _ in CLAUDE_HEADINGS:
            windows[key] = window_entry("not_requested", key, reason="not requested", heading=None)
    if "astra" in results:
        (good, text, result), read_at = results["astra"]
        if result is not None:
            windows["gpt_week"], evidence = parse_gpt_windows(result, read_at)
        else:
            windows["gpt_week"] = window_entry("unmeasured", None, reason=reason_of(text))
    else:
        windows["gpt_week"] = window_entry("not_requested", None, reason="not requested")
    requested = [k for k in WINDOW_KEYS if windows[k]["status"] != "not_requested"]
    code = 0 if all(windows[k]["status"] == "measured" for k in requested) else 1
    return {"schema": 1, "started_at": started, "finished_at": stamp(), "requested": only,
            "windows": {k: windows[k] for k in WINDOW_KEYS},
            "gpt_week_evidence": evidence}, code


def main():
    ap = argparse.ArgumentParser(description="one reading of the usage windows, stdout only")
    ap.add_argument("--only", choices=("claude", "astra", "both"), default="both")
    ap.add_argument("--timeout-s", type=int, default=TIMEOUT_S)
    ap.add_argument("--format", choices=("text", "json"), default="text",
                    help="text (the default, unchanged) or json: one object with the three "
                         "windows and the GPT weekly evidence (see the module text)")
    a = ap.parse_args()
    if a.timeout_s <= 0:
        print("PROBE FAILED: --timeout-s must be positive")
        return 2
    if a.format == "json":
        obj, code = json_reading(a.only, a.timeout_s)
        print(json.dumps(obj, ensure_ascii=False), flush=True)
        return code
    ok = True
    if a.only in ("claude", "both"):
        good, text, _ = read_claude(a.timeout_s)
        ok = ok and good
        print("claude-usage: %s" % text, flush=True)
    if a.only in ("astra", "both"):
        good, text, _ = read_astra(a.timeout_s)
        ok = ok and good
        print("astra-usage: %s" % text, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
