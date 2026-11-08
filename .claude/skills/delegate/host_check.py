#!/usr/bin/env python3
"""host_check.py: the host facts that can stop or disturb an unattended run overnight.

Shape C of the host-check design (version 2): the head runs this while it writes a hands-off
pre-flight and puts the lines, with their times, in the pre-flight row G22, where the owner reads
them before he gives his go. It warns only. It is not in the launch path and blocks nothing.

Run:  python3 host_check.py --caller         the form the head runs: the design's caller
                                             contract as code (see call_collector)
      python3 host_check.py                  the collector alone
      python3 host_check.py --caller PATH    the caller on the collector at PATH (for the suite)
No other argument is accepted; standard library only.

Output: one line per fact, and after the lid fact one fixed line, each in the shape
    host <HH:MM:SS> · <fact> · ok|warn|unknown · <detail>
with the time at which that fact was read. The exit code is 0 whatever the host shows. A
failed, empty, malformed or timed-out read prints `unknown`, never `ok`; a fault inside one fact
prints that fact as `unknown`, and a fault outside every fact prints one `collector · unknown`
line. The caller passes those lines through unchanged, or prints instead the one line
`collector · unknown · <reason>` for a missing collector, a non-zero exit, a run past its 20 s
deadline or unparseable output.

Read-only by construction: it opens no file and writes nothing but its standard output. The
collector runs only the seven read commands named in the fact functions below; the caller runs
one more process, the collector itself under the same Python. On a platform other than macOS
every fact prints `unknown` and no command is run.

Each read command is looked up in the standard system directories only, never on PATH, so a
command earlier on the head's PATH cannot answer a fact. The suite puts its stubs in place
through HOST_CHECK_BIN_DIRS: when that variable is set and not empty, the directories it names
(separated as on PATH) are searched instead of the system directories.

Each read leads a session of its own, so it can be ended together with anything it started, and
a signal sent to this script never reaches it. SIGTERM, SIGINT and SIGHUP therefore stop the
script in order: the read in flight is ended, no further read starts, the fact in hand prints
`unknown` naming the signal, one `collector` line names the first fact left unread (when one
is), and the exit code is 0. The caller passes such a signal on to the collector the same way.
The stated limit: a process that a read starts in a session of its own escapes that kill; the
read still returns within its bound.
"""
import datetime
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time

OK, WARN, UNKNOWN = "ok", "warn", "unknown"

DOMAIN = "/Library/Preferences/com.apple.SoftwareUpdate"
SYSTEM_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
BIN_DIRS_VAR = "HOST_CHECK_BIN_DIRS"

# The bound on each read. The four reads that could be timed while this was built (pmset -g
# batt, custom and sched, and ioreg) each took at most 0.021 s over five runs on 5 October 2026,
# so 2 s leaves about a hundredfold margin; the 2 s itself is set by judgement.
READ_BOUND_S = 2.0
# How long a stopped child is given to be reaped before it is abandoned, and how long the
# collector, as the caller's child, is given after SIGTERM to end its own read (set by judgement).
REAP_S = 1.0
# The budget for all seven reads together: no read starts once it is spent, and no read's bound
# runs past it. Seven reads that all hang cost 7 x 2 s = 14 s, which fits; the last can overrun
# by REAP_S, so the collector returns by about 16 s, inside the caller's 20 s deadline, leaving
# 4 s for the interpreter's start (measured at 0.04 s) and the output. The margin is set by
# judgement.
TOTAL_BUDGET_S = 15.0
# How often a waiting read looks for a stop signal: a stop is honoured within this (set by
# judgement; the wake-ups cost nothing measurable).
SLICE_S = 0.1
# The most output one child may print, both streams together, before it is stopped. The largest
# read that could be measured (ioreg, 5 October 2026) printed 3,310 bytes and the collector's six
# lines are about 1 kB, so 1 MiB is over 300 times either; the cap itself is set by judgement.
OUTPUT_CAP = 1 << 20
CAP_TEXT = "1 MiB"
CHUNK = 1 << 16
# The caller contract of the design: the collector is run with a total deadline of 20 s. Past it
# the collector is sent SIGTERM, given REAP_S to end its read, then killed and reaped for at most
# REAP_S more, so the caller returns by about 22 s.
CALLER_DEADLINE_S = 20.0

LID_FACT = "lid"
LATER_LID_FACT = "later lid closure"
LATER_LID_TEXT = "this check cannot predict a later lid closure; keep the lid open"


# ------------------------------------------------------------------- stopping in order -----
STOP_SIGNALS = ("SIGTERM", "SIGINT", "SIGHUP")
_stopped = []


def on_stop(signum, frame):
    """Record a stop request; the waiting code acts on it within SLICE_S."""
    _stopped.append(signum)


def install_stop_handlers():
    for name in STOP_SIGNALS:
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            signal.signal(number, on_stop)
        except (OSError, ValueError, RuntimeError):
            pass


def signal_name(number):
    try:
        return signal.Signals(number).name
    except ValueError:
        return "signal %d" % number


def stop_text():
    return "%s was received" % signal_name(_stopped[0])


# ------------------------------------------------------------------------- reading ----------
class Read(object):
    """One command's result: its exit code and output, or the reason there is none."""

    def __init__(self, label, rc=None, out="", err="", failure=None):
        self.label = label
        self.rc = rc
        self.out = out
        self.err = err
        self.failure = failure


def seconds(value):
    return "%g" % round(value, 2)


def bin_dirs():
    """Where the read commands are looked up: the system directories, or exactly the directories
    HOST_CHECK_BIN_DIRS names when it is set and not empty. PATH is never searched."""
    given = os.environ.get(BIN_DIRS_VAR, "")
    if given:
        return [d for d in given.split(os.pathsep) if d]
    return list(SYSTEM_DIRS)


def resolve(name):
    dirs = bin_dirs()
    return shutil.which(name, path=os.pathsep.join(dirs)) if dirs else None


def signal_group(proc, number):
    """Send a signal to a child's whole process group (the child leads a session of its own), or
    to the child alone when the group is gone."""
    try:
        os.killpg(proc.pid, number)
    except OSError:
        try:
            proc.send_signal(number)
        except OSError:
            pass


def stop(proc, grace=0.0):
    """End a child and everything in its process group, then reap it for at most REAP_S. With a
    grace, SIGTERM comes first and the child has that long to end in its own way (the collector,
    as the caller's child, ends its in-flight read); SIGKILL follows either way."""
    if grace > 0 and proc.poll() is None:
        signal_group(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
    signal_group(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=REAP_S)
    except subprocess.TimeoutExpired:
        pass


def drain(proc, label, bound, grace):
    """Read a child's two streams in chunks until both close and it exits. It is stopped when
    the bound passes, when its output passes OUTPUT_CAP or when a stop signal arrives."""
    end = time.monotonic() + bound
    out_fd, err_fd = proc.stdout.fileno(), proc.stderr.fileno()
    taken = {out_fd: [], err_fd: []}
    held = 0
    with selectors.DefaultSelector() as waiting:
        for fd in taken:
            waiting.register(fd, selectors.EVENT_READ)
        while True:
            if _stopped:
                stop(proc, grace)
                return Read(label, failure="%s was stopped: %s" % (label, stop_text()))
            left = end - time.monotonic()
            if left <= 0:
                stop(proc, grace)
                return Read(label, failure="%s timed out after %s s" % (label, seconds(bound)))
            if not waiting.get_map():
                try:
                    rc = proc.wait(timeout=min(left, SLICE_S))
                except subprocess.TimeoutExpired:
                    continue
                break
            for key, _ in waiting.select(min(left, SLICE_S)):
                data = os.read(key.fd, CHUNK)
                if not data:
                    waiting.unregister(key.fd)
                    continue
                held += len(data)
                if held > OUTPUT_CAP:
                    stop(proc, grace)
                    return Read(label, failure="%s printed more than %s and was stopped"
                                % (label, CAP_TEXT))
                taken[key.fd].append(data)
    return Read(label, rc=rc, out=b"".join(taken[out_fd]).decode("utf-8", "replace"),
                err=b"".join(taken[err_fd]).decode("utf-8", "replace"))


def run_child(argv, label, bound, grace=0.0):
    """Run one command for at most `bound` seconds in a session of its own (see drain). Never
    raises for a command that is missing, fails, hangs or floods."""
    if _stopped:
        return Read(label, failure="%s not run: %s" % (label, stop_text()))
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
    except OSError as exc:
        return Read(label, failure="%s could not start (%s)"
                    % (label, exc.strerror or type(exc).__name__))
    try:
        return drain(proc, label, bound, grace)
    except Exception as exc:
        stop(proc, grace)
        return Read(label, failure="%s could not be read (%s)" % (label, type(exc).__name__))
    finally:
        for stream in (proc.stdout, proc.stderr):
            try:
                stream.close()
            except Exception:
                pass


def run_read(argv, label, deadline):
    """One read command within its own bound: READ_BOUND_S, or what is left of the total budget
    if that is less."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return Read(label, failure="%s not read: the collector's %s s total budget was spent"
                    % (label, seconds(TOTAL_BUDGET_S)))
    exe = resolve(argv[0])
    if exe is None:
        return Read(label, failure="%s not found in %s"
                    % (argv[0], ", ".join(bin_dirs()) or "no directory"))
    return run_child([exe] + list(argv[1:]), label, min(READ_BOUND_S, remaining))


def one_line(text):
    """Control characters (newlines included) become spaces, and runs of space collapse."""
    return " ".join("".join(ch if ch.isprintable() else " " for ch in text).split())


def quote(text, limit=100):
    """A value printed literally inside double quotes, on one line and at most `limit` long."""
    text = one_line(text)
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def first_line(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def last_line(text):
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""


# What `defaults read` says, with a non-zero exit, for a key or a domain it does not hold. macOS
# 27.0.1 prints "Error: Could not find key '<key>' in domain '<domain>'." and "Error: Domain
# '<domain>' not found." (both observed, 5 October 2026); the form older releases are recalled to
# print, "The domain/default pair of (<domain>, <key>) does not exist", is kept (not observed).
ABSENT = re.compile(r"does not exist|Could not find key|Domain .+ not found")


def absent(read):
    """`defaults read` of a key or a domain that is not there."""
    return (read.failure is None and read.rc not in (None, 0)
            and ABSENT.search(read.err) is not None)


def problem(read):
    """None when the read gave output to interpret; otherwise why not, as an unknown's detail."""
    if read.failure:
        return read.failure
    if read.rc != 0:
        tail = first_line(read.err)
        return "%s failed (exit %s%s)" % (read.label, read.rc,
                                           ": " + quote(tail, 80) if tail else "")
    if not read.out.strip():
        return "%s printed nothing" % read.label
    return None


# ------------------------------------------- the property-list text `defaults read` prints ---
_TOKEN = re.compile(r'([(){}=;,])|"((?:[^"\\]|\\.)*)"|([^\s(){}=;,"]+)', re.S)
_ESCAPE = re.compile(r'\\(?:[Uu]([0-9A-Fa-f]{4})|([0-7]{1,3})|(.))', re.S)
_SIMPLE = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def _unescape(text):
    def one(match):
        if match.group(1):
            return chr(int(match.group(1), 16))
        if match.group(2):
            return chr(int(match.group(2), 8))
        return _SIMPLE.get(match.group(3), match.group(3))
    return _ESCAPE.sub(one, text)


def _tokens(text):
    found, pos, end = [], 0, len(text)
    while True:
        while pos < end and text[pos].isspace():
            pos += 1
        if pos >= end:
            return found
        match = _TOKEN.match(text, pos)
        if match is None:
            raise ValueError("unreadable text at offset %d" % pos)
        if match.group(1) is not None:
            found.append(("mark", match.group(1)))
        elif match.group(2) is not None:
            found.append(("text", _unescape(match.group(2))))
        else:
            found.append(("text", match.group(3)))
        pos = match.end()


def _expect(tokens, at, mark):
    if at >= len(tokens) or tokens[at] != ("mark", mark):
        raise ValueError("expected '%s'" % mark)
    return at + 1


def _value(tokens, at):
    if at >= len(tokens):
        raise ValueError("the text ends inside a value")
    kind, item = tokens[at]
    if kind == "text":
        return item, at + 1
    if item == "(":
        items, at = [], at + 1
        while True:
            if at < len(tokens) and tokens[at] == ("mark", ")"):
                return items, at + 1
            value, at = _value(tokens, at)
            items.append(value)
            if at < len(tokens) and tokens[at] == ("mark", ","):
                at += 1
            else:
                return items, _expect(tokens, at, ")")
    if item == "{":
        table, at = {}, at + 1
        while True:
            if at < len(tokens) and tokens[at] == ("mark", "}"):
                return table, at + 1
            key, at = _value(tokens, at)
            if not isinstance(key, str):
                raise ValueError("a key that is not a string")
            at = _expect(tokens, at, "=")
            value, at = _value(tokens, at)
            at = _expect(tokens, at, ";")
            table[key] = value
    raise ValueError("unexpected '%s'" % item)


def parse_openstep(text):
    """The array, dictionary and string subset of the old-style property list `defaults read`
    prints; anything outside that subset is malformed (a ValueError)."""
    tokens = _tokens(text)
    if not tokens:
        raise ValueError("no value")
    value, at = _value(tokens, 0)
    if at != len(tokens):
        raise ValueError("text after the value")
    return value


# --------------------------------------------------------------------------- the facts ------
def fact_auto_install(deadline):
    key = "AutomaticallyInstallMacOSUpdates"
    read = run_read(["defaults", "read", DOMAIN, "AutomaticallyInstallMacOSUpdates"],
                    "defaults read " + key, deadline)
    if absent(read):
        return UNKNOWN, ("%s absent: the setting in force is not recorded in this domain"
                         % key)
    why = problem(read)
    if why:
        return UNKNOWN, why
    value = read.out.strip()
    if value == "0":
        # The read names the local preference file; a configuration profile is not read here.
        return OK, "%s 0 (the local setting; a configuration profile is not read)" % key
    if value == "1":
        return WARN, ("%s 1: an update may install and restart the Mac during the run" % key)
    return UNKNOWN, "%s has an unexpected value %s" % (key, quote(value, 60))


def entry_name(entry):
    if isinstance(entry, dict):
        for key in ("Display Name", "Identifier", "Product Key"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return quote(value) if key == "Display Name" else "%s %s" % (key, quote(value))
        return "an entry without a name"
    if isinstance(entry, str):
        return quote(entry)
    return "an entry of unexpected shape"


def cached_entries(read):
    if absent(read):
        return UNKNOWN, ("RecommendedUpdates absent (no cached list was found, or the domain "
                         "could not be read)")
    why = problem(read)
    if why:
        return UNKNOWN, why
    try:
        value = parse_openstep(read.out)
    except ValueError as exc:
        return UNKNOWN, "RecommendedUpdates malformed (%s): %s" % (exc, quote(read.out, 60))
    if not isinstance(value, list):
        return UNKNOWN, "RecommendedUpdates is not a list: %s" % quote(read.out, 60)
    if not value:
        return OK, "none cached (current availability stays unknown)"
    return WARN, "%d cached: %s" % (len(value), ", ".join(entry_name(e) for e in value))


def describe_date(read):
    """LastSuccessfulDate under its own name, and whether it was read as a well-formed date.
    Nothing here claims it dates the list."""
    if absent(read):
        return False, "LastSuccessfulDate absent"
    why = problem(read)
    if why:
        return False, "LastSuccessfulDate unread (%s)" % why
    value = read.out.strip()
    try:
        datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return False, "LastSuccessfulDate malformed: %s" % quote(value, 60)
    return True, "LastSuccessfulDate %s (relationship to the list unverified)" % value


def fact_cached(deadline):
    listing = run_read(["defaults", "read", DOMAIN, "RecommendedUpdates"],
                       "defaults read RecommendedUpdates", deadline)
    dated = run_read(["defaults", "read", DOMAIN, "LastSuccessfulDate"],
                     "defaults read LastSuccessfulDate", deadline)
    status, text = cached_entries(listing)
    dated_well, date_text = describe_date(dated)
    # The date has no status of its own, but no fact is ok after a failed, empty, malformed or
    # timed-out read (an absent key is a failed `defaults read`): an empty list beside an unread
    # date prints unknown. A known warning, a cached entry, still stands, as in fact 3.
    if status == OK and not dated_well:
        status = UNKNOWN
    return status, "%s; %s" % (text, date_text)


def power_source(read):
    why = problem(read)
    if why:
        return UNKNOWN, "power source unknown (%s)" % why
    match = re.search(r"Now drawing from '([^']*)'", read.out)
    if match is None:
        return UNKNOWN, ("power source unknown (no 'Now drawing from' in %s)"
                         % quote(read.out, 60))
    source = match.group(1)
    if source == "AC Power":
        return OK, "on AC power"
    level = re.search(r"(\d{1,3})%", read.out)
    extra = " (%s%%)" % level.group(1) if level else ""
    if source == "Battery Power":
        return WARN, "on battery power" + extra
    if source == "UPS Power":
        return WARN, "on UPS power" + extra
    return UNKNOWN, "power source unrecognised: %s" % quote(source, 60)


def ac_sleep(read):
    why = problem(read)
    if why:
        return UNKNOWN, "AC sleep unknown (%s)" % why
    section, seen_ac, values = None, False, []
    for line in read.out.splitlines():
        if not line.strip():
            continue
        if not line[0].isspace():
            section = line.strip()
            seen_ac = seen_ac or section == "AC Power:"
            continue
        if section == "AC Power:":
            match = re.match(r"\s*sleep\s+(\S+)", line)
            if match:
                values.append(match.group(1))
    if not seen_ac:
        return UNKNOWN, "AC sleep unknown (no AC Power profile in pmset -g custom)"
    if len(values) != 1:
        return UNKNOWN, ("AC sleep unknown (%d sleep values in the AC Power profile)"
                         % len(values))
    if not re.fullmatch(r"[0-9]+", values[0]):
        return UNKNOWN, "AC sleep unknown (value %s)" % quote(values[0], 40)
    minutes = int(values[0])
    if minutes == 0:
        return OK, "AC sleep 0"
    return WARN, "AC sleep %d min (the run freezes if the Mac sleeps)" % minutes


def fact_power(deadline):
    batt = run_read(["pmset", "-g", "batt"], "pmset -g batt", deadline)
    custom = run_read(["pmset", "-g", "custom"], "pmset -g custom", deadline)
    parts = [power_source(batt), ac_sleep(custom)]
    statuses = [status for status, _ in parts]
    # A known warning outranks a part that could not be read: both are not ok, and the warning
    # is the one the owner can act on; the unread part still shows in the detail.
    status = WARN if WARN in statuses else UNKNOWN if UNKNOWN in statuses else OK
    return status, "; ".join(text for _, text in parts)


SCHED_HEADERS = ("Scheduled power events:", "Repeating power events:")
# What pmset prints when no event is scheduled: the string sits among pmset's `-g` messages in
# /usr/bin/pmset (macOS 27.0.1). Its printing by `-g sched` was not observed.
SCHED_NONE = "No scheduled events."


def fact_sched(deadline):
    read = run_read(["pmset", "-g", "sched"], "pmset -g sched", deadline)
    # An empty listing is an empty read and prints unknown like any other: it cannot be told
    # from a lookup that failed quietly, and pmset has its own words for none (SCHED_NONE).
    why = problem(read)
    if why:
        return UNKNOWN, why
    entries, header = [], None
    for line in read.out.splitlines():
        text = one_line(line)
        if not text or text == SCHED_NONE:
            continue
        if text in SCHED_HEADERS:
            header = text
            continue
        if header is None:
            return UNKNOWN, ("pmset -g sched printed an unrecognised listing: %s"
                             % quote(read.out, 80))
        entries.append(("repeating " + text) if header == SCHED_HEADERS[1] else text)
    if not entries:
        return OK, "none listed by pmset -g sched"
    return WARN, "%d listed: %s" % (len(entries), "; ".join(entries))


def fact_lid(deadline):
    read = run_read(["ioreg", "-r", "-c", "IOPMrootDomain", "-d", "1"],
                    "ioreg -c IOPMrootDomain", deadline)
    why = problem(read)
    if why:
        return UNKNOWN, why
    values = sorted(set(re.findall(r'^\s*"AppleClamshellState"\s*=\s*(\S+)\s*$',
                                   read.out, re.M)))
    if not values:
        return UNKNOWN, ("no AppleClamshellState in the ioreg reading (a Mac without a lid "
                         "reports none)")
    if len(values) > 1:
        return UNKNOWN, "conflicting AppleClamshellState values %s" % ", ".join(values)
    if values[0] == "No":
        return OK, "open (AppleClamshellState No)"
    if values[0] == "Yes":
        return WARN, "closed (AppleClamshellState Yes)"
    return UNKNOWN, "AppleClamshellState has an unexpected value %s" % quote(values[0], 40)


FACTS = (
    ("automatic macOS install", fact_auto_install),
    ("cached recommended entries", fact_cached),
    ("power and idle sleep", fact_power),
    ("scheduled wakes", fact_sched),
    (LID_FACT, fact_lid),
)


# -------------------------------------------------------------------------- the output -----
def now():
    return time.strftime("%H:%M:%S")


def line_text(stamp, fact, status, detail):
    return "host %s · %s · %s · %s" % (stamp, fact, status, one_line(detail) or "no detail")


def write_line(text):
    """Print one line. A closed or broken standard output ends the run at once with exit 0:
    there is no one left to tell, and the exit code must not suggest a finding."""
    try:
        sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
        sys.stdout.buffer.flush()
    except Exception:
        os._exit(0)


def emit(stamp, fact, status, detail):
    write_line(line_text(stamp, fact, status, detail))


def collect(write):
    deadline = time.monotonic() + TOTAL_BUDGET_S
    on_mac = sys.platform == "darwin"
    for name, reader in FACTS:
        if _stopped:
            write(now(), "collector", UNKNOWN, "stopped: %s before %s was read"
                  % (stop_text(), name))
            return
        stamp = now()
        if not on_mac:
            status, detail = UNKNOWN, ("unsupported platform %s: no macOS command was run"
                                       % sys.platform)
        else:
            try:
                status, detail = reader(deadline)
            except Exception as exc:
                status, detail = UNKNOWN, ("internal error reading this fact (%s)"
                                           % type(exc).__name__)
        write(stamp, name, status, detail)
        if name == LID_FACT:
            write(stamp, LATER_LID_FACT, UNKNOWN, LATER_LID_TEXT)


# -------------------------------------------------------------------------- the caller -----
LINE = re.compile(r"^host \d{2}:\d{2}:\d{2} · [^·]+? · (?:ok|warn|unknown) · \S.*$")


def well_formed(row):
    return LINE.match(row) is not None and one_line(row) == row


def call_collector(path):
    """The caller contract of the design as code: the collector at `path` run as a child with a
    total deadline of CALLER_DEADLINE_S. Its lines come back unchanged; a missing collector, a
    non-zero exit, a run past the deadline or unparseable output each comes back instead as the
    one line `collector · unknown · <reason>`. When this file itself is missing nothing here
    runs, and the head writes that line (the delegate skill's pre-flight sentence)."""
    def instead(reason):
        return [line_text(now(), "collector", UNKNOWN, reason)]
    if not os.path.isfile(path):
        return instead("collector missing: no file at %s" % path)
    python = sys.executable or resolve("python3")
    if not python:
        return instead("collector not run: no Python interpreter was found")
    read = run_child([python, path], "collector", CALLER_DEADLINE_S, grace=REAP_S)
    if read.failure:
        return instead(read.failure)
    if read.rc < 0:
        return instead("collector ended by %s" % signal_name(-read.rc))
    if read.rc != 0:
        tail = last_line(read.err)
        return instead("collector exited %d%s" % (read.rc, ": " + quote(tail, 80) if tail else ""))
    rows = [row for row in read.out.splitlines() if row.strip()]
    if not rows:
        return instead("unparseable output (nothing printed)")
    bad = [row for row in rows if not well_formed(row)]
    if bad:
        return instead("unparseable output (%d of %d lines, first: %s)"
                       % (len(bad), len(rows), quote(bad[0], 80)))
    return rows


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    install_stop_handlers()
    try:
        if not args:
            collect(emit)
        elif args[0] == "--caller" and len(args) <= 2:
            for row in call_collector(args[1] if len(args) == 2
                                      else os.path.abspath(__file__)):
                write_line(row)
        else:
            emit(now(), "collector", UNKNOWN, "unrecognised arguments %s: run with no argument, "
                 "or with --caller" % quote(" ".join(args), 60))
    except Exception as exc:
        emit(now(), "collector", UNKNOWN, "internal error (%s)" % type(exc).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
