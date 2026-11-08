#!/usr/bin/env python3
"""pass_order.py: list every command the weekly audit's reviewer ran before its first-pass message,
read from the reviewer's own run record (its Codex event log), for the head to judge.

Design: section 2 of the waste-reduction and retirement design page in `wiki/developments/`, as
simplified by option S (the owner's choice of 12 October 2026): the tool lists, the head judges.
Python 3 standard library only. It never runs, expands or interprets a command, and it writes
nothing.

    pass_order.py --events LOG [--whole-run]

WHAT IT PRINTS
1. The list: every command the record shows the reviewer starting before its first-pass message,
   in the order the commands started, one entry per execution (one command item of the record),
   each verbatim, with the count and the record's path. A command started before the message and
   finished after it is listed. Each entry prints its text whole, line for line, every line
   indented by four spaces. Verbatim means lossless, in one of two forms, and the entry's header
   says which:
   - an entry holding no character a terminal could hide or redraw (a control, format, private
     use, surrogate, unassigned or separator character other than a newline or a tab) prints
     byte for byte, and its header names no encoding;
   - an entry holding one or more such characters prints in this reversible encoding, which its
     header declares (`ESCAPED: <n> character(s) a terminal could hide written \\xHH, \\uHHHH or
     \\UHHHHHHHH, and every backslash doubled`): each such character is written `\\x` and two
     lower-case hex digits below U+0100, `\\u` and four below U+10000, else `\\U` and eight;
     every backslash of the text is written as two; every other character, newlines and tabs
     included, is itself.
     To recover the command, read the escapes left to right: `\\\\` is one backslash, and
     `\\x`, `\\u` and `\\U` give the character of their hex digits.
   So two different commands never print alike, and each print recovers its command. An item's
   id and a field name taken from the record print as they are when they hold no such character
   and no backslash, and otherwise as Python's quoted repr, which escapes them.
2. The file changes started before the message, which a read-only reviewer should not make, in a
   list of their own with their own count.
3. With --whole-run, every command started after the message as well, in a list of its own: for
   the smoke test on frozen copies, where the head asks of each later command whether it could
   have read a live file that a frozen copy stands in for (AUDIT.md, step 6).
4. The boundary, any message passed over as a boundary, the record's counts and the controls.
It judges nothing. No line, exit code or file of it says what the first pass read or saw: the head
reads the list and writes the week's outcome (AUDIT.md, step 6).

THE BOUNDARY
The first-pass message is the reviewer's first complete findings message under the brief's
heading: the first completed agent message whose first line is exactly `PASS 1 FINDINGS` and
whose last line is `END PASS 1: <n> findings` (`finding` for one), n being its count of distinct
P1- ids, zero allowed. A message with the heading that is cut off before that end line, or whose
end line miscounts its ids, is not a boundary: it is named on a `not a boundary:` line, and the
next complete one is the boundary. A message before the boundary (any message, when there is none)
whose first line only resembles the heading, or that holds the heading on a later line, is named
on a `near miss:` line; one after the boundary is not, since the final report repeats the
first-pass list. A command or file change is before the message when its first event comes before
the message's log line.

EVIDENCE INTEGRITY
Each line of the record holds one event, so an event's position is its log line. The record is
read under a bounded event grammar, enumerated from six real event logs of 11 and 12 October 2026
(595 lines: thread.started 6, turn.started 6, item.started 267, item.completed 310,
turn.completed 6; items: agent messages 43, command executions 263, file changes 4):
- Every line is one JSON object, decoded as strict UTF-8, with no key given twice and no NaN or
  Infinity, which JSON does not have (a final newline is allowed; a blank line is not an event).
- Events and their fields, exactly: `thread.started` (type, thread_id: a string), first in the
  record and once; `turn.started` (type); `item.started` and `item.completed` (type, item: an
  object); `turn.completed` (type, usage: an object). Item events come only inside the turn; the
  record holds one turn, as each of the six records did (one reviewer run, one turn), and ends
  with its turn.completed: a second turn is outside the grammar, so that no record cut short can
  read as a whole shorter one (revision 7: an event log is a framed input).
- Items and their fields, exactly. `agent_message` (id, type, text: a string) arrives once, as
  item.completed only. `command_execution` (id, type, command: a non-empty string,
  aggregated_output: a string, exit_code, status) arrives as item.started (status `in_progress`,
  exit_code null), then item.completed (status `completed` or `failed`, exit_code an integer).
  `file_change` (id, type, changes, status) arrives as item.started (status `in_progress`), then
  item.completed (status `completed`); its changes are a non-empty list of objects holding exactly
  a path (absolute) and a kind (`add` or `update`).
- An item's id names one execution for the whole record: started at most once, completed exactly
  once, both in the same turn, with no event after its completion; its type, and its command or
  its changes, never change across its events (its status, output and exit code may).
A record that is missing, cannot be looked at or opened, or is empty, that is truncated (cut
before its final turn completes, or ending on a torn line), or that holds anything outside the
grammar (a line that does not parse, an event or item of a missing or unknown type, a command
event without its command text, a missing or extra field, a command that changes across its
events) gives a `could not read:` line for each problem, naming the record and the event's log
line, and no list: such evidence is never dropped silently and never yields an empty list. The
grammar is what proves the record whole: its one turn completes on its last line, so a record cut
after any whole line short of that is truncated, and a record that goes on past its turn (a second
turn, which a cut between turns would otherwise drop unseen) is outside the grammar.

EXIT CODES
- 0: the list printed: the record read whole and its first-pass message found. The list can be
  empty; the controls line shows the reader listing planted commands on the same run.
- 1: could not read: the record cannot be read whole (above); no list.
- 2: PROBE FAILED: a bad argument, or an in-run control misread a plant; no list.
- 3: no first-pass message: the record reads whole but holds no complete first-pass message; no
  list.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

HEADER = "PASS 1 FINDINGS"
END_RE = re.compile(r"^END PASS 1: (\d+) findings?$")
FINDING_RE = re.compile(r"\bP1-(\d+)\b")
NEAR_RE = re.compile(r"pass\s*1\s*findings", re.I)
INDENT = "    "
SHOWN_PROBLEMS = 20   # problems printed before the rest are counted: set by judgement, unmeasured
HIDING = ("Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp")   # categories escaped (a newline and a tab aside)

EXIT_LISTED, EXIT_UNREAD, EXIT_PROBE, EXIT_NO_MESSAGE = 0, 1, 2, 3

# ------------------------------------------------------------------ the event grammar --------

EVENT_FIELDS = {
    "thread.started": ("type", "thread_id"),
    "turn.started": ("type",),
    "item.started": ("type", "item"),
    "item.completed": ("type", "item"),
    "turn.completed": ("type", "usage"),
}
ITEM_FIELDS = {
    "agent_message": ("id", "type", "text"),
    "command_execution": ("id", "type", "command", "aggregated_output", "exit_code", "status"),
    "file_change": ("id", "type", "changes", "status"),
}
EVIDENCE_FIELD = {"agent_message": "text", "command_execution": "command", "file_change": "changes"}
ITEM_EVENTS = {
    "agent_message": ("item.completed",),
    "command_execution": ("item.started", "item.completed"),
    "file_change": ("item.started", "item.completed"),
}
STATUSES = {
    ("command_execution", "item.started"): ("in_progress",),
    ("command_execution", "item.completed"): ("completed", "failed"),
    ("file_change", "item.started"): ("in_progress",),
    ("file_change", "item.completed"): ("completed",),
}
CHANGE_FIELDS = ("kind", "path")
CHANGE_KINDS = ("add", "update")


class ProbeFailed(Exception):
    pass


def probe(what):
    raise ProbeFailed("PROBE FAILED: %s" % what)


class CouldNotRead(Exception):
    """The record as a whole cannot be read; its message says why."""


def hides(char):
    """Whether a terminal could hide or redraw the character: a newline and a tab aside, every
    control, format, private-use, surrogate, unassigned and line or paragraph separator."""
    return char not in "\n\t" and unicodedata.category(char) in HIDING


def label(text):
    """An item id or a field name taken from the record, as printed: itself when it holds no
    character a terminal could hide and no backslash; otherwise its Python repr, which escapes
    such characters and holds a backslash, so the two forms never meet."""
    text = str(text)
    if any(hides(char) or char == "\\" for char in text):
        return repr(text)
    return text


class Item(object):
    def __init__(self, ident, kind, first, turn):
        self.id, self.type, self.first, self.turn = ident, kind, first, turn
        self.events, self.completed = [], None


class Record(object):
    """A record read under the event grammar: its problems (log line, what), its items in the order
    they first appear, its boundary and the messages passed over as one."""

    def __init__(self, total):
        self.total, self.problems, self.items, self.order = total, [], {}, []
        self.parsed, self.turns, self.final = 0, 0, None
        self.boundary, self.passed_over, self.near, self.sent = None, [], [], []

    def problem(self, line, what):
        self.problems.append((line, what))


def fields_problem(obj, expected, evidence=None):
    """What a JSON object lacks or holds beyond its grammar (its evidence field aside, which
    value_problems names), or None."""
    missing = [k for k in expected if k not in obj and k != evidence]
    extra = sorted(k for k in obj if k not in expected)
    parts = []
    if missing:
        parts.append("lacks %s" % ", ".join(missing))
    if extra:
        parts.append("holds fields outside the grammar (%s)" % ", ".join(label(k) for k in extra))
    return " and ".join(parts) or None


def changes_problem(changes):
    if not isinstance(changes, list) or not changes:
        return "a file change without its changes"
    for change in changes:
        if not isinstance(change, dict) or set(change) != set(CHANGE_FIELDS):
            return "a file change whose change is not exactly {kind, path}"
        if not isinstance(change["path"], str) or not change["path"].startswith("/"):
            return "a file change whose path is not absolute"
        if change["kind"] not in CHANGE_KINDS:
            return "a file change of kind %r, outside %s" % (change["kind"],
                                                               ", ".join(CHANGE_KINDS))
    return None


def value_problems(kind, phase, item):
    problems = []
    if kind == "agent_message":
        if not isinstance(item.get("text"), str):
            problems.append("a sent agent message without its text")
        return problems
    if kind == "command_execution":
        command = item.get("command")
        if not isinstance(command, str) or not command.strip():
            problems.append("a command event without its command text")
        if "aggregated_output" in item and not isinstance(item["aggregated_output"], str):
            problems.append("its output is not a string")
        if "exit_code" in item:
            code = item["exit_code"]
            if phase == "item.started" and code is not None:
                problems.append("an exit code on item.started")
            if phase == "item.completed" and (isinstance(code, bool) or not isinstance(code, int)):
                problems.append("an exit code on item.completed that is not an integer")
    else:
        problem = changes_problem(item.get("changes"))
        if problem:
            problems.append(problem)
    if "status" in item and (kind, phase) in STATUSES \
            and item["status"] not in STATUSES[(kind, phase)]:
        problems.append("status %r on %s, %s expected" % (item["status"], phase, " or ".join(
            STATUSES[(kind, phase)])))
    return problems


def fixed(item):
    """What must not change across an item's events: its command, or its changes."""
    if item.get("type") == "file_change":
        return json.dumps(item.get("changes"), sort_keys=True)
    return item.get("command")


def item_event(record, number, phase, item, turn):
    kind = item.get("type")
    if not isinstance(kind, str) or not kind or kind not in ITEM_FIELDS:
        record.problem(number, "an item with no type" if not isinstance(kind, str) or not kind
                       else "an item of unknown type %r" % kind)
        return
    ident = item.get("id")
    if not isinstance(ident, str) or not ident:
        record.problem(number, "a %s item with no id" % kind)
        return
    shown = label(ident)
    problem = fields_problem(item, ITEM_FIELDS[kind], EVIDENCE_FIELD[kind])
    if problem:
        record.problem(number, "%s, a %s item, %s" % (shown, kind, problem))
    if phase not in ITEM_EVENTS[kind]:
        record.problem(number, "%s, a %s item, arrives as %s, never as %s"
                       % (shown, kind, " then ".join(ITEM_EVENTS[kind]), phase))
    for problem in value_problems(kind, phase, item):
        record.problem(number, "%s, %s" % (shown, problem))
    entry = record.items.get(ident)
    if entry is None:
        entry = Item(ident, kind, number, turn)
        record.items[ident] = entry
        record.order.append(ident)
        if phase == "item.completed" and "item.started" in ITEM_EVENTS[kind]:
            record.problem(number, "%s completes with no item.started before it" % shown)
    else:
        if entry.completed is not None:
            record.problem(number, "%s has an event after its completion at log line %d"
                           % (shown, entry.completed))
        elif phase == "item.started":
            record.problem(number, "%s starts again (first at log line %d)" % (shown, entry.first))
        if kind != entry.type:
            record.problem(number, "%s changes its type from %s (log line %d) to %s"
                           % (shown, entry.type, entry.first, kind))
        elif fixed(item) != fixed(entry.events[0][2]):
            record.problem(number, "%s changes its %s between log line %d and log line %d"
                           % (shown, "changes" if kind == "file_change" else "command",
                              entry.events[0][0], number))
        if turn != entry.turn:
            record.problem(number, "%s ends in another turn than it started in" % shown)
    entry.events.append((number, phase, item))
    if phase == "item.completed" and entry.completed is None:
        entry.completed = number


def unique_keys(pairs):
    """A JSON object's pairs as a dict, refusing a key given twice, which would hide its first value
    from any reader."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key %r" % key)
        obj[key] = value
    return obj


def no_constant(name):
    raise ValueError("%s is not JSON" % name)


def analyse(raw_lines):
    """A Record of the raw lines (bytes, without their newlines) under the event grammar."""
    record = Record(len(raw_lines))
    thread, turn_open, turn, last, first_turn = None, None, 0, None, None
    for number, raw in enumerate(raw_lines, 1):
        if not raw.strip():
            record.problem(number, "a blank line, not an event")
            continue
        try:
            event = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys,
                               parse_constant=no_constant)
        except (UnicodeDecodeError, ValueError) as err:
            record.problem(number, "an envelope that does not parse as a JSON event (%s): %r"
                           % (str(err).split(":")[0], raw[:80]))
            continue
        if not isinstance(event, dict):
            record.problem(number, "an envelope that is not a JSON object: %r" % raw[:80])
            continue
        record.parsed += 1
        kind = event.get("type")
        if not isinstance(kind, str) or not kind or kind not in EVENT_FIELDS:
            record.problem(number, "an event with no type" if not isinstance(kind, str) or not kind
                           else "an event of unknown type %r" % kind)
            continue
        last = (number, kind)
        problem = fields_problem(event, EVENT_FIELDS[kind])
        if problem:
            record.problem(number, "an event of type %s %s" % (kind, problem))
        if kind == "thread.started":
            if thread is not None:
                record.problem(number, "a second thread.started (the first at log line %d)"
                               % thread)
            elif number != 1:
                record.problem(number, "thread.started is not the record's first line")
            thread = thread or number
            if not isinstance(event.get("thread_id"), str) or not event.get("thread_id"):
                record.problem(number, "thread.started has no thread id")
        elif kind == "turn.started":
            if thread is None:
                record.problem(number, "a turn starts before thread.started")
            if turn_open is not None:
                record.problem(number, "a turn starts while the turn of log line %d is open"
                               % turn_open)
            elif first_turn is not None:
                record.problem(number, "a second turn (the first started at log line %d): a "
                               "reviewer's record holds one turn, so a record that goes on past "
                               "it is outside the grammar" % first_turn)
            first_turn = first_turn or number
            turn_open, turn = number, turn + 1
            record.turns += 1
        elif kind == "turn.completed":
            if turn_open is None:
                record.problem(number, "turn.completed with no turn open")
            if not isinstance(event.get("usage"), dict):
                record.problem(number, "turn.completed has no usage object")
            turn_open = None
        else:
            if turn_open is None:
                record.problem(number, "an item event outside a turn")
            item = event.get("item")
            if not isinstance(item, dict):
                record.problem(number, "an item event with no item")
                continue
            item_event(record, number, kind, item, turn)
    if thread is None:
        record.problem(1, "no thread.started event")
    if turn_open is not None:
        record.problem(record.total, "truncated: the turn started at log line %d never completes, "
                       "and the record stops at log line %d" % (turn_open, record.total))
    elif last is None or last[1] != "turn.completed":
        record.problem(record.total, "truncated: the record does not end with turn.completed")
    else:
        record.final = last[0]
    for ident in record.order:
        entry = record.items[ident]
        if entry.completed is None:
            record.problem(entry.first, "%s starts at log line %d and never completes"
                           % (label(ident), entry.first))
    find_boundary(record)
    return record


# ------------------------------------------------------------------ the boundary -------------

def is_header(text):
    return isinstance(text, str) and text.split("\n", 1)[0].rstrip("\r") == HEADER


def completeness(text):
    """(rows, ids, why): why is None for a complete first-pass message, else why it is not."""
    rows = [row.rstrip("\r") for row in text.rstrip().split("\n")]
    ids = sorted(set(int(n) for n in FINDING_RE.findall(text)))
    end = END_RE.match(rows[-1].strip()) if len(rows) > 1 else None
    if end is None:
        return rows, ids, ("its last line is not `END PASS 1: <n> findings` (%r): a message cut "
                           "off before its end" % rows[-1][:60])
    if int(end.group(1)) != len(ids):
        return rows, ids, ("its last line counts %s finding(s), but it holds %d distinct P1- id(s)"
                           % (end.group(1), len(ids)))
    return rows, ids, None


def near_miss(text):
    """Why a message that is not under the heading still looks like a first-pass message (its first
    line resembles the heading, or the heading stands on a later line), or None."""
    rows = text.split("\n")
    if NEAR_RE.sub("pass1findings", re.sub(r"[^a-z0-9 ]", "", rows[0].lower())).replace(
            " ", "").startswith("pass1findings"):
        return "its first line %r only resembles the heading" % rows[0][:60]
    for number, row in enumerate(rows[1:], 2):
        if row.rstrip("\r") == HEADER:
            return "the heading stands on its line %d, not its first" % number
    return None


def find_boundary(record):
    """The first complete first-pass message; the heading messages before it that are not
    complete, and the near misses, are kept to be named."""
    sent = []
    for ident in record.order:
        entry = record.items[ident]
        if entry.type == "agent_message" and entry.completed is not None:
            text = entry.events[-1][2].get("text")
            if isinstance(text, str):
                sent.append((entry.completed, entry, text))
    sent.sort(key=lambda s: s[0])
    record.sent = sent
    for line, entry, text in sent:
        if not is_header(text):
            why = near_miss(text)
            if why is not None:
                record.near.append((line, entry.id, why))
            continue
        rows, ids, why = completeness(text)
        if why is None and record.boundary is None:
            record.boundary = (line, entry, rows, ids)
        elif why is not None and record.boundary is None:
            record.passed_over.append((line, entry.id, why))


def actions(record, kind, before):
    """The items of a kind ("command_execution" or "file_change") whose first event lies before
    the boundary (or after it), in the order they started: (first line, item)."""
    mark = record.boundary[0]
    found = [(record.items[i].first, record.items[i]) for i in record.order
             if record.items[i].type == kind and (record.items[i].first < mark) == before]
    return sorted(found, key=lambda pair: pair[0])


# ------------------------------------------------------------------ printing -----------------

ESCAPED = ("ESCAPED: %d character(s) a terminal could hide written \\xHH, \\uHHHH or \\UHHHHHHHH, "
           "and every backslash doubled")
ESCAPE_RE = re.compile(r"\\(?:(\\)|x([0-9a-f]{2})|u([0-9a-f]{4})|U([0-9a-f]{8}))")


def escape(char):
    code = ord(char)
    return "\\x%02x" % code if code < 0x100 else "\\u%04x" % code if code < 0x10000 \
        else "\\U%08x" % code


def encode(text):
    """(the text in the declared reversible encoding, the count of characters escaped), or (the
    text itself, 0) when it holds no character a terminal could hide: such a text prints byte for
    byte, backslashes and all."""
    if not any(hides(char) for char in text):
        return text, 0
    shown, escaped = [], 0
    for char in text:
        if char == "\\":
            shown.append("\\\\")
        elif hides(char):
            shown.append(escape(char))
            escaped += 1
        else:
            shown.append(char)
    return "".join(shown), escaped


def decode(shown):
    """The text an encoded print stands for: its escapes read left to right (the in-run controls
    check that it inverts `encode`). A backslash that starts no escape is no print of `encode`:
    ValueError."""
    out, at = [], 0
    while at < len(shown):
        if shown[at] != "\\":
            out.append(shown[at])
            at += 1
            continue
        match = ESCAPE_RE.match(shown, at)
        if match is None:
            raise ValueError("a backslash at %d starts no escape" % at)
        out.append("\\" if match.group(1) else chr(int(next(g for g in match.groups()[1:] if g),
                                                       16)))
        at = match.end()
    return "".join(out)


def show_block(text):
    """(lines, escaped): the text, in the encoding its header declares when it holds a character a
    terminal could hide and byte for byte otherwise, split at its newlines, each line indented;
    escaped is the count of characters written as escapes (0: printed byte for byte)."""
    shown, escaped = encode(text)
    return [INDENT + row for row in shown.split("\n")], escaped


def entry_lines(index, total, noun, entry, text):
    lines, escaped = show_block(text)
    completed = entry.events[-1]
    final = completed[2]
    outcome = (" (%s, exit %s)" % (final.get("status"), final.get("exit_code"))
               if entry.type == "command_execution" else " (%s)" % final.get("status"))
    header = ("%s %d of %d: %s · started at log line %d · completed at log line %d%s · %d line(s), "
              "%d character(s)%s" % (noun, index, total, label(entry.id), entry.first,
                                     entry.completed, outcome, len(lines), len(text),
                                     " · " + ESCAPED % escaped if escaped else ""))
    return [header] + lines


def change_text(item):
    return json.dumps(item.get("changes"), ensure_ascii=False, sort_keys=True)


def listing(record, path, whole_run):
    out = []
    before = actions(record, "command_execution", True)
    out.append("COMMANDS BEFORE THE FIRST-PASS MESSAGE: %d · record %s" % (len(before), path))
    line, entry, rows, ids = record.boundary
    out.append("boundary: %s, the first complete first-pass message, completed at log line %d · "
               "its last line `%s` · %d distinct P1- id(s), matching its count"
               % (label(entry.id), line, rows[-1].strip(), len(ids)))
    out.extend(boundary_notes(record))
    for index, (_, item) in enumerate(before, 1):
        out.extend(entry_lines(index, len(before), "command", item, item.events[0][2]["command"]))
    out.append("count: %d command(s) started before the first-pass message, each listed once, in "
               "the order it started, from the record %s" % (len(before), path))
    changes = actions(record, "file_change", True)
    out.append("file changes before the first-pass message: %d" % len(changes))
    for index, (_, item) in enumerate(changes, 1):
        out.extend(entry_lines(index, len(changes), "file change", item,
                               change_text(item.events[0][2])))
    if whole_run:
        after = actions(record, "command_execution", False)
        out.append("COMMANDS AFTER THE FIRST-PASS MESSAGE (--whole-run): %d · record %s"
                   % (len(after), path))
        for index, (_, item) in enumerate(after, 1):
            out.extend(entry_lines(index, len(after), "later command", item,
                                   item.events[0][2]["command"]))
        out.append("count: %d command(s) started after the first-pass message" % len(after))
        later = actions(record, "file_change", False)
        out.append("file changes after the first-pass message: %d" % len(later))
        for index, (_, item) in enumerate(later, 1):
            out.extend(entry_lines(index, len(later), "later file change", item,
                                   change_text(item.events[0][2])))
    return out


def boundary_notes(record):
    """The `not a boundary:` and `near miss:` lines: the messages before the boundary (all of them
    when there is none) that a reader might take for the first-pass message, and why each is not.
    A near miss after the boundary is left out: the final report repeats the first-pass list."""
    mark = record.boundary[0] if record.boundary else None
    lines = ["not a boundary: %s (log line %d) begins with `%s`, but %s"
             % (label(ident), number, HEADER, why) for number, ident, why in record.passed_over]
    lines += ["near miss: %s (log line %d), %s" % (label(ident), number, why)
              for number, ident, why in record.near if mark is None or number < mark]
    return lines


def tally(record, path):
    counts = {}
    for ident in record.order:
        counts[record.items[ident].type] = counts.get(record.items[ident].type, 0) + 1
    return ("record: %s · %d line(s) · %d turn(s)%s · %d item(s): agent messages %d, commands %d, "
            "file changes %d" % (path, record.total, record.turns,
                                 ", the last completed at log line %d" % record.final
                                 if record.final else "", len(record.order),
                                 counts.get("agent_message", 0),
                                 counts.get("command_execution", 0), counts.get("file_change", 0)))


# ------------------------------------------------------------------ reading ------------------

def read_record(path):
    """The record's lines (bytes, without their newlines); CouldNotRead when it is missing, cannot
    be looked at, cannot be opened or is empty. Missing only when its own metadata says so: an
    error looking at it is said as that error, never as a record that does not exist. WHOLE: what
    proves the record whole is the event grammar (analyse): every line one strict JSON event, one
    turn, completed on the last line, with every item completed in it, so a record cut after any
    whole line short of its end is truncated; a second turn is outside the grammar, so no cut can
    leave a whole shorter record (an event log is a framed input: no limit applies to it)."""
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        raise CouldNotRead("the record does not exist")
    except OSError as err:
        raise CouldNotRead("the record could not be looked at (%s), so it is not called missing"
                           % (err.strerror or err))
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as err:
        raise CouldNotRead("the record cannot be opened (%s)" % (err.strerror or err))
    if not data.strip():
        raise CouldNotRead("the record is empty")
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines


def report(path, whole_run):
    controls = run_controls()
    try:
        record = analyse(read_record(path))
    except CouldNotRead as reason:
        print("COULD NOT READ: %s; no list" % path)
        print("could not read: %s: %s; no event was read" % (path, reason))
        print("controls: %s" % controls)
        return EXIT_UNREAD
    if record.problems:
        print("COULD NOT READ: %s (%d problem(s)); no list" % (path, len(record.problems)))
        for line, what in record.problems[:SHOWN_PROBLEMS]:
            print("could not read: %s, log line %d: %s" % (path, line, what))
        if len(record.problems) > SHOWN_PROBLEMS:
            print("could not read: %s: %d more problem(s) not shown"
                  % (path, len(record.problems) - SHOWN_PROBLEMS))
        print(tally(record, path))
        print("controls: %s" % controls)
        return EXIT_UNREAD
    if record.boundary is None:
        print("NO FIRST-PASS MESSAGE: %s holds no complete first-pass message among its %d sent "
              "agent message(s); no list" % (path, len(record.sent)))
        for line in boundary_notes(record):
            print(line)
        print(tally(record, path))
        print("controls: %s" % controls)
        return EXIT_NO_MESSAGE
    print("\n".join(listing(record, path, whole_run)))
    print(tally(record, path))
    print("controls: %s" % controls)
    return EXIT_LISTED


# ------------------------------------------------------------------ controls -----------------

def planted_record(steps):
    """A record in memory, around item events given as (phase, item) pairs."""
    events = [{"type": "thread.started", "thread_id": "t"}, {"type": "turn.started"}]
    events += [{"type": phase, "item": item} for phase, item in steps]
    events.append({"type": "turn.completed", "usage": {}})
    return [json.dumps(e).encode("utf-8") for e in events]


def planted_command(ident, text):
    started = {"id": ident, "type": "command_execution", "command": text,
               "aggregated_output": "", "exit_code": None, "status": "in_progress"}
    return started, dict(started, aggregated_output="x", exit_code=0, status="completed")


def run_controls():
    """Plants in memory, each read as expected or the probe has failed: a record whose earlier
    commands must be listed in start order (one begun before the message and finished after it,
    one text run twice, one of two lines) past a cut-off heading message, with a later command
    left out; damaged records that must each give problems; a record with no first-pass message;
    and the escape of characters a terminal could hide. Returns the controls line."""
    spans, spans_done = planted_command("c1", "/bin/cat /x/a.md")
    twice_a, twice_a_done = planted_command("c2", "/bin/cat /x/b.md")
    twice_b, twice_b_done = planted_command("c3", "/bin/cat /x/b.md")
    lines, lines_done = planted_command("c4", "/usr/bin/wc -l /x/a.md\n/usr/bin/true")
    late, late_done = planted_command("c5", "/bin/cat /x/late.md")
    cut = {"id": "m1", "type": "agent_message", "text": "PASS 1 FINDINGS\nP1-1 x"}
    message = {"id": "m2", "type": "agent_message",
               "text": "PASS 1 FINDINGS\nP1-1 x\nEND PASS 1: 1 finding"}
    good = planted_record([("item.started", spans), ("item.started", twice_a),
                           ("item.completed", twice_a_done), ("item.started", twice_b),
                           ("item.completed", twice_b_done), ("item.completed", cut),
                           ("item.started", lines), ("item.completed", lines_done),
                           ("item.completed", message), ("item.completed", spans_done),
                           ("item.started", late), ("item.completed", late_done)])
    record = analyse(good)
    if record.problems or record.boundary is None or record.boundary[1].id != "m2":
        probe("a planted readable record was misread: %r" % (record.problems[:3],))
    listed = [(item.id, item.events[0][2]["command"])
              for _, item in actions(record, "command_execution", True)]
    if listed != [("c1", spans["command"]), ("c2", twice_a["command"]),
                  ("c3", twice_b["command"]), ("c4", lines["command"])]:
        probe("the planted earlier commands were not listed whole, once each, in start order: %r"
              % listed)
    if [item.id for _, item in actions(record, "command_execution", False)] != ["c5"] \
            or [p[1] for p in record.passed_over] != ["m1"]:
        probe("a planted later command was listed, or a cut-off message was taken as a boundary")
    no_type = [json.dumps({"item": spans}).encode("utf-8")]
    damaged = (("an event with no type", good[:2] + no_type + good[2:]),
               ("a changed command", planted_record([
                   ("item.started", spans), ("item.completed", dict(spans_done,
                                                                    command="/bin/ls /y")),
                   ("item.completed", message)])),
               ("a cut record", good[:-1]),
               ("a torn last line", good[:-1] + [good[-1][:-5]]),
               ("an unfinished second turn", good + [b'{"type": "turn.started"}']),
               ("a whole second turn", good + [b'{"type": "turn.started"}',
                                               b'{"type": "turn.completed", "usage": {}}']),
               ("an unknown item type", planted_record([("item.completed", message), (
                   "item.completed", {"id": "r", "type": "reasoning", "text": "x"})])),
               ("a command event without its command text", planted_record([
                   ("item.started", dict(spans, command="")),
                   ("item.completed", dict(spans_done, command="")),
                   ("item.completed", message)])))
    for name, lines_of in damaged:
        if not analyse(lines_of).problems:
            probe("the event grammar read a planted damaged record whole (%s)" % name)
    none = analyse(planted_record([("item.started", spans), ("item.completed", spans_done),
                                   ("item.completed", dict(cut, text="## PASS 1 FINDINGS\nx"))]))
    if none.problems or none.boundary is not None or not none.near:
        probe("a planted record with no first-pass message was misread")
    # the third build review's pair: a literal escape-looking text beside a real escape, and the
    # reverse; then texts mixing backslashes, escapes and hidden characters, each of which must
    # print apart from the others and decode back to itself
    pair = ("/bin/echo \\x1b\x1b", "/bin/echo \x1b\\x1b")
    texts = pair + ("a\x1bb\u202ec\td", "\\", "\\\\", "\\x1b", "\x1b", "\\\x1b", "x\\u202e\u202e",
                    "\U000e0001\\U000e0001", "line 1\nline\x07 2\n")
    prints = [show_block(text) for text in texts]
    recovered = [decode("\n".join(row[len(INDENT):] for row in lines)) if escaped
                 else "\n".join(row[len(INDENT):] for row in lines) for lines, escaped in prints]
    plain = "/usr/bin/printf '%s\\n' \"a\\tb\"\tc"
    if len(set((tuple(lines), escaped) for lines, escaped in prints)) != len(texts) \
            or recovered != list(texts) or show_block(plain) != ([INDENT + plain], 0) \
            or prints[2] != ([INDENT + "a\\x1bb\\u202ec\td"], 2):
        probe("the lossless listing misread a plant: two texts printed alike, a print did not "
              "decode back to its text, or a text with nothing hidden was not printed byte for "
              "byte: %r" % (prints[:2],))
    return ("a planted record listed its 4 earlier commands whole, in start order (one begun "
            "before the message and finished after it, one text run twice and listed twice, one "
            "of two lines), passed over a cut-off heading message, and left its later command "
            "out; %d planted damaged records each gave could-not-read problems; a planted record "
            "with no first-pass message gave none and named its near miss; %d planted texts with "
            "hidden characters and backslashes (a literal escape-looking text beside a real one, "
            "and the reverse, among them) printed apart and each decoded back, and a text with "
            "nothing hidden printed byte for byte" % (len(damaged), len(texts)))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ProbeFailed("PROBE FAILED: bad arguments: %s (see --help)" % message)


def main(argv=None):
    parser = Parser(description="List every command the weekly audit's reviewer ran before its "
                                "first-pass message, verbatim, in the order each started, from "
                                "its run record, for the head to judge. It judges nothing and "
                                "writes nothing.")
    parser.add_argument("--events", required=True, metavar="PATH",
                        help="the reviewer's run record (its Codex event log)")
    parser.add_argument("--whole-run", action="store_true",
                        help="list the commands started after the first-pass message too, in a "
                             "list of their own (the smoke test on frozen copies)")
    try:
        args = parser.parse_args(argv)
        return report(os.path.abspath(os.path.expanduser(args.events)), args.whole_run)
    except ProbeFailed as failure:
        print(str(failure))
        return EXIT_PROBE


if __name__ == "__main__":
    sys.exit(main())
