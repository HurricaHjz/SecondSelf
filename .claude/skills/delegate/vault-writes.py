#!/usr/bin/env python3
"""vault-writes.py — the vault writes a head composes by hand, as primitives that cannot slip.

Five writes recur in every run — a log entry, a defect-register entry, a register entry
closed or annotated, an IDEAS bullet annotated — and each has been
mis-composed by hand: a misplaced anchor, a doubled span, an entry inserted under the wrong
heading, a whole-file rewrite that erased a line a concurrent writer had added. Each verb
below makes one of them against an asserted anchor, prints one line, and refuses rather than
guesses.

  log-append         append one entry to `wiki/log.md` under the vault root given.
  register add       insert one entry at the top of `## Open` in
                     `wiki/developments/known-issues.md`.
  register close     move one `## Open` entry to the top of `## Closed`, dating its Status.
  register annotate  append one dated, clock-stamped note to one `## Open` entry.
  ideas annotate     append ` *(agent DATE TIME: NOTE)*` to one numbered IDEAS bullet.

The catalogue, `wiki/index.md`, is updated by anchored edits (CLAUDE.md §5), with no verb here.

The clock, and why it is not an argument

  A time of day written by hand is written from a sense of elapsed time, and such stamps
  spread across surfaces before anything compares one to a clock. So
  every stamp below is read from the clock at the moment of the write and from nowhere
  else — no `--time` argument exists to be guessed into:

    register add       `### [DATE HH:MM] SURFACE — TITLE (SEVERITY)`, the date from `--date`;
                       a stamp another heading already carries takes a suffix (below).
    register close     the status fact as `closed DATE HH:MM — …`: the time is inserted after
                       the date the caller's `--status` already opens with (`closed DATE …`),
                       and otherwise the whole stamp is prefixed to the caller's text.
    register annotate  `- **KIND DATE HH:MM ZONE (BY):** NOTE`, ` (BY)` omitted when absent.
    ideas annotate     `*(agent DATE HH:MM: NOTE)*`.
    log-append         one further bullet, `- **Clock**: HH:MM ZONE`, written through the
                       `--extra` path between Changed and Conflicts. The `## [DATE] ACTION |
                       TITLE` heading is a schema surface and is not touched.

  The zone is the clock's own (`%Z`), never a literal. And because a caller's free text may
  still name a time, every text argument is scanned for an `HH:MM` or `HH:Mx` token whose
  hour disagrees with the clock's: each such token prints one line on stderr,
  `clock: the note names TOKEN, the clock reads HH:MM`. It is a warning and never a
  refusal — a note may legitimately cite a past event — so the write proceeds either way,
  and `--dry-run` prints the same warnings. The hour has two digits, as every stamp the vault
  writes has, so a meter's model count (`claude-opus-5:88`) is not a time; nor is a token
  glued to a word by a hyphen or a dot, a minute above 59, or an ISO zone offset (`+01:00`).
  The time attached to a `YYYY-MM-DD` date cites that dated moment and is skipped: the token
  directly after the date, with spaces alone between them (`the entry of 2026-09-30 13:54`),
  and the far end of a range written from that token with a hyphen, an en dash or `to`
  (`2026-09-30 13:54–14:10`, `2026-09-30 13:54 to 14:10`). Every other token is checked, in
  a dated argument too (`seen 2026-09-30 13:54; now filing at 12:00` warns about 12:00), and
  so is the time of a `register close` caller's own `closed DATE HH:MM` stamp, which claims
  the close's own time rather than citing one.

One stamp, one entry (register add)

  A pointer that cites an entry by its stamp alone must find one heading. So `register add`
  reads the stamp of every heading in the register, Open, Closed and elsewhere, before it
  writes its own. The first entry of a minute keeps the bare stamp; a later one in the same
  minute takes a space and the first free letter from b to z inside the brackets,
  `### [2026-10-03 07:48 b] …`; the heading on the reported line, or a dry run, shows which.
  Every reader of the register reads a heading by its `### [` opening or as a whole line, so
  the suffix changes no reader. It refuses where it cannot tell what the new stamp would point
  at: a heading whose bracket opens with the same date and time in any other form (`07:48b`,
  `07:48:31`, `07:48 bb`), or opens with them and never closes (`[DATE HH:MM` alone, or
  `[DATE HH:MM unfinished`); a stamp of that minute that already heads two entries; and a
  minute whose every suffix is taken. Stamps of other minutes that are shared, as many older
  ones are, stop nothing.

Why not fixed now (register add)

  An entry parks a defect, and parking needs a named reason that blocks the fix now
  (CLAUDE.md §12). So `--why-not-fixed-now` is required, and its text is written as its own
  bullet, `- **Why not fixed now**: …`, between Suspected cause and Status, where the
  register's own entry format puts it. Missing, empty, blank or carrying a line break, it
  refuses.

The lines an entry owns (register close, register annotate)

  An entry is its heading, then its own lines: bullets opening `- **` (the fields, and the
  dated Status, Recurrence and Correction notes), lines indented under one of them, and —
  first under the heading only — a plain bullet opening with a date (the one-line entries
  that were given headings later, their text unchanged). Blank lines never end an entry; the
  first line that is none of these does, and so does any heading. A close moves those lines
  and the blank lines after them, and leaves anything after them where it was, with one
  `extent:` line on stderr.
  Its Status field is its own `- **Status**: …` bullet, or its `- **Severity**: … **Status**:
  …` line; a dated note, or any text that only quotes the marker, is not one. Both verbs read
  the entry's structure the same way and refuse what they cannot read: inside its own lines a
  bold bullet opening with a date anywhere but first, or a second copy of a field every entry
  carries once (Where observed, Symptom, Suspected cause, Why not fixed now, Status), which is
  another entry under the same heading; and a Status field under the same heading but below a
  line that is not its own. A close also refuses an entry with no Status field. A note never
  carries the field marker `**Status**:` itself (the register's lint reads that marker as a
  Status wherever it stands), so `register annotate` refuses one.

Concurrent writers (every write except the log append)

  These writes replace their target whole, so a change another writer made after this run
  read the file would be overwritten by it. Three measures bound that:

    the lock     each writing run holds an advisory lock on the target's directory from
                 before its read until after its replace, so two runs of this tool never
                 interleave on one target. Locking is a premise of the write: a platform
                 without `flock`, a directory that cannot be opened or locked, and a lock
                 another run holds past LOCK_WAIT each refuse before anything is read or
                 written. Other programs do not take the lock.
    the check    the bytes are hashed at the read; the new text is written to its temporary
                 file; then the target is read and hashed again, and its inode, device, size
                 and modification time are taken once more as the last look before the
                 replace. Any difference refuses: `error <verb>: <file>: it changed on disk
                 since this run read it …` (or it is gone, or cannot be read again), the
                 temporary file removed and the target left exactly as the other writer left
                 it. A rewrite of the same bytes completed before the last look is no change.
    the window   the guarantee covers changes that land before the last look. Nothing here
                 closes the interval between the last look and the moment the rename takes
                 effect, and this design puts no bound on it: the process can be descheduled
                 there for any length of time, and a write another program makes inside it is
                 overwritten (the suite's late-writer leg shows it). Runs of this tool never
                 meet there, because each holds the lock across it.

The payload, and what a shell may have done to it (log-append)

  A payload inside double quotes is expanded by the caller's shell before this script sees
  it: a backticked token is run as a command and replaced by its output, usually nothing. The
  clean loss arrives looking like ordinary text and cannot be seen here. Two of its traces
  can: an argument carrying an odd number of backticks (a code span left open), and one
  carrying the text `command not found` (a substitution's own error captured into the
  payload). Each prints one stderr line, `payload: ARGUMENT carries …`, and the write
  proceeds either way; `--dry-run` prints the same warnings.

The contract every verb keeps

  * One line of output. `ok <verb> <path>:<line>` names where the change landed, or
    `error <verb>: <reason>` names what stopped it and the process exits 2. A head pays
    a few tokens for a write and never reads a dump.
  * `--dry-run` prints `dry-run <verb> <path>:<line>` and the would-be block as `| `
    lines (at most PREVIEW_MAX, then a count), and writes nothing at all. It is the control
    run, and the way to see a change before making it. It takes no lock.
  * Every write except the log append is atomic and checked: a temp file beside the target,
    fsync, the check above, `os.replace`. An interruption leaves the old file or the new one,
    never half of one.
  * The log is append-only by contract, so `log-append` opens it in append mode and never
    rewrites it. Two bounded read-only probes support that append and neither holds the
    file in memory: its last two bytes (which decide the blank-line separator) and a
    chunked newline count (the line number the `ok` line reports). Neither alters a byte.
  * Every text argument carrying a line break is refused. Wiki prose is one line per
    paragraph or bullet (the schema line discipline), and a line break is also how a
    caller text would forge a heading inside somebody else entry.
  * Refusal beats repair. A structural heading that does not appear exactly once, a match
    count that is not one, a missing or unreadable file, an entry with no Status bullet, a
    lock that cannot be taken, a file changed since its read: `error`, exit 2, naming the
    count or the reason it actually found. Nothing is written on a refusal.

Formats, and where they come from

  The log entry is `## [DATE] ACTION | TITLE`, then `- **Changed**: …`, then the `Clock`
  bullet and any `--extra` bullets in the order given, then `- **Conflicts**: …`, then a
  blank line — the shape the file own recent entries carry, Changed first and Conflicts last.
  An `--extra` is the bare `Key: value`; the verb adds the bullet and the bold, so a key that
  starts with `- ` or carries `**` is a finished bullet passed whole and is refused.
  The register entry is the format the register documents above its own `## Open` heading:
  severity in the heading, then `- **Where observed**`, `- **Symptom**`,
  `- **Suspected cause**`, `- **Why not fixed now**`, `- **Status**`. `--status` is the
  caller's own words, prefixed on a close by the clock stamp above and otherwise untouched
  (`open — fix shape: …`); `--where` is optional and its bullet is omitted when it is absent
  rather than filled with invented text.
  `register close` dates the entry's Status field, so it dates both forms in live use: a
  `- **Status**: …` bullet, and a `- **Severity**: … **Status**: …` line.

Run

  vault-writes.py log-append --vault V --action ACTION --title T --changed C --conflicts X
                             [--extra "Key: value"]... [--date D] [--dry-run]
  vault-writes.py register add --vault V --date D --surface S --symptom Y --cause C
                               --why-not-fixed-now R --severity minor --status T
                               [--where W] [--dry-run]
  vault-writes.py register close --vault V --match TEXT --date D --status TEXT [--dry-run]
  vault-writes.py register annotate --vault V --match TEXT --kind KIND --note TEXT
                                    [--by WHO] [--date D] [--dry-run]
  vault-writes.py ideas annotate --file IDEAS.md --item N --note TEXT [--date D] [--dry-run]

Suite: `test_vault_writes.sh` beside this file (last line PASS n/n or FAIL k/n).
"""

import argparse
import datetime
import hashlib
import os
import re
import stat
import sys
import tempfile
import time

try:
    import fcntl                        # the write lock (take_lock). Where it is missing, every
except ImportError:                     # checked write refuses rather than writing unlocked.
    fcntl = None

# The vocabulary the log itself uses of entry kinds; anything else is a typo, never a new kind.
ACTIONS = ("ingest", "gather", "synthesis", "lint", "deep-lint", "framework",
           "setup", "maps", "attic", "export")
# The severities the register documents. Its format block offers "blocking · major · minor"
# and its live entries also carry "medium", so all four are accepted and none is invented.
SEVERITIES = ("blocking", "major", "medium", "minor")
# The kinds of dated note `register annotate` writes: the labels a register's hand-written dated
# notes carry most, so a written note reads like those beside it; anything else is a typo.
NOTE_KINDS = ("Status", "Recurrence", "Correction")

# Paths are derived from the vault root the caller passes: no absolute path is written here.
LOG_REL = os.path.join("wiki", "log.md")
REGISTER_REL = os.path.join("wiki", "developments", "known-issues.md")

OPEN_HEAD = "## Open"
CLOSED_HEAD = "## Closed"
WHY_LABEL = "Why not fixed now"
NUMERO = "№"                  # the IDEAS bullet marker, spelled as an escape
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ITEM_RE = re.compile(r"^[0-9]+$")
ENTRY_END_RE = re.compile(r"^#{1,6} ")  # any ATX heading ends the entry above it
CHUNK = 65536                           # the log newline count reads this much at a time
PREVIEW_MAX = 6                         # `--dry-run` prints at most this many `| ` lines
SHORT = 70                              # an error line quotes at most this much of a line

# The lines an entry owns (see the docstring): the shapes the register's entry format and its
# dated notes produce, and the date-led body of a one-line entry that was given a heading later.
OWN_BOLD_RE = re.compile(r"^- \*\*")
OWN_INDENTED_RE = re.compile(r"^[ \t]+\S")
OWN_FIRST_DATED_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}\b")
# Inside an entry's own lines, the shapes of another entry: a bold bullet opening with a date or
# a bracketed stamp below the first line, and a second copy of a field every entry carries once.
FOREIGN_DATED_RE = re.compile(r"^- \*\*\[?\d{4}-\d{2}-\d{2}")
ONCE_FIELD_RE = re.compile(r"^- \*\*(Where observed|Symptom|Suspected cause|Why not fixed now)\*\*:")
# An entry's Status field, in the two forms the register's entry format writes: its own bullet,
# and the combined Severity line. A dated note (`- **Status DATE …:**`) is not one, and neither
# is a field's text or a note that only quotes the marker.
STATUS_FIELD_RE = re.compile(r"^- \*\*Status\*\*:|^- \*\*Severity\*\*:.*?\*\*Status\*\*:")
# The marker the register's lint reads as a Status wherever it stands in an entry's line.
STATUS_MARKER = "**Status**:"

# A heading whose text opens with a bracket: the candidate for a stamp, closed or not.
STAMP_OPEN_RE = re.compile(r"^#{1,6}[ \t]+\[(.*)$")
# The suffixes a later entry of the same minute takes, in order; the first entry of a minute
# keeps the bare stamp. Twenty-five is set by judgement, far above any minute's count of entries.
STAMP_SUFFIXES = "bcdefghijklmnopqrstuvwxyz"

# The write lock. LOCK_WAIT is how long a run waits for another run of this tool to finish
# with the same directory before it refuses; LOCK_POLL is how often it asks. Set by judgement
# against a measurement: a write holds the lock for milliseconds, so ten seconds waits out
# hundreds of writes queued ahead, far beyond any run's concurrency; unmeasured on a network
# filesystem.
LOCK_WAIT = 10.0
LOCK_POLL = 0.05
_LOCKS = []                             # descriptors held by this run, released in main()

# A clock token as the register and the notes actually write one: a two-digit hour, a colon,
# then a minute 00-59 or the rounded `Mx` form the register uses ("filed 21:3x BST").
# The lookarounds keep the seconds of `19:52:29` from reading as a second token (`52:29`)
# and keep a token out of a longer word; an hour above 23 is not a time and is skipped.
# Anchored 2026-09-13 (register entry of 2026-09-09 15:27): a one-digit hour would read a meter's
# model count as a clock. Requiring a two-digit hour avoids that ambiguity; excluding a
# letter followed by a hyphen rejects model counts while retaining the second endpoint
# of a time range. Each lookbehind, and the shape it keeps out:
#   a letter, digit, colon or `+`        a word, a longer time, a zone offset (`+01:00`)
#   a letter then a hyphen               a model id and its count (`opus-15:30`)
#   an alphanumeric then a dot           a version and its count (`gpt-5.10:12`)
#   `:SS-` closing a timestamp           a negative zone offset (`12:00:00-05:00`)
CLOCK_TOKEN_RE = re.compile(r"(?<![0-9A-Za-z:+])(?<![A-Za-z]-)(?<![0-9A-Za-z]\.)"
                            r"(?<!:[0-9]{2}:[0-9]{2}-)"
                            r"([0-9]{2}):([0-5][0-9x])(?![0-9A-Za-z])")
HOUR_MAX = 23
HOURS = 24
# A date as the vault writes one, and the time attached to it: the clock token directly after it,
# with spaces alone between them, and the far end of a range written from that token with a
# hyphen, an en dash or `to`. That time cites the dated moment rather than stamping now (register
# entry of 2026-10-01 13:46), so it is skipped. Any other token of the argument is checked: a later
# one can as well be a slip of the present time (`seen 2026-09-30 13:54; now filing at 12:00`),
# which skipping every token after a date would hide; a second time joined by `and` is not a range.
DATE_TOKEN_RE = re.compile(r"(?<![0-9])[0-9]{4}-[0-9]{2}-[0-9]{2}(?![0-9])")
CITED_GAP_RE = re.compile(r"[ \t]+")                             # between a date and its own time
RANGE_JOIN_RE = re.compile(r"[ \t]*[-–][ \t]*|[ \t]+to[ \t]+")  # between a range's two ends
# The grace: the previous hour passes while the clock's minute is under ten — a note written
# just after the turn of the hour about the minute before it. Ten is set by judgement,
# unmeasured; the failure it forgives (a stamp one minute stale) is smaller than the one it
# would otherwise report, and no count of real notes was taken to choose it.
GRACE_MINUTES = 10
# The status fact `register close` writes, and the two shapes a caller's own `--status` may
# already carry: `closed DATE …` takes the time after its date, `closed DATE HH:MM …` is
# already stamped and is left exactly as it came.
# The already-stamped shape admits the rounded `HH:Mx` minute as well as `HH:MM`, so a
# caller who wrote one keeps it verbatim rather than collecting a second time beside it;
# whether that time agrees with the clock is the token check's business, not this one's.
CLOSED_DATED_RE = re.compile(r"^closed\s+\d{4}-\d{2}-\d{2}")
CLOSED_TIMED_RE = re.compile(r"^closed\s+\d{4}-\d{2}-\d{2}\s+\d{1,2}:[0-9][0-9x]")


def die(verb, reason):
    """One error line on stdout — where the head reads it — then exit 2. Never a traceback."""
    print("error %s: %s" % (verb, reason))
    sys.exit(2)


def note(kind, text):
    """One stderr line: a warning or a notice, never a refusal; stdout keeps the one line."""
    sys.stderr.write("%s: %s\n" % (kind, text))


def short(text):
    """A line quoted inside an error message stays inside one line."""
    text = " ".join(text.split())
    return text if len(text) <= SHORT else text[:SHORT - 1] + "…"


def check_text(verb, name, value, allow_empty=False):
    """A wiki line is one line: refuse any argument carrying a break, and refuse the blank."""
    if value is None:
        return None
    if "\n" in value or "\r" in value:
        die(verb, "%s carries a line break; a wiki bullet is one line" % name)
    if not allow_empty and not value.strip():
        die(verb, "%s is empty" % name)
    return value


def check_date(verb, value):
    """A date is YYYY-MM-DD and a real calendar day; absent, it is today."""
    if value is None:
        return datetime.date.today().isoformat()
    if not DATE_RE.match(value):
        die(verb, "--date '%s' is not YYYY-MM-DD" % value)
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        die(verb, "--date %s is not a real date" % value)
    return value


# ----------------------------------------------------------------------- clock ---------

def clock_now():
    """The wall clock, read once per run so every stamp of one write agrees with the rest."""
    return time.localtime()


def clock_hm(now):
    """The stamp itself: `HH:MM`, zero-padded, local time — the only source of a time here."""
    return time.strftime("%H:%M", now)


def clock_zone(now):
    """The clock's own zone name. `%z` (+0100) stands in where a host reports no name."""
    return time.strftime("%Z", now) or time.strftime("%z", now)


def hour_disagrees(token_hour, clock_hour, clock_minute):
    """Whether a token hour is neither the clock's own nor the previous one under the grace."""
    if token_hour == clock_hour:
        return False
    if clock_minute < GRACE_MINUTES and token_hour == (clock_hour - 1) % HOURS:
        return False
    return True


def cited_times(value, tokens):
    """The positions in `tokens` (the clock tokens of `value`, in reading order) of the times
    attached to a date: each date's own time, directly after it, and the far end of a range
    written from that time. Every other token of the argument is not a citation."""
    starts = {found.start(): number for number, found in enumerate(tokens)}
    cited = set()
    for dated in DATE_TOKEN_RE.finditer(value):
        gap = CITED_GAP_RE.match(value, dated.end())
        own = starts.get(gap.end()) if gap else None
        if own is None:
            continue
        cited.add(own)
        join = RANGE_JOIN_RE.match(value, tokens[own].end())
        far = starts.get(join.end()) if join else None
        if far is not None:
            cited.add(far)
    return cited


def clock_tokens(now, values, stamps=()):
    """Every distinct clock token in the caller's text whose hour disagrees, in reading order.

    Distinct, because one token repeated across two arguments is one mistake and earns one
    line; the order is the order the arguments are listed by the verb that collected them.
    The time attached to a date in the same argument cites that dated moment and is skipped
    (cited_times); every other token is checked. `stamps` are read first and whole, with no
    such skip: a caller's own stamp of the write's time (`register close`'s `closed DATE
    HH:MM`) claims now, so its date excuses nothing."""
    offenders = []
    for value, cited_skip in [(text, False) for text in stamps] + [(text, True) for text in values]:
        if not value:
            continue
        tokens = list(CLOCK_TOKEN_RE.finditer(value))
        cited = cited_times(value, tokens) if cited_skip else set()
        for number, found in enumerate(tokens):
            if number in cited:
                continue                # a citation: `the entry of 2026-09-30 13:54`
            hour = int(found.group(1))
            if hour > HOUR_MAX:
                continue                # 52 of `19:52:29` is not an hour; nor is 99
            if not hour_disagrees(hour, now.tm_hour, now.tm_min):
                continue
            if found.group(0) not in offenders:
                offenders.append(found.group(0))
    return offenders


def warn_clock(now, values, stamps=()):
    """One stderr line per offending token. A warning: a note may cite a past event, so the
    write goes ahead, and stdout keeps the one line a head reads."""
    reading = clock_hm(now)
    for token in clock_tokens(now, values, stamps):
        sys.stderr.write("clock: the note names %s, the clock reads %s\n" % (token, reading))


# --------------------------------------------------------------------- payload ---------

# Detect traces a caller's shell leaves when a double-quoted payload loses a backticked token
# (register entry of 2026-09-10 19:59). An odd backtick count is a code span left open: one
# argument is one wiki line, so a span cannot close in another. The phrase is the unknown-command
# text zsh and bash print ("zsh: command not found: X", "bash: X: command not found"), which
# reaches a payload only when a substitution captured its own stderr; dash prints "X: not found"
# and is not matched, since "not found" alone is ordinary prose. A clean loss (the token and both
# backticks gone) leaves neither trace, and preventing it is the caller's shell discipline.
BACKTICK = "`"
LOST_COMMAND_RE = re.compile(r"command not found", re.IGNORECASE)


def payload_traces(named):
    """(argument, reason) for each trace in the caller's text, in the order the verb lists them."""
    found = []
    for name, value in named:
        if not value:
            continue
        ticks = value.count(BACKTICK)
        if ticks % 2:
            found.append((name, "carries %d backtick%s, an odd count: a code span is left open, "
                                "or a double-quoted shell argument lost a backticked token"
                                % (ticks, "" if ticks == 1 else "s")))
        if LOST_COMMAND_RE.search(value):
            found.append((name, "carries 'command not found': a command substitution ran inside "
                                "a double-quoted shell argument"))
    return found


def warn_payload(named):
    """One stderr line per trace. A warning: the text may mean exactly what it says, so the
    write goes ahead, and stdout keeps the one line a head reads."""
    for name, reason in payload_traces(named):
        sys.stderr.write("payload: %s %s\n" % (name, reason))


def stamped_status(status, date, hm):
    """The `register close` status fact, stamped: `closed DATE HH:MM — …`.

    A caller who already opened with `closed DATE` gets the time inserted after that date
    rather than a second `closed`; one who already carries a time keeps it (the token check
    is what says whether that time agrees with the clock); anything else is prefixed whole."""
    if CLOSED_TIMED_RE.match(status):
        return status
    dated = CLOSED_DATED_RE.match(status)
    if dated:
        return "%s %s%s" % (status[:dated.end()], hm, status[dated.end():])
    return "closed %s %s — %s" % (date, hm, status)


# ------------------------------------------------------- reads, the lock, the check ------

class Snapshot(object):
    """One read of a target: the hash of its bytes, and the text decoded from exactly them."""
    __slots__ = ("path", "sha", "text")

    def __init__(self, path, data):
        self.path = path
        self.sha = hashlib.sha256(data).hexdigest()
        self.text = data.decode("utf-8")


def read_snapshot(verb, path):
    """The register and IDEAS are read whole, once; the log never is."""
    if not os.path.isfile(path):
        die(verb, "no file at %s" % path)
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        die(verb, "cannot read %s: %s" % (path, exc.strerror or exc))
    try:
        return Snapshot(path, data)
    except UnicodeDecodeError:
        die(verb, "%s is not UTF-8" % path)


def take_lock(verb, path):
    """Hold the lock on the target's directory until main() releases it.

    A directory, not a lock file: nothing is created beside the target, and closing the
    descriptor (or the process ending) releases it, so a killed run never leaves it behind.
    The lock is a premise of every checked write: without it two runs of this tool could both
    pass their checks and one replace the other's result, so a platform without flock, a
    directory that cannot be opened or locked, and a lock held past LOCK_WAIT each refuse
    here, before the target is read."""
    if not os.path.isfile(path):
        die(verb, "no file at %s" % path)
    directory = os.path.dirname(os.path.abspath(path))
    if fcntl is None:
        die(verb, "this platform has no flock, so this run cannot keep other runs of this tool out of "
                  "%s while it writes; nothing written" % directory)
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError as exc:
        die(verb, "cannot open %s to lock it (%s); nothing written" % (directory, exc.strerror or exc))
    _LOCKS.append(descriptor)
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                die(verb, "another run of this tool has held the lock on %s for %g s; "
                          "nothing written" % (directory, LOCK_WAIT))
            time.sleep(LOCK_POLL)
        except OSError as exc:
            die(verb, "cannot lock %s (%s), so this run cannot keep other runs of this tool out "
                      "while it writes; nothing written" % (directory, exc.strerror or exc))


def release_locks():
    """Close every lock descriptor this run holds; closing one releases its flock."""
    while _LOCKS:
        try:
            os.close(_LOCKS.pop())
        except OSError:
            pass


def reread(path):
    """The target read again through one descriptor: (its stat at that open, its bytes)."""
    with open(path, "rb") as handle:
        seen = os.fstat(handle.fileno())
        data = handle.read()
    return seen, data


def last_look(path):
    """The target's stat: the last look this tool takes before the caller's rename."""
    return os.stat(path)


def changed_since(snap):
    """None when the target still holds the bytes it was composed from, else the reason.

    The re-read and its hash come first; last_look() ends this function, so no work of this
    tool's own falls between it and the caller's rename. What lands after it is not seen
    (the docstring's window)."""
    path = snap.path
    try:
        seen, data = reread(path)
    except FileNotFoundError:
        return "it is gone since this run read it"
    except OSError as exc:
        return "it cannot be read again (%s)" % (exc.strerror or exc)
    now = hashlib.sha256(data).hexdigest()
    if now != snap.sha:
        return ("it changed on disk since this run read it (sha256 %s at the read, %s now)"
                % (snap.sha[:12], now[:12]))
    try:
        last = last_look(path)
    except FileNotFoundError:
        return "it is gone since this run read it"
    except OSError as exc:
        return "it cannot be looked at again (%s)" % (exc.strerror or exc)
    if ((last.st_ino, last.st_dev, last.st_size, last.st_mtime_ns)
            != (seen.st_ino, seen.st_dev, seen.st_size, seen.st_mtime_ns)):
        return "it changed on disk while this run read it again"
    return None


def atomic_write(verb, snap, text):
    """Write beside the target, fsync, check, rename: the file is whole or untouched, and a
    change another writer made before the last look is never overwritten (the window aside)."""
    path = snap.path
    directory = os.path.dirname(os.path.abspath(path))
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        mode = None
    handle_fd, tmp = tempfile.mkstemp(prefix=".vault-writes-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        reason = changed_since(snap)
        if reason is None:
            os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)          # a failed write leaves no debris beside the target
        except OSError:
            pass
        raise
    if reason is not None:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        die(verb, "%s: %s; it is left as the other writer left it and nothing was written; "
                  "re-run the command against the file as it now stands" % (path, reason))
    try:                            # the rename is durable only once the directory is
        dir_fd = os.open(directory, os.O_RDONLY)    # synced; best effort, never fatal
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def report(verb, path, line, preview, dry_run):
    """The whole of the output of a verb: one line, or the bounded block of a dry run."""
    if not dry_run:
        print("ok %s %s:%d" % (verb, path, line))
        return
    print("dry-run %s %s:%d" % (verb, path, line))
    for item in preview[:PREVIEW_MAX]:
        print("| %s" % item)
    if PREVIEW_MAX < len(preview):
        print("| + %d more lines" % (len(preview) - PREVIEW_MAX))


def line_terminator(line):
    """A file that arrived with CRLF keeps its CR on the line this run edits."""
    return "\r" if line.endswith("\r") else ""


# ------------------------------------------------------------------ log-append ---------

def log_tail(path, count=2):
    """The last bytes, by seek. The log is append-only and is never held in memory."""
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        handle.seek(max(0, size - count))
        return handle.read()


def log_line_count(path):
    """Newlines, counted in bounded chunks — again, never the whole file in memory."""
    total = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            total += chunk.count(b"\n")
    return total


def log_separator(tail):
    """Whatever it takes for exactly one blank line to sit above the new heading.

    An entry is written ending in a blank line, so a file whose tail is already a blank
    line needs nothing; one ending mid-line needs that line finished first."""
    if not tail:
        return ""                       # an empty log: the heading is line 1
    if tail.endswith(b"\n\n"):
        return ""
    if tail.endswith(b"\n"):
        return "\n"
    return "\n\n"


def cmd_log_append(args):
    verb = "log-append"
    path = os.path.join(args.vault, LOG_REL)
    if args.action not in ACTIONS:
        die(verb, "--action '%s' is none of: %s" % (args.action, " ".join(ACTIONS)))
    date = check_date(verb, args.date)
    title = check_text(verb, "--title", args.title)
    changed = check_text(verb, "--changed", args.changed)
    conflicts = check_text(verb, "--conflicts", args.conflicts)
    extras = []
    named = [("--title", title), ("--changed", changed), ("--conflicts", conflicts)]
    for raw in args.extra or []:
        check_text(verb, "--extra", raw)
        if ":" not in raw:
            die(verb, "--extra '%s' is not 'Key: value'" % short(raw))
        key, value = raw.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            die(verb, "--extra '%s' needs a key and a value" % short(raw))
        # The bullet and the bold are this verb's own: a key already shaped as one would be
        # wrapped again, `- **- **Key****: …` (register entry of 2026-10-03 00:25), into a log
        # that is never rewritten. Refused before the file is opened, so nothing lands.
        if key.startswith("- ") or "**" in key:
            die(verb, "--extra key '%s' is already shaped as a bullet; pass the bare 'Key: value' "
                "and the verb writes '- **Key**: value'" % short(key))
        extras.append((key, value))
        named.append(("--extra %s" % key, raw))
    if not os.path.isfile(path):
        die(verb, "no file at %s" % path)

    now = clock_now()
    warn_clock(now, [title, changed, conflicts] + [raw for raw in args.extra or []])
    warn_payload(named)
    # The heading shape is a schema surface and stays `## [DATE] ACTION | TITLE`, so the time
    # rides in a bullet instead — first among the extras, where it sits under the heading's
    # own date and does not move when the caller passes more of them.
    extras.insert(0, ("Clock", "%s %s" % (clock_hm(now), clock_zone(now))))

    block = ["## [%s] %s | %s" % (date, args.action, title),
             "- **Changed**: %s" % changed]
    for key, value in extras:
        block.append("- **%s**: %s" % (key, value))
    block.append("- **Conflicts**: %s" % conflicts)

    separator = log_separator(log_tail(path))
    payload = separator + "\n".join(block) + "\n\n"
    heading_line = log_line_count(path) + separator.count("\n") + 1

    if args.dry_run:
        report(verb, path, heading_line, block, True)
        return
    with open(path, "a", encoding="utf-8") as handle:   # append only, never a rewrite
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    report(verb, path, heading_line, block, False)


# -------------------------------------------------------------------- register ---------

def heading_index(verb, lines, heading):
    """The one line that IS the heading. Not one, not the register this code knows: refuse."""
    hits = [i for i, line in enumerate(lines) if line == heading]
    if len(hits) != 1:
        die(verb, "'%s' is %d lines of the register, not 1" % (heading, len(hits)))
    return hits[0]


def register_anchors(verb, lines):
    """Both section headings, asserted once each and in the order the register keeps them."""
    open_at = heading_index(verb, lines, OPEN_HEAD)
    closed_at = heading_index(verb, lines, CLOSED_HEAD)
    if closed_at < open_at:
        die(verb, "'%s' (line %d) sits above '%s' (line %d)"
            % (CLOSED_HEAD, closed_at + 1, OPEN_HEAD, open_at + 1))
    return open_at, closed_at


def first_body_index(lines, head_at):
    """Where the first entry of a section starts: the blank line under the heading is kept."""
    index = head_at + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def entry_end(lines, start, stop):
    """The next heading after an entry's own: the end of its span as the register reads it."""
    index = start + 1
    while index < stop and not ENTRY_END_RE.match(lines[index]):
        index += 1
    return index


def entry_extent(lines, start, stop):
    """(last, cut) for the entry headed at `start`: its own lines are lines[start:last + 1],
    and lines[last + 1:cut] are the blank lines after them, which leave with it on a close.

    Blank lines never end an entry. The first line that is neither blank nor one of its own
    (see the docstring) does, and so does any heading."""
    last, index, body = start, start + 1, 0
    while index < stop:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if ENTRY_END_RE.match(line):
            break
        own = (OWN_BOLD_RE.match(line) or OWN_INDENTED_RE.match(line)
               or (body == 0 and OWN_FIRST_DATED_RE.match(line)))
        if not own:
            break
        last, body, index = index, body + 1, index + 1
    cut = last + 1
    while cut < stop and not lines[cut].strip():
        cut += 1
    return last, cut


def foreign_line(lines, start, last):
    """(index, why) for the first of an entry's own lines that is another entry's, else None."""
    seen, body, status = set(), 0, None
    for index in range(start + 1, last + 1):
        line = lines[index]
        if not line.strip():
            continue
        if body and FOREIGN_DATED_RE.match(line):
            return index, "a bullet opening with a date below the first, the shape of an entry"
        once = ONCE_FIELD_RE.match(line)
        if once:
            if once.group(1) in seen:
                return index, "a second '%s' field: two entries under one heading" % once.group(1)
            seen.add(once.group(1))
        if STATUS_FIELD_RE.match(line):
            if status is not None:
                return index, "a second 'Status' field: two entries under one heading"
            status = index
        body += 1
    return None


def status_below(lines, last, stop):
    """The index of a Status field under the same heading but past the entry's own lines."""
    end = entry_end(lines, last, stop)
    for index in range(last + 1, end):
        if STATUS_FIELD_RE.match(lines[index]):
            return index
    return None


def entry_structure(verb, lines, start, stop):
    """(last, cut, fields): the entry's own lines (see entry_extent) and the indices of its
    Status fields, refused where its structure cannot be read — another entry inside its own
    lines, or a Status field under the same heading below a line that is not its own. A close
    and an annotation read an entry through this one function, so neither can take an entry
    the other would refuse. A dated note written date-first is the same shape as a one-line
    entry, so it refuses too, and the message says how such a note is written instead."""
    last, cut = entry_extent(lines, start, stop)
    foreign = foreign_line(lines, start, last)
    if foreign:
        die(verb, "the entry '%s' holds another entry at line %d (%s); nothing written; a dated "
                  "note of this entry opens with its kind (Status, Recurrence or Correction), as "
                  "register annotate writes it" % (short(lines[start]), foreign[0] + 1, foreign[1]))
    below = status_below(lines, last, stop)
    if below is not None:
        die(verb, "the entry '%s' carries a '**Status**' field at line %d, below line %d, which is "
                  "not one of its own lines; nothing written" % (short(lines[start]), below + 1, cut + 1))
    fields = [i for i in range(start + 1, last + 1) if STATUS_FIELD_RE.match(lines[i])]
    return last, cut, fields


def left_in_place(lines, cut, stop):
    """The lines a close leaves where they were: from `cut` to the next heading, as (first, count)
    of the non-blank ones, or None when the entry's own lines run to that heading."""
    end = entry_end(lines, cut - 1, stop) if cut < stop else stop
    kept = [i for i in range(cut, end) if lines[i].strip()]
    return (kept[0], len(kept)) if kept else None


def open_entry(verb, lines, open_at, closed_at, match):
    """The one Open heading `--match` names; any other count refuses."""
    hits = [i for i in range(open_at + 1, closed_at)
            if lines[i].startswith("### ") and match in lines[i]]
    if len(hits) != 1:
        die(verb, "'%s' matches %d entry headings under '%s', not 1"
            % (short(match), len(hits), OPEN_HEAD))
    return hits[0]


def unique_stamp(verb, lines, date, hm):
    """The stamp `register add` writes: `DATE HH:MM`, or that and a suffix letter when another
    heading already carries it (see the docstring). Refuses where it cannot tell.

    Every heading whose bracket opens with the candidate date and time is read first, closed
    or not, and only then is its complete form checked: one that never closes its bracket, or
    closes it on any form but the bare stamp or one suffix letter, cannot be read."""
    base = "%s %s" % (date, hm)
    taken = {}
    for number, line in enumerate(lines, 1):
        found = STAMP_OPEN_RE.match(line.rstrip("\r"))
        if not found:
            continue
        opened = found.group(1)
        if not " ".join(opened.split()).startswith(base):
            continue
        closing = opened.find("]")
        if closing < 0:
            die(verb, "line %d heads an entry whose stamp opens with %s and never closes its bracket "
                      "([%s), a form this check cannot read; nothing written" % (number, base, short(opened)))
        inner = " ".join(opened[:closing].split())
        rest = inner[len(base):] if inner.startswith(base) else None
        if rest == "":
            suffix = ""
        elif rest is not None and len(rest) == 2 and rest[0] == " " and rest[1] in STAMP_SUFFIXES:
            suffix = rest[1]
        else:
            die(verb, "line %d heads an entry [%s], a form of the stamp %s this check cannot read; "
                      "nothing written" % (number, short(inner), base))
        taken[suffix] = taken.get(suffix, 0) + 1
    for suffix in sorted(taken):
        if taken[suffix] > 1:
            stamp = base + (" " + suffix if suffix else "")
            die(verb, "the stamp [%s] already heads %d entries, so it names none of them; no further "
                      "entry is added under %s: retry in the next minute, or give one of those "
                      "headings a suffix by hand" % (stamp, taken[suffix], base))
    for suffix in [""] + list(STAMP_SUFFIXES):
        if suffix not in taken:
            return base + (" " + suffix if suffix else "")
    die(verb, "the stamp %s and every suffix from b to z already head entries; nothing written" % base)


def cmd_register_add(args):
    verb = "register-add"
    path = os.path.join(args.vault, REGISTER_REL)
    date = check_date(verb, args.date)
    surface = check_text(verb, "--surface", args.surface)
    tag = re.search(r"(\(\s*(?:%s|blocking\s*·\s*major\s*·\s*minor)\s*\))\s*\.?\s*$"
                    % "|".join(SEVERITIES), surface, re.I)
    if tag:
        die(verb, "--surface already ends with severity tag %s; use --severity instead; nothing written"
            % tag.group(1))
    symptom = check_text(verb, "--symptom", args.symptom)
    cause = check_text(verb, "--cause", args.cause)
    if args.why_not_fixed_now is None:
        die(verb, "--why-not-fixed-now is missing: an entry parks a defect only for a named "
                  "reason that blocks the fix now (CLAUDE.md §12), so fix it now or name that reason")
    why = check_text(verb, "--why-not-fixed-now", args.why_not_fixed_now)
    status = check_text(verb, "--status", args.status)
    where = check_text(verb, "--where", args.where)
    if args.severity not in SEVERITIES:
        die(verb, "--severity '%s' is none of: %s" % (args.severity, " ".join(SEVERITIES)))

    now = clock_now()
    warn_clock(now, [surface, symptom, cause, why, status, where])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    open_at, _ = register_anchors(verb, lines)
    stamp = unique_stamp(verb, lines, date, clock_hm(now))

    block = ["### [%s] %s (%s)" % (stamp, surface, args.severity)]
    if where:
        block.append("- **Where observed**: %s" % where)
    block.append("- **Symptom**: %s" % symptom)
    block.append("- **Suspected cause**: %s" % cause)
    block.append("- **%s**: %s" % (WHY_LABEL, why))
    block.append("- **Status**: %s" % status)

    at = first_body_index(lines, open_at)
    if args.dry_run:
        report(verb, path, at + 1, block, True)
        return
    atomic_write(verb, snap, "\n".join(lines[:at] + block + [""] + lines[at:]))
    report(verb, path, at + 1, block, False)


def cmd_register_close(args):
    verb = "register-close"
    path = os.path.join(args.vault, REGISTER_REL)
    date = check_date(verb, args.date)
    match = check_text(verb, "--match", args.match)
    status = check_text(verb, "--status", args.status)

    now = clock_now()
    # `--match` is a locator, not text this write lands: an entry already headed with a time
    # is addressed by that time, and warning about it would be warning about the register.
    # A caller's own `closed DATE HH:MM` stamp claims the close's time, so it is checked whole
    # even though its time follows a date; the rest of the status is free text as elsewhere.
    own = CLOSED_TIMED_RE.match(status)
    warn_clock(now, [status], stamps=[own.group(0)] if own else [])
    status = stamped_status(status, date, clock_hm(now))

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    open_at, closed_at = register_anchors(verb, lines)
    start = open_entry(verb, lines, open_at, closed_at, match)
    last, cut, fields = entry_structure(verb, lines, start, closed_at)
    if len(fields) != 1:
        die(verb, "the entry '%s' carries %d '**Status**' lines, not 1"
            % (short(lines[start]), len(fields)))
    block = lines[start:last + 1]
    at_status = fields[0] - start
    tail = line_terminator(block[at_status])
    block[at_status] = "%s *(%s: %s)*%s" % (block[at_status].rstrip(), date, status, tail)

    left = left_in_place(lines, cut, closed_at)
    remainder = lines[:start] + lines[cut:]
    # The anchors move once the span is gone, so they are asserted again on the remainder.
    _, closed_after = register_anchors(verb, remainder)
    at = first_body_index(remainder, closed_after)
    preview = [block[0], block[at_status],
               "moved %d lines to the top of '%s'" % (len(block), CLOSED_HEAD)]
    if left:
        kept = ("line %d and %d more lines below this entry are not its own and stay under '%s'"
                % (left[0] + 1, left[1] - 1, OPEN_HEAD) if left[1] > 1 else
                "line %d below this entry is not its own and stays under '%s'" % (left[0] + 1, OPEN_HEAD))
        note("extent", kept)
        preview.append(kept)
    if args.dry_run:
        report(verb, path, at + 1, preview, True)
        return
    atomic_write(verb, snap, "\n".join(remainder[:at] + block + [""] + remainder[at:]))
    report(verb, path, at + 1, preview, False)


def cmd_register_annotate(args):
    verb = "register-annotate"
    path = os.path.join(args.vault, REGISTER_REL)
    match = check_text(verb, "--match", args.match)
    if args.kind not in NOTE_KINDS:
        die(verb, "--kind '%s' is none of: %s" % (args.kind, " ".join(NOTE_KINDS)))
    text = check_text(verb, "--note", args.note)
    by = check_text(verb, "--by", args.by)
    for name, value in (("--note", text), ("--by", by)):
        if value and STATUS_MARKER in value:
            die(verb, "%s carries the field marker '%s', which the register's lint reads as the "
                      "entry's Status wherever it stands; quote the field without its colon" % (name, STATUS_MARKER))
    date = check_date(verb, args.date)

    now = clock_now()
    warn_clock(now, [text, by])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    open_at, closed_at = register_anchors(verb, lines)
    start = open_entry(verb, lines, open_at, closed_at, match)
    last, _, _ = entry_structure(verb, lines, start, closed_at)
    tail = line_terminator(lines[last])
    added = "- **%s %s %s %s%s:** %s%s" % (args.kind, date, clock_hm(now), clock_zone(now),
                                          " (%s)" % by if by else "", text, tail)
    at = last + 1
    preview = [short(lines[start]), added.rstrip("\r")]
    if args.dry_run:
        report(verb, path, at + 1, preview, True)
        return
    atomic_write(verb, snap, "\n".join(lines[:at] + [added] + lines[at:]))
    report(verb, path, at + 1, preview, False)


# ----------------------------------------------------------------------- ideas ---------

def cmd_ideas_annotate(args):
    verb = "ideas-annotate"
    path = args.file
    if not ITEM_RE.match(args.item):
        die(verb, "--item '%s' is not a number" % short(args.item))
    text = check_text(verb, "--note", args.note)
    date = check_date(verb, args.date)

    now = clock_now()
    warn_clock(now, [text])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    marker = "- **%s%s**" % (NUMERO, args.item)
    hits = [i for i, line in enumerate(lines) if line.startswith(marker)]
    if len(hits) != 1:
        die(verb, "'%s' begins %d lines of %s, not 1" % (marker, len(hits), path))
    at = hits[0]
    tail = line_terminator(lines[at])
    # The note shape IDEAS.md's own HOW TO USE comment prescribes — a one-line `(agent)`
    # annotation appended to the bullet — with the clock's time beside the date.
    lines[at] = "%s *(agent %s %s: %s)*%s" % (lines[at].rstrip(), date, clock_hm(now), text, tail)

    preview = [short(lines[at])]
    if args.dry_run:
        report(verb, path, at + 1, preview, True)
        return
    atomic_write(verb, snap, "\n".join(lines))
    report(verb, path, at + 1, preview, False)


# ----------------------------------------------------------------------- entry ---------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="vault-writes.py",
        description="The hand-composed writes of the vault, one asserted anchor at a time.")
    verbs = parser.add_subparsers(dest="verb", required=True)

    log = verbs.add_parser("log-append", help="append one entry to the wiki log")
    log.add_argument("--vault", required=True, help="the vault root; the path is derived")
    log.add_argument("--action", required=True, help="one of: %s" % " ".join(ACTIONS))
    log.add_argument("--title", required=True)
    log.add_argument("--changed", required=True)
    log.add_argument("--conflicts", required=True)
    log.add_argument("--extra", action="append", metavar="KEY: VALUE",
                     help="a further bullet, between Changed and Conflicts; repeatable; the bare "
                          "key (a key starting '- ' or carrying '**' is refused)")
    log.add_argument("--date", help="YYYY-MM-DD; today when absent")
    log.add_argument("--dry-run", action="store_true", help="print the block, write nothing")

    register = verbs.add_parser("register", help="the framework defect register")
    register_verbs = register.add_subparsers(dest="register_verb", required=True)

    add = register_verbs.add_parser("add", help="a new entry at the top of the Open section")
    add.add_argument("--vault", required=True)
    add.add_argument("--date", required=True)
    add.add_argument("--surface", required=True, help="surface — short title")
    add.add_argument("--symptom", required=True)
    add.add_argument("--cause", required=True)
    add.add_argument("--why-not-fixed-now", dest="why_not_fixed_now", metavar="REASON",
                     help="required: the named reason that blocks the fix now")
    add.add_argument("--severity", required=True, help="one of: %s" % " ".join(SEVERITIES))
    add.add_argument("--status", required=True, help="verbatim, the leading 'open — ' too")
    add.add_argument("--where", help="omitted entirely when absent")
    add.add_argument("--dry-run", action="store_true", help="print the block, write nothing")

    close = register_verbs.add_parser("close", help="move one entry to the Closed section")
    close.add_argument("--vault", required=True)
    close.add_argument("--match", required=True, help="text of exactly one Open heading")
    close.add_argument("--date", required=True)
    close.add_argument("--status", required=True,
                       help="the text of the dated line; the clock stamps its time")
    close.add_argument("--dry-run", action="store_true", help="print the change, write nothing")

    annotate_entry = register_verbs.add_parser(
        "annotate", help="append one dated note to one Open entry")
    annotate_entry.add_argument("--vault", required=True)
    annotate_entry.add_argument("--match", required=True, help="text of exactly one Open heading")
    annotate_entry.add_argument("--kind", required=True, help="one of: %s" % " ".join(NOTE_KINDS))
    annotate_entry.add_argument("--note", required=True)
    annotate_entry.add_argument("--by", help="who writes it; omitted when absent")
    annotate_entry.add_argument("--date", help="YYYY-MM-DD; today when absent")
    annotate_entry.add_argument("--dry-run", action="store_true",
                                help="print the note, write nothing")

    ideas = verbs.add_parser("ideas", help="the scratchpad of the owner")
    ideas_verbs = ideas.add_subparsers(dest="ideas_verb", required=True)
    annotate = ideas_verbs.add_parser("annotate", help="append one agent note to one bullet")
    annotate.add_argument("--file", required=True)
    annotate.add_argument("--item", required=True, metavar="N")
    annotate.add_argument("--note", required=True)
    annotate.add_argument("--date", help="YYYY-MM-DD; today when absent")
    annotate.add_argument("--dry-run", action="store_true",
                          help="print the line, write nothing")
    return parser


REGISTER_VERBS = {"add": cmd_register_add, "close": cmd_register_close,
                  "annotate": cmd_register_annotate}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.verb == "log-append":
            cmd_log_append(args)
        elif args.verb == "register":
            REGISTER_VERBS[args.register_verb](args)
        else:
            cmd_ideas_annotate(args)
    finally:
        release_locks()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except OSError as exc:          # a read-only target, a full disk: one line, exit 2
        print("error vault-writes: %s" % exc)
        sys.exit(2)
