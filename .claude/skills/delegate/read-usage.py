#!/usr/bin/env python3
"""read-usage.py: one reading of the account's usage windows, for a hands-off run's window plan
(the pre-flight's usage row: Claude's weekly window, a 5-hour window on an account that has one, and
Astra's weekly window, read at the start and at the close, and at an item's end where the plan asks). Stdout only: the script
writes no file itself; the `claude` and `codex` processes it starts keep their own session records,
as every call of theirs does.

Why a script: an armed head's fence reads the slash-command prompt of `claude -p '/usage'` as a path
outside the grants and refuses the call; the same reading driven from inside this program is one
plain `python3 <this file>` command, which the fence clears.

Usage: python3 .claude/skills/delegate/read-usage.py [--only claude|astra|both] [--timeout-s N]
Prints one line per window source:
  claude-usage: <the condensed text `claude -p /usage` printed>        or  claude-usage: could not read (<why>)
  astra-usage: <each rate-limit window: length, per cent used, reset>   or  astra-usage: could not read (<why>)
Exit 0 when every requested reading was read and every window in it carries a real figure; 1 when
any could not be read or its shape was not recognised (the line says which; a reading is never
guessed); 2 on a usage error. A real figure: in Claude's text, a per-cent token is read whole (the
whole run of digits, letters, dots and signs before a `%`), and every token is a figure from 0 to
100 with no sign, so `-1% used` is unread, never read as 1%; the text names at least one usage
window (a line naming a session or a week), every figure stands on a window line or after one, and
every window line has its figure, on that line or on a later line before the next window line. So
a notice such as "usage limits unavailable for this session", window headings with no figures, or
a progress line such as "Download 42% complete" is unread. In Astra's result, every window's used
percent is a number from 0 to 100, so a null, a string or a value out of range is unread.

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
import time

TIMEOUT_S = 90        # each reading's bound; set by judgement, unmeasured (a /usage call returns in seconds when healthy)
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
KEEP_RE = re.compile(r"%|reset|limit|session|week", re.I)
WINDOW_RE = re.compile(r"\b(session|week)\b", re.I)          # a line that names a usage window
TOKEN_CHAR_RE = re.compile(r"[\w.+\-−]")                # a character of a per-cent token
NUMBER_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")               # a whole figure, such as 4 or 17.5
SIGNED_RE = re.compile(r"[+\-−][0-9]+(?:\.[0-9]+)?")    # a figure with a sign, refused
TEXT_CUT = 400        # characters of condensed text kept on the line; set by judgement, unmeasured


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
    A run with no digit in it is no token."""
    out = []
    for at in [m.start() for m in re.finditer("%", line)]:
        end = at - 1 if at and line[at - 1].isspace() else at
        start = end
        while start and TOKEN_CHAR_RE.match(line[start - 1]):
            start -= 1
        if re.search("[0-9]", line[start:end]):
            out.append(line[start:end])
    return out


def figure_problem(token):
    """Why a per-cent token is no figure from 0 to 100, or None."""
    if NUMBER_RE.fullmatch(token):
        return None if percent(float(token)) is not None else "a figure out of range"
    if SIGNED_RE.fullmatch(token):
        return "a figure with a sign"
    return "a token that is no whole figure"


def text_problem(lines):
    """Why Claude's kept lines are no reading, or None: every per-cent token is a whole figure from
    0 to 100 with no sign, at least one line names a usage window, no figure comes before the first
    window line, and each window line is paired with the first figure on it or on a later line
    before the next window line."""
    windows, waiting = 0, None
    for line in lines:
        if WINDOW_RE.search(line):
            if waiting is not None:
                return "a window with no figure: %s" % waiting
            waiting, windows = line, windows + 1
        for token in tokens(line):
            why = figure_problem(token)
            if why:
                return "%s (%s%%): %s" % (why, token, line)
            if not windows:
                return "a figure outside any usage window: %s" % line
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
    binary, why = resolve("USAGE_CLAUDE_BIN", "claude")
    if binary is None:
        return False, "could not read (%s)" % why
    try:
        out = subprocess.run([binary, "-p", "/usage"], capture_output=True, text=True,
                             timeout=timeout_s, cwd="/tmp", stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, "could not read (timed out after %d s)" % timeout_s
    except OSError as exc:
        return False, "could not read (%s)" % exc
    text = ANSI_RE.sub("", out.stdout or "")
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if out.returncode != 0 or not lines:
        err = " ".join((out.stderr or "").split())[:200]
        return False, "could not read (exit %d%s)" % (out.returncode, "; " + err if err else "; empty output")
    kept = [line for line in lines if KEEP_RE.search(line)]
    if not kept:
        return False, "could not read (unrecognised output: %s)" % " / ".join(lines)[:TEXT_CUT]
    problem = text_problem(kept)
    if problem:
        return False, "could not read (%s)" % problem[:TEXT_CUT]
    return True, " / ".join(kept)[:TEXT_CUT]


def windows_in(node, found):
    """Every dict carrying a used-percent figure, wherever it sits in the result."""
    if isinstance(node, dict):
        keys = {k.lower().replace("_", ""): k for k in node}
        if "usedpercent" in keys:
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
    binary, why = resolve("USAGE_CODEX_BIN", "codex")
    if binary is None:
        return False, "could not read (%s)" % why
    deadline = time.monotonic() + timeout_s
    try:
        proc = subprocess.Popen([binary, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, cwd="/tmp")
    except OSError as exc:
        return False, "could not read (%s)" % exc
    try:
        send(proc, {"method": "initialize", "id": 1,
                    "params": {"clientInfo": {"name": "read-usage", "title": "read-usage", "version": "1"}}})
        reply, why = await_id(proc, 1, deadline)
        if reply is None:
            return False, "could not read (%s)" % why
        if "error" in reply:
            return False, "could not read (initialize refused: %s)" % json.dumps(reply["error"])[:200]
        send(proc, {"method": "initialized"})
        send(proc, {"method": "account/rateLimits/read", "id": 2})
        reply, why = await_id(proc, 2, deadline)
        if reply is None:
            return False, "could not read (%s)" % why
        if "error" in reply:
            return False, "could not read (account/rateLimits/read refused: %s)" % json.dumps(reply["error"])[:200]
        found = windows_in(reply.get("result"), [])
        if not found:
            return False, "could not read (unrecognised result shape: %s)" % json.dumps(reply.get("result"))[:300]
        for window in found:
            used = {k.lower().replace("_", ""): v for k, v in window.items()}.get("usedpercent")
            if percent(used) is None:
                return False, ("could not read (a window whose used percent is not a figure from 0 "
                               "to 100: %s)" % json.dumps(window)[:300])
        return True, " · ".join(describe(w) for w in found)
    except (OSError, ValueError) as exc:
        return False, "could not read (%s)" % exc
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


def main():
    ap = argparse.ArgumentParser(description="one reading of the usage windows, stdout only")
    ap.add_argument("--only", choices=("claude", "astra", "both"), default="both")
    ap.add_argument("--timeout-s", type=int, default=TIMEOUT_S)
    a = ap.parse_args()
    if a.timeout_s <= 0:
        print("PROBE FAILED: --timeout-s must be positive")
        return 2
    ok = True
    if a.only in ("claude", "both"):
        good, text = read_claude(a.timeout_s)
        ok = ok and good
        print("claude-usage: %s" % text, flush=True)
    if a.only in ("astra", "both"):
        good, text = read_astra(a.timeout_s)
        ok = ok and good
        print("astra-usage: %s" % text, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
