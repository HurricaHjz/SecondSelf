#!/usr/bin/env python3
"""weekly-waste.py: the weekly waste report, records only (the owner's decision D19).

Reads the run records, `<store>/spawn-records/*.jsonl`, under the owner's input contract (decision
B17 of 14 October 2026; spec-D19.md, "Input contract"; FIELDS.md, "Admission"), and nothing else:
no session transcript, no GPT-6 Astra event log, no helper report, brief or prompt, no file outside
the records folder and no per-run waste table (those are linked by path when they exist, found by a
stat, never opened). It starts no subprocess. Standard library only.

Admission is decided by name alone, for every candidate, before any file is opened: every `*.jsonl`
file directly in the records folder is a run record, whatever its run id, except the five
historical event logs pinned by exact name and the command checker's read logs, named
`<run>-unplaced-reads.jsonl` beside their run's record `<run>.jsonl` (a name of that form with no
such record beside it is a candidate like any other), which are listed in the report's coverage and
never opened. A
candidate that is a link or not a regular file is never opened either (named
unreadable). The records are acquired independently: what a record's fields name is never read,
resolved or followed, so a record that another record names as evidence is read as a run record
like any other, and the reference changes no figure, no coverage status and no other substantive
report content; the acquisition time, the measured byte counts and the folder inventory are
reported as they are (spec-D19.md, "Input contract": what a reference may and may not change).

No record content can stop the report (FIELDS.md, "The reader's range"): a number beyond the
reader's range, a timestamp finer than a nanosecond, a string that is not text or a number the
decimal library cannot hold is named invalid where it stands, never repaired, and the report
completes with every independent figure kept; a store line that cannot be read is named the same way.
Whether a value is uncertain travels in a field of its own, never in a string a record could hold:
no recorded string is read as one of the reader's labels (LABELS, every one of them, the total row of
a helper-time view included), and one that could read as a label is shown quoted (FIELDS.md,
"Recorded strings and the reader's labels"). Every sum of recorded decimals is exact, and a figure is
rounded once, where it is displayed. An identity is held as a structure, never read back out of a
string built from recorded values: an episode is its (record, helper, opening line), and the held
format's episode string `<record>:<helper>:<line>`, which a record or a helper holding ":" can make
name several openings, is applied only where it names exactly one (README.md, "The dispositions store").

Writes, and nothing else:
  - `waste-detail-<until>.md` and `waste-report-<until>.md` in the vault's `output/reports/` (or
    in `reports/` under --tools-dir), each through a temporary file and a rename, the main report last;
  - its lines in `dispositions.jsonl` in `<store>/tools/weekly-waste/`, outside the vault (or under
    --tools-dir), through one append. This script's own folder ships, so nothing is written beside
    it. The store is created only by `init`, which never overwrites; a report never creates a
    missing store.

Usage:
  weekly-waste.py [--until YYYY-MM-DD] [--since YYYY-MM-DD[THH:MM]] [--records DIR]
                  [--tools-dir DIR] [--tables-dir DIR]
  weekly-waste.py init [--tools-dir DIR]
  weekly-waste.py dispose KEY {fixed,registered,kept,owner} --note TEXT [--tools-dir DIR]
  weekly-waste.py abandon EPISODE --evidence TEXT [--record NAME --helper NAME --line N]
                          [--records DIR] [--tools-dir DIR]
  weekly-waste.py end-run RUN --evidence TEXT [--records DIR] [--tools-dir DIR]

Exit codes: 0 the report and detail were written and the store lines appended; 1 both were
written but the store is missing, unreadable or malformed (the report opens with it, and a
missing or unreadable store is never recreated); 2 a bad argument or a broken premise (no
records folder, no candidate record, no admitted record (only names left out), no reports
folder, an empty interval; for a subcommand, its refusal): `PROBE FAILED: ...` on stderr, nothing
written.

The field-to-figure contract, with every field's writer and line, is FIELDS.md beside this file.
"""

import argparse
import calendar
import difflib
import json
import os
import re
import stat
import sys
import time
from contextlib import contextmanager
from collections import namedtuple
from decimal import Decimal, ROUND_HALF_EVEN, Inexact, Rounded, localcontext
from fractions import Fraction

VERSION = "records-only-11"

PURPOSE = ("The weekly report shows recorded helper consumption and recorded operational outcomes "
           "across runs, so the Sunday review can identify concentrations and possible recurrence. "
           "It does not measure avoidable time or certify that a week contained no waste. "
           "Fine-grained diagnosis remains in each run's own evidence.")

GUIDANCE = ("Whether repeated review of one item was a loop is judged in the Sunday walk-through "
            "under CUSTOMISATION.md's rules \"Rounds are judged by progress, not counted\" and "
            "\"Stopped designs\".")

HELPER, FAILED, REVIEW, BOUNDARY, REFUSALS, SPEND = (
    "Helper time", "Failed closes", "Review activity and possible loops", "Phase boundaries",
    "Refusals", "Priced spend")
FIGURES = (HELPER, FAILED, REVIEW, BOUNDARY, REFUSALS, SPEND)
FIGURE_KEYS = {HELPER: "helper-time", FAILED: "failed-closes", REVIEW: "review-activity",
               BOUNDARY: "phase-boundaries", REFUSALS: "refusals", SPEND: "priced-spend"}

# The parts of the figures an input can feed. A named gap carries the parts it affects, the run
# (record stem) it sits in, and, where its own line establishes them, the helper and the class;
# each rendered total counts only the gaps that reach its own part, run, helper or class.
P_H = HELPER
P_F = FAILED
P_RVC = REVIEW + ": reviewing-class episodes"
P_RVG = REVIEW + ": positional groups"
P_B = BOUNDARY
P_BS = BOUNDARY + ": rewrites snapshots"
P_RFT = REFUSALS + ": helper tool"
P_RFF = REFUSALS + ": helper fence"
P_RFS = REFUSALS + ": helper sandbox"
P_RFH = REFUSALS + ": head fence"
P_RFB = REFUSALS + ": boundary summary"
P_SC = SPEND + ": closes"
P_SP = SPEND + ": plan usage"
P_SB = SPEND + ": hold beats"
P_SS = SPEND + ": snapshots"
EPISODE_PARTS = (P_H, P_F, P_RVC, P_RVG, P_RFT, P_RFF, P_RFS, P_SC)
ALL_PARTS = (P_H, P_F, P_RVC, P_RVG, P_B, P_BS, P_RFT, P_RFF, P_RFS, P_RFH, P_RFB, P_SC, P_SP,
             P_SB, P_SS)
CHANNEL_PART = {"tool": P_RFT, "fence": P_RFF, "sandbox": P_RFS}

# Episode lines. The writers' names, and the historical names read by a documented compatibility
# rule (FIELDS.md, "Historical event names"): each reads as the writers' opening or close, its
# values from the writers' field names only, so a field it lacks is unknown, never inferred.
OPENINGS = ("lane-open", "lane-resumed")
CLOSES = ("lane-closed",)
HIST_OPENINGS = {"lane-resume": "lane-resumed", "spawn": "lane-open", "probe-open": "lane-open"}
HIST_CLOSES = {"lane-close": "lane-closed", "close-out": "lane-closed",
               "close-out-2": "lane-closed", "probe-closed": "lane-closed"}
# Historical end markers: they record that a helper's process ended or stalled, but they are not
# a close (in their own records a close-out follows them), so they resolve no episode; each is
# noted on the episode it follows.
END_MARKERS = ("terminated", "stalled", "lane-aborted")
ALL_OPENINGS = OPENINGS + tuple(sorted(HIST_OPENINGS))
ALL_CLOSES = CLOSES + tuple(sorted(HIST_CLOSES))

# The parts each event kind feeds. A line whose kind cannot be established feeds every part.
KIND_PARTS = dict((k, EPISODE_PARTS) for k in ALL_OPENINGS + ALL_CLOSES)
KIND_PARTS.update({"phase-boundary": (P_B, P_BS, P_RFH, P_RFB, P_SS), "gate": (P_RVG, P_SS),
                   "hold-beat": (P_SB,), "head-exit": (P_SS,), "run-close": (P_SS,)})

# The known event names: every name the granted writers emit (lane.py, codex-lane.py,
# handsoff.py; FIELDS.md cites each one a figure reads) and every further name present in the
# run store when this build read it (historical, hand-written lines). Any other name, a misspelt
# one included, makes its line invalid, never ignored. `lane-awake`, the keep-awake line both
# wrappers write after `lane-spawned` or `lane-respawned` (lane.py AWAKE_EVENT; FIELDS.md,
# "Episodes"), and `stop-requested`, the line lane.py writes when a stop is asked of a running pass
# (a3_request_stop; FIELDS.md, "Episodes"), are known names that feed no figure.
KNOWN_EVENTS = frozenset("""
apply c13-fold-applied carriers-shipped close-out close-out-2 controls correction decision
design-filed duplicate-head durable-transcript envelope expect-items fast-armed fast-disarmed
fixture-defect fixtures-built fixtures-cleaned g3r-verdict-attempt-1 g3r-verdict-attempt-2 gate
grants guard-probe guard-probe-result hand-off head-arm-compiled head-exit head-resumed head-slice
head-successor heartbeat hold hold-beat hold-ended install lane-aborted lane-awake lane-close lane-closed
lane-event lane-open lane-report-persisted lane-respawned lane-resume lane-resumed lane-session
lane-spawned lane-swapped lanes-spawned live-observation note observation owner-correction
owner-rulings peer-critic-interrupted peer-stood-down phase-boundary phase-gate planned
plant-confirmed plant-recorded planted-controls probe-closed probe-open record-correction
reflect-inputs routing-phase4-passed-gates-shipped run-close run-closed run-note run-open
run-resume scope-review scope-verdict session-handoff shipped spawn spawn-planned stall stalled
stop-condition stop-requested successor-aborted supervise supervisor-stood-down terminated
throttle-phase3-shipped throttle-phase4-shipped unwatched verdict verify-dir-v3
""".split())

# The exit classes the writers emit (lane.py classify, its watch and kill closes and its
# spawn failure; codex-lane.py classify, its kill and its spawn failure). Any other recorded
# value is shown as recorded and counted as outside this vocabulary, neither completed nor not.
WRITER_EXIT_CLASSES = frozenset(("completed", "stall", "deadline", "limit", "refusal", "budget",
                                 "error", "empty", "failed", "killed", "spawn-failed",
                                 "watch-closed"))

# Reviewing classes: the helper classes whose role is to review another's work (set by
# judgement from the class names, unmeasured). A class is not evidence that an episode reviewed
# anything: the figure calls these reviewing-class episodes, never reviews.
REVIEW_CLASSES = ("critic", "verifier", "gate-judge")
GATE_DECISIONS = ("allow", "refuse")      # handsoff.py:4825-4827, 4857-4860

# Admission (FIELDS.md, "Admission"): the owner's input contract (decision B17; spec-D19.md, "Input
# contract"), decided by name for every candidate before any file is opened. Every `*.jsonl`
# file directly in the records folder is a run record (a run's record is `<run>.jsonl`, lane.py:577,
# handsoff.py:1340, whatever its run id), except the historical GPT-6 Astra event logs pinned by
# exact name and the command checker's read logs below; every other file a writer puts there has
# another extension (lane.py:573-583, codex-lane.py:976-984).
PINNED_EVENT_LOGS = frozenset("run-20260909-n14-accept-events-L%s.jsonl" % n for n in ("1", "2", "3", "5", "6"))
# The command checker's read log: lane-fence.py's read logging appends one line per cleared command
# holding a read it cannot place to `<run>-unplaced-reads.jsonl` in the records folder, `<run>` a run
# id of `[A-Za-z0-9._-]{1,128}`, and only while the run's own record `<run>.jsonl` is a regular file
# there (lane-fence.py: UNPLACED_LOG_SUFFIX, RUN_ID, record_unplaced_reads). Its lines carry no `event`
# (`v`, `ts`, `who`, `sid`, `cwd`, `n`, `reads`, `cmd`, `cut`): evidence under a run record's
# extension, left out by its name like the pinned event logs, the owner's B17 extended to it (approved
# 25 October 2026; FIELDS.md, "Admission"), but only beside `<run>.jsonl` in the same listing, so a run
# whose own id ends in `-unplaced-reads` is never left out unseen (CR-WW1 finding 6). Any other name
# ending so is a candidate like any other.
READ_LOG_NAME = re.compile(r"[A-Za-z0-9._-]{1,128}-unplaced-reads\.jsonl")
READ_LOG_SUFFIX = "-unplaced-reads.jsonl"
# The dated snapshots each event kind declares (FIELDS.md, "Snapshots"): (field, part).
SNAPSHOT_FIELDS = {"phase-boundary": (("rewrites_total", P_BS), ("run_spend_usd", P_SS)),
                   "gate": (("run_spend_usd", P_SS),), "run-close": (("run_spend_usd", P_SS),),
                   "head-exit": (("spent_usd", P_SS),)}
PLAIN_SHAPE = "plain-lane-run"        # handsoff.py:1423, 7881: a plain run's close and its fields

DISPOSITIONS = ("fixed", "registered", "kept", "owner")
STORE_KINDS = ("init", "report", "listed", "disposition", "abandoned", "run-ended")
TOP_VIEW = 3              # rows of each helper-time view in the main report (set by judgement)

MISSING = object()


class Probe(Exception):
    """A broken premise: the run writes nothing and exits 2."""


# ------------------------------------------------------------------------ time ------------

TS_RE = re.compile(r"\A([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2})"
                   r"(?::([0-9]{2})(?:\.([0-9]+))?)?(Z|[+-][0-9]{2}:?[0-9]{2})\Z")
# The most digits a fraction of a second may hold: nanoseconds, the finest any clock on the writers'
# machines reports (set by judgement, unmeasured; the writers write whole seconds, lane.py:2298-2299,
# handsoff.py:1343-1344, and no line in the store has a fraction). A longer one is no usable time, so
# the integer read of its digits is bounded (past 4,300 digits it raises in Python 3.11 and later).
TS_FRACTION_DIGITS = 9


def parse_ts(value):
    """An exact epoch (Fraction) from a well-formed ISO 8601 timestamp with its offset, or None.
    Nothing is normalised: every field must be in range, a fraction of a second has at most
    TS_FRACTION_DIGITS digits, and a stamp without an offset is no time at all (every writer writes
    one: lane.py:2298-2299, handsoff.py:1343-1344)."""
    if not isinstance(value, str):
        return None
    m = TS_RE.match(value)
    if not m or (m.group(7) and len(m.group(7)) > TS_FRACTION_DIGITS):
        return None
    y, mo, d, hh, mi = (int(m.group(i)) for i in range(1, 6))
    ss = int(m.group(6) or 0)
    if y < 1 or not 1 <= mo <= 12 or hh > 23 or mi > 59 or ss > 59:
        return None
    if not 1 <= d <= calendar.monthrange(y, mo)[1]:
        return None
    tz = m.group(8)
    offset = 0
    if tz != "Z":
        digits = tz[1:].replace(":", "")
        if len(digits) != 4:
            return None
        oh, om = int(digits[:2]), int(digits[2:])
        if oh > 23 or om > 59:
            return None
        offset = (oh * 3600 + om * 60) * (1 if tz[0] == "+" else -1)
    epoch = Fraction(calendar.timegm((y, mo, d, hh, mi, ss, 0, 0, 0)) - offset)
    if m.group(7):
        epoch += Fraction(int(m.group(7)), 10 ** len(m.group(7)))
    return epoch


def wall_epochs(y, mo, d, hh=0, mi=0, ss=0):
    """Every epoch whose local wall time is this one: none for a time the local clock skips, two for one
    it repeats."""
    found = set()
    for dst in (0, 1):
        try:
            e = int(time.mktime((y, mo, d, hh, mi, ss, 0, 0, dst)))
        except (OverflowError, ValueError):
            continue
        if time.localtime(e)[:6] == (y, mo, d, hh, mi, ss):
            found.add(e)
    return found


def local_epoch(y, mo, d, hh=0, mi=0):
    """The one epoch of a local wall time, refusing a time the local clock skips or repeats."""
    found = wall_epochs(y, mo, d, hh, mi)
    if len(found) != 1:
        raise Probe("local time %04d-%02d-%02d %02d:%02d %s on this clock"
                    % (y, mo, d, hh, mi, "does not exist" if not found else "is ambiguous"))
    return found.pop()


def parse_day(text, what):
    m = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})(?:T([0-9]{2}):([0-9]{2}))?", text or "")
    if not m:
        raise Probe("%s %r is not YYYY-MM-DD%s" % (what, text, "[THH:MM]" if what == "--since" else ""))
    if m.group(4) and what != "--since":
        raise Probe("%s takes a date only" % what)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mi = int(m.group(4) or 0), int(m.group(5) or 0)
    if not (1 <= mo <= 12 and 1 <= d <= calendar.monthrange(y, mo)[1] and hh < 24 and mi < 60):
        raise Probe("%s %r is not a valid local time" % (what, text))
    return local_epoch(y, mo, d, hh, mi)


def fmt_local(t, seconds=True):
    """A local time with its offset; fractional seconds kept as recorded."""
    if t is None:
        return "undated"
    whole = int(t // 1)
    frac = t - whole
    lt = time.localtime(whole)
    text = time.strftime("%Y-%m-%d %H:%M" + (":%S" if seconds else ""), lt)
    if frac and seconds:
        # The fraction's denominator divides 10^TS_FRACTION_DIGITS, so its quotient ends within nine
        # places and is exact; it is printed in fixed point, never in scientific notation, which
        # dropped a fraction such as .000000001 (CR-WASTE5 finding 3).
        digits = format(Decimal(frac.numerator) / Decimal(frac.denominator), "f")
        text += digits[1:] if digits.startswith("0.") else ""
    return text + " " + time.strftime("%z", lt)


def iso_local(t):
    lt = time.localtime(int(t))
    return time.strftime("%Y-%m-%dT%H:%M:%S", lt) + time.strftime("%z", lt)


def iso_exact(t):
    """An exact epoch as an ISO 8601 local time with its offset, its fraction of a second kept to the last
    digit, so parse_ts reads it back as the same instant: a determination's record extent, compared as an
    instant, never as text (a whole-second local string was the same text for two instants, and other text
    for the same instant under another zone or offset form)."""
    t = Fraction(t)
    whole = int(t // 1)
    lt = time.localtime(whole)
    text = time.strftime("%Y-%m-%dT%H:%M:%S", lt)
    frac = t - whole
    if frac:
        # As fmt_local: the denominator divides 10^TS_FRACTION_DIGITS, so the quotient is exact.
        text += format(Decimal(frac.numerator) / Decimal(frac.denominator), "f")[1:]
    return text + time.strftime("%z", lt)


def endpoint_seconds(t):
    lt = time.localtime(int(t // 1))
    return t % 1 != 0 or lt.tm_sec != 0 or wall_epochs(*lt[:6]) != {t}


def interval_label(start, end):
    """The interval as the reports and the store's keys name it: each end as its local date at a local
    midnight, as its local date and minute on any other whole minute, and as its full local time with
    its offset otherwise (a start a store line set within a minute, or a wall time the clock repeats),
    so no two intervals share a label and no disposition key names two intervals."""
    def one(t):
        lt = time.localtime(int(t // 1))
        if t % 1 == 0 and lt.tm_sec == 0 and wall_epochs(*lt[:6]) == {t}:
            return time.strftime("%Y-%m-%d" if (lt.tm_hour, lt.tm_min) == (0, 0) else "%Y-%m-%dT%H:%M", lt)
        return iso_exact(t)
    return "%s..%s" % (one(start), one(end))


# ------------------------------------------------------------------------ numbers ---------

def isnum(v):
    return (isinstance(v, (int, Decimal)) and not isinstance(v, bool)
            and (not isinstance(v, Decimal) or v.is_finite()))


def isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


# The reader's range (FIELDS.md, "The reader's range"). Every recorded number the reader sums, rounds
# or renders is read only within it: a magnitude below 10^RANGE_DIGITS, and at most RANGE_PLACES
# places after the decimal point as written. Any other is invalid and named, so that no sum can
# overflow the decimal context and no exact rendering of a recorded value can run to millions of
# digits (each of which aborted the whole report). Set by judgement, unmeasured, with headroom over the
# largest values the run store holds when this was built (evidence-B-WASTE13/value-survey.txt):
# magnitude 110,144,929 (one close's input tokens), 19 decimal places (one price). Within it every sum
# is exact (xadd) and every displayed rounding is done once, under a precision taken from the number
# itself (round_to, fmt_secs), never under the default context's 28 digits, which rounded a sum such
# as 0.025 + 1e-30 to 0.025 (CR-WASTE5 finding 2).
RANGE_DIGITS = 15
RANGE_PLACES = 30


def beyond(v):
    """Why a recorded number (an int, or a finite Decimal as JSON wrote it) lies beyond the reader's
    range, or None. Read from the number's own exponent and digits, never by arithmetic that could
    itself overflow; a zero has no magnitude, so only its places can lie beyond."""
    if isinstance(v, Decimal):
        if not v.is_zero() and v.adjusted() >= RANGE_DIGITS:
            return "beyond the reader's range (magnitude too large)"
        if v.adjusted() < -RANGE_PLACES or v.as_tuple().exponent < -RANGE_PLACES:
            return "beyond the reader's range (too many decimal places)"
        return None
    if not -10 ** RANGE_DIGITS < v < 10 ** RANGE_DIGITS:
        return "beyond the reader's range (magnitude too large)"
    return None


def xadd(a, b):
    """a + b exactly (CR-WASTE5 finding 2): two numbers within the reader's range, or exact sums of
    them, added under a precision P taken from their own digits, from the larger's leading digit to
    the smaller's last place, plus two: each operand, aligned to that last place, is below 10^(P-1),
    so their sum is below 10^P and keeps every digit, whatever the number of addends; never under the
    default context's 28 digits. The traps would make a rounding loud; that precision rules one out.
    A zero adds nothing, whatever its exponent, and is never aligned."""
    a, b = Decimal(a), Decimal(b)
    if b.is_zero():
        return a
    if a.is_zero():
        return b
    low = min(a.as_tuple().exponent, b.as_tuple().exponent)
    with localcontext() as ctx:
        ctx.prec = max(a.adjusted(), b.adjusted()) - low + 2
        ctx.traps[Inexact] = ctx.traps[Rounded] = True
        return a + b


def round_to(d, step):
    """d rounded half-even to the place of STEP (Decimal("0.01"): the cent), once, from its exact
    value, under a precision taken from d's own digits down to that place, so the rounding never needs
    more than the context holds, whatever the total."""
    d = Decimal(d)
    if d.is_zero():
        return Decimal(0).quantize(step)
    with localcontext() as ctx:
        ctx.prec = max(d.adjusted(), 0) - step.as_tuple().exponent + 2
        return d.quantize(step, rounding=ROUND_HALF_EVEN)


def fmt_dec(d, min_places=0):
    s = format(Decimal(d), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if min_places:
        whole, _, frac = s.partition(".")
        s = whole + "." + frac.ljust(min_places, "0")
    return s


def fmt_secs(d):
    """Seconds as summed, exactly, and minutes rounded half-even to 0.1 once, from the exact value:
    tenths of a minute are d / 6, a fraction rounded to the nearest integer (half to even), so no
    intermediate quotient is rounded first (CR-WASTE5 finding 2). A duration is never negative."""
    tenths = round(Fraction(Decimal(d)) / 6)
    return "%s s (%d.%d min)" % (fmt_dec(d), tenths // 10, tenths % 10)


def fmt_usd(d):
    """Dollars rounded half-even to the cent for the main report, once, from the exact total; the
    detail keeps each recorded value as written."""
    return "$" + fmt_dec(round_to(d, Decimal("0.01")), 2)


def plural(n, word, words=None):
    return "%d %s" % (n, word if n == 1 else (words or word + "s"))


def int_kind(v):
    """The kind of a value where a count belongs: a fraction is named as one."""
    return "a non-integer number" if isinstance(v, Decimal) else kind_of(v)


def kind_of(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "a boolean"
    if isinstance(v, (int, Decimal)):
        return "a number"
    if isinstance(v, str):
        return "a string"
    if isinstance(v, list):
        return "a list"
    if isinstance(v, dict):
        return "an object"
    return type(v).__name__


# Recorded strings and the reader's labels (FIELDS.md; CR-WASTE5 finding 1, CR-WASTE6 finding 3). Where
# the reports print one of the reader's own labels in a place a recorded value can hold (an unusable
# class, the unrecorded idle source, an unusable lane, None for a field absent or null as recorded, the
# total row of a helper-time view), the label is one of LABELS, each a parenthesised phrase or None, and
# whether the value is uncertain is carried in a field of its own (a key's state, a Reason's group),
# never read back from a string a record could hold. A recorded string that could read as a label, or
# as another value's rendering, is shown quoted.

def shown(v):
    """A recorded string as the reports show it where a label could stand in its place: as written,
    unless it is one of the labels (LABELS), begins with a parenthesis or a quotation mark, has white
    space at either end or holds a character that does not print (a line break, a zero-width space):
    then its repr, which begins with a quotation mark. So no recorded string renders as a label (each
    is in LABELS, and begins with a parenthesis or is None), none renders as another, and none hides in
    white space."""
    if v in LABELS or v[:1] in "('\"" or v != v.strip() or not v.isprintable():
        return repr(v)
    return v


def as_recorded(v):
    """A field's value as recorded, in the detail's boundary and beat lines: a string by shown(), an
    absent or null field as the label ABSENT_FIELD (None), any other value as Python prints it."""
    if isinstance(v, str):
        return shown(v)
    return ABSENT_FIELD if v is None else "%s" % (v,)


class Reason(str):
    """A named gap's reason as the detail prints it, carrying its group for the coverage section in a
    field of its own: the reason with each recorded value it quotes replaced by '…' (a count by N), set
    where the reason is made, so no recorded value reaches the grouping (CR-WASTE5 finding 1). A plain
    string, which quotes no recorded value, is its own group."""
    group = None


def noted(text, group):
    r = Reason(text)
    r.group = group
    return r


# ------------------------------------------------------------------------ records ---------

class Bad(ValueError):
    pass


def _members(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Bad("a duplicated member %r" % k)
        out[k] = v
    return out


def _constant(name):
    raise Bad("a non-finite number %s" % name)


def _decimal(text):
    """A JSON number with a fraction or an exponent, read exactly. One whose exponent the decimal
    library cannot hold (beyond about 10^18) raises its InvalidOperation, which is no ValueError: its
    line is named, like a NaN, never left to stop the report."""
    try:
        return Decimal(text)
    except ArithmeticError:
        raise Bad("a number the reader cannot represent (%s)" % (text if len(text) <= 40 else text[:37] + "..."))


# A string a line's JSON escapes can write but no text holds: a UTF-16 surrogate with no partner (an
# escaped pair is decoded to its one character first). Only an escape can write one, since the line's
# bytes are decoded as strict UTF-8; a report holding it cannot be written as UTF-8.
SURROGATE_ESCAPE = re.compile(r"\\u[dD][89a-fA-F]")
LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def unpaired_surrogate(obj):
    """The first unpaired surrogate in any string of a parsed line (a member's name or a value, at any
    depth), or None; read with a stack of its own, so no depth can exhaust the interpreter's."""
    stack = [obj]
    while stack:
        v = stack.pop()
        if isinstance(v, dict):
            for k, x in v.items():
                m = LONE_SURROGATE.search(k)
                if m:
                    return m.group()
                stack.append(x)
        elif isinstance(v, list):
            stack.extend(v)
        elif isinstance(v, str):
            m = LONE_SURROGATE.search(v)
            if m:
                return m.group()
    return None


def loads_strict(text):
    obj = json.loads(text, object_pairs_hook=_members, parse_constant=_constant,
                     parse_float=_decimal)
    if SURROGATE_ESCAPE.search(text):
        lone = unpaired_surrogate(obj)
        if lone is not None:
            raise Bad("a string holding the unpaired surrogate U+%04X, which is no character" % ord(lone))
    return obj


class Line(object):
    __slots__ = ("rec", "n", "obj", "kind", "ts", "problem", "lane", "lo", "hi", "source")

    def __init__(self, rec, n):
        self.rec, self.n = rec, n
        self.obj = self.kind = self.ts = self.problem = self.lane = None
        self.lo = self.hi = None
        self.source = ("record", getattr(rec, "ordinal", 0), n)

    def where(self):
        return "%s:%d" % (self.rec.name, self.n)


class Rec(object):
    def __init__(self, name, path, is_admitted):
        self.name, self.path = name, path
        self.anchor, self.ordinal, self.sources = GLOBAL_OWNER, 0, ()
        self.stem = name[:-len(".jsonl")]
        self.admitted = is_admitted
        self.status, self.reason, self.size = "listed", None, None
        self.lines, self.ordered = [], True
        self.first_ts = self.last_ts = None
        self.has_run_open = False
        self.bad_lines = []
        self.opened = False
        self._by_n = None

    @property
    def readable(self):
        return self.status in ("read", "empty")

    def line(self, n):
        """The line numbered N (its place in the file, blank lines counted), or None: a blank line, or
        past the end."""
        if self._by_n is None:
            self._by_n = dict((ln.n, ln) for ln in self.lines)
        return self._by_n.get(n)


def read_log(name, names):
    """Whether a candidate name is the command checker's read log: `<run>-unplaced-reads.jsonl`, `<run>`
    a run id, with the run's own record `<run>.jsonl` among NAMES, the folder's listing, which is the
    only place and time the logger writes one. A name of that form with no such record beside it is a
    candidate like any other (CR-WW1 finding 6). Decided from the names alone, never from what any
    file holds."""
    return (READ_LOG_NAME.fullmatch(name) is not None
            and name[:-len(READ_LOG_SUFFIX)] + ".jsonl" in names)


def admitted(name, names):
    """Whether a candidate name is a run record: decided from the names alone, never from what any
    file holds (FIELDS.md, "Admission"): every `*.jsonl` name but the pinned event logs and the
    command checker's read logs, each beside its run's record in NAMES, the folder's listing."""
    if read_log(name, names):
        return False
    return name.endswith(".jsonl") and name not in PINNED_EVENT_LOGS


class NotOpened(OSError):
    """An admitted name whose directory entry is not a regular file: never opened."""


# ------------------------------------------------------------------------ containment -----
# This is the finite route catalogue. A route/owner pair is terminal after its first failure.
# Owners are acquired physical positions, record anchors, or the single global anchor.
ROUTES = frozenset("""
record-blank record-decode record-kind record-time record-identity record-metadata
analysis-line analysis-final analysis
structural episode-duration episode-exit episode-review episode-denials episode-spend
boundary-value boundary-refusals beat-value snapshot-value spend-session compute
store-blank store-decode store-kind store-validate store-entry store-select store-group store-apply
store-history determinations keys tables coverage
main-row main-determination main-history main-key main-gap
detail-gap detail-inventory detail-invalid detail-open detail-run detail-episode
detail-history detail-view detail-group detail-review detail-boundary detail-snapshot
detail-exact detail-beat detail-table render sort-key
diagnostic gap-presentation unknown-presentation outgoing stdout encode-main encode-detail
encode-stdout
""".split())
ROUTES |= frozenset("main-row-" + k for k in FIGURE_KEYS.values())
ROUTES |= frozenset(("sort-store", "sort-gap", "sort-view", "sort-idle", "prepare"))
EPISODE_SCOPE = EPISODE_PARTS + (P_SP,)
BOUNDARY_SCOPE = (P_B, P_BS, P_RFH, P_RFB, P_SS)
# Five declared recovery families; their finite unions give 2**5 gap-presentation routes.
# A slot is never reused for a different domain merely because another gap occupies the row.
GAP_FAMILIES = (EPISODE_SCOPE, BOUNDARY_SCOPE, (P_RVG, P_SS), (P_SB,), (P_SS,))
ROUTES |= frozenset("detail-gap-%d" % mask for mask in range(1 << len(GAP_FAMILIES)))

GLOBAL_OWNER = ("global", 0, 0)
Envelope = namedtuple("Envelope", "source kind ts obj problem lane lo hi")
_ACTIVE = None


def containment_observer(event):
    """An in-memory observation point. Tests replace it; production has no telemetry I/O."""


def boundary_hook(route, owner, phase):
    """An inert seam for reached-injection and transaction tests, including after-candidate faults."""


class Replay(BaseException):
    """Discard a tentative generation; never confused with a data-validation exception."""


def terminal_text(text):
    """Trusted recovery encoding: ASCII, one line, no ordinary layout callback or object repr."""
    out = []
    for ch in text:
        n = ord(ch)
        if 32 <= n <= 126 and ch not in "\\|`":
            out.append(ch)
        else:
            out.append("\\u%04x" % n if n <= 65535 else "\\U%08x" % n)
    return "".join(out)


def helper_text(text):
    """One injective quoted helper component, before any table or line layout."""
    return json.dumps(text, ensure_ascii=True)


def immutable_mutation(*args, **kwargs):
    raise TypeError("acquired JSON is immutable")


class FrozenDict(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = immutable_mutation
    __ior__ = immutable_mutation


class FrozenList(list):
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = immutable_mutation
    __iadd__ = __imul__ = immutable_mutation


def immutable_json(value):
    """Freeze JSON iteratively, retaining dict/list validation semantics without recursion."""
    def container(v):
        return FrozenDict() if isinstance(v, dict) else FrozenList() if isinstance(v, list) else v
    root = container(value)
    pending = [(value, root)]
    while pending:
        old, new = pending.pop()
        if isinstance(old, dict):
            for key, val in old.items():
                child = container(val)
                dict.__setitem__(new, key, child)
                if isinstance(val, (dict, list)):
                    pending.append((val, child))
        elif isinstance(old, list):
            for val in old:
                child = container(val)
                list.append(new, child)
                if isinstance(val, (dict, list)):
                    pending.append((val, child))
    return root


def kind_scope(kind):
    if kind in EPISODE_KINDS:
        return EPISODE_SCOPE
    if kind is None:
        return ALL_PARTS
    return KIND_PARTS.get(kind, ())


class Recovery:
    def __init__(self):
        self.labels, self.facts, self.records = {}, {}, {}
        self.failed, self.ledger = set(), []
        self.domains, self.eligibility, self.authorities = {}, set(), set()
        self.persistence = False
        self.replaying = False
        self.generations = 0
        self.owners = {GLOBAL_OWNER}
        self.witnesses = {}
        self.current_sources = ()
        self.current_owner = GLOBAL_OWNER
        self.current_recs = ()

    def register(self, source, label, record=None):
        self.owners.add(source)
        self.labels[source] = terminal_text(label)
        if record is not None:
            self.records[source] = record

    def fail(self, route, owner, sources, parts, exc):
        # Every input here was prepared before the fallible operation. Never inspect its payload.
        slot = (route, owner)
        if slot in self.failed:
            raise Probe("a terminal containment slot was re-entered")
        self.failed.add(slot)
        token = terminal_text(type(exc).__name__)
        event = (route, owner, tuple(sources), token)
        self.ledger.append(event)
        for source in (() if route == "outgoing" else sources):
            if source[0] == "store":
                kind = self.facts.get(source)
                self.authorities.update((kind,) if kind in STORE_KINDS else STORE_KINDS)
            elif source in self.records:
                record = self.records[source]
                self.eligibility.add(record)
                effect = tuple(parts) if parts is not None else kind_scope(self.facts.get(source))
                self.domains.setdefault(record, set()).update(effect)
                self.witnesses.setdefault(source, set()).update(effect)
        if route in ("outgoing", "prepare"):
            self.persistence = True
        containment_observer(event)

    def ledger_text(self):
        # No sorting, source-object reads or normal rendering in the recovery kernel.
        lines = ["", "## Contained failures", ""]
        for route, owner, sources, token in self.ledger:
            labels = [self.labels[s] for s in sources]
            if not labels:
                labels = ["inventory/store premise" if owner == GLOBAL_OWNER else self.labels[owner]]
            lines.append("- " + "; ".join(labels) + " · " + route + " · " + token
                         + " · unknown (contained unexpected failure)")
        return "\n".join(lines) + "\n"


@contextmanager
def boundary(route, owner=GLOBAL_OWNER, sources=(), parts=None):
    """The only unexpected input catch. A failure commits flags then aborts the generation."""
    if _ACTIVE is None:
        yield True
        return
    if route not in ROUTES or owner not in _ACTIVE.owners:
        raise Probe("unregistered containment route or owner")
    if (route, owner) in _ACTIVE.failed:
        yield False
        return
    previous = _ACTIVE.current_sources
    previous_owner = _ACTIVE.current_owner
    _ACTIVE.current_sources = tuple(sources)
    _ACTIVE.current_owner = owner
    yielded = False
    try:
        boundary_hook(route, owner, "before")
        yielded = True
        yield True
        boundary_hook(route, owner, "after")
    except (Probe, Bad, NotOpened):
        raise
    except Exception as exc:
        _ACTIVE.fail(route, owner, tuple(sources), parts, exc)
        if _ACTIVE.replaying:
            raise Replay()
        if not yielded:
            yield False
    finally:
        _ACTIVE.current_sources = previous
        _ACTIVE.current_owner = previous_owner


def guarded(route, owner, sources, parts, fn, fallback):
    with boundary(route, owner, sources, parts) as live:
        if live:
            return fn()
    return fallback()


def record_sources(rec):
    return rec.sources if hasattr(rec, "sources") else ()


def episode_sources(ep):
    # Later openings can change this close's resumed status. Gates affect positional activity.
    return tuple(ln.source for ln in ep.rec.lines if ln is ep.opening or ln is ep.close
                 or ln is ep.gate or ln.kind == "gate" and ep.opening.n < ln.n < ep.close.n
                 or ln.kind in ALL_OPENINGS and ln.lane == ep.lane and ln.n > ep.opening.n)


def all_sources(recs):
    return tuple(s for r in recs for s in record_sources(r))


def withdrawn(rec, part):
    return _ACTIVE is not None and part in _ACTIVE.domains.get(rec.name, ())


def uncertain_record(rec):
    return _ACTIVE is not None and rec.name in _ACTIVE.eligibility


def authority(kind):
    return _ACTIVE is not None and kind in _ACTIVE.authorities


def store_sources(store):
    return getattr(store, "sources", ())


def source_of_store(rec):
    return getattr(rec, "source", GLOBAL_OWNER)


class StoreEntry(FrozenDict):
    """The payload stays a JSON mapping; its physical provenance is separate from JSON members."""
    def __init__(self, value, source):
        super().__init__(value)
        self.source = source


def sort_prepared(values, key, sources=(), parts=ALL_PARTS, owner=GLOBAL_OWNER, route="sort-key"):
    # Decorate under the boundary; sorting only compares homogeneous prepared primitives.
    return guarded(route, owner, sources, parts,
                   lambda: [v for _, _, v in sorted((key(v), n, v) for n, v in enumerate(values))],
                   lambda: [])


def gap_domain(gap):
    parts = set(gap.parts)
    mask = 0
    if P_RVG in parts and parts <= {P_RVG, P_SS}:
        mask |= 1 << 2
    elif parts.intersection(EPISODE_SCOPE):
        mask |= 1 << 0
    if parts.intersection((P_B, P_BS, P_RFH, P_RFB)):
        mask |= 1 << 1
    if P_SB in parts:
        mask |= 1 << 3
    if P_SS in parts and not mask & ((1 << 1) | (1 << 2)):
        mask |= 1 << 4
    domain = set(p for i, family in enumerate(GAP_FAMILIES) if mask & (1 << i) for p in family)
    return "detail-gap-%d" % mask, tuple(p for p in ALL_PARTS if p in domain)


def containment_gaps():
    if _ACTIVE is None:
        return []
    out = []
    for s, parts in _ACTIVE.witnesses.items():
        gap = Gap("contained unexpected failure", _ACTIVE.labels[s], None,
                  tuple(p for p in ALL_PARTS if p in parts), run=_ACTIVE.records[s][:-6],
                  scope="every report")
        gap.sources = (s,)
        gap.owner = s
        out.append(gap)
    return out


def read_candidate(path):
    """The bytes of an admitted candidate. Its entry is examined first (lstat, which opens nothing):
    a symbolic link is never followed, since its target could lie outside the records folder or be
    a pinned event log, and anything but a regular file is never opened; the open itself refuses a
    link (O_NOFOLLOW) and cannot block on a pipe (O_NONBLOCK)."""
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        raise NotOpened("a symbolic link, never followed")
    if not stat.S_ISREG(st.st_mode):
        raise NotOpened("not a regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise NotOpened("not a regular file")
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def decode_record_line(line, raw):
    # Each problem carries its group (Reason), the label it begins with, set here.
    try:
        obj = loads_strict(raw.decode("utf-8"))
    except UnicodeDecodeError:
        line.problem = noted("not UTF-8", "not UTF-8")
        return line
    except (Bad, ValueError, RecursionError) as exc:
        line.problem = noted(("not JSON (%s)" % exc) if isinstance(exc, Bad) else "not JSON", "not JSON")
        return line
    if not isinstance(obj, dict):
        line.problem = noted("not a JSON object", "not a JSON object")
        return line
    line.obj = immutable_json(obj)
    return line


def kind_record_line(line):
    obj = line.obj
    ev = obj.get("event", MISSING)
    if not isinstance(ev, str):
        line.problem = noted("no event name (%s)" % ("absent" if ev is MISSING else kind_of(ev)), "no event name")
    elif ev not in KNOWN_EVENTS:
        line.problem = noted("an event name outside the known list (%r)" % ev[:60], "an event name outside")
    else:
        line.kind = ev
    return line


def time_record_line(line):
    obj = line.obj
    line.ts = parse_ts(obj.get("ts"))
    if line.kind and line.ts is None:
        line.problem = noted("no usable timestamp (%s)" % (
            "absent" if "ts" not in obj else repr(obj.get("ts"))[:40]), "no usable timestamp")
    return line


def identity_record_line(line):
    obj = line.obj
    if line.kind in ALL_OPENINGS or line.kind in ALL_CLOSES:
        lane = obj.get("lane")
        if isinstance(lane, str) and lane.strip():
            line.lane = lane
        else:
            why = "no usable lane (%s)" % ("absent" if "lane" not in obj else kind_of(lane))
            line.problem = (noted(line.problem + "; " + why, line.problem.group) if line.problem
                            else noted(why, "no usable lane"))
    elif line.kind in END_MARKERS:
        lane = obj.get("lane")
        line.lane = lane if isinstance(lane, str) and lane.strip() else None
    return line


def read_record(rec, data):
    """Allocate physical identities before even testing blanks; commit validated facts in order."""
    rec.size = len(data)
    rec.sources = tuple(("record", getattr(rec, "ordinal", 0), n)
                        for n in range(1, len(data.split(b"\n")) + 1))
    if _ACTIVE:
        for source in rec.sources:
            _ACTIVE.register(source, rec.name + ":" + str(source[2]), rec.name)
    for n, raw in enumerate(data.split(b"\n"), 1):
        line = Line(rec, n)
        source = line.source
        blank = guarded("record-blank", source, (source,), ALL_PARTS,
                        lambda: not raw.strip(), lambda: False)
        if blank:
            continue
        line = guarded("record-decode", source, (source,), ALL_PARTS,
                       lambda: decode_record_line(line, raw), lambda: Line(rec, n))
        if line.obj is not None:
            line = guarded("record-kind", source, (source,), ALL_PARTS,
                           lambda: kind_record_line(line), lambda: Line(rec, n))
            if _ACTIVE:
                _ACTIVE.facts[source] = line.kind
            line = guarded("record-time", source, (source,), ALL_PARTS,
                           lambda: time_record_line(line), lambda: Line(rec, n))
            line = guarded("record-identity", source, (source,), kind_scope(line.kind),
                           lambda: identity_record_line(line), lambda: Line(rec, n))
        rec.lines.append(line)
    def metadata():
        dated = [ln.ts for ln in rec.lines if ln.ts is not None]
        rec.ordered = all(a <= b for a, b in zip(dated, dated[1:]))
        rec.first_ts = min(dated) if dated else None
        rec.last_ts = max(dated) if dated else None
        rec.status = "read" if rec.lines else "empty"
        # The span an undated line can occupy: between its dated neighbours in an ordered record,
        # anywhere in an unordered one.
        prev = None
        for i, ln in enumerate(rec.lines):
            if ln.ts is not None:
                ln.lo = ln.hi = ln.ts
                prev = ln.ts
                continue
            if not rec.ordered:
                continue
            nxt = next((x.ts for x in rec.lines[i + 1:] if x.ts is not None), None)
            ln.lo, ln.hi = prev, nxt
        rec.bad_lines = [ln for ln in rec.lines if ln.problem]
    
        rec.has_run_open = any(ln.kind == "run-open" for ln in rec.lines)
    guarded("record-metadata", getattr(rec, "anchor", GLOBAL_OWNER), record_sources(rec), ALL_PARTS,
            metadata, lambda: None)
    if rec.status == "listed":
        rec.status = "read" if rec.lines else "empty"


def reaches(line, start, end):
    """Whether a line's possible time reaches [start, end): a dated line at its own time; an
    undated one anywhere between its dated neighbours in an ordered record (an open end where a
    neighbour is missing), and anywhere at all in an unordered one."""
    if line.ts is not None:
        return start <= line.ts < end
    if not line.rec.ordered:
        return True
    if line.lo is not None and line.lo >= end:
        return False
    if line.hi is not None and line.hi < start:
        return False
    return True


def store_given():
    """The run store as named (LLM_WIKI_STORE, else its default), before links are resolved."""
    return os.path.expanduser(os.environ.get("LLM_WIKI_STORE") or os.path.join("~", ".llm-wiki"))


def store_root():
    """The run store as handsoff.py resolves it (handsoff.py:1001-1004)."""
    return os.path.realpath(store_given())


NOT_ADMITTED = ("an event log pinned by its name (FIELDS.md, \"Admission\"); not opened, its "
                "contents unread and unknown")
NOT_ADMITTED_READ_LOG = ("the command checker's read log, `<run>-unplaced-reads.jsonl` beside its run's "
                         "record `<run>.jsonl`, by its name (FIELDS.md, \"Admission\"); not opened, its "
                         "contents unread and unknown")


def acquire(records_dir):
    """Inventory every candidate (`*.jsonl`), decide for every one from its name alone whether it
    is a run record, and only then open each admitted record once (read_candidate). Returns the
    candidates, the count of other entries in the folder (not candidates) and the input volume. An
    empty or inaccessible inventory, or one with no admitted record, is a broken premise."""
    if not os.path.isdir(records_dir):
        raise Probe("no records folder at %s" % records_dir)
    try:
        names = sorted(os.listdir(records_dir))
    except OSError as exc:
        raise Probe("the records folder %s cannot be listed (%s)" % (records_dir, exc))
    others = sum(1 for n in names if not n.endswith(".jsonl"))
    # Every admission is decided here, from the names alone, before the first open below.
    listing = frozenset(names)
    recs = [Rec(n, os.path.join(records_dir, n), admitted(n, listing)) for n in names if n.endswith(".jsonl")]
    if not recs:
        raise Probe("no candidate record (*.jsonl) in %s: an empty inventory is a failed "
                    "premise, never a clean week" % records_dir)
    if not any(r.admitted for r in recs):
        raise Probe("no admitted run record in %s (%d candidates, each left out by its name: a "
                    "pinned event log or a command checker's read log): an empty inventory is a "
                    "failed premise, never a clean week" % (records_dir, len(recs)))
    volume = {"bytes": 0, "lines": 0, "files": 0}
    for ordinal, rec in enumerate(recs, 1):
        rec.ordinal, rec.anchor = ordinal, ("anchor", ordinal, 0)
        rec.sources = ()
        if _ACTIVE:
            _ACTIVE.register(rec.anchor, rec.name, rec.name)
        if not rec.admitted:
            rec.status, rec.reason = "not admitted", (NOT_ADMITTED_READ_LOG if read_log(rec.name, listing)
                                                      else NOT_ADMITTED)
            continue
        try:
            data = read_candidate(rec.path)
        except FileNotFoundError:
            rec.status, rec.reason = "gone", "listed, then gone before it could be read"
            continue
        except NotOpened as exc:
            rec.status, rec.reason = "unreadable", "%s (FIELDS.md, \"Admission\"); not opened" % exc
            continue
        except OSError as exc:
            rec.status, rec.reason = "unreadable", "cannot be read (%s)" % exc.strerror
            continue
        rec.opened = True
        volume["files"] += 1
        volume["bytes"] += len(data)
        read_record(rec, data)
        volume["lines"] += len(rec.lines)
    return recs, others, volume


# ------------------------------------------------------------------------ analysis --------

def episode_key(stem, lane, n):
    """The held format's episode string, `<record>:<helper>:<line>` (the held design's README, "The
    abandoned determination"), made to be shown and stored beside an episode's identity, the structure
    (record, helper, opening line), and never read back into it: a record or a helper may hold ":", so
    one string can name several openings (CR-WASTE6 finding 1; key_identities)."""
    return "%s:%s:%d" % (stem, lane, n)


class Episode(object):
    def __init__(self, rec, lane, opening, close, gate, gates_between, notes):
        self.rec, self.lane, self.opening, self.close = rec, lane, opening, close
        self.gate, self.gates_between, self.notes = gate, gates_between, notes
        self.resumed_later = False

    @property
    def key(self):
        return episode_key(self.rec.stem, self.lane, self.opening.n)


class Gap(object):
    """A named input that is not available for one or more parts of the figures. `run`, `lane`,
    `cls` and `src` narrow what it can reach (None: every run, helper, class or idle source): `cls`
    a class as recorded, `src` an idle source key (idle_source)."""

    def __init__(self, reason, where, when, parts, run=None, lane=None, cls=None,
                 scope="interval", src=None):
        self.reason, self.where, self.when, self.parts = reason, where, when, tuple(parts)
        self.run, self.lane, self.cls, self.scope, self.src = run, lane, cls, scope, src
        self.sources = _ACTIVE.current_sources if _ACTIVE else ()
        self.owner = _ACTIVE.current_owner if _ACTIVE else GLOBAL_OWNER


EPISODE_KINDS = ALL_OPENINGS + ALL_CLOSES
# The labels printed in place of a recorded value (each a parenthesised phrase; shown() quotes any
# recorded string that begins with a parenthesis): the states of an unusable class, the idle source of
# a boundary with no idle_src, and the helper of an end marker with no usable lane.
CLASS_LABELS = {"invalid": "(class invalid)", "conflicting": "(class conflicting)",
                "unrecorded": "(class unrecorded)"}
UNRECORDED_SOURCE = "(source unrecorded)"
UNUSABLE_LANE = "(unusable)"
# The total row of each helper-time view in the detail, printed below the rows of the recorded runs,
# classes and helpers it sums (CR-WASTE6 finding 3: it was "all", the text a recorded class "all" and
# a record all.jsonl print as).
VIEW_TOTAL = "(all)"
# A boundary's or beat's field absent or null as recorded, in the detail's lines of them (as_recorded).
ABSENT_FIELD = "None"
# Every label the reports print in a place a recorded value can hold, in this one definition: shown()
# quotes a recorded string equal to any of them, and the suite takes its list of labels from it.
LABELS = (CLASS_LABELS["invalid"], CLASS_LABELS["conflicting"], CLASS_LABELS["unrecorded"],
          UNRECORDED_SOURCE, UNUSABLE_LANE, VIEW_TOTAL, ABSENT_FIELD)


def class_reach(ln):
    """The one class a damaged or unpaired episode line could give its episode, or None for every
    class (FIELDS.md, "Scope of a gap"). An episode's class is its close's, else its opening's, and
    two that differ conflict; so a line's own usable class bounds its reach only when no other
    opening or close of its helper on the record (of any helper there, when its own is unusable)
    names a different class or an unusable one."""
    if ln.obj is None or ln.kind not in EPISODE_KINDS:
        return None
    own, problem = class_value(ln.obj)
    if own is None:
        return None
    for other in ln.rec.lines:
        if other is ln or other.obj is None or other.kind not in EPISODE_KINDS:
            continue
        if ln.lane is not None and other.lane != ln.lane:
            continue
        v, p = class_value(other.obj)
        if (p and p[0] == "invalid") or (v is not None and v != own):
            return None
    return own


def idle_source(obj):
    """The idle source a boundary names, as a key: ("recorded", its idle_src); ("unrecorded", None)
    when it is absent or null, a state of the key and never a string a boundary could record
    (CR-WASTE5 finding 1); None when the value is unusable (it could be any source)."""
    if not isinstance(obj, dict):
        return None
    src = obj.get("idle_src", MISSING)
    if src is MISSING or src is None:
        return ("unrecorded", None)
    return ("recorded", src) if isinstance(src, str) and src.strip() else None


def source_text(key):
    """An idle source key as the reports show it: a recorded idle_src by shown(), else the label."""
    return shown(key[1]) if key[0] == "recorded" else UNRECORDED_SOURCE


def analyse(recs):
    """Pairs every valid opening with its valid close, collects the boundary, beat, gate,
    snapshot and run lines, and lists every open or unresolved episode and every bad close."""
    out = {"episodes": [], "bad_closes": [], "open": [], "boundaries": [], "beats": [],
           "snap_events": [], "runs": [], "hist": []}
    for rec in recs:
        with boundary('analysis-final', rec.anchor, record_sources(rec), ALL_PARTS) as live:
            if not live:
                continue
            if rec.status != "read":
                continue
            # lane -> {"kind": "open" or "unresolved", "opening", "gate", "notes", "cause"}
            state = {}
            gate = None           # the last gate line before here, whatever its state
            gates = []            # every gate line's number
            closed = {}
            run_state = None

            def retire(lane, st, lead):
                if st["opening"] is not None:
                    why = "; ".join(([lead] if lead else []) + st["notes"])
                    out["open"].append((rec, lane, st["opening"], why, st["kind"]))

            for ln in rec.lines:
                with boundary('analysis-line', ln.source, record_sources(rec), kind_scope(ln.kind)) as live:
                    if not live:
                        continue
                    if all(withdrawn(rec, p) for p in ALL_PARTS):
                        continue
                    if ln.kind is None:
                        continue
                    if ln.kind in EPISODE_KINDS and withdrawn(rec, P_H):
                        continue
                    if ln.kind == "phase-boundary" and withdrawn(rec, P_B):
                        continue
                    if ln.kind == "hold-beat" and withdrawn(rec, P_SB):
                        continue
                    if ln.kind == "gate" and withdrawn(rec, P_RVG):
                        continue
                    obj = ln.obj
                    if ln.kind == "gate":
                        gate = ln
                        gates.append(ln.n)
                    if ln.kind in ("run-open", "run-resume"):
                        run_state = ("open", ln)
                    elif ln.kind == "run-close":
                        run_state = ("closed", ln)
                    if ln.ts is not None:
                        if ln.kind == "phase-boundary":
                            out["boundaries"].append(ln)
                        if ln.kind == "hold-beat":
                            out["beats"].append(ln)
                        if ln.kind in SNAPSHOT_FIELDS:
                            out["snap_events"].append(ln)
                    if ln.kind in HIST_OPENINGS or ln.kind in HIST_CLOSES or ln.kind in END_MARKERS:
                        out["hist"].append(ln)
                    if ln.kind in END_MARKERS:
                        st = state.get(ln.lane) if ln.lane else None
                        if st is not None:
                            st["notes"].append("line %d records %s, a historical end marker that is not a "
                                               "close" % (ln.n, ln.kind))
                        continue
                    if ln.lane is None or not (ln.kind in ALL_OPENINGS or ln.kind in ALL_CLOSES):
                        continue
                    st = state.get(ln.lane)
                    if ln.kind in ALL_OPENINGS:
                        if st is not None:
                            retire(ln.lane, st, "a later opening at line %d replaced it without a valid "
                                                "close" % ln.n)
                        if ln.problem:
                            state[ln.lane] = {"kind": "unresolved", "opening": None, "gate": None,
                                              "notes": [], "cause": "an opening of this helper at line "
                                                                    "%d with %s" % (ln.n, ln.problem)}
                        else:
                            state[ln.lane] = {"kind": "open", "opening": ln, "gate": gate, "notes": [],
                                              "cause": None}
                        for ep in closed.get(ln.lane, []):
                            ep.resumed_later = True
                        continue
                    # A close.
                    if st is None:
                        if not ln.problem:
                            out["bad_closes"].append((ln, noted("a close with no opening before it on the record",
                                                                "a close with no opening")))
                        continue
                    if st["kind"] == "unresolved":
                        if not ln.problem:
                            out["bad_closes"].append((ln, noted("a close after %s; not paired" % st["cause"],
                                                                "a close after")))
                        st["notes"].append("line %d closes it again%s" % (
                            ln.n, " with " + ln.problem if ln.problem else ""))
                        continue
                    opening = st["opening"]
                    if ln.problem:
                        # A malformed close is not evidence that the opening resolved (design item 5(b)).
                        st["kind"] = "unresolved"
                        st["cause"] = "a close of this helper at line %d with %s" % (ln.n, ln.problem)
                        st["notes"].append("line %d closes it with %s: a malformed close is not evidence "
                                           "that the episode resolved" % (ln.n, ln.problem))
                        continue
                    if opening.ts is not None and ln.ts < opening.ts:
                        # A close timed before its opening resolves nothing: the opening stays open.
                        out["bad_closes"].append((ln, noted("a close timed before its opening (line %d)"
                                                            % opening.n, "a close timed before")))
                        st["notes"].append("line %d closes it at an earlier time" % ln.n)
                        continue
                    del state[ln.lane]
                    ep = Episode(rec, ln.lane, opening, ln, st["gate"],
                                 [g for g in gates if g > opening.n], st["notes"])
                    out["episodes"].append(ep)
                    closed.setdefault(ln.lane, []).append(ep)
            for lane, st in sorted(state.items(), key=lambda kv: (kv[1]["opening"].n if kv[1]["opening"]
                                                                  else 0, kv[0])):
                if st["opening"] is None:
                    continue
                if st["kind"] == "open":
                    retire(lane, st, "no valid close on the record" if st["notes"]
                           else "no close on the record")
                else:
                    retire(lane, st, None)
            if run_state:
                status = "unknown" if uncertain_record(rec) or authority("run-ended") else run_state[0]
                if status != "closed":
                    out["runs"].append((rec, run_state[1], status))
    return out


# ------------------------------------------------------------------------ values ----------
# Each returns (state, number, note): state one of known, na, unknown, invalid.

def duration_value(c):
    if "duration_s" not in c:
        if c.get("exit_class") == "spawn-failed":
            return "na", None, "no process started (exit_class spawn-failed)"
        return "unknown", None, "duration_s is not on the close"
    v = c["duration_s"]
    if v is None:
        return "unknown", None, "duration_s is recorded as null"
    if not isnum(v):
        return "invalid", None, "duration_s is %s" % kind_of(v)
    if v < 0:
        return "invalid", None, "duration_s is negative"
    if beyond(v):
        return "invalid", None, "duration_s is %s" % beyond(v)
    return "known", Decimal(v), None


def exit_value(c):
    if "exit_class" not in c:
        return "unknown", None, "exit_class is not on the close"
    v = c["exit_class"]
    if v is None:
        return "unknown", None, "exit_class is recorded as null"
    if not isinstance(v, str) or not v.strip():
        return "invalid", None, "exit_class is %s" % ("blank" if isinstance(v, str) else kind_of(v))
    if v not in WRITER_EXIT_CLASSES:
        return "outside", v, noted("exit_class %r is outside the writers' vocabulary" % v,
                                   "exit_class '…' is outside the writers' vocabulary")
    return "known", v, None


def count_value(v, what):
    if v is MISSING:
        return "unknown", None, "%s is not on the record" % what
    if v is None:
        return "unknown", None, "%s is recorded as null" % what
    if not isint(v) or v < 0:
        return "invalid", None, "%s is %s" % (what, "negative" if isint(v) else int_kind(v))
    if beyond(v):
        return "invalid", None, "%s is %s" % (what, beyond(v))
    return "known", v, None


def denial_values(c):
    """The close's refusals by channel: tool, fence, sandbox."""
    if "denials" not in c and c.get("exit_class") == "spawn-failed":
        # The documented rule (FIELDS.md, "Not applicable, and why"): no process started, so a
        # channel the close does not record is not applicable. It covers absent fields only: a
        # standalone sandbox_denials the close does record is read as recorded, so an invalid or
        # null value stays invalid or unknown and is named (CR-WASTE3 finding 2).
        na = ("na", None, "no process started (exit_class spawn-failed)")
        b = c.get("sandbox_denials", MISSING)
        return {"tool": na, "fence": na,
                "sandbox": na if b is MISSING else count_value(b, "sandbox_denials")}
    d = c.get("denials", MISSING)
    out = {}
    for ch in ("tool", "fence"):
        if isinstance(d, dict):
            out[ch] = count_value(d.get(ch, MISSING), "denials.%s" % ch)
        elif d == "unknown":
            if ch == "fence" and "fence_denials_transcript" in c:
                out[ch] = count_value(c["fence_denials_transcript"], "fence_denials_transcript")
            else:
                out[ch] = ("unknown", None, "denials are recorded as \"unknown\"")
        elif d is MISSING:
            out[ch] = ("unknown", None, "denials are not on the close")
        elif d is None:
            out[ch] = ("unknown", None, "denials are recorded as null")
        elif isinstance(d, str):
            out[ch] = ("invalid", None, noted("denials is a string (%r)" % d[:30], "denials is a string ('…')"))
        else:
            out[ch] = ("invalid", None, "denials is %s" % kind_of(d))
    a = d.get("sandbox", MISSING) if isinstance(d, dict) else MISSING
    b = c.get("sandbox_denials", MISSING)
    va = count_value(a, "denials.sandbox") if a is not MISSING else None
    vb = count_value(b, "sandbox_denials") if b is not MISSING else None
    if va and vb and va[0] == "known" and vb[0] == "known" and va[1] != vb[1]:
        out["sandbox"] = ("invalid", None, noted("denials.sandbox %d and sandbox_denials %d disagree"
                                                 % (va[1], vb[1]),
                                                 "denials.sandbox N and sandbox_denials N disagree"))
    elif va and va[0] == "invalid":
        out["sandbox"] = va
    elif vb and vb[0] == "invalid":
        out["sandbox"] = vb
    elif va and va[0] == "known":
        out["sandbox"] = va
    elif vb and vb[0] == "known":
        out["sandbox"] = vb
    elif va or vb:
        out["sandbox"] = (va or vb)
    elif not isinstance(d, (dict, str)) and d is not MISSING and d is not None:
        out["sandbox"] = ("invalid", None, "denials is %s" % kind_of(d))
    else:
        out["sandbox"] = ("unknown", None, "no sandbox channel on the close")
    return out


PLAN_STATES = ("missing", "zero", "complete", "incomplete")
TOKEN_DIRECTIONS = (("input", "input_tokens"), ("output", "output_tokens"))


def token_value(usage, key):
    """One direction's token count on a plan-usage close, read on its own, whatever the other
    direction and the accounting state hold: absent or null is unknown; another kind, a negative
    or a fraction is invalid; a known 0 is a measured zero (codex-lane.py:661 admits only a
    non-negative integer to its sum)."""
    if usage is MISSING:
        return "unknown", None, "usage is not on the close"
    if usage is None:
        return "unknown", None, "usage is recorded as null"
    if not isinstance(usage, dict):
        return "invalid", None, "usage is %s" % kind_of(usage)
    v = usage.get(key, MISSING)
    if v is MISSING:
        return "unknown", None, "usage.%s is not on the close" % key
    if v is None:
        return "unknown", None, "usage.%s is recorded as null" % key
    if not isint(v) or v < 0:
        return "invalid", None, "usage.%s is %s" % (key, "negative" if isint(v) else int_kind(v))
    if beyond(v):
        return "invalid", None, "usage.%s is %s" % (key, beyond(v))
    return "known", v, None


def plan_usage(c):
    """(state, note, tokens). The state is the writer's accounting state (codex-lane.py:681-720):
    a recorded usage_state is read as written, whatever the tokens beside it, so an `incomplete`
    close stays incomplete; null is unknown and any other value invalid. Only an absent
    usage_state is read by codex-lane.py's own rule for a close written before it (usage_text,
    codex-lane.py:723-735), and only from values of the writer's kinds. `tokens` maps `input`
    and `output` to (state, number, note), each read on its own (token_value)."""
    u = c.get("usage", MISSING)
    tokens = dict((d, token_value(u, key)) for d, key in TOKEN_DIRECTIONS)
    if "usage_state" in c:
        state = c["usage_state"]
        if state is None:
            return "unknown", "usage_state is recorded as null", tokens
        if not isinstance(state, str) or state not in PLAN_STATES:
            return "invalid", (noted("usage_state %r is outside the writer's vocabulary" % state,
                                     "usage_state '…' is outside the writer's vocabulary")
                               if isinstance(state, str) else
                               "usage_state is %s" % kind_of(state)), tokens
    else:
        if u is not MISSING and u is not None and not isinstance(u, dict):
            return "invalid", "usage is %s" % kind_of(u), tokens
        usage = u if isinstance(u, dict) else {}
        complete = c.get("usage_complete", MISSING)
        if not usage:
            state = "missing"
        elif complete is None:
            return "unknown", "usage_complete is recorded as null", tokens
        elif complete is not MISSING and not isinstance(complete, bool):
            return "invalid", "usage_complete is %s" % kind_of(complete), tokens
        elif complete is False:
            calls = usage.get("calls", MISSING)
            if calls is MISSING or calls is None:
                state = "missing"
            elif not isint(calls) or calls < 0:
                return "invalid", "usage.calls is %s" % (
                    "negative" if isint(calls) else kind_of(calls)), tokens
            elif beyond(calls):
                return "invalid", "usage.calls is %s" % beyond(calls), tokens
            else:
                state = "incomplete" if calls else "missing"
        else:
            state = "complete"
    if state == "zero" and any(st == "known" and n for st, n, _ in tokens.values()):
        # Two recorded values that must agree and do not.
        return "invalid", "usage_state zero with non-zero tokens", tokens
    if state == "missing":
        return state, "no usage reported", tokens
    return state, None, tokens


def spend_value(c):
    """(basis, dollars, note). Bases: priced (cost_src result with a price, lane.py:3317-3318);
    plan (cost_src codex-plan with no price, codex-lane.py:948, 919, 1635); unpriced (cost_src
    transcript-estimate with no price, lane.py:3482-3483); na (no process started: exit_class
    spawn-failed with neither field, lane.py:3245-3252); missing (a result-priced close without a
    price); undeclared (a price with no cost_src); unknown-basis (no usable cost_src and no
    price); invalid-price; invalid-basis."""
    src = c.get("cost_src", MISSING)
    cost = c.get("total_cost_usd", MISSING)
    if src == "codex-plan":
        if cost is MISSING or cost is None:
            return "plan", None, None
        return "invalid-basis", None, "total_cost_usd is %s on a plan-usage close" % (
            "a price" if isnum(cost) else kind_of(cost))
    if src == "result":
        if cost is MISSING or cost is None:
            return "missing", None, "total_cost_usd is %s on a result-priced close" % (
                "absent" if cost is MISSING else "null")
        if isnum(cost) and cost >= 0:
            if beyond(cost):
                return "invalid-price", None, "total_cost_usd is %s" % beyond(cost)
            return "priced", Decimal(cost), None
        return "invalid-price", None, "total_cost_usd is %s" % (
            "negative" if isnum(cost) else kind_of(cost))
    if src == "transcript-estimate":
        if cost is not MISSING and cost is not None:
            return "invalid-basis", None, "total_cost_usd is %s on a transcript-estimate close" % (
                "a price" if isnum(cost) else kind_of(cost))
        return "unpriced", None, "a transcript estimate carries no dollar figure"
    if src is MISSING or src is None:
        if src is MISSING and cost is MISSING and c.get("exit_class") == "spawn-failed":
            return "na", None, "no process started (exit_class spawn-failed)"
        what = "no cost_src" if src is MISSING else "cost_src recorded as null"
        if isnum(cost) and cost >= 0:
            if beyond(cost):
                return "invalid-basis", None, "total_cost_usd is %s with %s" % (beyond(cost), what)
            return "undeclared", Decimal(cost), "a price with %s: its basis is undeclared" % what
        if cost is MISSING or cost is None:
            return "unknown-basis", None, "%s and no price on the close" % what
        return "invalid-basis", None, "total_cost_usd is %s with %s" % (
            "negative" if isnum(cost) else kind_of(cost), what)
    if isinstance(src, str):
        return "invalid-basis", None, noted("cost_src %r is not a known basis" % src, "cost_src '…' is not a known basis")
    return "invalid-basis", None, "cost_src is %s, not a known basis" % kind_of(src)


# Priced spend by session (FIELDS.md, "Priced spend"). A result-basis line's `total_cost_usd` is the harness
# result's own figure (lane.py's close and beat), and what it measures depends on the harness that wrote it, which
# no line names. From 19 September 2026 the records show a running total of the helper's session: each later close
# of a resumed session repeats the earlier passes' cost, every model's entry in usage.modelUsage carried over (a
# one-off model's unchanged), and a beat on a resumed session reports the session's running total too. Before then
# a resumed pass recorded its own cost. So each session is read from its own lines (classify): read as running
# totals, it counts its last total before the interval's end less its last total before the interval's start
# (none: zero); read as per-pass costs, the sum of its costs in the interval; read as neither, its spend is unknown
# and named, never guessed. One complete, usable line counts its total, which either reading gives. All
# histories first pass the same integrity gate, including losses anywhere before the exclusive end. The
# interval is half-open, [start, end): a line at the end's own instant belongs to the next interval.
SpendLine = namedtuple("SpendLine", "ln kind lane basis amount note state key why entries lane_v sid_v")
# A line that could be one of a session's and cannot be read into it: the line, the lane and session id it could
# still be matched by (None: any), and what it is.
Lost = namedtuple("Lost", "ln lane sid what")
RESULT_BASES = ("priced", "missing", "invalid-price")
# A model's measures in usage.modelUsage, the harness's own names (lane.py's beat_usage sums the four counts by
# them): its cost and its four token counts.
MODEL_COUNTS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
MODEL_MEASURES = ("costUSD",) + MODEL_COUNTS
READINGS = (("running", "running totals"), ("per-pass", "per-pass costs"), ("unclassified", "neither"),
            ("one", "one line"))
NEITHER = ": its totals read neither as running totals nor as per-pass costs, so its spend in the interval is unknown"
LOST_TAIL = (" could be one of the session's lines before the interval's end and cannot be read into it, "
             "so its spend in the interval is unknown")


def usable_name(v):
    return isinstance(v, str) and bool(v.strip())


def session_of(obj, lane):
    """(state, key, why, lane, sid): the session a result-basis close or beat names. ("known", (lane, session_id),
    None, lane, session_id) when both are non-blank strings. ("none", None, why, ...) when either is absent or null
    and neither is invalid: the line names no session, and an absent identity is no proof that the line is a
    session of its own (CR-WW1 finding 3), so its spend is unknown. ("invalid", None, why, ...) when either is of
    the wrong kind or blank: an invalid value stays invalid, never read as naming no session. The last two places
    hold the usable lane and session id, else None: what a line that names no session could still be matched by."""
    sid = obj.get("session_id", MISSING)
    lane_v, sid_v = (lane if usable_name(lane) else None), (sid if usable_name(sid) else None)
    for what, v in (("session_id", sid), ("lane", lane)):
        if v is not MISSING and v is not None and not usable_name(v):
            return ("invalid", None, "%s is %s: its running total cannot be placed in a session" % (
                what, "blank" if isinstance(v, str) else kind_of(v)), lane_v, sid_v)
    for what, v in (("session_id", sid), ("lane", lane)):
        if v is MISSING or v is None:
            return ("none", None, "%s is %s: the line names no session, so its spend in the interval is unknown" % (
                what, "absent" if v is MISSING else "recorded as null"), lane_v, sid_v)
    return "known", (lane, sid), None, lane_v, sid_v


# A close retains every per-model measure; a beat retains names and four sums. The validity gate
# precedes classification, including the one-line case: absence is never evidence of disappearance.
Inventory = namedtuple("Inventory", "entries models counts problem")
BEAT_COUNTS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
# The reconciliation tolerance (FIELDS.md, "Priced spend": the head's decision of 27 October 2026, which the owner
# may undo). A priced close's model inventory is consistent when its costs, summed exactly as written, lie within
# RECONCILE_TAU of its total_cost_usd; a larger difference makes the inventory inconsistent, unusable evidence, and
# its session's spend unknown. Otherwise a whole model entry left out of a complete-looking inventory reads as a
# model dropped, and so as per-pass costs (CR-WW2 finding N1: closes of $2 and $3, the second listing only $2.50,
# read as $5 complete). Derivation: the harness accumulates the total and each model's cost apart, in binary
# floating point, so they differ by rounding; the largest difference over the 169 weekly closes of 18 to 25
# October 2026 with a non-zero one is 6.4E-14 USD (the third build's measurement), and the largest over every
# measured close in the records on 27 October 2026 (1,691 closes, none between 6.4E-14 and 1E-7) is the same. One
# token at the cheapest list rate in the delegate skill's prices.json (Haiku's $1 per million input tokens at its
# 0.1 cache-read multiplier) costs 1E-7 USD. 1E-9 lies more than four orders of magnitude above the first and two
# below the second, so accumulated rounding passes and an omitted model entry of even one token does not.
RECONCILE_TAU = Decimal("1E-9")


def model_entries(obj, kind="close", total=None):
    """Normalise complete close/beat evidence, retaining unusable values only for diagnostics.
    No partial inventory participates in either reading. The four aggregate counts let beats and
    closes contradict a running-total reading in either direction without inventing per-model usage.
    TOTAL is a priced close's total_cost_usd (else None): its complete inventory must reconcile with it
    within RECONCILE_TAU, or the inventory is inconsistent and unusable."""
    usage = obj.get("usage")
    if not isinstance(usage, dict):
        return Inventory({}, frozenset(), None, "usage is absent or not an object")
    if kind == "beat":
        models = usage.get("models")
        if (not isinstance(models, list) or not models or not all(usable_name(m) for m in models)
                or len(set(models)) != len(models)):
            return Inventory({}, frozenset(), None, "usage.models is not a non-empty list of distinct model names")
        values = tuple(usage.get(field) for field in BEAT_COUNTS)
        if any(not isint(v) or v < 0 or beyond(v) for v in values):
            return Inventory({}, frozenset(models), None, "a beat aggregate token count is absent or unusable")
        return Inventory({}, frozenset(models), values, None)
    models = usage.get("modelUsage")
    if not isinstance(models, dict) or not models:
        return Inventory({}, frozenset(), None, "usage.modelUsage is not a non-empty model inventory")
    entries, problem = {}, None
    for model, entry in models.items():
        if not usable_name(model):
            problem = "usage.modelUsage contains an unusable model name"
        values = []
        for measure in MODEL_MEASURES:
            v = entry.get(measure, MISSING) if isinstance(entry, dict) else MISSING
            ok = isnum(v) if measure == "costUSD" else isint(v)
            values.append(v if ok and v >= 0 and not beyond(v) else None)
        if None in values:
            problem = "a model cost or token count is absent or unusable"
        entries[model] = tuple(values)
    if problem is None and total is not None:
        # Every cost and the total lie within the reader's range, so each sum and difference is exact (xadd).
        spent = Decimal(0)
        for values in entries.values():
            spent = xadd(spent, values[0])
        off = xadd(spent, Decimal(total).copy_negate()).copy_abs()
        if off > RECONCILE_TAU:
            problem = ("usage.modelUsage costs sum to $%s, not total_cost_usd $%s: they differ by $%s, more than the "
                       "reconciliation tolerance of $%s" % (fmt_dec(spent), fmt_dec(total), fmt_dec(off),
                                                            fmt_dec(RECONCILE_TAU)))
    counts = None if problem else tuple(sum(v[i] for v in entries.values()) for i in range(1, len(MODEL_MEASURES)))
    return Inventory(entries, frozenset(models), counts, problem)


def spend_line(ln, kind, lane):
    """A close or beat's identity, price and complete model evidence, before session admission. A priced
    close's inventory is reconciled with its own total (model_entries)."""
    basis, v, note = spend_value(ln.obj)
    state, key, why, lane_v, sid_v = session_of(ln.obj, lane)
    return SpendLine(ln, kind, lane, basis, v, note, state, key, why,
                     model_entries(ln.obj, kind, v if basis == "priced" else None), lane_v, sid_v)


def evidence_text(e):
    """(text, group) of one thing classify found: a model entry carried over unchanged, a total or a model's
    measure below its last usable earlier value, or a model dropped. The group replaces each recorded value by '...'
    and each line number by N (FIELDS.md, "Recorded strings and the reader's labels")."""
    if e[0] == "carry":
        _, model, a, b = e
        return ("model %s's entry is carried over unchanged from line %d to line %d" % (helper_text(model), a.ln.n, b.ln.n),
                "model …'s entry is carried over unchanged from line N to line N")
    if e[0] == "total":
        _, a, b = e
        return ("its total falls from $%s at line %d to $%s at line %d" % (fmt_dec(a.amount, 2), a.ln.n,
                                                                         fmt_dec(b.amount, 2), b.ln.n),
                "its total falls from $… at line N to $… at line N")
    if e[0] == "drop":
        _, model, (cost, a), b = e
        return ("model %s, at $%s on line %d, is dropped from %s at line %d" % (
                    helper_text(model), fmt_dec(cost, 2), a.ln.n,
                    "usage.models" if b.kind == "beat" else "usage.modelUsage", b.ln.n),
                "model …, at $… on line N, is dropped from usage.modelUsage at line N")
    if e[0] == "aggregate":
        _, measure, (va, a), (vb, b) = e
        return ("aggregate %s falls from %s at line %d to %s at line %d" % (measure, va, a.ln.n, vb, b.ln.n),
                "aggregate %s falls from N at line N to N at line N" % measure)
    if e[0] == "names":
        _, a, b = e
        return ("a model named at line %d is absent from the inventory at line %d" % (a.ln.n, b.ln.n),
                "a model named at line N is absent from the inventory at line N")
    _, model, measure, (va, a), (vb, b) = e
    money = measure == "costUSD"
    amount = lambda v: "$" + fmt_dec(v, 2) if money else str(v)
    mark = "$…" if money else "N"
    return ("model %s's %s falls from %s at line %d to %s at line %d" % (helper_text(model), measure, amount(va), a.ln.n,
                                                                      amount(vb), b.ln.n),
            "model …'s %s falls from %s at line N to %s at line N" % (measure, mark, mark))


def classify(seq):
    """Classify only a complete, usable sequence. A positive unchanged close entry supports
    running totals; a positive-cost model disappearing from a complete close or beat supports
    per-pass costs. Both together, or neither, leave the reading unknown. Every comparable
    cost/count and inventory (including beats) can contradict running totals. A fall alone
    cannot establish per-pass costs. One usable line has the same amount under both readings."""
    unusable = next((s for s in seq if s.entries.problem), None)
    if unusable is not None:
        return "unclassified", noted("line %d has unusable model evidence (%s), so its session's spend is unknown" %
                                     (unusable.ln.n, unusable.entries.problem),
                                     "a session line has unusable model evidence, so its spend is unknown")
    if len(seq) == 1:
        return "one", None
    prior = None
    last, whole = {}, {}
    carry = fall = drop = None
    for s in seq:
        if s.basis == "priced":
            if fall is None and prior is not None and s.amount < prior.amount:
                fall = ("total", prior, s)
        inventory = s.entries
        entries, models = inventory.entries, inventory.models
        if prior is not None:
            for measure, va, vb in zip(BEAT_COUNTS, prior.entries.counts, inventory.counts):
                if fall is None and vb < va:
                    fall = ("aggregate", measure, (va, prior), (vb, s))
            if fall is None and prior.entries.models - models:
                fall = ("names", prior, s)
        prior = s
        for model, seen in last.items():
            cost = seen.get("costUSD")
            if drop is None and cost is not None and cost[0] > 0 and model not in models:
                drop = ("drop", model, cost, s)
        for model, values in entries.items():
            seen = last.setdefault(model, {})
            for measure, v in zip(MODEL_MEASURES, values):
                if v is None:
                    continue
                if fall is None and measure in seen and v < seen[measure][0]:
                    fall = ("measure", model, measure, seen[measure], (v, s))
                seen[measure] = (v, s)
            if None not in values:
                if carry is None and values[0] > 0 and model in whole and whole[model][0] == values:
                    carry = ("carry", model, whole[model][1], s)
                whole[model] = (values, s)
    if carry and not fall and not drop:
        return "running", evidence_text(carry)
    if drop and not carry:
        return "per-pass", evidence_text(drop)
    if carry:
        c, cg = evidence_text(carry)
        f, fg = evidence_text(drop or fall)
        return "unclassified", noted("%s, but %s%s" % (c, f, NEITHER), "%s, but %s%s" % (cg, fg, NEITHER))
    if fall:
        f, fg = evidence_text(fall)
        tail = ", and no model's cost is dropped from a later close or beat"
        return "unclassified", noted(f + tail + NEITHER, fg + tail + NEITHER)
    return "unclassified", ("no model's entry is carried over unchanged to a later close and none is dropped from a close or beat"
                            + NEITHER)


def spend_gap(rec, inside, reason):
    """A named gap of a session's spend in the interval, at its last line there, reaching the priced
    parts its lines there feed (closes, beats or both)."""
    last = inside[-1]
    parts = tuple(p for p, k in ((P_SC, "close"), (P_SB, "beat")) if any(s.kind == k for s in inside))
    if last.kind == "close":
        return Gap(reason, "%s %s" % (last.ln.where(), helper_text(last.lane)), last.ln.ts, parts,
                   run=rec.stem, lane=last.lane)
    return Gap(reason, last.ln.where(), last.ln.ts, parts, run=rec.stem)


def before_end(ln, end):
    """Whether a line could lie before END: a dated one by its time; an undated one in an ordered record when its
    span between its dated neighbours reaches before END; in an unordered record, always."""
    if ln.ts is not None:
        return ln.ts < end
    return not ln.rec.ordered or ln.lo is None or ln.lo < end


def could_be(lost, key):
    """Whether a lost line could be one of the session KEY's (lane, session_id) lines: its own lane and session id,
    where it holds a usable one, are the session's."""
    return (lost.lane is None or lost.lane == key[0]) and (lost.sid is None or lost.sid == key[1])


def record_losses(lines, unpaired, damaged):
    """The lines of one record before the interval's end that could be one of a session's and cannot be read into
    one (CR-WW1 finding 2): a close or beat on another basis than the result's (one where no process started
    aside: it ran nothing); a result-basis one that names no session or cannot be placed in one; a close that pairs
    with no opening (UNPAIRED, as analyse names it); and an invalid line (DAMAGED) that could be a close or a beat.
    Each with the lane and session id it could still be matched by."""
    out = []
    for s in lines:
        if s.basis in RESULT_BASES:
            if s.state != "known":
                out.append(Lost(s.ln, s.lane_v, s.sid_v, "a %s that %s" % (
                    s.kind, "names no session" if s.state == "none" else "cannot be placed in a session")))
        elif s.basis != "na":
            out.append(Lost(s.ln, s.lane_v, s.sid_v, "a %s on another basis than the result's (%s)" % (
                s.kind, s.note or ("plan usage, not priced" if s.basis == "plan" else s.basis))))
    for ln, why in unpaired:
        sid = ln.obj.get("session_id", MISSING)
        out.append(Lost(ln, ln.lane, sid if usable_name(sid) else None, why))
    for ln in damaged:
        obj = ln.obj if isinstance(ln.obj, dict) else {}
        lane, sid = obj.get("lane", MISSING), obj.get("session_id", MISSING)
        out.append(Lost(ln, lane if usable_name(lane) else None, sid if usable_name(sid) else None,
                        "an invalid line: %s" % ln.problem))
    return out


def record_sessions(rec, lines, lost, start, out):
    """One record's sessions: each session's spend in [start, end) added to out["total"] exactly, its gaps to
    out["gaps"], its reading counted, and a detail line for each session holding more than one session line
    before the end. LINES are the record's closes and beats dated before the end, as spend lines, in line order;
    LOST the lines before the end that could be one of a session's and cannot be read into one (record_losses)."""
    seqs, order = {}, []
    for s in lines:
        if s.basis == "na":
            continue
        if s.state != "known":
            if s.basis not in RESULT_BASES:
                continue
            if s.ln.ts >= start:
                out["gaps"].append(spend_gap(rec, [s], s.why))
                out["invalid" if s.state == "invalid" else "missing"] += 1
            continue
        if s.key not in seqs:
            seqs[s.key] = []
            order.append(s.key)
        seqs[s.key].append(s)
    for key in order:
        seq = sorted(seqs[key], key=lambda s: (s.ln.ts, s.ln.n))
        if not any(s.basis in RESULT_BASES for s in seq):
            continue
        inside = [s for s in seq if s.ln.ts >= start]
        if not inside:
            # An unfinished or damaged pass inside the interval still depends on the session's
            # earlier price. It must not disappear merely because it supplied no usable close.
            anchors = [x for x in lost if could_be(x, key) and
                       (x.ln.ts >= start if x.ln.ts is not None else
                        not rec.ordered or x.ln.hi is None or x.ln.hi >= start)]
            if not anchors:
                continue
            inside = [seq[-1]._replace(ln=x.ln, kind="beat" if x.ln.kind == "hold-beat" else "close",
                                       basis="missing", amount=None) for x in anchors]
        out["sessions"] += 1
        before = [s for s in seq if s.ln.ts < start]
        base = before[-1] if before else None
        priced = [s for s in inside if s.basis == "priced"]
        # Integrity is decided before interpretation, for every reading and the entire history.
        gone = next((x for x in lost if could_be(x, key)), None)
        unusable_price = next((s for s in seq if s.basis != "priced"), None)
        why = None
        if gone is not None:
            why = noted("line %d (%s)%s" % (gone.ln.n, gone.what, LOST_TAIL),
                        "a session line before the interval's end cannot be read into it, so its spend is unknown")
        elif unusable_price is not None:
            why = noted("line %d has no usable result price (%s), so its session's spend is unknown" %
                        (unusable_price.ln.n, unusable_price.note),
                        "a session line has no usable result price, so its spend is unknown")
        # A lone unusable price already has its own interval field gap in compute(). A dependent
        # gap is needed for every multi-line session and every loss, including losses before the start.
        field_gap_only = gone is None and unusable_price is not None and len(seq) == 1
        if why is not None:
            reading, evidence = "unclassified", why
            if not field_gap_only:
                out["missing"] += 1
        else:
            reading, evidence = classify(seq)
            if reading == "unclassified":
                why = evidence
                out["unclassified"] += 1
        out["read"][reading] += 1
        spend = None
        if why is None and priced:
            if reading == "per-pass":
                spend = Decimal(0)
                for s in priced:
                    spend = xadd(spend, s.amount)
            else:
                spend = xadd(priced[-1].amount, Decimal(base.amount if base else 0).copy_negate())
            out["total"] = xadd(out["total"], spend)
        if why is not None and not field_gap_only:
            out["gaps"].append(spend_gap(rec, inside, why))
        if len(seq) > 1:
            read_as = dict(READINGS)[reading] + ("" if reading == "unclassified" else " (%s)" % evidence[0])
            out["detail"].append("- %s · helper %s · session %s · totals: %s · read as %s · before the start: %s · "
                                 "counted: %s" % (
                rec.name, helper_text(key[0]), helper_text(key[1]),
                ", ".join("line %d %s" % (s.ln.n, "$" + fmt_dec(s.amount, 2) if s.basis == "priced" else s.basis)
                          for s in seq),
                read_as, "none" if base is None else "line %d" % base.ln.n,
                "unknown (%s)" % why if why is not None else
                "$%s" % fmt_dec(spend if spend is not None else 0, 2)))


def session_spend(recs, an, start, end, gaps):
    """The priced figure by session (FIELDS.md, "Priced spend") over the half-open interval [START, END): each
    session with a line in it counts what its reading gives (record_sessions), summed exactly. A session is a
    record, a helper and a session id; a line naming none is unknown. Each record's sessions are one guarded
    collection, its closes and beats before the end and the lines that could be lost to them its suppliers. A
    record whose priced closes or beats were withdrawn by a contained failure joins no session at all: a session's
    closes and beats are one sequence, so either withdrawn leaves the other without its history."""
    by_rec, unpaired = {}, {}
    for ep in an["episodes"]:
        if ep.close.ts < end:
            by_rec.setdefault(ep.rec, []).append((ep.close, "close", ep.lane))
            opened_sid = ep.opening.obj.get("session_id")
            closed_sid = ep.close.obj.get("session_id")
            if usable_name(opened_sid) and usable_name(closed_sid) and opened_sid != closed_sid:
                reason = "an opening and its paired close name different sessions"
                unpaired.setdefault(ep.rec, []).extend(((ep.opening, reason), (ep.close, reason)))
    for ln in an["beats"]:
        if ln.ts < end:
            by_rec.setdefault(ln.rec, []).append((ln, "beat", None))
    for ln, why in an["bad_closes"]:
        if ln.ts is not None and ln.ts < end:
            unpaired.setdefault(ln.rec, []).append((ln, why))
            by_rec.setdefault(ln.rec, []).append((ln, "close", ln.lane))
    for rec, lane, opening, why, state in an["open"]:
        if before_end(opening, end):
            unpaired.setdefault(rec, []).append((opening, "an opening without a paired close before the interval's end"))
    # A paired close after the end cannot complete its earlier opening for this interval.
    for ep in an["episodes"]:
        if ep.opening.ts < end <= ep.close.ts:
            unpaired.setdefault(ep.rec, []).append((ep.opening, "an opening without a paired close before the interval's end"))
    out = {"total": Decimal(0), "sessions": 0, "missing": 0, "invalid": 0, "unclassified": 0,
           "read": dict((k, 0) for k, _ in READINGS), "gaps": gaps, "detail": []}
    for rec in recs:
        items = sorted(by_rec.get(rec, ()), key=lambda x: x[0].n)
        if not items or withdrawn(rec, P_SC) or withdrawn(rec, P_SB):
            continue
        damaged = [ln for ln in rec.bad_lines
                   if (ln.kind is None or ln.kind in EPISODE_KINDS or ln.kind == "hold-beat") and before_end(ln, end)]
        suppliers = (tuple(x[0].source for x in items) + tuple(ln.source for ln, _ in unpaired.get(rec, ()))
                     + tuple(ln.source for ln in damaged))
        parts = tuple(p for p, k in ((P_SC, "close"), (P_SB, "beat")) if any(x[1] == k for x in items))
        with boundary('spend-session', rec.anchor, suppliers, parts) as live:
            if not live:
                continue
            lines = [spend_line(ln, kind, lane if kind == "close" else ln.obj.get("lane", MISSING))
                     for ln, kind, lane in items]
            record_sessions(rec, lines, record_losses(lines, unpaired.get(rec, ()), damaged), start, out)
    return out


def class_value(obj):
    """(class, problem): a usable class (a non-blank string, as recorded) and None, or None and the
    problem as (state, detail): ("absent", None), ("null", None), ("invalid", "blank" or the kind)."""
    if "class" not in obj:
        return None, ("absent", None)
    v = obj["class"]
    if v is None:
        return None, ("null", None)
    if isinstance(v, str) and v.strip():
        return v, None
    return None, ("invalid", "blank" if isinstance(v, str) else kind_of(v))


def class_of(ep):
    """The episode's class as (key, note). The key is ("known", the class as recorded), or (state,
    None) for an unusable class, the state one of CLASS_LABELS's, with a note naming why: whether
    the class is usable travels in the key, never in the class's text, so a recorded class that looks
    like a label, "(builder)" or "(class invalid)", is a class like any other (CR-WASTE5 finding 1)."""
    a, pa = class_value(ep.close.obj)
    b, pb = class_value(ep.opening.obj)
    if pa and pa[0] == "invalid" or pb and pb[0] == "invalid":
        which, p = ("close", pa) if pa and pa[0] == "invalid" else ("opening", pb)
        return ("invalid", None), "the %s's class is %s" % (which, p[1])
    if a and b and a != b:
        return ("conflicting", None), noted("the close's class %r and the opening's %r disagree" % (a, b),
                                            "the close's class '…' and the opening's '…' disagree")
    if a or b:
        return ("known", a or b), None
    return ("unrecorded", None), "no class on the close or the opening"


def class_text(key):
    """A class key as the reports show it: a recorded class by shown(), an unusable one by its label."""
    return shown(key[1]) if key[0] == "known" else CLASS_LABELS[key[0]]


def reviewing_class(key):
    """Whether a class key is a reviewing class: a usable class among REVIEW_CLASSES."""
    return key[0] == "known" and key[1] in REVIEW_CLASSES


def snapshot_value(obj, field):
    v = obj.get(field, MISSING)
    if v is MISSING:
        return "unknown", None, "%s is not on the event" % field
    if v is None:
        return "unknown", None, "%s is recorded as null" % field
    if field == "rewrites_total":
        if not isint(v) or v < 0:
            return "invalid", None, "%s is %s" % (field, "negative" if isint(v) else int_kind(v))
    elif not isnum(v) or v < 0:
        return "invalid", None, "%s is %s" % (field, "negative" if isnum(v) else kind_of(v))
    if beyond(v):
        return "invalid", None, "%s is %s" % (field, beyond(v))
    return "known", v, None


def snapshot_fields(ln):
    """The snapshot fields this event declares, as (field, part, problem): its kind's, a plain run's
    close reading its own `spend_usd` (handsoff.py:7878-7885, an explicit `shape`). The writer
    writes `shape` on the plain run's close alone, and only as PLAIN_SHAPE (handsoff.py:1423, 7881),
    so an absent `shape` is the ordinary close; a present one of another value or kind is invalid
    and null is unknown, and either leaves the close's snapshot named, never read as the ordinary
    close's (problem: (state, note))."""
    if ln.kind == "run-close":
        shape = ln.obj.get("shape", MISSING)
        if shape == PLAIN_SHAPE:
            return (("spend_usd", P_SS, None),)
        if shape is None:
            return (("shape", P_SS, ("unknown", "shape is recorded as null")),)
        if shape is not MISSING:
            return (("shape", P_SS, ("invalid", noted("shape %r is outside the writer's vocabulary" % shape,
                                                      "shape '…' is outside the writer's vocabulary")
                                     if isinstance(shape, str) else "shape is %s" % kind_of(shape))),)
    return tuple((f, p, None) for f, p in SNAPSHOT_FIELDS.get(ln.kind, ()))


def positional(ep):
    """(item, note): the item of the last gate before the opening, by position, or None with
    the reason the association is unresolved."""
    g = ep.gate
    if g is None:
        return None, "no gate before its opening on the record"
    if g.problem:
        return None, "the last gate before its opening (line %d) is invalid: %s" % (g.n, g.problem)
    item = g.obj.get("item", MISSING)
    if not (isinstance(item, str) and item.strip()):
        return None, "the last gate before its opening (line %d) has no usable item (%s)" % (
            g.n, "absent" if item is MISSING else "blank" if isinstance(item, str) else kind_of(item))
    dec = g.obj.get("decision", MISSING)
    if dec == "refuse":
        return None, "the last gate before its opening (line %d) refused item %s" % (g.n, item)
    if dec != "allow":
        return None, "the last gate before its opening (line %d) records %s" % (
            g.n, "no decision" if dec is MISSING else "its decision as null" if dec is None else
            "the decision %r, outside the writer's vocabulary" % dec if isinstance(dec, str) else
            "a decision that is %s" % kind_of(dec))
    if ep.gates_between:
        return None, "a gate at line %d lies between its opening and its close" % ep.gates_between[0]
    return item, "by position: the last gate before its opening, line %d" % g.n


# ------------------------------------------------------------------------ the figures -----

class Fig(object):
    def __init__(self):
        self.rows = []          # (figure, part, value, status, coverage)
        self.summary = []       # the rows the command's summary prints, marked where they are made

    def add(self, figure, part, value, status, coverage, summary=False):
        self.rows.append((figure, part, value, status, coverage))
        if summary:
            self.summary.append(self.rows[-1])


def total_cell(known_sum, n_unknown, fmt):
    """(value, status): a total is complete only when none of its inputs is unavailable;
    otherwise it reads unknown, with its known subtotal beside it."""
    if n_unknown == 0:
        return fmt(known_sum), "complete"
    return "unknown; known subtotal %s" % fmt(known_sum), "unknown"


def gaps_note(n):
    return "%d named gap%s (detail)" % (n, "" if n == 1 else "s")


def compute(recs, an, start, end):
    """Every figure for [start, end) as rows (figure, part, value, status, coverage), the named
    gaps, and what the detail file lists."""
    structural = containment_gaps()
    for rec in recs:
        if rec.status in ("unreadable", "gone"):
            structural.append(Gap(noted("record %s: %s" % (rec.status, rec.reason), "record"), rec.name, None,
                                  ALL_PARTS, run=rec.stem, scope="every report"))
        for ln in rec.bad_lines:
            with boundary('structural', ln.source, (ln.source,), kind_scope(ln.kind)) as live:
                if not live:
                    continue
                if _ACTIVE and ln.source in _ACTIVE.witnesses:
                    continue
                if not reaches(ln, start, end):
                    continue
                parts = ALL_PARTS if ln.kind is None else KIND_PARTS.get(ln.kind, ())
                if parts:
                    structural.append(Gap(ln.problem, ln.where(), ln.ts, parts, run=rec.stem,
                                          lane=ln.lane, cls=class_reach(ln),
                                          src=idle_source(ln.obj) if ln.kind == "phase-boundary" else None))
    for ln, why in an["bad_closes"]:
        if ln.ts is not None and start <= ln.ts < end:
            structural.append(Gap(why, "%s %s" % (ln.where(), helper_text(ln.lane)), ln.ts, EPISODE_PARTS,
                                  run=ln.rec.stem, lane=ln.lane, cls=class_reach(ln)))
    gaps = list(structural)

    def sgaps(part, run=None, lane=None, cls=None, src=None):
        """The structural gaps reaching a part, optionally narrowed to a run, helper, class (a class
        key: a gap bounded to a recorded class reaches only that class's key, never an unusable
        class's) or idle source key; a gap whose own reach is None reaches every one."""
        return sum(1 for g in structural if part in g.parts
                   and (run is None or g.run is None or g.run == run)
                   and (lane is None or g.lane is None or g.lane == lane)
                   and (cls is None or g.cls is None or cls == ("known", g.cls))
                   and (src is None or g.src is None or g.src == src))

    def sgaps_reviewing(part):
        """The structural gaps reaching a review part: only those whose class could be a
        reviewing class (a gap bounded to another class cannot add a reviewing-class episode)."""
        return sum(1 for g in structural if part in g.parts
                   and (g.cls is None or g.cls in REVIEW_CLASSES))

    counted = [ep for ep in an["episodes"] if start <= ep.close.ts < end]
    fig = Fig()

    def field_gap(ep, part, note):
        gaps.append(Gap(note, "%s %s" % (ep.close.where(), helper_text(ep.lane)), ep.close.ts, (part,),
                        run=ep.rec.stem, lane=ep.lane))

    num = lambda v: str(v)

    # Helper time: the close's duration_s, summed exactly; views by run (the record's stem), class
    # (a class key) and helper (the pair of stem and lane).
    known, n_known, n_na, n_unknown = Decimal(0), 0, 0, 0
    views = {"run": {}, "class": {}, "helper": {}}
    for ep in counted:
        with boundary('episode-duration', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            st, v, note = duration_value(ep.close.obj)
            ep.cls, ep.cls_note = class_of(ep)
            ep.duration = (st, v, note)
            if st == "known":
                known = xadd(known, v)
                n_known += 1
            elif st == "na":
                n_na += 1
            else:
                n_unknown += 1
                field_gap(ep, P_H, note)
            for view, key in (("run", ep.rec.stem), ("class", ep.cls), ("helper", (ep.rec.stem, ep.lane))):
                slot = views[view].setdefault(key, [Decimal(0), 0, 0, 0])
                slot[1] += 1
                if st == "known":
                    slot[0] = xadd(slot[0], v)
                elif st == "na":
                    slot[2] += 1
                else:
                    slot[3] += 1
    # A run whose structural gaps reach helper time has a run row even with no counted close.
    for g in structural:
        if P_H in g.parts and g.run is not None:
            views["run"].setdefault(g.run, [Decimal(0), 0, 0, 0])

    def view_gaps(view, key):
        if view == "run":
            return sgaps(P_H, run=key)
        if view == "class":
            return sgaps(P_H, cls=key)
        return sgaps(P_H, run=key[0], lane=key[1])

    def view_text(view, key):
        """A view's key as the reports show it, one text per key and none a label's: a run by shown(),
        since its row shares the detail's view with the total row (VIEW_TOTAL); a class by class_text();
        a helper as its run by shown(), "/" and its lane (a stem holds no "/" and shown() adds none, so
        the first "/" ends the run, and no helper's text begins with a parenthesis)."""
        return (shown(key) if view == "run" else class_text(key) if view == "class"
                else "%s/%s" % (shown(key[0]), helper_text(key[1])))

    def ranked(view):
        """A view's rows, largest known seconds first, then by their text: two stable sorts, so no
        sort key is computed by arithmetic (a negated total was rounded to 28 digits)."""
        return sorted(sort_prepared(views[view].items(), lambda kv: view_text(view, kv[0]),
                                    all_sources(recs), EPISODE_SCOPE), key=lambda kv: kv[1][0], reverse=True)

    s_h = sgaps(P_H)
    value, status = total_cell(known, n_unknown + s_h, fmt_secs)
    fig.add(HELPER, "total", value, status,
            "%s: %d timed, %d not applicable, %d unknown or invalid; %s"
            % (plural(len(counted), "close"), n_known, n_na, n_unknown, gaps_note(s_h)), summary=True)
    for view in ("run", "class", "helper"):
        for key, (secs, n, na, unk) in ranked(view)[:TOP_VIEW]:
            vg = view_gaps(view, key)
            value, status = total_cell(secs, unk + vg, fmt_secs)
            fig.add(HELPER, "%s %s" % (view, view_text(view, key)), value, status,
                    "%s: %d not applicable, %d unknown or invalid; %s"
                    % (plural(n, "close"), na, unk, gaps_note(vg)))

    # Failed closes: the close's exit_class.
    statuses, outside, n_unk, n_completed, resumed, resumed_unsure = {}, {}, 0, 0, 0, 0
    for ep in counted:
        with boundary('episode-exit', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            st, v, note = exit_value(ep.close.obj)
            ep.exit = (st, v, note)
            if st == "known" and v == "completed":
                n_completed += 1
            elif st == "known":
                statuses[v] = statuses.get(v, 0) + 1
                resumed += 1 if ep.resumed_later else 0
            else:
                if st == "outside":
                    outside[v] = outside.get(v, 0) + 1
                else:
                    n_unk += 1
                resumed_unsure += 1 if ep.resumed_later else 0
                field_gap(ep, P_F, note)
    # A recorded value is certain; whether a value outside the vocabulary means completed is not,
    # and an unknown status could be any value.
    s_f = sgaps(P_F)
    unsure_value = n_unk + s_f
    unsure = unsure_value + sum(outside.values())
    value, status = total_cell(len(counted), s_f, num)
    fig.add(FAILED, "closes", value, status, gaps_note(s_f), summary=True)
    value, status = total_cell(n_completed, unsure, num)
    fig.add(FAILED, "completed", value, status, "exit_class completed")
    value, status = total_cell(sum(statuses.values()), unsure, num)
    fig.add(FAILED, "non-completed", value, status,
            "%d with a status outside the writers' vocabulary, %d unknown or invalid; %s"
            % (sum(outside.values()), n_unk, gaps_note(s_f)), summary=True)
    for v in sorted(statuses):
        value, status = total_cell(statuses[v], unsure_value, num)
        fig.add(FAILED, "status %s" % v, value, status, "recorded exit_class")
    for v in sorted(outside):
        value, status = total_cell(outside[v], unsure_value, num)
        fig.add(FAILED, "status outside the writers' vocabulary: %s" % v, value, status,
                "shown as recorded; neither completed nor non-completed")
    value, status = total_cell(n_unk, s_f, num)
    fig.add(FAILED, "status unknown or invalid", value, status, "no usable exit_class")
    value, status = total_cell(resumed, resumed_unsure + s_f, num)
    fig.add(FAILED, "non-completed, later resumed", value, status,
            "a later opening of the same helper on its record; no verdict on lost work")

    # Review activity and possible loops: reviewing-class episodes by class alone; positional
    # candidate groups by the gate before the opening; no evidenced item association exists.
    groups, no_group, no_class, reviewing = {}, 0, 0, []
    for ep in counted:
        with boundary('episode-review', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            ep.item, ep.item_note = None, None
            # Whether the class is usable is the key's state, never the class's text (CR-WASTE5 finding 1).
            if ep.cls[0] != "known":
                no_class += 1
                field_gap(ep, P_RVC, ep.cls_note)
                continue
            if not reviewing_class(ep.cls):
                continue
            reviewing.append(ep)
            if withdrawn(ep.rec, P_RVG):
                ep.item, ep.item_note = None, "unknown: contained positional activity failure"
                continue
            ep.item, ep.item_note = positional(ep)
            if ep.item is None:
                no_group += 1
            else:
                groups.setdefault((ep.rec.stem, ep.item), []).append(ep)
    s_rvc, s_rvg = sgaps_reviewing(P_RVC), sgaps_reviewing(P_RVG)
    value, status = total_cell(len(reviewing), no_class + s_rvc, num)
    fig.add(REVIEW, "reviewing-class episodes", value, status,
            "class %s (set by judgement); a class is not evidence that an episode reviewed "
            "anything; %s with no usable class; %s"
            % (", ".join(REVIEW_CLASSES), plural(no_class, "close"), gaps_note(s_rvc)), summary=True)
    fig.add(REVIEW, "evidenced item associations", "none recorded", "unresolved",
            "no opening or close records the item it serves (FIELDS.md); totals by item and "
            "loops by item are not computed")
    unsure = no_group + no_class + s_rvg
    value, status = total_cell(len(groups), unsure, num)
    fig.add(REVIEW, "positional candidate groups", value, status,
            "reviewing-class episodes grouped by the item of the last gate before the opening; by "
            "position, not an evidenced association; %s" % gaps_note(s_rvg))
    value, status = total_cell(no_group, no_class + s_rvg, num)
    fig.add(REVIEW, "reviewing-class episodes with no positional group", value, status,
            "no gate before the opening, the last gate refused, invalid or without an item, or a "
            "gate between the opening and the close; listed in the detail")
    multi = dict((k, v) for k, v in groups.items() if len(v) >= 2)
    value, status = total_cell(len(multi), unsure, num)
    fig.add(REVIEW, "candidate groups with two or more reviewing-class episodes", value, status,
            "a cue for the Sunday walk-through, not an evidenced loop; listed in the detail")
    fig.add(REVIEW, "rounds", "unresolved", "unresolved",
            "no record carries an item-and-round association; helper names and counts do not "
            "establish rounds or verdicts")

    # Phase boundaries: each boundary's own figures, at its own timestamp.
    bounds = [ln for ln in an["boundaries"] if start <= ln.ts < end]

    def bgap(ln, note, part):
        gaps.append(Gap(note, ln.where(), ln.ts, (part,), run=ln.rec.stem))

    # Idle minutes by source (FIELDS.md, Phase boundaries): a boundary whose idle_min is unusable
    # leaves only its own source's sum unknown; one whose idle_src is unusable could belong to any
    # source, so every source's sum reads unknown.
    idle, idle_any, over, over_unk, rew, rew_unk = {}, 0, 0, 0, 0, 0
    for ln in bounds:
        with boundary('boundary-value', ln.source, (ln.source,), BOUNDARY_SCOPE) as live:
            if not live:
                continue
            o = ln.obj
            v = o.get("idle_min", MISSING)
            src = o.get("idle_src", MISSING)
            key = idle_source(o)
            far = beyond(v) if isnum(v) and v >= 0 else None
            if not (isnum(v) and v >= 0) or far:
                bgap(ln, "idle_min is %s" % ("not on the boundary" if v is MISSING else
                                             "recorded as null" if v is None else
                                             far if far else
                                             "negative" if isnum(v) else kind_of(v)), P_B)
                if key is None:
                    idle_any += 1
                else:
                    idle.setdefault(key, [Decimal(0), 0, 0])[2] += 1
            elif key is None:
                idle_any += 1
                bgap(ln, "idle_src is %s" % ("blank" if isinstance(src, str) else kind_of(src)), P_B)
            else:
                slot = idle.setdefault(key, [Decimal(0), 0, 0])
                slot[0] = xadd(slot[0], v)
                slot[1] += 1
            st, n, note = count_value(o.get("over_cap_reports", MISSING), "over_cap_reports")
            if st == "known":
                over += n
            else:
                over_unk += 1
                bgap(ln, note, P_B)
            v = o.get("rewrites", MISSING)
            if isint(v) and not beyond(v):
                rew += v
            else:
                rew_unk += 1
                bgap(ln, "rewrites is %s" % ("not on the boundary" if v is MISSING else
                                             "recorded as null" if v is None else
                                             beyond(v) if isint(v) else int_kind(v)), P_B)
    # A source an undated or damaged boundary names gets its own row, unknown, even with no
    # dated boundary of that source in the interval.
    for g in structural:
        if P_B in g.parts and g.src is not None:
            idle.setdefault(g.src, [Decimal(0), 0, 0])
    s_b, s_bs = sgaps(P_B), sgaps(P_BS)
    value, status = total_cell(len(bounds), s_b, num)
    fig.add(BOUNDARY, "boundary events", value, status,
            "counted at their own timestamps; %s" % gaps_note(s_b), summary=True)
    for src in sort_prepared(idle, source_text, all_sources(recs), BOUNDARY_SCOPE, route="sort-idle"):
        mins, n, n_unk = idle[src]
        value, status = total_cell(mins, n_unk + idle_any + sgaps(P_B, src=src),
                                   lambda d: "%s min" % fmt_dec(d))
        fig.add(BOUNDARY, "recorded idle, idle_src %s" % source_text(src), value, status,
                "%s%s; not independently verified head idleness"
                % (plural(n, "boundary", "boundaries"),
                   ", %d more without a usable idle_min" % n_unk if n_unk else ""))
    value, status = total_cell(idle_any + sum(x[2] for x in idle.values()), s_b, num)
    fig.add(BOUNDARY, "recorded idle unknown", value, status,
            "boundaries without a usable idle_min or idle_src; sources are never summed together")
    value, status = total_cell(over, over_unk + s_b, num)
    fig.add(BOUNDARY, "over-cap reports", value, status,
            "%s without a usable count" % plural(over_unk, "boundary", "boundaries"))
    value, status = total_cell(rew, rew_unk + s_b, num)
    fig.add(BOUNDARY, "rewrites (deltas)", value, status,
            "%s without a usable delta; cumulative totals never summed"
            % plural(rew_unk, "boundary", "boundaries"))

    # Snapshots: every declared snapshot field of the events in the interval, listed and never
    # summed; an absent, null or invalid one is named.
    snaps = []
    snap_unknown = {P_BS: 0, P_SS: 0}
    snap_known = {P_BS: 0, P_SS: 0}
    for ln in an["snap_events"]:
        with boundary('snapshot-value', ln.source, (ln.source,), kind_scope(ln.kind)) as live:
            if not live:
                continue
            if not start <= ln.ts < end:
                continue
            for field, part, problem in snapshot_fields(ln):
                if withdrawn(ln.rec, part):
                    continue
                st, v, note = (problem[0], None, problem[1]) if problem else snapshot_value(ln.obj, field)
                snaps.append((ln, field, st, v, note))
                if st == "known":
                    snap_known[part] += 1
                else:
                    snap_unknown[part] += 1
                    gaps.append(Gap(note, ln.where(), ln.ts, (part,), run=ln.rec.stem))
    value, status = total_cell(snap_known[P_BS], snap_unknown[P_BS] + s_bs, num)
    fig.add(BOUNDARY, "cumulative rewrites snapshots", value, status,
            "rewrites_total on the boundaries: dated values listed in the detail, never summed; "
            "%d unknown or invalid" % snap_unknown[P_BS])

    # Refusals: helper closes by channel; head fence and the boundary's helper summary apart.
    for ep in counted:
        with boundary('episode-denials', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            ep.denials = denial_values(ep.close.obj)
    for ch in ("tool", "fence", "sandbox"):
        tot, n_k, n_na2, n_u = 0, 0, 0, 0
        for ep in counted:
            with boundary('episode-denials', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
                if not live:
                    continue
                st, n, note = ep.denials[ch]
                if st == "known":
                    tot += n
                    n_k += 1
                elif st == "na":
                    n_na2 += 1
                else:
                    n_u += 1
                    field_gap(ep, CHANNEL_PART[ch], note)
        s_ch = sgaps(CHANNEL_PART[ch])
        value, status = total_cell(tot, n_u + s_ch, num)
        fig.add(REFUSALS, "helper %s" % ch, value, status,
                "%s: %d known, %d not applicable, %d unknown or invalid; %s"
                % (plural(len(counted), "close"), n_k, n_na2, n_u, gaps_note(s_ch)), summary=ch == "sandbox")
    hf, hf_unk, hs, hs_unk = 0, 0, 0, 0
    for ln in bounds:
        with boundary('boundary-refusals', ln.source, (ln.source,), BOUNDARY_SCOPE) as live:
            if not live:
                continue
            st, n, note = count_value(ln.obj.get("head_denials", MISSING), "head_denials")
            if st == "known":
                hf += n
            else:
                hf_unk += 1
                bgap(ln, note, P_RFH)
            st, n, note = count_value(ln.obj.get("denials", MISSING),
                                      "denials (the boundary's helper summary)")
            if st == "known":
                hs += n
            else:
                hs_unk += 1
                bgap(ln, note, P_RFB)
    s_rfh, s_rfb = sgaps(P_RFH), sgaps(P_RFB)
    value, status = total_cell(hf, hf_unk + s_rfh, num)
    fig.add(REFUSALS, "head fence (boundaries)", value, status,
            "%s: %d without a usable head_denials; %s"
            % (plural(len(bounds), "boundary", "boundaries"), hf_unk, gaps_note(s_rfh)))
    value, status = total_cell(hs, hs_unk + s_rfb, num)
    fig.add(REFUSALS, "boundary summary of helper tool refusals", value, status,
            "never added to the helper closes; %s without a usable count; %s"
            % (plural(hs_unk, "boundary", "boundaries"), gaps_note(s_rfb)))

    # Priced spend: the close's cost_src and total_cost_usd; plan usage and unpriced work apart. The
    # dollars are counted by session below (session_spend), never by summing every priced line.
    n_priced, unpriced, na = 0, 0, 0
    bases = ("missing", "undeclared", "unknown-basis", "invalid-price", "invalid-basis")
    tally = dict((k, 0) for k in bases)
    plan = dict((k, 0) for k in ("complete", "zero", "incomplete", "missing", "unknown", "invalid"))
    # Plan tokens by the writer's state (complete and measured zero together; incomplete apart)
    # and by direction, each direction on its own: [known sum, known, unknown or invalid].
    tokens = dict(((pop, d), [0, 0, 0]) for pop in ("complete", "incomplete")
                  for d, _ in TOKEN_DIRECTIONS)
    for ep in counted:
        with boundary('episode-spend', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            basis, v, note = spend_value(ep.close.obj)
            ep.spend, ep.plan = (basis, v, note), None
            if basis == "priced":
                n_priced += 1
            elif basis == "plan":
                st, pnote, toks = plan_usage(ep.close.obj)
                ep.plan = (st, pnote, toks)
                plan[st] += 1
                if st in ("invalid", "unknown"):
                    field_gap(ep, P_SP, pnote)
                elif st != "missing":
                    pop = "incomplete" if st == "incomplete" else "complete"
                    named = []
                    for d, _ in TOKEN_DIRECTIONS:
                        tst, n, tnote = toks[d]
                        slot = tokens[(pop, d)]
                        if tst == "known":
                            slot[0] += n
                            slot[1] += 1
                        else:
                            slot[2] += 1
                            if tnote not in named:      # one gap for a usage object both lack
                                named.append(tnote)
                                field_gap(ep, P_SP, tnote)
            elif basis == "unpriced":
                unpriced += 1
            elif basis == "na":
                na += 1
            else:
                tally[basis] += 1
                field_gap(ep, P_SC, note)
    # Hold beats: a beat whose recorded basis is known but whose amount is missing or invalid
    # leaves only the priced total unknown; only an unknown or invalid basis could move a beat
    # between the priced total and the count of beats not priced.
    beats = [ln for ln in an["beats"] if start <= ln.ts < end]
    b_n, b_other = 0, 0
    b_tally = dict((k, 0) for k in bases)
    for ln in beats:
        with boundary('beat-value', ln.source, (ln.source,), (P_SB,)) as live:
            if not live:
                continue
            basis, v, note = spend_value(ln.obj)
            if basis == "priced":
                b_n += 1
            elif basis in ("plan", "unpriced", "na"):
                b_other += 1
            else:
                b_tally[basis] += 1
                gaps.append(Gap(note, ln.where(), ln.ts, (P_SB,), run=ln.rec.stem))
    # The dollars by session (FIELDS.md, "Priced spend"): a session whose totals read neither as running totals
    # nor as per-pass costs is unclassified, named; one with unusable prices or a line anywhere in its history
    # that cannot be read into it is missing, named; so is a line naming no session, and one whose session
    # cannot be placed is invalid, named.
    sess = session_spend(recs, an, start, end, gaps)
    s_sc, s_sb, s_ss = sgaps(P_SC), sgaps(P_SB), sgaps(P_SS)
    s_priced = sum(1 for g in structural if P_SC in g.parts or P_SB in g.parts)
    both = dict((k, tally[k] + b_tally[k]) for k in bases)
    priced_unsure = sum(both.values()) + sess["missing"] + sess["invalid"] + sess["unclassified"] + s_priced
    value, status = total_cell(sess["total"], priced_unsure, fmt_usd)
    fig.add(SPEND, "priced total (USD, Claude CLI result basis)", value, status,
            "%s and %s, counted by session: a session read as running totals counts its rise over the "
            "interval, a per-pass session its costs in it; %d missing, %d on an undeclared basis, %d invalid, "
            "%d unclassified; %s"
            % (plural(n_priced, "priced close"), plural(b_n, "priced hold beat"),
               both["missing"] + both["unknown-basis"] + sess["missing"], both["undeclared"],
               both["invalid-price"] + both["invalid-basis"] + sess["invalid"], sess["unclassified"],
               gaps_note(s_priced)), summary=True)
    sess["unsure"] = priced_unsure > 0
    # A close whose basis is unknown or invalid could belong to any basis below.
    unsure = tally["unknown-basis"] + tally["invalid-basis"] + s_sc
    value, status = total_cell(sum(plan.values()), unsure, num)
    fig.add(SPEND, "plan usage closes (GPT-6 Astra, not priced)", value, status,
            "complete %d, measured zero %d, incomplete %d, no usage reported %d, unknown %d, "
            "invalid %d" % (plan["complete"], plan["zero"], plan["incomplete"], plan["missing"],
                            plan["unknown"], plan["invalid"]))
    # A plan close of unknown or invalid state, or a close of unknown or invalid basis, could hold
    # tokens of either state; each direction's own unknown or invalid values reach that direction.
    elsewhere = unsure + plan["unknown"] + plan["invalid"]
    could = plan["unknown"] + plan["invalid"] + tally["unknown-basis"] + tally["invalid-basis"]
    for pop, label, members in (
            ("complete", "complete closes", "%s complete or measured zero"
             % plural(plan["complete"] + plan["zero"], "close")),
            ("incomplete", "incomplete closes (the writer's subtotal)",
             "%s marked incomplete by the writer" % plural(plan["incomplete"], "close"))):
        for d, _ in TOKEN_DIRECTIONS:
            total, n_k, n_u = tokens[(pop, d)]
            value, status = total_cell(total, n_u + elsewhere, num)
            if pop == "incomplete" and status == "complete" and plan["incomplete"]:
                status = "incomplete"
            fig.add(SPEND, "plan usage %s tokens, %s" % (d, label), value, status,
                    "%s: %d known, %d unknown or invalid; %s of unknown or invalid state or basis; %s"
                    % (members, n_k, n_u, plural(could, "close"), gaps_note(s_sc)))
    value, status = total_cell(unpriced, unsure, num)
    fig.add(SPEND, "unpriced closes (transcript estimate)", value, status,
            "token totals only; no dollar figure")
    value, status = total_cell(na, unsure, num)
    fig.add(SPEND, "not applicable (no process started)", value, status, "exit_class spawn-failed")
    value, status = total_cell(b_other, b_tally["unknown-basis"] + b_tally["invalid-basis"] + s_sb,
                               num)
    fig.add(SPEND, "hold beats not priced", value, status, "plan usage or no process")
    value, status = total_cell(snap_known[P_SS], snap_unknown[P_SS] + s_ss, num)
    fig.add(SPEND, "cumulative run or head spend snapshots", value, status,
            "dated values listed in the detail; not episode charges, never summed or added; "
            "%d unknown or invalid" % snap_unknown[P_SS])

    return {"rows": fig.rows, "summary": fig.summary, "gaps": gaps, "structural": structural,
            "counted": counted, "views": views, "view_gaps": view_gaps, "view_text": view_text,
            "s_h": s_h, "n_unknown_h": n_unknown, "groups": groups, "reviewing": reviewing,
            "bounds": bounds, "beats": beats, "snapshots": snaps, "spend": sess}


# ------------------------------------------------------------------------ the store -------

class Store(object):
    def __init__(self, path):
        self.path, self.state, self.lines, self.problems = path, "ok", [], []
        self.observed_keys = ()


def store_line_problem(rec):
    if not isinstance(rec, dict):
        return "not a JSON object"
    kind = rec.get("kind")
    if kind not in STORE_KINDS:
        return "an unknown kind %r" % (kind,)

    def text(k):
        return isinstance(rec.get(k), str) and bool(rec.get(k).strip())

    def span(k):
        v = rec.get(k)
        return isinstance(v, list) and len(v) == 2 and all(parse_ts(x) is not None for x in v)

    if kind == "init" and parse_ts(rec.get("at")) is None:
        return "an init line without its time"
    if kind == "report" and not span("interval"):
        return "a report line without a readable interval"
    if kind == "listed" and not (text("key") and span("interval")):
        return "a listed line without its key or its interval"
    if kind == "disposition" and not (text("key") and rec.get("disposition") in DISPOSITIONS
                                      and text("note")):
        return "a disposition line without its key, a known disposition or its note"
    if kind == "abandoned":
        if not (text("episode") and text("evidence") and parse_ts(rec.get("at")) is not None):
            return "an abandoned line without its episode, its evidence or a readable time"
        if episode_suffix(rec["episode"]) is None:
            return "an abandoned line with an invalid opening-line suffix"
        # The held format's line has no line count (the held design's README, "The dispositions store");
        # a line the reader writes carries one, and a count a line carries must be one (CR-WASTE6
        # finding 2).
        if "record_lines" in rec and not isint(rec.get("record_lines")):
            return "an abandoned line whose recorded extent is not a line count"
        if any(k in rec for k in IDENTITY_FIELDS) and structured_identity(rec) is None:
            return ("an abandoned line whose record, helper and line are incomplete or disagree with "
                    "its episode")
    if kind == "run-ended":
        if not (text("run") and text("evidence") and parse_ts(rec.get("at")) is not None
                and isint(rec.get("record_lines"))):
            return "a run-ended line without its run, evidence, time or recorded extent"
        if "record" in rec and rec.get("record") != rec["run"] + ".jsonl":
            return "a run-ended line whose record disagrees with its run"
    return None


def read_store(path):
    st = Store(path)
    if not os.path.lexists(path):
        st.state = "missing"
        st.problems.append("there is no store at %s (created at install by `init`; a store "
                           "missing after that is a continuity failure)" % path)
        return st
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        st.state = "unreadable"
        st.problems.append("the store %s cannot be read (%s)" % (path, exc.strerror))
        return st
    st.sources = tuple(("store", 0, n) for n in range(1, len(data.split(b"\n")) + 1))
    if _ACTIVE:
        for source in st.sources:
            _ACTIVE.register(source, "store line " + str(source[2]))
    first = True
    for n, raw in enumerate(data.split(b"\n"), 1):
        source = ("store", 0, n)
        if guarded("store-blank", source, (source,), (), lambda: not raw.strip(), lambda: False):
            continue
        def decode():
            try:
                text = raw.decode("utf-8")
                rec = json.loads(text)
                if SURROGATE_ESCAPE.search(text) and unpaired_surrogate(rec) is not None:
                    raise ValueError("an unpaired surrogate")
            except (UnicodeDecodeError, ValueError, RecursionError):
                return None
            return immutable_json(rec)
        rec = guarded("store-decode", source, (source,), (), decode, lambda: None)
        if rec is None:
            st.problems.append("line %d: not JSON" % n)
            first = False
            continue
        kind = guarded("store-kind", source, (source,), (),
                       lambda: rec.get("kind") if isinstance(rec, dict) and rec.get("kind") in STORE_KINDS else None,
                       lambda: None)
        if _ACTIVE:
            _ACTIVE.facts[source] = kind
        why = guarded("store-validate", source, (source,), (),
                      lambda: store_line_problem(rec), lambda: "contained validation failure")
        if first and why is None and rec.get("kind") != "init":
            why = "the first line is not the initialisation line"
        elif not first and why is None and rec.get("kind") == "init":
            why = "a second initialisation line"
        first = False
        if why:
            st.problems.append("line %d: %s" % (n, why))
            continue
        # Acquisition does not replay. Publish a whole line candidate, and roll it back
        # even when the failure occurs after publication (the boundary's after hook).
        previous_lines, previous_keys = st.lines, st.observed_keys
        with boundary("store-entry", source, (source,), ()) as live:
            if live:
                entry = StoreEntry(rec, source)
                # Full validation/publication can establish an observation after kind extraction failed.
                keys = previous_keys + ((entry["key"],) if entry["kind"] == "listed" else ())
                st.lines, st.observed_keys = previous_lines + [(n, entry)], keys
        if _ACTIVE and ("store-entry", source) in _ACTIVE.failed:
            st.lines, st.observed_keys = previous_lines, previous_keys
            st.problems.append("line %d: contained store-entry failure" % n)
    if first:
        st.problems.append("the store is empty: it has no initialisation line")
    st.state = "malformed" if st.problems else "ok"
    return st


def append_store(path, records):
    """The store's only write after init: one append of whole lines; never creates the file."""
    data = records if isinstance(records, bytes) else serialise_store(records)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def write_atomic(path, text):
    directory = os.path.dirname(path)
    temp = os.path.join(directory, ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    with open(temp, "wb") as handle:
        handle.write(text if isinstance(text, bytes) else text.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def serialise_store(records):
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records).encode("utf-8")


def now_iso():
    return iso_local(time.time())


# ------------------------------------------------------------------------ determinations --

def episode_last_event(rec, lane, opening):
    last = opening.ts
    for ln in rec.lines:
        if ln.n > opening.n and ln.obj is not None and ln.obj.get("lane") == lane and ln.ts:
            last = ln.ts if last is None or ln.ts > last else last
    return last


# The structured identity an abandoned line carries beside its episode string when the reader's own
# `abandon` wrote it: the opening's record (its file name), helper and line.
IDENTITY_FIELDS = ("record", "helper", "line")
# What a held-format abandoned line, which has no line count of its record, leaves unchecked (CR-WASTE6
# finding 2): its last event, its time and the record's validity are checked; a later line no later than
# that last event is not seen without the count.
HELD_EXTENT = ("; held format, with no line count of its record: an event added later at or before the "
               "record's last event then (the same second, or out of order) cannot be detected")


def positive_line_number(value):
    """Canonical positive ASCII decimal, bounded by the largest addressable byte position.
    Each physical line occupies at least a byte of acquired input; sys.maxsize bounds bytes length.
    Length then lexical comparison precedes int(), independently of the interpreter digit limit.
    """
    if isint(value):
        return value if 1 <= value <= sys.maxsize else None
    limit = str(sys.maxsize)
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value):
        return None
    if len(value) > len(limit) or len(value) == len(limit) and value > limit:
        return None
    return int(value)


def episode_suffix(key):
    if not isinstance(key, str):
        return None
    head, sep, tail = key.rpartition(":")
    return positive_line_number(tail) if sep and ":" in head else None


def cli_line_number(text):
    value = positive_line_number(text)
    if value is None:
        raise argparse.ArgumentTypeError("line must be a positive addressable ASCII decimal")
    return value


def structured_identity(rec):
    """The (record name, helper, opening line) an abandoned store line carries beside its episode
    string, or None: when it carries none of them (the held format), or when they are incomplete, of
    another kind or disagree with its string (store_line_problem names such a line malformed)."""
    name, lane, n = (rec.get(k) for k in IDENTITY_FIELDS)
    if not (isinstance(name, str) and name.endswith(".jsonl") and "/" not in name
            and isinstance(lane, str) and lane.strip() and isint(n) and positive_line_number(n) is not None):
        return None
    if episode_key(name[:-len(".jsonl")], lane, n) != rec.get("episode"):
        return None
    return name, lane, n


def could_open(rec, lane, n):
    """Whether line N of REC could be an opening of the helper LANE, as far as the record shows: never
    in a record not admitted or empty, nor at a line that is absent or of a kind that opens nothing, or
    that opens another helper; possibly in a record whose lines cannot be known (unreadable, gone) and
    at a line whose kind or lane cannot be established."""
    if not rec.admitted or rec.status == "empty":
        return False
    if rec.status != "read":
        return True
    ln = rec.line(n)
    if ln is None:
        return False
    if ln.kind is None:
        return True
    if ln.kind in ALL_OPENINGS:
        return ln.lane is None or ln.lane == lane
    return False


def key_identities(key, by_stem):
    """Every (record, helper, line) the held format's episode string KEY could name among the candidate
    records (BY_STEM: stem to record): each reading of it as a record's stem, ":", a helper, ":" and a line
    number written as "%d" writes one, whose record is a candidate and whose line could open that helper
    there (could_open). A record or a helper may hold ":", so one string can name several openings; the
    reader never picks one of them (CR-WASTE6 finding 1)."""
    m = re.fullmatch(r"(.*):([1-9][0-9]*)", key, re.S)
    if not m:
        return []
    head, n = m.group(1), positive_line_number(m.group(2))
    if n is None:
        return []
    out = []
    for i, ch in enumerate(head):
        if ch != ":":
            continue
        stem, lane = head[:i], head[i + 1:]
        rec = by_stem.get(stem)
        if rec is not None and lane.strip() and could_open(rec, lane, n):
            out.append((rec, lane, n))
    return out


def identity_text(name, lane, n):
    """An opening's structured identity as the reports show it, each part by its repr, as `abandon`
    takes it (--record, --helper, --line)."""
    return "record %r, helper %s, line %d" % (name, helper_text(lane), n)


def determinations(store, recs, an, start):
    """The abandoned and run-ended determinations, as (store line, effect, what it names): applied,
    voided, ambiguous or not yet applicable. An abandoned line names its opening by its structured
    identity when the reader's `abandon` wrote it, else by the held format's episode string alone, which
    applies only where it names exactly one opening of the candidate records: a string that could name
    several applies to none of them (CR-WASTE6 finding 1). Each line holds its record's extent when it
    was made: its last event and, when the reader wrote it, its non-blank line count, so any later event
    in the record, one with the same timestamp included, voids it; a held-format line, with no count, is
    checked by what its fields hold, and its effect names what that leaves unchecked (HELD_EXTENT)."""
    by_stem = dict((r.stem, r) for r in recs)
    by_name = dict((r.name, r) for r in recs)
    # Each opening still open or unresolved, by its identity, never by a string.
    open_kind = dict(((rec.name, lane, op.n), kind) for rec, lane, op, why, kind in an["open"])
    latest = {}
    for n, rec in (store.lines if store else []):
        with boundary('store-group', source_of_store(rec), (source_of_store(rec),), ()) as live:
            if not live:
                continue
            kind = rec.get("kind")
            if kind == "abandoned":
                ident = structured_identity(rec)
                if ident is not None:
                    r = by_name.get(ident[0])
                    cands = [(r, ident[1], ident[2])] if r is not None else []
                else:
                    cands = key_identities(rec["episode"], by_stem)
                # A line is grouped with the others naming the same opening; a string naming none, or
                # several, with the others of that string. The latest line of a group governs it.
                if ident is not None:
                    group = ("abandoned", "opening", ident)
                elif len(cands) == 1:
                    group = ("abandoned", "opening", (cands[0][0].name, cands[0][1], cands[0][2]))
                else:
                    group = ("abandoned", "string", rec["episode"])
                order = (kind, rec["episode"], group)
            elif kind == "run-ended":
                # Keyed by the field its kind is checked to hold (store_line_problem): another field a
                # line also carries, of any kind, is never hashed or ordered.
                cands, group = None, ("run-ended", rec["run"])
                order = (kind, rec["run"], group)
            else:
                continue
            if group not in latest or parse_ts(rec["at"]) >= parse_ts(latest[group][1]["at"]):
                latest[group] = (order, rec, cands)
    applied = []
    left_out = set()
    ended_runs = {}
    for order, rec, cands in sort_prepared(latest.values(), lambda v: v[0], tuple(source_of_store(v[1]) for v in latest.values()), (), route="sort-store"):
        with boundary('store-apply', source_of_store(rec), (source_of_store(rec),), ()) as live:
            if not live:
                continue
            at = parse_ts(rec["at"])
            if rec["kind"] == "abandoned":
                what = rec["episode"]
                ident = structured_identity(rec)
                if ident is not None and [(c[0].name, c[1], c[2]) for c in key_identities(what, by_stem)] != [ident]:
                    what = "%s (%s)" % (what, identity_text(*ident))
                if what == rec["episode"]:
                    what = helper_text(what)
                else:
                    what = helper_text(rec["episode"]) + " (" + identity_text(*ident) + ")"
                if len(cands) > 1:
                    applied.append((rec, "ambiguous: its episode string could name %d openings (%s); it applies "
                                         "to none of them" % (len(cands), "; ".join(
                                             identity_text(r.name, lane, n) for r, lane, n in cands)), what))
                    continue
                r, lane, n = cands[0] if cands else (None, None, None)
                if authority("abandoned") or any(uncertain_record(c[0]) for c in cands):
                    applied.append((rec, "unknown: exclusion authority or record eligibility unavailable", what))
                    continue
                if r is None or not r.readable or open_kind.get((r.name, lane, n)) != "open":
                    applied.append((rec, "void: the episode is no longer open on its record", what))
                    continue
                if r.bad_lines:
                    applied.append((rec, "void: its record holds invalid or undated lines, so no "
                                         "determination applies until it is mended", what))
                    continue
                counted = "record_lines" in rec
                if ((counted and len(r.lines) != rec["record_lines"]) or r.last_ts is None or r.last_ts > at
                        or parse_ts(rec.get("record_last_event")) != r.last_ts):
                    applied.append((rec, "void: an event after the determination is on its record; "
                                         "the episode is named as open again", what))
                    continue
                limit = "" if counted else HELD_EXTENT
                if start >= at:
                    left_out.add((r.name, lane, n))
                    applied.append((rec, "applied: left out of the open list (this interval begins "
                                         "after the determination)" + limit, what))
                else:
                    applied.append((rec, "recorded, not yet applicable: this interval begins before "
                                         "the determination, so the episode stays named, incomplete, "
                                         "duration unknown" + limit, what))
            else:
                key = rec["run"]
                r = by_stem.get(key)
                if authority("run-ended") or r is not None and uncertain_record(r):
                    applied.append((rec, "unknown: ending authority or record eligibility unavailable", key))
                    continue
                lines_now = len(r.lines) if r is not None and r.readable else None
                if r is None or lines_now != rec.get("record_lines") or (
                        r.last_ts is not None and parse_ts(rec.get("record_last_event")) != r.last_ts):
                    applied.append((rec, "void: its record changed after the determination", key))
                    continue
                if start >= at:
                    ended_runs[key] = rec
                    applied.append((rec, "applied: the run is listed as ended, not open", key))
                else:
                    applied.append((rec, "recorded, not yet applicable: this interval begins before it", key))
    return applied, left_out, ended_runs


# ------------------------------------------------------------------------ rendering -------

def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


# Every character str.splitlines() ends a line at. Only a recorded value can hold one (no text of the reader's
# does), so a report line holding one is a recorded value starting a line of its own, which could read as a
# total row or a placeholder ("- (all): ...", "- none").
LINE_ENDS = re.compile("[\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]")


def one_line(text):
    """A report line kept to one line: each line-ending character a recorded value holds shown by its escape, as
    repr shows it (\\n, \\u2028), so no recorded value starts a line, and so none prints a label's row."""
    text = LONE_SURROGATE.sub(lambda m: "\\u%04x" % ord(m.group()), text)
    return LINE_ENDS.sub(lambda m: repr(m.group())[1:-1], text)


def render_rows(rows):
    out = ["| Figure | Part | Value | Status | Coverage |", "|---|---|---|---|---|"]
    for r in rows:
        if _ACTIVE is None:
            out.append("| " + " | ".join(cell(x) for x in r) + " |")
            continue
        parts = (BOUNDARY_SCOPE if r[0] == BOUNDARY else EPISODE_SCOPE
                 if r[0] in (HELPER, FAILED, REVIEW) else ALL_PARTS)
        sources = all_sources(_ACTIVE.current_recs)
        route = "main-row-" + FIGURE_KEYS[r[0]]
        with boundary(route, GLOBAL_OWNER, sources, parts) as live:
            if live:
                out.append("| " + " | ".join(cell(x) for x in r) + " |")
            else:
                out.append("| " + r[0] + " | total | unknown | unknown | terminal row failure |")
    return out


def coverage_counts(recs, an, start, end, left_out):
    c = {}
    for rec in recs:
        c[rec.status] = c.get(rec.status, 0) + 1
    readable = [r for r in recs if r.status == "read"]
    c["without run-open"] = sum(1 for r in readable if not r.has_run_open)
    c["touching"] = sum(1 for r in readable if any(ln.ts is not None and start <= ln.ts < end
                                                   for ln in r.lines))
    c["outside"] = len(readable) - c["touching"]
    c["bad records"] = sum(1 for r in readable if r.bad_lines)
    # LEFT_OUT holds identities, (record name, helper, opening line), never strings (CR-WASTE6 finding 1).
    open_eps = [o for o in an["open"] if (o[0].name, o[1], o[2].n) not in left_out]
    c["open"] = len(open_eps)
    c["open after"] = sum(1 for o in open_eps if o[2].ts is not None and o[2].ts >= end)
    c["unresolved eps"] = sum(1 for o in open_eps if o[4] == "unresolved")
    c["hist"] = len(an["hist"])
    return c, open_eps


def gap_reason_group(g):
    """A gap's group in the coverage section: the group its reason carries (Reason), set where the
    reason was made; a plain reason quotes no recorded value and is its own group. The reason's text,
    which may quote recorded values, is never parsed to find it (CR-WASTE5 finding 1)."""
    return g.reason.group if isinstance(g.reason, Reason) else g.reason


def hist_note(kind):
    if kind in HIST_OPENINGS:
        return " (historical name, read as %s)" % HIST_OPENINGS[kind]
    if kind in HIST_CLOSES:
        return " (historical name, read as %s)" % HIST_CLOSES[kind]
    return ""


def render(recs, an, res, ctx):
    start, end = ctx["start"], ctx["end"]
    cov, open_eps = coverage_counts(recs, an, start, end, ctx["left_out"])
    detail_name = os.path.basename(ctx["detail_path"])
    lines = ["# Weekly waste report, records only: %s" % interval_label(start, end), "",
             PURPOSE, ""]
    if ctx["store_problems"]:
        lines += ["**Store continuity failure:** %s. %s" % (
            "; ".join(ctx["store_problems"]), ctx["store_effect"]), ""]
    zone = "/".join(time.tzname) if time.tzname else "local"
    lines += [
        # Each end to the minute, or to the second where it has one (a start a store line set within a
        # minute), as its label does: no two intervals read the same.
        "- Interval: [%s, %s), local time (%s)." % (fmt_local(start, endpoint_seconds(start)),
                                                     fmt_local(end, endpoint_seconds(end)), zone),
        "- Acquired: %s to %s; every figure is the records as they stood then. Completeness "
        "refers only to these declared record inputs; it cannot establish that an unrecorded run "
        "or a record missing before enumeration never existed." % (
            fmt_local(ctx["acq_start"]), fmt_local(ctx["acq_end"])),
        "- Runtime: %.2f s; input %d bytes in %d lines of %d files read from %s. The head's "
        "reading cost of this report: unmeasured until observed." % (
            ctx["runtime"], ctx["volume"]["bytes"], ctx["volume"]["lines"],
            ctx["volume"]["files"], ctx["records_dir"]),
        "- Episodes count wholly at their close; boundary events at their own timestamps. "
        "Report generation succeeding is not evidence of completeness.",
        "- Detail: [%s](%s), every named gap with the figures it affects." % (detail_name, detail_name),
        "", "## Coverage by reason", ""]
    unadmitted = [r.name for r in recs if not r.admitted]
    lines += [
        "- Candidate records: %d `*.jsonl` names in the records folder, each admitted or not by "
        "its name alone before any file was opened: %d admitted as run records (%d read, %d "
        "empty, %d unreadable, %d gone during acquisition), %d not admitted." % (
            len(recs), len(recs) - len(unadmitted), cov.get("read", 0), cov.get("empty", 0),
            cov.get("unreadable", 0), cov.get("gone", 0), len(unadmitted))]
    if unadmitted:
        # Each name left out by its name, in name order; the line says which kinds it holds (FIELDS.md,
        # "Admission"): the pinned event logs and the command checker's read logs.
        candidates = frozenset(r.name for r in recs)
        n_logs = sum(1 for n in unadmitted if read_log(n, candidates))
        n_pinned = len(unadmitted) - n_logs
        logs = " of the command checker (`<run>-unplaced-reads.jsonl`)"
        kinds = ("event logs pinned by their names" if not n_logs else "read logs" + logs if not n_pinned else
                 "%s pinned by name and %s%s" % (plural(n_pinned, "event log"), plural(n_logs, "read log"), logs))
        lines.append("- Not admitted by name: %d, %s, never opened, their contents unread and "
                     "unknown; no figure reads them (FIELDS.md, \"Admission\"):" % (len(unadmitted), kinds))
        lines += ["  - `%s`" % n for n in unadmitted]
    else:
        lines.append("- Not admitted by name: 0.")
    lines += [
        "- Other entries in the records folder: %d, not named `*.jsonl`, so not candidates; none "
        "opened or listed." % ctx["others"],
        "- Records read: %d with events in the interval, %d outside it; %d without run-open "
        "(counted like any other)." % (cov["touching"], cov["outside"], cov["without run-open"]),
        "- Records holding invalid or undated lines: %d, each named in the detail in every report "
        "until mended." % cov["bad records"],
        "- Episodes open or unresolved at acquisition: %d (%d opened after the interval's end; %d "
        "unresolved by an invalid close or opening), named in the detail; such an episode counts "
        "nowhere until a valid close resolves it." % (cov["open"], cov["open after"],
                                                      cov["unresolved eps"]),
        "- Runs open at acquisition: %s." % (
            "unknown" if any(status == "unknown" for _, _, status in an["runs"])
            else str(sum(1 for r, _, _ in an["runs"] if r.stem not in ctx["ended_runs"]))),
        "- Lines under a historical event name (FIELDS.md): %d, each marked in the detail." % cov["hist"],
    ]
    for r, ln, status in an["runs"]:
        if status == "unknown":
            lines.append("- Run %s: state unknown; observed run transition at line %d." % (r.stem, ln.n))
    groups = {}
    for g in res["gaps"]:
        with boundary('main-gap', GLOBAL_OWNER, all_sources(recs), ALL_PARTS) as live:
            if not live:
                continue
            k = gap_reason_group(g)
            slot = groups.setdefault(k, [0, set()])
            slot[0] += 1
            slot[1].update(p.split(":")[0] for p in g.parts)
    lines.append("- Named gaps affecting this interval's figures: %d%s" % (
        len(res["gaps"]), ":" if groups else "."))
    for k in sorted(groups):
        n, figs = groups[k]
        lines.append("  - %s: %d (affects %s)" % (k, n, ", ".join(f for f in FIGURES if f in figs)))
    lines += ["", "## Figures", "",
              "Each total is complete only when every input it declares is available; otherwise "
              "it reads unknown with its known subtotal. A missing field is never a zero. A gap "
              "counts only against the parts, runs, helpers, classes, idle sources and spend bases "
              "its input could feed.", ""]
    lines += render_rows(res["rows"])
    lines += ["", GUIDANCE, ""]
    lines += ["## Determinations applied", ""]
    if ctx["determinations"]:
        for rec, effect, what in ctx["determinations"]:
            with boundary('main-determination', source_of_store(rec), (source_of_store(rec),), ()) as live:
                if not live:
                    continue
                lines.append("- %s %s at %s: %s. Evidence: %s" % (
                    rec["kind"], what, rec["at"], effect, rec.get("evidence")))
    else:
        lines.append("- none")
    lines += ["", "## Dispositions", "",
              "The store `%s` is the one authority; editing this list changes nothing. Record one "
              "with `weekly-waste.py dispose <key> <fixed|registered|kept|owner> --note \"...\"`."
              % ctx["store_path"], ""]
    for key, status in ctx["keys"]:
        with boundary('main-key', GLOBAL_OWNER, all_sources(recs) + ctx["store_sources"], ALL_PARTS) as live:
            if not live:
                lines.append("- " + terminal_text(key) + ": undetermined (terminal key presentation)")
                continue
            lines.append("- %s: %s" % (key, status))
    lines += ["", "Recorded since the previous report:", ""]
    if ctx["since_prev"]:
        for rec in ctx["since_prev"]:
            with boundary('main-history', source_of_store(rec), (source_of_store(rec),), ()) as live:
                if not live:
                    lines.append("- " + terminal_text(rec["key"]) + ": unknown (history presentation unavailable)")
                    continue
                lines.append("- %s: %s (%s)" % (rec["key"], rec["disposition"], rec["note"]))
    else:
        lines.append(empty_history_text(ctx))

    d = ["# Weekly waste report detail: %s" % interval_label(start, end), "",
         "Companion of %s. Read to judge a specific item." % os.path.basename(ctx["report_path"]), ""]
    d += ["## Named gaps and the figures they affect", ""]
    if not res["gaps"]:
        d.append("- none")
    for g in sort_prepared(res["gaps"], lambda g: (g.where, str(g.reason), g.parts), all_sources(recs), ALL_PARTS, route="sort-gap"):
        gap_route, gap_parts = gap_domain(g)
        with boundary(gap_route, g.owner, g.sources, gap_parts) as live:
            if not live:
                d.append("- " + "; ".join(_ACTIVE.labels[source] for source in g.sources)
                         + " · unknown (terminal gap presentation) · affects: "
                         + ("; ".join(gap_parts) if gap_parts else "event coverage/eligibility"))
                continue
            d.append("- %s · %s · %s · affects: %s%s" % (
                g.where, fmt_local(g.when) if g.when is not None else "time unknown", g.reason,
                "; ".join(g.parts) if g.parts != ALL_PARTS else "every figure",
                " · named in every report" if g.scope == "every report" else ""))
    d += ["", "## Inventory: every candidate record", "",
          "| Record | Status | Bytes | Lines | First event | Last event | run-open | Invalid or undated lines | Dated order |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in recs:
        # A record not read shows "-" for what only its contents could tell.
        with boundary('detail-inventory', r.anchor, record_sources(r), ALL_PARTS) as live:
            if not live:
                d.append("| " + _ACTIVE.labels[r.anchor] + " | unknown | " + str(r.size)
                         + " | unknown | unknown | unknown | unknown | unknown | unknown |")
                continue
            status = r.status + (": " + r.reason if r.reason else "")
            d.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                cell(r.name), cell(status),
                r.size if r.size is not None else "-", len(r.lines) if r.opened else "-",
                fmt_local(r.first_ts) if r.first_ts is not None else "-",
                fmt_local(r.last_ts) if r.last_ts is not None else "-",
                ("yes" if r.has_run_open else "no") if r.readable else "-",
                len(r.bad_lines) if r.readable else "-",
                ("ordered" if r.ordered else "unordered") if r.readable else "-"))
    d += ["", "## Records holding invalid or undated lines (named in every report)", ""]
    any_bad = False
    for r in recs:
        with boundary('detail-inventory', r.anchor, record_sources(r), ALL_PARTS) as live:
            if not live:
                any_bad = True
                d.append("- " + _ACTIVE.labels[r.anchor] + " · unknown: invalid-line inventory unavailable")
                continue
            for ln in r.bad_lines:
                with boundary('detail-invalid', ln.source, (ln.source,), kind_scope(ln.kind)) as live:
                    if not live:
                        any_bad = True
                        d.append("- " + _ACTIVE.labels[ln.source] + " · unknown: invalid-line presentation unavailable")
                        continue
                    any_bad = True
                    span = ("its own time %s" % fmt_local(ln.ts) if ln.ts is not None else
                            "between %s and %s" % (fmt_local(ln.lo) if ln.lo is not None else "the start",
                                                   fmt_local(ln.hi) if ln.hi is not None else "the end")
                            if r.ordered else "any time (its record's dated lines are not in order)")
                    d.append("- %s · %s · kind %s · %s · %s" % (
                        ln.where(), ln.problem, ln.kind or "unknown", span,
                        "reaches this interval" if reaches(ln, start, end) else "outside this interval"))
    if not any_bad:
        d.append("- unknown: invalid-line inventory unavailable for affected records"
                 if any(uncertain_record(r) for r in recs) else "- none")
    by_stem = dict((r.stem, r) for r in recs)

    def episode_text(rec, lane, n):
        """An episode as the detail names it: its key, and, where that string could name another opening
        as well (a record or a helper holding ":"), its record, helper and line beside it, which
        `abandon` takes as --record, --helper and --line (CR-WASTE6 finding 1)."""
        key = episode_key(rec.stem, lane, n)
        if len(key_identities(key, by_stem)) > 1:
            return "%s (%s)" % (helper_text(key), identity_text(rec.name, lane, n))
        return "%s:%s:%d" % (shown(rec.stem), helper_text(lane), n)

    d += ["", "## Episodes open or unresolved at acquisition", ""]
    for rec, lane, op, why, kind in open_eps:
        with boundary('detail-open', op.source, record_sources(rec), EPISODE_SCOPE) as live:
            if not live:
                continue
            d.append("- %s · %s · opened %s%s · %s%s%s" % (
                episode_text(rec, lane, op.n), kind, fmt_local(op.ts), hist_note(op.kind), why,
                " · opened after the interval's end" if op.ts is not None and op.ts >= end else "",
                " · its record holds invalid lines" if rec.bad_lines else ""))
    if not open_eps:
        d.append("- unknown: contained open-state failure" if any(uncertain_record(r) for r in recs) or authority("abandoned") else "- none")
    d += ["", "## Runs open at acquisition", ""]
    runs = an["runs"]
    for r, ln, status in runs:
        with boundary('detail-run', ln.source, record_sources(r), ()) as live:
            if not live:
                d.append("- " + terminal_text(r.stem) + " · state unknown (terminal run presentation)")
                continue
            if status == "unknown":
                d.append("- %s · state unknown · observed run transition at %s (line %d)"
                         % (r.stem, fmt_local(ln.ts), ln.n))
                continue
            d.append("- %s · last run-open or run-resume at %s (line %d)%s" % (
                r.stem, fmt_local(ln.ts), ln.n,
                " · ended by determination" if r.stem in ctx["ended_runs"] else ""))
    if not runs:
        d.append("- unknown: contained run-state failure" if any(uncertain_record(r) for r in recs) or authority("run-ended") else "- none")
    d += ["", "## Episodes closing in the interval", "",
          "| Episode | Class | Opening | Close | Duration | Exit | Tool | Fence | Sandbox | Spend basis | Positional group |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]

    def state_text(t):
        st, v, note = t
        if st == "known":
            return ("0 (measured zero)" if v == 0 else fmt_dec(v)) if not isinstance(v, str) else v
        if st == "na":
            return "not applicable (%s)" % note
        return "%s (%s)" % (st, note)

    for ep in res["counted"]:
        with boundary('detail-episode', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            sp = ep.spend
            if sp[0] == "plan":
                # The writer's state as recorded, then each token direction's own value (none for a
                # close with no usage reported, whose zeros the writer marks as no measurement).
                pst, pnote, toks = ep.plan
                spend = "plan usage, %s%s" % (pst, " (%s)" % pnote if pnote else "")
                if pst != "missing":
                    spend += "; input %s, output %s" % (state_text(toks["input"]),
                                                        state_text(toks["output"]))
            elif sp[0] in ("priced", "undeclared"):
                spend = "%s $%s" % (sp[0], fmt_dec(sp[1], 2))
            else:
                spend = sp[0] + (" (%s)" % sp[2] if sp[2] else "")
            d.append("| %s | %s | %s line %d%s, %s | %s line %d%s, %s%s | %s | %s | %s | %s | %s | %s | %s |" % (
                cell(episode_text(ep.rec, ep.lane, ep.opening.n)), cell(class_text(ep.cls)), ep.opening.kind,
                ep.opening.n, hist_note(ep.opening.kind),
                fmt_local(ep.opening.ts), ep.close.kind, ep.close.n, hist_note(ep.close.kind),
                fmt_local(ep.close.ts), cell("; " + "; ".join(ep.notes) if ep.notes else ""),
                cell(state_text(ep.duration)),
                cell(state_text(ep.exit) + (" (later resumed)" if ep.resumed_later and ep.exit[1] != "completed" else "")),
                cell(state_text(ep.denials["tool"])), cell(state_text(ep.denials["fence"])),
                cell(state_text(ep.denials["sandbox"])), cell(spend),
                cell("-" if not reviewing_class(ep.cls) else
                     ("item %s (%s)" % (ep.item, ep.item_note)) if ep.item is not None else
                     ("unknown: %s" if withdrawn(ep.rec, P_RVG) else "none: %s") % ep.item_note)))
    d += ["", "## Lines under a historical event name (named in every report)", "",
          "Read by the compatibility rule in FIELDS.md: an opening or close under a historical "
          "name reads as the writers' event, its values from the writers' field names only; an "
          "end marker closes nothing and is noted on the episode it follows.", ""]
    for ln in an["hist"]:
        with boundary('detail-history', ln.source, (ln.source,), kind_scope(ln.kind)) as live:
            if not live:
                continue
            d.append("- %s · %s · %s · helper %s · %s" % (
                ln.where(), fmt_local(ln.ts), ln.kind, helper_text(ln.lane) if ln.lane is not None else UNUSABLE_LANE,
                "read as %s" % (HIST_OPENINGS.get(ln.kind) or HIST_CLOSES.get(ln.kind))
                if ln.kind in HIST_OPENINGS or ln.kind in HIST_CLOSES
                else "an end marker, not a close"))
    if not an["hist"]:
        d.append("- unknown: contained historical coverage failure" if any(uncertain_record(r) for r in recs) else "- none")
    d += ["", "## Helper time by run, class and helper", "",
          "The three views count the same episodes; concurrent durations add as helper "
          "consumption, not elapsed time. A view total is unknown when any of its closes has no "
          "usable duration or a named gap reaches it.", ""]
    for view in ("run", "class", "helper"):
        with boundary('detail-view', GLOBAL_OWNER, all_sources(recs), EPISODE_SCOPE) as live:
            if not live:
                continue
            tot, n, unk = Decimal(0), 0, 0
            d.append("### By %s" % view)
            text = lambda key, view=view: res["view_text"](view, key)
            for key, (secs, cnt, na, u) in sort_prepared(res["views"][view].items(), lambda kv: text(kv[0]), all_sources(recs), EPISODE_SCOPE, route="sort-view"):
                vg = res["view_gaps"](view, key)
                value, _ = total_cell(secs, u + vg, fmt_secs)
                d.append("- %s: %s over %s (%d not applicable, %d unknown or invalid; %s)"
                         % (text(key), value, plural(cnt, "close"), na, u, gaps_note(vg)))
                tot = xadd(tot, secs)
                n += cnt
                unk += u
            value, _ = total_cell(tot, unk + res["s_h"], fmt_secs)
            # Each view's total row (VIEW_TOTAL, a label apart from every recorded run, class and helper:
            # CR-WASTE6 finding 3) is the helper-time total over the same episodes.
            d.append("- %s: %s over %s (%d unknown or invalid; %s)"
                     % (VIEW_TOTAL, value, plural(n, "close"), unk, gaps_note(res["s_h"])))
            d.append("")
    d += ["## Review activity: reviewing-class episodes and positional candidate groups", "",
          GUIDANCE, "",
          "- Evidenced item associations: none recorded. No opening or close records the item it "
          "serves (FIELDS.md), so no episode is tied to an item by the record, and rounds stay "
          "unresolved.",
          "- Reviewing-class episodes are counted by class alone (%s); a class is not evidence that "
          "an episode reviewed anything." % ", ".join(REVIEW_CLASSES),
          "- Positional candidate groups gather the reviewing-class episodes whose last gate before "
          "the opening is dated, allowed and names an item, with no gate between the opening and "
          "the close: a cue for the walk-through, not an association.", ""]
    for (stem, item), eps in sorted(res["groups"].items()):
        # Distinct (helper, class) pairs, as pairs: never as joined text, which two pairs could share.
        with boundary('detail-group', eps[0].opening.source, tuple(s for ep in eps for s in episode_sources(ep)), EPISODE_SCOPE) as live:
            if not live:
                continue
            helpers = ["%s %s" % (helper_text(lane), cls) for lane, cls in sorted(set((e.lane, e.cls[1]) for e in eps))]
            gate_lines = sorted(set(e.gate.n for e in eps))
            d.append("- %s · item %s · %s from %s (%s) · gate line%s %s · grouped by position, not an "
                     "evidenced association%s · rounds unresolved"
                     % (stem, item, plural(len(eps), "reviewing-class episode"),
                        plural(len(set(e.lane for e in eps)), "helper"), ", ".join(helpers),
                        "" if len(gate_lines) == 1 else "s", ", ".join(str(g) for g in gate_lines),
                        " · two or more: a cue for the Sunday walk-through, not an evidenced loop"
                        if len(eps) >= 2 else ""))
    for ep in res["reviewing"]:
        with boundary('detail-review', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            if ep.item is None:
                d.append("- %s %s (%s) · no positional group: %s" % (ep.rec.stem, helper_text(ep.lane), ep.cls[1],
                                                                     ep.item_note))
    if not res["reviewing"]:
        d.append("- unknown: reviewing-class membership unavailable" if any(withdrawn(r, P_RVC) for r in recs) else "- no reviewing-class episode closed in the interval")
    d += ["", "## Phase boundaries", ""]
    for ln in res["bounds"]:
        with boundary('detail-boundary', ln.source, (ln.source,), BOUNDARY_SCOPE) as live:
            if not live:
                continue
            o = ln.obj
            # As recorded: `from` and `to` by repr (a string quoted), every other field by as_recorded
            # (an absent or null field as None, a string that could read as None quoted).
            d.append("- %s · %s · from %r to %r · idle_min %s (%s) · over_cap_reports %s · rewrites %s "
                     "(cumulative %s) · denials %s · head_denials %s (%s) · run_spend_usd %s" % ((
                         ln.where(), fmt_local(ln.ts), o.get("from"), o.get("to")) + tuple(as_recorded(v) for v in (
                             o.get("idle_min"), o.get("idle_src"), o.get("over_cap_reports"), o.get("rewrites"),
                             o.get("rewrites_total"), o.get("denials"), o.get("head_denials"),
                             o.get("head_denials_src"), o.get("run_spend_usd")))))
    if not res["bounds"]:
        d.append("- unknown: contained membership failure" if any(withdrawn(r, P_B) for r in recs) else "- none")
    d += ["", "## Cumulative snapshots (dated, never summed)", ""]
    for ln, field, st, val, note in res["snapshots"]:
        with boundary('detail-snapshot', ln.source, (ln.source,), kind_scope(ln.kind)) as live:
            if not live:
                continue
            d.append("- %s · %s · %s · %s" % (ln.where(), fmt_local(ln.ts), ln.kind,
                                              "%s %s" % (field, val) if st == "known"
                                              else "%s (%s)" % (st, note)))
    if not res["snapshots"]:
        d.append("- unknown: contained membership failure" if any(withdrawn(r, P_SS) for r in recs) else "- none")
    exact = Decimal(0)
    for ep in res["counted"]:
        with boundary('detail-exact', ep.opening.source, episode_sources(ep), EPISODE_SCOPE) as live:
            if not live:
                continue
            if ep.spend[0] == "priced" and not withdrawn(ep.rec, P_SC):
                exact = xadd(exact, ep.spend[1])
    sess = res["spend"]
    read = sess.get("read")
    d += ["", "## Priced spend, exact", "",
          "- priced closes, sum of the recorded values: %s$%s (the main report rounds to the cent)"
          % ("unknown; known subtotal " if any(P_SC in g.parts for g in res["structural"]) else "",
             fmt_dec(exact, 2)),
          # The main report's figure (FIELDS.md, "Priced spend"): a running total's lines repeat its earlier
          # passes' cost, so the sum above counts such a resumed session's earlier passes again.
          "- priced spend as the main report counts it, by session: %s$%s over %s: a session read as running "
          "totals counts its last total before the interval's end less its last before the start, a per-pass "
          "session the sum of its costs in the interval, a session of one line its total (the main report rounds "
          "to the cent)"
          % ("unknown; known subtotal " if sess["unsure"] else "", fmt_dec(sess["total"], 2),
             plural(sess["sessions"], "session")),
          "- sessions with a line in the interval, by how their totals read: %s" % (
              "unknown" if read is None else "%d as running totals, %d as per-pass costs, %d as neither, %d of one "
              "result-basis line before the interval's end" % (read["running"], read["per-pass"],
                                                               read["unclassified"], read["one"])),
          "- sessions with a line in the interval and more than one session line before its end, each "
          "below: %d" % len(sess["detail"])]
    d += sess["detail"]
    d += ["", "## Hold beats", ""]
    for ln in res["beats"]:
        with boundary('detail-beat', ln.source, (ln.source,), (P_SB,)) as live:
            if not live:
                continue
            d.append("- %s · %s · cost_src %s · total_cost_usd %s" % (
                ln.where(), fmt_local(ln.ts), as_recorded(ln.obj.get("cost_src")),
                as_recorded(ln.obj.get("total_cost_usd"))))
    if not res["beats"]:
        d.append("- unknown: contained membership failure" if any(withdrawn(r, P_SB) for r in recs) else "- none")
    d += ["", "## Per-run waste tables (linked by path, never read)", ""]
    rendered_tables = 0
    for stem, path in ctx["tables"]:
        with boundary('detail-table', GLOBAL_OWNER, all_sources(recs), ()) as live:
            if not live:
                continue
            d.append("- %s: [%s](<%s>)" % (stem, os.path.basename(path), path))
            rendered_tables += 1
    if not ctx["tables_available"]:
        d.append("- unknown: table selection unavailable; %d rendered" % rendered_tables)
    elif not ctx["tables"]:
        d.append("- none found")
    elif not rendered_tables:
        d.append("- unknown: link presentation unavailable; 0 rendered")
    lines += ["", "## Per-run waste tables", "",
              "%d linked in the detail (each run's own table, by path, never regenerated or read)."
              % rendered_tables, ""]
    if not ctx["tables_available"]:
        lines.append("Table selection unknown; the count above describes rendered links only.")
    main = "\n".join(one_line(l) for l in lines)
    if _ACTIVE.ledger:
        observations = observed_key_text(ctx)
        main += observations
        d.extend(observations.splitlines())
    d.append("")
    return main + "\n", "\n".join(one_line(l) for l in d)


# ------------------------------------------------------------------------ commands --------

def tools_dir_of(args):
    """The folder holding the store: --tools-dir, else `tools/weekly-waste` in the run store."""
    return os.path.realpath(args.tools_dir or os.path.join(store_given(), "tools", "weekly-waste"))


def reports_dir_of(args):
    """Where the reports go: `reports/` under --tools-dir when one is named, else the vault's
    `output/reports`, the user's layer, which the shipped ignore file keeps out of every push. The
    vault is three folders above this script's own (`.claude/skills/<skill>/`)."""
    if args.tools_dir:
        return os.path.join(tools_dir_of(args), "reports")
    vault = os.path.abspath(__file__)
    for _ in range(4):
        vault = os.path.dirname(vault)
    return os.path.realpath(os.path.join(vault, "output", "reports"))


def records_given(args):
    """The records folder as given (--records), else as the run store names it."""
    return args.records or os.path.join(store_given(), "spawn-records")


def records_dir_of(args):
    return os.path.realpath(records_given(args))


def snapshot_records(recs):
    """Immutable envelope tuples; decoded JSON is owned by acquisition and never mutated.
    Each generation receives fresh line/record/episode objects, not the previous derived state.
    """
    return tuple((tuple((k, v) for k, v in r.__dict__.items() if k not in ("lines", "bad_lines", "_by_n")),
                  tuple(Envelope(ln.source, ln.kind, ln.ts, ln.obj, ln.problem, ln.lane, ln.lo, ln.hi)
                        for ln in r.lines)) for r in recs)


def fresh_records(snapshot):
    out = []
    for attrs, envelopes in snapshot:
        r = Rec.__new__(Rec)
        r.__dict__.update(attrs)
        r.lines, r.bad_lines, r._by_n = [], [], None
        for e in envelopes:
            ln = Line(r, e.source[2])
            for field in Envelope._fields:
                setattr(ln, field, getattr(e, field))
            r.lines.append(ln)
            if ln.problem:
                r.bad_lines.append(ln)
        out.append(r)
    return out


def empty_analysis():
    return dict((k, []) for k in ("episodes", "bad_closes", "open", "boundaries", "beats",
                                  "snap_events", "runs", "hist"))


def empty_result():
    rows = [(f, "total", "unknown", "unknown", "terminal aggregate failure") for f in FIGURES]
    return dict(rows=rows, summary=rows, gaps=containment_gaps(), structural=containment_gaps(),
                counted=[], views={"run": {}, "class": {}, "helper": {}},
                view_gaps=lambda *a: 1, view_text=lambda *a: "unknown", s_h=1, n_unknown_h=0,
                groups={}, reviewing=[], bounds=[], beats=[], snapshots=[],
                spend={"total": Decimal(0), "sessions": 0, "detail": [], "unsure": True, "read": None})


def authority_notes():
    notes = []
    meanings = {"init": "initialisation continuity unknown",
                "report": "since-previous chronology unknown",
                "listed": "carried-key inventory incomplete; unobserved membership unknown",
                "disposition": "all relevant figure dispositions undetermined",
                "abandoned": "exclusion authority unknown; adjusted open counts unknown",
                "run-ended": "run-ending authority unknown; adjusted run coverage unknown"}
    for kind in STORE_KINDS:
        if authority(kind):
            notes.append(meanings[kind])
    if _ACTIVE.persistence:
        notes.append("persistence unavailable; no interval was recorded; nothing appended")
    return notes


def empty_history_text(ctx):
    """A prepared empty list is known empty only when its authorities are available."""
    if ctx["history_uncertain"]:
        return "- unknown: key history preparation unavailable"
    if authority("report") or authority("disposition"):
        return "- unknown: no complete since-previous disposition history"
    return "- none"


def observed_key_text(ctx):
    """Identity evidence is separate from prepared membership and disposition decisions."""
    text = "\n## Observed key identities\n\n"
    seen = set()
    for key in ctx.get("observed_keys", ()) + tuple(ctx.get("new_keys", ())):
        if key not in seen:
            seen.add(key)
            text += "- " + terminal_text(key) + ": observed identity; see dispositions for status\n"
    return text


def terminal_reports(recs, ctx, diagnostic=False):
    """Last-resort output uses only safe cached strings and fixed statuses."""
    title = ("diagnostic; start unresolved; end " + iso_exact(ctx["end"]) if diagnostic
             else "interval " + iso_exact(ctx["start"]) + " to " + iso_exact(ctx["end"]))
    text = "# Weekly waste report, records only: " + title + "\n\n" + PURPOSE + "\n\n"
    if diagnostic:
        text += "No interval was recorded; nothing appended. Every interval figure, membership, subtotal and determination is unknown/not evaluated.\n"
    else:
        text += "Every figure and event-derived coverage field is unknown (terminal output failure).\n"
    text += "Acquired candidate records: " + str(len(recs)) + "\n"
    for r in recs:
        text += "- " + terminal_text(r.name) + ": acquisition " + terminal_text(r.status) + "; event facts unknown\n"
    for note in authority_notes():
        text += "- " + note + "\n"
    text += "\n| Figure | Part | Value | Status | Coverage |\n|---|---|---|---|---|\n"
    for f in FIGURES:
        text += "| " + f + " | total | unknown | unknown | not evaluated |\n"
    if not diagnostic:
        if "keys" in ctx:
            text += "\n## Dispositions\n\n"
            for key, status in ctx["keys"]:
                text += "- " + terminal_text(key) + ": " + terminal_text(status) + "\n"
            text += "\nRecorded dispositions (since-previous chronology unknown):\n\n" if authority("report") else "\nRecorded since the previous report:\n\n"
            for rec in ctx["since_prev"]:
                text += "- " + terminal_text(rec["key"]) + ": " + terminal_text(rec["disposition"]) + " (" + terminal_text(rec["note"]) + ")\n"
            if not ctx["since_prev"]:
                text += empty_history_text(ctx) + "\n"
        text += observed_key_text(ctx)
    return text, text


def recovery_overlay(main, detail, recs, res, ctx):
    """Coverage is recomputed with the same monotone flags as the numbers, before publication."""
    damaged = bool(_ACTIVE.eligibility)
    if damaged:
        prefixes = ("- Records read:", "- Records holding invalid", "- Episodes open or unresolved",
                    "- Runs open at acquisition:", "- Lines under a historical")
        main = "\n".join((line.split(":", 1)[0] + ": unknown; affected record eligibility and event coverage unavailable.")
                         if line.startswith(prefixes) else line for line in main.split("\n"))
        main += "\nHelper-view membership/ranking unknown wherever a contained failure reaches helper time.\n"
        for r in recs:
            if not uncertain_record(r):
                continue
            label = terminal_text(r.name)
            note = "- " + label + ": determination eligibility unknown; affected domains " + "; ".join(
                p for p in ALL_PARTS if p in _ACTIVE.domains.get(r.name, ())) + "\n"
            main += note
            detail += note
        # Inventory event facts must not remain falsely definite beside an uncertainty overlay.
        inv = False
        rows = []
        names = {cell(r.name) for r in recs if uncertain_record(r)}
        for line in detail.split("\n"):
            if line.startswith("## Inventory:"):
                inv = True
            elif inv and line.startswith("## "):
                inv = False
            if inv and line.startswith("| "):
                cols = line.split(" | ")
                if cols[0][2:] in names:
                    cols[3:] = ["unknown"] * 5 + ["unknown |"]
                    line = " | ".join(cols)
            rows.append(line)
        detail = "\n".join(rows)
    if authority("abandoned"):
        main = "\n".join("- Episodes open or unresolved at acquisition: unknown; candidate exclusions undecided."
                         if l.startswith("- Episodes open or unresolved") else l for l in main.split("\n"))
    if authority("run-ended"):
        main = "\n".join("- Runs open at acquisition: unknown; candidate endings undecided."
                         if l.startswith("- Runs open at acquisition:") else l for l in main.split("\n"))
    if authority("report"):
        main = main.replace("Recorded since the previous report:", "Recorded dispositions (since-previous chronology unknown):")
    if ctx["store_problems"]:
        detail += "\nStore continuity failure: " + "; ".join(ctx["store_problems"]) + ". " + ctx["store_effect"] + "\n"
    notes = authority_notes()
    if notes:
        text = "\nStore authority uncertainty:\n" + "".join("- " + n + "\n" for n in notes)
        main += text
        detail += text
    # Candidate identities survive uncertain store authority; they are not definite open/ended claims.
    if authority("abandoned") or authority("run-ended"):
        text = "\nRecord-established determination candidates (status unknown):\n"
        for r in recs:
            for ln in r.lines:
                if ln.kind in ALL_OPENINGS and ln.lane is not None:
                    text += "- " + identity_text(r.name, ln.lane, ln.n) + ": exclusion unknown\n"
                elif ln.kind in ("run-open", "run-resume"):
                    text += "- " + terminal_text(r.name) + ": ending unknown\n"
        main += text
        detail += text
    return main, detail


def select_start(args, store, end):
    if args.since:
        return parse_day(args.since, "--since")
    if authority("report"):
        return None
    prev = None
    for n, rec in store.lines:
        with boundary("store-select", source_of_store(rec), (source_of_store(rec),), ()) as live:
            if not live:
                continue
            if rec.get("kind") == "report":
                e = parse_ts(rec["interval"][1])
                if e < end and (prev is None or e > prev):
                    prev = e
    if prev is not None:
        return prev
    # Seven civil dates: the noon offset avoids selecting the wrong local date at a DST change.
    lt = time.localtime(end - 7 * 86400 + 43200)
    return local_epoch(lt.tm_year, lt.tm_mon, lt.tm_mday)


def prepare_history(store, start, new_keys):
    listed, disposed = {}, {}
    prev_report = None
    for n, rec in store.lines:
        with boundary("store-history", source_of_store(rec), (source_of_store(rec),), ()) as live:
            if not live:
                # Safely committed keys remain observations even if membership could not be decided.
                if rec.get("kind") == "listed":
                    listed.setdefault(rec["key"], rec)
                continue
            if rec.get("kind") == "listed" and (authority("listed") or parse_ts(rec["interval"][1]) <= start):
                listed.setdefault(rec["key"], rec)
            elif rec.get("kind") == "disposition":
                disposed[rec["key"]] = rec
            elif rec.get("kind") == "report" and parse_ts(rec["interval"][1]) <= start:
                prev_report = n
    since_prev = [rec for n, rec in store.lines if rec.get("kind") == "disposition"
                  and (authority("report") or prev_report is None or n > prev_report)]
    keys = []
    for key in sorted(listed):
        if authority("disposition"):
            keys.append((key, "undetermined; observed carried key"))
        elif key not in disposed:
            keys.append((key, "membership unknown; observed key" if authority("listed")
                         else "open, carried from an earlier report"))
    for key in new_keys:
        if authority("disposition"):
            keys.append((key, "listed by this report; undetermined"))
        elif key in disposed:
            keys.append((key, "listed by this report; disposed: %s (%s)"
                         % (disposed[key]["disposition"], disposed[key]["note"])))
        else:
            keys.append((key, "listed by this report; open"))
    return keys, since_prev


def terminal_history(store, new_keys):
    """Retain committed primitive identities without repeating the failed history operation."""
    keys, seen = [], set()
    current = set(new_keys)
    for key in store.observed_keys + tuple(new_keys):
        if key not in seen:
            seen.add(key)
            prefix = "listed by this report; " if key in current else ""
            keys.append((key, prefix + "undetermined; membership unknown (observed key)"))
    return keys, []


def prepare_generation(args, snapshot, store, base_ctx):
    recs = fresh_records(snapshot)
    _ACTIVE.current_recs = recs
    sources = all_sources(recs)
    ctx = dict(base_ctx)
    start, end = select_start(args, store, ctx["end"]), ctx["end"]
    ctx["start"] = start
    state = "malformed" if _ACTIVE.authorities or _ACTIVE.persistence else store.state
    ctx["store_problems"] = list(store.problems)
    if _ACTIVE.authorities:
        ctx["store_problems"].append("contained store-line failure (physical locations below)")
    if _ACTIVE.persistence:
        ctx["store_problems"].append("outgoing store preparation failed")
    if start is None:
        main, detail = guarded("diagnostic", GLOBAL_OWNER, store_sources(store), (),
                               lambda: terminal_reports(recs, ctx, True),
                               lambda: terminal_reports(recs, ctx, True))
        output = "weekly-waste: diagnostic; start unresolved; end " + iso_exact(end) + " · no interval was recorded; nothing appended\n"
        append = None
        code = 1
    else:
        if start >= end:
            raise Probe("an empty interval: --since %s is not before --until %s"
                        % (fmt_local(start), fmt_local(end)))
        an = guarded("analysis", GLOBAL_OWNER, sources, ALL_PARTS, lambda: analyse(recs), empty_analysis)
        res = guarded("compute", GLOBAL_OWNER, sources, ALL_PARTS,
                      lambda: compute(recs, an, Fraction(start), Fraction(end)), empty_result)
        applied, left_out, ended_runs = guarded("determinations", GLOBAL_OWNER, store_sources(store), (),
            lambda: determinations(store if store.state in ("ok", "malformed") else None, recs, an, start),
            lambda: ([], set(), {}))
        label = interval_label(start, end)
        new_keys = [FIGURE_KEYS[f] + "@" + label for f in FIGURES]
        if res["gaps"] or _ACTIVE.eligibility:
            new_keys.append("coverage@" + label)
        if state == "malformed":
            new_keys.append("store-continuity@" + label)
        ctx["new_keys"] = tuple(new_keys)
        keys, since_prev = guarded("keys", GLOBAL_OWNER, store_sources(store), (),
                                  lambda: prepare_history(store, start, new_keys),
                                  lambda: terminal_history(store, new_keys))
        # Only a failed combined preparation loses this result. Individual store authorities
        # are already applied by prepare_history; unrelated failures cannot erase its decisions.
        history_uncertain = ("keys", GLOBAL_OWNER) in _ACTIVE.failed
        tables = []
        with boundary("tables", GLOBAL_OWNER, sources, ALL_PARTS) as live:
            if live:
                stems = sorted(set(r.stem for r in recs if r.status == "read" and any(
                    ln.ts is not None and start <= ln.ts < end for ln in r.lines)))
                for stem in stems:
                    path = os.path.join(ctx["tables_dir"], "%s-waste-table.md" % stem)
                    if os.path.isfile(path):
                        tables.append((stem, path))
        effect = ""
        if _ACTIVE.persistence:
            effect = "No interval was recorded; nothing appended (exit 1)."
        elif state in ("missing", "unreadable"):
            effect = "This report's lines were not recorded and the store was not recreated: restore it from a copy (exit 1)."
        elif state == "malformed":
            effect = "This report's lines were appended; the key store-continuity@%s stays open until disposed (exit 1)." % label
        ctx.update(keys=keys, since_prev=since_prev, tables=tables, determinations=applied,
                   history_uncertain=history_uncertain,
                   tables_available=("tables", GLOBAL_OWNER) not in _ACTIVE.failed,
                   store_sources=store_sources(store),
                   left_out=left_out, ended_runs=ended_runs, store_effect=effect)
        ctx["runtime"] = time.time() - ctx["started"]
        def render_candidate():
            main, detail = render(recs, an, res, ctx)
            return recovery_overlay(main, detail, recs, res, ctx)
        main, detail = guarded("render", GLOBAL_OWNER, sources + store_sources(store), ALL_PARTS,
                               render_candidate, lambda: terminal_reports(recs, ctx))
        # These routes are fixed slots even when containment first creates the branch.
        if _ACTIVE.ledger:
            with boundary("gap-presentation", GLOBAL_OWNER, sources, ALL_PARTS):
                pass
            with boundary("unknown-presentation", GLOBAL_OWNER, sources, ALL_PARTS):
                pass
        output = ""
        with boundary("stdout", GLOBAL_OWNER, sources, ALL_PARTS) as live:
            if live:
                output = ("weekly-waste: %s · %d candidates (%d read, %d not admitted) · %s episodes closing · %d named gaps · store %s\n"
                          % (label, len(recs), sum(1 for r in recs if r.status == "read"),
                             sum(1 for r in recs if not r.admitted),
                             "unknown" if _ACTIVE.eligibility else str(len(res["counted"])), len(res["gaps"]), state))
                output += "".join("  %s · %s: %s [%s]\n" % row[:4] for row in res["summary"])
            else:
                output = "weekly-waste: figures and coverage unknown (terminal summary failure)\n"
        append = None
        if not _ACTIVE.persistence and state in ("ok", "malformed"):
            with boundary("outgoing", GLOBAL_OWNER, sources + store_sources(store), ()) as live:
                if live:
                    at = now_iso()
                    pair = [iso_exact(start), iso_exact(end)]
                    lines = [{"kind": "report", "interval": pair, "report": ctx["report_path"], "detail": ctx["detail_path"],
                              "at": at, "listed": len(new_keys), "not_seen": len(res["gaps"])}]
                    for key in new_keys:
                        lines.append({"kind": "listed", "key": key, "class": key.split("@")[0],
                                      "name": key.split("@")[0], "interval": pair, "at": at})
                    append = serialise_store(lines)
        code = 0 if state == "ok" else 1
    # The ledger is the small terminal emitter, outside ordinary formatting and sorting.
    if _ACTIVE.ledger:
        ledger = _ACTIVE.ledger_text()
        main += ledger
        detail += ledger
    output += "report: " + terminal_text(ctx["report_path"]) + "\ndetail: " + terminal_text(ctx["detail_path"]) + "\n"
    if _ACTIVE.persistence:
        output += "persistence unavailable; no interval was recorded; nothing appended\n"
    def encoded(text, route, encoding, fallback):
        def terminal_bytes():
            if route in ("encode-main", "encode-detail"):
                terminal = terminal_reports(recs, ctx, start is None)[0] + _ACTIVE.ledger_text()
                return terminal.encode("utf-8")
            return "\n".join(terminal_text(line) for line in text.split("\n")).encode(encoding)
        return guarded(route, GLOBAL_OWNER, sources + store_sources(store), ALL_PARTS,
                       lambda: text.encode(encoding), terminal_bytes)
    main_bytes = encoded(main, "encode-main", "utf-8", terminal_text(main))
    detail_bytes = encoded(detail, "encode-detail", "utf-8", terminal_text(detail))
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    output_bytes = encoded(output, "encode-stdout", encoding, terminal_text(output))
    return ctx, main_bytes, detail_bytes, append, output, output_bytes, code


def terminal_generation(args, snapshot, ctx):
    """Terminal preparation slot: no ordinary model, sort, formatter or store append."""
    ctx = dict(ctx)
    ctx["start"] = parse_day(args.since, "--since") if args.since else None
    main, detail = terminal_reports(fresh_records(snapshot), ctx, ctx["start"] is None)
    ledger = _ACTIVE.ledger_text()
    output = ("weekly-waste: terminal preparation unavailable; all figures unknown; "
              "no interval was recorded; nothing appended\n")
    output += "report: " + terminal_text(ctx["report_path"]) + "\ndetail: " + terminal_text(ctx["detail_path"]) + "\n"
    return ctx, (main + ledger).encode("utf-8"), (detail + ledger).encode("utf-8"), None, output, output.encode("ascii"), 1


def cmd_report(args):
    global _ACTIVE
    previous = _ACTIVE
    recovery = Recovery()
    _ACTIVE = recovery
    try:
        t0 = time.time()
        tools = tools_dir_of(args)
        reports = reports_dir_of(args)
        if not os.path.isdir(reports):
            raise Probe("no reports folder at %s (created at install by `init`)" % reports)
        end = parse_day(args.until, "--until") if args.until else local_epoch(*time.localtime()[:3])
        store_path = os.path.join(tools, "dispositions.jsonl")
        store = read_store(store_path)
        records_dir = records_dir_of(args)
        acq_start = time.time()
        recs, others, volume = acquire(records_dir)
        acq_end = time.time()
        snapshot = snapshot_records(recs)
        until_name = time.strftime("%Y-%m-%d", time.localtime(int(end // 1)))
        ctx = dict(end=end, started=t0, acq_start=Fraction(int(acq_start)), acq_end=Fraction(int(acq_end)+(acq_end > int(acq_end))),
                   volume=volume, others=others, records_dir=records_dir, store_path=store_path,
                   observed_keys=store.observed_keys,
                   report_path=os.path.join(reports, "waste-report-%s.md" % until_name),
                   detail_path=os.path.join(reports, "waste-detail-%s.md" % until_name),
                   tables_dir=os.path.realpath(args.tables_dir) if args.tables_dir else records_dir,
                   runtime=time.time()-t0)
        recovery.replaying = True
        while True:
            recovery.generations += 1
            try:
                prepared = guarded("prepare", GLOBAL_OWNER, all_sources(recs) + store_sources(store),
                                   ALL_PARTS, lambda: prepare_generation(args, snapshot, store, ctx),
                                   lambda: terminal_generation(args, snapshot, ctx))
                break
            except Replay:
                # K times enumerated owners is a derived finite bound, not a retry limit.
                if len(recovery.failed) > len(ROUTES) * len(recovery.owners):
                    raise Probe("containment exceeded its registered finite slots")
        ctx, main_bytes, detail_bytes, append, output, output_bytes, code = prepared
        # Frozen commit: only I/O remains, in the established detail / append / main order.
        write_atomic(ctx["detail_path"], detail_bytes)
        if append is not None:
            append_store(store_path, append)
        write_atomic(ctx["report_path"], main_bytes)
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(output_bytes)
        else:
            sys.stdout.write(output)
        return code
    finally:
        _ACTIVE = previous


def require_store(tools):
    path = os.path.join(tools, "dispositions.jsonl")
    st = read_store(path)
    if st.state in ("missing", "unreadable"):
        raise Probe("; ".join(st.problems) + "; nothing written")
    return path, st


def cmd_init(args):
    tools = tools_dir_of(args)
    if not os.path.isdir(tools):
        raise Probe("no tools folder at %s (setup.sh makes it, or make it first); nothing written" % tools)
    path = os.path.join(tools, "dispositions.jsonl")
    if os.path.lexists(path):
        raise Probe("a store already exists at %s; init never overwrites it" % path)
    reports = reports_dir_of(args)
    if not os.path.isdir(reports):
        os.mkdir(reports)
    data = (json.dumps({"kind": "init", "at": now_iso(), "version": VERSION}, sort_keys=True)
            + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    print("init: created %s and %s" % (path, reports))
    return 0


def cmd_dispose(args):
    if not (args.note or "").strip():
        raise Probe("--note is empty: give the reason or the blocker; nothing written")
    path, st = require_store(tools_dir_of(args))
    listed = sorted(set(rec["key"] for n, rec in st.lines if rec.get("kind") == "listed"))
    if args.key not in listed:
        near = difflib.get_close_matches(args.key, listed, n=1)
        raise Probe("the store lists no key %r%s; nothing written"
                    % (args.key, " (nearest: %s)" % near[0] if near else ""))
    append_store(path, [{"kind": "disposition", "key": args.key, "disposition": args.disposition,
                         "note": args.note.strip(), "at": now_iso()}])
    print("dispose: %s %s" % (args.key, args.disposition))
    return 0


def listed_names(records_dir):
    """The names in the records folder exactly as its listing gives them. A record a subcommand names must
    be one of them: the file system may open a name given in another case or form (this one matches
    either), and a determination would then name a record no report finds."""
    try:
        return set(os.listdir(records_dir))
    except OSError as exc:
        raise Probe("the records folder %s cannot be listed (%s); nothing written"
                    % (records_dir, exc.strerror))


def load_one(args, stem, names=None):
    records_dir = records_dir_of(args)
    path = os.path.join(records_dir, stem + ".jsonl")
    refused = ("%s is not admitted as a run record by its name (FIELDS.md, \"Admission\"), so it is never "
               "opened; nothing written" % path)
    if "/" in stem:
        raise Probe(refused)
    # Admission is decided from the folder's listing (a read log only beside its run's record).
    names = listed_names(records_dir) if names is None else names
    if not admitted(stem + ".jsonl", names):
        raise Probe(refused)
    if stem + ".jsonl" not in names:
        raise Probe("there is no record named %r in %s (a name is compared exactly, case and form "
                    "included); nothing written" % (stem + ".jsonl", records_dir))
    rec = Rec(stem + ".jsonl", path, True)
    try:
        data = read_candidate(path)
    except NotOpened as exc:
        raise Probe("the record %s is %s, so it is never opened; nothing written" % (path, exc))
    except OSError as exc:
        raise Probe("the record %s cannot be read (%s); nothing written" % (path, exc.strerror))
    read_record(rec, data)
    rec.status = "read"
    if rec.bad_lines:
        raise Probe("the record %s holds %d invalid or undated lines (first: line %d, %s); a "
                    "record that is not valid has no such exit until it is mended; nothing written"
                    % (path, len(rec.bad_lines), rec.bad_lines[0].n, rec.bad_lines[0].problem))
    return rec


def cmd_abandon(args):
    """Record an abandoned determination for one open opening, named by the held format's episode string
    and written with its structured identity beside it (CR-WASTE6 finding 1). The string is read every way
    it can be (a record or a helper may hold ":"); it names the opening only when one reading alone could be
    an opening there, else --record, --helper and --line (which must spell the same string) name it."""
    if not (args.evidence or "").strip():
        raise Probe("--evidence is empty; nothing written")
    key = args.episode or ""
    m = re.fullmatch(r"(.*):([1-9][0-9]*)", key, re.S)
    if not m or ":" not in m.group(1):
        raise Probe("episode %r is not <record>:<helper>:<line>; nothing written" % key)
    n = positive_line_number(m.group(2))
    if n is None:
        raise Probe("invalid opening-line suffix; nothing written")
    given = (args.record, args.helper, args.line)
    if None in given and any(v is not None for v in given):
        raise Probe("--record, --helper and --line name an opening together; nothing written")
    if args.record is not None:
        if not (args.record.endswith(".jsonl") and args.line == n
                and episode_key(args.record[:-len(".jsonl")], args.helper, args.line) == key):
            raise Probe("episode %r is not %s written as <record>:<helper>:<line>; nothing written"
                        % (key, identity_text(args.record, args.helper, args.line)))
        readings = [(args.record[:-len(".jsonl")], args.helper)]
    else:
        head = m.group(1)
        readings = [(head[:i], head[i + 1:]) for i, ch in enumerate(head) if ch == ":"]
    path, st = require_store(tools_dir_of(args))
    records_dir = records_dir_of(args)
    names = listed_names(records_dir)
    # Each reading whose record is an admitted name in the folder and whose line there could open that
    # helper (could_open; a record that cannot be read could hold anything).
    possible = []
    for stem, lane in readings:
        name = stem + ".jsonl"
        if not lane.strip() or name not in names or not admitted(name, names):
            continue
        rec = Rec(name, os.path.join(records_dir, name), True)
        try:
            read_record(rec, read_candidate(rec.path))
        except OSError:
            rec.status = "unreadable"
        if could_open(rec, lane, n):
            possible.append((stem, lane))
    if len(possible) > 1:
        raise Probe("episode %r could name %d openings (%s): give the one meant with --record, --helper "
                    "and --line, as the report's detail shows them; nothing written"
                    % (key, len(possible), "; ".join(identity_text(s + ".jsonl", l, n) for s, l in possible)))
    # With no reading left, the held pattern's own reading (a helper without ":"), so the refusal says why.
    stem, lane = possible[0] if possible else readings[-1]
    rec = load_one(args, stem, names)
    an = analyse([rec])
    for r, l, op, why, kind in an["open"]:
        if l == lane and op.n == n and kind == "open":
            append_store(path, [{"kind": "abandoned", "episode": key, "record": rec.name, "helper": lane,
                                 "line": n, "evidence": args.evidence.strip(), "at": now_iso(),
                                 "last_event": iso_exact(episode_last_event(rec, lane, op)),
                                 "record_last_event": iso_exact(rec.last_ts),
                                 "record_lines": len(rec.lines)}])
            print("abandon: %s recorded (%s)" % (key, identity_text(rec.name, lane, n)))
            return 0
    for ep in an["episodes"]:
        if ep.lane == lane and ep.opening.n == n:
            raise Probe("episode %s is closed (line %d); nothing written" % (key, ep.close.n))
    raise Probe("no open opening of %s at line %d in %s; nothing written" % (lane, n, rec.path))


def cmd_end_run(args):
    if not (args.evidence or "").strip():
        raise Probe("--evidence is empty; nothing written")
    path, st = require_store(tools_dir_of(args))
    rec = load_one(args, args.run)
    an = analyse([rec])
    if not rec.has_run_open:
        raise Probe("the record %s has no run-open, so no head to end; nothing written" % rec.path)
    if not an["runs"]:
        raise Probe("the run %s is closed on its record; nothing written" % args.run)
    append_store(path, [{"kind": "run-ended", "run": args.run, "record": rec.name,
                         "evidence": args.evidence.strip(), "at": now_iso(),
                         "record_last_event": iso_exact(rec.last_ts), "record_lines": len(rec.lines)}])
    print("end-run: %s recorded" % args.run)
    return 0


def build_parser(sub):
    p = argparse.ArgumentParser(prog="weekly-waste.py" + (" " + sub if sub else ""))
    p.add_argument("--tools-dir", help="the folder holding dispositions.jsonl and reports/ "
                                       "(default: the store in <store>/tools/weekly-waste, the "
                                       "reports in the vault's output/reports)")
    if sub in (None, "abandon", "end-run"):
        p.add_argument("--records", help="the run records (default: <store>/spawn-records, the "
                                         "store being LLM_WIKI_STORE or ~/.llm-wiki)")
    if sub is None:
        p.add_argument("--until", help="the interval ends at 00:00 local time on this day (default: today)")
        p.add_argument("--since", help="the interval's start (default: the end of the previous "
                                       "report in the store, else seven days before --until)")
        p.add_argument("--tables-dir", help="where the per-run waste tables are looked for "
                                            "(default: the records folder)")
    elif sub == "dispose":
        p.add_argument("key")
        p.add_argument("disposition", choices=DISPOSITIONS)
        p.add_argument("--note", required=True)
    elif sub == "abandon":
        p.add_argument("episode")
        p.add_argument("--evidence", required=True)
        p.add_argument("--record", help="with --helper and --line: the opening's record, by its file name, "
                                        "where the episode string could name several openings")
        p.add_argument("--helper", help="the opening's helper (its lane), as the detail shows it")
        p.add_argument("--line", type=cli_line_number, help="the opening's line")
    elif sub == "end-run":
        p.add_argument("run")
        p.add_argument("--evidence", required=True)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sub = argv[0] if argv and argv[0] in ("init", "dispose", "abandon", "end-run") else None
    parser = build_parser(sub)
    try:
        args = parser.parse_args(argv[1:] if sub else argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if sub is None:
            return cmd_report(args)
        return {"init": cmd_init, "dispose": cmd_dispose, "abandon": cmd_abandon,
                "end-run": cmd_end_run}[sub](args)
    except Probe as exc:
        sys.stderr.write("PROBE FAILED: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
