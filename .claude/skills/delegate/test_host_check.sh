#!/bin/sh
# test_host_check.sh: the suite for host_check.py (delegate skill: the host check, shape C).
#
# Run:  sh test_host_check.sh                          (from beside host_check.py)
#       HOST_CHECK=<path to host_check.py> sh test_host_check.sh
#
# Every leg runs host_check.py with HOST_CHECK_BIN_DIRS naming a directory of stub `defaults`,
# `pmset` and `ioreg`, which the collector then searches instead of the system directories; each
# stub logs its argv and plays the scenario the leg planted, so no leg reads the real host. The
# collector under test is a read-only copy in a fresh directory under /tmp (never TMPDIR, which
# on this platform points at a per-user root outside the temp directory a lane is granted),
# removed on exit; HOST_CHECK_KEEP=1 keeps it for a post-mortem.
#
# One premise is read from the real system: before the legs, the real `defaults` is asked for a
# key missing from a property list the suite writes in its temp directory, and for a domain that
# does not exist there, and its two replies are planted verbatim in the absent-key legs, so that
# fixture cannot drift from what the command prints (a key the list holds is the control). If
# that capture fails, the suite stops with PROBE FAILED.
#
# The legs follow the design's "Tests that define done": each fact in each state, a stub that
# hangs, the caller cases run through the shipped caller (host_check.py --caller, the 20 s
# deadline the head runs), a planted clean host and a planted warning host; with legs for the
# output cap, the command lookup, stop signals and the stated limit on session-escaping
# grandchildren. The live run on a Mac is not a leg: it reads the real host and is compared with
# the values read directly in the same minute.
#
# Every clean result carries its positive control on the same run (each per-state leg changes
# one fact of the clean host and asserts the other facts still read ok), and the last legs prove
# that nothing was written: a checksum manifest of host_check.py, this suite and the read-only
# copy, taken before the legs and after them, with a check that no host_check byte-code appeared
# beside the collector (both with planted controls); the argv log of every stub call (only the
# seven reads, with a planted setter as control); a source scan of host_check.py for
# file-writing and process-starting calls (with a planted writer as control); and a scan of this
# file for a write verb aimed at an absolute path outside /tmp (with a planted control).
#
# The last line is PASS n/n or FAIL k/n (k legs failed of n); the exit code is 0 only when every
# leg passed, and 2 with one PROBE FAILED line when a premise of the suite is broken.
set -u

PY=${PYTHON:-python3}
SRC=$0
H0=${HOST_CHECK:-$(dirname "$SRC")/host_check.py}
DOMAIN=/Library/Preferences/com.apple.SoftwareUpdate

die() { printf 'PROBE FAILED: %s\n' "$1" >&2; exit 2; }

command -v "$PY" >/dev/null || die "no $PY on PATH"
[ -f "$SRC" ] || die "cannot read this suite's own source at $SRC (run it as: sh <path>)"
[ -f "$H0" ] || die "no host_check.py at $H0 (pass HOST_CHECK=<path>)"
SRC_DIR=$(cd "$(dirname "$H0")" && pwd) || die "cannot resolve the directory of $H0"

WORK=$(mktemp -d /tmp/host-check-suite.XXXXXX) || die "cannot make a temp directory under /tmp"
case $WORK in
  /tmp/*|/private/tmp/*) : ;;
  *) die "the temp directory $WORK is not under /tmp" ;;
esac
cleanup() {
  [ -d "$WORK/ro" ] && chmod u+w "$WORK/ro"
  [ "${HOST_CHECK_KEEP:-0}" = "1" ] || rm -rf "$WORK"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# The target must compile before anything is claimed about it; the byte-code goes to the temp
# directory, because py_compile ignores -B and the skill directory takes no __pycache__.
"$PY" -c 'import py_compile, sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)' \
      "$H0" "$WORK/host_check.pyc" || die "host_check.py does not compile"

TOOL="$WORK/tool.py"
FX="$WORK/fx"
mkdir "$WORK/bin" "$WORK/scn" "$FX" "$WORK/fake" "$WORK/ro" "$WORK/cap" "$WORK/decoy" \
  || die "cannot lay out $WORK"

# ------------------------------------------------------------------ the oracle toolkit -----
cat > "$TOOL" <<'TOOLPY'
#!/usr/bin/env python3
"""The independent oracle for test_host_check.sh. The line format, the fact names and the
fixed lid text are written here from the design, not imported from host_check.py, so a leg that
passes agrees with the design rather than with the code under test. It prints only, except
three commands that write, each only under /tmp, where the suite's temp directory is: plant (the
planted controls), plist (the capture's property list) and spawn (a run's two streams)."""
import hashlib
import os
import re
import sys
import time

LINE = re.compile(r"^host (\d{2}):(\d{2}):(\d{2}) · ([^·]+?) · (ok|warn|unknown) · (\S.*)$")
FACTS = ["automatic macOS install", "cached recommended entries", "power and idle sleep",
         "scheduled wakes", "lid", "later lid closure"]
FIXED = "this check cannot predict a later lid closure; keep the lid open"
TMP = ("/tmp/", "/private/tmp/")


def out(text):
    sys.stdout.write(str(text) + "\n")


def refuse_outside_tmp(*paths):
    for path in paths:
        if not path.startswith(TMP):
            out("refused: %s is not under /tmp" % path)
            sys.exit(2)


def lines_of(path):
    with open(path, "r", encoding="utf-8", errors="strict") as handle:
        text = handle.read()
    rows = text.split("\n")
    if rows and rows[-1] == "":
        rows.pop()
    return rows


def parse(line):
    m = LINE.match(line)
    if not m:
        return None
    hh, mm, ss = (int(m.group(i)) for i in (1, 2, 3))
    if hh > 23 or mm > 59 or ss > 59:
        return None
    return m.group(4), m.group(5), m.group(6)


def cmd_format(argv):
    """Every line is a host line; at least one line."""
    try:
        rows = lines_of(argv[0])
    except (OSError, UnicodeDecodeError) as exc:
        out("unreadable output (%s)" % type(exc).__name__)
        return
    if not rows:
        out("no lines")
        return
    for i, row in enumerate(rows, 1):
        if parse(row) is None:
            out("line %d is not a host line: %r" % (i, row[:100]))
            return
    out("ok")


def cmd_shape(argv):
    """A collector's whole output: six host lines, the five facts in the design's order, then
    the fixed lid line as an unknown."""
    try:
        rows = lines_of(argv[0])
    except (OSError, UnicodeDecodeError) as exc:
        out("unreadable output (%s)" % type(exc).__name__)
        return
    parsed = [parse(r) for r in rows]
    for i, p in enumerate(parsed, 1):
        if p is None:
            out("line %d is not a host line: %r" % (i, rows[i - 1][:100]))
            return
    facts = [p[0] for p in parsed]
    if facts != FACTS:
        out("facts %r, wanted %r" % (facts, FACTS))
        return
    if parsed[-1][1:] != ("unknown", FIXED):
        out("the line after the lid reads %r" % (parsed[-1][1:],))
        return
    out("ok")


def cmd_want(argv):
    """want OUT FACT STATUS [SUBSTRING | !ABSENT-SUBSTRING]...: 'ok' or every mismatch."""
    path, fact, status, subs = argv[0], argv[1], argv[2], argv[3:]
    rows = [parse(r) for r in lines_of(path)]
    hits = [r for r in rows if r is not None and r[0] == fact]
    if len(hits) != 1:
        out("%s: %d lines, wanted 1" % (fact, len(hits)))
        return
    _, got, detail = hits[0]
    bad = []
    if got != status:
        bad.append("%s: status %s, wanted %s (detail: %s)" % (fact, got, status, detail))
    for s in subs:
        if s.startswith("!"):
            if s[1:] in detail:
                bad.append("%s: detail carries %r: %s" % (fact, s[1:], detail))
        elif s not in detail:
            bad.append("%s: detail lacks %r: %s" % (fact, s, detail))
    out("; ".join(bad) or "ok")


def cmd_count(argv):
    """count OUT STATUS: how many lines carry that status."""
    rows = [parse(r) for r in lines_of(argv[0])]
    out(sum(1 for r in rows if r is not None and r[1] == argv[1]))


def cmd_clock(argv):
    out("%.3f" % time.time())


def cmd_within(argv):
    """within T0 T1 LO HI [UNIT]: 'ok' when LO <= T1 - T0 <= HI, else the span in UNIT (s)."""
    unit = argv[4] if len(argv) > 4 else "s"
    try:
        t0, t1, lo, hi = (float(v) for v in argv[:4])
    except ValueError:
        out("not a number among %r" % (argv,))
        return
    span = t1 - t0
    out("ok" if lo <= span <= hi else "%.2f %s, outside [%g, %g]" % (span, unit, lo, hi))


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_pids(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [int(t) for t in handle.read().split()]


def cmd_alive(argv):
    """alive PIDFILE: the listed pids still running after up to 3 s of grace, or 'none'; and
    the count listed, so an empty file cannot pass as a clean result."""
    pids = read_pids(argv[0])
    end = time.time() + 3
    live = [p for p in pids if alive(p)]
    while live and time.time() < end:
        time.sleep(0.1)
        live = [p for p in pids if alive(p)]
    out("listed %d live %s" % (len(pids), " ".join(map(str, live)) or "none"))


def cmd_living(argv):
    """living PIDFILE: the listed pids running at this moment, with no grace."""
    pids = read_pids(argv[0])
    live = [p for p in pids if alive(p)]
    out("listed %d live %s" % (len(pids), " ".join(map(str, live)) or "none"))


def cmd_reap(argv):
    """reap PIDFILE: SIGKILL each listed pid still running (a leftover the suite planted)."""
    import signal
    pids = read_pids(argv[0])
    killed = 0
    for pid in pids:
        if alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
                killed += 1
            except OSError:
                pass
    out("killed %d of %d" % (killed, len(pids)))


def cmd_spawn(argv):
    """spawn OUT ERR LIMIT WAITFILE SIGNAL CMD...: run CMD with its two streams written to OUT
    and ERR. When WAITFILE is not '-', wait up to 10 s for it to hold something, then send CMD
    the signal SIGNAL names. CMD then has LIMIT seconds (from the signal, or from its start) to
    end before it is killed. Prints 'rc N after S s peak B': S counted from the signal or the
    start, B the peak resident bytes of what ran; or why there is no such report."""
    import resource
    import signal
    import subprocess
    out_path, err_path, limit, waitfile, signame = argv[:5]
    refuse_outside_tmp(out_path, err_path)

    def filled():
        return os.path.exists(waitfile) and os.path.getsize(waitfile) > 0

    with open(out_path, "wb") as so, open(err_path, "wb") as se:
        proc = subprocess.Popen(argv[5:], stdin=subprocess.DEVNULL, stdout=so, stderr=se)
    mark = time.time()
    if waitfile != "-":
        end = mark + 10
        while time.time() < end and proc.poll() is None and not filled():
            time.sleep(0.02)
        if not filled():
            proc.kill()
            proc.wait()
            out("the wait file never filled")
            return
        mark = time.time()
        proc.send_signal(getattr(signal, signame))
    try:
        rc = proc.wait(timeout=float(limit))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        out("did not end within %s s" % limit)
        return
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    out("rc %d after %.2f s peak %d" % (rc, time.time() - mark, peak))


def cmd_plist(argv):
    """plist PATH: a property list holding PresentKey = fixture-value, written under /tmp."""
    import plistlib
    refuse_outside_tmp(argv[0])
    with open(argv[0], "wb") as handle:
        plistlib.dump({"PresentKey": "fixture-value"}, handle)
    out("written")


def cmd_pycache(argv):
    """pycache DIR: the host_check byte-code under DIR/__pycache__, or 'absent'."""
    cache = os.path.join(argv[0], "__pycache__")
    if not os.path.isdir(cache):
        out("absent")
        return
    names = sorted(n for n in os.listdir(cache) if n.startswith("host_check"))
    out("entries %d %s" % (len(names), " ".join(names)))


def cmd_manifest(argv):
    """sha256, size and path of each file given, and of every file under each directory given."""
    def digest(full):
        try:
            with open(full, "rb") as handle:
                value = hashlib.sha256(handle.read()).hexdigest()
            size = os.path.getsize(full)
        except OSError as exc:
            value, size = "unreadable", str(exc)
        out("%s %s %s" % (value, size, full))
    for root in argv:
        if os.path.isfile(root):
            digest(root)
            continue
        for base, dirs, files in os.walk(root):
            dirs.sort()
            for name in sorted(files):
                digest(os.path.join(base, name))


def cmd_argv(argv):
    """argv LOG DOMAIN: every stub call must be one of the seven reads."""
    log, domain = argv
    allowed = {"defaults read %s %s" % (domain, k) for k in
               ("AutomaticallyInstallMacOSUpdates", "RecommendedUpdates", "LastSuccessfulDate")}
    allowed |= {"pmset -g batt", "pmset -g custom", "pmset -g sched",
                "ioreg -r -c IOPMrootDomain -d 1"}
    calls = lines_of(log) if os.path.exists(log) else []
    bad = [c for c in calls if c not in allowed]
    out("calls %d bad %d" % (len(calls), len(bad)))
    for b in bad[:5]:
        out("bad: %s" % b)


# Matched against the code with every string literal and comment blanked, so a detail text such
# as "open (…)" or a docstring that names a call is not read as the call.
CODE_PATTERNS = [
    ("built-in open", r"(?<![\w.])open\s*\("),
    ("low-level file call", r"\b(?:io\.open|os\.open|os\.fdopen|os\.write|os\.pwrite)\b"),
    ("file-changing os call", r"\bos\.(?:remove|unlink|rename|renames|replace|rmdir|removedirs"
                              r"|mkdir|makedirs|symlink|link|chmod|lchmod|chown|lchown|truncate"
                              r"|ftruncate|utime|mkfifo|mknod|chflags|setxattr|removexattr)\b"),
    ("shutil other than which", r"\bshutil\.(?!which\b)\w+"),
    ("pathlib write", r"\.(?:write_text|write_bytes|touch|symlink_to|hardlink_to)\s*\("),
    ("file-writing module", r"^\s*(?:import|from)\s+(?:tempfile|pathlib|sqlite3|shelve|dbm"
                            r"|pickle|logging|zipfile|tarfile)\b"),
    ("process start other than Popen", r"\b(?:os\.system|os\.popen|os\.exec\w*|os\.spawn\w*"
                                       r"|os\.posix_spawn\w*|subprocess\.(?:run|call|check_call"
                                       r"|check_output|getoutput|getstatusoutput))\b"),
]
# Matched against the raw text: these are about the string arguments themselves.
TEXT_PATTERNS = [
    ("command argv other than a read", r"""\[\s*["'](?:defaults|pmset|ioreg)["']\s*,\s*"""
                                       r"""["'](?!read["']|-g["']|-r["'])"""),
    ("host-changing command", r"""["'](?:softwareupdate|sudo|launchctl|caffeinate|osascript"""
                              r"""|systemsetup|shutdown|reboot|kill|killall)["']"""),
]
ARGV_LIST = re.compile(r"""\[\s*["'](?:defaults|pmset|ioreg)["']\s*,""")


def blanked_lines(source):
    """The source's lines with every string literal and comment replaced by spaces."""
    import io
    import tokenize
    rows = [list(r) for r in source.split("\n")]
    blank = {tokenize.STRING, tokenize.COMMENT}
    for name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
        if hasattr(tokenize, name):
            blank.add(getattr(tokenize, name))
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type not in blank:
            continue
        (sr, sc), (er, ec) = tok.start, tok.end
        for r in range(sr, er + 1):
            row = rows[r - 1]
            for c in range(sc if r == sr else 0, ec if r == er else len(row)):
                row[c] = " "
    return ["".join(r) for r in rows]


def cmd_scanpy(argv):
    """Each write or process pattern on each line of a Python source is a hit; the collector
    must score zero, and the planted writer one hit per planted line. Also counts the Popen call
    sites and the command argv lists, so a scan of the wrong file cannot pass."""
    with open(argv[0], "r", encoding="utf-8", errors="replace") as handle:
        source = handle.read()
    try:
        code = blanked_lines(source)
    except Exception as exc:
        out("hits untokenisable (%s)" % type(exc).__name__)
        return
    hits, popen, lists = 0, 0, 0
    for i, (raw, bare) in enumerate(zip(source.split("\n"), code), 1):
        popen += len(re.findall(r"\bsubprocess\.Popen\s*\(", bare))
        lists += len(ARGV_LIST.findall(raw))
        for patterns, text in ((CODE_PATTERNS, bare), (TEXT_PATTERNS, raw)):
            for name, pattern in patterns:
                if re.search(pattern, text, re.M):
                    hits += 1
                    out("hit line %d (%s): %s" % (i, name, raw.strip()[:100]))
    out("popen %d argv-lists %d" % (popen, lists))
    out("hits %d" % hits)


ALLOWED = ("/tmp", "/private/tmp", "/dev/null", "/dev/stdout", "/dev/stderr")
VERB = re.compile(r"(?:(?<![0-9&])>>?|\b(?:cp|mv|rm|tee|touch|mkdir|install|truncate|dd|ln"
                  r"|chmod|chown)\b|sed\s+-i)")
ABS = re.compile(r"(?:^|[\s\"'=(:,])(/[A-Za-z0-9_.@%+-][^\s\"';|)]*)")


def cmd_scansh(argv):
    """Every line carrying a write verb is checked for an absolute path outside the temp root."""
    hits = 0
    with open(argv[0], "r", encoding="utf-8", errors="replace") as handle:
        for i, line in enumerate(handle, 1):
            text = line.rstrip("\n")
            if not VERB.search(text):
                continue
            for m in ABS.finditer(text):
                if m.group(1).startswith(ALLOWED):
                    continue
                hits += 1
                out("hit line %d: %s" % (i, text.strip()[:100]))
    out("hits %d" % hits)


def cmd_plant(argv):
    """plant WORKDIR: the two planted controls, each written only under WORKDIR. The absolute
    paths in the shell control are assembled here, so this source names none."""
    work = argv[0]
    refuse_outside_tmp(work + "/")
    root = "/"
    with open(os.path.join(work, "planted-writer.sh"), "w", encoding="utf-8") as handle:
        handle.write("cp a %s\n" % (root + "opt/planted/target"))
        handle.write("printf x > %s\n" % (root + "var/planted/file"))
        handle.write("printf x > \"$WORK/inside\"\n")
    py = [
        'fh = open("x", "w")',
        'os.remove(path)',
        'shutil.rmtree(folder)',
        'Path(path).write_text(text)',
        'import tempfile',
        'os.system(command)',
        'argv = ["pmset", "-a", "sleep", "0"]',
        'argv = ["defaults", "write", DOMAIN, "Key", "0"]',
        'argv = ["softwareupdate", "--install"]',
        'os.write(fd, data)',
        'detail = "open (a string that names a call is not the call)"',
    ]
    with open(os.path.join(work, "planted-writer.py"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(py) + "\n")
    out("planted sh 2 py %d" % len(py))


COMMANDS = {"format": cmd_format, "shape": cmd_shape, "want": cmd_want, "count": cmd_count,
            "clock": cmd_clock, "within": cmd_within, "alive": cmd_alive, "living": cmd_living,
            "reap": cmd_reap, "spawn": cmd_spawn, "plist": cmd_plist, "pycache": cmd_pycache,
            "manifest": cmd_manifest, "argv": cmd_argv, "scanpy": cmd_scanpy,
            "scansh": cmd_scansh, "plant": cmd_plant}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.stderr.write("tool.py: unknown command %r\n" % (sys.argv[1:2],))
        sys.exit(2)
    COMMANDS[sys.argv[1]](sys.argv[2:])
TOOLPY

tool() { "$PY" -B "$TOOL" "$@"; }

# ------------------------------------------- what the real `defaults` says for a missing key ---
DEF=""
for d in /usr/bin /bin /usr/sbin /sbin; do
  if [ -x "$d/defaults" ]; then DEF="$d/defaults"; break; fi
done
[ -n "$DEF" ] || die "no defaults command in the system directories (the absent-key replies are captured from it)"
CAP="$WORK/cap"
[ "$(tool plist "$CAP/held.plist")" = "written" ] || die "cannot write the capture's property list"
# capture NAME DOMAIN KEY: the real `defaults read` of KEY in DOMAIN (a path under $CAP), its
# streams kept as $CAP/NAME.out and $CAP/NAME.err; prints its exit code.
capture() {
  tool spawn "$CAP/$1.out" "$CAP/$1.err" 10 - - "$DEF" read "$CAP/$2" "$3" \
    | sed -n 's/^rc \([0-9-]*\) after .*/\1/p'
}
[ "$(capture held held PresentKey)" = "0" ] && [ "$(cat "$CAP/held.out")" = "fixture-value" ] \
  || die "the real defaults did not read a key the capture's list holds: $(head -c 200 "$CAP/held.err")"
[ "$(capture key held NoSuchKeyForThisSuite)" = "1" ] && [ -s "$CAP/key.err" ] && [ ! -s "$CAP/key.out" ] \
  || die "the real defaults gave no exit-1 reply on stderr alone for a missing key"
[ "$(capture domain no-such-domain NoSuchKeyForThisSuite)" = "1" ] && [ -s "$CAP/domain.err" ] \
  && [ ! -s "$CAP/domain.out" ] \
  || die "the real defaults gave no exit-1 reply on stderr alone for a missing domain"
printf '# captured from %s, missing key: %s\n' "$DEF" "$(head -1 "$CAP/key.err")"
printf '# captured from %s, missing domain: %s\n' "$DEF" "$(head -1 "$CAP/domain.err")"

# --------------------------------------------------------------------------- the stubs -----
# One stub for all three commands: it logs its argv, then plays the files the leg planted for
# its key under $STUB_SCN: <key>.out to stdout, <key>.err to stderr, <key>.rc as the exit code;
# <key>.hang to hang (a child `sleep 60` holding the pipe; the collector's pid goes to
# hung.ppids, then the stub's and the child's to hung.pids); <key>.flood to print without end
# (on stderr when the file says so; the stub's pid to flood.pids); and <key>.orphan to leave a
# grandchild in a session of its own holding the pipe for 8 s (its pid to orphan.pids).
cat > "$WORK/bin/stub" <<'STUB'
#!/bin/sh
name=${0##*/}
case $name in
  defaults) key="defaults-${3:-}" ;;
  pmset) key="pmset-${2:-}" ;;
  *) key=$name ;;
esac
printf '%s\n' "$name $*" >> "$STUB_LOG"
f="$STUB_SCN/$key"
if [ -f "$f.hang" ]; then
  printf '%s\n' "$PPID" >> "$STUB_SCN/hung.ppids"
  sleep 60 &
  printf '%s %s\n' "$$" "$!" >> "$STUB_SCN/hung.pids"
  wait
fi
if [ -f "$f.flood" ]; then
  printf '%s\n' "$$" >> "$STUB_SCN/flood.pids"
  [ "$(cat "$f.flood")" = "stderr" ] && exec yes host-check-flood >&2
  exec yes host-check-flood
fi
if [ -f "$f.orphan" ]; then
  "$STUB_PY" -c 'import os, time; os.setsid(); time.sleep(8)' &
  printf '%s\n' "$!" >> "$STUB_SCN/orphan.pids"
  exit 0
fi
[ -f "$f.out" ] && cat "$f.out"
[ -f "$f.err" ] && cat "$f.err" >&2
rc=0
[ -f "$f.rc" ] && rc=$(cat "$f.rc")
exit "$rc"
STUB
for c in defaults pmset ioreg; do
  cp "$WORK/bin/stub" "$WORK/bin/$c" || die "cannot place the $c stub"
  chmod 0755 "$WORK/bin/$c" || die "cannot make the $c stub executable"
done
# A decoy `defaults` for the lookup leg: first on PATH there, it must never be the one found.
cp "$WORK/bin/stub" "$WORK/decoy/defaults" || die "cannot place the decoy"
chmod 0755 "$WORK/decoy/defaults" || die "cannot make the decoy executable"
STUB_LOG="$WORK/stub.log"
STUB_SCN="$WORK/scn"
STUB_PY=$PY
HOST_CHECK_BIN_DIRS="$WORK/bin"
export STUB_LOG STUB_SCN STUB_PY HOST_CHECK_BIN_DIRS
export PYTHONDONTWRITEBYTECODE=1

# ------------------------------------------------------------------------ the fixtures -----
# Shapes copied from the real commands' output on a Mac; names, ids and times are synthetic.
cat > "$FX/batt-ac" <<'EOF1'
Now drawing from 'AC Power'
 -InternalBattery-0 (id=1234567)	80%; AC attached; not charging present: true
EOF1
cat > "$FX/batt-battery" <<'EOF1'
Now drawing from 'Battery Power'
 -InternalBattery-0 (id=1234567)	80%; discharging; 5:12 remaining present: true
EOF1
cat > "$FX/batt-ups" <<'EOF1'
Now drawing from 'UPS Power'
 -InternalBattery-0 (id=1234567)	80%; AC attached; not charging present: true
EOF1
cat > "$FX/batt-odd" <<'EOF1'
Now drawing from 'Fixture Power'
EOF1
# The AC profile sleeps 0 and the battery profile 10: a parser reading the wrong profile warns.
cat > "$FX/custom-ac0" <<'EOF1'
Battery Power:
 Sleep On Power Button 1
 lowpowermode         0
 standby              1
 hibernatemode        3
 displaysleep         20
 sleep                10
 disksleep            10
AC Power:
 Sleep On Power Button 1
 lowpowermode         0
 standby              1
 hibernatemode        3
 displaysleep         30
 womp                 1
 sleep                0
 disksleep            10
EOF1
# And the reverse: AC 10, battery 0.
cat > "$FX/custom-ac10" <<'EOF1'
Battery Power:
 Sleep On Power Button 1
 displaysleep         20
 sleep                0
 disksleep            10
AC Power:
 Sleep On Power Button 1
 displaysleep         30
 sleep                10
 disksleep            10
EOF1
cat > "$FX/custom-noac" <<'EOF1'
Battery Power:
 Sleep On Power Button 1
 displaysleep         20
 sleep                0
EOF1
cat > "$FX/custom-word" <<'EOF1'
AC Power:
 displaysleep         30
 sleep                never
EOF1
cat > "$FX/sched-two" <<'EOF1'
Scheduled power events:
 [0]  wake at 10/05/2026 20:35:48 by 'FixtureAgent'
 [1]  shutdown at 10/06/2026 03:00:00 by 'FixtureAgent'
EOF1
cat > "$FX/sched-header" <<'EOF1'
Scheduled power events:
EOF1
cat > "$FX/sched-repeat" <<'EOF1'
Repeating power events:
  wakepoweron at 8:00AM weekdays only
No scheduled events.
EOF1
cat > "$FX/sched-odd" <<'EOF1'
something pmset never prints
 [0]  wake at 10/05/2026 20:35:48 by 'FixtureAgent'
EOF1
cat > "$FX/rec-empty" <<'EOF1'
(
)
EOF1
# Three entries: an ordinary update, a name with an escaped quote and a \U escape, and a major
# upgrade with no display name (it must still count as a cached entry).
cat > "$FX/rec-three" <<'EOF1'
(
        {
        "Display Name" = "macOS Fixture 26.0.1";
        "Display Version" = "26.0.1";
        Identifier = "MSU_UPDATE_FIXTURE_26.0.1";
        MobileSoftwareUpdate = 1;
        "Product Key" = "MSU_UPDATE_FIXTURE_26.0.1";
    },
        {
        "Display Name" = "Caf\U00e9 \"Pro\" Tools";
        "Display Version" = "2.1";
        Identifier = "com.example.cafe";
        "Product Key" = "001-00001";
    },
        {
        Identifier = "MSU_MAJOR_FIXTURE_27";
        MobileSoftwareUpdate = 1;
        "Product Key" = "MSU_MAJOR_FIXTURE_27";
    }
)
EOF1
cat > "$FX/rec-broken" <<'EOF1'
(
        {
        "Display Name" = "macOS Fixture 26.0.1";
        "Display Version" = "26.0.1"
EOF1
cat > "$FX/ioreg-open" <<'EOF1'
+-o IOPMrootDomain  <class IOPMrootDomain, id 0x100000100, registered, matched, active, busy 0 (1 ms), retain 100>
    {
      "IOSleepSupported" = Yes
      "AppleClamshellCausesSleep" = Yes
      "AppleClamshellState" = No
      "SleepWakeUUID" = "00000000-0000-0000-0000-000000000000"
    }
EOF1
cat > "$FX/ioreg-closed" <<'EOF1'
+-o IOPMrootDomain  <class IOPMrootDomain, id 0x100000100, registered, matched, active, busy 0 (1 ms), retain 100>
    {
      "AppleClamshellCausesSleep" = No
      "AppleClamshellState" = Yes
    }
EOF1
cat > "$FX/ioreg-nokey" <<'EOF1'
+-o IOPMrootDomain  <class IOPMrootDomain, id 0x100000100, registered, matched, active, busy 0 (1 ms), retain 100>
    {
      "IOSleepSupported" = Yes
    }
EOF1
cat > "$FX/ioreg-odd" <<'EOF1'
+-o IOPMrootDomain  <class IOPMrootDomain, id 0x100000100, registered, matched, active, busy 0 (1 ms), retain 100>
    {
      "AppleClamshellState" = Maybe
    }
EOF1

# The reply older releases of `defaults read` are recalled to give for a key the domain does not
# hold (not observed here); the current replies are the captured ones in $CAP.
absent_msg() { printf '\nThe domain/default pair of (%s, %s) does not exist' "$DOMAIN" "$1"; }

# ------------------------------------------------------ fake collectors for the caller -----
cat > "$WORK/fake/exit3.py" <<'FAKE'
import sys
print("host 01:02:03 · lid · ok · open (AppleClamshellState No)")
sys.stderr.write("fake collector: a fault after one line\n")
sys.exit(3)
FAKE
cat > "$WORK/fake/killself.py" <<'FAKE'
import os
import signal
print("host 01:02:03 · lid · ok · open (AppleClamshellState No)", flush=True)
os.kill(os.getpid(), signal.SIGKILL)
FAKE
cat > "$WORK/fake/hang.py" <<'FAKE'
import os
import subprocess
import time
child = subprocess.Popen(["sleep", "60"])
with open(os.environ["FAKE_PIDS"], "a") as handle:
    handle.write("%d %d\n" % (os.getpid(), child.pid))
time.sleep(60)
FAKE
cat > "$WORK/fake/garbage.py" <<'FAKE'
print("host 01:02:03 · lid · ok · open (AppleClamshellState No)")
print("Traceback (most recent call last): not a host line")
FAKE
cat > "$WORK/fake/silent.py" <<'FAKE'
pass
FAKE
cat > "$WORK/fake/ctrl.py" <<'FAKE'
print("host 01:02:03 · lid · ok · open \x1b[31m(AppleClamshellState No)")
FAKE
cat > "$WORK/fake/flood.py" <<'FAKE'
import sys
row = "host 01:02:03 · lid · ok · open (AppleClamshellState No)\n"
for _ in range(40000):
    sys.stdout.write(row)
FAKE

# -------------------------------------------- the read-only copy and the manifest before ---
cp "$H0" "$WORK/ro/host_check.py" || die "cannot copy host_check.py"
chmod 0444 "$WORK/ro/host_check.py" || die "cannot make the copy read-only"
chmod 0555 "$WORK/ro" || die "cannot make the copy's directory read-only"
H="$WORK/ro/host_check.py"
# Only the two shipped files and the copy are hashed, never their whole directory, so a sibling
# file written or synced while the suite runs cannot fail the write proof.
MANIFEST_BEFORE="$WORK/manifest-before.txt"
tool manifest "$H0" "$SRC" "$WORK/ro" > "$MANIFEST_BEFORE" || die "cannot take the manifest"
[ "$(grep -c . "$MANIFEST_BEFORE")" -eq 3 ] || die "the manifest does not list exactly three files"
PYC_BEFORE=$(tool pycache "$SRC_DIR")
[ -n "$PYC_BEFORE" ] || die "cannot list the byte-code beside host_check.py"

# ------------------------------------------------------------------------ leg plumbing -----
N=0; PASSED=0; FAILED=0; why=""; RC=0; T0=0; T1=0; SPAWN=""

verdict() {
  N=$((N + 1))
  if [ -z "$why" ]; then
    PASSED=$((PASSED + 1)); printf 'ok   %2d  %s\n' "$N" "$1"
  else
    FAILED=$((FAILED + 1)); printf 'FAIL %2d  %s —%s\n' "$N" "$1" "$why"
  fi
  why=""
}
need_rc() { [ "$RC" = "$1" ] || why="$why; exit $RC, wanted $1"; }
need_eq() { [ "$1" = "$2" ] || why="$why; $3: '$1' != '$2'"; }
need_ok() { [ "$1" = "ok" ] || why="$why; $2: $1"; }
need_noerr() { [ ! -s "$WORK/err" ] || why="$why; stderr: $(head -c 200 "$WORK/err")"; }
need_fact() { need_ok "$(tool want "$WORK/out" "$@")" "$1"; }
# Every fact except the one or two named reads ok: the control that a planted change stayed in
# its fact.
need_others_ok() {
  for f in "automatic macOS install" "cached recommended entries" "power and idle sleep" \
           "scheduled wakes" "lid"; do
    [ "$f" = "$1" ] || [ "$f" = "${2:-}" ] || need_fact "$f" ok
  done
}
need_calls() { need_eq "$(grep -c . "$STUB_LOG")" "$1" "stub calls"; }
need_span() { need_ok "$(tool within "$T0" "$T1" "$1" "$2")" "elapsed"; }

reset_scn() { rm -rf "$STUB_SCN"; mkdir "$STUB_SCN" || die "cannot reset the scenario directory"; }
# put KEY STDOUT [STDERR [RC]]: a scenario for one read; an empty STDOUT prints nothing.
put() {
  rm -f "$STUB_SCN/$1.out" "$STUB_SCN/$1.err"
  [ -n "$2" ] && printf '%s\n' "$2" > "$STUB_SCN/$1.out"
  [ -n "${3:-}" ] && printf '%s\n' "$3" > "$STUB_SCN/$1.err"
  printf '%s\n' "${4:-0}" > "$STUB_SCN/$1.rc"
}
putf() { put "$1" ""; cp "$2" "$STUB_SCN/$1.out" || die "cannot plant $2"; }
# putcap KEY FILE RC: nothing on stdout, FILE verbatim on stderr (a captured reply), exit RC.
putcap() { put "$1" "" "" "$3"; cp "$2" "$STUB_SCN/$1.err" || die "cannot plant $2"; }
hang() { printf 'hang\n' > "$STUB_SCN/$1.hang"; }

clean_host() {
  reset_scn
  put defaults-AutomaticallyInstallMacOSUpdates "0"
  putf defaults-RecommendedUpdates "$FX/rec-empty"
  put defaults-LastSuccessfulDate "2026-10-04 09:12:33 +0000"
  putf pmset-batt "$FX/batt-ac"
  putf pmset-custom "$FX/custom-ac0"
  put pmset-sched "No scheduled events."
  putf ioreg "$FX/ioreg-open"
}

keep_log() {
  [ -f "$STUB_LOG" ] && cat "$STUB_LOG" >> "$WORK/argv-all.log"
  [ -f "$STUB_LOG" ] || : > "$STUB_LOG"
}

# hc: run the read-only copy of the collector against the planted scenario. Every run must exit
# 0, write nothing to stderr and print the six-line shape.
hc() {
  rm -f "$STUB_LOG"
  T0=$(tool clock)
  RC=0
  "$PY" -B "$H" >"$WORK/out" 2>"$WORK/err" || RC=$?
  T1=$(tool clock)
  keep_log
  need_rc 0
  need_noerr
  need_ok "$(tool shape "$WORK/out")" "output shape"
}

# sp WAITFILE SIGNAL ARG...: run the read-only copy with ARG... through `tool spawn`, which
# signals it once WAITFILE fills (or not, given '-' '-') and reports its exit, the seconds to it
# and the peak memory in $SPAWN.
sp() {
  rm -f "$STUB_LOG"
  w=$1; s=$2; shift 2
  SPAWN=$(tool spawn "$WORK/out" "$WORK/err" 30 "$w" "$s" "$PY" -B "$H" "$@")
  keep_log
}
spawn_rc() { printf '%s\n' "$SPAWN" | sed -n 's/^rc \([0-9-]*\) after .*/\1/p'; }
spawn_after() { printf '%s\n' "$SPAWN" | sed -n 's/^rc [0-9-]* after \([0-9.]*\) s .*/\1/p'; }
spawn_peak() { printf '%s\n' "$SPAWN" | sed -n 's/.* peak \([0-9]*\)$/\1/p'; }
# need_spawn MAX: the spawned run exited 0, within MAX seconds of its signal (or its start).
need_spawn() {
  [ "$(spawn_rc)" = "0" ] || why="$why; spawned run: $SPAWN"
  need_ok "$(tool within 0 "$(spawn_after)" 0 "$1")" "seconds to the exit"
}

# call [PATH]: the shipped caller, host_check.py --caller, on the read-only copy itself or on
# the collector at PATH.
call() {
  rm -f "$STUB_LOG"
  T0=$(tool clock)
  RC=0
  "$PY" -B "$H" --caller "$@" >"$WORK/out" 2>"$WORK/err" || RC=$?
  T1=$(tool clock)
  keep_log
  need_rc 0
  need_noerr
  need_ok "$(tool format "$WORK/out")" "caller output format"
}
# One collector line and nothing else, carrying the reason given.
need_collector_only() {
  need_eq "$(grep -c . "$WORK/out")" "1" "caller lines"
  need_fact collector unknown "$1"
}

# py_unit [ARG...]: run a Python snippet (on stdin) with the read-only copy's path as argv[1].
py_unit() {
  rm -f "$STUB_LOG"
  RC=0
  "$PY" -B - "$H" "$@" >"$WORK/out" 2>"$WORK/err" || RC=$?
  keep_log
}

# ------------------------------------------------------------- planted hosts ---------------
clean_host
hc
need_fact "automatic macOS install" ok "AutomaticallyInstallMacOSUpdates 0 (the local setting; a configuration profile is not read)"
need_fact "cached recommended entries" ok "none cached (current availability stays unknown)" \
          "LastSuccessfulDate 2026-10-04 09:12:33 +0000 (relationship to the list unverified)"
need_fact "power and idle sleep" ok "on AC power" "AC sleep 0"
need_fact "scheduled wakes" ok "none listed by pmset -g sched"
need_fact "lid" ok "open (AppleClamshellState No)"
need_fact "later lid closure" unknown "this check cannot predict a later lid closure; keep the lid open"
need_eq "$(tool count "$WORK/out" ok)" "5" "ok lines"
need_eq "$(sed -n '6p' "$WORK/out" | sed 's/^host [0-9:]* · //')" \
        "later lid closure · unknown · this check cannot predict a later lid closure; keep the lid open" \
        "the sixth line"
EXPECT_ORDER=$(printf 'defaults read %s AutomaticallyInstallMacOSUpdates\ndefaults read %s RecommendedUpdates\ndefaults read %s LastSuccessfulDate\npmset -g batt\npmset -g custom\npmset -g sched\nioreg -r -c IOPMrootDomain -d 1' "$DOMAIN" "$DOMAIN" "$DOMAIN")
need_eq "$(cat "$STUB_LOG")" "$EXPECT_ORDER" "the seven reads, in order, each answered by a stub"
verdict "planted clean host: every fact prints ok, then the fixed lid line as the sixth line; exactly the seven reads were made, in order, each answered by a stub (the control for every leg below)"

reset_scn
put defaults-AutomaticallyInstallMacOSUpdates "1"
putf defaults-RecommendedUpdates "$FX/rec-three"
put defaults-LastSuccessfulDate "2026-10-04 09:12:33 +0000"
putf pmset-batt "$FX/batt-battery"
putf pmset-custom "$FX/custom-ac10"
putf pmset-sched "$FX/sched-two"
putf ioreg "$FX/ioreg-closed"
hc
need_fact "automatic macOS install" warn "an update may install and restart the Mac during the run"
need_fact "cached recommended entries" warn "3 cached:"
need_fact "power and idle sleep" warn "on battery power (80%)" "AC sleep 10 min (the run freezes if the Mac sleeps)"
need_fact "scheduled wakes" warn "2 listed:"
need_fact "lid" warn "closed (AppleClamshellState Yes)"
need_fact "later lid closure" unknown "keep the lid open"
need_eq "$(tool count "$WORK/out" warn)" "5" "warn lines"
need_calls 7
verdict "planted warning host: every fact prints warn, and the fixed lid line still follows"

# ------------------------------------------------------- fact 1: automatic macOS install ---
clean_host; put defaults-AutomaticallyInstallMacOSUpdates "1"; hc
need_fact "automatic macOS install" warn "AutomaticallyInstallMacOSUpdates 1: an update may install and restart the Mac during the run"
need_others_ok "automatic macOS install"
verdict "fact 1, key 1: warn naming the restart risk; the other facts still ok"

clean_host; put defaults-AutomaticallyInstallMacOSUpdates "0"; hc
need_fact "automatic macOS install" ok "AutomaticallyInstallMacOSUpdates 0" "the local setting; a configuration profile is not read"
need_others_ok "automatic macOS install"
verdict "fact 1, key 0: ok, the detail naming what the read covers (the local setting, not a configuration profile)"

clean_host; putcap defaults-AutomaticallyInstallMacOSUpdates "$CAP/key.err" 1; hc
need_fact "automatic macOS install" unknown "AutomaticallyInstallMacOSUpdates absent" "!failed"
need_others_ok "automatic macOS install"
clean_host; putcap defaults-AutomaticallyInstallMacOSUpdates "$CAP/domain.err" 1; hc
need_fact "automatic macOS install" unknown "AutomaticallyInstallMacOSUpdates absent" "!failed"
clean_host; put defaults-AutomaticallyInstallMacOSUpdates "" "$(absent_msg AutomaticallyInstallMacOSUpdates)" 1; hc
need_fact "automatic macOS install" unknown "AutomaticallyInstallMacOSUpdates absent" "!failed"
verdict "fact 1, key absent: the real defaults reply for a missing key and for a missing domain (captured this run) and the older recalled reply each print unknown, read as absent and not as a failure"

clean_host; put defaults-AutomaticallyInstallMacOSUpdates "" "defaults: could not read the domain (fixture fault)" 1; hc
need_fact "automatic macOS install" unknown "defaults read AutomaticallyInstallMacOSUpdates failed (exit 1" "fixture fault" "!absent"
need_others_ok "automatic macOS install"
verdict "fact 1, erroring: unknown, the failure and its message quoted (not read as absent: the control on the widened absent match)"

clean_host; put defaults-AutomaticallyInstallMacOSUpdates "YES"; hc
need_fact "automatic macOS install" unknown 'has an unexpected value "YES"'
clean_host; put defaults-AutomaticallyInstallMacOSUpdates ""; hc
need_fact "automatic macOS install" unknown "printed nothing"
verdict "fact 1, malformed and empty: an unexpected value and an empty read each print unknown, never ok"

clean_host; put defaults-AutomaticallyInstallMacOSUpdates "$(printf '\377\033[31mred\tline')"; hc
need_fact "automatic macOS install" unknown "has an unexpected value" "[31mred line"
verdict "fact 1, a byte that is not UTF-8 and control characters: unknown, the value quoted on one line with the byte replaced and the controls blanked"

# ---------------------------------------------------- fact 2: cached recommended entries ---
clean_host; hc
need_fact "cached recommended entries" ok "none cached (current availability stays unknown)"
verdict "fact 2, list empty: ok, printed as none cached with availability unknown"

clean_host; putf defaults-RecommendedUpdates "$FX/rec-three"; hc
need_fact "cached recommended entries" warn \
  '3 cached: "macOS Fixture 26.0.1", "Café \"Pro\" Tools", Identifier "MSU_MAJOR_FIXTURE_27"' \
  "LastSuccessfulDate 2026-10-04 09:12:33 +0000 (relationship to the list unverified)"
need_others_ok "cached recommended entries"
verdict "fact 2, with entries: warn listing each cached name literally (escapes decoded, quotes kept unambiguous), the nameless major upgrade counted by its identifier"

clean_host; put defaults-RecommendedUpdates "" "defaults: fixture read fault" 1; hc
need_fact "cached recommended entries" unknown "defaults read RecommendedUpdates failed (exit 1" "LastSuccessfulDate 2026-10-04"
clean_host; putcap defaults-RecommendedUpdates "$CAP/key.err" 1; hc
need_fact "cached recommended entries" unknown "RecommendedUpdates absent" "!failed"
clean_host; put defaults-RecommendedUpdates "" "$(absent_msg RecommendedUpdates)" 1; hc
need_fact "cached recommended entries" unknown "RecommendedUpdates absent"
verdict "fact 2, list unreadable: an erroring read, an absent key in the real reply and an absent key in the older reply each print unknown (the date still printed)"

clean_host; putf defaults-RecommendedUpdates "$FX/rec-broken"; hc
need_fact "cached recommended entries" unknown "RecommendedUpdates malformed" '"( { \"Display Name\"'
clean_host; put defaults-RecommendedUpdates "a lone word"; hc
need_fact "cached recommended entries" unknown "malformed"
clean_host; put defaults-RecommendedUpdates "plainword"; hc
need_fact "cached recommended entries" unknown "is not a list"
verdict "fact 2, list malformed: a truncated listing, two loose words and a bare value each print unknown with the raw text quoted"

clean_host; hc
need_fact "cached recommended entries" ok "; LastSuccessfulDate 2026-10-04 09:12:33 +0000 (relationship to the list unverified)"
verdict "LastSuccessfulDate present: printed under its own name, marked relationship to the list unverified"

clean_host; putcap defaults-LastSuccessfulDate "$CAP/key.err" 1; hc
need_fact "cached recommended entries" unknown "none cached" "LastSuccessfulDate absent" "!relationship"
need_others_ok "cached recommended entries"
clean_host; put defaults-LastSuccessfulDate "" "$(absent_msg LastSuccessfulDate)" 1; hc
need_fact "cached recommended entries" unknown "none cached" "LastSuccessfulDate absent"
clean_host; putf defaults-RecommendedUpdates "$FX/rec-three"; putcap defaults-LastSuccessfulDate "$CAP/key.err" 1; hc
need_fact "cached recommended entries" warn "3 cached:" "LastSuccessfulDate absent"
verdict "LastSuccessfulDate missing (the real reply, then the older one): printed as absent, and an empty list beside it prints unknown, never ok; a cached entry's warning still stands"

clean_host; put defaults-LastSuccessfulDate "yesterday"; hc
need_fact "cached recommended entries" unknown "none cached" 'LastSuccessfulDate malformed: "yesterday"'
clean_host; put defaults-LastSuccessfulDate "2026-13-45 09:12:33 +0000"; hc
need_fact "cached recommended entries" unknown 'LastSuccessfulDate malformed: "2026-13-45 09:12:33 +0000"'
clean_host; put defaults-LastSuccessfulDate "" "defaults: fixture date fault" 1; hc
need_fact "cached recommended entries" unknown "LastSuccessfulDate unread (defaults read LastSuccessfulDate failed (exit 1"
clean_host; put defaults-LastSuccessfulDate ""; hc
need_fact "cached recommended entries" unknown "LastSuccessfulDate unread (defaults read LastSuccessfulDate printed nothing)"
verdict "LastSuccessfulDate malformed, erroring or empty: a word and an impossible date print malformed with the raw value, an erroring or empty read prints unread, and each leaves an empty list unknown, never ok"

clean_host; hang defaults-LastSuccessfulDate; hc
need_fact "cached recommended entries" unknown "none cached" "LastSuccessfulDate unread (defaults read LastSuccessfulDate timed out after 2 s)"
need_others_ok "cached recommended entries"
need_span 2.0 4.0
need_eq "$(tool alive "$STUB_SCN/hung.pids")" "listed 2 live none" "the hung stub and its child"
verdict "LastSuccessfulDate timed out: printed as unread after its 2 s bound, and the empty list beside it prints unknown, never ok"

# ------------------------------------------------------------ fact 3: power and idle sleep -
clean_host; hc
need_fact "power and idle sleep" ok "on AC power; AC sleep 0"
verdict "fact 3, on AC with AC sleep 0: ok, while the battery profile's sleep 10 is ignored (the control on the profile read)"

clean_host; putf pmset-batt "$FX/batt-battery"; hc
need_fact "power and idle sleep" warn "on battery power (80%); AC sleep 0"
need_others_ok "power and idle sleep"
verdict "fact 3, on battery: warn"

clean_host; putf pmset-batt "$FX/batt-ups"; hc
need_fact "power and idle sleep" warn "on UPS power (80%); AC sleep 0"
need_others_ok "power and idle sleep"
clean_host; putf pmset-batt "$FX/batt-odd"; hc
need_fact "power and idle sleep" unknown 'power source unrecognised: "Fixture Power"' "AC sleep 0"
need_others_ok "power and idle sleep"
verdict "fact 3, other power sources: on UPS power prints warn, and a source this check does not know prints unknown, never ok"

clean_host; putf pmset-custom "$FX/custom-ac10"; hc
need_fact "power and idle sleep" warn "on AC power; AC sleep 10 min (the run freezes if the Mac sleeps)"
need_others_ok "power and idle sleep"
verdict "fact 3, AC sleep 10: warn, while the battery profile's sleep 0 is ignored"

clean_host; put pmset-custom "" "pmset: fixture fault" 1; hc
need_fact "power and idle sleep" unknown "on AC power" "AC sleep unknown (pmset -g custom failed (exit 1"
clean_host; putf pmset-custom "$FX/custom-noac"; hc
need_fact "power and idle sleep" unknown "AC sleep unknown (no AC Power profile"
clean_host; putf pmset-custom "$FX/custom-word"; hc
need_fact "power and idle sleep" unknown 'AC sleep unknown (value "never")'
verdict "fact 3, AC sleep unreadable: an erroring read, no AC profile and a non-numeric value each print unknown"

clean_host; put pmset-batt "" "pmset: fixture fault" 1; hc
need_fact "power and idle sleep" unknown "power source unknown (pmset -g batt failed (exit 1" "AC sleep 0"
clean_host; put pmset-batt "Battery information unavailable"; hc
need_fact "power and idle sleep" unknown "power source unknown (no 'Now drawing from'"
verdict "fact 3, power source unreadable: an erroring read and a listing without the source each print unknown"

clean_host; putf pmset-batt "$FX/batt-battery"; put pmset-custom "" "pmset: fixture fault" 1; hc
need_fact "power and idle sleep" warn "on battery power (80%)" "AC sleep unknown"
verdict "fact 3, on battery with AC sleep unreadable: the known warning stands, and the unread part is named in the detail"

# ------------------------------------------------------------------ fact 4: scheduled wakes -
clean_host; hc
need_fact "scheduled wakes" ok "none listed by pmset -g sched"
clean_host; putf pmset-sched "$FX/sched-header"; hc
need_fact "scheduled wakes" ok "none listed by pmset -g sched"
clean_host; put pmset-sched ""; hc
need_fact "scheduled wakes" unknown "pmset -g sched printed nothing"
need_others_ok "scheduled wakes"
verdict "fact 4, wake list empty: pmset's 'No scheduled events.' and a header with no event each print ok, while an empty listing is an empty read and prints unknown, never ok"

clean_host; putf pmset-sched "$FX/sched-two"; hc
need_fact "scheduled wakes" warn "2 listed: [0] wake at 10/05/2026 20:35:48 by 'FixtureAgent'; [1] shutdown at 10/06/2026 03:00:00 by 'FixtureAgent'"
need_others_ok "scheduled wakes"
clean_host; putf pmset-sched "$FX/sched-repeat"; hc
need_fact "scheduled wakes" warn "1 listed: repeating wakepoweron at 8:00AM weekdays only"
verdict "fact 4, with entries: listed literally as information, under warn; 'No scheduled events.' beside a repeating event does not hide it"

clean_host; put pmset-sched "" "pmset: fixture fault" 1; hc
need_fact "scheduled wakes" unknown "pmset -g sched failed (exit 1"
clean_host; putf pmset-sched "$FX/sched-odd"; hc
need_fact "scheduled wakes" unknown "unrecognised listing"
verdict "fact 4, erroring: unknown; an unrecognised listing is unknown too"

# ----------------------------------------------------------------------------- fact 5: lid -
clean_host; hc
need_fact "lid" ok "open (AppleClamshellState No)"
need_fact "later lid closure" unknown "keep the lid open"
verdict "fact 5, lid open: ok, followed by the fixed line"

clean_host; putf ioreg "$FX/ioreg-closed"; hc
need_fact "lid" warn "closed (AppleClamshellState Yes)"
need_fact "later lid closure" unknown "keep the lid open"
need_others_ok "lid"
verdict "fact 5, lid closed: warn, followed by the fixed line"

clean_host; put ioreg "" "ioreg: fixture fault" 1; hc
need_fact "lid" unknown "ioreg -c IOPMrootDomain failed (exit 1"
clean_host; putf ioreg "$FX/ioreg-nokey"; hc
need_fact "lid" unknown "no AppleClamshellState"
clean_host; putf ioreg "$FX/ioreg-odd"; hc
need_fact "lid" unknown 'unexpected value "Maybe"'
need_fact "later lid closure" unknown "keep the lid open"
verdict "fact 5, lid unreadable: an erroring read, a missing key and an unexpected value each print unknown, the fixed line still following"

# -------------------------------------------------------------------------------- hangs ----
clean_host; hang ioreg; hc
need_fact "lid" unknown "ioreg -c IOPMrootDomain timed out after 2 s"
need_others_ok "lid"
need_span 2.0 4.0
need_eq "$(tool alive "$STUB_SCN/hung.pids")" "listed 2 live none" "the hung stub and its child"
verdict "hang: a hanging ioreg prints unknown within its 2 s bound, the script exits 0, and the stub and the child holding its pipe are both gone"

clean_host; hang pmset-batt; hc
need_fact "power and idle sleep" unknown "power source unknown (pmset -g batt timed out after 2 s)" "AC sleep 0"
need_fact "scheduled wakes" ok
need_fact "lid" ok
need_calls 7
need_span 2.0 4.0
need_eq "$(tool alive "$STUB_SCN/hung.pids")" "listed 2 live none" "the hung stub and its child"
verdict "hang: a hanging pmset -g batt costs only its own fact; every later read is still made and reads ok"

clean_host
for k in defaults-AutomaticallyInstallMacOSUpdates defaults-RecommendedUpdates defaults-LastSuccessfulDate \
         pmset-batt pmset-custom pmset-sched ioreg; do hang "$k"; done
hc
need_eq "$(tool count "$WORK/out" unknown)" "6" "unknown lines (five facts and the fixed line)"
need_fact "automatic macOS install" unknown "timed out after 2 s"
need_fact "cached recommended entries" unknown "RecommendedUpdates timed out after 2 s" "LastSuccessfulDate unread"
need_fact "lid" unknown "timed out after 2 s"
need_calls 7
need_span 14.0 17.0
need_eq "$(tool alive "$STUB_SCN/hung.pids")" "listed 14 live none" "the seven hung stubs and their children"
verdict "hang: when every read hangs, each still gets its own 2 s bound, all five facts print unknown, the script exits 0 inside 17 s (under the caller's 20 s), and nothing it started survives"

clean_host; hang ioreg
py_unit <<'UNIT'
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("host_check_unit", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
r = m.run_read(["pmset", "-g", "batt"], "pmset -g batt", time.monotonic() - 1)
print("SPENT %s" % r.failure)
t = time.monotonic()
r = m.run_read(["ioreg", "-r", "-c", "IOPMrootDomain", "-d", "1"], "ioreg", t + 0.5)
print("SHORT %.2f %s" % (time.monotonic() - t, r.failure))
r = m.run_read(["no-such-command-for-this-suite"], "absent command", time.monotonic() + 5)
print("MISSING %s" % r.failure)
UNIT
need_rc 0
need_noerr
need_eq "$(grep '^SPENT' "$WORK/out")" "SPENT pmset -g batt not read: the collector's 15 s total budget was spent" "a read after the budget"
SHORT=$(grep '^SHORT' "$WORK/out")
case $SHORT in "SHORT 0.5"*" ioreg timed out after 0.5 s"|"SHORT 0.6"*" ioreg timed out after 0.5 s") : ;; *) why="$why; a read with 0.5 s of budget left: $SHORT" ;; esac
need_eq "$(grep '^MISSING' "$WORK/out")" "MISSING no-such-command-for-this-suite not found in $WORK/bin" "a command that does not exist"
need_eq "$(cat "$STUB_LOG")" "ioreg -r -c IOPMrootDomain -d 1" "stub calls (the spent read starts nothing)"
verdict "the total budget: a read after the budget is spent starts nothing and prints why, a read with 0.5 s left is bounded at 0.5 s not 2 s, and a missing command is named with where it was looked for"

# A command found but impossible to start: an ioreg whose interpreter does not exist.
clean_host
mv "$WORK/bin/ioreg" "$WORK/bin/ioreg.stub" || die "cannot set the ioreg stub aside"
printf '#!%s\nexit 0\n' "$WORK/no-such-interpreter" > "$WORK/bin/ioreg"
chmod 0755 "$WORK/bin/ioreg"
hc
need_fact "lid" unknown "ioreg -c IOPMrootDomain could not start ("
need_fact "later lid closure" unknown "keep the lid open"
need_others_ok "lid"
need_calls 6
mv "$WORK/bin/ioreg.stub" "$WORK/bin/ioreg" || die "cannot restore the ioreg stub"
verdict "a command that cannot start (its interpreter is missing): its fact prints unknown naming the failure, the script exits 0, and the six other reads are made"

clean_host; printf 'orphan\n' > "$STUB_SCN/ioreg.orphan"; hc
need_fact "lid" unknown "ioreg -c IOPMrootDomain timed out after 2 s"
need_fact "later lid closure" unknown "keep the lid open"
need_others_ok "lid"
need_span 2.0 4.0
ORPHAN_PID=$(tr -d ' \n' < "$STUB_SCN/orphan.pids")
need_eq "$(tool living "$STUB_SCN/orphan.pids")" "listed 1 live $ORPHAN_PID" "the grandchild in its own session, just after the script returned"
need_eq "$(tool reap "$STUB_SCN/orphan.pids")" "killed 1 of 1" "the suite ending that grandchild"
need_eq "$(tool alive "$STUB_SCN/orphan.pids")" "listed 1 live none" "the grandchild once the suite ended it"
verdict "the stated limit: a read whose grandchild starts a session of its own and keeps the pipe still returns at its 2 s bound, the script exits 0 and the other facts read; that grandchild survives the kill (the suite then ends it)"

clean_host; sp - -
need_spawn 10
PEAK_CLEAN=$(spawn_peak)
need_ok "$(tool shape "$WORK/out")" "clean run shape"
clean_host; printf 'stdout\n' > "$STUB_SCN/pmset-sched.flood"; printf 'stderr\n' > "$STUB_SCN/ioreg.flood"; sp - -
need_spawn 3
PEAK_FLOOD=$(spawn_peak)
need_noerr
need_ok "$(tool shape "$WORK/out")" "output shape"
need_fact "scheduled wakes" unknown "pmset -g sched printed more than 1 MiB and was stopped"
need_fact "lid" unknown "ioreg -c IOPMrootDomain printed more than 1 MiB and was stopped"
need_others_ok "scheduled wakes" "lid"
need_eq "$(tool alive "$STUB_SCN/flood.pids")" "listed 2 live none" "the two flooding reads"
# The collector holds at most the 1 MiB cap and one 64 KiB chunk of a read, so the flood run
# should peak about 1.1 MiB above the clean run; 16 MiB is the allowance (set by judgement).
# Uncapped, the build review measured a peak of 1,697 MB after a quarter of a second.
need_ok "$(tool within "${PEAK_CLEAN:-0}" "${PEAK_FLOOD:-999999999999}" -999999999999 16777216 bytes)" "peak memory above the clean run"
verdict "output cap: a read flooding stdout and one flooding stderr each stop past 1 MiB with their fact unknown, the script exits 0 inside 3 s, the flooders are gone, and the peak memory stays within 16 MiB of a clean run's (clean $PEAK_CLEAN, flood $PEAK_FLOOD bytes)"

# ------------------------------------------------------------------- the command lookup ----
SYS_DEFAULTS=""; SYS_IOREG=""
for d in /usr/bin /bin /usr/sbin /sbin; do
  [ -z "$SYS_DEFAULTS" ] && [ -x "$d/defaults" ] && SYS_DEFAULTS="$d/defaults"
  [ -z "$SYS_IOREG" ] && [ -x "$d/ioreg" ] && SYS_IOREG="$d/ioreg"
done
py_unit "$WORK/decoy" "$WORK/bin" <<'UNIT'
import importlib.util, os, shutil, sys
spec = importlib.util.spec_from_file_location("host_check_unit", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
os.environ["PATH"] = sys.argv[2] + os.pathsep + os.environ.get("PATH", "")
os.environ.pop("HOST_CHECK_BIN_DIRS", None)
print("UNSET defaults %s" % m.resolve("defaults"))
print("UNSET ioreg %s" % m.resolve("ioreg"))
print("PATH defaults %s" % shutil.which("defaults"))
os.environ["HOST_CHECK_BIN_DIRS"] = sys.argv[3]
print("SET defaults %s" % m.resolve("defaults"))
print("SET ioreg %s" % m.resolve("ioreg"))
os.environ["HOST_CHECK_BIN_DIRS"] = ""
print("EMPTY defaults %s" % m.resolve("defaults"))
UNIT
need_rc 0
need_noerr
need_eq "$(grep '^PATH ' "$WORK/out")" "PATH defaults $WORK/decoy/defaults" "control: a PATH lookup finds the decoy"
need_eq "$(grep '^UNSET defaults' "$WORK/out")" "UNSET defaults $SYS_DEFAULTS" "defaults with the variable unset"
need_eq "$(grep '^UNSET ioreg' "$WORK/out")" "UNSET ioreg $SYS_IOREG" "ioreg with the variable unset"
need_eq "$(grep '^SET defaults' "$WORK/out")" "SET defaults $WORK/bin/defaults" "defaults with the variable set"
need_eq "$(grep '^SET ioreg' "$WORK/out")" "SET ioreg $WORK/bin/ioreg" "ioreg with the variable set"
need_eq "$(grep '^EMPTY defaults' "$WORK/out")" "EMPTY defaults $SYS_DEFAULTS" "defaults with the variable empty"
[ -n "$SYS_DEFAULTS" ] && [ -n "$SYS_IOREG" ] || why="$why; no system defaults or ioreg to compare with"
need_eq "$(grep -c . "$STUB_LOG")" "0" "stub calls (the lookup runs nothing)"
verdict "command lookup: with HOST_CHECK_BIN_DIRS unset or empty the system directories answer ($SYS_DEFAULTS, $SYS_IOREG), never a decoy first on PATH (control: a PATH lookup finds it); set, exactly the directories it names answer"

# ------------------------------------------------------------------------ stop signals -----
for sig in SIGTERM SIGINT SIGHUP; do
  clean_host; hang defaults-AutomaticallyInstallMacOSUpdates
  sp "$STUB_SCN/hung.pids" "$sig"
  need_spawn 1.5
  need_noerr
  need_ok "$(tool format "$WORK/out")" "$sig: line format"
  need_eq "$(grep -c . "$WORK/out")" "2" "$sig: lines"
  need_fact "automatic macOS install" unknown "defaults read AutomaticallyInstallMacOSUpdates was stopped: $sig was received"
  need_fact collector unknown "stopped: $sig was received before cached recommended entries was read"
  need_calls 1
  need_eq "$(tool alive "$STUB_SCN/hung.pids")" "listed 2 live none" "$sig: the read in flight and its child"
done
verdict "stopped by SIGTERM, SIGINT or SIGHUP mid-read: the read in flight and the child keeping its pipe are ended (a signal to the script never reaches them, as each read leads a session of its own), no further read starts, the fact in hand prints unknown, one collector line names the signal, and the script exits 0 within 1.5 s"

# ----------------------------------------------------------- platform, faults, stdout ------
clean_host
rm -f "$STUB_LOG"
RC=0
"$PY" -B -c 'import runpy, sys
path = sys.argv[1]
sys.argv = [path]
sys.platform = "linux"
runpy.run_path(path, run_name="__main__")' "$H" >"$WORK/out" 2>"$WORK/err" || RC=$?
need_rc 0
need_noerr
need_ok "$(tool shape "$WORK/out")" "output shape"
need_eq "$(tool count "$WORK/out" unknown)" "6" "unknown lines"
need_fact "lid" unknown "unsupported platform linux: no macOS command was run"
PCALLS=0
[ -f "$STUB_LOG" ] && PCALLS=$(grep -c . "$STUB_LOG")
need_eq "$PCALLS" "0" "stub calls"
verdict "unsupported platform: every fact prints unknown, the fixed line follows, and no command runs (the clean-host leg's seven calls on the same stubs are the control)"

clean_host
py_unit <<'UNIT'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("host_check_unit", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def broken(text):
    return 1 / 0
m.parse_openstep = broken
sys.stdout.flush()
print("RC %s" % m.main([]))
UNIT
need_rc 0
need_noerr
grep -v '^RC ' "$WORK/out" > "$WORK/out.lines"
need_ok "$(tool shape "$WORK/out.lines")" "output shape"
need_ok "$(tool want "$WORK/out.lines" "cached recommended entries" unknown "internal error reading this fact (ZeroDivisionError)")" "the faulty fact"
need_ok "$(tool want "$WORK/out.lines" "lid" ok)" "a later fact"
need_eq "$(grep '^RC ' "$WORK/out")" "RC 0" "main's return"
py_unit <<'UNIT'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("host_check_unit", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.FACTS = None
sys.stdout.flush()
print("RC %s" % m.main([]))
UNIT
need_noerr
grep -v '^RC ' "$WORK/out" > "$WORK/out.lines"
need_eq "$(grep -c . "$WORK/out.lines")" "1" "lines after a fault outside every fact"
need_ok "$(tool want "$WORK/out.lines" collector unknown "internal error (TypeError)")" "the collector line"
need_eq "$(grep '^RC ' "$WORK/out")" "RC 0" "main's return"
verdict "internal faults: a fault inside one fact prints that fact unknown and the rest still read; a fault outside every fact prints one collector unknown line; main returns 0 in both"

clean_host
rm -f "$STUB_LOG"
RC=0
"$PY" -B "$H" >&- 2>"$WORK/err" || RC=$?
need_rc 0
need_noerr
verdict "standard output closed: the script exits 0 and writes no traceback"

clean_host
rm -f "$STUB_LOG"
RC=0
"$PY" -B "$H" --bogus >"$WORK/out" 2>"$WORK/err" || RC=$?
need_rc 0
need_noerr
need_eq "$(grep -c . "$WORK/out")" "1" "lines for --bogus"
need_fact collector unknown 'unrecognised arguments "--bogus": run with no argument, or with --caller'
RC=0
"$PY" -B "$H" --caller one two >"$WORK/out" 2>"$WORK/err" || RC=$?
need_rc 0
need_noerr
need_fact collector unknown 'unrecognised arguments "--caller one two"'
PCALLS=0
[ -f "$STUB_LOG" ] && PCALLS=$(grep -c . "$STUB_LOG")
need_eq "$PCALLS" "0" "stub calls"
verdict "unrecognised arguments: one collector line naming them, exit 0, and no read is made"

# ------------------------------------------------------------- the caller (shipped) --------
clean_host; hc
sed 's/^host [0-9:]* · //' "$WORK/out" > "$WORK/direct.txt"
clean_host; call
need_ok "$(tool shape "$WORK/out")" "lines through the caller"
need_eq "$(sed 's/^host [0-9:]* · //' "$WORK/out")" "$(cat "$WORK/direct.txt")" "the lines, times aside, against a direct run"
need_eq "$(grep -c ' · collector · ' "$WORK/out")" "0" "collector lines"
need_calls 7
verdict "caller control: host_check.py --caller passes the collector's six lines through unchanged (times aside, equal to a direct run's), with no collector line"

call "$WORK/fake/absent.py"
need_collector_only "collector missing: no file at $WORK/fake/absent.py"
verdict "caller, missing collector: one collector unknown line"

call "$WORK/fake/exit3.py"
need_collector_only 'collector exited 3: "fake collector: a fault after one line"'
call "$WORK/fake/killself.py"
need_collector_only "collector ended by SIGKILL"
verdict "caller, non-zero exit: an exit 3 and a collector killed by a signal each give one collector unknown line, the valid-looking line printed first discarded"

rm -f "$WORK/fake.pids"
export FAKE_PIDS="$WORK/fake.pids"
call "$WORK/fake/hang.py"
unset FAKE_PIDS
need_collector_only "collector timed out after 20 s"
need_span 20.0 23.0
need_eq "$(tool alive "$WORK/fake.pids")" "listed 2 live none" "the hung collector and its child"
verdict "caller, hang past the 20 s deadline: one collector unknown line at 20 s, and the collector and its child are gone"

call "$WORK/fake/garbage.py"
need_collector_only 'unparseable output (1 of 2 lines, first: "Traceback'
call "$WORK/fake/silent.py"
need_collector_only "unparseable output (nothing printed)"
call "$WORK/fake/ctrl.py"
need_collector_only "unparseable output (1 of 1 lines, first:"
call "$WORK/fake/flood.py"
need_collector_only "collector printed more than 1 MiB and was stopped"
verdict "caller, unparseable output: a stray line among good ones, no output at all, a line carrying a control character and over 1 MiB of output each give one collector unknown line"

clean_host; hang defaults-AutomaticallyInstallMacOSUpdates
sp "$STUB_SCN/hung.pids" SIGTERM --caller
need_spawn 2.5
need_noerr
need_collector_only "collector was stopped: SIGTERM was received"
need_calls 1
need_eq "$(tool alive "$STUB_SCN/hung.pids")" "listed 2 live none" "the read in flight and its child"
need_eq "$(tool alive "$STUB_SCN/hung.ppids")" "listed 1 live none" "the collector the caller ran"
verdict "caller stopped by SIGTERM (as a timeout on the head's call would stop it): it passes SIGTERM to the collector, which ends its read in flight; one collector line names the signal, the caller exits 0 within 2.5 s, and nothing it started survives"

# ----------------------------------------------------------------------- write proofs ------
MANIFEST_AFTER="$WORK/manifest-after.txt"
tool manifest "$H0" "$SRC" "$WORK/ro" > "$MANIFEST_AFTER"
DIFF=$(diff "$MANIFEST_BEFORE" "$MANIFEST_AFTER" | grep '^[<>]' | cut -c1-110)
need_eq "$DIFF" "" "manifest difference"
need_eq "$(grep -c . "$MANIFEST_AFTER")" "3" "manifest length"
need_eq "$(tool pycache "$SRC_DIR")" "$PYC_BEFORE" "host_check byte-code beside the collector"
verdict "write proof: host_check.py, this suite and the read-only copy are byte-identical after every leg, and no host_check byte-code appeared beside the collector (before: $PYC_BEFORE)"

COPY="$WORK/manifest-control"
rm -rf "$COPY"
mkdir "$COPY"
cp "$H0" "$COPY/host_check.py"
chmod u+w "$COPY/host_check.py"   # a copy of a read-only source is read-only, and this leg appends to it
tool manifest "$COPY/host_check.py" > "$WORK/control-before.txt"
PYC_CONTROL=$(tool pycache "$COPY")
printf '# a planted change\n' >> "$COPY/host_check.py"
mkdir "$COPY/__pycache__"
: > "$COPY/__pycache__/host_check.cpython-0.pyc"
tool manifest "$COPY/host_check.py" > "$WORK/control-after.txt"
if diff "$WORK/control-before.txt" "$WORK/control-after.txt" >/dev/null; then
  why="$why; the manifest did not notice a planted one-line change"
fi
need_eq "$PYC_CONTROL" "absent" "byte-code before the plant"
need_eq "$(tool pycache "$COPY")" "entries 1 host_check.cpython-0.pyc" "the planted byte-code"
verdict "write proof control: the manifest detects a planted one-line change in a copy, and the byte-code check a planted host_check byte-code file"

ARGV=$(tool argv "$WORK/argv-all.log" "$DOMAIN")
case $ARGV in
  "calls "*" bad 0") : ;;
  *) why="$why; $ARGV" ;;
esac
CALLS=$(printf '%s\n' "$ARGV" | sed -n 's/^calls \([0-9]*\) .*/\1/p')
[ "${CALLS:-0}" -ge 200 ] || why="$why; only ${CALLS:-0} stub calls logged across the legs"
cp "$WORK/argv-all.log" "$WORK/argv-planted.log"
printf 'pmset -a sleep 0\n' >> "$WORK/argv-planted.log"
need_eq "$(tool argv "$WORK/argv-planted.log" "$DOMAIN" | head -1 | sed 's/^calls [0-9]* //')" "bad 1" "the planted setter"
verdict "write proof: every one of the $CALLS commands the collector ran across the legs was one of the seven reads (control: a planted pmset setter is caught)"

tool plant "$WORK" > "$WORK/plant.txt"
need_eq "$(cat "$WORK/plant.txt")" "planted sh 2 py 11" "the planted controls"
SCANPY=$(tool scanpy "$H0")
need_eq "$(printf '%s\n' "$SCANPY" | tail -1)" "hits 0" "write or process patterns in host_check.py"
need_eq "$(printf '%s\n' "$SCANPY" | grep '^popen')" "popen 1 argv-lists 7" "Popen sites and argv lists in host_check.py"
need_eq "$(tool scanpy "$WORK/planted-writer.py" | tail -1)" "hits 10" "the planted writer"
verdict "write proof: host_check.py has no file-writing call and one process start, whose seven read argv lists all read (control: ten planted writes and setters give ten hits, and an eleventh line naming open( inside a string gives none)"

need_eq "$(tool scansh "$SRC" | tail -1)" "hits 0" "source scan of this suite"
need_eq "$(tool scansh "$WORK/planted-writer.sh" | tail -1)" "hits 2" "source scan of the planted control"
verdict "write proof: no write verb in this suite aims outside /tmp (control: 2 planted hits, the third planted write inside the work directory not counted)"

# ----------------------------------------------------------------------------- summary -----
printf '\n'
if [ "$FAILED" -eq 0 ]; then
  printf 'PASS %d/%d\n' "$PASSED" "$N"
  exit 0
fi
printf 'FAIL %d/%d\n' "$FAILED" "$N"
exit 1
